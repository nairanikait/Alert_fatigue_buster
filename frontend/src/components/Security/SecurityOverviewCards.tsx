import React from "react";
import { ShieldCheck, ShieldAlert, ShieldX, Activity, AlertTriangle, RefreshCw, Lock, Zap } from "lucide-react";
import { SecurityOverviewData } from "../../services/api";

interface SecurityOverviewCardsProps {
  data: SecurityOverviewData | null;
  loading: boolean;
  onRefresh: () => void;
}

export const SecurityOverviewCards: React.FC<SecurityOverviewCardsProps> = ({ data, loading, onRefresh }) => {
  if (!data) return null;

  const status = data.system_status;
  const metrics = data.metrics;

  const getStatusBadge = () => {
    if (status === "CRITICAL") {
      return {
        bg: "bg-red-50 border-red-200 text-red-700",
        dot: "bg-red-500",
        icon: ShieldX,
        label: "CRITICAL THREAT",
      };
    }
    if (status === "WARNING") {
      return {
        bg: "bg-amber-50 border-amber-200 text-amber-700",
        dot: "bg-amber-500",
        icon: ShieldAlert,
        label: "ELEVATED RISK",
      };
    }
    return {
      bg: "bg-emerald-50 border-emerald-200 text-emerald-700",
      dot: "bg-emerald-500",
      icon: ShieldCheck,
      label: "SYSTEM PROTECTED",
    };
  };

  const badge = getStatusBadge();
  const StatusIcon = badge.icon;

  return (
    <div className="space-y-4">
      {/* Top Banner: Status & Health */}
      <div className={`p-4 rounded-xl border flex items-center justify-between shadow-xs transition-all ${badge.bg}`}>
        <div className="flex items-center space-x-3.5">
          <div className="p-2.5 rounded-lg bg-white/80 shadow-xs border border-current/10">
            <StatusIcon className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className={`w-2.5 h-2.5 rounded-full animate-pulse ${badge.dot}`} />
              <span className="text-xs font-bold uppercase tracking-wider">{badge.label}</span>
              <span className="text-slate-300">•</span>
              <span className="text-xs font-medium text-slate-600">Alert Integrity Shield Active</span>
            </div>
            <p className="text-sm font-semibold mt-0.5 text-slate-800">{data.status_message}</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div className="text-right hidden sm:block">
            <div className="text-[11px] uppercase font-semibold text-slate-500 tracking-wider">Avg Trust Score</div>
            <div className="text-xl font-bold font-mono text-indigo-600">
              {metrics.average_trust_score.toFixed(1)}
              <span className="text-xs text-slate-400 font-normal"> / 100</span>
            </div>
          </div>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors shadow-xs"
            title="Refresh Security Metrics"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-indigo-600" : ""}`} />
          </button>
        </div>
      </div>

      {/* Critical Alert Quarantine Emergency Warning */}
      {metrics.pending_critical_quarantines > 0 && (
        <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-300 flex items-center justify-between text-rose-800 text-xs shadow-xs animate-pulse">
          <div className="flex items-center space-x-2.5 font-medium">
            <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span>
              <strong>CRITICAL ALERT SAFETY:</strong> {metrics.pending_critical_quarantines} critical severity alerts have suspicious attributes. Preserved in quarantine — SRE review required.
            </span>
          </div>
          <span className="px-2.5 py-1 rounded bg-rose-600 text-white font-bold text-[11px]">Action Required</span>
        </div>
      )}

      {/* 8 Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white border border-slate-200 rounded-lg p-3.5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Blocked Threats</span>
            <ShieldX className="w-4 h-4 text-red-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-red-600">{metrics.blocked_requests}</div>
          <div className="mt-1 text-[11px] text-slate-400">Invalid sigs, replays & abuses</div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3.5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Quarantined Alerts</span>
            <ShieldAlert className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-amber-600">{metrics.quarantined_alerts}</div>
          <div className="mt-1 text-[11px] text-slate-400">
            {metrics.pending_critical_quarantines > 0 ? (
              <span className="text-red-600 font-semibold">{metrics.pending_critical_quarantines} Critical</span>
            ) : (
              "Preserved for review"
            )}
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3.5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Invalid Signatures</span>
            <Lock className="w-4 h-4 text-rose-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-800">{metrics.invalid_signatures}</div>
          <div className="mt-1 text-[11px] text-slate-400">HMAC-SHA256 mismatches</div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3.5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Replay Attacks</span>
            <RefreshCw className="w-4 h-4 text-orange-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-800">{metrics.replay_attempts}</div>
          <div className="mt-1 text-[11px] text-slate-400">Duplicated nonces/stale times</div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3.5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Rate Throttles</span>
            <Zap className="w-4 h-4 text-purple-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-800">{metrics.rate_limit_violations}</div>
          <div className="mt-1 text-[11px] text-slate-400">HTTP 429 flood rejections</div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3.5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Alert Injections</span>
            <Activity className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-800">{metrics.alert_injection_attempts}</div>
          <div className="mt-1 text-[11px] text-slate-400">&gt;5x baseline volume spikes</div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3.5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Accepted Alerts</span>
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-emerald-600">{metrics.accepted_requests}</div>
          <div className="mt-1 text-[11px] text-slate-400">Verified &amp; pipeline-routed</div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-3.5 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Total Screened</span>
            <Activity className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-indigo-600">{metrics.total_screened}</div>
          <div className="mt-1 text-[11px] text-slate-400">Shield inspection passes</div>
        </div>
      </div>
    </div>
  );
};
