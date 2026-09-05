import React, { useState } from "react";
import { Lock, Key, RefreshCw, Plus, Check, Power, AlertCircle } from "lucide-react";
import { rotateSourceSecret, toggleSourceStatus, createWebhookSource } from "../../services/api";

interface WebhookSourcesListProps {
  sources: any[];
  loading: boolean;
  onRefresh: () => void;
}

export const WebhookSourcesList: React.FC<WebhookSourcesListProps> = ({ sources, loading, onRefresh }) => {
  const [rotatingId, setRotatingId] = useState<string | null>(null);
  const [rotatedResult, setRotatedResult] = useState<any | null>(null);
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newSourceName, setNewSourceName] = useState<string>("");
  const [newSourceRPM, setNewSourceRPM] = useState<number>(1000);
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);

  const handleRotate = async (sourceId: string) => {
    if (!confirm(`Are you sure you want to rotate the secret for this source? The previous secret will remain active for 24 hours during transition.`)) return;
    setRotatingId(sourceId);
    try {
      const res = await rotateSourceSecret(sourceId, 24);
      setRotatedResult(res);
      onRefresh();
    } catch (e: any) {
      alert(`Rotation failed: ${e.message}`);
    } finally {
      setRotatingId(null);
    }
  };

  const handleToggle = async (sourceId: string) => {
    try {
      await toggleSourceStatus(sourceId);
      onRefresh();
    } catch (e: any) {
      alert(`Toggle failed: ${e.message}`);
    }
  };

  const handleCreateSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSourceName.trim()) return;
    try {
      const res = await createWebhookSource({
        source_name: newSourceName.trim(),
        rate_limit_per_minute: newSourceRPM,
      });
      setCreatedSecret(res.generated_secret);
      setNewSourceName("");
      onRefresh();
    } catch (e: any) {
      alert(`Registration failed: ${e.message}`);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
      <div className="p-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
        <div className="flex items-center space-x-2">
          <Key className="w-4 h-4 text-slate-700" />
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
            Registered Webhook Sources ({sources.length})
          </h3>
        </div>
        <button
          onClick={() => {
            setCreatedSecret(null);
            setShowAddModal(true);
          }}
          className="px-2.5 py-1 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 text-xs font-semibold flex items-center space-x-1"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Register Source</span>
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              <th className="py-2 px-3">Source Name</th>
              <th className="py-2 px-3">Status</th>
              <th className="py-2 px-3">Masked Secret</th>
              <th className="py-2 px-3">Rate Limit</th>
              <th className="py-2 px-3">Rotation State</th>
              <th className="py-2 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sources.map((src) => (
              <tr key={src.id} className="hover:bg-slate-50/70 transition-colors">
                <td className="py-2.5 px-3 font-semibold text-slate-800 font-mono">
                  {src.source_name}
                </td>
                <td className="py-2.5 px-3">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                      src.is_enabled
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {src.is_enabled ? "Active" : "Disabled"}
                  </span>
                </td>
                <td className="py-2.5 px-3 font-mono text-slate-500 text-[11px]">
                  {src.masked_secret || "••••••••••••"}
                </td>
                <td className="py-2.5 px-3 font-mono text-slate-700">
                  {src.rate_limit_per_minute} req/min
                </td>
                <td className="py-2.5 px-3">
                  {src.has_secondary_secret ? (
                    <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 text-[10px] font-semibold">
                      Transition Active
                    </span>
                  ) : (
                    <span className="text-[11px] text-slate-400">Single Secret</span>
                  )}
                </td>
                <td className="py-2.5 px-3 text-right">
                  <div className="flex items-center justify-end space-x-1.5">
                    <button
                      onClick={() => handleToggle(src.id)}
                      className="p-1 rounded bg-slate-100 text-slate-600 hover:text-slate-900"
                      title={src.is_enabled ? "Disable Source" : "Enable Source"}
                    >
                      <Power className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleRotate(src.id)}
                      disabled={rotatingId === src.id}
                      className="px-2 py-1 rounded bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 font-medium text-[11px] flex items-center space-x-1"
                      title="Rotate Secret (24h Grace)"
                    >
                      <RefreshCw className={`w-3 h-3 ${rotatingId === src.id ? "animate-spin text-indigo-600" : ""}`} />
                      <span>Rotate</span>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Secret Rotation Result Modal */}
      {rotatedResult && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full border border-slate-200 shadow-xl p-5 space-y-4">
            <div className="flex items-center space-x-2 text-emerald-600">
              <Key className="w-5 h-5" />
              <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Secret Rotated</h4>
            </div>
            <p className="text-xs text-slate-600">
              A new secret has been generated. The previous secret will continue working for 24 hours to ensure zero downtime during webhook sender migration.
            </p>
            <div className="p-3 bg-slate-900 rounded-lg text-emerald-400 font-mono text-xs break-all">
              {rotatedResult.rotation_details?.new_secret}
            </div>
            <p className="text-[11px] text-rose-600 font-semibold">
              Copy this secret now. It will never be shown again.
            </p>
            <div className="text-right">
              <button
                onClick={() => setRotatedResult(null)}
                className="px-3.5 py-1.5 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-700"
              >
                I Have Saved the Secret
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Register Source Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full border border-slate-200 shadow-xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <h4 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Register Alert Source</h4>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-slate-600 text-sm font-bold">✕</button>
            </div>

            {createdSecret ? (
              <div className="space-y-3">
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-xs font-medium">
                  Source registered successfully!
                </div>
                <div className="p-3 bg-slate-900 rounded-lg text-emerald-400 font-mono text-xs break-all">
                  {createdSecret}
                </div>
                <p className="text-[11px] text-rose-600 font-semibold">
                  Copy this secret now. It will never be displayed again.
                </p>
                <div className="text-right">
                  <button
                    onClick={() => {
                      setCreatedSecret(null);
                      setShowAddModal(false);
                    }}
                    className="px-3.5 py-1.5 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-700"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleCreateSource} className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Source Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. cloudwatch, newrelic, grafana"
                    value={newSourceName}
                    onChange={(e) => setNewSourceName(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Rate Limit (req/min)</label>
                  <input
                    type="number"
                    min="50"
                    max="10000"
                    value={newSourceRPM}
                    onChange={(e) => setNewSourceRPM(parseInt(e.target.value) || 1000)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
                <div className="flex justify-end space-x-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowAddModal(false)}
                    className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-xs font-medium hover:bg-slate-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-3.5 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700"
                  >
                    Generate Secret &amp; Save
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
