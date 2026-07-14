**Tech Council ABNs — Manual Data Pull Instructions (superseded — now automated)**

**This process is now automated, and event-driven rather than scheduled.** A Zoho CRM Workflow Rule pushes a webhook straight to this repo (via GitHub's `repository_dispatch` API) whenever a Tech Council member Account is added, edited, or its membership status changes in Zoho CRM — `.github/workflows/sync-zoho-abn-webhook.yml` receives it and `scripts/sync_zoho_abn_webhook.py` updates `data/input/automated_pull/Tech_Council_ABNs.csv` accordingly. Nobody needs to ask the membership team for a CSV or upload one by hand anymore, and there's no scheduled pull to wait for — changes land within minutes of being made in Zoho. The steps below are kept as an **explicit fallback**: if the webhook ever breaks (the Zoho PAT expires, a workflow rule gets disabled, etc.), follow this doc to get a manual CSV into the repo at `data/input/manual_pull/Tech_Council_ABNs.csv` instead, and temporarily point `scripts/automated_data_prep.py`'s read path back at `manual_pull` until the webhook is fixed.

**Zoho webhook setup (one-time, in Zoho CRM — not part of this repo's code)**

Three Workflow Rules on the **Accounts** module in Zoho CRM, each with a **Webhook** instant action targeting `POST https://api.github.com/repos/tca-research/tech_vector/dispatches`, header `Authorization: token <A GITHUB PAT SCOPED TO THIS REPO>` and `Accept: application/vnd.github+json`. The PAT lives only inside this Zoho webhook configuration — never in this repo.

1. **Join/update** — trigger: Create or Edit, criteria `Membership_Status equals Active`. Webhook body:
   ```json
   {"event_type": "tech_vector_export", "client_payload": {"action": "upsert", "abn": "${Accounts.ABN}", "account_name": "${Accounts.Account_Name}"}}
   ```
2. **Departure (status change)** — trigger: Edit, criteria `Membership_Status is not Active`. Webhook body: same shape with `"action": "remove"`. Zoho workflow rules only fire on a false→true criteria transition, never true→false, so a rule scoped to "Active" alone will never catch a company *leaving* — this second, oppositely-scoped rule is what catches it. It will also re-fire on every subsequent edit to an already-inactive record, not just the moment it left; that's expected and harmless, since `sync_zoho_abn_webhook.py` treats removing an already-absent ABN as a no-op.
3. **Departure (record deleted)** — trigger: Delete. Webhook body: same `"action": "remove"` shape. **Not fully verified**: Zoho's own docs confirm Delete triggers support Webhook actions, but don't confirm whether `${Accounts.ABN}`/`${Accounts.Account_Name}` merge fields still resolve once the record is being deleted. Test this explicitly when setting up (create a test Account, delete it, confirm the webhook fires with real values) — if merge fields don't resolve, drop this rule and rely on rule 2 instead (mark an Account Inactive before removing/archiving it, rather than hard-deleting).

**Known trade-off**: there's no periodic reconciliation anymore. Zoho retries a failed webhook delivery once, ~15 minutes later, then stops trying for that trigger permanently — if both attempts fail, that one membership change is silently lost with no further attempts and no automated alert. This was a deliberate simplicity choice, not an oversight.

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
- This is now automated via a Zoho CRM webhook pushing directly to `scripts/sync_zoho_abn_webhook.py` — see the "Zoho webhook setup" section above for the exact rule/criteria/webhook-body configuration.
- `scripts/automated_data_prep.py` now reads `data/input/automated_pull/Tech_Council_ABNs.csv` by default. **If you're using this doc's fallback steps**, temporarily change that read path back to `DATA_INPUT / "manual_pull" / "Tech_Council_ABNs.csv"` until the webhook is working again, and revert once fixed.

**Where to put files (fallback only)**
- Place the CSV in `data/input/manual_pull/` in the repository. This is the folder `scripts/automated_data_prep.py` reads `Tech_Council_ABNs.csv` from **only** when temporarily reverted to the fallback path described above — normally it reads from `automated_pull/` instead.
