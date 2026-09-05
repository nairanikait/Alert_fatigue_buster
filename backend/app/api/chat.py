import os
import json
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
import httpx

from app.core.config import settings
from app.core.database import get_db
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.notification import Notification
from app.models.service import Service, ServiceDependency
from app.models.system_rule import SystemRule
from app.services.gemini_service import (
    gemini_service,
    GeminiAuthenticationError,
    GeminiRateLimitError,
    GeminiServiceError,
)

logger = logging.getLogger("alert_buster.api.chat")
router = APIRouter(prefix="/chat", tags=["AI Chatbot"])


class ChatMessage(BaseModel):
    role: str = Field("user", description="Role: user, assistant, or system")
    content: str = Field(..., description="Message text")


class ChatContext(BaseModel):
    current_tab: Optional[str] = "dashboard"
    metrics: Optional[Dict[str, Any]] = None
    incidents: Optional[List[Dict[str, Any]]] = None
    recent_alerts: Optional[List[Dict[str, Any]]] = None
    selected_entity: Optional[Dict[str, Any]] = None
    topology_summary: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    message: str = Field(..., description="User question or prompt")
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Recent conversation history")
    context: Optional[ChatContext] = Field(None, description="Live system and page context")
    page_context: Optional[ChatContext] = Field(None, description="Alias for context")
    api_key: Optional[str] = Field(None, description="Optional user-provided API key from UI settings")
    provider: Optional[str] = Field("openai", description="Preferred provider: openai, gemini, or auto")
    model: Optional[str] = Field(None, description="Override LLM model name")


class ChatResponse(BaseModel):
    reply: str
    provider_used: str
    has_api_key: bool
    suggested_actions: List[str] = []


def _resolve_api_key(req_key: Optional[str], provider: str) -> tuple[Optional[str], str]:
    """
    Resolves API key from request payload, environment variables, or app settings.
    Returns (api_key, provider_name).
    """
    if req_key and req_key.strip():
        k = req_key.strip()
        p = "gemini" if (k.startswith("AIza") or provider == "gemini") else "openai"
        return k, p

    openai_key = os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
    gemini_key = os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)

    # Honor preferred provider if its key is configured
    if provider == "openai" and openai_key and str(openai_key).strip():
        return str(openai_key).strip(), "openai"
    if provider == "gemini" and gemini_key and str(gemini_key).strip():
        return str(gemini_key).strip(), "gemini"

    # Default to whichever key is present (OpenAI first for ultra-fast response, then Gemini)
    if openai_key and str(openai_key).strip():
        return str(openai_key).strip(), "openai"
    if gemini_key and str(gemini_key).strip():
        return str(gemini_key).strip(), "gemini"

    return None, "built-in"


def _gather_live_context(db: Session, client_context: Optional[ChatContext] = None) -> Dict[str, Any]:
    """
    Retrieves authoritative server-side facts directly from the database:
    - Live alert volumes and deduplication metrics
    - Real active/recent incidents, costs, and root causes
    - Real service inventory and multi-hop topology graph
    - Real recent alerts with suppression reasoning
    - Real active system policies
    """
    # 1. Real Live Metrics from DB
    total_incoming = db.query(func.coalesce(func.sum(Alert.occurrence_count), 0)).scalar() or 0
    unique_alerts = db.query(func.count(Alert.id)).scalar() or 0
    notifications_sent = db.query(func.count(Notification.id)).scalar() or 0
    suppressed_alerts = max(0, total_incoming - notifications_sent)
    reduction_percentage = round((1.0 - (notifications_sent / total_incoming)) * 100.0, 1) if total_incoming > 0 else 0.0

    # 2. Real Incidents from DB
    active_incidents = db.query(Incident).filter(Incident.status == "FIRING").order_by(Incident.created_at.desc()).all()
    all_incidents = db.query(Incident).order_by(Incident.created_at.desc()).limit(10).all()

    total_active_cost = sum(float(i.estimated_cost_loss or 0.0) for i in active_incidents)
    total_cumulative_cost = sum(float(i.estimated_cost_loss or 0.0) for i in all_incidents)

    # 3. Real Recent Alerts from DB
    recent_alerts = db.query(Alert).order_by(Alert.last_seen.desc()).limit(12).all()

    # 4. Real Services and Topology from DB
    services = db.query(Service).all()
    dependencies = db.query(ServiceDependency).all()
    
    # Build topology string
    dep_map: Dict[str, List[str]] = {}
    for d in dependencies:
        dep_map.setdefault(d.parent_service, []).append(d.child_service)
    
    topology_lines = []
    for parent, children in dep_map.items():
        topology_lines.append(f"{parent} -> {', '.join(children)}")
    if not topology_lines and services:
        topology_lines = [f"Registered services: {', '.join(s.id for s in services)} (no explicit edges configured)"]

    # 5. Real System Rules / Policies
    rules = {r.key: r.value for r in db.query(SystemRule).all()}

    # Merge client context tab/entity if present
    curr_tab = (client_context.current_tab if client_context else "dashboard") or "dashboard"
    selected_entity = client_context.selected_entity if client_context else None

    return {
        "current_tab": curr_tab,
        "selected_entity": selected_entity,
        "metrics": {
            "incoming_alerts": int(total_incoming),
            "unique_alerts": int(unique_alerts),
            "suppressed_alerts": int(suppressed_alerts),
            "notifications_sent": int(notifications_sent),
            "reduction_percentage": reduction_percentage,
            "active_incidents": len(active_incidents),
            "total_active_cost": total_active_cost,
            "total_cumulative_cost": total_cumulative_cost,
        },
        "active_incidents": [
            {
                "id": inc.id,
                "title": inc.title,
                "status": inc.status,
                "severity": inc.severity,
                "root_cause_service": inc.root_cause_service,
                "root_cause_alert_name": inc.root_cause_alert_name,
                "root_cause_reason": inc.root_cause_reason,
                "affected_services": inc.affected_services or [],
                "estimated_cost_loss": float(inc.estimated_cost_loss or 0.0),
                "created_at": inc.created_at.isoformat() if inc.created_at else None,
            }
            for inc in active_incidents
        ],
        "all_incidents": [
            {
                "id": inc.id,
                "title": inc.title,
                "status": inc.status,
                "severity": inc.severity,
                "root_cause_service": inc.root_cause_service,
                "root_cause_alert_name": inc.root_cause_alert_name,
                "root_cause_reason": inc.root_cause_reason,
                "affected_services": inc.affected_services or [],
                "estimated_cost_loss": float(inc.estimated_cost_loss or 0.0),
            }
            for inc in all_incidents
        ],
        "recent_alerts": [
            {
                "id": a.id,
                "alert_name": a.alert_name,
                "service": a.service,
                "severity": a.severity,
                "status": a.status,
                "occurrence_count": a.occurrence_count,
                "notification_status": a.notification_status,
                "suppression_reason": a.suppression_reason,
                "suppression_category": a.suppression_category,
                "fingerprint": a.fingerprint,
            }
            for a in recent_alerts
        ],
        "services": [s.to_dict() for s in services],
        "topology_lines": topology_lines,
        "rules": rules,
    }


def _build_system_prompt(live_ctx: Dict[str, Any]) -> str:
    """
    Assembles a comprehensive, grounded prompt containing live telemetry,
    current view, active incidents, costs, and topology for the LLM.
    """
    curr_tab = live_ctx.get("current_tab", "dashboard").capitalize()
    m = live_ctx.get("metrics", {})
    active_incidents = live_ctx.get("active_incidents", [])
    recent_alerts = live_ctx.get("recent_alerts", [])
    topology_lines = live_ctx.get("topology_lines", [])
    services = live_ctx.get("services", [])
    selected_entity = live_ctx.get("selected_entity")

    # Format Incidents
    incidents_summary = []
    for inc in active_incidents:
        cost = inc.get("estimated_cost_loss", 0.0)
        affected = ", ".join(inc.get("affected_services", []))
        incidents_summary.append(
            f"- Incident #{inc.get('id')}: {inc.get('title')} | Status: {inc.get('status')} | "
            f"Severity: {inc.get('severity', '').upper()} | Root Cause: {inc.get('root_cause_service')} "
            f"({inc.get('root_cause_alert_name')}) | Reason: {inc.get('root_cause_reason')} | "
            f"Blast Radius / Affected: [{affected}] | Live Outage Cost: ${cost:,.2f} USD"
        )

    # Format Alerts
    alerts_summary = []
    for a in recent_alerts[:8]:
        alerts_summary.append(
            f"- Alert #{a.get('id')}: '{a.get('alert_name')}' on service '{a.get('service')}' ({a.get('severity')}) -> "
            f"Status: {a.get('notification_status')} ({a.get('occurrence_count', 1)} occurrences). "
            f"Suppression: {a.get('suppression_reason') or 'None (Paged)'}"
        )

    # Selected Entity details
    selected_entity_str = ""
    if selected_entity:
        selected_entity_str = f"\nUSER CURRENTLY INSPECTING ENTITY: {json.dumps(selected_entity, indent=2)}\n"

    services_list_str = ", ".join(f"{s.get('id')} (criticality: {s.get('criticality', 50)})" for s in services) if services else "None"

    return f"""You are Zen, the Alert Buster SRE Copilot, an elite Site Reliability Engineering AI assistant built into the Alert Fatigue Buster platform.
You have real-time access to the live database, active incidents, telemetry metrics, multi-hop topology graph, and financial loss calculations.

=== LIVE TELEMETRY & SYSTEM STATE (SERVER AUTHORITATIVE) ===
CURRENT PAGE: {curr_tab}
• Active Firing Outage Incidents: {m.get('active_incidents', 0)}
• Active Live Outage Cost Loss: ${m.get('total_active_cost', 0.0):,.2f} USD
• Cumulative Total Outage Loss: ${m.get('total_cumulative_cost', 0.0):,.2f} USD
• Noise Reduction Rate: {m.get('reduction_percentage', 0.0)}%
• Total Raw Ingested Alerts: {m.get('incoming_alerts', 0)}
• Unique Deduplicated Alerts: {m.get('unique_alerts', 0)}
• Suppressed Noise Alarms: {m.get('suppressed_alerts', 0)}
• Actionable Notifications Dispatched: {m.get('notifications_sent', 0)}
{selected_entity_str}
ACTIVE INCIDENTS (DATABASE):
{chr(10).join(incidents_summary) if incidents_summary else "No active firing incidents. All systems are operational."}

RECENT ALERTS (DATABASE):
{chr(10).join(alerts_summary) if alerts_summary else "No recent alerts recorded."}

SERVICES INVENTORY:
{services_list_str}

LIVE TOPOLOGY GRAPH (DEPENDENCY EDGES):
{chr(10).join(topology_lines) if topology_lines else "No dependency edges configured."}

ALERTING POLICIES:
• Deduplication Window: 30 seconds (SHA-256 fingerprint matching)
• Burst Batch Digest Window: 10 seconds
• Alert Storm Cooldown Window: 300 seconds
• Critical Alerts Policy: Immediate dispatch, bypasses batching

=== BEHAVIOR RULES ===
1. GROUNDING IN LIVE FACTS: Use ONLY the live numbers, active incidents, services, and topology provided above. NEVER invent or hallucinate incidents, services, metrics, or alerts.
2. DISTINGUISH FACTS VS INFERENCES: Clearly distinguish between:
   - FACTS (real data retrieved from the platform)
   - INFERENCES (causal deductions based on graph topology and alert timestamps)
   - RECOMMENDATIONS (practical SRE remediation steps)
3. SRE RESPONSE FORMAT: When analyzing an incident or alert, structure your answer clearly with:
   - **Root Cause & Service**
   - **Affected Blast Radius**
   - **Causal Analysis / Why This Happened**
   - **Evidence (Metrics & Alerts)**
   - **Recommended SRE Remediation**
4. CASUAL & GENERAL CONVERSATION: If the user says "hello", "how are you", or asks general questions, respond naturally, warmly, and concisely without dumping unsolicited metrics.
5. NO UNAUTHORIZED MUTATIONS: You are a read-only observability assistant. You can explain, investigate, and recommend actions, but do not execute destructive changes.
6. API KEY CONFIGURATION: If asked where to configure API keys, explain that GEMINI_API_KEY or OPENAI_API_KEY can be placed in the `.env` file in the project root or configured via the Key icon in the chat UI.
7. Format all answers cleanly in GitHub Markdown with bold text, bullet points, and code blocks.
"""


def _fallback_context_response(user_msg: str, live_ctx: Dict[str, Any]) -> ChatResponse:
    """
    Deterministic rule-based SRE knowledge engine fallback that intelligently answers
    questions using strictly real server-side state when an external LLM API key has not been configured.
    """
    msg_lower = user_msg.lower().strip()
    curr_tab = live_ctx.get("current_tab", "dashboard")
    m = live_ctx.get("metrics", {})
    active_incidents = live_ctx.get("active_incidents", [])
    all_incidents = live_ctx.get("all_incidents", [])
    recent_alerts = live_ctx.get("recent_alerts", [])
    topology_lines = live_ctx.get("topology_lines", [])
    services = live_ctx.get("services", [])

    total_active_cost = m.get("total_active_cost", 0.0)
    active_inc_count = m.get("active_incidents", 0)
    reduction = m.get("reduction_percentage", 0.0)
    incoming = m.get("incoming_alerts", 0)
    sent = m.get("notifications_sent", 0)
    suppressed = m.get("suppressed_alerts", 0)

    # 1. CASUAL GREETINGS
    greeting_words = ["hi", "hello", "hey", "how are you", "good morning", "good evening", "what's up"]
    if any(g == msg_lower or msg_lower.startswith(g) or g in msg_lower for g in greeting_words) and not any(w in msg_lower for w in ["cost", "root cause", "outage", "topology", "alert", "incident", "noise", "reduction"]):
        status_note = f"System is currently operational with {active_inc_count} active incidents." if active_inc_count == 0 else f"⚠️ We currently have {active_inc_count} active outage incident(s) requiring attention."
        reply = (
            f"👋 Hello! I am **Zen**, your Alert Buster SRE Copilot (running in built-in deterministic mode).\n\n"
            f"{status_note}\n\n"
            f"I can help you analyze active incidents, inspect root causes, evaluate operational outage costs, "
            f"explain noise suppression policies, or explore the service dependency graph.\n\n"
            f"*Tip: To enable full generative AI reasoning with Google Gemini or OpenAI, insert your API key via the Key icon above or in `.env`.*"
        )
        suggestions = (
            ["Why is the active incident occurring?", "What is our total outage cost?", "Which services are affected?"]
            if active_inc_count > 0
            else ["Summarize current system health", "How much alert noise was reduced?", "Explain our deduplication & correlation policies"]
        )
        return ChatResponse(
            reply=reply,
            provider_used="built-in (SRE Engine)",
            has_api_key=False,
            suggested_actions=suggestions
        )

    # 2. API KEY QUESTIONS
    if any(w in msg_lower for w in ["api key", "llm key", "openai_api_key", "gemini_api_key", "insert", "where to put", "configure key"]):
        reply = (
            "### 🔑 How to Configure Your LLM API Key\n\n"
            "You can enable **Google Gemini** or **OpenAI** for generative SRE reasoning in two ways:\n\n"
            "#### Option 1: In the `.env` File (Recommended for Persistence)\n"
            "Add the following to the `.env` file in the project root:\n"
            "```env\n"
            "# Google Gemini API Key (Official google-genai SDK)\n"
            "GEMINI_API_KEY=AIzaSyYourGeminiApiKeyHere\n\n"
            "# OR OpenAI API Key\n"
            "OPENAI_API_KEY=sk-proj-your-openai-key-here\n"
            "```\n\n"
            "#### Option 2: Directly in this Chat Window\n"
            "Click the **Key icon (🔑)** in the top right of this chat window to paste your API key directly for this session.\n\n"
            "*Once configured, Alert Buster will dynamically use the configured LLM model with full live system context.*"
        )
        return ChatResponse(
            reply=reply,
            provider_used="built-in (SRE Engine)",
            has_api_key=False,
            suggested_actions=["What is our current system health?", "Explain noise reduction"]
        )

    # 3. COST / OUTAGE LOSS QUESTIONS
    if any(w in msg_lower for w in ["cost", "money", "loss", "burn rate", "financial", "dollar", "expensive", "lost"]):
        if active_incidents:
            inc_cost_lines = "\n**Active Outage Breakdown:**\n" + "\n".join(
                f"• **Incident #{inc.get('id')}: {inc.get('title')}** ({inc.get('severity', '').upper()}): "
                f"**${inc.get('estimated_cost_loss', 0.0):,.2f} USD** | Root Cause: `{inc.get('root_cause_service')}`"
                for inc in active_incidents
            )
            reply = (
                f"### 💰 Live Operational Outage Cost Analysis\n\n"
                f"• **Active Outage Financial Loss**: **${total_active_cost:,.2f} USD** across {len(active_incidents)} active incident(s).\n"
                f"• **Noise Reduction Savings**: **${suppressed * 50:,.2f} USD** preserved by eliminating redundant on-call pages (~$50/false page).\n"
                f"{inc_cost_lines}\n\n"
                f"#### Cost Loss Calculation Mechanics:\n"
                f"1. **Downtime Burn Rate**: Continuous rate based on incident severity (Critical = ~$65/sec).\n"
                f"2. **Blast Radius Multiplier**: Downstream cascaded services amplify overall operational impact.\n"
                f"3. **Triage Overhead**: Fixed mobilization baseline for incident war-rooms."
            )
            actions = [f"Why is {active_incidents[0].get('root_cause_service')} failing?", "Which services are in the blast radius?"]
        else:
            reply = (
                f"### 💰 Operational Outage Cost Analysis\n\n"
                f"• **Active Outage Financial Loss**: **$0.00 USD** (0 active outages currently firing).\n"
                f"• **Cumulative Historical Loss**: **${m.get('total_cumulative_cost', 0.0):,.2f} USD** across all recorded incidents.\n"
                f"• **Alert Noise Suppression Savings**: **${suppressed * 50:,.2f} USD** saved by suppressing {suppressed} redundant alerts.\n\n"
                f"All systems are operating normally within baseline cost bounds."
            )
            actions = ["Summarize current system health", "How much alert noise was reduced?"]

        return ChatResponse(
            reply=reply,
            provider_used="built-in (SRE Engine)",
            has_api_key=False,
            suggested_actions=actions
        )

    # 4. ROOT CAUSE & BLAST RADIUS QUESTIONS
    if any(w in msg_lower for w in ["root cause", "why", "failing", "down", "outage", "cascade", "blast radius", "cause", "affected"]):
        if active_incidents:
            primary = active_incidents[0]
            affected_str = ", ".join(f"`{s}`" for s in primary.get("affected_services", [])) or "None"
            reply = (
                f"### 🎯 Root Cause & Causal Analysis\n\n"
                f"• **Incident**: #{primary.get('id')} - {primary.get('title')}\n"
                f"• **Identified Root Cause Service**: **`{primary.get('root_cause_service')}`**\n"
                f"• **Triggering Alert**: `{primary.get('root_cause_alert_name')}`\n"
                f"• **Causal Explanation**: {primary.get('root_cause_reason')}\n"
                f"• **Downstream Blast Radius**: {affected_str}\n\n"
                f"#### Multi-Hop Correlation Analysis:\n"
                f"The correlation engine identified `{primary.get('root_cause_service')}` as the upstream root cause based on "
                f"the topological dependency hierarchy and earliest timestamp (T=0s). Downstream symptoms across "
                f"{affected_str} were suppressed and correlated under this single master incident."
            )
            actions = ["What is our total outage cost?", "How can we remediate this outage?"]
        else:
            reply = (
                "### 🎯 Root Cause & Causal Analysis\n\n"
                "• **Current Status**: **No active outage incidents** are currently firing in the system.\n"
                "• All monitored services are healthy and responsive.\n\n"
                "You can inspect the **Service Topology** page to review dependency connections, or use the **Simulator** "
                "to trigger a synthetic outage scenario."
            )
            actions = ["Summarize current system health", "Explain the service dependency graph"]

        return ChatResponse(
            reply=reply,
            provider_used="built-in (SRE Engine)",
            has_api_key=False,
            suggested_actions=actions
        )

    # 5. NOISE REDUCTION / SUPPRESSION QUESTIONS
    if any(w in msg_lower for w in ["noise", "reduction", "suppress", "filter", "percent", "how many alerts", "duplicate", "batch"]):
        reply = (
            f"### ⚡ Noise Reduction & Alert Compression\n\n"
            f"• **Noise Reduction Rate**: **{reduction}% reduction**\n"
            f"• **Total Raw Alerts Ingested**: **{incoming}** alarms\n"
            f"• **Unique Deduplicated Alerts**: **{m.get('unique_alerts', 0)}**\n"
            f"• **Suppressed Redundant Alerts**: **{suppressed}** alarms filtered\n"
            f"• **Actionable Notifications Dispatched**: **{sent}** paged\n\n"
            f"#### Alert Buster Suppression Architecture:\n"
            f"1. **Deduplication (30s window)**: Identical alarms sharing the same SHA-256 fingerprint increment a counter instead of spamming.\n"
            f"2. **Topological Multi-Hop Correlation**: Downstream cascade symptoms are linked to the upstream root cause.\n"
            f"3. **Burst Batching (10s digest)**: Non-critical alerts are aggregated into clean digests.\n"
            f"4. **Cooldown Suppression**: Repeated alerts during active outages are temporarily muted."
        )
        return ChatResponse(
            reply=reply,
            provider_used="built-in (SRE Engine)",
            has_api_key=False,
            suggested_actions=["What is our total outage cost?", "Which services are affected?"]
        )

    # 6. TOPOLOGY & SERVICES
    if any(w in msg_lower for w in ["topology", "dependency", "graph", "services", "upstream", "downstream", "hops"]):
        topo_formatted = "\n".join(f"• `{line}`" for line in topology_lines) if topology_lines else "• No active dependency edges."
        svcs_str = ", ".join(f"`{s.get('id')}`" for s in services) if services else "None"
        reply = (
            f"### 🗺️ Live Service Topology & Dependencies\n\n"
            f"**Registered Monitored Services ({len(services)}):**\n"
            f"{svcs_str}\n\n"
            f"**Active Dependency Edges (Parent -> Downstream Children):**\n"
            f"{topo_formatted}\n\n"
            f"The correlation engine performs breadth-first multi-hop graph traversal to correlate alerts across arbitrary depth."
        )
        return ChatResponse(
            reply=reply,
            provider_used="built-in (SRE Engine)",
            has_api_key=False,
            suggested_actions=["Which services are affected right now?", "Explain root cause analysis"]
        )

    # 7. SYSTEM HEALTH / DEFAULT PAGE CONTEXT
    page_explanations = {
        "dashboard": "The **Executive Dashboard** displays overall noise reduction KPIs, alert volume time series, severity distribution, and active outage incident summaries.",
        "alerts": "The **Alerts Feed** provides real-time visibility into all ingested alerts, occurrence counts, fingerprint hashes, and exact suppression reasons.",
        "incidents": "The **Incidents View** groups correlated alerts into unified outage records with root-cause identification, blast radiuses, and live financial downtime loss calculations.",
        "rootcause": "The **Causal Graph** visualizes multi-hop dependency relationships and failure cascades.",
        "topology": "The **Service Topology** view allows real-time management and visual graph editing of services and runtime dependencies.",
        "notifications": "The **Notification Feed** logs all dispatches sent to external notification channels (PagerDuty, Slack, Email).",
        "rules": "The **Rules & Policies Editor** configures deduplication windows (30s), batch windows (10s), cooldown timers, and channel routing.",
        "demo": "The **Simulator** enables triggering realistic synthetic scenarios (Database Outage, Flaky Pod, Alert Storm, Cascades, Recovery) to test noise reduction."
    }

    curr_desc = page_explanations.get(curr_tab.lower(), "Live operational telemetry view.")
    reply = (
        f"### ℹ️ Live System Health Summary ({curr_tab.capitalize()} View)\n\n"
        f"{curr_desc}\n\n"
        f"**Authoritative System State:**\n"
        f"• **Active Outage Incidents**: {active_inc_count}\n"
        f"• **Live Outage Cost Loss**: ${total_active_cost:,.2f} USD\n"
        f"• **Noise Reduction**: {reduction}% ({incoming} raw alerts → {sent} notifications dispatched)\n"
        f"• **Monitored Services**: {len(services)} registered services\n\n"
        f"*Ask me any question regarding active outages, root causes, noise reduction, or service dependencies!*"
    )
    return ChatResponse(
        reply=reply,
        provider_used="built-in (SRE Engine)",
        has_api_key=False,
        suggested_actions=(
            ["Why is the active incident occurring?", "What is our total outage cost?"]
            if active_inc_count > 0
            else ["How much alert noise was reduced?", "Explain the service dependency graph", "Where do I insert my LLM API key?"]
        )
    )


@router.post("", response_model=ChatResponse, summary="Context-aware AI SRE Chatbot query")
async def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    # 1. Gather authoritative live server-side context from the database
    client_ctx = req.context or req.page_context
    live_ctx = _gather_live_context(db, client_ctx)
    
    # 2. Resolve API Key and provider
    api_key, provider = _resolve_api_key(req.api_key, req.provider or "openai")
    
    # 3. If no API key is available, use our built-in context-aware SRE knowledge engine
    if not api_key:
        return _fallback_context_response(req.message, live_ctx)

    # 4. Gemini Provider (via official google-genai SDK)
    if provider == "gemini":
        model_name = req.model or gemini_service.DEFAULT_MODEL
        system_prompt = _build_system_prompt(live_ctx)

        history_list = [
            {"role": hist.role, "content": hist.content}
            for hist in (req.history or [])[-8:]
        ]

        try:
            reply_text = await gemini_service.async_generate_chat_response(
                prompt=req.message,
                system_instruction=system_prompt,
                history=history_list,
                model=model_name,
                override_key=api_key,
            )
            suggested = (
                ["What is our total outage cost?", "Explain the blast radius"]
                if live_ctx.get("metrics", {}).get("active_incidents", 0) > 0
                else ["Summarize current system health", "How much alert noise was reduced?"]
            )
            return ChatResponse(
                reply=reply_text,
                provider_used=f"Google Gemini ({model_name})",
                has_api_key=True,
                suggested_actions=suggested
            )
        except GeminiAuthenticationError as e:
            logger.error("Gemini authentication error: %s", e)
            fallback = _fallback_context_response(req.message, live_ctx)
            fallback.reply = f"⚠️ *Gemini API Authentication Failed (Invalid GEMINI_API_KEY). Operating in built-in SRE engine mode:*\n\n" + fallback.reply
            return fallback
        except GeminiRateLimitError as e:
            logger.warning("Gemini rate limit error: %s", e)
            fallback = _fallback_context_response(req.message, live_ctx)
            fallback.reply = f"⚠️ *Gemini API rate limit exceeded. Operating in built-in SRE engine mode:*\n\n" + fallback.reply
            return fallback
        except Exception as e:
            logger.warning("Error querying Gemini API: %s", e)
            fallback = _fallback_context_response(req.message, live_ctx)
            fallback.reply = f"⚠️ *Could not reach Gemini API ({str(e)}). Operating in built-in SRE engine mode:*\n\n" + fallback.reply
            return fallback

    # 5. OpenAI Provider
    elif provider == "openai":
        model_name = req.model or getattr(settings, "LLM_MODEL", None) or "gpt-4o-mini"
        system_prompt = _build_system_prompt(live_ctx)
        
        messages = [{"role": "system", "content": system_prompt}]
        for hist in (req.history or [])[-8:]:
            messages.append({"role": hist.role, "content": hist.content})
        messages.append({"role": "user", "content": req.message})

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model_name,
                        "messages": messages,
                        "temperature": 0.2,
                        "max_tokens": 900
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    reply_text = data["choices"][0]["message"]["content"]
                    suggested = (
                        ["What is our total outage cost?", "Explain the blast radius"]
                        if live_ctx.get("metrics", {}).get("active_incidents", 0) > 0
                        else ["Summarize current system health", "How much alert noise was reduced?"]
                    )
                    return ChatResponse(
                        reply=reply_text,
                        provider_used=f"OpenAI ({model_name})",
                        has_api_key=True,
                        suggested_actions=suggested
                    )
                else:
                    logger.warning("OpenAI API returned status %s: %s", res.status_code, res.text)
                    fallback = _fallback_context_response(req.message, live_ctx)
                    fallback.reply = f"⚠️ *OpenAI API returned status {res.status_code}. Operating in built-in SRE engine mode:*\n\n" + fallback.reply
                    return fallback
        except Exception as e:
            logger.warning("Error querying OpenAI API: %s", e)
            fallback = _fallback_context_response(req.message, live_ctx)
            fallback.reply = f"⚠️ *Could not reach OpenAI API ({str(e)}). Operating in built-in SRE engine mode:*\n\n" + fallback.reply
            return fallback

    return _fallback_context_response(req.message, live_ctx)


@router.get("/gemini-test", summary="Test Gemini API connectivity via official SDK")
def test_gemini_endpoint():
    """
    Validates that the Gemini API is reachable using the official google-genai SDK
    and the GEMINI_API_KEY environment variable.
    """
    return gemini_service.test_connection()


@router.get("/status", summary="Check LLM API key configuration status")
def get_chat_status():
    has_gemini = gemini_service.is_configured()
    has_openai = bool(os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None))
    configured = has_gemini or has_openai
    provider = "gemini" if has_gemini else ("openai" if has_openai else "none")

    return {
        "configured": configured,
        "provider": provider,
        "gemini_configured": has_gemini,
        "gemini_sdk": "google-genai",
        "gemini_model": gemini_service.DEFAULT_MODEL,
        "openai_configured": has_openai,
        "instructions": "Set GEMINI_API_KEY or OPENAI_API_KEY in the .env file in the project root or configure in UI."
    }
