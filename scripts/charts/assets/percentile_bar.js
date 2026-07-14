// PERCENTILE BAR — one horizontal bar per salary percentile (90th/75th/
// Median/25th), filtered by a Job Title dropdown and a Level dropdown. All
// dataset-specific values come from DATA.percentile.config, built in
// build_charts.py's PERCENTILE_BAR_CONFIG.
function renderPercentileBar() {
  const cfg = DATA.percentile.config;
  const data = DATA.percentile.data;
  applyChromeConfig(cfg);

  const fmt = cfg.valueFormat || {};
  const formatValue = (v) => (fmt.prefix || "") + Math.round(v / (fmt.divisor || 1)).toLocaleString("en-AU") + (fmt.suffix || "");

  const controls = document.getElementById("percentile-controls");
  const mount = document.getElementById("percentile-chart");
  controls.innerHTML = "";

  const jobTitles = Array.from(new Set(data.map((d) => d.jobTitle))).sort();
  let activeJobTitle = cfg.defaultJobTitle && jobTitles.includes(cfg.defaultJobTitle) ? cfg.defaultJobTitle : jobTitles[0];
  let activeLevel = cfg.defaultLevel || cfg.levelOptions[0].value;

  const jobLabel = document.createElement("label");
  jobLabel.className = "dropdown-label";
  jobLabel.textContent = cfg.jobTitleDropdownLabel || "Job Title:";
  const jobSelect = document.createElement("select");
  jobSelect.className = "filter-select";
  jobTitles.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    jobSelect.appendChild(opt);
  });
  jobSelect.value = activeJobTitle;
  jobSelect.addEventListener("change", () => { activeJobTitle = jobSelect.value; draw(); });
  jobLabel.appendChild(jobSelect);

  const levelLabel = document.createElement("label");
  levelLabel.className = "dropdown-label";
  levelLabel.textContent = cfg.levelDropdownLabel || "Level:";
  const levelSelect = document.createElement("select");
  levelSelect.className = "filter-select";
  cfg.levelOptions.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = o.value;
    opt.textContent = o.label;
    levelSelect.appendChild(opt);
  });
  levelSelect.value = activeLevel;
  levelSelect.addEventListener("change", () => { activeLevel = levelSelect.value; draw(); });
  levelLabel.appendChild(levelSelect);

  controls.appendChild(jobLabel);
  controls.appendChild(levelLabel);

  const W = 900, labelW = 90, rightPad = 60, topPad = 10, rowH = 46, bottomPad = 34;
  const color = colorVar(cfg.barColor || "cat-3");

  function draw() {
    const byPercentile = {};
    data
      .filter((d) => d.jobTitle === activeJobTitle && d.level === activeLevel)
      .forEach((d) => { byPercentile[d.percentile] = d.value; });
    const rows = cfg.percentileOrder
      .filter((p) => byPercentile[p] != null)
      .map((p) => ({ percentile: p, value: byPercentile[p] }));

    const H = topPad + rows.length * rowH + bottomPad;
    const plotW = W - labelW - rightPad;
    mount.innerHTML = "";
    const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H }, mount);

    if (!rows.length) {
      textEl(W / 2, H / 2, "No data for this combination.", { "text-anchor": "middle", class: "axis-label" }, svg);
      registerDownload("percentile", cfg.downloadFilename, ["Percentile", "Salary"], []);
      return;
    }

    const maxVal = Math.max(...rows.map((d) => d.value));
    const ticks = niceTicks(0, maxVal * 1.15, 6);
    const xMax = ticks[ticks.length - 1];
    const x = (v) => (v / xMax) * plotW;
    const plotBottom = topPad + rows.length * rowH;

    ticks.forEach((t) => {
      const gx = labelW + x(t);
      el("line", { class: "grid-line", x1: gx, x2: gx, y1: topPad - 4, y2: plotBottom }, svg);
      textEl(gx, plotBottom + 20, formatValue(t), { class: "axis-label", "text-anchor": "middle" }, svg);
    });
    el("line", { class: "axis-line", x1: labelW, x2: labelW, y1: topPad - 4, y2: plotBottom }, svg);

    const barH = 28;
    const tableRows = [];
    rows.forEach((d, i) => {
      const rowY = topPad + i * rowH + (rowH - barH) / 2;
      textEl(labelW - 14, rowY + barH / 2 + 4, d.percentile, { "text-anchor": "end", "font-size": "13", "font-weight": "700", fill: "var(--ink-primary)" }, svg);
      const w = Math.max(2, x(d.value));
      const r = 4;
      const path = "M " + labelW + " " + rowY +
        " H " + (labelW + Math.max(w - r, r)) +
        " A " + r + " " + r + " 0 0 1 " + (labelW + w) + " " + (rowY + r) +
        " V " + (rowY + barH - r) +
        " A " + r + " " + r + " 0 0 1 " + (labelW + Math.max(w - r, r)) + " " + (rowY + barH) +
        " H " + labelW + " Z";
      const bar = el("path", { d: path, fill: color }, svg);
      const hit = el("rect", { x: labelW, y: rowY - 2, width: Math.max(w, 6), height: barH + 4, fill: "transparent" }, svg);
      const valueLabel = formatValue(d.value);
      [bar, hit].forEach((node) => {
        node.style.cursor = "pointer";
        bindTooltipHover(node, (ev) => {
          bar.style.filter = "brightness(1.1)";
          showTooltip(ev.clientX, ev.clientY, ttBox(activeJobTitle + " — " + activeLevel, [ttRow(color, d.percentile, valueLabel)]));
        }, () => { bar.style.filter = ""; hideTooltip(); });
      });
      const labelInside = w > 60;
      textEl(
        labelInside ? labelW + w - 10 : labelW + w + 8,
        rowY + barH / 2 + 4,
        valueLabel,
        { "text-anchor": labelInside ? "end" : "start", "font-size": "13", "font-weight": "700", fill: labelInside ? "#fff" : colorTextVar(cfg.barColor || "cat-3") },
        svg
      );
      tableRows.push([d.percentile, valueLabel]);
    });

    registerDownload("percentile", cfg.downloadFilename, ["Percentile", "Salary"], tableRows);
  }

  draw();
}

renderPercentileBar();
wireDownloadButtons();
