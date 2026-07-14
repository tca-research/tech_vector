---
name: refresh-manual-data
description: Refresh one of the 3 manually-curated data sources feeding the Tech Vector dashboard (headline metrics/gauges, Tech Council member ABNs, ABS TableBuilder exports) and rebuild the affected charts. Use when asked to update a gauge figure, refresh member ABNs, upload a TableBuilder export, or otherwise update data this pipeline can't fetch automatically.
---

# Refresh manually-curated data

Three inputs need a human to refresh them — nothing in this repo fetches
them automatically, and the GitHub Actions rebuild workflow doesn't touch
them either. Each has its own instructions doc under `scripts/`; **read the
matching doc in full before editing anything** — don't improvise a CSV
shape or filename, the aggregation step reads exact column names/filenames.

| Source | Instructions doc | Feeds |
|---|---|---|
| Tech Investment / Tech Sector GDP gauge figures, Tech Jobs raw source | `scripts/MANUAL_DATA_PULL_INSTRUCTIONS_HEADLINE_METRICS.md` | `headline_metrics.csv`, `tech_jobs_in_australia.csv` |
| Tech Council member ABNs | `scripts/MANUAL_DATA_PULL_INSTRUCTIONS_TECH_COUNCIL_ABNS.md` | `Tech_Council_ABNs.csv` |
| ABS TableBuilder exports | `scripts/MANUAL_DATA_PULL_INSTRUCTIONS_TABLEBUILDER_UPLOAD.md` | `tech_roles_in_tech_subsector.csv`, `tech_jobs_in_australia.csv` |

## Steps

1. **Identify which source needs refreshing.** If ambiguous, ask rather
   than guessing — the three docs have non-overlapping but similarly-named
   files (`tech_jobs_in_australia.csv` is shared between two of them).
2. **Read and follow that doc exactly.** Exact filename, exact column
   name/casing (e.g. `ABN` must be exactly that, case-sensitive —
   `automated_data_prep.py` reads it by name and raises `KeyError`
   otherwise).
3. **Place the file in `data/input/manual_pull/`** with the expected
   filename.
4. **If a `_cleaned` sibling exists** (e.g. `tech_jobs_in_australia.csv` →
   `tech_jobs_in_australia_cleaned.csv`), regenerate it — don't hand-edit
   the `_cleaned` file, it's a generated output that gets overwritten:
   ```bash
   python3 scripts/manual_data_prep.py --dir data/input/manual_pull/
   ```
5. **Rebuild:**
   ```bash
   python3 scripts/automated_data_prep.py
   python3 scripts/charts/build_charts.py
   ```
6. **Verify just the affected chart(s)** with a screenshot + console-error
   check (see the `run-pipeline` skill for the exact command) — a full
   19-chart sweep isn't necessary unless you're unsure which charts your
   change touches.
7. **If you edited `headline_metrics.csv`**, double-check `current_label`
   and `target_label` share the same unit family (both `%`, both `$...B`,
   both a `k`/`M` count) in the row you changed. `parse_metric_value()`
   compares them as plain numbers after stripping the unit — mismatched
   units silently produce the wrong "met target" pill with no error.
