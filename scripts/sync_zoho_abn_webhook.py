"""
Applies a single ABN add/update/remove signal pushed from a Zoho CRM
Workflow Rule's webhook action (see .github/workflows/
sync-zoho-abn-webhook.yml, which passes github.event.client_payload
through as the 3 env vars below).

Replaces an earlier OAuth/CRM-polling design entirely: Zoho now pushes
membership changes to us event-driven, via 3 Workflow Rules on the
Accounts module (see scripts/MANUAL_DATA_PULL_INSTRUCTIONS_
TECH_COUNCIL_ABNS.md's "Zoho webhook setup" section for the exact
criteria/webhook-body configuration). No Zoho OAuth client and no GitHub
secrets are needed for this path at all -- the only credential involved
(a GitHub PAT with access to trigger repository_dispatch) lives inside
Zoho's own webhook header config, never in this repo.

REQUIRED ENVIRONMENT VARIABLES (set by the workflow from
github.event.client_payload)
-------------------------------------------------------------------------
    ZOHO_WEBHOOK_ACTION        - "upsert" or "remove"
    ZOHO_WEBHOOK_ACCOUNT_NAME  - the Zoho Account's name (commit-message
                                  traceability only -- ABN is the actual
                                  join key downstream, not the name)
    ZOHO_WEBHOOK_ABN           - the account's ABN

Idempotent by design: Zoho's own workflow-rule semantics mean "remove"
can arrive repeatedly for the same ABN -- a rule scoped to
"Membership_Status is not Active" fires on every subsequent edit to an
already-inactive record, not just the moment it became inactive (Zoho
workflow rules only fire on a false->true criteria transition, so the
reverse direction needs this separately-scoped rule, which then re-fires
on every later edit too). Removing an ABN that's already absent, or
upserting one that's already present with the same value, are both safe
no-ops here -- that's what makes the repeated-firing behavior harmless.
"""

import sys
import os
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
ABNS_CSV = REPO_ROOT / "data" / "input" / "automated_pull" / "Tech_Council_ABNs.csv"


def _normalize_abn(value) -> str:
    return str(value).strip()


def main():
    action = os.environ.get("ZOHO_WEBHOOK_ACTION")
    account_name = os.environ.get("ZOHO_WEBHOOK_ACCOUNT_NAME") or "<unknown>"
    abn = os.environ.get("ZOHO_WEBHOOK_ABN")

    if action not in ("upsert", "remove"):
        print(
            f"Error: ZOHO_WEBHOOK_ACTION must be 'upsert' or 'remove', got {action!r}.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not abn or not _normalize_abn(abn):
        print("Error: ZOHO_WEBHOOK_ABN is missing or empty -- refusing to guess.", file=sys.stderr)
        sys.exit(1)

    abn = _normalize_abn(abn)

    if ABNS_CSV.exists():
        df = pd.read_csv(ABNS_CSV, dtype=str)
    else:
        df = pd.DataFrame({"ABN": []})

    existing = set(df["ABN"].dropna().map(_normalize_abn))

    if action == "upsert":
        if abn in existing:
            print(f"ABN {abn} ({account_name}) already present -- no change.")
        else:
            df = pd.concat([df, pd.DataFrame({"ABN": [abn]})], ignore_index=True)
            print(f"Added ABN {abn} ({account_name}).")
    else:  # remove
        if abn not in existing:
            print(f"ABN {abn} ({account_name}) not present -- no change.")
        else:
            df = df[df["ABN"].map(_normalize_abn) != abn]
            print(f"Removed ABN {abn} ({account_name}).")

    df = df.drop_duplicates(subset="ABN").sort_values("ABN").reset_index(drop=True)
    ABNS_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ABNS_CSV, index=False)


if __name__ == "__main__":
    main()
