**Tech Council ABNs — Manual Data Pull Instructions (superseded — now automated)**

**This process is now automated.** `scripts/automated_fetch_zoho_abns.py` pulls the current member ABN list directly from Zoho CRM on every scheduled rebuild, writing `data/input/automated_pull/Tech_Council_ABNs.csv` — nobody needs to ask the membership team for a CSV or upload one by hand anymore. The steps below are kept as an **explicit fallback**: if the Zoho automation ever breaks (expired credentials, a CRM field renamed, etc.), follow this doc to get a manual CSV into the repo at `data/input/manual_pull/Tech_Council_ABNs.csv` instead, and temporarily point `scripts/automated_data_prep.py`'s read path back at `manual_pull` until the automation is fixed.

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
- This is now automated via `scripts/automated_fetch_zoho_abns.py`, pulling directly from the TCA Zoho CRM (Accounts module) on every scheduled rebuild — see that script's docstring for the exact auth/field-mapping details and its two unconfirmed placeholders (`ZOHO_ABN_FIELD`, `ZOHO_MEMBER_CRITERIA`).
- `scripts/automated_data_prep.py` now reads `data/input/automated_pull/Tech_Council_ABNs.csv` by default. **If you're using this doc's fallback steps**, temporarily change that read path back to `DATA_INPUT / "manual_pull" / "Tech_Council_ABNs.csv"` until the Zoho automation is working again, and revert once fixed.

**Where to put files (fallback only)**
- Place the CSV in `data/input/manual_pull/` in the repository. This is the folder `scripts/automated_data_prep.py` reads `Tech_Council_ABNs.csv` from **only** when temporarily reverted to the fallback path described above — normally it reads from `automated_pull/` instead.
