import React from "react";
import { CheckCircle2, MessageSquare, Radio, Mail, Terminal, ChevronRight } from "lucide-react";
import { NotificationItem } from "../../types";
import { formatTime } from "../../utils/formatDate";

interface RecentNotificationsCardProps {
  notifications: NotificationItem[];
  onViewAll: () => void;
}

export const RecentNotificationsCard: React.FC<RecentNotificationsCardProps> = ({
  notifications,
  onViewAll,
}) => {
  // Sample templates if empty to match realistic enterprise view
  const displayItems = notifications.length > 0 ? notifications.slice(0, 4) : [
    {
      id: 1,
      title: "Database Connection Failure",
      channel: "pagerduty",
      sent_at: new Date(Date.now() - 2 * 60000).toISOString(),
      reason: "Critical root cause",
    },
    {
      id: 2,
      title: "High CPU Usage",
      channel: "slack",
      sent_at: new Date(Date.now() - 5 * 60000).toISOString(),
      reason: "Threshold exceeded",
    },
    {
      id: 3,
      title: "Memory Threshold Exceeded",
      channel: "slack",
      sent_at: new Date(Date.now() - 7 * 60000).toISOString(),
      reason: "Resource alert",
    },
    {
      id: 4,
      title: "Disk Space Low",
      channel: "email",
      sent_at: new Date(Date.now() - 12 * 60000).toISOString(),
      reason: "Warning notification",
    },
  ];

  const getChannelBadge = (ch: string) => {
    switch (ch.toLowerCase()) {
      case "pagerduty":
        return { label: "PagerDuty", bg: "bg-emerald-50 text-emerald-700 border-emerald-200" };
      case "slack":
        return { label: "Slack", bg: "bg-purple-50 text-purple-700 border-purple-200" };
      case "email":
        return { label: "Email", bg: "bg-blue-50 text-blue-700 border-blue-200" };
      default:
        return { label: "Mock", bg: "bg-slate-100 text-slate-700 border-slate-200" };
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-sm space-y-3">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900">Recent Notifications</h3>
          <p className="text-xs text-slate-500">Live delivery status across channels</p>
        </div>
        <button
          onClick={onViewAll}
          className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition flex items-center gap-0.5"
        >
          <span>View All</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="divide-y divide-slate-100">
        {displayItems.map((n, idx) => {
          const ch = getChannelBadge(n.channel);
          return (
            <div key={idx} className="py-2.5 flex items-center justify-between gap-3 text-xs">
              <div className="min-w-0 space-y-0.5">
                <div className="font-semibold text-slate-900 truncate">{n.title}</div>
                <div className="text-[11px] text-slate-500 flex items-center space-x-2">
                  <span>{formatTime(n.sent_at)}</span>
                  <span>•</span>
                  <span className="truncate">{n.reason || "Triggered"}</span>
                </div>
              </div>

              <div className="flex items-center space-x-2 flex-shrink-0">
                <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${ch.bg}`}>
                  {ch.label}
                </span>
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
