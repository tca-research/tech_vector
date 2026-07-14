**Tech Council ABNs — Manual Data Pull Instructions (superseded — now automated)**

**This process is now automated.** A Zoho-side process pushes the **full current list** of active Tech Council member Accounts straight to this repo (via GitHub's `repository_dispatch` API) in one payload — `.github/workflows/sync-zoho-abn-webhook.yml` receives it and `scripts/sync_zoho_abn_webhook.py` overwrites `data/input/automated_pull/Tech_Council_ABNs.csv` wholesale with what it received. Nobody needs to ask the membership team for a CSV or upload one by hand anymore. The steps below are kept as an **explicit fallback**: if the webhook ever breaks, follow this doc to get a manual CSV into the repo at `data/input/manual_pull/Tech_Council_ABNs.csv` instead, and temporarily point `scripts/automated_data_prep.py`'s read path back at `manual_pull` until the webhook is fixed.

**Payload contract** — `repository_dispatch` with `event_type: "tech_vector_export"` and a `client_payload` shaped:
```json
{"sync_date": "14-Jul-2026", "account_count": 158, "accounts_data": [{"account_id": "...", "company_name": "...", "abn": "44 645 215 194"}, ...]}
```
- `accounts_data` must contain **every currently-active member**, not a diff/incremental change — each delivery fully replaces the CSV, so a delivery that only contains a subset would silently drop every member missing from it. This is what makes the sync self-healing (a delivery that fails just means the previous good snapshot stays in place until the next one succeeds), but it also means a *malformed* delivery is dangerous in a different way than a missing one — treat "send a complete list every time" as a hard requirement on whatever generates this payload.
- ABNs arrive in human display format with spaces (`"44 645 215 194"`); `sync_zoho_abn_webhook.py` strips them to bare digits before writing. It also skips (with a per-company warning, not a hard failure) any account whose ABN isn't exactly 11 digits after stripping — real production data has had both blank ABNs and wrong-length ones (e.g. a 9-digit value) for a handful of accounts; these need fixing at the CRM source, this script can't guess a company's real ABN.
- `account_count` is checked against `len(accounts_data)` as an integrity sanity check (a mismatch is only a warning, not a hard failure — an update to this doc noting whatever generates the payload should probably make these agree).

**Owner:** Leo (leo@techcouncil.com.au) owns the Zoho-side process that sends this payload — he's the contact for changes to the trigger, the GitHub PAT, or the payload shape.

**What sends this payload, and on what trigger, isn't documented here yet** — this section previously described a 3-Workflow-Rule, per-record-change design that turned out not to match what's actually running. Leo should fill in: what triggers a send (a schedule? a manual run? a record change that then queries everyone?), and the GitHub PAT setup (`Authorization: token <PAT>` header, `POST https://api.github.com/repos/tca-research/tech_vector/dispatches`) it uses to reach this repo.

This document explains how to get the current list of Tech Council of Australia member ABNs into this repository so `scripts/automated_data_prep.py` can identify which WGEA-reporting companies are Tech Council members.

**Overview**
- **Purpose:** Obtain the latest list of Tech Council member ABNs and place it in the repository at `data/input/manual_pull/Tech_Council_ABNs.csv`, with a column named `ABN`, so the data prep pipeline can match it against WGEA data.
- **This is now automated** — see the banner above and "Future automation" below.

**Step 1: Request the ABNs**
- **Ask the membership team** for a copy of the latest Tech Council ABNs (the current list of Tech Council of Australia member companies and their Australian Business Numbers).

**Step 2: Save as CSV**
- **Save the list as a CSV file** (not Excel).
- **Column name:** The file must have a column named exactly `ABN` (case-sensitive) containing each member company's ABN. `scripts/automated_data_prep.py` reads this column by name — a different name or casing will raise a `KeyError` when the script runs.
- **No stray index column:** Save with just the `ABN` column (and any other columns the membership team provides) — don't let a spreadsheet tool add an unnamed leading index column when exporting.
- **Filename:** Save the file as `Tech_Council_ABNs.csv` (exact filename expected by the automation).

**Step 3: Upload the CSV to GitHub (Web UI)**
- **Open the repository in GitHub:** Go to the repo page in your browser.
- **Navigate to folder:** Click through to `data/input/manual_pull/`.
- **Add file → Upload files:** Click `Add file` → `Upload files` and drag-and-drop `Tech_Council_ABNs.csv`, or use the file picker to select it. This will overwrite the previous version.
- **Commit changes:** In the commit form, set a clear message, e.g. `Update Tech Council ABNs`.
  - If you want to use a branch and PR workflow, create a new branch and then create a pull request after uploading.
  - If you have permission and the repo policy allows, you can commit directly to `main` (or the default branch).

**Step 4: Upload the CSV via Git (CLI)**
- **Copy the file into your local repo clone:** Place the CSV in `data/input/manual_pull/`, overwriting the previous version.
- **Commit and push:** Run the following commands from the root of your local repository clone:

```bash
git add data/input/manual_pull/Tech_Council_ABNs.csv
git commit -m "Update Tech Council ABNs"
git push origin main
```

- **If you prefer a feature branch / PR:**

```bash
git checkout -b update_tca_abns
git add data/input/manual_pull/Tech_Council_ABNs.csv
git commit -m "Update Tech Council ABNs"
git push -u origin update_tca_abns
# Then open a PR on GitHub
```

**Checklist before uploading**
- **Filename:** `Tech_Council_ABNs.csv` exactly.
- **Column name:** `ABN`, exact spelling and casing.
- **File must be a CSV, not an Excel file.**

**Future automation — done**
- This is now automated via a Zoho CRM webhook pushing directly to `scripts/sync_zoho_abn_webhook.py` — see "Payload contract" above for the exact payload shape and field-level caveats, and "Owner" above for who to contact about the Zoho-side setup.
- `scripts/automated_data_prep.py` now reads `data/input/automated_pull/Tech_Council_ABNs.csv` by default. **If you're using this doc's fallback steps**, temporarily change that read path back to `DATA_INPUT / "manual_pull" / "Tech_Council_ABNs.csv"` until the webhook is working again, and revert once fixed.

**Where to put files (fallback only)**
- Place the CSV in `data/input/manual_pull/` in the repository. This is the folder `scripts/automated_data_prep.py` reads `Tech_Council_ABNs.csv` from **only** when temporarily reverted to the fallback path described above — normally it reads from `automated_pull/` instead.
