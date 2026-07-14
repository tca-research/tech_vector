# Tech Vector

Data pipeline and chart-generation system underlying the Tech Council of
Australia's Tech Vector dashboard (techcouncil.com.au/tech-vector). See
`README.md` for the full repo layout and local run instructions — this file
is conventions and gotchas, not a repeat of that.

## Ownership context

The research team owns this GitHub repo directly — there is no separate IT
team running scheduled automation. Anything that needs to keep working
unattended (the GitHub Actions rebuild, in particular) has to be
maintainable by that team, not assume any one person will be around to fix
it. Keep this in mind before proposing anything that adds an operational
dependency (a new external service, a credential only one person holds,
etc.) without a clear owner.

## Architecture in one paragraph

`scripts/automated_fetch_all_data.py` → `scripts/manual_data_prep.py` →
`scripts/automated_data_prep.py` → `scripts/charts/build_charts.py`. The
first three stages produce CSVs (`data/input/`, `data/output/`); the last
stage is config-driven — each chart is a `CONFIG` dict + `load_*_data()`
loader in `build_charts.py`, registered in its `CHARTS` list, rendered into
a standalone, self-contained HTML file (no chart library, no external
requests). `.github/workflows/rebuild-data.yml` runs all four stages on an
8-week cycle and commits the result back to `main`.

## Skills for common tasks

Three project skills cover the recurring work here in more depth than fits
this file — invoke them rather than re-deriving the steps:

- **add-chart** — adding a new chart type or a new dataset in an existing
  chart shape.
- **refresh-manual-data** — updating one of the 2 manually-curated data
  sources (headline gauge figures, ABS TableBuilder exports) that nothing
  in this repo can fetch automatically. (Tech Council member ABNs used to
  be a 3rd manual source — now automated via a Zoho CRM webhook, see below.)
- **run-pipeline** — running the full local pipeline and verifying charts
  render correctly (the headless-Chrome console-error sweep + screenshot
  method used throughout this project).

## Non-obvious rules that have already caused real bugs

- **Dates must be ISO (`YYYY-MM-DD`/`YYYY-MM`) before they reach any
  chart.** `new Date("Aug-06")` parses with no error and no warning, just
  silently at the wrong x-position (day=6, year=2000) — this exact bug
  shipped once in the small-multiples chart. See `scripts/charts/
  DATA_FORMAT.md` for the full rule and where conversion has to happen.
- **A gauge/KPI's "met target" pill is derived, not hand-entered** —
  `parse_metric_value()` compares `current_label`/`target_label` as plain
  numbers after stripping `$`/`%`/`k`/`M`/`B`. Mismatched units between the
  two silently produce the wrong status.
- **A chart's "last updated" date only advances when its data (or source
  wording) actually changed**, not on every `build_charts.py` run — see
  `read_previous_chart_state()`/`data_unchanged` in that file. Don't expect
  a no-op rebuild to bump every timestamp.
- **`shared.css`/`shared.js` are inlined into every chart's HTML.** Editing
  either makes `git status` show all `charts/*.html` files as modified even
  when no chart's actual data changed — check with `git diff` before
  assuming something else broke.
- **Bare `exit()` in Python without `import sys` returns exit code 0**
  (`SystemExit(None)` reads as success), which is why a CI step could show
  green on a real failure. Always use `sys.exit(1)` for a real failure path.
- **`.gitignore` entries are case-sensitive on Linux CI** even though macOS
  silently tolerates a case mismatch locally (`core.ignorecase=true` by
  default) — a path that "works" locally can be un-ignored on the GitHub
  Actions runner. Match the actual on-disk casing (this repo's data
  directories are lowercase).
- **`automated_data_prep.py`'s pay-quartiles example-role text uses
  unseeded `random.sample()`** — running it purely to verify produces a
  spurious diff each time, not a real data change. Don't commit that noise.
- **The Zoho ABN webhook sends a full membership snapshot every time, not
  an incremental change.** `sync_zoho_abn_webhook.py` overwrites
  `Tech_Council_ABNs.csv` wholesale with whatever `accounts_data` list it
  receives — it does not merge/diff against the existing file. A payload
  containing only a subset of members (a bug on the sending side, a
  truncated request, etc.) would silently drop every member missing from
  it. This is what makes the sync self-healing against a single failed
  delivery (the next good snapshot fully corrects everything), but it also
  means "always send the complete list" is a hard requirement on whatever
  generates the payload, not just a nice-to-have.
- **Zoho sends ABNs in human display format with spaces**
  (`"44 645 215 194"`), not bare digits — `sync_zoho_abn_webhook.py` strips
  them before writing. Real production data has also had blank and
  wrong-length (e.g. 9-digit) ABNs for a handful of accounts; these are
  skipped with a per-company warning rather than failing the whole sync,
  since the CRM data itself needs fixing, not this script's logic.

## GitHub Actions automation

`.github/workflows/rebuild-data.yml` runs weekly on cron but gates itself
to actually execute only every 56 days from a fixed anchor date (GitHub
Actions cron can't express "every 8 weeks" directly) — see the workflow's
own comments for the day-count math. `workflow_dispatch` with `force: true`
bypasses the gate for manual testing.

This automation **only handles the automated-pull sources** — it commits
regenerated `data/output/*.csv`, cleaned manual-pull CSVs, and
`charts/*.html`/`chart_manifest.csv` back to `main`. It does not refresh
the 2 remaining manually-curated inputs (see the `refresh-manual-data`
skill). It does not deploy anywhere — still scoped out for now; the
workflow has a clean seam to add a `deploy` job later if that's revisited.

A separate workflow, `.github/workflows/sync-zoho-abn-webhook.yml`, handles
Tech Council member ABNs — event-driven via `repository_dispatch`, not on
this file's 8-week schedule. It has no Zoho credentials of its own; the
only credential in that whole path (a GitHub PAT) lives inside Zoho's own
webhook config, not in this repo. See
`scripts/MANUAL_DATA_PULL_INSTRUCTIONS_TECH_COUNCIL_ABNS.md`'s payload
contract section, and the two gotchas above (full-snapshot semantics,
ABN normalization) for why the receiving script is built the way it is.
What exactly triggers a send on the Zoho side isn't documented yet —
flagged as an open item in that doc. Leo (leo@techcouncil.com.au) owns
that Zoho-side process — he's the contact for changing the trigger, the
GitHub PAT, or the payload shape.

`charts/dashboard_status.html` (the `status` chart in `build_charts.py`)
shows "Last updated" / "Next update" using the same cycle-anchor math as
the workflow — keep `CYCLE_ANCHOR_DATE`/`CYCLE_LENGTH_DAYS` in the two
files in sync by hand if the cadence ever changes; there's no way to share
the literal constant across a YAML file and a Python file.
