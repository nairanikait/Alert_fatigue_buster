import React, { useState } from "react";
import { Play, CheckCircle, ShieldAlert, ShieldX, RefreshCw, Zap, Lock, AlertTriangle } from "lucide-react";
import { runSecurityTestScenario } from "../../services/api";

interface SecurityTestControlsProps {
  onScenarioExecuted: () => void;
}

export const SecurityTestControls: React.FC<SecurityTestControlsProps> = ({ onScenarioExecuted }) => {
  const [runningScenario, setRunningScenario] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<any | null>(null);

  const scenarios = [
    {
      id: "valid_alert",
      title: "Valid Webhook",
      desc: "Signed HMAC + fresh timestamp + unique nonce",
      expected: "ACCEPTED (Trust 95+)",
      icon: CheckCircle,
      color: "hover:border-emerald-300 hover:bg-emerald-50/40 text-emerald-700",
    },
    {
      id: "invalid_signature",
      title: "Invalid Signature",
      desc: "Tampered or corrupted HMAC-SHA256 signature",
      expected: "BLOCKED (401)",
      icon: Lock,
      color: "hover:border-red-300 hover:bg-red-50/40 text-red-700",
    },
    {
      id: "replay_attack",
      title: "Replay Attack",
      desc: "Duplicate Request ID reused across requests",
      expected: "BLOCKED (409)",
      icon: RefreshCw,
      color: "hover:border-orange-300 hover:bg-orange-50/40 text-orange-700",
    },
    {
      id: "alert_flood",
      title: "Alert Flood Attack",
      desc: "High-frequency flood exceeding rate limits",
      expected: "THROTTLED (429)",
      icon: Zap,
      color: "hover:border-purple-300 hover:bg-purple-50/40 text-purple-700",
    },
    {
      id: "unknown_source",
      title: "Unknown Source",
      desc: "Unregistered or disabled webhook source",
      expected: "QUARANTINED (Low Trust)",
      icon: ShieldAlert,
      color: "hover:border-amber-300 hover:bg-amber-50/40 text-amber-700",
    },
    {
      id: "malformed_payload",
      title: "Malformed Payload",
      desc: "Invalid JSON syntax & boundary violations",
      expected: "REJECTED (400)",
      icon: ShieldX,
      color: "hover:border-rose-300 hover:bg-rose-50/40 text-rose-700",
    },
    {
      id: "critical_suspicious",
      title: "Critical Alert Safety",
      desc: "Critical severity alert with volume anomaly",
      expected: "QUARANTINED & PRESERVED (Never dropped!)",
      icon: AlertTriangle,
      color: "hover:border-indigo-300 hover:bg-indigo-50/40 text-indigo-700",
    },
  ];

  const handleRun = async (scenId: string) => {
    setRunningScenario(scenId);
    try {
      const res = await runSecurityTestScenario(scenId);
      setTestResult(res);
      onScenarioExecuted();
    } catch (e: any) {
      setTestResult({ error: e.message });
    } finally {
      setRunningScenario(null);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
      <div className="p-3.5 border-b border-slate-200 bg-slate-50/70 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Play className="w-4 h-4 text-indigo-600" />
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
            Alert Integrity Shield — Live Security Test Suite
          </h3>
        </div>
        <span className="text-[11px] text-slate-500 font-medium hidden sm:inline">
          1-Click Automated Scenario Demonstrator
        </span>
      </div>

      <div className="p-3.5">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2.5">
          {scenarios.map((scen) => {
            const Icon = scen.icon;
            const isRunning = runningScenario === scen.id;

            return (
              <button
                key={scen.id}
                onClick={() => handleRun(scen.id)}
                disabled={isRunning}
                className={`p-3 text-left border border-slate-200 rounded-lg transition-all flex flex-col justify-between space-y-2 bg-white shadow-xs ${scen.color}`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className="font-bold text-xs text-slate-900 flex items-center space-x-1.5">
                    <Icon className="w-3.5 h-3.5" />
                    <span>{scen.title}</span>
                  </span>
                  {isRunning && <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-600" />}
                </div>
                <p className="text-[11px] text-slate-500 line-clamp-2">{scen.desc}</p>
                <div className="pt-1.5 border-t border-slate-100 flex items-center justify-between text-[10px] w-full font-mono">
                  <span className="text-slate-400">Expected:</span>
                  <span className="font-semibold text-slate-700">{scen.expected}</span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Test Result Execution Banner */}
        {testResult && (
          <div className="mt-3.5 p-3 rounded-lg bg-slate-900 text-white font-mono text-xs border border-slate-800 space-y-2">
            <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
              <span className="text-emerald-400 font-bold uppercase tracking-wider flex items-center space-x-1.5">
                <CheckCircle className="w-3.5 h-3.5" />
                <span>Scenario Execution Result: {testResult.scenario}</span>
              </span>
              <button onClick={() => setTestResult(null)} className="text-slate-500 hover:text-slate-300">✕</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px]">
              <div>
                <span className="text-slate-400">Expected: </span>
                <span className="text-indigo-300 font-semibold">{testResult.expected}</span>
              </div>
              <div>
                <span className="text-slate-400">Shield Decision: </span>
                <span className="text-emerald-300 font-bold">{testResult.result?.decision || "REJECTED"}</span>
              </div>
              <div>
                <span className="text-slate-400">Trust Score: </span>
                <span className="text-amber-300 font-bold">{testResult.result?.trust_score ?? 0} / 100</span>
              </div>
            </div>
            <div className="text-[11px] text-slate-300 pt-1 border-t border-slate-800/80">
              <span className="text-slate-400">Reason: </span>
              {testResult.result?.reason || testResult.error}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
