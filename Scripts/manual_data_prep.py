#!/usr/bin/env python3
"""manual_data_prep.py

Usage:
  python manual_data_prep.py                                # defaults to --dir Data/input/manual_pull/
  python manual_data_prep.py input.csv [output.csv]
  python manual_data_prep.py --inplace input.csv
  python manual_data_prep.py --dir Data/input/manual_pull/  # process all CSVs in dir

This script performs the following cleaning steps on CSV files:
- Remove the ABS TableBuilder header block (leading rows up through the third
  blank row) and the trailing footer block (the "Dataset:"/"INFO"/"Copyright"
  notes at the end of the export).
- Delete any columns whose header ends with " - Annotations" or " - RSE".
- If the second row (after removal of metadata rows) is empty except for the first column, delete it.
- Remove ABS "Total" rows: a "Total" in the first column marks a trailing
  grand-total block covering the whole time series, so that row and everything
  after it is dropped; a "Total" in any other column marks a per-period
  subtotal, so only that row is dropped.
- Delete rows where all cells except the first column are numeric zeros (e.g. 0, 0.0, or "0") and convertible to float.
- Drop the leaked real-header row (the ABS labels row that lands as the first
  data row) and the trailing all-empty column, then rename the remaining
  columns to Date, Metric, Count (3 columns) or Date, Metric, Occupation,
  Count (4 columns).
- Forward-fill the Date and Metric columns.
- Drop rows where Metric is "Non Tech Sector Industries" and Occupation is
  "Non tech occupations" (only when an Occupation column is present).
- For tech_jobs_in_australia specifically: sum Count per Date and collapse
  Metric to "Tech jobs in Australia".
- Add a "Rolling Average" column: a 4-period rolling mean of Count computed
  within each Metric's own chronological series (first 3 periods are blank).

By default the script writes cleaned files with suffix `_cleaned.csv` next to the input file.
Use `--inplace` to overwrite the original file (a backup is not created automatically).
"""

from pathlib import Path
import argparse
import pandas as pd
import sys


def is_zero_string(val: object) -> bool:
    """Return True if val represents numeric zero (after stripping and removing thousand separators).
    Non-numeric or empty strings return False.
    """
    if pd.isna(val):
        return False
    s = str(val).strip()
    if s == "":
        return False
    # remove common thousand separators
    s_clean = s.replace(',', '')
    try:
        f = float(s_clean)
        return f == 0.0
    except Exception:
        return False


def find_top_cutoff(lines: list) -> int:
    """Return the 0-based index of the first line to keep.

    ABS TableBuilder exports have a header block (title, filters, blank
    separators) ending at the third blank line, immediately before the
    column-header row(s).
    """
    blank_count = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            blank_count += 1
            if blank_count == 3:
                return i + 1
    return 0


_FOOTER_MARKERS = ("dataset:", "np rse data is concealed")


def find_bottom_cutoff(lines: list) -> int:
    """Return the 0-based index of the first line of the trailing footer block.

    ABS TableBuilder exports end with a footer starting at a note such as
    'np RSE data is concealed' and/or a '"Dataset: ..."' line. Falls back to
    keeping everything if no such marker exists.
    """
    for i, line in enumerate(lines):
        stripped = line.strip().strip('"').lower()
        if any(stripped.startswith(marker) for marker in _FOOTER_MARKERS):
            while i > 0 and lines[i - 1].strip() == "":
                i -= 1
            return i
    return len(lines)


def strip_total_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove ABS "Total" rows.

    A "Total" in the first column marks a trailing grand-total block that
    summarises the whole time series, so that row and everything after it is
    dropped. A "Total" in any other column marks a per-period subtotal, so
    only that row is dropped.
    """
    if df.shape[1] == 0 or df.empty:
        return df

    first_col = df.iloc[:, 0].astype(str).str.strip()
    grand_total_rows = first_col[first_col == "Total"]
    if len(grand_total_rows) > 0:
        cutoff_pos = df.index.get_loc(grand_total_rows.index[0])
        df = df.iloc[:cutoff_pos]

    other_cols = df.iloc[:, 1:]
    if other_cols.shape[1] > 0:
        subtotal_mask = other_cols.apply(lambda col: col.astype(str).str.strip() == "Total").any(axis=1)
        df = df.loc[~subtotal_mask]

    return df


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    # Operate on a copy
    df = df.copy()
    df = df.reset_index(drop=True)

    # Remove ABS "Total" summary rows
    df = strip_total_rows(df)
    df = df.reset_index(drop=True)

    # Drop columns ending with given suffixes
    drop_suffixes = ("Annotations", "RSE")
    cols_to_drop = [c for c in df.columns if any(str(c).endswith(s) for s in drop_suffixes)]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    # If the second row (index 1) is empty except first column, drop it
    if df.shape[0] >= 2:
        second_row = df.iloc[1]
        rest = [x for x in second_row.iloc[1:]]
        rest_empty = all((pd.isna(x) or str(x).strip() == "") for x in rest)
        if rest_empty:
            df = df.drop(df.index[1]).reset_index(drop=True)

    return df


def promote_real_header(df: pd.DataFrame) -> pd.DataFrame:
    """Drop the leaked ABS labels row and trailing empty column, then rename
    the remaining columns to Date, Metric, Count (or Date, Metric, Occupation,
    Count for a 4-column table).
    """
    if df.shape[0] == 0:
        return df

    # The first data row is the real ABS column-labels row (e.g. "Survey
    # month", "Industry of main job ..."), not data.
    df = df.iloc[1:].reset_index(drop=True)

    # Drop the trailing all-empty column left by ABS's trailing comma.
    if df.shape[1] > 0:
        last_col = df.columns[-1]
        if (df[last_col].isna() | (df[last_col].astype(str).str.strip() == "")).all():
            df = df.drop(columns=[last_col])

    n_cols = df.shape[1]
    if n_cols == 3:
        df.columns = ["Date", "Metric", "Count"]
    elif n_cols == 4:
        df.columns = ["Date", "Metric", "Occupation", "Count"]
    else:
        raise ValueError(f"Unexpected column count ({n_cols}) after cleaning; expected 3 or 4")

    return df


def ffill_key_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = df["Date"].ffill()
    df["Metric"] = df["Metric"].ffill()
    return df


def drop_non_tech_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that are Non Tech Sector Industries x Non tech occupations."""
    if "Occupation" not in df.columns:
        return df
    mask = (df["Metric"] == "Non Tech Sector Industries") & (df["Occupation"] == "Non tech occupations")
    return df.loc[~mask].reset_index(drop=True)


def aggregate_tech_jobs_in_australia(df: pd.DataFrame) -> pd.DataFrame:
    """Sum Count per Date across the remaining Metric/Occupation breakdown,
    collapsing the result to a single "Tech jobs in Australia" series.
    """
    df = df.copy()
    df["Count"] = pd.to_numeric(df["Count"], errors="coerce")
    summed = df.groupby("Date", as_index=False)["Count"].sum()
    summed["Count"] = summed["Count"].round(1)
    summed["Metric"] = "Tech jobs in Australia"
    sort_key = pd.to_datetime(summed["Date"], format="%b-%y", errors="coerce")
    summed = summed.assign(_sort_key=sort_key).sort_values("_sort_key").drop(columns="_sort_key")
    return summed[["Date", "Metric", "Count"]].reset_index(drop=True)


def add_rolling_average(df: pd.DataFrame) -> pd.DataFrame:
    """Add a "Rolling Average" column: a 4-period rolling mean of Count within
    each Metric's own chronological series (blank for the first 3 periods).
    """
    df = df.copy()
    df["Count"] = pd.to_numeric(df["Count"], errors="coerce")
    sort_key = pd.to_datetime(df["Date"], format="%b-%y", errors="coerce")
    order = df.assign(_sort_key=sort_key).sort_values(["Metric", "_sort_key"]).index
    rolling = df.loc[order].groupby("Metric")["Count"].transform(lambda s: s.rolling(4).mean())
    df["Rolling Average"] = rolling.reindex(df.index).round(2)
    return df


def process_file(path_in: Path, path_out: Path, inplace: bool = False):
    print(f"Processing: {path_in}")
    # Read raw text and strip metadata lines before parsing into CSV
    try:
        text = path_in.read_text(encoding='utf-8', errors='replace')
    except Exception:
        try:
            text = path_in.read_text(encoding='latin-1', errors='replace')
        except Exception as e:
            print(f"Failed to read file {path_in}: {e}")
            return

    lines = text.splitlines()
    n_lines = len(lines)

    start_idx = min(find_top_cutoff(lines), n_lines)
    end_idx = min(find_bottom_cutoff(lines), n_lines)
    # slice lines to keep
    keep_lines = lines[start_idx:end_idx]
    if not keep_lines:
        # fallback: try reading entire file as CSV
        keep_text = text
    else:
        keep_text = "\n".join(keep_lines)

    from io import StringIO
    try:
        df = pd.read_csv(StringIO(keep_text), dtype=str, engine='python')
    except Exception as e:
        try:
            df = pd.read_csv(StringIO(keep_text), dtype=str, engine='python', encoding='latin-1')
        except Exception as e2:
            print(f"Failed to parse CSV after stripping metadata for {path_in}: {e} / {e2}")
            return

    cleaned = clean_df(df)
    cleaned = promote_real_header(cleaned)
    cleaned = ffill_key_columns(cleaned)
    cleaned = drop_non_tech_rows(cleaned)
    if path_in.stem == 'tech_jobs_in_australia':
        cleaned = aggregate_tech_jobs_in_australia(cleaned)
    cleaned = add_rolling_average(cleaned)

    if inplace:
        out_path = path_in
    else:
        out_path = path_out

    cleaned.to_csv(out_path, index=False, encoding='utf-8')
    print(f"Wrote cleaned CSV: {out_path} (rows: {len(cleaned)})")


DEFAULT_DIR = Path(__file__).resolve().parent.parent / 'Data' / 'input' / 'manual_pull'


def main():
    parser = argparse.ArgumentParser(description="Clean ABS TableBuilder CSV files by removing metadata and annotations.")
    parser.add_argument('input', nargs='?', help='Input CSV file path (optional; defaults to --dir target if omitted)')
    parser.add_argument('output', nargs='?', help='Output CSV file path (optional). If omitted and --inplace not set, _cleaned.csv is used.')
    parser.add_argument('--inplace', action='store_true', help='Overwrite input file with cleaned output')
    parser.add_argument('--dir', help=f'Directory containing CSVs to process (default: {DEFAULT_DIR})')
    args = parser.parse_args()

    if args.dir:
        p = Path(args.dir)
    elif args.input:
        p = Path(args.input)
    else:
        p = Path(DEFAULT_DIR)

    if p.is_dir():
        csvs = [f for f in p.glob('*.csv') if not f.stem.endswith('_cleaned')]
        if not csvs:
            print(f"No CSV files found in {p}")
            sys.exit(1)
        for f in csvs:
            out = f.with_name(f.stem + "_cleaned.csv") if not args.inplace else f
            process_file(f, out, inplace=args.inplace)
        return

    if not p.exists():
        print(f"Input file not found: {p}")
        sys.exit(2)

    out_path = None
    if args.output:
        out_path = Path(args.output)
    else:
        if not args.inplace:
            out_path = p.with_name(p.stem + "_cleaned.csv")

    process_file(p, out_path, inplace=args.inplace)


if __name__ == '__main__':
    main()
