"""
Replaces data/input/automated_pull/Tech_Council_ABNs.csv wholesale with the
full current membership snapshot pushed by a Zoho-side process via
GitHub's repository_dispatch API (see .github/workflows/
sync-zoho-abn-webhook.yml).

Every delivery carries ALL currently-active Tech Council member Accounts
in one payload, e.g.:
    {"sync_date": "14-Jul-2026", "account_count": 158,
     "accounts_data": [{"account_id": "...", "company_name": "...",
     "abn": "44 645 215 194"}, ...]}
So this script always overwrites the CSV wholesale rather than tracking
incremental add/remove events -- this is self-healing by construction,
since there's no way for the CSV to drift from Zoho's true state between
deliveries when each one already IS the full true state.

ABN NORMALIZATION
------------------
Zoho sends ABNs in human display format with space separators (e.g.
"44 645 215 194"), not the bare-digit string automated_data_prep.py's
.isin() match against WGEA's Employer ABN column needs -- leaving the
spaces in would make every one of these companies silently fail to match
anything, with no error. This is the same class of bug as this pipeline's
established ISO-date and gauge-unit rules: it renders/runs fine and
produces a wrong answer. Every ABN is stripped to bare digits before being
written out (normalize_abn()).

A real fraction of records have a missing ("") or malformed (not exactly
11 digits, e.g. "149633116") ABN -- genuine data quality issues in the
source CRM, not something this script can fix. Rather than failing the
whole sync over a handful of bad records (which would block 150+ good
ones over 2-3 companies with no valid ABN on file), invalid entries are
skipped with a clear per-company warning, so whoever administers the CRM
can go fix the record -- collect every issue and report it clearly,
don't silently drop data or crash on the first bad row.

REQUIRED ENVIRONMENT VARIABLE
-------------------------------------------------------------------------
    ZOHO_WEBHOOK_PAYLOAD - the raw JSON string of the webhook's
                            client_payload (see
                            .github/workflows/sync-zoho-abn-webhook.yml
                            for how this is populated from
                            github.event.client_payload, or a
                            workflow_dispatch test input)
"""

import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
ABNS_CSV = REPO_ROOT / "data" / "input" / "automated_pull" / "Tech_Council_ABNs.csv"


def normalize_abn(raw) -> str:
    """Strips everything but digits. A valid Australian ABN is always
    exactly 11 digits -- callers should treat any other length as
    invalid, not attempt to coerce/pad it."""
    return re.sub(r"\D", "", str(raw or ""))


def extract_abns(accounts: list) -> tuple:
    """Returns (valid_abns, skipped_descriptions). An account is skipped
    if its normalized ABN isn't exactly 11 digits (covers both a blank
    "" ABN and a wrong-length one like Deloitte's real "149633116")."""
    valid = []
    skipped = []
    for acct in accounts:
        name = acct.get("company_name") or acct.get("account_id") or "<unnamed>"
        raw_abn = acct.get("abn")
        abn = normalize_abn(raw_abn)
        if len(abn) != 11:
            skipped.append(f"{name} (raw ABN: {raw_abn!r})")
            continue
        valid.append(abn)
    return valid, skipped


def write_github_output(**kwargs):
    """Best-effort: writes step outputs for the workflow's commit-message
    step to reference. No-op if GITHUB_OUTPUT isn't set (e.g. running
    this script by hand locally)."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        for key, value in kwargs.items():
            f.write(f"{key}={value}\n")


def main():
    raw_payload = os.environ.get("ZOHO_WEBHOOK_PAYLOAD")
    if not raw_payload:
        print("Error: ZOHO_WEBHOOK_PAYLOAD is missing or empty.", file=sys.stderr)
        sys.exit(1)

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as e:
        print(f"Error: ZOHO_WEBHOOK_PAYLOAD is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    accounts = payload.get("accounts_data")
    if not isinstance(accounts, list) or not accounts:
        print(
            "Error: expected a non-empty 'accounts_data' list in the payload, got: "
            f"{type(accounts).__name__ if accounts is not None else 'missing'}.",
            file=sys.stderr,
        )
        sys.exit(1)

    expected_count = payload.get("account_count")
    if expected_count is not None and expected_count != len(accounts):
        print(
            f"Warning: payload's account_count ({expected_count}) doesn't match "
            f"the actual accounts_data length ({len(accounts)}) -- possible "
            "truncated/corrupted payload. Proceeding with what was received.",
            file=sys.stderr,
        )

    abns, skipped = extract_abns(accounts)

    if skipped:
        print(
            f"Warning: skipped {len(skipped)} of {len(accounts)} account(s) with a "
            "missing or malformed (not exactly 11 digits) ABN -- these companies "
            "won't be cross-referenced against WGEA data until fixed in Zoho CRM:",
            file=sys.stderr,
        )
        for s in skipped:
            print(f"  - {s}", file=sys.stderr)

    if not abns:
        print(
            "Error: zero usable ABNs extracted from the payload -- refusing to "
            "overwrite the CSV with an empty/garbage result.",
            file=sys.stderr,
        )
        sys.exit(1)

    df = pd.DataFrame({"ABN": sorted(set(abns))})
    ABNS_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ABNS_CSV, index=False)

    print(
        f"Wrote {len(df)} unique ABN(s) to {ABNS_CSV} "
        f"(from {len(accounts)} accounts in the payload, {len(skipped)} skipped)."
    )
    write_github_output(
        written_count=len(df),
        skipped_count=len(skipped),
        account_count=len(accounts),
        sync_date=payload.get("sync_date", ""),
    )


if __name__ == "__main__":
    main()
