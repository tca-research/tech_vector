// INTERACTIVE LINE CHART — single or multi-select filter, direct end labels, crosshair
// All dataset-specific values (default series, filter mode, palette,
// formatting, text) come from DATA.interactiveLine.config, built in
// build_charts.py's INTERACTIVE_LINE_CONFIG.
function renderInteractiveLine() {
  const cfg = DATA.interactiveLine.config;
  const data = DATA.interactiveLine.data;
  applyChromeConfig(cfg);

  const fmt = cfg.valueFormat || {};
  const formatShort = (v) => {
    if (Math.abs(v) < (fmt.divisor || 1000)) return String(Math.round(v));
    return Math.round(v / (fmt.divisor || 1000)) + (fmt.suffix || "");
  };
  const formatFull = (v) => Math.round(v).toLocaleString("en-AU");

  const allSeries = Object.keys(data.series);
  const palette = cfg.palette.map(colorVar);
  const mount = document.getElementById("line-chart");
  const note = document.getElementById("line-filter-note");
  const filterMount = document.getElementById("line-filter-mount");

  const W = 900, H = 440, padL = 56, padR = 132, padT = 16, padB = 46;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const dates = data.dates.map(monthYearToDate);
  const x = (d) => padL + ((d.getTime() - dates[0].getTime()) / (dates[dates.length - 1].getTime() - dates[0].getTime())) * plotW;

  // Colors are assigned per-series to a fixed palette "slot" and held there
  // for as long as that series stays selected — never reassigned by
  // position in the current selection. Otherwise unchecking one series
  // would repaint the others, which breaks "color follows the entity, not
  // its rank" the moment a user toggles anything.
  const seriesColor = new Map();
  function assignColor(name) {
    if (seriesColor.has(name)) return;
    const used = new Set(seriesColor.values());
    const free = palette.find((c) => !used.has(c));
    if (free) seriesColor.set(name, free);
  }
  function releaseColor(name) {
    seriesColor.delete(name);
  }

  function draw(selection) {
    // Stable display order (not selection order) so the legend/lines don't
    // reshuffle as items are toggled — only color assignment (above) needs
    // to be selection-independent; display order is free to just follow the
    // source column order.
    const names = allSeries.filter((n) => selection.includes(n));

    const allVals = names.flatMap((n) => data.series[n].filter((v) => v != null));
    // Derive yMax from this single niceTicks call's own last tick — see
    // line_chart.js for why calling niceTicks twice can flip the step size
    // at certain boundary values and render a tick off the top of the chart.
    const yTicks = niceTicks(0, Math.max(1, ...allVals), 5);
    const yMax = yTicks[yTicks.length - 1];
    const y = (v) => padT + plotH - (v / yMax) * plotH;

    mount.innerHTML = "";
    const svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H }, mount);

    yTicks.forEach((t) => {
      const gy = y(t);
      el("line", { class: "grid-line", x1: padL, x2: W - padR, y1: gy, y2: gy }, svg);
      textEl(padL - 8, gy + 4, formatShort(t), { class: "axis-label", "text-anchor": "end" }, svg);
    });
    el("line", { class: "axis-line", x1: padL, x2: padL, y1: padT, y2: padT + plotH }, svg);

    const yearSpan = dates[dates.length - 1].getFullYear() - dates[0].getFullYear();
    const tickEvery = Math.max(1, Math.round(yearSpan / 9));
    for (let yr = dates[0].getFullYear(); yr <= dates[dates.length - 1].getFullYear(); yr += tickEvery) {
      const gx = x(new Date(yr, 0, 1));
      if (gx < padL || gx > W - padR) continue;
      const t = textEl(gx, H - padB + 16, "Jan " + yr, { class: "axis-label", "text-anchor": "end" }, svg);
      t.setAttribute("transform", "rotate(-30 " + gx + " " + (H - padB + 16) + ")");
    }

    const seriesInfo = [];
    names.forEach((name) => {
      const color = seriesColor.get(name) || palette[0];
      const values = data.series[name];
      let d = "";
      let lastX = null, lastY = null, lastV = null;
      values.forEach((v, j) => {
        if (v == null) return;
        const px = x(dates[j]), py = y(v);
        d += (d ? " L " : "M ") + px + " " + py;
        lastX = px; lastY = py; lastV = v;
      });
      el("path", { d, fill: "none", stroke: color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
      if (lastX != null) {
        el("circle", { cx: lastX, cy: lastY, r: 4, fill: color, stroke: "var(--surface)", "stroke-width": 2 }, svg);
      }
      seriesInfo.push({ name, color, values, lastX, lastY, lastV });
    });

    // Direct end labels are this chart's only identity mechanism (no
    // legend row — it would just duplicate these) — only when few enough
    // to avoid collision, which in practice is always true since this is
    // also the max number of series that can ever be concurrently shown.
    if (names.length <= palette.length) {
      const placed = [];
      seriesInfo
        .filter((s) => s.lastY != null)
        .sort((a, b) => a.lastY - b.lastY)
        .forEach((s) => {
          let ly = s.lastY;
          for (const p of placed) if (Math.abs(p - ly) < 16) ly = p + 16;
          placed.push(ly);
          if (ly !== s.lastY) {
            el("line", { x1: s.lastX + 6, x2: s.lastX + 16, y1: s.lastY, y2: ly, stroke: s.color, "stroke-width": 1, opacity: 0.5 }, svg);
          }
          const t = textEl(s.lastX + 10, ly + 4, s.name, { class: "end-label", fill: s.color }, svg);
          wrapEndLabel(t, s.name, padR - 16);
        });
    }

    // Greedy word-wrap by estimated character width, not word count — a
    // two-word name can still be too long to fit ("Information Technology"
    // overflowed past the card edge under the old ">2 words" rule, and with
    // no legend row as a fallback, a clipped label means that series has no
    // identity at all).
    function wrapEndLabel(textNode, str, maxWidth) {
      const maxCharsPerLine = Math.max(8, Math.floor(maxWidth / 6.2));
      if (str.length <= maxCharsPerLine) return;
      const words = str.split(" ");
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
      if (lines.length <= 1) return;

      textNode.textContent = "";
      const baseX = textNode.getAttribute("x"), baseY = +textNode.getAttribute("y");
      const lineHeight = 14;
      lines.forEach((l, i) => {
        el("tspan", { x: baseX, dy: i === 0 ? 0 : lineHeight }, textNode).textContent = l;
      });
      textNode.setAttribute("y", baseY - (lineHeight * (lines.length - 1)) / 2);
    }

    // hover crosshair + shared tooltip
    const hit = el("rect", { x: padL, y: padT, width: plotW, height: plotH, fill: "transparent" }, svg);
    // pointer-events: none — see small_multiples.js's identical crosshair for
    // why: without it, hover repositioning this line under the cursor makes
    // it win hit-testing over the hit rect beneath, firing a spurious
    // pointerleave that hides the tooltip the same pointermove just showed.
    const cross = el("line", { x1: 0, x2: 0, y1: padT, y2: padT + plotH, stroke: "var(--axis)", "stroke-width": 1, opacity: 0, "pointer-events": "none" }, svg);
    bindTooltipHover(hit, (ev) => {
      const rect = svg.getBoundingClientRect();
      const scale = rect.width / W;
      const mx = (ev.clientX - rect.left) / scale;
      let idx = 0, best = Infinity;
      dates.forEach((d, i) => { const dx = Math.abs(x(d) - mx); if (dx < best) { best = dx; idx = i; } });
      cross.setAttribute("x1", x(dates[idx])); cross.setAttribute("x2", x(dates[idx])); cross.setAttribute("opacity", 1);
      const rows = seriesInfo
        .filter((s) => s.values[idx] != null)
        .map((s) => ttRow(s.color, s.name, formatFull(s.values[idx])));
      if (rows.length) {
        showTooltip(ev.clientX, ev.clientY, ttBox(data.dates[idx], rows));
      }
    }, () => { cross.setAttribute("opacity", 0); hideTooltip(); });

    registerDownload(
      "line",
      cfg.downloadFilename,
      ["Date"].concat(names),
      data.dates.map((dt, i) => [dt].concat(names.map((n) => (data.series[n][i] != null ? formatFull(data.series[n][i]) : ""))))
    );
  }

  // ---------------------------------------------------------------------
  // Single-select: a plain dropdown, exactly one series at a time.
  // ---------------------------------------------------------------------
  function buildSingleSelect() {
    filterMount.innerHTML = "";
    const select = document.createElement("select");
    select.className = "filter-select";
    allSeries.forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      select.appendChild(opt);
    });
    const initial = cfg.defaultSeries[0] || allSeries[0];
    select.value = initial;
    assignColor(initial);
    select.addEventListener("change", () => {
      seriesColor.clear();
      assignColor(select.value);
      note.textContent = "Showing " + select.value + ".";
      draw([select.value]);
    });
    filterMount.appendChild(select);
    note.textContent = "Showing " + initial + ".";
    draw([initial]);
  }

  // ---------------------------------------------------------------------
  // Multi-select: a checkbox-list dropdown, up to len(palette) series at
  // once — the palette only has that many CVD-safe hues, so once the cap
  // is reached, unchecked boxes disable instead of silently reusing a color.
  // ---------------------------------------------------------------------
  function buildMultiSelect() {
    filterMount.innerHTML = "";
    const checked = new Set(cfg.defaultSeries.filter((n) => allSeries.includes(n)).slice(0, palette.length));
    checked.forEach(assignColor);

    const wrap = document.createElement("div");
    wrap.className = "multiselect";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "multiselect-button";
    const label = document.createElement("span");
    const chevron = document.createElement("span");
    chevron.className = "chevron";
    chevron.textContent = "▾";
    button.appendChild(label);
    button.appendChild(chevron);

    const panel = document.createElement("div");
    panel.className = "multiselect-panel";

    function updateLabel() {
      label.textContent = checked.size ? checked.size + " of " + allSeries.length + " selected" : "None selected";
    }
    function updateDisabled() {
      const atCap = checked.size >= palette.length;
      panel.querySelectorAll("input[type=checkbox]").forEach((cb) => {
        if (!checked.has(cb.value)) cb.disabled = atCap;
      });
    }
    function updateNote() {
      note.textContent = checked.size >= palette.length
        ? "Showing the maximum of " + palette.length + " series — uncheck one to add another."
        : checked.size + " of " + allSeries.length + " series shown.";
    }

    allSeries.forEach((name) => {
      const row = document.createElement("label");
      row.className = "multiselect-option";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = name;
      cb.checked = checked.has(name);
      cb.addEventListener("change", () => {
        if (cb.checked) { checked.add(name); assignColor(name); }
        else { checked.delete(name); releaseColor(name); }
        updateLabel();
        updateDisabled();
        updateNote();
        draw(Array.from(checked));
      });
      row.appendChild(cb);
      const span = document.createElement("span");
      span.textContent = name;
      row.appendChild(span);
      panel.appendChild(row);
    });

    button.addEventListener("click", (ev) => {
      ev.stopPropagation();
      panel.classList.toggle("open");
    });
    document.addEventListener("click", (ev) => {
      if (!wrap.contains(ev.target)) panel.classList.remove("open");
    });

    wrap.appendChild(button);
    wrap.appendChild(panel);
    filterMount.appendChild(wrap);

    updateLabel();
    updateDisabled();
    updateNote();
    draw(Array.from(checked));
  }

  // ---------------------------------------------------------------------
  // Search: a free-text type-ahead ("Enter series to show") — matches the
  // live Tech Vector site's interaction pattern. Selected series were meant
  // to double as removable legend chips, but this chart has no legend row
  // (direct end-of-line labels are its only identity mechanism, so a legend
  // would just duplicate them) — _removeSeries below is currently dead code
  // as a result. Re-add a chip UI (or otherwise call filterMount
  // ._removeSeries) if this filterMode is ever turned back on.
  // ---------------------------------------------------------------------
  function buildSearchSelect() {
    filterMount.innerHTML = "";
    const checked = new Set(cfg.defaultSeries.filter((n) => allSeries.includes(n)).slice(0, palette.length));
    checked.forEach(assignColor);

    const wrap = document.createElement("div");
    wrap.className = "series-search";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "series-search-input";
    input.placeholder = "Enter series to show";
    input.autocomplete = "off";
    const suggestions = document.createElement("div");
    suggestions.className = "series-suggestions";

    function updateNote() {
      note.textContent = checked.size >= palette.length
        ? "Showing the maximum of " + palette.length + " series — remove one (×) to add another."
        : checked.size + " of " + allSeries.length + " series shown.";
    }

    function renderSuggestions() {
      suggestions.innerHTML = "";
      if (checked.size >= palette.length) {
        const msg = document.createElement("div");
        msg.className = "series-suggestion disabled";
        msg.textContent = "Maximum of " + palette.length + " series shown.";
        suggestions.appendChild(msg);
        suggestions.classList.add("open");
        return;
      }
      const q = input.value.trim().toLowerCase();
      const matches = allSeries.filter((n) => !checked.has(n) && (q === "" || n.toLowerCase().includes(q)));
      if (!matches.length) {
        suggestions.classList.remove("open");
        return;
      }
      matches.slice(0, 8).forEach((name) => {
        const item = document.createElement("div");
        item.className = "series-suggestion";
        item.textContent = name;
        // mousedown, not click — fires before the input's blur hides the list
        item.addEventListener("mousedown", (ev) => { ev.preventDefault(); addSeries(name); });
        suggestions.appendChild(item);
      });
      suggestions.classList.add("open");
    }

    function addSeries(name) {
      checked.add(name);
      assignColor(name);
      input.value = "";
      renderSuggestions();
      updateNote();
      draw(Array.from(checked));
    }
    function removeSeries(name) {
      checked.delete(name);
      releaseColor(name);
      renderSuggestions();
      updateNote();
      draw(Array.from(checked));
    }
    filterMount._removeSeries = removeSeries;

    input.addEventListener("input", renderSuggestions);
    input.addEventListener("focus", renderSuggestions);
    input.addEventListener("blur", () => suggestions.classList.remove("open"));
    input.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter" || checked.size >= palette.length) return;
      const q = input.value.trim().toLowerCase();
      if (!q) return;
      const exact = allSeries.find((n) => !checked.has(n) && n.toLowerCase() === q);
      const firstMatch = allSeries.find((n) => !checked.has(n) && n.toLowerCase().includes(q));
      const pick = exact || firstMatch;
      if (pick) { addSeries(pick); ev.preventDefault(); }
    });

    wrap.appendChild(input);
    wrap.appendChild(suggestions);
    filterMount.appendChild(wrap);

    updateNote();
    draw(Array.from(checked));
  }

  if (cfg.filterMode === "single") {
    buildSingleSelect();
  } else if (cfg.filterMode === "search") {
    buildSearchSelect();
  } else {
    buildMultiSelect();
  }
}

renderInteractiveLine();
wireDownloadButtons();
