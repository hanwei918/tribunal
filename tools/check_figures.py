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
the same graded reads ``tests/test_readme_figures.py`` makes; and the version-7
figures come from the same :func:`eval.run_benchmark.grade_run` call over the
directory each version-7 run was written to. No figure is typed in here and no
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

from eval import development_sets, fairness, run_benchmark, v6_runs  # noqa: E402
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
            r"median of (\d+\.\d+) s",
            r"decision of (\d+\.\d+) s and a 90th",
            r"class=\"big\">(\d+\.\d+) s</span><h3>",
            r"num\">(\d+\.\d+)<small>min</small>",
            r"num\">(\d+\.\d+)<small>\u5206\u949f</small>",
            r"\u4e2d\u4f4d (\d+\.\d+) \u79d2",
            r"in (\d+\.\d+) min at the median",
            r"At the (\d+\.\d+) s median",
            r"(\d+\.\d+) s; p90",
        ),
    ),
    Figure(
        "90th percentile time to a decision",
        ("286.9", "4.8"),
        (
            r"(\d+\.\d+) s at the 90th percentile",
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
            r"<i></i>(\d+) ruled by the AI",
            r"<i></i>(\d+) \u7531 AI \u5224",
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
            r"<i class=\"h\"></i>(\d+) ruled, payout waits",
            r"<i class=\"h\"></i>(\d+) \u5df2\u5224",
            r"(\d+) waited for sign-off",
            r"(\d+) \u4e2a\u7b49\u4eba\u7b7e\u5b57",
        ),
    ),
    Figure(
        "cases with no ruling",
        ("26",),
        (
            r"\| (\d+) with no ruling",
            r"class=\"big\">(\d+)</span><h3>No ruling issued",
            r"class=\"big\">(\d+)</span><h3>\u4e0d\u51fa\u5224\u51b3",
            r"<i class=\"p\"></i>(\d+) no ruling",
            r"<i class=\"p\"></i>(\d+) \u6ca1\u5224",
            r"(\d+) went to a person",
            r"\uff1a(\d+) \u4e2a\u4ea4\u7ed9\u4eba",
        ),
    ),
    Figure(
        "cases in the four runs",
        ("151",),
        (
            r"\*\*112 of (\d+)\*\*",
            r"112/(\d+) = ",
            r"Of the (\d+), 112 are decided",
            r"</span><small>/(\d+)</small>",
            r"(\d+) version-6 cases",
            r"Of (\d+) cases:",
            r"(\d+) \u4e2a\u6848\u5b50\u4e2d\uff1a",
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
            r"nothing in (\d+) of 141 cases",
            r"\u540e\u6709 (\d+) \u4e2a\u7ed3\u8bba\u4e0d\u53d8",
            r"data-count=\"(\d+)\">\d+</span><small>/141",
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
            r"Hidden tests: (\d+)/12",
            r"\u9690\u85cf\u8003\u9898\uff1a(\d+)/12",
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
            r"Hidden tests: 12/12 and (\d+)/24",
            r"\u9690\u85cf\u8003\u9898\uff1a12/12 \u548c (\d+)/24",
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
            r"keyed by Ryde's stated outcome, is (1 of 2):",
            r"keyed by Ryde's stated outcomes \(`ryde-v7`\), are (1 of 2):",
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
        (r"median is \*\*(\d+\.\d+) s\*\* a case",),
    ),
    Figure(
        "version-7 sealed run, median model cost",
        ("0.0398",),
        (r"model cost of \*\*(\d+\.\d+) USD\*\* a case",),
    ),
)

# The figures by name, so the report and the tests can name one.
BY_NAME: Dict[str, Figure] = {figure.name: figure for figure in FIGURES}


# --------------------------------------------------------------------------
# The computed values
# --------------------------------------------------------------------------
_COMPUTED: "Optional[Dict[str, str]]" = None


def graded_version_seven(name: str) -> "grade.GradeReport":
    """One version-7 set's committed run, graded against its own key.

    The same :func:`eval.run_benchmark.grade_run` call the sealed and held-out
    sets are graded with, over the directory the run was **written to**:
    ``dev-v7`` and ``ryde-v7`` are registered for a policy base, so their runs
    sit one level down (``runs/<set>/policy-v7/<model>/``) and the un-versioned
    path holds nothing.
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

    @property
    def ok(self) -> bool:
        return not self.mismatches and not self.dead


def check(root: Path = PROJECT_ROOT) -> Report:
    """Every figure, against every document under ``root``.

    ``root`` is a directory the relative names in :data:`DOCUMENTS` are read
    under, so the check can be pointed at a copy of one file and shown to fail.
    A document that is not there is skipped rather than reported: a copy holding
    one file is exactly what the control uses.
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
    return Report(tuple(rows), tuple(mismatches), tuple(dead))


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
        sys.stdout.write(
            "check_figures: {0}\n".format("OK" if found.ok else "FAILED")
        )
    return 0 if found.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
