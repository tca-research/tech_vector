**Headline Metrics (Gauge Charts) — Manual Data Pull Instructions**

This document explains how to update the 3 headline "goal" gauges (Tech Jobs, Tech Investment, Tech Sector GDP) shown at the top of the Tech Vector-style chart set.

**Overview**
- **Purpose:** Keep `data/input/manual_pull/headline_metrics.csv` current so the gauge chart (`charts/gauge.html`, built from `scripts/charts/build_charts.py`'s `GAUGE_CONFIG`) shows up-to-date progress-to-target figures.
- **There is no automated source for these** — they're curated headline KPIs, typically sourced from Tech Council research/reports, not a scraped or API-fed dataset.

**File format**
`data/input/manual_pull/headline_metrics.csv` has one row per gauge:

| Column | Meaning |
|---|---|
| `label` | Gauge title, e.g. `Tech Jobs` |
| `value` | Progress percentage (0–100) — where the needle points |
| `current_label` | Short label for the current value, e.g. `949k` |
| `target_label` | Short label for the goal, e.g. `1.2M` |
| `description` | One sentence shown under the gauge |

Colors for each gauge are set separately in `GAUGE_CONFIG` in `build_charts.py` (not in the CSV), matched by `label`.

**Updating a value**
- Edit the row for the metric you're updating — change `value`, `current_label`, `target_label`, and `description` to match the latest figure.
- Adding a new gauge: add a new row here, then add a matching entry (by `label`) to `GAUGE_CONFIG["gauges"]` in `scripts/charts/build_charts.py` specifying its colors.
- Rebuild with `python3 scripts/charts/build_charts.py`.

**Where to put files**
- `data/input/manual_pull/headline_metrics.csv` — this is the only file to edit for routine updates.
