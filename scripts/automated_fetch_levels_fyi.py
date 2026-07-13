import requests
from bs4 import BeautifulSoup
import re
import csv
from pathlib import Path

# data/ lives alongside scripts/ at the repo root, not inside scripts/.
DATA_INPUT_AUTOMATED_PULL = Path(__file__).resolve().parent.parent / "data" / "input" / "automated_pull"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0 Safari/537.36"
    )
}

def generate_au_urls():
    base = "https://www.levels.fyi/en-gb"
    levels = ["", "levels/entry-level", "levels/senior"]  # "" = all levels
    urls = []
    mapping_url = "https://www.levels.fyi/t"
    map_resp = requests.get(mapping_url, headers=HEADERS)
    map_soup = BeautifulSoup(map_resp.text, "html.parser")
    job_links = map_soup.find_all("a", href=True)
    exclude_terms = ["title", "focus", "location", "from", "fashion", "real-estate", "meteor", "toxic", "claims", "physician"]
    filtered_links = list({
        a["href"]
        for a in job_links
        if "/t/" in a["href"] and not any(term in a["href"] for term in exclude_terms)
    })
    for occupation in filtered_links:
        for level in levels:
            if level:
                url = f"{base}{occupation}/{level}/locations/australia"
                level_name = level.split("/")[-1]
            else:
                url = f"{base}{occupation}/locations/australia"
                level_name = "all"
            urls.append({
                "URL": url,
                "job_title": occupation.split("/")[-1].replace("-", " ").title(),
                "level": level_name.title(),
                "country": "Australia"
            })
    return urls

def parse_salary(text):
    """
    Parse a currency-formatted string like "A$152,055", "A$113K", or "A$1.2M"
    into an integer (e.g., 152055, 113000, 1200000).
    """
    if not text:
        return None

    text = text.upper().replace("A$", "").strip()

    # Match the numeric part and the optional suffix
    match = re.match(r"([\d.,]+)\s*([KM]?)", text)
    if not match:
        return None

    number_str, suffix = match.groups()

    # Normalize number (e.g. "1.2" or "152,055")
    number_str = number_str.replace(",", "")
    try:
        number = float(number_str)
    except ValueError:
        return None

    # Apply multiplier
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000}.get(suffix, 1)

    return int(number * multiplier)

def scrape_levelsfyi(url):
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Overall table: median, 25th, 75th, 90th
    # levels.fyi ships each stat as a value element (h3/h6) immediately
    # followed by a sibling label element whose class contains
    # "percentileLabel" (e.g. "Median Total Comp", "25th%"). The module
    # class names carry a build-specific hash that changes on every
    # deploy, so match on the stable "percentileLabel" substring instead
    # of a full class name.
    summary = {}
    card = soup.find(class_=lambda c: c and "percentileCardContainer" in c)
    if card:
        for label_el in card.find_all(class_=lambda c: c and "percentileLabel" in c):
            value_el = label_el.find_previous_sibling(["h3", "h6"])
            if not value_el:
                continue
            key_match = re.search(r"(25th|75th|90th|Median)", label_el.get_text(strip=True))
            if not key_match:
                continue
            summary[key_match.group(1)] = parse_salary(value_el.get_text(strip=True))
        
    # Top paying companies/locations
    top_companies_or_locations = []
    for a in soup.find_all("a"):
        text = a.get_text(strip=True)
        if re.match(r"[A-Za-z].*A\$\d", text):
            # Split "Atlassian A$297,509" into name + value
            parts = text.rsplit("A$", 1)
            if len(parts) == 2:
                name = parts[0].strip()
                salary = parse_salary(parts[1].replace(",", ""))
                top_companies_or_locations.append({"company_or_location": name, "salary": salary})

    return {"summary": summary, "top_companies_or_locations": top_companies_or_locations}

if __name__ == "__main__":
    urls = generate_au_urls()

    for entry in urls:
        url = entry["URL"]
        try:
            data = scrape_levelsfyi(url)
            has_summary = bool(data.get("summary"))
            has_top = bool(data.get("top_companies_or_locations"))
            entry["data_exists"] = "Data available" if has_summary or has_top else "No data available"
        except Exception:
            entry["data_exists"] = "No data available"

    metadata_dir = DATA_INPUT_AUTOMATED_PULL / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    with open(metadata_dir / "au_levelsfyi_urls_with_data_flags.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["URL", "job_title", "level", "country", "data_exists"])
        writer.writeheader()
        writer.writerows(urls)

    all_rows = []

    for entry in urls:
        if entry["data_exists"] != "Data available":
            continue
        try:
            data = scrape_levelsfyi(entry["URL"])
        except Exception:
            continue

        # Summary
        for label, value in data.get("summary", {}).items():
            all_rows.append({
                "Metric": "Summary",
                "Measurement": "Percentile",
                "Rank Order": "",
                "Label": label,
                "Salary": value,
                "Job Title": entry["job_title"],
                "Level": entry["level"],
                "Country": entry["country"],
                "URL": entry["URL"]
            })

        # Companies
        top_items = data.get("top_companies_or_locations", [])
        for i, company in enumerate(top_items[:3], 1):
            all_rows.append({
                "Metric": "Top Company",
                "Measurement": "Ranking",
                "Rank Order": i,
                "Label": company["company_or_location"],
                "Salary": company["salary"],
                "Job Title": entry["job_title"],
                "Level": entry["level"],
                "Country": entry["country"],
                "URL": entry["URL"]
            })
        # Locations
        for i, loc in enumerate(top_items[3:6], 1):
            all_rows.append({
                "Metric": "Top Location",
                "Measurement": "Ranking",
                "Rank Order": i,
                "Label": loc["company_or_location"],
                "Salary": loc["salary"],
                "Job Title": entry["job_title"],
                "Level": entry["level"],
                "Country": entry["country"],
                "URL": entry["URL"]
            })


        final_csv_path = DATA_INPUT_AUTOMATED_PULL / "au_levelsfyi_detailed_data.csv"
        with open(final_csv_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["Metric", "Measurement", "Rank Order", "Label", "Salary", "Job Title", "Level", "Country", "URL"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
