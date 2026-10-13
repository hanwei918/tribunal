"""The two narrow-screen fixes, read out of the built pages rather than a browser.

The owner scanned every built page with axe-core 4.8.2 at a 1440 x 900 window and
found no violations; at a 375 px window 25 pages were wider than the screen. Two
causes were fixed in the sources -- the case page's status chip, which carries the
trigger and the time and can be 460 px wide, and the About page's three-figure row,
whose inline grid held three cells and pushed "3,200+" out of its own.

Both fixes are CSS, and both are only observable in what the builders write, so
this module reads the built files directly. It launches no browser and runs no
builder. What it holds:

* the built case page carries the item-1 rule that lets the chip row wrap at 560
  px or less;
* the built queue's own ``.chip`` rule still refuses to wrap -- the queue's Status
  column draws no ``.chips`` row, so the queue is untouched by the fix;
* the built About pages, English and Chinese, give the stats row the ``stats s3``
  class and carry no inline ``grid-template-columns``;
* the built site stylesheet carries the three ``.stats.s3`` rules, the 560 px one
  included.

Every failure names the file it read, so a reader knows which page moved.

No model call, no browser, and nothing here reads a run.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "ui" / "dist"

# The one rule item 1 adds, as ``ui/v2/build.py`` writes it and the builder embeds
# it. The exact bytes, so a reworded rule is a failure and not a near miss.
CHIP_RULE = (
    "@media (max-width:560px){.chips .chip{white-space:normal;height:auto;"
    "min-height:24px;max-width:100%;padding:3px 10px;line-height:1.35}}"
)

# The three rules item 2 adds to the site stylesheet.
S3_COLUMNS_RULE = ".stats.s3{grid-template-columns:repeat(3,minmax(0,1fr))}"
S3_DIVIDER_RULE = (
    ".stats.s3 .stat+.stat{border-left:1px solid var(--band-line);border-top:0}"
)
S3_NARROW_RULE = (
    "@media (max-width:560px){.stats.s3{grid-template-columns:minmax(0,1fr)}"
    ".stats.s3 .stat+.stat{border-left:0;border-top:1px solid var(--band-line)}}"
)

# The page's own stylesheet is not markup: a built page carries the whole site CSS
# inline, so the checks below that look for an inline *style attribute* read the
# body on its own, exactly as ``tests/test_ui_v2.py`` does.
STYLE_BLOCK = re.compile(r"<style>(.*?)</style>", re.DOTALL)
# Every ``.chip{...}`` block -- ``.chip.ok`` and ``.chip.ev`` are qualified and do
# not match. The item-1 rule's own ``.chip`` is inside a media query and matches
# too, so :func:`base_chip_rule` picks the base one out by its first declaration.
CHIP_RULE_BLOCK = re.compile(r"\.chip\{([^}]*)\}")


def built(name: str) -> str:
    """One built page, read from ``ui/dist/``, so a failure can name it."""
    return (DIST_DIR / name).read_text(encoding="utf-8")


def stylesheet(page: str) -> str:
    """The inline stylesheet a built page carries, or ``""`` when it has none."""
    found = STYLE_BLOCK.search(page)
    return found.group(1) if found else ""


def body(page: str) -> str:
    """The markup alone, with the page's own stylesheet removed."""
    return STYLE_BLOCK.sub("", page)


def base_chip_rule(page: str) -> str:
    """The base ``.chip`` rule's declarations, or ``""`` when the page has none.

    The base rule is the one that opens ``display:inline-flex``; the item-1 rule's
    ``.chip`` opens ``white-space:normal`` and is a different rule.
    """
    for declarations in CHIP_RULE_BLOCK.findall(page):
        if "display:inline-flex" in declarations:
            return declarations
    return ""


class TheCasePageChipWrapsTests(unittest.TestCase):
    """Item 1: the case page's chip row wraps on a narrow screen."""

    def test_the_built_case_page_carries_the_rule(self):
        self.assertIn(
            CHIP_RULE,
            built("case-00207.html"),
            "ui/dist/case-00207.html does not carry the item-1 chip rule",
        )

    def test_the_built_queue_chip_rule_still_does_not_wrap(self):
        """The queue's Status column draws no ``.chips`` row, so it is unchanged."""
        declarations = base_chip_rule(built("queue.html"))
        self.assertNotEqual("", declarations, "ui/dist/queue.html carries no .chip rule")
        self.assertIn(
            "white-space:nowrap",
            declarations,
            "ui/dist/queue.html's .chip rule no longer refuses to wrap",
        )


class TheAboutStatsFitTests(unittest.TestCase):
    """Item 2: the About page's three figures stack on a narrow screen."""

    def test_the_built_about_pages_carry_the_stats_s3_row(self):
        for name in ("about.html", "about.zh.html"):
            with self.subTest(page=name):
                self.assertIn(
                    'class="stats s3"',
                    built(name),
                    "ui/dist/{0} does not carry the stats s3 row".format(name),
                )

    def test_the_built_about_pages_carry_no_inline_grid(self):
        for name in ("about.html", "about.zh.html"):
            with self.subTest(page=name):
                self.assertNotIn(
                    "grid-template-columns",
                    body(built(name)),
                    "ui/dist/{0} still carries an inline grid-template-columns".format(
                        name
                    ),
                )

    def test_the_built_site_stylesheet_carries_the_s3_rules(self):
        css = stylesheet(built("about.html"))
        for rule in (S3_COLUMNS_RULE, S3_DIVIDER_RULE, S3_NARROW_RULE):
            with self.subTest(rule=rule):
                self.assertIn(
                    rule,
                    css,
                    "ui/dist/about.html's stylesheet does not carry the .stats.s3 rule",
                )


if __name__ == "__main__":
    unittest.main()
