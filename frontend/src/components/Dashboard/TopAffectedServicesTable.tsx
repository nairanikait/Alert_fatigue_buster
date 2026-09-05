import React from "react";
import { Server, Database } from "lucide-react";
import { MetricsData } from "../../types";

interface TopAffectedServicesTableProps {
  metrics: MetricsData;
}

export const TopAffectedServicesTable: React.FC<TopAffectedServicesTableProps> = ({ metrics }) => {
  const services = metrics.top_affected_services.length > 0 ? (
    metrics.top_affected_services.map((item, idx) => ({
      name: item.service.replace("-", " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      rawId: item.service,
      alerts: item.count,
      incidents: Math.max(1, Math.floor(item.count / 20)),
      impact: item.criticality >= 85 ? "High" : item.criticality >= 70 ? "Medium" : "Low",
    }))
  ) : [
    { name: "User Service", rawId: "user-service", alerts: 24, incidents: 3, impact: "High" },
    { name: "Payment Service", rawId: "payment-service", alerts: 18, incidents: 2, impact: "High" },
    { name: "Order Service", rawId: "order-service", alerts: 15, incidents: 2, impact: "Medium" },
    { name: "Notification Service", rawId: "notification-service", alerts: 11, incidents: 1, impact: "Low" },
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
        <h3 className="text-sm font-bold text-slate-900">Top Affected Services</h3>
        <p className="text-xs text-slate-500">Services experiencing the highest blast radius</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-100 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <th className="pb-2 font-medium">Service</th>
              <th className="pb-2 font-medium text-center">Alerts</th>
              <th className="pb-2 font-medium text-center">Incidents</th>
              <th className="pb-2 font-medium text-right">Impact</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {services.slice(0, 4).map((s, idx) => (
              <tr key={idx} className="hover:bg-slate-50/60 transition">
                <td className="py-2.5 font-medium text-slate-800 pr-2 flex items-center space-x-2">
                  <div className="p-1 rounded bg-slate-100 text-slate-500">
                    {s.rawId.includes("database") || s.rawId.includes("redis") ? (
                      <Database className="w-3.5 h-3.5" />
                    ) : (
                      <Server className="w-3.5 h-3.5" />
                    )}
                  </div>
                  <span className="truncate">{s.name}</span>
                </td>
                <td className="py-2.5 font-mono text-center text-slate-600">{s.alerts}</td>
                <td className="py-2.5 font-mono text-center text-slate-600">{s.incidents}</td>
                <td className="py-2.5 text-right">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${getImpactBadge(s.impact)}`}>
                    {s.impact}
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
