import React, { useState, useEffect, useCallback } from "react";
import {
  fetchSecurityOverview,
  fetchSecurityEvents,
  fetchQuarantinedAlerts,
  fetchWebhookSources,
  SecurityOverviewData,
} from "../../services/api";
import { SecurityOverviewCards } from "./SecurityOverviewCards";
import { QuarantineReviewTable } from "./QuarantineReviewTable";
import { SecurityEventsStream } from "./SecurityEventsStream";
import { WebhookSourcesList } from "./WebhookSourcesList";
import { SecurityTestControls } from "./SecurityTestControls";

export const SecurityView: React.FC = () => {
  const [overview, setOverview] = useState<SecurityOverviewData | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [quarantinedAlerts, setQuarantinedAlerts] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadAllData = useCallback(async () => {
    try {
      const [overviewData, eventsData, quarantineData, sourcesData] = await Promise.all([
        fetchSecurityOverview(),
        fetchSecurityEvents({ limit: 40 }),
        fetchQuarantinedAlerts({ limit: 50 }),
        fetchWebhookSources(),
      ]);

      setOverview(overviewData);
      setEvents(eventsData.events || []);
      setQuarantinedAlerts(quarantineData.quarantined_alerts || []);
      setSources(sourcesData.sources || []);
    } catch (e: any) {
      console.error("Failed to load security dashboard data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAllData();
    const interval = setInterval(loadAllData, 10000); // 10s auto-refresh
    return () => clearInterval(interval);
  }, [loadAllData]);

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">
      {/* 1. System Status & Security Metrics */}
      <SecurityOverviewCards data={overview} loading={loading} onRefresh={loadAllData} />

      {/* 2. Interactive 1-Click Security Test Suite */}
      <SecurityTestControls onScenarioExecuted={loadAllData} />

      {/* 3. Quarantined & Suspicious Alerts Triage */}
      <QuarantineReviewTable
        alerts={quarantinedAlerts}
        loading={loading}
        onActionComplete={loadAllData}
      />

      {/* 4. Live Events Audit Stream + Registered Webhook Sources */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SecurityEventsStream events={events} loading={loading} />
        <WebhookSourcesList sources={sources} loading={loading} onRefresh={loadAllData} />
      </div>
    </div>
  );
};
