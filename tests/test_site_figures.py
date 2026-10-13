"""Every figure the product site states, bound to the record it was read from.

The policy owner's pages state figures, and ``ui/site/figures.py`` recomputes
each one from the committed runs. This module is the other half: it holds every
figure to the page that shows it, in both languages, so a page that drifts away
from the record fails here rather than misleading a reader.

**How a figure is bound.** Each row names a page, the text the page shows, and
the figures that text carries. Two assertions are made, and they fail in opposite
directions:

* the page's visible text contains the text the row names -- so a page whose
  figure moved fails;
* that text contains each named figure's own value -- so a figure whose record
  moved fails.

The second is what makes this a check rather than a restatement:
``test_the_check_fails_on_a_page_carrying_a_different_figure`` moves one figure
in one page and shows the first assertion going red, and moves it in the record
and shows the second going red.

**The text is the visible text.** Tags are removed and entities resolved before
the comparison, so the row is a sentence a reader reads and not a fragment of
markup; and the unit a figure is written with is the page's, which is why the
figures themselves are bare numbers where the two languages write the unit
differently (``585 s`` in English, ``585 秒`` in Chinese).

**No model call.** ``ui.site.figures`` reads committed runs and frozen keys, the
same readings ``eval.v6_runs --report``, ``eval.business_value --report``,
``eval.func_sets --report`` and ``eval.fairness --report`` make, and
``tests/test_readme_figures.py`` recomputes the same sealed and held-out figures
from the same places.
"""

from __future__ import annotations

import html
import re
import sys
import unittest
from pathlib import Path
from typing import Dict, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.site import build as site  # noqa: E402
from ui.site import figures  # noqa: E402

# A style or script block, and any other tag. Removed before the comparison, so
# a row is compared against what a reader sees.
BLOCK_RE = re.compile(r"<(style|script)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")


def visible_text(markup: str) -> str:
    """A page as a reader meets it: no markup, entities resolved, runs collapsed."""
    text = BLOCK_RE.sub(" ", markup)
    text = TAG_RE.sub(" ", text)
    return " ".join(html.unescape(text).split())


# ``(page, the text the page shows, the figures that text carries)``.
#
# One row per place a figure is stated. The pages that state none -- ``try``,
# ``safety``, ``developers``, ``docs``, ``why`` and ``architecture`` -- are
# absent, and ``test_the_table_covers_the_pages_and_the_figures`` is what says
# the set of pages here is the set that states a figure.
SHOWN: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    # -- the front page ---------------------------------------------------
    ("index.html", "160.4 s; p90 286.9 s.", ("median_wall_seconds", "p90_wall_seconds")),
    ("index.html", "2.7 min", ("median_wall_minutes",)),
    ("index.html", "$0.058", ("median_cost_dollars",)),
    ("index.html", "0.0579 USD", ("median_cost_usd",)),
    ("index.html", "74%", ("decided_share",)),
    ("index.html", "112 / 151", ("decided_automatically", "cases_total")),
    (
        "index.html",
        "112 ruled by the AI 13 ruled, payout waits for a person "
        "26 no ruling: a person decides",
        ("decided_automatically", "held_for_release", "no_ruling"),
    ),
    ("index.html", "26 /151 disputes got no AI ruling", ("no_ruling", "cases_total")),
    (
        "index.html",
        "136 /141:",
        ("position_swap_agreed", "position_swap_total"),
    ),
    (
        "index.html",
        "6 tries: 5 unchanged, 1 sent to a person",
        ("inject_total", "inject_unchanged", "inject_sent_to_a_person"),
    ),
    (
        "index.html",
        "Case 208: 7 points for the rider, 12 for the driver.",
        ("case_208_rider_points", "case_208_driver_points"),
    ),
    ("index.html", "19 of 19 points passed", ("case_208_claims",)),
    ("index.html", "585 s", ("case_208_waiting_seconds",)),
    ("index.html", "SGD 6.40", ("case_208_driver_amount",)),
    ("index.html", "conf. 0.95", ("case_208_confidence",)),
    (
        "index.html",
        "Driver paid SGD 4.00 / conf. 0.9",
        ("case_901_driver_amount", "case_901_confidence"),
    ),
    ("index.html", "0 model calls", ("case_2735_model_calls",)),
    (
        "index.html",
        "12/12 right on test cases it had never seen sealed-v2, "
        "Wilson 95% [75.8%, 100%]",
        ("sealed_v2_exact", "sealed_v2_interval"),
    ),
    # -- the front page, in Chinese ---------------------------------------
    ("index.zh.html", "160.4 s; p90 286.9 s.", ("median_wall_seconds", "p90_wall_seconds")),
    ("index.zh.html", "2.7 分钟", ("median_wall_minutes",)),
    ("index.zh.html", "$0.058", ("median_cost_dollars",)),
    ("index.zh.html", "0.0579 USD", ("median_cost_usd",)),
    ("index.zh.html", "74%", ("decided_share",)),
    ("index.zh.html", "112 / 151", ("decided_automatically", "cases_total")),
    (
        "index.zh.html",
        "112 由 AI 判 13 已判，等人放款 26 没判，交给人",
        ("decided_automatically", "held_for_release", "no_ruling"),
    ),
    ("index.zh.html", "26 /151", ("no_ruling", "cases_total")),
    ("index.zh.html", "136 /141：", ("position_swap_agreed", "position_swap_total")),
    (
        "index.zh.html",
        "6 次攻击：5 个不变，1 个转人工",
        ("inject_total", "inject_unchanged", "inject_sent_to_a_person"),
    ),
    ("index.zh.html", "585 秒", ("case_208_waiting_seconds",)),
    (
        "index.zh.html",
        "司机获 SGD 6.40 / 置信度 0.95",
        ("case_208_driver_amount", "case_208_confidence"),
    ),
    (
        "index.zh.html",
        "司机获 SGD 4.00 / 置信度 0.9",
        ("case_901_driver_amount", "case_901_confidence"),
    ),
    ("index.zh.html", "0 次模型调用", ("case_2735_model_calls",)),
    (
        "index.zh.html",
        "12/12 从没见过的考题全部判对 sealed-v2, Wilson 95% [75.8%, 100%]",
        ("sealed_v2_exact", "sealed_v2_interval"),
    ),
    # -- results ----------------------------------------------------------
    ("results.html", "160.4 s", ("median_wall_seconds",)),
    ("results.html", "within 4.8 minutes", ("p90_wall_minutes",)),
    ("results.html", "$0.0579", ("median_cost_usd",)),
    ("results.html", "112", ("decided_automatically",)),
    ("results.html", "13", ("held_for_release",)),
    ("results.html", "26", ("no_ruling",)),
    (
        "results.html",
        "Safety 2, failed checks 3, split decisions 4, "
        "judge escalated under the policy 17.",
        ("trigger_safety", "trigger_failed_checks", "trigger_split", "trigger_judge"),
    ),
    ("results.html", "~$68", ("cost_per_1000_usd",)),
    ("results.html", "10.33 USD over the 151 version-6 cases", ("cost_sum_usd", "cases_total")),
    ("results.html", "12/12", ("sealed_v2_exact",)),
    ("results.html", "21/24", ("sealed_v1_exact",)),
    ("results.html", "20/24", ("sealed_v1_imported",)),
    ("results.html", "18/20", ("wild_v2_exact",)),
    ("results.html", "136/141", ("position_swap_agreed", "position_swap_total")),
    ("results.html", "0.088", ("calibration_error",)),
    (
        "results.html",
        "6 attacks: 5 had no effect, 1 was sent to a person",
        ("inject_total", "inject_unchanged", "inject_sent_to_a_person"),
    ),
    ("results.html", "115/120", ("dev_v2_ext_exact",)),
    ("results.html", "Wilson 90.6-98.2%", ("dev_v2_ext_interval",)),
    ("results.html", "16/20 / 16/17", ("dev_v2_ext_precision", "dev_v2_ext_recall")),
    ("results.html", "26/29", ("corpus_v6_exact",)),
    ("results.html", "15/15 / 13/15", ("precedents_with", "precedents_without")),
    # -- results, in Chinese ----------------------------------------------
    ("results.zh.html", "160.4 s", ("median_wall_seconds",)),
    ("results.zh.html", "在 4.8 分钟内完成", ("p90_wall_minutes",)),
    ("results.zh.html", "$0.0579", ("median_cost_usd",)),
    ("results.zh.html", "112", ("decided_automatically",)),
    ("results.zh.html", "13", ("held_for_release",)),
    ("results.zh.html", "26", ("no_ruling",)),
    (
        "results.zh.html",
        "安全类 2、没过检查 3、意见分歧 4、法官依政策转人工 17。",
        ("trigger_safety", "trigger_failed_checks", "trigger_split", "trigger_judge"),
    ),
    ("results.zh.html", "~$68", ("cost_per_1000_usd",)),
    (
        "results.zh.html",
        "151 个第 6 版案子共 10.33 美元",
        ("cost_sum_usd", "cases_total"),
    ),
    ("results.zh.html", "12/12", ("sealed_v2_exact",)),
    ("results.zh.html", "21/24", ("sealed_v1_exact",)),
    ("results.zh.html", "20/24", ("sealed_v1_imported",)),
    ("results.zh.html", "18/20", ("wild_v2_exact",)),
    ("results.zh.html", "136/141", ("position_swap_agreed", "position_swap_total")),
    ("results.zh.html", "0.088", ("calibration_error",)),
    (
        "results.zh.html",
        "6 次攻击：5 次无效，1 次转给人",
        ("inject_total", "inject_unchanged", "inject_sent_to_a_person"),
    ),
    ("results.zh.html", "115/120", ("dev_v2_ext_exact",)),
    ("results.zh.html", "Wilson 90.6-98.2%", ("dev_v2_ext_interval",)),
    ("results.zh.html", "16/20 / 16/17", ("dev_v2_ext_precision", "dev_v2_ext_recall")),
    ("results.zh.html", "26/29", ("corpus_v6_exact",)),
    ("results.zh.html", "15/15 / 13/15", ("precedents_with", "precedents_without")),
    # -- how it works -----------------------------------------------------
    ("how-it-works.html", "7 evidence items", ("case_208_evidence",)),
    (
        "how-it-works.html",
        "7 vs 12 claims, rider vs driver",
        ("case_208_rider_points", "case_208_driver_points"),
    ),
    ("how-it-works.html", "19/19 claims kept", ("case_208_claims_kept",)),
    ("how-it-works.html", "conf. 0.95", ("case_208_confidence",)),
    (
        "how-it-works.html",
        "SGD 6.40 to the driver, 277.9 s",
        ("case_208_driver_amount", "case_208_wall_seconds"),
    ),
    (
        "how-it-works.html",
        "Of 151 cases: 26 went to a person, 13 waited for sign-off.",
        ("cases_total", "no_ruling", "held_for_release"),
    ),
    ("how-it-works.html", "136 of 141", ("position_swap_agreed", "position_swap_total")),
    (
        "how-it-works.html",
        "Case 208: 585 s of waiting, driver paid SGD 6.40.",
        ("case_208_waiting_seconds", "case_208_driver_amount"),
    ),
    ("how-it-works.html", "Hidden tests: 12/12 and 21/24.", ("sealed_v2_exact", "sealed_v1_exact")),
    (
        "how-it-works.html",
        "15/15 with, 13/15 without",
        ("precedents_with", "precedents_without"),
    ),
    (
        "how-it-works.html",
        "6 attack tests: 0 rulings flipped (5 unchanged, 1 sent to a person).",
        ("inject_flipped", "inject_unchanged", "inject_sent_to_a_person"),
    ),
    # -- how it works, in Chinese -----------------------------------------
    ("how-it-works.zh.html", "7 项证据", ("case_208_evidence",)),
    (
        "how-it-works.zh.html",
        "7 vs 12 条主张",
        ("case_208_rider_points", "case_208_driver_points"),
    ),
    ("how-it-works.zh.html", "19/19 条主张保留", ("case_208_claims_kept",)),
    ("how-it-works.zh.html", "置信度 0.95", ("case_208_confidence",)),
    (
        "how-it-works.zh.html",
        "SGD 6.40 判给司机，用时 277.9 秒",
        ("case_208_driver_amount", "case_208_wall_seconds"),
    ),
    (
        "how-it-works.zh.html",
        "151 个案子中：26 个交给人，13 个等人签字。",
        ("cases_total", "no_ruling", "held_for_release"),
    ),
    ("how-it-works.zh.html", "136 个结论不变", ("position_swap_agreed",)),
    ("how-it-works.zh.html", "141 个案子里", ("position_swap_total",)),
    (
        "how-it-works.zh.html",
        "案例 208：等了 585 秒，司机获赔 6.40 新元。",
        ("case_208_waiting_seconds",),
    ),
    ("how-it-works.zh.html", "12/12 和 21/24。", ("sealed_v2_exact", "sealed_v1_exact")),
    (
        "how-it-works.zh.html",
        "有先例 15/15，无 13/15",
        ("precedents_with", "precedents_without"),
    ),
    (
        "how-it-works.zh.html",
        "6 次攻击测试：0 个判决被改反(5 个不变，1 个转人工)。",
        ("inject_flipped", "inject_unchanged", "inject_sent_to_a_person"),
    ),
    # -- about ------------------------------------------------------------
    (
        "about.html",
        "the third hidden set (sealed-v1) run once: 21/24.",
        ("sealed_v1_exact",),
    ),
    (
        "about.html",
        "the fourth hidden set (sealed-v2): 12/12.",
        ("sealed_v2_exact",),
    ),
    (
        "about.zh.html",
        "第三套隐藏考题(sealed-v1)跑一次：21/24。",
        ("sealed_v1_exact",),
    ),
    (
        "about.zh.html",
        "第四套隐藏考题(sealed-v2)：12/12。",
        ("sealed_v2_exact",),
    ),
)

# The pages this table names. It is asserted to be exactly the pages that state
# a run-derived figure, so a page that gains one and is not added here fails.
PAGES: Tuple[str, ...] = (
    "index.html",
    "index.zh.html",
    "results.html",
    "results.zh.html",
    "how-it-works.html",
    "how-it-works.zh.html",
    "about.html",
    "about.zh.html",
)


class SiteFigureTests(unittest.TestCase):
    """The pages' figures against the records they were read from."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.pages = {path.name: visible_text(text) for path, text in site.pages()}
        cls.figures = figures.page_figures()

    def assert_shows(
        self, text: str, page: str, shown: str, names: Tuple[str, ...]
    ) -> None:
        """The page shows ``shown``, and ``shown`` carries every named figure."""
        self.assertIn(
            shown,
            text,
            "{0} does not show {1!r}".format(page, shown),
        )
        for name in names:
            self.assertIn(
                self.figures[name],
                shown,
                "{0} shows {1!r}, which does not carry {2} = {3!r}".format(
                    page, shown, name, self.figures[name]
                ),
            )

    def test_each_figure_appears_on_every_page_that_shows_it(self) -> None:
        for page, shown, names in SHOWN:
            with self.subTest(page=page, shown=shown):
                self.assert_shows(self.pages[page], page, shown, names)

    def test_the_table_covers_the_pages_and_the_figures(self) -> None:
        """No figure is read and unbound, and no page that states one is absent."""
        stated = {name for _page, _shown, names in SHOWN for name in names}
        self.assertEqual(
            set(self.figures),
            stated,
            "the table and the module disagree about which figures there are: "
            "unbound {0}, unknown {1}".format(
                sorted(set(self.figures) - stated), sorted(stated - set(self.figures))
            ),
        )
        self.assertEqual(set(PAGES), {page for page, _shown, _names in SHOWN})
        for page in PAGES:
            self.assertIn(page, self.pages, "{0} is not a page this builder writes".format(page))

    def test_every_figure_is_a_figure_the_pages_show(self) -> None:
        """A figure is a short string, not a paragraph that would match anything."""
        for name, value in sorted(self.figures.items()):
            with self.subTest(figure=name):
                self.assertTrue(value, "{0} is empty".format(name))
                self.assertLess(len(value), 24, "{0} is too long to be a figure".format(name))

    def test_the_check_fails_on_a_page_carrying_a_different_figure(self) -> None:
        """The control: both assertions are ones that can fail.

        Moving the figure in the page reddens the first assertion; moving it in
        the record reddens the second. ``index.html``'s ``160.4 s; p90 286.9 s.``
        is the row used, so the line the report names is this one.
        """
        shown = "160.4 s; p90 286.9 s."
        names = ("median_wall_seconds", "p90_wall_seconds")
        page = self.pages["index.html"]
        moved_page = page.replace("160.4 s", "160.5 s")
        self.assertNotEqual(page, moved_page, "the fixture did not move the figure")
        with self.assertRaises(AssertionError):
            self.assert_shows(moved_page, "index.html", shown, names)
        with self.assertRaises(AssertionError):
            self.assert_shows(page, "index.html", "160.5 s; p90 286.9 s.", names)
        # The record's own value is what the second assertion compares against,
        # so a record that moved is what makes a page fail rather than a page
        # that moved.
        self.figures["median_wall_seconds"] = "160.5"
        try:
            with self.assertRaises(AssertionError):
                self.assert_shows(page, "index.html", shown, names)
        finally:
            self.figures["median_wall_seconds"] = figures.named("median_wall_seconds")


if __name__ == "__main__":
    unittest.main()
