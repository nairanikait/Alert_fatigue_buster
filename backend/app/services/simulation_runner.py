import datetime
import asyncio
import logging
import uuid
import json
from typing import Dict, Any, List, Optional, Set
from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, Base, engine
from app.core.events import ws_manager
from app.models.simulation import Simulation
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.notification import Notification
from app.services.normalization import normalize_generic
from app.services.alert_processor import process_alert

logger = logging.getLogger("alert_buster.simulation_runner")


class SimulationEvent:
    def __init__(self, seq: int, event_type: str, simulation_id: str, data: Dict[str, Any]):
        self.seq = seq
        self.type = event_type
        self.simulation_id = simulation_id
        self.timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        self.data = data

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "type": self.type,
            "simulation_id": self.simulation_id,
            "timestamp": self.timestamp,
            **self.data
        }


class SimulationRun:
    def __init__(self, simulation_id: str, scenario: str, target_count: int, speed: str = "normal", severity: str = "mixed"):
        self.simulation_id = simulation_id
        self.scenario = scenario
        self.target_count = target_count
        self.speed = speed
        self.severity = severity
        self.status = "RUNNING"  # RUNNING, COMPLETED, STOPPED, FAILED
        self.started_at = datetime.datetime.utcnow()
        self.completed_at: Optional[datetime.datetime] = None
        self.is_cancelled = False
        
        # Event sequence and history
        self.seq_counter = 0
        self.events: List[Dict[str, Any]] = []
        self.max_events = 2500  # retain event history for reconnection
        
        # Live counters
        self.counts = {
            "generated": 0,
            "total": target_count,
            "processed": 0,
            "suppressed": 0,
            "notifications": 0,
            "incidents": 0,
            "correlated": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "reduction_percentage": 0.0
        }
        
        # Summary
        self.summary: Optional[Dict[str, Any]] = None
        
        # Dedicated WebSocket clients for this simulation
        self.subscribers: Set[WebSocket] = set()

    def add_event(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        self.seq_counter += 1
        event = {
            "seq": self.seq_counter,
            "type": event_type,
            "simulation_id": self.simulation_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            **data
        }
        if len(self.events) < self.max_events:
            self.events.append(event)
        return event

    def to_metadata(self) -> Dict[str, Any]:
        elapsed = (datetime.datetime.utcnow() - self.started_at).total_seconds()
        if self.completed_at:
            elapsed = (self.completed_at - self.started_at).total_seconds()

        return {
            "simulation_id": self.simulation_id,
            "scenario": self.scenario,
            "status": self.status,
            "target_count": self.target_count,
            "speed": self.speed,
            "severity": self.severity,
            "started_at": self.started_at.isoformat() + "Z",
            "completed_at": self.completed_at.isoformat() + "Z" if self.completed_at else None,
            "elapsed_seconds": round(elapsed, 2),
            "counts": self.counts,
            "summary": self.summary
        }


class SimulationManager:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal
        self.active_simulation: Optional[SimulationRun] = None
        self.simulation_history: Dict[str, SimulationRun] = {}
        self.task: Optional[asyncio.Task] = None

    def get_simulation(self, simulation_id: str) -> Optional[SimulationRun]:
        return self.simulation_history.get(simulation_id)

    def get_active(self) -> Optional[SimulationRun]:
        if self.active_simulation and self.active_simulation.status == "RUNNING":
            return self.active_simulation
        return None

    async def broadcast_simulation_event(self, sim: SimulationRun, event: Dict[str, Any]):
        """Broadcasts simulation events directly to simulation WebSocket subscribers and global event bus."""
        # 1. Broadcast to dedicated simulation subscribers (live drawer)
        dead_sockets = set()
        for ws in list(sim.subscribers):
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                dead_sockets.add(ws)
        sim.subscribers.difference_update(dead_sockets)

        # 2. Broadcast to global dashboard WS only on milestones/completion to prevent network choking
        event_type = event.get("type")
        seq = event.get("seq", 0)
        if event_type in ["simulation.started", "simulation.completed", "simulation.stopped", "simulation.failed"] or (seq % 25 == 0):
            try:
                await ws_manager.broadcast("SIMULATION_EVENT", event)
            except Exception:
                pass

    async def start_simulation(
        self,
        scenario: str,
        count: Optional[int] = None,
        speed: str = "normal",
        severity: str = "mixed",
        force_stop_active: bool = False
    ) -> SimulationRun:
        # Check active simulation concurrency
        if self.active_simulation and self.active_simulation.status == "RUNNING":
            if force_stop_active:
                await self.stop_simulation(self.active_simulation.simulation_id)
            else:
                raise ValueError(
                    f"A simulation '{self.active_simulation.simulation_id}' is already running. "
                    f"Stop it first or pass force_stop_active=True."
                )

        # Determine target count
        normalized_scenario = scenario.lower().replace("-", "_")
        target_count = 500
        if normalized_scenario == "database_outage":
            target_count = 500
        elif normalized_scenario == "flaky_pod":
            target_count = 64
        elif normalized_scenario == "alert_storm":
            target_count = count or 500
        elif normalized_scenario in ["critical", "critical_emergency"]:
            target_count = 1
        elif normalized_scenario in ["cascade", "service_cascade"]:
            target_count = 280
        elif normalized_scenario == "recovery":
            target_count = 20
        else:
            target_count = count or 500

        # Unique simulation ID: sim_YYYYMMDD_HHMMSS_XXXX
        now_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        rand_suffix = uuid.uuid4().hex[:4]
        sim_id = f"sim_{now_str}_{rand_suffix}"

        sim = SimulationRun(
            simulation_id=sim_id,
            scenario=scenario,
            target_count=target_count,
            speed=speed,
            severity=severity
        )
        self.active_simulation = sim
        self.simulation_history[sim_id] = sim

        # Persist Simulation run to PostgreSQL / Database
        db = (self.session_factory or SessionLocal)()
        try:
            db_sim = Simulation(
                id=sim_id,
                scenario=scenario,
                status="RUNNING",
                total_alerts=target_count,
                processed_alerts=0,
                suppressed_alerts=0,
                notifications=0,
                reduction_percentage=0.0,
                speed=speed,
                severity=severity,
                start_time=sim.started_at
            )
            db.add(db_sim)
            db.commit()
        except Exception as e:
            logger.warning(f"Could not persist simulation record on start: {e}")
            db.rollback()
        finally:
            db.close()

        # Emit simulation.started
        start_event = sim.add_event("simulation.started", {
            "scenario": scenario,
            "target_count": target_count,
            "speed": speed,
            "counts": sim.counts
        })
        await self.broadcast_simulation_event(sim, start_event)

        # Launch background execution task
        self.task = asyncio.create_task(self._run_simulation_task(sim))
        return sim

    async def stop_simulation(self, simulation_id: str) -> bool:
        sim = self.get_simulation(simulation_id)
        if not sim or sim.status != "RUNNING":
            return False

        sim.is_cancelled = True
        sim.status = "STOPPED"
        sim.completed_at = datetime.datetime.utcnow()

        # Update Simulation in Database
        db = (self.session_factory or SessionLocal)()
        try:
            db_sim = db.query(Simulation).filter(Simulation.id == simulation_id).first()
            if db_sim:
                db_sim.status = "STOPPED"
                db_sim.completion_time = sim.completed_at
                db_sim.total_alerts = sim.counts.get("total", 0)
                db_sim.processed_alerts = sim.counts.get("processed", 0)
                db_sim.suppressed_alerts = sim.counts.get("suppressed", 0)
                db_sim.notifications = sim.counts.get("notifications", 0)
                db_sim.reduction_percentage = sim.counts.get("reduction_percentage", 0.0)
                db.commit()
        except Exception as e:
            logger.warning(f"Could not update simulation record on stop: {e}")
            db.rollback()
        finally:
            db.close()

        stop_event = sim.add_event("simulation.stopped", {
            "message": "Simulation halted by user request.",
            "counts": sim.counts
        })
        await self.broadcast_simulation_event(sim, stop_event)

        if self.task and not self.task.done():
            self.task.cancel()
        return True

    async def _run_simulation_task(self, sim: SimulationRun):
        """
        Executes the scenario generation loop progressively:
        Raw alert generated -> passes through central process_alert() pipeline -> emits real-time event.
        """
        logger.info(f"Starting simulation task {sim.simulation_id} for scenario: {sim.scenario}")
        
        # Velocity delay mapping
        delays = {
            "slow": 0.015,     # ~65 alerts/sec
            "normal": 0.003,   # ~300 alerts/sec
            "fast": 0.0005     # ~1000 alerts/sec
        }
        step_delay = delays.get(sim.speed, 0.003)

        db = (self.session_factory or SessionLocal)()
        try:
            raw_alerts = self._generate_scenario_alerts(sim)
            sim.target_count = len(raw_alerts)
            sim.counts["total"] = len(raw_alerts)

            for idx, raw in enumerate(raw_alerts):
                if sim.is_cancelled:
                    logger.info(f"Simulation {sim.simulation_id} was cancelled after {idx} alerts.")
                    break

                # Timestamp with exact millisecond precision
                event_time = datetime.datetime.utcnow()
                raw["timestamp"] = event_time
                raw["simulation_id"] = sim.simulation_id

                # 1. Normalize
                normalized = normalize_generic(raw)

                # 2. Process through real central pipeline with batched commits to eliminate network round-trip bottlenecks
                result = process_alert(db, normalized, auto_commit=False)
                
                # Batch commit every 20 alerts (or on the final alert)
                if (idx + 1) % 20 == 0 or (idx + 1) == len(raw_alerts):
                    try:
                        db.commit()
                    except Exception as e:
                        logger.warning(f"Batch commit at alert {idx + 1} warning: {e}")
                        db.rollback()

                action = result.get("action", "UNKNOWN")
                alert_dict = result.get("alert", {})
                incident_dict = result.get("incident")
                reason = result.get("reason") or alert_dict.get("suppression_reason") or ""
                
                # Update live counters
                sim.counts["generated"] += 1
                sim.counts["processed"] += 1

                sev = (alert_dict.get("severity") or raw.get("severity") or "medium").lower()
                if sev in sim.counts:
                    sim.counts[sev] += 1

                # Determine readable result status
                result_status = "received"
                if "SUPPRESSED_DUPLICATE" in action:
                    result_status = "duplicate"
                    sim.counts["suppressed"] += 1
                elif "SUPPRESSED_DOWNSTREAM" in action:
                    result_status = "correlated"
                    sim.counts["suppressed"] += 1
                    sim.counts["correlated"] += 1
                elif "SUPPRESSED_COOLDOWN" in action:
                    result_status = "cooldown"
                    sim.counts["suppressed"] += 1
                elif "BATCHED" in action:
                    result_status = "batched"
                    sim.counts["suppressed"] += 1
                elif "NOTIFIED" in action:
                    result_status = "notified"
                    sim.counts["notifications"] += 1
                elif "RESOLVED" in action:
                    result_status = "resolved"
                else:
                    if alert_dict.get("notification_status") == "SUPPRESSED":
                        result_status = "suppressed"
                        sim.counts["suppressed"] += 1
                    elif alert_dict.get("notification_status") == "SENT":
                        result_status = "notified"
                        sim.counts["notifications"] += 1

                if incident_dict:
                    sim.counts["incidents"] = max(sim.counts["incidents"], 1)

                if sim.counts["generated"] > 0:
                    sim.counts["reduction_percentage"] = round(
                        (sim.counts["suppressed"] / sim.counts["generated"]) * 100.0, 1
                    )

                # Emit alert.processed event
                event_data = {
                    "alert": {
                        "id": alert_dict.get("id", idx + 1),
                        "alert_name": raw.get("alert_name", "Alert"),
                        "service": raw.get("service", "unknown"),
                        "host": raw.get("host"),
                        "severity": (alert_dict.get("severity") or raw.get("severity", "medium")).upper(),
                        "severity_score": alert_dict.get("severity_score", 50.0),
                        "status": alert_dict.get("status", "FIRING"),
                        "source": raw.get("source", "generic"),
                        "fingerprint": raw.get("fingerprint", f"fp_{idx}"),
                        "message": raw.get("message", ""),
                        "labels": raw.get("labels", {}),
                        "timestamp": event_time.isoformat() + "Z"
                    },
                    "result": result_status,
                    "action": action,
                    "reason": reason,
                    "correlation_id": alert_dict.get("correlation_group_id") or (incident_dict.get("id") if incident_dict else None),
                    "incident_id": incident_dict.get("id") if incident_dict else None,
                    "notification_id": result.get("notification", {}).get("id"),
                    "counts": dict(sim.counts)
                }

                processed_event = sim.add_event("alert.processed", event_data)
                await self.broadcast_simulation_event(sim, processed_event)

                # Control progressive speed
                await asyncio.sleep(step_delay)

            if not sim.is_cancelled:
                sim.status = "COMPLETED"
                sim.completed_at = datetime.datetime.utcnow()
                
                # Fetch final summary directly from database
                total_incoming = db.query(Alert).count()
                notifications_sent = db.query(Notification).count()
                active_incidents = db.query(Incident).filter(Incident.status == "FIRING").count()
                
                sim.summary = {
                    "total_generated": sim.counts["generated"],
                    "total_processed": sim.counts["processed"],
                    "suppressed_count": sim.counts["suppressed"],
                    "notifications_dispatched": sim.counts["notifications"],
                    "incidents_created": sim.counts["incidents"] or active_incidents,
                    "reduction_percentage": sim.counts["reduction_percentage"],
                    "elapsed_seconds": round((sim.completed_at - sim.started_at).total_seconds(), 2),
                    "completed_at": sim.completed_at.isoformat() + "Z"
                }

                # Update Simulation record in database
                try:
                    db_sim = db.query(Simulation).filter(Simulation.id == sim.simulation_id).first()
                    if db_sim:
                        db_sim.status = "COMPLETED"
                        db_sim.completion_time = sim.completed_at
                        db_sim.total_alerts = sim.counts["total"]
                        db_sim.processed_alerts = sim.counts["processed"]
                        db_sim.suppressed_alerts = sim.counts["suppressed"]
                        db_sim.notifications = sim.counts["notifications"]
                        db_sim.reduction_percentage = sim.counts["reduction_percentage"]
                        db_sim.metadata_json = sim.summary
                        db.commit()
                except Exception as e:
                    logger.warning(f"Could not update simulation record on completion: {e}")
                    db.rollback()

                complete_event = sim.add_event("simulation.completed", {
                    "summary": sim.summary,
                    "counts": sim.counts
                })
                await self.broadcast_simulation_event(sim, complete_event)
                logger.info(f"Simulation {sim.simulation_id} finished successfully: {sim.summary}")

        except asyncio.CancelledError:
            logger.info(f"Simulation {sim.simulation_id} task was cancelled.")
        except Exception as e:
            logger.exception(f"Error in simulation task {sim.simulation_id}: {e}")
            sim.status = "FAILED"
            sim.completed_at = datetime.datetime.utcnow()
            try:
                db_sim = db.query(Simulation).filter(Simulation.id == sim.simulation_id).first()
                if db_sim:
                    db_sim.status = "FAILED"
                    db_sim.completion_time = sim.completed_at
                    db.commit()
            except Exception:
                db.rollback()
            fail_event = sim.add_event("simulation.failed", {
                "error": str(e),
                "counts": sim.counts
            })
            await self.broadcast_simulation_event(sim, fail_event)
        finally:
            db.close()

    def _generate_scenario_alerts(self, sim: SimulationRun) -> List[Dict[str, Any]]:
        scenario = sim.scenario.lower().replace("-", "_")
        base_time = datetime.datetime.utcnow()
        raw_alerts: List[Dict[str, Any]] = []

        if scenario == "database_outage":
            # 1. Primary Root Cause (T=0)
            raw_alerts.append({
                "source": "prometheus",
                "alert_name": "DatabaseDown",
                "service": "database",
                "host": "db-cluster-node-01",
                "environment": "production",
                "severity": "critical",
                "status": "firing",
                "message": "FATAL: Connection refused on postgres-primary:5432. All connections dropping.",
                "labels": {"cluster": "us-east-1", "tier": "storage"}
            })

            # 2. Payment Failure x 100
            for i in range(100):
                raw_alerts.append({
                    "source": "datadog",
                    "alert_name": "PaymentFailure",
                    "service": "payment-service",
                    "host": f"pay-pod-{(i % 4) + 1}",
                    "environment": "production",
                    "severity": "high",
                    "status": "firing",
                    "message": "Payment processing failed: DB connection timeout during transaction commit",
                    "labels": {"team": "payments"}
                })

            # 3. Order Failure x 150
            for i in range(150):
                raw_alerts.append({
                    "source": "prometheus",
                    "alert_name": "OrderFailure",
                    "service": "order-service",
                    "host": f"order-pod-{(i % 6) + 1}",
                    "environment": "production",
                    "severity": "high",
                    "status": "firing",
                    "message": "Could not persist customer order: database pool exhausted",
                    "labels": {"team": "orders"}
                })

            # 4. Authentication Failure x 100
            for i in range(100):
                raw_alerts.append({
                    "source": "datadog",
                    "alert_name": "AuthenticationFailure",
                    "service": "authentication-service",
                    "host": f"auth-pod-{(i % 3) + 1}",
                    "environment": "production",
                    "severity": "high",
                    "status": "firing",
                    "message": "JWT session validation timeout: unable to reach user credential store",
                    "labels": {"team": "security"}
                })

            # 5. API Unavailable x 149
            for i in range(149):
                raw_alerts.append({
                    "source": "generic",
                    "alert_name": "APIUnavailable",
                    "service": "api-gateway",
                    "host": f"edge-gw-{(i % 2) + 1}",
                    "environment": "production",
                    "severity": "medium",
                    "status": "firing",
                    "message": "HTTP 502 Bad Gateway: Upstream order and auth services unreachable",
                    "labels": {"team": "platform"}
                })

        elif scenario == "flaky_pod":
            for i in range(8):
                # 4 firing
                for b in range(4):
                    raw_alerts.append({
                        "source": "prometheus",
                        "alert_name": "PodRestarted",
                        "service": "order-service",
                        "host": "worker-k8s-node-4",
                        "environment": "production",
                        "severity": "medium",
                        "status": "firing",
                        "message": f"Pod order-service-worker-{i} crashed with OOMKilled, restarting container",
                        "labels": {"team": "orders", "flaky_cycle": str(i)}
                    })
                # 4 resolved
                for b in range(4):
                    raw_alerts.append({
                        "source": "prometheus",
                        "alert_name": "PodRestarted",
                        "service": "order-service",
                        "host": "worker-k8s-node-4",
                        "environment": "production",
                        "severity": "medium",
                        "status": "resolved",
                        "message": f"Pod order-service-worker-{i} back to Running state",
                        "labels": {"team": "orders", "flaky_cycle": str(i)}
                    })

        elif scenario in ["critical", "critical_emergency"]:
            raw_alerts.append({
                "source": "prometheus",
                "alert_name": "ProductionDatabaseDown",
                "service": "database",
                "host": "prod-master-db-01",
                "environment": "production",
                "severity": "critical",
                "status": "firing",
                "message": "EMERGENCY: Primary production database cluster unreachable. Immediate response required.",
                "labels": {"priority": "P1", "page": "immediate", "team": "sre"}
            })

        elif scenario in ["cascade", "service_cascade"]:
            cascade_steps = [
                {"service": "database", "alert": "DatabaseStorageExhausted", "severity": "critical", "msg": "Storage volume /data at 100% capacity on postgres-master", "count": 40},
                {"service": "payment-service", "alert": "PaymentTxCommitFailed", "severity": "high", "msg": "Payment ledger unable to persist transaction due to upstream DB disk full", "count": 60},
                {"service": "order-service", "alert": "OrderCheckoutTimeout", "severity": "high", "msg": "Order workflow timed out awaiting payment confirmation", "count": 60},
                {"service": "checkout", "alert": "CheckoutCartDropoff", "severity": "medium", "msg": "User cart submissions failing downstream order placement", "count": 60},
                {"service": "api-gateway", "alert": "Gateway504GatewayTimeout", "severity": "medium", "msg": "API gateway ingress dropping timed-out requests to checkout", "count": 60}
            ]
            for step in cascade_steps:
                for b in range(step["count"]):
                    raw_alerts.append({
                        "source": "prometheus",
                        "alert_name": step["alert"],
                        "service": step["service"],
                        "host": f"{step['service']}-pod-{(b % 3) + 1}",
                        "environment": "production",
                        "severity": step["severity"],
                        "status": "firing",
                        "message": step["msg"],
                        "labels": {"tier": step["service"]}
                    })

        elif scenario == "recovery":
            # Recovery signals
            services = ["database", "payment-service", "order-service", "authentication-service", "api-gateway"]
            alerts = ["DatabaseDown", "PaymentFailure", "OrderFailure", "AuthenticationFailure", "APIUnavailable"]
            for i in range(20):
                svc = services[i % len(services)]
                alt = alerts[i % len(alerts)]
                raw_alerts.append({
                    "source": "prometheus",
                    "alert_name": alt,
                    "service": svc,
                    "host": f"{svc}-host-01",
                    "environment": "production",
                    "severity": "low",
                    "status": "resolved",
                    "message": f"Service {svc} health check passed. Incident recovered.",
                    "labels": {"lifecycle": "auto-recovered"}
                })

        else:
            # Alert Storm (Default)
            target = min(max(sim.target_count, 50), 2000)
            services = ["payment-service", "order-service", "redis", "message-queue", "api-gateway", "database"]
            alerts = ["HighCPU", "HighMemory", "QueueBacklog", "SlowQueries", "CacheMissSpike", "NetworkLatency"]
            severities = ["critical", "high", "medium", "low"] if sim.severity == "mixed" else [sim.severity]
            
            for i in range(target):
                svc = services[i % len(services)]
                alt = alerts[i % len(alerts)]
                sev = severities[i % len(severities)]
                raw_alerts.append({
                    "source": "datadog" if i % 2 == 0 else "prometheus",
                    "alert_name": alt,
                    "service": svc,
                    "host": f"{svc}-node-{(i % 5) + 1}",
                    "environment": "production",
                    "severity": sev,
                    "status": "firing",
                    "message": f"Resource threshold breached on {svc} ({alt}: {85 + (i % 15)}% utilization)",
                    "labels": {"tier": svc, "batch_id": f"burst_{i // 25}"}
                })

        return raw_alerts


# Global singleton instance
simulation_manager = SimulationManager()
