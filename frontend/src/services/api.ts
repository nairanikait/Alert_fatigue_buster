import { AlertItem, IncidentItem, NotificationItem, MetricsData, TopologyData } from "../types";

const API_BASE = "/api";

export async function fetchMetrics(): Promise<MetricsData> {
  const res = await fetch(`${API_BASE}/metrics`);
  if (!res.ok) throw new Error("Failed to fetch metrics");
  return res.json();
}

export async function fetchAlerts(params?: {
  severity?: string;
  status?: string;
  service?: string;
  search?: string;
  is_flaky?: boolean;
  limit?: number;
  offset?: number;
}): Promise<AlertItem[]> {
  const query = new URLSearchParams();
  if (params?.severity) query.append("severity", params.severity);
  if (params?.status) query.append("status", params.status);
  if (params?.service) query.append("service", params.service);
  if (params?.search) query.append("search", params.search);
  if (params?.is_flaky !== undefined) query.append("is_flaky", String(params.is_flaky));
  if (params?.limit) query.append("limit", String(params.limit));
  if (params?.offset) query.append("offset", String(params.offset));

  const res = await fetch(`${API_BASE}/alerts?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch alerts");
  return res.json();
}

export async function fetchAlertDetail(alertId: number): Promise<AlertItem> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}`);
  if (!res.ok) throw new Error(`Failed to fetch alert ${alertId}`);
  return res.json();
}

export async function fetchIncidents(status?: string): Promise<IncidentItem[]> {
  const query = status ? `?status=${status}` : "";
  const res = await fetch(`${API_BASE}/incidents${query}`);
  if (!res.ok) throw new Error("Failed to fetch incidents");
  return res.json();
}

export async function fetchIncidentDetail(incidentId: string): Promise<{ incident: IncidentItem; alerts: AlertItem[] }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`);
  if (!res.ok) throw new Error(`Failed to fetch incident ${incidentId}`);
  return res.json();
}

export async function fetchNotifications(channel?: string): Promise<NotificationItem[]> {
  const query = channel ? `?channel=${channel}` : "";
  const res = await fetch(`${API_BASE}/notifications${query}`);
  if (!res.ok) throw new Error("Failed to fetch notifications");
  return res.json();
}

export async function fetchTopology(): Promise<TopologyData> {
  const res = await fetch(`${API_BASE}/services`);
  if (!res.ok) throw new Error("Failed to fetch service topology");
  return res.json();
}

export async function createService(data: { id: string; display_name: string; criticality: number }): Promise<any> {
  const res = await fetch(`${API_BASE}/services`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to create service" }));
    throw new Error(error.detail || "Failed to create service");
  }
  return res.json();
}

export async function updateService(serviceId: string, data: { display_name?: string; criticality?: number }): Promise<any> {
  const res = await fetch(`${API_BASE}/services/${serviceId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to update service" }));
    throw new Error(error.detail || "Failed to update service");
  }
  return res.json();
}

export async function deleteService(serviceId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/services/${serviceId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to delete service" }));
    throw new Error(error.detail || "Failed to delete service");
  }
  return res.json();
}

export async function fetchDependencies(): Promise<Array<{ id?: number; parent: string; child: string }>> {
  const res = await fetch(`${API_BASE}/services/dependencies`);
  if (!res.ok) throw new Error("Failed to fetch dependencies");
  return res.json();
}

export async function createDependency(data: { parent: string; child: string }): Promise<any> {
  const res = await fetch(`${API_BASE}/services/dependencies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to create dependency" }));
    throw new Error(error.detail || "Failed to create dependency");
  }
  return res.json();
}

export async function deleteDependency(parent: string, child: string): Promise<any> {
  const res = await fetch(`${API_BASE}/services/dependencies?parent=${encodeURIComponent(parent)}&child=${encodeURIComponent(child)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to delete dependency" }));
    throw new Error(error.detail || "Failed to delete dependency");
  }
  return res.json();
}

export async function fetchConfig(): Promise<any> {
  const res = await fetch(`${API_BASE}/config`);
  if (!res.ok) throw new Error("Failed to fetch configuration");
  return res.json();
}

export async function updateConfig(rules: any): Promise<any> {
  const res = await fetch(`${API_BASE}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rules }),
  });
  if (!res.ok) throw new Error("Failed to update configuration");
  return res.json();
}

// Demo Simulation Actions
export async function triggerDatabaseOutage(): Promise<any> {
  const res = await fetch(`${API_BASE}/demo/database-outage`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger Database Outage simulation");
  return res.json();
}

export async function triggerFlakyPod(): Promise<any> {
  const res = await fetch(`${API_BASE}/demo/flaky-pod`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger Flaky Pod simulation");
  return res.json();
}

export async function triggerAlertStorm(): Promise<any> {
  const res = await fetch(`${API_BASE}/demo/alert-storm`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger Alert Storm simulation");
  return res.json();
}

export async function triggerCriticalEmergency(): Promise<any> {
  const res = await fetch(`${API_BASE}/demo/critical`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger Critical Emergency simulation");
  return res.json();
}

export async function triggerRecovery(): Promise<any> {
  const res = await fetch(`${API_BASE}/demo/recovery`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger Recovery simulation");
  return res.json();
}

export async function resetDemoData(): Promise<any> {
  const res = await fetch(`${API_BASE}/demo/reset`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to reset demo data");
  return res.json();
}

export async function checkHealth(): Promise<any> {
  const res = await fetch("/health");
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

// AI Chatbot API Endpoints
export async function sendChatMessage(payload: {
  message: string;
  history?: Array<{ role: string; content: string }>;
  context?: any;
  api_key?: string;
  provider?: string;
  model?: string;
}): Promise<{
  reply: string;
  provider_used: string;
  has_api_key: boolean;
  suggested_actions?: string[];
}> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Chat request failed (${res.status}): ${errorText}`);
  }
  return res.json();
}

export async function fetchChatStatus(): Promise<{
  configured: boolean;
  provider: string;
  model: string;
  instructions: string;
}> {
  const res = await fetch(`${API_BASE}/chat/status`);
  if (!res.ok) throw new Error("Failed to fetch chat status");
  return res.json();
}

// Ingestion Security & Audit Log Endpoints
export async function fetchSecurityAuditLog(limit: number = 50): Promise<{
  status: string;
  total_entries: number;
  entries: any[];
}> {
  const res = await fetch(`${API_BASE}/alerts/security-audit?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch security audit log");
  return res.json();
}

export async function clearSecurityAuditLog(): Promise<any> {
  const res = await fetch(`${API_BASE}/alerts/security-audit`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to clear security audit log");
  return res.json();
}

// Alert Integrity Shield API Services
export interface SecurityOverviewData {
  status: string;
  system_status: "PROTECTED" | "WARNING" | "CRITICAL";
  status_message: string;
  metrics: {
    total_screened: number;
    blocked_requests: number;
    quarantined_alerts: number;
    pending_critical_quarantines: number;
    invalid_signatures: number;
    replay_attempts: number;
    rate_limit_violations: number;
    alert_injection_attempts: number;
    average_trust_score: number;
    accepted_requests: number;
  };
  distribution: {
    trusted: number;
    suspicious: number;
    blocked: number;
  };
}

export async function fetchSecurityOverview(): Promise<SecurityOverviewData> {
  const res = await fetch(`${API_BASE}/security/overview`);
  if (!res.ok) throw new Error("Failed to fetch security overview");
  return res.json();
}

export async function fetchSecurityEvents(params?: {
  event_type?: string;
  source?: string;
  action?: string;
  limit?: number;
  offset?: number;
}): Promise<{ status: string; total: number; events: any[] }> {
  const query = new URLSearchParams();
  if (params?.event_type) query.append("event_type", params.event_type);
  if (params?.source) query.append("source", params.source);
  if (params?.action) query.append("action", params.action);
  if (params?.limit) query.append("limit", String(params.limit));
  if (params?.offset) query.append("offset", String(params.offset));

  const res = await fetch(`${API_BASE}/security/events?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch security events");
  return res.json();
}

export async function fetchQuarantinedAlerts(params?: {
  is_critical?: boolean;
  search?: string;
  limit?: number;
}): Promise<{ status: string; total: number; quarantined_alerts: any[] }> {
  const query = new URLSearchParams();
  if (params?.is_critical !== undefined) query.append("is_critical", String(params.is_critical));
  if (params?.search) query.append("search", params.search);
  if (params?.limit) query.append("limit", String(params.limit));

  const res = await fetch(`${API_BASE}/security/quarantine?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch quarantined alerts");
  return res.json();
}

export async function approveQuarantinedAlert(alertId: number): Promise<any> {
  const res = await fetch(`${API_BASE}/security/quarantine/${alertId}/approve`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to approve quarantined alert ${alertId}`);
  return res.json();
}

export async function rejectQuarantinedAlert(alertId: number, reason?: string): Promise<any> {
  const query = reason ? `?reason=${encodeURIComponent(reason)}` : "";
  const res = await fetch(`${API_BASE}/security/quarantine/${alertId}/reject${query}`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to reject quarantined alert ${alertId}`);
  return res.json();
}

export async function fetchWebhookSources(): Promise<{ status: string; sources: any[] }> {
  const res = await fetch(`${API_BASE}/security/sources`);
  if (!res.ok) throw new Error("Failed to fetch webhook sources");
  return res.json();
}

export async function createWebhookSource(data: { source_name: string; rate_limit_per_minute?: number }): Promise<any> {
  const res = await fetch(`${API_BASE}/security/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create webhook source");
  return res.json();
}

export async function rotateSourceSecret(sourceId: string, graceHours: number = 24): Promise<any> {
  const res = await fetch(`${API_BASE}/security/sources/${sourceId}/rotate-secret?grace_period_hours=${graceHours}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to rotate source secret");
  return res.json();
}

export async function toggleSourceStatus(sourceId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/security/sources/${sourceId}/toggle`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to toggle source status");
  return res.json();
}

export async function runSecurityTestScenario(scenario: string): Promise<any> {
  const res = await fetch(`${API_BASE}/security/test-scenario?scenario=${encodeURIComponent(scenario)}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to execute security test '${scenario}'`);
  return res.json();
}


