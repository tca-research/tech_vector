// STACKED BAR — one 100%-stacked horizontal bar per category, with a sector
// dropdown swapping the active slice of rows. All dataset-specific values
// (categories, series/colors, sectors, labels) come from DATA.stackedBar
// .config, built in build_charts.py's STACKED_BAR_CONFIG-style configs.
// (roundedRectPath and drawStackedBarRow are shared helpers, defined in shared.js.)
function renderStackedBar() {
  const cfg = DATA.stackedBar.config;
  const data = DATA.stackedBar.data;
  applyChromeConfig(cfg);

  const controls = document.getElementById("stacked-bar-controls");
  const legend = document.getElementById("stacked-bar-legend");
  const mount = document.getElementById("stacked-bar-chart");
  controls.innerHTML = "";
  legend.innerHTML = "";

  cfg.series.forEach((s) => legendItem(legend, colorVar(s.color), s.label));

  let activeSector = cfg.defaultSector || cfg.sectors[0].value;

  const label = document.createElement("label");
  label.className = "dropdown-label";
  label.textContent = cfg.dropdownLabel || "Sector:";
  const select = document.createElement("select");
  select.className = "filter-select";
  cfg.sectors.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.value;
    opt.textContent = s.label;
    select.appendChild(opt);
  });
  select.value = activeSector;
  select.addEventListener("change", () => {
    activeSector = select.value;
    draw();
  });
  label.appendChild(select);
  controls.appendChild(label);

  const W = 900, labelW = 270, rightPad = 20;
  const plotW = W - labelW - rightPad;
  const rowH = 44, barH = 26, topPad = 10, bottomPad = 10;

  function draw() {
    const bySector = data.filter((d) => d.sector === activeSector);
    const byCategory = {};
    bySector.forEach((d) => { byCategory[d.category] = d; });
    const rows = (cfg.categoryOrder || Object.keys(byCategory))
      .map((cat) => byCategory[cat])
      .filter(Boolean);

    const H = topPad + rows.length * rowH + bottomPad;
    mount.innerHTML = "";
    const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H }, mount);

    const tableRows = [];
    rows.forEach((d, i) => {
      const rowY = topPad + i * rowH;
      const barY = rowY + (rowH - barH) / 2;
      textEl(labelW - 14, rowY + rowH / 2 + 4, d.category, { "text-anchor": "end", "font-size": "12", "font-weight": "600", fill: "var(--ink-primary)" }, svg);

      const values = drawStackedBarSegments(svg, labelW, barY, plotW, barH, cfg.series, d, d.category);
      tableRows.push([d.category, ...values]);
    });

    registerDownload("stackedBar", cfg.downloadFilename, ["Category", ...cfg.series.map((s) => s.label)], tableRows);
  }

  draw();
}

renderStackedBar();
wireDownloadButtons();
