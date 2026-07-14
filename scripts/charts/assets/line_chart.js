// LINE CHART — a single time series, direct end label, crosshair tooltip.
// A single series needs no legend (the title already names it). All
// dataset-specific values (line color, end label, value formatting) come
// from DATA.line.config, built in build_charts.py's LINE_CONFIG-style
// configs — point this at any {dates:[...], values:[...]} shape and it works.
function renderLineChart() {
  const cfg = DATA.line.config;
  const data = DATA.line.data;
  applyChromeConfig(cfg);

  const fmt = cfg.valueFormat || {};
  const formatValue = (v) => {
    const scaled = v / (fmt.divisor || 1);
    const decimals = fmt.decimals != null ? fmt.decimals : 0;
    const text = decimals > 0 ? scaled.toFixed(decimals) : Math.round(scaled).toLocaleString("en-AU");
    return (fmt.prefix || "") + text + (fmt.suffix || "");
  };

  const mount = document.getElementById("line-chart");
  const color = colorVar(cfg.lineColor || "cat-3");

  const W = 900, H = 400, padL = 56, padR = 180, padT = 26, padB = 40;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const dates = data.dates.map((d) => new Date(d));
  const x = (d) => padL + ((d.getTime() - dates[0].getTime()) / (dates[dates.length - 1].getTime() - dates[0].getTime())) * plotW;

  const vals = data.values.filter((v) => v != null);
  // Derive yMax from this single niceTicks call's own last tick — calling
  // niceTicks a second time on that yMax can flip the step size at certain
  // boundary values (e.g. max/5 lands just under a bucket edge but
  // yMax/5 lands just over it), producing a coarser top tick that exceeds
  // the y-scale's actual domain and renders off the top of the chart.
  const yTicks = niceTicks(0, Math.max(1, ...vals), 5);
  const yMax = yTicks[yTicks.length - 1];
  const y = (v) => padT + plotH - (v / yMax) * plotH;

  mount.innerHTML = "";
  const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img", "aria-label": cfg.title }, mount);

  yTicks.forEach((t) => {
    const gy = y(t);
    el("line", { class: "grid-line", x1: padL, x2: W - padR, y1: gy, y2: gy }, svg);
    textEl(padL - 8, gy + 4, formatValue(t), { class: "axis-label", "text-anchor": "end" }, svg);
  });
  el("line", { class: "axis-line", x1: padL, x2: padL, y1: padT, y2: padT + plotH }, svg);

  const yearSpan = dates[dates.length - 1].getFullYear() - dates[0].getFullYear();
  const tickEvery = Math.max(1, Math.round(yearSpan / 9));
  for (let yr = dates[0].getFullYear(); yr <= dates[dates.length - 1].getFullYear(); yr += tickEvery) {
    const gx = x(new Date(yr, 0, 1));
    if (gx < padL || gx > W - padR) continue;
    textEl(gx, H - padB + 20, String(yr), { class: "axis-label", "text-anchor": "middle" }, svg);
  }

  let d = "", lastX = null, lastY = null;
  data.values.forEach((v, i) => {
    if (v == null) return;
    const px = x(dates[i]), py = y(v);
    d += (d ? " L " : "M ") + px + " " + py;
    lastX = px; lastY = py;
  });
  el("path", { d, fill: "none", stroke: color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
  if (lastX != null) {
    el("circle", { cx: lastX, cy: lastY, r: 4, fill: color, stroke: "var(--surface)", "stroke-width": 2 }, svg);
    if (cfg.endLabel) {
      // Greedy word-wrap to fit the fixed right margin — a direct end label
      // can be a long axis-style phrase (e.g. "% of labour force in tech
      // occupations (smoothed)"), not just a short series name.
      const maxCharsPerLine = Math.max(10, Math.floor((padR - 20) / 6.2));
      const words = cfg.endLabel.split(" ");
      const lines = [];
      let line = "";
      words.forEach((w) => {
        const candidate = line ? line + " " + w : w;
        if (candidate.length > maxCharsPerLine && line) {
          lines.push(line);
          line = w;
        } else {
          line = candidate;
        }
      });
      if (line) lines.push(line);

      const lineHeight = 13;
      const baseX = lastX + 10;
      const startY = lastY - ((lines.length - 1) * lineHeight) / 2;
      const t = el("text", { x: baseX, y: startY, class: "end-label", fill: color }, svg);
      lines.forEach((l, i) => {
        el("tspan", { x: baseX, dy: i === 0 ? 0 : lineHeight }, t).textContent = l;
      });
    }
  }

  const hit = el("rect", { x: padL, y: padT, width: plotW, height: plotH, fill: "transparent" }, svg);
  // pointer-events: none — see small_multiples.js's identical crosshair for
  // why: without it, hover repositioning this line under the cursor makes it
  // win hit-testing over the hit rect beneath, firing a spurious
  // pointerleave that hides the tooltip the same pointermove just showed.
  const cross = el("line", { x1: 0, x2: 0, y1: padT, y2: padT + plotH, stroke: "var(--axis)", "stroke-width": 1, opacity: 0, "pointer-events": "none" }, svg);
  bindTooltipHover(hit, (ev) => {
    const rect = svg.getBoundingClientRect();
    const scale = rect.width / W;
    const mx = (ev.clientX - rect.left) / scale;
    let idx = 0, best = Infinity;
    dates.forEach((dt, i) => { const dx = Math.abs(x(dt) - mx); if (dx < best) { best = dx; idx = i; } });
    if (data.values[idx] == null) return;
    cross.setAttribute("x1", x(dates[idx])); cross.setAttribute("x2", x(dates[idx])); cross.setAttribute("opacity", 1);
    showTooltip(ev.clientX, ev.clientY, ttBox(data.dates[idx], [ttRow(color, cfg.endLabel || cfg.title, formatValue(data.values[idx]))]));
  }, () => { cross.setAttribute("opacity", 0); hideTooltip(); });

  registerDownload(
    "line",
    cfg.downloadFilename,
    ["Date", cfg.endLabel || cfg.title],
    data.dates.map((dt, i) => [dt, data.values[i] != null ? formatValue(data.values[i]) : ""])
  );
}

renderLineChart();
wireDownloadButtons();
