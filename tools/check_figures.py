"""One figure, one value everywhere: every headline figure against every place.

A figure that is stated in eight documents and eleven built pages is a figure
that can come to say one thing in one place and something else in another, and
nothing in this repository would say so: the run is correct, the page is a page,
and a reader who reads only one of the two never sees the disagreement. This
command closes that gap. It computes each headline figure from the committed
runs with the same functions ``ui/site/figures.py`` uses -- it does not recompute
anything differently -- and then reads every document and built page that states
it and reports whether the value there is the computed one.

**What is computed, and from where.** The medians and the percentiles come from
:func:`ui.site.figures.figures`, which reads the four version-6 runs through
:mod:`eval.business_value` and :mod:`eval.v6_runs`; the position swap's two
figures come from :mod:`eval.fairness`; the sealed and held-out sets come from
the same graded reads ``tests/test_readme_figures.py`` makes; the version-7 and
version-8 figures come from the same :func:`eval.run_benchmark.grade_run` call
over the directory each of those runs was written to; and the four version-8
measurements -- decided with no person, the position swap, the calibration error
and the draft count -- come from :func:`eval.v8_report.figures`, which measures
them off the same two runs; and the one figure that is not a measurement of a run
-- the count of tests that read the repository's git history -- comes from
:func:`tests_that_read_the_git_history`, which counts them in the test modules'
own source, because this command runs no tests. No figure is typed in here and no
figure is read from a second copy of itself.

**How a figure is found.** Each figure carries a table of patterns, one per way
the documents spell it -- ``160.4 s`` in one, ``2.7 min`` in another, ``2.7``
followed by the Chinese unit in a third. Every pattern has a capture group, and
every captured value must be one of the figure's accepted spellings; a value
that is not is reported as a mismatch, which is what makes the check able to fail
when a document is edited to say ``160.5``. A pattern that matches nothing
anywhere is reported too: a pattern that has died is a place nobody is checking.
The table is ASCII only, so the Chinese patterns are written as ``\\uXXXX``
escapes and the module carries no Han character.

**The claims, which are sentences rather than values.** A figure is a number and
a claim is a sentence a document may not make -- three about version 8 were found
on 2026-10-14 that the runs themselves contradict. :data:`CLAIMS` names the
documents each is read in, a pattern a line must match for the claim to speak
about it, and a pattern the line must then not match. A hit is reported the way a
mismatched figure is, and a claim is written so that the version-7 sentence it
resembles (``the panel split 2-2``) is left alone.

**No model call, no network.** Every reading is a committed run, a committed key
or a built page. Run from the project root with::

    python3 -m tools.check_figures --report
"""

from __future__ import annotations

import argparse
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Mapping, NamedTuple, Optional, Sequence, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import (  # noqa: E402
    development_sets,
    fairness,
    run_benchmark,
    v6_runs,
    v8_report,
)
from ui.site import figures as site_figures  # noqa: E402

MODEL = run_benchmark.resolve_model(None)


# --------------------------------------------------------------------------
# The documents that state a figure
# --------------------------------------------------------------------------
# The README and the record, the submission texts, the five judge documents
# part 55 adds, and the three built pages the product site publishes (each in
# English and Chinese). A figure stated in a file not named here is a figure
# this command does not check, and the report says so by not listing it.
DOCUMENTS: Tuple[str, ...] = (
    "README.md",
    "docs/record.md",
    "docs/submission/description.md",
    "docs/submission/description-form.txt",
    "docs/submission/qa.md",
    "docs/submission/blurb.md",
    "docs/why-debate.md",
    "docs/scale.md",
    "docs/integration.md",
    "docs/data.md",
    "docs/submission/demo-script.md",
    "ui/dist/index.html",
    "ui/dist/results.html",
    "ui/dist/how-it-works.html",
    "ui/dist/index.zh.html",
    "ui/dist/results.zh.html",
    "ui/dist/how-it-works.zh.html",
    "ui/dist/safety.html",
    "ui/dist/safety.zh.html",
    # The note part 90 adds, which states the table `eval.v8_report --report`
    # prints. It is named here so the version-8 measurements below are read out
    # of the document that states them rather than out of nothing.
    "docs/notes/2026-10-14-version-8-measurements.md",
)


class Figure(NamedTuple):
    """One figure: how it is spelled, and the patterns that find it.

    ``spellings`` are the accepted forms of the value, normalised (a trailing
    ``.0`` dropped), and they are what a captured value is compared with.
    ``patterns`` are regular expressions, each with at least one capture group;
    the group is the value a document states and is compared with the spellings.
    The value itself is not stored here: it is computed from the committed runs
    by :func:`computed`, so there is one copy of it and not two.
    """

    name: str
    spellings: Tuple[str, ...]
    patterns: Tuple[str, ...]


# --------------------------------------------------------------------------
# The figures, and how the documents spell them
# --------------------------------------------------------------------------
FIGURES: Tuple[Figure, ...] = (
    Figure(
        "median time to a decision",
        ("160.4", "2.7"),
        (
            r"\*\*(\d+\.\d+) s\*\* median",
            r"median wall clock \| (\d+\.\d+) s",
            r"(\d+\.\d+) s median time",
            r"median time to a decision of (\d+\.\d+) seconds",
            r"median of (\d+\.\d+) seconds",
            r"decision of (\d+\.\d+) s and a 90th",
            r"class=\"big\">(\d+\.\d+) s</span><h3>",
            r"num\">(\d+\.\d+)<small>min</small>",
            r"num\">(\d+\.\d+)<small>\u5206\u949f</small>",
            r"in (\d+\.\d+) min at the median",
            r"At the (\d+\.\d+) s median",
            r"(\d+\.\d+) s; p90",
        ),
    ),
    Figure(
        "90th percentile time to a decision",
        ("286.9", "4.8"),
        (
            r"median, (\d+\.\d+) s at the 90th percentile",
            r"90th percentile wall clock \| (\d+\.\d+) s",
            r"p90 of (\d+\.\d+)\s+seconds",
            r"90th percentile\s+of (\d+\.\d+)\s+seconds",
            r"90th percentile of (\d+\.\d+) s",
            r"p90 (\d+\.\d+) s",
            r"within (\d+\.\d+) minutes",
            r"(\d+\.\d+) \u5206\u949f\u5185\u5b8c\u6210",
        ),
    ),
    Figure(
        "median model cost per case",
        ("0.0579", "0.058"),
        (
            r"\*\*(\d+\.\d+) USD\*\* median",
            r"published prices \| (\d+\.\d+) USD",
            r"the median (\d+\.\d+) USD",
            r"at the median, (\d+\.\d+) USD",
            r"t the (\d+\.\d+) USD median",
            r"(\d+\.\d+) USD median",
            r"cost per case is (\d+\.\d+)\s+USD",
            r"published prices is (\d+\.\d+)",
            r"class=\"big\">\$(\d+\.\d+)</span><h3>Model cost",
            r"num\">\$(\d+\.\d+)</div>",
            r"src\">(\d+\.\d+) USD</span>",
            r"\u4e2d\u4f4d\u6570 (\d+\.\d+) \u7f8e\u5143",
        ),
    ),
    Figure(
        "cases decided automatically",
        ("112",),
        (
            r"\*\*(\d+) of 151\*\*",
            r"Decided automatically \| (\d+)/151 = ",
            r"the 151, (\d+) are decided",
            r"class=\"big\">(\d+)</span><h3>Decided and executed",
            r"class=\"big\">(\d+)</span><h3>\u5224\u51b3\u5e76\u6267\u884c",
            r"src\">(\d+) / 151</span>",
        ),
    ),
    Figure(
        "cases held for release",
        ("13",),
        (
            r"(\d+) ruled but above SGD 8",            r"(\d+) are decided with the amount held",
            r"class=\"big\">(\d+)</span><h3>Decided, money held",
            r"class=\"big\">(\d+)</span><h3>\u5df2\u5224\u51b3\uff0c\u6b3e\u9879\u51bb\u7ed3",
        ),
    ),
    Figure(
        "cases with no ruling",
        ("26",),
        (
            r"\| (\d+) with no ruling",
            r"class=\"big\">(\d+)</span><h3>No ruling issued",
            r"class=\"big\">(\d+)</span><h3>\u4e0d\u51fa\u5224\u51b3",
        ),
    ),
    Figure(
        "cases in the four runs",
        ("151",),
        (
            r"\*\*112 of (\d+)\*\*",
            r"112/(\d+) = ",
            r"Of the (\d+), 112 are decided",
            r"(\d+) version-6 cases",
            r"(\d+) \u4e2a\u7b2c 6 \u7248\u6848\u5b50",
        ),
    ),
    Figure(
        "share decided automatically",
        ("74.2", "74"),
        (
            r"\*\*112 of 151\*\* \((\d+\.\d)%\)",
            r"112/151 = (\d+\.\d)%",
            r"executed \((\d+\.\d)%\)",
            r"num\">(\d+)%</div>",
        ),
    ),
    Figure(
        "position swap, all four graded fields",
        ("136",),
        (
            r"graded fields in (\d+) of 141",
            r"graded fields \| (\d+)/141 = ",
            r"graded fields in (\d+) and on the ruling",
            r"class=\"big\">(\d+)/141</span>",
        ),
    ),
    Figure(
        "position swap, the ruling alone",
        ("139",),
        (
            r"on the ruling alone in (\d+)",
        ),
    ),
    Figure(
        "inject-v1, attacks",
        ("6",),
        (
            r"(\d+) attacks: ",
            r"(\d+) attack tests",
            r"(\d+) tries: ",
            r"(\d+) \u6b21\u653b\u51fb\uff1a",
            r"(\d+) \u6b21\u653b\u51fb\u6d4b\u8bd5",
        ),
    ),
    Figure(
        "inject-v1, rulings flipped",
        ("0",),
        (
            r"class=\"big\">(\d+)</span><h3>rulings flipped",
            r"(\d+) rulings flipped \(",
            r"data-count=\"(\d+)\">\d+</span></div><p>rulings flipped",
            r"class=\"big\">(\d+)</span><h3>\u4e2a\u5224\u51b3\u88ab\u6539",
            r"(\d+) \u4e2a\u5224\u51b3\u88ab\u6539\u53cd",
            r"data-count=\"(\d+)\">\d+</span></div><p>\u4e2a\u5224\u51b3\u88ab",
        ),
    ),
    Figure(
        "inject-v1, rulings unchanged",
        ("5",),
        (
            r"(\d+) rulings unchanged",
            r"(\d+) had no effect",
            r"\((\d+) unchanged",
            r"(\d+) unchanged",
            r"(\d+) \u4e2a\u4e0d\u53d8",
            r"(\d+) \u6b21\u65e0\u6548",
        ),
    ),
    Figure(
        "inject-v1, sent to a person",
        ("1",),
        (
            r"(\d+) sent to a person, none flipped",
            r"(\d+) was sent to a person",
            r"(\d+) sent to a person\)",
            r"tries: \d+ unchanged, (\d+) sent to a person",
            r"(\d+) \u4e2a\u8f6c\u4eba\u5de5",
            r"(\d+) \u6b21\u8f6c\u7ed9\u4eba",
        ),
    ),
    Figure(
        "dev-v2-ext, four-field exact",
        ("115",),
        (
            r"`dev-v2-ext`\s+(\d+)/120",
            r"\| (\d+)/120 = 95\.8% \|",
            r">(\d+)/120, Wilson",
        ),
    ),
    Figure(
        "dev-v2-ext, Wilson 95% interval",
        ("90.6", "98.2"),
        (
            r"\| \[(\d+\.\d)%, (\d+\.\d+)%\] \| `runs/dev-v2-ext",
            r"/120, Wilson (\d+\.\d)-(\d+\.\d)%",
        ),
    ),
    Figure(
        "corpus at version 6, four-field exact",
        ("26",),
        (
            r"corpus\s+(\d+)/29",
            r"\| (\d+)/29 = 89\.7% \|",
            r">(\d+)/29 \(107",
            r"(\d+)/29 at version 6",
        ),
    ),
    Figure(
        "sealed-v2, four-field agreement",
        ("12",),
        (
            r"\| (\d+)/12 \|",
            r"\| (\d+)/12 = 100\.0% \|",
            r"graded fields in (\d+)/12 = 100",
            r"(\d+)/12 = 100\.0%",
            r"class=\"big\">(\d+)/12</span>",
            r"num\">(\d+)/12</div>",
        ),
    ),
    Figure(
        "sealed-v2, Wilson 95% interval",
        ("75.8", "100"),
        (
            r"\| 12/12 \| \[(\d+\.\d)%, (\d+\.\d+)%\]",
            r"\| 12/12 = 100\.0% \| \[(\d+\.\d)%, (\d+\.\d+)%\]",
            r"12/12 = 100\.0%, Wilson 95% \[(\d+\.\d)%, (\d+\.\d+)%\]",
            r"interval \| \[(\d+\.\d)%, (\d+\.\d+)%\] \| `runs/sealed-v2",
            r"sealed-v2, Wilson 95% \[(\d+\.\d)%, (\d+)%\]",
        ),
    ),
    Figure(
        "sealed-v1, four-field agreement",
        ("21",),
        (
            r"\| (\d+)/24 \(20/24",
            r"\| (\d+)/24 = 87\.5%, and",
            r"\| (\d+)/24 = 87\.5% \|",
            r"table below: (\d+)/24",
            r"agrees in (\d+)/24 = 87\.5%",
            r"(\d+)/24 = 87\.5%",
            r"class=\"big\">(\d+)/24</span>",
            r"rather than (\d+)/24",
        ),
    ),
    Figure(
        "sealed-v1, the key as imported",
        ("20",),
        (
            r"\((\d+)/24 under the key as imported\)",
            r"and (\d+)/24 = 83\.3%",
            r"under the key as imported \| (\d+)/24 = 83\.3%",
            r"the same run is (\d+)/24",
            r"is the (\d+)/24 above",
            r"and is (\d+)/24 under the key as imported",
            r"is (\d+)/24 rather than",
            r"(\d+)/24 against the answers as first written",
            r"\u7b97\u662f (\d+)/24",
        ),
    ),
    Figure(
        "wild-v2, four-field exact",
        ("18",),
        (
            r"`wild-v2` \(20 cases\) \| (\d+)/20",
            r"\| (\d+)/20 = 90\.0% \|",
            r"class=\"big\">(\d+)/20</span>",
            r"so (\d+)/20 is read as",
        ),
    ),
    # ----------------------------------------------------------------------
    # Policy version 7 -- Ryde's own Dispute Resolution Policy v2.1
    # ----------------------------------------------------------------------
    # Three sets, one run each, and none of them pooled with another. The
    # patterns are anchored on the set's own name and case count rather than on
    # the number alone, because 30/30 and 100.0% are values other rows carry:
    # an unanchored interval pattern would capture sealed-v2's [75.8%, 100.0%]
    # and report it as a mismatch.
    Figure(
        "sealed-v4, four-field agreement",
        ("30/30",),
        (
            r"`sealed-v4` \(30 cases\) \| (\d+/30) \|",
            r"`sealed-v4` \(30 cases\) \| (\d+/30) = 100\.0% \|",
            r"graded fields in\s+(\d+/30) = 100\.0%",
        ),
    ),
    Figure(
        "sealed-v4, Wilson 95% interval",
        ("88.6", "100"),
        (
            r"`sealed-v4` \(30 cases\) \| \d+/30 \| \[(\d+\.\d)%, (\d+\.\d+)%\]",
            r"`sealed-v4` \(30 cases\) \| \d+/30 = 100\.0% \| \[(\d+\.\d)%, (\d+\.\d+)%\]",
            r"30/30 = 100\.0%, Wilson 95% \[(\d+\.\d)%, (\d+\.\d+)%\]",
        ),
    ),
    Figure(
        "ryde-v7, samples matching Ryde's stated outcomes",
        ("1 of 2",),
        (
            r"`ryde-v7` \(2 cases\) \| (1 of 2) against Ryde's stated outcomes",
        ),
    ),
    Figure(
        "dev-v7, four-field agreement",
        ("40/40",),
        (
            r"`dev-v7` \(40 cases\) \| (\d+/40) \|",
            r"`dev-v7` \(40 cases\) \| (\d+/40) = 100\.0% \|",
            r"`dev-v7` (\d+/40) \(development data\)",
            r"dev-v7 (\d+/40) \(development data\)",
        ),
    ),
    Figure(
        "version-7 sealed run, median time to a decision",
        ("139.8",),
        (
            r"At version 7\*\* the sealed run's own median is \*\*(\d+\.\d+) s\*\* a case",
        ),
    ),
    Figure(
        "version-7 sealed run, median model cost",
        ("0.0398",),
        (
            r"At version 7\*\* the sealed run's own median is \*\*[\d.]+ s\*\* a case,"
            r" with a median\s+model cost of \*\*(\d+\.\d+) USD\*\* a case",
        ),
    ),
    # ----------------------------------------------------------------------
    # Policy version 8 -- v2.1 with Ryde's answers of 2026-10-14
    # ----------------------------------------------------------------------
    # Two sets, one run each, never pooled with another. The patterns are
    # anchored on the set's own name and case count rather than on the number
    # alone, because ``1 of 2`` and ``39/40`` are values other rows could
    # carry: the version-7 medians' own patterns are anchored on "At version 7"
    # for the same reason, so the version-8 medians below cannot capture for
    # them.
    Figure(
        "ryde-v8, samples matching Ryde's stated outcomes",
        ("1 of 2",),
        (
            r"`ryde-v8` \(2 cases\) \| (1 of 2) against Ryde's stated outcomes",
            r"keyed by Ryde's stated\s+outcome as\s+amended by\s+Ryde's answer of"
            r" 2026-10-14, is (1 of 2):",
            r"stated outcomes as amended by Ryde's\s+answer of 2026-10-14"
            r" \(`ryde-v8`\), are (1 of 2):",
            # the record's own glance table
            r"\| agreement, `ryde-v8` \| (1 of 2) \|",
        ),
    ),
    Figure(
        "dev-v8, four-field agreement",
        ("39/40",),
        (
            r"`dev-v8` \(40 cases\) \| (\d+/40) \|",
            r"`dev-v8` (\d+/40) and `dev-v7`",
            r"dev-v8 (\d+/40) and dev-v7",
            # the record's own glance table
            r"\| agreement, `dev-v8` \| (\d+/40) \|",
        ),
    ),
    Figure(
        "dev-v8, median time to a decision",
        ("153.1",),
        (
            r"Median time to a decision (\d+\.\d+) s a case",
            # the README's version-8 table, and the record's own glance table
            r"a median of \*\*(\d+\.\d+) s\*\* a case",
            r"a median of (\d+\.\d+) s a case",
            # the product site's own statements of the same measurement
            r"median of (\d+\.\d+) s is slow for a chat reply",
            r"(\d+\.\d+) s at the median and \d+\.\d+ s at the 90th",
            r"\u4e2d\u4f4d (\d+\.\d+) s\uff0c\u7b2c 90",
            r"\u4e2d\u4f4d (\d+\.\d+) s \u5bf9\u804a\u5929",
            r"\(\u4e2d\u4f4d (\d+\.\d+) s\)",
        ),
    ),
    Figure(
        "dev-v8, 90th percentile time to a decision",
        ("299.4",),
        (
            r"and (\d+\.\d+) s at the 90th percentile",
            r"\u7b2c 90 \u767e\u5206\u4f4d (\d+\.\d+) s",
        ),
    ),
    Figure(
        "dev-v8, the median in minutes",
        ("2.6",),
        (
            r"class=\"big\">(\d+\.\d+) min</span><h3>Median per case",
        ),
    ),
    Figure(
        "dev-v8, median model cost",
        ("0.039",),
        (
            r"a median model cost of \*\*(\d+\.\d+) USD\*\* a case",
            r"a median model cost of (\d+\.\d+) USD a case",
            r"(\d+\.\d+) USD of model cost a case",
            r"\u6a21\u578b\u6210\u672c\u4e2d\u4f4d\u6570 (\d+\.\d+) USD",
        ),
    ),
    # The no-show sample's four version-8 drafts, counted by what each one did.
    # The sentence the pattern reads is the one every place 903 is described at
    # version 8 uses, so a document that counts the drafts differently -- three
    # that escalated, two that upheld the fee -- captures a word that is not one
    # of the figure's spellings and is reported.
    Figure(
        "ryde-v8, 903's drafts counted by outcome",
        ("two", "one"),
        (
            r"(two)\s+drafts\s+escalated,\s+(one)\s+upheld\s+the\s+fee\s+and\s+"
            r"(one)\s+was\s+voided\s+for\s+citing\s+a\s+clause\s+version\s+8\s+"
            r"does\s+not\s+have;\s+three\s+must\s+agree",
        ),
    ),
    # ----------------------------------------------------------------------
    # The version-8 measurements part 90 adds, read by ``eval.v8_report``
    # ----------------------------------------------------------------------
    # Four figures off the same run the version-8 rows above read, measured
    # there rather than recomputed here: the value is
    # :func:`eval.v8_report.figures`, and every pattern reads the note that
    # states the table ``python3 -m eval.v8_report --report`` prints. Each is
    # anchored on the row's own label, so the ``dev-v8`` and ``ryde-v8`` columns
    # of one row cannot capture for each other -- ``decided with no person`` is
    # ``28 of 40`` and ``0 of 2`` on the same line.
    Figure(
        "dev-v8 decided with no person",
        ("28 of 40",),
        (
            r"\| decided with no person \| (\d+ of 40)\b",
            r"(\d+ of 40) ruled by the AI",
            r"class=\"big\">(\d+ of 40)</span><h3>Ruled by the AI",
        ),
    ),
    Figure(
        "dev-v8 position swap",
        ("33 of 34", "33"),
        (
            r"\| position swap, all four fields \| (\d+ of 34)\b",
            r"data-count=\"(\d+)\">\d+</span><small> of 34",
            r"(\d+ of 34) at version 8",
            # the submission texts' own pain-point table
            r"in (\d+ of 34) cases",
            r"class=\"big\">(\d+ of 34)</span><h3>Agreed when the sides were swapped",
        ),
    ),
    Figure(
        "dev-v8 ECE",
        ("0.097",),
        (
            r"\| valid drafts, ECE \| \d+, (\d+\.\d+)\b",
            r"Expected calibration error (\d+\.\d+) over",
            r"\u671f\u671b\u6821\u51c6\u8bef\u5dee (\d+\.\d+)\uff0c\u57fa\u4e8e",
        ),
    ),
    Figure(
        "dev-v8 drafts",
        ("139",),
        (
            r"\| valid drafts, ECE \| (\d+)\b",
            r"over (\d+) drafts, at the version-8 bar",
            r"\u57fa\u4e8e (\d+) \u4efd\u8349\u7a3f",
        ),
    ),
    Figure(
        "dev-v8, cases that went to a person",
        ("12",),
        (
            r"(\d+) to a person --",
            r"(\d+) went to a person:",
            r"(\d+) \u4e2a\u4ea4\u7ed9\u4eba\uff1a",
            r"(\d+) \u4e2a\u4ea4\u7ed9\u4eba\u2014\u2014",
        ),
    ),
    Figure(
        "dev-v8, the gate's cases",
        ("5",),
        (
            r"(\d+) stopped by a v2.1 rule before the judge",
            r"the three limbs stopped (\d+) between them",
            r"\u4e09\u4e2a\u9650\u5236\u5171\u62e6\u4e0b (\d+) \u4e2a",
        ),
    ),
    Figure(
        "dev-v8, the gate's 2 km limb",
        ("2",),
        (
            r"(\d+) on the 2 km limit",
            r"(\d+) \u4e2a\u51fa\u5728 2 \u516c\u91cc\u4e0a\u9650",
        ),
    ),
    Figure(
        "dev-v8, the gate's value limb",
        ("1",),
        (
            r"(\d+) on the value",
            r"(\d+) \u4e2a\u51fa\u5728\u91d1\u989d",
        ),
    ),
    Figure(
        "dev-v8, the gate's safety limb",
        ("2",),
        (
            r"(\d+) on a safety flag",
            r"(\d+) \u4e2a\u51fa\u5728\u5b89\u5168\u6807\u8bb0",
        ),
    ),
    Figure(
        "dev-v8, the panel's escalations",
        ("6",),
        (
            r"(\d+) the panel sent on",
        ),
    ),
    Figure(
        "dev-v8, the panels without a majority",
        ("1",),
        (
            r"(\d+) without a majority",
        ),
    ),
    Figure(
        "dev-v8, route deviation limit",
        ("2",),
        (
            r"route deviation over (\d+) km",
            r"over the (\d+) km an AI may rule on",
            r"\u7ed5\u8def\u8d85\u8fc7 (\d+) \u516c\u91cc",
            r"\u53ef\u4ee5\u88c1\u51b3\u7684 (\d+) km",
        ),
    ),
    Figure(
        "dev-v8, the value a person decides above",
        ("50",),
        (
            r"over SGD (\d+)",
        ),
    ),
    Figure(
        "dev-v8, confidence the policy asks",
        ("0.8",),
        (
            r"\((\d+\.\d+); 0\.95 with a fraud flag\)",
            r"\uff08(\d+\.\d+)\uff1b\u5e26\u6b3a\u8bc8\u6807\u8bb0\u65f6 0\.95\uff09",
            r"the version-8 bar of (\d+\.\d+)",
            # the README's own row, which spells the same bar out
            r"\((\d+\.\d+); 0\.95 where a party carries a fraud flag",
        ),
    ),
    Figure(
        "case 5051, evidence items",
        ("7",),
        (
            r"Case 5051: (\d+) pieces of evidence",
            r"\u6848\u4f8b 5051\uff1a(\d+) \u9879\u8bc1\u636e",
        ),
    ),
    Figure(
        "case 5051, the rider's and the driver's points",
        ("3", "8"),
        (
            r"Case 5051: (\d+) points for the rider, (\d+) for the driver",
            r"\u6848\u4f8b 5051\uff1a\u4e58\u5ba2\u65b9\u63d0\u4e86 (\d+) \u70b9\uff0c\u53f8\u673a\u65b9 (\d+) \u70b9",
        ),
    ),
    Figure(
        "case 5051, claims kept",
        ("10/11",),
        (
            r"Case 5051: (\d+/\d+) claims kept",
            r"\u4e3b\u5f20\u4fdd\u7559 (\d+/\d+)",
        ),
    ),
    Figure(
        "case 5051, the dropped point",
        ("1",),
        (
            r"Case 5051: (\d+) of \d+ points thrown out",
            r"\u6848\u4f8b 5051\uff1a\d+ \u70b9\u91cc\u6709 (\d+) \u70b9",
        ),
    ),
    Figure(
        "case 5051, the amount to the driver",
        ("SGD 5.00",),
        (
            r"driver paid (SGD \d+\.\d+)",
            r"\u53f8\u673a\u83b7 (SGD \d+\.\d+)",
        ),
    ),
    Figure(
        "case 5051, the wall clock",
        ("254.8",),
        (
            r"to the driver, (\d+\.\d+)&nbsp;s",
            r"\u7528\u65f6 (\d+\.\d+)&nbsp;s",
        ),
    ),
    Figure(
        "case 5051, the wait and the free wait",
        ("345", "300"),
        (
            r"waited (\d+) s from the wait's start to the cancellation, (\d+) s of it free",
            r"\u5171\u7b49\u4e86 (\d+) \u79d2\uff0c\u5176\u4e2d (\d+) \u79d2\u662f\u514d\u8d39\u7b49\u5f85",
        ),
    ),
    Figure(
        "version-8 case pages",
        ("42",),
        (
            r"All (\d+) version-8 cases",
            r"\u5168\u90e8 (\d+) \u9053\u7b2c 8 \u7248\u6848\u4ef6",
        ),
    ),
    Figure(
        "sealed-v4, cases that needed a person",
        ("9",),
        (
            r"all (\d+) cases that needed a person got one",
            r"(\d+) \u4e2a\u8be5\u4ea4\u7ed9\u4eba\u7684\u6848\u5b50\u90fd\u4ea4\u4e86",
        ),
    ),
    # The tests that read the repository's git history. It is counted from the
    # test modules' own source -- this command runs no tests -- and the rule is
    # written out in ``tests_that_read_the_git_history``. The README states the
    # count as a numeral and the record spells it out, so both spellings are
    # accepted and both are read.
    Figure(
        "tests that read the git history",
        ("29", "Twenty-nine"),
        (
            r"(\d+) tests read the git history",
            r"(Twenty-nine) of the tests read the repository's git history",
        ),
    ),
)

# The figures by name, so the report and the tests can name one.
BY_NAME: Dict[str, Figure] = {figure.name: figure for figure in FIGURES}


# --------------------------------------------------------------------------
# The claims: sentences a named document may not make
# --------------------------------------------------------------------------
# A figure is a value; a claim is a sentence. Three claims about version 8 were
# found in the documents on 2026-10-14 that the runs themselves contradict, and
# this table holds them closed: a line that says one of them is reported the way
# a mismatched figure is. Each claim names the documents it reads and a pattern
# the line must match for the claim to speak about it, so a sentence that is
# true at version 7 (``the panel split 2-2``) is left alone while the same words
# at version 8 are a finding.
class Claim(NamedTuple):
    """One thing no line of a named document may say.

    ``files`` are the documents the claim reads. ``applies`` are regular
    expressions a line must **all** match for the claim to speak about it; an
    empty tuple means every line. ``forbidden`` are regular expressions a line
    the claim speaks about must not match.
    """

    name: str
    files: Tuple[str, ...]
    applies: Tuple[str, ...]
    forbidden: Tuple[str, ...]


# The submission texts, the whole directory: each carries the version-8 summary.
SUBMISSION_DOCUMENTS: Tuple[str, ...] = (
    "docs/submission/blurb.md",
    "docs/submission/demo-script.md",
    "docs/submission/description-form.txt",
    "docs/submission/description.md",
    "docs/submission/how-we-built-it.md",
    "docs/submission/qa.md",
)

# The documents a version-8 claim is read in. The two built pages under ``ui/``
# state the version-8 samples too, but ``ui/`` is frozen for this part, so they
# are named here neither as a claim nor as a figure document for these claims.
VERSION_EIGHT_CLAIM_DOCUMENTS: Tuple[str, ...] = (
    "README.md",
    "docs/record.md",
) + SUBMISSION_DOCUMENTS + (
    "docs/notes/2026-10-14-version-8-runs.md",
)

CLAIMS: Tuple[Claim, ...] = (
    Claim(
        "version-8 903 is not a 2-2 split",
        VERSION_EIGHT_CLAIM_DOCUMENTS,
        (r"ryde-v8|version 8", r"903"),
        (r"2-2", r"2:2"),
    ),
    Claim(
        "v2.1 does not route a fare dispute to a person",
        VERSION_EIGHT_CLAIM_DOCUMENTS
        + ("data/external/ryde-v7/README.md", "tests/test_ryde_v7.py"),
        (),
        (r"v2\.1[^\n]{0,80}?(?:route|send)\w*[^\n]{0,80}?fare\s+dispute",),
    ),
)


# --------------------------------------------------------------------------
# The computed values
# --------------------------------------------------------------------------
_COMPUTED: "Optional[Dict[str, str]]" = None


def graded_version_seven(name: str) -> "grade.GradeReport":
    """One registered set's committed run, graded against its own key.

    The same :func:`eval.run_benchmark.grade_run` call the sealed and held-out
    sets are graded with, over the directory the run was **written to**: the
    version-7 pair ``dev-v7`` and ``ryde-v7`` and the version-8 pair ``dev-v8``
    and ``ryde-v8`` are registered for a policy base, so their runs sit one
    level down (``runs/<set>/policy-<version>/<model>/``) and the un-versioned
    path holds nothing. The name is the one ``ui/site/figures.py`` cites, and
    the read is the same for a set at either policy version.
    """
    development_set = development_sets.named(name)
    return run_benchmark.grade_run(
        development_sets.run_dir_at_its_version(development_set, MODEL),
        development_set.key(),
        case_loader=development_set.load_case,
        policy_version=development_set.policy_version,
    )


def case_cost(document: Mapping[str, object]) -> Decimal:
    """One case's model cost at the prices ``eval.v6_runs`` bills at.

    The same three prices and the same arithmetic that module's own cost line
    uses, so a version-7 cost figure is the one ``eval.v6_runs`` would print
    for those tokens rather than a second reading of them.
    """
    tokens = document.get("tokens") or {}
    prompt = int(tokens.get("prompt_tokens", 0))
    cached = int(tokens.get("cached_tokens", 0))
    completion = int(tokens.get("completion_tokens", 0))
    return (
        Decimal(prompt - cached) * v6_runs.PRICE_INPUT
        + Decimal(cached) * v6_runs.PRICE_CACHED_INPUT
        + Decimal(completion) * v6_runs.PRICE_OUTPUT
    ) / v6_runs.MILLION


# --------------------------------------------------------------------------
# The tests that read the repository's git history
# --------------------------------------------------------------------------
# The test modules whose whole subject is a record read out of git -- the two
# sealed runs' manifests and the ignore rules -- and the module that reads the
# history from one of its tests rather than from all of them. The helper the
# suite calls is ``tests/portability.py``'s.
_TEST_DEFINITION = re.compile(r"^\s+def (test_\w+)", re.MULTILINE)

HISTORY_MODULES: Tuple[str, ...] = (
    "tests/test_repository_hygiene.py",
    "tests/test_wild_run_manifest.py",
    "tests/test_wild_v2_run_manifest.py",
)

HISTORY_TEST_MODULES: Tuple[str, ...] = ("tests/test_known_limitations.py",)

HISTORY_HELPER = "portability.require_git_history()"


def _test_bodies(source: str) -> List[str]:
    """Every test method's own source, in the module's order.

    A body runs from its ``def`` to the next ``def test_`` at any indentation,
    so a nested helper or a decorator between two tests stays with the test above
    it and nothing is counted twice.
    """
    matches = list(_TEST_DEFINITION.finditer(source))
    bodies: List[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        bodies.append(source[match.start() : end])
    return bodies


def _test_names(source: str) -> List[str]:
    """Every test method's name, in the module's order."""
    return [match.group(1) for match in _TEST_DEFINITION.finditer(source)]


def tests_that_read_the_git_history() -> str:
    """How many tests read the repository's git history.

    The figure the README states and ``tests/portability.py`` names: the tests
    that skip, saying why, when the history is not there to read. It is counted
    from the test modules' own source rather than by running the suite -- this
    command runs no tests -- and it is counted the way the suite meets it: every
    test of a module whose whole subject is a record read out of git
    (``HISTORY_MODULES``), and, in a module that reads the history from one test
    rather than from all of them (``HISTORY_TEST_MODULES``), the tests whose own
    body asks ``portability.require_git_history``. ``tests/test_portability.py``
    is not counted: it tests the helper itself, and its tests answer with or
    without a history because they patch the availability rather than call it.
    """
    total = 0
    for name in HISTORY_MODULES:
        total += len(_test_names((PROJECT_ROOT / name).read_text(encoding="utf-8")))
    for name in HISTORY_TEST_MODULES:
        for body in _test_bodies((PROJECT_ROOT / name).read_text(encoding="utf-8")):
            if HISTORY_HELPER in body:
                total += 1
    return str(total)


def _compute() -> Dict[str, str]:
    """Every headline figure, computed from the committed runs.

    Read through :func:`ui.site.figures.figures` and :mod:`eval.fairness`, the
    functions the pages and ``tests/test_readme_figures.py`` read them through,
    so a figure this command checks is the figure those already compute.
    """
    values = site_figures.figures()
    _lean, swap, _calibration = fairness.combined_measurements()
    sealed_v4 = graded_version_seven("sealed-v4")
    dev_v7 = graded_version_seven("dev-v7")
    ryde_v7 = graded_version_seven("ryde-v7")
    v4_bounds = v6_runs.wilson(sealed_v4.exact_matches, sealed_v4.total)
    v4_run_dir = development_sets.run_dir_at_its_version(
        development_sets.named("sealed-v4"), MODEL
    )
    v4_documents = {
        case_no: run_benchmark.load_cached(v4_run_dir, case_no)
        for case_no in sealed_v4.graded_cases
    }
    v4_walls = [document.get("wall_seconds") for document in v4_documents.values()]
    v4_costs = [case_cost(document) for document in v4_documents.values()]
    ryde_v8 = graded_version_seven("ryde-v8")
    dev_v8 = graded_version_seven("dev-v8")
    no_show_drafts = site_figures.ryde_no_show_drafts()
    v8_run_dir = development_sets.run_dir_at_its_version(
        development_sets.named("dev-v8"), MODEL
    )
    v8_documents = {
        case_no: run_benchmark.load_cached(v8_run_dir, case_no)
        for case_no in dev_v8.graded_cases
    }
    v8_walls = [document.get("wall_seconds") for document in v8_documents.values()]
    v8_costs = [case_cost(document) for document in v8_documents.values()]
    # The version-8 measurements are computed by the module that measures them,
    # so a figure this command checks is the figure ``eval.v8_report`` prints
    # rather than a second reading of the same runs.
    measured_eight = v8_report.figures()
    return {
        "median time to a decision": values["median_wall_seconds"],
        "90th percentile time to a decision": values["p90_wall_seconds"],
        "median model cost per case": values["median_cost_usd"],
        "cases decided automatically": values["decided_automatically"],
        "cases held for release": values["held_for_release"],
        "cases with no ruling": values["no_ruling"],
        "cases in the four runs": values["cases_total"],
        "share decided automatically": values["decided_share"],
        "position swap, all four graded fields": "{0}/{1}".format(
            values["position_swap_agreed"], values["position_swap_total"]
        ),
        "position swap, the ruling alone": "{0}/{1}".format(
            swap.agree_ruling, swap.total
        ),
        "inject-v1, attacks": values["inject_total"],
        "inject-v1, rulings flipped": values["inject_flipped"],
        "inject-v1, rulings unchanged": values["inject_unchanged"],
        "inject-v1, sent to a person": values["inject_sent_to_a_person"],
        "dev-v2-ext, four-field exact": values["dev_v2_ext_exact"],
        "dev-v2-ext, Wilson 95% interval": values["dev_v2_ext_interval"],
        "corpus at version 6, four-field exact": values["corpus_v6_exact"],
        "sealed-v2, four-field agreement": values["sealed_v2_exact"],
        "sealed-v2, Wilson 95% interval": values["sealed_v2_interval"],
        "sealed-v1, four-field agreement": values["sealed_v1_exact"],
        "sealed-v1, the key as imported": values["sealed_v1_imported"],
        "wild-v2, four-field exact": values["wild_v2_exact"],
        # Policy version 7. The three sets, each graded against its own key.
        "sealed-v4, four-field agreement": "{0}/{1}".format(
            sealed_v4.exact_matches, sealed_v4.total
        ),
        "sealed-v4, Wilson 95% interval": "{0:.1f}-{1:.1f}%".format(
            v4_bounds[0] * 100, v4_bounds[1] * 100
        ),
        "ryde-v7, samples matching Ryde's stated outcomes": "{0} of {1}".format(
            ryde_v7.exact_matches, ryde_v7.total
        ),
        "dev-v7, four-field agreement": "{0}/{1}".format(
            dev_v7.exact_matches, dev_v7.total
        ),
        "version-7 sealed run, median time to a decision": v6_runs._seconds(
            v6_runs._median(v4_walls)
        ),
        "version-7 sealed run, median model cost": "{0:.4f}".format(
            v6_runs._median(v4_costs)
        ),
        # Policy version 8. The two sets, each graded against its own key.
        "ryde-v8, samples matching Ryde's stated outcomes": "{0} of {1}".format(
            ryde_v8.exact_matches, ryde_v8.total
        ),
        "dev-v8, four-field agreement": "{0}/{1}".format(
            dev_v8.exact_matches, dev_v8.total
        ),
        "dev-v8, median time to a decision": v6_runs._seconds(
            v6_runs._median(v8_walls)
        ),
        "dev-v8, 90th percentile time to a decision": v6_runs._seconds(
            v6_runs._percentile(v8_walls, Decimal("0.9"))
        ),
        "dev-v8, median model cost": "{0:.4f}".format(v6_runs._median(v8_costs)),
        "ryde-v8, 903's drafts counted by outcome": "{0} escalate, {1} fee, {2} voided".format(
            no_show_drafts["escalate"],
            no_show_drafts["fee"],
            no_show_drafts["voided"],
        ),
        # The four version-8 measurements, read off ``eval.v8_report``.
        "dev-v8 decided with no person": measured_eight["dev-v8 decided with no person"],
        "dev-v8 position swap": measured_eight["dev-v8 position swap"],
        "dev-v8 ECE": measured_eight["dev-v8 ECE"],
        "dev-v8 drafts": measured_eight["dev-v8 drafts"],
        # The version-8 figures the product site states, read from the module
        # that computes them: a figure checked here is the figure a page shows.
        "dev-v8, the median in minutes": values["v8_median_minutes"].split(" ")[0],
        "dev-v8, cases that went to a person": values["v8_to_person"],
        "dev-v8, the gate's cases": values["v8_gate_total"],
        "dev-v8, the gate's 2 km limb": values["v8_gate_2km"],
        "dev-v8, the gate's value limb": values["v8_gate_value"],
        "dev-v8, the gate's safety limb": values["v8_gate_safety"],
        "dev-v8, the panel's escalations": values["v8_panel_escalated"],
        "dev-v8, the panels without a majority": values["v8_no_majority"],
        "dev-v8, route deviation limit": values["v8_route_limit_km"],
        "dev-v8, the value a person decides above": values["v8_human_above"],
        "dev-v8, confidence the policy asks": values["v8_confidence_between"],
        "case 5051, evidence items": values["case5051_evidence"],
        "case 5051, the rider's and the driver's points": "{0} and {1}".format(
            values["case5051_rider_points"], values["case5051_driver_points"]
        ),
        "case 5051, claims kept": values["case5051_claims_kept"],
        "case 5051, the dropped point": values["case5051_dropped"],
        "case 5051, the amount to the driver": values["case5051_amount"],
        "case 5051, the wall clock": values["case5051_wall"].split(" ")[0],
        "case 5051, the wait and the free wait": values["case5051_wait_seconds"],
        "version-8 case pages": values["v8_case_pages"],
        "sealed-v4, cases that needed a person": values["sealed_v4_to_person"],
        # The tests that read the repository's git history, counted from the test
        # modules rather than by running them.
        "tests that read the git history": tests_that_read_the_git_history(),
    }


def computed() -> Dict[str, str]:
    """The computed values, read once per process."""
    global _COMPUTED
    if _COMPUTED is None:
        _COMPUTED = _compute()
    return dict(_COMPUTED)


# --------------------------------------------------------------------------
# Reading the documents
# --------------------------------------------------------------------------
def normalise(text: str) -> str:
    """A captured value, as the spellings are written.

    A trailing ``.0`` is dropped, so ``100.0%`` and ``100%`` are the same
    value; nothing else is changed, because every other spelling is the
    document's own.
    """
    text = text.strip()
    if re.fullmatch(r"\d+\.\d+", text):
        text = text.rstrip("0").rstrip(".")
    return text


class Mismatch(NamedTuple):
    """One place a figure is stated with a value that is not the computed one."""

    figure: str
    document: str
    value: str
    expected: str


class DeadPattern(NamedTuple):
    """One pattern that matches nothing, anywhere."""

    figure: str
    pattern: str


class ClaimHit(NamedTuple):
    """One line a claim forbids, in one document."""

    claim: str
    document: str
    line: str


class Row(NamedTuple):
    """One line of the report."""

    figure: str
    value: str
    documents: Tuple[str, ...]
    ok: bool


class Report(NamedTuple):
    """Everything one run of the check found."""

    rows: Tuple[Row, ...]
    mismatches: Tuple[Mismatch, ...]
    dead: Tuple[DeadPattern, ...]
    claims: Tuple[ClaimHit, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.mismatches and not self.dead and not self.claims


def check(root: Path = PROJECT_ROOT) -> Report:
    """Every figure, and every claim, against every document under ``root``.

    ``root`` is a directory the relative names in :data:`DOCUMENTS` and in each
    claim's own ``files`` are read under, so the check can be pointed at a copy
    of one file and shown to fail. A document that is not there is skipped
    rather than reported: a copy holding one file is exactly what the controls
    use.
    """
    values = computed()
    rows: List[Row] = []
    mismatches: List[Mismatch] = []
    dead: List[DeadPattern] = []
    for figure in FIGURES:
        documents: Set[str] = set()
        matched: Set[str] = set()
        ok = True
        for name in DOCUMENTS:
            path = root / name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in figure.patterns:
                for match in re.finditer(pattern, text):
                    matched.add(pattern)
                    documents.add(name)
                    for group in match.groups():
                        if group is None:
                            continue
                        value = normalise(group)
                        if value not in figure.spellings:
                            ok = False
                            mismatches.append(
                                Mismatch(
                                    figure.name, name, value, values[figure.name]
                                )
                            )
        for pattern in figure.patterns:
            if pattern not in matched:
                dead.append(DeadPattern(figure.name, pattern))
        rows.append(Row(figure.name, values[figure.name], tuple(sorted(documents)), ok))
    claims: List[ClaimHit] = []
    for claim in CLAIMS:
        for name in claim.files:
            path = root / name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if any(
                    re.search(pattern, line) is None for pattern in claim.applies
                ):
                    continue
                if any(re.search(pattern, line) for pattern in claim.forbidden):
                    claims.append(ClaimHit(claim.name, name, line.strip()))
    return Report(tuple(rows), tuple(mismatches), tuple(dead), tuple(claims))


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
def report(root: Path = PROJECT_ROOT, found: "Optional[Report]" = None) -> str:
    """The table, and every mismatch and dead pattern below it."""
    if found is None:
        found = check(root)
    width = max(len(row.figure) for row in found.rows)
    lines: List[str] = [
        "One figure, one value everywhere",
        "================================",
        "",
        "Each headline figure, computed from the committed runs, against every",
        "document and built page that states it. A figure's value here is what",
        "the runs say; a document that states another value is a mismatch.",
        "",
        "{0}  {1}  {2}".format(
            "figure".ljust(width), "value".ljust(18), "check"
        ),
        "{0}  {1}  {2}".format("-" * width, "-" * 18, "-----"),
    ]
    for row in found.rows:
        lines.append(
            "{0}  {1}  {2}".format(
                row.figure.ljust(width),
                row.value.ljust(18),
                "OK" if row.ok else "MISMATCH",
            )
        )
        lines.append(
            "    in: {0}".format(", ".join(row.documents) or "(nowhere)")
        )
    lines.append("")
    if found.mismatches:
        lines.append("Mismatches:")
        for mismatch in found.mismatches:
            lines.append(
                "  {0}: {1} says {2!r}, the runs say {3!r}".format(
                    mismatch.figure,
                    mismatch.document,
                    mismatch.value,
                    mismatch.expected,
                )
            )
    else:
        lines.append("Every occurrence matches the computed value.")
    if found.dead:
        lines.append("")
        lines.append("Patterns that match nothing anywhere:")
        for pattern in found.dead:
            lines.append("  {0}: {1}".format(pattern.figure, pattern.pattern))
    if found.claims:
        lines.append("")
        lines.append("Claims a document may not make:")
        for hit in found.claims:
            lines.append(
                "  {0}: {1} says {2!r}".format(hit.claim, hit.document, hit.line)
            )
    else:
        lines.append("")
        lines.append("No document makes a forbidden claim.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.check_figures",
        description=(
            "Every headline figure, computed from the committed runs, against "
            "every document and built page that states it. Reads and writes "
            "nothing, and makes no model call."
        ),
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="print the table, every mismatch and every dead pattern",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Check every figure. Nothing is written and no model is called."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    found = check(PROJECT_ROOT)
    if args.report:
        sys.stdout.write(report(PROJECT_ROOT, found))
    else:
        for mismatch in found.mismatches:
            sys.stdout.write(
                "MISMATCH {0}: {1} says {2!r}, the runs say {3!r}\n".format(
                    mismatch.figure,
                    mismatch.document,
                    mismatch.value,
                    mismatch.expected,
                )
            )
        for pattern in found.dead:
            sys.stdout.write(
                "DEAD {0}: {1}\n".format(pattern.figure, pattern.pattern)
            )
        for hit in found.claims:
            sys.stdout.write(
                "CLAIM {0}: {1} says {2!r}\n".format(
                    hit.claim, hit.document, hit.line
                )
            )
        sys.stdout.write(
            "check_figures: {0}\n".format("OK" if found.ok else "FAILED")
        )
    return 0 if found.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
