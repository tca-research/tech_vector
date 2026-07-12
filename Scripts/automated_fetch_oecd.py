"""
Fetches data from the OECD Main Science and Technology Indicators (MSTI)
dataset via the OECD SDMX REST API, starting from the dataflow/structure
link:
    https://sdmx.oecd.org/public/rest/dataflow/OECD.STI.STP/DSD_MSTI@DF_MSTI/?references=all

HOW THIS WORKS
--------------
SDMX splits every dataset into two pieces you query separately:
  1. STRUCTURE - the Data Structure Definition (DSD): which dimensions
     exist, in what order, and what codes are valid for each (e.g. which
     country codes, which measure codes). This is what the URL above
     returns (as SDMX-ML/XML).
  2. DATA - the actual observations, fetched from a different endpoint,
     where the URL path encodes a dot-separated "key" with one segment per
     dimension (in the exact order defined by the DSD), e.g.:
         .../DSD_MSTI@DF_MSTI,1.3/USA+DEU.A.PT_GERD...?startPeriod=2015

This script:
  1. Downloads and parses the DSD (step 1) so it always uses the *current*
     dimension order/version rather than a hardcoded guess - if the OECD
     changes the DSD version, this still works.
  2. Lets you filter by any dimension using --filter DIM=CODE1,CODE2 (run
     with --list-dimensions first to see what's available).
  3. Downloads the resulting data as CSV (with both codes and labels) into
     a pandas DataFrame, and optionally writes it to disk.

USAGE
-----
    # Just run it - filters to measures labeled "Gross Domestic Expenditure
    # on R&D" and units labeled "Percentage of GDP", finds Australia's
    # latest year with data, returns ALL countries for that one year,
    # writes oecd_msti_data.csv:
    python3 fetch_oecd_msti.py

    # Different metric/unit, same idea:
    python3 fetch_oecd_msti.py --metric-label "Researchers" --unit-label "Head counts"

    # Same idea, different anchor country:
    python3 fetch_oecd_msti.py --latest-year-for-country DEU

    # See what dimensions/codes exist:
    python3 fetch_oecd_msti.py --list-dimensions

    # Raw pull instead of the latest-year default - everything, or filtered:
    python3 fetch_oecd_msti.py --full --metric-label "" --unit-label ""
    python3 fetch_oecd_msti.py --full \\
        --filter REF_AREA=USA,DEU,JPN \\
        --filter MEASURE=PT_GERD \\
        --filter SECTOR=BES \\
        --start-period 2015 \\
        --output msti_gerd.csv
"""

import argparse
import io
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests

# The exact dataflow the user linked to. Only the base identifiers are
# hardcoded; version and dimension order are always read live from the DSD.
STRUCTURE_URL = (
    "https://sdmx.oecd.org/public/rest/dataflow/OECD.STI.STP/DSD_MSTI@DF_MSTI/"
    "?references=all"
)
DATA_BASE_URL = "https://sdmx.oecd.org/public/rest/data"
# Data/ lives alongside Scripts/ at the repo root, not inside Scripts/.
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "Data" / "input" / "automated_pull" / "oecd_msti_data.csv"
DEFAULT_LATEST_YEAR_COUNTRY = "AUS"
DEFAULT_METRIC_LABEL = "Gross Domestic Expenditure on R&D"
DEFAULT_UNIT_LABEL = "Percentage of GDP"


# ---------------------------------------------------------------------------
# Step 1: fetch + parse the DSD (structure) so we know the dimension order
# and valid codes without hardcoding them.
# ---------------------------------------------------------------------------

def _local_name(tag: str) -> str:
    """Strips the XML namespace off a tag, e.g. '{...}Dimension' -> 'Dimension'."""
    return tag.split("}")[-1] if "}" in tag else tag


def _ref_class(ref_el) -> str:
    return (ref_el.attrib.get("class") or "").lower()


def fetch_dsd(structure_url: str, session: requests.Session) -> dict:
    """
    Downloads the SDMX-ML structure message and extracts:
      - agency_id, dataflow_id, version  (identifies the dataflow)
      - dimensions: ordered list of {id, position, codelist_id}
        (excludes the time dimension - that's queried via startPeriod/endPeriod)
      - time_dimension_id
      - codelists: {codelist_id: {code_id: code_name}}
    """
    resp = session.get(structure_url, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    dataflow_el = None
    for el in root.iter():
        if _local_name(el.tag) == "Dataflow":
            dataflow_el = el
            break
    if dataflow_el is None:
        raise RuntimeError(
            "No <Dataflow> element found in the structure response - "
            "double check the structure URL."
        )

    agency_id = dataflow_el.attrib.get("agencyID")
    dataflow_id = dataflow_el.attrib.get("id")
    version = dataflow_el.attrib.get("version")

    # The data endpoint needs the flow ref as "DSD_ID@DATAFLOW_ID" (e.g.
    # "DSD_MSTI@DF_MSTI"), not just the dataflow id - that structure id
    # lives in the Dataflow's own <Structure><Ref id="..."/></Structure>.
    dsd_id = dataflow_id
    for child in dataflow_el:
        if _local_name(child.tag) == "Structure":
            for ref in child.iter():
                if _local_name(ref.tag) == "Ref" and ref.attrib.get("id"):
                    dsd_id = ref.attrib["id"]
                    break

    dimensions = []
    time_dimension_id = None
    for el in root.iter():
        tag = _local_name(el.tag)
        if tag == "Dimension":
            dim_id = el.attrib.get("id")
            position = int(el.attrib.get("position", len(dimensions) + 1))
            codelist_id = None
            for ref in el.iter():
                if _local_name(ref.tag) == "Ref" and _ref_class(ref) == "codelist":
                    codelist_id = ref.attrib.get("id")
                    break
            dimensions.append({"id": dim_id, "position": position, "codelist_id": codelist_id})
        elif tag == "TimeDimension":
            time_dimension_id = el.attrib.get("id")

    dimensions.sort(key=lambda d: d["position"])

    codelists = defaultdict(dict)
    for el in root.iter():
        if _local_name(el.tag) == "Codelist":
            cl_id = el.attrib.get("id")
            for code_el in el:
                if _local_name(code_el.tag) != "Code":
                    continue
                code_id = code_el.attrib.get("id")
                name = None
                for name_el in code_el:
                    if _local_name(name_el.tag) == "Name" and name_el.get(
                        "{http://www.w3.org/XML/1998/namespace}lang", "en"
                    ) == "en":
                        name = name_el.text
                        break
                codelists[cl_id][code_id] = name or ""

    if not dimensions:
        raise RuntimeError(
            "Parsed the structure response but found no <Dimension> elements. "
            "The DSD format may have changed - inspect the raw XML."
        )

    return {
        "agency_id": agency_id,
        "dataflow_id": dataflow_id,
        "dsd_id": dsd_id,
        "version": version,
        "dimensions": dimensions,
        "time_dimension_id": time_dimension_id,
        "codelists": dict(codelists),
    }


def format_flow_ref(dsd: dict) -> str:
    """
    Builds the "AGENCY,DSD_ID@DATAFLOW_ID,VERSION" flow ref the data
    endpoint expects. OECD's live DSD response sometimes reports the
    Dataflow's own "id" attribute already as the combined "DSD_ID@DATAFLOW_ID"
    form (rather than just "DATAFLOW_ID" as the generic SDMX spec would
    suggest) - prepending dsd_id again in that case doubles it up into
    "DSD_ID@DSD_ID@DATAFLOW_ID", which 404s. Guard against that here.
    """
    if "@" in dsd["dataflow_id"]:
        return f"{dsd['agency_id']},{dsd['dataflow_id']},{dsd['version']}"
    return f"{dsd['agency_id']},{dsd['dsd_id']}@{dsd['dataflow_id']},{dsd['version']}"


def find_codes_by_label(dsd: dict, dim_id: str, label_substring: str) -> list:
    """
    Finds every code in `dim_id`'s codelist whose human-readable label
    contains `label_substring` (case-insensitive) - e.g. matching MEASURE
    codes whose label mentions "Gross Domestic Expenditure on R&D" without
    needing to know the exact code (GERD, PT_GERD, USD_GERD, etc. might all
    qualify - this returns all of them as an OR filter, not just one).
    Raises with a sample of available labels if nothing matches.
    """
    dim = next((d for d in dsd["dimensions"] if d["id"] == dim_id), None)
    if dim is None:
        valid = ", ".join(d["id"] for d in dsd["dimensions"])
        raise ValueError(f"Dimension '{dim_id}' not found in this DSD. Valid dimensions: {valid}")

    codes = dsd["codelists"].get(dim["codelist_id"], {})
    matches = sorted(code for code, name in codes.items() if label_substring.lower() in (name or "").lower())

    if not matches:
        sample = list(codes.items())[:15]
        raise ValueError(
            f"No {dim_id} codes found with a label containing '{label_substring}'.\n"
            f"Sample of available {dim_id} codes/labels (run --list-dimensions for the full list):\n"
            + "\n".join(f"  {c}: {n}" for c, n in sample)
        )
    return matches


def print_dimensions(dsd: dict, max_codes_shown: int = 15) -> None:
    print(f"Dataflow: {format_flow_ref(dsd)}\n")
    print("Dimensions (in key order):")
    for dim in dsd["dimensions"]:
        codelist_id = dim["codelist_id"]
        codes = dsd["codelists"].get(codelist_id, {}) if codelist_id else {}
        print(f"  [{dim['position']}] {dim['id']}  (codelist: {codelist_id}, {len(codes)} codes)")
        for i, (code_id, name) in enumerate(sorted(codes.items())):
            if i >= max_codes_shown:
                print(f"        ... and {len(codes) - max_codes_shown} more")
                break
            print(f"        {code_id:<15} {name}")
    if dsd["time_dimension_id"]:
        print(f"\nTime dimension: {dsd['time_dimension_id']} (use --start-period / --end-period)")


# ---------------------------------------------------------------------------
# Step 2: build the data query URL and fetch it
# ---------------------------------------------------------------------------

def build_data_url(
    dsd: dict,
    filters: dict,
    start_period: str = None,
    end_period: str = None,
    fmt: str = "csvfilewithlabels",
) -> str:
    key_parts = []
    for dim in dsd["dimensions"]:
        values = filters.get(dim["id"], [])
        key_parts.append("+".join(values))  # empty string = wildcard (all values)
    key = ".".join(key_parts)

    flow_ref = format_flow_ref(dsd)
    url = f"{DATA_BASE_URL}/{flow_ref}/{key or 'all'}"

    params = [f"format={fmt}", "dimensionAtObservation=AllDimensions"]
    if start_period:
        params.append(f"startPeriod={start_period}")
    if end_period:
        params.append(f"endPeriod={end_period}")

    return url + "?" + "&".join(params)


def fetch_data(url: str, session: requests.Session) -> pd.DataFrame:
    resp = session.get(url, timeout=180)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text))


def latest_period(df: pd.DataFrame, time_col: str):
    """
    Returns the most recent value in the time dimension column. Works for
    plain years (2023), or zero-padded periods like '2023-Q4' / '2023-11',
    since both sort correctly as strings.
    """
    values = df[time_col].dropna().unique().tolist()
    return max(values, key=str)


def simplify_to_country_year_metric_value(
    df: pd.DataFrame,
    dsd: dict,
    country_dim_id: str = "REF_AREA",
) -> pd.DataFrame:
    """
    Reshapes the raw SDMX-CSV-with-labels output down to exactly 4 columns:
    country, year, metric, value.

    - country: the label column for REF_AREA if present (e.g. "Reference
      area"), falling back to the raw REF_AREA code.
    - year: the time dimension column (e.g. TIME_PERIOD).
    - metric: the SECOND and THIRD non-country dimension labels (list
      indices 1 and 2, skipping index 0) concatenated with " - " - e.g.
      for MSTI (REF_AREA, FREQ, SECTOR, MEASURE, ...), that's SECTOR and
      MEASURE, giving something like "Government - GERD as % of GDP".
      Raises if there aren't at least 3 non-country dimension columns.
    - value: OBS_VALUE.
    """
    time_col = dsd["time_dimension_id"] or "TIME_PERIOD"
    columns = list(df.columns)

    def label_col_for(dim_id):
        """The OECD 'withlabels' CSV puts a dimension's code column
        immediately followed by its human-readable label column."""
        if dim_id not in columns:
            return None
        idx = columns.index(dim_id)
        if idx + 1 < len(columns):
            candidate = columns[idx + 1]
            # Only treat it as a label if it's not itself another known
            # dimension/standard field (i.e. there really is a label column).
            known_fields = {d["id"] for d in dsd["dimensions"]} | {time_col, "OBS_VALUE"}
            if candidate not in known_fields:
                return candidate
        return None

    country_label_col = label_col_for(country_dim_id) or country_dim_id
    if country_dim_id not in df.columns:
        raise ValueError(f"Expected a '{country_dim_id}' column in the fetched data, got: {columns}")

    other_dims = [d["id"] for d in dsd["dimensions"] if d["id"] != country_dim_id]
    metric_cols = []
    for dim_id in other_dims:
        if dim_id not in df.columns:
            continue
        metric_cols.append(label_col_for(dim_id) or dim_id)

    if len(metric_cols) < 3:
        raise ValueError(
            f"Need at least 3 non-country dimension columns to build 'metric' from "
            f"indices 1 and 2, but only found {len(metric_cols)}: {metric_cols}"
        )
    metric_series = df[metric_cols[1]].astype(str) + " - " + df[metric_cols[2]].astype(str)

    out = pd.DataFrame(
        {
            "country": df[country_label_col],
            "year": df[time_col],
            "metric": metric_series,
            "value": df["OBS_VALUE"],
        }
    )
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_filter_args(filter_args):
    """Turns repeated --filter DIM=CODE1,CODE2 args into {DIM: [CODE1, CODE2]}."""
    filters = {}
    for raw in filter_args or []:
        if "=" not in raw:
            print(f"Error: --filter must look like DIM=CODE1,CODE2 (got '{raw}')", file=sys.stderr)
            sys.exit(1)
        dim, values = raw.split("=", 1)
        filters[dim.strip().upper()] = [v.strip() for v in values.split(",") if v.strip()]
    return filters


def parse_label_filter_args(label_filter_args):
    """Turns repeated --label-filter DIM=TEXT args into {DIM: TEXT}."""
    label_filters = {}
    for raw in label_filter_args or []:
        if "=" not in raw:
            print(f"Error: --label-filter must look like DIM=TEXT (got '{raw}')", file=sys.stderr)
            sys.exit(1)
        dim, text = raw.split("=", 1)
        label_filters[dim.strip().upper()] = text.strip()
    return label_filters


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--structure-url",
        default=STRUCTURE_URL,
        help="SDMX structure/dataflow URL to introspect (default: the MSTI dataflow)",
    )
    parser.add_argument(
        "--list-dimensions",
        action="store_true",
        help="Print the dataflow's dimensions and available codes, then exit (no data is fetched)",
    )
    parser.add_argument(
        "--filter",
        action="append",
        metavar="DIM=CODE1,CODE2",
        help="Filter a dimension to specific codes, e.g. --filter REF_AREA=USA,DEU. Repeatable.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help=(
            "Skip the default latest-year-for-Australia behavior and just pull data "
            "directly using --filter/--start-period/--end-period (everything, if none given)."
        ),
    )
    parser.add_argument(
        "--latest-year-for-country",
        default=DEFAULT_LATEST_YEAR_COUNTRY,
        metavar="CODE",
        help=(
            f"Find CODE's most recent year with data (under any other --filter given), "
            f"then return ALL countries for that single year, reshaped to columns: "
            f"country, year, metric, value. (default: {DEFAULT_LATEST_YEAR_COUNTRY}; "
            f"pass --full to disable this and do a raw pull instead)"
        ),
    )
    parser.add_argument(
        "--metric-label",
        default=DEFAULT_METRIC_LABEL,
        metavar="TEXT",
        help=(
            f"Filter MEASURE to codes whose label contains this text "
            f"(default: '{DEFAULT_METRIC_LABEL}'). Ignored if you explicitly "
            f"pass --filter MEASURE=... yourself. Pass '' to disable."
        ),
    )
    parser.add_argument(
        "--unit-label",
        default=DEFAULT_UNIT_LABEL,
        metavar="TEXT",
        help=(
            f"Filter UNIT_MEASURE to codes whose label contains this text "
            f"(default: '{DEFAULT_UNIT_LABEL}'). Ignored if you explicitly "
            f"pass --filter UNIT_MEASURE=... yourself. Pass '' to disable."
        ),
    )
    parser.add_argument(
        "--label-filter",
        action="append",
        metavar="DIM=TEXT",
        help=(
            "Filter any dimension to codes whose label contains TEXT, e.g. "
            "--label-filter UNIT_MEASURE='Percentage of GDP'. Same matching "
            "as --metric-label, generalized to any dimension. Repeatable. "
            "Ignored for a dimension you've also given via --filter."
        ),
    )
    parser.add_argument("--start-period", default=None, help="e.g. 2015")
    parser.add_argument("--end-period", default=None, help="e.g. 2023")
    parser.add_argument(
        "--format",
        default="csvfilewithlabels",
        choices=["csvfilewithlabels", "csvfile"],
        help="csvfilewithlabels includes both codes and human-readable labels (default); "
        "csvfile is codes only and lighter",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Path to write the fetched data as CSV (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; oecd-msti-fetch-script/1.0)"})

    print(f"Fetching DSD structure from {args.structure_url} ...", file=sys.stderr)
    dsd = fetch_dsd(args.structure_url, session)

    if args.list_dimensions:
        print_dimensions(dsd)
        return

    explicit_filters = parse_filter_args(args.filter)
    filters = dict(explicit_filters)

    unknown_dims = set(filters) - {d["id"] for d in dsd["dimensions"]}
    if unknown_dims:
        valid = ", ".join(d["id"] for d in dsd["dimensions"])
        print(
            f"Error: unknown dimension(s) {sorted(unknown_dims)}. Valid dimensions: {valid}\n"
            f"Run with --list-dimensions to see codes for each.",
            file=sys.stderr,
        )
        sys.exit(1)

    def apply_label_filter(dim_id: str, label_text: str) -> None:
        codes = find_codes_by_label(dsd, dim_id, label_text)
        codelist = dsd["codelists"][next(d for d in dsd["dimensions"] if d["id"] == dim_id)["codelist_id"]]
        print(f"Filtering {dim_id} to codes matching '{label_text}':", file=sys.stderr)
        for c in codes:
            print(f"  {c}: {codelist[c]}", file=sys.stderr)
        filters[dim_id] = codes

    def dim_exists(dim_id: str) -> bool:
        return any(d["id"] == dim_id for d in dsd["dimensions"])

    if "MEASURE" not in explicit_filters and args.metric_label:
        if dim_exists("MEASURE"):
            apply_label_filter("MEASURE", args.metric_label)
        else:
            print("Note: this dataflow has no MEASURE dimension - skipping --metric-label.", file=sys.stderr)

    if "UNIT_MEASURE" not in explicit_filters and args.unit_label:
        if dim_exists("UNIT_MEASURE"):
            apply_label_filter("UNIT_MEASURE", args.unit_label)
        else:
            print("Note: this dataflow has no UNIT_MEASURE dimension - skipping --unit-label.", file=sys.stderr)

    label_filters = parse_label_filter_args(args.label_filter)
    for dim_id, label_text in label_filters.items():
        if dim_id in explicit_filters:
            print(
                f"Note: --label-filter {dim_id}=... ignored - you already gave --filter {dim_id}=...",
                file=sys.stderr,
            )
            continue
        apply_label_filter(dim_id, label_text)

    if args.latest_year_for_country and not args.full:
        code = args.latest_year_for_country.strip().upper()
        time_col = dsd["time_dimension_id"] or "TIME_PERIOD"

        # Step 1: fetch just this country (under the user's other filters,
        # e.g. --filter MEASURE=...) across all periods, to find its latest year.
        probe_filters = dict(filters)
        if "REF_AREA" in probe_filters and probe_filters["REF_AREA"] != [code]:
            print(
                f"Note: --latest-year-for-country {code} overrides your "
                f"--filter REF_AREA={','.join(probe_filters['REF_AREA'])} for the year lookup",
                file=sys.stderr,
            )
        probe_filters["REF_AREA"] = [code]

        probe_url = build_data_url(dsd, probe_filters, fmt=args.format)
        print(f"Finding {code}'s latest year: {probe_url} ...", file=sys.stderr)
        probe_df = fetch_data(probe_url, session)
        if probe_df.empty or time_col not in probe_df.columns:
            print(f"No data found for {code} at all under these filters.", file=sys.stderr)
            sys.exit(1)
        latest = latest_period(probe_df, time_col)
        print(f"Latest year with data for {code}: {latest}", file=sys.stderr)

        # Step 2: re-fetch ALL countries (any REF_AREA filter removed), same
        # other filters, restricted to just that one year.
        all_country_filters = {k: v for k, v in filters.items() if k != "REF_AREA"}
        data_url = build_data_url(
            dsd, all_country_filters, start_period=str(latest), end_period=str(latest), fmt=args.format
        )
        print(f"Fetching all countries for {latest}: {data_url} ...", file=sys.stderr)
        df = fetch_data(data_url, session)
        df = simplify_to_country_year_metric_value(df, dsd)
    else:
        data_url = build_data_url(
            dsd, filters, start_period=args.start_period, end_period=args.end_period, fmt=args.format
        )
        print(f"Fetching data from {data_url} ...", file=sys.stderr)
        df = fetch_data(data_url, session)

    print(f"\nFetched {len(df):,} rows, {len(df.columns)} columns.")
    print(df.head(10).to_string(index=False))

    if args.output:
        df.to_csv(args.output, index=False)
        print(f"\nFull data written to {args.output}")


if __name__ == "__main__":
    main()