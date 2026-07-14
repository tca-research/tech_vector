---
name: run-pipeline
description: Run the Tech Vector dashboard's full fetch-clean-aggregate-build pipeline locally and verify the generated charts render correctly. Use when asked to run, rebuild, regenerate, or test the dashboard/charts locally, or to verify a change didn't break anything.
---

# Run the full pipeline + verify

The pipeline is 4 independent, safe-to-rerun steps. This is the same
sequence `.github/workflows/rebuild-data.yml` runs on its 8-week schedule.

## 1. Install dependencies (one-time)

```bash
pip install -r requirements.txt
Rscript -e 'install.packages(c("readabs", "readrba"), repos = "https://cloud.r-project.org")'
```

## 2. Run the pipeline

```bash
python3 scripts/automated_fetch_all_data.py
```
Refreshes `data/input/automated_pull/*` from WGEA, OECD, ABS, RBA, Stanford
HAI, Levels.fyi. Any single source's failure is treated as fatal for this
whole step, by design — if a source is unreachable (e.g. Levels.fyi
scraping gets bot-blocked), the step aborts. Rerun once it's reachable, or
run that one source's `automated_fetch_*.py` script alone to isolate it.

```bash
python3 scripts/manual_data_prep.py --dir data/input/manual_pull/
```
Cleans any new manual-pull CSVs into `*_cleaned.csv` siblings.

```bash
python3 scripts/automated_data_prep.py
```
Aggregates everything into `data/output/*.csv`. **Check the exit code** —
a missing-file or other real error prints `Error: ...` and exits 1 (fixed
from a prior bug where a bare `exit()` silently returned success). A
non-zero exit means stop and investigate, not rerun blindly.

```bash
python3 scripts/charts/build_charts.py
```
Regenerates `charts/*.html` + `chart_manifest.csv`. Read the per-chart log
line — `data changed, stamping today's date` or `data unchanged, keeping
previous date` — don't assume every chart rebuilt just because the command
succeeded.

## 3. Verify — don't skip this

**a. Headless-Chrome console-error sweep across every chart:**

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
for f in charts/*.html; do
  [[ "$f" == charts/test/* ]] && continue
  out=$("$CHROME" --headless=new --disable-gpu --no-sandbox --virtual-time-budget=3000 \
    --enable-logging=stderr --v=1 --window-size=900,600 --screenshot=/dev/null \
    "file://$(pwd)/$f" 2>&1 | grep -E ":CONSOLE" | grep -iE "error|exception|uncaught")
  [ -n "$out" ] && { echo "=== $f ==="; echo "$out"; }
done
```
No output across all charts = clean. Any hit needs investigation before
moving on.

**b. Screenshot + actually view anything visually new or changed** (Read
tool on the resulting PNG) — a clean console log doesn't catch layout bugs
(label overlap, wrong colors, misaligned rows, a card rendering empty).

## 4. Before committing

```bash
git status --short
```

- `shared.css`/`shared.js` are inlined into **every** chart's HTML — a
  change to either shows all `charts/*.html` files as modified even when
  only CSS changed and no chart's data did. Confirm this with `git diff` on
  one or two files before assuming something unrelated broke.
- `automated_data_prep.py`'s pay-quartiles output uses unseeded
  `random.sample()` for example-role text, so running the pipeline purely
  to verify (not because real source data changed) can produce a spurious
  diff in `data/output/tech_pay_quartiles.csv` and the charts fed by it.
  Check whether a diff reflects a real change before committing; `git
  checkout --` it if it's just test-run noise.
