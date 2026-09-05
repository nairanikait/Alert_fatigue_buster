export interface SimulationCounts {
  generated: number;
  total: number;
  processed: number;
  suppressed: number;
  notifications: number;
  incidents: number;
  correlated: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  reduction_percentage: number;
}

export interface SimulationSummary {
  total_generated: number;
  total_processed: number;
  suppressed_count: number;
  notifications_dispatched: number;
  incidents_created: number;
  reduction_percentage: number;
  elapsed_seconds: number;
  completed_at: string;
}

export interface SimulationAlertItem {
  id: number | string;
  alert_name: string;
  service: string;
  host?: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  severity_score?: number;
  status: string;
  source?: string;
  fingerprint?: string;
  message?: string;
  labels?: Record<string, string>;
  timestamp: string;
}

export interface SimulationEventPayload {
  seq: number;
  type: string;
  simulation_id: string;
  timestamp: string;
  alert?: SimulationAlertItem;
  result?: string; // "received", "duplicate", "correlated", "cooldown", "batched", "suppressed", "notified", "resolved"
  action?: string;
  reason?: string;
  correlation_id?: string | number;
  incident_id?: string | number;
  notification_id?: string | number;
  counts?: SimulationCounts;
  summary?: SimulationSummary;
  error?: string;
  scenario?: string;
  status?: string;
}

export interface SimulationMetadata {
  simulation_id: string;
  scenario: string;
  target_count: number;
  speed: string;
  severity: string;
  status: "RUNNING" | "COMPLETED" | "STOPPED" | "FAILED" | string;
  started_at: string;
  completed_at?: string;
  elapsed_seconds: number;
  counts: SimulationCounts;
  summary?: SimulationSummary;
}

const API_BASE = "/api";

export async function startSimulation(params: {
  scenario: string;
  count?: number;
  speed?: string;
  severity?: string;
  force_stop_active?: boolean;
}): Promise<{
  simulation_id: string;
  scenario: string;
  target_count: number;
  status: string;
  speed: string;
  started_at: string;
}> {
  const res = await fetch(`${API_BASE}/simulations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (res.status === 409) {
    const errorData = await res.json();
    throw { isConflict: true, detail: errorData.detail };
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to start simulation");
  }

  return res.json();
}

export async function stopSimulation(simulationId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/simulations/${simulationId}/stop`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to stop simulation");
  return res.json();
}

export async function fetchActiveSimulation(): Promise<{
  active: boolean;
  simulation: SimulationMetadata | null;
}> {
  const res = await fetch(`${API_BASE}/simulations/active`);
  if (!res.ok) throw new Error("Failed to check active simulation");
  return res.json();
}

export async function fetchSimulationMetadata(simulationId: string): Promise<SimulationMetadata> {
  const res = await fetch(`${API_BASE}/simulations/${simulationId}`);
  if (!res.ok) throw new Error(`Failed to fetch metadata for ${simulationId}`);
  return res.json();
}

export async function fetchSimulationEvents(
  simulationId: string,
  sinceSeq: number = 0,
  limit: number = 1000
): Promise<{
  simulation_id: string;
  status: string;
  total_events: number;
  returned_events: number;
  events: SimulationEventPayload[];
  counts: SimulationCounts;
}> {
  const res = await fetch(
    `${API_BASE}/simulations/${simulationId}/events?since_seq=${sinceSeq}&limit=${limit}`
  );
  if (!res.ok) throw new Error(`Failed to fetch events for ${simulationId}`);
  return res.json();
}

export class SimulationStreamClient {
  private ws: WebSocket | null = null;
  private simulationId: string | null = null;
  private eventHandlers: Set<(event: SimulationEventPayload) => void> = new Set();
  private statusHandlers: Set<(connected: boolean) => void> = new Set();
  private isConnected: boolean = false;
  private reconnectTimer: any = null;
  private lastSeq: number = 0;

  public connect(simulationId: string) {
    if (this.simulationId === simulationId && this.ws && this.ws.readyState === WebSocket.OPEN) {
      return;
    }

    this.disconnect();
    this.simulationId = simulationId;
    this.lastSeq = 0;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/ws/simulation/${simulationId}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.notifyStatus(true);
        console.log(`[SimulationStream] Connected to simulation ${simulationId}`);

        // If we had previously received events, catch up on missed events
        if (this.lastSeq > 0) {
          this.recoverMissedEvents();
        }
      };

      this.ws.onmessage = (msgEvent) => {
        try {
          const payload: SimulationEventPayload = JSON.parse(msgEvent.data);
          if (payload.seq && payload.seq > this.lastSeq) {
            this.lastSeq = payload.seq;
          }
          this.eventHandlers.forEach((handler) => handler(payload));
        } catch (err) {
          console.warn("[SimulationStream] Failed to parse message:", err);
        }
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this.notifyStatus(false);
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.ws?.close();
      };
    } catch {
      this.scheduleReconnect();
    }
  }

  private async recoverMissedEvents() {
    if (!this.simulationId) return;
    try {
      const data = await fetchSimulationEvents(this.simulationId, this.lastSeq);
      for (const event of data.events) {
        if (event.seq > this.lastSeq) {
          this.lastSeq = event.seq;
          this.eventHandlers.forEach((handler) => handler(event));
        }
      }
    } catch (err) {
      console.warn("[SimulationStream] Error recovering missed events:", err);
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (!this.simulationId) return;

    this.reconnectTimer = setTimeout(() => {
      if (this.simulationId) {
        this.connect(this.simulationId);
      }
    }, 2500);
  }

  public disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
    this.notifyStatus(false);
    this.simulationId = null;
  }

  public onEvent(handler: (event: SimulationEventPayload) => void): () => void {
    this.eventHandlers.add(handler);
    return () => this.eventHandlers.delete(handler);
  }

  public onStatusChange(handler: (connected: boolean) => void): () => void {
    this.statusHandlers.add(handler);
    handler(this.isConnected);
    return () => this.statusHandlers.delete(handler);
  }

  private notifyStatus(status: boolean) {
    this.statusHandlers.forEach((h) => h(status));
  }
}

export const simulationStream = new SimulationStreamClient();
