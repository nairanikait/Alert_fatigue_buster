import React, { useState } from "react";
import { IncidentItem } from "../../types";
import {
  ShieldAlert,
  Target,
  Clock,
  Bell,
  Layers,
  CheckCircle2,
  AlertTriangle,
  ArrowUpRight,
  Search,
  Filter,
  DollarSign,
  TrendingDown,
  Info,
  X,
  Zap,
  ShieldCheck,
} from "lucide-react";
import { AIIncidentCopilotPanel } from "./AIIncidentCopilotPanel";

interface IncidentListProps {
  incidents: IncidentItem[];
  onSelectIncident: (inc: IncidentItem) => void;
}

export const calculateIncidentCost = (
  inc: IncidentItem
): {
  totalCost: number;
  burnRatePerMin: number;
  durationSeconds: number;
  baseTriage: number;
  ratePerSec: number;
  blastMultiplier: number;
} => {
  let duration = inc.duration_seconds || 0;
  if (!duration || duration <= 0) {
    if (inc.created_at) {
      const start = new Date(inc.created_at).getTime();
      const end = inc.resolved_at ? new Date(inc.resolved_at).getTime() : Date.now();
      duration = Math.max(10, Math.round((end - start) / 1000));
    } else {
      duration = 35;
    }
  }

  const sev = (inc.severity || "HIGH").toUpperCase();
  let ratePerSec = 32;
  let baseTriage = 300;
  let ratePerMin = 1920;

  if (sev === "CRITICAL") {
    ratePerSec = 65;
    baseTriage = 500;
    ratePerMin = 3900;
  } else if (sev === "HIGH") {
    ratePerSec = 32;
    baseTriage = 300;
    ratePerMin = 1920;
  } else if (sev === "MEDIUM") {
    ratePerSec = 14;
    baseTriage = 150;
    ratePerMin = 840;
  } else {
    ratePerSec = 5;
    baseTriage = 50;
    ratePerMin = 300;
  }

  const blastMultiplier = 1.0 + Math.max(0, (inc.affected_services?.length || 1) - 1) * 0.18;
  const calculatedCost = baseTriage + duration * ratePerSec * blastMultiplier;
  const burnRate = ratePerMin * blastMultiplier;

  const finalCost = inc.estimated_cost_loss && inc.estimated_cost_loss > 0
    ? inc.estimated_cost_loss
    : calculatedCost;

  const finalBurnRate = inc.cost_burn_rate_per_minute && inc.cost_burn_rate_per_minute > 0
    ? inc.cost_burn_rate_per_minute
    : burnRate;

  return {
    totalCost: Math.round(finalCost),
    burnRatePerMin: Math.round(finalBurnRate),
    durationSeconds: Math.round(duration),
    baseTriage,
    ratePerSec,
    blastMultiplier: Number(blastMultiplier.toFixed(2)),
  };
};

export const IncidentList: React.FC<IncidentListProps> = ({ incidents, onSelectIncident }) => {
  const [filterTab, setFilterTab] = useState<"ALL" | "ACTIVE" | "RESOLVED">("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCostIncident, setSelectedCostIncident] = useState<IncidentItem | null>(null);

  const filteredIncidents = incidents.filter((inc) => {
    if (filterTab === "ACTIVE" && inc.status !== "FIRING") return false;
    if (filterTab === "RESOLVED" && inc.status === "FIRING") return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        inc.title.toLowerCase().includes(q) ||
        inc.id.toLowerCase().includes(q) ||
        inc.root_cause_service.toLowerCase().includes(q) ||
        inc.affected_services?.some((s) => s.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const activeCount = incidents.filter((i) => i.status === "FIRING").length;
  const resolvedCount = incidents.filter((i) => i.status !== "FIRING").length;

  // Aggregate Financial Statistics
  const totalOutageCost = incidents.reduce((acc, inc) => acc + calculateIncidentCost(inc).totalCost, 0);
  const activeBurnRate = incidents
    .filter((i) => i.status === "FIRING")
    .reduce((acc, inc) => acc + calculateIncidentCost(inc).burnRatePerMin, 0);
  const totalSuppressedSavings = incidents.reduce((acc, inc) => acc + (inc.suppressed_count || 0) * 50, 0);

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-indigo-600" />
            <span>Incidents & Operational Impact</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time correlated incidents tracking root causes, affected services, and estimated operational downtime cost loss.
          </p>
        </div>

        {/* Tab Filter & Search */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search incidents or services..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-slate-800 placeholder-slate-400 w-64 shadow-xs"
            />
          </div>

          <div className="flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs font-medium">
            <button
              onClick={() => setFilterTab("ALL")}
              className={`px-3 py-1 rounded-md transition ${
                filterTab === "ALL"
                  ? "bg-white text-slate-900 shadow-xs font-semibold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              All ({incidents.length})
            </button>
            <button
              onClick={() => setFilterTab("ACTIVE")}
              className={`px-3 py-1 rounded-md transition flex items-center gap-1.5 ${
                filterTab === "ACTIVE"
                  ? "bg-white text-rose-700 shadow-xs font-semibold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
              Active ({activeCount})
            </button>
            <button
              onClick={() => setFilterTab("RESOLVED")}
              className={`px-3 py-1 rounded-md transition ${
                filterTab === "RESOLVED"
                  ? "bg-white text-emerald-700 shadow-xs font-semibold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Resolved ({resolvedCount})
            </button>
          </div>
        </div>
      </div>

      {/* EXECUTIVE OPERATIONAL COST KPI SUMMARY CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Total Cost Loss */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <DollarSign className="w-4 h-4 text-rose-600" />
              <span>Total Estimated Outage Loss</span>
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
              Down Time Cost
            </span>
          </div>
          <div className="flex items-baseline space-x-2 pt-1">
            <span className="text-2xl font-extrabold font-mono text-slate-900">
              ${totalOutageCost.toLocaleString()}
            </span>
            <span className="text-xs text-slate-400 font-medium">USD</span>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Financial impact across {incidents.length} incidents (SLA breaches, lost throughput & triage overhead).
          </p>
        </div>

        {/* Active Outage Burn Rate */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <TrendingDown className="w-4 h-4 text-amber-600" />
              <span>Active Outage Burn Rate</span>
            </span>
            {activeCount > 0 ? (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-700 border border-rose-200 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-ping" />
                Live Outage
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Stable
              </span>
            )}
          </div>
          <div className="flex items-baseline space-x-2 pt-1">
            <span className="text-2xl font-extrabold font-mono text-slate-900">
              ${activeBurnRate.toLocaleString()}
            </span>
            <span className="text-xs text-slate-400 font-medium">/ minute</span>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            {activeCount > 0
              ? `Real-time loss compounding across ${activeCount} currently ongoing incident(s).`
              : "Zero active outages currently burning operational capital."}
          </p>
        </div>

        {/* Prevented SRE Waste & Savings */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Fatigue Prevention Savings</span>
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
              Noise ROI
            </span>
          </div>
          <div className="flex items-baseline space-x-2 pt-1">
            <span className="text-2xl font-extrabold font-mono text-emerald-600">
              ${totalSuppressedSavings.toLocaleString()}
            </span>
            <span className="text-xs text-slate-400 font-medium">USD saved</span>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Engineering context-switch cost preserved by suppressing redundant noise (~$50 / false page).
          </p>
        </div>
      </div>

      {/* INCIDENTS LIST */}
      {filteredIncidents.length === 0 ? (
        <div className="p-12 text-center bg-white border border-slate-200 rounded-xl space-y-3 shadow-xs">
          <div className="w-10 h-10 rounded-full bg-slate-50 border border-slate-200 flex items-center justify-center mx-auto text-slate-400">
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
          </div>
          <h3 className="text-sm font-semibold text-slate-900">No active incidents found</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {searchQuery
              ? "No incidents matched your query. Try clearing the search."
              : "All monitoring signals are stable. Run a simulation from the Alert Simulator to trigger realistic incidents."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredIncidents.map((inc) => {
            const isFiring = inc.status === "FIRING";
            const costInfo = calculateIncidentCost(inc);

            return (
              <div
                key={inc.id}
                onClick={() => onSelectIncident(inc)}
                className="bg-white border border-slate-200 rounded-xl p-5 hover:border-indigo-300 hover:shadow-sm transition-all duration-150 cursor-pointer space-y-4 shadow-xs"
              >
                {/* Header Row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center space-x-3">
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border uppercase ${
                        isFiring
                          ? "bg-rose-50 text-rose-700 border-rose-200"
                          : "bg-emerald-50 text-emerald-700 border-emerald-200"
                      }`}
                    >
                      {inc.status}
                    </span>
                    <span className="text-xs font-mono font-bold text-slate-500">{inc.id}</span>
                    <h3 className="text-sm font-bold text-slate-900 hover:text-indigo-600 transition flex items-center gap-1">
                      {inc.title}
                      <ArrowUpRight className="w-3.5 h-3.5 text-slate-400" />
                    </h3>
                  </div>

                  <div className="flex items-center space-x-3 text-xs font-mono">
                    {/* Operational Cost Badge */}
                    <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 font-bold">
                      <DollarSign className="w-3.5 h-3.5 text-rose-600" />
                      <span>Est. Loss: ${costInfo.totalCost.toLocaleString()}</span>
                    </div>
                    <span className="text-slate-300">•</span>
                    <span className="text-indigo-600 font-semibold">{inc.suppressed_count} Suppressed</span>
                    <span className="text-slate-300">•</span>
                    <span className="text-slate-700 font-medium">{inc.notifications_count} Paged</span>
                  </div>
                </div>

                {/* OPERATIONAL COST OUTAGE LOSS CARD */}
                <div className="p-3.5 rounded-lg bg-gradient-to-r from-rose-50/70 via-orange-50/40 to-slate-50 border border-rose-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  <div className="flex items-start space-x-3">
                    <div className="p-2 rounded-lg bg-rose-100/80 text-rose-700 font-bold flex-shrink-0 mt-0.5">
                      <DollarSign className="w-4 h-4" />
                    </div>
                    <div className="space-y-0.5">
                      <div className="flex items-center space-x-2">
                        <span className="font-extrabold text-slate-900 text-sm font-mono">
                          ${costInfo.totalCost.toLocaleString()} USD
                        </span>
                        <span className="text-[10px] uppercase font-bold text-rose-800 bg-rose-100 px-2 py-0.5 rounded border border-rose-200">
                          Estimated Outage Loss
                        </span>
                        {isFiring && (
                          <span className="text-[10px] text-rose-600 font-semibold animate-pulse">
                            (compounding live)
                          </span>
                        )}
                      </div>
                      <p className="text-slate-600 text-[11px] leading-relaxed">
                        Calculated from {costInfo.durationSeconds}s outage duration at ~${costInfo.burnRatePerMin.toLocaleString()}/min burn rate + $500 engineering triage baseline.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 text-[11px] font-mono flex-shrink-0 self-end sm:self-center">
                    <span className="px-2.5 py-1 rounded bg-white border border-slate-200 text-rose-700 font-bold shadow-2xs">
                      ~${costInfo.burnRatePerMin.toLocaleString()}/min
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedCostIncident(inc);
                      }}
                      className="px-2 py-1 rounded bg-white border border-slate-200 hover:bg-slate-50 text-indigo-600 font-semibold shadow-2xs transition flex items-center gap-1"
                    >
                      <span>Cost Breakdown</span>
                      <ArrowUpRight className="w-3 h-3 text-indigo-500" />
                    </button>
                  </div>
                </div>

                {/* Root Cause & Blast Radius Box */}
                <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5 text-slate-800 font-semibold">
                      <Target className="w-4 h-4 text-indigo-600" />
                      <span>
                        Root Cause: <strong className="text-indigo-600">{inc.root_cause_service}</strong> ({inc.root_cause_alert_name})
                      </span>
                    </div>
                    <p className="text-slate-600 leading-relaxed text-[11px]">{inc.root_cause_reason}</p>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="px-2.5 py-1 rounded bg-indigo-50 border border-indigo-100 text-indigo-700 font-mono font-bold text-xs">
                      {inc.confidence_score}% Confidence
                    </span>
                  </div>
                </div>

                {/* AI SRE Copilot Solution Panel */}
                <div onClick={(e) => e.stopPropagation()} className="pt-1">
                  <AIIncidentCopilotPanel incident={inc} defaultExpanded={false} />
                </div>

                {/* Affected Services & Timestamps */}
                <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500 pt-2 border-t border-slate-100">
                  <div className="flex items-center space-x-2">
                    <Layers className="w-3.5 h-3.5 text-slate-400" />
                    <span className="text-[11px] font-medium text-slate-600">
                      Affected Services ({inc.affected_services?.length || 0}):
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {inc.affected_services?.map((s) => (
                        <span
                          key={s}
                          className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-700 text-[10px] font-medium"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center space-x-4 text-[11px] font-mono text-slate-500">
                    <span>Started: {new Date(inc.created_at).toLocaleTimeString()}</span>
                    {costInfo.durationSeconds > 0 && (
                      <span className="text-slate-700 font-medium">
                        Duration: {costInfo.durationSeconds}s
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* DETAILED COST BREAKDOWN MODAL POPUP */}
      {selectedCostIncident && (() => {
        const cost = calculateIncidentCost(selectedCostIncident);
        const downtimeLoss = cost.durationSeconds * cost.ratePerSec * cost.blastMultiplier;
        const preventedLoss = (selectedCostIncident.suppressed_count || 0) * 50;

        return (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fadeIn"
            onClick={() => setSelectedCostIncident(null)}
          >
            <div
              className="relative w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white border border-slate-200 shadow-2xl p-6 space-y-5"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-start justify-between border-b border-slate-100 pb-4">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-rose-50 text-rose-700 border border-rose-200 flex items-center gap-1">
                      <DollarSign className="w-3 h-3" />
                      <span>Financial Outage Audit</span>
                    </span>
                    <span className="text-xs font-mono text-slate-400">{selectedCostIncident.id}</span>
                  </div>
                  <h2 className="text-lg font-bold text-slate-900 tracking-tight mt-1">
                    Operational Cost & Downtime Impact
                  </h2>
                  <p className="text-xs text-slate-500">
                    {selectedCostIncident.title}
                  </p>
                </div>

                <button
                  onClick={() => setSelectedCostIncident(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Big Metric Box */}
              <div className="p-4 rounded-xl bg-gradient-to-br from-rose-50 to-orange-50/50 border border-rose-200 flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-rose-800 uppercase tracking-wider block">
                    Net Estimated Outage Loss
                  </span>
                  <div className="text-3xl font-black font-mono text-slate-900 pt-0.5">
                    ${cost.totalCost.toLocaleString()} <span className="text-sm font-normal text-slate-500">USD</span>
                  </div>
                  <span className="text-[11px] text-slate-500">
                    Downtime: {cost.durationSeconds}s @ ~${cost.burnRatePerMin.toLocaleString()} / min
                  </span>
                </div>

                <div className="text-right p-2.5 rounded-lg bg-white/80 border border-rose-100">
                  <span className="text-[10px] uppercase font-semibold text-slate-500 block">Severity Tier</span>
                  <span className="text-sm font-bold font-mono text-rose-700 uppercase">
                    {selectedCostIncident.severity || "CRITICAL"}
                  </span>
                </div>
              </div>

              {/* Mathematical Drivers Breakdown Table */}
              <div className="space-y-2.5 text-xs">
                <span className="text-[11px] font-bold text-slate-900 uppercase tracking-wider block">
                  Outage Cost Equation Breakdown
                </span>

                <div className="space-y-2">
                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-slate-800">1. Service Interruption & Revenue Burn</div>
                      <div className="text-[11px] text-slate-500">
                        {cost.durationSeconds}s downtime × ${cost.ratePerSec}/sec base rate × {cost.blastMultiplier}x blast radius multiplier
                      </div>
                    </div>
                    <span className="font-mono font-bold text-slate-900 text-sm">
                      +${Math.round(downtimeLoss).toLocaleString()}
                    </span>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-slate-800">2. Primary SRE Triage & Emergency Response</div>
                      <div className="text-[11px] text-slate-500">
                        Fixed operational triage overhead for {selectedCostIncident.severity || "CRITICAL"} paging & war-room assembly
                      </div>
                    </div>
                    <span className="font-mono font-bold text-slate-900 text-sm">
                      +${cost.baseTriage.toLocaleString()}
                    </span>
                  </div>

                  <div className="p-3 rounded-lg bg-emerald-50/70 border border-emerald-200 flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-emerald-900">3. Deduplication Noise Savings (Offset)</div>
                      <div className="text-[11px] text-emerald-700">
                        {selectedCostIncident.suppressed_count} duplicate alarms suppressed (~$50 / false alert fatigue prevented)
                      </div>
                    </div>
                    <span className="font-mono font-bold text-emerald-700 text-sm">
                      -${preventedLoss.toLocaleString()} saved
                    </span>
                  </div>
                </div>
              </div>

              {/* Affected Services Impact Multiplier */}
              <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1.5">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                  Downstream Blast Multiplier ({cost.blastMultiplier}x)
                </span>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Root cause in <strong className="text-slate-900">{selectedCostIncident.root_cause_service}</strong> cascaded into {selectedCostIncident.affected_services?.length || 1} downstream services ({selectedCostIncident.affected_services?.join(", ")}), compounding business impact.
                </p>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
                <span className="text-slate-400 text-[11px]">
                  Enterprise Outage Cost Model (Gartner / Atlassian Standard)
                </span>
                <button
                  onClick={() => setSelectedCostIncident(null)}
                  className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-medium transition shadow-xs"
                >
                  Close Breakdown
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};

