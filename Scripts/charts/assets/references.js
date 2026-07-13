// REFERENCES — the citation list shown at the bottom of the Tech Vector
// page, replicated here as a config-driven "chart" so it rebuilds alongside
// everything else. Each entry's year/viewed date is already resolved to a
// display string by build_charts.py's load_references_data (dynamic ones
// tracking the build date, fixed ones — e.g. a specific data vintage —
// passed through unchanged) — this file just lays the text out.
function renderReferences() {
  const cfg = DATA.references.config;
  const entries = DATA.references.data;
  applyChromeConfig(cfg);

  const list = document.getElementById("reference-list");
  list.innerHTML = "";

  entries.forEach((e) => {
    const li = document.createElement("li");
    li.className = "reference-item";

    const prefix = document.createElement("span");
    prefix.textContent = e.author + " " + e.yearDisplay + ", ";
    li.appendChild(prefix);

    const em = document.createElement("em");
    em.textContent = e.title;
    li.appendChild(em);

    const trailingParts = [];
    if (e.publisher) trailingParts.push(e.publisher);
    if (e.viewedDisplay) trailingParts.push("viewed " + e.viewedDisplay);
    const tail = document.createElement("span");
    tail.textContent = (trailingParts.length ? ", " + trailingParts.join(", ") : "") + (e.url ? ", " : ".");
    li.appendChild(tail);

    if (e.url) {
      const a = document.createElement("a");
      a.href = e.url;
      a.textContent = e.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      li.appendChild(a);
      const period = document.createElement("span");
      period.textContent = ".";
      li.appendChild(period);
    }

    list.appendChild(li);
  });
}

renderReferences();
