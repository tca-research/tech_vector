// SCATTER — quadrant annotations, categorical by group
// All dataset-specific values (groups/colors, axis labels, quadrant callouts)
// come from DATA.scatter.config, built in build_charts.py's SCATTER_CONFIG.
function renderScatter() {
  const cfg = DATA.scatter.config;
  const data = DATA.scatter.data;
  applyChromeConfig(cfg);

  const mount = document.getElementById("scatter-chart");
  const legend = document.getElementById("scatter-legend");
  legend.innerHTML = "";
  const groupColor = {};
  cfg.groups.forEach((g) => { groupColor[g.value] = colorVar(g.color); });
  const fallbackColor = colorVar(cfg.groups[cfg.groups.length - 1].color);
  cfg.groups.forEach((g) => legendItem(legend, colorVar(g.color), g.label));

  const W = 900, H = 560, pad = 46;
  const plotW = W - pad * 2, plotH = H - pad * 2;
  const x = (v) => pad + v * plotW;
  const y = (v) => pad + plotH - v * plotH;

  mount.innerHTML = "";
  const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H }, mount);

  for (let t = 0; t <= 1.0001; t += 0.1) {
    const gx = x(t), gy = y(t);
    el("line", { class: "grid-line", x1: gx, x2: gx, y1: pad, y2: H - pad }, svg);
    el("line", { class: "grid-line", x1: pad, x2: W - pad, y1: gy, y2: gy }, svg);
    textEl(gx, H - pad + 18, t.toFixed(1), { class: "axis-label", "text-anchor": "middle" }, svg);
    textEl(pad - 10, gy + 4, t.toFixed(1), { class: "axis-label", "text-anchor": "end" }, svg);
  }
  el("line", { class: "axis-line", x1: pad, x2: pad, y1: pad, y2: H - pad }, svg);
  el("line", { class: "axis-line", x1: pad, x2: W - pad, y1: H - pad, y2: H - pad }, svg);

  textEl(W / 2, H - 6, cfg.xAxisLabel, { class: "axis-label", "text-anchor": "middle", "font-size": "12.5" }, svg);
  const ylab = textEl(16, H / 2, cfg.yAxisLabel, { class: "axis-label", "text-anchor": "middle", "font-size": "12.5" }, svg);
  ylab.setAttribute("transform", "rotate(-90 16 " + H / 2 + ")");

  const cornerPos = {
    "top-left": { x: pad + 14, y: pad + 22 },
    "bottom-left": { x: pad + 14, y: H - pad - 48 },
  };
  (cfg.quadrantAnnotations || []).forEach((ann) => {
    const pos = cornerPos[ann.corner];
    if (!pos) return;
    const t = el("text", { x: pos.x, y: pos.y, fill: "var(--cat-1-text)", "font-size": "12.5", "font-weight": "700" }, svg);
    ann.lines.forEach((line, i) => {
      el("tspan", { x: pos.x, dy: i === 0 ? 0 : 15 }, t).textContent = line;
    });
  });

  const tableRows = [];
  data.forEach((d) => {
    const color = groupColor[d.group] || fallbackColor;
    const cx = x(d.x), cy = y(d.y);
    const isHighlighted = d.group === cfg.highlightGroup;
    // Visible mark first, then a larger transparent hit-circle on top of it
    // (same center) — an SVG element painted later sits on top and wins
    // hit-testing, so the hit target must be last or hovering directly over
    // the dot itself (what a user actually aims for) hits the marker, which
    // has no listener, instead of the hit target underneath it.
    el("circle", { cx, cy, r: isHighlighted ? 8 : 7, fill: color, stroke: "var(--surface)", "stroke-width": 2 }, svg);
    if (isHighlighted) {
      textEl(cx + 12, cy + 4, d.name, { "font-size": "12", "font-weight": "700", fill: color }, svg);
    }
    el("circle", { cx, cy, r: 14, fill: "transparent" }, svg).addEventListener("pointermove", (ev) => {
      showTooltip(ev.clientX, ev.clientY, ttBox(d.name, [
        ttRow(color, cfg.xAxisLabel, d.x.toFixed(2)),
        ttRow(color, cfg.yAxisLabel, d.y.toFixed(2)),
      ]));
    });
    svg.lastChild.addEventListener("pointerleave", hideTooltip);
    tableRows.push([d.name, d.group, d.x.toFixed(3), d.y.toFixed(3)]);
  });

  registerDownload("scatter", cfg.downloadFilename, ["Name", "Group", cfg.xAxisLabel, cfg.yAxisLabel], tableRows);
}

renderScatter();
wireDownloadButtons();
