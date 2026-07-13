**Headline Metrics — Manual Data Pull Instructions**

This document explains how to update the 3 headline "goal" gauges (Tech Jobs, Tech Investment, Tech Sector GDP), each its own standalone page (`charts/tech_jobs_gauge.html`, `charts/tech_investment_gauge.html`, `charts/tech_sector_gdp_gauge.html`), built from `scripts/charts/build_charts.py`'s `GAUGE_CONFIG`.

Each gauge is a KPI card — title, big current value, a "Target: X" pill, and a description — not a progress-arc/needle. The pill turns green ("met") once the current value actually reaches or exceeds the target; otherwise it's a neutral grey ("in progress"). That status is derived by parsing `current_label`/`target_label` directly (see `parse_metric_value` in `build_charts.py`) rather than from a separately hand-entered percentage — a hand-entered "progress %" field used to exist and could silently drift out of sync with the labels (which is exactly what broke the old needle gauge when a metric's current value was updated to exceed its target without also updating that field — a percentage past 100% doesn't fit on a semi-circle). There's nothing equivalent to keep in sync now.

**The two are not maintained the same way:**
- **Tech Investment** and **Tech Sector GDP** are curated headline KPIs with no automated source — hand-updated in `data/input/manual_pull/headline_metrics.csv` as figures come out of Tech Council research/reports.
- **Tech Jobs** is computed automatically at build time from `data/input/manual_pull/tech_jobs_in_australia_cleaned.csv` (the latest quarter's rolling-average tech job count vs. a fixed 1.2 million target) — there is nothing to hand-edit for this gauge; see below.

**Tech Investment / Tech Sector GDP — file format**
`data/input/manual_pull/headline_metrics.csv` has one row per manually-curated gauge:

| Column | Meaning |
|---|---|
| `label` | Gauge title, e.g. `Tech Investment` |
| `current_label` | Short label for the current value, e.g. `8.9%` — shown as the card's big number |
| `target_label` | Short label for the goal, e.g. `4.6%` — shown in the pill |
| `description` | One sentence shown under the card. Wrap key figures in `**double asterisks**` to render them bold (e.g. `"contributes **8.9%** to GDP"`) — parsed at render time, not literal asterisks. |

`current_label`/`target_label` must share the same unit within a row (both `%`, both `$...B`, or both a `k`/`M` count) — `parse_metric_value` strips the `$`/`%`/`k`/`M`/`B` and compares the numbers directly to decide the pill's met/not-met styling, so mismatched units (e.g. current in `k` vs. target in `M`) would compare wrong.

Colors for each gauge are set separately in `GAUGE_CONFIG["colors"]` in `build_charts.py` (not in the CSV), matched by `label`.

**Updating Tech Investment or Tech Sector GDP**
- Edit the row for the metric you're updating — change `current_label`, `target_label`, and `description` to match the latest figure.
- Rebuild with `python3 scripts/charts/build_charts.py`.

**Updating Tech Jobs**
- There's no CSV row to edit — `load_tech_jobs_gauge_data` in `build_charts.py` reads the latest row (by date) of `data/input/manual_pull/tech_jobs_in_australia_cleaned.csv`, uses its `Rolling Average` column (falling back to `Count` if that's blank) as the current job count, and divides by the fixed `TECH_JOBS_TARGET` constant (1,200,000 — a published Tech Council policy goal, not derived from any dataset) to get the gauge's percentage.
- To refresh the underlying figure: update `data/input/manual_pull/tech_jobs_in_australia.csv` (the raw manual pull) with the latest quarter's data, then regenerate the cleaned file with `python3 scripts/manual_data_prep.py data/input/manual_pull/tech_jobs_in_australia.csv` (writes `tech_jobs_in_australia_cleaned.csv` alongside it). Don't hand-edit the `_cleaned` file directly — it's a generated output, and will just be overwritten.
- To change the 1.2 million target itself: update `TECH_JOBS_TARGET` in `build_charts.py`.
- Rebuild with `python3 scripts/charts/build_charts.py`.

**Adding a new gauge**
- Add a new row to `headline_metrics.csv` (if it's a manually-curated metric) or a new loader (if it should compute from a dataset, following `load_tech_jobs_gauge_data` as an example).
- Add a matching entry (by `label`) to `GAUGE_CONFIG["colors"]` in `scripts/charts/build_charts.py` for its colors.
- Add a matching `CHARTS` entry with its own `out_file` — each gauge is its own standalone page, not a shared combined one.
- Rebuild with `python3 scripts/charts/build_charts.py`.

**Where to put files**
- `data/input/manual_pull/headline_metrics.csv` — edit for Tech Investment / Tech Sector GDP updates.
- `data/input/manual_pull/tech_jobs_in_australia.csv` — edit for Tech Jobs updates, then regenerate the `_cleaned` file (see above).
