import React from "react";
import { IncidentItem } from "../../types";
import { AlertCircle, CheckCircle2, ChevronRight, Clock, Target } from "lucide-react";

interface RecentIncidentsProps {
  incidents: IncidentItem[];
  onSelectIncident: (inc: IncidentItem) => void;
  onViewAll: () => void;
}

export const RecentIncidents: React.FC<RecentIncidentsProps> = ({
  incidents,
  onSelectIncident,
  onViewAll,
}) => {
  return (
    <div className="glass-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-white">Active & Recent Incidents</h3>
          <p className="text-xs text-slate-400">Correlated incidents with identified root causes</p>
        </div>
        <button
          onClick={onViewAll}
          className="text-xs text-brand-400 hover:text-brand-300 font-medium flex items-center gap-1"
        >
          <span>View All</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {incidents.length === 0 ? (
        <div className="py-8 text-center text-slate-500 text-xs font-mono">
        </div>
      ) : (
        <div className="space-y-2.5">
          {incidents.slice(0, 5).map((inc) => {
            const isFiring = inc.status === "FIRING";
            return (
              <div
                key={inc.id}
                onClick={() => onSelectIncident(inc)}
                className="p-3.5 rounded-xl bg-dark-950/60 border border-slate-800 hover:border-slate-700 cursor-pointer transition flex items-center justify-between gap-4"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${isFiring
                          ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                          : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        }`}
                    >
                      {inc.status}
                    </span>
                    <span className="text-xs font-mono font-bold text-slate-300">{inc.id}</span>
                    <span className="text-xs font-bold text-white truncate">{inc.title}</span>
                  </div>

                  <div className="flex items-center space-x-3 text-xs text-slate-400">
                    <span className="flex items-center gap-1 text-cyan-400">
                      <Target className="w-3 h-3" />
                      Root Cause: <strong className="text-slate-200">{inc.root_cause_service}</strong>
                    </span>
                    <span>•</span>
                    <span>Confidence: {inc.confidence_score}%</span>
                    <span>•</span>
                    <span>{inc.alert_count} alerts</span>
                  </div>
                </div>

                <div className="text-right flex-shrink-0 space-y-0.5">
                  <div className="text-xs font-mono font-bold text-rose-600">
                    ${(inc.estimated_cost_loss || Math.round(500 + (inc.duration_seconds || 35) * 45)).toLocaleString()} loss
                  </div>
                  <div className="text-[11px] font-mono font-medium text-emerald-600">
                    {inc.suppressed_count} Suppressed
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono">
                    {inc.notifications_count} Paged
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
