import React, { useState, useEffect } from "react";
import {
  Sparkles,
  X,
  AlertTriangle,
  CheckCircle2,
  Layers,
  ShieldAlert,
  Target,
  Wrench,
  Flame,
  ArrowRight,
  RefreshCw
} from "lucide-react";
import { IncidentItem, AlertItem } from "../../types";
import { AIIncidentCopilotPanel } from "../Incidents/AIIncidentCopilotPanel";

interface AIFixSolutionModalProps {
  isOpen: boolean;
  onClose: () => void;
  incidents: IncidentItem[];
  alerts: AlertItem[];
  onUpdateIncident?: (updated: IncidentItem) => void;
}

export const AIFixSolutionModal: React.FC<AIFixSolutionModalProps> = ({
  isOpen,
  onClose,
  incidents,
  alerts,
  onUpdateIncident,
}) => {
  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Determine active incident to fix
  const activeIncident =
    incidents.find((i) => i.status === "FIRING") ||
    incidents[0] ||
    null;

  // Fallback: If no incident in DB, construct a virtual incident from active firing alerts
  const firingAlerts = alerts.filter((a) => a.status === "FIRING" || a.notification_status === "SENT");
  const primaryAlert = firingAlerts[0] || alerts[0] || null;

  const resolvedIncident: IncidentItem | null =
    activeIncident ||
    (primaryAlert
      ? {
          id: `INC-VIRTUAL-${primaryAlert.id}`,
          title: `Active Outage: ${primaryAlert.alert_name} on ${primaryAlert.service}`,
          root_cause_alert_id: primaryAlert.id,
          root_cause_service: primaryAlert.service,
          root_cause_alert_name: primaryAlert.alert_name,
          root_cause_reason: primaryAlert.message || "Active alert requiring automated AI resolution",
          confidence_score: 92.0,
          severity: (primaryAlert.severity || "HIGH").toUpperCase(),
          severity_score: 85.0,
          status: "FIRING",
          affected_services: Array.from(new Set(alerts.map((a) => a.service))).filter(Boolean),
          alert_count: alerts.length || 1,
          suppressed_count: alerts.filter((a) => a.notification_status === "SUPPRESSED").length,
          notifications_count: 1,
          created_at: primaryAlert.first_seen || new Date().toISOString(),
          updated_at: primaryAlert.last_seen || new Date().toISOString(),
          resolved_at: null,
          duration_seconds: primaryAlert.duration_seconds || 35,
          evidence: [primaryAlert.message],
        }
      : null);

  return (
    <div
      className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[92vh] overflow-y-auto rounded-2xl bg-white border border-slate-200 shadow-2xl p-6 space-y-5 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Bar */}
        <div className="flex items-start justify-between border-b border-slate-100 pb-4">
          <div className="flex items-start space-x-3">
            <div className="p-3 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-600 text-white shadow-xs flex-shrink-0">
              <Wrench className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-emerald-600" />
                  AI Fix Solution
                </span>
                <span className="text-xs font-mono text-slate-400">Automated Remediation</span>
              </div>
              <h2 className="text-lg font-bold text-slate-900 tracking-tight mt-1 flex items-center gap-2">
                <span>AI Error Fix & Incident Resolution</span>
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Evaluated from live telemetry stream, topological dependencies, and root-cause evidence.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition cursor-pointer"
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        {resolvedIncident ? (
          <div className="space-y-4">
            {/* Quick Context Summary Banner */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex items-center space-x-2 text-slate-700">
                <Target className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>
                  Target Outage: <strong className="text-slate-900">{resolvedIncident.title}</strong>
                </span>
              </div>
              <div className="flex items-center space-x-2 text-xs font-mono">
                <span className="px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200 font-bold uppercase">
                  {resolvedIncident.severity}
                </span>
                <span className="text-slate-400">•</span>
                <span className="text-indigo-600 font-semibold">{resolvedIncident.alert_count} Alerts</span>
                <span className="text-slate-400">•</span>
                <span className="text-emerald-600 font-semibold">{resolvedIncident.suppressed_count} Suppressed</span>
              </div>
            </div>

            {/* AI SRE Copilot Solution Panel */}
            <AIIncidentCopilotPanel
              incident={resolvedIncident}
              onUpdateIncident={onUpdateIncident}
              defaultExpanded={true}
            />
          </div>
        ) : (
          <div className="p-12 text-center space-y-3 bg-slate-50 rounded-xl border border-slate-200">
            <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
            <h3 className="text-sm font-bold text-slate-900">All Alert Signals are Healthy</h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              No active firing outage errors detected. Run an alert storm or database outage simulation to test the AI Fix Solution.
            </p>
          </div>
        )}

        {/* Footer */}
        <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <span className="text-[11px] text-slate-400 font-mono">
            Powered by Google Gemini SRE Copilot Engine
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-xs transition cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
