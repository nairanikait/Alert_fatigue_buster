import React, { useState, useEffect, useRef } from "react";
import {
  Bot,
  X,
  Send,
  Sparkles,
  Key,
  RotateCcw,
  Check,
  ChevronDown,
  Info,
  ExternalLink,
  ShieldAlert,
  DollarSign,
  TrendingDown,
  Zap,
} from "lucide-react";
import { sendChatMessage, fetchChatStatus } from "../../services/api";
import { MetricsData, AlertItem, IncidentItem, TopologyData } from "../../types";

interface AIChatbotProps {
  currentTab: string;
  metrics: MetricsData;
  alerts: AlertItem[];
  incidents: IncidentItem[];
  topology: TopologyData;
  selectedAlert?: AlertItem | null;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  provider?: string;
  suggestedActions?: string[];
}

export const AIChatbot: React.FC<AIChatbotProps> = ({
  currentTab,
  metrics,
  alerts,
  incidents,
  topology,
  selectedAlert,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [inputMessage, setInputMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [showKeyModal, setShowKeyModal] = useState(false);

  // User-configured API Key (stored in localStorage)
  const [apiKey, setApiKey] = useState<string>(() => {
    return localStorage.getItem("alertbuster_llm_api_key") || "";
  });
  const [provider, setProvider] = useState<string>(() => {
    return localStorage.getItem("alertbuster_llm_provider") || "openai";
  });
  const [keySaved, setKeySaved] = useState(false);

  // Backend key status
  const [serverKeyConfigured, setServerKeyConfigured] = useState(false);
  const [serverProvider, setServerProvider] = useState<string>("built-in");

  // Helper for dynamic suggestions based on real-time state and active tab
  const getContextSuggestions = () => {
    const activeInc = incidents.find((i) => i.status === "FIRING");

    if (activeInc) {
      switch (currentTab) {
        case "incidents":
          return [
            `Why is Incident #${activeInc.id} firing?`,
            `What is the root cause of ${activeInc.root_cause_service}?`,
            "What is our live outage cost?",
          ];
        case "alerts":
          return [
            "Why was this alert suppressed?",
            `Show alerts for ${activeInc.root_cause_service}`,
            "How does fingerprint deduplication work?",
          ];
        case "rootcause":
        case "topology":
          return [
            `Which services are downstream of ${activeInc.root_cause_service}?`,
            `Explain the blast radius for ${activeInc.root_cause_service}`,
            "Are there multi-hop cascades?",
          ];
        default:
          return [
            `Why is ${activeInc.root_cause_service} failing?`,
            "What is our total outage loss?",
            "Which services are in the blast radius?",
          ];
      }
    }

    switch (currentTab) {
      case "incidents":
        return [
          "Summarize past outage history",
          "How is downtime loss calculated?",
          "Which services have highest criticality?",
        ];
      case "alerts":
        return [
          "Why was this alert suppressed?",
          "How does fingerprint deduplication work?",
          "What is our noise reduction rate?",
        ];
      case "rootcause":
      case "topology":
        return [
          "Explain the service dependency graph",
          "Which services are upstream root causes?",
          "How does multi-hop correlation work?",
        ];
      case "rules":
        return [
          "What are our cooldown timers?",
          "How does the 30s deduplication window work?",
          "How are critical alerts routed?",
        ];
      case "demo":
        return [
          "What happens during Database Outage simulation?",
          "How does Alert Storm reduce noise?",
          "How does multi-hop cascade work?",
        ];
      default:
        return [
          "Summarize overall system health",
          "How much alert noise was reduced?",
          "Explain our deduplication & correlation policies",
        ];
    }
  };

  // Initial Assistant Welcome Message
  const [messages, setMessages] = useState<Message[]>(() => [
    {
      id: "welcome-1",
      role: "assistant",
      content:
        "👋 Hello! I am **Zen**, your Alert Buster SRE Copilot.\n\nI have real-time access to live server telemetry, active incidents, root-cause graphs, alerts, and financial outage costs. Ask me anything about what is happening in your system!",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      suggestedActions: [
        "Summarize overall system health",
        "How much alert noise was reduced?",
        "What is our total outage cost?",
      ],
    },
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom of chat
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  // Check backend key status on mount
  useEffect(() => {
    fetchChatStatus()
      .then((res) => {
        setServerKeyConfigured(res.configured);
        if (res.provider && res.provider !== "none") {
          setServerProvider(res.provider);
        }
      })
      .catch(() => {});
  }, []);

  // Save API key
  const handleSaveKey = () => {
    if (apiKey.trim()) {
      localStorage.setItem("alertbuster_llm_api_key", apiKey.trim());
      localStorage.setItem("alertbuster_llm_provider", provider);
    } else {
      localStorage.removeItem("alertbuster_llm_api_key");
    }
    setKeySaved(true);
    setTimeout(() => {
      setKeySaved(false);
      setShowKeyModal(false);
    }, 1200);
  };

  // Build Context for current page
  const buildPageContext = () => {
    return {
      current_tab: currentTab,
      metrics: {
        reduction_percentage: metrics.reduction_percentage,
        incoming_alerts: metrics.incoming_alerts,
        unique_alerts: metrics.unique_alerts,
        suppressed_alerts: metrics.suppressed_alerts,
        batched_alerts: metrics.batched_alerts,
        notifications_sent: metrics.notifications_sent,
        active_incidents: metrics.active_incidents,
      },
      incidents: incidents.slice(0, 5).map((inc) => ({
        id: inc.id,
        title: inc.title,
        status: inc.status,
        severity: inc.severity,
        root_cause_service: inc.root_cause_service,
        root_cause_alert_name: inc.root_cause_alert_name,
        root_cause_reason: inc.root_cause_reason,
        affected_services: inc.affected_services,
        estimated_cost_loss: inc.estimated_cost_loss,
        cost_burn_rate_per_minute: inc.cost_burn_rate_per_minute,
      })),
      recent_alerts: alerts.slice(0, 8).map((a) => ({
        id: a.id,
        alert_name: a.alert_name,
        service: a.service,
        severity: a.severity,
        status: a.status,
        occurrence_count: a.occurrence_count,
        notification_status: a.notification_status,
        suppression_reason: a.suppression_reason,
        fingerprint: a.fingerprint,
      })),
      selected_entity: selectedAlert ? { type: "alert", alert: selectedAlert } : null,
      topology_summary: {
        total_services: topology.services.length,
        total_dependencies: topology.dependencies.length,
      },
    };
  };

  // Send message
  const handleSendMessage = async (textToSend?: string) => {
    const query = (textToSend || inputMessage).trim();
    if (!query || loading) return;

    const userMsg: Message = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputMessage("");
    setLoading(true);

    try {
      const pageContext = buildPageContext();
      const historyPayload = messages
        .filter((m) => m.id !== "welcome-1")
        .slice(-8)
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await sendChatMessage({
        message: query,
        history: historyPayload,
        context: pageContext,
        api_key: apiKey.trim() || undefined,
        provider: provider,
      });

      const assistantMsg: Message = {
        id: `reply-${Date.now()}`,
        role: "assistant",
        content: res.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        provider: res.provider_used,
        suggestedActions: res.suggested_actions || [],
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: Message = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: `⚠️ **Error communicating with assistant:** ${err.message || "Unknown error"}. Please check your connection or backend server.`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  // Format simple markdown helper
  const renderMarkdown = (text: string) => {
    const lines = text.split("\n");
    return (
      <div className="space-y-1.5 leading-relaxed text-xs">
        {lines.map((line, idx) => {
          if (line.startsWith("### ")) {
            return (
              <h4 key={idx} className="font-bold text-slate-900 text-sm mt-2 mb-1">
                {line.replace("### ", "")}
              </h4>
            );
          }
          if (line.startsWith("#### ")) {
            return (
              <h5 key={idx} className="font-bold text-slate-800 text-xs mt-1.5">
                {line.replace("#### ", "")}
              </h5>
            );
          }
          if (line.startsWith("• ") || line.startsWith("- ")) {
            return (
              <div key={idx} className="flex items-start space-x-1.5 ml-1">
                <span className="text-indigo-600 font-bold">•</span>
                <span dangerouslySetInnerHTML={{ __html: formatInlineMarkdown(line.slice(2)) }} />
              </div>
            );
          }
          if (line.startsWith("```")) {
            return null;
          }
          if (!line.trim()) {
            return <div key={idx} className="h-1" />;
          }
          return (
            <p
              key={idx}
              dangerouslySetInnerHTML={{ __html: formatInlineMarkdown(line) }}
            />
          );
        })}
      </div>
    );
  };

  const formatInlineMarkdown = (str: string) => {
    return str
      .replace(/\*\*(.*?)\*\*/g, "<strong class='font-bold text-slate-900'>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em class='italic text-slate-700'>$1</em>")
      .replace(/`([^`]+)`/g, "<code class='px-1 py-0.5 rounded bg-slate-100 font-mono text-[11px] text-indigo-700 font-medium'>$1</code>");
  };

  const hasConfiguredKey = Boolean(apiKey.trim() || serverKeyConfigured);

  return (
    <>
      {/* FLOATING TRIGGER BUTTON (Bottom Right of all pages) */}
      <div className="fixed bottom-6 right-6 z-50 flex items-center space-x-3">
        {!isOpen && (
          <button
            onClick={() => setIsOpen(true)}
            className="group relative flex items-center space-x-2.5 px-4 py-3 rounded-full bg-gradient-to-r from-indigo-600 via-indigo-700 to-purple-600 text-white shadow-xl shadow-indigo-500/25 hover:shadow-2xl hover:shadow-indigo-500/40 hover:scale-105 active:scale-95 transition-all duration-200 border border-indigo-400/30"
          >
            <div className="relative">
              <Bot className="w-5 h-5 text-white" />
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-400 ring-2 ring-indigo-600 animate-pulse" />
            </div>
            <span className="text-xs font-bold tracking-wide">Ask Zen</span>
            <span className="px-1.5 py-0.5 rounded-full bg-white/20 text-[10px] font-mono uppercase tracking-wider backdrop-blur-xs">
              AI
            </span>
          </button>
        )}
      </div>

      {/* CHATBOT WINDOW DIALOG */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-96 sm:w-[430px] h-[590px] max-h-[90vh] flex flex-col rounded-2xl bg-white border border-slate-200 shadow-2xl animate-fadeIn overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3.5 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white border-b border-slate-800">
            <div className="flex items-center space-x-2.5">
              <div className="relative p-2 rounded-xl bg-indigo-600/30 border border-indigo-400/30 text-indigo-300">
                <Bot className="w-4 h-4" />
                <span className="absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400 ring-1 ring-slate-900" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="text-xs font-bold text-white tracking-tight">
                    Zen AI Copilot
                  </h3>
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-indigo-500/30 text-indigo-300 border border-indigo-500/40">
                    Live
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 flex items-center space-x-1.5 font-mono">
                  <span>Context:</span>
                  <span className="capitalize text-indigo-300 font-semibold">{currentTab}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-1 text-slate-400">
              {/* API Key settings trigger */}
              <button
                onClick={() => setShowKeyModal(!showKeyModal)}
                className={`p-1.5 rounded-lg transition ${
                  hasConfiguredKey
                    ? "hover:bg-slate-800 hover:text-white"
                    : "text-amber-400 bg-amber-400/10 hover:bg-amber-400/20"
                }`}
                title={hasConfiguredKey ? "API Key Configured" : "Click to configure LLM API Key"}
              >
                <Key className="w-3.5 h-3.5" />
              </button>

              {/* Reset Chat */}
              <button
                onClick={() =>
                  setMessages([
                    {
                      id: `welcome-${Date.now()}`,
                      role: "assistant",
                      content:
                        "Chat history cleared. I am ready to answer questions grounded in live telemetry!",
                      timestamp: new Date().toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      }),
                      suggestedActions: getContextSuggestions(),
                    },
                  ])
                }
                className="p-1.5 rounded-lg hover:bg-slate-800 hover:text-white transition"
                title="Clear conversation"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>

              {/* Close / Minimize */}
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded-lg hover:bg-slate-800 hover:text-white transition"
                title="Close chat"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Context Telemetry Bar */}
          <div className="px-4 py-2 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-[11px] text-slate-600">
            <div className="flex items-center space-x-2">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-600" />
              <span className="font-medium text-slate-700">Live Telemetry Ingested:</span>
            </div>
            <div className="flex items-center space-x-3 font-mono text-[10px]">
              <span>{metrics.reduction_percentage}% Noise Reduced</span>
              <span>•</span>
              <span className="text-indigo-700 font-semibold">{incidents.length} Incidents</span>
            </div>
          </div>

          {/* API Key Notice Banner (if not set) */}
          {!hasConfiguredKey && (
            <div className="px-3.5 py-2 bg-amber-50 border-b border-amber-200 flex items-center justify-between text-[11px] text-amber-900">
              <div className="flex items-center space-x-1.5">
                <Info className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                <span>Operating in built-in SRE Engine mode. Insert LLM Key for Google Gemini / GPT-4.</span>
              </div>
              <button
                onClick={() => setShowKeyModal(true)}
                className="font-bold text-amber-800 underline underline-offset-2 hover:text-amber-950 flex-shrink-0 ml-1 text-[11px]"
              >
                Insert Key
              </button>
            </div>
          )}

          {/* KEY CONFIG MODAL OVERLAY */}
          {showKeyModal && (
            <div className="absolute inset-x-0 top-14 z-30 p-4 bg-white/95 backdrop-blur-sm border-b border-slate-200 shadow-lg space-y-3 animate-fadeIn">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-1.5 text-xs font-bold text-slate-900">
                  <Key className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Configure LLM API Key</span>
                </div>
                <button
                  onClick={() => setShowKeyModal(false)}
                  className="p-1 text-slate-400 hover:text-slate-600 rounded"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              <p className="text-[11px] text-slate-500 leading-relaxed">
                Insert your API key below or configure <code className="text-indigo-600 font-mono">GEMINI_API_KEY</code> / <code className="text-indigo-600 font-mono">OPENAI_API_KEY</code> in the backend <code className="text-slate-800 font-mono">.env</code> file.
              </p>

              <div className="space-y-2">
                <div className="flex items-center space-x-2 text-xs">
                  <span className="text-slate-500 text-[11px]">Provider:</span>
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    className="px-2 py-1 bg-slate-50 border border-slate-200 rounded text-xs text-slate-800"
                  >
                    <option value="gemini">Google Gemini (Official google-genai SDK)</option>
                    <option value="openai">OpenAI (gpt-4o-mini / gpt-4o)</option>
                  </select>
                </div>

                <input
                  type="password"
                  placeholder={provider === "gemini" ? "AIzaSy..." : "sk-proj-..."}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="w-full px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />

                <div className="flex items-center justify-between pt-1">
                  <span className="text-[10px] text-slate-400">
                    {serverKeyConfigured ? `✓ Backend .env (${serverProvider}) active` : "Key saved locally in browser"}
                  </span>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => {
                        setApiKey("");
                        localStorage.removeItem("alertbuster_llm_api_key");
                        setShowKeyModal(false);
                      }}
                      className="px-2.5 py-1 text-xs text-slate-500 hover:text-slate-700"
                    >
                      Clear
                    </button>
                    <button
                      onClick={handleSaveKey}
                      className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded text-xs font-semibold shadow-xs flex items-center space-x-1"
                    >
                      {keySaved ? <Check className="w-3 h-3" /> : null}
                      <span>{keySaved ? "Saved" : "Save Key"}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Messages Thread */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3 text-xs bg-slate-50/50">
            {messages.map((m) => {
              const isUser = m.role === "user";
              return (
                <div
                  key={m.id}
                  className={`flex flex-col ${isUser ? "items-end" : "items-start"} space-y-1`}
                >
                  <div
                    className={`max-w-[88%] p-3 rounded-2xl shadow-2xs ${
                      isUser
                        ? "bg-indigo-600 text-white rounded-br-xs"
                        : "bg-white border border-slate-200 text-slate-800 rounded-bl-xs"
                    }`}
                  >
                    {isUser ? (
                      <p className="whitespace-pre-wrap">{m.content}</p>
                    ) : (
                      renderMarkdown(m.content)
                    )}
                  </div>

                  <div className="flex items-center space-x-2 text-[10px] text-slate-400 px-1 font-mono">
                    <span>{m.timestamp}</span>
                    {m.provider && <span>• {m.provider}</span>}
                  </div>

                  {/* Suggestion Chips */}
                  {m.suggestedActions && m.suggestedActions.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1.5 max-w-[90%]">
                      {m.suggestedActions.map((sug, i) => (
                        <button
                          key={i}
                          onClick={() => handleSendMessage(sug)}
                          className="px-2.5 py-1 rounded-full bg-white border border-slate-200 hover:border-indigo-400 hover:bg-indigo-50 text-[11px] text-slate-700 transition shadow-2xs text-left"
                        >
                          {sug}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {loading && (
              <div className="flex items-center space-x-2 p-3 bg-white border border-slate-200 rounded-2xl max-w-[65%] text-xs text-slate-500 shadow-2xs">
                <div className="flex space-x-1 items-center">
                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-600 animate-bounce" />
                  <div
                    className="w-1.5 h-1.5 rounded-full bg-indigo-600 animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <div
                    className="w-1.5 h-1.5 rounded-full bg-indigo-600 animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
                <span className="font-mono text-[11px] text-slate-400">Analyzing live system state...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Questions Helper for Active Tab */}
          <div className="px-3 py-1.5 bg-white border-t border-slate-100 flex items-center space-x-1.5 overflow-x-auto no-scrollbar text-[11px]">
            <span className="text-[10px] uppercase font-bold text-slate-400 flex-shrink-0">
              Suggestions:
            </span>
            {getContextSuggestions().map((sug, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(sug)}
                className="px-2 py-0.5 rounded-md bg-slate-100 hover:bg-indigo-50 hover:text-indigo-600 text-slate-600 text-[10px] whitespace-nowrap transition flex-shrink-0"
              >
                {sug}
              </button>
            ))}
          </div>

          {/* Input Bar */}
          <div className="p-3 bg-white border-t border-slate-200">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center space-x-2"
            >
              <input
                type="text"
                placeholder={`Ask Zen anything about ${currentTab} or system state...`}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                className="flex-1 px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:bg-white"
              />
              <button
                type="submit"
                disabled={!inputMessage.trim() || loading}
                className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white transition shadow-xs flex-shrink-0"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
};
