const SVGNS = "http://www.w3.org/2000/svg";

// Applies the title/source/caption fields every chart's Python config
// carries, so per-dataset text lives in build_charts.py only — none of it
// is hardcoded in these JS files.
function colorVar(token) {
  return "var(--" + token + ")";
}
function colorTextVar(token) {
  return "var(--" + token + "-text)";
}
function applyChromeConfig(cfg) {
  if (cfg.pageTitle) document.title = cfg.pageTitle;
  const titleEl = document.getElementById("chart-title");
  if (titleEl) titleEl.textContent = cfg.title || "";
  const sourceEl = document.getElementById("chart-source");
  if (sourceEl) sourceEl.textContent = cfg.source || "";
  const captionEl = document.getElementById("chart-caption");
  if (captionEl && cfg.caption) captionEl.textContent = cfg.caption;
}

// ---------- generic helpers ----------------------------------------------
function el(tag, attrs, parent) {
  const n = document.createElementNS(SVGNS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}
function textEl(x, y, str, attrs, parent) {
  const t = el("text", Object.assign({ x, y }, attrs), parent);
  t.textContent = str; // untrusted-safe: textContent, never innerHTML
  return t;
}
function niceStep(rawStep) {
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const norm = rawStep / mag;
  let step;
  if (norm < 1.5) step = 1;
  else if (norm < 3) step = 2;
  else if (norm < 7) step = 5;
  else step = 10;
  return step * mag;
}
function niceTicks(min, max, count) {
  const step = niceStep((max - min) / count || 1);
  const start = Math.floor(min / step) * step;
  const end = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = start; v <= end + step * 1e-6; v += step) ticks.push(Math.round(v * 1e6) / 1e6);
  return ticks;
}
function formatMoney(v) {
  return "$" + Math.round(v / 1000) + "K";
}
function formatCount(v) {
  return Math.round(v).toLocaleString("en-AU");
}
function formatCountShort(v) {
  // Independent-axis small multiples can have a max well under 1000 (e.g. a
  // ~100-160 range) — dividing everything by 1000 there would print "0K" on
  // every tick, so only use the K suffix once it's actually needed.
  if (Math.abs(v) < 1000) return String(Math.round(v));
  return Math.round(v / 1000) + "K";
}
function rollingMeanCentered(values, window) {
  const half = Math.floor(window / 2);
  return values.map((_, i) => {
    const lo = Math.max(0, i - half);
    const hi = Math.min(values.length - 1, i + half);
    let sum = 0, n = 0;
    for (let j = lo; j <= hi; j++) {
      if (values[j] != null) { sum += values[j]; n++; }
    }
    return n ? sum / n : null;
  });
}
function monthYearToDate(my) {
  // "August 1986" -> Date
  const [mon, yr] = my.split(" ");
  return new Date(Date.parse(mon + " 1, " + yr));
}
// All date fields in chart-data.json MUST already be ISO "YYYY-MM-DD" or
// "YYYY-MM" strings by the time they reach this page (see DATA_FORMAT.md).
// This guard exists because that exact mistake shipped once already: an
// ABS-style "Aug-06" string handed to `new Date()` silently parses as
// month=Aug, day=06, year=2000 — not August 2006 — which produces a
// non-monotonic x-scale and a shredded, zig-zagging line with no error or
// warning anywhere. Fail loudly instead.
function assertIsoDate(d) {
  if (!/^\d{4}-\d{2}(-\d{2})?$/.test(d)) {
    throw new Error("Expected an ISO date (YYYY-MM-DD or YYYY-MM), got: " + JSON.stringify(d) +
      ". See DATA_FORMAT.md — non-ISO date strings parse silently wrong in JS.");
  }
  return d;
}

// shared tooltip -----------------------------------------------------------
const tooltipEl = document.getElementById("tooltip");
function showTooltip(x, y, html) {
  tooltipEl.innerHTML = "";
  tooltipEl.appendChild(html);
  tooltipEl.classList.add("visible");
  const pad = 14;
  let left = x + pad, top = y + pad;
  const rect = tooltipEl.getBoundingClientRect();
  if (left + rect.width > window.innerWidth - 8) left = x - rect.width - pad;
  if (top + rect.height > window.innerHeight - 8) top = y - rect.height - pad;
  tooltipEl.style.transform = "translate(" + left + "px," + top + "px)";
}
function hideTooltip() {
  tooltipEl.classList.remove("visible");
}
function ttRow(color, label, value) {
  const row = document.createElement("div");
  row.className = "tt-row";
  if (color) {
    const key = document.createElement("span");
    key.className = "tt-key";
    key.style.background = color;
    row.appendChild(key);
  }
  const lab = document.createElement("span");
  lab.textContent = label;
  row.appendChild(lab);
  if (value !== undefined) {
    const val = document.createElement("span");
    val.className = "tt-value";
    val.style.marginLeft = "auto";
    val.style.paddingLeft = "10px";
    val.textContent = value;
    row.appendChild(val);
  }
  return row;
}
function ttBox(titleText, rows) {
  const box = document.createElement("div");
  if (titleText) {
    const t = document.createElement("div");
    t.className = "tt-title";
    t.textContent = titleText;
    box.appendChild(t);
  }
  rows.forEach((r) => box.appendChild(r));
  return box;
}

function legendItem(container, color, label, lineStyle) {
  const item = document.createElement("div");
  item.className = "legend-item";
  const sw = document.createElement("span");
  sw.className = "legend-swatch" + (lineStyle ? " line" : "");
  sw.style.background = color;
  item.appendChild(sw);
  const lab = document.createElement("span");
  lab.textContent = label;
  item.appendChild(lab);
  container.appendChild(item);
}

// csv download — replaces the table-view toggle with a direct data export
const downloadRegistry = {};
function csvCell(v) {
  const s = String(v);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
function registerDownload(key, filename, columns, rows) {
  const csv = [columns, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n");
  downloadRegistry[key] = { filename, csv };
}
function wireDownloadButtons() {
  document.querySelectorAll(".download-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const entry = downloadRegistry[btn.dataset.target];
      if (!entry) return;
      const blob = new Blob([entry.csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = entry.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    });
  });
}
