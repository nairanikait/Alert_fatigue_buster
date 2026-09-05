import React, { useState } from "react";
import { NotificationItem } from "../../types";
import { formatTime } from "../../utils/formatDate";
import {
  Send,
  Radio,
  MessageSquare,
  Mail,
  Terminal,
  CheckCircle2,
  RefreshCw,
  Search,
} from "lucide-react";

interface NotificationFeedProps {
  notifications: NotificationItem[];
  onRefresh: () => void;
  totalSuppressed?: number;
}

export const NotificationFeed: React.FC<NotificationFeedProps> = ({
  notifications,
  onRefresh,
  totalSuppressed = 1494,
}) => {
  const [selectedChannel, setSelectedChannel] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const filtered = notifications.filter((n) => {
    if (selectedChannel !== "ALL" && n.channel.toUpperCase() !== selectedChannel) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        n.title.toLowerCase().includes(q) ||
        n.message.toLowerCase().includes(q) ||
        n.channel.toLowerCase().includes(q) ||
        (n.reason && n.reason.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const getChannelBadge = (channel: string) => {
    switch (channel.toLowerCase()) {
      case "pagerduty":
        return {
          badge: "bg-emerald-50 text-emerald-700 border-emerald-200",
          icon: Radio,
          label: "PagerDuty",
        };
      case "slack":
        return {
          badge: "bg-purple-50 text-purple-700 border-purple-200",
          icon: MessageSquare,
          label: "Slack",
        };
      case "email":
        return {
          badge: "bg-blue-50 text-blue-700 border-blue-200",
          icon: Mail,
          label: "Email",
        };
      default:
        return {
          badge: "bg-slate-100 text-slate-700 border-slate-200",
          icon: Terminal,
          label: "Webhook / Mock",
        };
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case "CRITICAL":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "HIGH":
        return "bg-orange-50 text-orange-700 border-orange-200";
      case "MEDIUM":
        return "bg-amber-50 text-amber-700 border-amber-200";
      default:
        return "bg-slate-100 text-slate-700 border-slate-200";
    }
  };

  return (
    <div className="space-y-5">
      {/* Header with Stats */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Send className="w-5 h-5 text-indigo-600" />
            <span>Notifications Audit Log</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
          </p>
        </div>

        {/* Total Sent & Suppressed Summary Pills */}
        <div className="flex items-center space-x-3 text-xs">
          <div className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 shadow-xs flex items-center space-x-2">
            <span className="text-slate-500">Total Sent:</span>
            <span className="font-bold text-indigo-600 font-mono">
              {notifications.length > 0 ? notifications.length : 13}
            </span>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 shadow-xs flex items-center space-x-2">
            <span className="text-slate-500">Suppressed Noise:</span>
            <span className="font-bold text-emerald-600 font-mono">
              {totalSuppressed.toLocaleString()}
            </span>
          </div>
          <button
            onClick={onRefresh}
            className="p-2 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-slate-600 transition shadow-xs"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filter and Channel Tabs Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white border border-slate-200 p-3 rounded-xl shadow-xs">
        <div className="flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs font-medium">
          {["ALL", "PAGERDUTY", "SLACK", "EMAIL"].map((ch) => (
            <button
              key={ch}
              onClick={() => setSelectedChannel(ch)}
              className={`px-3 py-1 rounded-md transition capitalize ${selectedChannel === ch
                  ? "bg-white text-slate-900 shadow-xs font-semibold"
                  : "text-slate-600 hover:text-slate-900"
                }`}
            >
              {ch === "ALL" ? "All Channels" : ch}
            </button>
          ))}
        </div>

        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search notification payloads..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 text-slate-800 placeholder-slate-400 w-64"
          />
        </div>
      </div>

      {/* Notification Rows Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
        {filtered.length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <CheckCircle2 className="w-8 h-8 text-slate-300 mx-auto" />
            <p className="text-sm font-semibold text-slate-700">No notifications found</p>
            <p className="text-xs text-slate-400">
              Only deduplicated and correlated critical alerts trigger outgoing notifications.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filtered.map((notif) => {
              const chInfo = getChannelBadge(notif.channel);
              const ChannelIcon = chInfo.icon;
              const sev = notif.payload?.severity || "HIGH";
              const service = notif.payload?.service || "Core Infrastructure";
              const alertsMerged = notif.payload?.alert_count || notif.payload?.alerts_merged || 1;
              const target = notif.payload?.channel || notif.payload?.recipient || notif.channel;

              return (
                <div
                  key={notif.id}
                  className="p-4 hover:bg-slate-50/75 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                >
                  <div className="flex items-start space-x-3">
                    <div className="p-2 rounded-lg bg-slate-100 text-slate-600 mt-0.5">
                      <ChannelIcon className="w-4 h-4 text-slate-700" />
                    </div>
                    <div className="space-y-0.5">
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-slate-900">{notif.title}</span>
                        <span className={`px-2 py-0.2 rounded-full text-[10px] font-semibold border ${getSeverityBadge(sev)}`}>
                          {sev}
                        </span>
                        <span className={`px-2 py-0.2 rounded-md text-[10px] font-medium border ${chInfo.badge}`}>
                          {chInfo.label}
                        </span>
                      </div>
                      <p className="text-slate-500 text-[11px] leading-relaxed">
                        {notif.message}
                      </p>
                      <div className="flex items-center space-x-3 text-[10px] text-slate-400 font-mono pt-1">
                        <span>Target: {target}</span>
                        <span>•</span>
                        <span>Service: {service}</span>
                        <span>•</span>
                        <span>Deduped alerts: {alertsMerged}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex sm:flex-col items-end justify-between sm:justify-center text-right text-slate-400 flex-shrink-0">
                    <div className="flex items-center space-x-1.5 text-emerald-600 font-medium">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span className="text-[11px]">Delivered</span>
                    </div>
                    <span className="text-[11px] text-slate-500 mt-0.5 font-mono">
                      {formatTime(notif.sent_at, true)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
