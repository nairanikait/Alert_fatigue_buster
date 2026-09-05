import React from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { MetricsData } from "../../types";

interface TopAffectedServicesProps {
  metrics: MetricsData;
}

export const TopAffectedServices: React.FC<TopAffectedServicesProps> = ({ metrics }) => {
  const data = metrics.top_affected_services.map((item) => ({
    name: item.service,
    count: item.count,
    criticality: item.criticality,
  }));

  const hasData = data.length > 0;

  return (
    <div className="glass-card p-5 space-y-4">
      <div>
        <h3 className="text-base font-bold text-white">Top Impacted Services</h3>
        <p className="text-xs text-slate-400">Total alert volume aggregated per service</p>
      </div>

      <div className="h-64 w-full">
        {hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 10, right: 20, left: 40, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis type="number" stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <YAxis dataKey="name" type="category" stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  borderRadius: "8px",
                  color: "#f8fafc",
                  fontSize: "12px",
                }}
              />
              <Bar dataKey="count" fill="#818cf8" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-xs text-slate-500 font-mono">
            No service failures recorded
          </div>
        )}
      </div>
    </div>
  );
};
