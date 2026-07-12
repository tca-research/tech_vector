// BAR CHART — grouped horizontal bars + direct annotations
// All dataset-specific values (series, colors, labels, formatting) come from
// DATA.bar.config, built in build_charts.py's BAR_CONFIG — nothing about a
// particular dataset is hardcoded here.
function renderBarChart() {
  const cfg = DATA.bar.config;
  const data = DATA.bar.data;
  applyChromeConfig(cfg);

  const formatValue = (v) => (cfg.valueFormat.prefix || "") + Math.round(v / (cfg.valueFormat.divisor || 1)) + (cfg.valueFormat.suffix || "");

  const mount = document.getElementById("bar-chart");
  const legend = document.getElementById("bar-legend");
  legend.innerHTML = "";
  const series = cfg.series;
  series.forEach((s) => legendItem(legend, colorVar(s.color), s.label));

  const W = 900, labelW = 190, annW = 250, rightPad = 14;
  const plotW = W - labelW - annW - rightPad;
  const rowH = 150, topPad = 14, bottomPad = 34;
  const H = topPad + data.length * rowH + bottomPad;
  mount.innerHTML = "";
  const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img", "aria-label": cfg.title }, mount);

  const maxVal = Math.max(...data.map((d) => d[series[0].column]));
  // Pad the domain 10% past the longest bar so its value label (drawn past
  // the bar's tip) always has clearance before the annotation column —
  // without this, a bar whose value sits right at the rounded tick max runs
  // its label straight into the annotation box next to it.
  const ticks = niceTicks(0, maxVal * 1.1, 6);
  const xMax = ticks[ticks.length - 1];
  const x = (v) => (v / xMax) * plotW;

  const plotBottom = topPad + data.length * rowH;
  ticks.forEach((t) => {
    const gx = labelW + x(t);
    el("line", { class: "grid-line", x1: gx, x2: gx, y1: topPad - 6, y2: plotBottom }, svg);
    textEl(gx, plotBottom + 20, formatValue(t), { class: "axis-label", "text-anchor": "middle" }, svg);
  });
  el("line", { class: "axis-line", x1: labelW, x2: labelW, y1: topPad - 6, y2: plotBottom }, svg);

  const barH = 22, barGap = 5;
  const barsBlockH = barH * series.length + barGap * (series.length - 1);
  const tableRows = [];
  data.forEach((d, i) => {
    const rowY = topPad + i * rowH;
    const barsTop = rowY + (rowH - barsBlockH) / 2;
    textEl(labelW - 14, rowY + rowH / 2 + 4, d.category, { "text-anchor": "end", "font-size": "13.5", "font-weight": "600", fill: "var(--ink-primary)" }, svg);

    series.forEach((s, si) => {
      const by = barsTop + si * (barH + barGap);
      const val = d[s.column];
      const w = Math.max(2, x(val));
      const barColor = colorVar(s.color);
      const r = 4;
      const path = "M " + labelW + " " + by +
        " H " + (labelW + Math.max(w - r, r)) +
        " A " + r + " " + r + " 0 0 1 " + (labelW + w) + " " + (by + r) +
        " V " + (by + barH - r) +
        " A " + r + " " + r + " 0 0 1 " + (labelW + Math.max(w - r, r)) + " " + (by + barH) +
        " H " + labelW + " Z";
      const bar = el("path", { d: path, fill: barColor, class: "bar-mark" }, svg);
      bar.style.cursor = "pointer";
      const hit = el("rect", { x: labelW, y: by - 2, width: Math.max(w, 6), height: barH + 4, fill: "transparent" }, svg);
      [bar, hit].forEach((node) => {
        node.addEventListener("pointermove", (ev) => {
          bar.style.filter = "brightness(1.08)";
          showTooltip(ev.clientX, ev.clientY, ttBox(d.category, [ttRow(barColor, s.label, formatValue(val))]));
        });
        node.addEventListener("pointerleave", () => { bar.style.filter = ""; hideTooltip(); });
      });
      const textColor = colorTextVar(s.color);
      textEl(labelW + w + 8, by + barH / 2 + 5, formatValue(val), { "font-size": "13.5", "font-weight": "700", fill: textColor }, svg);
    });

    if (d.annotation) {
      const fo = el("foreignObject", { x: labelW + plotW + 18, y: rowY + 6, width: annW, height: rowH - 12 }, svg);
      const div = document.createElement("div");
      div.setAttribute("xmlns", "http://www.w3.org/1999/xhtml");
      div.className = "bar-annotation";
      div.textContent = d.annotation;
      fo.appendChild(div);
    }

    if (i < data.length - 1) {
      el("line", { x1: 0, x2: W - rightPad, y1: rowY + rowH - 8, y2: rowY + rowH - 8, class: "grid-line" }, svg);
    }

    tableRows.push([d.category, ...series.map((s) => formatValue(d[s.column]))]);
  });

  registerDownload("bar", cfg.downloadFilename, ["Category", ...series.map((s) => s.label)], tableRows);
}

renderBarChart();
wireDownloadButtons();
