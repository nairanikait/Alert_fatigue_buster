import logging
import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, Field

from app.services.simulation_runner import simulation_manager

logger = logging.getLogger("alert_buster.api_simulations")
router = APIRouter(prefix="/simulations", tags=["Simulations"])


class StartSimulationRequest(BaseModel):
    scenario: str = Field(..., description="Scenario identifier: database_outage, flaky_pod, alert_storm, critical_emergency, service_cascade, recovery")
    count: Optional[int] = Field(None, description="Alert count override")
    speed: Optional[str] = Field("normal", description="Simulation speed: slow, normal, fast")
    severity: Optional[str] = Field("mixed", description="Severity filter: mixed, critical, high, medium, low")
    force_stop_active: Optional[bool] = Field(False, description="Whether to stop an ongoing simulation before starting this one")


@router.post("", summary="Start a new streaming simulation")
async def start_simulation_endpoint(req: StartSimulationRequest):
    try:
        sim = await simulation_manager.start_simulation(
            scenario=req.scenario,
            count=req.count,
            speed=req.speed or "normal",
            severity=req.severity or "mixed",
            force_stop_active=req.force_stop_active or False
        )
        return {
            "simulation_id": sim.simulation_id,
            "scenario": sim.scenario,
            "target_count": sim.target_count,
            "status": sim.status,
            "speed": sim.speed,
            "started_at": sim.started_at.isoformat() + "Z"
        }
    except ValueError as ve:
        # 409 Conflict if simulation already running
        active = simulation_manager.get_active()
        active_meta = active.to_metadata() if active else None
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(ve),
                "active_simulation": active_meta
            }
        )
    except Exception as e:
        logger.exception("Failed to start simulation: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", summary="Get currently running simulation")
async def get_active_simulation():
    active = simulation_manager.get_active()
    if not active:
        return {"active": False, "simulation": None}
    return {
        "active": True,
        "simulation": active.to_metadata()
    }


@router.get("/{simulation_id}", summary="Get simulation metadata and live counters")
async def get_simulation_status(simulation_id: str):
    sim = simulation_manager.get_simulation(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found.")
    return sim.to_metadata()


@router.get("/{simulation_id}/events", summary="Get event history for reconnection and replay")
async def get_simulation_events(
    simulation_id: str,
    since_seq: Optional[int] = Query(0, description="Retrieve events after this sequence number"),
    limit: Optional[int] = Query(1000, description="Maximum number of events to return")
):
    sim = simulation_manager.get_simulation(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found.")

    filtered_events = [e for e in sim.events if e.get("seq", 0) > (since_seq or 0)]
    if limit and len(filtered_events) > limit:
        filtered_events = filtered_events[-limit:]

    return {
        "simulation_id": simulation_id,
        "status": sim.status,
        "total_events": len(sim.events),
        "returned_events": len(filtered_events),
        "events": filtered_events,
        "counts": sim.counts
    }


@router.get("/{simulation_id}/summary", summary="Get simulation final summary")
async def get_simulation_summary(simulation_id: str):
    sim = simulation_manager.get_simulation(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found.")
    return {
        "simulation_id": simulation_id,
        "scenario": sim.scenario,
        "status": sim.status,
        "counts": sim.counts,
        "summary": sim.summary
    }


@router.post("/{simulation_id}/stop", summary="Stop an active simulation")
async def stop_simulation_endpoint(simulation_id: str):
    stopped = await simulation_manager.stop_simulation(simulation_id)
    if not stopped:
        sim = simulation_manager.get_simulation(simulation_id)
        if not sim:
            raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found.")
        return {"status": sim.status, "message": f"Simulation is already in status '{sim.status}'."}
    return {"status": "STOPPED", "message": f"Simulation '{simulation_id}' stopped."}


# Dedicated WebSocket endpoint for simulation streaming
async def handle_simulation_ws(websocket: WebSocket, simulation_id: str):
    await websocket.accept()
    sim = simulation_manager.get_simulation(simulation_id)
    if not sim:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Simulation '{simulation_id}' not found."
        }))
        await websocket.close()
        return

    sim.subscribers.add(websocket)
    logger.info(f"WebSocket client connected to simulation stream: {simulation_id} (subscribers: {len(sim.subscribers)})")

    # Send initial state sync event
    initial_sync = {
        "type": "simulation.sync",
        "simulation_id": sim.simulation_id,
        "scenario": sim.scenario,
        "status": sim.status,
        "counts": sim.counts,
        "summary": sim.summary
    }
    await websocket.send_text(json.dumps(initial_sync))

    try:
        while True:
            # Keep connection alive, listen for ping/heartbeat
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text('{"type": "pong"}')
            elif msg.startswith("stop"):
                await simulation_manager.stop_simulation(simulation_id)
    except WebSocketDisconnect:
        sim.subscribers.discard(websocket)
        logger.info(f"WebSocket client disconnected from simulation {simulation_id}")
    except Exception as e:
        logger.warning(f"WebSocket error in simulation {simulation_id}: {e}")
        sim.subscribers.discard(websocket)
