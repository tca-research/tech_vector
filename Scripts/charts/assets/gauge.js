// GAUGE — semi-circle progress-to-target gauges, one config entry per gauge.
// All dataset-specific values (label, value, current/target labels, colors,
// description) come from DATA.gauge.config.gauges, built in build_charts.py's
// GAUGE_CONFIG.
function renderGauges() {
  const cfg = DATA.gauge.config;
  const data = DATA.gauge.data;
  applyChromeConfig(cfg);

  const row = document.getElementById("gauge-row");
  row.innerHTML = "";

  function polar(cx, cy, r, angleDeg) {
    const rad = (angleDeg * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
  }
  function arcPath(cx, cy, r, a1, a2) {
    const p1 = polar(cx, cy, r, a1);
    const p2 = polar(cx, cy, r, a2);
    const largeArc = Math.abs(a1 - a2) > 180 ? 1 : 0;
    return "M " + p1.x + " " + p1.y + " A " + r + " " + r + " 0 " + largeArc + " 1 " + p2.x + " " + p2.y;
  }
  function badge(svg, cx, cy, text, color) {
    const w = Math.max(34, text.length * 7.5 + 12);
    const h = 22;
    el("rect", { x: cx - w / 2, y: cy - h / 2, width: w, height: h, rx: h / 2, fill: color }, svg);
    textEl(cx, cy + 4, text, { "text-anchor": "middle", "font-size": "12", "font-weight": "700", fill: "#fff" }, svg);
  }

  data.forEach((g) => {
    const wrap = document.createElement("div");
    wrap.className = "gauge-item";

    const W = 280, H = 165;
    const cx = W / 2, cy = 148, r = 96;
    const svg = el("svg", { viewBox: "0 0 " + W + " " + H }, wrap);

    const valueAngle = 180 - (g.value / 100) * 180;
    el("path", { d: arcPath(cx, cy, r, 180, valueAngle), fill: "none", stroke: colorVar(g.filledColor), "stroke-width": 20, "stroke-linecap": "round" }, svg);
    el("path", { d: arcPath(cx, cy, r, valueAngle, 0), fill: "none", stroke: colorVar(g.remainingColor), "stroke-width": 20, "stroke-linecap": "round" }, svg);

    const needleTip = polar(cx, cy, r - 32, valueAngle);
    el("line", { x1: cx, y1: cy, x2: needleTip.x, y2: needleTip.y, stroke: colorVar(g.needleColor), "stroke-width": 6, "stroke-linecap": "round" }, svg);
    el("circle", { cx, cy, r: 7, fill: colorVar(g.needleColor) }, svg);

    const currentPos = polar(cx, cy, r + 22, valueAngle);
    badge(svg, currentPos.x, currentPos.y, g.currentLabel, colorVar(g.currentBadgeColor));
    const targetPos = polar(cx, cy, r + 22, 0);
    badge(svg, targetPos.x, targetPos.y, g.targetLabel, colorVar(g.targetBadgeColor));

    textEl(cx, cy - 8, Math.round(g.value) + "%", { "text-anchor": "middle", "font-size": "30", "font-weight": "800", fill: "var(--ink-primary)" }, svg);

    wrap.appendChild(svg);

    const label = document.createElement("div");
    label.className = "gauge-label";
    label.textContent = g.label;
    wrap.appendChild(label);

    if (g.description) {
      const desc = document.createElement("p");
      desc.className = "gauge-desc";
      desc.textContent = g.description;
      wrap.appendChild(desc);
    }

    row.appendChild(wrap);
  });

  registerDownload(
    "gauge",
    cfg.downloadFilename,
    ["Label", "Value (%)", "Current", "Target"],
    data.map((g) => [g.label, g.value, g.currentLabel, g.targetLabel])
  );
}

renderGauges();
wireDownloadButtons();
