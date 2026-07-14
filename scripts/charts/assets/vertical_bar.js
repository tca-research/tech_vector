// VERTICAL BAR — a single value per category, drawn as upright bars (one
// category axis along the bottom, one shared value axis on the left).
// Reuses roundedRectPath from shared.js. All dataset-specific values come
// from DATA.verticalBar.config, built in build_charts.py's
// AVERAGE_REMUNERATION_CONFIG-style configs.
function renderVerticalBar() {
  const cfg = DATA.verticalBar.config;
  const data = DATA.verticalBar.data;
  applyChromeConfig(cfg);

  const fmt = cfg.valueFormat || {};
  const formatValue = (v) => {
    const scaled = v / (fmt.divisor || 1);
    const decimals = fmt.decimals != null ? fmt.decimals : 0;
    const text = decimals > 0 ? scaled.toFixed(decimals) : Math.round(scaled).toLocaleString("en-AU");
    return (fmt.prefix || "") + text + (fmt.suffix || "");
  };

  const mount = document.getElementById("vertical-bar-chart");
  const W = 900, H = 460, padL = 64, padR = 20, padT = 20, padB = 44;
  const plotW = W - padL - padR, plotH = H - padT - padB;

  const maxVal = Math.max(...data.map((d) => d.value));
  const ticks = niceTicks(0, maxVal * 1.15, 5);
  const yMax = ticks[ticks.length - 1];
  const y = (v) => padT + plotH - (v / yMax) * plotH;

  mount.innerHTML = "";
  const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img", "aria-label": cfg.title }, mount);

  ticks.forEach((t) => {
    const gy = y(t);
    el("line", { class: "grid-line", x1: padL, x2: W - padR, y1: gy, y2: gy }, svg);
    textEl(padL - 10, gy + 4, formatValue(t), { class: "axis-label", "text-anchor": "end" }, svg);
  });
  el("line", { class: "axis-line", x1: padL, x2: padL, y1: padT, y2: padT + plotH }, svg);

  const slotW = plotW / data.length;
  const barW = slotW * 0.5;
  const tableRows = [];

  data.forEach((d, i) => {
    const cx = padL + slotW * (i + 0.5);
    const barX = cx - barW / 2;
    const barTop = y(d.value);
    const barH = padT + plotH - barTop;
    const color = colorVar(d.color);
    const r = 6;
    const path = roundedRectPath(barX, barTop, barW, barH, { tl: r, tr: r, bl: 0, br: 0 });
    const bar = el("path", { d: path, fill: color }, svg);
    const hit = el("rect", { x: barX - 4, y: barTop - 2, width: barW + 8, height: barH + 4, fill: "transparent" }, svg);
    const valueLabel = formatValue(d.value);
    [bar, hit].forEach((node) => {
      node.style.cursor = "pointer";
      bindTooltipHover(node, (ev) => {
        bar.style.filter = "brightness(1.08)";
        showTooltip(ev.clientX, ev.clientY, ttBox(d.category, [ttRow(color, "Value", valueLabel)]));
      }, () => { bar.style.filter = ""; hideTooltip(); });
    });
    textEl(cx, barTop + 24, valueLabel, { "text-anchor": "middle", "font-size": "14", "font-weight": "700", fill: "#fff" }, svg);
    textEl(cx, padT + plotH + 22, d.category, { "text-anchor": "middle", "font-size": "12.5", "font-weight": "600", fill: "var(--ink-primary)" }, svg);
    tableRows.push([d.category, valueLabel]);
  });

  registerDownload("verticalBar", cfg.downloadFilename, ["Category", "Value"], tableRows);
}

renderVerticalBar();
wireDownloadButtons();
