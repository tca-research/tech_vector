// RANKED BAR — countries/entities ranked by value, one highlighted, with an
// optional dropdown when more than one value column is available. All
// dataset-specific values come from DATA.rankedBar.config, built in
// build_charts.py's RANKED_BAR_CONFIG-style configs.
function renderRankedBar() {
  const cfg = DATA.rankedBar.config;
  const data = DATA.rankedBar.data;
  applyChromeConfig(cfg);

  const controls = document.getElementById("ranked-bar-controls");
  const mount = document.getElementById("ranked-bar-chart");
  controls.innerHTML = "";

  let activeKey = cfg.defaultValueColumn || cfg.valueColumns[0].key;

  if (cfg.valueColumns.length > 1) {
    const label = document.createElement("label");
    label.className = "dropdown-label";
    label.textContent = cfg.dropdownLabel || "Sub-Indicators:";
    const select = document.createElement("select");
    select.className = "filter-select";
    cfg.valueColumns.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.key;
      opt.textContent = c.label;
      select.appendChild(opt);
    });
    select.value = activeKey;
    select.addEventListener("change", () => {
      activeKey = select.value;
      draw();
    });
    label.appendChild(select);
    controls.appendChild(label);
  }

  const W = 900, labelW = 170, rightPad = 60, topPad = 10, rowH = 30, bottomPad = 34;

  function draw() {
    const rows = data
      .map((d) => ({ name: d.name, region: d.region, value: d.values[activeKey] }))
      .filter((d) => d.value != null)
      .sort((a, b) => b.value - a.value);

    const H = topPad + rows.length * rowH + bottomPad;
    const plotW = W - labelW - rightPad;
    mount.innerHTML = "";
    const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H }, mount);

    const maxVal = Math.max(...rows.map((d) => d.value));
    const ticks = niceTicks(0, maxVal * 1.15, 6);
    const xMax = ticks[ticks.length - 1];
    const x = (v) => (v / xMax) * plotW;
    const plotBottom = topPad + rows.length * rowH;

    ticks.forEach((t) => {
      const gx = labelW + x(t);
      el("line", { class: "grid-line", x1: gx, x2: gx, y1: topPad - 4, y2: plotBottom }, svg);
      textEl(gx, plotBottom + 20, Math.round(t * 100) / 100 + (cfg.valueSuffix || ""), { class: "axis-label", "text-anchor": "middle" }, svg);
    });
    el("line", { class: "axis-line", x1: labelW, x2: labelW, y1: topPad - 4, y2: plotBottom }, svg);

    const barH = 18;
    const tableRows = [];
    rows.forEach((d, i) => {
      const rowY = topPad + i * rowH;
      const isHighlighted = d.name === cfg.highlightName;
      const color = isHighlighted ? colorVar(cfg.highlightColor) : colorVar(cfg.barColor);
      textEl(labelW - 10, rowY + barH / 2 + 4, d.name, { "text-anchor": "end", "font-size": "12.5", "font-weight": isHighlighted ? "700" : "400", fill: "var(--ink-primary)" }, svg);
      const w = Math.max(2, x(d.value));
      const r = 3;
      const path = "M " + labelW + " " + rowY +
        " H " + (labelW + Math.max(w - r, r)) +
        " A " + r + " " + r + " 0 0 1 " + (labelW + w) + " " + (rowY + r) +
        " V " + (rowY + barH - r) +
        " A " + r + " " + r + " 0 0 1 " + (labelW + Math.max(w - r, r)) + " " + (rowY + barH) +
        " H " + labelW + " Z";
      const bar = el("path", { d: path, fill: color }, svg);
      const hit = el("rect", { x: labelW, y: rowY - 2, width: Math.max(w, 6), height: barH + 4, fill: "transparent" }, svg);
      const valueLabel = (Math.round(d.value * 10) / 10) + (cfg.valueSuffix || "");
      [bar, hit].forEach((node) => {
        node.style.cursor = "pointer";
        bindTooltipHover(node, (ev) => {
          bar.style.filter = "brightness(1.1)";
          showTooltip(ev.clientX, ev.clientY, ttBox(d.name, [ttRow(color, d.region || "", valueLabel)]));
        }, () => { bar.style.filter = ""; hideTooltip(); });
      });
      textEl(labelW + w + 6, rowY + barH / 2 + 4, valueLabel, { "font-size": "12", "font-weight": "700", fill: isHighlighted ? colorTextVar(cfg.highlightColor) : "var(--ink-secondary)" }, svg);
      tableRows.push([d.name, d.region || "", valueLabel]);
    });

    const activeLabel = (cfg.valueColumns.find((c) => c.key === activeKey) || {}).label || "Value";
    registerDownload("rankedBar", cfg.downloadFilename, ["Name", "Region", activeLabel], tableRows);
  }

  draw();
}

renderRankedBar();
wireDownloadButtons();
