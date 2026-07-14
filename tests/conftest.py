"""Shared fixtures for the whole suite.

This repo has no packages (no __init__.py anywhere) — scripts/*.py and
scripts/charts/*.py are plain modules meant to be run directly, the same way
build_charts.py itself does `sys.path.insert(0, str(SCRIPTS_DIR))` before
`import manual_data_prep`. Tests need the same path setup to import them.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
CHARTS_SCRIPT_DIR = SCRIPTS_DIR / "charts"
CHARTS_OUT_DIR = REPO_ROOT / "charts"

for _p in (SCRIPTS_DIR, CHARTS_SCRIPT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


@pytest.fixture
def repo_root():
    return REPO_ROOT


@pytest.fixture
def charts_out_dir():
    """Directory of already-built, committed chart HTML files (charts/*.html)
    — these are checked into the repo (see CLAUDE.md), so rendering tests can
    exercise them directly without running the data pipeline first."""
    return CHARTS_OUT_DIR
