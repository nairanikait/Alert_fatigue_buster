import React, { useState, useEffect } from "react";
import {
  Sparkles,
  CheckCircle2,
  Loader2,
  X,
  AlertCircle,
  Clock,
  Zap,
  Server,
  Terminal,
  ShieldCheck,
  TrendingUp,
  RefreshCw,
} from "lucide-react";
import { autoSolveSuppressedAlerts, resetSuppressedAlerts, AutoSolveResult } from "../../services/api";

interface AutoSolvePipelineModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCompleted: () => void;
}

const DEFAULT_STAGES = [
  {
    id: "scan",
    name: "Telemetry & Query Ingestion Scan",
    description: "Scan active telemetry feeds for suppressed query signatures (dedup, cooldown, downstream, batching).",
  },
  {
    id: "reconciliation",
    name: "Root-Cause & Correlation Audit",
    description: "Verify topological service dependencies and check if parent incidents can be resolved.",
  },
  {
    id: "transition",
    name: "Automated Query State Transition Engine",
    description: "Execute bulk atomic transition of query states to RESOLVED and notification status to SENT.",
  },
  {
    id: "metrics",
    name: "Operational ROI & MTTR Indexing",
    description: "Recalculate noise suppression ratios, MTTR acceleration, and restored engineer focus hours.",
  },
  {
    id: "audit",
    name: "Audit Trail & Event Commitment",
    description: "Persist signed resolution lifecycle events and synchronize live UI monitoring feeds.",
  },
];

export const AutoSolvePipelineModal: React.FC<AutoSolvePipelineModalProps> = ({
  isOpen,
  onClose,
  onCompleted,
}) => {
  const [currentStageIdx, setCurrentStageIdx] = useState<number>(0);
  const [progress, setProgress] = useState<number>(10);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [result, setResult] = useState<AutoSolveResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);

  useEffect(() => {
    if (!isOpen) {
      setCurrentStageIdx(0);
      setProgress(10);
      setIsRunning(false);
      setResult(null);
      setError(null);
      setTerminalLogs([]);
      return;
    }

    // Automatically trigger the pipeline when modal opens
    runAutoSolvePipeline();
  }, [isOpen]);

  const addLog = (msg: string) => {
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    setTerminalLogs((prev) => [...prev, `[${time}] ${msg}`]);
  };

  const runAutoSolvePipeline = async () => {
    setIsRunning(true);
    setError(null);
    setCurrentStageIdx(0);
    setProgress(15);
    setTerminalLogs([]);

    addLog("Initializing AutoSolve Suppressed Pipeline orchestrator...");
    addLog("Scanning telemetry buffer for suppressed, batched, and deduplicated query records...");

    try {
      // Step 1 -> Step 2 transition
      await new Promise((r) => setTimeout(r, 600));
      setCurrentStageIdx(1);
      setProgress(35);
      addLog("Verifying cross-service correlation graphs and topological dependency chains...");

      // Execute backend API call
      const res = await autoSolveSuppressedAlerts();

      // Step 2 -> Step 3 transition
      await new Promise((r) => setTimeout(r, 600));
      setCurrentStageIdx(2);
      setProgress(60);
      addLog(`Found ${res.solved_count} suppressed queries (${res.total_occurrences} occurrences) across ${res.services_affected.length} services.`);
      addLog(`Transitioning states: FIRING/SUPPRESSED -> RESOLVED and notification status to SENT...`);

      // Step 3 -> Step 4 transition
      await new Promise((r) => setTimeout(r, 600));
      setCurrentStageIdx(3);
      setProgress(85);
      addLog(`Re-indexing MTTR and operational cost savings. Preserved +${res.focus_hours_saved} hours focus time.`);
      if (res.incidents_resolved > 0) {
        addLog(`Parent incident correlation groups fully resolved: ${res.incidents_resolved} incidents.`);
      }

      // Step 4 -> Step 5 transition
      await new Promise((r) => setTimeout(r, 500));
      setCurrentStageIdx(4);
      setProgress(100);
      addLog(`Committed ${res.solved_count} RESOLVED lifecycle records into persistent SQLite audit trail.`);
      addLog(`Pipeline execution finished successfully. All suppressed queries resolved!`);

      setResult(res);
      setIsRunning(false);
    } catch (err: any) {
      console.error("AutoSolve pipeline error:", err);
      setError(err?.message || "Failed to execute AutoSolve pipeline.");
      setIsRunning(false);
      addLog(`[ERROR] Pipeline aborted: ${err?.message || "Internal error"}`);
    }
  };

  const handleFinish = () => {
    onCompleted();
    onClose();
  };

  const handleRunAgain = async () => {
    try {
      setIsRunning(true);
      await resetSuppressedAlerts();
      onCompleted();
      await runAutoSolvePipeline();
    } catch (err: any) {
      console.error("Run again error:", err);
      setIsRunning(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-50 to-white">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 text-white shadow-xs">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
                <span>AutoSolve Suppressed Queries Pipeline</span>
                {isRunning ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Running
                  </span>
                ) : result ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    Completed
                  </span>
                ) : null}
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Automated multi-stage resolution, topological reconciliation, and MTTR indexing.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            disabled={isRunning}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition disabled:opacity-30"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-slate-100 h-1.5 overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${
              error ? "bg-rose-500" : progress === 100 ? "bg-emerald-500" : "bg-indigo-600"
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Body Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* Error Banner if any */}
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Pipeline Execution Failed</p>
                <p className="text-rose-700 mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {/* Pipeline Stages Stepper */}
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <span>Pipeline Stages</span>
              <span>{Math.min(currentStageIdx + 1, 5)} / 5</span>
            </div>

            <div className="space-y-2.5">
              {DEFAULT_STAGES.map((stage, idx) => {
                const isCurrent = idx === currentStageIdx && isRunning;
                const isDone = idx < currentStageIdx || (idx === 4 && !isRunning && result !== null);

                return (
                  <div
                    key={stage.id}
                    className={`p-3 rounded-xl border transition-all flex items-start space-x-3 text-xs ${
                      isCurrent
                        ? "bg-indigo-50/50 border-indigo-200 shadow-xs ring-1 ring-indigo-500/20"
                        : isDone
                        ? "bg-emerald-50/20 border-emerald-200/60"
                        : "bg-slate-50/60 border-slate-200 opacity-60"
                    }`}
                  >
                    <div className="mt-0.5 flex-shrink-0">
                      {isDone ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      ) : isCurrent ? (
                        <Loader2 className="w-4 h-4 text-indigo-600 animate-spin" />
                      ) : (
                        <div className="w-4 h-4 rounded-full border border-slate-300 text-[10px] font-mono flex items-center justify-center text-slate-400">
                          {idx + 1}
                        </div>
                      )}
                    </div>

                    <div className="flex-1 space-y-0.5">
                      <div className="flex items-center justify-between">
                        <span className={`font-semibold ${isCurrent ? "text-indigo-900" : isDone ? "text-slate-900" : "text-slate-600"}`}>
                          {stage.name}
                        </span>
                        {isDone && (
                          <span className="text-[10px] font-semibold text-emerald-600 uppercase">Done</span>
                        )}
                        {isCurrent && (
                          <span className="text-[10px] font-semibold text-indigo-600 uppercase animate-pulse">Running</span>
                        )}
                      </div>
                      <p className="text-slate-500 text-[11px] leading-relaxed">
                        {result && result.pipeline_stages && result.pipeline_stages[idx]?.details
                          ? result.pipeline_stages[idx].details
                          : stage.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Live Execution Console Terminal */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
              <span className="flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-slate-600" />
                <span>Execution Log Stream</span>
              </span>
              <span className="text-[10px] font-mono text-slate-400">stdout</span>
            </div>

            <div className="bg-slate-900 text-slate-200 rounded-xl p-3.5 font-mono text-[11px] space-y-1 max-h-36 overflow-y-auto shadow-inner border border-slate-800">
              {terminalLogs.map((log, i) => (
                <div key={i} className="leading-relaxed flex items-start space-x-2">
                  <span className="text-indigo-400 select-none">&gt;</span>
                  <span className={log.includes("[ERROR]") ? "text-rose-400 font-bold" : log.includes("successfully") ? "text-emerald-400 font-semibold" : "text-slate-300"}>
                    {log}
                  </span>
                </div>
              ))}
              {isRunning && (
                <div className="flex items-center space-x-2 text-indigo-400 animate-pulse pt-1">
                  <span>&gt;</span>
                  <span>Processing pipeline stage...</span>
                </div>
              )}
            </div>
          </div>

          {/* Results Summary Card */}
          {result && (
            <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-50/60 to-slate-50 border border-emerald-200/80 space-y-3 shadow-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span className="text-xs font-bold text-slate-900">AutoSolve Resolution Summary</span>
                </div>
                <span className="text-[11px] text-emerald-700 font-medium font-mono">
                  {result.solved_count} queries resolved
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                <div className="p-2.5 rounded-lg bg-white border border-slate-200 shadow-xs">
                  <span className="text-[10px] text-slate-400 font-medium block">Solved Queries</span>
                  <span className="text-lg font-bold font-mono text-emerald-600 mt-0.5 block">
                    {result.solved_count}
                  </span>
                </div>

                <div className="p-2.5 rounded-lg bg-white border border-slate-200 shadow-xs">
                  <span className="text-[10px] text-slate-400 font-medium block">Occurrences Cleared</span>
                  <span className="text-lg font-bold font-mono text-indigo-600 mt-0.5 block">
                    {result.total_occurrences}
                  </span>
                </div>

                <div className="p-2.5 rounded-lg bg-white border border-slate-200 shadow-xs">
                  <span className="text-[10px] text-slate-400 font-medium block">Services Restored</span>
                  <span className="text-lg font-bold font-mono text-slate-800 mt-0.5 block">
                    {result.services_affected.length}
                  </span>
                </div>

                <div className="p-2.5 rounded-lg bg-white border border-slate-200 shadow-xs">
                  <span className="text-[10px] text-slate-400 font-medium block">Focus Time Preserved</span>
                  <span className="text-lg font-bold font-mono text-amber-600 mt-0.5 block">
                    +{result.focus_hours_saved}h
                  </span>
                </div>
              </div>

              {result.solved_alerts && result.solved_alerts.length > 0 && (
                <div className="pt-2 border-t border-emerald-100">
                  <span className="text-[11px] font-semibold text-slate-700 block mb-1.5">
                    Sample Resolved Telemetry:
                  </span>
                  <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                    {result.solved_alerts.slice(0, 10).map((a) => (
                      <span
                        key={a.id}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-white border border-slate-200 text-slate-700 font-medium"
                      >
                        <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                        <span>{a.alert_name}</span>
                        <span className="text-slate-400 font-mono">({a.service})</span>
                      </span>
                    ))}
                    {result.solved_alerts.length > 10 && (
                      <span className="text-[10px] text-slate-500 self-center">
                        +{result.solved_alerts.length - 10} more
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50/80 flex items-center justify-between">
          <span className="text-[11px] text-slate-500 flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-indigo-500" />
            <span>Resolves alert fatigue without missing critical anomalies.</span>
          </span>

          <div className="flex items-center space-x-2">
            {isRunning ? (
              <button
                disabled
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold shadow-xs flex items-center space-x-2 opacity-80 cursor-wait"
              >
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Executing Pipeline...</span>
              </button>
            ) : result ? (
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleRunAgain}
                  className="px-3.5 py-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-xs transition flex items-center space-x-1.5"
                  title="Reset back to original status (7 suppressed, 1 sent) and re-run pipeline"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
                  <span>Run Again</span>
                </button>
                <button
                  onClick={handleFinish}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white text-xs font-semibold shadow-xs transition flex items-center space-x-1.5"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Done & View Resolved Alerts</span>
                </button>
              </div>
            ) : (
              <button
                onClick={onClose}
                className="px-3.5 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition shadow-xs"
              >
                Close
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
