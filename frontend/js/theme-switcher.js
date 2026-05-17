/**
 * 随机主题切换器 — 应用 CSS 变量、装饰层与图谱配色。
 */
(function () {
  let currentThemeId = null;
  let isAnimating = false;

  function getThemeById(id) {
    return THEMES.find((t) => t.id === id) || THEMES[0];
  }

  function pickRandomTheme(excludeId) {
    const pool = THEMES.filter((t) => t.id !== excludeId);
    return pool[Math.floor(Math.random() * pool.length)];
  }

  function applyGraphTheme(graph) {
    if (!graph || !window.network) return;
    const g = graph;
    const fontFace = getComputedStyle(document.documentElement)
      .getPropertyValue("--font-body")
      .trim()
      .replace(/"/g, "")
      .split(",")[0]
      .trim();

    try {
      window.network.setOptions({
        nodes: {
          font: { color: g.nodeFont, face: fontFace },
          color: { border: g.nodeBorder, highlight: { border: g.nodeHighlightBorder } },
        },
        edges: {
          font: { color: g.edgeFont, background: g.edgeFontBg, face: fontFace },
          color: { color: g.edgeColor, highlight: g.edgeHighlight, hover: g.edgeHighlight },
        },
      });

      const nodes = window.network.body?.data?.nodes;
      if (nodes?.getIds) {
        nodes.update(
          nodes.getIds().map((id) => {
            const n = nodes.get(id);
            const bg = n.color?.background || n.color;
            return {
              id,
              font: { color: g.nodeFont, face: fontFace },
              color: {
                background: bg,
                border: g.nodeBorder,
                highlight: { background: bg, border: g.nodeHighlightBorder },
              },
            };
          })
        );
      }

      const edges = window.network.body?.data?.edges;
      if (edges?.getIds) {
        edges.update(
          edges.getIds().map((id) => ({
            id,
            font: { color: g.edgeFont, background: g.edgeFontBg, face: fontFace },
            color: { color: g.edgeColor, highlight: g.edgeHighlight, hover: g.edgeHighlight },
          }))
        );
      }

      window.network.redraw();
      window.resumeGraphPhysics?.();
    } catch (_) {
      /* 图谱尚未就绪 */
    }
  }

  function applyTheme(theme, { animate = true } = {}) {
    if (!theme) return;
    const root = document.documentElement;

    if (animate) {
      root.classList.add("theme-transition");
      setTimeout(() => root.classList.remove("theme-transition"), 550);
    }

    Object.entries(theme.vars).forEach(([key, val]) => {
      root.style.setProperty(key, val);
    });

    root.dataset.theme = theme.id;
    root.dataset.deco = theme.deco;
    root.dataset.dark = theme.dark ? "true" : "false";

    currentThemeId = theme.id;
    localStorage.setItem(THEME_STORAGE_KEY, theme.id);

    applyGraphTheme(theme.graph);

    const fab = document.getElementById("themeSwitcher");
    const label = document.getElementById("themeSwitcherLabel");
    if (fab) fab.dataset.themeName = theme.name;
    if (label) label.textContent = theme.name;

    window.dispatchEvent(new CustomEvent("themechange", { detail: theme }));
  }

  function switchRandomTheme() {
    if (isAnimating) return;
    isAnimating = true;

    const fab = document.getElementById("themeSwitcher");
    fab?.classList.add("theme-fab--spin");

    const next = pickRandomTheme(currentThemeId);
    applyTheme(next);

    setTimeout(() => {
      fab?.classList.remove("theme-fab--spin");
      isAnimating = false;
    }, 520);
  }

  function initThemeSwitcher() {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    const initial = saved ? getThemeById(saved) : THEMES[0];
    applyTheme(initial, { animate: false });

    const fab = document.getElementById("themeSwitcher");
    fab?.addEventListener("click", switchRandomTheme);

    window.addEventListener("graphrendered", () => {
      applyGraphTheme(getThemeById(currentThemeId).graph);
      setTimeout(() => window.resumeGraphPhysics?.(), 100);
    });
  }

  window.ThemeSwitcher = {
    apply: applyTheme,
    random: switchRandomTheme,
    getCurrent: () => getThemeById(currentThemeId),
    getAll: () => THEMES,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initThemeSwitcher);
  } else {
    initThemeSwitcher();
  }
})();
