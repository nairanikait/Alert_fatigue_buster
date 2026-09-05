import React from "react";
import { ShieldAlert, AlertTriangle, ChevronRight, Clock, Layers, ArrowUpRight } from "lucide-react";
import { IncidentItem } from "../../types";

interface IncidentOverviewCardProps {
  incidents: IncidentItem[];
  onViewIncident: (inc: IncidentItem) => void;
  onViewAll: () => void;
}

export const IncidentOverviewCard: React.FC<IncidentOverviewCardProps> = ({
  incidents,
  onViewIncident,
  onViewAll,
}) => {
  // Pick active firing incident or fallback to most recent or default template
  const active = incidents.find((i) => i.status === "FIRING") || incidents[0];

  const title = active ? active.title : "Database Connection Failure";
  const incidentId = active ? active.id : "INC-2024-001";
  const severity = active ? active.severity : "CRITICAL";
  const reason = active
    ? active.root_cause_reason
    : "Database connectivity issues causing cascading failures in dependent services.";
  const affectedServices = active?.affected_services?.length
    ? active.affected_services
    : ["Payment", "Orders", "Authentication", "API Gateway", "Checkout"];
  const alertCount = active ? active.alert_count : 24;
  const durationText = active && active.duration_seconds > 0
    ? `${Math.floor(active.duration_seconds / 60)}m ${Math.floor(active.duration_seconds % 60)}s`
    : "2m 34s";

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-sm space-y-4 flex flex-col justify-between">
      <div className="space-y-3">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2">
            <span className="p-1.5 rounded bg-red-50 text-red-600 border border-red-100">
              <ShieldAlert className="w-4 h-4" />
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Incident Overview</h3>
              <p className="text-[11px] text-slate-500">Primary active or recent incident</p>
            </div>
          </div>

          <button
            onClick={onViewAll}
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition flex items-center gap-0.5"
          >
            <span>All Incidents</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Incident Content */}
        <div className="p-3.5 rounded-lg border border-red-200 bg-red-50/30 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs font-semibold text-slate-700">{incidentId}</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-red-100 text-red-700 border border-red-200">
              {severity}
            </span>
          </div>

          <h4 className="text-sm font-bold text-slate-900 leading-snug">{title}</h4>
          <p className="text-xs text-slate-600 leading-relaxed line-clamp-2">{reason}</p>

          {/* Affected Services */}
          <div className="space-y-1 pt-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Affected Services:
            </span>
            <div className="flex flex-wrap gap-1">
              {affectedServices.slice(0, 3).map((s) => (
                <span
                  key={s}
                  className="px-2 py-0.5 rounded bg-white border border-slate-200 text-slate-700 text-[11px] font-medium"
                >
                  {s}
                </span>
              ))}
              {affectedServices.length > 3 && (
                <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[11px] font-medium">
                  +{affectedServices.length - 3} more
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Incident Metrics */}
        <div className="grid grid-cols-3 gap-2 text-center text-xs pt-1">
          <div className="p-2 rounded bg-slate-50 border border-slate-100">
            <div className="text-[10px] text-slate-500">Started</div>
            <div className="font-semibold text-slate-800 font-mono">2m ago</div>
          </div>
          <div className="p-2 rounded bg-slate-50 border border-slate-100">
            <div className="text-[10px] text-slate-500">Duration</div>
            <div className="font-semibold text-slate-800 font-mono">{durationText}</div>
          </div>
          <div className="p-2 rounded bg-slate-50 border border-slate-100">
            <div className="text-[10px] text-slate-500">Alerts</div>
            <div className="font-semibold text-slate-800 font-mono">{alertCount}</div>
          </div>
        </div>
      </div>

      <button
        onClick={() => active && onViewIncident(active)}
        className="w-full py-2 px-3 rounded-md bg-white hover:bg-slate-50 text-slate-700 font-semibold text-xs border border-slate-300 shadow-xs transition flex items-center justify-center space-x-1.5"
      >
        <span>View Incident Details</span>
        <ArrowUpRight className="w-3.5 h-3.5 text-slate-500" />
      </button>
    </div>
  );
};
