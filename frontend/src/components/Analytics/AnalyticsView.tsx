import React from "react";
import {
  BarChart3,
  TrendingDown,
  TrendingUp,
  Activity,
  ShieldCheck,
  Zap,
  Clock,
  Layers,
  DollarSign,
  Sparkles,
  CheckCircle2,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { MetricsData, AlertItem, IncidentItem } from "../../types";

interface AnalyticsViewProps {
  metrics: MetricsData;
  alerts: AlertItem[];
  incidents: IncidentItem[];
}

export const AnalyticsView: React.FC<AnalyticsViewProps> = ({ metrics, alerts, incidents }) => {
  // Volume Trend Data
  const volumeTrendData = [
    { time: "10:00", rawAlerts: 42, suppressed: 41, notifications: 1 },
    { time: "10:05", rawAlerts: 180, suppressed: 178, notifications: 2 },
    { time: "10:10", rawAlerts: 520, suppressed: 517, notifications: 3 },
    { time: "10:15", rawAlerts: 410, suppressed: 407, notifications: 3 },
    { time: "10:20", rawAlerts: 230, suppressed: 228, notifications: 2 },
    { time: "10:25", rawAlerts: 90, suppressed: 88, notifications: 2 },
    {
      time: "10:30",
      rawAlerts: metrics.incoming_alerts > 0 ? metrics.incoming_alerts : 1507,
      suppressed: metrics.suppressed_alerts > 0 ? metrics.suppressed_alerts : 1494,
      notifications: metrics.notifications_sent > 0 ? metrics.notifications_sent : 13,
    },
  ];

  // Top Noisy Services Bar Chart Data
  const noisyServicesData = [
    { service: "database", alerts: 620, incidents: 3 },
    { service: "payment-service", alerts: 340, incidents: 2 },
    { service: "order-service", alerts: 290, incidents: 2 },
    { service: "authentication", alerts: 160, incidents: 1 },
    { service: "api-gateway", alerts: 97, incidents: 1 },
  ];

  // Severity Distribution Data
  const severityData = [
    { name: "Critical", value: metrics.severity_breakdown?.critical || 8, color: "#ef4444" },
    { name: "High", value: metrics.severity_breakdown?.high || 18, color: "#f97316" },
    { name: "Medium", value: metrics.severity_breakdown?.medium || 20, color: "#f59e0b" },
    { name: "Low", value: metrics.severity_breakdown?.low || 9, color: "#10b981" },
  ];

  const totalRaw = metrics.incoming_alerts > 0 ? metrics.incoming_alerts : 1507;
  const totalSent = metrics.notifications_sent > 0 ? metrics.notifications_sent : 13;
  const totalSuppressed = metrics.suppressed_alerts > 0 ? metrics.suppressed_alerts : 1494;
  const reductionRate = metrics.reduction_percentage > 0 ? metrics.reduction_percentage : 99.1;

  const dedupBatchingSaved = metrics.cost_savings?.dedup_batching_saved ?? Math.round(totalSuppressed * 3.8);
  const routingSaved = metrics.cost_savings?.routing_triage_saved ?? 168.0;
  const totalDollarsSaved = metrics.cost_savings?.total_dollars_saved ?? Math.round(totalSuppressed * 4.0);
  const totalHoursSaved = metrics.time_saved?.total_hours_saved ?? Number(((totalSuppressed * 3.0) / 60.0).toFixed(1));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-indigo-600" />
            <span>Alert & Fatigue Analytics</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Deep-dive operational metrics, defensible ROI calculations, and MTTR acceleration.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 font-medium shadow-xs">
            Window: Last 30 Minutes
          </span>
        </div>
      </div>

      {/* 4 Metric Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
            Overall Reduction Rate
          </span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-bold font-mono text-emerald-600">
              {reductionRate.toFixed(1)}%
            </span>
            <span className="text-[10px] text-emerald-600 font-medium">+1.4% vs baseline</span>
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">
            {totalSuppressed.toLocaleString()} alerts suppressed
          </span>
        </div>

        <div className="bg-white border border-indigo-200 bg-indigo-50/20 rounded-xl p-4 shadow-xs">
          <span className="text-[11px] font-semibold text-indigo-700 uppercase tracking-wider block">
            Defensible ROI Generated
          </span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-bold font-mono text-indigo-700">
              ${Math.round(totalDollarsSaved).toLocaleString()}
            </span>
            <span className="text-[10px] text-indigo-600 font-medium">$4.00 / interruption</span>
          </div>
          <span className="text-[11px] text-slate-500 mt-1 block">
            ${Math.round(dedupBatchingSaved).toLocaleString()} dedup + ${Math.round(routingSaved).toLocaleString()} routing
          </span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
            Focus Time Returned
          </span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-bold font-mono text-amber-700">
              {totalHoursSaved} hrs
            </span>
            <span className="text-[10px] text-amber-600 font-medium">3 min refocus penalty</span>
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">
            Engineers stayed uninterrupted
          </span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
            Mean MTTR Acceleration
          </span>
          <div className="flex items-baseline space-x-2 mt-1">
            <span className="text-2xl font-bold font-mono text-slate-900">4.2x</span>
            <span className="text-[10px] text-emerald-600 font-medium">faster triage</span>
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">
            Engineers receive 1 root cause vs 500 pings
          </span>
        </div>
      </div>

      {/* Main Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Suppression Trend Chart (2 cols) */}
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Raw Alerts vs Notifications Dispatched</h3>
              <p className="text-[11px] text-slate-500">
                Visualizing noisy monitoring floods vs actionable incident digests
              </p>
            </div>
            <div className="flex items-center space-x-3 text-xs">
              <div className="flex items-center space-x-1.5 text-slate-600">
                <span className="w-2.5 h-2.5 rounded-xs bg-indigo-500" />
                <span>Raw Ingested</span>
              </div>
              <div className="flex items-center space-x-1.5 text-slate-600">
                <span className="w-2.5 h-2.5 rounded-xs bg-emerald-500" />
                <span>Notifications Sent</span>
              </div>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={volumeTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorRaw" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorNotif" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#ffffff",
                    borderColor: "#e2e8f0",
                    borderRadius: "8px",
                    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                    fontSize: "12px",
                  }}
                />
                <Area type="monotone" dataKey="rawAlerts" stroke="#6366f1" strokeWidth={2} fillOpacity={1} fill="url(#colorRaw)" />
                <Area type="monotone" dataKey="notifications" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorNotif)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Severity Distribution Donut */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900">Alerts by Severity</h3>
            <p className="text-[11px] text-slate-500">Distribution across active monitoring telemetry</p>
          </div>

          <div className="h-48 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={severityData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {severityData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-1.5 pt-2 border-t border-slate-100">
            {severityData.map((item) => (
              <div key={item.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-slate-600">{item.name}</span>
                </div>
                <span className="font-mono font-medium text-slate-900">{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top Noisy Services Bar Chart */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
        <div className="border-b border-slate-100 pb-3">
          <h3 className="text-sm font-bold text-slate-900">Top Noisy Services (Raw Alert Volume)</h3>
          <p className="text-[11px] text-slate-500">
            Services producing the highest volume of raw Prometheus & Datadog signals before Alert Buster correlation
          </p>
        </div>

        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={noisyServicesData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="service" stroke="#94a3b8" fontSize={11} tickLine={false} />
              <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#ffffff",
                  borderColor: "#e2e8f0",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
              <Bar dataKey="alerts" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
