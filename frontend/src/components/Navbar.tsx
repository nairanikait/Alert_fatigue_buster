import React, { useState, useRef, useEffect } from "react";
import {
  ShieldCheck,
  Radio,
  Play,
  FileCode,
  Clock,
  Settings as SettingsIcon,
  CheckCircle2,
  Smartphone,
  ChevronDown,
  Flame,
  Database,
  RefreshCw,
  Zap,
  Activity,
} from "lucide-react";

interface NavbarProps {
  wsConnected: boolean;
  reductionPercentage: number;
  activeIncidents: number;
  onOpenDemo: () => void;
  onOpenSettings: () => void;
  onStartSimulation?: (scenario: string, name: string, count?: number) => void;
  activeSimulation?: {
    simulationId: string;
    scenarioName: string;
    status: string;
    counts?: { generated: number; total: number };
  } | null;
  onOpenDrawer?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  wsConnected,
  reductionPercentage,
  activeIncidents,
  onOpenDemo,
  onOpenSettings,
  onStartSimulation,
  activeSimulation,
  onOpenDrawer,
}) => {
  const [dropdownOpen, setDropdownOpen] = useState<boolean>(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const scenarios = [
    { id: "database_outage", name: "Database Outage", count: 500, desc: "500 cascading service alerts", icon: Database, color: "text-rose-600" },
    { id: "flaky_pod", name: "Flaky Pod Flapping", count: 64, desc: "64 flapping pod restart alerts", icon: RefreshCw, color: "text-amber-600" },
    { id: "alert_storm", name: "Alert Storm", count: 500, desc: "500 multi-service burst alerts", icon: Flame, color: "text-purple-600" },
    { id: "critical_emergency", name: "Critical Emergency", count: 1, desc: "P1 production database crash", icon: Zap, color: "text-rose-600" },
    { id: "service_cascade", name: "Service Cascade", count: 280, desc: "280 topological dependency alerts", icon: Activity, color: "text-blue-600" },
    { id: "recovery", name: "Incident Recovery", count: 20, desc: "Resolution signals for active alerts", icon: CheckCircle2, color: "text-emerald-600" },
  ];

  const handleSelectScenario = (scen: typeof scenarios[0]) => {
    setDropdownOpen(false);
    if (onStartSimulation) {
      onStartSimulation(scen.id, scen.name, scen.count);
    }
  };

  const isSimRunning = activeSimulation?.status === "RUNNING";

  return (
    <header className="sticky top-0 z-30 h-14 border-b border-slate-200 bg-white px-5 flex items-center justify-between shadow-xs">
      {/* Brand & Subtitle */}
      <div className="flex items-center space-x-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-xs flex-shrink-0">
          <ShieldCheck className="w-4 h-4" />
        </div>
        <div className="flex items-baseline space-x-2">
          <span className="font-bold text-base text-slate-900 tracking-tight">Alert Buster</span>
          <span className="hidden sm:inline text-xs text-slate-500 font-normal">
            — Turn alert noise into actionable incidents
          </span>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center space-x-2.5 text-xs">
        {/* System Status */}
        <div className="hidden md:flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
          <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
          <span>Operational</span>
        </div>

        {/* Live WebSocket Stream Indicator */}
        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md border border-slate-200 text-slate-700 bg-white font-mono">
          <span className={`w-2 h-2 rounded-full ${wsConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-400"}`} />
          <span className="text-[11px] font-medium">{wsConnected ? "Live" : "Connecting"}</span>
        </div>

        {/* Active Simulation Live Stream Button */}
        {isSimRunning && onOpenDrawer && (
          <button
            onClick={onOpenDrawer}
            className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-md bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-300 font-semibold shadow-xs transition animate-pulse"
            title="Open Live Simulation Stream Drawer"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-600" />
            <span>
              Live Stream ({activeSimulation?.counts?.generated || 0}/{activeSimulation?.counts?.total || 500})
            </span>
          </button>
        )}

        {/* Generate Simulation Dropdown Button */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-indigo-600 hover:bg-indigo-700 text-white font-medium shadow-xs transition active:scale-95"
            title="Trigger a real-time scenario simulation"
          >
            <Play className="w-3.5 h-3.5 fill-white text-white" />
            <span>Generate Simulation</span>
            <ChevronDown className="w-3 h-3 text-indigo-200 ml-0.5" />
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-72 bg-white rounded-xl shadow-xl border border-slate-200 py-2 z-50 divide-y divide-slate-100 font-sans">
              <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Choose Simulation Scenario
              </div>
              <div className="py-1">
                {scenarios.map((scen) => {
                  const Icon = scen.icon;
                  return (
                    <button
                      key={scen.id}
                      onClick={() => handleSelectScenario(scen)}
                      className="w-full px-3 py-2 text-left hover:bg-slate-50 transition flex items-start space-x-2.5 group"
                    >
                      <div className={`p-1.5 rounded-md bg-slate-50 group-hover:bg-white border border-slate-200 mt-0.5 ${scen.color}`}>
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-xs text-slate-900 group-hover:text-indigo-600 transition">
                            {scen.name}
                          </span>
                          <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 py-0.2 rounded font-medium">
                            {scen.count}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 line-clamp-1">{scen.desc}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Mobile Simulator Guide CTA */}
        <button
          onClick={onOpenDemo}
          className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200/80 text-slate-700 font-medium text-xs border border-slate-200 transition"
          title="Open Mobile Simulator App instructions"
        >
          <Smartphone className="w-3.5 h-3.5 text-slate-500" />
          <span>Mobile App</span>
        </button>

        {/* Settings button */}
        <button
          onClick={onOpenSettings}
          className="p-1.5 rounded-md text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition"
          title="Settings"
        >
          <SettingsIcon className="w-4 h-4" />
        </button>

        {/* User / Profile Avatar */}
        <div className="flex items-center space-x-2 pl-1 border-l border-slate-200">
          <div className="w-7 h-7 rounded-full bg-slate-800 text-white flex items-center justify-center font-medium text-[11px]">
            SRE
          </div>
        </div>
      </div>
    </header>
  );
};
