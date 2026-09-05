export interface AlertItem {
  id: number;
  fingerprint: string;
  source: string;
  alert_name: string;
  title?: string;
  service: string;
  host: string | null;
  environment: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  severity_score: number;
  status: "FIRING" | "ONGOING" | "RESOLVED" | "SUPPRESSED" | "BATCHED" | "OPEN" | "ACKNOWLEDGED" | string;
  message: string;
  description?: string;
  root_cause?: string | null;
  dedup_key?: string | null;
  created_at?: string;
  labels: Record<string, any>;
  timestamp: string;
  first_seen: string;
  last_seen: string;
  resolved_at: string | null;
  duration_seconds: number;
  occurrence_count: number;
  root_cause_id: number | null;
  correlation_group_id: string | null;
  notification_status: "SENT" | "SUPPRESSED" | "BATCHED" | "PENDING";
  suppression_reason: string | null;
  suppression_category: "duplicate" | "batch" | "downstream" | "cooldown" | "flaky" | null;
  is_flaky: boolean;
  fire_count: number;
  resolve_count: number;
  explainability_notes: string[];
}

export interface IncidentItem {
  id: string;
  title: string;
  root_cause_alert_id: number | null;
  root_cause_service: string;
  root_cause_alert_name: string;
  root_cause_reason: string;
  confidence_score: number;
  severity: string;
  severity_score: number;
  status: "FIRING" | "RESOLVED";
  affected_services: string[];
  alert_count: number;
  suppressed_count: number;
  notifications_count: number;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  duration_seconds: number;
  evidence: any[];
  ai_analysis?: AIIncidentAnalysis;
  estimated_cost_loss?: number;
  cost_burn_rate_per_minute?: number;
}

export interface AIIncidentAnalysis {
  summary: string;
  root_cause_explanation: string;
  correlation_explanation: string;
  suppression_explanation: string;
  immediate_mitigation: string[];
  investigation_steps: string[];
  long_term_prevention: string[];
  potential_impact: string;
  confidence: number;
  risk_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  technical_reasoning: string[];
  analyzed_at?: string;
  provider?: string;
}

export interface NotificationItem {
  id: number;
  incident_id: string | null;
  alert_id: number | null;
  channel: "pagerduty" | "slack" | "email" | "mock";
  status: string;
  title: string;
  message: string;
  payload: Record<string, any>;
  reason: string | null;
  sent_at: string;
}

export interface CostSavingsBreakdown {
  cost_saved_dedup_batching?: number;
  cost_saved_routing_triage?: number;
  total_cost_saved?: number;
  engineering_hours_saved?: number;
  interruption_minutes_saved?: number;
  incoming_alerts?: number;
  notifications_sent?: number;
  suppressed_alerts?: number;
  downstream_suppressed?: number;
  engineer_hourly_rate?: number;
  interruption_recovery_minutes?: number;
  avoided_interruption_cost?: number;
  avoided_downstream_triage_cost?: number;

  // Compatibility aliases
  cost_per_interruption?: number;
  avg_context_switch_min?: number;
  dedup_batching_saved?: number;
  routing_triage_saved?: number;
  total_dollars_saved?: number;
}

export interface EngineeringTimeSaved {
  total_minutes_saved: number;
  total_hours_saved: number;
  human_readable: string;
}

export interface MetricsData {
  incoming_alerts: number;
  unique_alerts: number;
  suppressed_alerts: number;
  batched_alerts: number;
  notifications_sent: number;
  reduction_percentage: number;
  active_incidents: number;
  suppression_breakdown: {
    duplicates: number;
    batched: number;
    downstream: number;
    cooldown: number;
    flaky: number;
  };
  channel_breakdown: {
    pagerduty: number;
    slack: number;
    email: number;
    mock: number;
  };
  severity_breakdown: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  top_affected_services: Array<{
    service: string;
    count: number;
    criticality: number;
  }>;
  cost_savings?: CostSavingsBreakdown;
  time_saved?: EngineeringTimeSaved;
}

export interface ServiceNodeInfo {
  [key: string]: any;
  id: string;
  display_name: string;
  criticality: number;
  status: "healthy" | "impacted" | "root_cause";
  incident_info?: {
    incident_id: string;
    reason: string;
    confidence: number;
    severity: string;
  } | null;
}

export interface DependencyEdgeInfo {
  parent: string;
  child: string;
}

export interface TopologyData {
  services: ServiceNodeInfo[];
  dependencies: DependencyEdgeInfo[];
}

export interface SecurityAuditEntry {
  id: string;
  timestamp: number;
  iso_time: string;
  endpoint: string;
  source: string;
  client_ip: string;
  reason: "AUTH_FAILED" | "RATE_LIMITED" | "INVALID_SCHEMA" | string;
  status_code: number;
  payload_excerpt?: string | null;
}

export interface SecurityAuditResponse {
  status: string;
  total_entries: number;
  entries: SecurityAuditEntry[];
}
