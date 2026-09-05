"""
AI-Powered Incident Solution / AI SRE Copilot Service.
Analyzes the FINAL correlated incident using live evidence, topology graph,
and suppression details to generate structured, actionable SRE recommendations.

Strict Security:
- Never includes secrets, credentials, API keys, or webhooks in prompts.
- All LLM calls execute strictly server-side.
- Isolated failure: If LLM is unreachable or errors, returns safe deterministic fallback.
"""

import os
import json
import logging
import datetime
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.incident import Incident
from app.models.alert import Alert
from app.models.service import Service, ServiceDependency
from app.services.gemini_service import (
    gemini_service,
    GeminiAuthenticationError,
    GeminiRateLimitError,
    GeminiServiceError,
)

logger = logging.getLogger("alert_buster.services.ai_incident_copilot")

# Strict Schema required for AI Incident Analysis
EXPECTED_KEYS = [
    "summary",
    "root_cause_explanation",
    "correlation_explanation",
    "suppression_explanation",
    "immediate_mitigation",
    "investigation_steps",
    "long_term_prevention",
    "potential_impact",
    "confidence",
    "risk_level",
]


def build_incident_context(db: Session, incident: Incident) -> Dict[str, Any]:
    """
    Constructs clean, structured incident context based exclusively on real database facts.
    Guaranteed NEVER to leak secrets, tokens, or environment credentials.
    """
    # 1. Correlated alerts for this incident
    alerts = (
        db.query(Alert)
        .filter(Alert.correlation_group_id == incident.id)
        .order_by(Alert.first_seen.asc())
        .all()
    )

    alert_names = list(dict.fromkeys([a.alert_name for a in alerts if a.alert_name]))
    services_seen = list(dict.fromkeys([a.service for a in alerts if a.service]))
    
    # Identify suppressed samples vs firing/sent
    suppressed_examples = []
    for a in alerts:
        if a.notification_status == "SUPPRESSED" or a.status == "BATCHED":
            desc = f"{a.alert_name} on {a.service}"
            if desc not in suppressed_examples:
                suppressed_examples.append(desc)
        if len(suppressed_examples) >= 6:
            break

    # 2. Dependency relationships between affected services
    deps = db.query(ServiceDependency).all()
    all_affected = set(incident.affected_services or []) | set(services_seen) | {incident.root_cause_service}
    
    dependency_relationships = []
    for d in deps:
        if d.parent_service in all_affected or d.child_service in all_affected:
            rel = f"{d.parent_service} -> {d.child_service}"
            if rel not in dependency_relationships:
                dependency_relationships.append(rel)

    # 3. Timeline
    timeline = []
    if incident.created_at:
        timeline.append(f"Incident triggered at {incident.created_at.isoformat()}Z")
    if alerts:
        first_alert = alerts[0]
        timeline.append(
            f"T=0: Earliest alarm '{first_alert.alert_name}' fired on '{first_alert.service}'"
        )
        if len(alerts) > 1:
            last_alert = alerts[-1]
            timeline.append(
                f"T+{int(incident.duration_seconds or 30)}s: Latest cascading alarm '{last_alert.alert_name}' on '{last_alert.service}'"
            )

    # Clean, strictly safe context dictionary
    context = {
        "incident_id": str(incident.id),
        "title": str(incident.title or "Infrastructure Outage"),
        "severity": str(incident.severity or "HIGH").upper(),
        "affected_service": str(incident.root_cause_service or "unknown-service"),
        "root_cause_alert": str(incident.root_cause_alert_name or "UnknownAlarm"),
        "root_cause_reason": str(incident.root_cause_reason or "Identified via topology traversal"),
        "correlated_alert_count": int(incident.alert_count or len(alerts)),
        "suppressed_alert_count": int(incident.suppressed_count or max(0, len(alerts) - 1)),
        "affected_services": sorted(list(all_affected)),
        "correlated_alerts": alert_names[:10],
        "suppressed_alert_examples": suppressed_examples,
        "dependency_relationships": dependency_relationships[:12],
        "timeline": timeline,
        "confidence_score": float(incident.confidence_score or 90.0),
    }

    return context


def build_system_instruction() -> str:
    """
    Returns the system prompt instructing the AI to act as an elite SRE.
    """
    return """You are an elite Site Reliability Engineering (SRE) Incident Response Copilot.
Your job is to analyze the FINAL CORRELATED INCIDENT and prescribe actionable, precise incident-resolution guidance.

BEHAVIORAL RULES:
1. REASON FROM EVIDENCE: Base your analysis solely on the provided incident context (services, topology, alert timestamps, root cause).
2. DISTINGUISH ROOT CAUSE FROM SYMPTOMS: The root cause service/alert triggered first; downstream alerts are cascading symptoms.
3. EXPLAIN CORRELATION: Explain clearly why these alerts belong together based on the dependency graph and temporal sequence.
4. EXPLAIN SUPPRESSION: Explain why redundant alerts were suppressed (e.g. duplicate alarms, downstream cascades). Mention actual alert examples.
5. THREE SEPARATED RECOMMENDATION LEVELS:
   - IMMEDIATE MITIGATION: Safe, tactical steps the engineer should investigate or do right now to stabilize or triage the system.
   - INVESTIGATION: Exact diagnostic commands/queries, logs, deployment checks, or baseline comparisons to confirm diagnosis.
   - LONG-TERM PREVENTION: Architectural fixes, circuit breakers, pool sizing, query timeouts, or alerts to prevent recurrence.
6. SAFE RECOMMENDATIONS: DO NOT generate destructive or blind terminal commands (e.g. NEVER suggest rm -rf, DROP TABLE, or rebooting production databases without failover).
7. POTENTIAL IMPACT: Clearly explain consequences if left unresolved (e.g. cascading queue saturation, payment timeouts). Do not fabricate exact monetary losses unless provided.
8. CONFIDENCE: Report an integer confidence percentage between 70 and 99 that aligns with evidence clarity.
9. UNCERTAINTY: If evidence is insufficient, explicitly state: "Insufficient evidence to confidently determine the root cause."
10. STRICT JSON OUTPUT: You MUST respond ONLY with a single valid JSON object matching the requested schema. No conversational filler, no markdown code blocks enclosing the JSON.
"""


def build_analysis_prompt(ctx: Dict[str, Any]) -> str:
    """
    Assembles the incident payload prompt for the LLM.
    """
    return f"""Analyze this final correlated incident and return a JSON object:

INCIDENT CONTEXT:
{json.dumps(ctx, indent=2)}

OUTPUT SCHEMA (JSON ONLY):
{{
  "summary": "Concise 1-2 sentence overview of what happened and the direct impact.",
  "root_cause_explanation": "Detailed explanation of the root cause and initial failure point.",
  "correlation_explanation": "Clear explanation of why the alerts were grouped together via dependency relationships.",
  "suppression_explanation": "Clear explanation of why downstream/duplicate alerts were suppressed to protect on-call engineers, referencing specific alert names.",
  "immediate_mitigation": [
    "Step 1: Immediate action to stabilize or triage...",
    "Step 2: Immediate check...",
    "Step 3: Immediate mitigation..."
  ],
  "investigation_steps": [
    "Step 1: Metric or log to inspect...",
    "Step 2: Deployment or configuration check...",
    "Step 3: Baseline comparison..."
  ],
  "long_term_prevention": [
    "Step 1: Architectural or monitoring improvement...",
    "Step 2: Capacity or timeout policy...",
    "Step 3: Guardrail or automation..."
  ],
  "potential_impact": "What happens if this issue remains unresolved over time.",
  "confidence": {int(ctx.get('confidence_score', 94))},
  "risk_level": "{ctx.get('severity', 'HIGH')}",
  "technical_reasoning": [
    "Evidence: Primary alarm '{ctx.get('root_cause_alert')}' on service '{ctx.get('affected_service')}' fired at T=0",
    "Evidence: Evaluated topological dependencies across {len(ctx.get('affected_services', []))} affected services",
    "Evidence: Downstream cascade suppressed {ctx.get('suppressed_alert_count', 0)} redundant symptom alarms"
  ]
}}
"""


def _clean_json_text(text: str) -> str:
    """Removes markdown code block backticks if present."""
    t = text.strip()
    if t.startswith("```json"):
        t = t[7:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def validate_and_normalize_ai_response(
    data: Dict[str, Any],
    ctx: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validates that the AI response contains all required fields and correct types.
    Fills in safe defaults if any field is missing or malformed.
    """
    summary = str(data.get("summary") or f"Incident rooted at {ctx.get('affected_service')} causing cascading downstream alarms.")
    root_cause_explanation = str(data.get("root_cause_explanation") or ctx.get("root_cause_reason") or "Root cause identified via dependency graph.")
    correlation_explanation = str(
        data.get("correlation_explanation") or 
        f"Alerts across {', '.join(ctx.get('affected_services', [])[:4])} occurred in close temporal proximity and are connected through service topology."
    )
    suppression_explanation = str(
        data.get("suppression_explanation") or 
        f"{ctx.get('suppressed_alert_count', 0)} alerts were identified as duplicate or downstream symptoms of the primary root cause."
    )

    immediate_mitigation = data.get("immediate_mitigation")
    if not isinstance(immediate_mitigation, list) or not immediate_mitigation:
        immediate_mitigation = [
            f"Verify operational health and connection saturation on service '{ctx.get('affected_service')}'.",
            "Check recent deployment diffs or configuration updates on the root-cause service.",
            "Inspect resource utilization (CPU, memory, connection limits) on the affected infrastructure.",
        ]

    investigation_steps = data.get("investigation_steps")
    if not isinstance(investigation_steps, list) or not investigation_steps:
        investigation_steps = [
            f"Inspect error logs and slow traces on '{ctx.get('affected_service')}'.",
            "Compare current error rates against the 7-day operational baseline.",
            "Verify latency thresholds and timeouts on downstream connected services.",
        ]

    long_term_prevention = data.get("long_term_prevention")
    if not isinstance(long_term_prevention, list) or not long_term_prevention:
        long_term_prevention = [
            f"Implement automated circuit breakers between downstream clients and '{ctx.get('affected_service')}'.",
            "Configure proactive early-warning alert thresholds before capacity saturation.",
            "Establish automated chaos tests to validate graceful failure degradation.",
        ]

    potential_impact = str(
        data.get("potential_impact") or 
        f"Continued failure in '{ctx.get('affected_service')}' may cause timeouts and availability degradation across dependent downstream services."
    )

    confidence = data.get("confidence")
    try:
        confidence = int(float(confidence))
        if confidence < 1 or confidence > 100:
            confidence = int(ctx.get("confidence_score", 94))
    except (ValueError, TypeError):
        confidence = int(ctx.get("confidence_score", 94))

    risk_level = str(data.get("risk_level") or ctx.get("severity") or "HIGH").upper()
    if risk_level not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        risk_level = "HIGH"

    technical_reasoning = data.get("technical_reasoning")
    if not isinstance(technical_reasoning, list) or not technical_reasoning:
        technical_reasoning = [
            f"Evaluated root cause alert: {ctx.get('root_cause_alert')} ({ctx.get('affected_service')})",
            f"Topological dependency cascade across: {', '.join(ctx.get('affected_services', []))}",
            f"Correlated {ctx.get('correlated_alert_count', 0)} signals and suppressed {ctx.get('suppressed_alert_count', 0)} duplicates/symptoms",
            "Temporal alignment: alarms fired within 15-second multi-hop correlation window",
        ]

    return {
        "summary": summary,
        "root_cause_explanation": root_cause_explanation,
        "correlation_explanation": correlation_explanation,
        "suppression_explanation": suppression_explanation,
        "immediate_mitigation": [str(x) for x in immediate_mitigation],
        "investigation_steps": [str(x) for x in investigation_steps],
        "long_term_prevention": [str(x) for x in long_term_prevention],
        "potential_impact": potential_impact,
        "confidence": confidence,
        "risk_level": risk_level,
        "technical_reasoning": [str(x) for x in technical_reasoning],
        "analyzed_at": datetime.datetime.utcnow().isoformat() + "Z",
        "provider": data.get("provider", "built-in SRE engine"),
    }


def generate_deterministic_sre_analysis(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic rule-based SRE engine fallback.
    Produces highly realistic, grounded SRE incident guidance using only real incident context
    when external LLM APIs are unreachable, unconfigured, or timing out.
    """
    service = ctx.get("affected_service", "database")
    root_alert = ctx.get("root_cause_alert", "ConnectionExhausted")
    reason = ctx.get("root_cause_reason", "Identified via topology traversal")
    affected = ctx.get("affected_services", [])
    suppressed_count = ctx.get("suppressed_alert_count", 0)
    suppressed_examples = ctx.get("suppressed_alert_examples", [])
    severity = ctx.get("severity", "HIGH")

    suppressed_str = (
        f"{suppressed_count} alerts were identified as duplicate or downstream symptoms of the same incident (including {', '.join(suppressed_examples[:3])})."
        if suppressed_examples
        else f"{suppressed_count} alerts were identified as duplicate or downstream symptoms of the same incident."
    )

    data = {
        "summary": f"{severity} severity incident on '{service}' triggered by '{root_alert}', affecting {len(affected)} services.",
        "root_cause_explanation": f"The primary failure originated on '{service}' with alarm '{root_alert}'. {reason}",
        "correlation_explanation": f"Downstream services ({', '.join(affected[:4])}) experienced failures due to direct or transitive topological dependency on '{service}' during the outage window.",
        "suppression_explanation": suppressed_str,
        "immediate_mitigation": [
            f"Inspect current active connection utilization and resource saturation on '{service}'.",
            f"Identify long-running blocking queries or stalled transactions on '{service}'.",
            f"Verify if horizontal scaling, pool recycling, or worker pod restarts relieve pressure on '{service}'.",
        ],
        "investigation_steps": [
            f"Inspect slow query logs and error traces on '{service}' around the time of the initial alarm.",
            "Compare current traffic throughput against baseline levels to verify if this was caused by a sudden traffic surge.",
            "Check recent git deployments or configuration flag updates for all affected services.",
        ],
        "long_term_prevention": [
            f"Implement connection pool saturation alerts and strict client-side timeout policies for '{service}'.",
            "Introduce circuit breakers with exponential backoff on downstream consumers to prevent cascading stampedes.",
            "Establish automated health-check degradation drills to ensure graceful degradation during upstream outages.",
        ],
        "potential_impact": f"Continued failure on '{service}' will cause cascading request timeouts and error rate spikes across downstream clients ({', '.join(affected[:3])}), degrading end-user experience.",
        "confidence": int(ctx.get("confidence_score", 94)),
        "risk_level": severity,
        "technical_reasoning": [
            f"Root cause alert: '{root_alert}' on '{service}' was the earliest registered telemetry signal",
            f"Topological dependency verification: downstream nodes connect directly or transitively to '{service}'",
            f"Noise reduction: {suppressed_count} secondary symptom alarms suppressed to protect on-call attention",
        ],
        "provider": "built-in SRE engine",
    }

    return validate_and_normalize_ai_response(data, ctx)


async def analyze_incident_with_ai(
    db: Session,
    incident: Incident,
    override_api_key: Optional[str] = None,
    preferred_provider: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point for AI SRE Incident Analysis.
    1. Extracts clean, secret-free incident context.
    2. Calls Gemini (or OpenAI) server-side.
    3. Validates and normalizes structured response.
    4. Falls back gracefully to deterministic SRE engine if any failure occurs.
    """
    ctx = build_incident_context(db, incident)

    # Check available API keys
    gemini_key = override_api_key if (override_api_key and override_api_key.startswith("AIza")) else None
    if not gemini_key:
        gemini_key = gemini_service.get_api_key()

    openai_key = override_api_key if (override_api_key and override_api_key.startswith("sk-")) else None
    if not openai_key:
        openai_key = os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)

    # Provider preference logic
    target_provider = preferred_provider or ("gemini" if gemini_key else ("openai" if openai_key else "fallback"))

    # 1. Try Gemini Provider
    if target_provider == "gemini" and gemini_key:
        try:
            logger.info("Calling Gemini for Incident %s AI SRE Analysis...", incident.id)
            system_prompt = build_system_instruction()
            prompt = build_analysis_prompt(ctx)

            raw_reply = await gemini_service.async_generate_chat_response(
                prompt=prompt,
                system_instruction=system_prompt,
                model=gemini_service.DEFAULT_MODEL,
                temperature=0.1,
                override_key=gemini_key,
            )

            cleaned = _clean_json_text(raw_reply)
            parsed = json.loads(cleaned)
            parsed["provider"] = f"Google Gemini ({gemini_service.DEFAULT_MODEL})"
            return validate_and_normalize_ai_response(parsed, ctx)

        except (GeminiAuthenticationError, GeminiRateLimitError, GeminiServiceError) as ge:
            logger.warning("Gemini AI incident analysis error: %s. Using fallback SRE analysis.", ge)
        except json.JSONDecodeError as je:
            logger.warning("Gemini returned non-JSON response for incident %s: %s", incident.id, je)
        except Exception as e:
            logger.exception("Unexpected error in Gemini AI incident analysis: %s", e)

    # 2. Try OpenAI Provider if Gemini was not available or failed
    if (target_provider == "openai" or openai_key) and openai_key:
        try:
            logger.info("Calling OpenAI for Incident %s AI SRE Analysis...", incident.id)
            system_prompt = build_system_instruction()
            prompt = build_analysis_prompt(ctx)
            model_name = getattr(settings, "LLM_MODEL", None) or "gpt-4o-mini"

            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openai_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 1200,
                        "response_format": {"type": "json_object"},
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(_clean_json_text(content))
                    parsed["provider"] = f"OpenAI ({model_name})"
                    return validate_and_normalize_ai_response(parsed, ctx)
                else:
                    logger.warning("OpenAI API returned status %s for incident %s", res.status_code, incident.id)

        except Exception as oe:
            logger.warning("OpenAI AI incident analysis error: %s. Using fallback SRE analysis.", oe)

    # 3. Graceful Deterministic Fallback: Never break the incident or platform!
    logger.info("Using deterministic SRE engine for Incident %s analysis.", incident.id)
    return generate_deterministic_sre_analysis(ctx)
