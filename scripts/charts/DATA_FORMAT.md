# Chart data format

`build_charts.py` generates standalone HTML files, one per chart (19 files
across 14 chart types, registered in the `CHARTS` list at the bottom of
the file). Each chart's JS expects its input JSON in a specific shape. This
is the contract — if you change what feeds a chart (a new source CSV, a
different aggregation), match this shape or the chart will render with no
error and look wrong.

## Rule zero: never trust a CSV's row order

Every loader in `build_charts.py` re-sorts by the *parsed* date before
building chart JSON, even when the source CSV "looks" sorted. It isn't
always: `tech_jobs_occupations_over_time_WIDE-SIMPLE.csv` is sorted
alphabetically by its `"Month Year"` string column (August, August, ...,
December, December, ..., February, ...) — an artifact of `data_prep.py`'s
`pivot()` sorting its string index lexicographically, not chronologically.
A line chart built straight off that row order draws a path that jumps
between whichever months happen to be alphabetically adjacent, producing
long diagonal lines slicing across the whole chart — with no error, since
nothing here is actually invalid, just out of order. Sort by a real parsed
date, always, regardless of what order the file arrives in.

## The one rule that matters most: dates must be ISO

**Every date string handed to a chart must be `"YYYY-MM-DD"` or `"YYYY-MM"`.**
Never an ABS-style abbreviation like `"Aug-06"`.

This is not a style preference — it's a correctness requirement, and it fails
silently. In JavaScript:

```js
new Date("Aug-06")
// -> Sun Aug 06 2000 00:00:00  (day = 6, year defaults to 2000)
// NOT August 2006, and no error is thrown.
```

This exact bug shipped once already: the small-multiples chart's three
employment panels went through `new Date("Aug-06")`-style parsing, which
silently reinterpreted the two-digit year as a day-of-month. Every point
still rendered — just at the wrong, non-chronological x-position — so the
lines looked shredded/zig-zagging across the whole panel width, and the
x-axis showed a nonsensical single year ("2001") instead of a normal range.
Nothing crashed. Nothing warned. It just looked wrong.

**Where this matters in the pipeline:** `manual_data_prep.py` keeps the
`Date` column in its original ABS format (`"Aug-06"`) in the *cleaned* CSVs,
because that's the format WGEA/ABS exports use and downstream consumers may
expect it. `build_charts.py` is responsible for converting to ISO before
building any chart JSON — see `load_small_multiples_data()`'s
`pd.to_datetime(df["Date"], format="%b-%y").dt.strftime("%Y-%m-%d")` step,
and the same pattern in `load_tech_jobs_gauge_data()`. If you add a new
date-bearing source, convert it the same way, immediately after loading,
before it touches any chart-building code.

`build_charts.py` also calls `assert_iso_date()` on every date series before
handing it off, and `shared.js`'s `assertIsoDate()` re-checks on the JS side
in the small-multiples chart specifically (where the bug lived) — both will
throw loudly rather than render silently wrong. Don't remove either check;
add the same call anywhere else a new date column enters the pipeline.

## A second silent-failure class: mismatched units in a gauge's labels

The three gauges (`tech_jobs_gauge.html`, `tech_investment_gauge.html`,
`tech_sector_gdp_gauge.html`) show a "met target" (green) vs. "in progress"
(grey) pill. That status is *derived*, not hand-entered: `parse_metric_value()`
strips `$`/`%`/`k`/`M`/`B` off `current_label` and `target_label` and compares
the two numbers directly (`>=100%` of target ⇒ met).

This used to be a separately hand-entered "progress %" column, which could
silently drift out of sync with the labels — exactly what happened when
Tech Investment's `current_label` was updated to exceed its `target_label`
without updating that percentage to match (a percentage past 100% doesn't
fit on a semi-circle needle either, which is why the gauge was redesigned
as a flat KPI card instead of a needle). There's nothing to keep in sync now,
**provided `current_label` and `target_label` share the same unit** — both
`%`, both `$...B`, or both a `k`/`M` count. Mismatched units (current in `k`,
target in `M`) compare as plain numbers and silently produce the wrong
met/not-met status, with no error.

## Source lines: the `{year}` placeholder and "only stamp a new date when
data actually changed"

Most `source` config strings carry a `"({year})"` placeholder, e.g.
`"Source: WGEA ({year})."` — resolved to the actual build year in
`build_html()`. Two different things can happen to a chart's displayed
date, and they're driven by different logic:

- **The `{year}` in the source line** is for data that's "current as of
  last fetch" (WGEA, ABS, OECD headline pages, etc.) — it should track the
  build year. A source citing a fixed historical data vintage instead (e.g.
  `RND_CONFIG`'s `"Source: OECD (2021)."` — the actual OECD R&D figures are
  dated 2021, unrelated to when this repo last rebuilt) just omits the
  placeholder entirely and stays untouched forever. Don't add `{year}` to a
  source that means "this specific dataset's vintage."
- **The "Chart last updated on ..." footer text** and the matching row in
  `charts/chart_manifest.csv` only advance when that chart's *computed data*
  (or its source template's wording) actually differs from the previous
  build — see `read_previous_chart_state()` and the `data_unchanged` check
  in `main()`. Running `build_charts.py` again with no underlying CSV
  changes reuses the exact same date, rather than bumping every chart's
  timestamp on every run regardless of whether anything changed.

One exception: `references.html`'s entries marked `"viewed": True` compute
`viewedDisplay` from `now` on every run (`load_references_data`) — that's
deliberate, since a citation's "viewed" date is supposed to mean "as of the
last time this repo was rebuilt," not "as of the last time the reference
text itself changed."

If you add a new source string with a real "current as of fetch" meaning,
use `{year}`. If you add a hand-curated description that should read
differently only when its underlying figures change (most of them), you get
that behavior for free from the `data_unchanged` mechanism — no extra work
needed.

**A config's `title` does *not* share the source line's `{year}` machinery
automatically** — `{year}` there resolves against `build_year` (today's
build date), which is the wrong value for a title describing the date range
a chart's *data* actually covers (e.g. `INTERACTIVE_LINE_CONFIG`'s
`"Employed persons by tech occupation, 1986–{year}"`): the data can lag
behind the build date (a rebuild in the new year doesn't mean the ABS
release caught up to it), so using `build_year` would silently overstate the
range. Instead, `main()` computes `title_year` from that chart's own loaded
data (currently: `interactiveLine`'s last `dates` entry, parsed with its
`dateFormat`) and passes it to `build_html()`, which resolves `{year}` in
`title` from that instead. A chart adding `{year}` to its own `title` needs
the equivalent of that `title_year` computation added to its branch in
`main()`'s build loop — it isn't automatic the way the source line is.

## Per-chart data contracts

Each entry below is the shape of the list/dict a loader function returns —
i.e. `DATA.<key>.data` on the JS side, where `<key>` is the chart's `"key"`
in the `CHARTS` list (`DATA.<key>.config` is the matching CONFIG dict, with
`lastUpdated` and a resolved `source` added at build time).

### Gauges (`gauge.html`/`gauge.js`) — `key: "gauge"`, 3 standalone pages

`load_gauge_data()` (Tech Investment, Tech Sector GDP, from
`headline_metrics.csv`) and `load_tech_jobs_gauge_data()` (Tech Jobs, from
`tech_jobs_in_australia_cleaned.csv`) both return a **1-element list**:

```json
[{
  "label": "Tech Investment",
  "value": 193.5,
  "currentLabel": "8.9%",
  "targetLabel": "4.6%",
  "description": "The tech sector contributes **8.9%** to Australia's GDP, surpassing our **4.6%** target set in 2021.",
  "filledColor": "cat-3", "remainingColor": "cat-1", "needleColor": "cat-1",
  "currentBadgeColor": "cat-1", "targetBadgeColor": "cat-4"
}]
```

- `value`: derived progress-toward-target percentage (see the silent-failure
  note above) — **not** hand-entered; `>= 100` triggers the "met" (green)
  pill styling in `gauge.js`.
- `currentLabel` / `targetLabel`: display strings, same unit family (see
  above).
- `description`: plain text, but `**double asterisks**` around a substring
  render it bold — parsed client-side in `gauge.js`, not literal asterisks.
- The five `*Color` keys are palette tokens (`cat-1`..`cat-5`), matched by
  `label` from `GAUGE_CONFIG["colors"]`, falling back to `"defaultColors"`.
  (Currently only the decorative header icon uses a fixed brand color in
  the JS; these per-gauge colors are legacy from the old needle design and
  are otherwise unused by the KPI-card rendering — harmless to leave.)

### Bar chart (`bar_chart.html`/`bar_chart.js`) — `key: "bar"`, 2 pages

Shared by `BAR_CONFIG` (`bar_chart.html` output, from `tech_pay_quartiles.csv`)
and `WOMENS_PAY_CONFIG` (`womens_pay_scales_chart.html`, same source file,
different columns). `load_bar_data()` returns a list of records, one per row:

```json
{
  "category": "Q1 (Lower quartile)",
  "TCA Member Remuneration - Average": 119426.0,
  "Direct Tech Remuneration - Average": 97555.0,
  "Australian Average Remuneration - Average": 74895.0,
  "annotation": "Quartile 1 band include, on average, ..."
}
```

- `category`: exact row label, used as the category axis text — comes from
  whatever column `config["categoryColumn"]` names.
- One key per entry in `config["series"]`, named after that series'
  `"column"` value (**not** a fixed `tca`/`direct`/`aus`-style key — this
  chart is fully config-driven, so the series keys are whatever the config
  says, and both `BAR_CONFIG` and `WOMENS_PAY_CONFIG` use different real
  column names). Values are numeric — `money_to_float()` has already
  stripped `$`/`,` for dollar series; percentage series pass through as
  plain numbers (e.g. `47.5`, not `"47.5%"`).
- `annotation`: empty string `""` (not `null`, not `NaN`) when there's no
  callout text for a row (only used when `config["annotationColumn"]` is
  set — `WOMENS_PAY_CONFIG` sets it to `None` and disables the annotation
  column in the layout entirely).
- Row order is the display order, top to bottom.

### Scatter (`scatter.html`/`scatter.js`) — `key: "scatter"`

```json
{ "name": "Australia", "x": 0.704414164, "y": 0.438553423, "group": "Australia" }
```

- `x` / `y`: floats in `[0, 1]` — the chart's axes are hardcoded to that
  range. A value outside it will still render but past the plotted grid.
- `group` must be one of the `"value"` entries in `SCATTER_CONFIG["groups"]`
  (currently `"Australia"`, `"EMEA"`, `"Americas"`, `"Global Average"`,
  `"APAC"`) — anything else silently falls back to the last group's color,
  with no error.

### Interactive line chart (`interactive_line.html`/`interactive_line.js`) — `key: "interactiveLine"`

```json
{
  "dates": ["August 1986", "November 1986", ...],
  "series": {
    "Software Engineers": [20137.0, 24073.0, ...],
    "Business & Data Analysts": [18383.0, ...]
  }
}
```

- `dates` uses the **full month name + 4-digit year** format (`"August
  1986"`), deliberately different from the ISO rule above — this is parsed
  client-side by `monthYearToDate()` via `Date.parse("August 1, 1986")`,
  which handles full month names correctly. Do not swap this for an
  abbreviated or 2-digit-year format; it would hit the exact same class of
  bug described above.
- `series` values align 1:1 with `dates` by index; use `null` (not `NaN`,
  which doesn't survive JSON) for missing observations.
- Every column in the source CSV becomes a series automatically — no
  allow-list to maintain.

**Filter UI** — set in `INTERACTIVE_LINE_CONFIG["filterMode"]`:
- `"single"`: plain dropdown, one series at a time.
- `"multi"`: checkbox-list dropdown, up to `len(palette)` series at once.
- `"search"`: free-text type-ahead ("Enter series to show") — matches the
  live Tech Vector site; selected series become removable legend chips
  (only wired up when this chart *has* a legend row — the current build
  drops the legend entirely in favor of direct end-of-line labels, so `×`
  removal currently has no UI trigger in `"search"` mode; re-add a chip UI
  if you switch back to it).
- All three cap concurrent series at `len(palette)` — the palette is
  CVD-safe only up to that many hues, so the UI blocks further additions at
  the cap rather than silently reusing a color. Colors are assigned per-series
  to a fixed palette slot and held there for as long as that series stays
  selected (`assignColor`/`releaseColor`) — never reassigned by position in
  the current selection, so toggling one series never repaints another.
  Direct end-of-line labels are the *only* identity mechanism now (no
  legend), so they render for up to `len(palette)` series (not a smaller
  hardcoded cap), with a greedy width-based word-wrap — a word-count-based
  wrap once let a two-word series name ("Information Technology") overflow
  the card uncaught.

### Small multiples (`small_multiples.html`/`small_multiples.js`) — `key: "smallMultiples"`

Derived from raw ABS/RBA pulls, not one ready-made CSV. Four-plus series,
each a list of `{"date": ..., "value": ...}` records, **sorted
chronologically, ISO dates**:

- `macro.unemployment` — from `abs_unemployment_rate.csv`, `date` truncated
  to `"YYYY-MM"` (one row per month; if the source has multiple observations
  in a month, the last one wins).
- `macro.cashRate` — from `rba_cash_rate.csv`, same monthly-last treatment.
- One key per entry in `config["occupationPanels"]` (currently
  `techSectorNonTechOcc`, `techSectorTechOcc`, `nonTechSectorTechOcc` — note
  this is the *display* order, matched against the live site, not
  alphabetical or insertion order) — from `tech_jobs_in_australia.csv`'s
  Metric/Occupation breakdown (see `manual_data_prep.py`), quarterly, `date`
  as full `"YYYY-MM-DD"`.
- `sharedYAxis`: bool, set by the `--small-multiples-y-axis` CLI flag
  (`shared` default vs. `independent`) — whether the occupation panels share
  one Y-axis scale or each fits its own values.

The chart filters all series to `date >= "2018-01"` client-side (a string
comparison, which only works correctly because everything is zero-padded
ISO — `"2006-08-01" >= "2018-01"` compares correctly character by character;
a non-padded or non-ISO format would not).

### Ranked bar (`ranked_bar.html`/`ranked_bar.js`) — `key: "rankedBar"`, 2 pages

Shared by `AI_VIBRANCY_CONFIG` (`ai_vibrancy_chart.html`, sub-indicator
dropdown) and `RND_CONFIG` (`rnd_chart.html`, single ranked list, no
dropdown). `load_ranked_bar_data()` returns:

```json
{ "name": "Australia", "region": "APAC", "values": {"total_score": 11.2, "research_weight": 8.4, ...} }
```

- `values` has one key per entry in `config["valueColumns"]` (by `"key"`,
  not necessarily the real source column name — e.g. R&D's real column is
  `"% of GDP"`, mapped to the JS-safe key `"pct_gdp"`; see the `src_col`
  remap in `load_ranked_bar_data()` if you add a value column whose source
  name isn't already JS-safe). `None` for a missing observation.
- The bar highlighted in a different color (`config["highlightName"]`, e.g.
  `"Australia"`) is matched by exact `name` string.

### Stacked bar (`stacked_bar.html`/`stacked_bar.js`) — `key: "stackedBar"`

```json
{ "sector": "TCA Member Companies", "category": "CEOs", "Men": 77.8, "Women": 22.2 }
```

- One key per entry in `config["series"]` (currently always `Men`/`Women`),
  named after that series' `"column"` — same config-driven pattern as the
  bar chart above. Values are percentages that should sum to ~100 across a
  row's series (100%-stacked bar) — nothing enforces this at build time, so
  a source column change that breaks the sum will render a visibly
  short/overflowing bar rather than erroring.
- `category` order is `config["categoryOrder"]`, not the source CSV's row
  order.

### Stacked bar small multiples (`stacked_bar_small_multiples.html`/`.js`) — `key: "stackedSmallMultiples"`

```json
{ "panel": "Top level management", "sector": "Direct Tech Sector Companies", "filter": "Promotions", "Men": 70.0, "Women": 30.0 }
```

- Same `Men`/`Women`-style series pattern as stacked bar above, plus
  `panel` (one 100%-stacked-bar-per-sector group per panel;
  `config["panelOrder"]` sets display order) and `filter` (the dropdown
  value that must match the UI's current selection for a row to render —
  `config["filterOptions"]`/`"defaultFilterValue"`).

### Line chart (`line_chart.html`/`line_chart.js`) — `key: "line"`, 2 pages

A single time series with a direct end label, no legend/dropdown. Shared by
`TECH_SHARE_LINE_CONFIG` and `TOTAL_TECH_EMPLOYMENT_LINE_CONFIG`:

```json
{ "dates": ["1986-08-01", "1986-11-01", ...], "values": [2.5, 2.47, ...] }
```

- `dates`: ISO (`assert_iso_date()`-checked) — unlike the interactive line
  chart above, this one does *not* use the full-month-name format.
- `values`: `null` for missing observations.
- The end-of-line label text comes from `config["endLabel"]`, wrapped with
  the same greedy width-based algorithm noted under the interactive line
  chart.

### Percentile bar (`percentile_bar.html`/`percentile_bar.js`) — `key: "percentile"`

```json
{ "jobTitle": "Software Engineer", "level": "All", "percentile": "90th", "value": 236000.0 }
```

- `percentile` must be one of `config["percentileOrder"]` (currently
  `"90th"`, `"75th"`, `"Median"`, `"25th"`) to render in the right row —
  anything else is silently dropped from view (not an error, just absent).
- The Job Title / Level dropdowns filter client-side on exact string match
  against `jobTitle`/`level`; a combination with no matching rows renders a
  "No data for this combination." message rather than an empty chart (a
  real, expected case — e.g. `Marketing` only has a `Level == "All"` row in
  the source data, no `Senior`/`Entry-Level` breakdown).

### References (`references.html`/`references.js`) — `key: "references"`

```json
{
  "author": "Organisation for Economic Co-operation and Development (OECD)",
  "yearDisplay": "2021",
  "title": "Gross Domestic Spending on R&D (% of GDP)",
  "publisher": "OECD Data",
  "url": "https://www.oecd.org/en/data/indicators/gross-domestic-spending-on-r-d.html",
  "viewedDisplay": "13 July 2026"
}
```

- `yearDisplay`/`viewedDisplay` are already resolved to display strings by
  `load_references_data()` — see the `{year}`/"dynamic" note above.
  `yearDisplay` is `"n.d."` when the config entry's `"year"` is `None`.
  `viewedDisplay` is `None` (omit the "viewed ..." clause) unless the
  config entry sets `"viewed": True`.
- `title` renders italicized; `url` (if present) renders as a real link with
  the raw URL as its own visible text, matching the citation style.

### Vertical bar (`vertical_bar.html`/`vertical_bar.js`) — `key: "verticalBar"`

```json
{ "category": "TCA Member Companies", "value": 237647.0, "color": "cat-3" }
```

- One value per category, upright bars — for a single-series comparison
  (currently `salaries_comparision.csv`'s 3 sectors), not a breakdown.
- `color` is assigned by row position, cycling through `config["colors"]` —
  a fixed hue per category row in CSV order, not reassigned if the row
  order changes, so keep the CSV's category order stable if the color
  mapping matters to you.

### Top ranked dual (`top_ranked_dual.html`/`top_ranked_dual.js`) — `key: "topRankedDual"`

```json
{ "dropdownValue": "Software Engineer", "panel": "Top Company", "rank": 1.0, "label": "Block", "value": 254934.0 }
```

- Two ranked top-N panels (`config["panels"]`, matched by `panel` against
  each entry's `"panelValue"`) sharing one dropdown filter
  (`dropdownValue`, matched against the UI's current selection) and one
  x-axis scale across both panels.
- `rank` (float, ascending — 1 = top) determines row order within a panel,
  truncated to `config["topN"]` (default 3).
- If a panel has zero matching rows for the current dropdown value, it
  renders "No `<panel title>` breakdown available for this role." instead
  of an empty axis — a real, known gap for some job titles in the source
  data (a scrape artifact mislabels some roles' location-only breakdown as
  `"Top Company"`, leaving `"Top Location"` empty — not something this
  chart can detect or fix, just render gracefully).

### Status (`status.html`/`status.js`) — `key: "status"`, `dashboard_status.html`

```json
[{ "lastUpdated": "13 Jul 2026", "nextUpdate": "10 Aug 2026" }]
```

- Not a data chart — a small "Last updated / Next update" card. No download
  button, no source-line footer; `applyChromeConfig()` only sets the title.
- Both dates come from `load_status_data()`'s own 8-week cycle arithmetic
  (`CYCLE_ANCHOR_DATE`, `CYCLE_LENGTH_DAYS` at the top of `build_charts.py`),
  **not** from the per-chart data-unchanged/freshness mechanism described
  above — this is the one chart where `main()` always passes `now=` through
  regardless of the data-unchanged check, since the whole point is to show
  today's actual date, not a stamp frozen at some prior build.
- `lastUpdated` doubles as "last successful GitHub Actions run" with no API
  call: `build_charts.py` is the terminal step of the pipeline, so reaching
  this loader at all means everything upstream already succeeded that run.
  It's simply today's date at build time. If a scheduled run fails earlier
  (e.g. a scraper gets blocked) this file is never regenerated that day, so
  it keeps showing the last date the pipeline actually completed.
- `lastUpdated` is `null` before the very first cycle has ever run
  (`days_since_anchor < 0`) — `status.js` omits that row entirely rather
  than showing a placeholder. `nextUpdate` is always the next multiple of
  `CYCLE_LENGTH_DAYS` after `CYCLE_ANCHOR_DATE` strictly in the future
  (never today itself, even exactly on a rebuild day).
- Keep `CYCLE_ANCHOR_DATE`/`CYCLE_LENGTH_DAYS` here in sync with the
  matching `env` block in `.github/workflows/rebuild-data.yml` by hand —
  there's no way to share the literal constant across a YAML file and this
  one.

## Adding a new source column, file, or chart

1. Load it with pandas as usual.
2. If it has a date column, convert to ISO *immediately*, before any merge
   or aggregation: `pd.to_datetime(col, format=...).dt.strftime("%Y-%m-%d")`.
3. Run `assert_iso_date()` on the result before it goes into the JSON.
4. If the chart needs a "current vs. target" style comparison, use
   `parse_metric_value()` rather than a separately hand-entered percentage
   (see the gauge note above) — don't reintroduce a field that can drift
   out of sync with the labels it's supposed to describe.
5. If the source string should track "current as of last fetch," use a
   `"{year}"` placeholder; if it's a fixed historical vintage, don't.
6. For a genuinely new chart (not just a new config for an existing
   JS/HTML pair): add the loader, a `CONFIG` dict, the matching
   `body_file`/`js_file` under `scripts/charts/assets/`, and a `CHARTS`
   list entry with its own `out_file`. It'll pick up `chart_manifest.csv`
   tracking and the date-freshness mechanism automatically — no extra
   wiring needed for either.
7. Re-run `build_charts.py` and re-open the affected HTML file in a browser —
   the JS-side `assertIsoDate()` guard will throw in the console if a bad
   date slips through, but only a visual check catches a bug that isn't a
   date problem (wrong axis scale, mis-mapped region, mismatched gauge
   units, etc.). There is no automated screenshot check in this pipeline
   yet.
