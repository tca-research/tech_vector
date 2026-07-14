"""Tests for scripts/charts/build_charts.py's own helper/loader functions —
not the full CLI (that's covered end-to-end by tests/test_chart_rendering.py
against the already-built charts/*.html files). Loader tests monkeypatch the
module's DATA_OUTPUT_DIR/PULL_DIR/MANUAL_PULL_DIR constants to point at
per-test tmp_path fixture CSVs, the same way build_charts.py itself resolves
them relative to the repo root.
"""
import json

import pandas as pd
import pytest

import build_charts as bc


# ---------------------------------------------------------------------------
# money_to_float / parse_metric_value
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("$1,234.56", 1234.56),
    ("-$5", -5.0),
    ("8.9%", 8.9),
    ("100", 100.0),
])
def test_money_to_float(raw, expected):
    assert bc.money_to_float(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("979k", 979_000.0),
    ("$248.5B", 248_500_000_000.0),
    ("8.9%", 8.9),
    ("4.6%", 4.6),
    ("1.2M", 1_200_000.0),
])
def test_parse_metric_value_applies_unit_suffix_multiplier(raw, expected):
    assert bc.parse_metric_value(raw) == expected


# ---------------------------------------------------------------------------
# assert_iso_date
# ---------------------------------------------------------------------------

def test_assert_iso_date_accepts_full_and_year_month_forms():
    bc.assert_iso_date(pd.Series(["2020-01-01", "2020-01"]), "test")  # no raise


def test_assert_iso_date_rejects_abs_style_month_abbrev_dates():
    # The exact historical bug this guard exists for: "Aug-06" parses in JS
    # as day=06/year=2000, silently, with no error — see DATA_FORMAT.md.
    with pytest.raises(ValueError, match="non-ISO date"):
        bc.assert_iso_date(pd.Series(["Aug-06"]), "test.csv")


# ---------------------------------------------------------------------------
# read_previous_chart_state
# ---------------------------------------------------------------------------

def test_read_previous_chart_state_returns_all_none_when_file_missing(tmp_path):
    result = bc.read_previous_chart_state(tmp_path / "does_not_exist.html", "gauge")
    assert result == (None, None, None, None)


def test_read_previous_chart_state_returns_all_none_on_malformed_html(tmp_path):
    path = tmp_path / "chart.html"
    path.write_text("<html>no chart-data script tag here</html>", encoding="utf-8")
    assert bc.read_previous_chart_state(path, "gauge") == (None, None, None, None)


def test_read_previous_chart_state_round_trips_a_real_build_html_output(tmp_path, monkeypatch):
    monkeypatch.setattr(bc, "read_asset", lambda name: f"/* {name} */")
    html = bc.build_html(
        body_html="<div></div>", chart_js_file="gauge.js", data_key="gauge",
        config={"title": "T", "source": "Source: WGEA ({year})."}, data=[{"a": 1}],
        last_updated="13 Jul 2026", build_year=2026,
    )
    path = tmp_path / "chart.html"
    path.write_text(html, encoding="utf-8")

    data_json, last_updated, source, source_template = bc.read_previous_chart_state(path, "gauge")
    assert json.loads(data_json) == [{"a": 1}]
    assert last_updated == "13 Jul 2026"
    assert source == "Source: WGEA (2026)."
    assert source_template == "Source: WGEA ({year})."


# ---------------------------------------------------------------------------
# build_html — {year} resolution in "source" vs "title"
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_assets(monkeypatch):
    monkeypatch.setattr(bc, "read_asset", lambda name: f"/* {name} */")


def _config_payload_from_html(html, data_key):
    match = bc._CHART_DATA_RE.search(html)
    return json.loads(match.group(1))[data_key]["config"]


def test_build_html_resolves_source_year_from_build_year(fake_assets):
    html = bc.build_html(
        "<div></div>", "gauge.js", "gauge",
        {"source": "Source: WGEA ({year})."}, data=[], build_year=2026,
    )
    cfg = _config_payload_from_html(html, "gauge")
    assert cfg["source"] == "Source: WGEA (2026)."


def test_build_html_resolved_source_overrides_build_year_substitution(fake_assets):
    html = bc.build_html(
        "<div></div>", "gauge.js", "gauge",
        {"source": "Source: WGEA ({year})."}, data=[],
        build_year=2026, resolved_source="Source: WGEA (2024).",
    )
    cfg = _config_payload_from_html(html, "gauge")
    assert cfg["source"] == "Source: WGEA (2024)."
    # The raw, unresolved template is still stashed for next time regardless.
    assert cfg["_sourceTemplate"] == "Source: WGEA ({year})."


def test_build_html_resolves_title_year_from_title_year_not_build_year(fake_assets):
    # This is the interactiveLine title bug: title's "{year}" must reflect
    # the chart's own data range, not today's build date — build_year and
    # title_year are deliberately different here to prove that.
    html = bc.build_html(
        "<div></div>", "interactive_line.js", "interactiveLine",
        {"title": "Employed persons by tech occupation, 1986–{year}"}, data=[],
        build_year=2026, title_year=2025,
    )
    cfg = _config_payload_from_html(html, "interactiveLine")
    assert cfg["title"] == "Employed persons by tech occupation, 1986–2025"


def test_build_html_leaves_title_unresolved_without_title_year(fake_assets):
    html = bc.build_html(
        "<div></div>", "interactive_line.js", "interactiveLine",
        {"title": "Employed persons by tech occupation, 1986–{year}"}, data=[],
        build_year=2026,
    )
    cfg = _config_payload_from_html(html, "interactiveLine")
    assert cfg["title"] == "Employed persons by tech occupation, 1986–{year}"


# ---------------------------------------------------------------------------
# load_gauge_data
# ---------------------------------------------------------------------------

def test_load_gauge_data_computes_progress_percent_and_matches_colors(tmp_path, monkeypatch):
    monkeypatch.setattr(bc, "MANUAL_PULL_DIR", tmp_path)
    pd.DataFrame([
        {"label": "Tech Jobs", "current_label": "600k", "target_label": "1.2M", "description": "d1"},
        {"label": "Unknown Metric", "current_label": "50", "target_label": "0", "description": "d2"},
    ]).to_csv(tmp_path / "headline_metrics.csv", index=False)

    rows = bc.load_gauge_data(config=bc.GAUGE_CONFIG, source_file="headline_metrics.csv")

    tech_jobs = next(r for r in rows if r["label"] == "Tech Jobs")
    assert tech_jobs["value"] == 50.0  # 600,000 / 1,200,000 * 100
    assert tech_jobs["filledColor"] == bc.GAUGE_CONFIG["colors"]["Tech Jobs"]["filledColor"]

    unknown = next(r for r in rows if r["label"] == "Unknown Metric")
    assert unknown["value"] == 0.0  # target_num falsy -> 0.0, not a ZeroDivisionError
    assert unknown["filledColor"] == bc.GAUGE_CONFIG["defaultColors"]["filledColor"]


# ---------------------------------------------------------------------------
# load_line_data
# ---------------------------------------------------------------------------

def test_load_line_data_sorts_by_date_and_preserves_nulls(tmp_path, monkeypatch):
    monkeypatch.setattr(bc, "DATA_OUTPUT_DIR", tmp_path)
    pd.DataFrame({
        "date": ["2020-02-01", "2020-01-01", "2020-03-01"],
        "value": [2.0, 1.0, None],
    }).to_csv(tmp_path / "series.csv", index=False)

    data = bc.load_line_data({"dateColumn": "date", "valueColumn": "value"}, "series.csv")
    assert data["dates"] == ["2020-01-01", "2020-02-01", "2020-03-01"]
    assert data["values"] == [1.0, 2.0, None]


def test_load_line_data_raises_on_non_iso_dates(tmp_path, monkeypatch):
    monkeypatch.setattr(bc, "DATA_OUTPUT_DIR", tmp_path)
    pd.DataFrame({"date": ["Jan-20"], "value": [1.0]}).to_csv(tmp_path / "series.csv", index=False)

    with pytest.raises(ValueError, match="non-ISO date"):
        bc.load_line_data({"dateColumn": "date", "valueColumn": "value"}, "series.csv")


# ---------------------------------------------------------------------------
# load_small_multiples_data — the highest-risk loader (raw ABS-shaped export
# + the "Aug-06 -> 2006-08-01, not day=06/year=2000" conversion).
# ---------------------------------------------------------------------------

_RAW_TECH_JOBS_CSV = "\n".join([
    "Table 1: Some title",
    "Filters: blah",
    "", "", "",  # 3rd blank triggers find_top_cutoff
    "Survey month,Industry group,Occupation group,Count",
    "Date,Metric,Occupation,Count",  # leaked ABS labels row — dropped
    "Nov-06,Tech Sector Industries,Tech occupations,155.0",
    "Aug-06,Tech Sector Industries,Tech occupations,150.0",
    "Aug-06,Tech Sector Industries,Non tech occupations,90.0",
    "Aug-06,Non Tech Sector Industries,Tech occupations,260.0",
    "Aug-06,Non Tech Sector Industries,Non tech occupations,500.0",  # excludeCombo
    "",
    "Dataset: LM8",
])


@pytest.fixture
def small_multiples_fixture_dirs(tmp_path, monkeypatch):
    manual_pull = tmp_path / "manual_pull"
    pull = tmp_path / "automated_pull"
    manual_pull.mkdir()
    pull.mkdir()
    (manual_pull / "tech_jobs_in_australia.csv").write_text(_RAW_TECH_JOBS_CSV, encoding="utf-8")
    pd.DataFrame({
        "date": ["2017-12-15", "2018-01-15", "2018-01-20", "2018-02-10"],
        "value": [5.9, 5.5, 5.6, 5.4],
    }).to_csv(pull / "abs_unemployment_rate.csv", index=False)
    pd.DataFrame({
        "date": ["2018-01-01", "2018-02-01"],
        "value": [1.5, 1.5],
    }).to_csv(pull / "rba_cash_rate.csv", index=False)
    monkeypatch.setattr(bc, "MANUAL_PULL_DIR", manual_pull)
    monkeypatch.setattr(bc, "PULL_DIR", pull)


def test_load_small_multiples_data_converts_abs_dates_to_iso_correctly(small_multiples_fixture_dirs):
    result = bc.load_small_multiples_data(config=bc.SMALL_MULTIPLES_CONFIG, shared_y_axis=True)

    # Aug-06 must become 2006-08-01 (year 2006), not the silent 2000-08-06
    # misparse this exact guard exists to prevent.
    tech_by_tech = result["techSectorTechOcc"]
    assert tech_by_tech == [
        {"date": "2006-08-01", "value": 150.0},
        {"date": "2006-11-01", "value": 155.0},
    ]


def test_load_small_multiples_data_applies_exclude_combo_and_shared_y_axis_flag(small_multiples_fixture_dirs):
    result = bc.load_small_multiples_data(config=bc.SMALL_MULTIPLES_CONFIG, shared_y_axis=False)

    assert result["nonTechSectorTechOcc"] == [{"date": "2006-08-01", "value": 260.0}]
    assert result["techSectorNonTechOcc"] == [{"date": "2006-08-01", "value": 90.0}]
    # excludeCombo (Non Tech Sector Industries x Non tech occupations) has no
    # configured panel of its own, so its removal is verified structurally:
    # the fixture's 5 rows minus the excluded one is 4, spread across
    # exactly the three configured panels above with none left over.
    total_rows = sum(len(result[p["key"]]) for p in bc.SMALL_MULTIPLES_CONFIG["occupationPanels"])
    assert total_rows == 4
    assert result["sharedYAxis"] is False


def test_load_small_multiples_data_filters_macro_series_to_start_date(small_multiples_fixture_dirs):
    result = bc.load_small_multiples_data(config=bc.SMALL_MULTIPLES_CONFIG)

    # 2017-12 predates SMALL_MULTIPLES_CONFIG's startDate ("2018-01") and
    # must be dropped; within 2018-01, the *last* same-month observation
    # wins (2018-01-20's 5.6, not 2018-01-15's 5.5).
    assert result["macro"]["unemployment"] == [
        {"date": "2018-01", "value": 5.6},
        {"date": "2018-02", "value": 5.4},
    ]
    assert result["macro"]["cashRate"] == [
        {"date": "2018-01", "value": 1.5},
        {"date": "2018-02", "value": 1.5},
    ]
