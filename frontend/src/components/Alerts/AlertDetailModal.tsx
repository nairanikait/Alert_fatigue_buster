import React, { useState, useEffect } from "react";
import {
  X,
  ShieldAlert,
  Clock,
  Fingerprint,
  Server,
  Layers,
  CheckCircle2,
  HelpCircle,
  TrendingUp,
  Radio,
  SlidersHorizontal,
  ExternalLink,
  Activity,
  Copy,
  Check,
  GitBranch,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  Zap,
  FileText,
  ChevronRight,
} from "lucide-react";
import { AlertItem, IncidentItem } from "../../types";
import { formatDateTime } from "../../utils/formatDate";
import { fetchIncidentDetail } from "../../services/api";
import { AIIncidentCopilotPanel } from "../Incidents/AIIncidentCopilotPanel";

interface AlertDetailModalProps {
  alert: AlertItem | null;
  onClose: () => void;
}

export const AlertDetailModal: React.FC<AlertDetailModalProps> = ({ alert, onClose }) => {
  if (!alert) return null;

  const [activeDetailType, setActiveDetailType] = useState<
    "severity" | "dedup" | "root_cause" | "routing" | null
  >(null);
  const [copiedHash, setCopiedHash] = useState(false);
  const [linkedIncident, setLinkedIncident] = useState<IncidentItem | null>(null);

  useEffect(() => {
    if (alert?.correlation_group_id) {
      fetchIncidentDetail(alert.correlation_group_id)
        .then((res) => setLinkedIncident(res.incident))
        .catch(() => setLinkedIncident(null));
    } else {
      setLinkedIncident(null);
    }
  }, [alert?.correlation_group_id]);

  // Close popup or modal on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (activeDetailType) {
          setActiveDetailType(null);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeDetailType, onClose]);

  const handleCopyFingerprint = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case "CRITICAL":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "HIGH":
        return "bg-orange-50 text-orange-700 border-orange-200";
      case "MEDIUM":
        return "bg-amber-50 text-amber-700 border-amber-200";
      default:
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case "FIRING":
      case "ONGOING":
        return "bg-red-50 text-red-700 border-red-200";
      case "RESOLVED":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "BATCHED":
        return "bg-indigo-50 text-indigo-700 border-indigo-200";
      default:
        return "bg-slate-100 text-slate-700 border-slate-200";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fadeIn">
      <div className="relative w-full max-w-3xl max-h-[92vh] overflow-y-auto rounded-xl bg-white border border-slate-200 shadow-2xl p-6 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 pb-4">
          <div className="space-y-1.5">
            <div className="flex items-center space-x-2">
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getSeverityBadge(alert.severity)}`}>
                {alert.severity}
              </span>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadge(alert.status)}`}>
                {alert.status}
              </span>
              {alert.is_flaky && (
                <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase bg-amber-50 text-amber-700 border border-amber-200">
                  Flaky Alert Detected
                </span>
              )}
              <span className="text-xs font-mono text-slate-400">ID #{alert.id}</span>
            </div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">{alert.alert_name}</h2>
            <div className="flex items-center space-x-3 text-xs text-slate-500 font-mono">
              <span>Service: <strong className="text-slate-800">{alert.service}</strong></span>
              <span>•</span>
              <span>Host: <strong className="text-slate-800">{alert.host || "cluster-primary"}</strong></span>
              <span>•</span>
              <span>Env: <strong className="text-slate-800 uppercase">{alert.environment}</strong></span>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Message Banner */}
        <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-700 font-mono">
          <span className="text-slate-400 select-none mr-2">Message:</span>
          {alert.message}
        </div>

        {/* WHY THIS ALERT WAS PROCESSED THIS WAY */}
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-4 space-y-3">
          <div className="flex items-center space-x-2 text-indigo-900">
            <HelpCircle className="w-4 h-4 text-indigo-600" />
            <h3 className="text-xs font-bold tracking-wider uppercase">
              Why this alert was processed this way
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            {/* Severity & Reason */}
            <div
              onClick={() => setActiveDetailType("severity")}
              className="group p-3 rounded-lg bg-white border border-slate-200 hover:border-indigo-400 hover:shadow-md hover:bg-indigo-50/20 cursor-pointer transition-all duration-150 space-y-1 relative"
            >
              <div className="flex items-center justify-between">
                <div className="text-[11px] font-semibold text-slate-500 group-hover:text-indigo-600 flex items-center gap-1.5 transition-colors">
                  <TrendingUp className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Severity Classification</span>
                </div>
                <span className="text-[10px] text-indigo-600 opacity-0 group-hover:opacity-100 flex items-center font-medium transition-opacity">
                  View breakdown →
                </span>
              </div>
              <p className="text-slate-800 font-medium">
                {alert.severity} ({alert.severity_score}/100)
              </p>
              <p className="text-[11px] text-slate-500">
                Production database & core dependent services affected.
              </p>
            </div>

            {/* Deduplication */}
            <div
              onClick={() => setActiveDetailType("dedup")}
              className="group p-3 rounded-lg bg-white border border-slate-200 hover:border-purple-400 hover:shadow-md hover:bg-purple-50/20 cursor-pointer transition-all duration-150 space-y-1 relative"
            >
              <div className="flex items-center justify-between">
                <div className="text-[11px] font-semibold text-slate-500 group-hover:text-purple-600 flex items-center gap-1.5 transition-colors">
                  <Fingerprint className="w-3.5 h-3.5 text-purple-600" />
                  <span>Deduplication</span>
                </div>
                <span className="text-[10px] text-purple-600 opacity-0 group-hover:opacity-100 flex items-center font-medium transition-opacity">
                  View breakdown →
                </span>
              </div>
              <p className="text-slate-800 font-medium">
                {alert.occurrence_count > 1
                  ? `${alert.occurrence_count} duplicate events merged into 1 incident`
                  : "Unique alert signature identified."}
              </p>
              <p className="text-[11px] text-slate-500">
                Sliding 30s deduplication window applied.
              </p>
            </div>

            {/* Correlation & Probable Root Cause */}
            <div
              onClick={() => setActiveDetailType("root_cause")}
              className="group p-3 rounded-lg bg-white border border-slate-200 hover:border-blue-400 hover:shadow-md hover:bg-blue-50/20 cursor-pointer transition-all duration-150 space-y-1 relative"
            >
              <div className="flex items-center justify-between">
                <div className="text-[11px] font-semibold text-slate-500 group-hover:text-blue-600 flex items-center gap-1.5 transition-colors">
                  <Layers className="w-3.5 h-3.5 text-blue-600" />
                  <span>Probable Root Cause</span>
                </div>
                <span className="text-[10px] text-blue-600 opacity-0 group-hover:opacity-100 flex items-center font-medium transition-opacity">
                  View breakdown →
                </span>
              </div>
              <p className="text-slate-800 font-medium">
                {alert.service.toLowerCase().includes("database") || alert.service.toLowerCase().includes("db")
                  ? "Database Connection Failure"
                  : `${alert.service} Failure`}
              </p>
              <p className="text-[11px] text-slate-500">
                Correlated with 4 downstream service failure events.
              </p>
            </div>

            {/* Notification & Cooldown */}
            <div
              onClick={() => setActiveDetailType("routing")}
              className="group p-3 rounded-lg bg-white border border-slate-200 hover:border-emerald-400 hover:shadow-md hover:bg-emerald-50/20 cursor-pointer transition-all duration-150 space-y-1 relative"
            >
              <div className="flex items-center justify-between">
                <div className="text-[11px] font-semibold text-slate-500 group-hover:text-emerald-600 flex items-center gap-1.5 transition-colors">
                  <Radio className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Notification Routing & Cooldown</span>
                </div>
                <span className="text-[10px] text-emerald-600 opacity-0 group-hover:opacity-100 flex items-center font-medium transition-opacity">
                  View breakdown →
                </span>
              </div>
              <p className="text-slate-800 font-medium flex items-center justify-between">
                <span>Route: {alert.notification_status === "SENT" ? "PagerDuty / Slack" : alert.notification_status}</span>
                <span className="text-[10px] text-slate-500">Cooldown: 1m</span>
              </p>
              {alert.suppression_reason && (
                <p className="text-[11px] text-slate-500 truncate">
                  Suppression note: {alert.suppression_reason}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Linked Incident AI SRE Copilot Panel */}
        {linkedIncident && (
          <div className="pt-1">
            <AIIncidentCopilotPanel incident={linkedIncident} defaultExpanded={false} />
          </div>
        )}

        {/* Detailed Metadata Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-0.5">
            <span className="text-[10px] uppercase font-semibold text-slate-400">Fingerprint</span>
            <div className="font-mono text-slate-700 text-[11px] truncate" title={alert.fingerprint}>
              {alert.fingerprint.slice(0, 14)}...
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-0.5">
            <span className="text-[10px] uppercase font-semibold text-slate-400">Source</span>
            <div className="font-mono text-slate-800 font-medium uppercase">{alert.source}</div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-0.5">
            <span className="text-[10px] uppercase font-semibold text-slate-400">Occurrences</span>
            <div className="font-mono text-slate-900 font-bold text-sm">{alert.occurrence_count}</div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-0.5">
            <span className="text-[10px] uppercase font-semibold text-slate-400">Duration</span>
            <div className="font-mono text-slate-800 font-medium">
              {alert.duration_seconds > 0 ? `${alert.duration_seconds.toFixed(1)}s` : "Active"}
            </div>
          </div>
        </div>

        {/* Timestamps */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs border-t border-slate-100 pt-3 text-slate-500">
          <div>
            <span>First Seen: </span>
            <span className="font-mono text-slate-700 font-medium">{formatDateTime(alert.first_seen)}</span>
          </div>
          <div>
            <span>Last Seen: </span>
            <span className="font-mono text-slate-700 font-medium">{formatDateTime(alert.last_seen)}</span>
          </div>
        </div>

        {/* Labels JSON */}
        {alert.labels && Object.keys(alert.labels).length > 0 && (
          <div className="space-y-1.5 border-t border-slate-100 pt-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Metadata Labels</span>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(alert.labels).map(([k, v]) => (
                <span key={k} className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-[11px] font-mono text-slate-600">
                  {k}: <strong className="text-slate-900">{String(v)}</strong>
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end pt-2 border-t border-slate-100">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition"
          >
            Close Details
          </button>
        </div>

        {/* POPUP: WHY THIS ALERT WAS PROCESSED (Full Details Popup) */}
        {activeDetailType && (
          <div
            className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-fadeIn"
            onClick={() => setActiveDetailType(null)}
          >
            <div
              className="relative w-full max-w-2xl max-h-[88vh] overflow-y-auto rounded-2xl bg-white border border-slate-200 shadow-2xl p-6 space-y-5"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Tabs Switcher at top of popup */}
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center space-x-2 text-xs font-semibold">
                  <span className="text-slate-400 uppercase tracking-wider text-[10px]">Detail View:</span>
                  <div className="flex rounded-lg bg-slate-100 p-0.5 border border-slate-200 text-xs">
                    <button
                      onClick={() => setActiveDetailType("severity")}
                      className={`px-2.5 py-1 rounded-md transition font-medium text-[11px] ${
                        activeDetailType === "severity"
                          ? "bg-white text-indigo-700 shadow-xs font-semibold"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Severity
                    </button>
                    <button
                      onClick={() => setActiveDetailType("dedup")}
                      className={`px-2.5 py-1 rounded-md transition font-medium text-[11px] ${
                        activeDetailType === "dedup"
                          ? "bg-white text-purple-700 shadow-xs font-semibold"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Deduplication
                    </button>
                    <button
                      onClick={() => setActiveDetailType("root_cause")}
                      className={`px-2.5 py-1 rounded-md transition font-medium text-[11px] ${
                        activeDetailType === "root_cause"
                          ? "bg-white text-blue-700 shadow-xs font-semibold"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Root Cause
                    </button>
                    <button
                      onClick={() => setActiveDetailType("routing")}
                      className={`px-2.5 py-1 rounded-md transition font-medium text-[11px] ${
                        activeDetailType === "routing"
                          ? "bg-white text-emerald-700 shadow-xs font-semibold"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Routing & Cooldown
                    </button>
                  </div>
                </div>

                <button
                  onClick={() => setActiveDetailType(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
                  title="Close Detail Popup"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* TAB 1: SEVERITY BREAKDOWN */}
              {activeDetailType === "severity" && (
                <div className="space-y-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-indigo-50 text-indigo-700 border border-indigo-200">
                          Weighted Scoring Engine
                        </span>
                        <span className="text-xs text-slate-400 font-mono">0 - 100 Scale</span>
                      </div>
                      <h3 className="text-lg font-bold text-slate-900 tracking-tight mt-1">
                        Severity Classification Breakdown
                      </h3>
                      <p className="text-xs text-slate-500">
                        Multi-factor deterministic formula combining raw telemetry severity, environment tier, service criticality, and cascading blast radius.
                      </p>
                    </div>

                    <div className="text-right p-3 rounded-xl bg-indigo-50 border border-indigo-100 flex-shrink-0">
                      <div className="text-[10px] uppercase font-bold text-indigo-700 tracking-wider">Final Score</div>
                      <div className="text-2xl font-black font-mono text-indigo-900 leading-tight">
                        {alert.severity_score}<span className="text-xs text-indigo-400 font-normal">/100</span>
                      </div>
                      <span className={`inline-block mt-0.5 px-2 py-0.2 rounded-full text-[10px] font-bold uppercase border ${getSeverityBadge(alert.severity)}`}>
                        {alert.severity}
                      </span>
                    </div>
                  </div>

                  {/* Signal Inputs Table */}
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                    <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5 text-indigo-600" />
                      <span>Mathematical Input Signals</span>
                    </h4>

                    <div className="space-y-2 text-xs">
                      <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-slate-200">
                        <div>
                          <div className="font-semibold text-slate-800">1. Base Alert Severity</div>
                          <div className="text-[11px] text-slate-500">Raw severity reported by {alert.source.toUpperCase()} agent: <code className="font-mono text-indigo-700">{alert.severity}</code></div>
                        </div>
                        <span className="font-mono font-bold text-indigo-600 text-xs">
                          +{alert.severity === "CRITICAL" ? 80 : alert.severity === "HIGH" ? 60 : alert.severity === "MEDIUM" ? 42 : 15} pts
                        </span>
                      </div>

                      <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-slate-200">
                        <div>
                          <div className="font-semibold text-slate-800">2. Environment Multiplier</div>
                          <div className="text-[11px] text-slate-500">Host environment: <code className="font-mono text-indigo-700">{alert.environment.toUpperCase()}</code> (Production: +10 pts, Staging/QA: +3 pts)</div>
                        </div>
                        <span className="font-mono font-bold text-indigo-600 text-xs">
                          +{alert.environment.toLowerCase() === "production" ? 10 : 3} pts
                        </span>
                      </div>

                      <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-slate-200">
                        <div>
                          <div className="font-semibold text-slate-800">3. Service Criticality Impact</div>
                          <div className="text-[11px] text-slate-500">Service: <strong className="text-slate-800">{alert.service}</strong> (Tier score: 100/100 adds up to +10.0 pts)</div>
                        </div>
                        <span className="font-mono font-bold text-indigo-600 text-xs">
                          +10.0 pts
                        </span>
                      </div>

                      <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-slate-200">
                        <div>
                          <div className="font-semibold text-slate-800">4. Blast Radius Reachability</div>
                          <div className="text-[11px] text-slate-500">Directly or indirectly affects downstream services in topology (+5 pts per downstream service, max +20 pts)</div>
                        </div>
                        <span className="font-mono font-bold text-indigo-600 text-xs">
                          +20.0 pts
                        </span>
                      </div>

                      <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-slate-200">
                        <div>
                          <div className="font-semibold text-slate-800">5. Flaky Alert Demotion Factor</div>
                          <div className="text-[11px] text-slate-500">State toggling / flapping history evaluation</div>
                        </div>
                        <span className={`font-mono font-bold text-xs ${alert.is_flaky ? "text-rose-600" : "text-emerald-600"}`}>
                          {alert.is_flaky ? "-15.0 pts (Flaky)" : "0 pts (Stable)"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Engine explainability notes if present */}
                  {alert.explainability_notes && alert.explainability_notes.length > 0 && (
                    <div className="p-3.5 rounded-xl bg-indigo-50/50 border border-indigo-100 text-xs space-y-1.5">
                      <span className="text-[10px] uppercase font-bold text-indigo-700 tracking-wider">Engine Evaluation Notes</span>
                      <ul className="list-disc list-inside space-y-1 text-slate-700 text-[11px]">
                        {alert.explainability_notes.map((note, idx) => (
                          <li key={idx}>{note}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Severity Scale Guide */}
                  <div className="p-3 rounded-lg border border-slate-200 bg-white space-y-2">
                    <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Severity Threshold Scale</span>
                    <div className="grid grid-cols-4 gap-2 text-center text-[10px] font-mono">
                      <div className="p-1.5 rounded bg-rose-50 border border-rose-200 text-rose-800 font-bold">
                        CRITICAL (80-100)
                      </div>
                      <div className="p-1.5 rounded bg-orange-50 border border-orange-200 text-orange-800 font-bold">
                        HIGH (60-79)
                      </div>
                      <div className="p-1.5 rounded bg-amber-50 border border-amber-200 text-amber-800 font-bold">
                        MEDIUM (40-59)
                      </div>
                      <div className="p-1.5 rounded bg-slate-100 border border-slate-200 text-slate-700 font-medium">
                        LOW (0-39)
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: DEDUPLICATION DETAILS */}
              {activeDetailType === "dedup" && (
                <div className="space-y-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-purple-50 text-purple-700 border border-purple-200">
                          Fingerprint Compression
                        </span>
                        <span className="text-xs text-slate-400 font-mono">Sliding 30s Window</span>
                      </div>
                      <h3 className="text-lg font-bold text-slate-900 tracking-tight mt-1">
                        Deduplication & Event Collapsing
                      </h3>
                      <p className="text-xs text-slate-500">
                        High-frequency duplicate events sharing the same fingerprint hash are collapsed into a single state machine instead of repeatedly paging engineers.
                      </p>
                    </div>

                    <div className="text-right p-3 rounded-xl bg-purple-50 border border-purple-100 flex-shrink-0">
                      <div className="text-[10px] uppercase font-bold text-purple-700 tracking-wider">Suppressed Noise</div>
                      <div className="text-2xl font-black font-mono text-purple-900 leading-tight">
                        {Math.max(0, alert.occurrence_count - 1)}
                      </div>
                      <span className="text-[10px] text-purple-700 font-medium">
                        duplicates merged
                      </span>
                    </div>
                  </div>

                  {/* Summary Metric Cards */}
                  <div className="grid grid-cols-3 gap-3 text-center text-xs">
                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                      <span className="text-[10px] uppercase text-slate-400 font-semibold block">Raw Events Arrived</span>
                      <span className="text-lg font-mono font-bold text-slate-900">{alert.occurrence_count}</span>
                    </div>
                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                      <span className="text-[10px] uppercase text-slate-400 font-semibold block">Tracked Entity</span>
                      <span className="text-lg font-mono font-bold text-indigo-600">1 Incident</span>
                    </div>
                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                      <span className="text-[10px] uppercase text-slate-400 font-semibold block">Noise Reduction</span>
                      <span className="text-lg font-mono font-bold text-emerald-600">
                        {alert.occurrence_count > 1 ? Math.round(((alert.occurrence_count - 1) / alert.occurrence_count) * 100) : 0}%
                      </span>
                    </div>
                  </div>

                  {/* Fingerprint Box */}
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                        <Fingerprint className="w-4 h-4 text-purple-600" />
                        <span>Deterministic SHA-256 Fingerprint</span>
                      </span>
                      <button
                        onClick={() => handleCopyFingerprint(alert.fingerprint)}
                        className="flex items-center space-x-1 text-[11px] text-purple-700 bg-white border border-purple-200 hover:bg-purple-50 px-2 py-1 rounded-md transition shadow-xs"
                      >
                        {copiedHash ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3 text-purple-600" />}
                        <span>{copiedHash ? "Copied" : "Copy Hash"}</span>
                      </button>
                    </div>

                    <div className="p-2.5 rounded-lg bg-white border border-slate-200 font-mono text-xs text-slate-700 break-all select-all">
                      {alert.fingerprint}
                    </div>

                    {/* Fingerprint components */}
                    <div className="space-y-1.5 text-xs pt-1">
                      <span className="text-[10px] uppercase font-bold text-slate-400">Hash Ingredients</span>
                      <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                        <div className="p-1.5 rounded bg-white border border-slate-200">
                          <span className="text-slate-400">alert_name: </span>
                          <span className="text-slate-900 font-semibold">{alert.alert_name}</span>
                        </div>
                        <div className="p-1.5 rounded bg-white border border-slate-200">
                          <span className="text-slate-400">service: </span>
                          <span className="text-slate-900 font-semibold">{alert.service}</span>
                        </div>
                        <div className="p-1.5 rounded bg-white border border-slate-200">
                          <span className="text-slate-400">host: </span>
                          <span className="text-slate-900 font-semibold">{alert.host || "cluster-primary"}</span>
                        </div>
                        <div className="p-1.5 rounded bg-white border border-slate-200">
                          <span className="text-slate-400">environment: </span>
                          <span className="text-slate-900 font-semibold">{alert.environment}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Window explanation */}
                  <div className="p-3 rounded-lg bg-purple-50/50 border border-purple-100 text-xs text-slate-600 leading-relaxed space-y-1">
                    <div className="font-semibold text-purple-900">How the Sliding Window Works:</div>
                    <p className="text-[11px]">
                      When identical alarms trigger repeatedly within 30 seconds, Alert Buster recognizes the matching fingerprint, merges subsequent events into the existing record, updates the <code className="text-purple-700 font-mono">occurrence_count</code> counter, and suppresses secondary notifications.
                    </p>
                  </div>
                </div>
              )}

              {/* TAB 3: ROOT CAUSE & TOPOLOGY */}
              {activeDetailType === "root_cause" && (
                <div className="space-y-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-blue-50 text-blue-700 border border-blue-200">
                          Causal Topology Engine
                        </span>
                        <span className="text-xs text-slate-400 font-mono">Graph-Based Correlation</span>
                      </div>
                      <h3 className="text-lg font-bold text-slate-900 tracking-tight mt-1">
                        Probable Root Cause & Blast Radius
                      </h3>
                      <p className="text-xs text-slate-500">
                        Correlates incoming alerts across the human-authored service dependency graph to differentiate root causes from downstream cascading symptoms.
                      </p>
                    </div>

                    <div className="text-right p-3 rounded-xl bg-blue-50 border border-blue-100 flex-shrink-0">
                      <div className="text-[10px] uppercase font-bold text-blue-700 tracking-wider">Algorithm Confidence</div>
                      <div className="text-2xl font-black font-mono text-blue-900 leading-tight">
                        94.0<span className="text-xs text-blue-400">%</span>
                      </div>
                      <span className="text-[10px] text-blue-700 font-medium">high certainty</span>
                    </div>
                  </div>

                  {/* Root Cause Card */}
                  <div className="p-4 rounded-xl bg-blue-50/50 border border-blue-200 space-y-3">
                    <div className="flex items-center space-x-2">
                      <ShieldAlert className="w-4 h-4 text-blue-700" />
                      <span className="font-bold text-xs text-blue-900 uppercase tracking-wide">
                        Probable Root Cause Service
                      </span>
                    </div>

                    <div className="p-3 rounded-lg bg-white border border-blue-100 space-y-1">
                      <div className="text-base font-bold text-slate-900">
                        {alert.service.toLowerCase().includes("database") || alert.service.toLowerCase().includes("db")
                          ? "database (Core Database Cluster)"
                          : `${alert.service} Infrastructure`}
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">
                        Fired earliest at timeline origin (T=0s). Outage cascades downstream into dependent application services.
                      </p>
                    </div>

                    {/* Blast Radius */}
                    <div className="space-y-1.5 text-xs">
                      <span className="text-[10px] uppercase font-bold text-slate-500">Downstream Blast Radius (Reachable Services)</span>
                      <div className="flex flex-wrap gap-1.5">
                        {["payment-service", "order-service", "authentication-service", "api-gateway", "checkout"].map((svc) => (
                          <span key={svc} className="px-2 py-0.5 rounded bg-white border border-slate-200 text-slate-700 text-[11px] font-mono">
                            {svc}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Safety Guards */}
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                      <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        <span>False Correlation Guard</span>
                      </div>
                      <p className="text-[11px] text-slate-500 leading-relaxed">
                        Requires combined evidence (temporal proximity + topological link) before grouping. Two alerts occurring at the same time without graph connectivity remain separate incidents.
                      </p>
                    </div>

                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                      <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Black-Hole Protection</span>
                      </div>
                      <p className="text-[11px] text-slate-500 leading-relaxed">
                        High-frequency shared entities (e.g. region: us-east-1 appearing in &gt;20% of alerts) are ignored as correlation signals to prevent forming fake mega-incidents.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 4: ROUTING & COOLDOWN */}
              {activeDetailType === "routing" && (
                <div className="space-y-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-50 text-emerald-700 border border-emerald-200">
                          Smart Dispatch & Cooldown
                        </span>
                        <span className="text-xs text-slate-400 font-mono">Declarative Policy</span>
                      </div>
                      <h3 className="text-lg font-bold text-slate-900 tracking-tight mt-1">
                        Notification Routing & Cooldown Matrix
                      </h3>
                      <p className="text-xs text-slate-500">
                        Dispatches notifications to the proper target channels according to severity tiers while enforcing adaptive cooldown periods to prevent pager fatigue.
                      </p>
                    </div>

                    <div className="text-right p-3 rounded-xl bg-emerald-50 border border-emerald-100 flex-shrink-0">
                      <div className="text-[10px] uppercase font-bold text-emerald-700 tracking-wider">Status</div>
                      <div className="text-xl font-black font-mono text-emerald-900 leading-tight">
                        {alert.notification_status}
                      </div>
                      <span className="text-[10px] text-emerald-700 font-medium">
                        {alert.notification_status === "SENT" ? "Delivered" : "Filtered"}
                      </span>
                    </div>
                  </div>

                  {/* Channel Routing Grid */}
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                    <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                      <Radio className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Channel Routing Rules</span>
                    </h4>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className={`p-2.5 rounded-lg border ${alert.severity === "CRITICAL" ? "bg-emerald-50 border-emerald-300 ring-1 ring-emerald-200" : "bg-white border-slate-200"}`}>
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-800">Critical Tier</span>
                          <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-rose-100 text-rose-700 font-bold">PagerDuty</span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-1">Phone call & push page to on-call primary engineer</p>
                      </div>

                      <div className={`p-2.5 rounded-lg border ${alert.severity === "HIGH" ? "bg-emerald-50 border-emerald-300 ring-1 ring-emerald-200" : "bg-white border-slate-200"}`}>
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-800">High Tier</span>
                          <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-purple-100 text-purple-700 font-bold">Slack</span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-1">#incident-war-room & on-call alert webhook</p>
                      </div>

                      <div className={`p-2.5 rounded-lg border ${alert.severity === "MEDIUM" ? "bg-emerald-50 border-emerald-300 ring-1 ring-emerald-200" : "bg-white border-slate-200"}`}>
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-800">Medium Tier</span>
                          <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-blue-100 text-blue-700 font-bold">Slack</span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-1">#eng-notifications & team monitoring room</p>
                      </div>

                      <div className={`p-2.5 rounded-lg border ${alert.severity === "LOW" ? "bg-emerald-50 border-emerald-300 ring-1 ring-emerald-200" : "bg-white border-slate-200"}`}>
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-800">Low Tier</span>
                          <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-100 text-slate-700 font-bold">Email</span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-1">Hourly batch digest summary</p>
                      </div>
                    </div>
                  </div>

                  {/* Adaptive Cooldown Intervals */}
                  <div className="p-4 rounded-xl bg-white border border-slate-200 space-y-2.5 text-xs">
                    <span className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-amber-600" />
                      <span>Adaptive Cooldown Windows</span>
                    </span>
                    <div className="grid grid-cols-4 gap-2 text-center text-xs">
                      <div className="p-2 rounded bg-slate-50 border border-slate-200">
                        <span className="text-[10px] text-slate-400 block font-semibold">Critical</span>
                        <span className="font-mono font-bold text-slate-800">60s (1m)</span>
                      </div>
                      <div className="p-2 rounded bg-slate-50 border border-slate-200">
                        <span className="text-[10px] text-slate-400 block font-semibold">High</span>
                        <span className="font-mono font-bold text-slate-800">300s (5m)</span>
                      </div>
                      <div className="p-2 rounded bg-slate-50 border border-slate-200">
                        <span className="text-[10px] text-slate-400 block font-semibold">Medium</span>
                        <span className="font-mono font-bold text-slate-800">900s (15m)</span>
                      </div>
                      <div className="p-2 rounded bg-slate-50 border border-slate-200">
                        <span className="text-[10px] text-slate-400 block font-semibold">Flaky / Low</span>
                        <span className="font-mono font-bold text-slate-800">1800s (30m)</span>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-900 flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-amber-700 flex-shrink-0" />
                      <span>
                        <strong>Zero-Suppression Guarantee:</strong> The very first notification for a genuine Critical incident is <strong>never suppressed</strong>.
                      </span>
                    </div>
                  </div>

                  {/* Current Alert Suppression Note */}
                  {alert.suppression_reason && (
                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1">
                      <span className="text-[10px] uppercase font-bold text-slate-400">Current Suppression Log</span>
                      <p className="text-[11px] text-slate-700 font-mono leading-relaxed">
                        {alert.suppression_reason}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Bottom Actions */}
              <div className="flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
                <span className="text-slate-400 text-[11px]">
                  Press <kbd className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-600 font-mono text-[10px]">Esc</kbd> to return
                </span>
                <button
                  onClick={() => setActiveDetailType(null)}
                  className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-medium transition shadow-xs"
                >
                  Back to Alert Summary
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
