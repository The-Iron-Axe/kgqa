const TYPE_COLORS = {
  Technology: "#818cf8",
  Model: "#c084fc",
  Product: "#34d399",
  Organization: "#fbbf24",
  Person: "#f472b6",
  Application: "#22d3ee",
  Algorithm: "#6366f1",
  Hardware: "#f87171",
  Policy: "#a3e635",
  Infrastructure: "#94a3b8",
};

const HIGHLIGHT = {
  focus: { border: "#e11d48", glow: "rgba(225, 29, 72, 0.65)", fill: "#fff5f7" },
  keyword: { border: "#f59e0b", glow: "rgba(245, 158, 11, 0.7)", fill: "#fffbeb" },
  related: { border: "#10b981", glow: "rgba(16, 185, 129, 0.65)", fill: "#ecfdf5" },
};

let network = null;
window.network = null;
let graphNodes = null;
let graphEdges = null;
let nodeNameById = new Map();
let allEntities = [];
let entityNameSet = new Set();
let graphFocusEntity = null;
let graphQuestionKeywords = [];
let graphRelatedNames = [];
let graphViewMode = "full";
let egoCenterEntity = null;
let graphResizeObserver = null;
let graphFitTimer = null;
let graphResizeTimer = null;
let graphPhysicsKeeper = null;
let graphPhysicsNudgeTimer = null;
let highlightPulseTimer = null;
let highlightPulsePhase = 0;
let entityTableHighlight = { keywords: [], focus: null, related: [] };
let pendingGraphFromAnswer = null;
let graphLoadToken = 0;
let viewportRefreshGen = 0;
let graphRenderLimit = 200;
let lastCypherResult = null;

function getGraphRenderLimit() {
  const el = document.getElementById("graphRenderLimit");
  const value = Number.parseInt(el?.value || String(graphRenderLimit), 10);
  if (!Number.isFinite(value)) return graphRenderLimit;
  graphRenderLimit = Math.max(40, Math.min(500, value));
  return graphRenderLimit;
}

function getGraphTheme() {
  const t = window.ThemeSwitcher?.getCurrent?.();
  return (
    t?.graph || {
      nodeFont: "#1a1a28",
      edgeFont: "#1a1a28",
      nodeBorder: "rgba(0,0,0,0.12)",
      nodeHighlightBorder: "#6366f1",
      edgeColor: "rgba(99,102,241,0.45)",
      edgeHighlight: "#6366f1",
      edgeFocus: "rgba(225, 29, 72, 0.75)",
    }
  );
}

function graphFontFace() {
  return getComputedStyle(document.documentElement)
    .getPropertyValue("--font-body")
    .trim()
    .replace(/"/g, "")
    .split(",")[0]
    .trim();
}

function waitForLayout() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => setTimeout(resolve, 400));
    });
  });
}

let graphViewportRetryTimer = null;

function isGraphViewVisible() {
  const panel = document.getElementById("view-graph");
  return Boolean(panel && !panel.hidden && panel.classList.contains("app-view--active"));
}

function getGraphContainerSize() {
  const container = document.getElementById("graphContainer");
  if (!container) return { width: 0, height: 0 };
  return {
    width: container.clientWidth || container.offsetWidth,
    height: container.clientHeight || container.offsetHeight,
  };
}

/** 修正 vis-network 在容器尺寸为 0 时初始化导致的空白画布 */
function refreshGraphViewport({ fit = true } = {}) {
  const container = document.getElementById("graphContainer");
  if (!network || !container) return false;

  const { width, height } = getGraphContainerSize();
  if (width < 8 || height < 8) return false;

  try {
    network.setSize(`${width}px`, `${height}px`);
    network.redraw();
    if (graphViewMode === "ego" && egoCenterEntity && graphNodes) {
      const nodeList = graphNodes.get().map((n) => ({
        id: n.id,
        name: n.name || nodeNameById.get(n.id) || "",
      }));
      applyEgoRadialLayout(egoCenterEntity, nodeList);
    } else if (fit) {
      scheduleGraphFitOnce(60);
    }
    return true;
  } catch (err) {
    console.warn("图谱视口刷新失败", err);
    return false;
  }
}

function scheduleGraphViewportRefresh(maxAttempts = 3) {
  const gen = ++viewportRefreshGen;
  clearTimeout(graphViewportRetryTimer);
  let attempts = 0;
  const tryRefresh = () => {
    if (gen !== viewportRefreshGen) return;
    attempts += 1;
    if (refreshGraphViewport()) return;
    if (attempts < maxAttempts) {
      graphViewportRetryTimer = setTimeout(tryRefresh, 150);
    }
  };
  requestAnimationFrame(() => {
    requestAnimationFrame(tryRefresh);
  });
}

/** 关系网模式：中心固定，邻居环绕 */
function buildEgoPhysics() {
  return {
    enabled: true,
    solver: "barnesHut",
    stabilization: { enabled: false, iterations: 0, fit: false },
    barnesHut: {
      gravitationalConstant: -2800,
      centralGravity: 0.4,
      springLength: 165,
      springConstant: 0.06,
      damping: 0.28,
      avoidOverlap: 0.55,
    },
    minVelocity: 0.18,
    maxVelocity: 35,
    timestep: 0.32,
  };
}

/** 轻量力导向：保留展开动效，但避免长期高成本乱动 */
function buildLivePhysics(nodeCount) {
  const n = Math.max(nodeCount, 8);
  const spread = Math.sqrt(n);
  const springLength = Math.min(260, Math.max(120, 80 + spread * 14));
  return {
    enabled: true,
    solver: "barnesHut",
    stabilization: { enabled: false, iterations: 0, fit: false },
    barnesHut: {
      gravitationalConstant: Math.min(-4200, -1500 - n * 12),
      centralGravity: 0.18,
      springLength,
      springConstant: 0.035,
      damping: 0.34,
      avoidOverlap: 0.45,
    },
    minVelocity: 0.18,
    maxVelocity: 28,
    timestep: 0.28,
    adaptiveTimestep: true,
  };
}

function stopGraphSimulationSoon(net, nodeCount = getGraphNodeCount()) {
  if (!net) return;
  const stop = () => {
    try {
      net.stopSimulation();
    } catch (_) {
      /* ignore */
    }
  };

  clearTimeout(graphPhysicsNudgeTimer);
  graphPhysicsNudgeTimer = setTimeout(stop, Math.min(8500, Math.max(4200, nodeCount * 32)));
}

function enableContinuousPhysics(net, nodeCount) {
  if (!net) return;
  try {
    net.setOptions({ physics: buildLivePhysics(nodeCount) });
    net.startSimulation();
    stopGraphSimulationSoon(net, nodeCount);
  } catch (_) {
    /* ignore */
  }
}

function energizeGraphSimulation() {
  if (!network) return;
  try {
    network.setOptions({ physics: { enabled: true } });
    network.startSimulation();
    stopGraphSimulationSoon(network);
  } catch (_) {
    /* ignore */
  }
}

function stopGraphPhysicsKeeper() {
  if (graphPhysicsKeeper) {
    clearInterval(graphPhysicsKeeper);
    graphPhysicsKeeper = null;
  }
  if (graphPhysicsNudgeTimer) {
    clearTimeout(graphPhysicsNudgeTimer);
    graphPhysicsNudgeTimer = null;
  }
}

function stopHighlightPulse() {
  if (highlightPulseTimer) {
    clearInterval(highlightPulseTimer);
    highlightPulseTimer = null;
  }
}

function startGraphPhysicsKeeper(nodeCount) {
  stopGraphPhysicsKeeper();
  graphPhysicsKeeper = setInterval(() => {
    if (!network) return;
    try {
      if (graphViewMode === "ego" && egoCenterEntity) {
        // 关系网中心只在初始布局时放到中心，不再锁死，保证所有节点都能拖动。
        return;
      }
    } catch (_) {
      /* ignore */
    }
  }, 2500);
}

function getGraphNodeCount() {
  return network?.body?.nodeIndices?.length || graphNodes?.length || 50;
}

window.resumeGraphPhysics = () => {
  if (network) enableContinuousPhysics(network, getGraphNodeCount());
};

function scheduleGraphFitOnce(delay = 80) {
  clearTimeout(graphFitTimer);
  graphFitTimer = setTimeout(() => {
    if (!network) return;
    try {
      network.fit({ animation: { duration: 480, easingFunction: "easeInOutQuad" } });
    } catch (_) {
      /* ignore */
    }
  }, delay);
}

function bindGraphInteraction(net, nodeCount, dragHooks = {}) {
  if (net._kgInteractionBound) return;
  net._kgInteractionBound = true;

  net.on("dragStart", () => {
    dragHooks.onDragStart?.();
    if (graphViewMode === "ego") {
      energizeGraphSimulation();
    }
  });
  net.on("dragging", () => dragHooks.onDragging?.());
  net.on("dragEnd", () => {
    if (graphViewMode === "ego" && egoCenterEntity) {
      net.setOptions({ physics: buildEgoPhysics() });
      net.startSimulation();
      stopGraphSimulationSoon(net, nodeCount);
    }
  });
}

function computeEgoPositions(centerName, nodeList) {
  const center = nodeList.find((n) => n.name === centerName);
  if (!center) return [];
  const others = nodeList.filter((n) => n.name !== centerName);
  const R = Math.max(140, Math.min(320, 85 + others.length * 26));
  const positions = [{ id: center.id, x: 0, y: 0, fixed: false }];
  others.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(others.length, 1) - Math.PI / 2;
    positions.push({
      id: n.id,
      x: Math.round(R * Math.cos(angle)),
      y: Math.round(R * Math.sin(angle)),
    });
  });
  return positions;
}

function applyEgoRadialLayout(centerName, nodeList) {
  if (!graphNodes || !network || !centerName) return;
  const positions = computeEgoPositions(centerName, nodeList);
  if (!positions.length) return;

  graphNodes.update(positions);
  network.setOptions({ physics: buildEgoPhysics() });
  network.startSimulation();
  stopGraphSimulationSoon(network, nodeList.length);

  setTimeout(() => {
    try {
      network.moveTo({
        position: { x: 0, y: 0 },
        scale: 1.08,
        animation: { duration: 480, easingFunction: "easeInOutQuad" },
      });
    } catch (_) {
      /* ignore */
    }
  }, 150);
}

const FULL_GRAPH_ANCHOR_NAMES = [
  "人工智能",
  "机器学习",
  "深度学习",
  "大语言模型",
  "多模态大模型",
  "计算机视觉",
  "自然语言处理",
  "知识图谱",
  "AI Agent",
  "具身智能",
  "算力基础设施",
  "智能制造",
  "自动驾驶",
  "智慧医疗",
  "百度",
  "阿里巴巴",
  "腾讯",
  "华为",
  "深度求索",
  "智谱AI",
];

function stableHash(text) {
  return String(text || "").split("").reduce((acc, ch) => {
    return (acc * 31 + ch.charCodeAt(0)) >>> 0;
  }, 7);
}

function computeNodeDegrees(edgeList) {
  const degrees = new Map();
  edgeList.forEach((edge) => {
    degrees.set(edge.source, (degrees.get(edge.source) || 0) + 1);
    degrees.set(edge.target, (degrees.get(edge.target) || 0) + 1);
  });
  return degrees;
}

function pickFullGraphAnchors(nodeList, edgeList) {
  const byName = new Map(nodeList.map((node) => [node.name, node]));
  const degrees = computeNodeDegrees(edgeList);
  const anchors = [];
  const seen = new Set();

  FULL_GRAPH_ANCHOR_NAMES.forEach((name) => {
    const node = byName.get(name);
    if (node && !seen.has(node.id)) {
      seen.add(node.id);
      anchors.push(node);
    }
  });

  nodeList
    .slice()
    .sort((a, b) => (degrees.get(b.id) || 0) - (degrees.get(a.id) || 0))
    .forEach((node) => {
      if (anchors.length >= 14) return;
      if (!seen.has(node.id) && (degrees.get(node.id) || 0) >= 3) {
        seen.add(node.id);
        anchors.push(node);
      }
    });

  return anchors.slice(0, 14);
}

function applyFullMultiCenterLayout(nodeList, edgeList) {
  if (!graphNodes || !nodeList.length) return;

  const anchors = pickFullGraphAnchors(nodeList, edgeList);
  if (anchors.length < 2) return;

  const anchorIds = new Set(anchors.map((node) => node.id));
  const anchorPositions = new Map();
  const radius = Math.max(190, Math.min(320, 150 + anchors.length * 12));

  anchors.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / anchors.length - Math.PI / 2;
    const x = Math.round(radius * Math.cos(angle));
    const y = Math.round(radius * Math.sin(angle));
    anchorPositions.set(node.id, { x, y });
  });

  const linkedAnchorByNode = new Map();
  edgeList.forEach((edge) => {
    if (anchorIds.has(edge.source) && !anchorIds.has(edge.target)) {
      linkedAnchorByNode.set(edge.target, edge.source);
    }
    if (anchorIds.has(edge.target) && !anchorIds.has(edge.source)) {
      linkedAnchorByNode.set(edge.source, edge.target);
    }
  });

  const updates = nodeList.map((node, index) => {
    const anchorPosition = anchorPositions.get(node.id);
    if (anchorPosition) {
      return {
        id: node.id,
        x: anchorPosition.x,
        y: anchorPosition.y,
        fixed: false,
      };
    }

    const anchorId = linkedAnchorByNode.get(node.id) || anchors[index % anchors.length]?.id;
    const base = anchorPositions.get(anchorId) || { x: 0, y: 0 };
    const h = stableHash(node.name || node.id);
    const angle = ((h % 360) * Math.PI) / 180;
    const distance = 70 + (h % 105);
    return {
      id: node.id,
      x: Math.round(base.x + Math.cos(angle) * distance),
      y: Math.round(base.y + Math.sin(angle) * distance),
      fixed: false,
    };
  });

  graphNodes.update(updates);
}

function clearNodeLayoutLocks() {
  if (!graphNodes) return;
  graphNodes.update(
    graphNodes.get().map((n) => ({
      id: n.id,
      x: undefined,
      y: undefined,
      fixed: false,
    }))
  );
}

function updateEgoBar(name) {
  const bar = document.getElementById("graphEgoBar");
  const container = document.getElementById("graphContainer");
  const title = document.getElementById("graphEgoTitle");
  if (!bar) return;

  if (graphViewMode === "ego" && name) {
    bar.classList.remove("hidden");
    container?.classList.add("graph-shell--ego");
    if (title) title.textContent = name;
  } else {
    bar.classList.add("hidden");
    container?.classList.remove("graph-shell--ego");
    if (title) title.textContent = "—";
  }
}

function setupNetworkClick(network) {
  if (network._egoClickBound) return;
  network._egoClickBound = true;

  let pointerDown = null;

  network.on("pointerDown", (params) => {
    pointerDown = params.pointer.DOM
      ? { x: params.pointer.DOM.x, y: params.pointer.DOM.y }
      : null;
  });

  network.on("pointerUp", () => {
    setTimeout(() => {
      pointerDown = null;
    }, 0);
  });

  network.on("click", (params) => {
    if (!params.nodes.length) return;

    if (pointerDown && params.pointer?.DOM) {
      const dx = params.pointer.DOM.x - pointerDown.x;
      const dy = params.pointer.DOM.y - pointerDown.y;
      if (dx * dx + dy * dy > 64) return;
    }

    const nodeId = params.nodes[0];
    const name = nodeNameById.get(nodeId) || graphNodes?.get(nodeId)?.name;
    if (name) enterEntityNetwork(name);
  });
}

function truncateLabel(text, max = 14) {
  if (!text) return "";
  const s = String(text);
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

function getNodeRole(name) {
  if (graphFocusEntity && name === graphFocusEntity) return "focus";
  if (graphQuestionKeywords.includes(name)) return "keyword";
  if (graphRelatedNames.includes(name)) return "related";
  return "normal";
}

function buildVisNode(n, role = null) {
  const r = role || getNodeRole(n.name);
  const gt = getGraphTheme();
  const fontFace = graphFontFace();
  const base = TYPE_COLORS[n.type] || "#94a3b8";

  let size = 18;
  let borderWidth = 1.5;
  let borderColor = gt.nodeBorder;
  let background = base;
  let shape = "dot";
  let shadow = { enabled: false };
  let fontSize = 11;
  let fontBold = false;

  if (r === "keyword") {
    size = 24;
    borderWidth = 4;
    borderColor = HIGHLIGHT.keyword.border;
    background = HIGHLIGHT.keyword.fill;
    shadow = { enabled: true, color: HIGHLIGHT.keyword.glow, size: 16, x: 0, y: 0 };
    fontSize = 12;
    fontBold = true;
  }
  if (r === "related") {
    size = 22;
    borderWidth = 3;
    borderColor = HIGHLIGHT.related.border;
    background = HIGHLIGHT.related.fill;
    shadow = { enabled: true, color: HIGHLIGHT.related.glow, size: 14, x: 0, y: 0 };
    fontSize = 12;
  }
  if (r === "focus") {
    size = 34;
    borderWidth = 5;
    borderColor = HIGHLIGHT.focus.border;
    background = HIGHLIGHT.focus.fill;
    shape = "diamond";
    shadow = { enabled: true, color: HIGHLIGHT.focus.glow, size: 22, x: 0, y: 0 };
    fontSize = 13;
    fontBold = true;
  }

  return {
    id: n.id,
    label: truncateLabel(n.name, r === "focus" ? 16 : 14),
    name: n.name,
    title: `${n.name}\n${n.type}\n${n.description || ""}\n\n参考文献：${n.reference || "—"}`,
    color: {
      background,
      border: borderColor,
      highlight: { background, border: gt.nodeHighlightBorder },
      hover: { background, border: gt.nodeHighlightBorder },
    },
    font: {
      color: gt.nodeFont,
      size: fontSize,
      face: fontFace,
      vadjust: 4,
      bold: fontBold,
    },
    shape,
    size,
    borderWidth,
    shadow,
    margin: 16,
    entityType: n.type,
    _role: r,
  };
}

function buildVisEdge(e, i, focusId = null) {
  const gt = getGraphTheme();
  const touchesFocus =
    focusId && (e.source === focusId || e.target === focusId);
  return {
    id: `e-${e.source}-${e.target}-${e.type || i}`,
    from: e.source,
    to: e.target,
    title: `${e.type || "关系"}\n${e.description || ""}\n\n参考文献：${e.reference || "—"}`,
    label: e.type ? truncateLabel(e.type, 6) : undefined,
    arrows: { to: { enabled: true, scaleFactor: 0.55 } },
    color: {
      color: touchesFocus ? gt.edgeFocus : gt.edgeColor,
      highlight: gt.edgeHighlight,
      hover: gt.edgeHighlight,
    },
    width: touchesFocus ? 2.2 : 1,
    selectionWidth: 2,
    hoverWidth: 1.6,
  };
}

function rebuildNodeNameMap(nodeList) {
  nodeNameById = new Map();
  for (const n of nodeList) {
    nodeNameById.set(n.id, n.name);
  }
}

function nameToNodeId(name) {
  for (const [id, n] of nodeNameById.entries()) {
    if (n === name) return id;
  }
  if (graphNodes) {
    const found = graphNodes.get({
      filter: (item) => item.name === name,
    });
    if (found.length) return found[0].id;
  }
  return null;
}

function applyGraphHighlights() {
  if (!graphNodes) return;
  const focusId = graphFocusEntity ? nameToNodeId(graphFocusEntity) : null;
  const hasHighlight =
    graphFocusEntity || graphQuestionKeywords.length || graphRelatedNames.length;

  const nodeUpdates = [];
  for (const node of graphNodes.get()) {
    const name = node.name || nodeNameById.get(node.id) || "";
    const role = getNodeRole(name);
    const prevRole = node._role || "normal";
    if (!hasHighlight && prevRole === "normal") continue;
    if (hasHighlight && role === "normal" && prevRole === "normal") continue;

    const styled = buildVisNode(
      { id: node.id, name, type: node.entityType || "", description: "", reference: "" },
      role
    );
    const next = { ...styled };
    if (node.x != null) next.x = node.x;
    if (node.y != null) next.y = node.y;
    if (node.fixed) next.fixed = node.fixed;
    nodeUpdates.push(next);
  }
  if (nodeUpdates.length) graphNodes.update(nodeUpdates);

  if (graphEdges) {
    const gt = getGraphTheme();
    const edgeUpdates = [];
    for (const edge of graphEdges.get()) {
      const touches = focusId && (edge.from === focusId || edge.to === focusId);
      const wasFocus = edge.width > 1.5;
      if (!focusId && !wasFocus) continue;
      if (focusId && touches === wasFocus) continue;
      edgeUpdates.push({
        id: edge.id,
        color: {
          color: touches ? gt.edgeFocus : gt.edgeColor,
          highlight: gt.edgeHighlight,
          hover: gt.edgeHighlight,
        },
        width: touches ? 2.2 : 1,
      });
    }
    if (edgeUpdates.length) graphEdges.update(edgeUpdates);
  }

  updateGraphLegend();
  if (hasHighlight) selectHighlightedNodes();
  else {
    try {
      network?.unselectAll();
    } catch (_) {
      /* ignore */
    }
  }
}

function clearGraphHighlightState() {
  stopHighlightPulse();
  graphFocusEntity = null;
  graphQuestionKeywords = [];
  graphRelatedNames = [];
  applyGraphHighlights();
}

function selectHighlightedNodes() {
  if (!network) return;
  const ids = [];
  if (graphFocusEntity) {
    const id = nameToNodeId(graphFocusEntity);
    if (id) ids.push(id);
  }
  for (const name of graphQuestionKeywords) {
    const id = nameToNodeId(name);
    if (id && !ids.includes(id)) ids.push(id);
  }
  for (const name of graphRelatedNames) {
    const id = nameToNodeId(name);
    if (id && !ids.includes(id)) ids.push(id);
  }
  if (ids.length) {
    try {
      network.selectNodes(ids);
    } catch (_) {
      /* ignore */
    }
  }
}

function focusOnHighlightNodes(animate = true) {
  if (!network) return;
  const ids = [];
  if (graphFocusEntity) {
    const id = nameToNodeId(graphFocusEntity);
    if (id) ids.push(id);
  }
  for (const name of [...graphQuestionKeywords, ...graphRelatedNames]) {
    const id = nameToNodeId(name);
    if (id && !ids.includes(id)) ids.push(id);
  }
  if (!ids.length) return;

  try {
    if (ids.length === 1) {
      network.focus(ids[0], {
        scale: 1.15,
        animation: animate ? { duration: 550, easingFunction: "easeInOutQuad" } : false,
      });
    } else {
      network.fit({
        nodes: ids,
        animation: animate ? { duration: 550, easingFunction: "easeInOutQuad" } : false,
      });
    }
    selectHighlightedNodes();
  } catch (_) {
    scheduleGraphFitOnce(100);
  }
}

function updateGraphLegend() {
  const legend = document.getElementById("graphLegend");
  if (!legend) return;
  const hasHighlight =
    graphFocusEntity || graphQuestionKeywords.length || graphRelatedNames.length;
  legend.classList.toggle("hidden", !hasHighlight);
  legend.setAttribute("aria-hidden", hasHighlight ? "false" : "true");
}

function startHighlightPulse() {
  stopHighlightPulse();
}

function setGraphHighlightState({ focus = null, keywords = [], related = [] } = {}, { applyToGraph = true } = {}) {
  graphFocusEntity = focus;
  graphQuestionKeywords = [...new Set(keywords.filter(Boolean))];
  graphRelatedNames = [...new Set(related.filter((n) => n && n !== focus && !graphQuestionKeywords.includes(n)))];
  updateGraphLegend();
  if (applyToGraph && graphNodes) applyGraphHighlights();
}

function filterKnownEntityNames(names) {
  if (!entityNameSet.size) {
    entityNameSet = new Set(allEntities.map((e) => e.name));
  }
  return names.filter((n) => typeof n === "string" && entityNameSet.has(n));
}

async function api(path, options = {}) {
  const { timeoutMs = 0, ...fetchOptions } = options;
  const controller = timeoutMs > 0 ? new AbortController() : null;
  const timer =
    controller &&
    setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(path, {
      ...fetchOptions,
      signal: controller?.signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `请求失败: ${res.status}`);
    }
    return res.json();
  } catch (err) {
    if (err?.name === "AbortError") {
      throw new Error("请求超时，请检查后端是否已启动或改用 KG-only 模式");
    }
    if (err instanceof TypeError) {
      throw new Error("无法连接服务，请先运行 run_server.py");
    }
    throw err;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function escapeHtml(s) {
  if (!s) return "-";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function loadStatistics() {
  const [stats, health] = await Promise.all([
    api("/api/statistics"),
    api("/api/health"),
  ]);

  document.getElementById("metricNodes").textContent = stats.node_count ?? "—";
  document.getElementById("metricRels").textContent = stats.relation_count ?? "—";
  document.getElementById("metricEngine").textContent =
    health.graph_database?.includes("Neo4j") ? "Neo4j" : "Local";

  const subtitle = document.getElementById("heroSubtitle");
  if (subtitle) {
    subtitle.textContent = `领域：${health.domain} · ${health.graph_database} · KG / KG+LLM 双引擎`;
  }
}

async function loadEntities() {
  const data = await api("/api/entities?limit=500");
  allEntities = data.entities || [];
  entityNameSet = new Set(allEntities.map((e) => e.name));
  renderEntityTable(allEntities);
}

function filterEntitiesByInput(text) {
  const kw = (text || "").trim().toLowerCase();
  if (!kw) return [...allEntities];
  return allEntities.filter(
    (ent) =>
      ent.name.toLowerCase().includes(kw) ||
      (ent.description || "").toLowerCase().includes(kw) ||
      (ent.type || "").toLowerCase().includes(kw) ||
      (ent.reference || "").toLowerCase().includes(kw)
  );
}

function sortEntitiesWithHighlight(entities, highlight) {
  const { focus, keywords = [], related = [] } = highlight;
  const kwSet = new Set(keywords.filter(Boolean));
  const relSet = new Set(related.filter((n) => n && !kwSet.has(n) && n !== focus));

  const rank = (name) => {
    if (focus && name === focus) return 0;
    if (kwSet.has(name)) return 1;
    if (relSet.has(name)) return 2;
    return 3;
  };

  return [...entities].sort((a, b) => {
    const ra = rank(a.name);
    const rb = rank(b.name);
    if (ra !== rb) return ra - rb;
    return a.name.localeCompare(b.name, "zh-CN");
  });
}

function entityRowHighlightClass(name, highlight) {
  const { focus, keywords = [], related = [] } = highlight;
  if (focus && name === focus) return "entity-row--focus";
  if (keywords.includes(name)) return "entity-row--keyword";
  if (related.includes(name)) return "entity-row--related";
  return "";
}

function updateEntityHighlightBar() {
  const bar = document.getElementById("entityHighlightBar");
  if (!bar) return;
  const { focus, keywords = [], related = [] } = entityTableHighlight;
  const hasHighlight = Boolean(focus || keywords.length || related.length);
  bar.classList.toggle("hidden", !hasHighlight);
  bar.setAttribute("aria-hidden", hasHighlight ? "false" : "true");
  if (!hasHighlight) return;

  const parts = [];
  if (focus) parts.push(`<span class="entity-hl-tag entity-hl-tag--focus">答案实体：${escapeHtml(focus)}</span>`);
  if (keywords.length) {
    parts.push(
      `<span class="entity-hl-tag entity-hl-tag--keyword">问句关键词：${escapeHtml(keywords.join("、"))}</span>`
    );
  }
  if (related.length) {
    parts.push(
      `<span class="entity-hl-tag entity-hl-tag--related">关联：${escapeHtml(related.slice(0, 8).join("、"))}${related.length > 8 ? "…" : ""}</span>`
    );
  }
  bar.innerHTML = `<span class="entity-hl-label">问答高亮</span>${parts.join("")}<span class="entity-hl-hint">匹配项已置顶</span>`;
}

function applyEntityTableHighlights({ keywords = [], focus = null, related = [] } = {}) {
  entityTableHighlight = {
    keywords: [...new Set(keywords.filter(Boolean))],
    focus: focus || null,
    related: [...new Set(related.filter(Boolean))],
  };
  updateEntityHighlightBar();
  const filterText = document.getElementById("entityFilter")?.value || "";
  renderEntityTable(filterEntitiesByInput(filterText));

  if (currentView === "entities") {
    requestAnimationFrame(() => {
      const first = document.querySelector(
        ".entity-row--focus, .entity-row--keyword, .entity-row--related"
      );
      first?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  }
}

function renderEntityTable(entities) {
  const tbody = document.getElementById("entityTableBody");
  const hl = entityTableHighlight;
  const hasHighlight = Boolean(hl.focus || hl.keywords?.length || hl.related?.length);
  const sorted = hasHighlight ? sortEntitiesWithHighlight(entities, hl) : entities;

  tbody.innerHTML = sorted
    .map((e, i) => {
      const hlClass = entityRowHighlightClass(e.name, hl);
      const pinBadge =
        hlClass === "entity-row--focus"
          ? '<span class="entity-pin-badge">答案</span>'
          : hlClass === "entity-row--keyword"
            ? '<span class="entity-pin-badge entity-pin-badge--kw">问句</span>'
            : hlClass === "entity-row--related"
              ? '<span class="entity-pin-badge entity-pin-badge--rel">关联</span>'
              : "";
      return `
    <tr class="stagger-row entity-row ${hlClass}" data-name="${String(e.name).replace(/"/g, "&quot;")}" style="--i: ${i}">
      <td class="entity-name-cell">${pinBadge}${escapeHtml(e.name)}</td>
      <td>${escapeHtml(e.type)}</td>
      <td>${escapeHtml(e.description || "-")}</td>
      <td>${e.year != null ? escapeHtml(String(e.year)) : "-"}</td>
      <td>${escapeHtml(e.country || "-")}</td>
      <td class="col-ref" title="${escapeHtml(e.reference || "")}">${escapeHtml(e.reference || "-")}</td>
    </tr>`;
    })
    .join("");

  tbody.querySelectorAll(".entity-row").forEach((row) => {
    row.addEventListener("click", () => {
      const name = row.dataset.name;
      if (name) {
        switchView("graph");
        enterEntityNetwork(name, {
          preserveKeywords: true,
          keywords: hl.keywords,
          related: hl.related,
        });
      }
    });
  });
}

async function loadGraph(entity = null, opts = {}) {
  const egoLayout = opts.egoLayout ?? graphViewMode === "ego";
  const {
    keywords = [],
    related = [],
    hops = entity ? 1 : 2,
    limit = getGraphRenderLimit(),
    fitView = !entity,
  } = opts;

  const url = entity
    ? `/api/graph?entity=${encodeURIComponent(entity)}&limit=${limit}&hops=${hops}`
    : `/api/graph?limit=${limit}&hops=2`;
  const data = await api(url);

  if (entity) {
    setGraphHighlightState({
      focus: entity,
      keywords: keywords.length ? keywords : [entity],
      related,
    });
  } else if (keywords.length || related.length) {
    setGraphHighlightState({
      focus: keywords[0] || related[0] || null,
      keywords,
      related,
    });
  }

  renderGraph(data, {
    fitView: fitView && !entity,
    focusCamera: !!entity && !egoLayout,
    egoLayout: egoLayout && !!entity,
    egoCenter: entity,
  });
}

function syncGraphDatasets(nodeList, edgeList) {
  const focusId = graphFocusEntity ? nameToNodeId(graphFocusEntity) : null;
  const nodeItems = nodeList.map((n) => buildVisNode(n));
  const edgeItems = edgeList.map((e, i) => buildVisEdge(e, i, focusId));

  const newNodeIds = new Set(nodeItems.map((n) => n.id));
  const newEdgeIds = new Set(edgeItems.map((e) => e.id));

  graphNodes.remove(graphNodes.getIds().filter((id) => !newNodeIds.has(id)));
  graphEdges.remove(graphEdges.getIds().filter((id) => !newEdgeIds.has(id)));
  graphNodes.update(nodeItems);
  graphEdges.update(edgeItems);
}

function renderGraph(data, { fitView = true, focusCamera = false, egoLayout = false, egoCenter = null } = {}) {
  const container = document.getElementById("graphContainer");

  if (typeof vis === "undefined" || !vis.Network) {
    container.innerHTML = '<p class="graph-empty">图谱库加载失败，请检查网络后刷新页面</p>';
    return;
  }

  const nodeList = data.nodes || [];
  const edgeList = data.edges || [];

  if (!nodeList.length) {
    stopGraphPhysicsKeeper();
    stopHighlightPulse();
    if (network) {
      network.destroy();
      network = null;
      window.network = null;
      graphNodes = null;
      graphEdges = null;
    }
    container.innerHTML = '<p class="graph-empty">暂无图谱数据，请先运行导入脚本或点击「加载全图」</p>';
    return;
  }

  if (container.querySelector(".graph-empty")) {
    container.innerHTML = "";
  }

  rebuildNodeNameMap(nodeList);
  const nodeCount = nodeList.length;
  const gt = getGraphTheme();
  const fontFace = graphFontFace();
  const focusId = graphFocusEntity ? nameToNodeId(graphFocusEntity) : null;

  const useEgo = egoLayout && egoCenter;
  const options = {
    physics: useEgo ? buildEgoPhysics() : buildLivePhysics(nodeCount),
    layout: { improvedLayout: false },
    interaction: {
      hover: true,
      tooltipDelay: 100,
      zoomView: true,
      dragNodes: true,
      dragView: true,
      hideEdgesOnDrag: false,
      hideEdgesOnZoom: false,
      hoverConnectedEdges: true,
      keyboard: false,
      multiselect: false,
    },
    nodes: { shape: "dot" },
    edges: {
      smooth: { enabled: true, type: "dynamic", roundness: 0.45, forceDirection: "none" },
      font: { size: 8, color: gt.edgeFont, strokeWidth: 0, face: fontFace, align: "middle" },
      chosen: { label: false },
    },
    configure: { enabled: false },
  };

  if (network && graphNodes && graphEdges) {
    syncGraphDatasets(nodeList, edgeList);
    if (useEgo) {
      applyEgoRadialLayout(egoCenter, nodeList);
    } else {
      clearNodeLayoutLocks();
      applyFullMultiCenterLayout(nodeList, edgeList);
      network.setOptions({ physics: buildLivePhysics(nodeCount) });
      network.startSimulation();
      stopGraphSimulationSoon(network, nodeCount);
    }
    applyGraphHighlights();
    if (useEgo) {
      /* 镜头已在 applyEgoRadialLayout */
    } else if (focusCamera) {
      setTimeout(() => focusOnHighlightNodes(true), 280);
    } else if (fitView) {
      scheduleGraphFitOnce(200);
    }
    scheduleGraphViewportRefresh();
    window.dispatchEvent(new CustomEvent("graphrendered"));
    return;
  }

  stopGraphPhysicsKeeper();
  stopHighlightPulse();

  if (network) {
    network.destroy();
    network = null;
    window.network = null;
  }

  graphNodes = new vis.DataSet(nodeList.map((n) => buildVisNode(n)));
  graphEdges = new vis.DataSet(edgeList.map((e, i) => buildVisEdge(e, i, focusId)));

  network = new vis.Network(container, { nodes: graphNodes, edges: graphEdges }, options);
  window.network = network;

  if (useEgo) {
    network.setOptions({ physics: buildEgoPhysics() });
    stopGraphSimulationSoon(network, nodeCount);
  } else {
    applyFullMultiCenterLayout(nodeList, edgeList);
    enableContinuousPhysics(network, nodeCount);
  }
  startGraphPhysicsKeeper(nodeCount);
  applyGraphHighlights();
  setupNetworkClick(network);
  bindGraphInteraction(network, nodeCount);

  if (useEgo) {
    applyEgoRadialLayout(egoCenter, nodeList);
  }

  if (!graphResizeObserver && typeof ResizeObserver !== "undefined") {
    graphResizeObserver = new ResizeObserver(() => {
      clearTimeout(graphResizeTimer);
      graphResizeTimer = setTimeout(() => {
        refreshGraphViewport({ fit: false });
      }, 120);
    });
    graphResizeObserver.observe(container);
  }

  if (!useEgo && focusCamera) {
    setTimeout(() => focusOnHighlightNodes(true), 400);
  } else if (!useEgo && fitView) {
    scheduleGraphFitOnce(350);
  }
  scheduleGraphViewportRefresh();
  window.dispatchEvent(new CustomEvent("graphrendered"));
}

function hideEntityPanel() {
  document.getElementById("entityPanel")?.classList.add("hidden");
  document.querySelectorAll(".entity-row.row-active").forEach((r) => r.classList.remove("row-active"));
}

function renderRelationList(listEl, items, direction) {
  if (!items.length) {
    listEl.innerHTML = '<li class="rel-empty">暂无关系</li>';
    return;
  }
  listEl.innerHTML = items
    .map((item) => {
      const peer = direction === "out" ? item.target : item.source;
      const rel = item.relation;
      return `<li><button type="button" data-peer="${escapeHtml(peer)}"><span class="rel-type">${escapeHtml(rel)}</span> → ${escapeHtml(peer)}</button></li>`;
    })
    .join("");

  listEl.querySelectorAll("button[data-peer]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const peer = btn.dataset.peer;
      if (peer) enterEntityNetwork(peer);
    });
  });
}

async function showEntityPanel(name) {
  const panel = document.getElementById("entityPanel");
  if (!panel) return;

  try {
    const detail = await api(`/api/entity/${encodeURIComponent(name)}`);
    const e = detail.entity;
    const outCount = (detail.outgoing || []).length;
    const inCount = (detail.incoming || []).length;

    document.getElementById("entityPanelTitle").textContent = e.name;
    document.getElementById("entityPanelType").textContent =
      `${e.type || "—"} · 出${outCount} / 入${inCount}`;
    document.getElementById("entityPanelDesc").textContent = e.description || "暂无描述";

    renderRelationList(document.getElementById("entityPanelOut"), detail.outgoing || [], "out");
    renderRelationList(document.getElementById("entityPanelIn"), detail.incoming || [], "in");

    panel.classList.remove("hidden");

    document.querySelectorAll(".entity-row").forEach((row) => {
      row.classList.toggle("row-active", row.dataset.name === name);
    });
  } catch (err) {
    console.error("加载实体关系失败:", err);
  }
}

/** 单击进入以该实体为中心的关系网 */
async function enterEntityNetwork(name, opts = {}) {
  const { preserveKeywords = false, related = [], keywords: explicitKeywords = null } = opts;
  const loadToken = ++graphLoadToken;

  graphViewMode = "ego";
  egoCenterEntity = name;
  document.getElementById("graphSearch").value = name;

  const keywords = explicitKeywords?.length
    ? [...new Set([...explicitKeywords, name])]
    : preserveKeywords && graphQuestionKeywords.length
      ? [...new Set([...graphQuestionKeywords, name])]
      : [name];
  const relatedNames =
    related.length > 0
      ? related
      : preserveKeywords
        ? graphRelatedNames
        : [];

  setGraphHighlightState({ focus: name, keywords, related: relatedNames });
  updateEgoBar(name);

  await loadGraph(name, {
    keywords,
    related: relatedNames,
    hops: 1,
    limit: 120,
    fitView: false,
    egoLayout: true,
  });
  if (loadToken !== graphLoadToken) return;

  await showEntityPanel(name);
  if (loadToken !== graphLoadToken) return;

  scheduleGraphViewportRefresh(2);
}

async function exitEntityNetwork() {
  graphLoadToken += 1;
  viewportRefreshGen += 1;
  pendingGraphFromAnswer = null;
  graphViewMode = "full";
  egoCenterEntity = null;
  clearGraphHighlightState();
  applyEntityTableHighlights({ keywords: [], focus: null, related: [] });
  hideEntityPanel();
  updateEgoBar(null);
  clearNodeLayoutLocks();
  await loadGraph(null, { fitView: true });
}

async function matchEntitiesInText(text) {
  try {
    const data = await api(`/api/match-entities?text=${encodeURIComponent(text)}`);
    return data.matched_entities || [];
  } catch (_) {
    const occupied = new Array(text.length).fill(false);
    const found = [];
    const sorted = [...allEntities].sort((a, b) => b.name.length - a.name.length);
    for (const ent of sorted) {
      const nm = ent.name;
      let start = 0;
      while (true) {
        const idx = text.indexOf(nm, start);
        if (idx < 0) break;
        const span = Array.from({ length: nm.length }, (_, i) => idx + i);
        if (!span.some((i) => occupied[i])) {
          found.push(nm);
          span.forEach((i) => {
            occupied[i] = true;
          });
        }
        start = idx + 1;
      }
    }
    return found;
  }
}

async function fetchAnswer(question, mode = "kg") {
  const timeoutMs = mode === "kg_llm" ? 120000 : 45000;
  return api("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, mode }),
    timeoutMs,
  });
}

async function runCypherQuery(query) {
  return api("/api/cypher", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
    timeoutMs: 45000,
  });
}

async function buildHighlightFromAnswer(question, result) {
  const questionKeywords =
    result.matched_entities?.length > 0
      ? [...result.matched_entities]
      : await matchEntitiesInText(question);
  const focus = result.entity || questionKeywords[0] || null;
  const related = filterKnownEntityNames([
    ...(result.matched_entities || []),
    ...questionKeywords,
    result.entity,
  ]).filter((n) => n && n !== focus && !questionKeywords.includes(n));
  return { questionKeywords, focus, related };
}

/** 问答后记录高亮；若已处于分屏，则同步更新右侧图谱 */
async function syncGraphFromAnswer(question, result) {
  const { questionKeywords, focus, related } = await buildHighlightFromAnswer(question, result);

  pendingGraphFromAnswer = { question, result, questionKeywords, focus, related };
  applyEntityTableHighlights({ keywords: questionKeywords, focus, related });
  setGraphHighlightState(
    { focus, keywords: questionKeywords, related },
    { applyToGraph: false }
  );

  if (splitViewActive && (focus || questionKeywords.length)) {
    await applyGraphHighlightsInView();
  }

  return { questionKeywords, related };
}

function focusGraphViewportOnHighlights() {
  requestAnimationFrame(() => {
    if (graphViewMode === "ego" && egoCenterEntity) {
      try {
        network?.moveTo({
          position: { x: 0, y: 0 },
          scale: 1.12,
          animation: { duration: 450, easingFunction: "easeInOutQuad" },
        });
      } catch (_) {
        /* ignore */
      }
      selectHighlightedNodes();
    } else if (graphFocusEntity || graphQuestionKeywords.length) {
      focusOnHighlightNodes(true);
    }
    scheduleGraphViewportRefresh(2);
  });
}

/** 在当前可见图谱区域展示待处理的高亮（不自动开启分屏） */
async function applyGraphHighlightsInView() {
  if (!pendingGraphFromAnswer) return null;

  const { focus, questionKeywords } = pendingGraphFromAnswer;
  if (!focus && !questionKeywords.length) return null;

  await applyPendingGraphToView();
  focusGraphViewportOnHighlights();
  return pendingGraphFromAnswer;
}

/** 用户查看图谱高亮时再加载关系网（只执行一次） */
async function applyPendingGraphToView() {
  if (!pendingGraphFromAnswer) return null;

  const { focus, questionKeywords, related } = pendingGraphFromAnswer;

  if (focus) {
    await enterEntityNetwork(focus, {
      preserveKeywords: true,
      keywords: questionKeywords,
      related,
    });
  } else if (questionKeywords.length) {
    await enterEntityNetwork(questionKeywords[0], {
      preserveKeywords: true,
      keywords: questionKeywords,
      related,
    });
  }

  return pendingGraphFromAnswer;
}

async function askAndSyncGraph(question, mode = "kg") {
  const result = await fetchAnswer(question, mode);
  await syncGraphFromAnswer(question, result);
  return result;
}

let currentView = "graph";
let splitViewActive = false;

function applySingleView(viewId) {
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === viewId);
  });
  document.querySelectorAll(".app-view").forEach((panel) => {
    const isActive = panel.dataset.view === viewId;
    panel.classList.toggle("app-view--active", isActive);
    panel.hidden = !isActive;
  });
}

function applySplitViewPanels() {
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === "chat");
  });
  document.querySelectorAll(".app-view").forEach((panel) => {
    const inSplit = panel.dataset.view === "chat" || panel.dataset.view === "graph";
    panel.classList.toggle("app-view--active", inSplit);
    panel.hidden = !inSplit;
  });
}

function setSplitView(enabled, { skipViewUpdate = false } = {}) {
  splitViewActive = enabled;
  const appViews = document.querySelector(".app-views");
  appViews?.classList.toggle("app-views--split", enabled);

  const btn = document.getElementById("btnSplitCompare");
  if (btn) {
    btn.classList.toggle("active", enabled);
    btn.setAttribute("aria-pressed", String(enabled));
    const label = btn.querySelector(".btn-split-label");
    if (label) label.textContent = enabled ? "退出分屏" : "分屏对比";
  }

  if (enabled) {
    currentView = "chat";
    applySplitViewPanels();
    scheduleGraphViewportRefresh(4);
    setTimeout(() => refreshGraphViewport({ fit: false }), 180);
    setTimeout(() => refreshGraphViewport({ fit: true }), 420);
    if (pendingGraphFromAnswer) {
      void applyGraphHighlightsInView();
    }
  } else if (!skipViewUpdate) {
    applySingleView(currentView || "chat");
    if (currentView === "graph") {
      scheduleGraphViewportRefresh(2);
    }
  }
}

function toggleSplitView() {
  if (!splitViewActive && currentView !== "chat") {
    currentView = "chat";
    applySingleView("chat");
  }
  setSplitView(!splitViewActive);
}

function switchView(viewId) {
  if (splitViewActive && viewId === "chat") {
    return;
  }
  if (splitViewActive) {
    setSplitView(false, { skipViewUpdate: true });
  }
  currentView = viewId;
  applySingleView(viewId);

  if (viewId === "graph") {
    scheduleGraphViewportRefresh(2);
  }
}

async function focusGraphFromAnswer() {
  if (!splitViewActive) {
    switchView("graph");
  }
  return applyGraphHighlightsInView();
}

async function rerenderCurrentGraph() {
  getGraphRenderLimit();
  graphLoadToken += 1;
  viewportRefreshGen += 1;

  if (graphViewMode === "ego" && egoCenterEntity) {
    await loadGraph(egoCenterEntity, {
      keywords: graphQuestionKeywords,
      related: graphRelatedNames,
      hops: 1,
      limit: graphRenderLimit,
      fitView: false,
      egoLayout: true,
    });
  } else {
    await loadGraph(null, {
      keywords: graphQuestionKeywords,
      related: graphRelatedNames,
      limit: graphRenderLimit,
      fitView: true,
      egoLayout: false,
    });
  }
  scheduleGraphViewportRefresh(3);
}

async function refreshGraphDataAfterWrite() {
  await loadStatistics();
  await loadEntities();
  if (currentView === "graph" || currentView === "cypher") {
    await rerenderCurrentGraph();
  }
}

function stringifyCell(value) {
  if (value == null) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function renderCypherJson(result) {
  const rows = result.rows || [];
  return `<pre>${escapeHtml(`${result.message || "执行成功"}\n\n${JSON.stringify(rows, null, 2)}`)}</pre>`;
}

function renderCypherTable(result) {
  const rows = result.rows || [];
  if (!rows.length) {
    return `<div class="cypher-empty">${escapeHtml(result.message || "执行成功，未返回数据行")}</div>`;
  }

  const columns = [...rows.reduce((set, row) => {
    Object.keys(row || {}).forEach((key) => set.add(key));
    return set;
  }, new Set())];

  const header = columns.map((col) => `<div class="cypher-cell cypher-cell--head">${escapeHtml(col)}</div>`).join("");
  const body = rows
    .map((row) => {
      const cells = columns
        .map((col) => `<div class="cypher-cell">${escapeHtml(stringifyCell(row?.[col]))}</div>`)
        .join("");
      return cells;
    })
    .join("");

  return `
    <div class="cypher-result-summary">${escapeHtml(result.message || `返回 ${rows.length} 行`)}</div>
    <div class="cypher-grid" style="--cols: ${columns.length}">
      ${header}
      ${body}
    </div>`;
}

function renderCypherResult(result) {
  const mode = document.getElementById("cypherOutputMode")?.value || "table";
  return mode === "json" ? renderCypherJson(result) : renderCypherTable(result);
}

function cypherResultColumns(rows) {
  return [...rows.reduce((set, row) => {
    Object.keys(row || {}).forEach((key) => set.add(key));
    return set;
  }, new Set())];
}

function csvEscape(value) {
  const text = stringifyCell(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function downloadTextFile(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function exportCypherResult() {
  if (!lastCypherResult) {
    const output = document.getElementById("cypherOutput");
    if (output) output.textContent = "暂无可导出的查询结果。";
    return;
  }

  const rows = lastCypherResult.rows || [];
  const mode = document.getElementById("cypherOutputMode")?.value || "table";
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);

  if (mode === "json") {
    downloadTextFile(
      `cypher-result-${stamp}.json`,
      JSON.stringify({ ...lastCypherResult, exported_at: new Date().toISOString() }, null, 2),
      "application/json;charset=utf-8"
    );
    return;
  }

  const columns = cypherResultColumns(rows);
  const csv = [
    columns.map(csvEscape).join(","),
    ...rows.map((row) => columns.map((col) => csvEscape(row?.[col])).join(",")),
  ].join("\r\n");
  downloadTextFile(`cypher-result-${stamp}.csv`, `\ufeff${csv}`, "text/csv;charset=utf-8");
}

async function executeCypherFromConsole() {
  const input = document.getElementById("cypherInput");
  const output = document.getElementById("cypherOutput");
  const btn = document.getElementById("btnRunCypher");
  const query = input?.value.trim();
  if (!query || !output) return;

  output.textContent = "正在执行...";
  if (btn) btn.disabled = true;
  try {
    const result = await runCypherQuery(query);
    lastCypherResult = result;
    output.innerHTML = renderCypherResult(result);
    if (result.changed) {
      await refreshGraphDataAfterWrite();
    }
  } catch (err) {
    output.textContent = `执行失败：${err.message}`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

function insertCypherQuery(query) {
  const input = document.getElementById("cypherInput");
  if (!input) return;
  input.value = query;
  input.focus();
}

function openCypherHelpModal() {
  document.getElementById("cypherHelpModal")?.classList.remove("hidden");
}

function closeCypherHelpModal() {
  document.getElementById("cypherHelpModal")?.classList.add("hidden");
}

function bindTabNavigation() {
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const view = tab.dataset.view;
      if (view) switchView(view);
    });
  });

  document.getElementById("btnSplitCompare")?.addEventListener("click", toggleSplitView);
}

window.KGApp = {
  askAndSyncGraph,
  fetchAnswer,
  syncGraphFromAnswer,
  applyGraphHighlightsInView,
  applyPendingGraphToView,
  matchEntitiesInText,
  filterKnownEntityNames,
  applyEntityTableHighlights,
  switchView,
  setSplitView,
  toggleSplitView,
  isSplitViewActive: () => splitViewActive,
  focusGraphFromAnswer,
  enterEntityNetwork,
};

function bindEvents() {
  const graphContainer = document.getElementById("graphContainer");
  const btnFs = document.getElementById("btnGraphFullscreen");
  const iconExpand = btnFs?.querySelector(".icon-expand");
  const iconShrink = btnFs?.querySelector(".icon-shrink");

  btnFs?.addEventListener("click", async () => {
    if (!graphContainer) return;
    try {
      if (document.fullscreenElement === graphContainer) {
        await document.exitFullscreen();
      } else {
        await graphContainer.requestFullscreen();
      }
    } catch (err) {
      console.error("全屏切换失败", err);
    }
  });

  document.addEventListener("fullscreenchange", () => {
    const isFs = document.fullscreenElement === graphContainer;
    iconExpand?.classList.toggle("hidden", isFs);
    iconShrink?.classList.toggle("hidden", !isFs);
    setTimeout(() => {
      if (graphViewMode === "ego" && egoCenterEntity) {
        try {
          network?.moveTo({
            position: { x: 0, y: 0 },
            scale: 1.08,
            animation: { duration: 400, easingFunction: "easeInOutQuad" },
          });
        } catch (_) {
          /* ignore */
        }
      } else {
        focusOnHighlightNodes(true);
      }
      energizeGraphSimulation();
    }, 150);
  });

  document.getElementById("entityPanelClose")?.addEventListener("click", hideEntityPanel);

  document.getElementById("btnExitEgo")?.addEventListener("click", () => exitEntityNetwork());

  document.getElementById("btnLoadGraph").addEventListener("click", () => exitEntityNetwork());
  document.getElementById("graphRenderLimit")?.addEventListener("change", () => {
    rerenderCurrentGraph().catch((err) => console.warn("重渲染图谱失败", err));
  });
  document.getElementById("btnRunCypher")?.addEventListener("click", () => {
    executeCypherFromConsole().catch((err) => console.warn("执行 Cypher 失败", err));
  });
  document.getElementById("btnCypherHelp")?.addEventListener("click", openCypherHelpModal);
  document.getElementById("btnExportCypher")?.addEventListener("click", exportCypherResult);
  document.querySelectorAll("[data-close-cypher-help]").forEach((el) => {
    el.addEventListener("click", closeCypherHelpModal);
  });
  document.querySelectorAll(".cypher-example").forEach((btn) => {
    btn.addEventListener("click", () => {
      insertCypherQuery(btn.dataset.query || "");
      closeCypherHelpModal();
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeCypherHelpModal();
  });
  document.getElementById("cypherOutputMode")?.addEventListener("change", () => {
    const output = document.getElementById("cypherOutput");
    if (output && lastCypherResult) {
      output.innerHTML = renderCypherResult(lastCypherResult);
    }
  });
  document.getElementById("cypherInput")?.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      executeCypherFromConsole().catch((err) => console.warn("执行 Cypher 失败", err));
    }
  });

  const focusGraph = () => {
    const entity = document.getElementById("graphSearch").value.trim();
    if (entity) enterEntityNetwork(entity);
  };
  document.getElementById("btnFocusGraph").addEventListener("click", focusGraph);
  document.getElementById("graphSearch").addEventListener("keydown", (e) => {
    if (e.key === "Enter") focusGraph();
  });

  document.getElementById("entityFilter").addEventListener("input", (e) => {
    renderEntityTable(filterEntitiesByInput(e.target.value));
  });

  window.addEventListener("themechange", () => applyGraphHighlights());
}

async function init() {
  bindEvents();
  bindTabNavigation();
  try {
    await loadStatistics();
    await loadEntities();
    await waitForLayout();
    await loadGraph(null, { fitView: true });
  } catch (err) {
    const subtitle = document.getElementById("heroSubtitle");
    if (subtitle) {
      subtitle.textContent = `连接失败：${err.message}（请先运行 run_server.py）`;
      subtitle.style.color = "#fb7185";
    }
    console.error(err);
  } finally {
    if (typeof window.initChat === "function") window.initChat();
  }
}

init();
