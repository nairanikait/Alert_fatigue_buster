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
  AlertCircle,
  RefreshCw,
  Search,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Server,
  Layers,
  FileText,
  Clock,
} from "lucide-react";

interface NotificationFeedProps {
  notifications: NotificationItem[];
  onRefresh: () => void;
  totalSuppressed?: number;
}

export const NotificationFeed: React.FC<NotificationFeedProps> = ({
  notifications,
  onRefresh,
  totalSuppressed = 0,
}) => {
  const [selectedChannel, setSelectedChannel] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

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
          iconBg: "bg-emerald-100 text-emerald-700",
          icon: Radio,
          label: "PagerDuty",
        };
      case "slack":
        return {
          badge: "bg-purple-50 text-purple-700 border-purple-200",
          iconBg: "bg-purple-100 text-purple-700",
          icon: MessageSquare,
          label: "Slack",
        };
      case "email":
        return {
          badge: "bg-blue-50 text-blue-700 border-blue-200",
          iconBg: "bg-blue-100 text-blue-700",
          icon: Mail,
          label: "Email",
        };
      default:
        return {
          badge: "bg-slate-100 text-slate-700 border-slate-200",
          iconBg: "bg-slate-100 text-slate-700",
          icon: Terminal,
          label: "Webhook",
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

  // Clean title from redundant screaming prefixes
  const formatCleanTitle = (title: string) => {
    return title.replace(/^[🚨⚠️ℹ️\s]*(CRITICAL|HIGH|MEDIUM|LOW)?\s*INCIDENT:\s*/i, "").trim() || title;
  };

  // Extract a clean, single-line preview from the reason or message
  const getSummaryPreview = (notif: NotificationItem) => {
    if (notif.reason) return notif.reason;
    const lines = notif.message.split("\n").map((l) => l.trim()).filter(Boolean);
    const candidate = lines.find((l) => !l.includes("INCIDENT") && !l.includes("Recommended Action"));
    if (candidate) {
      return candidate.replace(/^[•\-\*]\s*/, "");
    }
    return notif.message.slice(0, 100);
  };

  const handleCopyMessage = (id: number, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
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
            Audit trail of deduplicated and dispatched alert notifications across operational channels.
          </p>
        </div>

        {/* Total Sent & Suppressed Summary Pills */}
        <div className="flex items-center space-x-3 text-xs">
          <div className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 shadow-xs flex items-center space-x-2">
            <span className="text-slate-500">Total Dispatched:</span>
            <span className="font-bold text-indigo-600 font-mono">
              {notifications.length}
            </span>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 shadow-xs flex items-center space-x-2">
            <span className="text-slate-500">Noise Suppressed:</span>
            <span className="font-bold text-emerald-600 font-mono">
              {totalSuppressed.toLocaleString()}
            </span>
          </div>
          <button
            onClick={onRefresh}
            className="p-2 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-slate-600 transition shadow-xs"
            title="Refresh logs"
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
              className={`px-3 py-1 rounded-md transition capitalize ${
                selectedChannel === ch
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
            placeholder="Search by title, service, channel..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 text-slate-800 placeholder-slate-400 w-64"
          />
        </div>
      </div>

      {/* Audit Log Entries List */}
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
              const service = notif.payload?.service || "Infrastructure";
              const alertsMerged = notif.payload?.alert_count || notif.payload?.alerts_merged || 1;
              const target = notif.payload?.channel || notif.payload?.recipient || notif.channel;
              const isDelivered = (notif.status || "SENT").toUpperCase() !== "FAILED";
              const isExpanded = expandedId === notif.id;

              return (
                <div key={notif.id} className="transition-colors hover:bg-slate-50/50">
                  {/* Compact Header Row */}
                  <div className="p-3.5 sm:p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                    <div className="flex items-start space-x-3 min-w-0 flex-1">
                      {/* Channel Icon */}
                      <div className={`p-2 rounded-lg flex-shrink-0 ${chInfo.iconBg} mt-0.5`}>
                        <ChannelIcon className="w-4 h-4" />
                      </div>

                      {/* Main Info */}
                      <div className="space-y-1 min-w-0 flex-1">
                        {/* Title & Key Badges */}
                        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                          <span className="font-semibold text-slate-900 truncate text-[13px]">
                            {formatCleanTitle(notif.title)}
                          </span>

                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wide ${getSeverityBadge(sev)}`}>
                            {sev}
                          </span>

                          <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${chInfo.badge}`}>
                            {chInfo.label}
                          </span>

                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                            <Server className="w-3 h-3 text-slate-500" />
                            <span>{service}</span>
                          </span>

                          {alertsMerged > 1 && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <Layers className="w-3 h-3" />
                              <span>{alertsMerged} alerts consolidated</span>
                            </span>
                          )}
                        </div>

                        {/* Clean 1-Line Summary Preview (No cluttered text dumps) */}
                        <div className="flex items-center gap-2 text-slate-500 text-[11px]">
                          <span className="font-mono text-slate-400">Target: {target}</span>
                          <span className="text-slate-300">•</span>
                          <span className="truncate max-w-xl text-slate-600">
                            {getSummaryPreview(notif)}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Right-Side Status & Actions */}
                    <div className="flex items-center justify-between sm:justify-end gap-3 flex-shrink-0">
                      <div className="text-right">
                        <div className="flex items-center gap-1.5 justify-end">
                          {isDelivered ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <CheckCircle2 className="w-3 h-3" />
                              <span>Delivered</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
                              <AlertCircle className="w-3 h-3" />
                              <span>Failed</span>
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1 text-[11px] text-slate-400 mt-1 justify-end font-mono">
                          <Clock className="w-3 h-3" />
                          <span>{formatTime(notif.sent_at, true)}</span>
                        </div>
                      </div>

                      {/* Expand / Collapse Button */}
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : notif.id)}
                        className={`p-1.5 rounded-md border transition flex items-center gap-1 text-[11px] font-medium ${
                          isExpanded
                            ? "bg-slate-100 border-slate-300 text-slate-900"
                            : "bg-white border-slate-200 hover:bg-slate-50 text-slate-600"
                        }`}
                        title={isExpanded ? "Collapse details" : "Inspect notification payload"}
                      >
                        <span className="hidden sm:inline">{isExpanded ? "Hide" : "Details"}</span>
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>

                  {/* Expanded Detail Panel */}
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-1 bg-slate-50/70 border-t border-slate-100">
                      <div className="bg-white rounded-lg border border-slate-200 p-3.5 space-y-3 shadow-xs">
                        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                            <FileText className="w-3.5 h-3.5 text-indigo-500" />
                            <span>Notification Message Payload</span>
                          </span>
                          <button
                            onClick={() => handleCopyMessage(notif.id, notif.message)}
                            className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-600 hover:text-slate-900 transition px-2 py-0.5 rounded border border-slate-200 hover:bg-slate-50"
                          >
                            {copiedId === notif.id ? (
                              <>
                                <Check className="w-3 h-3 text-emerald-600" />
                                <span className="text-emerald-600">Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-3 h-3" />
                                <span>Copy Message</span>
                              </>
                            )}
                          </button>
                        </div>

                        {/* Neatly Formatted Message Body */}
                        <div className="p-3 bg-slate-50 rounded-md border border-slate-200 text-slate-700 text-xs font-mono whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                          {notif.message}
                        </div>

                        {/* Meta Tags Row */}
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[11px]">
                          <div className="p-2 rounded bg-slate-50 border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">Incident ID</span>
                            <span className="font-mono font-medium text-slate-700">
                              {notif.incident_id || "Unlinked / Direct"}
                            </span>
                          </div>
                          <div className="p-2 rounded bg-slate-50 border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">Recipient / Channel</span>
                            <span className="font-mono font-medium text-slate-700 truncate block">
                              {target}
                            </span>
                          </div>
                          <div className="p-2 rounded bg-slate-50 border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">Alerts Correlated</span>
                            <span className="font-mono font-medium text-slate-700">
                              {alertsMerged} raw signals
                            </span>
                          </div>
                          <div className="p-2 rounded bg-slate-50 border border-slate-100">
                            <span className="text-slate-400 block text-[10px]">Status</span>
                            <span className="font-mono font-medium text-emerald-600">
                              {notif.status || "SENT"}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
