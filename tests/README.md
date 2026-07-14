# Tests

Runs automatically on every push/PR via `.github/workflows/test.yml`. To run
locally:

```
pip install -r requirements-dev.txt
python -m playwright install chromium   # one-time, downloads a browser
python -m pytest
```

Run one file or one test the normal pytest way, e.g.
`python -m pytest tests/test_manual_data_prep.py -k rolling_average -v`.

## What's covered, and why it's split this way

- **`test_manual_data_prep.py`**, **`test_zoho_webhook.py`**,
  **`test_build_charts_helpers.py`** — plain unit tests against the pure
  functions in `scripts/manual_data_prep.py`, `scripts/sync_zoho_abn_webhook.py`,
  and `scripts/charts/build_charts.py`. No browser, no fixtures beyond small
  inline DataFrames/CSVs written to `tmp_path`. These three scripts are
  function-based enough to test directly — `conftest.py` puts `scripts/` and
  `scripts/charts/` on `sys.path` so they import as plain modules (there are
  no `__init__.py`/packages in this repo; `build_charts.py` does the same
  `sys.path.insert` trick to import `manual_data_prep` itself).

- **`test_chart_rendering.py`** — Playwright tests against the actual,
  already-built `charts/*.html` files (committed to the repo, so this needs
  no pipeline run first). This exists because several real bugs here only
  showed up in the rendered page's actual DOM/CSS/event behavior — a
  `position: fixed` element's anchor point, an SVG element's paint-order
  hit-testing, a touch pointer's event lifecycle — nothing a function-level
  unit test could catch, since the bug wasn't in any one function's logic.
  It also formalizes the console-error sweep from
  `.claude/skills/run-pipeline/SKILL.md` into a real, parametrized,
  assertable test instead of a bash snippet to run and eyeball by hand.

## What's deliberately *not* covered

`scripts/automated_data_prep.py` is one large top-level script (reads ~10
real CSVs and executes at import time, not wrapped in functions apart from
`find_example_roles`), and `scripts/automated_fetch_*.py` hit live external
sources (ABS, RBA, WGEA, OECD, Levels.fyi). Both are out of scope for this
suite for the same reason: black-box testing either would mean either
building a large, fragile set of fixture CSVs matching ~10 real schemas
exactly, or hitting real external APIs from CI. Neither is a good trade for
what it'd catch. If you're changing `automated_data_prep.py`, the safest
check is still: run it against real data locally (`run-pipeline` skill) and
diff the output CSVs.

## Adding to this later

- A new pure function in one of the three covered scripts: add a test next
  to the others in its file, no new infrastructure needed.
- A new chart type: it gets the console-error/tooltip/touch coverage in
  `test_chart_rendering.py` automatically (chart files are discovered via
  `charts/*.html` glob, not hardcoded) — add a chart-specific test only if it
  has its own regression-worthy behavior (like `small_multiples`' axis
  suffixes or `interactive_line`'s adaptive rotation).
- A config field like `INTERACTIVE_LINE_CONFIG`'s `title_year` mechanism:
  see `DATA_FORMAT.md`'s "Source lines: the `{year}` placeholder..." section
  before assuming it works the same way `source`'s `{year}` does — it
  doesn't, and `test_build_charts_helpers.py`'s `build_html` tests are why.
