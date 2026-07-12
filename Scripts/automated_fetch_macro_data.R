# fetch_macro_data.R
#
# Fetches three Australian macro/labour-market series using the R
# `readabs` and `readrba` packages (both on CRAN, maintained by Matt
# Cowgill):
#
#   1. ABS EQ08 - "Employed persons by Occupation unit group of main job
#      (ANZSCO), Sex, State and Territory" - a data cube from the
#      Labour Force, Australia, Detailed release. readabs has a
#      purpose-built function for exactly this: read_lfs_datacube().
#   2. ABS unemployment rate (Persons, seasonally adjusted) - from the
#      main Labour Force, Australia release (cat. 6202.0), via read_abs().
#   3. RBA cash rate target (the Australian interest rate) - via
#      readrba's read_cashrate() convenience function.
#
# INSTALL
# -------
#   install.packages(c("readabs", "readrba"))
#
# USAGE
# -----
#   Rscript fetch_macro_data.R
#
# CAVEATS - PLEASE READ ON FIRST RUN
# ------------------------------------
# - I don't have an R interpreter in this environment (no outbound network
#   here either), so none of this has been run against the real ABS/RBA
#   files. It's built directly from readabs' and readrba's documented
#   function signatures and, for read_lfs_datacube(), its actual published
#   source code - not a verified live run.
# - read_lfs_datacube("EQ08") is a real, purpose-built function for this
#   exact data cube (confirmed from the readabs source: it reads the
#   "Data 1" sheet, skips 3 header rows, and tidies column names) - this
#   is the one piece I'm most confident about.
# - The unemployment-rate filter matches on the exact ABS series label
#   "Unemployment rate ;  Persons ;" - this is the same string format
#   ABS uses across both the R and Python ecosystems, but if ABS has
#   changed the wording, the script will error out and tell you to
#   inspect unique(lfs$series) to find the current label.
# - read_abs()'s tidied output column names (series, series_type, date,
#   value) reflect readabs' long-standing standard tidy format; flagged
#   here in case a newer version has renamed anything.

suppressPackageStartupMessages({
  library(readabs)
  library(readrba)
})

# Data/ lives alongside Scripts/ at the repo root, not inside Scripts/. Anchor
# to this script's own location (via the "--file=" argument Rscript passes)
# rather than the caller's working directory, so this works regardless of
# where it's invoked from. Falls back to getwd() if run interactively (no
# "--file=" argument, e.g. pasted into an R console).
script_dir <- function() {
  file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(file_arg) == 1) {
    return(dirname(normalizePath(sub("^--file=", "", file_arg))))
  }
  getwd()
}
DATA_INPUT_AUTOMATED_PULL <- file.path(dirname(script_dir()), "Data", "input", "automated_pull")

DEFAULT_EQ08_OUTPUT <- file.path(DATA_INPUT_AUTOMATED_PULL, "abs_eq08_employed_by_occupation.csv")
DEFAULT_UNEMPLOYMENT_OUTPUT <- file.path(DATA_INPUT_AUTOMATED_PULL, "abs_unemployment_rate.csv")
DEFAULT_INTEREST_RATE_OUTPUT <- file.path(DATA_INPUT_AUTOMATED_PULL, "rba_cash_rate.csv")
DEFAULT_UNEMPLOYMENT_CAT <- "A84423050A"

fetch_eq08 <- function(output_path = DEFAULT_EQ08_OUTPUT) {
  message("\nFetching EQ08 (Employed persons by Occupation unit group, Sex, State) ...")
  tryCatch(
    {
      df <- read_lfs_datacube("EQ08")
      message(sprintf("Got EQ08: %d rows, %d columns.", nrow(df), ncol(df)))
      message("Columns: ", paste(utils::head(colnames(df), 10), collapse = ", "))
      utils::write.csv(df, output_path, row.names = FALSE)
      message("Wrote ", output_path)
      TRUE
    },
    error = function(e) {
      message("Error fetching EQ08: ", conditionMessage(e))
      FALSE
    }
  )
}

fetch_unemployment_rate <- function(output_path = DEFAULT_UNEMPLOYMENT_OUTPUT, cat = DEFAULT_UNEMPLOYMENT_CAT) {
  message(sprintf("\nFetching unemployment rate from catalogue ID %s ...", cat))
  tryCatch(
    {
      unemployment <- read_abs_series(series_id = cat)
      if (nrow(unemployment) == 0) {
        stop(
          "No rows matched 'Unemployment rate ;  Persons ;' / 'Seasonally Adjusted'. ",
          "Run unique(lfs$series) to find the current exact label."
        )
      }
      message(sprintf("Got unemployment rate: %d observations.", nrow(unemployment)))
      utils::write.csv(unemployment[, c("date", "value")], output_path, row.names = FALSE)
      message("Wrote ", output_path)
      TRUE
    },
    error = function(e) {
      message("Error fetching unemployment rate: ", conditionMessage(e))
      FALSE
    }
  )
}

fetch_cash_rate <- function(output_path = DEFAULT_INTEREST_RATE_OUTPUT) {
  message("\nFetching RBA cash rate target ...")
  tryCatch(
    {
      cashrate <- read_cashrate(type = "target")
      message(sprintf("Got cash rate: %d observations.", nrow(cashrate)))
      utils::write.csv(cashrate, output_path, row.names = FALSE)
      message("Wrote ", output_path)
      TRUE
    },
    error = function(e) {
      message("Error fetching RBA cash rate: ", conditionMessage(e))
      FALSE
    }
  )
}

main <- function() {
  results <- c(
    "EQ08 (employed persons by occupation)" = fetch_eq08(),
    "Unemployment rate" = fetch_unemployment_rate(),
    "RBA cash rate" = fetch_cash_rate()
  )

  message("\nSummary:")
  for (name in names(results)) {
    status <- if (results[[name]]) "OK" else "FAILED"
    message(sprintf("  %-40s %s", name, status))
  }

  if (any(!results)) {
    quit(status = 1)
  }
}

main()
