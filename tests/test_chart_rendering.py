"""Playwright-driven tests against the actual, already-built chart HTML in
charts/*.html (committed to the repo — see CLAUDE.md — so these run without
needing the data pipeline or a rebuild first).

This complements the pure-function tests elsewhere in tests/: several real
bugs fixed in this project only showed up in the rendered page's actual
DOM/CSS/event behavior (a tooltip's fixed-position anchor, an SVG element's
paint-order hit-testing, touch's pointer-event lifecycle) — nothing a
function-level unit test could have caught. Formalizes the manual
console-error sweep from .claude/skills/run-pipeline/SKILL.md into a real,
parametrized, assertable test, plus regression coverage for each bug found
this way so far.
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CHARTS_DIR = REPO_ROOT / "charts"
# Path.glob("*.html") is non-recursive, so charts/test/*.html (a stale
# fixture directory, not part of the live site) is naturally excluded —
# matching the same convention the run-pipeline skill's sweep uses.
CHART_FILES = sorted(p.name for p in CHARTS_DIR.glob("*.html"))


def _chart_url(filename):
    return "file://" + str((CHARTS_DIR / filename).resolve())


def _first_hit_target(page):
    """The invisible rect/circle each interactive chart draws to catch
    hover/tap — gauges, references, and the status card have none."""
    return page.query_selector('svg rect[fill="transparent"], svg circle[fill="transparent"]')


# ---------------------------------------------------------------------------
# Console-error sweep — every chart, no exceptions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", CHART_FILES, ids=CHART_FILES)
def test_chart_has_no_console_errors(page, filename):
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(_chart_url(filename))
    page.wait_for_timeout(300)
    assert errors == []


# ---------------------------------------------------------------------------
# Tooltip behavior — mouse hover, positioning, and overflow.
# Regression coverage for: the crosshair-line hit-testing self-interference
# bug, the position:fixed top/left:auto anchor bug, and the tt-row overflow
# bug — all found by actually observing the rendered tooltip, not by
# unit-testing showTooltip()/ttRow() in isolation.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", CHART_FILES, ids=CHART_FILES)
def test_tooltip_shows_on_hover_positioned_near_cursor_without_overflow(page, filename):
    page.goto(_chart_url(filename))
    page.wait_for_timeout(250)
    hit = _first_hit_target(page)
    if hit is None:
        pytest.skip(f"{filename} has no hoverable chart element")
    box = hit.bounding_box()
    if not box or box["width"] == 0 or box["height"] == 0:
        pytest.skip(f"{filename}'s hit target has no visible size")

    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(cx, cy)
    page.wait_for_timeout(150)

    tooltip = page.query_selector("#tooltip")
    assert "visible" in tooltip.get_attribute("class"), "tooltip never appeared on hover"

    ttbox = tooltip.bounding_box()
    # showTooltip()'s own pad is 14px past the cursor. A much larger offset
    # means the fixed-position anchor bug is back (tooltip anchored to its
    # own static flow position instead of the viewport's top-left corner).
    assert abs((ttbox["y"] - cy) - 14) < 3, (
        f"tooltip is {ttbox['y'] - cy:.0f}px below the cursor, expected ~14px"
    )

    for value_el in tooltip.query_selector_all(".tt-value"):
        vbox = value_el.bounding_box()
        assert vbox["x"] + vbox["width"] <= ttbox["x"] + ttbox["width"] + 1, (
            f"a .tt-value in {filename}'s tooltip overflows the tooltip box"
        )


@pytest.mark.parametrize("filename", CHART_FILES, ids=CHART_FILES)
def test_tooltip_works_via_touch_tap_and_dismisses_on_tap_elsewhere(browser, filename):
    context = browser.new_context(has_touch=True, is_mobile=True, viewport={"width": 1200, "height": 900})
    try:
        page = context.new_page()
        page.goto(_chart_url(filename))
        page.wait_for_timeout(250)
        hit = _first_hit_target(page)
        if hit is None:
            pytest.skip(f"{filename} has no hoverable chart element")
        box = hit.bounding_box()
        if not box or box["width"] == 0 or box["height"] == 0:
            pytest.skip(f"{filename}'s hit target has no visible size")

        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.touchscreen.tap(cx, cy)
        page.wait_for_timeout(150)
        tooltip = page.query_selector("#tooltip")
        assert "visible" in tooltip.get_attribute("class"), "tap never showed the tooltip"

        page.touchscreen.tap(5, 5)
        page.wait_for_timeout(150)
        assert "visible" not in tooltip.get_attribute("class"), "tap elsewhere didn't dismiss the tooltip"
    finally:
        context.close()


# ---------------------------------------------------------------------------
# small_multiples.html — axis unit suffixes + panel alignment
# ---------------------------------------------------------------------------

def test_small_multiples_axis_suffixes_and_panels_are_aligned(page):
    page.goto(_chart_url("small_multiples.html"))
    page.wait_for_timeout(300)

    svgs = page.query_selector_all(".chart-mount svg")
    assert len(svgs) == 4

    tops = [round(s.bounding_box()["y"], 1) for s in svgs]
    assert len(set(tops)) == 1, f"panels are not vertically aligned: {tops}"

    def axis_texts(svg):
        return [t.evaluate("el => el.textContent") for t in svg.query_selector_all("text.axis-label")]

    macro_labels = axis_texts(svgs[0])
    assert any(t.endswith("%") for t in macro_labels), "macro panel y-axis missing '%' suffix"

    for occ_svg in svgs[1:]:
        occ_labels = axis_texts(occ_svg)
        assert any(t.endswith("K") for t in occ_labels), "occupation panel y-axis missing 'K' suffix"


# ---------------------------------------------------------------------------
# interactive_line_chart.html — title {year} resolution + adaptive x-axis
# ---------------------------------------------------------------------------

def test_interactive_line_title_has_no_unresolved_year_placeholder(page):
    page.goto(_chart_url("interactive_line_chart.html"))
    page.wait_for_timeout(300)
    title = page.query_selector("#chart-title").inner_text()
    assert "{year}" not in title


def test_interactive_line_year_axis_has_no_forced_rotation_or_jan_prefix(page):
    page.goto(_chart_url("interactive_line_chart.html"))
    page.wait_for_timeout(300)

    axis_labels = page.query_selector_all(".chart-mount svg text.axis-label")
    year_labels = [l for l in axis_labels if re.fullmatch(r"\d{4}", l.evaluate("el => el.textContent"))]
    assert year_labels, "no 4-digit year tick labels found"

    for label in year_labels:
        assert label.evaluate("el => el.textContent").strip().startswith(("1", "2"))
        assert "Jan" not in label.evaluate("el => el.textContent")
        # Angle 0 unless genuinely needed — see interactive_line.js's
        # rotateLabels check; this dataset's ticks are wide enough apart
        # that no rotation transform should be present at all.
        assert label.get_attribute("transform") is None


# ---------------------------------------------------------------------------
# line_chart.js charts — tooltip date must be human-readable, not raw ISO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", [
    "tech_share_of_labour_force_chart.html",
    "total_tech_employment_chart.html",
])
def test_line_chart_tooltip_date_is_human_readable(page, filename):
    page.goto(_chart_url(filename))
    page.wait_for_timeout(300)
    hit = page.query_selector('svg rect[fill="transparent"]')
    box = hit.bounding_box()
    cx, cy = box["x"] + box["width"] * 0.4, box["y"] + box["height"] * 0.5
    page.mouse.move(cx, cy)
    page.wait_for_timeout(150)

    title_el = page.query_selector("#tooltip .tt-title")
    assert title_el is not None, "tooltip never appeared"
    title_text = title_el.inner_text()
    assert re.fullmatch(r"[A-Za-z]+ \d{4}", title_text), (
        f"expected a 'Month YYYY' tooltip title, got {title_text!r}"
    )
