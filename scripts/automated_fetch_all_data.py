"""
Runs all five data-pull scripts in one go:
    - automated_fetch_oecd.py               (OECD MSTI - Australia GERD % of GDP, all countries)
    - automated_fetch_wgea.py                (WGEA salary/composition/management stats)
    - automated_fetch_global_ai_ranking.py   (Stanford HAI Global AI Vibrancy ranking)
    - automated_fetch_levels_fyi.py          (Levels FYI - Australia tech sector salaries)
    - automated_fetch_macro_data.R           (Macro data - ABS unemployment rate, RBA cash
                                     rate, ABS EQ08 employed by occupation)

Each script is fully standalone with its own sensible defaults (no required
arguments), so this just calls each one in turn and reports what happened -
it doesn't duplicate any of their logic.

Individual scripts' own stdout/stderr is captured rather than printed, so
this file's own progress/summary lines are the only thing shown on a
successful run. If a script fails, its captured output is printed in full
underneath its summary line, so failures are still fully debuggable.

USAGE
-----
    python3 fetch_all_data.py

Put this file in the same directory as the scripts above (or edit SCRIPTS
below to point elsewhere). Exits non-zero if any script failed, so it plugs
into a CI job / GitHub Action the same way a single script would.
"""

import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

SCRIPTS = [
    "automated_fetch_wgea.py",
    "automated_fetch_oecd.py",
    "automated_fetch_global_ai_ranking.py",
    "automated_fetch_levels_fyi.py",
    "automated_fetch_macro_data.R",
]

INTERPRETERS = {
    ".py": [sys.executable],
    ".R": ["Rscript"],
}


def run_script(script_name: str) -> tuple:
    """Runs one script as a subprocess, capturing (not streaming) its
    output. Returns (script_name, returncode, elapsed_seconds, output)."""
    path = SCRIPT_DIR / script_name
    print(f"Running {script_name} ...")

    if not path.exists():
        print(f"  Error: {path} not found - skipping.", file=sys.stderr)
        return script_name, 1, 0.0, ""

    interpreter = INTERPRETERS.get(path.suffix)
    if interpreter is None:
        print(f"  Error: no interpreter configured for '{path.suffix}' files - skipping.", file=sys.stderr)
        return script_name, 1, 0.0, ""

    start = time.monotonic()
    try:
        result = subprocess.run(interpreter + [str(path)], capture_output=True, text=True)
        returncode = result.returncode
        output = result.stdout + result.stderr
    except FileNotFoundError as e:
        elapsed = time.monotonic() - start
        print(f"  Error: couldn't launch interpreter {interpreter[0]!r} - is it installed? ({e})", file=sys.stderr)
        return script_name, 1, elapsed, str(e)
    elapsed = time.monotonic() - start
    return script_name, returncode, elapsed, output


def main():
    results = [run_script(script) for script in SCRIPTS]

    print(f"\n{'=' * 70}\nSummary\n{'=' * 70}")
    any_failed = False
    for script_name, returncode, elapsed, output in results:
        status = "OK" if returncode == 0 else f"FAILED (exit {returncode})"
        any_failed = any_failed or returncode != 0
        print(f"  {script_name:<30} {status:<20} {elapsed:5.1f}s")
        if returncode != 0:
            print(f"  {'-' * 66}")
            print(f"  Output from {script_name}:")
            for line in output.splitlines():
                print(f"    {line}")
            print(f"  {'-' * 66}")

    if any_failed:
        print("\nOne or more scripts failed - see output above for details.")
        sys.exit(1)
    print("\nAll scripts completed successfully.")


if __name__ == "__main__":
    main()