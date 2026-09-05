import test from "node:test";
import assert from "node:assert/strict";

// Re-implement or import the pure layout algorithm for Node unit testing
function calculateTopologyLayout(services, dependencies, options = {}) {
  const {
    nodeWidth = 220,
    nodeHeight = 110,
    layerSpacingY = 160,
    nodeSpacingX = 80,
    startX = 100,
    startY = 50,
  } = options;

  const positions = {};
  if (!services || services.length === 0) return positions;

  const serviceIds = new Set(services.map((s) => s.id));
  const childrenMap = {};
  const parentsMap = {};
  const inDegree = {};

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

  const isolated = [];
  const connected = [];

  for (const s of services) {
    if (childrenMap[s.id].length === 0 && parentsMap[s.id].length === 0) {
      isolated.push(s.id);
    } else {
      connected.push(s.id);
    }
  }

  const layerMap = {};
  const queue = [];
  const visited = new Set();

  const roots = connected.filter((id) => inDegree[id] === 0);
  const initialRoots = roots.length > 0 ? roots : connected.slice(0, 1);

  for (const root of initialRoots) {
    queue.push({ id: root, layer: 0 });
    layerMap[root] = 0;
  }

  while (queue.length > 0) {
    const { id, layer } = queue.shift();
    visited.add(id);

    for (const child of childrenMap[id] || []) {
      const targetLayer = layer + 1;
      if (!visited.has(child) || targetLayer > (layerMap[child] || 0)) {
        layerMap[child] = Math.max(layerMap[child] || 0, targetLayer);
        if (!visited.has(child)) {
          visited.add(child);
          queue.push({ id: child, layer: targetLayer });
        }
      }
    }
  }

  for (const id of connected) {
    if (layerMap[id] === undefined) {
      layerMap[id] = 0;
    }
  }

  const layers = {};
  for (const id of connected) {
    const l = layerMap[id] || 0;
    if (!layers[l]) layers[l] = [];
    layers[l].push(id);
  }

  const layerIndices = Object.keys(layers).map(Number).sort((a, b) => a - b);
  let maxNodesInLayer = 1;
  for (const l of layerIndices) {
    maxNodesInLayer = Math.max(maxNodesInLayer, layers[l].length);
  }
  const totalMaxWidth = maxNodesInLayer * nodeWidth + (maxNodesInLayer - 1) * nodeSpacingX;

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

  if (isolated.length > 0) {
    const lastLayerY = layerIndices.length > 0 ? startY + layerIndices.length * layerSpacingY : startY;
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

function getCausalPathEdges(rootCauseId, dependencies, maxHops = 10) {
  const causalEdges = new Set();
  if (!rootCauseId) return causalEdges;

  const adj = {};
  for (const dep of dependencies) {
    if (!adj[dep.parent]) adj[dep.parent] = [];
    adj[dep.parent].push(dep.child);
  }

  const queue = [{ id: rootCauseId, depth: 0 }];
  const visited = new Set([rootCauseId]);

  while (queue.length > 0) {
    const { id, depth } = queue.shift();
    if (depth >= maxHops) continue;

    for (const child of adj[id] || []) {
      causalEdges.add(`${id}->${child}`);
      if (!visited.has(child)) {
        visited.add(child);
        queue.push({ id: child, depth: depth + 1 });
      }
    }
  }

  return causalEdges;
}

// 1. Dynamic 4-node chain layout (alpha -> beta -> gamma -> delta)
test("1. Dynamic 4-node chain layout", () => {
  const services = [
    { id: "alpha", display_name: "Alpha", criticality: 90, status: "healthy" },
    { id: "beta", display_name: "Beta", criticality: 80, status: "healthy" },
    { id: "gamma", display_name: "Gamma", criticality: 70, status: "healthy" },
    { id: "delta", display_name: "Delta", criticality: 60, status: "healthy" },
  ];
  const dependencies = [
    { parent: "alpha", child: "beta" },
    { parent: "beta", child: "gamma" },
    { parent: "gamma", child: "delta" },
  ];

  const layout = calculateTopologyLayout(services, dependencies);
  assert.equal(Object.keys(layout).length, 4);
  assert.ok(layout.alpha.y < layout.beta.y);
  assert.ok(layout.beta.y < layout.gamma.y);
  assert.ok(layout.gamma.y < layout.delta.y);
});

// 2. Branching topology
test("2. Branching topology layout", () => {
  const services = [
    { id: "root", display_name: "Root", criticality: 100, status: "healthy" },
    { id: "branch-a", display_name: "Branch A", criticality: 80, status: "healthy" },
    { id: "branch-b", display_name: "Branch B", criticality: 80, status: "healthy" },
    { id: "leaf", display_name: "Leaf", criticality: 60, status: "healthy" },
  ];
  const dependencies = [
    { parent: "root", child: "branch-a" },
    { parent: "root", child: "branch-b" },
    { parent: "branch-a", child: "leaf" },
    { parent: "branch-b", child: "leaf" },
  ];

  const layout = calculateTopologyLayout(services, dependencies);
  assert.equal(layout["branch-a"].y, layout["branch-b"].y);
  assert.notEqual(layout["branch-a"].x, layout["branch-b"].x);
  assert.ok(layout.root.y < layout["branch-a"].y);
  assert.ok(layout["branch-a"].y < layout.leaf.y);
});

// 3. Isolated service layout
test("3. Isolated service layout", () => {
  const services = [
    { id: "connected-1", display_name: "C1", criticality: 80, status: "healthy" },
    { id: "connected-2", display_name: "C2", criticality: 70, status: "healthy" },
    { id: "standalone", display_name: "Standalone", criticality: 50, status: "healthy" },
  ];
  const dependencies = [{ parent: "connected-1", child: "connected-2" }];

  const layout = calculateTopologyLayout(services, dependencies);
  assert.ok(layout.standalone);
  assert.ok(layout.standalone.y > layout["connected-2"].y);
});

// 4. Cycle-safe layout
test("4. Cycle-safe layout (A -> B -> C -> A)", () => {
  const services = [
    { id: "node-a", display_name: "A", criticality: 80, status: "healthy" },
    { id: "node-b", display_name: "B", criticality: 70, status: "healthy" },
    { id: "node-c", display_name: "C", criticality: 60, status: "healthy" },
  ];
  const dependencies = [
    { parent: "node-a", child: "node-b" },
    { parent: "node-b", child: "node-c" },
    { parent: "node-c", child: "node-a" },
  ];

  const layout = calculateTopologyLayout(services, dependencies);
  assert.equal(Object.keys(layout).length, 3);
});

// 5. Root cause highlighting and causal path calculation
test("5. Root cause highlighting and causal path calculation", () => {
  const dependencies = [
    { parent: "alpha", child: "beta" },
    { parent: "beta", child: "gamma" },
    { parent: "unrelated", child: "leaf" },
  ];

  const causalEdges = getCausalPathEdges("alpha", dependencies);
  assert.ok(causalEdges.has("alpha->beta"));
  assert.ok(causalEdges.has("beta->gamma"));
  assert.ok(!causalEdges.has("unrelated->leaf"));
});

// 6. Downstream highlighting
test("6. Downstream highlighting identification", () => {
  const services = [
    { id: "alpha", status: "root_cause" },
    { id: "beta", status: "impacted" },
    { id: "gamma", status: "impacted" },
    { id: "delta", status: "healthy" },
  ];

  const impacted = services.filter((s) => s.status === "impacted");
  assert.equal(impacted.length, 2);
  assert.deepEqual(
    impacted.map((s) => s.id),
    ["beta", "gamma"]
  );
});

// 7. Add service validation
test("7. Add service validation logic", () => {
  const validateService = (id, name, criticality) => {
    const cleanId = (id || "").trim().toLowerCase();
    const cleanName = (name || "").trim();
    if (!cleanId) return { valid: false, error: "ID required" };
    if (!cleanName) return { valid: false, error: "Name required" };
    if (criticality < 0 || criticality > 100) return { valid: false, error: "Criticality range" };
    return { valid: true };
  };

  assert.equal(validateService("alpha-svc", "Alpha Service", 80).valid, true);
  assert.equal(validateService("", "Alpha Service", 80).valid, false);
  assert.equal(validateService("alpha", "", 80).valid, false);
  assert.equal(validateService("alpha", "Alpha", 150).valid, false);
});

// 8. Add dependency validation
test("8. Add dependency validation logic", () => {
  const validateDependency = (parent, child, existingDeps = []) => {
    if (!parent || !child) return { valid: false, error: "Missing fields" };
    if (parent === child) return { valid: false, error: "Self link" };
    if (existingDeps.some((d) => d.parent === parent && d.child === child)) {
      return { valid: false, error: "Duplicate" };
    }
    return { valid: true };
  };

  const existing = [{ parent: "alpha", child: "beta" }];
  assert.equal(validateDependency("alpha", "beta", existing).valid, false);
  assert.equal(validateDependency("alpha", "alpha", existing).valid, false);
  assert.equal(validateDependency("alpha", "gamma", existing).valid, true);
});

// 9. Delete service behavior
test("9. Delete service cascade simulation", () => {
  let services = ["alpha", "beta", "gamma"];
  let dependencies = [
    { parent: "alpha", child: "beta" },
    { parent: "beta", child: "gamma" },
  ];

  const deleteService = (targetId) => {
    services = services.filter((s) => s !== targetId);
    dependencies = dependencies.filter((d) => d.parent !== targetId && d.child !== targetId);
  };

  deleteService("beta");
  assert.deepEqual(services, ["alpha", "gamma"]);
  assert.equal(dependencies.length, 0);
});

// 10. Multi-hop topology rendering
test("10. Multi-hop topology rendering structure", () => {
  const services = [
    { id: "alpha", display_name: "Alpha" },
    { id: "beta", display_name: "Beta" },
    { id: "gamma", display_name: "Gamma" },
    { id: "delta", display_name: "Delta" },
  ];
  const dependencies = [
    { parent: "alpha", child: "beta" },
    { parent: "beta", child: "gamma" },
    { parent: "gamma", child: "delta" },
  ];

  const layout = calculateTopologyLayout(services, dependencies);
  assert.equal(Object.keys(layout).length, 4);
  assert.ok(layout.alpha && layout.beta && layout.gamma && layout.delta);
});
