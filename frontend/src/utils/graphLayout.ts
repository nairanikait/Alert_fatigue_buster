import { ServiceNodeInfo, DependencyEdgeInfo } from "../types";

export interface NodePosition {
  x: number;
  y: number;
}

export interface GraphLayoutOptions {
  nodeWidth?: number;
  nodeHeight?: number;
  layerSpacingY?: number;
  nodeSpacingX?: number;
  startX?: number;
  startY?: number;
}

/**
 * Computes deterministic, hierarchical coordinates for arbitrary directed graphs.
 * Features:
 * - Identifies root nodes (in-degree = 0)
 * - Assigns topological layers via BFS with cycle prevention
 * - Horizontally centers layers to avoid overlapping
 * - Places isolated nodes cleanly in their own row/cluster
 * - Handles arbitrary cycles safely (never loops infinitely)
 */
export function calculateTopologyLayout(
  services: ServiceNodeInfo[],
  dependencies: DependencyEdgeInfo[],
  options: GraphLayoutOptions = {}
): Record<string, NodePosition> {
  const {
    nodeWidth = 220,
    nodeHeight = 110,
    layerSpacingY = 160,
    nodeSpacingX = 80,
    startX = 100,
    startY = 50,
  } = options;

  const positions: Record<string, NodePosition> = {};
  if (!services || services.length === 0) {
    return positions;
  }

  const serviceIds = new Set(services.map((s) => s.id));

  // Build adjacency lists and compute in-degrees
  const childrenMap: Record<string, string[]> = {};
  const parentsMap: Record<string, string[]> = {};
  const inDegree: Record<string, number> = {};

  for (const s of services) {
    childrenMap[s.id] = [];
    parentsMap[s.id] = [];
    inDegree[s.id] = 0;
  }

  for (const dep of dependencies) {
    if (serviceIds.has(dep.parent) && serviceIds.has(dep.child)) {
      childrenMap[dep.parent].push(dep.child);
      parentsMap[dep.child].push(dep.parent);
      inDegree[dep.child] = (inDegree[dep.child] || 0) + 1;
    }
  }

  // Identify connected vs isolated services
  const isolated: string[] = [];
  const connected: string[] = [];

  for (const s of services) {
    if (childrenMap[s.id].length === 0 && parentsMap[s.id].length === 0) {
      isolated.push(s.id);
    } else {
      connected.push(s.id);
    }
  }

  // Assign layers using BFS from root nodes (inDegree === 0)
  const layerMap: Record<string, number> = {};
  const queue: Array<{ id: string; layer: number }> = [];
  const visited = new Set<string>();

  // Roots among connected services
  const roots = connected.filter((id) => inDegree[id] === 0);
  // If graph is a pure cycle and has no root with inDegree 0, pick first connected service
  const initialRoots = roots.length > 0 ? roots : connected.slice(0, 1);

  for (const root of initialRoots) {
    queue.push({ id: root, layer: 0 });
    layerMap[root] = 0;
  }

  while (queue.length > 0) {
    const { id, layer } = queue.shift()!;
    visited.add(id);

    for (const child of childrenMap[id] || []) {
      const targetLayer = layer + 1;
      if (!visited.has(child) || targetLayer > (layerMap[child] || 0)) {
        layerMap[child] = Math.max(layerMap[child] || 0, targetLayer);
        // Only re-queue if not in a cycle or path is strictly bounded
        if (!visited.has(child)) {
          visited.add(child);
          queue.push({ id: child, layer: targetLayer });
        }
      }
    }
  }

  // Handle any disconnected components in connected list
  for (const id of connected) {
    if (layerMap[id] === undefined) {
      layerMap[id] = 0;
    }
  }

  // Group services by layer
  const layers: Record<number, string[]> = {};
  for (const id of connected) {
    const l = layerMap[id] || 0;
    if (!layers[l]) layers[l] = [];
    layers[l].push(id);
  }

  const layerIndices = Object.keys(layers)
    .map(Number)
    .sort((a, b) => a - b);

  // Calculate max width across layers to center everything
  let maxNodesInLayer = 1;
  for (const l of layerIndices) {
    maxNodesInLayer = Math.max(maxNodesInLayer, layers[l].length);
  }
  const totalMaxWidth = maxNodesInLayer * nodeWidth + (maxNodesInLayer - 1) * nodeSpacingX;

  // Position connected nodes layer by layer
  for (const l of layerIndices) {
    const nodesInLayer = layers[l];
    const layerWidth = nodesInLayer.length * nodeWidth + (nodesInLayer.length - 1) * nodeSpacingX;
    const layerOffsetX = startX + (totalMaxWidth - layerWidth) / 2;
    const yPos = startY + l * layerSpacingY;

    nodesInLayer.forEach((id, idx) => {
      const xPos = layerOffsetX + idx * (nodeWidth + nodeSpacingX);
      positions[id] = { x: Math.round(xPos), y: Math.round(yPos) };
    });
  }

  // Position isolated nodes in a neat row at the bottom or side
  if (isolated.length > 0) {
    const lastLayerY = layerIndices.length > 0 ? startY + (layerIndices.length) * layerSpacingY : startY;
    const isolatedWidth = isolated.length * nodeWidth + (isolated.length - 1) * nodeSpacingX;
    const isolatedOffsetX = startX + Math.max(0, (totalMaxWidth - isolatedWidth) / 2);

    isolated.forEach((id, idx) => {
      positions[id] = {
        x: Math.round(isolatedOffsetX + idx * (nodeWidth + nodeSpacingX)),
        y: Math.round(lastLayerY + 20),
      };
    });
  }

  return positions;
}

/**
 * Finds all downstream dependency edges that are part of the active causal path from root cause.
 */
export function getCausalPathEdges(
  rootCauseId: string | null,
  dependencies: DependencyEdgeInfo[],
  maxHops: number = 10
): Set<string> {
  const causalEdges = new Set<string>();
  if (!rootCauseId) return causalEdges;

  const adj: Record<string, string[]> = {};
  for (const dep of dependencies) {
    if (!adj[dep.parent]) adj[dep.parent] = [];
    adj[dep.parent].push(dep.child);
  }

  const queue: Array<{ id: string; depth: number }> = [{ id: rootCauseId, depth: 0 }];
  const visited = new Set<string>([rootCauseId]);

  while (queue.length > 0) {
    const { id, depth } = queue.shift()!;
    if (depth >= maxHops) continue;

    for (const child of adj[id] || []) {
      const edgeKey = `${id}->${child}`;
      causalEdges.add(edgeKey);

      if (!visited.has(child)) {
        visited.add(child);
        queue.push({ id: child, depth: depth + 1 });
      }
    }
  }

  return causalEdges;
}
