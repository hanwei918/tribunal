"""The version-8 case pages, built from the committed runs.

The site's case pages are the version-6 runs and their builder (``ui.v2.build``)
is written for version 6. The submission applies version 8, and its 42
version-8 cases -- ``dev-v8`` (40) and ``ryde-v8`` (2) -- have no page. This
package gives them one: a page per case, in English and in Chinese, plus an
index, so a judge can read a version-8 decision from the evidence to the ruling,
gates included.

What is read, and from where
----------------------------
* the two sets' registrations, through :func:`eval.development_sets.named` and
  :func:`eval.development_sets.run_dir_at_its_version` -- which is what puts
  ``dev-v8``'s run at ``runs/dev-v8/policy-v8/<model>/`` -- and the run
  document ``case-NNNNN.json`` and the transcript it names;
* the case file, through the set's own ``load_case``: the category, the filing
  party, the amount contested, the filer's statement and the counterparty's,
  and the evidence list;
* the **version-8 brief**, rebuilt with
  ``tribunal.brief.build_brief_for_case(case, policy_version=8)``. Its digest
  must equal the run document's ``brief_sha256``; a case whose rebuilt brief
  hashes differently is **refused**, because this code would then be drawing a
  page from a brief that only resembles the one the agents were handed;
* the set's key, through ``eval.run_benchmark.grade_run`` -- the same call
  ``ui/site/figures.py`` grades the same sets with -- for whether the published
  ruling agrees with the key on the four graded fields;
* the authority gate, through ``tribunal.pipeline.authority_gate``, which is the
  function the pipeline itself calls: the transcript records whether the judge
  was asked, and the gate says why when it was not.

One figure is not on the brief: the value above which POL-GEN-22 makes a dispute
a person's. The brief states the band and the clause and not the edge, so the
edge is read from ``policy/v8/general.json`` through
:func:`tribunal.policy_versions.base_directory` -- the same file and the same
read ``ui/site/figures.py`` makes for the safety page's thresholds.

What is written
---------------
Flat names in ``ui/dist/`` so every relative link works as on the other pages:
``v8-NNNNN.html`` and ``v8-NNNNN.zh.html`` per case, and ``v8-cases.html`` /
``v8-cases.zh.html`` for the index. Each page is the site's own shell -- head,
header, language switch and footer -- taken from
``ui/site/src/pages/cases.html`` (``cases.zh.html`` in Chinese) and assembled
with :func:`ui.site.build.assemble`, with its ``<main>``, title, description and
``hreflang`` alternates set for the case. No stylesheet is added.

Every ``table.dt`` this builder writes is the only child of a
``<div class="scroll-x">`` -- a class ``ui/site/src/site.css`` already defines
(``.scroll-x{overflow-x:auto}``) -- because the drafts table's five columns and
the run's 40-character commit are wider than a phone and a page that scrolled
sideways would carry the whole layout with it.

Every page is **ASCII**: a character outside ASCII is written as a numeric
character reference, or, inside a ``<script>`` element, as a JavaScript
``\\uXXXX`` escape -- which is how ``ui.v2.build`` writes its own pages, and
what keeps the repository's language rule true of a file this repository writes.
:func:`ascii_page` refuses a page it cannot make ASCII rather than writing one.

The pages are deterministic: the set order and the case order are this module's
own constants, and no timestamp is written.

Usage::

    python3 -m ui.v8.build            # write every page
    python3 -m ui.v8.build --check    # compare, change nothing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, grade, run_benchmark  # noqa: E402
from tribunal import brief as brief_module  # noqa: E402
from tribunal import pipeline as pipeline_module  # noqa: E402
from tribunal import policy_versions  # noqa: E402
from ui.site import build as site_build  # noqa: E402
from ui.site import queue_rows as site_rows  # noqa: E402
from ui.v2 import build as v2  # noqa: E402

DIST_DIR = PROJECT_ROOT / "ui" / "dist"

# The version these pages are briefed at, and the model the two runs were made
# with. The model is asked of ``eval.run_benchmark`` rather than typed here, so a
# page and the report cannot name two different runs.
POLICY_VERSION = 8
MODEL = run_benchmark.resolve_model(None)

# The two sets, in the order the pages list them: the 40 development cases
# first, then Ryde's own two samples. The order is a fact about this file rather
# than about a directory listing.
SET_ORDER: Tuple[str, ...] = ("dev-v8", "ryde-v8")

# What a case's own page calls its set.
SET_DESCRIPTIONS: Mapping[str, Tuple[str, str]] = {
    "dev-v8": (
        "development data, version 8",
        "\u5f00\u53d1\u6570\u636e\uff0c\u7248\u672c 8",
    ),
    "ryde-v8": (
        "Ryde's own sample, version 8",
        "Ryde \u81ea\u5df1\u7684\u6837\u672c\uff0c\u7248\u672c 8",
    ),
}

EN = "en"
ZH = "zh"
LANGUAGES: Tuple[str, ...] = (EN, ZH)

# The site shell each language's pages are taken from, and the suffix its own
# files carry. The shell is the policy owner's design and is read, never edited.
SHELL_PAGE: Mapping[str, str] = {EN: "cases.html", ZH: "cases.zh.html"}

INDEX_PAGE = "v8-cases.html"
CASE_PAGE = "v8-{0:05d}.html"

# The four graded fields, in the order ``eval.grade`` scores them: what "agrees
# with the key" means on every page here.
GRADED_FIELDS = grade.GRADED_FIELDS

# The ruling value that means the dispute was not decided by the machine, and
# the two vote outcomes that mean the panel carried what it agreed on.
ESCALATE = pipeline_module.ESCALATE
CARRIED_OUTCOMES: Tuple[str, ...] = (
    pipeline_module.VOTE_CARRIED,
    pipeline_module.VOTE_CARRIED_NOT_UNANIMOUS,
)

# The currency a page falls back to where a case carries no money block at all.
CURRENCY_FALLBACK = "SGD"


class BuildError(Exception):
    """A page could not be built from the files it reads."""


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------
def _read_json(path: Path) -> Any:
    """One committed file, with every JSON number carrying a point a ``Decimal``."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise BuildError("cannot read {0}: {1}".format(path, exc)) from exc
    try:
        return json.loads(text, parse_float=Decimal)
    except ValueError as exc:
        raise BuildError("invalid JSON in {0}: {1}".format(path, exc)) from exc


def _leaf(node: Any, *path: str) -> Any:
    """A derived fact's own value, or ``None`` where the block does not carry it.

    Every fact the version-7 block publishes is an object with a ``value`` key,
    so a caller asking for a fact gets the value rather than the wrapper. A block
    that is absent, or a leaf that is a plain ``None``, answers ``None``.
    """
    current = node
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    if isinstance(current, Mapping) and "value" in current:
        return current["value"]
    return current


def _clause(node: Any, *path: str) -> Optional[str]:
    """The clause id a derived fact is published under, where it states one."""
    current = node
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    if isinstance(current, Mapping):
        clause = current.get("clause_id")
        return clause if isinstance(clause, str) else None
    return None


@dataclass(frozen=True)
class V8Case:
    """Everything one version-8 case page and one index row are built from."""

    set_name: str
    case_no: int
    run_dir: Path
    document: Mapping[str, Any]
    transcript: Mapping[str, Any]
    case: Mapping[str, Any]
    brief: Mapping[str, Any]
    brief_sha256: str
    authority: Mapping[str, Any]
    gate: Optional[Mapping[str, Any]]
    score: "grade.CaseScore"

    @property
    def link(self) -> str:
        return CASE_PAGE.format(self.case_no)

    @property
    def zh_link(self) -> str:
        return CASE_PAGE.format(self.case_no).replace(".html", ".zh.html")

    @property
    def dispute(self) -> Mapping[str, Any]:
        return self.case.get("dispute") or {}

    @property
    def category(self) -> str:
        return str(self.dispute.get("category"))

    @property
    def filed_by(self) -> Any:
        return self.dispute.get("filed_by")

    @property
    def amount(self) -> Any:
        return self.dispute.get("amount_contested_sgd")

    @property
    def ruling(self) -> Mapping[str, Any]:
        block = self.document.get("ruling")
        inner = block.get("ruling") if isinstance(block, Mapping) else None
        return inner if isinstance(inner, Mapping) else {}

    @property
    def ruling_value(self) -> str:
        return str(self.ruling.get("ruling"))

    @property
    def confidence(self) -> Any:
        return self.ruling.get("confidence")

    @property
    def vote(self) -> Optional[Mapping[str, Any]]:
        vote = self.transcript.get("vote")
        return vote if isinstance(vote, Mapping) else None

    @property
    def key(self) -> "grade.Ruling":
        """The set's own key for this case, as the grader reduced it."""
        return self.score.expected

    @property
    def value_band(self) -> Any:
        return _leaf(self.authority, "value_band")

    @property
    def required_confidence(self) -> Any:
        return _leaf(self.authority, "required_confidence")

    @property
    def required_basis(self) -> str:
        return str(self.authority.get("required_confidence_basis") or "")

    @property
    def currency(self) -> str:
        money = _derived(self.brief, "FARE_BREAKDOWN", brief_module.MONEY_KEY)
        currency = _leaf(money, "currency") if isinstance(money, Mapping) else None
        return str(currency) if currency else CURRENCY_FALLBACK

    @property
    def drafts(self) -> List[Dict[str, Any]]:
        """The panel's drafts, each with the ruling it parsed to."""
        return v2._drafts(self.transcript)


def _transcript_name(document: Mapping[str, Any], case_no: int) -> str:
    """The transcript's file name, as the run recorded it."""
    recorded = document.get("transcript_file")
    if isinstance(recorded, str) and recorded:
        return recorded
    return "case-{0:05d}.transcript.json".format(case_no)


def _derived(brief: Mapping[str, Any], evidence_type: str, block: str) -> Any:
    """One derived block, off the artifact of ``evidence_type`` that carries it."""
    for artifact in brief["case"]["evidence"]:
        if artifact.get("evidence_type") != evidence_type:
            continue
        payload = artifact.get("payload") or {}
        return (payload.get("derived") or {}).get(block)
    return None


def _load_case(development_set: Any, case_no: int, scores: Mapping[int, Any]) -> V8Case:
    """Read one case, refusing anything the run and the brief disagree about."""
    run_dir = development_sets.run_dir_at_its_version(development_set, MODEL)
    document = _read_json(run_dir / "case-{0:05d}.json".format(case_no))
    transcript = _read_json(run_dir / _transcript_name(document, case_no))
    try:
        case = development_set.load_case(case_no)
    except Exception as exc:  # noqa: BLE001 - a loader refusal is this module's refusal
        raise BuildError(
            "case {0} of {1} cannot be loaded: {2}".format(
                case_no, development_set.name, exc
            )
        ) from exc

    configuration = document.get("configuration")
    version = (
        configuration.get("policy_version")
        if isinstance(configuration, Mapping)
        else None
    )
    if int(version or 0) != POLICY_VERSION:
        raise BuildError(
            "case {0} of {1} was run at policy version {2}, and these are the "
            "version-{3} pages".format(
                case_no, development_set.name, version, POLICY_VERSION
            )
        )
    if document.get("development_set") != development_set.name:
        raise BuildError(
            "case {0} of {1} records the development set {2!r}".format(
                case_no, development_set.name, document.get("development_set")
            )
        )

    try:
        brief = brief_module.build_brief_for_case(case, policy_version=POLICY_VERSION)
    except Exception as exc:  # noqa: BLE001 - a brief refusal is this module's refusal
        raise BuildError(
            "the brief for case {0} of {1} cannot be built: {2}".format(
                case_no, development_set.name, exc
            )
        ) from exc
    _canonical, digest = brief_module.brief_digest(brief)
    recorded = document.get("brief_sha256")
    if recorded != digest:
        # The page shows the facts the agents were handed. A digest that does
        # not match means this code builds a different brief, so the case is
        # refused rather than drawn from a brief that merely resembles it.
        raise BuildError(
            "case {0} of {1}: the rebuilt brief hashes to {2} and the run "
            "recorded {3}, so this code builds a different brief from the one "
            "the agents were handed".format(
                case_no, development_set.name, digest, recorded
            )
        )

    authority = brief["case"]["authority"]
    gate = pipeline_module.authority_gate(case, brief)
    vote = transcript.get("vote")
    if (gate is None) == (vote is None):
        # The transcript says whether the judge ran and the gate says whether it
        # was asked. Exactly one of the two must be absent, and a case where
        # they disagree is a case this code cannot draw.
        raise BuildError(
            "case {0} of {1}: the run's transcript and the rebuilt brief "
            "disagree about whether the version-8 gate fired".format(
                case_no, development_set.name
            )
        )

    score = scores.get(case_no)
    if score is None:
        raise BuildError(
            "case {0} of {1} is not in the set's graded report".format(
                case_no, development_set.name
            )
        )
    return V8Case(
        set_name=development_set.name,
        case_no=case_no,
        run_dir=run_dir,
        document=document,
        transcript=transcript,
        case=case,
        brief=brief,
        brief_sha256=digest,
        authority=authority,
        gate=gate,
        score=score,
    )


def read_set(set_name: str) -> List[V8Case]:
    """Every case of one set, in case-number order, with its own key's verdict."""
    development_set = development_sets.named(set_name)
    run_dir = development_sets.run_dir_at_its_version(development_set, MODEL)
    report = run_benchmark.grade_run(
        run_dir,
        development_set.key(),
        case_loader=development_set.load_case,
        policy_version=development_set.policy_version,
    )
    scores = {score.case_no: score for score in report.cases}
    return [
        _load_case(development_set, case_no, scores)
        for case_no in sorted(development_set.cases)
    ]


def read_every_case() -> List[V8Case]:
    """Every case of both sets: the set order above, then case number."""
    out: List[V8Case] = []
    for set_name in SET_ORDER:
        out.extend(read_set(set_name))
    return out


# --------------------------------------------------------------------------
# Labels and sentences, in the two languages
# --------------------------------------------------------------------------
# Every label this module writes, English beside Chinese, so the two pages of a
# case cannot come to say different things. The Chinese is written as escapes
# because this file is ASCII, exactly as ``ui/site/queue_rows.py`` writes its own
# vocabulary.
WORDS: Mapping[str, Tuple[str, str]] = {
    "Outcome": ("Outcome", "\u7ed3\u679c"),
    "The dispute": ("The dispute", "\u4e89\u8bae"),
    "What the code worked out": (
        "What the code worked out",
        "\u4ee3\u7801\u7b97\u51fa\u7684\u4e8b\u5b9e",
    ),
    "The two sides": ("The two sides", "\u53cc\u65b9\u4e3b\u5f20"),
    "The judge's drafts": ("The judge's drafts", "\u6cd5\u5b98\u8349\u7a3f"),
    "The ruling's explanation": (
        "The ruling's explanation",
        "\u88c1\u51b3\u8bf4\u660e",
    ),
    "The run": ("The run", "\u8fd0\u884c\u8bb0\u5f55"),
    "Part": ("Part {0}", "\u7b2c {0} \u90e8\u5206"),
    "Case": ("Case", "\u6848\u4ef6"),
    "Category": ("Category", "\u7c7b\u522b"),
    "Set": ("Set", "\u6570\u636e\u96c6"),
    "Filed by": ("Filed by", "\u63d0\u4ea4\u65b9"),
    "Amount contested": ("Amount contested", "\u4e89\u8bae\u91d1\u989d"),
    "Value band": ("Value band", "\u91d1\u989d\u533a\u95f4"),
    "Published ruling": ("Published ruling", "\u516c\u5e03\u88c1\u51b3"),
    "Referrals": ("Referrals", "\u8f6c\u529e"),
    "How it was decided": ("How it was decided", "\u5982\u4f55\u51b3\u5b9a"),
    "Agrees with the key": ("Agrees with the key", "\u4e0e\u7b54\u6848\u4e00\u81f4"),
    "Evidence": ("Evidence", "\u8bc1\u636e"),
    "Evidence id": ("Evidence id", "\u8bc1\u636e\u7f16\u53f7"),
    "Evidence type": ("Evidence type", "\u8bc1\u636e\u7c7b\u578b"),
    "Statements": ("Statements", "\u9648\u8ff0"),
    "Filer": ("The filer's statement", "\u63d0\u4ea4\u65b9\u9648\u8ff0"),
    "Other party": ("The other party's statement", "\u5bf9\u65b9\u9648\u8ff0"),
    "Rider advocate": ("Rider advocate", "\u4e58\u5ba2\u65b9\u4e3b\u5f20"),
    "Driver advocate": ("Driver advocate", "\u53f8\u673a\u65b9\u4e3b\u5f20"),
    "Claim": ("Claim {0}", "\u4e3b\u5f20 {0}"),
    "Evidence ids": ("Evidence ids", "\u8bc1\u636e\u7f16\u53f7"),
    "Clause ids": ("Clause ids", "\u6761\u6b3e\u7f16\u53f7"),
    "Verdict": ("Verdict", "\u88c1\u5224\u5458\u7ed3\u8bba"),
    "Kept": ("kept", "\u4fdd\u7559"),
    "Dropped": ("dropped", "\u9a73\u56de"),
    "Draft": ("Draft", "\u8349\u7a3f"),
    "Kind": ("Kind", "\u79cd\u7c7b"),
    "Proposed": ("Proposed", "\u4e3b\u5f20"),
    "Confidence": ("Confidence", "\u7f6e\u4fe1\u5ea6"),
    "Validity": ("Validity", "\u662f\u5426\u6709\u6548"),
    "Valid": ("valid", "\u6709\u6548"),
    "Voided": ("voided", "\u4f5c\u5e9f"),
    "Sampled": ("sampled", "\u62bd\u6837"),
    "Position swapped": ("position-swapped", "\u4ea4\u6362\u7acb\u573a"),
    "No proposed ruling": ("no ruling was carried", "\u6ca1\u6709\u63d0\u51fa\u88c1\u51b3"),
    "No referee verdict": (
        "No referee verdict was recorded.",
        "\u6ca1\u6709\u88c1\u5224\u5458\u7ed3\u8bba\u3002",
    ),
    "No drafts": (
        "No drafts: the judge was not asked.",
        "\u6ca1\u6709\u8349\u7a3f\uff1a\u672a\u8be2\u95ee\u6cd5\u5b98\u3002",
    ),
    "None": ("none", "\u65e0"),
    "Fraud flags": ("Fraud flags", "\u6b3a\u8bc8\u6807\u8bb0"),
    "Required confidence": ("Required confidence", "\u6240\u9700\u7f6e\u4fe1\u5ea6"),
    "Safety flag": ("Safety flag", "\u5b89\u5168\u6807\u8bb0"),
    "A person decides": ("A person decides", "\u662f\u5426\u4ec5\u4eba\u5de5"),
    "Authority": ("The authority block", "\u6743\u9650\u533a\u5757"),
    "Deviation": ("Deviation", "\u7ed5\u8def"),
    "Actual distance": ("Actual distance", "\u5b9e\u9645\u8ddd\u79bb"),
    "Recommended distance": ("Recommended distance", "\u63a8\u8350\u8ddd\u79bb"),
    "Deviation km": ("Deviation", "\u7ed5\u8def\u8ddd\u79bb"),
    "Tolerance": ("Tolerance", "\u5bb9\u5dee"),
    "AI limit": ("AI limit", "\u4eba\u5de5\u667a\u80fd\u4e0a\u9650"),
    "The limit applies": ("The limit applies", "\u4e0a\u9650\u662f\u5426\u9002\u7528"),
    "Over the limit": ("Over the limit", "\u662f\u5426\u8d85\u8fc7\u4e0a\u9650"),
    "Free wait": ("Free wait", "\u514d\u8d39\u7b49\u5f85"),
    "Arrived": ("Arrived", "\u5230\u8fbe"),
    "Starts": ("Starts", "\u5f00\u59cb"),
    "Ends": ("Ends", "\u7ed3\u675f"),
    "Cancelled": ("Cancelled", "\u53d6\u6d88"),
    "After the free wait": (
        "After the free wait",
        "\u5728\u514d\u8d39\u7b49\u5f85\u4e4b\u540e",
    ),
    "Free wait seconds": ("Free wait seconds", "\u514d\u8d39\u7b49\u5f85\u79d2\u6570"),
    "Driver deadline": ("Driver deadline", "\u53f8\u673a\u65f6\u9650"),
    "Late seconds": ("Late after the deadline", "\u8d85\u8fc7\u65f6\u9650\u79d2\u6570"),
    "Contact before cancelling": (
        "Contact before cancelling",
        "\u53d6\u6d88\u524d\u8054\u7cfb",
    ),
    "Messages": ("Messages", "\u6d88\u606f"),
    "Calls": ("Calls", "\u901a\u8bdd"),
    "Obligation met": ("Obligation met", "\u4e49\u52a1\u5df2\u5c65\u884c"),
    "Record complete": ("Record complete", "\u8bb0\u5f55\u662f\u5426\u5b8c\u6574"),
    "Money": ("Money", "\u91d1\u989d"),
    "Excess distance fare": (
        "Excess distance fare",
        "\u8d85\u51fa\u8ddd\u79bb\u8f66\u8d39",
    ),
    "Per km rate": ("Per km rate", "\u6bcf\u516c\u91cc\u8d39\u7387"),
    "Fee charged": ("Fee charged", "\u5df2\u6536\u8d39\u7528"),
    "Policy fee": ("The policy's fee", "\u653f\u7b56\u89c4\u5b9a\u7684\u8d39\u7528"),
    "Fee matches policy": (
        "Fee matches the policy",
        "\u8d39\u7528\u662f\u5426\u7b26\u5408\u653f\u7b56",
    ),
    "Refund if voided": ("Refund if voided", "\u4f5c\u5e9f\u65f6\u9000\u6b3e"),
    "Driver if upheld": (
        "Driver compensation if upheld",
        "\u7ef4\u6301\u65f6\u53f8\u673a\u8865\u507f",
    ),
    "Refund already issued": ("Refund already issued", "\u5df2\u9000\u6b3e"),
    "Commit": ("Commit", "\u63d0\u4ea4"),
    "Wall seconds": ("Wall seconds", "\u7528\u65f6"),
    "Tokens": ("Tokens", "\u4ee4\u724c"),
    "Cost": ("Cost", "\u6210\u672c"),
    "Model": ("Model", "\u6a21\u578b"),
    "Gate": ("gate", "\u95f8\u95e8"),
    "Panel": ("panel", "\u5408\u8bae"),
    "No majority": ("no majority", "\u6ca1\u6709\u591a\u6570"),
    "The judge's own escalation": (
        "the judge's own escalation",
        "\u6cd5\u5b98\u81ea\u884c\u8f6c\u4eba\u5de5",
    ),
    "No valid drafts": ("no valid drafts", "\u6ca1\u6709\u6709\u6548\u8349\u7a3f"),
    "Below the bar": ("below the bar", "\u4f4e\u4e8e\u4e0b\u9650"),
    "Cases": ("Cases", "\u6848\u4ef6"),
    "Decided with no person": (
        "Decided with no person",
        "\u65e0\u9700\u4eba\u5de5\u51b3\u5b9a",
    ),
    "Gates": ("Gates", "\u95f8\u95e8"),
    "Stopped before the judge": (
        "Stopped before the judge",
        "\u5728\u6cd5\u5b98\u4e4b\u524d\u88ab\u62e6\u4e0b",
    ),
    "Agreement with the key, dev-v8": (
        "Agreement with the key, dev-v8",
        "\u4e0e\u7b54\u6848\u4e00\u81f4\uff08dev-v8\uff09",
    ),
    "No ruling carried": (
        "\u2014 (no ruling carried)",
        "\u2014\uff08\u672a\u51fa\u88c1\u51b3\uff09",
    ),
    "Statements note": (
        "The parties' statements, the claims and the ruling's explanation are "
        "quoted in English, the language the record was made in.",
        "\u5f53\u4e8b\u4eba\u9648\u8ff0\u3001\u53cc\u65b9\u4e3b\u5f20\u548c\u6cd5\u5b98\u7684\u88c1\u51b3\u8bf4\u660e\u4fdd\u7559\u82f1\u6587\u539f\u6587\uff1b\u7cfb\u7edf\u81ea\u52a8\u751f\u6210\u7684\u53e5\u5b50\u5df2\u8bd1\u4e3a"
        "\u4e2d\u6587\u3002",
    ),
    "Prices": (
        "At the repository's prices.",
        "\u6309\u672c\u4ed3\u5e93\u7684\u4ef7\u683c\u8ba1\u7b97\u3002",
    ),
}

# The sentences a page builds from the run's own numbers. Each is a template with
# named fields, English beside Chinese for the same reason the labels are.
TEXT: Mapping[str, Tuple[str, str]] = {
    "gate sentence": (
        "The referee and the judge were not asked: {gate}.",
        "\u672a\u8be2\u95ee\u88c1\u5224\u5458\u4e0e\u6cd5\u5b98\uff1a{gate}\u3002",
    ),
    "gate basis": ("{gate} ({basis})", "{gate}\uff08{basis}\uff09"),
    "gate ai limit": (
        "the 2 km limb of POL-RD-25",
        "POL-RD-25 \u7684 2 \u516c\u91cc\u4e0a\u9650",
    ),
    "gate value": (
        "a value above SGD {threshold} under POL-GEN-22",
        "POL-GEN-22 \u4e0b\u91d1\u989d\u8d85\u8fc7 SGD {threshold}",
    ),
    "gate flag": (
        "a safety flag under POL-GEN-21",
        "POL-GEN-21 \u4e0b\u7684\u5b89\u5168\u6807\u8bb0",
    ),
    "panel": (
        "The panel decided: {agreeing} of {valid} valid drafts agreed and "
        "{threshold} were needed.",
        "\u5408\u8bae\u51b3\u5b9a\uff1a{valid} \u4efd\u6709\u6548\u8349\u7a3f\u4e2d\u6709 "
        "{agreeing} \u4efd\u4e00\u81f4\uff0c\u9700\u8981 {threshold} \u4efd\u3002",
    ),
    "judge": (
        "The judge's own escalation: the panel carried an ESCALATE -- "
        "{agreeing} of {valid} valid drafts agreed and {threshold} were needed.",
        "\u6cd5\u5b98\u81ea\u884c\u8f6c\u4eba\u5de5\uff1a\u5408\u8bae\u901a\u8fc7\u4e86"
        "\u4e00\u4efd\u8f6c\u4eba\u5de5\u88c1\u51b3\u2014\u2014{valid} \u4efd\u6709\u6548"
        "\u8349\u7a3f\u4e2d\u6709 {agreeing} \u4efd\u4e00\u81f4\uff0c\u9700\u8981 "
        "{threshold} \u4efd\u3002",
    ),
    "no majority": (
        "No majority: at most {agreeing} of {valid} valid drafts agreed and "
        "{threshold} were needed, so no ruling was carried.",
        "\u6ca1\u6709\u591a\u6570\uff1a{valid} \u4efd\u6709\u6548\u8349\u7a3f\u4e2d"
        "\u6700\u591a {agreeing} \u4efd\u4e00\u81f4\uff0c\u9700\u8981 {threshold} "
        "\u4efd\uff0c\u56e0\u6b64\u6ca1\u6709\u88c1\u51b3\u88ab\u901a\u8fc7\u3002",
    ),
    "no valid drafts": (
        "No valid drafts: every one of the {votes} drafts was rejected by the "
        "code checks.",
        "\u6ca1\u6709\u6709\u6548\u8349\u7a3f\uff1a{votes} \u4efd\u8349\u7a3f"
        "\u5168\u90e8\u88ab\u4ee3\u7801\u68c0\u67e5\u62d2\u7edd\u3002",
    ),
    "below the bar": (
        "The panel carried a ruling, but its confidence was below the bar the "
        "policy requires, so the case was published as an escalation.",
        "\u5408\u8bae\u901a\u8fc7\u4e86\u4e00\u4efd\u88c1\u51b3\uff0c\u4f46\u5176"
        "\u7f6e\u4fe1\u5ea6\u4f4e\u4e8e\u653f\u7b56\u8981\u6c42\u7684\u4e0b\u9650"
        "\uff0c\u56e0\u6b64\u8be5\u6848\u4ee5\u8f6c\u4eba\u5de5\u516c\u5e03\u3002",
    ),
    "panel short": (
        "panel: {agreeing} of {valid} agreed",
        "\u5408\u8bae\uff1a{valid} \u4efd\u6709\u6548\u8349\u7a3f\u4e2d {agreeing} "
        "\u4efd\u4e00\u81f4",
    ),
    "gate short": ("gate: {gate}", "\u95f8\u95e8\uff1a{gate}"),
    "agrees": (
        "Agrees with the key on all {fields} graded fields: {answer}.",
        "\u4e0e\u7b54\u6848\u4e00\u81f4\uff08\u5168\u90e8 {fields} \u9879\u8bc4\u5206"
        "\u5b57\u6bb5\uff09\uff1a{answer}\u3002",
    ),
    "key line": (
        "The key's ruling: {ruling}",
        "\u7b54\u6848\u7684\u88c1\u51b3\uff1a{ruling}",
    ),
    "yes": ("yes", "\u662f"),
    "no": ("no", "\u5426"),
    "band AI_FINAL": (
        "the AI's ruling is final",
        "\u4eba\u5de5\u667a\u80fd\u7684\u88c1\u51b3\u4e3a\u7ec8\u5c40",
    ),
    "band CONFIDENCE_0_80": (
        "a ruling needs {bar} confidence",
        "\u9700\u8981 {bar} \u7f6e\u4fe1\u5ea6",
    ),
    "band HUMAN_ONLY": ("a person decides", "\u7531\u4eba\u5de5\u51b3\u5b9a"),
    "hero lede": (
        "{category} \u00b7 {set} \u00b7 filed by the {party} \u00b7 "
        "{amount} contested",
        "{category} \u00b7 {set} \u00b7 \u63d0\u4ea4\u65b9{party} \u00b7 "
        "\u4e89\u8bae\u91d1\u989d {amount}",
    ),
    "hero ruling": (
        "Published ruling: {ruling}",
        "\u516c\u5e03\u88c1\u51b3\uff1a{ruling}",
    ),
    "index h1": ("The version-8 cases.", "\u7248\u672c 8 \u7684\u6848\u4ef6\u3002"),
    "index lede": (
        "{total} disputes: dev-v8's {dev} and Ryde's own {ryde}, each on a page "
        "of its own, at policy version 8.",
        "{total} \u4e2a\u4e89\u8bae\uff1adev-v8 \u7684 {dev} \u4e2a\u4e0e Ryde "
        "\u81ea\u5df1\u7684 {ryde} \u4e2a\uff0c\u6bcf\u4e2a\u4e00\u9875\uff0c"
        "\u653f\u7b56\u7248\u672c 8\u3002",
    ),
    "count sets": (
        "dev-v8 {dev}, ryde-v8 {ryde}",
        "dev-v8 {dev} \u4e2a\uff0cryde-v8 {ryde} \u4e2a",
    ),
    "count no person split": (
        "dev-v8 {dev} of {dev_total}, ryde-v8 {ryde} of {ryde_total}",
        "dev-v8 {dev} / {dev_total}\uff0cryde-v8 {ryde} / {ryde_total}",
    ),
    "count gate split": (
        "dev-v8 {dev}, ryde-v8 {ryde}",
        "dev-v8 {dev} \u4e2a\uff0cryde-v8 {ryde} \u4e2a",
    ),
    "col case": ("Case", "\u6848\u4ef6"),
    "col set": ("Set", "\u6570\u636e\u96c6"),
    "col category": ("Category", "\u7c7b\u522b"),
    "col filed by": ("Filed by", "\u63d0\u4ea4\u65b9"),
    "col band": ("Value band", "\u91d1\u989d\u533a\u95f4"),
    "col ruling": ("Published ruling", "\u516c\u5e03\u88c1\u51b3"),
    "col how": ("How it was decided", "\u5982\u4f55\u51b3\u5b9a"),
    "col agrees": ("Agrees with the key", "\u4e0e\u7b54\u6848\u4e00\u81f4"),
    "tokens": (
        "prompt {prompt}, cached {cached}, completion {completion}, total {total}",
        "\u8f93\u5165 {prompt}\uff0c\u7f13\u5b58 {cached}\uff0c\u8f93\u51fa "
        "{completion}\uff0c\u5408\u8ba1 {total}",
    ),
    # The pipeline's own sentences, in part 6. The vote it appends to the judge's
    # explanation has two forms, and a gated case's whole explanation is the
    # pipeline's because the judge was never asked. On a Chinese page these are
    # printed in Chinese, filled from what the run recorded.
    "no bar": ("No bar \u2014 {basis}", "\u4e0d\u8bbe\u95e8\u69db\u2014\u2014{basis}"),
    "count agreement note": (
        "ryde-v8 {ryde} of {ryde_total}; the two sets are never pooled.",
        "ryde-v8 {ryde} / {ryde_total}\uff1b\u4e24\u4e2a\u6570\u636e\u96c6\u4ece\u4e0d\u5408\u5e76\u3002",
    ),
    "vote unanimous": (
        "The judge was asked {n} times on the same inputs and every draft agreed "
        "on this ruling, so it is carried unanimously (vote agreement {a}).",
        "\u6cd5\u5b98\u5c31\u540c\u6837\u7684\u6750\u6599\u88ab\u95ee\u4e86 {n} \u6b21\uff0c\u6bcf\u4efd\u8349\u7a3f\u90fd\u540c\u610f\u8fd9\u4e2a\u88c1\u51b3\uff0c\u56e0\u6b64\u4e00\u81f4\u901a\u8fc7"
        "\uff08\u6295\u7968\u4e00\u81f4\u5ea6 {a}\uff09\u3002",
    ),
    "vote split": (
        "The judge was asked {n} times on the same inputs and {k} of the {m} "
        "drafts agreed on this ruling, so it is carried, not unanimous (vote "
        "agreement {a}).",
        "\u6cd5\u5b98\u5c31\u540c\u6837\u7684\u6750\u6599\u88ab\u95ee\u4e86 {n} \u6b21\uff0c{m} \u4efd\u8349\u7a3f\u4e2d\u6709 {k} \u4efd\u540c\u610f\u8fd9\u4e2a\u88c1\u51b3\uff0c\u56e0\u6b64"
        "\u901a\u8fc7\uff0c\u4f46\u4e0d\u662f\u4e00\u81f4\u901a\u8fc7\uff08\u6295\u7968\u4e00\u81f4\u5ea6 {a}\uff09\u3002",
    ),
    "gated explanation": (
        "Under {clause}, {basis}. The AI prepared the case file -- both advocates "
        "were asked -- and no ruling is issued, so the dispute is escalated to a "
        "human reviewer with both amounts null and no referral. The reason code "
        "is {code}.",
        "\u6309 {clause}\uff0c{basis}\u3002AI \u5df2\u5907\u597d\u6848\u5377\uff08\u53cc\u65b9\u5f8b\u5e08\u90fd\u5df2\u9648\u8ff0\uff09\uff0c\u4f46\u4e0d\u51fa\u88c1\u51b3\uff1a"
        "\u4e89\u8bae\u8f6c\u7ed9\u4eba\u5de5\u5ba1\u6838\u5458\uff0c\u4e24\u4e2a\u91d1\u989d\u90fd\u4e3a\u7a7a\uff0c\u4e5f\u6ca1\u6709\u8f6c\u529e\u3002\u539f\u56e0\u4ee3\u7801\uff1a{code}\u3002",
    ),
}

# The evidence codes the 42 cases carry, in the words a page writes them with.
# The seven artifact types, the three admissibility statuses and the eight
# issues are all here; a code this table does not know is refused, so a later run
# cannot put a code on a page with no words beside it.
EVIDENCE: Mapping[str, Tuple[str, str]] = {
    "TRIP_RECORD": ("Trip record", "\u884c\u7a0b\u8bb0\u5f55"),
    "GPS_TRACE": ("GPS trace", "GPS \u8f68\u8ff9"),
    "CHAT_LOG": ("Chat log", "\u804a\u5929\u8bb0\u5f55"),
    "FARE_BREAKDOWN": ("Fare breakdown", "\u8f66\u8d39\u660e\u7ec6"),
    "RIDER_PROFILE": ("Rider profile", "\u4e58\u5ba2\u8d44\u6599"),
    "DRIVER_PROFILE": ("Driver profile", "\u53f8\u673a\u8d44\u6599"),
    "TRAFFIC_ADVISORY": ("Traffic advisory", "\u4ea4\u901a\u901a\u544a"),
    "COMPLETE": ("complete", "\u5b8c\u6574"),
    "MISSING": ("missing", "\u7f3a\u5931"),
    "IMPAIRED": ("impaired", "\u53d7\u635f"),
    "MISSING_ARTIFACT": ("the file is missing", "\u6587\u4ef6\u7f3a\u5931"),
    "CROSS_SOURCE_CONFLICT": ("the sources disagree", "\u6765\u6e90\u4e92\u76f8\u77db\u76fe"),
    "LANGUAGE_AMBIGUITY": ("ambiguous wording", "\u63aa\u8f9e\u6709\u6b67\u4e49"),
    "TRUNCATED_LOG": ("the log is cut short", "\u8bb0\u5f55\u88ab\u622a\u65ad"),
    "UNREAD_MESSAGE": ("a message was not read", "\u6709\u6d88\u606f\u672a\u8bfb"),
    "GPS_GAP_STRADDLING_CANCELLATION": (
        "a GPS gap across the cancellation",
        "\u53d6\u6d88\u524d\u540e GPS \u4e2d\u65ad",
    ),
    "LOW_SAMPLE_RATE": ("sparse GPS fixes", "GPS \u91c7\u6837\u7a00\u758f"),
    "PARTIAL_RECORD": ("a partial record", "\u8bb0\u5f55\u4e0d\u5b8c\u6574"),
}

# The sentences the code wrote rather than the model: the brief's authority
# block, the version-8 gate's own basis, and the reason a trip record gives for
# having no driver deadline. A Chinese page prints the Chinese; a recorded text
# this table does not know is refused rather than printed in English, so a later
# run cannot put English back on a Chinese page silently.
RECORDED: Mapping[str, str] = {
    "a route deviation (POL-RD-25)": "\u7ed5\u8def\u6848\u4ef6\uff08POL-RD-25\uff09",
    "a no-show below POL-GEN-22's first band, where POL-NS-26 makes the AI "
    "ruling final": "\u91d1\u989d\u4f4e\u4e8e POL-GEN-22 \u7b2c\u4e00\u6863\u7684\u672a\u5230\u573a\u6848\u4ef6\uff0c\u6309 POL-NS-26\uff0cAI \u7684"
    "\u88c1\u51b3\u5373\u4e3a\u6700\u7ec8",
    "a fraud flag on a party's profile (POL-GEN-22)": "\u4e00\u65b9\u8d44\u6599\u5e26\u6b3a\u8bc8\u6807\u8bb0"
    "\uff08POL-GEN-22\uff09",
    "neither a safety flag nor a value above POL-GEN-22's second band": "\u6ca1\u6709\u5b89\u5168"
    "\u6807\u8bb0\uff0c\u91d1\u989d\u4e5f\u4e0d\u9ad8\u4e8e POL-GEN-22 \u7b2c\u4e8c\u6863",
    "a safety flag on the dispute (POL-GEN-21)": "\u4e89\u8bae\u5e26\u5b89\u5168\u6807\u8bb0\uff08POL-GEN-21\uff09",
    "a dispute value above POL-GEN-22's second band": "\u4e89\u8bae\u91d1\u989d\u9ad8\u4e8e POL-GEN-22 \u7b2c\u4e8c\u6863",
    "the deviation is over the POL-RD-25 ceiling this policy applies to an AI "
    "ruling, so the ruling does not stand": "\u7ed5\u8def\u8d85\u8fc7\u672c\u653f\u7b56\u7ed9 AI \u88c1\u51b3\u8bbe\u7684 POL-RD-25 "
    "\u4e0a\u9650\uff0c\u56e0\u6b64 AI \u7684\u88c1\u51b3\u4e0d\u80fd\u6210\u7acb",
    "the dispute carries dispute.safety_flag, and POL-GEN-21 makes a flagged "
    "dispute a person's whatever the category and whatever the value": "\u4e89\u8bae\u5e26\u6709 "
    "dispute.safety_flag\uff1b\u6309 POL-GEN-21\uff0c\u5e26\u6807\u8bb0\u7684\u4e89\u8bae\u4e0d\u8bba\u7c7b\u522b\u548c\u91d1\u989d\u90fd\u7531\u4eba\u51b3\u5b9a",
    "on-demand trip: no scheduled time": "\u5373\u65f6\u884c\u7a0b\uff1a\u6ca1\u6709\u9884\u7ea6\u65f6\u95f4",
}

# The one number these pages need that the brief does not carry: the value above
# which POL-GEN-22 makes a dispute a person's. Read from the version-8 base's own
# general policy -- the file the briefs are built from -- exactly as
# ``ui/site/figures.py`` reads the safety page's thresholds.
_HUMAN_ABOVE: "Optional[Decimal]" = None


def human_above_sgd() -> Decimal:
    """``POL-GEN-22``'s second band edge, from ``policy/v8/general.json``."""
    global _HUMAN_ABOVE
    if _HUMAN_ABOVE is None:
        path = policy_versions.base_directory(POLICY_VERSION) / "general.json"
        general = json.loads(path.read_text(encoding="utf-8"))
        _HUMAN_ABOVE = Decimal(str(general["thresholds"]["human_above_sgd"]))
    return _HUMAN_ABOVE


def human_above_words() -> str:
    """The edge as the page writes it: whole SGD, without the cents."""
    return format(human_above_sgd().normalize(), "f")


def label(key: str, language: str) -> str:
    """One label, in one language. A key this module does not state is refused."""
    if key not in WORDS:
        raise BuildError("{0!r} is not a label this module states".format(key))
    return WORDS[key][0 if language == EN else 1]


def sentence(key: str, language: str, **fields: Any) -> str:
    """One sentence, in one language, with its own numbers filled in."""
    if key not in TEXT:
        raise BuildError("{0!r} is not a sentence this module states".format(key))
    return TEXT[key][0 if language == EN else 1].format(**fields)


def recorded_words(text: Any, language: str) -> str:
    """One of the run's own sentences, in the language the page prints it in.

    The brief's authority block, the gate's own basis and a trip record's reason
    for having no driver deadline are sentences the code wrote rather than the
    model, so a Chinese page prints the Chinese. English is what the run
    recorded, and a recorded text this table does not know is refused rather than
    printed in English on a Chinese page.
    """
    english = str(text)
    if language == EN:
        return english
    try:
        return RECORDED[english]
    except KeyError as exc:
        raise BuildError(
            "the recorded text {0!r} has no Chinese and a Chinese page prints "
            "it".format(english)
        ) from exc


def evidence_words(code: Any, language: str) -> str:
    """One evidence code, in the words of the page's own language."""
    key = str(code)
    try:
        words = EVIDENCE[key]
    except KeyError as exc:
        raise BuildError(
            "the evidence code {0!r} has no words to print".format(key)
        ) from exc
    return words[0 if language == EN else 1]


def codename(code: Any) -> str:
    """A code after the words it stands for, in a small monospace parenthesis."""
    return '<small class="codename">({0})</small>'.format(_t(code))


def worded(words: Any, code: Any) -> str:
    """The words first and the code in the small parenthesis after them."""
    return "{0} {1}".format(_t(words), codename(code))


def category_words(value: Any, language: str) -> str:
    """A category, in the vocabulary the two sites already use for it."""
    code = str(value)
    if language == ZH:
        return site_rows.ZH_CATEGORY.get(code, code)
    return v2.CATEGORY_WORDS.get(code, code)


def ruling_words(value: Any, language: str) -> str:
    """A ruling value, in the words the queue's own vocabulary gives it."""
    code = str(value)
    if language == ZH:
        return site_rows.ZH_RULING.get(code, code)
    return v2.ruling_words(code)


def filed_by_words(value: Any, language: str) -> str:
    """The filing party, in the words the table's own column gives it."""
    code = str(value)
    if language == ZH:
        return site_rows.ZH_FILED_BY.get(code, code)
    return v2.filed_by_words(code)


def party_in_prose(value: Any, language: str) -> str:
    """The filing party as a sentence names it: "filed by the rider"."""
    words = filed_by_words(value, language)
    return words.lower() if language == EN else words


def draft_kind_words(value: Any, language: str) -> str:
    """A draft's kind: sampled, or the same case with the sides swapped."""
    if str(value) == pipeline_module.DRAFT_POSITION_SWAPPED:
        return label("Position swapped", language)
    return label("Sampled", language)


def gate_name(gate: Mapping[str, Any], language: str, with_basis: bool = True) -> str:
    """The version-8 gate that fired, named by the clause and the condition.

    The three limbs are POL-GEN-21 (a flagged dispute), POL-GEN-22 (a value above
    the second band edge) and POL-RD-25 (the 2 km ceiling this policy applies to
    an AI ruling). Which one fired is read from the clause the gate itself cites,
    so a page cannot name a limb the pipeline did not use. ``with_basis`` adds
    the gate's own sentence about the condition; the index's column is a cell and
    carries the name alone.
    """
    clause = str(gate.get("clause") or "")
    basis = str(gate.get("basis") or "")
    if clause == pipeline_module.V7_AI_LIMIT_CLAUSE:
        named = sentence("gate ai limit", language)
    elif clause == pipeline_module.V7_SCOPE_GATE_CLAUSE:
        named = sentence("gate flag", language)
    elif clause == pipeline_module.V7_HUMAN_ONLY_CLAUSE:
        named = sentence("gate value", language, threshold=human_above_words())
    else:
        named = clause or str(gate.get("reason_code") or "")
    if with_basis and basis:
        return sentence(
            "gate basis", language, gate=named, basis=recorded_words(basis, language)
        )
    return named


def gate_sentence(case: V8Case, language: str) -> str:
    """The one sentence a gated case carries where its drafts would be."""
    return sentence(
        "gate sentence", language, gate=gate_name(case.gate or {}, language)
    )


# --------------------------------------------------------------------------
# How it was decided
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Decision:
    """How one case reached its ruling, read off the run's own vote record."""

    kind: str
    agreeing: int
    valid: int
    votes: int
    threshold: int

    def words(self, language: str) -> str:
        return sentence(
            self.kind,
            language,
            agreeing=self.agreeing,
            valid=self.valid,
            votes=self.votes,
            threshold=self.threshold,
        )

    def short(self, language: str) -> str:
        if self.kind == "panel":
            return sentence(
                "panel short",
                language,
                agreeing=self.agreeing,
                valid=self.valid,
                threshold=self.threshold,
            )
        return label(
            {
                "judge": "The judge's own escalation",
                "no majority": "No majority",
                "no valid drafts": "No valid drafts",
                "below the bar": "Below the bar",
            }[self.kind],
            language,
        )


def decision_of(case: V8Case) -> Decision:
    """How one case was decided, from the gate and the vote the run recorded.

    Five shapes, and each is the pipeline's own: the gate ran and the judge was
    never asked; the panel carried a ruling (three of the four drafts, or all
    four); the panel carried an ESCALATE, which is the judge's own escalation;
    the panel did not agree, so no ruling was carried; or the panel carried a
    ruling whose confidence was below the policy's bar, which is published as an
    escalation too and is reported as that rather than as a disagreement.
    """
    if case.gate is not None:
        return Decision("gate", 0, 0, 0, 0)
    vote = case.vote or {}
    votes = int(vote.get("votes") or 0)
    valid = int(vote.get("valid") or 0)
    threshold = int(vote.get("threshold") or 0)
    agreement = vote.get("agreement")
    agreeing = (
        int((Decimal(str(agreement)) * votes).quantize(Decimal(1)))
        if agreement is not None
        else 0
    )
    outcome = str(vote.get("outcome") or "")
    if outcome == pipeline_module.VOTE_NO_VALID_DRAFTS:
        return Decision("no valid drafts", agreeing, valid, votes, threshold)
    carried = agreeing >= threshold and valid >= threshold
    if outcome in CARRIED_OUTCOMES:
        if case.ruling_value == ESCALATE:
            return Decision("judge", agreeing, valid, votes, threshold)
        return Decision("panel", agreeing, valid, votes, threshold)
    if carried:
        return Decision("below the bar", agreeing, valid, votes, threshold)
    return Decision("no majority", agreeing, valid, votes, threshold)


def carries_no_ruling(case: V8Case) -> bool:
    """Whether the run published no ruling at all.

    The six cases the version-8 gate stopped and the two the panel could not
    agree on record a confidence of 0.0 because there is no ruling for one to
    belong to; their page says so rather than printing "0.0". The judge's own
    escalations carried a ruling and keep the confidence they record.
    """
    return decision_of(case).kind in ("gate", "no majority")


def no_bar(case: V8Case) -> bool:
    """Whether the policy sets no confidence bar: the AI's ruling is final.

    The 18 no-show cases whose value is below POL-GEN-22's first band record a
    required confidence of 0.0, because POL-NS-26 makes the AI's ruling final
    there and no bar applies.
    """
    return v2._decimal(case.required_confidence) == 0


def required_bar(case: V8Case, language: str) -> str:
    """The bar a case had to meet and the basis for it, in one cell.

    A case with no bar says so and names the clause; every other bar keeps the
    number the run recorded and the basis the brief states.
    """
    basis = recorded_words(case.required_basis, language)
    if no_bar(case):
        return sentence("no bar", language, basis=_t(basis))
    return "{0} \u2014 {1}".format(_t(case.required_confidence), _t(basis))


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _t(value: Any) -> str:
    """A value as HTML text, ASCII only (``ui.v2.build``'s own writer).

    Every leaf a page prints reaches text here, so this is the one place an
    unknown shape is stopped rather than printed. A mapping or a list that
    arrives is a fact this code has not been taught to render -- a
    ``{value, evidence_id}`` wrapper passed on whole, say -- and rendering it
    would put Python's own ``repr`` on the page, so it is refused and the build
    fails with the shape named.
    """
    if isinstance(value, (Mapping, list)):
        raise BuildError(
            "a leaf reaches text as a {0}: {1!r}".format(type(value).__name__, value)
        )
    return v2._text(value)


def _a(value: Any) -> str:
    """A value as an HTML attribute value, ASCII only."""
    return v2._attribute(value)


def _paragraphs(text: Any) -> str:
    """A run's prose as one paragraph per line, escaped."""
    if text is None:
        return ""
    return "\n".join(
        "<p>{0}</p>".format(_t(line))
        for line in str(text).split("\n")
        if line.strip()
    )


def _scroll(table: str) -> str:
    """A table inside the site's own horizontal-scroll box.

    ``ui/site/src/site.css`` defines ``.scroll-x{overflow-x:auto}`` and this
    builder adds no stylesheet of its own. A five-column drafts table, and the
    run's 40-character commit, are wider than a phone, so every ``table.dt``
    this builder writes is the only child of one of these and the page itself
    stays the width of the viewport.
    """
    return '<div class="scroll-x">{0}</div>'.format(table)


def _grid(cards: Sequence[str], classes: str = "cards c2", columns: int = 2) -> str:
    """A grid of cards, the last one filling its row when the count is odd.

    The two statements and each side's claims sit in ``.cards c2`` grids, two to
    a row. When the count is odd the last card would be the only one in its row
    and half the grid would be empty, so it takes ``span2`` -- part 98's class,
    which ``site.css`` gives a second column -- and the row fills.
    """
    rendered = list(cards)
    if rendered and len(rendered) % columns:
        rendered[-1] = rendered[-1].replace(
            '<div class="card"', '<div class="card span2"', 1
        )
    return '<div class="{0}">{1}</div>'.format(classes, "".join(rendered))


def _table(rows: Sequence[Tuple[str, str]]) -> str:
    """A ``.dt`` table: a label and its value, one row each."""
    body = "".join(
        '<tr><th scope="row">{0}</th><td>{1}</td></tr>'.format(_t(name), value)
        for name, value in rows
    )
    return _scroll('<table class="dt"><tbody>{0}</tbody></table>'.format(body))


def _heading(text: str, language: str, number: Optional[int] = None) -> str:
    """A heading inside a page, in the site's own ``.sh`` shape.

    A numbered part gets the site's section heading -- the part number in the
    ``.kicker`` and the title in the ``.display`` line. A block inside a part
    gets the ``.kicker`` alone, because a case page has seven parts and a dozen
    blocks and a 44-pixel heading on each of the dozen is not a hierarchy.
    """
    if number is None:
        return '<p class="kicker">{0}</p>'.format(_t(text))
    return (
        '<div class="sh left"><p class="kicker">{0}</p><h2 class="display">{1}</h2>'
        "</div>"
    ).format(_t(label("Part", language).format(number)), _t(text))


def _section(number: int, title: str, body: str, language: str) -> str:
    """One numbered part of a case page, in the site's own section shape."""
    return (
        '<section class="paper"><div class="wrap">\n'
        "{0}\n{1}\n</div></section>"
    ).format(_heading(title, language, number), body)


def _band_words(case: V8Case, language: str) -> str:
    """The value band, with what it means in the words of the policy."""
    band = str(case.value_band)
    if band == brief_module.VALUE_BAND_AI_FINAL:
        gloss = sentence("band AI_FINAL", language)
    elif band == brief_module.VALUE_BAND_CONFIDENCE:
        gloss = sentence(
            "band CONFIDENCE_0_80", language, bar=str(case.required_confidence)
        )
    elif band == brief_module.VALUE_BAND_HUMAN_ONLY:
        gloss = sentence("band HUMAN_ONLY", language)
    else:
        return _t(band)
    return worded(gloss, band)


def _money(value: Any, case: V8Case) -> str:
    """An amount as the page writes it: the currency and two decimals."""
    return _t(v2._money(value, case.currency))


def _yes_no(value: Any, language: str) -> str:
    return sentence("yes" if value else "no", language)


def _km(value: Any) -> str:
    return "none" if value is None else "{0} km".format(_t(value))


def _coded(value: str, clause: Optional[str]) -> str:
    """A figure with the clause it comes from, where the block states one."""
    return value if not clause else "{0} ({1})".format(value, _t(clause))


def _ruling_line(case: V8Case, language: str) -> str:
    """The published ruling in words, with its amounts and its referrals."""
    ruling = case.ruling
    parts = [worded(ruling_words(case.ruling_value, language), case.ruling_value)]
    if case.ruling_value in v2.REFUND_RULINGS:
        parts.append(
            "{0} {1}".format(
                _t(label("Amount contested", language)),
                _money(ruling.get("amount_sgd"), case),
            )
        )
    if case.ruling_value == pipeline_module.DRIVER_COMPENSATION:
        parts.append(
            "{0} {1}".format(
                _t(label("Driver if upheld", language)),
                _money(ruling.get("driver_compensation_sgd"), case),
            )
        )
    if carries_no_ruling(case):
        confidence = label("No ruling carried", language)
    else:
        confidence = _t("none" if case.confidence is None else case.confidence)
    parts.append(
        "{0} {1}".format(_t(label("Confidence", language)), confidence)
    )
    referrals = ruling.get("referrals") or []
    listed = "; ".join(_t(item) for item in referrals) or _t(label("None", language))
    parts.append("{0} {1}".format(_t(label("Referrals", language)), listed))
    return " &middot; ".join(parts)


# --------------------------------------------------------------------------
# Part 1: the outcome
# --------------------------------------------------------------------------
def outcome_body(case: V8Case, language: str) -> str:
    """The ruling, how it was decided, the bar it had to meet, and the key."""
    description = SET_DESCRIPTIONS[case.set_name][0 if language == EN else 1]
    rows = [
        (label("Case", language), _t(case.case_no)),
        (
            label("Category", language),
            worded(category_words(case.category, language), case.category),
        ),
        (
            label("Set", language),
            "{0} ({1})".format(_t(case.set_name), _t(description)),
        ),
        (label("Filed by", language), _t(filed_by_words(case.filed_by, language))),
        (label("Amount contested", language), _money(case.amount, case)),
        (label("Value band", language), _band_words(case, language)),
        (label("Published ruling", language), _ruling_line(case, language)),
        (label("Required confidence", language), required_bar(case, language)),
    ]
    decision = decision_of(case)
    how = gate_sentence(case, language) if decision.kind == "gate" else decision.words(language)
    key = case.key
    key_amount = (
        " {0}".format(v2._money(key.amount_sgd, case.currency))
        if key.amount_sgd is not None
        else ""
    )
    agrees = sentence(
        "agrees",
        language,
        fields=len(GRADED_FIELDS),
        answer=sentence("yes" if case.score.exact else "no", language),
    )
    key_line = sentence(
        "key line",
        language,
        ruling="{0}{1}".format(
            worded(ruling_words(key.ruling, language), key.ruling), key_amount
        ),
    )
    return (
        _table(rows)
        + '<p class="lede">{0}</p>'.format(_t(how))
        # The key's ruling carries the code in the small parenthesis, so the
        # sentence is inserted as it stands: the words, the code and the amount
        # are escaped where they are written, and the template's own text holds
        # no markup.
        + "<p>{0} {1}</p>".format(_t(agrees), key_line)
    )


# --------------------------------------------------------------------------
# Part 2: the dispute
# --------------------------------------------------------------------------
def dispute_body(case: V8Case, language: str) -> str:
    """Who filed, the amount and its band, both statements, and the evidence."""
    dispute = case.dispute
    counterparty = dispute.get("counterparty_statement") or {}
    cards = []
    if dispute.get("claim_text") is not None:
        cards.append(
            '<div class="card"><span class="kicker">{0}</span><p>{1}</p></div>'.format(
                _t(label("Filer", language)), _t(dispute.get("claim_text"))
            )
        )
    if counterparty.get("text") is not None:
        cards.append(
            '<div class="card"><span class="kicker">{0} ({1})</span>'
            "<p>{2}</p></div>".format(
                _t(label("Other party", language)),
                _t(filed_by_words(counterparty.get("submitted_by"), language)),
                _t(counterparty.get("text")),
            )
        )
    evidence_rows = []
    for artifact in case.brief["case"]["evidence"]:
        admissibility = artifact.get("admissibility") or {}
        status = admissibility.get("status")
        detail = worded(evidence_words(status, language), status)
        for issue in admissibility.get("issues") or []:
            detail += "; {0}".format(worded(evidence_words(issue, language), issue))
        evidence_type = artifact.get("evidence_type")
        evidence_rows.append(
            (
                artifact.get("evidence_id"),
                "{0} &middot; {1}".format(
                    worded(evidence_words(evidence_type, language), evidence_type),
                    detail,
                ),
            )
        )
    parts = [
        _table(
            [
                (
                    label("Filed by", language),
                    _t(filed_by_words(case.filed_by, language)),
                ),
                (label("Amount contested", language), _money(case.amount, case)),
                (label("Value band", language), _band_words(case, language)),
            ]
        ),
        _grid(cards),
        _heading(label("Evidence", language), language),
        _scroll(
            '<table class="dt"><thead><tr><th>{0}</th><th>{1}</th></tr></thead>'
            "<tbody>{2}</tbody></table>".format(
                _t(label("Evidence id", language)),
                _t(label("Evidence type", language)),
                "".join(
                    '<tr><td class="n">{0}</td><td>{1}</td></tr>'.format(
                        _t(name), detail
                    )
                    for name, detail in evidence_rows
                ),
            )
        ),
    ]
    if language == ZH:
        parts.append(
            '<p class="muted">{0}</p>'.format(_t(label("Statements note", language)))
        )
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Part 3: what the code worked out
# --------------------------------------------------------------------------
def _deviation_rows(deviation: Mapping[str, Any], language: str) -> List[Tuple[str, str]]:
    """The route-deviation block's own facts, and the two clause figures."""
    return [
        (label("Actual distance", language), _km(_leaf(deviation, "actual_distance_km"))),
        (
            label("Recommended distance", language),
            _km(_leaf(deviation, "optimal_distance_km")),
        ),
        (
            label("Deviation km", language),
            _coded(
                _km(_leaf(deviation, "deviation_km")),
                _clause(deviation, "deviation_km"),
            ),
        ),
        (
            label("Tolerance", language),
            _coded(
                _km(_leaf(deviation, "tolerance_km")),
                _clause(deviation, "tolerance_km"),
            ),
        ),
        (
            label("AI limit", language),
            _coded(
                _km(_leaf(deviation, "ai_limit_km")),
                _clause(deviation, "ai_limit_km"),
            ),
        ),
        (
            label("The limit applies", language),
            _yes_no(_leaf(deviation, "ai_limit_applied"), language),
        ),
        (
            label("Over the limit", language),
            _yes_no(_leaf(deviation, "over_ai_limit"), language),
        ),
    ]


def _free_wait_rows(free_wait: Mapping[str, Any], language: str) -> List[Tuple[str, str]]:
    """The free-wait block: arrival, the window, the cancellation, and when."""
    return [
        (label("Arrived", language), _t(v2._clock(_leaf(free_wait, "arrived_at")))),
        (
            label("Starts", language),
            "{0} ({1})".format(
                _t(v2._clock(_leaf(free_wait, "starts_at"))),
                _t(_leaf(free_wait, "starts_from")),
            ),
        ),
        (label("Ends", language), _t(v2._clock(_leaf(free_wait, "ends_at")))),
        (label("Cancelled", language), _t(v2._clock(_leaf(free_wait, "cancelled_at")))),
        (
            label("After the free wait", language),
            _yes_no(_leaf(free_wait, "cancelled_after_free_wait"), language),
        ),
        (label("Free wait seconds", language), _t(_leaf(free_wait, "free_wait_sec"))),
    ]


def _sourced_instant(leaf: Any) -> str:
    """A ``{value, evidence_id}`` instant: the time of day, and its evidence id.

    The brief wraps a derived instant with the artifact it came from. The free
    wait's own times are read through ``_leaf`` and shown as the clock alone;
    the driver's deadline is the one instant the page shows with its source
    beside it, the way the page's other sourced figures carry the clause they
    come from, so it is rendered ``08:50:00 (EV-TRIP-00903)`` and never as the
    wrapper it arrives in.
    """
    if not isinstance(leaf, Mapping):
        return _t(v2._clock(leaf))
    clock = _t(v2._clock(leaf.get("value")))
    evidence = leaf.get("evidence_id")
    return "{0} ({1})".format(clock, _t(evidence)) if evidence else clock


def _deadline_rows(deadline: Mapping[str, Any], language: str) -> List[Tuple[str, str]]:
    """The driver's deadline, or the record's reason for having none."""
    when = deadline.get("deadline")
    return [
        (
            label("Driver deadline", language),
            _sourced_instant(when)
            if when
            else _t(recorded_words(deadline.get("reason"), language)),
        ),
        (
            label("Late seconds", language),
            _coded(
                _t(_leaf(deadline, "driver_late_after_scheduled_sec")),
                _clause(deadline, "driver_late_after_scheduled_sec"),
            ),
        ),
    ]


def _contact_rows(contact: Mapping[str, Any], language: str) -> List[Tuple[str, str]]:
    """What the driver sent and called before cancelling, and whether it met it."""
    return [
        (label("Messages", language), _t(_leaf(contact, "message_count"))),
        (label("Calls", language), _t(_leaf(contact, "call_count"))),
        (
            label("Obligation met", language),
            _yes_no(_leaf(contact, "obligation_met"), language),
        ),
        (
            label("Record complete", language),
            _yes_no(_leaf(contact, "complete"), language),
        ),
    ]


def _money_rows(money: Mapping[str, Any], case: V8Case, language: str) -> List[Tuple[str, str]]:
    """The fare record's own figures, block by block, for this category."""
    rows: List[Tuple[str, str]] = []
    if "excess_distance_fare_sgd" in money:
        rows.append(
            (
                label("Excess distance fare", language),
                _coded(
                    _money(_leaf(money, "excess_distance_fare_sgd"), case),
                    _clause(money, "excess_distance_fare_sgd"),
                ),
            )
        )
        rows.append(
            (label("Per km rate", language), _money(_leaf(money, "per_km_rate_sgd"), case))
        )
        rows.append((label("Deviation km", language), _km(_leaf(money, "deviation_km"))))
    if "fee_charged_sgd" in money:
        rows.append(
            (
                label("Fee charged", language),
                _coded(
                    _money(_leaf(money, "fee_charged_sgd"), case),
                    _clause(money, "fee_charged_sgd"),
                ),
            )
        )
        rows.append(
            (label("Policy fee", language), _money(_leaf(money, "policy_fee_sgd"), case))
        )
        rows.append(
            (
                label("Fee matches policy", language),
                _yes_no(_leaf(money, "fee_matches_policy"), language),
            )
        )
        rows.append(
            (
                label("Refund if voided", language),
                _money(_leaf(money, "refund_if_voided_sgd"), case),
            )
        )
        rows.append(
            (
                label("Driver if upheld", language),
                _money(_leaf(money, "driver_compensation_if_upheld_sgd"), case),
            )
        )
    rows.append(
        (
            label("Refund already issued", language),
            _coded(
                _money(_leaf(money, "refund_already_issued_sgd"), case),
                _clause(money, "refund_already_issued_sgd"),
            ),
        )
    )
    return rows


def derived_body(case: V8Case, language: str) -> str:
    """The brief's derived blocks and the authority block, block by block.

    Only the blocks the case has are drawn: a route-deviation case has no free
    wait and a no-show has no deviation, and a page that showed an empty table
    for the block a case does not have would be inventing a fact.
    """
    trip = _derived(case.brief, "TRIP_RECORD", brief_module.V7_KEY) or {}
    money = _derived(case.brief, "FARE_BREAKDOWN", brief_module.MONEY_KEY) or {}
    blocks: List[Tuple[str, List[Tuple[str, str]]]] = []

    deviation = trip.get("deviation")
    if isinstance(deviation, Mapping):
        blocks.append((label("Deviation", language), _deviation_rows(deviation, language)))
    free_wait = trip.get("free_wait")
    if isinstance(free_wait, Mapping):
        blocks.append((label("Free wait", language), _free_wait_rows(free_wait, language)))
    deadline = trip.get("driver_deadline")
    if isinstance(deadline, Mapping):
        blocks.append(
            (label("Driver deadline", language), _deadline_rows(deadline, language))
        )
    contact = trip.get("contact_before_cancel")
    if isinstance(contact, Mapping):
        blocks.append(
            (
                label("Contact before cancelling", language),
                _contact_rows(contact, language),
            )
        )
    if isinstance(money, Mapping):
        blocks.append((label("Money", language), _money_rows(money, case, language)))

    authority_rows = [
        (label("Value band", language), _band_words(case, language)),
        (label("Fraud flags", language), _t(_leaf(case.authority, "fraud_flags"))),
        (label("Required confidence", language), required_bar(case, language)),
        (
            label("Safety flag", language),
            _yes_no(_leaf(case.authority, "safety_flag"), language),
        ),
        (
            label("A person decides", language),
            "{0} ({1})".format(
                _yes_no(_leaf(case.authority, "human_only"), language),
                _t(recorded_words(case.authority.get("human_only_basis"), language)),
            ),
        ),
    ]
    blocks.append((label("Authority", language), authority_rows))

    return "\n".join(
        "{0}\n{1}".format(_heading(title, language), _table(rows))
        for title, rows in blocks
    )


# --------------------------------------------------------------------------
# Part 4: the two sides
# --------------------------------------------------------------------------
def _claim_card(case: V8Case, claim: Mapping[str, Any], number: int, language: str) -> str:
    """One advocate's claim: its text, its ids, and the referee's verdict."""
    status = claim.get("status")
    reason = claim.get("reason_code")
    if status is None:
        verdict = label("No referee verdict", language)
    elif status == "KEPT":
        verdict = worded(label("Kept", language), reason or status)
    else:
        verdict = worded(label("Dropped", language), reason or status)
    evidence = ", ".join(_t(item) for item in claim.get("evidence_ids") or []) or _t(
        label("None", language)
    )
    clauses = ", ".join(_t(item) for item in claim.get("clause_ids") or []) or _t(
        label("None", language)
    )
    return (
        '<div class="card"><span class="kicker">{0}</span><p>{1}</p>'
        '<p class="mono">{2}: {3}</p><p class="mono">{4}: {5}</p>'
        "<p>{6}: {7}</p></div>"
    ).format(
        _t(label("Claim", language).format(number)),
        _t(claim.get("text")),
        _t(label("Evidence ids", language)),
        evidence,
        _t(label("Clause ids", language)),
        clauses,
        _t(label("Verdict", language)),
        verdict,
    )


def sides_body(case: V8Case, language: str) -> str:
    """Each advocate's claims, with the referee's verdict where there is one."""
    parts = []
    if case.gate is not None:
        parts.append('<p class="lede">{0}</p>'.format(_t(gate_sentence(case, language))))
    for side, key in (("RIDER", "Rider advocate"), ("DRIVER", "Driver advocate")):
        claims = v2._claims(case.transcript, side)
        parts.append(_heading(label(key, language), language))
        if not claims:
            parts.append('<p class="muted">{0}</p>'.format(_t(label("None", language))))
            continue
        parts.append(
            _grid(
                [
                    _claim_card(case, claim, number, language)
                    for number, claim in enumerate(claims, 1)
                ]
            )
        )
    if language == ZH:
        parts.append(
            '<p class="muted">{0}</p>'.format(_t(label("Statements note", language)))
        )
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Part 5: the judge's drafts
# --------------------------------------------------------------------------
def _draft_proposal(case: V8Case, draft: Mapping[str, Any], language: str) -> str:
    """The ruling and the amounts the vote recorded this draft as proposing.

    The vote drops a voided draft's proposal -- there is nothing to carry -- so a
    draft the code checks refused proposes nothing here, and the Validity column
    says which check refused it and why.
    """
    proposal = draft.get("proposal") or {}
    if not proposal.get("ruling"):
        return label("No proposed ruling", language)
    parts = [
        "{0} ({1})".format(
            _t(ruling_words(proposal["ruling"], language)), _t(proposal["ruling"])
        )
    ]
    if proposal.get("amount_sgd") is not None:
        parts.append(
            "{0} {1}".format(
                _t(label("Amount contested", language)),
                _money(proposal.get("amount_sgd"), case),
            )
        )
    if proposal.get("driver_compensation_sgd") is not None:
        parts.append(
            "{0} {1}".format(
                _t(label("Driver if upheld", language)),
                _money(proposal.get("driver_compensation_sgd"), case),
            )
        )
    return " &middot; ".join(parts)


def drafts_body(case: V8Case, language: str) -> str:
    """Every draft: its kind, what it proposed, its confidence, its validity."""
    if case.gate is not None:
        return '<p class="lede">{0}</p>\n<p class="muted">{1}</p>'.format(
            _t(gate_sentence(case, language)), _t(label("No drafts", language))
        )
    rows = []
    for draft in case.drafts:
        if draft["valid"]:
            validity = label("Valid", language)
        else:
            reasons = v2._void_reasons(draft["abstention"])
            validity = "{0}: {1}".format(
                label("Voided", language),
                "; ".join(
                    "{0} ({1}){2}".format(
                        v2.draft_words(code),
                        code,
                        ": {0}".format(detail) if detail else "",
                    )
                    for code, detail in reasons
                )
                or label("None", language),
            )
        rows.append(
            "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td></tr>".format(
                _t(draft["draft"]),
                _t(draft_kind_words(draft["kind"], language)),
                _draft_proposal(case, draft, language),
                _t("none" if draft["confidence"] is None else draft["confidence"]),
                _t(validity),
            )
        )
    return _scroll(
        (
            '<table class="dt"><thead><tr><th>{0}</th><th>{1}</th><th>{2}</th>'
            "<th>{3}</th><th>{4}</th></tr></thead><tbody>{5}</tbody></table>"
        ).format(
            _t(label("Draft", language)),
            _t(label("Kind", language)),
            _t(label("Proposed", language)),
            _t(label("Confidence", language)),
            _t(label("Validity", language)),
            "".join(rows),
        )
    )


# --------------------------------------------------------------------------
# Part 6: the ruling's explanation
# --------------------------------------------------------------------------
# The sentences the pipeline writes for itself in part 6: the vote it appends to
# the judge's explanation, in its two forms, and the whole explanation of a case
# the gate stopped before the judge was asked. Matching them is what lets the
# code's own words be printed in Chinese while the model's own words are left
# exactly as the run recorded them.
VOTE_UNANIMOUS_EN = re.compile(
    r"The judge was asked (?P<n>\d+) times on the same inputs and every draft "
    r"agreed on this ruling, so it is carried unanimously "
    r"\(vote agreement (?P<a>[0-9.]+)\)\."
)
VOTE_SPLIT_EN = re.compile(
    r"The judge was asked (?P<n>\d+) times on the same inputs and (?P<k>\d+) of "
    r"the (?P<m>\d+) drafts agreed on this ruling, so it is carried, not "
    r"unanimous \(vote agreement (?P<a>[0-9.]+)\)\."
)
GATED_EN = re.compile(
    r"Under (?P<clause>[A-Z0-9\-]+), (?P<basis>.+?)\. The AI prepared the case "
    r"file -- both advocates were asked -- and no ruling is issued, so the "
    r"dispute is escalated to a human reviewer with both amounts null and no "
    r"referral\. The reason code is (?P<code>[A-Z0-9_]+)\."
)


def split_vote(explanation: str) -> Optional[Tuple[str, Mapping[str, str], bool]]:
    """The reasoning, the vote sentence the pipeline appended, and its form.

    The pipeline ends every judge-asked explanation with one sentence of its own
    -- the vote the panel took -- and the judge's reasoning is everything before
    it. The sentence is matched at the very end, so a run's prose that mentions
    the vote in passing is left where it is.
    """
    text = explanation.rstrip()
    for pattern, unanimous in ((VOTE_UNANIMOUS_EN, True), (VOTE_SPLIT_EN, False)):
        match = pattern.search(text)
        if match is not None and not text[match.end():].strip():
            return text[: match.start()].rstrip(), match.groupdict(), unanimous
    return None


def chinese_explanation(case: V8Case, explanation: str) -> List[str]:
    """Part 6 of a Chinese page: the reasoning, and the code's words in Chinese.

    A gated case's explanation was written by the pipeline -- the judge was never
    asked -- so it is printed whole in Chinese. Every other explanation is the
    judge's own reasoning, which stays English, with the pipeline's vote sentence
    split off the end and printed after it in Chinese. An explanation whose shape
    this code does not know is refused rather than printed in English.
    """
    if case.gate is not None:
        match = GATED_EN.match(explanation.strip())
        if match is None:
            raise BuildError(
                "the gated explanation {0!r} is not the sentence this builder "
                "knows".format(explanation)
            )
        fields = match.groupdict()
        return [
            _paragraphs(
                sentence(
                    "gated explanation",
                    ZH,
                    clause=fields["clause"],
                    basis=recorded_words(fields["basis"], ZH),
                    code=fields["code"],
                )
            )
        ]
    split = split_vote(explanation)
    if split is None:
        return [_paragraphs(explanation)]
    reasoning, fields, unanimous = split
    parts: List[str] = []
    if reasoning.strip():
        parts.append(_paragraphs(reasoning))
    if unanimous:
        words = sentence("vote unanimous", ZH, n=fields["n"], a=fields["a"])
    else:
        words = sentence(
            "vote split",
            ZH,
            n=fields["n"],
            k=fields["k"],
            m=fields["m"],
            a=fields["a"],
        )
    parts.append("<p>{0}</p>".format(_t(words)))
    return parts


def explanation_body(case: V8Case, language: str) -> str:
    """The ruling's explanation: the judge's own words, and the code's own.

    The judge's reasoning is the model's text and stays English on both pages.
    The pipeline writes one sentence of its own at the end of it -- the vote --
    and writes a gated case's explanation whole, because the judge was never
    asked; on a Chinese page those are printed in Chinese.
    """
    explanation = str(case.ruling.get("explanation") or "")
    if language == EN:
        parts = [_paragraphs(explanation)]
    else:
        parts = chinese_explanation(case, explanation)
    if language == ZH:
        parts.append(
            '<p class="muted">{0}</p>'.format(_t(label("Statements note", language)))
        )
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Part 7: the run
# --------------------------------------------------------------------------
def run_body(case: V8Case, language: str) -> str:
    """The commit, the clock, the tokens and the model cost."""
    tokens = case.document.get("tokens") or {}
    prompt = int(tokens.get("prompt_tokens") or 0)
    cached = int(tokens.get("cached_tokens") or 0)
    completion = int(tokens.get("completion_tokens") or 0)
    total = int(tokens.get("total_tokens") or 0)
    return _table(
        [
            (label("Model", language), _t(MODEL)),
            (label("Commit", language), _t(case.document.get("git_commit"))),
            (
                label("Wall seconds", language),
                _t(v2._seconds(case.document.get("wall_seconds"))),
            ),
            (
                label("Tokens", language),
                _t(
                    sentence(
                        "tokens",
                        language,
                        prompt=prompt,
                        cached=cached,
                        completion=completion,
                        total=total,
                    )
                ),
            ),
            (
                label("Cost", language),
                "{0} ({1})".format(
                    _t(v2._usd(v2._cost_usd(prompt, cached, completion))),
                    _t(label("Prices", language)),
                ),
            ),
        ]
    )


# --------------------------------------------------------------------------
# A case page
# --------------------------------------------------------------------------
def _crumb(language: str) -> str:
    """The breadcrumb: the site's front page, the cases page, then this one."""
    if language == EN:
        return '<a href="index.html">Home</a> / <a href="cases.html">Cases</a>'
    return (
        '<a href="index.zh.html">\u9996\u9875</a> / '
        '<a href="cases.zh.html">\u6848\u4f8b</a>'
    )


def case_main(case: V8Case, language: str) -> str:
    """One case page's ``<main>``, top to bottom."""
    description = SET_DESCRIPTIONS[case.set_name][0 if language == EN else 1]
    hero = (
        '<section class="band phero"><div class="wrap">\n'
        '<p class="crumb">{0} / {1} {2}</p>\n'
        '<h1 class="display">{1} {2}</h1>\n'
        '<p class="lede">{3}</p>\n'
        '<p class="lede">{4}</p>\n'
        "</div></section>"
    ).format(
        _crumb(language),
        _t(label("Case", language)),
        _t(case.case_no),
        _t(
            sentence(
                "hero lede",
                language,
                category=category_words(case.category, language),
                set=description,
                party=party_in_prose(case.filed_by, language),
                amount=v2._money(case.amount, case.currency),
            )
        ),
        _t(
            sentence(
                "hero ruling",
                language,
                ruling=ruling_words(case.ruling_value, language),
            )
        ),
    )
    sections = [
        _section(1, label("Outcome", language), outcome_body(case, language), language),
        _section(2, label("The dispute", language), dispute_body(case, language), language),
        _section(
            3,
            label("What the code worked out", language),
            derived_body(case, language),
            language,
        ),
        _section(4, label("The two sides", language), sides_body(case, language), language),
        _section(
            5,
            label("The judge's drafts", language),
            drafts_body(case, language),
            language,
        ),
        _section(
            6,
            label("The ruling's explanation", language),
            explanation_body(case, language),
            language,
        ),
        _section(7, label("The run", language), run_body(case, language), language),
    ]
    return hero + "\n" + "\n".join(sections)


# --------------------------------------------------------------------------
# The index
# --------------------------------------------------------------------------
def counts(cases: Sequence[V8Case]) -> Dict[str, Any]:
    """The four counts the index states, each read off the rows it prints."""
    out: Dict[str, Any] = {
        "total": len(cases),
        "no_person": sum(1 for case in cases if case.ruling_value != ESCALATE),
        "gates": sum(1 for case in cases if case.gate is not None),
        "sets": {},
    }
    for set_name in SET_ORDER:
        rows = [case for case in cases if case.set_name == set_name]
        out["sets"][set_name] = {
            "total": len(rows),
            "no_person": sum(1 for row in rows if row.ruling_value != ESCALATE),
            "gates": sum(1 for row in rows if row.gate is not None),
            "agree": sum(1 for row in rows if row.score.exact),
        }
    return out


def index_main(cases: Sequence[V8Case], language: str) -> str:
    """The index: the four counts, then one row per case."""
    figures = counts(cases)
    dev = figures["sets"]["dev-v8"]
    ryde = figures["sets"]["ryde-v8"]
    # The big line is the number alone: a sentence in the 56-pixel figure face
    # wraps to a different height on each card. What the number counts is the
    # kicker above it and the line below it.
    cards = [
        (
            label("Cases", language),
            _t(figures["total"]),
            sentence("count sets", language, dev=dev["total"], ryde=ryde["total"]),
        ),
        (
            label("Decided with no person", language),
            "{0}/{1}".format(figures["no_person"], figures["total"]),
            sentence(
                "count no person split",
                language,
                dev=dev["no_person"],
                dev_total=dev["total"],
                ryde=ryde["no_person"],
                ryde_total=ryde["total"],
            ),
        ),
        (
            label("Stopped before the judge", language),
            _t(figures["gates"]),
            sentence("count gate split", language, dev=dev["gates"], ryde=ryde["gates"]),
        ),
        (
            label("Agreement with the key, dev-v8", language),
            "{0}/{1}".format(dev["agree"], dev["total"]),
            sentence(
                "count agreement note",
                language,
                ryde=ryde["agree"],
                ryde_total=ryde["total"],
            ),
        ),
    ]
    cards_html = "".join(
        '<div class="card"><span class="kicker">{0}</span>'
        '<p class="big">{1}</p><p>{2}</p></div>'.format(_t(title), _t(value), _t(note))
        for title, value, note in cards
    )
    columns = (
        "col case",
        "col set",
        "col category",
        "col filed by",
        "col band",
        "col ruling",
        "col how",
        "col agrees",
    )
    rows = []
    for case in cases:
        decision = decision_of(case)
        if decision.kind == "gate":
            how = sentence(
                "gate short",
                language,
                gate=gate_name(case.gate or {}, language, with_basis=False),
            )
        else:
            how = decision.short(language)
        rows.append(
            '<tr><td class="n"><a href="{0}">{1}</a></td><td>{2}</td><td>{3}</td>'
            "<td>{4}</td><td>{5}</td><td>{6}</td><td>{7}</td><td>{8}</td></tr>".format(
                _a(case.link if language == EN else case.zh_link),
                _t(case.case_no),
                _t(case.set_name),
                _t(category_words(case.category, language)),
                _t(filed_by_words(case.filed_by, language)),
                _t(case.value_band),
                worded(ruling_words(case.ruling_value, language), case.ruling_value),
                how,
                _t(sentence("yes" if case.score.exact else "no", language)),
            )
        )
    hero = (
        '<section class="band phero"><div class="wrap">\n'
        '<p class="crumb">{0} / {1}</p>\n'
        '<h1 class="display">{2}</h1>\n'
        '<p class="lede">{3}</p>\n'
        "</div></section>"
    ).format(
        _crumb(language),
        _t(label("Cases", language)),
        _t(sentence("index h1", language)),
        _t(
            sentence(
                "index lede",
                language,
                total=figures["total"],
                dev=dev["total"],
                ryde=ryde["total"],
            )
        ),
    )
    table_html = (
        '<table class="dt"><thead><tr>{0}</tr></thead><tbody>{1}</tbody></table>'
    ).format(
        "".join("<th>{0}</th>".format(_t(sentence(key, language))) for key in columns),
        "".join(rows),
    )
    table = (
        '<section class="paper"><div class="wrap">\n'
        '<div class="cards c4">{0}</div>\n'
        '<div class="tscroll" tabindex="0" role="region">{1}</div>\n'
        "</div></section>"
    ).format(cards_html, _scroll(table_html))
    return hero + "\n" + table


# --------------------------------------------------------------------------
# The site shell
# --------------------------------------------------------------------------
MAIN_RE = re.compile(r'<main id="main">.*?</main>', re.S)
TITLE_RE = re.compile(r"<title>.*?</title>", re.S)
DESCRIPTION_RE = re.compile(r'<meta name="description" content="[^"]*">')
OG_TITLE_RE = re.compile(r'<meta property="og:title" content="[^"]*">')
OG_DESCRIPTION_RE = re.compile(r'<meta property="og:description" content="[^"]*">')
ALTERNATE_RE: Mapping[str, "re.Pattern[str]"] = {
    "en": re.compile(r'<link rel="alternate" hreflang="en" href="[^"]*">'),
    "zh": re.compile(r'<link rel="alternate" hreflang="zh" href="[^"]*">'),
}

SCRIPT_RE = re.compile(r"(<script\b[^>]*>)(.*?)(</script>)", re.S)

# The href the shell's own language switch carries, per language. Once the two
# ``hreflang`` alternates above have been rewritten, exactly two of these are
# left -- the two switches, in the header's own two copies -- and they are what
# points a reader at the other language's page for this same case.
SWITCH_HREF: Mapping[str, str] = {EN: 'href="cases.zh.html"', ZH: 'href="cases.html"'}


def _entity(text: str) -> str:
    """``text`` with every non-ASCII character written as a numeric reference."""
    return "".join(
        character if ord(character) < 128 else "&#x{0:x};".format(ord(character))
        for character in text
    )


def _script_safe(text: str) -> str:
    """``text`` with every non-ASCII character written as a JS ``\\uXXXX`` escape.

    A ``<script>`` element's content is raw text: an HTML character reference
    inside it is not decoded, so the escape has to be the JavaScript one.
    """
    out: List[str] = []
    for character in text:
        code = ord(character)
        if code < 128:
            out.append(character)
        elif code <= 0xFFFF:
            out.append("\\u{0:04x}".format(code))
        else:
            offset = code - 0x10000
            out.append(
                "\\u{0:04x}\\u{1:04x}".format(
                    0xD800 + (offset >> 10), 0xDC00 + (offset & 0x3FF)
                )
            )
    return "".join(out)


def ascii_page(text: str) -> str:
    """One page with every non-ASCII character escaped, or a refusal.

    The repository's language rule governs every tracked text file outside
    ``runs/`` and the product site's own files; these pages are this repository's
    writing, so they are ASCII. HTML text and attributes take a numeric
    character reference and a ``<script>`` element takes a JavaScript escape,
    which render as the same characters. A page that still holds a non-ASCII
    character after both is refused rather than written.
    """
    parts: List[str] = []
    position = 0
    for match in SCRIPT_RE.finditer(text):
        parts.append(_entity(text[position:match.start()]))
        parts.append(match.group(1))
        parts.append(_script_safe(match.group(2)))
        parts.append(match.group(3))
        position = match.end()
    parts.append(_entity(text[position:]))
    page = "".join(parts)
    for character in page:
        if ord(character) >= 128:
            raise BuildError(
                "a page still carries the character U+{0:04X} after escaping".format(
                    ord(character)
                )
            )
    return page


def shell(language: str) -> str:
    """The site's own page source for one language, read and not edited."""
    return (site_build.PAGES_DIR / SHELL_PAGE[language]).read_text(encoding="utf-8")


def page(
    language: str,
    *,
    title: str,
    description: str,
    main: str,
    en_href: str,
    zh_href: str,
) -> str:
    """One page: the site's shell with its head and ``<main>`` set for a case.

    The shell carries the head, the header, the language switch and the footer.
    Four things are set for this page: the ``<title>``, the description and the
    ``og:`` tags, the ``hreflang`` alternates, and the two language-switch links,
    which point at the other language's page for the same case.

    What this builder writes -- the title, the description and the ``<main>`` --
    is passed through :func:`_defuse`, so a key-shaped run of characters in a
    run's own prose cannot be read as a leaked credential. The shell is not: it
    is the policy owner's imported design, published byte for byte at
    ``ui/dist/cases.html``, and a stylesheet whose property names had been
    rewritten would not be the design any more.
    """
    text = shell(language)
    replacements = (
        (TITLE_RE, "<title>{0}</title>".format(_defuse(title))),
        (
            DESCRIPTION_RE,
            '<meta name="description" content="{0}">'.format(_defuse(description)),
        ),
        (
            OG_TITLE_RE,
            '<meta property="og:title" content="{0}">'.format(_defuse(title)),
        ),
        (
            OG_DESCRIPTION_RE,
            '<meta property="og:description" content="{0}">'.format(
                _defuse(description)
            ),
        ),
        (
            ALTERNATE_RE["en"],
            '<link rel="alternate" hreflang="en" href="{0}">'.format(en_href),
        ),
        (
            ALTERNATE_RE["zh"],
            '<link rel="alternate" hreflang="zh" href="{0}">'.format(zh_href),
        ),
    )
    for pattern, replacement in replacements:
        text, count = pattern.subn(replacement, text, count=1)
        if count != 1:
            raise BuildError(
                "the page shell {0} carries no {1} to set".format(
                    SHELL_PAGE[language], pattern.pattern
                )
            )
    old = SWITCH_HREF[language]
    if text.count(old) != 2:
        raise BuildError(
            "the page shell {0} carries {1} language switches and not two".format(
                SHELL_PAGE[language], text.count(old)
            )
        )
    text = text.replace(old, 'href="{0}"'.format(zh_href if language == EN else en_href))
    text, count = MAIN_RE.subn(
        '<main id="main">\n{0}\n</main>'.format(_defuse(main)), text, count=1
    )
    if count != 1:
        raise BuildError(
            'the page shell {0} carries no <main id="main"> to replace'.format(
                SHELL_PAGE[language]
            )
        )
    return ascii_page(site_build.assemble(text, site_build.shared_blocks()))


def _defuse(text: str) -> str:
    """``text`` with the first hyphen of every key-shaped run entity-escaped.

    ``ui.v2.build``'s own writer, applied to the parts of a page this builder
    writes. A key-shaped run is two letters and a hyphen at the start of a longer
    word, and ordinary prose produces one -- a hyphenated phrase such as "ask to
    cancel" is one, and it occurs in a transcript this site draws from -- so a
    page carrying it verbatim would be read as a leaked credential by a scan
    looking for one.
    """
    return v2.defuse_key_shaped(text)


def case_page(case: V8Case, language: str) -> str:
    """One case's page in one language."""
    return page(
        language,
        title="{0} {1} - {2} - Tribunal Agent".format(
            label("Case", language),
            case.case_no,
            category_words(case.category, language),
        ),
        description=(
            "Case {0} of {1}: {2}, filed by the {3}. The evidence, both sides' "
            "arguments, the drafts and the ruling, at policy version 8.".format(
                case.case_no,
                case.set_name,
                category_words(case.category, language),
                filed_by_words(case.filed_by, language),
            )
        ),
        main=case_main(case, language),
        en_href=case.link,
        zh_href=case.zh_link,
    )


def index_page(cases: Sequence[V8Case], language: str) -> str:
    """The index in one language."""
    return page(
        language,
        title="The version-8 cases - Tribunal Agent",
        description="All 42 version-8 cases: dev-v8's 40 and Ryde's own 2.",
        main=index_main(cases, language),
        en_href=INDEX_PAGE,
        zh_href=INDEX_PAGE.replace(".html", ".zh.html"),
    )


# --------------------------------------------------------------------------
# The paths, and the build
# --------------------------------------------------------------------------
def case_numbers(set_name: str) -> List[int]:
    """One set's case numbers, ascending, without reading a case."""
    return sorted(development_sets.named(set_name).cases)


def written_paths() -> frozenset:
    """Every path this builder writes, relative to ``ui/dist/``.

    Exposed so a test can hold the builders apart: this builder's paths are
    disjoint from the site's, the queue's and the replay's, and this is this
    builder's own list. It **lists the paths without building anything** -- the
    set order and the case numbers, both of which are the registrations' own --
    so it answers on a machine whose libm cannot rebuild a recorded brief, where
    the pages themselves cannot be built at all.
    """
    names = [INDEX_PAGE, INDEX_PAGE.replace(".html", ".zh.html")]
    for set_name in SET_ORDER:
        for case_no in case_numbers(set_name):
            names.append(CASE_PAGE.format(case_no))
            names.append(CASE_PAGE.format(case_no).replace(".html", ".zh.html"))
    return frozenset(names)


def pages() -> List[Tuple[Path, str]]:
    """Every page this builder writes, as ``(destination, text)``.

    The one place the pages are decided, so a writing build and ``--check``
    cannot disagree about which files there are.
    """
    cases = read_every_case()
    out: List[Tuple[Path, str]] = []
    for case in cases:
        for language in LANGUAGES:
            out.append(
                (
                    DIST_DIR / (case.link if language == EN else case.zh_link),
                    case_page(case, language),
                )
            )
    out.append((DIST_DIR / INDEX_PAGE, index_page(cases, EN)))
    out.append(
        (DIST_DIR / INDEX_PAGE.replace(".html", ".zh.html"), index_page(cases, ZH))
    )
    return out


def _write_or_check(path: Path, text: str, check: bool) -> int:
    data = text.encode("utf-8")
    committed = path.read_bytes() if path.is_file() else None
    if check:
        if committed == data:
            print("{0}: identical".format(path.relative_to(PROJECT_ROOT)))
            return 0
        print("{0}: differs".format(path.relative_to(PROJECT_ROOT)))
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return 0


def build(check: bool = False) -> int:
    """Write every page, or compare the committed bytes with a fresh build."""
    status = 0
    for destination, text in pages():
        # What this builder writes was defused where it was written, so any
        # entity-escaped hyphen here is one, and the count is reported rather
        # than the rewrite done quietly.
        defused = text.count(v2.DEFUSED)
        if defused:
            print(
                "{0}: {1} key-shaped run(s) written with an entity-escaped "
                "hyphen, so a scan cannot read them as a credential".format(
                    destination, defused
                )
            )
        status |= _write_or_check(destination, text, check)
    if check and status:
        print(
            "the version-8 pages differ from a fresh build; run "
            "`python3 -m ui.v8.build`",
            file=sys.stderr,
        )
    return 0 if status == 0 else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m ui.v8.build",
        description=(
            "Build a page for every version-8 case, in English and in Chinese, "
            "plus the index. Read-only on everything outside ui/dist/; no model "
            "call, no network."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the committed files with a fresh build and write nothing",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return build(check=args.check)
    except BuildError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
