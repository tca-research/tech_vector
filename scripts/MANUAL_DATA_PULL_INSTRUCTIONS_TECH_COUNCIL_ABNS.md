**Tech Council ABNs — Manual Data Pull Instructions**

This document explains how to get the current list of Tech Council of Australia member ABNs into this repository so `scripts/automated_data_prep.py` can identify which WGEA-reporting companies are Tech Council members.

**Overview**
- **Purpose:** Obtain the latest list of Tech Council member ABNs and place it in the repository at `data/input/manual_pull/Tech_Council_ABNs.csv`, with a column named `ABN`, so the data prep pipeline can match it against WGEA data.
- **There is no automated source for this yet** — see "Future automation" below.

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

**Future automation**
- This may be automated down the line using Zoho Flow, pulling directly from the TCA CRM — but that integration hasn't been configured yet, so for now this is a manual pull.
- **Once that automation is set up:** move the file from `data/input/manual_pull/Tech_Council_ABNs.csv` to `data/input/automated_pull/Tech_Council_ABNs.csv`, and update the read path in `scripts/data_prep.py` (currently `DATA_INPUT / "manual_pull" / "Tech_Council_ABNs.csv"`) to point at `automated_pull` instead. Search the repo for `Tech_Council_ABNs.csv` to make sure no other file references the old `manual_pull` path.

**Where to put files**
- Place the CSV in `data/input/manual_pull/` in the repository. This is the folder `scripts/data_prep.py` currently reads `Tech_Council_ABNs.csv` from.
