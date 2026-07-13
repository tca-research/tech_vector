// STATUS — a small "Last updated / Next update" card, dates computed from
// the same 8-week cycle as .github/workflows/rebuild-data.yml (see
// build_charts.py's load_status_data). No download button/source line —
// this chart's only content is the two dates themselves.
function renderStatus() {
  const cfg = DATA.status.config;
  const s = DATA.status.data[0];
  applyChromeConfig(cfg);

  const row = document.getElementById("status-row");
  row.innerHTML = "";

  function item(label, value) {
    const wrap = document.createElement("div");
    wrap.className = "status-item";
    const labelEl = document.createElement("span");
    labelEl.className = "status-label";
    labelEl.textContent = label;
    const valueEl = document.createElement("span");
    valueEl.className = "status-value";
    valueEl.textContent = value;
    wrap.appendChild(labelEl);
    wrap.appendChild(valueEl);
    row.appendChild(wrap);
  }

  if (s.lastUpdated) {
    item("Last updated", s.lastUpdated);
  }
  item("Next update", s.nextUpdate);
  item("Comments or concerns? Email research@techcouncil.com.au.", "");
}

renderStatus();
