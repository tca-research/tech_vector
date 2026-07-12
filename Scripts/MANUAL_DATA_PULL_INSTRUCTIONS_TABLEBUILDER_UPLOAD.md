**TableBuilder CSV Download & GitHub Upload**

This document explains how to download CSVs from the ABS TableBuilder and upload them to this repository so the automated GH Actions workflows can run.

**Overview**
- **Purpose:** Download the required CSV(s) from ABS TableBuilder and place them in the repository at `Data/input/manual_pull/` with the exact filenames expected by the automation: `tech_vector_roles_in_subsector.csv` and `tech_vector_roles_across_economy.csv`.

**Step 1: Downloading CSV from ABS TableBuilder**
- **Open the TableBuilder link:** Click the link to the ABS TableBuilder page provided by the dashboard or bookmarking the ABS TableBuilder URL in your browser.
- **Sign in / accept terms:** If prompted, sign in or accept any usage terms required by ABS TableBuilder.
- **Open the table layout:** Locate and open the relevant table (the dashboard usually points to the exact table). If the table provides multiple views, choose the view/layout that matches the automation expectations (usually the full table with variables in columns and years/units in rows).
- **Export / Download:** Look for an `Export` or `Download` button (top-right). Choose `CSV` (comma-separated) as the format. Name the files `tech_vector_roles_in_subsector` and `tech_vector_roles_across_economy`. You may need to delete older versions of this file to write over the data.
- **View the saved files page:** Click through to the saved files page and download the files you need.
- **Save file with expected filename:** Save the downloaded files: `tech_vector_roles_in_subsector.csv` and `tech_vector_roles_across_economy.csv`
- **Unzip the zipped folder and grab the CSV export.**


**Step 2: Uploading the CSV to GitHub (Web UI)**
- **Open the repository in GitHub:** Go to the repo page in your browser.
- **Navigate to folder:** Click through to `Data/input/manual_pull/`.
- **Add file → Upload files:** Click `Add file` → `Upload files` and either drag-and-drop the CSV or use the file picker to select it.
- **Commit changes:** In the commit form, set a clear message, e.g. `Add ABS TableBuilder CSV: tech_vector_roles_in_subsector.csv`.
  - If you want to use a branch and PR workflow, create a new branch and then create a pull request after uploading.
  - If you have permission and the repo policy allows, you can commit directly to `main` (or the default branch).
- **Wait for GH Actions:** After pushing or merging, GitHub Actions should trigger automatically. Check the Actions tab for the workflow run and any errors.

**Step 3: Uploading the CSV via Git (CLI)**
- **Copy the file into your local repo clone:** Place the CSV in `Data/input/manual_pull/`.
- **Commit and push:** Run the following commands from the root of your local repository clone:

```bash
git add Data/input/manual_pull/*.csv
git commit -m "Add ABS TableBuilder CSV'
git push origin main
```

- **If you prefer a feature branch / PR:**

```bash
git checkout -b add_csv
git add Data/input/manual_pull/*csv
git commit -m "Add ABS TableBuilder CSV"
git push -u origin add_csv
# Then open a PR on GitHub
```

**Checklist before uploading**
- **Filename:** Use the exact filename expected by automation (see `Data/input/manual_pull/`).
- **File must be a CSV, not Excel file**.

**Troubleshooting**
- If GH Actions fails after upload, check the Actions run log for the file path and parsing errors.
- If the script expects a particular column name or order, open the CSV and confirm column names match the automation's expectations.

**Where to put files**
- Place the CSV(s) in `Data/input/manual_pull/` in the repository. This is the folder the automation currently reads from.
