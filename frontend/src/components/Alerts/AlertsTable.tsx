import React, { useState, useMemo } from "react";
import { AlertItem } from "../../types";
import { Search, Filter, Eye, RefreshCw, AlertTriangle, Radio, Sparkles } from "lucide-react";
import { formatTime } from "../../utils/formatDate";
import { AutoSolvePipelineModal } from "./AutoSolvePipelineModal";

interface AlertsTableProps {
  alerts: AlertItem[];
  onSelectAlert: (alert: AlertItem) => void;
  onRefresh: () => void;
}

export const AlertsTable: React.FC<AlertsTableProps> = ({ alerts, onSelectAlert, onRefresh }) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [serviceFilter, setServiceFilter] = useState("ALL");
  const [sourceFilter, setSourceFilter] = useState("ALL");
  const [flakyOnly, setFlakyOnly] = useState(false);
  const [isAutoSolveModalOpen, setIsAutoSolveModalOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Standard telemetry refresh
  const handleRefresh = async () => {
    try {
      setIsRefreshing(true);
      await onRefresh();
    } finally {
      setIsRefreshing(false);
    }
  };

  // Count unresolved suppressed alerts
  const suppressedCount = useMemo(() => {
    return alerts.filter(
      (a) =>
        a.status !== "RESOLVED" &&
        (a.notification_status === "SUPPRESSED" ||
          a.status === "SUPPRESSED" ||
          Boolean(a.suppression_category) ||
          a.status === "BATCHED")
    ).length;
  }, [alerts]);

  // Available unique services and sources for filters
  const availableServices = useMemo(() => {
    return Array.from(new Set(alerts.map((a) => a.service))).filter(Boolean);
  }, [alerts]);

  const availableSources = useMemo(() => {
    return Array.from(new Set(alerts.map((a) => a.source))).filter(Boolean);
  }, [alerts]);

  const filteredAlerts = useMemo(() => {
    return alerts.filter((a) => {
      if (severityFilter !== "ALL" && a.severity.toUpperCase() !== severityFilter) return false;
      if (statusFilter !== "ALL" && a.status.toUpperCase() !== statusFilter) return false;
      if (serviceFilter !== "ALL" && a.service !== serviceFilter) return false;
      if (sourceFilter !== "ALL" && a.source.toLowerCase() !== sourceFilter.toLowerCase()) return false;
      if (flakyOnly && !a.is_flaky) return false;

      if (searchTerm) {
        const query = searchTerm.toLowerCase();
        const matchName = a.alert_name.toLowerCase().includes(query);
        const matchService = a.service.toLowerCase().includes(query);
        const matchHost = a.host?.toLowerCase().includes(query);
        const matchMsg = a.message.toLowerCase().includes(query);
        if (!matchName && !matchService && !matchHost && !matchMsg) return false;
      }
      return true;
    });
  }, [alerts, searchTerm, severityFilter, statusFilter, serviceFilter, sourceFilter, flakyOnly]);

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case "CRITICAL":
        return "bg-red-50 text-red-700 border-red-200 font-bold";
      case "HIGH":
        return "bg-orange-50 text-orange-700 border-orange-200 font-semibold";
      case "MEDIUM":
        return "bg-amber-50 text-amber-700 border-amber-200 font-medium";
      default:
        return "bg-emerald-50 text-emerald-700 border-emerald-200 font-medium";
    }
  };

  const getStatusBadge = (status: string) => {
    switch ((status || "").toUpperCase()) {
      case "FIRING":
      case "ONGOING":
      case "OPEN":
        return "bg-red-50 text-red-700 border-red-200";
      case "ACKNOWLEDGED":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "RESOLVED":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "BATCHED":
        return "bg-indigo-50 text-indigo-700 border-indigo-200";
      default:
        return "bg-slate-100 text-slate-700 border-slate-200";
    }
  };

  const handleAutoSolveClick = () => {
    setIsAutoSolveModalOpen(true);
  };

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3.5">
        <div>
          <h2 className="text-base font-bold text-slate-900 tracking-tight">Alerts</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time telemetry stream, deduplication pipeline, and automated query resolution
          </p>
        </div>

        <div className="flex items-center space-x-2 self-start sm:self-auto">
          {/* Button 1: AutoSolve Suppressed */}
          <button
            id="btn-autosolve-suppressed"
            onClick={handleAutoSolveClick}
            disabled={isRefreshing}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white text-xs font-semibold shadow-xs transition active:scale-95 group disabled:opacity-60 cursor-pointer"
            title="Automatically solve and reconcile all suppressed alert queries"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-200 group-hover:rotate-12 transition-transform" />
            <span>AutoSolve Suppressed</span>
            {suppressedCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-white/20 text-white font-mono font-bold">
                {suppressedCount}
              </span>
            )}
          </button>

          {/* Button 2: Refresh Telemetry */}
          <button
            id="btn-refresh-telemetry"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 text-xs font-medium transition shadow-xs disabled:opacity-60 cursor-pointer"
            title="Refresh current telemetry view"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-slate-400 ${isRefreshing ? "animate-spin text-indigo-600" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2.5">
        {/* Search */}
        <div className="lg:col-span-2 relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search alerts, services, hosts..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-md text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 focus:bg-white"
          />
        </div>

        {/* Severity */}
        <div>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="w-full px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-md text-slate-700 focus:outline-none focus:border-indigo-500 focus:bg-white"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </div>

        {/* Status */}
        <div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-md text-slate-700 focus:outline-none focus:border-indigo-500 focus:bg-white"
          >
            <option value="ALL">All Statuses</option>
            <option value="FIRING">Firing</option>
            <option value="ONGOING">Ongoing</option>
            <option value="RESOLVED">Resolved</option>
            <option value="BATCHED">Batched</option>
          </select>
        </div>

        {/* Service */}
        <div>
          <select
            value={serviceFilter}
            onChange={(e) => setServiceFilter(e.target.value)}
            className="w-full px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-md text-slate-700 focus:outline-none focus:border-indigo-500 focus:bg-white"
          >
            <option value="ALL">All Services</option>
            {availableServices.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* Flaky Filter */}
        <div>
          <button
            onClick={() => setFlakyOnly(!flakyOnly)}
            className={`w-full py-1.5 px-3 text-xs rounded-md border font-medium transition flex items-center justify-center space-x-1.5 ${flakyOnly
                ? "bg-amber-50 text-amber-800 border-amber-300 font-semibold"
                : "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100"
              }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
            <span>Flaky Only</span>
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-slate-200 rounded-md">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-200">
            <tr>
              <th className="px-3.5 py-2.5 font-medium">Alert</th>
              <th className="px-3 py-2.5 font-medium">Service</th>
              <th className="px-3 py-2.5 font-medium">Severity</th>
              <th className="px-3 py-2.5 font-medium">Status</th>
              <th className="px-3 py-2.5 font-medium text-center">Occurrences</th>
              <th className="px-3 py-2.5 font-medium">Source</th>
              <th className="px-3 py-2.5 font-medium">First Seen</th>
              <th className="px-3 py-2.5 font-medium">Last Seen</th>
              <th className="px-3 py-2.5 font-medium">Notification</th>
              <th className="px-3 py-2.5 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredAlerts.length === 0 ? (
              <tr>
                <td colSpan={10} className="py-12 text-center text-slate-500 text-xs font-mono">
                  No alerts found matching the current criteria.
                </td>
              </tr>
            ) : (
              filteredAlerts.map((alert) => (
                <tr
                  key={alert.id}
                  onClick={() => onSelectAlert(alert)}
                  className="hover:bg-slate-50/70 transition cursor-pointer"
                >
                  <td className="px-3.5 py-2.5">
                    <div className="flex items-center space-x-1.5">
                      <span className="font-semibold text-slate-900">{alert.title || alert.alert_name}</span>
                      {alert.root_cause && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-purple-50 text-purple-700 border border-purple-200">
                          Root: {alert.root_cause}
                        </span>
                      )}
                      {alert.is_flaky && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-50 text-amber-700 border border-amber-200">
                          Flaky
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-500 truncate max-w-xs">{alert.description || alert.message}</div>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-slate-700 font-medium">{alert.service}</td>
                  <td className="px-3 py-2.5">
                    <span className={`px-2 py-0.5 rounded text-[10px] uppercase border ${getSeverityBadge(alert.severity)}`}>
                      {alert.severity}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase border ${getStatusBadge(alert.status)}`}>
                      {alert.status}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-center font-mono font-bold text-slate-800">
                    {alert.occurrence_count > 1 ? (
                      <span className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200">
                        {alert.occurrence_count}x
                      </span>
                    ) : (
                      "1x"
                    )}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-[11px] text-slate-500 uppercase">{alert.source}</td>
                  <td className="px-3 py-2.5 text-[11px] text-slate-500 font-mono">
                    {formatTime(alert.first_seen)}
                  </td>
                  <td className="px-3 py-2.5 text-[11px] text-slate-500 font-mono">
                    {formatTime(alert.last_seen)}
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className={`text-[10px] uppercase font-semibold px-2 py-0.5 rounded border ${
                        alert.notification_status === "SENT"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : alert.notification_status === "SUPPRESSED"
                            ? "bg-amber-50 text-amber-700 border-amber-200"
                            : alert.notification_status === "BATCHED"
                              ? "bg-indigo-50 text-indigo-700 border-indigo-200"
                              : "bg-slate-100 text-slate-600 border-slate-200"
                      }`}
                    >
                      {alert.notification_status}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectAlert(alert);
                      }}
                      className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
                      title="Inspect processing logic"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500 font-medium pt-1">
        <span>Showing {filteredAlerts.length} of {alerts.length} total events</span>
        <span>Tip: Click any row to view explainability details</span>
      </div>

      {/* AutoSolve Pipeline Visualizer Modal */}
      <AutoSolvePipelineModal
        isOpen={isAutoSolveModalOpen}
        onClose={() => setIsAutoSolveModalOpen(false)}
        onCompleted={onRefresh}
      />
    </div>
  );
};
