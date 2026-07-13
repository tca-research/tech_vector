// STACKED BAR SMALL MULTIPLES — one panel per manager_type-style breakdown,
// each panel showing one 100%-stacked Men/Women bar per sector, with a single
// dropdown (e.g. movement type) filtering all panels at once. All
// dataset-specific values come from DATA.stackedSmallMultiples.config, built
// in build_charts.py's STACKED_SMALL_MULTIPLES_CONFIG-style configs. Reuses
// drawStackedBarSegments/roundedRectPath from shared.js.
function renderStackedSmallMultiples() {
  const cfg = DATA.stackedSmallMultiples.config;
  const data = DATA.stackedSmallMultiples.data;
  applyChromeConfig(cfg);

  const controls = document.getElementById("stacked-sm-controls");
  const legend = document.getElementById("stacked-sm-legend");
  const panelsEl = document.getElementById("stacked-sm-panels");
  controls.innerHTML = "";
  legend.innerHTML = "";

  cfg.series.forEach((s) => legendItem(legend, colorVar(s.color), s.label));

  let activeFilter = cfg.defaultFilterValue || cfg.filterOptions[0].value;

  const label = document.createElement("label");
  label.className = "dropdown-label";
  label.textContent = cfg.dropdownLabel || "Filter:";
  const select = document.createElement("select");
  select.className = "filter-select";
  cfg.filterOptions.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = o.value;
    opt.textContent = o.label;
    select.appendChild(opt);
  });
  select.value = activeFilter;
  select.addEventListener("change", () => {
    activeFilter = select.value;
    draw();
  });
  label.appendChild(select);
  controls.appendChild(label);

  const W = 900, labelW = 220, rightPad = 20;
  const plotW = W - labelW - rightPad;
  const rowH = 40, barH = 24, topPad = 6, bottomPad = 6;

  function draw() {
    panelsEl.innerHTML = "";
    const tableRows = [];

    cfg.panelOrder.forEach((panelName) => {
      const panelRows = (cfg.sectorOrder || [])
        .map((sector) => data.find((d) => d.panel === panelName && d.sector === sector && d.filter === activeFilter))
        .filter(Boolean);
      if (!panelRows.length) return;

      const panelDiv = document.createElement("div");
      panelDiv.className = "stacked-sm-panel";
      const title = document.createElement("h4");
      title.className = "sm-panel-title";
      title.textContent = panelName;
      panelDiv.appendChild(title);

      const H = topPad + panelRows.length * rowH + bottomPad;
      const svgHost = document.createElement("div");
      panelDiv.appendChild(svgHost);
      const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H }, svgHost);

      panelRows.forEach((d, i) => {
        const rowY = topPad + i * rowH;
        const barY = rowY + (rowH - barH) / 2;
        textEl(labelW - 14, rowY + rowH / 2 + 4, d.sector, { "text-anchor": "end", "font-size": "12", "font-weight": "600", fill: "var(--ink-primary)" }, svg);
        const values = drawStackedBarSegments(svg, labelW, barY, plotW, barH, cfg.series, d, panelName + " — " + d.sector);
        tableRows.push([panelName, d.sector, ...values]);
      });

      panelsEl.appendChild(panelDiv);
    });

    registerDownload(
      "stackedSmallMultiples",
      cfg.downloadFilename,
      [cfg.panelLabel || "Panel", "Sector", ...cfg.series.map((s) => s.label)],
      tableRows
    );
  }

  draw();
}

renderStackedSmallMultiples();
wireDownloadButtons();
