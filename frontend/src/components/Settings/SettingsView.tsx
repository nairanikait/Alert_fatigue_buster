import React, { useState, useEffect } from "react";
import {
  Settings as SettingsIcon,
  Radio,
  Bell,
  Webhook,
  Database,
  Palette,
  PlayCircle,
  CheckCircle2,
  ExternalLink,
  Copy,
  Server,
  Key,
  Shield,
  ShieldAlert,
  AlertTriangle,
  Trash2,
  RefreshCw,
  Lock,
} from "lucide-react";
import { fetchSecurityAuditLog, clearSecurityAuditLog } from "../../services/api";
import { SecurityAuditEntry } from "../../types";

export const SettingsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<
    "system" | "security" | "notifications" | "webhooks" | "database" | "demo"
  >("system");
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);

  // Security Audit Log State
  const [auditEntries, setAuditEntries] = useState<SecurityAuditEntry[]>([]);
  const [loadingAudit, setLoadingAudit] = useState<boolean>(false);

  const loadAuditLog = async () => {
    try {
      setLoadingAudit(true);
      const res = await fetchSecurityAuditLog(50);
      setAuditEntries(res.entries || []);
    } catch (err) {
      console.warn("Audit log fetch error:", err);
    } finally {
      setLoadingAudit(false);
    }
  };

  useEffect(() => {
    if (activeTab === "security") {
      loadAuditLog();
    }
  }, [activeTab]);

  const handleClearAudit = async () => {
    try {
      await clearSecurityAuditLog();
      setAuditEntries([]);
    } catch (err: any) {
      alert(`Could not clear audit log: ${err.message}`);
    }
  };

  const integrations = [
    {
      name: "Prometheus Alertmanager",
      type: "Ingestion Source",
      status: "Connected / Live",
      badge: "bg-emerald-50 text-emerald-700 border-emerald-200",
      description: "Receives raw alert webhooks via Alertmanager webhook receiver.",
      endpoint: "/api/alerts/prometheus",
    },
    {
      name: "Datadog Monitors",
      type: "Ingestion Source",
      status: "Connected / Live",
      badge: "bg-emerald-50 text-emerald-700 border-emerald-200",
      description: "Direct ingestion of Datadog monitor notifications and synthetic alarms.",
      endpoint: "/api/alerts/datadog",
    },
    {
      name: "PagerDuty Incident Sync",
      type: "Dispatch Channel",
      status: "Connected / Mock",
      badge: "bg-indigo-50 text-indigo-700 border-indigo-200",
      description: "Events API v2 integration for critical incident escalation.",
      endpoint: "https://events.pagerduty.com/v2/enqueue",
    },
    {
      name: "Slack Incident Channel",
      type: "Dispatch Channel",
      status: "Connected / Mock",
      badge: "bg-indigo-50 text-indigo-700 border-indigo-200",
      description: "Rich block-kit alert cards posted to designated channel (#incident-war-room).",
      endpoint: "https://hooks.slack.com/services/T00/B00/X00",
    },
    {
      name: "Email SMTP Digest",
      type: "Dispatch Channel",
      status: "Connected / Mock",
      badge: "bg-indigo-50 text-indigo-700 border-indigo-200",
      description: "Digest rollup delivery for low/medium non-urgent alerts.",
      endpoint: "smtp://alerts.internal.corp:587",
    },
  ];

  const handleCopy = (url: string) => {
    navigator.clipboard.writeText(window.location.origin.replace("5173", "8000") + url);
    setCopiedUrl(url);
    setTimeout(() => setCopiedUrl(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-indigo-600" />
          <span>System Settings & Security Controls</span>
        </h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Configure proxy middleware, ingestion security, rate limiting, and webhook endpoints.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 space-x-6 text-xs font-medium overflow-x-auto no-scrollbar">
        {[
          { id: "system", label: "System & Architecture" },
          { id: "security", label: "Security & Rate Limiting" },
          { id: "notifications", label: "Notifications & Channels" },
          { id: "webhooks", label: "Webhook Endpoints" },
          { id: "database", label: "Database Persistence" },
          { id: "demo", label: "Demo Environment" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`pb-2.5 transition border-b-2 whitespace-nowrap ${
              activeTab === tab.id
                ? "border-indigo-600 text-indigo-600 font-semibold"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab: System & Architecture */}
      {activeTab === "system" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-xs">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Server className="w-4 h-4 text-indigo-600" />
              <span>Middleware Pipeline Status</span>
            </h3>
            <div className="space-y-3 text-xs">
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Pipeline Mode</span>
                <span className="font-semibold text-slate-900">Intelligent Proxy & Correlation</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">FastAPI Core Backend</span>
                <span className="font-semibold text-emerald-600">v1.4.0 (Operational)</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Sliding Dedup Engine</span>
                <span className="font-mono text-slate-700">30s Fingerprint Window</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Root Cause Engine</span>
                <span className="font-semibold text-slate-700">Topological BFS + Temporal Causality</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-slate-500">WebSocket Dispatcher</span>
                <span className="font-semibold text-emerald-600">Connected / Live</span>
              </div>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-xs">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Key className="w-4 h-4 text-purple-600" />
              <span>Authentication & Security</span>
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              API key authentication and per-source rate limiters protect the webhook ingestion endpoints from spam or unauthorized injection.
            </p>
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
              <div className="text-slate-500">Active Ingestion Auth Mode:</div>
              <div className="font-mono text-slate-800 font-bold">X-API-Key / X-Webhook-Secret Header Verification</div>
            </div>
            <button
              onClick={() => setActiveTab("security")}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition block"
            >
              View Security Controls & Audit Log →
            </button>
          </div>
        </div>
      )}

      {/* Tab: Security & Rate Limiting (Idea 10) */}
      {activeTab === "security" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-2">
              <div className="flex items-center space-x-2 text-indigo-600 font-bold text-xs uppercase tracking-wider">
                <Lock className="w-4 h-4" />
                <span>API-Key Ingest Auth</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Rejects unauthorized POST requests with <code>401 Unauthorized</code> unless valid <code>X-API-Key</code> or <code>X-Webhook-Secret</code> header is supplied.
              </p>
              <div className="pt-2 text-[11px] font-mono text-slate-500 bg-slate-50 p-2 rounded border border-slate-200">
                Header: X-API-Key: &lt;secret&gt;
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-2">
              <div className="flex items-center space-x-2 text-amber-600 font-bold text-xs uppercase tracking-wider">
                <Shield className="w-4 h-4" />
                <span>Per-Source Rate Limiter</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Limits bursts to <strong>150 req/min per monitoring source</strong> via sliding window algorithm, rejecting rogue senders with <code>429 Too Many Requests</code>.
              </p>
              <div className="pt-2 text-[11px] font-mono text-emerald-700 bg-emerald-50 p-2 rounded border border-emerald-200 font-bold">
                Status: Active (Sliding Window 60s)
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-2">
              <div className="flex items-center space-x-2 text-rose-600 font-bold text-xs uppercase tracking-wider">
                <ShieldAlert className="w-4 h-4" />
                <span>Payload Schema Gatekeeper</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Inspects incoming JSON structure before correlation. Rejects malformed junk with <code>400 Bad Request</code> early to protect downstream scoring.
              </p>
              <div className="pt-2 text-[11px] font-mono text-slate-500 bg-slate-50 p-2 rounded border border-slate-200">
                Enforces alert_name, service & labels
              </div>
            </div>
          </div>

          {/* Security Audit Log Table */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-rose-600" />
                  <span>Ingestion Security & Abuse Audit Log</span>
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Real-time circular audit trail of rejected requests, unauthorized probes, schema violations, and rate-limit triggers.
                </p>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={loadAuditLog}
                  disabled={loadingAudit}
                  className="px-2.5 py-1.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium transition flex items-center gap-1.5"
                  title="Refresh Audit Log"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingAudit ? "animate-spin text-indigo-600" : "text-slate-500"}`} />
                  <span>Refresh</span>
                </button>
                <button
                  onClick={handleClearAudit}
                  className="px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-rose-50 hover:text-rose-700 text-slate-600 text-xs font-medium transition flex items-center gap-1.5"
                  title="Clear Log"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Clear</span>
                </button>
              </div>
            </div>

            {auditEntries.length === 0 ? (
              <div className="py-10 text-center text-slate-400 space-y-2">
                <CheckCircle2 className="w-8 h-8 mx-auto text-emerald-500" />
                <p className="text-xs font-medium text-slate-600">All Clear — No Security Rejections Logged</p>
                <p className="text-[11px] text-slate-400">
                  Rate limits, schema checks, and authentication filters are standing by.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500 text-[11px] uppercase tracking-wider">
                      <th className="py-2.5 px-3 font-semibold">Timestamp</th>
                      <th className="py-2.5 px-3 font-semibold">Endpoint</th>
                      <th className="py-2.5 px-3 font-semibold">Source</th>
                      <th className="py-2.5 px-3 font-semibold">Client IP</th>
                      <th className="py-2.5 px-3 font-semibold">Code</th>
                      <th className="py-2.5 px-3 font-semibold">Rejection Reason</th>
                      <th className="py-2.5 px-3 font-semibold">Payload Excerpt</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {auditEntries.map((entry) => (
                      <tr key={entry.id} className="hover:bg-slate-50/80 transition">
                        <td className="py-2.5 px-3 text-slate-500 text-[11px] whitespace-nowrap">
                          {entry.iso_time ? entry.iso_time.replace("T", " ").replace("Z", "") : "--"}
                        </td>
                        <td className="py-2.5 px-3 font-semibold text-slate-800">{entry.endpoint}</td>
                        <td className="py-2.5 px-3 text-slate-700 font-medium">{entry.source}</td>
                        <td className="py-2.5 px-3 text-slate-500 text-[11px]">{entry.client_ip}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              entry.status_code === 401
                                ? "bg-purple-50 text-purple-700 border border-purple-200"
                                : entry.status_code === 429
                                ? "bg-amber-50 text-amber-700 border border-amber-200"
                                : "bg-rose-50 text-rose-700 border border-rose-200"
                            }`}
                          >
                            {entry.status_code} ({entry.reason})
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-sans text-slate-700 max-w-xs truncate">
                          {entry.reason === "AUTH_FAILED" && <span className="text-purple-700 font-medium">Authentication Failed (401)</span>}
                          {entry.reason === "RATE_LIMITED" && <span className="text-amber-700 font-medium">Per-Source Rate Limit Exceeded (429)</span>}
                          {entry.reason === "INVALID_SCHEMA" && <span className="text-rose-700 font-medium">Malformed Payload / Missing Schema (400)</span>}
                          {entry.reason !== "AUTH_FAILED" && entry.reason !== "RATE_LIMITED" && entry.reason !== "INVALID_SCHEMA" && entry.reason}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400 text-[10px] max-w-xs truncate" title={entry.payload_excerpt || ""}>
                          {entry.payload_excerpt || "--"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab: Notifications & Integrations */}
      {(activeTab === "notifications" || activeTab === "system") && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <h3 className="text-sm font-bold text-slate-900">Connected Channels & Services</h3>
          <div className="divide-y divide-slate-100">
            {integrations.map((item) => (
              <div key={item.name} className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div className="space-y-0.5">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-slate-900">{item.name}</span>
                    <span className="text-[10px] text-slate-400 font-mono">({item.type})</span>
                  </div>
                  <p className="text-slate-500 text-[11px]">{item.description}</p>
                </div>
                <div className="flex items-center space-x-3 flex-shrink-0">
                  <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold border ${item.badge}`}>
                    {item.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Webhooks */}
      {activeTab === "webhooks" && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Webhook className="w-4 h-4 text-indigo-600" />
            <span>Incoming Webhook Endpoints</span>
          </h3>
          <p className="text-xs text-slate-500">
            Send raw alerts to these endpoints with optional <code>X-API-Key</code> header for authenticated ingestion.
          </p>

          <div className="space-y-3 pt-2">
            {[
              { label: "Generic / Unified Ingestion", path: "/api/alerts/webhook" },
              { label: "Prometheus Alertmanager Ingestion", path: "/api/alerts/prometheus" },
              { label: "Datadog Monitor Webhook", path: "/api/alerts/datadog" },
            ].map((ep) => (
              <div key={ep.path} className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between gap-3 text-xs font-mono">
                <div>
                  <span className="text-[10px] text-slate-400 uppercase font-sans font-bold block">{ep.label}</span>
                  <span className="text-indigo-600 font-bold">http://localhost:8000{ep.path}</span>
                </div>
                <button
                  onClick={() => handleCopy(ep.path)}
                  className="px-2.5 py-1 rounded bg-white border border-slate-200 hover:bg-slate-100 text-slate-700 text-xs font-sans transition flex items-center gap-1"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>{copiedUrl === ep.path ? "Copied!" : "Copy URL"}</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Database */}
      {activeTab === "database" && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Database className="w-4 h-4 text-indigo-600" />
            <span>Telemetry Persistence & Storage</span>
          </h3>
          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Storage Backend</span>
              <span className="font-semibold text-slate-900">SQLite + SQLAlchemy ORM (WAL mode)</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Database File</span>
              <span className="font-mono text-slate-700">backend/alerts.db</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Lifecycle Engine</span>
              <span className="font-semibold text-slate-700">Thread-safe background batch flusher</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-500">Alert Retention</span>
              <span className="font-semibold text-slate-700">7 days with auto-compaction</span>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Demo Environment */}
      {activeTab === "demo" && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <PlayCircle className="w-4 h-4 text-indigo-600" />
            <span>Demo Mode & Simulator Setup</span>
          </h3>
          <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-2">
            <div className="font-semibold text-slate-900">Demo Telemetry Ready</div>
            <p className="text-slate-600">
              Navigate to the <strong>Alert Simulator</strong> tab to launch preset incident scenarios or clear existing records.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
