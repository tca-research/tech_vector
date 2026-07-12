#!/usr/bin/env python3
"""build_charts.py

Generates the Tech Vector-style chart set as standalone HTML files — one
file per chart, each self-contained (no external requests, no build step;
just open it in a browser). Run from anywhere:

  python3 Scripts/charts/build_charts.py

Repurposing a chart for a different dataset: everything a coder is likely to
need to change — source file/column names, title, caption, source line,
series/legend labels and colors, axis labels, download filename — lives in
the CONFIG dict for that chart below (BAR_CONFIG, SMALL_MULTIPLES_CONFIG,
INTERACTIVE_LINE_CONFIG, SCATTER_CONFIG). The JS in assets/*.js reads all of
that from the config object at render time; none of it is hardcoded there.
Point a config at a differently-shaped CSV with the same role columns
(a category + N series columns, for example) and the chart just works.

Data contract: see DATA_FORMAT.md in this directory before changing what
feeds these charts, especially the date-format rule — getting it wrong
produces a chart that renders without any error and looks subtly wrong
(this happened once already, see the small-multiples note in that file).
"""

import argparse
import json
import re
import sys
from io import StringIO
from pathlib import Path

import pandas as pd

CHARTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = CHARTS_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
# Data/ and Charts/ live alongside Scripts/ at the repo root.
DATA_OUTPUT_DIR = REPO_ROOT / "Data" / "output"
PULL_DIR = REPO_ROOT / "Data" / "input" / "automated_pull"
MANUAL_PULL_DIR = REPO_ROOT / "Data" / "input" / "manual_pull"
ASSETS_DIR = CHARTS_DIR / "assets"
DEFAULT_OUT_DIR = REPO_ROOT / "Charts"

sys.path.insert(0, str(SCRIPTS_DIR))
import manual_data_prep as mdp  # noqa: E402


def money_to_float(s):
    return float(re.sub(r"[^0-9.\-]", "", str(s)))


def assert_iso_date(series, source):
    bad = series[~series.astype(str).str.match(r"^\d{4}-\d{2}(-\d{2})?$")]
    if len(bad):
        raise ValueError(
            f"{source}: found non-ISO date value(s) {bad.head(3).tolist()!r} — "
            "dates fed to these charts must be 'YYYY-MM-DD' or 'YYYY-MM'. "
            "An ABS-style 'Aug-06' string parses in JS as day=06, not year=2006 — "
            "silently, with no error. See DATA_FORMAT.md."
        )


# =============================================================================
# 1. BAR CHART — config + loader
# =============================================================================
BAR_CONFIG = {
    "pageTitle": "Tech Vector — pay quartiles",
    "title": "Average total remuneration ($AUD) per company among WGEA-reporting organisations (100+ employees)",
    "source": "Source: WGEA (2025) · tech_pay_quartiles.csv",
    "downloadFilename": "tech_pay_quartiles.csv",
    # Which CSV column holds each row's category label (the Y-axis group).
    "categoryColumn": "WGEA Quartile",
    # Which CSV column (if any) holds free-text annotation copy shown beside
    # each row. Leave as None to disable the annotation column entirely.
    "annotationColumn": "TCA Members - Example Roles",
    # One entry per bar series: which CSV column it reads, its legend/tooltip
    # label, and which palette token (see shared.css :root) colors it. Bars
    # are drawn from a shared 0..max(first series) domain, in this order.
    "series": [
        {"column": "TCA Member Remuneration - Average", "label": "TCA Member Remuneration — Average", "color": "cat-1"},
        {"column": "Direct Tech Remuneration - Average", "label": "Direct Tech Remuneration — Average", "color": "cat-2"},
        {"column": "Australian Average Remuneration - Average", "label": "Australian Average Remuneration — Average", "color": "cat-3"},
    ],
    # How to render a raw numeric value as a label, e.g. 119426 -> "$119K".
    "valueFormat": {"prefix": "$", "divisor": 1000, "suffix": "K"},
}


def load_bar_data(config=BAR_CONFIG, source_file="tech_pay_quartiles.csv"):
    df = pd.read_csv(DATA_OUTPUT_DIR / source_file)
    rows = []
    for _, row in df.iterrows():
        record = {"category": row[config["categoryColumn"]]}
        for s in config["series"]:
            record[s["column"]] = money_to_float(row[s["column"]])
        ann_col = config.get("annotationColumn")
        record["annotation"] = (
            "" if not ann_col or pd.isna(row[ann_col]) else str(row[ann_col]).strip()
        )
        rows.append(record)
    return rows


# =============================================================================
# 2. SCATTER — config + loader
# =============================================================================
SCATTER_CONFIG = {
    "pageTitle": "Tech Vector — skills readiness vs labour market pressure",
    "title": "Skills-first readiness vs labour market pressure, by region",
    "source": "Source: global_skills_rankings.csv",
    "downloadFilename": "global_skills_rankings.csv",
    "nameColumn": "Category",
    "xColumn": "Skills-First Readiness and Adoption Index",
    "yColumn": "Labour Market Pressure Index",
    "groupColumn": "Region",
    "xAxisLabel": "Skills-First Readiness and Adoption Index",
    "yAxisLabel": "Labour Market Pressure Index",
    # Fixed hue order for the groups found in groupColumn — the legend and
    # dot colors are assigned in this order. A group not listed here falls
    # back to the last entry's color.
    "groups": [
        {"value": "Australia", "label": "Australia", "color": "cat-1"},
        {"value": "EMEA", "label": "EMEA", "color": "cat-3"},
        {"value": "Americas", "label": "Americas", "color": "cat-2"},
        {"value": "Global Average", "label": "Global Average", "color": "cat-4"},
        {"value": "APAC", "label": "APAC", "color": "cat-5"},
    ],
    # The one group whose points get a bigger dot + a direct text label
    # (rather than relying on the legend alone) — set to None to disable.
    "highlightGroup": "Australia",
    "quadrantAnnotations": [
        {"corner": "top-left", "lines": ["↑ Greater labour market", "pressure — and greater benefits", "from timely action"]},
        {"corner": "bottom-left", "lines": ["↓ Weaker labour market", "pressure — and fewer benefits", "from timely action"]},
    ],
}


def load_scatter_data(config=SCATTER_CONFIG, source_file="global_skills_rankings.csv"):
    df = pd.read_csv(DATA_OUTPUT_DIR / source_file)
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "name": row[config["nameColumn"]],
            "x": float(row[config["xColumn"]]),
            "y": float(row[config["yColumn"]]),
            "group": row[config["groupColumn"]],
        })
    return rows


# =============================================================================
# 3. INTERACTIVE LINE CHART — config + loader
# =============================================================================
INTERACTIVE_LINE_CONFIG = {
    "pageTitle": "Tech Vector — employment by occupation",
    "title": "Employed persons by tech occupation, 1986–2025",
    "caption": (
        "Real ABS employment counts, standing in for Tech Vector's searchable "
        "long-run salary chart — same interaction pattern (type to isolate "
        "series, direct end-of-line labels, shared crosshair tooltip), "
        "honestly re-labeled since no historical salary series exists in "
        "this repo yet."
    ),
    "source": "Source: Australian Bureau of Statistics · tech_jobs_occupations_over_time_WIDE-SIMPLE.csv",
    "downloadFilename": "tech_occupations_over_time.csv",
    # Which column holds the date label, and its strptime format (used only
    # for sorting — the CSV's own row order can't be trusted, see
    # DATA_FORMAT.md). Every other column becomes a selectable series.
    "dateColumn": "Month Year",
    "dateFormat": "%B %Y",
    # "single": a plain dropdown, exactly one series shown at a time.
    # "multi": a multi-select dropdown (checkbox list); up to len(palette)
    # series can be shown at once — the palette is CVD-safe only up to that
    # many concurrent hues, so the UI disables further checkboxes at the cap
    # rather than silently reusing a color.
    "filterMode": "multi",
    # Initial selection. In "single" mode only the first name is used; in
    # "multi" mode every name here starts checked (capped to len(palette)).
    "defaultSeries": ["Software Engineers", "Business & Data Analysts", "Hardware Engineers"],
    # Palette assigned to selected series — fixed slots, not selection order,
    # so a series already on screen never changes color when another is
    # added or removed (see interactive_line.js's slot assignment).
    "palette": ["cat-3", "cat-4", "cat-1", "cat-2", "cat-5"],
    "valueFormat": {"divisor": 1000, "suffix": "K"},
}


def load_interactive_line_data(config=INTERACTIVE_LINE_CONFIG, source_file="tech_jobs_occupations_over_time_WIDE-SIMPLE.csv"):
    df = pd.read_csv(DATA_OUTPUT_DIR / source_file)
    date_col = config["dateColumn"]
    # The source CSV is sorted alphabetically by its date-label column (an
    # artifact of data_prep.py's pivot sorting its string index
    # lexicographically — "April" < "August" < "December" < ... <
    # "November"), not chronologically. Never trust a date-bearing CSV's row
    # order; always re-sort by the parsed date.
    df = df.assign(_sort_date=pd.to_datetime(df[date_col], format=config["dateFormat"])).sort_values("_sort_date")
    cols = [c for c in df.columns if c not in (date_col, "_sort_date")]
    series = {}
    for c in cols:
        series[c] = [None if pd.isna(v) else float(v) for v in df[c]]
    return {"dates": df[date_col].tolist(), "series": series}


# =============================================================================
# 4. SMALL MULTIPLES — config + loader
#    Derived from raw ABS/RBA pulls, not a single ready-made dashboard CSV.
# =============================================================================
SMALL_MULTIPLES_CONFIG = {
    "pageTitle": "Tech Vector — hiring vs macro conditions",
    "title": "Tech sector hiring vs macroeconomic conditions",
    "source": "Source: Australian Bureau of Statistics, Reserve Bank of Australia · tech_jobs_in_australia.csv, abs_unemployment_rate.csv, rba_cash_rate.csv",
    "downloadFilename": "tech_hiring_vs_macro.csv",
    # The caption is a sequence of [text, colorToken] segments — colorToken
    # "muted" uses the ink-muted text color, any other token uses that
    # palette slot's "-text" variant, null/omitted renders as plain text.
    "captionParts": [
        ["Strong increases in tech sector hiring — ", None],
        ["employee count", "muted"],
        [", ", None],
        ["smoothed rolling average", "cat-3"],
        [" — coincided with falling ", None],
        ["interest rates", "cat-2"],
        [" during COVID-19 as well as a sharp decline in the national ", None],
        ["unemployment rate", "cat-1"],
        [".", None],
    ],
    "legend": [
        {"color": "ink-muted", "label": "Employee count (raw)"},
        {"color": "cat-3", "label": "Smoothed rolling average"},
        {"color": "cat-2", "label": "Cash rate (RBA)"},
        {"color": "cat-1", "label": "Unemployment rate (ABS)"},
    ],
    "macroPanel": {
        "title": "Macroeconomic indicators (%)",
        "series": [
            {"key": "unemployment", "label": "Unemployment rate", "color": "cat-1", "valueSuffix": "%", "valueDecimals": 1},
            {"key": "cashRate", "label": "Cash rate", "color": "cat-2", "valueSuffix": "%", "valueDecimals": 2},
        ],
    },
    # Each occupation panel is derived from one (Metric, Occupation) slice of
    # tech_jobs_in_australia.csv. Add/remove entries to repurpose this chart
    # for a different Metric/Occupation breakdown of the same file shape.
    "occupationPanels": [
        {"key": "nonTechSectorTechOcc", "metric": "Non Tech Sector Industries", "occupation": "Tech occupations", "title": "Tech occupations — Non-tech sector industries"},
        {"key": "techSectorTechOcc", "metric": "Tech Sector Industries", "occupation": "Tech occupations", "title": "Tech occupations — Tech sector industries"},
        {"key": "techSectorNonTechOcc", "metric": "Tech Sector Industries", "occupation": "Non tech occupations", "title": "Non-tech occupations — Tech sector industries"},
    ],
    # A (Metric, Occupation) combo to drop entirely before building panels —
    # here, "not tech at all" rows that aren't part of this story. Set to
    # None to keep every combo.
    "excludeCombo": {"metric": "Non Tech Sector Industries", "occupation": "Non tech occupations"},
    "startDate": "2018-01",
}


def load_small_multiples_data(config=SMALL_MULTIPLES_CONFIG, shared_y_axis=True):
    start = config["startDate"]
    raw_path = MANUAL_PULL_DIR / "tech_jobs_in_australia.csv"
    text = raw_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    top = mdp.find_top_cutoff(lines)
    bottom = mdp.find_bottom_cutoff(lines)
    df = pd.read_csv(StringIO("\n".join(lines[top:bottom])), dtype=str, engine="python")
    df = mdp.clean_df(df)
    df = mdp.promote_real_header(df)
    df = mdp.ffill_key_columns(df)
    exclude = config.get("excludeCombo")
    if exclude:
        df = df[~((df["Metric"] == exclude["metric"]) & (df["Occupation"] == exclude["occupation"]))]
    df["Count"] = pd.to_numeric(df["Count"], errors="coerce")

    # Convert ABS-style "Aug-06" to ISO "2006-08-01" — see DATA_FORMAT.md.
    iso_date = pd.to_datetime(df["Date"], format="%b-%y").dt.strftime("%Y-%m-%d")
    df = df.assign(IsoDate=iso_date)
    assert_iso_date(df["IsoDate"], "tech_jobs_in_australia.csv (post-conversion)")

    def series_for(metric, occupation):
        sub = df[(df["Metric"] == metric) & (df["Occupation"] == occupation)].sort_values("IsoDate")
        return [{"date": d, "value": v} for d, v in zip(sub["IsoDate"], sub["Count"])]

    unemployment = pd.read_csv(PULL_DIR / "abs_unemployment_rate.csv")
    cash_rate = pd.read_csv(PULL_DIR / "rba_cash_rate.csv")

    def monthly_last(df_in, date_col, value_col):
        df_in = df_in.copy()
        df_in["ym"] = df_in[date_col].str.slice(0, 7)
        assert_iso_date(df_in["ym"], f"{date_col} (monthly-resampled)")
        return (
            df_in.sort_values(date_col)
            .drop_duplicates("ym", keep="last")[["ym", value_col]]
            .rename(columns={"ym": "date", value_col: "value"})
        )

    unemployment_m = monthly_last(unemployment, "date", "value")
    cash_rate_m = monthly_last(cash_rate, "date", "value")
    unemployment_m = unemployment_m[unemployment_m["date"] >= start]
    cash_rate_m = cash_rate_m[cash_rate_m["date"] >= start]

    result = {
        "macro": {
            "unemployment": unemployment_m.to_dict("records"),
            "cashRate": cash_rate_m.to_dict("records"),
        },
        # Whether the occupation panels share one Y-axis scale (so their
        # heights are directly comparable) or each gets its own scale fitted
        # to just its own values (so small series aren't squashed flat).
        "sharedYAxis": shared_y_axis,
    }
    for panel in config["occupationPanels"]:
        result[panel["key"]] = series_for(panel["metric"], panel["occupation"])
    return result


# =============================================================================
# HTML assembly
# =============================================================================
def read_asset(name):
    return (ASSETS_DIR / name).read_text(encoding="utf-8")


def build_html(body_html, chart_js_file, data_key, config, data):
    css = read_asset("shared.css")
    shared_js = read_asset("shared.js")
    chart_js = read_asset(chart_js_file)
    # Each chart's JS reads DATA.<data_key>.config / .data — same data_key
    # convention as when all four charts shared one combined payload, so the
    # key has to match here even though this file now carries only one
    # chart's data.
    data_json = json.dumps({data_key: {"config": config, "data": data}})
    return f"""<title>{config.get("pageTitle", config.get("title", ""))}</title>
<style>
{css}
</style>
{body_html}
<script type="application/json" id="chart-data">
{data_json}
</script>
<script>
(function () {{
  "use strict";
  const DATA = JSON.parse(document.getElementById("chart-data").textContent);

{shared_js}

{chart_js}
}})();
</script>
"""


CHARTS = [
    {
        "key": "bar",
        "body_file": "bar_chart.html",
        "js_file": "bar_chart.js",
        "loader": load_bar_data,
        "config": BAR_CONFIG,
        "out_file": "bar_chart.html",
    },
    {
        "key": "smallMultiples",
        "body_file": "small_multiples.html",
        "js_file": "small_multiples.js",
        "loader": load_small_multiples_data,
        "config": SMALL_MULTIPLES_CONFIG,
        "out_file": "small_multiples.html",
    },
    {
        "key": "interactiveLine",
        "body_file": "interactive_line.html",
        "js_file": "interactive_line.js",
        "loader": load_interactive_line_data,
        "config": INTERACTIVE_LINE_CONFIG,
        "out_file": "interactive_line_chart.html",
    },
    {
        "key": "scatter",
        "body_file": "scatter.html",
        "js_file": "scatter.js",
        "loader": load_scatter_data,
        "config": SCATTER_CONFIG,
        "out_file": "scatter_chart.html",
    },
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--small-multiples-y-axis",
        choices=["shared", "independent"],
        default="shared",
        help=(
            "'shared' (default): the occupation panels use one common Y-axis "
            "scale, so bar/line heights are directly comparable across panels. "
            "'independent': each panel scales to fit only its own values."
        ),
    )
    args = parser.parse_args()

    out_dir = DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    for chart in CHARTS:
        print(f"Building {chart['key']}...")
        if chart["key"] == "smallMultiples":
            data = chart["loader"](chart["config"], shared_y_axis=(args.small_multiples_y_axis == "shared"))
        else:
            data = chart["loader"](chart["config"])
        body_html = read_asset(chart["body_file"])
        html = build_html(body_html, chart["js_file"], chart["key"], chart["config"], data)
        out_path = out_dir / chart["out_file"]
        out_path.write_text(html, encoding="utf-8")
        print(f"  wrote {out_path}")

    print(f"\nDone. Open the files in {out_dir} directly in a browser.")


if __name__ == "__main__":
    main()
