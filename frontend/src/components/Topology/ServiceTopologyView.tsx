import React, { useMemo, useState, useCallback, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  NodeProps,
  Edge,
  Node,
  MarkerType,
  useReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { TopologyData, ServiceNodeInfo, DependencyEdgeInfo } from "../../types";
import { calculateTopologyLayout, getCausalPathEdges } from "../../utils/graphLayout";
import {
  createService,
  updateService,
  deleteService,
  createDependency,
  deleteDependency,
} from "../../services/api";
import {
  AddServiceModal,
  EditServiceModal,
  AddDependencyModal,
  DeleteConfirmModal,
} from "../Services/ServiceModals";
import {
  Server,
  Database,
  Search,
  Plus,
  ArrowRight,
  GitBranch,
  Target,
  Layers,
  Edit2,
  Trash2,
  Maximize2,
  RotateCcw,
  LayoutGrid,
  Network,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  Info,
  ExternalLink,
  ChevronRight,
  Filter,
} from "lucide-react";

interface ServiceTopologyViewProps {
  topology: TopologyData;
  onRefreshTopology: () => void;
  initialViewMode?: "graph" | "catalog";
}

// Criticality Tier Formatter
export function getCriticalityTier(criticality: number): {
  label: string;
  badgeClass: string;
} {
  if (criticality >= 90) {
    return {
      label: "CRITICAL",
      badgeClass: "bg-rose-50 text-rose-700 border-rose-200",
    };
  }
  if (criticality >= 75) {
    return {
      label: "HIGH",
      badgeClass: "bg-orange-50 text-orange-700 border-orange-200",
    };
  }
  if (criticality >= 50) {
    return {
      label: "MEDIUM",
      badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
    };
  }
  return {
    label: "LOW",
    badgeClass: "bg-slate-50 text-slate-600 border-slate-200",
  };
}

// Custom Dynamic Service Node Component
const CustomServiceNode: React.FC<NodeProps> = ({ data, selected }) => {
  const info = (data || {}) as unknown as ServiceNodeInfo & {
    isHighlighted?: boolean;
    isDimmed?: boolean;
  };

  const isRootCause = info.status === "root_cause";
  const isImpacted = info.status === "impacted";
  const tier = getCriticalityTier(info.criticality);

  return (
    <div
      className={`px-4 py-3 rounded-xl border transition-all duration-200 min-w-[200px] bg-white shadow-xs ${
        isRootCause
          ? "border-rose-500 ring-2 ring-rose-200 bg-rose-50/40 shadow-rose-100"
          : isImpacted
          ? "border-amber-400 ring-2 ring-amber-100 bg-amber-50/30"
          : selected
          ? "border-indigo-500 ring-2 ring-indigo-100 shadow-md"
          : info.isHighlighted
          ? "border-indigo-400 ring-2 ring-indigo-50"
          : "border-slate-200 hover:border-slate-300 hover:shadow-sm"
      } ${info.isDimmed ? "opacity-35" : "opacity-100"}`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-slate-300 hover:!bg-indigo-500 !w-2.5 !h-2.5 !border-2 !border-white transition"
      />

      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center space-x-2.5 min-w-0">
          <div
            className={`p-2 rounded-lg flex-shrink-0 ${
              isRootCause
                ? "bg-rose-100 text-rose-700"
                : isImpacted
                ? "bg-amber-100 text-amber-700"
                : "bg-slate-100 text-slate-600"
            }`}
          >
            {info.id.includes("db") || info.id.includes("data") || info.id.includes("redis") ? (
              <Database className="w-4 h-4" />
            ) : (
              <Server className="w-4 h-4" />
            )}
          </div>

          <div className="min-w-0">
            <div className="text-xs font-bold text-slate-900 truncate" title={info.display_name}>
              {info.display_name}
            </div>
            <div className="text-[10px] text-slate-400 font-mono truncate">{info.id}</div>
          </div>
        </div>

        <span
          className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase flex-shrink-0 ${tier.badgeClass}`}
          title={`Criticality Score: ${info.criticality}/100`}
        >
          {tier.label}
        </span>
      </div>

      {/* Dynamic Status Badge */}
      <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between">
        <div className="flex items-center space-x-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              isRootCause
                ? "bg-rose-500 animate-pulse"
                : isImpacted
                ? "bg-amber-500"
                : "bg-emerald-500"
            }`}
          />
          <span
            className={`text-[10px] font-bold uppercase tracking-wider ${
              isRootCause
                ? "text-rose-700"
                : isImpacted
                ? "text-amber-700"
                : "text-emerald-700"
            }`}
          >
            {isRootCause
              ? "ROOT CAUSE"
              : isImpacted
              ? "DOWNSTREAM SYMPTOM"
              : "OPERATIONAL"}
          </span>
        </div>

        <span className="text-[10px] font-mono text-slate-400 font-semibold">
          {info.criticality}
        </span>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-slate-300 hover:!bg-indigo-500 !w-2.5 !h-2.5 !border-2 !border-white transition"
      />
    </div>
  );
};

const nodeTypes = {
  serviceNode: CustomServiceNode,
};

// Inner Graph Controller for layout & controls
const FlowGraphInner: React.FC<{
  nodes: Node[];
  edges: Edge[];
  onNodeClick: (_: any, node: Node) => void;
}> = ({ nodes, edges, onNodeClick }) => {
  const { fitView } = useReactFlow();

  useEffect(() => {
    const timer = setTimeout(() => {
      fitView({ padding: 0.2, duration: 400 });
    }, 50);
    return () => clearTimeout(timer);
  }, [nodes.length, fitView]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={onNodeClick}
      fitView
      className="bg-slate-50/60"
      minZoom={0.2}
      maxZoom={1.8}
    >
      <Background color="#cbd5e1" gap={18} size={1} />
      <Controls className="!bg-white !border-slate-200 !text-slate-600 !shadow-sm !rounded-lg" />
    </ReactFlow>
  );
};

export const ServiceTopologyView: React.FC<ServiceTopologyViewProps> = ({
  topology,
  onRefreshTopology,
  initialViewMode = "graph",
}) => {
  const [viewMode, setViewMode] = useState<"graph" | "catalog">(initialViewMode);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(null);

  // Modals state
  const [isAddServiceOpen, setIsAddServiceOpen] = useState(false);
  const [isEditServiceOpen, setIsEditServiceOpen] = useState(false);
  const [isAddDependencyOpen, setIsAddDependencyOpen] = useState(false);
  const [defaultParentForDep, setDefaultParentForDep] = useState<string | undefined>(undefined);
  const [deleteTarget, setDeleteTarget] = useState<{
    type: "service" | "dependency";
    serviceId?: string;
    parent?: string;
    child?: string;
    title: string;
    message: string;
  } | null>(null);

  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(
    null
  );

  const showFeedback = (type: "success" | "error", message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 4000);
  };

  // Find active root cause service
  const rootCauseSvc = topology.services.find((s) => s.status === "root_cause");
  const impactedSvcs = topology.services.filter((s) => s.status === "impacted");

  // Selected service info
  const selectedService = useMemo(() => {
    return topology.services.find((s) => s.id === selectedServiceId) || null;
  }, [topology.services, selectedServiceId]);

  // Upstream & Downstream dependencies for selected service
  const selectedUpstream = useMemo(() => {
    if (!selectedServiceId) return [];
    return topology.dependencies.filter((d) => d.child === selectedServiceId);
  }, [topology.dependencies, selectedServiceId]);

  const selectedDownstream = useMemo(() => {
    if (!selectedServiceId) return [];
    return topology.dependencies.filter((d) => d.parent === selectedServiceId);
  }, [topology.dependencies, selectedServiceId]);

  // Causal path edges from root cause
  const causalPathEdgeKeys = useMemo(() => {
    return getCausalPathEdges(rootCauseSvc?.id || null, topology.dependencies);
  }, [rootCauseSvc, topology.dependencies]);

  // Calculate dynamic node positions using the reusable layout engine
  const layoutPositions = useMemo(() => {
    return calculateTopologyLayout(topology.services, topology.dependencies, {
      nodeWidth: 220,
      nodeHeight: 110,
      layerSpacingY: 170,
      nodeSpacingX: 70,
      startX: 80,
      startY: 50,
    });
  }, [topology.services, topology.dependencies]);

  // Construct React Flow Nodes
  const nodes: Node[] = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return topology.services.map((svc) => {
      const isMatch = query
        ? svc.display_name.toLowerCase().includes(query) || svc.id.toLowerCase().includes(query)
        : true;
      const isDimmed = query ? !isMatch : false;
      const isHighlighted = query && isMatch;
      const isSelected = svc.id === selectedServiceId;

      const pos = layoutPositions[svc.id] || { x: 100, y: 100 };

      return {
        id: svc.id,
        type: "serviceNode",
        position: pos,
        selected: isSelected,
        data: {
          ...svc,
          isHighlighted,
          isDimmed,
        },
      };
    });
  }, [topology.services, layoutPositions, searchQuery, selectedServiceId]);

  // Construct React Flow Directed Edges with Causal Path Highlighting
  const edges: Edge[] = useMemo(() => {
    return topology.dependencies.map((dep, idx) => {
      const edgeKey = `${dep.parent}->${dep.child}`;
      const isCausalPath = causalPathEdgeKeys.has(edgeKey);
      const isSelectedLink =
        selectedServiceId && (dep.parent === selectedServiceId || dep.child === selectedServiceId);

      return {
        id: `e-${dep.parent}-${dep.child}-${idx}`,
        source: dep.parent,
        target: dep.child,
        animated: isCausalPath,
        style: {
          stroke: isCausalPath
            ? "#e11d48"
            : isSelectedLink
            ? "#6366f1"
            : "#94a3b8",
          strokeWidth: isCausalPath ? 2.5 : isSelectedLink ? 2 : 1.25,
          strokeDasharray: isCausalPath ? "4 2" : undefined,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isCausalPath ? "#e11d48" : isSelectedLink ? "#6366f1" : "#94a3b8",
        },
      };
    });
  }, [topology.dependencies, causalPathEdgeKeys, selectedServiceId]);

  // Node click handler
  const handleNodeClick = (_: any, node: Node) => {
    setSelectedServiceId(node.id);
  };

  // CRUD Handlers
  const handleCreateService = async (data: { id: string; display_name: string; criticality: number }) => {
    await createService(data);
    showFeedback("success", `Service '${data.display_name}' created successfully.`);
    onRefreshTopology();
    setSelectedServiceId(data.id);
  };

  const handleUpdateService = async (
    serviceId: string,
    data: { display_name?: string; criticality?: number }
  ) => {
    await updateService(serviceId, data);
    showFeedback("success", `Service '${serviceId}' updated successfully.`);
    onRefreshTopology();
  };

  const handleDeleteService = async (serviceId: string) => {
    await deleteService(serviceId);
    showFeedback("success", `Service '${serviceId}' deleted.`);
    if (selectedServiceId === serviceId) {
      setSelectedServiceId(null);
    }
    onRefreshTopology();
  };

  const handleCreateDependency = async (data: { parent: string; child: string }) => {
    await createDependency(data);
    showFeedback("success", `Dependency '${data.parent} → ${data.child}' created.`);
    onRefreshTopology();
  };

  const handleDeleteDependency = async (parent: string, child: string) => {
    await deleteDependency(parent, child);
    showFeedback("success", `Dependency '${parent} → ${child}' removed.`);
    onRefreshTopology();
  };

  return (
    <div className="space-y-4">
      {/* Toast Feedback Banner */}
      {feedback && (
        <div
          className={`p-3 rounded-xl text-xs font-semibold flex items-center justify-between shadow-sm animate-in fade-in ${
            feedback.type === "success"
              ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
              : "bg-rose-50 text-rose-800 border border-rose-200"
          }`}
        >
          <div className="flex items-center space-x-2">
            {feedback.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-600" />
            )}
            <span>{feedback.message}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="text-slate-400 hover:text-slate-600">
            ×
          </button>
        </div>
      )}

      {/* Incident & Causal Banner (Visible when root cause detected) */}
      {rootCauseSvc && (
        <div className="p-4 rounded-xl bg-white border border-rose-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start space-x-3">
            <div className="p-2.5 rounded-lg bg-rose-50 text-rose-600 border border-rose-100 flex-shrink-0">
              <Target className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-[11px] font-bold text-rose-700 uppercase tracking-wider">
                  Active Root Cause Incident
                </span>
                <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-800 text-[10px] font-bold">
                  Confidence: {rootCauseSvc.incident_info?.confidence || 94}%
                </span>
              </div>
              <h2 className="text-base font-bold text-slate-900 mt-0.5">
                {rootCauseSvc.display_name}{" "}
                <span className="text-xs font-mono font-normal text-slate-400">({rootCauseSvc.id})</span>
              </h2>
              {rootCauseSvc.incident_info?.reason && (
                <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">
                  {rootCauseSvc.incident_info.reason}
                </p>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-slate-500 font-medium">Downstream Blast Radius:</span>
            {impactedSvcs.length > 0 ? (
              impactedSvcs.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSelectedServiceId(s.id)}
                  className="px-2.5 py-1 rounded-lg bg-amber-50 text-amber-800 border border-amber-200 font-semibold text-[11px] hover:bg-amber-100 transition"
                >
                  {s.display_name}
                </button>
              ))
            ) : (
              <span className="text-slate-400 italic text-[11px]">No cascading symptoms</span>
            )}
          </div>
        </div>
      )}

      {/* Main Controls Bar */}
      <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Left: View Mode Toggle & Stats */}
        <div className="flex items-center space-x-2">
          <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs font-semibold">
            <button
              onClick={() => setViewMode("graph")}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md transition ${
                viewMode === "graph"
                  ? "bg-white text-indigo-700 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Network className="w-3.5 h-3.5" />
              <span>Topology Graph</span>
            </button>
            <button
              onClick={() => setViewMode("catalog")}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md transition ${
                viewMode === "catalog"
                  ? "bg-white text-indigo-700 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              <span>Service Catalog</span>
            </button>
          </div>

          <div className="hidden md:flex items-center space-x-2 text-xs text-slate-500 pl-2 border-l border-slate-200">
            <span>
              <strong className="text-slate-800">{topology.services.length}</strong> Services
            </span>
            <span>•</span>
            <span>
              <strong className="text-slate-800">{topology.dependencies.length}</strong> Dependency Links
            </span>
          </div>
        </div>

        {/* Right: Search & Action Buttons */}
        <div className="flex items-center space-x-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search / highlight..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-800 placeholder-slate-400 w-44 sm:w-56 shadow-2xs"
            />
          </div>

          <button
            onClick={onRefreshTopology}
            className="p-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition"
            title="Refresh Topology"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <button
            onClick={() => {
              setDefaultParentForDep(selectedServiceId || undefined);
              setIsAddDependencyOpen(true);
            }}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-2xs transition"
          >
            <ArrowRight className="w-3.5 h-3.5 text-indigo-600" />
            <span>Link</span>
          </button>

          <button
            onClick={() => setIsAddServiceOpen(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Service</span>
          </button>
        </div>
      </div>

      {/* GRAPH VIEW */}
      {viewMode === "graph" && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-[650px]">
          {/* React Flow Graph Area */}
          <div className="lg:col-span-3 bg-white border border-slate-200 rounded-xl relative overflow-hidden h-full shadow-xs">
            {/* Header overlay */}
            <div className="absolute top-3 left-3 z-10 space-y-0.5 bg-white/95 backdrop-blur-xs px-3 py-2 rounded-lg border border-slate-200 shadow-2xs">
              <h3 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                <GitBranch className="w-3.5 h-3.5 text-indigo-600" />
                <span>Multi-Hop Dependency Topology</span>
              </h3>
              <p className="text-[11px] text-slate-500">
                Directional graph ($Parent \to Child$) dynamically calculated by automatic layout
              </p>
            </div>

            {/* Legend */}
            <div className="absolute bottom-3 left-3 z-10 flex flex-wrap items-center gap-3 bg-white/95 backdrop-blur-xs px-3 py-1.5 rounded-lg border border-slate-200 text-[11px] shadow-2xs">
              <div className="flex items-center gap-1.5 text-rose-700 font-semibold">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" />
                <span>Root Cause</span>
              </div>
              <div className="flex items-center gap-1.5 text-amber-700 font-semibold">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <span>Downstream Symptom</span>
              </div>
              <div className="flex items-center gap-1.5 text-emerald-700 font-medium">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                <span>Operational</span>
              </div>
              {causalPathEdgeKeys.size > 0 && (
                <div className="flex items-center gap-1.5 text-rose-600 font-semibold border-l border-slate-200 pl-2">
                  <span className="w-4 h-0.5 bg-rose-500 border-t border-dashed border-rose-500" />
                  <span>Active Causal Flow</span>
                </div>
              )}
            </div>

            <ReactFlowProvider>
              <FlowGraphInner nodes={nodes} edges={edges} onNodeClick={handleNodeClick} />
            </ReactFlowProvider>
          </div>

          {/* Service Inspector Sidebar */}
          <div className="lg:col-span-1 bg-white border border-slate-200 rounded-xl p-4 flex flex-col justify-between h-full shadow-xs overflow-y-auto">
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Service Inspector
                </h4>
                {selectedService && (
                  <div className="flex items-center space-x-1">
                    <button
                      onClick={() => setIsEditServiceOpen(true)}
                      className="p-1 rounded text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition"
                      title="Edit Service"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() =>
                        setDeleteTarget({
                          type: "service",
                          serviceId: selectedService.id,
                          title: `Delete Service: ${selectedService.display_name}`,
                          message: `Are you sure you want to delete '${selectedService.id}'? Deleting this service will also remove its connected dependency edges.`,
                        })
                      }
                      className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition"
                      title="Delete Service"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>

              {selectedService ? (
                <div className="space-y-4 text-xs">
                  {/* Service ID & Name */}
                  <div>
                    <span className="text-[10px] font-semibold text-slate-400 uppercase">Service</span>
                    <div className="text-sm font-bold text-slate-900">{selectedService.display_name}</div>
                    <div className="text-xs font-mono text-indigo-600">{selectedService.id}</div>
                  </div>

                  {/* Criticality Tier */}
                  <div>
                    <span className="text-[10px] font-semibold text-slate-400 uppercase">Criticality</span>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-xs font-mono font-bold text-slate-800">
                        {selectedService.criticality} / 100
                      </span>
                      <span
                        className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                          getCriticalityTier(selectedService.criticality).badgeClass
                        }`}
                      >
                        {getCriticalityTier(selectedService.criticality).label}
                      </span>
                    </div>
                  </div>

                  {/* Status */}
                  <div>
                    <span className="text-[10px] font-semibold text-slate-400 uppercase">
                      Operational State
                    </span>
                    <div className="mt-1">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase ${
                          selectedService.status === "root_cause"
                            ? "bg-rose-50 text-rose-700 border border-rose-200"
                            : selectedService.status === "impacted"
                            ? "bg-amber-50 text-amber-700 border border-amber-200"
                            : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        }`}
                      >
                        {selectedService.status === "root_cause"
                          ? "ROOT CAUSE"
                          : selectedService.status === "impacted"
                          ? "DOWNSTREAM SYMPTOM"
                          : "OPERATIONAL"}
                      </span>
                    </div>
                  </div>

                  {/* Active Incident Detail if present */}
                  {selectedService.incident_info && (
                    <div className="p-3 rounded-xl bg-rose-50/70 border border-rose-200 space-y-1.5 text-xs">
                      <div className="flex items-center space-x-1.5 text-rose-700 font-bold text-[10px] uppercase">
                        <ShieldAlert className="w-3.5 h-3.5" />
                        <span>Correlated Incident</span>
                      </div>
                      <div className="font-bold text-slate-900">
                        {selectedService.incident_info.incident_id}
                      </div>
                      <p className="text-slate-600 text-[11px] leading-relaxed">
                        {selectedService.incident_info.reason}
                      </p>
                      <div className="text-rose-700 font-semibold text-[11px]">
                        Confidence: {selectedService.incident_info.confidence}%
                      </div>
                    </div>
                  )}

                  {/* Upstream Dependencies */}
                  <div>
                    <div className="flex items-center justify-between text-[10px] font-semibold text-slate-400 uppercase mb-1.5">
                      <span>Upstream Providers ({selectedUpstream.length})</span>
                    </div>
                    {selectedUpstream.length > 0 ? (
                      <div className="space-y-1.5">
                        {selectedUpstream.map((dep, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200 text-[11px]"
                          >
                            <span className="font-mono font-medium text-slate-700 truncate">
                              {dep.parent}
                            </span>
                            <button
                              onClick={() =>
                                setDeleteTarget({
                                  type: "dependency",
                                  parent: dep.parent,
                                  child: dep.child,
                                  title: `Remove Dependency Link`,
                                  message: `Are you sure you want to remove link '${dep.parent} → ${dep.child}'?`,
                                })
                              }
                              className="text-slate-400 hover:text-rose-600 p-0.5 rounded transition"
                              title="Delete Link"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-2 rounded-lg bg-slate-50/50 text-[11px] text-slate-400 italic">
                        Top-level service (no upstream dependencies)
                      </div>
                    )}
                  </div>

                  {/* Downstream Dependents */}
                  <div>
                    <div className="flex items-center justify-between text-[10px] font-semibold text-slate-400 uppercase mb-1.5">
                      <span>Downstream Dependents ({selectedDownstream.length})</span>
                      <button
                        onClick={() => {
                          setDefaultParentForDep(selectedService.id);
                          setIsAddDependencyOpen(true);
                        }}
                        className="text-indigo-600 hover:text-indigo-800 text-[10px] font-bold"
                      >
                        + Add Child
                      </button>
                    </div>
                    {selectedDownstream.length > 0 ? (
                      <div className="space-y-1.5">
                        {selectedDownstream.map((dep, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200 text-[11px]"
                          >
                            <span className="font-mono font-medium text-slate-700 truncate">
                              {dep.child}
                            </span>
                            <button
                              onClick={() =>
                                setDeleteTarget({
                                  type: "dependency",
                                  parent: dep.parent,
                                  child: dep.child,
                                  title: `Remove Dependency Link`,
                                  message: `Are you sure you want to remove link '${dep.parent} → ${dep.child}'?`,
                                })
                              }
                              className="text-slate-400 hover:text-rose-600 p-0.5 rounded transition"
                              title="Delete Link"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-2 rounded-lg bg-slate-50/50 text-[11px] text-slate-400 italic">
                        Leaf service (no downstream dependencies)
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="py-16 text-center text-xs text-slate-400 space-y-2">
                  <Network className="w-8 h-8 mx-auto text-slate-300" />
                  <p>Select any node in the topology graph to inspect its upstream & downstream links.</p>
                </div>
              )}
            </div>

            <div className="pt-4 border-t border-slate-100">
              <div className="p-3 rounded-lg bg-slate-50 text-[11px] text-slate-500 leading-relaxed">
                The multi-hop correlation engine traverses this runtime graph to pinpoint root causes and suppress downstream noise across arbitrary service depths.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CATALOG VIEW */}
      {viewMode === "catalog" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {topology.services
            .filter((svc) => {
              if (!searchQuery.trim()) return true;
              const q = searchQuery.toLowerCase();
              return svc.display_name.toLowerCase().includes(q) || svc.id.toLowerCase().includes(q);
            })
            .map((svc) => {
              const upstream = topology.dependencies.filter((d) => d.child === svc.id);
              const downstream = topology.dependencies.filter((d) => d.parent === svc.id);
              const isRoot = svc.status === "root_cause";
              const isImpacted = svc.status === "impacted";
              const tier = getCriticalityTier(svc.criticality);

              return (
                <div
                  key={svc.id}
                  className={`bg-white border rounded-xl p-5 space-y-4 shadow-xs transition duration-150 hover:shadow-sm ${
                    isRoot
                      ? "border-rose-400 ring-2 ring-rose-100"
                      : isImpacted
                      ? "border-amber-300"
                      : "border-slate-200"
                  }`}
                >
                  {/* Card Header */}
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      <div
                        className={`p-2.5 rounded-lg ${
                          isRoot
                            ? "bg-rose-50 text-rose-600"
                            : isImpacted
                            ? "bg-amber-50 text-amber-600"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {svc.id.includes("db") || svc.id.includes("data") || svc.id.includes("redis") ? (
                          <Database className="w-4 h-4" />
                        ) : (
                          <Server className="w-4 h-4" />
                        )}
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">{svc.display_name}</h3>
                        <span className="text-[11px] font-mono text-slate-400">{svc.id}</span>
                      </div>
                    </div>

                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase border ${
                        isRoot
                          ? "bg-rose-50 text-rose-700 border-rose-200"
                          : isImpacted
                          ? "bg-amber-50 text-amber-700 border-amber-200"
                          : "bg-emerald-50 text-emerald-700 border-emerald-200"
                      }`}
                    >
                      {isRoot ? "Root Cause" : isImpacted ? "Downstream" : "Operational"}
                    </span>
                  </div>

                  {/* Metrics Row */}
                  <div className="grid grid-cols-3 gap-2 py-2 border-y border-slate-100 text-center text-xs">
                    <div>
                      <span className="text-[10px] text-slate-400 font-medium block">Criticality</span>
                      <span className="font-mono font-bold text-slate-800">{svc.criticality}/100</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 font-medium block">Upstream</span>
                      <span className="font-mono font-bold text-slate-800">{upstream.length}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 font-medium block">Downstream</span>
                      <span className="font-mono font-bold text-slate-800">{downstream.length}</span>
                    </div>
                  </div>

                  {/* Dependents list */}
                  <div className="space-y-1.5 text-xs">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">
                      Downstream Dependents:
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {downstream.map((d, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-[10px] font-mono text-slate-700 font-medium"
                        >
                          {d.child}
                        </span>
                      ))}
                      {downstream.length === 0 && (
                        <span className="text-[10px] text-slate-400 italic">Leaf node</span>
                      )}
                    </div>
                  </div>

                  {/* Card Actions */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
                    <button
                      onClick={() => {
                        setSelectedServiceId(svc.id);
                        setViewMode("graph");
                      }}
                      className="text-indigo-600 hover:text-indigo-800 font-semibold flex items-center gap-1"
                    >
                      <span>Inspect in Graph</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>

                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => {
                          setSelectedServiceId(svc.id);
                          setIsEditServiceOpen(true);
                        }}
                        className="p-1 rounded text-slate-400 hover:text-indigo-600 hover:bg-slate-100 transition"
                        title="Edit Service"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() =>
                          setDeleteTarget({
                            type: "service",
                            serviceId: svc.id,
                            title: `Delete Service: ${svc.display_name}`,
                            message: `Are you sure you want to delete '${svc.id}'? Deleting this service will also remove its connected dependency edges.`,
                          })
                        }
                        className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-slate-100 transition"
                        title="Delete Service"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
        </div>
      )}

      {/* Modals */}
      <AddServiceModal
        isOpen={isAddServiceOpen}
        onClose={() => setIsAddServiceOpen(false)}
        onSubmit={handleCreateService}
      />

      <EditServiceModal
        isOpen={isEditServiceOpen}
        service={selectedService}
        onClose={() => setIsEditServiceOpen(false)}
        onSubmit={handleUpdateService}
      />

      <AddDependencyModal
        isOpen={isAddDependencyOpen}
        services={topology.services}
        defaultParent={defaultParentForDep}
        onClose={() => setIsAddDependencyOpen(false)}
        onSubmit={handleCreateDependency}
      />

      <DeleteConfirmModal
        isOpen={!!deleteTarget}
        title={deleteTarget?.title || "Confirm Deletion"}
        message={deleteTarget?.message || "Are you sure?"}
        onClose={() => setDeleteTarget(null)}
        onConfirm={async () => {
          if (!deleteTarget) return;
          if (deleteTarget.type === "service" && deleteTarget.serviceId) {
            await handleDeleteService(deleteTarget.serviceId);
          } else if (deleteTarget.type === "dependency" && deleteTarget.parent && deleteTarget.child) {
            await handleDeleteDependency(deleteTarget.parent, deleteTarget.child);
          }
        }}
      />
    </div>
  );
};
