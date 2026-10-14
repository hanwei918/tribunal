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
and shows the second going red;
``test_the_check_fails_on_a_page_carrying_a_different_version_seven_figure``
does the same for the results page's version-7 sealed figure, and
``test_the_check_fails_on_a_page_carrying_a_different_version_eight_figure``
for the results page's version-8 Ryde-samples figure.

**The text is the visible text.** Tags are removed and entities resolved before
the comparison, so the row is a sentence a reader reads and not a fragment of
markup; and the unit a figure is written with is the page's, which is why the
figures themselves are bare numbers where the two languages write the unit
differently (``585 s`` in English, ``585 \u79d2`` in Chinese).

**No model call.** ``ui.site.figures`` reads committed runs and frozen keys, the
same readings ``eval.v6_runs --report``, ``eval.business_value --report``,
``eval.func_sets --report`` and ``eval.fairness --report`` make, and
``tests/test_readme_figures.py`` recomputes the same sealed and held-out figures
from the same places.

**The version-7 pages.** Ryde's own Dispute Resolution Policy v2.1 was adopted
as policy version 7 on 2026-10-13, and ``ui.site.figures`` reads its three sets
-- the fourth sealed set, Ryde's own two samples and the development set -- from
their committed runs. The front page, the results page and the about page's
timeline state those figures, and the version-6 figures they sit beside are
labelled as version 6's: two further checks hold that block, one that every page
stating a version-7 figure is a page bound to it here, and one that the
sentences saying which version a block belongs to are present in both languages.
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

from tests import portability  # noqa: E402
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


def states_a_value(text: str, value: str) -> bool:
    """Whether a page states one figure's value, and not a piece of another's.

    ``1/2`` sits inside ``21/24``, so a bare containment test would read a page
    that states the second as stating the first. A digit or a decimal point is
    what can join two values, so neither may touch the value on either side.
    """
    return (
        re.search(r"(?<![0-9.])" + re.escape(value) + r"(?![0-9])", text) is not None
    )


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
    ("index.zh.html", "2.7 \u5206\u949f", ("median_wall_minutes",)),
    ("index.zh.html", "$0.058", ("median_cost_dollars",)),
    ("index.zh.html", "0.0579 USD", ("median_cost_usd",)),
    ("index.zh.html", "74%", ("decided_share",)),
    ("index.zh.html", "112 / 151", ("decided_automatically", "cases_total")),
    (
        "index.zh.html",
        "112 \u7531 AI \u5224 13 \u5df2\u5224\uff0c\u7b49\u4eba\u653e\u6b3e 26 \u6ca1\u5224\uff0c\u4ea4\u7ed9\u4eba",
        ("decided_automatically", "held_for_release", "no_ruling"),
    ),
    ("index.zh.html", "26 /151", ("no_ruling", "cases_total")),
    ("index.zh.html", "136 /141\uff1a", ("position_swap_agreed", "position_swap_total")),
    (
        "index.zh.html",
        "6 \u6b21\u653b\u51fb\uff1a5 \u4e2a\u4e0d\u53d8\uff0c1 \u4e2a\u8f6c\u4eba\u5de5",
        ("inject_total", "inject_unchanged", "inject_sent_to_a_person"),
    ),
    ("index.zh.html", "585 \u79d2", ("case_208_waiting_seconds",)),
    (
        "index.zh.html",
        "\u53f8\u673a\u83b7 SGD 6.40 / \u7f6e\u4fe1\u5ea6 0.95",
        ("case_208_driver_amount", "case_208_confidence"),
    ),
    (
        "index.zh.html",
        "\u53f8\u673a\u83b7 SGD 4.00 / \u7f6e\u4fe1\u5ea6 0.9",
        ("case_901_driver_amount", "case_901_confidence"),
    ),
    ("index.zh.html", "0 \u6b21\u6a21\u578b\u8c03\u7528", ("case_2735_model_calls",)),
    (
        "index.zh.html",
        "12/12 \u4ece\u6ca1\u89c1\u8fc7\u7684\u8003\u9898\u5168\u90e8\u5224\u5bf9 sealed-v2, Wilson 95% [75.8%, 100%]",
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
    ("results.zh.html", "\u5728 4.8 \u5206\u949f\u5185\u5b8c\u6210", ("p90_wall_minutes",)),
    ("results.zh.html", "$0.0579", ("median_cost_usd",)),
    ("results.zh.html", "112", ("decided_automatically",)),
    ("results.zh.html", "13", ("held_for_release",)),
    ("results.zh.html", "26", ("no_ruling",)),
    (
        "results.zh.html",
        "\u5b89\u5168\u7c7b 2\u3001\u6ca1\u8fc7\u68c0\u67e5 3\u3001\u610f\u89c1\u5206\u6b67 4\u3001\u6cd5\u5b98\u4f9d\u653f\u7b56\u8f6c\u4eba\u5de5 17\u3002",
        ("trigger_safety", "trigger_failed_checks", "trigger_split", "trigger_judge"),
    ),
    ("results.zh.html", "~$68", ("cost_per_1000_usd",)),
    (
        "results.zh.html",
        "151 \u4e2a\u7b2c 6 \u7248\u6848\u5b50\u5171 10.33 \u7f8e\u5143",
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
        "6 \u6b21\u653b\u51fb\uff1a5 \u6b21\u65e0\u6548\uff0c1 \u6b21\u8f6c\u7ed9\u4eba",
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
    ("how-it-works.zh.html", "7 \u9879\u8bc1\u636e", ("case_208_evidence",)),
    (
        "how-it-works.zh.html",
        "7 vs 12 \u6761\u4e3b\u5f20",
        ("case_208_rider_points", "case_208_driver_points"),
    ),
    ("how-it-works.zh.html", "19/19 \u6761\u4e3b\u5f20\u4fdd\u7559", ("case_208_claims_kept",)),
    ("how-it-works.zh.html", "\u7f6e\u4fe1\u5ea6 0.95", ("case_208_confidence",)),
    (
        "how-it-works.zh.html",
        "SGD 6.40 \u5224\u7ed9\u53f8\u673a\uff0c\u7528\u65f6 277.9 \u79d2",
        ("case_208_driver_amount", "case_208_wall_seconds"),
    ),
    (
        "how-it-works.zh.html",
        "151 \u4e2a\u6848\u5b50\u4e2d\uff1a26 \u4e2a\u4ea4\u7ed9\u4eba\uff0c13 \u4e2a\u7b49\u4eba\u7b7e\u5b57\u3002",
        ("cases_total", "no_ruling", "held_for_release"),
    ),
    ("how-it-works.zh.html", "136 \u4e2a\u7ed3\u8bba\u4e0d\u53d8", ("position_swap_agreed",)),
    ("how-it-works.zh.html", "141 \u4e2a\u6848\u5b50\u91cc", ("position_swap_total",)),
    (
        "how-it-works.zh.html",
        "\u6848\u4f8b 208\uff1a\u7b49\u4e86 585 \u79d2\uff0c\u53f8\u673a\u83b7\u8d54 6.40 \u65b0\u5143\u3002",
        ("case_208_waiting_seconds",),
    ),
    ("how-it-works.zh.html", "12/12 \u548c 21/24\u3002", ("sealed_v2_exact", "sealed_v1_exact")),
    (
        "how-it-works.zh.html",
        "\u6709\u5148\u4f8b 15/15\uff0c\u65e0 13/15",
        ("precedents_with", "precedents_without"),
    ),
    (
        "how-it-works.zh.html",
        "6 \u6b21\u653b\u51fb\u6d4b\u8bd5\uff1a0 \u4e2a\u5224\u51b3\u88ab\u6539\u53cd(5 \u4e2a\u4e0d\u53d8\uff0c1 \u4e2a\u8f6c\u4eba\u5de5)\u3002",
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
        "\u7b2c\u4e09\u5957\u9690\u85cf\u8003\u9898(sealed-v1)\u8dd1\u4e00\u6b21\uff1a21/24\u3002",
        ("sealed_v1_exact",),
    ),
    (
        "about.zh.html",
        "\u7b2c\u56db\u5957\u9690\u85cf\u8003\u9898(sealed-v2)\uff1a12/12\u3002",
        ("sealed_v2_exact",),
    ),
    # -- version 7, Ryde's own Dispute Resolution Policy v2.1 --------------
    # The three version-7 sets, each run once and never pooled: the fourth
    # sealed set, Ryde's own two samples, and the development set the team
    # tuned against. The front page's sentence carries the sealed set's figure
    # and its interval, the results page carries all three, and the about
    # page's timeline carries the sealed set's figure.
    (
        "index.html",
        "Applies Ryde's own Dispute Resolution Policy v2.1 with Ryde's answers of 2026-10-14 (policy version 8). Hidden test set, run at version 7: 30/30, Wilson 95% [88.6%, 100%].",
        ("sealed_v4_exact", "sealed_v4_interval"),
    ),
    (
        "index.zh.html",
        "\u6309 Ryde \u5b98\u65b9\u7684\u300a\u4e89\u8bae\u5904\u7406\u653f\u7b56 v2.1\u300b\u53ca Ryde 2026-10-14 \u7684\u7b54\u590d\u88c1\u51b3\uff08\u7b2c 8 \u7248\u653f\u7b56\uff09\u3002\u9690\u85cf\u9898\uff08\u5728\u7b2c 7 \u7248\u4e0a\u8dd1\uff09\uff1a30/30\uff0cWilson 95% [88.6%, 100%]\u3002",
        ("sealed_v4_exact", "sealed_v4_interval"),
    ),
    (
        "results.html",
        "30/30 right on 30 hidden cases, Wilson 95% 88.6%, 100%; written by Claude (Opus 5.5) in a fresh claude.ai chat from Ryde's v2.1 and the version-7 files; run once from freeze-2026-10-14.",
        ("sealed_v4_exact", "sealed_v4_interval"),
    ),
    (
        "results.html",
        "1/2 -- DISP-001 (route deviation) ruled exactly as Ryde states (partial refund 3.44); DISP-002 (no-show) escalated: the four drafts split 2-2 on whether eight sparse GPS fixes reach the 0.95 confidence v2.1 requires when a party carries a fraud flag.",
        ("ryde_v7_exact",),
    ),
    (
        "results.html",
        "dev-v7: 40/40, development data the team tuned against.",
        ("dev_v7_exact",),
    ),
    (
        "results.zh.html",
        "30 \u9053\u9690\u85cf\u9898\u5bf9\u4e86 30/30\uff0cWilson 95% 88.6%, 100%\uff1b\u7531 Claude\uff08Opus 5.5\uff09\u5728\u5168\u65b0\u7684 claude.ai \u5bf9\u8bdd\u4e2d\u6309 Ryde v2.1 \u4e0e\u7b2c 7 \u7248\u653f\u7b56\u51fa\u9898\uff1b\u4ece freeze-2026-10-14 \u53ea\u8dd1\u4e00\u6b21\u3002",
        ("sealed_v4_exact", "sealed_v4_interval"),
    ),
    (
        "results.zh.html",
        "Ryde \u5b98\u65b9\u6837\u4f8b 1/2\uff1aDISP-001\uff08\u7ed5\u8def\uff09\u4e0e Ryde \u7ed9\u51fa\u7684\u7b54\u6848\u4e00\u81f4\uff08\u90e8\u5206\u9000\u6b3e 3.44\uff09\uff1b",
        ("ryde_v7_exact",),
    ),
    (
        "results.zh.html",
        "\u5f00\u53d1\u96c6 40/40\uff08\u56e2\u961f\u636e\u6b64\u8c03\u8bd5\uff0c\u4e0d\u662f\u6cdb\u5316\u6210\u7ee9\uff09\u3002",
        ("dev_v7_exact",),
    ),
    (
        "about.html",
        "Version 7 frozen; the sixth hidden set (sealed-v4): 30/30.",
        ("sealed_v4_exact",),
    ),
    (
        "about.zh.html",
        "\u7b2c 7 \u7248\u51bb\u7ed3\uff1b\u7b2c\u516d\u5957\u9690\u85cf\u8003\u9898\uff08sealed-v4\uff09\uff1a30/30\u3002",
        ("sealed_v4_exact",),
    ),
    # -- version 8, v2.1 with Ryde's answers of 2026-10-14 ------------------
    # The two version-8 sets, each run once and never pooled: Ryde's own two
    # samples, keyed as Ryde's answer of 2026-10-14 leaves them, and the
    # development set the team tuned against. The results page carries both.
    (
        "results.html",
        "1/2: DISP-001 (route deviation, 4.3 km) escalated, as Ryde answered on 2026-10-14 that the 2 km limb applies; DISP-002 (no-show) escalated: the drafts did not agree on whether eight sparse GPS fixes reach the 0.95 confidence v2.1 requires when a party carries a fraud flag.",
        ("ryde_v8_exact",),
    ),
    (
        "results.html",
        "dev-v8: 39/40, development data the team tuned against.",
        ("dev_v8_exact",),
    ),
    (
        "results.zh.html",
        "Ryde \u5b98\u65b9\u6837\u4f8b 1/2\uff1aDISP-001\uff08\u7ed5\u8def 4.3 km\uff09\u8f6c\u4eba\u5de5\u2014\u2014Ryde \u4e8e 2026-10-14 \u7b54\u590d 2 km \u89c4\u5219\u9002\u7528\uff1bDISP-002\uff08\u672a\u51fa\u73b0\uff09\u8f6c\u4eba\u5de5\uff1a\u4e58\u5ba2\u5e26\u6b3a\u8bc8\u6807\u8bb0\u65f6 v2.1 \u8981\u6c42 0.95 \u7684\u7f6e\u4fe1\u5ea6\uff0c\u8349\u7a3f\u5728 8 \u4e2a\u7a00\u758f GPS \u70b9\u662f\u5426\u8db3\u591f\u4e0a\u6ca1\u6709\u8fbe\u6210\u4e00\u81f4\u3002",
        ("ryde_v8_exact",),
    ),
    (
        "results.zh.html",
        "\u5f00\u53d1\u96c6 39/40\uff08\u56e2\u961f\u636e\u6b64\u8c03\u8bd5\uff0c\u4e0d\u662f\u6cdb\u5316\u6210\u7ee9\uff09\u3002",
        ("dev_v8_exact",),
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

# The figures the version-7 pages state -- Ryde's own Dispute Resolution Policy
# v2.1, adopted 2026-10-13. A page that states one of these values and has no
# row above is a page nothing here holds to the record, which is what
# ``test_no_page_states_a_version_seven_figure_the_module_does_not_compute``
# refuses; the set of pages is computed from the pages themselves rather than
# listed, so a page that gains one of the values fails until it is bound.
VERSION_SEVEN_FIGURES: Tuple[str, ...] = (
    "sealed_v4_exact",
    "sealed_v4_interval",
    "ryde_v7_exact",
    "dev_v7_exact",
)

# The sentences that say which policy version a block of figures belongs to.
# They state no figure, so they are not rows in ``SHOWN``; they are the lines
# that stop a reader taking the version-6 figures beside them for version 7's,
# and -- on the try page, which states no figure at all -- the line that says
# which policy the browser runs against the one the submission applies.
VERSION_SENTENCES: Tuple[Tuple[str, str], ...] = (
    (
        "index.html",
        "The figures above are from version 6, the team's own policy.",
    ),
    (
        "index.zh.html",
        "\u4ee5\u4e0a\u6570\u5b57\u6765\u81ea\u7b2c 6 \u7248\uff08\u56e2\u961f\u81ea\u5b9a\u653f\u7b56\uff09\u3002",
    ),
    (
        "results.html",
        "The case pages show the version-6 development runs.",
    ),
    (
        "results.zh.html",
        "\u6848\u4f8b\u9875\u5c55\u793a\u7684\u662f\u7b2c 6 \u7248\u7684\u5f00\u53d1\u8dd1\u5206\u3002",
    ),
    (
        "how-it-works.html",
        "Since 2026-10-14 the policy is Ryde's v2.1 with Ryde's answers to the team's three questions (the 2 km limb applies, the free wait runs from the driver's arrival, no surge on the excess distance fare), written as numbered clauses (docs/notes/2026-10-14-policy-v8.md). The stages and figures on this page are from version 6 unless they say otherwise.",
    ),
    (
        "how-it-works.zh.html",
        "\u81ea 2026-10-14 \u8d77\uff0c\u653f\u7b56\u662f Ryde \u7684 v2.1 \u52a0\u4e0a Ryde \u5bf9\u56e2\u961f\u4e09\u4e2a\u95ee\u9898\u7684\u7b54\u590d\uff082 km \u89c4\u5219\u9002\u7528\uff1b\u514d\u8d39\u7b49\u5f85\u4ece\u53f8\u673a\u5230\u8fbe\u8d77\u7b97\uff1b\u8d85\u989d\u91cc\u7a0b\u8d39\u4e0d\u52a0 surge\uff09\uff0c\u6539\u5199\u4e3a\u5e26\u7f16\u53f7\u7684\u6761\u6b3e\uff08docs/notes/2026-10-14-policy-v8.md\uff09\u3002\u672c\u9875\u7684\u6d41\u7a0b\u548c\u6570\u5b57\u9664\u7279\u522b\u6ce8\u660e\u5916\uff0c\u6765\u81ea\u7b2c 6 \u7248\u3002",
    ),
    (
        "try.html",
        "This page runs the team's version-6 policy in your browser; the submission applies version 8.",
    ),
    (
        "try.zh.html",
        "\u672c\u9875\u5728\u6d4f\u89c8\u5668\u91cc\u8fd0\u884c\u7684\u662f\u56e2\u961f\u7684\u7b2c 6 \u7248\u653f\u7b56\uff1b\u63d0\u4ea4\u7684\u7cfb\u7edf\u7528\u7684\u662f\u7b2c 8 \u7248\u3002",
    ),
)


class SiteFigureTests(unittest.TestCase):
    """The pages' figures against the records they were read from."""

    @classmethod
    def setUpClass(cls) -> None:
        portability.require_the_same_libm()
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

    def test_the_pages_say_which_policy_version_they_show(self) -> None:
        """The version-6 blocks are labelled, and the policy is named.

        None of these sentences states a figure, so none is a row in ``SHOWN``.
        They are the lines that stop a reader taking the version-6 figures
        beside them for the version-7 ones, and a page that lost one would do
        exactly that. The try page states no figure either, and its line is the
        one that says which policy the browser runs against the submission's.
        """
        for page, sentence in VERSION_SENTENCES:
            with self.subTest(page=page):
                self.assertIn(sentence, self.pages[page])

    def test_no_page_states_a_version_seven_figure_the_module_does_not_compute(
        self,
    ) -> None:
        """Every page that states a version-7 figure is a page bound to it here.

        The pages are computed from the pages themselves, so a page that gains
        one of these values and no row above fails rather than passing on the
        pages that are bound. A value is looked for as a value, not as a
        fragment of another.
        """
        for name in VERSION_SEVEN_FIGURES:
            value = self.figures[name]
            bound = {page for page, _shown, names in SHOWN if name in names}
            stating = {
                page
                for page, text in self.pages.items()
                if states_a_value(text, value)
            }
            with self.subTest(figure=name):
                self.assertEqual(
                    stating,
                    bound,
                    "{0} = {1!r}: stated by {2}, bound to {3}".format(
                        name, value, sorted(stating), sorted(bound)
                    ),
                )

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

    def test_the_check_fails_on_a_page_carrying_a_different_version_seven_figure(
        self,
    ) -> None:
        """The control: ``results.html``'s sealed-v4 figure, moved, is reported.

        The row used is the results page's sealed-v4 one, so the line the report
        names is that row. The figure is moved in the page and then in the
        record, one after the other, and each reddens one of the two assertions
        ``assert_shows`` makes.
        """
        shown = (
            "30/30 right on 30 hidden cases, Wilson 95% 88.6%, 100%; written by "
            "Claude (Opus 5.5) in a fresh claude.ai chat from Ryde's v2.1 and the "
            "version-7 files; run once from freeze-2026-10-14."
        )
        names = ("sealed_v4_exact", "sealed_v4_interval")
        page = self.pages["results.html"]
        moved = page.replace(
            "30/30 right on 30 hidden cases", "29/30 right on 30 hidden cases"
        )
        self.assertNotEqual(page, moved, "the fixture did not move the figure")
        with self.assertRaises(AssertionError):
            self.assert_shows(moved, "results.html", shown, names)
        self.figures["sealed_v4_exact"] = "29/30"
        try:
            with self.assertRaises(AssertionError):
                self.assert_shows(page, "results.html", shown, names)
        finally:
            self.figures["sealed_v4_exact"] = figures.named("sealed_v4_exact")

    def test_the_check_fails_on_a_page_carrying_a_different_version_eight_figure(
        self,
    ) -> None:
        """The control: ``results.html``'s ryde-v8 figure, moved, is reported.

        The row used is the results page's version-8 Ryde-samples one, so the
        line the report names is that row. The figure is moved in the page and
        then in the record, one after the other, and each reddens one of the
        two assertions ``assert_shows`` makes.
        """
        shown = (
            "1/2: DISP-001 (route deviation, 4.3 km) escalated, as Ryde answered "
            "on 2026-10-14 that the 2 km limb applies; DISP-002 (no-show) "
            "escalated: the drafts did not agree on whether eight sparse GPS "
            "fixes reach the 0.95 confidence v2.1 requires when a party carries "
            "a fraud flag."
        )
        names = ("ryde_v8_exact",)
        page = self.pages["results.html"]
        moved = page.replace(
            "1/2: DISP-001 (route deviation, 4.3 km)",
            "1/3: DISP-001 (route deviation, 4.3 km)",
        )
        self.assertNotEqual(page, moved, "the fixture did not move the figure")
        with self.assertRaises(AssertionError):
            self.assert_shows(moved, "results.html", shown, names)
        self.figures["ryde_v8_exact"] = "1/3"
        try:
            with self.assertRaises(AssertionError):
                self.assert_shows(page, "results.html", shown, names)
        finally:
            self.figures["ryde_v8_exact"] = figures.named("ryde_v8_exact")


if __name__ == "__main__":
    unittest.main()
