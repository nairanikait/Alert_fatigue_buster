import axios from "axios";
import { SimulationResult, StormParams, ScenarioId } from "../types/simulator";

export const createApiClient = (baseUrl: string) => {
  const cleanBase = baseUrl.replace(/\/+$/, "");
  const client = axios.create({
    baseURL: cleanBase,
    timeout: 30000, // 30s for high-volume batches
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
  });

  return {
    // SCENARIO 1: DATABASE OUTAGE
    runDatabaseOutage: async (): Promise<SimulationResult> => {
      const res = await client.post<SimulationResult>("/api/simulator/database-outage");
      return res.data;
    },

    // SCENARIO 2: FLAKY POD
    runFlakyPod: async (): Promise<SimulationResult> => {
      const res = await client.post<SimulationResult>("/api/simulator/flaky-pod");
      return res.data;
    },

    // SCENARIO 3: ALERT STORM
    runAlertStorm: async (params?: Partial<StormParams>): Promise<SimulationResult> => {
      const queryParams = new URLSearchParams();
      if (params?.alertCount) queryParams.append("alert_count", params.alertCount.toString());
      if (params?.speed) queryParams.append("speed", params.speed);
      if (params?.severity) queryParams.append("severity", params.severity);

      const qs = queryParams.toString();
      const endpoint = `/api/simulator/alert-storm${qs ? `?${qs}` : ""}`;
      const res = await client.post<SimulationResult>(endpoint);
      return res.data;
    },

    // SCENARIO 4: CRITICAL EMERGENCY
    runCriticalEmergency: async (): Promise<SimulationResult> => {
      const res = await client.post<SimulationResult>("/api/simulator/critical-emergency");
      return res.data;
    },

    // SCENARIO 5: SERVICE CASCADE
    runServiceCascade: async (): Promise<SimulationResult> => {
      const res = await client.post<SimulationResult>("/api/simulator/service-cascade");
      return res.data;
    },

    // SCENARIO 6: RECOVERY
    runRecovery: async (): Promise<SimulationResult> => {
      const res = await client.post<SimulationResult>("/api/simulator/recovery");
      return res.data;
    },

    // RESET
    resetData: async (): Promise<{ status: string; message: string }> => {
      const res = await client.post("/api/simulator/reset");
      return res.data;
    },

    // GENERIC RUNNER
    runScenario: async (scenario: ScenarioId, params?: any): Promise<SimulationResult> => {
      const res = await client.post<SimulationResult>("/api/simulator/run", {
        scenario,
        ...(params || {}),
      });
      return res.data;
    },

    // SECURITY TEST SCENARIOS (Server-side signed, zero client secrets)
    runSecurityTest: async (scenario: string): Promise<any> => {
      const res = await client.post("/api/simulator/security-test", { scenario });
      return res.data;
    },

    // HEALTH CHECK
    checkHealth: async (): Promise<boolean> => {
      try {
        const res = await client.get("/health", { timeout: 3000 });
        return res.status === 200 && res.data?.status === "ok";
      } catch {
        return false;
      }
    },
  };
};
