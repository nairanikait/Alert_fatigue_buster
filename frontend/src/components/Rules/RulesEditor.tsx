import React, { useState, useEffect } from "react";
import {
  SlidersHorizontal,
  Save,
  RotateCcw,
  CheckCircle2,
  RefreshCw,
  Clock,
  Layers,
  ShieldAlert,
  Radio,
  HelpCircle,
} from "lucide-react";
import { fetchConfig, updateConfig } from "../../services/api";

export const RulesEditor: React.FC = () => {
  const [rules, setRules] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    loadRulesData();
  }, []);

  const loadRulesData = async () => {
    try {
      setLoading(true);
      const data = await fetchConfig();
      setRules(data);
    } catch (err: any) {
      console.error("Failed to load rules:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await updateConfig(rules);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      alert("Failed to save rules: " + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleResetDefaults = () => {
    setRules({
      deduplication: { window_seconds: 30 },
      batching: { window_seconds: 10, max_batch_size: 25 },
      cooldown: {
        critical_minutes: 1,
        high_minutes: 5,
        medium_minutes: 15,
        low_minutes: 30,
      },
      flaky_detection: {
        flapping_threshold: 4,
        window_minutes: 10,
        quarantine_minutes: 15,
      },
      routing: {
        critical_channel: "pagerduty",
        high_channel: "slack",
        medium_channel: "slack",
        low_channel: "email",
      },
    });
  };

  if (loading || !rules) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-xs text-slate-500 font-mono">
        Loading configuration policies...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <SlidersHorizontal className="w-5 h-5 text-indigo-600" />
            <span>Rules & Policies</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleResetDefaults}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium text-xs shadow-xs transition"
          >
            <RotateCcw className="w-3.5 h-3.5 text-slate-500" />
            <span>Reset to Defaults</span>
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-xs shadow-xs transition disabled:opacity-50"
          >
            {saving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            <span>{saving ? "Saving..." : "Save Changes"}</span>
          </button>
        </div>
      </div>

      {savedSuccess && (
        <div className="p-3.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>Policies successfully persisted to declarative rules storage.</span>
        </div>
      )}

      {/* Grid of Rule Sections */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Deduplication & Sliding Window */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Clock className="w-4 h-4 text-indigo-600" />
              <span>Deduplication</span>
            </h3>
            <span className="text-[10px] uppercase font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
              Active
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <label className="block text-slate-700 font-medium mb-1">
                Deduplication Window (seconds)
              </label>
              <input
                type="number"
                value={rules.deduplication?.window_seconds || 30}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    deduplication: {
                      ...rules.deduplication,
                      window_seconds: parseInt(e.target.value) || 30,
                    },
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 font-mono text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              />
              <p className="text-[11px] text-slate-400 mt-1">
              </p>
            </div>
          </div>
        </div>

        {/* Batching Interval */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Layers className="w-4 h-4 text-purple-600" />
              <span>Batching & Digests</span>
            </h3>
            <span className="text-[10px] uppercase font-semibold text-purple-600 bg-purple-50 px-2 py-0.5 rounded">
              Active
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block text-slate-700 font-medium mb-1">
                Batch Window (seconds)
              </label>
              <input
                type="number"
                value={rules.batching?.window_seconds || 10}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    batching: {
                      ...rules.batching,
                      window_seconds: parseInt(e.target.value) || 10,
                    },
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 font-mono text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-slate-700 font-medium mb-1">
                Max Batch Size
              </label>
              <input
                type="number"
                value={rules.batching?.max_batch_size || 25}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    batching: {
                      ...rules.batching,
                      max_batch_size: parseInt(e.target.value) || 25,
                    },
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 font-mono text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              />
            </div>
          </div>
          <p className="text-[11px] text-slate-400">
          </p>
        </div>

        {/* Adaptive Cooldown */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-600" />
              <span>Cooldown Throttling</span>
            </h3>
            <span className="text-[10px] uppercase font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded">
              By Severity
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block text-slate-700 font-medium mb-1">Critical Cooldown (min)</label>
              <input
                type="number"
                value={rules.cooldown?.critical_minutes || 1}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    cooldown: {
                      ...rules.cooldown,
                      critical_minutes: parseInt(e.target.value) || 1,
                    },
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 font-mono text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-slate-700 font-medium mb-1">High Cooldown (min)</label>
              <input
                type="number"
                value={rules.cooldown?.high_minutes || 5}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    cooldown: {
                      ...rules.cooldown,
                      high_minutes: parseInt(e.target.value) || 5,
                    },
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 font-mono text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-slate-700 font-medium mb-1">Medium Cooldown (min)</label>
              <input
                type="number"
                value={rules.cooldown?.medium_minutes || 15}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    cooldown: {
                      ...rules.cooldown,
                      medium_minutes: parseInt(e.target.value) || 15,
                    },
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 font-mono text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-slate-700 font-medium mb-1">Low Cooldown (min)</label>
              <input
                type="number"
                value={rules.cooldown?.low_minutes || 30}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    cooldown: {
                      ...rules.cooldown,
                      low_minutes: parseInt(e.target.value) || 30,
                    },
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 font-mono text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Notification Routing Matrix */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-xs">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Radio className="w-4 h-4 text-emerald-600" />
              <span>Smart Routing Matrix</span>
            </h3>
            <span className="text-[10px] uppercase font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">
              Channel Map
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block text-slate-700 font-medium mb-1">Critical Tier</label>
              <select
                value={rules.routing?.critical_channel || "pagerduty"}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    routing: { ...rules.routing, critical_channel: e.target.value },
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              >
                <option value="pagerduty">PagerDuty (Direct Page)</option>
                <option value="slack">Slack (#incident-war-room)</option>
                <option value="email">Email</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-700 font-medium mb-1">High Tier</label>
              <select
                value={rules.routing?.high_channel || "slack"}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    routing: { ...rules.routing, high_channel: e.target.value },
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              >
                <option value="pagerduty">PagerDuty</option>
                <option value="slack">Slack (#eng-alerts)</option>
                <option value="email">Email</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-700 font-medium mb-1">Medium Tier</label>
              <select
                value={rules.routing?.medium_channel || "slack"}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    routing: { ...rules.routing, medium_channel: e.target.value },
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              >
                <option value="slack">Slack (#eng-notifications)</option>
                <option value="email">Email</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-700 font-medium mb-1">Low Tier</label>
              <select
                value={rules.routing?.low_channel || "email"}
                onChange={(e) =>
                  setRules({
                    ...rules,
                    routing: { ...rules.routing, low_channel: e.target.value },
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-slate-900 text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-none"
              >
                <option value="email">Email Digest</option>
                <option value="slack">Slack (#low-priority)</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
