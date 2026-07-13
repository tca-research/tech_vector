# Chart data format

`build_charts.py` generates four standalone HTML files, one per chart. Each
chart's JS expects its input JSON in a specific shape. This is the contract —
if you change what feeds a chart (a new source CSV, a different aggregation),
match this shape or the chart will render with no error and look wrong.

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
`pd.to_datetime(df["Date"], format="%b-%y").dt.strftime("%Y-%m-%d")` step.
If you add a new date-bearing source, convert it the same way, immediately
after loading, before it touches any chart-building code.

`build_charts.py` also calls `assert_iso_date()` on every date series before
handing it off, and `shared.js`'s `assertIsoDate()` re-checks on the JS side
in the small-multiples chart specifically (where the bug lived) — both will
throw loudly rather than render silently wrong. Don't remove either check;
add the same call anywhere else a new date column enters the pipeline.

## Per-chart data contract

### Bar chart (`bar_chart.html`) — from `tech_pay_quartiles.csv`

A list of records, one per WGEA quartile row:

```json
{
  "quartile": "Q1 (Lower quartile)",
  "tca": 119426.0,
  "direct": 97555.0,
  "aus": 74895.0,
  "annotation": "Quartile 1 band include, on average, ..."
}
```

- `quartile`: exact row label, used as the category axis text.
- `tca` / `direct` / `aus`: numeric, in dollars (not thousands, not
  dollar-formatted strings — `build_charts.py` strips `$` and `,` via
  `money_to_float()` before this JSON is built).
- `annotation`: empty string `""` (not `null`, not `NaN`) when there's no
  callout text for a row — the "Total workforce" row has none.
- Row order is the display order, top to bottom.

### Small multiples (`small_multiples.html`) — derived, not one CSV

Four series, each a list of `{"date": ..., "value": ...}` records, **sorted
chronologically, ISO dates**:

- `macro.unemployment` — from `abs_unemployment_rate.csv`, `date` truncated
  to `"YYYY-MM"` (one row per month; if the source has multiple observations
  in a month, the last one wins).
- `macro.cashRate` — from `rba_cash_rate.csv`, same monthly-last treatment.
- `nonTechSectorTechOcc`, `techSectorTechOcc`, `techSectorNonTechOcc` — from
  `tech_jobs_in_australia.csv`'s Metric/Occupation breakdown (see
  `manual_data_prep.py`), quarterly, `date` as full `"YYYY-MM-DD"`.

The chart filters all four series to `date >= "2018-01"` client-side (a
string comparison, which only works correctly because everything is
zero-padded ISO — `"2006-08-01" >= "2018-01"` compares correctly character by
character; a non-padded or non-ISO format would not).

### Interactive line chart (`interactive_line_chart.html`) — from
`tech_jobs_occupations_over_time_WIDE-SIMPLE.csv`

```json
{
  "dates": ["August 1986", "November 1986", ...],
  "series": {
    "Software Engineers": [20137.0, 24073.0, ...],
    "Business & Data Analysts": [18383.0, ...],
    ...
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
- Every occupation column in the source CSV becomes a series automatically —
  no allow-list to maintain.

**Filter UI** — set in `INTERACTIVE_LINE_CONFIG`:
- `filterMode`: `"single"` (plain dropdown, one series at a time) or
  `"multi"` (checkbox-list dropdown, up to `len(palette)` series at once —
  the palette is only CVD-safe up to that many concurrent hues, so the UI
  disables further checkboxes at the cap rather than reusing a color).
- `defaultSeries`: initial selection. In `"single"` mode only the first name
  is used; in `"multi"` mode every name here starts checked (capped to
  `len(palette)` if you list more).
- Colors are assigned per-series to a fixed palette slot and held there for
  as long as that series stays selected (see `interactive_line.js`'s
  `assignColor`/`releaseColor`) — never reassigned by position in the
  current selection, so toggling one series never repaints another.

### Scatter (`scatter_chart.html`) — from `global_skills_rankings.csv`

```json
{
  "name": "Australia",
  "x": 0.704414164,
  "y": 0.438553423,
  "region": "Australia"
}
```

- `x` / `y`: floats in `[0, 1]` — the chart's axes are hardcoded to that
  range. A value outside it will still render but past the plotted grid.
- `region` must be one of `"Australia"`, `"EMEA"`, `"Americas"`,
  `"Global Average"`, `"APAC"` — these are the only keys in the chart's
  `regionColor` map; anything else silently falls back to the EMEA/blue
  color with no error.

## Adding a new source column or file

1. Load it with pandas as usual.
2. If it has a date column, convert to ISO *immediately*, before any merge
   or aggregation: `pd.to_datetime(col, format=...).dt.strftime("%Y-%m-%d")`.
3. Run `assert_iso_date()` on the result before it goes into the JSON.
4. Re-run `build_charts.py` and re-open the affected HTML file in a browser —
   the JS-side `assertIsoDate()` guard will throw in the console if a bad
   date slips through, but only a visual check catches a bug that isn't a
   date problem (wrong axis scale, mis-mapped region, etc.). There is no
   automated screenshot check in this pipeline yet.
