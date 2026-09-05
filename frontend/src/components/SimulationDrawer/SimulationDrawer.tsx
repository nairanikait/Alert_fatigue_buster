import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  X,
  Play,
  Square,
  ArrowDown,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Radio,
  Clock,
  Copy,
  Check,
  Filter,
  Eye,
  Info,
  ShieldAlert,
  Send,
  GitBranch,
  Layers,
  ChevronRight,
  Database,
  Smartphone,
  DollarSign,
  Sparkles,
} from "lucide-react";
import {
  SimulationEventPayload,
  SimulationAlertItem,
  SimulationCounts,
  SimulationSummary,
  simulationStream,
  stopSimulation,
} from "../../services/simulationStream";

interface SimulationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  simulationId: string | null;
  scenarioName: string;
  initialTargetCount?: number;
  onSimulationComplete?: () => void;
}

type FilterCategory = "ALL" | "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "SUPPRESSED" | "NOTIFIED" | "CORRELATED";

export const SimulationDrawer: React.FC<SimulationDrawerProps> = ({
  isOpen,
  onClose,
  simulationId,
  scenarioName,
  initialTargetCount = 500,
  onSimulationComplete,
}) => {
  // Event stream state
  const [events, setEvents] = useState<SimulationEventPayload[]>([]);
  const [status, setStatus] = useState<string>("RUNNING");
  const [counts, setCounts] = useState<SimulationCounts>({
    generated: 0,
    total: initialTargetCount,
    processed: 0,
    suppressed: 0,
    notifications: 0,
    incidents: 0,
    correlated: 0,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    reduction_percentage: 0.0,
  });
  const [summary, setSummary] = useState<SimulationSummary | null>(null);

  // Stop modal state
  const [showStopModal, setShowStopModal] = useState<boolean>(false);
  const [isStopping, setIsStopping] = useState<boolean>(false);

  // Inspection state
  const [selectedEvent, setSelectedEvent] = useState<SimulationEventPayload | null>(null);

  // Filter state
  const [activeFilter, setActiveFilter] = useState<FilterCategory>("ALL");

  // Auto-scroll state
  const streamContainerRef = useRef<HTMLDivElement>(null);
  const [isUserScrolledUp, setIsUserScrolledUp] = useState<boolean>(false);
  const [unseenCount, setUnseenCount] = useState<number>(0);

  // Elapsed timer state
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const timerRef = useRef<any>(null);

  // Copied simulation ID state
  const [copiedId, setCopiedId] = useState<boolean>(false);

  // Handle stream subscription
  useEffect(() => {
    if (!isOpen || !simulationId) return;

    setEvents([]);
    setStatus("RUNNING");
    setSummary(null);
    setElapsedSeconds(0);
    setUnseenCount(0);
    setIsUserScrolledUp(false);

    // Connect to WebSocket stream
    simulationStream.connect(simulationId);

    // Timer for elapsed seconds
    const startTimestamp = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTimestamp) / 1000));
    }, 1000);

    const unsub = simulationStream.onEvent((event) => {
      if (event.type === "simulation.sync") {
        if (event.counts) setCounts(event.counts);
        if (event.status) setStatus(event.status);
        if (event.summary) setSummary(event.summary);
      } else if (event.type === "alert.processed") {
        setEvents((prev) => {
          // Avoid duplicates by sequence number
          if (prev.some((e) => e.seq === event.seq)) return prev;
          return [...prev, event];
        });

        if (event.counts) {
          setCounts(event.counts);
        }

        // Auto-scroll logic
        if (isUserScrolledUp) {
          setUnseenCount((c) => c + 1);
        } else {
          requestAnimationFrame(() => {
            if (streamContainerRef.current) {
              streamContainerRef.current.scrollTop = streamContainerRef.current.scrollHeight;
            }
          });
        }
      } else if (event.type === "simulation.completed") {
        setStatus("COMPLETED");
        if (event.summary) setSummary(event.summary);
        if (event.counts) setCounts(event.counts);
        if (timerRef.current) clearInterval(timerRef.current);
        if (onSimulationComplete) onSimulationComplete();
      } else if (event.type === "simulation.stopped") {
        setStatus("STOPPED");
        if (event.counts) setCounts(event.counts);
        if (timerRef.current) clearInterval(timerRef.current);
        if (onSimulationComplete) onSimulationComplete();
      } else if (event.type === "simulation.failed") {
        setStatus("FAILED");
        if (timerRef.current) clearInterval(timerRef.current);
      }
    });

    return () => {
      unsub();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isOpen, simulationId]);

  // Handle scroll detection
  const handleScroll = () => {
    if (!streamContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = streamContainerRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 40;

    if (atBottom) {
      setIsUserScrolledUp(false);
      setUnseenCount(0);
    } else {
      setIsUserScrolledUp(true);
    }
  };

  const scrollToBottom = () => {
    if (streamContainerRef.current) {
      streamContainerRef.current.scrollTo({
        top: streamContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
      setIsUserScrolledUp(false);
      setUnseenCount(0);
    }
  };

  const handleStopSimulation = async () => {
    if (!simulationId) return;
    try {
      setIsStopping(true);
      await stopSimulation(simulationId);
      setStatus("STOPPED");
      setShowStopModal(false);
      if (timerRef.current) clearInterval(timerRef.current);
    } catch (err: any) {
      alert(`Could not stop simulation: ${err.message}`);
    } finally {
      setIsStopping(false);
    }
  };

  const handleCopyId = () => {
    if (!simulationId) return;
    navigator.clipboard.writeText(simulationId);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  // Format elapsed time MM:SS
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  // Format real timestamp e.g. 10:42:01.125
  const formatTimestamp = (isoString?: string) => {
    if (!isoString) return "--:--:--";
    try {
      const date = new Date(isoString);
      const h = date.getHours().toString().padStart(2, "0");
      const m = date.getMinutes().toString().padStart(2, "0");
      const s = date.getSeconds().toString().padStart(2, "0");
      const ms = date.getMilliseconds().toString().padStart(3, "0");
      return `${h}:${m}:${s}.${ms}`;
    } catch {
      return isoString;
    }
  };

  // Filtered alert list
  const filteredEvents = useMemo(() => {
    if (activeFilter === "ALL") return events;
    return events.filter((ev) => {
      const sev = (ev.alert?.severity || "").toUpperCase();
      const res = (ev.result || "").toLowerCase();
      const action = (ev.action || "").toUpperCase();

      if (activeFilter === "CRITICAL") return sev === "CRITICAL";
      if (activeFilter === "HIGH") return sev === "HIGH";
      if (activeFilter === "MEDIUM") return sev === "MEDIUM";
      if (activeFilter === "LOW") return sev === "LOW";
      if (activeFilter === "SUPPRESSED") return res === "suppressed" || res === "duplicate" || res === "cooldown" || res === "batched";
      if (activeFilter === "NOTIFIED") return res === "notified" || action === "NOTIFIED";
      if (activeFilter === "CORRELATED") return res === "correlated" || action.includes("DOWNSTREAM") || Boolean(ev.correlation_id);
      return true;
    });
  }, [events, activeFilter]);

  // Filter counts
  const filterCounts = useMemo(() => {
    const fc = {
      ALL: events.length,
      CRITICAL: 0,
      HIGH: 0,
      MEDIUM: 0,
      LOW: 0,
      SUPPRESSED: 0,
      NOTIFIED: 0,
      CORRELATED: 0,
    };

    events.forEach((ev) => {
      const sev = (ev.alert?.severity || "").toUpperCase();
      const res = (ev.result || "").toLowerCase();
      const action = (ev.action || "").toUpperCase();

      if (sev === "CRITICAL") fc.CRITICAL++;
      else if (sev === "HIGH") fc.HIGH++;
      else if (sev === "MEDIUM") fc.MEDIUM++;
      else if (sev === "LOW") fc.LOW++;

      if (res === "suppressed" || res === "duplicate" || res === "cooldown" || res === "batched") fc.SUPPRESSED++;
      if (res === "notified" || action === "NOTIFIED") fc.NOTIFIED++;
      if (res === "correlated" || action.includes("DOWNSTREAM") || Boolean(ev.correlation_id)) fc.CORRELATED++;
    });

    return fc;
  }, [events]);

  // Visual status badge helper
  const renderStatusBadge = (event: SimulationEventPayload) => {
    const result = (event.result || "").toLowerCase();
    const action = (event.action || "").toUpperCase();

    if (result === "duplicate" || action.includes("DUPLICATE")) {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
          <span className="mr-1">⊘</span> DUPLICATE
        </span>
      );
    }
    if (result === "correlated" || action.includes("DOWNSTREAM")) {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
          <span className="mr-1">↗</span> CORRELATED
        </span>
      );
    }
    if (result === "batched" || action === "BATCHED") {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
          <span className="mr-1">⊘</span> BATCHED
        </span>
      );
    }
    if (result === "cooldown" || action.includes("COOLDOWN")) {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          <span className="mr-1">⊘</span> COOLDOWN
        </span>
      );
    }
    if (result === "notified" || action === "NOTIFIED") {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <span className="mr-1">✓</span> NOTIFIED
        </span>
      );
    }
    if (result === "resolved" || action.includes("RESOLVED")) {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-teal-50 text-teal-700 border border-teal-200">
          <span className="mr-1">✓</span> RESOLVED
        </span>
      );
    }
    if (result === "suppressed" || action.includes("SUPPRESSED")) {
      return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
          <span className="mr-1">⊘</span> SUPPRESSED
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-50 text-slate-600 border border-slate-200">
        <span className="mr-1">●</span> RECEIVED
      </span>
    );
  };

  const getSeverityBadgeClass = (sev: string) => {
    switch (sev?.toUpperCase()) {
      case "CRITICAL":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "HIGH":
        return "bg-purple-50 text-purple-700 border-purple-200";
      case "MEDIUM":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "LOW":
        return "bg-slate-100 text-slate-700 border-slate-200";
      default:
        return "bg-slate-100 text-slate-700 border-slate-200";
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Dimmed backdrop - clicking it closes drawer while leaving simulation running */}
      <div
        className="fixed inset-0 bg-slate-900/20 backdrop-blur-[1px] z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Right Drawer Panel */}
      <aside className="fixed top-0 right-0 h-full w-[490px] max-w-[95vw] bg-white border-l border-slate-200 shadow-2xl z-50 flex flex-col justify-between text-slate-900 transition-transform duration-300 ease-out transform translate-x-0 font-sans">
        {/* 1. Header */}
        <div className="p-4 border-b border-slate-200 bg-slate-50/80 flex-shrink-0 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-600 animate-pulse" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Simulation Live Stream
              </h2>
            </div>

            <div className="flex items-center space-x-2">
              {/* Stop Simulation Button */}
              {status === "RUNNING" && (
                <button
                  onClick={() => setShowStopModal(true)}
                  className="flex items-center space-x-1 px-2.5 py-1 rounded bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 text-[11px] font-semibold transition"
                  title="Stop simulation execution"
                >
                  <Square className="w-3 h-3 fill-rose-600 text-rose-600" />
                  <span>Stop</span>
                </button>
              )}

              {/* Close Button */}
              <button
                onClick={onClose}
                className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition"
                title="Close drawer (simulation will continue in background)"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Scenario Name & Running Badge Row */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-1.5">
                <span>{scenarioName}</span>
              </h1>
              <div className="flex items-center space-x-2 text-[11px] text-slate-500 font-mono mt-0.5">
                <span>ID: {simulationId || "--"}</span>
                <button
                  onClick={handleCopyId}
                  className="hover:text-slate-800 transition"
                  title="Copy Simulation ID"
                >
                  {copiedId ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                </button>
              </div>
            </div>

            <div className="flex flex-col items-end space-y-1">
              {/* Status Badge */}
              {status === "RUNNING" && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping mr-1.5" />
                  RUNNING
                </span>
              )}
              {status === "COMPLETED" && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                  <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-700" />
                  COMPLETED
                </span>
              )}
              {status === "STOPPED" && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
                  STOPPED
                </span>
              )}
              {status === "FAILED" && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
                  FAILED
                </span>
              )}

              {/* Elapsed Timer */}
              <div className="flex items-center space-x-1 text-[11px] text-slate-500 font-mono">
                <Clock className="w-3 h-3 text-slate-400" />
                <span>Elapsed {formatTime(elapsedSeconds)}</span>
              </div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] text-slate-600 font-medium">
              <span>Progress:</span>
              <span className="font-mono font-bold text-slate-900">
                {counts.generated} / {counts.total} alerts (
                {counts.total > 0 ? Math.round((counts.generated / counts.total) * 100) : 0}%)
              </span>
            </div>
            <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-150 ${
                  status === "COMPLETED" ? "bg-emerald-500" : "bg-indigo-600"
                }`}
                style={{
                  width: `${counts.total > 0 ? Math.min(100, (counts.generated / counts.total) * 100) : 0}%`,
                }}
              />
            </div>
          </div>
        </div>

        {/* 2. Live Counters Grid */}
        <div className="px-4 py-2.5 bg-white border-b border-slate-200 grid grid-cols-6 gap-1.5 flex-shrink-0 text-center">
          <div className="p-1.5 rounded bg-slate-50 border border-slate-100">
            <div className="text-[9px] font-bold uppercase text-slate-400">Gen</div>
            <div className="text-xs font-mono font-bold text-slate-800">{counts.generated}</div>
          </div>
          <div className="p-1.5 rounded bg-slate-50 border border-slate-100">
            <div className="text-[9px] font-bold uppercase text-slate-400">Proc</div>
            <div className="text-xs font-mono font-bold text-slate-800">{counts.processed}</div>
          </div>
          <div className="p-1.5 rounded bg-slate-50 border border-slate-100">
            <div className="text-[9px] font-bold uppercase text-slate-400">Supp</div>
            <div className="text-xs font-mono font-bold text-indigo-700">{counts.suppressed}</div>
          </div>
          <div className="p-1.5 rounded bg-slate-50 border border-slate-100">
            <div className="text-[9px] font-bold uppercase text-slate-400">Notif</div>
            <div className="text-xs font-mono font-bold text-emerald-700">{counts.notifications}</div>
          </div>
          <div className="p-1.5 rounded bg-slate-50 border border-slate-100">
            <div className="text-[9px] font-bold uppercase text-slate-400">Inc</div>
            <div className="text-xs font-mono font-bold text-rose-700">{counts.incidents}</div>
          </div>
          <div className="p-1.5 rounded bg-emerald-50 border border-emerald-200">
            <div className="text-[9px] font-bold uppercase text-emerald-700">Reduct</div>
            <div className="text-xs font-mono font-bold text-emerald-800">
              {counts.reduction_percentage.toFixed(1)}%
            </div>
          </div>
        </div>

        {/* 2.5 Live Real-Time ROI & Time Saved Climbing Bar */}
        <div className="px-4 py-2 bg-gradient-to-r from-indigo-50/70 via-slate-50 to-emerald-50/70 border-b border-slate-200 flex items-center justify-between gap-2 flex-shrink-0">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-3.5 h-3.5 text-indigo-600 animate-spin" />
            <div className="text-[11px] font-semibold text-slate-700">
              Live Value Generated:
            </div>
          </div>
          <div className="flex items-center space-x-3 text-xs font-mono">
            <div className="flex items-center space-x-1 text-indigo-700 font-bold bg-white px-2 py-0.5 rounded border border-indigo-200 shadow-2xs">
              <DollarSign className="w-3 h-3 text-indigo-600 -mr-0.5" />
              <span>{Math.round(counts.suppressed * 4.0).toLocaleString()} Saved</span>
            </div>
            <div className="flex items-center space-x-1 text-amber-800 font-semibold bg-white px-2 py-0.5 rounded border border-amber-200 shadow-2xs">
              <Clock className="w-3 h-3 text-amber-600" />
              <span>{((counts.suppressed * 3.0) / 60.0).toFixed(1)}h Returned</span>
            </div>
          </div>
        </div>

        {/* 3. Filter Chips Bar */}
        <div className="px-4 py-2 border-b border-slate-200 bg-slate-50/50 flex items-center space-x-1 overflow-x-auto no-scrollbar flex-shrink-0 text-xs">
          {(
            [
              { key: "ALL", label: "ALL" },
              { key: "CRITICAL", label: "CRIT" },
              { key: "HIGH", label: "HIGH" },
              { key: "MEDIUM", label: "MED" },
              { key: "SUPPRESSED", label: "SUPP" },
              { key: "NOTIFIED", label: "NOTIF" },
              { key: "CORRELATED", label: "CORR" },
            ] as const
          ).map((filter) => {
            const count = filterCounts[filter.key];
            const isActive = activeFilter === filter.key;
            return (
              <button
                key={filter.key}
                onClick={() => setActiveFilter(filter.key)}
                className={`px-2 py-1 rounded-md text-[11px] font-medium transition flex items-center space-x-1 ${
                  isActive
                    ? "bg-indigo-600 text-white shadow-xs font-semibold"
                    : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
                }`}
              >
                <span>{filter.label}</span>
                <span
                  className={`text-[9px] px-1 py-0.2 rounded-full font-mono ${
                    isActive ? "bg-indigo-700 text-white" : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* 4. Stream Container (Scrollable) */}
        <div
          ref={streamContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-100/40 relative"
        >
          {/* Completion Banner */}
          {status === "COMPLETED" && (
            <div className="p-3.5 rounded-lg bg-emerald-50 border border-emerald-300 text-emerald-900 space-y-1.5 shadow-xs mb-3">
              <div className="flex items-center space-x-1.5 text-xs font-bold text-emerald-800">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Simulation Complete</span>
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-emerald-900 pt-1">
                <div>
                  Generated: <strong>{counts.generated} alerts</strong>
                </div>
                <div>
                  Suppressed: <strong>{counts.suppressed} alerts</strong>
                </div>
                <div>
                  Notifications: <strong>{counts.notifications} sent</strong>
                </div>
                <div>
                  Incidents: <strong>{counts.incidents} created</strong>
                </div>
              </div>
              <div className="text-xs pt-1.5 border-t border-emerald-200 font-medium text-emerald-800 flex flex-col space-y-1">
                <div className="flex justify-between">
                  <span>Alert Noise Reduction:</span>
                  <span className="font-mono font-bold text-emerald-700">
                    {counts.reduction_percentage.toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between text-[11px] text-emerald-900 font-mono">
                  <span>Defensible Value Created:</span>
                  <span className="font-bold text-indigo-700">
                    +${Math.round(counts.suppressed * 4.0).toLocaleString()} / {((counts.suppressed * 3.0) / 60.0).toFixed(1)} hrs returned
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Stopped Banner */}
          {status === "STOPPED" && (
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-300 text-amber-900 space-y-1 mb-3 text-xs">
              <div className="font-bold flex items-center gap-1.5">
                <Square className="w-3.5 h-3.5 fill-amber-600 text-amber-600" />
                <span>Simulation Stopped</span>
              </div>
              <p className="text-[11px] text-amber-800">
                Halted by user. Processed {counts.processed} / {counts.total} alerts.
              </p>
            </div>
          )}

          {/* Empty stream state */}
          {filteredEvents.length === 0 && (
            <div className="h-64 flex flex-col items-center justify-center text-slate-400 space-y-2">
              <Radio className="w-6 h-6 animate-pulse text-indigo-500" />
              <p className="text-xs">
                {status === "RUNNING"
                  ? "Streaming alerts from pipeline in real time..."
                  : "No events match the selected filter."}
              </p>
            </div>
          )}

          {/* Alert Stream Rows */}
          {filteredEvents.map((event) => {
            const alert = event.alert;
            if (!alert) return null;

            return (
              <div
                key={event.seq}
                onClick={() => setSelectedEvent(event)}
                className="p-2.5 rounded-lg bg-white border border-slate-200 hover:border-indigo-300 shadow-2xs hover:shadow-xs transition cursor-pointer space-y-1.5 group"
              >
                {/* Row Header: Timestamp + Severity + Status */}
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-[11px] text-slate-500 font-medium">
                      {formatTimestamp(alert.timestamp || event.timestamp)}
                    </span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase border ${getSeverityBadgeClass(
                        alert.severity
                      )}`}
                    >
                      {alert.severity}
                    </span>
                  </div>

                  <div>{renderStatusBadge(event)}</div>
                </div>

                {/* Row Body: Alert Name + Service */}
                <div className="flex items-baseline justify-between">
                  <div className="font-semibold text-xs text-slate-900 group-hover:text-indigo-600 transition truncate max-w-[280px]">
                    {alert.alert_name}
                  </div>
                  <div className="text-[11px] font-mono text-slate-500 truncate max-w-[150px]">
                    {alert.service}
                  </div>
                </div>

                {/* Reason / Action snippet */}
                {event.reason && (
                  <div className="text-[10px] text-slate-500 truncate border-t border-slate-100 pt-1">
                    {event.reason}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Floating "Latest" Button when scrolled up */}
        {isUserScrolledUp && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-16 right-6 bg-slate-900 hover:bg-slate-800 text-white px-3 py-1.5 rounded-full shadow-lg text-xs font-semibold flex items-center space-x-1.5 transition transform hover:scale-105 z-30"
          >
            <ArrowDown className="w-3.5 h-3.5" />
            <span>Latest</span>
            {unseenCount > 0 && (
              <span className="bg-indigo-600 text-white text-[10px] px-1.5 py-0.2 rounded-full font-mono">
                +{unseenCount}
              </span>
            )}
          </button>
        )}

        {/* 5. Drawer Footer */}
        <div className="p-3 border-t border-slate-200 bg-white flex items-center justify-between text-xs text-slate-500 flex-shrink-0">
          <div className="flex items-center space-x-1.5 font-mono text-[11px]">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Telemetry connected</span>
          </div>

          <div className="text-[11px]">Click row for alert details</div>
        </div>

        {/* Stop Confirmation Modal */}
        {showStopModal && (
          <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px] z-50 flex items-center justify-center p-6">
            <div className="bg-white rounded-xl p-5 shadow-xl border border-slate-200 w-full max-w-sm space-y-4 text-slate-900">
              <div className="flex items-center space-x-2 text-rose-600 font-bold text-sm">
                <AlertTriangle className="w-5 h-5" />
                <span>Stop this simulation?</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Already generated: <strong>{counts.generated} / {counts.total}</strong> alerts. Stopping will halt background processing immediately.
              </p>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  onClick={() => setShowStopModal(false)}
                  disabled={isStopping}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-medium hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleStopSimulation}
                  disabled={isStopping}
                  className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-xs transition"
                >
                  {isStopping ? "Stopping..." : "Stop Simulation"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Alert Details Slide-Over Modal */}
        {selectedEvent && (
          <div className="absolute inset-0 bg-slate-900/30 backdrop-blur-[2px] z-50 flex justify-end">
            <div className="w-[420px] max-w-full h-full bg-white border-l border-slate-200 shadow-2xl p-5 flex flex-col justify-between overflow-y-auto space-y-4">
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                  <div className="flex items-center space-x-2">
                    <Info className="w-4 h-4 text-indigo-600" />
                    <h3 className="text-sm font-bold text-slate-900">Alert Telemetry Details</h3>
                  </div>
                  <button
                    onClick={() => setSelectedEvent(null)}
                    className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <span className="text-[10px] font-bold uppercase text-slate-400 block">Alert Name</span>
                    <span className="font-bold text-sm text-slate-900">{selectedEvent.alert?.alert_name}</span>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-[10px] font-bold uppercase text-slate-400 block">Service</span>
                      <span className="font-mono font-semibold text-slate-800">{selectedEvent.alert?.service}</span>
                    </div>
                    <div>
                      <span className="text-[10px] font-bold uppercase text-slate-400 block">Severity</span>
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase border mt-0.5 ${getSeverityBadgeClass(
                          selectedEvent.alert?.severity || "MEDIUM"
                        )}`}
                      >
                        {selectedEvent.alert?.severity}
                      </span>
                    </div>
                  </div>

                  <div>
                    <span className="text-[10px] font-bold uppercase text-slate-400 block">Timestamp</span>
                    <span className="font-mono text-slate-700">
                      {selectedEvent.alert?.timestamp || selectedEvent.timestamp}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-[10px] font-bold uppercase text-slate-400 block">Processing Action</span>
                      <span className="font-mono text-indigo-700 font-medium">{selectedEvent.action || "--"}</span>
                    </div>
                    <div>
                      <span className="text-[10px] font-bold uppercase text-slate-400 block">Status Outcome</span>
                      <div className="mt-0.5">{renderStatusBadge(selectedEvent)}</div>
                    </div>
                  </div>

                  {selectedEvent.reason && (
                    <div>
                      <span className="text-[10px] font-bold uppercase text-slate-400 block">Suppression / Correlation Reason</span>
                      <p className="p-2 rounded bg-slate-50 border border-slate-200 text-slate-700 leading-relaxed mt-1">
                        {selectedEvent.reason}
                      </p>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-100">
                    <div>
                      <span className="text-[10px] font-bold uppercase text-slate-400 block">Incident ID</span>
                      <span className="font-mono text-slate-700">{selectedEvent.incident_id || "None"}</span>
                    </div>
                    <div>
                      <span className="text-[10px] font-bold uppercase text-slate-400 block">Correlation Group</span>
                      <span className="font-mono text-slate-700">{selectedEvent.correlation_id || "None"}</span>
                    </div>
                  </div>

                  {selectedEvent.alert?.fingerprint && (
                    <div>
                      <span className="text-[10px] font-bold uppercase text-slate-400 block">Fingerprint Hash</span>
                      <span className="font-mono text-[10px] text-slate-500 break-all">
                        {selectedEvent.alert.fingerprint}
                      </span>
                    </div>
                  )}

                  {selectedEvent.alert?.message && (
                    <div>
                      <span className="text-[10px] font-bold uppercase text-slate-400 block">Raw Event Message</span>
                      <p className="p-2 rounded bg-slate-50 border border-slate-200 text-slate-600 text-[11px] leading-relaxed mt-1">
                        {selectedEvent.alert.message}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="pt-2">
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="w-full py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs transition"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        )}
      </aside>
    </>
  );
};
