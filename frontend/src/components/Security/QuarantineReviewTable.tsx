import React, { useState } from "react";
import { ShieldAlert, CheckCircle, XCircle, AlertTriangle, Eye, RefreshCw, Filter } from "lucide-react";
import { approveQuarantinedAlert, rejectQuarantinedAlert } from "../../services/api";

interface QuarantineReviewTableProps {
  alerts: any[];
  loading: boolean;
  onActionComplete: () => void;
}

export const QuarantineReviewTable: React.FC<QuarantineReviewTableProps> = ({
  alerts,
  loading,
  onActionComplete,
}) => {
  const [filterCritical, setFilterCritical] = useState<boolean>(false);
  const [selectedPayload, setSelectedPayload] = useState<any | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);

  const displayedAlerts = filterCritical
    ? alerts.filter((a) => String(a.severity).toLowerCase() === "critical")
    : alerts;

  const handleApprove = async (id: number) => {
    setActionLoadingId(id);
    try {
      await approveQuarantinedAlert(id);
      onActionComplete();
    } catch (e: any) {
      alert(`Approval error: ${e.message}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleReject = async (id: number) => {
    const reason = prompt("Enter reason for rejection:", "Rejected by SRE after security inspection");
    if (!reason) return;
    setActionLoadingId(id);
    try {
      await rejectQuarantinedAlert(id, reason);
      onActionComplete();
    } catch (e: any) {
      alert(`Rejection error: ${e.message}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
      {/* Header */}
      <div className="p-3.5 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2 bg-slate-50/70">
        <div className="flex items-center space-x-2">
          <ShieldAlert className="w-4 h-4 text-amber-600" />
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
            Quarantine Review &amp; Triage ({alerts.length})
          </h3>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setFilterCritical(!filterCritical)}
            className={`px-2.5 py-1 rounded text-xs font-semibold flex items-center space-x-1.5 transition-colors ${
              filterCritical
                ? "bg-rose-100 text-rose-800 border border-rose-200"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            <Filter className="w-3 h-3" />
            <span>Critical Alerts Only</span>
          </button>
        </div>
      </div>

      {/* Table */}
      {displayedAlerts.length === 0 ? (
        <div className="p-8 text-center text-slate-400 text-xs">
          <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-2 opacity-80" />
          <p className="font-semibold text-slate-700">No alerts currently quarantined</p>
          <p className="mt-0.5 text-slate-400">All incoming alerts have satisfied security verification or been resolved.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                <th className="py-2.5 px-3">Alert</th>
                <th className="py-2.5 px-3">Service</th>
                <th className="py-2.5 px-3">Severity</th>
                <th className="py-2.5 px-3">Trust Score</th>
                <th className="py-2.5 px-3">Quarantine Reason</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {displayedAlerts.map((a) => {
                const isCrit = String(a.severity).toLowerCase() === "critical";
                const isOperating = actionLoadingId === a.id;

                return (
                  <tr
                    key={a.id}
                    className={`hover:bg-slate-50/80 transition-colors ${
                      isCrit ? "bg-rose-50/30" : ""
                    }`}
                  >
                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-slate-800">{a.alert_name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">
                        Src: {a.source} • ID #{a.id}
                      </div>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[11px]">
                        {a.service}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          isCrit
                            ? "bg-rose-100 text-rose-800 border border-rose-200"
                            : "bg-amber-100 text-amber-800"
                        }`}
                      >
                        {a.severity}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono font-bold">
                      <span
                        className={
                          (a.trust_score || 0) >= 70
                            ? "text-emerald-600"
                            : (a.trust_score || 0) >= 40
                            ? "text-amber-600"
                            : "text-red-600"
                        }
                      >
                        {Math.round(a.trust_score || 0)}/100
                      </span>
                    </td>
                    <td className="py-2.5 px-3 max-w-xs truncate text-slate-600 text-[11px]" title={a.quarantine_reason || a.suppression_reason}>
                      {a.quarantine_reason || a.suppression_reason || "Low Trust Score"}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="flex items-center justify-end space-x-1.5">
                        <button
                          onClick={() => setSelectedPayload(a.raw_payload || a)}
                          className="p-1 rounded bg-slate-100 text-slate-600 hover:text-slate-900 hover:bg-slate-200"
                          title="View Payload"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleApprove(a.id)}
                          disabled={isOperating}
                          className="px-2 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 font-semibold text-[11px] flex items-center space-x-1"
                          title="Approve and route through alert pipeline"
                        >
                          <CheckCircle className="w-3 h-3" />
                          <span>Approve</span>
                        </button>
                        <button
                          onClick={() => handleReject(a.id)}
                          disabled={isOperating}
                          className="px-2 py-1 rounded bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 font-semibold text-[11px] flex items-center space-x-1"
                          title="Reject and purge alert"
                        >
                          <XCircle className="w-3 h-3" />
                          <span>Reject</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Payload Modal */}
      {selectedPayload && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-xl w-full border border-slate-200 shadow-xl overflow-hidden">
            <div className="p-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Raw Quarantined Payload
              </h4>
              <button
                onClick={() => setSelectedPayload(null)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>
            <div className="p-4 max-h-96 overflow-y-auto bg-slate-900 text-emerald-400 font-mono text-xs rounded-b-xl">
              <pre>{JSON.stringify(selectedPayload, null, 2)}</pre>
            </div>
            <div className="p-3 bg-slate-50 border-t border-slate-200 text-right">
              <button
                onClick={() => setSelectedPayload(null)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 text-white font-medium text-xs hover:bg-slate-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
