"""
Automates the pull of Tech Council of Australia member ABNs from Zoho CRM
(replacing the manual "ask the membership team for a CSV" process described
in scripts/MANUAL_DATA_PULL_INSTRUCTIONS_TECH_COUNCIL_ABNS.md), so the
member-ABN list feeding automated_data_prep.py's WGEA cross-sector
comparisons can be refreshed automatically on every rebuild cycle instead
of depending on someone remembering to upload a CSV by hand.

HOW ZOHO AUTH WORKS (Self Client OAuth2, not a 3-legged user login)
---------------------------------------------------------------------
This script expects a Zoho "Self Client" OAuth2 app (set up once, manually,
in the Zoho API Console) that has already been exchanged for a long-lived
refresh_token - see the 3 required environment variables below. On every
run, this script:
  1. POSTs to Zoho's OAuth token endpoint with the refresh_token to get a
     1-hour access_token, AND an "api_domain" (e.g.
     https://www.zohoapis.com.au for an AU-hosted org - Zoho splits orgs
     across regional data centers, so this is NOT always zohoapis.com).
     The api_domain returned in THIS response is always used for the CRM
     call below - it is never hardcoded, since hardcoding the wrong data
     center's domain is a common Zoho integration bug.
  2. Uses that access_token to page through the CRM "Accounts" module
     (Tech Council members are Accounts in this org's CRM), filtered to
     just current members via ZOHO_MEMBER_CRITERIA below, extracting each
     Account's ABN custom field (ZOHO_ABN_FIELD below).
  3. Writes the result as data/input/automated_pull/Tech_Council_ABNs.csv
     with a single "ABN" column - the exact column name/location that
     automated_data_prep.py already expects (previously read from
     data/input/manual_pull/Tech_Council_ABNs.csv by hand).

PLACEHOLDERS THAT MUST BE CONFIRMED BEFORE THIS SCRIPT WORKS (see TODOs
below) - both of these need sign-off from whoever administers the Tech
Council's Zoho CRM, NOT guessed:
  - ZOHO_ABN_FIELD: the exact API field name (not the display label) of
    the custom field on the Accounts module that holds each member's ABN.
  - ZOHO_MEMBER_CRITERIA: the exact CRM search criteria that identifies a
    CURRENTLY ACTIVE Tech Council member Account. The Accounts module
    almost certainly also contains non-member relationships (sponsors,
    partners, vendors), so pulling ALL Accounts unfiltered is very likely
    wrong - do not remove this filter without confirming that first.
Everything else (auth, pagination, CSV writing) is fully working.

REQUIRED ENVIRONMENT VARIABLES
-------------------------------
    ZOHO_CLIENT_ID       - from the Self Client's API Console entry
    ZOHO_CLIENT_SECRET   - from the Self Client's API Console entry
    ZOHO_REFRESH_TOKEN   - obtained once via the Self Client's "Generate
                           Code" -> token exchange flow; long-lived (doesn't
                           expire except on manual revocation, or exceeding
                           20 active tokens for one client)

USAGE
-----
    python3 automated_fetch_zoho_abns.py
    python3 automated_fetch_zoho_abns.py --output /tmp/test_abns.csv
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import requests

# Always the global Zoho accounts server for the token exchange itself -
# this is separate from api_domain (below), which IS region-specific and
# is read fresh from the token response every run, never hardcoded.
ZOHO_ACCOUNTS_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"

ZOHO_MODULE = "Accounts"
PER_PAGE = 200          # Zoho CRM v8's documented max per_page
MAX_PAGES = 50          # safety cap: 50 * 200 = 10,000 records - well above
                        # the ~2,000 records a Tech Council membership list
                        # is expected to ever have; stops a runaway loop
                        # rather than paging forever if criteria is wrong.

# ---------------------------------------------------------------------------
# TODO: confirm both of these with whoever administers the Tech Council's
# Zoho CRM before relying on this script - see the module docstring above.
# ---------------------------------------------------------------------------
ZOHO_ABN_FIELD = "ABN"  # TODO: confirm exact API field name (Setup > Customization > Modules and Fields > Accounts) - "ABN" is an unconfirmed placeholder guess
ZOHO_MEMBER_CRITERIA = "(Membership_Status:equals:Active)"  # TODO: confirm exact field/value identifying a CURRENT Tech Council member Account. Set to "" to fall back to an unfiltered Accounts listing instead of /search (NOT recommended until confirmed - Accounts likely also holds sponsors/partners/vendors).
# ---------------------------------------------------------------------------

# data/ lives alongside scripts/ at the repo root, not inside scripts/.
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent / "data" / "input" / "automated_pull" / "Tech_Council_ABNs.csv"
)


def get_access_token(session: requests.Session, client_id: str, client_secret: str, refresh_token: str) -> tuple:
    """
    Exchanges the long-lived refresh_token for a 1-hour access_token.
    Returns (access_token, api_domain) - api_domain (e.g.
    "https://www.zohoapis.com.au") must be used for every subsequent CRM
    call; it reflects the data center this Zoho org actually lives on and
    is NOT necessarily the default zohoapis.com.
    """
    resp = session.post(
        ZOHO_ACCOUNTS_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "access_token" not in payload or "api_domain" not in payload:
        raise RuntimeError(f"Unexpected token response from Zoho (missing access_token/api_domain): {payload}")
    return payload["access_token"], payload["api_domain"]


def fetch_accounts(session: requests.Session, access_token: str, api_domain: str) -> list:
    """
    Pages through the Accounts module (filtered by ZOHO_MEMBER_CRITERIA if
    set, else an unfiltered listing), requesting only the Account_Name and
    ZOHO_ABN_FIELD fields, and returns the raw list of record dicts.
    """
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    fields = f"Account_Name,{ZOHO_ABN_FIELD}"
    records = []
    page = 1

    while True:
        if page > MAX_PAGES:
            raise RuntimeError(
                f"Hit the {MAX_PAGES}-page safety cap ({MAX_PAGES * PER_PAGE:,} records) without "
                f"running out of pages - that's far more than a membership list should ever have, "
                f"so something is likely wrong (e.g. ZOHO_MEMBER_CRITERIA too broad). Stopping "
                f"rather than looping forever."
            )

        params = {"fields": fields, "per_page": PER_PAGE, "page": page}
        if ZOHO_MEMBER_CRITERIA:
            url = f"{api_domain}/crm/v8/{ZOHO_MODULE}/search"
            params["criteria"] = ZOHO_MEMBER_CRITERIA
        else:
            url = f"{api_domain}/crm/v8/{ZOHO_MODULE}"

        resp = session.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 204:
            # Zoho's /search returns 204 No Content (not 200 + empty "data")
            # when nothing matches the criteria on this page - treat as "no
            # more records" rather than trying to parse an empty JSON body.
            break
        resp.raise_for_status()

        payload = resp.json()
        page_records = payload.get("data", [])
        records.extend(page_records)

        more_records = payload.get("info", {}).get("more_records", False)
        if not more_records or len(page_records) < PER_PAGE:
            break
        page += 1

    return records


def _normalize_abn(value) -> str:
    """
    Coerces a raw Zoho field value to a plain digit string. Zoho may return
    a numeric-typed custom field as a JSON float (e.g. 12345678901.0) -
    normalize at the source rather than leaving a stray ".0" suffix for a
    downstream consumer to clean up.
    """
    if value is None:
        return ""
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return str(value)
    return str(value).strip()


def extract_abns(records: list) -> list:
    """Pulls ZOHO_ABN_FIELD out of each raw record, normalizes it, drops
    blanks (with a warning), de-dupes, and sorts for a stable/diffable CSV.
    Hard-fails if NOTHING usable was found, since a silently-empty ABN list
    would make every downstream WGEA/Tech-Council filter match zero rows
    without raising anything - printing the first record's actual field
    names to help diagnose a wrong ZOHO_ABN_FIELD guess."""
    abns = []
    missing = []
    for rec in records:
        normalized = _normalize_abn(rec.get(ZOHO_ABN_FIELD))
        if not normalized:
            missing.append(rec.get("Account_Name") or rec.get("id") or "<unnamed>")
            continue
        abns.append(normalized)

    if missing:
        print(
            f"Warning: {len(missing)} of {len(records)} fetched Account(s) had no value in "
            f"'{ZOHO_ABN_FIELD}' - skipped (first few: {missing[:10]}).",
            file=sys.stderr,
        )

    if not abns:
        sample_keys = sorted(records[0].keys()) if records else []
        print(
            f"Error: no usable ABNs extracted from {len(records)} fetched Account(s).\n"
            f"ZOHO_ABN_FIELD is currently '{ZOHO_ABN_FIELD}' - confirm this is the correct API "
            f"field name with your CRM admin (Setup > Customization > Modules and Fields > "
            f"Accounts).\n"
            + (f"Field API names on the first fetched record were: {sample_keys}" if sample_keys
               else "No records were fetched at all - check ZOHO_MEMBER_CRITERIA too."),
            file=sys.stderr,
        )
        sys.exit(1)

    return sorted(set(abns))


def main():
    client_id = os.environ.get("ZOHO_CLIENT_ID")
    client_secret = os.environ.get("ZOHO_CLIENT_SECRET")
    refresh_token = os.environ.get("ZOHO_REFRESH_TOKEN")
    missing_env = [
        name
        for name, value in [
            ("ZOHO_CLIENT_ID", client_id),
            ("ZOHO_CLIENT_SECRET", client_secret),
            ("ZOHO_REFRESH_TOKEN", refresh_token),
        ]
        if not value
    ]
    if missing_env:
        print(
            f"Error: missing required environment variable(s): {', '.join(missing_env)}. "
            f"Set these (e.g. as GitHub Actions secrets) before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Path to write the fetched ABNs as CSV (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; zoho-abns-fetch-script/1.0)"})

    print("Requesting a Zoho access token ...", file=sys.stderr)
    try:
        access_token, api_domain = get_access_token(session, client_id, client_secret, refresh_token)
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else "<no body>"
        print(f"Error: Zoho token request failed: {e}\nResponse body: {body}", file=sys.stderr)
        sys.exit(1)
    print(f"Got access token; api_domain = {api_domain}", file=sys.stderr)

    print(f"Fetching {ZOHO_MODULE} records ...", file=sys.stderr)
    try:
        records = fetch_accounts(session, access_token, api_domain)
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else "<no body>"
        print(f"Error: Zoho {ZOHO_MODULE} fetch failed: {e}\nResponse body: {body}", file=sys.stderr)
        sys.exit(1)
    print(f"Fetched {len(records)} raw {ZOHO_MODULE} record(s).", file=sys.stderr)

    abns = extract_abns(records)
    print(f"Extracted {len(abns)} unique ABN(s).")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ABN": abns}).to_csv(output_path, index=False)
    print(f"Written to {output_path}")


if __name__ == "__main__":
    main()
