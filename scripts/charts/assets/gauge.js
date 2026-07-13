// GAUGE — a single KPI card (title, big current value, "Target: X" pill,
// description) rather than a progress-arc gauge. A semi-circle needle can't
// meaningfully show a metric that's already met or exceeded its target
// (needle position would exceed the arc), so this reads the actual
// current/target values directly instead. All dataset-specific values come
// from DATA.gauge.config/.data, built in build_charts.py's GAUGE_CONFIG.
//
// g.description may use "**bold**" markdown-style emphasis around key
// figures (e.g. "now contributes **8.9%** of GDP") — parsed below, not
// treated as literal asterisks.
function renderGauges() {
  const cfg = DATA.gauge.config;
  const g = DATA.gauge.data[0];
  applyChromeConfig(cfg);

  document.getElementById("kpi-title").textContent = g.label;
  document.getElementById("kpi-value").textContent = g.currentLabel;

  const icon = document.getElementById("kpi-icon");
  icon.innerHTML = "";
  const iconColor = colorVar("cat-4");
  const svg = el("svg", { viewBox: "0 0 28 28" }, icon);
  el("circle", { cx: 14, cy: 14, r: 12, fill: "none", stroke: iconColor, "stroke-width": 2 }, svg);
  el("path", {
    d: "M9 14.5 L12.5 18 L19 10.5", fill: "none", stroke: iconColor,
    "stroke-width": 2.2, "stroke-linecap": "round", "stroke-linejoin": "round",
  }, svg);

  // g.value is progress toward target as a percentage (see build_charts.py)
  // — >= 100 means the target has actually been met or exceeded, which is
  // the only case that gets the "good" pill styling.
  const met = g.value >= 100;
  const pill = document.getElementById("kpi-pill");
  pill.textContent = "Target: " + g.targetLabel;
  pill.className = "kpi-pill" + (met ? " kpi-pill--good" : "");

  const desc = document.getElementById("kpi-description");
  desc.textContent = "";
  (g.description || "").split("**").forEach((part, i) => {
    if (!part) return;
    if (i % 2 === 1) {
      const strong = document.createElement("strong");
      strong.textContent = part;
      desc.appendChild(strong);
    } else {
      desc.appendChild(document.createTextNode(part));
    }
  });
}

renderGauges();
