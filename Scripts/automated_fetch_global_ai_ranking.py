"""
Reproduces the "Global AI Vibrancy Ranking" bar chart from Stanford HAI's
Global AI Vibrancy Tool (https://d3i91vx6n7fixv.cloudfront.net/).

This is a line-for-line port of the scoring logic found in the tool's
front-end source (vibrancyUtils.ts / tableViewUtils.ts / constant.ts),
specifically:
    - createCountryData()              -> load_country_data()
    - createMetricData()                -> load_metric_groups()
    - calculateWeightedGlobalBarChart() -> calculate_weighted_global_bar_chart()
    - generateGlobalBarChartData()      -> the final sort/rank step in main()

HOW SCORING WORKS (short version)
----------------------------------
1. Metrics are grouped into 7 pillars (R&D, Responsible AI, Economy, Talent,
   Policy and Governance, Public Opinion, Infrastructure), each with a fixed
   pillar weight (PILLAR_MULTIPLIER below) and each metric within a pillar
   has its own fixed weight (METRIC_DEFAULT_MULTIPLIER below).
2. Only metrics flagged is_for_ranking == "yes" in the codebook count.
3. For a given country/year, each metric's already-normalized score
   (the "<shortname>_calc" column, 0-100ish scale) is weighted by
   (metric weight / sum of weights of metrics that HAVE data that year)
   -> this "renormalizes" so missing metrics don't drag a pillar to zero.
4. Each pillar's weighted metric scores are summed -> pillar score.
5. Each pillar score is weighted by (pillar weight / sum of ALL pillar
   weights) and summed across pillars -> the country's total score.
6. Countries are ranked by total score, descending.

Two independent inputs, both distributed alongside this script's data
(the "full_data" file has the country-year values; the "codebook" file
maps every metric to its pillar, its column names, and its ranking flag).
"""

import argparse
import io
import re
import sys
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://d3i91vx6n7fixv.cloudfront.net"
DATA_DIR_URL = f"{BASE_URL}/data/"

# ---------------------------------------------------------------------------
# Static config, ported directly from constant.ts
# ---------------------------------------------------------------------------

# PILLAR_INFO -> {pillar name in codebook: (dataKey, defaultMultiplier)}
PILLAR_INFO = {
    "R&D":                    {"dataKey": "research",       "multiplier": 1.0},
    "Responsible AI":         {"dataKey": "responsible",    "multiplier": 0.2},
    "Economy":                {"dataKey": "economy",        "multiplier": 0.8},
    "Talent":                 {"dataKey": "talent",         "multiplier": 0.6},
    "Policy and Governance":  {"dataKey": "policy",         "multiplier": 0.2},
    "Public Opinion":         {"dataKey": "publicOpinion",  "multiplier": 0.2},
    "Infrastructure":         {"dataKey": "infrastructure", "multiplier": 0.6},
}

# METRIC_DEFAULT_MULTIPLIER, ported directly. Divided by 10 when used
# (matches `multiplier: mtp / 10` in createMetricData()).
METRIC_DEFAULT_MULTIPLIER = {
    "AI Publications (Total)": 7,
    "AI Citations (Total)": 8,
    "AI Patent Grants": 8,
    "Notable AI Models": 9,
    "Academia-Industry Model Production Concentration": 0,
    "AI GitHub Projects": 7,
    "AI GitHub Projects Stars": 8,
    "Conference Submissions on RAI Topics (Total)": 8,
    "Total AI Private Investment": 10,
    "Newly Funded AI Companies": 9,
    "AI Hiring Rate YoY Ratio": 6,
    "Relative AI Skill Penetration": 3,
    "AI Talent Concentration": 6,
    "AI Job Postings (% of Total)": 0,
    "Net Migration Flow of AI Skills": 6,
    "AI Legislation Passed (3-Year MA)": 10,
    "AI Mentions in Legislative Proceedings": 6,
    "AI Social Media Posts": 6,
    "AI-Related Social Media Conversations Net Sentiment": 9,
    "Parts Semiconductor Devices Exports": 10,
    "Supercomputers": 9,
    "Compute Capacity (Rmax)": 10,
    "Internet Speed": 8,
}


# ---------------------------------------------------------------------------
# Auto-discovery of the current dated filenames (e.g. "09.24.25") straight
# from the live site, since the app's constant.ts (and therefore the CSV
# filenames it points at) gets updated whenever new data is published.
# ---------------------------------------------------------------------------

FILENAME_PATTERN = re.compile(r"(full_data|codebook)_(\d{2}\.\d{2}\.\d{2})")
SCRIPT_SRC_PATTERN = re.compile(r'<script[^>]+src="([^"]+\.js)"', re.IGNORECASE)


def discover_current_date(session: requests.Session) -> str:
    """
    Fetches the site's index.html, follows its <script> bundles, and greps
    them for "full_data_MM.DD.YY.csv" / "codebook_MM.DD.YY.csv" references
    to figure out which dated file is currently live - so this script keeps
    working even after the site publishes a new data drop.
    """
    resp = session.get(BASE_URL + "/", timeout=30)
    resp.raise_for_status()
    html = resp.text

    script_urls = SCRIPT_SRC_PATTERN.findall(html)
    if not script_urls:
        raise RuntimeError(
            "Could not find any <script> bundles on the site's homepage to "
            "scan for the current data filename. Pass --date explicitly instead."
        )

    for src in script_urls:
        bundle_url = src if src.startswith("http") else BASE_URL + (src if src.startswith("/") else "/" + src)
        try:
            bundle_resp = session.get(bundle_url, timeout=30)
            bundle_resp.raise_for_status()
        except requests.RequestException:
            continue

        match = FILENAME_PATTERN.search(bundle_resp.text)
        if match:
            return match.group(2)  # the "MM.DD.YY" part

    raise RuntimeError(
        "Scanned the site's JS bundles but couldn't find a "
        "full_data_MM.DD.YY.csv / codebook_MM.DD.YY.csv reference. "
        "Pass --date explicitly instead (check the site's Network tab for the "
        "current filename)."
    )


def fetch_csv(url: str, session: requests.Session) -> pd.DataFrame:
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text))


# ---------------------------------------------------------------------------

def load_metric_groups(codebook: pd.DataFrame) -> pd.DataFrame:
    """
    Takes the raw codebook dataframe and returns one row per *ranking*
    metric (is_for_ranking == 'yes'), with columns:
        pillar_name, data_key, pillar_multiplier,
        metric_name, metric_value_type ('absolute'|'perCapita'),
        shortname_raw, shortname_scaled, metric_multiplier
    """
    codebook = codebook[codebook["pillar_1"].notna()].copy()
    codebook = codebook[codebook["is_for_ranking"].str.strip().str.lower() == "yes"].copy()

    def refine_name(metric_name: str) -> str:
        # Port of: metric.metric_name?.replace(' PC', '')?.trim()
        # JS String.replace(str) only replaces the FIRST match, but there's
        # only ever one " PC" substring in these labels, so a plain replace
        # behaves identically.
        return metric_name.replace(" PC", "").strip()

    rows = []
    for _, row in codebook.iterrows():
        pillar_name = row["pillar_1"]
        if pillar_name not in PILLAR_INFO:
            # Should not happen with the current codebook, but mirrors the
            # JS `findPillar!` (non-null assertion) failing loudly rather
            # than silently dropping data.
            raise ValueError(f"Unknown pillar '{pillar_name}' - not in PILLAR_INFO")

        metric_name = row["metric_name"]
        refined = refine_name(metric_name)
        if refined not in METRIC_DEFAULT_MULTIPLIER:
            raise ValueError(f"No METRIC_DEFAULT_MULTIPLIER entry for '{refined}'")

        rows.append(
            {
                "pillar_name": pillar_name,
                "data_key": PILLAR_INFO[pillar_name]["dataKey"],
                "pillar_multiplier": PILLAR_INFO[pillar_name]["multiplier"],
                "metric_name": metric_name,
                "metric_value_type": "perCapita" if " PC" in metric_name else "absolute",
                "shortname_raw": row["shortname_raw"],
                "shortname_scaled": row["shortname_scaled"],
                "metric_multiplier": METRIC_DEFAULT_MULTIPLIER[refined] / 10,
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Step 2: load country/year data (ports createCountryData)
# ---------------------------------------------------------------------------

def load_country_data(data: pd.DataFrame, core_only: bool = True) -> pd.DataFrame:
    """
    Takes the raw full_data dataframe. Treats '-' (the app's own "no data"
    sentinel) as missing, same as empty cells. By default keeps only
    CountryGroup == 'core' rows, matching the `countryData` (as opposed to
    `fullCountryData`) used to build the global ranking bar chart in the app.
    """
    df = data.replace("-", pd.NA)
    if core_only:
        df = df[df["CountryGroup"] == "core"].copy()
    return df


# ---------------------------------------------------------------------------
# Step 3: the scoring itself (ports calculateWeightedGlobalBarChart)
# ---------------------------------------------------------------------------

def calculate_weighted_global_bar_chart(
    country_year_df: pd.DataFrame,
    metric_groups: pd.DataFrame,
    metric_value_type: str,
) -> pd.DataFrame:
    """
    country_year_df: one row per country, already filtered to a single
                      PublishYear (this mirrors `dataForCurrentYear` in the
                      TS code, found per-country from `country.metadatas`).
    metric_groups:   output of load_metric_groups()
    metric_value_type: 'absolute' or 'perCapita' (matches selectedMetricValue)

    Returns a dataframe with one row per country and columns:
        <dataKey>_weight for each of the 7 pillars, and total_score.
    """
    metrics = metric_groups[metric_groups["metric_value_type"] == metric_value_type]

    results = []
    for _, country in country_year_df.iterrows():
        pillar_weighted_scores = {}

        for pillar_name, pillar_info in PILLAR_INFO.items():
            data_key = pillar_info["dataKey"]
            pillar_metrics = metrics[metrics["pillar_name"] == pillar_name]

            # total_multiplier: sum of metric weights, but only for metrics
            # that actually have a value this country/year (renormalizes
            # the weighting so missing data doesn't zero out a pillar).
            calc_cols = pillar_metrics["shortname_scaled"] + "_calc"
            present_mask = calc_cols.apply(lambda c: pd.notna(country.get(c)))
            total_multiplier = pillar_metrics.loc[present_mask, "metric_multiplier"].sum()

            weight_scores = []
            for _, metric in pillar_metrics.iterrows():
                calc_col = f"{metric['shortname_scaled']}_calc"
                score = country.get(calc_col)
                score = 0.0 if pd.isna(score) else float(score)

                if total_multiplier == 0:
                    weight_score = 0.0
                else:
                    weight_score = (metric["metric_multiplier"] / total_multiplier) * score
                weight_scores.append(weight_score)

            total_weight_score = sum(w for w in weight_scores if not pd.isna(w))
            pillar_weighted_scores[data_key] = total_weight_score

        # totalMetricMultiplier: sum of pillar weights across ALL pillars
        # (not just ones with data) - matches the JS reduce over metricsData.
        total_metric_multiplier = sum(p["multiplier"] for p in PILLAR_INFO.values())

        total_score = 0.0
        row_out = {
            "CountryName": country["CountryName"],
            "Country": country["Country"],          # short code
            "Code": country["Code"],                # long code
            "Region": country.get("Region"),
            "IncomeGroup": country.get("IncomeGroup"),
        }
        for pillar_name, pillar_info in PILLAR_INFO.items():
            data_key = pillar_info["dataKey"]
            pillar_score = pillar_weighted_scores[data_key]
            pillar_weight = pillar_score * (pillar_info["multiplier"] / total_metric_multiplier)
            row_out[f"{data_key}_weight"] = pillar_weight
            total_score += pillar_weight

        row_out["total_score"] = total_score
        results.append(row_out)

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Step 4: put it together (ports generateGlobalBarChartData)
# ---------------------------------------------------------------------------

def build_global_ranking(
    data_df: pd.DataFrame,
    codebook_df: pd.DataFrame,
    year: int,
    metric_value_type: str = "absolute",
) -> pd.DataFrame:
    metric_groups = load_metric_groups(codebook_df)
    country_data = load_country_data(data_df, core_only=True)

    year_data = country_data[country_data["PublishYear"] == year].copy()
    if year_data.empty:
        available = sorted(country_data["PublishYear"].dropna().unique().tolist())
        raise ValueError(f"No data for year {year}. Available years: {available}")

    scored = calculate_weighted_global_bar_chart(year_data, metric_groups, metric_value_type)

    # Drop NaN scores (mirrors the `.filter(el => !_.isNaN(Number(el.score)))`
    # step), then sort descending and assign rank ids.
    scored = scored[scored["total_score"].notna()].copy()
    scored = scored.sort_values("total_score", ascending=False).reset_index(drop=True)
    scored.insert(0, "rank", scored.index + 1)

    return scored


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--date",
        default=None,
        help=(
            "The MM.DD.YY date stamp used in the live filenames, e.g. '09.24.25'. "
            "If omitted, the script auto-detects the current one from the site."
        ),
    )
    parser.add_argument(
        "--data-csv",
        default=None,
        help="Local path OR URL for the full_data CSV (overrides --date / auto-discovery)",
    )
    parser.add_argument(
        "--codebook-csv",
        default=None,
        help="Local path OR URL for the codebook CSV (overrides --date / auto-discovery)",
    )
    parser.add_argument("--year", type=int, default=2024, help="PublishYear to rank (default: 2024)")
    parser.add_argument(
        "--metric-value",
        choices=["absolute", "perCapita"],
        default="absolute",
        help="Whether to rank on absolute or per-capita metrics (default: absolute)",
    )
    parser.add_argument("--top", type=int, default=None, help="Only show the top N countries")
    parser.add_argument("--output", default=None, help="Optional path to write the full ranking as CSV")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; vibrancy-repro-script/1.0)"})

    def resolve(explicit_path_or_url, filename_stub):
        """
        Precedence: explicit --data-csv/--codebook-csv path or URL > --date flag
        > auto-discovered current date.
        """
        if explicit_path_or_url:
            return explicit_path_or_url
        date_str = args.date or discover_current_date(session)
        return f"{DATA_DIR_URL}{filename_stub}_{date_str}.csv"

    data_source = resolve(args.data_csv, "full_data")
    codebook_source = resolve(args.codebook_csv, "codebook")

    def load(source, label):
        is_url = source.startswith("http://") or source.startswith("https://")
        print(f"Loading {label} from {source} ...", file=sys.stderr)
        if is_url:
            return fetch_csv(source, session)
        if not Path(source).exists():
            print(f"Error: {label} not found at '{source}'", file=sys.stderr)
            sys.exit(1)
        return pd.read_csv(source)

    data_df = load(data_source, "data CSV")
    codebook_df = load(codebook_source, "codebook CSV")

    ranking = build_global_ranking(
        data_df=data_df,
        codebook_df=codebook_df,
        year=args.year,
        metric_value_type=args.metric_value,
    )

    display_cols = ["rank", "CountryName", "Country", "Code", "total_score"] + [
        f"{p['dataKey']}_weight" for p in PILLAR_INFO.values()
    ]
    to_show = ranking[display_cols]
    if args.top:
        to_show = to_show.head(args.top)

    pd.set_option("display.float_format", lambda x: f"{x:.3f}")
    pd.set_option("display.width", 160)
    print(to_show.to_string(index=False))

    if args.output:
        ranking.to_csv(args.output, index=False)
        print(f"\nFull ranking written to {args.output}")

    input_dir = Path(__file__).resolve().parent.parent / "Data" / "input" / "automated_pull"
    input_dir.mkdir(parents=True, exist_ok=True)
    input_path = input_dir / "global_ai_vibrancy_indices.csv"
    ranking.to_csv(input_path, index=False)
    print(f"Full ranking also written to {input_path}")


if __name__ == "__main__":
    main()
