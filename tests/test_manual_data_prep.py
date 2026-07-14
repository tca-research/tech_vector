"""Tests for scripts/manual_data_prep.py — the ABS TableBuilder CSV cleaning
pipeline. This file is where the "Aug-06 parses as day=06/year=2000" class of
bug lives (see DATA_FORMAT.md and CLAUDE.md), so date-order/date-format
behavior gets deliberately exercised here, not just happy-path shapes.
"""
import numpy as np
import pandas as pd
import pytest

import manual_data_prep as mdp


# ---------------------------------------------------------------------------
# is_zero_string
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("0", True),
    ("0.0", True),
    ("  0  ", True),
    ("1,000", False),
    ("1,000.0", False),
    ("", False),
    ("abc", False),
    (np.nan, False),
    # Only thousand-separators are stripped, not currency symbols — a "$0"
    # cell is NOT treated as zero by this function (float("$0") raises,
    # caught by the except branch). Documenting the actual behavior, not an
    # assumption about what it "should" do.
    ("$0", False),
])
def test_is_zero_string(value, expected):
    assert mdp.is_zero_string(value) is expected


# ---------------------------------------------------------------------------
# find_top_cutoff / find_bottom_cutoff
# ---------------------------------------------------------------------------

def test_find_top_cutoff_returns_index_after_third_blank_line():
    lines = ["Table 1: Some title", "Filters: blah", "", "", "", "Date,Metric,Count", "Aug-06,X,1"]
    assert mdp.find_top_cutoff(lines) == 5


def test_find_top_cutoff_falls_back_to_zero_without_three_blanks():
    lines = ["Date,Metric,Count", "", "Aug-06,X,1"]
    assert mdp.find_top_cutoff(lines) == 0


@pytest.mark.parametrize("marker_line", [
    "Dataset: LM8",
    '"Dataset: LM8"',
    "np RSE data is concealed where applicable.",
    "NP RSE DATA IS CONCEALED",
])
def test_find_bottom_cutoff_detects_footer_marker_case_and_quote_insensitive(marker_line):
    lines = ["Date,Metric,Count", "Aug-06,X,1", marker_line]
    assert mdp.find_bottom_cutoff(lines) == 2


def test_find_bottom_cutoff_walks_back_over_blank_lines_before_marker():
    lines = ["Date,Metric,Count", "Aug-06,X,1", "", "", "Dataset: LM8"]
    assert mdp.find_bottom_cutoff(lines) == 2


def test_find_bottom_cutoff_keeps_everything_without_a_marker():
    lines = ["Date,Metric,Count", "Aug-06,X,1"]
    assert mdp.find_bottom_cutoff(lines) == 2


# ---------------------------------------------------------------------------
# strip_total_rows
# ---------------------------------------------------------------------------

def test_strip_total_rows_truncates_at_grand_total_in_first_column():
    df = pd.DataFrame({
        "Date": ["Aug-06", "Nov-06", "Total", "Notes"],
        "Metric": ["Tech", "Tech", "", ""],
        "Count": ["1", "2", "3", ""],
    })
    out = mdp.strip_total_rows(df)
    assert out["Date"].tolist() == ["Aug-06", "Nov-06"]


def test_strip_total_rows_drops_only_the_subtotal_row_in_other_columns():
    df = pd.DataFrame({
        "Date": ["Aug-06", "Aug-06", "Nov-06"],
        "Metric": ["Tech", "Total", "Tech"],
        "Count": ["1", "5", "2"],
    })
    out = mdp.strip_total_rows(df)
    # Only the "Total" row itself is removed — rows after it survive, unlike
    # a first-column "Total" which truncates everything after it.
    assert out["Date"].tolist() == ["Aug-06", "Nov-06"]
    assert "Total" not in out["Metric"].tolist()


def test_strip_total_rows_handles_empty_dataframe():
    df = pd.DataFrame()
    assert mdp.strip_total_rows(df).empty


# ---------------------------------------------------------------------------
# clean_df
# ---------------------------------------------------------------------------

def test_clean_df_drops_annotation_and_rse_columns():
    df = pd.DataFrame({
        "Date": ["Aug-06"],
        "Value": ["1"],
        "Value - Annotations": ["note"],
        "Value - RSE": ["0.1"],
    })
    out = mdp.clean_df(df)
    assert list(out.columns) == ["Date", "Value"]


def test_clean_df_drops_second_row_when_empty_except_first_column():
    df = pd.DataFrame({
        "Date": ["header-leak", "", "Aug-06"],
        "Metric": ["Survey month", np.nan, "Tech"],
        "Count": ["Count", np.nan, "1"],
    })
    out = mdp.clean_df(df)
    assert len(out) == 2
    assert out.iloc[1]["Date"] == "Aug-06"


# ---------------------------------------------------------------------------
# promote_real_header
# ---------------------------------------------------------------------------

def test_promote_real_header_renames_three_columns():
    df = pd.DataFrame({
        "c1": ["Survey month", "Aug-06"],
        "c2": ["Industry", "Tech"],
        "c3": ["Count", "150"],
    })
    out = mdp.promote_real_header(df)
    assert list(out.columns) == ["Date", "Metric", "Count"]
    assert out.iloc[0].tolist() == ["Aug-06", "Tech", "150"]


def test_promote_real_header_renames_four_columns():
    df = pd.DataFrame({
        "c1": ["Survey month", "Aug-06"],
        "c2": ["Industry", "Tech Sector Industries"],
        "c3": ["Occupation", "Tech occupations"],
        "c4": ["Count", "150"],
    })
    out = mdp.promote_real_header(df)
    assert list(out.columns) == ["Date", "Metric", "Occupation", "Count"]


def test_promote_real_header_drops_trailing_all_empty_column():
    df = pd.DataFrame({
        "c1": ["Survey month", "Aug-06"],
        "c2": ["Industry", "Tech"],
        "c3": ["Count", "150"],
        "c4": [np.nan, np.nan],
    })
    out = mdp.promote_real_header(df)
    assert list(out.columns) == ["Date", "Metric", "Count"]


def test_promote_real_header_raises_on_unexpected_column_count():
    df = pd.DataFrame({"c1": ["a", "b"], "c2": ["c", "d"]})
    with pytest.raises(ValueError, match="Unexpected column count"):
        mdp.promote_real_header(df)


def test_promote_real_header_returns_empty_df_unchanged():
    df = pd.DataFrame(columns=["a", "b", "c"])
    out = mdp.promote_real_header(df)
    assert out.empty


# ---------------------------------------------------------------------------
# ffill_key_columns
# ---------------------------------------------------------------------------

def test_ffill_key_columns_forward_fills_date_and_metric():
    df = pd.DataFrame({
        "Date": ["Aug-06", np.nan, np.nan],
        "Metric": ["Tech Sector Industries", np.nan, np.nan],
        "Occupation": ["Tech occupations", "Non tech occupations", "Tech occupations"],
        "Count": ["1", "2", "3"],
    })
    out = mdp.ffill_key_columns(df)
    assert out["Date"].tolist() == ["Aug-06", "Aug-06", "Aug-06"]
    assert out["Metric"].tolist() == ["Tech Sector Industries"] * 3


# ---------------------------------------------------------------------------
# drop_non_tech_rows
# ---------------------------------------------------------------------------

def test_drop_non_tech_rows_removes_non_tech_by_non_tech_combo():
    df = pd.DataFrame({
        "Metric": ["Tech Sector Industries", "Non Tech Sector Industries", "Non Tech Sector Industries"],
        "Occupation": ["Tech occupations", "Non tech occupations", "Tech occupations"],
        "Count": ["1", "2", "3"],
    })
    out = mdp.drop_non_tech_rows(df)
    assert len(out) == 2
    assert "Non tech occupations" not in out["Occupation"].tolist()


def test_drop_non_tech_rows_is_noop_without_occupation_column():
    df = pd.DataFrame({"Metric": ["Non Tech Sector Industries"], "Count": ["1"]})
    out = mdp.drop_non_tech_rows(df)
    assert len(out) == 1


# ---------------------------------------------------------------------------
# aggregate_tech_jobs_in_australia
# ---------------------------------------------------------------------------

def test_aggregate_tech_jobs_in_australia_sums_per_date_and_sorts_chronologically():
    # Deliberately out of chronological order (Nov before Aug) — the ABS
    # export's own row order can't be trusted (see DATA_FORMAT.md); this
    # asserts the function actually re-sorts by parsed date, not row order.
    df = pd.DataFrame({
        "Date": ["Nov-06", "Nov-06", "Aug-06", "Aug-06"],
        "Metric": ["Tech Sector Industries", "Non Tech Sector Industries"] * 2,
        "Occupation": ["Tech occupations"] * 4,
        "Count": ["100", "200", "10", "20"],
    })
    out = mdp.aggregate_tech_jobs_in_australia(df)
    assert out["Date"].tolist() == ["Aug-06", "Nov-06"]
    assert out["Count"].tolist() == [30.0, 300.0]
    assert (out["Metric"] == "Tech jobs in Australia").all()


# ---------------------------------------------------------------------------
# add_rolling_average
# ---------------------------------------------------------------------------

def test_add_rolling_average_is_a_4_period_mean_per_metric_in_original_row_order():
    # Two metrics interleaved out of chronological order — the function must
    # sort per-metric internally to compute the rolling mean, but the
    # returned Rolling Average column must still align to df's ORIGINAL row
    # order (main pipeline consumers expect that), not the sorted order.
    df = pd.DataFrame({
        "Date": ["Mar-06", "Feb-06", "Jan-06", "Apr-06", "Jan-06", "Feb-06", "Mar-06", "Apr-06"],
        "Metric": ["A", "A", "A", "A", "B", "B", "B", "B"],
        "Count": ["30", "20", "10", "40", "100", "200", "300", "400"],
    })
    out = mdp.add_rolling_average(df)

    # Row order unchanged from input.
    assert out["Date"].tolist() == df["Date"].tolist()
    assert out["Metric"].tolist() == df["Metric"].tolist()

    # Metric A's 4th chronological period (Apr-06, row index 3) is the mean
    # of Jan/Feb/Mar/Apr = (10+20+30+40)/4 = 25.0; earlier periods are blank.
    a_rows = out[out["Metric"] == "A"].set_index("Date")
    assert pd.isna(a_rows.loc["Jan-06", "Rolling Average"])
    assert pd.isna(a_rows.loc["Feb-06", "Rolling Average"])
    assert pd.isna(a_rows.loc["Mar-06", "Rolling Average"])
    assert a_rows.loc["Apr-06", "Rolling Average"] == 25.0

    b_rows = out[out["Metric"] == "B"].set_index("Date")
    assert b_rows.loc["Apr-06", "Rolling Average"] == 250.0
