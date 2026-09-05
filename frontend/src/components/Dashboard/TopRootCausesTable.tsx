import React from "react";
import { IncidentItem } from "../../types";

interface TopRootCausesTableProps {
  incidents: IncidentItem[];
}

export const TopRootCausesTable: React.FC<TopRootCausesTableProps> = ({ incidents }) => {
  // Aggregate incidents by root cause or use representative data
  const rootCauses = incidents.length > 0 ? (
    Object.values(
      incidents.reduce((acc: any, inc) => {
        const key = inc.root_cause_service || "Database Connection Failure";
        if (!acc[key]) {
          acc[key] = {
            name: `${inc.root_cause_service.replace("-", " ").toUpperCase()} Outage`,
            incidents: 0,
            alerts: 0,
            impact: inc.severity === "CRITICAL" ? "High" : "Medium",
          };
        }
        acc[key].incidents += 1;
        acc[key].alerts += inc.alert_count;
        return acc;
      }, {})
    )
  ) : [
    { name: "Database Connection Failure", incidents: 3, alerts: 24, impact: "High" },
    { name: "External API Timeout", incidents: 2, alerts: 15, impact: "Medium" },
    { name: "High CPU Utilization", incidents: 2, alerts: 11, impact: "Medium" },
    { name: "Memory Leak", incidents: 1, alerts: 5, impact: "Low" },
  ];

  const getImpactBadge = (impact: string) => {
    switch (impact) {
      case "High":
        return "bg-red-50 text-red-700 border-red-200";
      case "Medium":
        return "bg-amber-50 text-amber-700 border-amber-200";
      default:
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-sm space-y-3">
      <div>
        <h3 className="text-sm font-bold text-slate-900">Top Root Causes</h3>
        <p className="text-xs text-slate-500">Most frequent underlying failure drivers</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <th className="pb-2 font-medium">Root Cause</th>
              <th className="pb-2 font-medium text-center">Incidents</th>
              <th className="pb-2 font-medium text-center">Alerts</th>
              <th className="pb-2 font-medium text-right">Impact</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(rootCauses as any[]).slice(0, 4).map((rc, idx) => (
              <tr key={idx} className="hover:bg-slate-50/60 transition">
                <td className="py-2.5 font-medium text-slate-800 pr-2">{rc.name}</td>
                <td className="py-2.5 font-mono text-center text-slate-600">{rc.incidents}</td>
                <td className="py-2.5 font-mono text-center text-slate-600">{rc.alerts}</td>
                <td className="py-2.5 text-right">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${getImpactBadge(rc.impact)}`}>
                    {rc.impact}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
