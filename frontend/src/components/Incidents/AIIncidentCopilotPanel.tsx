import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Loader2,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Layers,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  ShieldAlert,
  Target,
  Clock,
  ArrowRight,
  Info,
  Sliders,
  Cpu,
  Flame,
  Check
} from "lucide-react";
import { IncidentItem, AIIncidentAnalysis } from "../../types";
import { generateIncidentAIAnalysis } from "../../services/api";

interface AIIncidentCopilotPanelProps {
  incident: IncidentItem;
  onUpdateIncident?: (updated: IncidentItem) => void;
  defaultExpanded?: boolean;
}

export const AIIncidentCopilotPanel: React.FC<AIIncidentCopilotPanelProps> = ({
  incident,
  onUpdateIncident,
  defaultExpanded = false,
}) => {
  const [analysis, setAnalysis] = useState<AIIncidentAnalysis | null>(incident.ai_analysis || null);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [showTechnicalReasoning, setShowTechnicalReasoning] = useState(false);
  const [isPanelOpen, setIsPanelOpen] = useState(defaultExpanded || Boolean(incident.ai_analysis));

  useEffect(() => {
    if (incident.ai_analysis) {
      setAnalysis(incident.ai_analysis);
    }
  }, [incident.ai_analysis]);

  const loadingSteps = [
    "Scanning telemetry and alert fingerprints...",
    "Tracing service dependency graph hops...",
    "Auditing root-cause evidence & timeline...",
    "Synthesizing 3-tier SRE remediation plan...",
  ];

  const handleGenerate = async (regenerate: boolean = false) => {
    try {
      setLoading(true);
      setError(null);
      setLoadingStep(0);
      setIsPanelOpen(true);

      // Multi-stage progressive loading animation
      const interval = setInterval(() => {
        setLoadingStep((prev) => (prev < loadingSteps.length - 1 ? prev + 1 : prev));
      }, 700);

      const res = await generateIncidentAIAnalysis(incident.id, regenerate);
      clearInterval(interval);

      setAnalysis(res.analysis);
      if (onUpdateIncident) {
        onUpdateIncident({
          ...incident,
          ai_analysis: res.analysis,
        });
      }
    } catch (err: any) {
      setError(err?.message || "AI analysis temporarily unavailable. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const getRiskBadge = (risk: string) => {
    switch ((risk || "").toUpperCase()) {
      case "CRITICAL":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "HIGH":
        return "bg-orange-50 text-orange-700 border-orange-200";
      case "MEDIUM":
        return "bg-amber-50 text-amber-700 border-amber-200";
      default:
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
    }
  };

  return (
    <div className="rounded-xl border border-indigo-100 bg-gradient-to-b from-indigo-50/40 via-white to-white overflow-hidden shadow-xs transition-all duration-200">
      {/* Top Banner & Control Bar */}
      <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-indigo-100/70">
        <div className="flex items-start space-x-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 text-white shadow-xs flex-shrink-0 mt-0.5">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold uppercase tracking-wider text-indigo-700 bg-indigo-100/80 px-2 py-0.5 rounded-md">
                AI SRE Copilot
              </span>
              <span className="text-xs font-mono text-slate-400">Incident Analysis</span>
              {analysis && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold flex items-center gap-1">
                  <Check className="w-3 h-3 text-emerald-600" />
                  Analysis Ready
                </span>
              )}
            </div>
            <h3 className="text-base font-extrabold text-slate-900 tracking-tight mt-1 flex items-center gap-2">
              <span>{incident.title}</span>
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Root Cause: <strong className="text-indigo-600">{incident.root_cause_service}</strong> ({incident.root_cause_alert_name}) • {incident.alert_count} correlated alerts • {incident.suppressed_count} suppressed
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-2 self-end sm:self-center">
          {!analysis && !loading && (
            <button
              onClick={() => handleGenerate(false)}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 active:scale-95 text-white text-xs font-semibold shadow-xs transition flex items-center space-x-2 cursor-pointer"
            >
              <Sparkles className="w-4 h-4 text-indigo-200" />
              <span>Generate AI Solution</span>
            </button>
          )}

          {analysis && !loading && (
            <div className="flex items-center space-x-2">
              <button
                onClick={() => handleGenerate(true)}
                className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition shadow-2xs flex items-center space-x-1.5 cursor-pointer"
                title="Request a fresh analysis for this incident"
              >
                <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
                <span>Regenerate</span>
              </button>
              <button
                onClick={() => setIsPanelOpen(!isPanelOpen)}
                className="p-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition shadow-2xs cursor-pointer"
                title={isPanelOpen ? "Collapse panel" : "Expand panel"}
              >
                {isPanelOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Loading State with Progressive SRE Steps */}
      {loading && (
        <div className="p-8 text-center space-y-5 bg-indigo-50/20">
          <div className="inline-flex p-3 rounded-2xl bg-indigo-600/10 text-indigo-600">
            <Loader2 className="w-8 h-8 animate-spin" />
          </div>
          <div className="space-y-1">
            <h4 className="text-sm font-bold text-slate-900">
              Analyzing Correlated Incident with AI SRE Copilot...
            </h4>
            <p className="text-xs text-slate-500 font-mono">
              Evaluating 1 master incident from {incident.alert_count} signals across {incident.affected_services?.length || 1} services
            </p>
          </div>

          <div className="max-w-md mx-auto bg-white border border-indigo-100 rounded-xl p-4 text-left space-y-2.5 shadow-xs">
            {loadingSteps.map((step, idx) => (
              <div key={idx} className="flex items-center space-x-2.5 text-xs">
                {idx < loadingStep ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                ) : idx === loadingStep ? (
                  <Loader2 className="w-4 h-4 text-indigo-600 animate-spin flex-shrink-0" />
                ) : (
                  <div className="w-4 h-4 rounded-full border border-slate-300 flex-shrink-0" />
                )}
                <span
                  className={`${
                    idx < loadingStep
                      ? "text-slate-600 line-through"
                      : idx === loadingStep
                      ? "text-indigo-900 font-bold"
                      : "text-slate-400"
                  }`}
                >
                  {step}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="p-5 bg-rose-50 border-t border-rose-100 flex items-start justify-between gap-3 text-xs text-rose-800">
          <div className="flex items-start space-x-2.5">
            <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">AI Analysis Unavailable:</span> {error}
              <p className="text-[11px] text-rose-600 mt-0.5">
                Core incident tracking, metrics, and notification routing remain fully operational.
              </p>
            </div>
          </div>
          <button
            onClick={() => handleGenerate(true)}
            className="px-2.5 py-1 rounded bg-white border border-rose-200 text-rose-700 font-semibold hover:bg-rose-50 transition cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Analysis Content Body */}
      {analysis && !loading && isPanelOpen && (
        <div className="p-5 sm:p-6 space-y-6 animate-fadeIn">
          {/* Top Metric & Confidence Row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Confidence Score */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                AI Confidence
              </span>
              <div className="flex items-baseline space-x-2">
                <span className="text-2xl font-extrabold font-mono text-indigo-600">
                  {analysis.confidence}%
                </span>
                <span className="text-xs text-slate-500 font-medium">calibrated</span>
              </div>
              <p className="text-[10px] text-slate-500 leading-tight">
                Grounded on multi-hop topology and earliest telemetry signals.
              </p>
            </div>

            {/* Risk Assessment */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                Risk Level
              </span>
              <div className="flex items-center space-x-2">
                <span
                  className={`px-2.5 py-0.5 rounded text-xs font-bold uppercase border ${getRiskBadge(
                    analysis.risk_level
                  )}`}
                >
                  {analysis.risk_level}
                </span>
              </div>
              <p className="text-[10px] text-slate-500 leading-tight">
                Potential blast radius across {incident.affected_services?.length || 1} downstream services.
              </p>
            </div>

            {/* Provider & Model */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                Intelligence Provider
              </span>
              <div className="text-xs font-bold text-slate-900 truncate">
                {analysis.provider || "Google Gemini SRE"}
              </div>
              <p className="text-[10px] text-slate-500 leading-tight">
                Server-side evaluated. Zero sensitive credentials leaked.
              </p>
            </div>
          </div>

          {/* Section 1: What Happened */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5 text-indigo-800">
              <Info className="w-3.5 h-3.5 text-indigo-600" />
              <span>What Happened</span>
            </h4>
            <div className="p-3.5 rounded-xl bg-white border border-slate-200 text-xs text-slate-700 leading-relaxed shadow-2xs">
              <p className="font-semibold text-slate-900 mb-1">{analysis.summary}</p>
              <p className="text-slate-600">{analysis.root_cause_explanation}</p>
            </div>
          </div>

          {/* Section 2: Why Correlated & Why Suppressed */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Correlation Explanation */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-indigo-600" />
                <span>Why These Alerts Are Correlated</span>
              </h4>
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 leading-relaxed h-full">
                {analysis.correlation_explanation}
              </div>
            </div>

            {/* Suppression Explanation */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span>Why Alerts Were Suppressed</span>
              </h4>
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 leading-relaxed h-full">
                {analysis.suppression_explanation}
              </div>
            </div>
          </div>

          {/* Section 3: 3-Tier SRE Recommendations */}
          <div className="space-y-4 pt-2 border-t border-slate-100">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Actionable SRE Remediation Guidance
              </h4>
              <span className="text-[11px] text-slate-500 font-mono">3-Tier Escalation</span>
            </div>

            {/* 🔴 Immediate Mitigation */}
            <div className="p-4 rounded-xl bg-rose-50/50 border border-rose-200/80 space-y-2.5">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-600" />
                <h5 className="text-xs font-bold uppercase tracking-wider text-rose-900">
                  Immediate Mitigation (Do Right Now)
                </h5>
              </div>
              <ol className="list-decimal list-inside space-y-1.5 text-xs text-rose-950 font-medium leading-relaxed pl-1">
                {analysis.immediate_mitigation.map((step, idx) => (
                  <li key={idx} className="pl-1">
                    <span className="text-slate-800">{step}</span>
                  </li>
                ))}
              </ol>
            </div>

            {/* 🟡 Investigation */}
            <div className="p-4 rounded-xl bg-amber-50/50 border border-amber-200/80 space-y-2.5">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <h5 className="text-xs font-bold uppercase tracking-wider text-amber-900">
                  Investigation & Diagnosis (Inspect to Confirm)
                </h5>
              </div>
              <ol className="list-decimal list-inside space-y-1.5 text-xs text-amber-950 font-medium leading-relaxed pl-1">
                {analysis.investigation_steps.map((step, idx) => (
                  <li key={idx} className="pl-1">
                    <span className="text-slate-800">{step}</span>
                  </li>
                ))}
              </ol>
            </div>

            {/* 🟢 Long-Term Prevention */}
            <div className="p-4 rounded-xl bg-emerald-50/50 border border-emerald-200/80 space-y-2.5">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-600" />
                <h5 className="text-xs font-bold uppercase tracking-wider text-emerald-900">
                  Long-Term Prevention (Prevent Recurrence)
                </h5>
              </div>
              <ol className="list-decimal list-inside space-y-1.5 text-xs text-emerald-950 font-medium leading-relaxed pl-1">
                {analysis.long_term_prevention.map((step, idx) => (
                  <li key={idx} className="pl-1">
                    <span className="text-slate-800">{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>

          {/* Section 4: Potential Impact */}
          {analysis.potential_impact && (
            <div className="p-3.5 rounded-xl bg-orange-50/60 border border-orange-200/70 text-xs text-orange-950 space-y-1">
              <span className="font-bold text-orange-900 uppercase tracking-wider text-[10px] flex items-center gap-1">
                <AlertTriangle className="w-3 h-3 text-orange-600" />
                Potential Impact If Unresolved
              </span>
              <p className="text-slate-700 leading-relaxed">{analysis.potential_impact}</p>
            </div>
          )}

          {/* Section 5: Technical Reasoning Accordion */}
          <div className="pt-2 border-t border-slate-100">
            <button
              onClick={() => setShowTechnicalReasoning(!showTechnicalReasoning)}
              className="w-full flex items-center justify-between text-xs font-semibold text-slate-700 hover:text-indigo-600 transition p-2 rounded-lg hover:bg-slate-50 cursor-pointer"
            >
              <span className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-indigo-600" />
                <span>View Technical Reasoning & Evidence</span>
              </span>
              {showTechnicalReasoning ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {showTechnicalReasoning && (
              <div className="mt-2 p-3.5 rounded-xl bg-slate-900 text-slate-200 font-mono text-[11px] space-y-1.5 animate-fadeIn">
                <div className="text-[10px] uppercase text-indigo-400 font-bold tracking-wider mb-1">
                  Evidence Considered by AI Copilot:
                </div>
                {analysis.technical_reasoning?.map((evidence, idx) => (
                  <div key={idx} className="flex items-start space-x-2 text-slate-300">
                    <span className="text-emerald-400">✓</span>
                    <span>{evidence}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Governance & Human Approval Notice */}
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between text-[11px] text-slate-500">
            <div className="flex items-center space-x-2">
              <ShieldAlert className="w-3.5 h-3.5 text-slate-400" />
              <span>
                <strong>SRE Governance:</strong> AI Copilot produces read-only guidance. Engineer review and sign-off required prior to production execution.
              </span>
            </div>
            {analysis.analyzed_at && (
              <span className="text-[10px] font-mono text-slate-400">
                Generated: {new Date(analysis.analyzed_at).toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
