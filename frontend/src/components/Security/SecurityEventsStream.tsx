import React from "react";
import { Activity, ShieldX, ShieldAlert, ShieldCheck, Zap, RefreshCw } from "lucide-react";

interface SecurityEventsStreamProps {
  events: any[];
  loading: boolean;
}

export const SecurityEventsStream: React.FC<SecurityEventsStreamProps> = ({ events, loading }) => {
  const getActionBadge = (action: string) => {
    switch (action) {
      case "BLOCKED":
        return "bg-red-50 text-red-700 border-red-200";
      case "QUARANTINED":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "THROTTLED":
        return "bg-purple-50 text-purple-700 border-purple-200";
      case "ACCEPTED":
      default:
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
    }
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case "BLOCKED":
        return ShieldX;
      case "QUARANTINED":
        return ShieldAlert;
      case "THROTTLED":
        return Zap;
      case "ACCEPTED":
      default:
        return ShieldCheck;
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden flex flex-col h-[340px]">
      <div className="p-3 border-b border-slate-200 flex items-center justify-between bg-slate-50/70 flex-shrink-0">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-indigo-600" />
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
            Live Security Audit Trail
          </h3>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
          <span className="text-[11px] font-semibold text-slate-500 uppercase font-mono">
            {events.length} Events Logged
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-slate-100 font-mono text-xs">
        {events.length === 0 ? (
          <div className="p-8 text-center text-slate-400">
            <p>No security audit events recorded yet.</p>
          </div>
        ) : (
          events.map((evt) => {
            const ActionIcon = getActionIcon(evt.action);
            const timeStr = evt.created_at
              ? new Date(evt.created_at).toLocaleTimeString()
              : "Just now";

            return (
              <div key={evt.id} className="p-2.5 hover:bg-slate-50/80 transition-colors flex items-start justify-between space-x-3">
                <div className="flex items-start space-x-2.5">
                  <span className="text-slate-400 text-[11px] font-mono mt-0.5 whitespace-nowrap">
                    {timeStr}
                  </span>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-slate-800">{evt.event_type}</span>
                      <span className="text-[10px] text-slate-400">•</span>
                      <span className="text-slate-500 font-medium">Source: {evt.source}</span>
                    </div>
                    <p className="text-slate-600 text-[11px] mt-0.5">{evt.reason}</p>
                  </div>
                </div>

                <div className="flex items-center space-x-2 flex-shrink-0">
                  <span className="text-[11px] font-bold text-slate-600">
                    Trust: {Math.round(evt.trust_score || 0)}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded border text-[10px] font-bold uppercase tracking-wider flex items-center space-x-1 ${getActionBadge(
                      evt.action
                    )}`}
                  >
                    <ActionIcon className="w-3 h-3" />
                    <span>{evt.action}</span>
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
