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
for the results page's version-8 Ryde-samples figure, and
``test_the_check_fails_on_a_page_carrying_a_different_ryde_sample_figure`` for
the cases page's new version-8 section.

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

**The organisers' samples on the cases page.** Version 8 is v2.1 with Ryde's
answers of 2026-10-14, and the cases page opens with a section about Ryde's own
two samples decided under it. Its figures come from the version-8 briefs of the
two cases, the committed ``ryde-v8`` run's own transcript for the judge's four
drafts, and ``policy/v8/general.json`` for the thresholds the safety page
states; the front page links to the section by its id, and the safety page's
version-6 sign-off is followed by version 8's own. The cases page and the safety
page therefore join the pages this table covers.
"""

from __future__ import annotations

import html
import json
import re
import sys
import unittest
from pathlib import Path
from typing import Dict, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets  # noqa: E402
from tests import portability  # noqa: E402
from tribunal import pipeline as pipeline_module  # noqa: E402
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
# ``developers``, ``docs``, ``why`` and ``architecture`` -- are absent, and
# ``test_the_table_covers_the_pages_and_the_figures`` is what says the set of
# pages here is the set that states a figure.
SHOWN: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    # ``(page, the text the page shows, the figures that text carries)``.
    #
    # One row per place a figure is stated. The pages that state none -- ``try``,
    # ``developers``, ``docs``, ``why`` and ``architecture`` -- are absent, and
    # ``test_the_table_covers_the_pages_and_the_figures`` is what says the set of
    # pages here is the set that states a figure.
    (
        "index.html",
        "153.1 s; p90 299.4 s (dev-v8).",
        (
            "v8_median_seconds",
            "v8_p90_seconds",
        ),
    ),
    (
        "index.html",
        "2.6 min",
        (
            "v8_median_minutes",
        ),
    ),
    (
        "index.html",
        "$0.039",
        (
            "v8_median_cost_dollars",
        ),
    ),
    (
        "index.html",
        "0.0390 USD (dev-v8).",
        (
            "v8_median_cost_usd",
        ),
    ),
    (
        "index.html",
        "70%",
        (
            "v8_decided_share",
        ),
    ),
    (
        "index.html",
        "28 of 40 (dev-v8).",
        (
            "v8_decided",
        ),
    ),
    (
        "index.html",
        "30/30 on the sealed set sealed-v4, run once at version 7, Wilson 95% [88.6%, 100%]; written by the team's own development assistant, so not an independent benchmark.",
        (
            "sealed_v4_exact",
            "sealed_v4_interval",
        ),
    ),
    (
        "index.html",
        "6 tries: 5 unchanged, 1 sent to a person",
        (
            "inject_total",
            "inject_unchanged",
            "inject_sent_to_a_person",
        ),
    ),
    (
        "index.html",
        "Typically decided in under 3 minutes, for about 4 cents.",
        (
            "v8_median_cost_cents",
        ),
    ),
    (
        "index.html",
        "a median of 153.1 s is slow for a chat reply",
        (
            "v8_median_seconds",
        ),
    ),
    (
        "index.html",
        "Case 5051: 3 points for the rider, 8 for the driver.",
        (
            "case5051_rider_points",
            "case5051_driver_points",
        ),
    ),
    (
        "index.html",
        "Case 5051: 1 of 11 points thrown out by code before the judge saw them.",
        (
            "case5051_dropped",
            "case5051_claims",
        ),
    ),
    (
        "index.html",
        "SGD 3.44 = 4.30 km x 0.80, worked out by code for Ryde's DISP-001 and handed to the person who decides.",
        (
            "ryde902_excess_sgd",
            "ryde902_deviation_km",
            "ryde902_rate_sgd",
        ),
    ),
    (
        "index.html",
        "33 of 34:",
        (
            "v8_swap",
        ),
    ),
    (
        "index.html",
        "28 ruled by the AI 12 to a person",
        (
            "v8_decided_count",
            "v8_to_person",
        ),
    ),
    (
        "index.html",
        "12 /40 28 of 40 ruled by the AI; 12 to a person -- 5 stopped by a v2.1 rule before the judge (2 km, over SGD 50, safety), 6 the panel sent on, 1 without a majority.",
        (
            "v8_to_person",
            "v8_cases",
            "v8_decided",
            "v8_gate_total",
            "v8_route_limit_km",
            "v8_human_above",
            "v8_panel_escalated",
            "v8_no_majority",
        ),
    ),
    (
        "index.html",
        "Over SGD 50, a safety flag, or a route deviation over 2 km? A person decides.",
        (
            "v8_human_above",
            "v8_route_limit_km",
        ),
    ),
    (
        "index.html",
        "Ryde's own sample: the trip ran 4.30 km past the recommended route, over the 2 km an AI may rule on. A person decides, as Ryde answered. Over 2 km: escalated, as Ryde answered",
        (
            "ryde902_deviation_km",
            "v8_route_limit_km",
        ),
    ),
    (
        "index.html",
        "Fee stands: driver paid SGD 5.00",
        (
            "case5051_amount",
        ),
    ),
    (
        "index.html",
        "All 42 version-8 cases",
        (
            "v8_case_pages",
        ),
    ),
    (
        "index.zh.html",
        "153.1 s\uff1bp90 299.4 s\uff08dev-v8\uff09\u3002",
        (
            "v8_median_seconds",
            "v8_p90_seconds",
        ),
    ),
    (
        "index.zh.html",
        "2.6 \u5206\u949f",
        (
            "v8_median_minutes",
        ),
    ),
    (
        "index.zh.html",
        "$0.039",
        (
            "v8_median_cost_dollars",
        ),
    ),
    (
        "index.zh.html",
        "0.0390 USD\uff08dev-v8\uff09\u3002",
        (
            "v8_median_cost_usd",
        ),
    ),
    (
        "index.zh.html",
        "70%",
        (
            "v8_decided_share",
        ),
    ),
    (
        "index.zh.html",
        "40 \u4e2a\u4e2d 28 \u4e2a\uff08dev-v8\uff09\u3002",
        (
            "v8_decided_count",
            "v8_cases",
        ),
    ),
    (
        "index.zh.html",
        "30/30 \u5c01\u5b58\u96c6\u4e0a\u5168\u90e8\u5224\u5bf9 sealed-v4\uff0c\u5728\u7b2c 7 \u7248\u4e0a\u53ea\u8dd1\u8fc7\u4e00\u6b21\uff0cWilson 95% [88.6%, 100%]\uff1b\u7531\u56e2\u961f\u81ea\u5df1\u7684\u5f00\u53d1\u52a9\u624b\u51fa\u9898\uff0c\u4e0d\u662f\u72ec\u7acb\u57fa\u51c6\u3002",
        (
            "sealed_v4_exact",
            "sealed_v4_interval",
        ),
    ),
    (
        "index.zh.html",
        "6 \u6b21\u653b\u51fb\uff1a5 \u4e2a\u4e0d\u53d8\uff0c1 \u4e2a\u8f6c\u4eba\u5de5",
        (
            "inject_total",
            "inject_unchanged",
            "inject_sent_to_a_person",
        ),
    ),
    (
        "index.zh.html",
        "\u4e00\u822c\u4e0d\u5230 3 \u5206\u949f\uff0c\u6210\u672c\u7ea6 4 \u7f8e\u5206\u3002",
        (
            "v8_median_cost_cents_zh",
        ),
    ),
    (
        "index.zh.html",
        "\u4e2d\u4f4d 153.1 s \u5bf9\u804a\u5929\u56de\u590d\u6765\u8bf4\u504f\u6162",
        (
            "v8_median_seconds",
        ),
    ),
    (
        "index.zh.html",
        "\u6848\u4f8b 5051\uff1a\u4e58\u5ba2\u65b9 3 \u70b9\uff0c\u53f8\u673a\u65b9 8 \u70b9\u3002",
        (
            "case5051_rider_points",
            "case5051_driver_points",
        ),
    ),
    (
        "index.zh.html",
        "\u6848\u4f8b 5051\uff1a11 \u70b9\u91cc\u6709 1 \u70b9\u88ab\u4ee3\u7801\u5728\u6cd5\u5b98\u770b\u5230\u4e4b\u524d\u6254\u6389\u3002",
        (
            "case5051_dropped",
            "case5051_claims",
        ),
    ),
    (
        "index.zh.html",
        "= 4.30 km x 0.80\uff0c\u7531\u4ee3\u7801\u4e3a Ryde \u7684 DISP-001 \u7b97\u51fa\uff0c\u4ea4\u7ed9\u8d1f\u8d23\u51b3\u5b9a\u7684\u4eba\u3002",
        (
            "ryde902_deviation_km",
            "ryde902_rate_sgd",
        ),
    ),
    (
        "index.zh.html",
        "33 /34",
        (
            "v8_swap_agreed",
            "v8_swap_total",
        ),
    ),
    (
        "index.zh.html",
        "28 \u7531 AI \u5224 12 \u4ea4\u7ed9\u4eba",
        (
            "v8_decided_count",
            "v8_to_person",
        ),
    ),
    (
        "index.zh.html",
        "12 /40 40 \u4e2a\u91cc 28 \u4e2a\u7531 AI \u5224\uff1b12 \u4e2a\u4ea4\u7ed9\u4eba\u2014\u20145 \u4e2a\u88ab v2.1 \u7684\u89c4\u5219\u5728\u6cd5\u5b98\u4e4b\u524d\u62e6\u4e0b\uff082 \u516c\u91cc\u3001\u8d85\u8fc7 50 \u65b0\u5143\u3001\u5b89\u5168\uff09\uff0c6 \u4e2a\u7531\u5408\u8bae\u5ead\u8f6c\u51fa\uff0c1 \u4e2a\u6ca1\u6709\u5f62\u6210\u591a\u6570\u3002",
        (
            "v8_to_person",
            "v8_cases",
            "v8_decided_count",
            "v8_gate_total",
            "v8_route_limit_km",
            "v8_human_above",
            "v8_panel_escalated",
            "v8_no_majority",
        ),
    ),
    (
        "index.zh.html",
        "\u8d85\u8fc7 50 \u65b0\u5143\u3001\u6709\u5b89\u5168\u6807\u8bb0\u3001\u6216\u7ed5\u8def\u8d85\u8fc7 2 \u516c\u91cc\uff0c\u90fd\u7531\u4eba\u51b3\u5b9a\u3002",
        (
            "v8_human_above",
            "v8_route_limit_km",
        ),
    ),
    (
        "index.zh.html",
        "Ryde \u81ea\u5df1\u7684\u6837\u4f8b\uff1a\u5b9e\u9645\u6bd4\u63a8\u8350\u8def\u7ebf\u591a\u8d70\u4e86 4.30 km\uff0c\u8d85\u8fc7 AI \u53ef\u4ee5\u88c1\u51b3\u7684 2 km\u3002\u6309 Ryde \u7684\u7b54\u590d\uff0c\u8f6c\u4eba\u5de5\u3002 \u8d85\u8fc7 2 km\uff1a\u8f6c\u4eba\u5de5\uff0c\u4e0e Ryde \u7b54\u590d\u4e00\u81f4",
        (
            "ryde902_deviation_km",
            "v8_route_limit_km",
        ),
    ),
    (
        "index.zh.html",
        "\u8d39\u7528\u6210\u7acb\uff1a\u53f8\u673a\u83b7 SGD 5.00",
        (
            "case5051_amount",
        ),
    ),
    (
        "index.zh.html",
        "\u5168\u90e8 42 \u9053\u7b2c 8 \u7248\u6848\u4ef6",
        (
            "v8_case_pages",
        ),
    ),
    (
        "results.html",
        "160.4 s",
        (
            "median_wall_seconds",
        ),
    ),
    (
        "results.html",
        "within 4.8 minutes",
        (
            "p90_wall_minutes",
        ),
    ),
    (
        "results.html",
        "$0.0579",
        (
            "median_cost_usd",
        ),
    ),
    (
        "results.html",
        "112",
        (
            "decided_automatically",
        ),
    ),
    (
        "results.html",
        "13",
        (
            "held_for_release",
        ),
    ),
    (
        "results.html",
        "26",
        (
            "no_ruling",
        ),
    ),
    (
        "results.html",
        "Safety 2, failed checks 3, split decisions 4, judge escalated under the policy 17.",
        (
            "trigger_safety",
            "trigger_failed_checks",
            "trigger_split",
            "trigger_judge",
        ),
    ),
    (
        "results.html",
        "~$68",
        (
            "cost_per_1000_usd",
        ),
    ),
    (
        "results.html",
        "10.33 USD over the 151 version-6 cases",
        (
            "cost_sum_usd",
            "cases_total",
        ),
    ),
    (
        "results.html",
        "12/12",
        (
            "sealed_v2_exact",
        ),
    ),
    (
        "results.html",
        "21/24",
        (
            "sealed_v1_exact",
        ),
    ),
    (
        "results.html",
        "20/24",
        (
            "sealed_v1_imported",
        ),
    ),
    (
        "results.html",
        "18/20",
        (
            "wild_v2_exact",
        ),
    ),
    (
        "results.html",
        "136/141",
        (
            "position_swap_agreed",
            "position_swap_total",
        ),
    ),
    (
        "results.html",
        "0.088",
        (
            "calibration_error",
        ),
    ),
    (
        "results.html",
        "6 attacks: 5 had no effect, 1 was sent to a person",
        (
            "inject_total",
            "inject_unchanged",
            "inject_sent_to_a_person",
        ),
    ),
    (
        "results.html",
        "115/120",
        (
            "dev_v2_ext_exact",
        ),
    ),
    (
        "results.html",
        "Wilson 90.6-98.2%",
        (
            "dev_v2_ext_interval",
        ),
    ),
    (
        "results.html",
        "16/20 / 16/17",
        (
            "dev_v2_ext_precision",
            "dev_v2_ext_recall",
        ),
    ),
    (
        "results.html",
        "26/29",
        (
            "corpus_v6_exact",
        ),
    ),
    (
        "results.html",
        "15/15 / 13/15",
        (
            "precedents_with",
            "precedents_without",
        ),
    ),
    (
        "results.html",
        "2.6 min",
        (
            "v8_median_minutes",
        ),
    ),
    (
        "results.html",
        "153.1 s at the median and 299.4 s at the 90th percentile; 0.0390 USD of model cost a case (dev-v8, development data).",
        (
            "v8_median_seconds",
            "v8_p90_seconds",
            "v8_median_cost_usd",
        ),
    ),
    (
        "results.html",
        "28 of 40",
        (
            "v8_decided",
        ),
    ),
    (
        "results.html",
        "28 of 40 ruled by the AI, 70% of the set; 12 went to a person: 5 stopped by a v2.1 rule before the judge (2 km, over SGD 50, safety), 6 the panel sent on, 1 without a majority (dev-v8, development data).",
        (
            "v8_decided",
            "v8_decided_share",
            "v8_to_person",
            "v8_gate_total",
            "v8_route_limit_km",
            "v8_human_above",
            "v8_panel_escalated",
            "v8_no_majority",
        ),
    ),
    (
        "results.html",
        "33 of 34",
        (
            "v8_swap",
        ),
    ),
    (
        "results.html",
        "Expected calibration error 0.097 over 139 drafts, at the version-8 bar of 0.80 (dev-v8, development data).",
        (
            "v8_ece",
            "v8_drafts",
            "v8_confidence_between",
        ),
    ),
    # Part 98's version-8 grid states two figures the results page did not
    # carry before: the cost tile and the calibration error, each in a short
    # sentence of its own card. The long sentences the cards used to hold are
    # rows above, and they moved verbatim.
    (
        "results.html",
        "$0.039",
        (
            "v8_median_cost_dollars",
        ),
    ),
    (
        "results.html",
        "Calibration error 0.097 (lower is better).",
        (
            "v8_ece",
        ),
    ),
    # The five version-6 figures the front page's tiles used to be the only
    # place for. They left the front page with version 8's own four tiles and
    # are stated here instead, each in a block that names version 6: the poster
    # caption on the about page, the three rows at the end of the development
    # table, and the sentence that closes the panel on the hidden tests.
    (
        "results.html",
        "160.4 s; p90 286.9 s.",
        (
            "median_wall_seconds",
            "p90_wall_seconds",
        ),
    ),
    (
        "results.html",
        "$0.058",
        (
            "median_cost_dollars",
        ),
    ),
    (
        "results.html",
        "74% (112 / 151)",
        (
            "decided_share",
            "decided_automatically",
            "cases_total",
        ),
    ),
    (
        "results.html",
        "sealed-v2's 12/12 has a Wilson 95% interval of [75.8%, 100%].",
        (
            "sealed_v2_exact",
            "sealed_v2_interval",
        ),
    ),
    (
        "results.zh.html",
        "160.4 s",
        (
            "median_wall_seconds",
        ),
    ),
    (
        "results.zh.html",
        "\u5728 4.8 \u5206\u949f\u5185\u5b8c\u6210",
        (
            "p90_wall_minutes",
        ),
    ),
    (
        "results.zh.html",
        "$0.0579",
        (
            "median_cost_usd",
        ),
    ),
    (
        "results.zh.html",
        "112",
        (
            "decided_automatically",
        ),
    ),
    (
        "results.zh.html",
        "13",
        (
            "held_for_release",
        ),
    ),
    (
        "results.zh.html",
        "26",
        (
            "no_ruling",
        ),
    ),
    (
        "results.zh.html",
        "\u5b89\u5168\u7c7b 2\u3001\u6ca1\u8fc7\u68c0\u67e5 3\u3001\u610f\u89c1\u5206\u6b67 4\u3001\u6cd5\u5b98\u4f9d\u653f\u7b56\u8f6c\u4eba\u5de5 17\u3002",
        (
            "trigger_safety",
            "trigger_failed_checks",
            "trigger_split",
            "trigger_judge",
        ),
    ),
    (
        "results.zh.html",
        "~$68",
        (
            "cost_per_1000_usd",
        ),
    ),
    (
        "results.zh.html",
        "151 \u4e2a\u7b2c 6 \u7248\u6848\u5b50\u5171 10.33 \u7f8e\u5143",
        (
            "cost_sum_usd",
            "cases_total",
        ),
    ),
    (
        "results.zh.html",
        "12/12",
        (
            "sealed_v2_exact",
        ),
    ),
    (
        "results.zh.html",
        "21/24",
        (
            "sealed_v1_exact",
        ),
    ),
    (
        "results.zh.html",
        "20/24",
        (
            "sealed_v1_imported",
        ),
    ),
    (
        "results.zh.html",
        "18/20",
        (
            "wild_v2_exact",
        ),
    ),
    (
        "results.zh.html",
        "136/141",
        (
            "position_swap_agreed",
            "position_swap_total",
        ),
    ),
    (
        "results.zh.html",
        "0.088",
        (
            "calibration_error",
        ),
    ),
    (
        "results.zh.html",
        "6 \u6b21\u653b\u51fb\uff1a5 \u6b21\u65e0\u6548\uff0c1 \u6b21\u8f6c\u7ed9\u4eba",
        (
            "inject_total",
            "inject_unchanged",
            "inject_sent_to_a_person",
        ),
    ),
    (
        "results.zh.html",
        "115/120",
        (
            "dev_v2_ext_exact",
        ),
    ),
    (
        "results.zh.html",
        "Wilson 90.6-98.2%",
        (
            "dev_v2_ext_interval",
        ),
    ),
    (
        "results.zh.html",
        "16/20 / 16/17",
        (
            "dev_v2_ext_precision",
            "dev_v2_ext_recall",
        ),
    ),
    (
        "results.zh.html",
        "26/29",
        (
            "corpus_v6_exact",
        ),
    ),
    (
        "results.zh.html",
        "15/15 / 13/15",
        (
            "precedents_with",
            "precedents_without",
        ),
    ),
    (
        "results.zh.html",
        "2.6 min",
        (
            "v8_median_minutes",
        ),
    ),
    (
        "results.zh.html",
        "\u4e2d\u4f4d 153.1 s\uff0c\u7b2c 90 \u767e\u5206\u4f4d 299.4 s\uff1b\u6bcf\u6848\u6a21\u578b\u6210\u672c\u4e2d\u4f4d\u6570 0.0390 USD\uff08dev-v8\uff0c\u5f00\u53d1\u6570\u636e\uff09\u3002",
        (
            "v8_median_seconds",
            "v8_p90_seconds",
            "v8_median_cost_usd",
        ),
    ),
    (
        "results.zh.html",
        "28/40",
        (
            "v8_decided_count",
            "v8_cases",
        ),
    ),
    (
        "results.zh.html",
        "40 \u4e2a\u91cc 28 \u4e2a\u7531 AI \u5224\uff0c\u5360 70%\uff1b12 \u4e2a\u4ea4\u7ed9\u4eba\uff1a5 \u4e2a\u88ab v2.1 \u7684\u89c4\u5219\u5728\u6cd5\u5b98\u4e4b\u524d\u62e6\u4e0b\uff082 \u516c\u91cc\u3001\u8d85\u8fc7 SGD 50\u3001\u5b89\u5168\uff09\uff0c6 \u4e2a\u7531\u5408\u8bae\u5ead\u8f6c\u51fa\uff0c1 \u4e2a\u6ca1\u6709\u5f62\u6210\u591a\u6570\uff08dev-v8\uff0c\u5f00\u53d1\u6570\u636e\uff09\u3002",
        (
            "v8_decided_count",
            "v8_cases",
            "v8_decided_share",
            "v8_to_person",
            "v8_gate_total",
            "v8_route_limit_km",
            "v8_human_above",
            "v8_panel_escalated",
            "v8_no_majority",
        ),
    ),
    (
        "results.zh.html",
        "33/34",
        (
            "v8_swap_agreed",
            "v8_swap_total",
        ),
    ),
    (
        "results.zh.html",
        "\u671f\u671b\u6821\u51c6\u8bef\u5dee 0.097\uff0c\u57fa\u4e8e 139 \u4efd\u8349\u7a3f\uff0c\u6309\u7b2c 8 \u7248\u7684 0.80 \u4e0b\u9650\u5212\u5206\uff08dev-v8\uff0c\u5f00\u53d1\u6570\u636e\uff09\u3002",
        (
            "v8_ece",
            "v8_drafts",
            "v8_confidence_between",
        ),
    ),
    (
        "results.zh.html",
        "$0.039",
        (
            "v8_median_cost_dollars",
        ),
    ),
    (
        "results.zh.html",
        "\u6821\u51c6\u8bef\u5dee 0.097\uff08\u8d8a\u4f4e\u8d8a\u597d\uff09\u3002",
        (
            "v8_ece",
        ),
    ),
    (
        "results.zh.html",
        "160.4 s\uff1bp90 286.9 s\u3002",
        (
            "median_wall_seconds",
            "p90_wall_seconds",
        ),
    ),
    (
        "results.zh.html",
        "$0.058",
        (
            "median_cost_dollars",
        ),
    ),
    (
        "results.zh.html",
        "74% (112 / 151)",
        (
            "decided_share",
            "decided_automatically",
            "cases_total",
        ),
    ),
    (
        "results.zh.html",
        "sealed-v2 \u7684 12/12 \u5bf9\u5e94\u7684 Wilson 95% \u533a\u95f4\u662f [75.8%, 100%]\u3002",
        (
            "sealed_v2_exact",
            "sealed_v2_interval",
        ),
    ),
    (
        "how-it-works.html",
        "Case 5051: 3 points for the rider, 8 for the driver.",
        (
            "case5051_rider_points",
            "case5051_driver_points",
        ),
    ),
    (
        "how-it-works.html",
        "33 of 34 at version 8.",
        (
            "v8_swap",
        ),
    ),
    (
        "how-it-works.html",
        "Case 5051: 345 s of waiting, driver paid SGD 5.00.",
        (
            "case5051_wait_seconds",
            "case5051_amount",
        ),
    ),
    (
        "how-it-works.html",
        "A safety flag, a value over SGD 50 or a route deviation over 2 km goes to a person before the judge is asked.",
        (
            "v8_human_above",
            "v8_route_limit_km",
        ),
    ),
    (
        "how-it-works.html",
        "In the sixth sealed set (sealed-v4, version 7), all 9 cases that needed a person got one.",
        (
            "sealed_v4_to_person",
        ),
    ),
    (
        "how-it-works.html",
        "6 attack tests, version 6: 0 rulings flipped (5 unchanged, 1 sent to a person).",
        (
            "inject_flipped",
            "inject_unchanged",
            "inject_sent_to_a_person",
        ),
    ),
    (
        "how-it-works.html",
        "Sealed set (version 7): 30/30, written by the team's own development assistant.",
        (
            "sealed_v4_exact",
        ),
    ),
    (
        "how-it-works.html",
        "A safety flag, a value over SGD 50 or a route deviation over 2 km goes to a person; the lawyers have prepared the case file and the judge is not asked.",
        (
            "v8_human_above",
            "v8_route_limit_km",
        ),
    ),
    (
        "how-it-works.html",
        "Below the confidence v2.1 asks (0.80; 0.95 with a fraud flag), or with the drafts split, the money is held and a person decides.",
        (
            "v8_confidence_between",
            "v8_confidence_fraud",
        ),
    ),
    (
        "how-it-works.html",
        "Case 5051: 7 pieces of evidence, one pack.",
        (
            "case5051_evidence",
        ),
    ),
    (
        "how-it-works.html",
        "Case 5051: 10/11 claims kept.",
        (
            "case5051_claims_kept",
        ),
    ),
    (
        "how-it-works.html",
        "4 of 4 agree; conf. 0.95",
        (
            "case5051_agree",
            "case5051_confidence",
        ),
    ),
    (
        "how-it-works.html",
        "28 of 40 ruled by the AI; 12 to a person -- 5 stopped by a v2.1 rule before the judge, 6 the panel sent on, 1 without a majority.",
        (
            "v8_decided",
            "v8_to_person",
            "v8_gate_total",
            "v8_panel_escalated",
            "v8_no_majority",
        ),
    ),
    (
        "how-it-works.html",
        "The trip record says the driver waited 345 s from the wait's start to the cancellation, 300 s of it free, before cancelling.",
        (
            "case5051_wait_seconds",
            "case5051_free_wait_seconds",
        ),
    ),
    (
        "how-it-works.html",
        "7 evidence items",
        (
            "case5051_evidence",
        ),
    ),
    (
        "how-it-works.html",
        "3 vs 8 claims, rider vs driver",
        (
            "case5051_rider_points",
            "case5051_driver_points",
        ),
    ),
    (
        "how-it-works.html",
        "10/11 claims kept",
        (
            "case5051_claims_kept",
        ),
    ),
    (
        "how-it-works.html",
        "conf. 0.95",
        (
            "case5051_confidence",
        ),
    ),
    (
        "how-it-works.html",
        "SGD 5.00 to the driver, 254.8 s",
        (
            "case5051_amount",
            "case5051_wall",
        ),
    ),
    (
        "how-it-works.html",
        "15/15 with, 13/15 without",
        (
            "precedents_with",
            "precedents_without",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u6848\u4f8b 5051\uff1a\u4e58\u5ba2\u65b9\u63d0\u4e86 3 \u70b9\uff0c\u53f8\u673a\u65b9 8 \u70b9\u3002",
        (
            "case5051_rider_points",
            "case5051_driver_points",
        ),
    ),
    (
        "how-it-works.zh.html",
        "34 \u4e2a\u6848\u5b50\u91cc\uff0c\u5bf9\u8c03\u53cc\u65b9\u540e\u6709 33 \u4e2a\u7ed3\u8bba\u4e0d\u53d8",
        (
            "v8_swap_agreed",
            "v8_swap_total",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u6848\u4f8b 5051\uff1a\u7b49\u4e86 345 \u79d2\uff0c\u53f8\u673a\u83b7 SGD 5.00\u3002",
        (
            "case5051_wait_seconds",
            "case5051_amount",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u6709\u5b89\u5168\u6807\u8bb0\u3001\u91d1\u989d\u8d85\u8fc7 SGD 50\u3001\u6216\u7ed5\u8def\u8d85\u8fc7 2 \u516c\u91cc\uff0c\u90fd\u5728\u6cd5\u5b98\u4e4b\u524d\u8f6c\u7ed9\u4eba\u3002",
        (
            "v8_human_above",
            "v8_route_limit_km",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u7b2c\u516d\u5957\u5c01\u5b58\u96c6\uff08sealed-v4\uff0c\u7b2c 7 \u7248\uff09\u91cc\uff0c9 \u4e2a\u8be5\u4ea4\u7ed9\u4eba\u7684\u6848\u5b50\u90fd\u4ea4\u4e86\u3002",
        (
            "sealed_v4_to_person",
        ),
    ),
    (
        "how-it-works.zh.html",
        "6 \u6b21\u653b\u51fb\u6d4b\u8bd5\uff08\u7b2c 6 \u7248\uff09\uff1a0 \u4e2a\u5224\u51b3\u88ab\u6539\u53cd\uff085 \u4e2a\u4e0d\u53d8\uff0c1 \u4e2a\u8f6c\u4eba\u5de5\uff09\u3002",
        (
            "inject_flipped",
            "inject_unchanged",
            "inject_sent_to_a_person",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u5c01\u5b58\u96c6\uff08\u7b2c 7 \u7248\uff09\uff1a30/30\uff0c\u7531\u56e2\u961f\u81ea\u5df1\u7684\u5f00\u53d1\u52a9\u624b\u51fa\u9898\u3002",
        (
            "sealed_v4_exact",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u6709\u5b89\u5168\u6807\u8bb0\u3001\u91d1\u989d\u8d85\u8fc7 SGD 50\u3001\u6216\u7ed5\u8def\u8d85\u8fc7 2 \u516c\u91cc\uff0c\u5c31\u4ea4\u7ed9\u4eba\uff1b\u53cc\u65b9\u5f8b\u5e08\u5df2\u7ecf\u51c6\u5907\u597d\u6848\u5377\uff0c\u4e0d\u8be2\u95ee\u6cd5\u5b98\u3002",
        (
            "v8_human_above",
            "v8_route_limit_km",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u4f4e\u4e8e v2.1 \u8981\u6c42\u7684\u7f6e\u4fe1\u5ea6\uff080.80\uff1b\u5e26\u6b3a\u8bc8\u6807\u8bb0\u65f6 0.95\uff09\uff0c\u6216\u8349\u7a3f\u610f\u89c1\u4e0d\u4e00\uff0c\u5c31\u51bb\u7ed3\u6b3e\u9879\uff0c\u4ea4\u7ed9\u4eba\u5b9a\u3002",
        (
            "v8_confidence_between",
            "v8_confidence_fraud",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u6848\u4f8b 5051\uff1a7 \u9879\u8bc1\u636e\uff0c\u4e00\u4e2a\u8bc1\u636e\u5305\u3002",
        (
            "case5051_evidence",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u6848\u4f8b 5051\uff1a\u4e3b\u5f20\u4fdd\u7559 10/11\u3002",
        (
            "case5051_claims_kept",
        ),
    ),
    (
        "how-it-works.zh.html",
        "40 \u4e2a\u91cc 28 \u4e2a\u7531 AI \u5224\uff1b12 \u4e2a\u4ea4\u7ed9\u4eba\u2014\u20145 \u4e2a\u88ab v2.1 \u7684\u89c4\u5219\u5728\u6cd5\u5b98\u4e4b\u524d\u62e6\u4e0b\uff0c6 \u4e2a\u7531\u5408\u8bae\u5ead\u8f6c\u51fa\uff0c1 \u4e2a\u6ca1\u6709\u5f62\u6210\u591a\u6570\u3002",
        (
            "v8_decided_count",
            "v8_cases",
            "v8_to_person",
            "v8_gate_total",
            "v8_panel_escalated",
            "v8_no_majority",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u53f8\u673a\u5728\u4e0a\u8f66\u70b9\u4ece\u7b49\u5f85\u5f00\u59cb\u5230\u53d6\u6d88\u5171\u7b49\u4e86 345 \u79d2\uff0c\u5176\u4e2d 300 \u79d2\u662f\u514d\u8d39\u7b49\u5f85\u3002",
        (
            "case5051_wait_seconds",
            "case5051_free_wait_seconds",
        ),
    ),
    (
        "how-it-works.zh.html",
        "7 \u9879\u8bc1\u636e",
        (
            "case5051_evidence",
        ),
    ),
    (
        "how-it-works.zh.html",
        "3 vs 8 \u6761\u4e3b\u5f20",
        (
            "case5051_rider_points",
            "case5051_driver_points",
        ),
    ),
    (
        "how-it-works.zh.html",
        "10/11 \u6761\u4e3b\u5f20\u4fdd\u7559",
        (
            "case5051_claims_kept",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u7f6e\u4fe1\u5ea6 0.95",
        (
            "case5051_confidence",
        ),
    ),
    (
        "how-it-works.zh.html",
        "SGD 5.00 \u5224\u7ed9\u53f8\u673a\uff0c\u7528\u65f6 254.8 s",
        (
            "case5051_amount",
            "case5051_wall",
        ),
    ),
    (
        "how-it-works.zh.html",
        "\u6709\u5148\u4f8b 15/15\uff0c\u65e0 13/15",
        (
            "precedents_with",
            "precedents_without",
        ),
    ),
    (
        "about.html",
        "the third sealed set (sealed-v1) run once: 21/24.",
        (
            "sealed_v1_exact",
        ),
    ),
    (
        "about.html",
        "the fourth sealed set (sealed-v2): 12/12.",
        (
            "sealed_v2_exact",
        ),
    ),
    (
        "about.zh.html",
        "\u7b2c\u4e09\u5957\u5c01\u5b58\u96c6\uff08sealed-v1\uff09\u8dd1\u4e00\u6b21\uff1a21/24\u3002",
        (
            "sealed_v1_exact",
        ),
    ),
    (
        "about.zh.html",
        "\u7b2c\u56db\u5957\u5c01\u5b58\u96c6\uff08sealed-v2\uff09\uff1a12/12\u3002",
        (
            "sealed_v2_exact",
        ),
    ),
    # Part 105's two. The poster is version 8's, so the caption is a sentence
    # that names version 8 and carries the version-8 median in minutes; the
    # cost it states is rounded the way version 6's was, and no figure carries
    # the rounded spelling, so the row names the median-in-minutes figure.
    (
        "about.html",
        "The poster's figures (2.6 min, US$0.04 a case) are version 8's: dev-v8's medians, rounded.",
        (
            "v8_median_minutes",
        ),
    ),
    (
        "about.zh.html",
        "\u6d77\u62a5\u4e0a\u7684\u6570\u5b57\uff082.6 \u5206\u949f\u3001\u6bcf\u6848 0.04 \u7f8e\u5143\uff09\u662f\u7b2c 8 \u7248\u7684\uff1adev-v8 \u7684\u4e2d\u4f4d\u6570\uff0c\u56db\u820d\u4e94\u5165\u3002",
        (
            "v8_median_minutes",
        ),
    ),
    (
        "index.html",
        "Applies Ryde's own Dispute Resolution Policy v2.1 with Ryde's answers of 2026-10-14 (policy version 8). Sealed set, run at version 7: 30/30, Wilson 95% [88.6%, 100%] -- written by the team's own development assistant, so not an independent benchmark.",
        (
            "sealed_v4_exact",
            "sealed_v4_interval",
        ),
    ),
    (
        "index.zh.html",
        "\u6309 Ryde \u5b98\u65b9\u7684\u300a\u4e89\u8bae\u5904\u7406\u653f\u7b56 v2.1\u300b\u53ca Ryde 2026-10-14 \u7684\u7b54\u590d\u88c1\u51b3\uff08\u7b2c 8 \u7248\u653f\u7b56\uff09\u3002\u5c01\u5b58\u96c6\uff08\u5728\u7b2c 7 \u7248\u4e0a\u8dd1\uff09\uff1a30/30\uff0cWilson 95% [88.6%, 100%]\u2014\u2014\u7531\u56e2\u961f\u81ea\u5df1\u7684\u5f00\u53d1\u52a9\u624b\u51fa\u9898\uff0c\u4e0d\u662f\u72ec\u7acb\u57fa\u51c6\u3002",
        (
            "sealed_v4_exact",
            "sealed_v4_interval",
        ),
    ),
    (
        "results.html",
        "30/30 right on the 30 sealed cases, Wilson 95% [88.6%, 100%]; written by Claude (Opus 5.5) in a fresh claude.ai chat from Ryde's v2.1 and the version-7 files; run once from freeze-2026-10-14.",
        (
            "sealed_v4_exact",
            "sealed_v4_interval",
        ),
    ),
    (
        "results.html",
        "1/2 -- DISP-001 (route deviation) ruled exactly as Ryde states (partial refund 3.44); DISP-002 (no-show) escalated: the four drafts split 2-2 on whether eight sparse GPS fixes reach the 0.95 confidence Tribunal's version-7 policy requires -- its reading of v2.1 6.3 (C15) -- when a party carries a fraud flag.",
        (
            "ryde_v7_exact",
        ),
    ),
    (
        "results.html",
        "dev-v7: 40/40, development data the team tuned against.",
        (
            "dev_v7_exact",
        ),
    ),
    (
        "results.zh.html",
        "30 \u9053\u5c01\u5b58\u9898\u5bf9\u4e86 30/30\uff0cWilson 95% [88.6%, 100%]\uff1b\u7531 Claude\uff08Opus 5.5\uff09\u5728\u5168\u65b0\u7684 claude.ai \u5bf9\u8bdd\u4e2d\u6309 Ryde v2.1 \u4e0e\u7b2c 7 \u7248\u653f\u7b56\u51fa\u9898\uff1b\u4ece freeze-2026-10-14 \u53ea\u8dd1\u4e00\u6b21\u3002",
        (
            "sealed_v4_exact",
            "sealed_v4_interval",
        ),
    ),
    (
        "results.zh.html",
        "Ryde \u5b98\u65b9\u6837\u4f8b 1/2\uff1aDISP-001\uff08\u7ed5\u8def\uff09\u4e0e Ryde \u7ed9\u51fa\u7684\u7b54\u6848\u4e00\u81f4\uff08\u90e8\u5206\u9000\u6b3e 3.44\uff09\uff1b",
        (
            "ryde_v7_exact",
        ),
    ),
    (
        "results.zh.html",
        "\u5f00\u53d1\u96c6 40/40\uff08\u56e2\u961f\u636e\u6b64\u8c03\u8bd5\uff0c\u4e0d\u662f\u6cdb\u5316\u6210\u7ee9\uff09\u3002",
        (
            "dev_v7_exact",
        ),
    ),
    (
        "about.html",
        "Version 7 frozen; the sixth sealed set (sealed-v4): 30/30.",
        (
            "sealed_v4_exact",
        ),
    ),
    (
        "about.zh.html",
        "\u7b2c 7 \u7248\u51bb\u7ed3\uff1b\u7b2c\u516d\u5957\u5c01\u5b58\u96c6\uff08sealed-v4\uff09\uff1a30/30\u3002",
        (
            "sealed_v4_exact",
        ),
    ),
    (
        "results.html",
        "1/2: DISP-001 (route deviation, 4.3 km) escalated, as Ryde answered on 2026-10-14 that the 2 km limb applies; DISP-002 (no-show) escalated: the drafts did not agree on whether eight sparse GPS fixes reach the 0.95 confidence Tribunal's version-8 policy requires -- its reading of v2.1 6.3 (C15); v2.1 6.2 makes a no-show ruling AI-final and Ryde's outcome upholds the fee; Ryde has since said, through the organisers on 2026-10-15, that a team may use its own policy, so C15 stays Tribunal's stated reading.",
        (
            "ryde_v8_exact",
        ),
    ),
    (
        "results.html",
        "dev-v8: 39/40, development data the team tuned against.",
        (
            "dev_v8_exact",
        ),
    ),
    (
        "results.zh.html",
        "Ryde \u5b98\u65b9\u6837\u4f8b 1/2\uff1aDISP-001\uff08\u7ed5\u8def 4.3 km\uff09\u8f6c\u4eba\u5de5\u2014\u2014Ryde \u4e8e 2026-10-14 \u7b54\u590d 2 km \u89c4\u5219\u9002\u7528\uff1bDISP-002\uff08\u672a\u5230\u573a\uff09\u8f6c\u4eba\u5de5\uff1a\u4e58\u5ba2\u5e26\u6b3a\u8bc8\u6807\u8bb0\u65f6\uff0cTribunal \u7684\u7b2c 8 \u7248\u653f\u7b56\u8981\u6c42 0.95 \u7684\u7f6e\u4fe1\u5ea6\u2014\u2014\u8fd9\u662f\u5b83\u5bf9 v2.1 \u7b2c 6.3 \u6761\u7684\u8bfb\u6cd5\uff08C15\uff09\uff1bv2.1 \u7b2c 6.2 \u6761\u4f7f\u672a\u5230\u573a\u88c1\u51b3\u6210\u4e3a\u6700\u7ec8\uff0c\u800c Ryde \u7ed9\u51fa\u7684\u7ed3\u679c\u662f\u7ef4\u6301\u6536\u8d39\uff0c\u4e3b\u529e\u65b9 2026-10-15 \u8f6c\u8fbe Ryde \u7684\u610f\u89c1\uff1a\u5404\u961f\u53ef\u4ee5\u7528\u81ea\u5df1\u7684\u653f\u7b56\uff0c\u6240\u4ee5 C15 \u4ecd\u662f Tribunal \u660e\u786e\u8bf4\u660e\u7684\u8bfb\u6cd5\u3002",
        (
            "ryde_v8_exact",
        ),
    ),
    (
        "results.zh.html",
        "\u5f00\u53d1\u96c6 39/40\uff08\u56e2\u961f\u636e\u6b64\u8c03\u8bd5\uff0c\u4e0d\u662f\u6cdb\u5316\u6210\u7ee9\uff09\u3002",
        (
            "dev_v8_exact",
        ),
    ),
    (
        "cases.html",
        "The trip record gives 24.8 km driven against 20.5 km on the recommended route: a deviation of 4.30 km, over the 2.0 km limit of v2.1 6.2. Ryde answered on 2026-10-14 that the limit applies, so version 8 sends the case to a person before the judge is asked, with the excess distance fare the code computed: SGD 3.44 (4.30 km x 0.80). Result: escalated, as Ryde answered.",
        (
            "ryde902_actual_km",
            "ryde902_optimal_km",
            "ryde902_deviation_km",
            "ryde902_limit_km",
            "ryde902_excess_sgd",
            "ryde902_rate_sgd",
        ),
    ),
    (
        "cases.html",
        "The driver arrived at 08:43; the free wait ran to 08:48 and the trip was cancelled at 08:51, after it. The rider's profile carries a fraud flag, so Tribunal's version-8 policy requires a confidence of 0.95 -- its reading of v2.1 6.3 (C15); v2.1 6.2 makes a no-show ruling AI-final and Ryde's outcome upholds the fee, and Ryde has since said, through the organisers on 2026-10-15, that a team may use its own policy -- and the arrival rests on 8 GPS fixes two to four minutes apart. Of the judge's four drafts, 2 escalated, 1 upheld the fee and 1 was voided for citing a clause that does not exist; three must agree, so the case went to a person with the fee held. Ryde's stated outcome is the fee upheld: this is our one known divergence.",
        (
            "ryde903_arrived",
            "ryde903_free_wait_ends",
            "ryde903_cancelled",
            "ryde903_required_confidence",
            "ryde903_gps_fixes",
            "ryde903_drafts_escalate",
            "ryde903_drafts_fee",
            "ryde903_drafts_voided",
        ),
    ),
    (
        "cases.html",
        "All 42 version-8 cases",
        (
            "v8_case_pages",
        ),
    ),
    (
        "cases.zh.html",
        "\u884c\u7a0b\u8bb0\u5f55\uff1a\u5b9e\u9645 24.8 km\uff0c\u63a8\u8350\u8def\u7ebf 20.5 km\uff0c\u7ed5\u8def 4.30 km\uff0c\u8d85\u8fc7 v2.1 \u7b2c 6.2 \u6761\u7684 2.0 km \u4e0a\u9650\u3002Ryde \u4e8e 2026-10-14 \u7b54\u590d\u8be5\u4e0a\u9650\u9002\u7528\uff0c\u6240\u4ee5\u7b2c 8 \u7248\u5728\u6cd5\u5b98\u4e4b\u524d\u76f4\u63a5\u8f6c\u4eba\u5de5\uff0c\u5e76\u9644\u4e0a\u4ee3\u7801\u7b97\u51fa\u7684\u8d85\u989d\u91cc\u7a0b\u8d39\uff1aSGD 3.44\uff084.30 km \u00d7 0.80\uff09\u3002\u7ed3\u679c\uff1a\u8f6c\u4eba\u5de5\uff0c\u4e0e Ryde \u7684\u7b54\u590d\u4e00\u81f4\u3002",
        (
            "ryde902_actual_km",
            "ryde902_optimal_km",
            "ryde902_deviation_km",
            "ryde902_limit_km",
            "ryde902_excess_sgd",
            "ryde902_rate_sgd",
        ),
    ),
    (
        "cases.zh.html",
        "\u53f8\u673a 08:43 \u5230\u8fbe\uff0c\u514d\u8d39\u7b49\u5f85\u5230 08:48\uff0c\u884c\u7a0b\u5728 08:51 \u53d6\u6d88\uff0c\u5df2\u8fc7\u514d\u8d39\u7b49\u5f85\u3002\u4e58\u5ba2\u5e26\u6b3a\u8bc8\u6807\u8bb0\uff0cTribunal \u7684\u7b2c 8 \u7248\u653f\u7b56\u8981\u6c42\u7f6e\u4fe1\u5ea6 0.95\u2014\u2014\u8fd9\u662f\u5b83\u5bf9 v2.1 \u7b2c 6.3 \u6761\u7684\u8bfb\u6cd5\uff08C15\uff09\uff1bv2.1 \u7b2c 6.2 \u6761\u4f7f\u672a\u5230\u573a\u88c1\u51b3\u6210\u4e3a\u6700\u7ec8\uff0c\u800c Ryde \u7ed9\u51fa\u7684\u7ed3\u679c\u662f\u7ef4\u6301\u6536\u8d39\uff0c\u4e3b\u529e\u65b9 2026-10-15 \u8f6c\u8fbe Ryde \u7684\u610f\u89c1\uff1a\u5404\u961f\u53ef\u4ee5\u7528\u81ea\u5df1\u7684\u653f\u7b56\u2014\u2014\u800c\u5230\u8fbe\u53ea\u9760 8 \u4e2a\u76f8\u9694\u4e24\u5230\u56db\u5206\u949f\u7684 GPS \u70b9\u3002\u6cd5\u5b98\u7684\u56db\u4efd\u8349\u7a3f\u4e2d\uff0c2 \u4efd\u8f6c\u4eba\u5de5\uff0c1 \u4efd\u7ef4\u6301\u6536\u8d39\uff0c1 \u4efd\u56e0\u5f15\u7528\u4e0d\u5b58\u5728\u7684\u6761\u6b3e\u88ab\u4f5c\u5e9f\uff1b\u9700\u8981\u4e09\u4efd\u4e00\u81f4\uff0c\u6240\u4ee5\u8f6c\u7ed9\u4eba\uff0c\u8d39\u7528\u6682\u6263\u3002Ryde \u7ed9\u51fa\u7684\u7ed3\u679c\u662f\u7ef4\u6301\u6536\u8d39\uff1a\u8fd9\u662f\u6211\u4eec\u552f\u4e00\u5df2\u77e5\u7684\u5206\u6b67\u3002",
        (
            "ryde903_arrived",
            "ryde903_free_wait_ends",
            "ryde903_cancelled",
            "ryde903_required_confidence",
            "ryde903_gps_fixes",
            "ryde903_drafts_escalate",
            "ryde903_drafts_fee",
            "ryde903_drafts_voided",
        ),
    ),
    (
        "cases.zh.html",
        "\u5168\u90e8 42 \u9053\u7b2c 8 \u7248\u6848\u4ef6",
        (
            "v8_case_pages",
        ),
    ),
    (
        "safety.html",
        "The SGD 8 sign-off is version 6's rule. Version 8 applies v2.1's own: below SGD 10 the AI ruling is final, from 10 to 50 it stands only at a confidence of 0.80 or more (0.95 with a fraud flag), and above 50 a person decides.",
        (
            "v8_ai_final_below",
            "v8_human_above",
            "v8_confidence_between",
            "v8_confidence_fraud",
        ),
    ),
    (
        "safety.html",
        "The AI wasn't sure or its drafts split, the amount is over SGD 50, it's about safety, or the route deviates by over 2 km.",
        (
            "v8_human_above",
            "v8_route_limit_km",
        ),
    ),
    (
        "safety.html",
        "slow for a chat reply (median 153.1 s)",
        (
            "v8_median_seconds",
        ),
    ),
    (
        "safety.html",
        "On the 40 version-8 cases the three limbs stopped 5 between them: 2 on the 2 km limit, 1 on the value, 2 on a safety flag.",
        (
            "v8_cases",
            "v8_gate_total",
            "v8_gate_2km",
            "v8_gate_value",
            "v8_gate_safety",
            "v8_route_limit_km",
        ),
    ),
    (
        "safety.zh.html",
        "SGD 8 \u7b7e\u6838\u662f\u7b2c 6 \u7248\u7684\u89c4\u5219\u3002\u7b2c 8 \u7248\u7528 v2.1 \u81ea\u5df1\u7684\u89c4\u5219\uff1a\u4f4e\u4e8e SGD 10 \u65f6 AI \u5224\u51b3\u5373\u4e3a\u6700\u7ec8\uff1b10 \u5230 50 \u4e4b\u95f4\uff0c\u7f6e\u4fe1\u5ea6\u987b\u8fbe 0.80\uff08\u6709\u6b3a\u8bc8\u6807\u8bb0\u65f6 0.95\uff09\uff1b\u9ad8\u4e8e 50 \u7531\u4eba\u51b3\u5b9a\u3002",
        (
            "v8_ai_final_below",
            "v8_human_above",
            "v8_confidence_between",
            "v8_confidence_fraud",
        ),
    ),
    (
        "safety.zh.html",
        "AI \u6ca1\u628a\u63e1\u6216\u610f\u89c1\u4e0d\u4e00\u3001\u91d1\u989d\u8d85\u8fc7 SGD 50\u3001\u6d89\u53ca\u5b89\u5168\uff0c\u6216\u7ed5\u8def\u8d85\u8fc7 2 \u516c\u91cc\u3002",
        (
            "v8_human_above",
            "v8_route_limit_km",
        ),
    ),
    (
        "safety.zh.html",
        "\u5bf9\u804a\u5929\u56de\u590d\u800c\u8a00\u504f\u6162\uff08\u4e2d\u4f4d 153.1 s\uff09",
        (
            "v8_median_seconds",
        ),
    ),
    (
        "safety.zh.html",
        "40 \u4e2a\u7b2c 8 \u7248\u6848\u5b50\u91cc\uff0c\u4e09\u4e2a\u9650\u5236\u5171\u62e6\u4e0b 5 \u4e2a\uff1a2 \u4e2a\u51fa\u5728 2 \u516c\u91cc\u4e0a\u9650\uff0c1 \u4e2a\u51fa\u5728\u91d1\u989d\uff0c2 \u4e2a\u51fa\u5728\u5b89\u5168\u6807\u8bb0\u3002",
        (
            "v8_cases",
            "v8_gate_total",
            "v8_gate_2km",
            "v8_gate_value",
            "v8_gate_safety",
            "v8_route_limit_km",
        ),
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
    "cases.html",
    "cases.zh.html",
    "safety.html",
    "safety.zh.html",
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
        "results.html",
        "The team's own policy, frozen on 2026-10-11 and kept as history.",
    ),
    (
        "results.zh.html",
        "\u56e2\u961f\u81ea\u5b9a\u653f\u7b56\uff0c\u4e8e 2026-10-11 \u51bb\u7ed3\uff0c\u7559\u4f5c\u5386\u53f2\u3002",
    ),
    (
        "cases.html",
        "The case pages and the queue below show the version-6 runs.",
    ),
    (
        "cases.zh.html",
        "\u4e0b\u9762\u7684\u6848\u4ef6\u9875\u548c\u961f\u5217\u5c55\u793a\u7684\u662f\u7b2c 6 \u7248\u7684\u8dd1\u5206\u3002",
    ),
    (
        "how-it-works.html",
        "Since 2026-10-14 the policy is Ryde's v2.1 with Ryde's answers to the team's three questions (the 2 km limb applies, the free wait runs from the driver's arrival, no surge on the excess distance fare), written as numbered clauses (docs/notes/2026-10-14-policy-v8.md).",
    ),
    (
        "how-it-works.zh.html",
        "\u81ea 2026-10-14 \u8d77\uff0c\u653f\u7b56\u662f Ryde \u7684 v2.1 \u52a0\u4e0a Ryde \u5bf9\u56e2\u961f\u4e09\u4e2a\u95ee\u9898\u7684\u7b54\u590d\uff082 km \u89c4\u5219\u9002\u7528\uff1b\u514d\u8d39\u7b49\u5f85\u4ece\u53f8\u673a\u5230\u8fbe\u8d77\u7b97\uff1b\u8d85\u989d\u91cc\u7a0b\u8d39\u4e0d\u52a0 surge\uff09\uff0c\u6539\u5199\u4e3a\u5e26\u7f16\u53f7\u7684\u6761\u6b3e\uff08docs/notes/2026-10-14-policy-v8.md\uff09\u3002",
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
        written = site.pages()
        cls.raw = {path.name: text for path, text in written}
        cls.pages = {name: visible_text(text) for name, text in cls.raw.items()}
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
        the record reddens the second. The row used is ``results.html``'s
        ``Version 6, time to a decision`` one -- the version-6 median and 90th
        percentile, which left the front page's tiles for the fine print's
        table -- so the line the report names is this one.
        """
        shown = "160.4 s; p90 286.9 s."
        names = ("median_wall_seconds", "p90_wall_seconds")
        page = self.pages["results.html"]
        moved_page = page.replace("160.4 s", "160.5 s")
        self.assertNotEqual(page, moved_page, "the fixture did not move the figure")
        with self.assertRaises(AssertionError):
            self.assert_shows(moved_page, "results.html", shown, names)
        with self.assertRaises(AssertionError):
            self.assert_shows(page, "results.html", "160.5 s; p90 286.9 s.", names)
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
            "30/30 right on the 30 sealed cases, Wilson 95% 88.6%, 100%; written by "
            "Claude (Opus 5.5) in a fresh claude.ai chat from Ryde's v2.1 and the "
            "version-7 files; run once from freeze-2026-10-14."
        )
        names = ("sealed_v4_exact", "sealed_v4_interval")
        page = self.pages["results.html"]
        moved = page.replace(
            "30/30 right on the 30 sealed cases", "29/30 right on the 30 sealed cases"
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

    def test_the_check_fails_on_a_page_carrying_a_different_front_page_cost(
        self,
    ) -> None:
        """The control: ``index.html``'s version-8 cost tile, moved, is reported.

        The row used is the front page's ``$0.039`` one -- the figure this part
        adds, so that the tile's number is the number ``ui.site.figures``
        computes and not a second copy of it. The figure is moved in the page
        and then in the record, one after the other, and each reddens one of the
        two assertions ``assert_shows`` makes.
        """
        shown = "$0.039"
        names = ("v8_median_cost_dollars",)
        page = self.pages["index.html"]
        moved = page.replace("$0.039", "$0.040")
        self.assertNotEqual(page, moved, "the fixture did not move the figure")
        with self.assertRaises(AssertionError):
            self.assert_shows(moved, "index.html", shown, names)
        self.figures["v8_median_cost_dollars"] = "$0.040"
        try:
            with self.assertRaises(AssertionError):
                self.assert_shows(page, "index.html", shown, names)
        finally:
            self.figures["v8_median_cost_dollars"] = figures.named(
                "v8_median_cost_dollars"
            )

    def test_the_index_links_to_the_samples_section_in_both_languages(self) -> None:
        """The front page's line to the new section resolves to that section.

        The line names the cases page and the section's own id, and the two are
        checked together: the line is on the front page with the words it
        carries, and the page it points at is the page that holds the id. Both
        languages, because the two front pages link to the two cases pages.
        """
        for page, target, label in (
            (
                "index.html",
                "cases.html#ryde",
                "Ryde's own two samples, at version 8 ->",
            ),
            (
                "index.zh.html",
                "cases.zh.html#ryde",
                "Ryde \u5b98\u65b9\u7684\u4e24\u9053\u6837\u4f8b\uff08\u7b2c 8"
                " \u7248\uff09 ->",
            ),
        ):
            with self.subTest(page=page):
                self.assertIn('href="{0}"'.format(target), self.raw[page])
                self.assertIn(label, self.pages[page])
                self.assertIn('id="ryde"', self.raw[target.split("#", 1)[0]])

    def test_the_check_fails_on_a_page_carrying_a_different_ryde_sample_figure(
        self,
    ) -> None:
        """The control: ``cases.html``'s deviation figure, moved, is reported.

        The row used is the new section's DISP-001 one, so the line the report
        names is that row. The figure is moved in the page and then in the
        record, one after the other, and each reddens one of the two assertions
        ``assert_shows`` makes.
        """
        shown = (
            "The trip record gives 24.8 km driven against 20.5 km on the recommended "
            "route: a deviation of 4.30 km, over the 2.0 km limit of v2.1 6.2. Ryde "
            "answered on 2026-10-14 that the limit applies, so version 8 sends the "
            "case to a person before the judge is asked, with the excess distance "
            "fare the code computed: SGD 3.44 (4.30 km x 0.80). Result: escalated, "
            "as Ryde answered."
        )
        names = ("ryde902_deviation_km",)
        page = self.pages["cases.html"]
        moved = page.replace("a deviation of 4.30 km", "a deviation of 4.31 km")
        self.assertNotEqual(page, moved, "the fixture did not move the figure")
        with self.assertRaises(AssertionError):
            self.assert_shows(moved, "cases.html", shown, names)
        self.figures["ryde902_deviation_km"] = "4.31"
        try:
            with self.assertRaises(AssertionError):
                self.assert_shows(page, "cases.html", shown, names)
        finally:
            self.figures["ryde902_deviation_km"] = figures.named(
                "ryde902_deviation_km"
            )# --------------------------------------------------------------------------
# The version-6 phrases, and the one rule the gate counts are read by
# --------------------------------------------------------------------------
# The phrases that state a version-6 rule as though it were the current one.
# None may stand in a block that does not name version 6 for itself.
VERSION_SIX_PHRASES: Tuple[str, ...] = (
    "over SGD 8",
    "Over SGD 8",
    "0.70",
    "prompts/v1",
    "within 30 days",
    "never reach the AI",
    # Part 97's three. "Hidden test" was what the site called a sealed set and
    # "The figures above are from version 6" the line under the front page's
    # tiles; the tiles are version 8's now, so the line is gone and the phrase
    # with it. "Collected before any model runs" was the evidence card's claim,
    # and ``ops/evidence.py`` is a standalone command the pipeline never calls.
    "Hidden test",
    "The figures above are from version 6",
    "Collected before any model runs",
    # Part 101's two. The C15 question was put to Ryde and both pages stated it
    # as open, in each language. The organisers relayed Ryde's position on
    # 2026-10-15, so C15 is Tribunal's own, stated reading, and a page that
    # still said the question was with Ryde would be stating a reading the
    # pages no longer hold.
    "the question is with Ryde",
    "\u8fd9\u4e2a\u95ee\u9898\u5728 Ryde \u90a3\u8fb9",
    # Part 103's six. Part 97 renamed the hidden test set on the front page and
    # left the same wording in twelve more sentences; part 103 finished the job,
    # so no page calls a sealed set hidden and no Chinese page calls a no-show
    # \u723d\u7ea6. "hidden set" is the two words the twelve English sentences shared;
    # the other two English phrases are the plural and the case count, and the
    # three Chinese ones are their own. A page that called a sealed set hidden
    # would be describing the set the system was never developed against as one
    # a reader cannot check, which is the reading part 97 removed.
    "hidden set",
    "hidden cases",
    "hidden test sets",
    "\u9690\u85cf\u8003\u9898",
    "\u9690\u85cf\u9898",
    "\u723d\u7ea6",
    # Part 105's one. \u672a\u51fa\u73b0 is "did not appear" -- the wording the two
    # Chinese pages used for the DISP-002 no-show, beside part 103's \u723d\u7ea6.
    # The case is a no-show, so the pages read \u672a\u5230\u573a now, and a block
    # that still carried the old phrase would be naming the case as something
    # it is not.
    "\u672a\u51fa\u73b0",
)


def names_version_six(text: str) -> bool:
    """Whether a page's visible text names version 6, in English or in Chinese."""
    return "version 6" in text or "\u7b2c 6 \u7248" in text


# The one phrase that is still stated, and the pages that state it. Both are the
# appeal sentence, which names version 6 in its own words; every other phrase is
# gone from the site.
VERSION_SIX_PLACES: Tuple[Tuple[str, str], ...] = (
    ("index.html", "within 30 days"),
    ("safety.html", "within 30 days"),
)

# What a block that states a version-6 rule must say for itself.
VERSION_SIX_WORDS: Tuple[str, ...] = ("version 6", "version-6", "Version 6", "Version-6")

# The closing tag of a block. A block is the text a reader meets between two of
# them, which is the unit a heading or a sentence labels.
BLOCK_END_RE = re.compile(r"</(?:p|li|h1|h2|h3|h4|td|th|button|pre|figcaption|div)>")


def text_blocks(markup: str) -> Tuple[str, ...]:
    """A page's visible text, split into the blocks a heading or sentence labels."""
    blocks: list = []
    position = 0
    for match in BLOCK_END_RE.finditer(markup):
        blocks.append(visible_text(markup[position : match.end()]))
        position = match.end()
    blocks.append(visible_text(markup[position:]))
    return tuple(block for block in blocks if block)


def blocks_stating_a_phrase(markup: str) -> Tuple[Tuple[str, str], ...]:
    """Every ``(phrase, block)`` a page's markup states, in block order."""
    stated: list = []
    for block in text_blocks(markup):
        for phrase in VERSION_SIX_PHRASES:
            if phrase in block:
                stated.append((phrase, block))
    return tuple(stated)


def unlabelled_phrases(markup: str) -> Tuple[Tuple[str, str], ...]:
    """The ``(phrase, block)`` pairs a page states without naming version 6.

    A block that names version 6 for itself is where a version-6 rule may
    stand, so those pairs are not findings. Every other pair is what
    ``TheVersionSixPhrasesTests`` reports, and the control beside that test
    shows the reporting can fire.
    """
    return tuple(
        (phrase, block)
        for phrase, block in blocks_stating_a_phrase(markup)
        if not any(word in block for word in VERSION_SIX_WORDS)
    )


class TheVersionSixPhrasesTests(unittest.TestCase):
    """No built page states a version-6 rule as the one in force.

    Every page under ``ui/dist`` is read. The product site's own pages -- the 22
    this part rewrites -- are read **block by block**, the unit a heading or a
    sentence labels: a block that carries one of :data:`VERSION_SIX_PHRASES`
    must name version 6 itself, and the blocks that do are
    :data:`VERSION_SIX_PLACES`. The pages the other builders write are read
    **whole**: they are the version-6 support site and the version-8 case pages,
    neither of which this part changes, and each says which policy version it
    replays in its own top bar, so a page is the section there.
    """

    @classmethod
    def setUpClass(cls) -> None:
        portability.require_the_same_libm()
        cls.site_pages = frozenset(source.name for source in site.page_sources())
        cls.raw = {
            path.name: path.read_text(encoding="utf-8")
            for path in sorted(site.DIST_DIR.glob("*.html"))
        }

    def test_no_block_states_a_version_six_rule_without_naming_version_six(self):
        for name, markup in sorted(self.raw.items()):
            if name not in self.site_pages:
                continue
            for phrase, block in unlabelled_phrases(markup):
                with self.subTest(page=name, phrase=phrase):
                    self.fail(
                        "{0} states {1!r} in a block that does not name version "
                        "6: {2!r}".format(name, phrase, block)
                    )

    def test_the_blocks_that_state_one_are_the_ones_listed(self):
        found = set()
        for name, markup in sorted(self.raw.items()):
            if name not in self.site_pages:
                continue
            for phrase, _block in blocks_stating_a_phrase(markup):
                found.add((name, phrase))
        self.assertEqual(
            set(VERSION_SIX_PLACES),
            found,
            "the pages state version-6 phrases at {0}, and the table lists {1}".format(
                sorted(found), sorted(VERSION_SIX_PLACES)
            ),
        )

    def test_the_check_fails_on_a_page_carrying_the_old_ending(self):
        """The control: the results page's old ending, put back, is reported.

        Part 101 settled C15, and the two phrases it removed are the ones the
        old ending wrote -- "the question is with Ryde" in English and its
        Chinese opposite number -- on the results page and the cases page. This
        is the built results page's own markup with that ending put back, and
        the check above must report it: the block states the question as open
        and names version 6 nowhere.
        """
        markup = self.raw["results.html"]
        self.assertNotIn("the question is with Ryde", markup)
        restored = markup.replace(
            "so C15 stays Tribunal's stated reading.",
            "so the question is with Ryde.",
        )
        self.assertNotEqual(markup, restored, "the fixture did not restore the ending")
        reported = unlabelled_phrases(restored)
        self.assertEqual(
            [phrase for phrase, _block in reported],
            ["the question is with Ryde"],
            "the copy is reported as {0!r}".format(reported),
        )

    def test_the_check_fails_on_a_page_carrying_the_old_hidden_wording(self):
        """The control: the about page's old wording, put back, is reported.

        Part 97 renamed the hidden test set on the front page and part 103
        finished the job on the twelve sentences that still called a sealed set
        hidden. This is the built about page's own markup with "the sixth hidden
        set" put back, and the check above must report it: the block calls a
        sealed set hidden and names version 6 nowhere.
        """
        markup = self.raw["about.html"]
        self.assertNotIn("hidden set", markup)
        restored = markup.replace(
            "the sixth sealed set (sealed-v4)", "the sixth hidden set (sealed-v4)"
        )
        self.assertNotEqual(markup, restored, "the fixture did not restore the wording")
        reported = unlabelled_phrases(restored)
        self.assertEqual(
            [phrase for phrase, _block in reported],
            ["hidden set"],
            "the copy is reported as {0!r}".format(reported),
        )

    def test_the_check_fails_on_a_page_carrying_the_old_no_show_wording(self):
        """The control: the cases page's old wording, put back, is reported.

        Part 105 renamed the DISP-002 no-show on the two Chinese pages, in the
        card's heading and in the sentence about v2.1 6.2. This is the built
        cases page's own markup with the heading put back, and the check above
        must report it: the block names the case as one that did not appear and
        names version 6 nowhere.
        """
        markup = self.raw["cases.zh.html"]
        self.assertNotIn("\u672a\u51fa\u73b0", markup)
        restored = markup.replace(
            "<h3>\u672a\u5230\u573a</h3>", "<h3>\u672a\u51fa\u73b0</h3>"
        )
        self.assertNotEqual(markup, restored, "the fixture did not restore the wording")
        reported = unlabelled_phrases(restored)
        self.assertEqual(
            [phrase for phrase, _block in reported],
            ["\u672a\u51fa\u73b0"],
            "the copy is reported as {0!r}".format(reported),
        )

    def test_the_other_builders_pages_name_the_version_they_replay(self):
        """The pages this part does not write say which policy version they are.

        The version-6 support site and the version-8 case pages are the other
        two builders'; the support site's top bar reads "Recorded runs, policy
        version 6" and the case pages are named by the version their own index
        states. A Chinese page names the version in its own words, \u7b2c 6 \u7248,
        which :func:`names_version_six` reads beside the English. A page that
        states one of the phrases and does not name version 6 would be a page
        stating a version-6 rule as the current one.
        """
        others = {
            name: markup for name, markup in self.raw.items() if name not in self.site_pages
        }
        self.assertTrue(others, "ui/dist holds no page but the site's own")
        for name, markup in sorted(others.items()):
            text = visible_text(markup)
            stated = [phrase for phrase in VERSION_SIX_PHRASES if phrase in text]
            if not stated:
                continue
            with self.subTest(page=name):
                # A Chinese page names the version in its own words.
                self.assertTrue(
                    names_version_six(text),
                    "{0} states a version-6 phrase and names no version".format(name),
                )

    def test_the_check_fails_on_a_chinese_page_naming_no_version(self):
        """The control: a Chinese case page with its Chinese version taken out.

        The pages the other builders write name the version in Chinese, in the
        line under the title -- the built ``case-00102.zh.html`` writes it three
        times -- and state a version-6 phrase in the record's own English. So
        this is that page's visible text, held to stating one of the phrases and
        to naming the version, and then the same text with every Chinese mention
        of the version taken out, which :func:`names_version_six` must refuse.
        """
        text = visible_text(self.raw["case-00102.zh.html"])
        self.assertTrue(
            any(phrase in text for phrase in VERSION_SIX_PHRASES),
            "case-00102.zh.html states none of the version-6 phrases",
        )
        self.assertTrue(
            names_version_six(text),
            "case-00102.zh.html names no version",
        )
        stripped = text.replace("\u7b2c 6 \u7248", "")
        self.assertNotEqual(text, stripped, "the fixture did not remove the version")
        self.assertFalse(
            names_version_six(stripped),
            "the copy names version 6 after every mention was removed",
        )


class TheChinesePagesLinkTests(unittest.TestCase):
    """No Chinese page source sends a reader to an English page's own twin.

    Every page a Chinese reader can be sent to has a Chinese twin. Version 8 is
    the policy the submission applies: the index at ``v8-cases.zh.html`` and each
    case at ``v8-<NNNNN>.zh.html``. And since part 106 the 151 version-6 case
    pages are written in both languages too, so each case is at
    ``case-<NNNNN>.zh.html`` as well. A Chinese page that linked to the English
    one would send a Chinese reader to a page in the other language where the
    page in theirs exists, so this reads the pages' own source -- which is where
    the links are written -- and refuses it.
    """

    LINK_RE = re.compile(r'href="((?:v8|case)-[^"]+\.html)"')

    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = {
            source.name: source.read_text(encoding="utf-8")
            for source in site.page_sources()
            if source.name.endswith(".zh.html")
        }

    def english_links(self, markup: str) -> Tuple[str, ...]:
        """Every ``v8-*.html`` or ``case-*.html`` link a source carries twinless."""
        return tuple(
            href
            for href in self.LINK_RE.findall(markup)
            if not href.endswith(".zh.html")
        )

    def test_no_chinese_page_links_to_an_english_version_eight_page(self) -> None:
        self.assertTrue(self.sources, "the site's sources hold no Chinese page")
        for name, markup in sorted(self.sources.items()):
            found = self.english_links(markup)
            with self.subTest(page=name):
                self.assertEqual(
                    (),
                    found,
                    "{0} links to {1}".format(name, ", ".join(found)),
                )

    def test_the_check_fails_on_a_page_carrying_the_old_link(self) -> None:
        """The control: index.zh.html with one link put back is reported.

        The page linked to the English ``v8-05051.html`` twice before part 105;
        this is its own source with one of those put back, and the check above
        must report it.
        """
        markup = self.sources["index.zh.html"]
        self.assertNotIn('href="v8-05051.html"', markup)
        restored = markup.replace(
            'href="v8-05051.zh.html"', 'href="v8-05051.html"', 1
        )
        self.assertNotEqual(markup, restored, "the fixture did not restore the link")
        self.assertEqual(
            ("v8-05051.html",),
            self.english_links(restored),
            "the copy is reported as {0!r}".format(self.english_links(restored)),
        )

    def test_the_check_fails_on_a_page_carrying_the_old_case_link(self) -> None:
        """The control: index.zh.html with one case link put back is reported.

        The page linked to the English ``case-00208.html`` before part 106, when
        the version-6 case pages were English only; this is its own source with
        that link put back, and the check above must report it.
        """
        markup = self.sources["index.zh.html"]
        self.assertNotIn('href="case-00208.html"', markup)
        restored = markup.replace(
            'href="case-00208.zh.html"', 'href="case-00208.html"', 1
        )
        self.assertNotEqual(markup, restored, "the fixture did not restore the link")
        self.assertEqual(
            ("case-00208.html",),
            self.english_links(restored),
            "the copy is reported as {0!r}".format(self.english_links(restored)),
        )


class TheVersionEightGateTests(unittest.TestCase):
    """The rule the gate counts are read by, held against the committed run.

    ``ui.site.figures.version_eight_escalations`` states its rule in its own
    docstring: a case the version-8 gate stopped has **no vote** in its
    transcript and a ruling explanation that opens "Under <clause>", and every
    other escalated case was asked of the judge. These are that rule read
    independently, and the cross-check that the five lanes cover the run's own
    escalation count -- the figure ``eval.v8_report`` measures.
    """

    @classmethod
    def setUpClass(cls) -> None:
        portability.require_the_same_libm()
        cls.counts = figures.version_eight_escalations()
        cls.run_dir = figures.version_eight_run_dir()
        cls.cases = sorted(development_sets.named(figures.V8_SET).cases)
        cls.measured = figures.version_eight_measurements()

    def escalated(self) -> Tuple[Tuple[int, Dict, Dict], ...]:
        """Every case the run published as an escalation, with its own record."""
        found = []
        for case_no in self.cases:
            document = json.loads(
                (self.run_dir / "case-{0:05d}.json".format(case_no)).read_text(
                    encoding="utf-8"
                )
            )
            transcript = json.loads(
                (self.run_dir / document["transcript_file"]).read_text(
                    encoding="utf-8"
                )
            )
            ruling = figures._inner_ruling(document)
            if ruling.get("ruling") == pipeline_module.ESCALATE:
                found.append((case_no, ruling, transcript))
        return tuple(found)

    def test_a_gated_case_has_no_vote_and_opens_with_its_clause(self):
        for case_no, ruling, transcript in self.escalated():
            if "vote" in transcript:
                continue
            with self.subTest(case=case_no):
                match = figures.V8_GATE_OPENING_RE.match(
                    str(ruling.get("explanation") or "")
                )
                self.assertIsNotNone(
                    match,
                    "case {0}'s explanation does not open with a clause".format(case_no),
                )
                assert match is not None
                self.assertIn(match.group(1), figures.V8_GATE_CLAUSES)

    def test_a_case_the_judge_was_asked_is_never_counted_in_a_gate_lane(self):
        asked = [case_no for case_no, _r, t in self.escalated() if "vote" in t]
        gated = [case_no for case_no, _r, t in self.escalated() if "vote" not in t]
        self.assertEqual(len(asked) + len(gated), len(self.escalated()))
        self.assertEqual(
            self.counts["panel"] + self.counts["no_majority"], len(asked)
        )
        self.assertEqual(
            self.counts["2km"] + self.counts["value"] + self.counts["safety"],
            len(gated),
        )

    def test_the_five_lanes_cover_the_run_s_own_escalation_count(self):
        self.assertEqual(sum(self.counts.values()), self.measured.escalated_produced)

    def test_a_clause_the_gate_does_not_state_is_refused(self):
        with self.assertRaises(KeyError):
            figures._gate_limb("Under POL-XX-99, the case goes to a person.")
        with self.assertRaises(KeyError):
            figures._gate_limb("the judge was asked")


if __name__ == "__main__":
    unittest.main()
