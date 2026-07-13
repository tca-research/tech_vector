// TOP RANKED DUAL — two side-by-side top-N ranked bar panels (e.g. top
// companies vs. top locations for a role), sharing one x-scale so bar
// lengths are directly comparable across panels, filtered by a single
// dropdown (e.g. Job Title). All dataset-specific values come from
// DATA.topRankedDual.config, built in build_charts.py's
// TOP_RANKED_DUAL_CONFIG. Reuses roundedRectPath from shared.js.
function renderTopRankedDual() {
  const cfg = DATA.topRankedDual.config;
  const data = DATA.topRankedDual.data;
  applyChromeConfig(cfg);

  const fmt = cfg.valueFormat || {};
  const formatValue = (v) => (fmt.prefix || "") + Math.round(v / (fmt.divisor || 1)).toLocaleString("en-AU") + (fmt.suffix || "");

  const controls = document.getElementById("top-ranked-controls");
  const panelsEl = document.getElementById("top-ranked-panels");
  controls.innerHTML = "";

  const dropdownValues = Array.from(new Set(data.map((d) => d.dropdownValue))).sort();
  let active = cfg.defaultDropdownValue && dropdownValues.includes(cfg.defaultDropdownValue)
    ? cfg.defaultDropdownValue
    : dropdownValues[0];

  const label = document.createElement("label");
  label.className = "dropdown-label";
  label.textContent = cfg.dropdownLabel || "Filter:";
  const select = document.createElement("select");
  select.className = "filter-select";
  dropdownValues.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  });
  select.value = active;
  select.addEventListener("change", () => { active = select.value; draw(); });
  label.appendChild(select);
  controls.appendChild(label);

  const topN = cfg.topN || 3;
  const W = 430, labelW = 110, rightPad = 50, topPad = 8, rowH = 34, bottomPad = 30, barH = 20;

  function draw() {
    panelsEl.innerHTML = "";
    const rowsByPanel = cfg.panels.map((p) => ({
      ...p,
      rows: data
        .filter((d) => d.dropdownValue === active && d.panel === p.panelValue)
        .sort((a, b) => a.rank - b.rank)
        .slice(0, topN),
    }));

    const allVals = rowsByPanel.flatMap((p) => p.rows.map((r) => r.value));
    const ticks = niceTicks(0, Math.max(1, ...allVals) * 1.15, 5);
    const xMax = ticks[ticks.length - 1];
    const plotW = W - labelW - rightPad;
    const x = (v) => (v / xMax) * plotW;

    const tableRows = [];

    rowsByPanel.forEach((p) => {
      const panelDiv = document.createElement("div");
      panelDiv.className = "dual-panel";
      const title = document.createElement("h4");
      title.className = "sm-panel-title";
      title.textContent = p.title;
      panelDiv.appendChild(title);

      if (!p.rows.length) {
        const note = document.createElement("p");
        note.className = "filter-note";
        note.textContent = "No " + p.title.toLowerCase() + " breakdown available for this role.";
        panelDiv.appendChild(note);
        panelsEl.appendChild(panelDiv);
        return;
      }

      const H = topPad + Math.max(p.rows.length, 1) * rowH + bottomPad;
      const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H }, panelDiv);
      const color = colorVar(p.color);
      const plotBottom = topPad + p.rows.length * rowH;

      ticks.forEach((t) => {
        const gx = labelW + x(t);
        el("line", { class: "grid-line", x1: gx, x2: gx, y1: topPad - 4, y2: plotBottom }, svg);
        textEl(gx, plotBottom + 18, formatValue(t), { class: "axis-label", "text-anchor": "middle" }, svg);
      });
      el("line", { class: "axis-line", x1: labelW, x2: labelW, y1: topPad - 4, y2: plotBottom }, svg);

      p.rows.forEach((r, i) => {
        const rowY = topPad + i * rowH;
        textEl(labelW - 10, rowY + barH / 2 + 4, r.label, { "text-anchor": "end", "font-size": "12.5", "font-weight": "600", fill: "var(--ink-primary)" }, svg);
        const w = Math.max(2, x(r.value));
        const path = roundedRectPath(labelW, rowY, w, barH, { tl: 0, bl: 0, tr: 3, br: 3 });
        const bar = el("path", { d: path, fill: color }, svg);
        const hit = el("rect", { x: labelW, y: rowY - 2, width: Math.max(w, 6), height: barH + 4, fill: "transparent" }, svg);
        const valueLabel = formatValue(r.value);
        [bar, hit].forEach((node) => {
          node.style.cursor = "pointer";
          node.addEventListener("pointermove", (ev) => {
            bar.style.filter = "brightness(1.1)";
            showTooltip(ev.clientX, ev.clientY, ttBox(r.label, [ttRow(color, p.title, valueLabel)]));
          });
          node.addEventListener("pointerleave", () => { bar.style.filter = ""; hideTooltip(); });
        });
        textEl(labelW + w + 6, rowY + barH / 2 + 4, valueLabel, { "font-size": "12", "font-weight": "700", fill: colorTextVar(p.color) }, svg);
        tableRows.push([active, p.title, r.label, valueLabel]);
      });

      panelsEl.appendChild(panelDiv);
    });

    registerDownload("topRankedDual", cfg.downloadFilename, [cfg.dropdownLabel || "Filter", "Panel", "Label", "Value"], tableRows);
  }

  draw();
}

renderTopRankedDual();
wireDownloadButtons();
