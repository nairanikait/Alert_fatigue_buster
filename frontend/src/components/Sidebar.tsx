import React from "react";
import {
  LayoutDashboard,
  Bell,
  ShieldAlert,
  ShieldCheck,
  GitBranch,
  Send,
  SlidersHorizontal,
  Server,
  BarChart3,
  FlaskConical,
  Smartphone,
  Settings as SettingsIcon,
} from "lucide-react";

export type NavTab =
  | "dashboard"
  | "security"
  | "alerts"
  | "incidents"
  | "rootcause"
  | "notifications"
  | "services"
  | "rules"
  | "analytics"
  | "demo"
  | "settings";


interface SidebarProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  alertCount: number;
  incidentCount: number;
  notificationCount: number;
  filteringRate: number;
  noiseReducedCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  alertCount,
  incidentCount,
  notificationCount,
  filteringRate,
  noiseReducedCount,
}) => {
  const navItems = [
    {
      id: "dashboard" as NavTab,
      label: "Dashboard",
      icon: LayoutDashboard,
      badge: null,
    },
    {
      id: "security" as NavTab,
      label: "Security Shield",
      icon: ShieldCheck,
      badge: "ACTIVE",
      badgeColor: "bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold text-[9px]",
    },
    {
      id: "alerts" as NavTab,
      label: "Alerts",
      icon: Bell,
      badge: alertCount > 0 ? alertCount : null,
      badgeColor: "bg-slate-100 text-slate-700 font-medium",
    },
    {
      id: "incidents" as NavTab,
      label: "Incidents",
      icon: ShieldAlert,
      badge: incidentCount > 0 ? incidentCount : null,
      badgeColor: "bg-red-50 text-red-700 border border-red-200 font-semibold",
    },
    {
      id: "rootcause" as NavTab,
      label: "Root Cause",
      icon: GitBranch,
      badge: null,
    },
    {
      id: "notifications" as NavTab,
      label: "Notifications",
      icon: Send,
      badge: notificationCount > 0 ? notificationCount : null,
      badgeColor: "bg-slate-100 text-slate-700 font-medium",
    },
    {
      id: "services" as NavTab,
      label: "Services",
      icon: Server,
      badge: null,
    },
    {
      id: "rules" as NavTab,
      label: "Rules & Policies",
      icon: SlidersHorizontal,
      badge: null,
    },
    {
      id: "analytics" as NavTab,
      label: "Analytics",
      icon: BarChart3,
      badge: null,
    },
    {
      id: "demo" as NavTab,
      label: "Simulator",
      icon: Smartphone,
      badge: null,
      badgeColor: "bg-indigo-50 text-indigo-700 border border-indigo-200 font-medium text-[10px]",
    },
    {
      id: "settings" as NavTab,
      label: "Settings",
      icon: SettingsIcon,
      badge: null,
    },
  ];

  return (
    <aside className="w-60 border-r border-slate-200 bg-white flex flex-col justify-between p-3 flex-shrink-0 min-h-[calc(100vh-3.5rem)]">
      <div className="space-y-1">
        <div className="px-3 pt-2 pb-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
          Main Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-xs transition-colors duration-150 ${
                isActive
                  ? "bg-indigo-50 text-indigo-700 font-semibold"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-50 font-medium"
              }`}
            >
              <div className="flex items-center space-x-2.5">
                <Icon className={`w-4 h-4 ${isActive ? "text-indigo-600" : "text-slate-400"}`} />
                <span>{item.label}</span>
              </div>
              {item.badge !== null && (
                <span className={`text-[11px] px-2 py-0.5 rounded-full ${item.badgeColor || "bg-slate-100 text-slate-600"}`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Bottom System Mode Box */}
      <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-2 text-xs mt-4">
        <div className="flex items-center justify-between text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
          <span>System Mode</span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[10px] font-bold">
            ON
          </span>
        </div>
        
        <div className="pt-1.5 border-t border-slate-200 space-y-1.5">
          <div className="flex justify-between items-center text-slate-600">
            <span>Filtering Rate:</span>
            <span className="font-mono font-bold text-slate-900">
              {filteringRate > 0 ? `${filteringRate.toFixed(1)}%` : "99.1%"}
            </span>
          </div>
          <div className="flex justify-between items-center text-slate-600">
            <span>Noise Reduced:</span>
            <span className="font-mono font-bold text-indigo-600">
              {noiseReducedCount > 0 ? noiseReducedCount.toLocaleString() : "1,494"}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
};
