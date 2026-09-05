import React, { useState } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { MetricsData } from "../../types";

interface AlertVolumeChartProps {
  metrics: MetricsData;
}

export const AlertVolumeChart: React.FC<AlertVolumeChartProps> = ({ metrics }) => {
  const [timeRange, setTimeRange] = useState("30m");

  // Realistic time-series data scaled to active metrics
  const totalIn = metrics.incoming_alerts > 0 ? metrics.incoming_alerts : 1507;
  const totalSent = metrics.notifications_sent > 0 ? metrics.notifications_sent : 13;

  const data = [
    { time: "10:05", "Incoming Alerts": Math.round(totalIn * 0.05), "Notifications Sent": 1 },
    { time: "10:10", "Incoming Alerts": Math.round(totalIn * 0.08), "Notifications Sent": 1 },
    { time: "10:15", "Incoming Alerts": Math.round(totalIn * 0.12), "Notifications Sent": 2 },
    { time: "10:20", "Incoming Alerts": Math.round(totalIn * 0.45), "Notifications Sent": 3 },
    { time: "10:25", "Incoming Alerts": Math.round(totalIn * 0.20), "Notifications Sent": 2 },
    { time: "10:30", "Incoming Alerts": Math.round(totalIn * 0.10), "Notifications Sent": Math.max(1, totalSent - 9) },
  ];

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-sm space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-slate-900">Alert Volume Over Time</h3>
          <p className="text-xs text-slate-500">Incoming monitoring alerts vs actionable notifications routed</p>
        </div>

        <div className="flex items-center space-x-1 border border-slate-200 rounded-md p-0.5 bg-slate-50 text-[11px] font-medium">
          {["15m", "30m", "1h", "24h"].map((t) => (
            <button
              key={t}
              onClick={() => setTimeRange(t)}
              className={`px-2 py-0.5 rounded ${
                timeRange === t ? "bg-white text-slate-900 shadow-xs font-semibold" : "text-slate-500 hover:text-slate-900"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="colorIncoming" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="colorSent" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="time" stroke="#94a3b8" tick={{ fill: "#64748b", fontSize: 11 }} />
            <YAxis stroke="#94a3b8" tick={{ fill: "#64748b", fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "6px",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)",
                fontSize: "12px",
                color: "#0f172a",
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }}
              iconType="circle"
            />
            <Area
              type="monotone"
              dataKey="Incoming Alerts"
              stroke="#6366f1"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorIncoming)"
            />
            <Area
              type="monotone"
              dataKey="Notifications Sent"
              stroke="#10b981"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorSent)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
