import React from "react";
import {
  Smartphone,
  Server,
  LayoutDashboard,
  ArrowRight,
  CheckCircle2,
  Terminal,
  ExternalLink,
  ShieldCheck,
  Zap,
  Radio,
  Layers,
} from "lucide-react";

interface MobileSimulatorGuideProps {
  wsConnected: boolean;
}

export const MobileSimulatorGuide: React.FC<MobileSimulatorGuideProps> = ({ wsConnected }) => {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Smartphone className="w-5 h-5 text-indigo-600" />
            <span>Mobile Alert Simulator (React Native)</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono text-slate-700">/simulator-mobile</code>.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 font-medium shadow-xs flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${wsConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-400"}`} />
            <span>{wsConnected ? "Dashboard Live Connected" : "Connecting"}</span>
          </span>
        </div>
      </div>

      {/* Architecture Visual Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-5">
        <div className="border-b border-slate-100 pb-3">
          <h2 className="text-sm font-bold text-slate-900">Decoupled Architecture Flow</h2>
          <p className="text-xs text-slate-500">

          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
          {/* Step 1: Mobile App */}
          <div className="p-4 rounded-xl border border-indigo-200 bg-indigo-50/50 space-y-3">
            <div className="flex items-center justify-between">
              <span className="p-2 rounded-lg bg-indigo-600 text-white shadow-xs">
                <Smartphone className="w-5 h-5" />
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-700 bg-white px-2 py-0.5 rounded border border-indigo-200">
                Client 1
              </span>
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">React Native Simulator</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              </p>
            </div>
            <div className="text-[11px] font-mono text-indigo-700 font-medium pt-1 border-t border-indigo-100">
              POST /api/simulator/*
            </div>
          </div>

          {/* Step 2: Backend */}
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-3">
            <div className="flex items-center justify-between">
              <span className="p-2 rounded-lg bg-slate-800 text-white shadow-xs">
                <Server className="w-5 h-5" />
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">
                Single Source of Truth
              </span>
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Core FastAPI Backend</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              </p>
            </div>
            <div className="text-[11px] font-mono text-emerald-700 font-medium pt-1 border-t border-slate-200">
              process_alert() Pipeline
            </div>
          </div>

          {/* Step 3: Web Dashboard */}
          <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/50 space-y-3">
            <div className="flex items-center justify-between">
              <span className="p-2 rounded-lg bg-emerald-600 text-white shadow-xs">
                <LayoutDashboard className="w-5 h-5" />
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-white px-2 py-0.5 rounded border border-emerald-200">
                Client 2 (Observer)
              </span>
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Web SRE Dashboard</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">

              </p>
            </div>
            <div className="text-[11px] font-mono text-emerald-700 font-medium pt-1 border-t border-emerald-100">
              WebSocket ws://.../api/ws
            </div>
          </div>
        </div>
      </div>

      {/* Instructions to Run Mobile App */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
        <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <Terminal className="w-4 h-4 text-indigo-600" />
          <span>How to Run the React Native Mobile Simulator</span>
        </h2>

        <div className="space-y-3 text-xs">
          <div className="p-3.5 bg-slate-900 text-slate-100 rounded-lg font-mono space-y-1">
            <div className="text-slate-400"># 1. Navigate to the simulator-mobile directory</div>
            <div className="text-emerald-400">cd simulator-mobile</div>
            <div className="text-slate-400 mt-2"># 2. Start Expo Metro bundler</div>
            <div className="text-emerald-400">npx expo start</div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
              <span className="font-bold text-slate-900 block">📱 Physical Phone</span>
              <p className="text-[11px] text-slate-600">
                Install <strong>Expo Go</strong> from App Store / Google Play and scan the terminal QR code.
              </p>
            </div>

            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
              <span className="font-bold text-slate-900 block">🍎 iOS Simulator</span>
              <p className="text-[11px] text-slate-600">
                Press <code className="bg-slate-200 px-1 py-0.5 rounded font-mono">i</code> in the terminal to launch on Xcode Simulator.
              </p>
            </div>

            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
              <span className="font-bold text-slate-900 block">🤖 Android Emulator</span>
              <p className="text-[11px] text-slate-600">
                Press <code className="bg-slate-200 px-1 py-0.5 rounded font-mono">a</code> to launch on Android Studio emulator.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Network Configuration Tips */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-3 text-xs">
        <h3 className="font-bold text-slate-900 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          <span>Mobile Device Network Access</span>
        </h3>
        <p className="text-slate-600 leading-relaxed">
          When running on a physical phone over Wi-Fi, open the mobile app's <strong>Settings</strong> tab and configure the backend URL to your computer's local network IP (e.g. <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono text-indigo-700">http://192.168.1.X:8000</code>). On iOS Simulator use <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">http://localhost:8000</code> and on Android Emulator use <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">http://10.0.2.2:8000</code>.
        </p>
      </div>
    </div>
  );
};
