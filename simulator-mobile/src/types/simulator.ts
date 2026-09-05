export type ScenarioId =
  | "database_outage"
  | "flaky_pod"
  | "alert_storm"
  | "critical_emergency"
  | "service_cascade"
  | "recovery"
  | "reset";

export interface ScenarioMetadata {
  id: ScenarioId;
  name: string;
  tag: string;
  description: string;
  expectedBehavior: string;
  defaultAlertCount: number;
  severity: "critical" | "high" | "medium" | "low" | "mixed";
  buttonText: string;
  badgeColor: string;
  badgeTextColor: string;
}

export interface SimulationResult {
  status: string;
  scenario: string;
  total_generated: number;
  total_accepted: number;
  total_incoming: number;
  unique_alerts: number;
  duplicates_merged: number;
  correlated_alerts: number;
  batched_alerts: number;
  suppressed_count: number;
  notifications_dispatched: number;
  reduction_percentage: number;
  active_incidents: number;
  probable_root_cause: string;
  confidence_score: number;
  channel_breakdown: {
    pagerduty: number;
    slack: number;
    email: number;
    mock: number;
  };
  timestamp: string;
  message?: string;
}

export interface SimulationHistoryItem {
  id: string;
  scenarioId: ScenarioId;
  scenarioName: string;
  status: "Completed" | "Failed" | "Cancelled";
  totalGenerated: number;
  totalAccepted: number;
  suppressedCount: number;
  notificationsDispatched: number;
  reductionPercentage: number;
  probableRootCause: string;
  startedAt: string;
  completedAt: string;
}

export interface StormParams {
  alertCount: number;
  speed: "slow" | "normal" | "fast";
  severity: "mixed" | "critical" | "high" | "medium" | "low";
}
