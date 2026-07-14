// SMALL MULTIPLES — macro panel + N dual-line occupation panels
// All dataset-specific values (caption, legend, panel titles/series, which
// Metric/Occupation keys map to which panel) come from
// DATA.smallMultiples.config, built in build_charts.py's
// SMALL_MULTIPLES_CONFIG.
function renderSmallMultiples() {
  const cfg = DATA.smallMultiples.config;
  const data = DATA.smallMultiples.data;
  applyChromeConfig(cfg);

  const caption = document.getElementById("sm-caption");
  caption.innerHTML = "";
  cfg.captionParts.forEach(([txt, cls]) => {
    const span = document.createElement("span");
    if (cls === "muted") { span.style.color = "var(--ink-muted)"; span.style.fontWeight = "700"; }
    else if (cls) { span.style.color = colorTextVar(cls); span.style.fontWeight = "700"; }
    span.textContent = txt;
    caption.appendChild(span);
  });

  const legend = document.getElementById("sm-legend");
  legend.innerHTML = "";
  cfg.legend.forEach((item) => legendItem(legend, colorVar(item.color), item.label, true));

  const grid = document.getElementById("sm-grid");
  grid.innerHTML = "";

  const START = cfg.startDate;
  const occPanels = cfg.occupationPanels;
  occPanels.forEach((p) => data[p.key].forEach((d) => assertIsoDate(d.date)));
  cfg.macroPanel.series.forEach((s) => data.macro[s.key].forEach((d) => assertIsoDate(d.date)));

  // data.sharedYAxis (set by build_charts.py's --small-multiples-y-axis
  // flag): true -> all occupation panels use one common scale (heights
  // comparable across panels); false -> each panel scales to fit only its
  // own values.
  const sharedOccMax = Math.max(...occPanels.flatMap((p) => data[p.key].filter((d) => d.date >= START).map((d) => d.value)));
  const sharedOccTicks = niceTicks(0, sharedOccMax, 4);
  const sharedOccYMax = sharedOccTicks[sharedOccTicks.length - 1];

  function drawPanel(title) {
    const wrap = document.createElement("div");
    const h3 = document.createElement("h4");
    h3.className = "sm-panel-title";
    h3.textContent = title;
    wrap.appendChild(h3);
    const mount = document.createElement("div");
    mount.className = "chart-mount";
    wrap.appendChild(mount);
    grid.appendChild(wrap);
    return mount;
  }

  const W = 260, H = 190, padL = 34, padB = 22, padT = 8, padR = 8;
  const plotW = W - padL - padR, plotH = H - padT - padB;

  function xScaleFor(dates) {
    const t0 = new Date(dates[0]).getTime(), t1 = new Date(dates[dates.length - 1]).getTime();
    return (d) => padL + ((new Date(d).getTime() - t0) / (t1 - t0)) * plotW;
  }

  function drawAxes(svg, dates, yTicks, yMax, yFmt) {
    const x = xScaleFor(dates);
    yTicks.forEach((t) => {
      const gy = padT + plotH - (t / yMax) * plotH;
      el("line", { class: "grid-line", x1: padL, x2: W - padR, y1: gy, y2: gy }, svg);
      textEl(padL - 6, gy + 3, yFmt(t), { class: "axis-label", "text-anchor": "end", "font-size": "9.5" }, svg);
    });
    const years = [...new Set(dates.map((d) => new Date(d).getFullYear()))];
    const step = Math.ceil(years.length / 4) || 1;
    years.filter((_, i) => i % step === 0).forEach((yr) => {
      const gx = x(yr + "-06-15");
      textEl(gx, H - 4, yr, { class: "axis-label", "text-anchor": "middle", "font-size": "9.5" }, svg);
    });
    el("line", { class: "axis-line", x1: padL, x2: padL, y1: padT, y2: padT + plotH }, svg);
  }

  function linePath(svg, dates, values, yMax, color, width, dash) {
    const x = xScaleFor(dates);
    const y = (v) => padT + plotH - (v / yMax) * plotH;
    let d = "";
    values.forEach((v, i) => {
      if (v == null) return;
      d += (d ? " L " : "M ") + x(dates[i]) + " " + y(v);
    });
    const attrs = { d, fill: "none", stroke: color, "stroke-width": width, "stroke-linejoin": "round", "stroke-linecap": "round" };
    if (dash) attrs["stroke-dasharray"] = dash;
    el("path", attrs, svg);
  }

  function hoverLayer(svg, dates, seriesList, yMax) {
    const x = xScaleFor(dates);
    const hit = el("rect", { x: padL, y: padT, width: plotW, height: plotH, fill: "transparent" }, svg);
    // pointer-events: none — this line is drawn after (so painted over) the
    // hit rect, and hover repositions it to sit right under the cursor's own
    // x-coordinate; without this it would then win hit-testing over the hit
    // rect at that exact pixel, firing a spurious pointerleave that hides
    // the tooltip the same pointermove just showed.
    const cross = el("line", { x1: 0, x2: 0, y1: padT, y2: padT + plotH, stroke: "var(--axis)", "stroke-width": 1, opacity: 0, "pointer-events": "none" }, svg);
    bindTooltipHover(hit, (ev) => {
      const rect = svg.getBoundingClientRect();
      const scale = rect.width / W;
      const mx = (ev.clientX - rect.left) / scale;
      let idx = 0, best = Infinity;
      dates.forEach((d, i) => { const dx = Math.abs(x(d) - mx); if (dx < best) { best = dx; idx = i; } });
      cross.setAttribute("x1", x(dates[idx]));
      cross.setAttribute("x2", x(dates[idx]));
      cross.setAttribute("opacity", 1);
      const rows = seriesList
        .filter((s) => s.values[idx] != null)
        .map((s) => ttRow(s.color, s.label, s.fmt(s.values[idx])));
      showTooltip(ev.clientX, ev.clientY, ttBox(new Date(dates[idx]).toLocaleDateString("en-AU", { year: "numeric", month: "short" }), rows));
    }, () => { cross.setAttribute("opacity", 0); hideTooltip(); });
  }

  // macro panel — an arbitrary number of series, all sharing one Y-axis,
  // aligned onto the first series' dates.
  (function () {
    const macroCfg = cfg.macroPanel;
    const mount = drawPanel(macroCfg.title);
    const baseSeries = macroCfg.series[0];
    const dates = data.macro[baseSeries.key].map((d) => d.date).filter((d) => d >= START);
    const seriesValues = macroCfg.series.map((s) => {
      const byDate = new Map(data.macro[s.key].map((d) => [d.date, d.value]));
      return dates.map((d) => (byDate.has(d) ? byDate.get(d) : null));
    });
    // Single niceTicks call — see line_chart.js for why calling it twice
    // (once on the raw max, again on that result) can flip the step size at
    // certain boundary values and render a tick off the top of the chart.
    const macroTicks = niceTicks(0, Math.max(...seriesValues.flat().filter((v) => v != null)), 4);
    const yMax = macroTicks[macroTicks.length - 1];
    const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H }, mount);
    drawAxes(svg, dates, macroTicks, yMax, (v) => v + "%");
    macroCfg.series.forEach((s, i) => linePath(svg, dates, seriesValues[i], yMax, colorVar(s.color), 2, null));
    hoverLayer(svg, dates, macroCfg.series.map((s, i) => ({
      label: s.label,
      color: colorVar(s.color),
      values: seriesValues[i],
      fmt: (v) => v.toFixed(s.valueDecimals == null ? 1 : s.valueDecimals) + (s.valueSuffix || ""),
    })), yMax);
  })();

  occPanels.forEach((p) => {
    const mount = drawPanel(p.title);
    const rows = data[p.key].filter((d) => d.date >= START);
    const dates = rows.map((d) => d.date);
    const raw = rows.map((d) => d.value);
    const smoothed = rollingMeanCentered(raw, 5);

    let panelTicks, panelYMax;
    if (data.sharedYAxis) {
      panelTicks = sharedOccTicks;
      panelYMax = sharedOccYMax;
    } else {
      panelTicks = niceTicks(0, Math.max(...raw), 4);
      panelYMax = panelTicks[panelTicks.length - 1];
    }

    // tech_jobs_in_australia.csv's Count column is already reported in
    // thousands of people (same column the Tech Jobs gauge multiplies by
    // 1000 to get a headcount) — so an axis tick of "200" is 200,000
    // people, not 200. Suffix "K" unconditionally to make that legible
    // rather than reading as a bare, much-too-small headcount.
    const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H }, mount);
    drawAxes(svg, dates, panelTicks, panelYMax, (v) => Math.round(v) + "K");
    linePath(svg, dates, raw, panelYMax, "var(--ink-muted)", 1.5, "4 3");
    linePath(svg, dates, smoothed, panelYMax, "var(--cat-3)", 2, null);
    hoverLayer(svg, dates, [
      { label: "Smoothed", color: "var(--cat-3)", values: smoothed, fmt: (v) => formatCount(v) },
      { label: "Raw count", color: "var(--ink-muted)", values: raw, fmt: (v) => formatCount(v) },
    ], panelYMax);
  });

  const macroByDate = cfg.macroPanel.series.map((s) => new Map(data.macro[s.key].map((d) => [d.date, d.value])));
  const occByDate = occPanels.map((p) => new Map(data[p.key].map((d) => [d.date, d.value])));
  const tableDates = data[occPanels[0].key].filter((d) => d.date >= START).map((d) => d.date);
  const tableCols = ["Date", ...cfg.macroPanel.series.map((s) => s.label), ...occPanels.map((p) => p.title)];
  const tableRows = tableDates.map((d) => [
    d,
    ...macroByDate.map((m, i) => (m.has(d) ? m.get(d).toFixed(cfg.macroPanel.series[i].valueDecimals == null ? 1 : cfg.macroPanel.series[i].valueDecimals) : "")),
    ...occByDate.map((m) => (m.has(d) ? formatCount(m.get(d)) : "")),
  ]);
  registerDownload("sm", cfg.downloadFilename, tableCols, tableRows);
}

renderSmallMultiples();
wireDownloadButtons();
