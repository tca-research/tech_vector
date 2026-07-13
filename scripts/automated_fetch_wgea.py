"""
Pulls WGEA (Workplace Gender Equality Agency) data from TWO sources and
produces three CSVs:

    SOURCE                                    -> OUTPUT FILE
    -----------------------------------------------------------------------
    wgea.gov.au direct xlsx,
      sheet "2. Employers" (skipping the
      first 3 header rows)                    -> wgea_salary_data_{YEAR}.csv
    data.gov.au CKAN resource
      "wgea_public_dataset_{YEAR}.zip",
      member matching "workforce composition" -> wgea_workforce_composition_{YEAR}.csv
    same zip, member matching
      "management statistics"                 -> wgea_workforce_management_statistics_{YEAR}.csv

YEAR is always CURRENT_YEAR = str(datetime.now().year - 1), computed fresh
each run - never hardcoded.

WHY TWO SOURCES
---------------
The Employer Gender Pay Gaps Spreadsheet (with the salary sheet) is only
published on wgea.gov.au directly, not registered on data.gov.au. The
workforce composition and management statistics data are bundled together
inside a single zip - "wgea_public_dataset_{YEAR}.zip" - that IS registered
as a CKAN resource on data.gov.au, located via package_search (your
original approach, fixed for WGEA's actual "YYYY-YY" financial-year naming
- see below).

BUG FIX FROM YOUR ORIGINAL SCRIPT
-----------------------------------
WGEA names things by financial year, e.g. "2024-25", not a bare "2025".
`"2025" in "2024-25"` is False in Python, so a plain year-substring check
would never match real WGEA filenames. Fixed by also checking the
"YYYY-YY" financial-year label anywhere matching against a year happens.

NOTE ON ROBOTS.TXT
------------------
wgea.gov.au's robots.txt disallows crawling `/sites/default/files/` and
`*.xlsx` site-wide (looks like generic Drupal boilerplate blocking the
whole uploads directory from search crawlers, not something aimed at this
dataset specifically). The data.gov.au CKAN API calls are unaffected by
this - only the direct salary-sheet download touches wgea.gov.au. Worth a
quick check with WGEA before running that part on an unattended schedule.
"""

import io
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

# data/ lives alongside scripts/ at the repo root, not inside scripts/.
DATA_INPUT_AUTOMATED_PULL = Path(__file__).resolve().parent.parent / "data" / "input" / "automated_pull"

CURRENT_YEAR = str(datetime.now().year - 1)
FY_LABEL = f"{int(CURRENT_YEAR) - 1}-{CURRENT_YEAR[2:]}"  # e.g. "2024-25"

CKAN_API_URL = "https://data.gov.au/data/api/3/action/package_search"
WGEA_URL = "https://www.wgea.gov.au/sites/default/files/documents/Employer-Gender-Pay-Gaps-Spreadsheet.xlsx"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def download_bytes(url: str, session: requests.Session) -> bytes:
    print(f"Downloading {url} ...", file=sys.stderr)
    resp = session.get(url, timeout=180)
    resp.raise_for_status()
    print(f"Downloaded {len(resp.content):,} bytes", file=sys.stderr)
    return resp.content


def bytes_to_dataframe(content: bytes, filename_hint: str) -> pd.DataFrame:
    """Loads CSV or Excel bytes into a DataFrame based on the filename's
    extension, with a CSV-then-Excel fallback if the extension is unclear."""
    lower = filename_hint.lower()
    if lower.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content))
    if lower.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    try:
        return pd.read_csv(io.BytesIO(content))
    except Exception:
        return pd.read_excel(io.BytesIO(content))


def find_by_keyword(names: list, keyword: str, label: str) -> str:
    """
    Case-insensitive substring match of `keyword` against a list of names
    (sheet names, zip member names, etc). Raises with the full list on zero
    or multiple matches, so ambiguity/naming drift fails loudly with
    useful info instead of silently grabbing the wrong thing.
    """
    candidates = [n for n in names if keyword.lower() in n.lower()]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise ValueError(f"Multiple {label} match keyword '{keyword}': {candidates}. Be more specific.")
    raise ValueError(f"No {label} matches keyword '{keyword}'.\nAvailable: {names}")


# ---------------------------------------------------------------------------
# data.gov.au CKAN lookup (your original script's approach) - now finds the
# "wgea_public_dataset_{YEAR}.zip" resource specifically.
# ---------------------------------------------------------------------------

def search_ckan(session: requests.Session, query: str = "WGEA", rows: int = 100) -> list:
    response = session.get(CKAN_API_URL, params={"q": query, "rows": rows}, timeout=60)
    response.raise_for_status()
    return response.json()["result"]["results"]


def find_public_dataset_zip(datasets: list, current_year: str, fy_label: str) -> dict:
    """
    Finds the "wgea_public_dataset_{YEAR}.zip" resource among CKAN search
    results, matching on the bare year OR WGEA's financial-year label
    appearing in the resource name/url, and requiring the filename pattern
    "wgea_public_dataset_...zip". Raises with the full candidate list on
    zero or multiple matches.
    """
    pattern = re.compile(r"wgea_public_dataset.*\.zip", re.IGNORECASE)
    candidates = []
    for dataset in datasets:
        for resource in dataset.get("resources", []):
            name = resource.get("name", "") or ""
            url = resource.get("url", "") or ""
            combined = f"{name} {url}"

            if not pattern.search(combined):
                continue
            if current_year in combined or fy_label in combined:
                candidates.append({**resource, "dataset_title": dataset.get("title", "")})

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) == 0:
        raise ValueError(
            f"No 'wgea_public_dataset_*.zip' resource found mentioning '{current_year}' or "
            f"'{fy_label}' on data.gov.au. Check data.gov.au manually for the current filename."
        )
    listing = "\n".join(f"  - [{c['dataset_title']}] {c.get('name')} ({c.get('url')})" for c in candidates)
    raise ValueError(
        f"Multiple 'wgea_public_dataset_*.zip' resources match '{current_year}'/'{fy_label}':\n"
        f"{listing}\nNarrow the match to disambiguate."
    )


def extract_from_zip(zip_bytes: bytes, keyword: str, out_path: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        member = find_by_keyword(names, keyword, label="zip member")
        content = zf.read(member)

    df = bytes_to_dataframe(content, filename_hint=member)
    df.to_csv(out_path, index=False)
    print(f"'{member}' -> {out_path}  ({len(df):,} rows, {len(df.columns)} cols)")


# ---------------------------------------------------------------------------
# Direct wgea.gov.au download for the salary sheet
# ---------------------------------------------------------------------------

def save_salary_sheet(session: requests.Session, out_path: Path) -> None:
    content = download_bytes(WGEA_URL, session)
    xls = pd.ExcelFile(io.BytesIO(content))
    print(f"Sheets in workbook: {xls.sheet_names}", file=sys.stderr)

    sheet_name = "2. Employers" if "2. Employers" in xls.sheet_names else find_by_keyword(
        xls.sheet_names, "employer", label="sheet"
    )
    df = pd.read_excel(xls, sheet_name=sheet_name, skiprows=3)
    df.to_csv(out_path, index=False)
    print(f"'{sheet_name}' -> {out_path}  ({len(df):,} rows, {len(df.columns)} cols)")


# ---------------------------------------------------------------------------
def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; wgea-fetch-script/1.0)"})

    print(f"Year: {CURRENT_YEAR} (financial year label: {FY_LABEL})\n")

    # 1. Salary sheet - direct wgea.gov.au download.
    save_salary_sheet(session, DATA_INPUT_AUTOMATED_PULL / "wgea_salary_data.csv")
    print()

    # 2 & 3. Workforce composition + management statistics - both live inside
    # one zip resource found via data.gov.au CKAN.
    print("Searching data.gov.au for WGEA resources...", file=sys.stderr)
    datasets = search_ckan(session, query="WGEA", rows=100)

    zip_resource = find_public_dataset_zip(datasets, CURRENT_YEAR, FY_LABEL)
    print(f"Found zip resource: {zip_resource.get('name')} ({zip_resource.get('url')})", file=sys.stderr)
    zip_bytes = download_bytes(zip_resource["url"], session)

    extract_from_zip(zip_bytes, "workforce_composition", DATA_INPUT_AUTOMATED_PULL / "wgea_workforce_composition.csv")
    extract_from_zip(
        zip_bytes, "management_statistics", DATA_INPUT_AUTOMATED_PULL / "wgea_workforce_management_statistics.csv"
    )


if __name__ == "__main__":
    main()