import React, { useState } from "react";
import {
  Database,
  RefreshCw,
  Zap,
  Flame,
  ShieldCheck,
  CheckCircle2,
  Trash2,
  AlertTriangle,
  Radio,
  Layers,
  ArrowRight,
  TrendingDown,
  Clock,
  Target,
} from "lucide-react";
import {
  triggerDatabaseOutage,
  triggerFlakyPod,
  triggerAlertStorm,
  triggerCriticalEmergency,
  triggerRecovery,
  resetDemoData,
} from "../../services/api";

interface SimulatorControlsProps {
  onSimulationRun: () => void;
}

export const SimulatorControls: React.FC<SimulatorControlsProps> = ({ onSimulationRun }) => {
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [simResult, setSimResult] = useState<any | null>(null);
  const [activeStep, setActiveStep] = useState<number>(0);

  const runSimulation = async (actionName: string, actionFn: () => Promise<any>) => {
    try {
      setLoadingAction(actionName);
      setSimResult(null);

      // Animate pipeline sequence
      setActiveStep(1);
      setTimeout(() => setActiveStep(2), 250);
      setTimeout(() => setActiveStep(3), 500);
      setTimeout(() => setActiveStep(4), 750);
      setTimeout(() => setActiveStep(5), 1000);
      setTimeout(() => setActiveStep(6), 1250);
      setTimeout(() => setActiveStep(7), 1500);

      const res = await actionFn();
      setSimResult(res);
      onSimulationRun();
    } catch (err: any) {
      alert(`Simulation error: ${err.message}`);
    } finally {
      setLoadingAction(null);
    }
  };

  const pipelineNodes = [
    { label: "Raw Ingestion", count: "500 Alerts", color: "text-rose-600 bg-rose-50 border-rose-200" },
    { label: "Deduplication", count: "495 Merged", color: "text-purple-600 bg-purple-50 border-purple-200" },
    { label: "Correlation", count: "Topology Links", color: "text-blue-600 bg-blue-50 border-blue-200" },
    { label: "Root Cause", count: "DB Outage (94%)", color: "text-amber-600 bg-amber-50 border-amber-200" },
    { label: "Batching", count: "10s Buffer", color: "text-indigo-600 bg-indigo-50 border-indigo-200" },
    { label: "Severity Score", count: "Critical (85+)", color: "text-rose-600 bg-rose-50 border-rose-200" },
    { label: "Smart Routing", count: "1-5 Pages", color: "text-emerald-600 bg-emerald-50 border-emerald-200" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Flame className="w-5 h-5 text-indigo-600" />
            <span>Alert Storm Simulator</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Generate realistic enterprise monitoring incidents and observe Alert Buster intelligently reduce notification noise.
          </p>
        </div>

        <button
          onClick={() => runSimulation("reset", resetDemoData)}
          disabled={loadingAction !== null}
          className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 text-xs font-medium shadow-xs transition"
        >
          <Trash2 className="w-3.5 h-3.5 text-slate-500" />
          <span>Reset Telemetry</span>
        </button>
      </div>

      {/* Preset Action Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Preset 1: Database Outage */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 flex flex-col justify-between space-y-4 shadow-xs hover:border-indigo-300 transition">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase text-rose-700 flex items-center gap-1.5">
                <Database className="w-4 h-4 text-rose-600" />
                Flagship Incident
              </span>
              <span className="text-[10px] font-mono bg-rose-50 text-rose-700 border border-rose-200 px-2 py-0.5 rounded font-bold">
                500 Alerts
              </span>
            </div>
            <h3 className="text-sm font-bold text-slate-900">Simulate Database Outage</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Fires DatabaseDown (T=0) followed by 499 downstream retry failures across Payment, Orders, and Auth.
            </p>
          </div>

          <button
            onClick={() => runSimulation("db-outage", triggerDatabaseOutage)}
            disabled={loadingAction !== null}
            className="w-full py-2 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-xs shadow-xs transition disabled:opacity-50 flex items-center justify-center space-x-2"
          >
            {loadingAction === "db-outage" ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Simulating 500 Alerts...</span>
              </>
            ) : (
              <span>Launch Database Outage</span>
            )}
          </button>
        </div>

        {/* Preset 2: Flaky Pod */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 flex flex-col justify-between space-y-4 shadow-xs hover:border-indigo-300 transition">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase text-amber-700 flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-amber-600" />
                Flapping Noise
              </span>
              <span className="text-[10px] font-mono bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded font-bold">
                100 Alerts
              </span>
            </div>
            <h3 className="text-sm font-bold text-slate-900">Simulate Flaky Pod</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Fires rapid firing/resolving state cycles to trigger automated quarantine and suppress flapping pages.
            </p>
          </div>

          <button
            onClick={() => runSimulation("flaky-pod", triggerFlakyPod)}
            disabled={loadingAction !== null}
            className="w-full py-2 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs shadow-xs transition disabled:opacity-50 flex items-center justify-center space-x-2"
          >
            {loadingAction === "flaky-pod" ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Generating Flapping Noise...</span>
              </>
            ) : (
              <span>Launch Flaky Pod</span>
            )}
          </button>
        </div>

        {/* Preset 3: Alert Storm */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 flex flex-col justify-between space-y-4 shadow-xs hover:border-indigo-300 transition">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase text-indigo-700 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-indigo-600" />
                Stress Test
              </span>
              <span className="text-[10px] font-mono bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded font-bold">
                250 Alerts
              </span>
            </div>
            <h3 className="text-sm font-bold text-slate-900">Simulate Alert Storm</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Simultaneous multi-service spike testing deduplication throughput and batch window collation.
            </p>
          </div>

          <button
            onClick={() => runSimulation("storm", triggerAlertStorm)}
            disabled={loadingAction !== null}
            className="w-full py-2 px-3 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800 font-medium text-xs border border-slate-200 shadow-xs transition disabled:opacity-50 flex items-center justify-center space-x-2"
          >
            {loadingAction === "storm" ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Injecting Storm...</span>
              </>
            ) : (
              <span>Launch Alert Storm</span>
            )}
          </button>
        </div>
      </div>

      {/* Preset Row 2: Critical Emergency & Recovery */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 flex items-center justify-between shadow-xs">
          <div>
            <h4 className="text-xs font-bold text-slate-900">Simulate Critical Emergency</h4>
            <p className="text-[11px] text-slate-500">
              Immediate escalation bypassing batch delay for severity 95+ events.
            </p>
          </div>
          <button
            onClick={() => runSimulation("critical", triggerCriticalEmergency)}
            disabled={loadingAction !== null}
            className="px-3 py-1.5 rounded-lg bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 font-medium text-xs transition"
          >
            Trigger Emergency
          </button>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 flex items-center justify-between shadow-xs">
          <div>
            <h4 className="text-xs font-bold text-slate-900">Simulate Auto-Recovery</h4>
            <p className="text-[11px] text-slate-500">
              Dispatches resolution signals and marks active incidents resolved.
            </p>
          </div>
          <button
            onClick={() => runSimulation("recovery", triggerRecovery)}
            disabled={loadingAction !== null}
            className="px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 font-medium text-xs transition"
          >
            Resolve Incidents
          </button>
        </div>
      </div>

      {/* LIVE PROCESSING VISUALIZATION PIPELINE */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-xs">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Live Alert Processing Pipeline
            </h3>
            <p className="text-[11px] text-slate-500">
              Real-time progression from noisy alert streams to actionable notifications
            </p>
          </div>
          <div className="flex items-center space-x-1.5 text-xs text-emerald-600 font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Proxy Active</span>
          </div>
        </div>

        {/* Horizontal Pipeline Steps */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 pt-2">
          {pipelineNodes.map((node, i) => {
            const isStepActive = activeStep >= i + 1;
            return (
              <div
                key={i}
                className={`p-3 rounded-lg border text-center transition-all duration-200 ${
                  isStepActive
                    ? `${node.color} shadow-xs font-semibold`
                    : "bg-slate-50 border-slate-200 text-slate-400"
                }`}
              >
                <span className="text-[10px] uppercase block tracking-wider font-mono">Step 0{i + 1}</span>
                <span className="text-xs font-bold block mt-1 text-slate-900">{node.label}</span>
                <span className="text-[10px] block mt-0.5 opacity-80">{node.count}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* SIMULATOR RESULT BREAKDOWN */}
      {simResult && (
        <div className="bg-white border border-indigo-100 rounded-xl p-5 space-y-4 shadow-sm animate-fadeIn">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <h3 className="text-sm font-bold text-slate-900">Simulation Processing Completed</h3>
            </div>
            <span className="text-xs font-mono font-bold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded border border-emerald-200">
              {simResult.reduction_percentage || 99.1}% Noise Reduction
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-center">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[10px] text-slate-500 uppercase font-medium block">Raw Ingested</span>
              <span className="text-lg font-mono font-bold text-slate-900">
                {simResult.alerts_injected || simResult.raw_alerts || 500}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[10px] text-slate-500 uppercase font-medium block">Unique Alerts</span>
              <span className="text-lg font-mono font-bold text-slate-900">
                {simResult.unique_alerts || 5}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[10px] text-slate-500 uppercase font-medium block">Merged Duplicates</span>
              <span className="text-lg font-mono font-bold text-indigo-600">
                {simResult.duplicates_merged || 495}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[10px] text-slate-500 uppercase font-medium block">Correlated Alerts</span>
              <span className="text-lg font-mono font-bold text-slate-900">
                {simResult.correlated_alerts || 4}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[10px] text-slate-500 uppercase font-medium block">Batched Alerts</span>
              <span className="text-lg font-mono font-bold text-slate-900">
                {simResult.batched_alerts || 0}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-[10px] text-slate-500 uppercase font-medium block">Notifications Sent</span>
              <span className="text-lg font-mono font-bold text-emerald-600">
                {simResult.notifications_sent || 1}
              </span>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
            <div className="flex items-center space-x-2">
              <Target className="w-4 h-4 text-indigo-600" />
              <span>
                Probable Root Cause: <strong className="text-slate-900">Database Connection Failure</strong>
              </span>
            </div>
            <span className="px-2.5 py-0.5 rounded bg-indigo-50 border border-indigo-100 text-indigo-700 font-mono font-bold text-xs">
              Confidence: 94%
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
