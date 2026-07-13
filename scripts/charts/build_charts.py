#!/usr/bin/env python3
"""build_charts.py

Generates the Tech Vector-style chart set as standalone HTML files — one
file per chart, each self-contained (no external requests, no build step;
just open it in a browser). Run from anywhere:

  python3 scripts/charts/build_charts.py

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
import csv
import json
import re
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd

CHARTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = CHARTS_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
# data/ and charts/ live alongside scripts/ at the repo root.
DATA_OUTPUT_DIR = REPO_ROOT / "data" / "output"
PULL_DIR = REPO_ROOT / "data" / "input" / "automated_pull"
MANUAL_PULL_DIR = REPO_ROOT / "data" / "input" / "manual_pull"
ASSETS_DIR = CHARTS_DIR / "assets"
DEFAULT_OUT_DIR = REPO_ROOT / "charts"

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
# 0. GAUGES — config + loader
#    Data is manually curated (no automated source) — see
#    MANUAL_DATA_PULL_INSTRUCTIONS_HEADLINE_METRICS.md.
# =============================================================================
GAUGE_CONFIG = {
    "pageTitle": "Tech Vector — headline metrics",
    "title": "Tech Sector Goals",
    "source": "Source: Tech Council of Australia research",
    "downloadFilename": "headline_metrics.csv",
    # Per-gauge colors, matched to data/input/manual_pull/headline_metrics.csv
    # rows by "label" — everything else about a gauge (value, current/target
    # labels, description) lives in that CSV, not here.
    "colors": {
        "Tech Jobs": {"filledColor": "cat-1", "remainingColor": "cat-3", "needleColor": "cat-4", "currentBadgeColor": "cat-3", "targetBadgeColor": "cat-1"},
        "Tech Investment": {"filledColor": "cat-3", "remainingColor": "cat-1", "needleColor": "cat-1", "currentBadgeColor": "cat-1", "targetBadgeColor": "cat-4"},
        "Tech Sector GDP": {"filledColor": "cat-4", "remainingColor": "cat-1", "needleColor": "cat-3", "currentBadgeColor": "cat-1", "targetBadgeColor": "cat-1"},
    },
    "defaultColors": {"filledColor": "cat-4", "remainingColor": "cat-5", "needleColor": "cat-3", "currentBadgeColor": "cat-3", "targetBadgeColor": "cat-4"},
}


def load_gauge_data(config=GAUGE_CONFIG, source_file="headline_metrics.csv"):
    df = pd.read_csv(MANUAL_PULL_DIR / source_file)
    rows = []
    for _, row in df.iterrows():
        colors = config["colors"].get(row["label"], config["defaultColors"])
        rows.append({
            "label": row["label"],
            "value": float(row["value"]),
            "currentLabel": row["current_label"],
            "targetLabel": row["target_label"],
            "description": row["description"],
            **colors,
        })
    return rows


# =============================================================================
# 1. BAR CHART — config + loader
# =============================================================================
BAR_CONFIG = {
    "pageTitle": "Tech Vector — pay quartiles",
    "title": "Average total remuneration ($AUD) per company among WGEA-reporting organisations (100+ employees)",
    "source": "Source: WGEA ({year}). Data is anonymised and aggregated by the Tech Council of Australia.",
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


WOMENS_PAY_CONFIG = {
    "pageTitle": "Tech Vector — women's pay scales in tech",
    "title": "Quartile pay bands per company",
    "source": "Source: WGEA ({year}). Data is anonymised and aggregated by the Tech Council of Australia.",
    "downloadFilename": "tech_pay_quartiles_women.csv",
    "categoryColumn": "WGEA Quartile",
    "annotationColumn": None,
    "series": [
        {"column": "TCA Members - % Women - Average", "label": "TCA Members - % Women - Average", "color": "cat-4"},
        {"column": "Direct Tech - % Women - Average", "label": "Direct Tech - % Women - Average", "color": "cat-1"},
        {"column": "Australian Average - % Women - Average", "label": "Australian Average - % Women - Average", "color": "cat-3"},
    ],
    "valueFormat": {"divisor": 1, "suffix": "%", "decimals": 1},
}


def load_womens_pay_data(config=WOMENS_PAY_CONFIG, source_file="tech_pay_quartiles.csv"):
    return load_bar_data(config, source_file)


# =============================================================================
# 2. SCATTER — config + loader
# =============================================================================
SCATTER_CONFIG = {
    "pageTitle": "Tech Vector — skills readiness vs labour market pressure",
    "title": "Skills-first readiness vs labour market pressure, by region",
    "source": "Source: OECD ({year}). Data is anonymised and aggregated by the Tech Council of Australia.",
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
    "source": "Source: Australian Bureau of Statistics ({year}). Data is anonymised and aggregated by the Tech Council of Australia.",
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
    "source": "Source: Australian Bureau of Statistics, Reserve Bank of Australia ({year}). Data is anonymised and aggregated by the Tech Council of Australia.",
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
        {"key": "techSectorNonTechOcc", "metric": "Tech Sector Industries", "occupation": "Non tech occupations", "title": "Non tech occupations — Tech sector industries"},
        {"key": "techSectorTechOcc", "metric": "Tech Sector Industries", "occupation": "Tech occupations", "title": "Tech occupations — Tech sector industries"},
        {"key": "nonTechSectorTechOcc", "metric": "Non Tech Sector Industries", "occupation": "Tech occupations", "title": "Tech occupations — Non tech sector industries"},
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
# 5. RANKED BAR — config + loader. Two instances share the same JS/HTML
#    (ranked_bar.js / .html): AI vibrancy (has a sub-indicator dropdown) and
#    R&D spend (a single ranked list, no dropdown).
# =============================================================================
AI_VIBRANCY_CONFIG = {
    "pageTitle": "Tech Vector — Global AI Vibrancy Index",
    "title": "Global AI Vibrancy Index",
    "caption": "Australia is ranked 28 out of 36 countries on AI vibrancy.",
    "source": "Source: Stanford HAI ({year}).",  
    "downloadFilename": "global_ai_rankings.csv",
    "nameColumn": "CountryName",
    "regionColumn": "Region",
    "dropdownLabel": "Sub-Indicators:",
    "defaultValueColumn": "total_score",
    "valueColumns": [
        {"key": "total_score", "label": "Total"},
        {"key": "research_weight", "label": "Research"},
        {"key": "responsible_weight", "label": "Responsible AI"},
        {"key": "economy_weight", "label": "Economy"},
        {"key": "talent_weight", "label": "Talent"},
        {"key": "policy_weight", "label": "Policy"},
        {"key": "publicOpinion_weight", "label": "Public Opinion"},
        {"key": "infrastructure_weight", "label": "Infrastructure"},
    ],
    "valueSuffix": "",
    "highlightName": "Australia",
    "highlightColor": "cat-4",
    "barColor": "cat-3",
}

RND_CONFIG = {
    "pageTitle": "Tech Vector — R&D spending",
    "title": "R&D",
    "caption": "Australia sits at the median (1.7%) for OECD R&D spending as a percent of GDP.",
    "source": "Source: OECD (2021).",
    "downloadFilename": "global_r_and_d_rankings.csv",
    "nameColumn": "Category",
    "regionColumn": "Region",
    "defaultValueColumn": "pct_gdp",
    "valueColumns": [{"key": "pct_gdp", "label": "% of GDP"}],
    "valueSuffix": "%",
    "highlightName": "Australia",
    "highlightColor": "cat-4",
    "barColor": "cat-3",
}


def load_ranked_bar_data(config, source_file):
    df = pd.read_csv(DATA_OUTPUT_DIR / source_file)
    rows = []
    for _, row in df.iterrows():
        values = {}
        for c in config["valueColumns"]:
            col = c["key"]
            # R&D's source column is "% of GDP", but "%" isn't a usable dict
            # key on the JS side — config["valueColumns"] keys are already
            # JS-safe, so map back to the real column name when it differs.
            src_col = "% of GDP" if col == "pct_gdp" else col
            values[col] = None if pd.isna(row[src_col]) else float(row[src_col])
        rows.append({
            "name": row[config["nameColumn"]],
            "region": row.get(config["regionColumn"], ""),
            "values": values,
        })
    return rows


def load_ai_vibrancy_data(config=AI_VIBRANCY_CONFIG, source_file="global_ai_rankings.csv"):
    return load_ranked_bar_data(config, source_file)


def load_rnd_data(config=RND_CONFIG, source_file="global_r_and_d_rankings.csv"):
    return load_ranked_bar_data(config, source_file)


# =============================================================================
# 6. STACKED BAR — one 100%-stacked bar per category + a sector dropdown
# =============================================================================
STACKED_BAR_CONFIG = {
    "pageTitle": "Tech Vector — women in leadership by sector",
    "title": "Per cent of men and women in leadership roles.",
    "source": "Source: WGEA ({year}). Data is anonymised and aggregated by the Tech Council of Australia.",
    "downloadFilename": "workplace_leadership_comp_pct.csv",
    "sectorColumn": "Sector",
    "categoryColumn": "occupation",
    # Display order, most senior first — not the source CSV's row order.
    "categoryOrder": [
        "CEOs",
        "Heads of Business",
        "Other Executives and General Managers",
        "Senior managers",
        "Other managers",
        "Non-managers",
    ],
    "dropdownLabel": "Sector:",
    "sectors": [
        {"value": "TCA Member Companies", "label": "TCA Member Companies"},
        {"value": "Direct Tech Sector Companies", "label": "Direct Tech Sector Companies"},
        {"value": "Australian Average", "label": "Australian Average"},
    ],
    "defaultSector": "TCA Member Companies",
    "series": [
        {"column": "Men", "label": "Men", "color": "cat-3"},
        {"column": "Women", "label": "Women", "color": "cat-1"},
    ],
}


def load_stacked_bar_data(config=STACKED_BAR_CONFIG, source_file="workplace_leadership_comp_pct.csv"):
    df = pd.read_csv(DATA_OUTPUT_DIR / source_file)
    rows = []
    for _, row in df.iterrows():
        record = {"sector": row[config["sectorColumn"]], "category": row[config["categoryColumn"]]}
        for s in config["series"]:
            record[s["column"]] = float(row[s["column"]])
        rows.append(record)
    return rows


# =============================================================================
# 7. STACKED BAR SMALL MULTIPLES — panels x sector rows + one dropdown filter
# =============================================================================
STACKED_SMALL_MULTIPLES_CONFIG = {
    "pageTitle": "Tech Vector — women's promotion rates",
    "title": "Per cent of men & women promoted, moved laterally or hired externally within workplace seniority levels.",
    "source": "Source: WGEA ({year}). Data is anonymised and aggregated by the Tech Council of Australia.",
    "downloadFilename": "mgmt_promotions_pct.csv",
    "panelColumn": "manager_type",
    "panelLabel": "Managerial level",
    "panelOrder": ["Mid to entry level management", "Non-managers", "Top level management"],
    "sectorColumn": "Sector",
    "sectorOrder": ["Direct Tech Sector Companies", "Australian Average"],
    "dropdownColumn": "movement_type",
    "dropdownLabel": "Movement type:",
    "filterOptions": [
        {"value": "Promotions", "label": "Promotions"},
        {"value": "Internal appointments", "label": "Internal appointments"},
        {"value": "External appointments", "label": "External appointments"},
    ],
    "defaultFilterValue": "Promotions",
    "series": [
        {"column": "Men", "label": "Men", "color": "cat-3"},
        {"column": "Women", "label": "Women", "color": "cat-1"},
    ],
}


def load_stacked_small_multiples_data(config=STACKED_SMALL_MULTIPLES_CONFIG, source_file="mgmt_promotions_pct.csv"):
    df = pd.read_csv(DATA_OUTPUT_DIR / source_file)
    rows = []
    for _, row in df.iterrows():
        record = {
            "panel": row[config["panelColumn"]],
            "sector": row[config["sectorColumn"]],
            "filter": row[config["dropdownColumn"]],
        }
        for s in config["series"]:
            record[s["column"]] = float(row[s["column"]])
        rows.append(record)
    return rows


# =============================================================================
# 8. LINE CHART — a single time series + direct end label, no legend/dropdown
# =============================================================================
TECH_SHARE_LINE_CONFIG = {
    "pageTitle": "Tech Vector — tech roles as a share of the labour force",
    "title": "Tech Roles as a Share of the Total Labour Force",
    "caption": "This proportion indicates how tech employment has grown as a segment of the overall workforce, showing tech's increasing economic importance over time.",
    "source": "Source: Australian Bureau of Statistics ({year}). Data is aggregated by the Tech Council of Australia.",
    "downloadFilename": "tech_occupations_share_of_labour_force.csv",
    "dateColumn": "date",
    "valueColumn": "% of labour force in tech occupations (smoothed)",
    "endLabel": "% of labour force in tech occupations (smoothed)",
    "lineColor": "cat-3",
    "valueFormat": {"suffix": "%", "decimals": 0},
}

TOTAL_TECH_EMPLOYMENT_LINE_CONFIG = {
    "pageTitle": "Tech Vector — total employment in the direct tech sector",
    "title": "Total Employment in the Direct Tech Sector",
    "caption": "Total number of people employed by companies in the direct tech sector.",
    "source": "Source: Australian Bureau of Statistics ({year}). Data is aggregated by the Tech Council of Australia.",
    "downloadFilename": "total_employment_direct_tech_sector.csv",
    "dateColumn": "Date",
    "valueColumn": "Total number of people in the tech sector",
    "endLabel": "Total number of people in the tech sector",
    "lineColor": "cat-3",
    "valueFormat": {"decimals": 0},
}


def load_line_data(config, source_file):
    df = pd.read_csv(DATA_OUTPUT_DIR / source_file)
    df = df.sort_values(config["dateColumn"])
    dates = df[config["dateColumn"]].tolist()
    assert_iso_date(pd.Series(dates), f"{source_file} ({config['dateColumn']})")
    values = [None if pd.isna(v) else float(v) for v in df[config["valueColumn"]]]
    return {"dates": dates, "values": values}


def load_tech_share_line_data(config=TECH_SHARE_LINE_CONFIG, source_file="tech_jobs_tech_occupations_as_percent_of_labour_force.csv"):
    return load_line_data(config, source_file)


def load_total_tech_employment_line_data(config=TOTAL_TECH_EMPLOYMENT_LINE_CONFIG, source_file="jobs_in_tech_companies_WIDE.csv"):
    return load_line_data(config, source_file)


# =============================================================================
# 9. PERCENTILE BAR — salary percentiles by Job Title + Level dropdowns
# =============================================================================
PERCENTILE_BAR_CONFIG = {
    "pageTitle": "Tech Vector — salary distribution by tech role",
    "title": "Percentile remuneration per seniority level ($AUD) for common tech roles.",
    "source": "Source: Levels.fyi ({year})",
    "downloadFilename": "tech_jobs_salary_percentiles.csv",
    "jobTitleColumn": "Job Title",
    "levelColumn": "Level",
    "percentileColumn": "Label",
    "valueColumn": "Salary",
    "jobTitleDropdownLabel": "Job Title:",
    "levelDropdownLabel": "Level:",
    "defaultJobTitle": "Software Engineer",
    "levelOptions": [
        {"value": "All", "label": "All"},
        {"value": "Senior", "label": "Senior"},
        {"value": "Entry-Level", "label": "Entry-Level"},
    ],
    "defaultLevel": "All",
    "percentileOrder": ["90th", "75th", "Median", "25th"],
    "barColor": "cat-3",
    "valueFormat": {"prefix": "$", "divisor": 1000, "suffix": "K"},
}


def load_percentile_bar_data(config=PERCENTILE_BAR_CONFIG, source_file="tech_jobs_pay_within_percentile_level_occupation.csv"):
    df = pd.read_csv(DATA_OUTPUT_DIR / source_file)
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "jobTitle": row[config["jobTitleColumn"]],
            "level": row[config["levelColumn"]],
            "percentile": row[config["percentileColumn"]],
            "value": float(row[config["valueColumn"]]),
        })
    return rows


# =============================================================================
# 10. REFERENCES — the citation list at the bottom of the page, entered by
#     the TCA team. Each entry's "year" is either a fixed int (a specific
#     data vintage, e.g. the 2021 OECD R&D figures), "dynamic" (tracks the
#     build year — for sources that are "current as of last fetch"), or None
#     ("n.d." — no publication date, e.g. an ever-updating web platform).
#     "viewed": True stamps that entry with the build date, formatted the
#     same way the live site does ("16 October 2025").
# =============================================================================
REFERENCES_CONFIG = {
    "pageTitle": "Tech Vector — references",
    "title": "References",
    "caption": "Data sources cited across the Tech Vector charts.",
    "entries": [
        {
            "author": "Australian Bureau of Statistics (ABS)",
            "year": "dynamic",
            "title": "Labour Force Survey",
            "publisher": "ABS, Canberra",
            "url": None,
            "viewed": False,
        },
        {
            "author": "Workplace Gender Equality Agency (WGEA)",
            "year": "dynamic",
            "title": "WGEA Data Explorer and Employer Reporting Dataset",
            "publisher": "WGEA, Canberra",
            "url": None,
            "viewed": False,
        },
        {
            "author": "Levels.fyi",
            "year": None,
            "title": "Levels.fyi — Tech Compensation and Career Benchmarking Platform",
            "publisher": None,
            "url": "https://www.levels.fyi/",
            "viewed": True,
        },
        {
            "author": "Organisation for Economic Co-operation and Development (OECD)",
            "year": 2021,
            "title": "Gross Domestic Spending on R&D (% of GDP)",
            "publisher": "OECD Data",
            "url": "https://www.oecd.org/en/data/indicators/gross-domestic-spending-on-r-d.html",
            "viewed": True,
        },
        {
            "author": "Organisation for Economic Co-operation and Development (OECD)",
            "year": 2025,
            "title": "Skills-First Readiness and Adoption Index Dashboard",
            "publisher": "OECD Data",
            "url": "https://www.oecd.org/en/data/dashboards/skills-first-readiness-and-adoption-index.html",
            "viewed": True,
        },
        {
            "author": "Stanford University, Institute for Human-Centered Artificial Intelligence (HAI)",
            "year": "dynamic",
            "title": "Global AI Vibrancy Tool – Global AI Vibrancy Ranking",
            "publisher": "Stanford HAI",
            "url": "https://hai.stanford.edu/research/vibrancy",
            "viewed": True,
        },
    ],
}


def load_references_data(config, now):
    build_year = now.year
    # Full month name — matches the live site's "viewed 16 October 2025"
    # citation style (vs. the abbreviated month used in "Chart last updated").
    viewed_display = now.strftime("%d %B %Y")
    rows = []
    for e in config["entries"]:
        year = e["year"]
        if year == "dynamic":
            year_display = str(build_year)
        elif year is None:
            year_display = "n.d."
        else:
            year_display = str(year)
        rows.append({
            "author": e["author"],
            "yearDisplay": year_display,
            "title": e["title"],
            "publisher": e.get("publisher"),
            "url": e.get("url"),
            "viewedDisplay": viewed_display if e.get("viewed") else None,
        })
    return rows


# =============================================================================
# HTML assembly
# =============================================================================
def read_asset(name):
    return (ASSETS_DIR / name).read_text(encoding="utf-8")


def build_html(body_html, chart_js_file, data_key, config, data, last_updated=None, build_year=None):
    css = read_asset("shared.css")
    shared_js = read_asset("shared.js")
    chart_js = read_asset(chart_js_file)
    # Each chart's JS reads DATA.<data_key>.config / .data — same data_key
    # convention as when all four charts shared one combined payload, so the
    # key has to match here even though this file now carries only one
    # chart's data. lastUpdated is stamped fresh on every build rather than
    # stored in the CONFIG dicts, so it's never stale by hand.
    config_payload = dict(config)
    if last_updated:
        config_payload["lastUpdated"] = last_updated
    # A config's "source" string can carry a "{year}" placeholder for data
    # that's "current as of last fetch" (WGEA, ABS, etc.) — resolved to the
    # build year here so it's never manually bumped. A source citing a fixed
    # historical data vintage (e.g. RND_CONFIG's "OECD (2021)") just omits
    # the placeholder and stays untouched.
    if build_year and config_payload.get("source"):
        config_payload["source"] = config_payload["source"].replace("{year}", str(build_year))
    data_json = json.dumps({data_key: {"config": config_payload, "data": data}})
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
        "key": "gauge",
        "body_file": "gauge.html",
        "js_file": "gauge.js",
        "loader": load_gauge_data,
        "config": GAUGE_CONFIG,
        "out_file": "gauge.html",
    },
    {
        "key": "bar",
        "body_file": "bar_chart.html",
        "js_file": "bar_chart.js",
        "loader": load_bar_data,
        "config": BAR_CONFIG,
        "out_file": "bar_chart.html",
    },
    {
        "key": "bar",
        "body_file": "bar_chart.html",
        "js_file": "bar_chart.js",
        "loader": load_womens_pay_data,
        "config": WOMENS_PAY_CONFIG,
        "out_file": "womens_pay_scales_chart.html",
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
    {
        "key": "rankedBar",
        "body_file": "ranked_bar.html",
        "js_file": "ranked_bar.js",
        "loader": load_ai_vibrancy_data,
        "config": AI_VIBRANCY_CONFIG,
        "out_file": "ai_vibrancy_chart.html",
    },
    {
        "key": "rankedBar",
        "body_file": "ranked_bar.html",
        "js_file": "ranked_bar.js",
        "loader": load_rnd_data,
        "config": RND_CONFIG,
        "out_file": "rnd_chart.html",
    },
    {
        "key": "stackedBar",
        "body_file": "stacked_bar.html",
        "js_file": "stacked_bar.js",
        "loader": load_stacked_bar_data,
        "config": STACKED_BAR_CONFIG,
        "out_file": "womens_leadership_by_sector_chart.html",
    },
    {
        "key": "stackedSmallMultiples",
        "body_file": "stacked_bar_small_multiples.html",
        "js_file": "stacked_bar_small_multiples.js",
        "loader": load_stacked_small_multiples_data,
        "config": STACKED_SMALL_MULTIPLES_CONFIG,
        "out_file": "womens_promotion_rates_chart.html",
    },
    {
        "key": "line",
        "body_file": "line_chart.html",
        "js_file": "line_chart.js",
        "loader": load_tech_share_line_data,
        "config": TECH_SHARE_LINE_CONFIG,
        "out_file": "tech_share_of_labour_force_chart.html",
    },
    {
        "key": "line",
        "body_file": "line_chart.html",
        "js_file": "line_chart.js",
        "loader": load_total_tech_employment_line_data,
        "config": TOTAL_TECH_EMPLOYMENT_LINE_CONFIG,
        "out_file": "total_tech_employment_chart.html",
    },
    {
        "key": "percentile",
        "body_file": "percentile_bar.html",
        "js_file": "percentile_bar.js",
        "loader": load_percentile_bar_data,
        "config": PERCENTILE_BAR_CONFIG,
        "out_file": "salary_percentiles_chart.html",
    },
    {
        "key": "references",
        "body_file": "references.html",
        "js_file": "references.js",
        "loader": load_references_data,
        "config": REFERENCES_CONFIG,
        "out_file": "references.html",
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

    now = datetime.now()
    build_time = now.strftime("%Y-%m-%d %H:%M:%S")
    # Human-readable form shown on-chart, e.g. "13 Jul 2026" — matches the
    # "Chart last updated on ..." convention on the live Tech Vector site.
    build_date_display = now.strftime("%d %b %Y")
    manifest_rows = []

    for chart in CHARTS:
        print(f"Building {chart['key']}...")
        if chart["key"] == "smallMultiples":
            data = chart["loader"](chart["config"], shared_y_axis=(args.small_multiples_y_axis == "shared"))
        elif chart["key"] == "references":
            data = chart["loader"](chart["config"], now=now)
        else:
            data = chart["loader"](chart["config"])
        body_html = read_asset(chart["body_file"])
        html = build_html(body_html, chart["js_file"], chart["key"], chart["config"], data, last_updated=build_date_display, build_year=now.year)
        out_path = out_dir / chart["out_file"]
        out_path.write_text(html, encoding="utf-8")
        print(f"  wrote {out_path}")
        title = chart["config"].get("title") or chart["config"].get("pageTitle", "")
        manifest_rows.append([chart["out_file"], title, build_time])

    manifest_path = out_dir / "chart_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Chart File", "Title", "Last Updated"])
        writer.writerows(manifest_rows)
    print(f"  wrote {manifest_path}")

    print(f"\nDone. Open the files in {out_dir} directly in a browser.")


if __name__ == "__main__":
    main()
