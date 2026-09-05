import React, { useState, useEffect, useCallback } from "react";
import { Navbar } from "./components/Navbar";
import { Sidebar, NavTab } from "./components/Sidebar";
import { OverviewCards } from "./components/Dashboard/OverviewCards";
import { BeforeAfterReduction } from "./components/Dashboard/BeforeAfterReduction";
import { AlertVolumeChart } from "./components/Dashboard/AlertVolumeChart";
import { SeverityDistribution } from "./components/Dashboard/SeverityDistribution";
import { IncidentOverviewCard } from "./components/Dashboard/IncidentOverviewCard";
import { RecentNotificationsCard } from "./components/Dashboard/RecentNotificationsCard";
import { TopRootCausesTable } from "./components/Dashboard/TopRootCausesTable";
import { TopAffectedServicesTable } from "./components/Dashboard/TopAffectedServicesTable";

import { AlertsTable } from "./components/Alerts/AlertsTable";
import { AlertDetailModal } from "./components/Alerts/AlertDetailModal";
import { IncidentList } from "./components/Incidents/IncidentList";
import { RootCauseGraph } from "./components/RootCause/RootCauseGraph";
import { NotificationFeed } from "./components/Notifications/NotificationFeed";
import { RulesEditor } from "./components/Rules/RulesEditor";
import { ServicesCatalog } from "./components/Services/ServicesCatalog";
import { AnalyticsView } from "./components/Analytics/AnalyticsView";
import { MobileSimulatorGuide } from "./components/Demo/MobileSimulatorGuide";
import { SettingsView } from "./components/Settings/SettingsView";
import { SecurityView } from "./components/Security/SecurityView";
import { SimulationDrawer } from "./components/SimulationDrawer/SimulationDrawer";
import { AIChatbot } from "./components/Chat/AIChatbot";

import {
  fetchMetrics,
  fetchAlerts,
  fetchIncidents,
  fetchNotifications,
  fetchTopology,
} from "./services/api";
import { wsClient } from "./services/websocket";
import {
  startSimulation,
  fetchActiveSimulation,
  SimulationMetadata,
} from "./services/simulationStream";
import { AlertItem, IncidentItem, NotificationItem, MetricsData, TopologyData } from "./types";
import { Flame, Zap, Database, Play } from "lucide-react";

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>("dashboard");
  const [wsConnected, setWsConnected] = useState<boolean>(false);

  // Core Data States
  const [metrics, setMetrics] = useState<MetricsData>({
    incoming_alerts: 0,
    unique_alerts: 0,
    suppressed_alerts: 0,
    batched_alerts: 0,
    notifications_sent: 0,
    reduction_percentage: 0.0,
    active_incidents: 0,
    suppression_breakdown: { duplicates: 0, batched: 0, downstream: 0, cooldown: 0, flaky: 0 },
    channel_breakdown: { pagerduty: 0, slack: 0, email: 0, mock: 0 },
    severity_breakdown: { critical: 0, high: 0, medium: 0, low: 0 },
    top_affected_services: [],
  });

  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [topology, setTopology] = useState<TopologyData>({ services: [], dependencies: [] });

  // Inspection Modal State
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);

  // Right-side Simulation Live Stream Drawer State
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [activeSimulationId, setActiveSimulationId] = useState<string | null>(null);
  const [activeScenarioName, setActiveScenarioName] = useState<string>("Database Outage");
  const [activeTargetCount, setActiveTargetCount] = useState<number>(500);
  const [activeSimMetadata, setActiveSimMetadata] = useState<SimulationMetadata | null>(null);

  // Load Data
  const loadAllData = useCallback(async () => {
    try {
      const [m, a, inc, n, top] = await Promise.all([
        fetchMetrics(),
        fetchAlerts({ limit: 150 }),
        fetchIncidents(),
        fetchNotifications(),
        fetchTopology(),
      ]);
      setMetrics(m);
      setAlerts(a);
      setIncidents(inc);
      setNotifications(n);
      setTopology(top);
    } catch (err) {
      console.warn("Telemetry refresh error:", err);
    }
  }, []);

  // Check active simulation on load
  const checkActiveSim = useCallback(async () => {
    try {
      const res = await fetchActiveSimulation();
      if (res.active && res.simulation) {
        setActiveSimMetadata(res.simulation);
        setActiveSimulationId(res.simulation.simulation_id);
        setActiveScenarioName(res.simulation.scenario);
        setActiveTargetCount(res.simulation.target_count);
      } else {
        setActiveSimMetadata(null);
      }
    } catch {
      // Ignore background active check errors
    }
  }, []);

  useEffect(() => {
    loadAllData();
    checkActiveSim();

    // Polling fallback every 4s
    const interval = setInterval(() => {
      loadAllData();
      checkActiveSim();
    }, 4000);

    // WebSocket Real-Time Events
    const unsubStatus = wsClient.onStatusChange(setWsConnected);
    const unsubWs = wsClient.subscribe((type, data) => {
      if (
        type === "ALERT_UPDATE" ||
        type === "DEMO_COMPLETE" ||
        type === "DEMO_RESET" ||
        type === "SIMULATION_COMPLETE"
      ) {
        loadAllData();
        checkActiveSim();
      }
    });

    return () => {
      clearInterval(interval);
      unsubStatus();
      unsubWs();
    };
  }, [loadAllData, checkActiveSim]);

  // Handler to trigger simulation and open drawer
  const handleStartSimulation = async (scenario: string, name: string, count?: number) => {
    try {
      const res = await startSimulation({
        scenario,
        count,
        speed: "normal",
        force_stop_active: true,
      });
      setActiveSimulationId(res.simulation_id);
      setActiveScenarioName(name);
      setActiveTargetCount(res.target_count);
      setIsDrawerOpen(true);
      loadAllData();
    } catch (err: any) {
      if (err?.isConflict && err.detail?.active_simulation) {
        const active = err.detail.active_simulation;
        setActiveSimulationId(active.simulation_id);
        setActiveScenarioName(active.scenario);
        setActiveTargetCount(active.target_count);
        setIsDrawerOpen(true);
      } else {
        alert(`Failed to start simulation: ${err.message || err}`);
      }
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 selection:bg-indigo-600 selection:text-white font-sans">
      {/* Top Telemetry Header */}
      <Navbar
        wsConnected={wsConnected}
        reductionPercentage={metrics.reduction_percentage}
        activeIncidents={metrics.active_incidents}
        onOpenDemo={() => setCurrentTab("demo")}
        onOpenSettings={() => setCurrentTab("settings")}
        onStartSimulation={handleStartSimulation}
        activeSimulation={
          activeSimMetadata
            ? {
                simulationId: activeSimMetadata.simulation_id,
                scenarioName: activeSimMetadata.scenario,
                status: activeSimMetadata.status,
                counts: activeSimMetadata.counts,
              }
            : null
        }
        onOpenDrawer={() => setIsDrawerOpen(true)}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Left Navigation Sidebar */}
        <Sidebar
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          alertCount={alerts.length}
          incidentCount={incidents.filter((i) => i.status === "FIRING").length}
          notificationCount={notifications.length}
          filteringRate={metrics.reduction_percentage}
          noiseReducedCount={metrics.suppressed_alerts}
        />

        {/* Main Workspace Area */}
        <main className="flex-1 overflow-y-auto p-6">
          {currentTab === "dashboard" && (
            <div className="space-y-6 max-w-7xl mx-auto">
              {/* Heading with Quick Simulation Triggers */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <h1 className="text-xl font-bold text-slate-900 tracking-tight">Overview</h1>
                  <p className="text-xs text-slate-500">
                    Real-time overview of your alert management system.
                  </p>
                </div>

                {/* Direct Simulation Trigger Buttons on Dashboard */}
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() =>
                      handleStartSimulation("database_outage", "Database Outage", 500)
                    }
                    className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-xs transition active:scale-95"
                    title="Generate 500-alert Database Outage incident cascade"
                  >
                    <Flame className="w-3.5 h-3.5 fill-white text-white" />
                    <span>Generate Database Outage</span>
                  </button>

                  <button
                    onClick={() => handleStartSimulation("alert_storm", "Alert Storm", 500)}
                    className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs transition active:scale-95"
                    title="Generate multi-service resource alert storm"
                  >
                    <Zap className="w-3.5 h-3.5 fill-white text-white" />
                    <span>Alert Storm</span>
                  </button>
                </div>
              </div>

              {/* 6 Core KPI Cards */}
              <OverviewCards metrics={metrics} />

              {/* Flagship Hero Noise Reduction Impact */}
              <BeforeAfterReduction metrics={metrics} />

              {/* Charts Row */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <AlertVolumeChart metrics={metrics} />
                </div>
                <div className="lg:col-span-1">
                  <SeverityDistribution metrics={metrics} />
                </div>
              </div>

              {/* Incident Overview & Recent Notifications Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <IncidentOverviewCard
                  incidents={incidents}
                  onViewIncident={(inc) => {
                    if (inc.root_cause_alert_id) {
                      const match = alerts.find((a) => a.id === inc.root_cause_alert_id);
                      if (match) setSelectedAlert(match);
                    }
                  }}
                  onViewAll={() => setCurrentTab("incidents")}
                />
                <RecentNotificationsCard
                  notifications={notifications}
                  onViewAll={() => setCurrentTab("notifications")}
                />
              </div>

              {/* Top Root Causes & Top Affected Services Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <TopRootCausesTable incidents={incidents} />
                <TopAffectedServicesTable metrics={metrics} />
              </div>
            </div>
          )}

          {currentTab === "security" && (
            <div className="max-w-7xl mx-auto">
              <SecurityView />
            </div>
          )}

          {currentTab === "alerts" && (
            <div className="max-w-7xl mx-auto">
              <AlertsTable
                alerts={alerts}
                onSelectAlert={setSelectedAlert}
                onRefresh={loadAllData}
              />
            </div>
          )}

          {currentTab === "incidents" && (
            <div className="max-w-7xl mx-auto">
              <IncidentList
                incidents={incidents}
                onSelectIncident={(inc) => {
                  if (inc.root_cause_alert_id) {
                    const match = alerts.find((a) => a.id === inc.root_cause_alert_id);
                    if (match) setSelectedAlert(match);
                  }
                }}
              />
            </div>
          )}

          {currentTab === "rootcause" && (
            <div className="max-w-7xl mx-auto">
              <RootCauseGraph topology={topology} onRefreshTopology={loadAllData} />
            </div>
          )}

          {currentTab === "notifications" && (
            <div className="max-w-7xl mx-auto">
              <NotificationFeed
                notifications={notifications}
                onRefresh={loadAllData}
                totalSuppressed={metrics.suppressed_alerts}
              />
            </div>
          )}

          {currentTab === "services" && (
            <div className="max-w-7xl mx-auto">
              <ServicesCatalog topology={topology} onRefreshTopology={loadAllData} />
            </div>
          )}

          {currentTab === "rules" && (
            <div className="max-w-7xl mx-auto">
              <RulesEditor />
            </div>
          )}

          {currentTab === "analytics" && (
            <div className="max-w-7xl mx-auto">
              <AnalyticsView
                metrics={metrics}
                alerts={alerts}
                incidents={incidents}
                notifications={notifications}
              />
            </div>
          )}

          {currentTab === "demo" && (
            <div className="max-w-7xl mx-auto">
              <MobileSimulatorGuide wsConnected={wsConnected} />
            </div>
          )}

          {currentTab === "settings" && (
            <div className="max-w-7xl mx-auto">
              <SettingsView />
            </div>
          )}
        </main>
      </div>

      {/* Full Alert Detail Modal */}
      <AlertDetailModal
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
      />

      {/* Right-Side Simulation Live Stream Drawer */}
      <SimulationDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        simulationId={activeSimulationId}
        scenarioName={activeScenarioName}
        initialTargetCount={activeTargetCount}
        onSimulationComplete={loadAllData}
      />

      {/* Global AI Chatbot (Visible on all pages in bottom right corner) */}
      <AIChatbot
        currentTab={currentTab}
        metrics={metrics}
        alerts={alerts}
        incidents={incidents}
        topology={topology}
        selectedAlert={selectedAlert}
      />
    </div>
  );
};
