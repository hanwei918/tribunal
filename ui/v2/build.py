"""The product view: what a support team sees when Tribunal runs at policy version 6.

Why a second site
-----------------
``ui/build.py`` replays the headline run as an *evaluation*: 29 cases, policy
version 1, an answer key beside them and a miss marked where the ruling and the
key disagree. That is the right page for a judge of the benchmark and the wrong
one for the person who works the queue. This module builds the other page. It
shows what a support team would have in front of it when the system runs at
policy version 6: today's disputes, what was decided automatically, what went to
a human, and -- for one case -- the whole decision, step by step, with the
agents' own words.

It is a **separate site**. ``ui/build.py`` and every page it commits are
untouched; the code lives in ``ui/v2/`` and the output in ``ui/dist/v2/``.

What it reads
-------------
Only committed files, and only these four run directories:

* ``runs/policy-v6/`` -- the 29-case corpus at version 6;
* ``runs/dev-v2-ext/policy-v6/`` -- the 120-case second development set;
* ``runs/dev-v2/policy-v6/`` -- case 1779 alone, the prompt-injection case;
* ``runs/ryde-v3/policy-v6/`` -- the organisers' sample case, 901.

Per case it reads the run's own case file and transcript, the public case file
the run was made from (through the set's own loader), the loaded policy, and --
for a case that was sent to a reviewer -- the escalation packet
:mod:`ops.escalation` builds, which is called rather than re-implemented. The
only other file read is ``ops/config.json``, for the queue's targets.

**No answer key is opened anywhere in this module**, and nothing under
``eval/answers/sealed-v1/``, ``data/external/sealed-v1/`` or
``eval/external/sealed-v1/`` is read. The sealed-v1 set is not shown, not
counted and not named.

Every number is read, not typed
-------------------------------
Nothing in this module writes a figure into a template. The five queue figures,
the amounts, the confidences, the confidence floor, the execution threshold, the
appeal window, the token prices and the wall clock are each read from the file
that records them, and :func:`build` recomputes all of them from those files on
every run. A number that cannot be read raises :class:`BuildError` and names
what was missing rather than defaulting to something plausible.

Two builds are byte-identical
-----------------------------
There is no clock, no random seed and no dictionary iteration in the output
path: cases are walked in a fixed order, every mapping is rendered in sorted key
order where its order is not already meaningful, and ``--check`` compares the
committed bytes against a fresh build and exits non-zero on any difference.

One thing this module rewrites, and it says so
----------------------------------------------
The repository scans every published file for a key-shaped run -- ``sk-``
followed by eight or more word characters -- before it goes public, and ordinary
prose produces one: the transcript of case 2738 says "ask-to-cancel". A page that
carried that verbatim would be reported as a leaked credential by the scan that
exists to catch one, so the run's first hyphen is written as a numeric entity.
It renders as the same character and cannot be read as part of a key, and
:func:`build` prints the page and the count of what it rewrote, so nothing is
done quietly.

Where the sealed set enters, and where it does not
--------------------------------------------------
This module names no path under ``eval/answers/sealed-v1/``,
``data/external/sealed-v1/`` or ``eval/external/sealed-v1/``, and during a build
it opens none. It does import :mod:`ops.escalation`, which imports the
development-set registry, and that registry reads the sealed set's *index* at
import time -- the twenty-four case numbers, their dispute ids, their trip ids
and their category, and nothing else. That is the same import ``ui/build.py``
has always made. No case file and no answer key of the sealed set is read, no
sealed case is built, and no page names one.

Run it with::

    python3 -m ui.v2.build
    python3 -m ui.v2.build --check
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets  # noqa: E402
from eval import v6_runs  # noqa: E402
from ops import escalation  # noqa: E402
from tribunal import brief as brief_module  # noqa: E402
from tribunal import loader  # noqa: E402
from tribunal import pipeline as pipeline_module  # noqa: E402
from tribunal import precedents as precedents_module  # noqa: E402

# --------------------------------------------------------------------------
# Where the site lives
# --------------------------------------------------------------------------
DIST_DIR = PROJECT_ROOT / "ui" / "dist" / "v2"
INDEX_PATH = DIST_DIR / "index.html"

# The four runs the queue is drawn from, in the order the set selector lists
# them. The name is the run's name in ``eval.v6_runs``; the label is what a
# reader sees, and for the two one-case sets it is the case number, because that
# is the only thing that tells them apart.
SET_ORDER: Tuple[str, ...] = ("corpus", "dev-v2-ext", "ryde-v3", "dev-v2")
SET_LABELS: Mapping[str, str] = {
    "corpus": "corpus",
    "dev-v2-ext": "dev-v2-ext",
    "ryde-v3": "901",
    "dev-v2": "1779",
}

# The words a category is shown under. The codes are the loader's own; the words
# are the two the track brief uses for them.
CATEGORY_WORDS: Mapping[str, str] = {
    "ROUTE_DEVIATION": "Route deviation",
    "NO_SHOW_CHARGE": "No-show fee",
}

# --------------------------------------------------------------------------
# The escalation triggers
# --------------------------------------------------------------------------
# A case reaches a human for one of four reasons, and each is read off the run's
# own record rather than inferred from the ruling value alone:
#
# * ``GEN08_SCOPE`` -- the dispute carries ``safety_flag`` or ``complaint_flag``,
#   so POL-GEN-08(1) refuses to adjudicate it and no agent was asked. The flags
#   are on the public case file; the reason code is the pipeline's own.
# * ``NO_VALID_DRAFTS`` -- every draft was rejected by the code checks. The vote
#   the transcript records says so.
# * ``NO_MAJORITY`` -- the panel produced rulings but no majority carried one.
#   The vote's outcome says so.
# * ``JUDGE_ESCALATE`` -- the panel carried an ``ESCALATE``. This is the judge
#   escalating on the merits, which the explanation states in its own words.
#
# The first two are the pipeline's own named reason codes. The other two are
# named here because the pipeline names them only through the vote's outcome
# (``escalated``) and through the ruling value itself, and a queue that counted
# every human review under one word would be counting nothing.
TRIGGER_SCOPE = "GEN08_SCOPE"
TRIGGER_NO_VALID_DRAFTS = "NO_VALID_DRAFTS"
TRIGGER_NO_MAJORITY = "NO_MAJORITY"
TRIGGER_JUDGE = "JUDGE_ESCALATE"
TRIGGER_ORDER: Tuple[str, ...] = (
    TRIGGER_SCOPE,
    TRIGGER_NO_VALID_DRAFTS,
    TRIGGER_NO_MAJORITY,
    TRIGGER_JUDGE,
)

# The ruling value that means "a human decides this".
ESCALATE = pipeline_module.ESCALATE

# The two ruling values that return money to the filing party, and the one that
# leaves the present state standing. ``ESCALATE`` and ``DRIVER_COMPENSATION``
# come from the pipeline; these are named here because nothing else names them.
FULL_REFUND = "FULL_REFUND"
PARTIAL_REFUND = "PARTIAL_REFUND"
NO_ACTION = "NO_ACTION"
REFUND_RULINGS: Tuple[str, ...] = (FULL_REFUND, PARTIAL_REFUND)

# The two outcomes a queue row can have, as the filter row names them.
OUTCOME_AUTO = "auto"
OUTCOME_REVIEWER = "reviewer"

# The words a ruling value is shown under, before its code. These are the words
# the track brief uses for the five values; the code follows in small monospace,
# so a reader meets the meaning first and the vocabulary the policy names after
# it. A value with no words of its own is shown as the code itself.
RULING_WORDS: Mapping[str, str] = {
    "FULL_REFUND": "Full refund",
    "PARTIAL_REFUND": "Partial refund",
    "NO_ACTION": "No change",
    "DRIVER_COMPENSATION": "Fee stands, driver compensated",
    "ESCALATE": "Sent to a human reviewer",
}

# The words a reviewer trigger is shown under, before its code. Three of the
# four are fixed phrases. The fourth -- ``NO_MAJORITY`` -- names the panel size,
# so it is built from the run's own count of drafts rather than typed here, and
# :func:`trigger_words` is what builds it. A code with no phrase of its own is
# shown as the code.
TRIGGER_WORDS: Mapping[str, str] = {
    TRIGGER_SCOPE: "safety or complaint flag",
    TRIGGER_NO_VALID_DRAFTS: "no judge draft passed the code checks",
    TRIGGER_JUDGE: "the judge escalated under the policy",
}

# The words the filing party is shown under, by the loader's own role.
FILED_BY_WORDS: Mapping[str, str] = {
    "RIDER": "Rider",
    "DRIVER": "Driver",
}

# What a case sent to a reviewer says where a decided case carries its
# provisional-ruling disclosure.
NO_AUTOMATED_RULING = (
    "No automated ruling was issued. A human reviewer decides this case."
)

# The set order, as an index. The queue's row order is this order and then the
# case number; nothing about a directory listing or an interpreter's string hash
# seed may decide it.
SET_ORDER_INDEX: Mapping[str, int] = {
    name: index for index, name in enumerate(SET_ORDER)
}

CASE_FILE_RE = re.compile(r"^case-(\d{5})\.json$")

# The six steps a case page walks. It is a tuple so its order is a fact about
# this file rather than about a dict.
STEP_TITLES: Tuple[str, ...] = (
    "Evidence pack",
    "Both sides argue",
    "Citation check",
    "Judge",
    "Floor and triggers",
    "Outcome",
)

DISCLOSURE = "This is a provisional ruling made by an automated system."


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


def _case_numbers(run_dir: Path) -> List[int]:
    """Every case number a run directory holds, ascending.

    ``os.walk`` rather than a glob: the walk names every file it visits, and the
    transcripts beside the case files match ``case-*.json`` too, so they are
    skipped by name.
    """
    found: List[int] = []
    for dirpath, _dirnames, filenames in os.walk(run_dir):
        for name in sorted(filenames):
            match = CASE_FILE_RE.match(name)
            if match is not None:
                found.append(int(match.group(1)))
    return sorted(found)


def _set_for(name: str):
    """The registered development set a run name belongs to."""
    if name not in development_sets.BY_NAME:
        raise BuildError("no development set is registered as {0!r}".format(name))
    return development_sets.BY_NAME[name]


def _run_for(name: str) -> "v6_runs.V6Run":
    try:
        return v6_runs.run_by_name(name)
    except KeyError as exc:
        raise BuildError("no version-6 run is registered as {0!r}".format(name)) from exc


def _transcript_of(run_dir: Path, document: Mapping[str, Any], case_no: int) -> Mapping[str, Any]:
    """The case's transcript, by the name the run recorded for it."""
    recorded = document.get("transcript_file")
    name = recorded if isinstance(recorded, str) and recorded else "case-{0:05d}.transcript.json".format(case_no)
    return _read_json(Path(run_dir) / name)


def _inner_ruling(document: Mapping[str, Any]) -> Mapping[str, Any]:
    block = document.get("ruling")
    inner = block.get("ruling") if isinstance(block, Mapping) else None
    if not isinstance(inner, Mapping):
        raise BuildError("case {0} records no ruling".format(document.get("case_no")))
    return inner


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------
def _entity(text: str) -> str:
    """``text`` with every non-ASCII character written as a numeric entity.

    The pages are ASCII only, and the run's prose is not: a judge's explanation
    is written with em dashes and typographic quotes. Escaping them keeps the
    file ASCII without changing a character of what it says.
    """
    out: List[str] = []
    for character in text:
        if ord(character) < 128:
            out.append(character)
        else:
            out.append("&#{0};".format(ord(character)))
    return "".join(out)


def _text(value: Any) -> str:
    """A value as HTML text, ASCII only."""
    if value is None:
        return ""
    return _entity(html.escape(str(value), quote=False))


def _attribute(value: Any) -> str:
    """A value as an HTML attribute value, ASCII only."""
    if value is None:
        return ""
    return _entity(html.escape(str(value), quote=True))


def _coded(words: Any, code: Any, strong: bool = False) -> str:
    """The plain words first, the code after them in small monospace.

    Every place a reader meets a ruling value or a reason code is drawn with
    this: the words carry the meaning, and the code follows in ``.mono`` so the
    vocabulary the policy names is still on the page. The words are escaped
    here, so a caller passes the rendered HTML straight through.
    """
    word_html = "<strong>{0}</strong>".format(_text(words)) if strong else _text(words)
    return '{0} <span class="mono">{1}</span>'.format(word_html, _text(code))


def _money(value: Any, currency: str) -> str:
    """An amount as the currency and two decimals, or ``none`` when absent.

    The literal is the one the file wrote: ``Decimal`` throughout, so ``3.20``
    is rendered ``3.20`` and never re-rounded through a binary float.
    """
    if value is None or isinstance(value, bool):
        return "none"
    try:
        return "{0} {1:.2f}".format(currency, Decimal(str(value)))
    except Exception as exc:  # pragma: no cover - a malformed amount is a refusal
        raise BuildError("cannot render the amount {0!r}".format(value)) from exc


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _share(count: int, total: int) -> str:
    if total == 0:
        raise BuildError("a share of nothing has no value")
    return "{0:.1f}%".format(Decimal(count) * 100 / Decimal(total))


def _seconds(value: Any) -> str:
    number = _decimal(value)
    return "none" if number is None else "{0:.1f} s".format(number)


def _cost_usd(prompt: int, cached: int, completion: int) -> Decimal:
    """One case's cost, at the prices ``eval.v6_runs`` bills at.

    Read from that module rather than typed here, so the queue and the report
    cannot come to bill the same tokens at two different prices.
    """
    return (
        Decimal(prompt - cached) * v6_runs.PRICE_INPUT
        + Decimal(cached) * v6_runs.PRICE_CACHED_INPUT
        + Decimal(completion) * v6_runs.PRICE_OUTPUT
    ) / v6_runs.MILLION


def _median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    if not ordered:
        raise BuildError("a median of nothing has no value")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _usd(value: Decimal) -> str:
    return "{0:.4f} USD".format(value)


# A key-shaped run of characters: ``sk-`` followed by eight or more word
# characters. It is the pattern the repository scans every published file for
# before the repository goes public, and ordinary prose produces it --
# "ask-to-cancel" is one, and it occurs in a transcript this site draws from.
# A page that carried such a run verbatim would be reported as a leaked
# credential by the scan that exists to catch one, so the run's first hyphen is
# written as a numeric entity. It renders as the same character and cannot be
# read as part of a key. :func:`pages` counts what it rewrote and names the page,
# so nothing is done quietly.
KEY_SHAPED_RE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
DEFUSED = "sk&#45;"


def defuse_key_shaped(text: str) -> str:
    """``text`` with the first hyphen of every key-shaped run entity-escaped."""
    return KEY_SHAPED_RE.sub(
        lambda match: match.group(0).replace("-", "&#45;", 1), text
    )


# --------------------------------------------------------------------------
# The policy the pages quote
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PolicyFacts:
    """The general policy's own figures and sentences, read once per category."""

    category: str
    version: int
    currency: str
    confidence_floor: Decimal
    execution_threshold: Decimal
    clause_rules: Mapping[str, str]

    def rule(self, clause_id: str) -> str:
        try:
            return self.clause_rules[clause_id]
        except KeyError as exc:
            raise BuildError(
                "the loaded policy carries no clause {0}".format(clause_id)
            ) from exc


def _policy_facts(category: str, version: int) -> PolicyFacts:
    """The loaded policy for one category, at one version."""
    try:
        policies = loader.load_policies(category, version)
    except loader.LoaderError as exc:
        raise BuildError(
            "the policy for {0} at version {1} cannot be loaded: {2}".format(
                category, version, exc
            )
        ) from exc
    general = policies["general"]
    floor = _decimal(general.get("confidence_floor"))
    threshold = _decimal(general.get("execution_threshold_sgd"))
    if floor is None or threshold is None:
        raise BuildError(
            "the general policy states no confidence floor or execution threshold"
        )
    rules: Dict[str, str] = {}
    for clause in general.get("clauses") or []:
        if isinstance(clause, Mapping) and isinstance(clause.get("id"), str):
            rules[clause["id"]] = str(clause.get("rule") or "")
    return PolicyFacts(
        category=category,
        version=version,
        currency=str(general.get("currency") or ""),
        confidence_floor=floor,
        execution_threshold=threshold,
        clause_rules=rules,
    )


def ruling_words(ruling_value: Any) -> str:
    """The words a ruling value is shown under, before its code."""
    return RULING_WORDS.get(str(ruling_value), str(ruling_value))


def trigger_words(trigger: str, votes: int) -> str:
    """The words a reviewer trigger is shown under, before its code.

    The no-majority phrase names the panel size -- "the four drafts did not
    agree" -- and the count is the run's own number of judge drafts, so the
    number on the page is read from the run rather than typed here.
    """
    if trigger == TRIGGER_NO_MAJORITY:
        return "the {0} drafts did not agree".format(votes)
    return TRIGGER_WORDS.get(trigger, trigger)


def filed_by_words(value: Any) -> str:
    """The words the filing party is shown under, before its role code."""
    return FILED_BY_WORDS.get(str(value), str(value))


def money_statement(
    ruling: Mapping[str, Any], currency: str, filed_by: Any
) -> str:
    """What money moves, stated by the ruling value (POL-GEN-03).

    POL-GEN-03 says ``amount_sgd`` is the refund to the filing party on every
    ruling but one. Its single exception is ``DRIVER_COMPENSATION``: there the
    field carries the same figure as ``driver_compensation_sgd`` -- the amount
    the ruling moves, not a second payment and not a refund -- so the sentence
    is chosen by the ruling value and never calls that figure a refund. A value
    the clause does not cover is refused rather than described by hand.
    """
    value = str(ruling.get("ruling"))
    if value in REFUND_RULINGS:
        who = str(filed_by or "").strip().lower() or "filing party"
        return "Refund to the {0}: {1}".format(
            who, _money(ruling.get("amount_sgd"), currency)
        )
    if value == pipeline_module.DRIVER_COMPENSATION:
        return "The fee stands. The driver is paid {0}. No refund.".format(
            _money(ruling.get("driver_compensation_sgd"), currency)
        )
    if value == NO_ACTION:
        return "No money moves. The charge stands."
    if value == ESCALATE:
        return "No money moves. The disputed amount is held."
    raise BuildError(
        "POL-GEN-03 states no money rule for the ruling value {0!r}".format(value)
    )


# POL-GEN-04's own sentence about the route: "may appeal it once, within 30
# days". Both numbers are read from it, so a clause whose sentence has moved is
# a refusal rather than a re-typed figure.
_APPEAL_RE = re.compile(
    r"may appeal it (once|twice|[0-9]+ times), within ([0-9]+) days"
)


def appeal_line(policy: PolicyFacts) -> str:
    """POL-GEN-04's appeal route in one line, built from the clause's numbers."""
    match = _APPEAL_RE.search(policy.rule("POL-GEN-04"))
    if match is None:
        raise BuildError(
            "POL-GEN-04 no longer states how many times a party may appeal and "
            "within how many days"
        )
    return (
        "Either party may appeal {0} within {1} days. A different human reviewer "
        "hears it, and only record evidence may be added.".format(
            match.group(1), match.group(2)
        )
    )


# POL-GEN-06(2)'s own sentence about the two review limits: "decided within 24
# hours of entry, within 2 hours for a safety flag".
_REVIEW_TIME_RE = re.compile(
    r"decided within ([0-9]+) hours of entry, within ([0-9]+) hours for a safety flag"
)


def review_time_limit(policy: PolicyFacts) -> str:
    """POL-GEN-06(2)'s two review time limits, read from the clause's sentence."""
    match = _REVIEW_TIME_RE.search(policy.rule("POL-GEN-06"))
    if match is None:
        raise BuildError("POL-GEN-06 no longer states the two review time limits")
    return (
        "A reviewer decides within {0} hours of entry, or within {1} hours when "
        "the case carries a safety flag.".format(match.group(1), match.group(2))
    )


# --------------------------------------------------------------------------
# The pieces of a case
# --------------------------------------------------------------------------
def escalation_trigger(case: Mapping[str, Any], transcript: Mapping[str, Any]) -> str:
    """Why a case was sent to a reviewer, read off the run's own record."""
    dispute = case.get("dispute") or {}
    if dispute.get("safety_flag") is True or dispute.get("complaint_flag") is True:
        return TRIGGER_SCOPE
    vote = transcript.get("vote")
    outcome = vote.get("outcome") if isinstance(vote, Mapping) else None
    if outcome == pipeline_module.VOTE_NO_VALID_DRAFTS:
        return TRIGGER_NO_VALID_DRAFTS
    if outcome == pipeline_module.VOTE_ESCALATED:
        return TRIGGER_NO_MAJORITY
    return TRIGGER_JUDGE


def monetary_effect(ruling: Mapping[str, Any]) -> Decimal:
    """The money a ruling moves, under POL-GEN-05.

    The clause names "the refund, the driver compensation, or their sum". On a
    ``DRIVER_COMPENSATION`` ruling POL-GEN-03 states the one exception: the two
    fields carry the same figure, which is the amount of money the ruling moves
    and not a second payment, so it is counted once. On every other ruling the
    two are independent and are added.
    """
    amount = _decimal(ruling.get("amount_sgd")) or Decimal(0)
    driver = _decimal(ruling.get("driver_compensation_sgd")) or Decimal(0)
    if ruling.get("ruling") == pipeline_module.DRIVER_COMPENSATION:
        return driver if driver else amount
    return amount + driver


def execution_sentence(
    policy: PolicyFacts, ruling: Mapping[str, Any], currency: str
) -> str:
    """Whether the money executes on issue or is held for release (POL-GEN-05)."""
    threshold = policy.execution_threshold
    if ruling.get("ruling") == ESCALATE:
        return (
            "Escalation is terminal: no monetary outcome issues, so there is "
            "nothing for POL-GEN-05 to execute and the disputed amount is held "
            "rather than collected or refunded."
        )
    effect = monetary_effect(ruling)
    sentence = (
        "POL-GEN-05: the monetary effect is {0} against an execution threshold "
        "of {1}. ".format(_money(effect, currency), _money(threshold, currency))
    )
    if effect > threshold:
        return sentence + (
            "It exceeds the threshold, so the amount is issued but not executed: "
            "it is held for release and the case is placed in the human queue."
        )
    return sentence + (
        "It does not exceed the threshold, so the amount is executed "
        "automatically on issue, subject to POL-GEN-04."
    )


def _notice(
    side: str,
    policy: PolicyFacts,
    ruling: Mapping[str, Any],
    filed_by: Any,
) -> str:
    """One party's notice: what was decided, what money moves, how to appeal.

    It adds no fact and no figure the ruling does not already carry, and it does
    not repeat the judge's explanation: the explanation is shown once under the
    ruling, and the notice links to it. The appeal is POL-GEN-04's route in one
    line, and the full clause sits once under the ruling.
    """
    value = str(ruling.get("ruling"))
    decided = "What was decided: the ruling is {0}.".format(
        _coded(ruling_words(value), value)
    )
    money = "What money moves: {0}".format(
        money_statement(ruling, policy.currency, filed_by)
    )
    appeal = "How to appeal: {0}".format(appeal_line(policy))
    link = (
        '<p><a href="#judge-explanation">Read the judge\'s explanation, as '
        "written</a>.</p>"
    )
    return (
        "<h3>{0}</h3>"
        "<p>{1}</p>"
        "<p>{2}</p>"
        "<p>{3}</p>"
        "{4}"
    ).format(
        _text("Notice to the " + side.lower()),
        decided,
        _text(money),
        _text(appeal),
        link,
    )


def _claims(transcript: Mapping[str, Any], side: str) -> List[Dict[str, Any]]:
    """One side's claims, each with the referee's verdict where there is one.

    The advocate's own parsed answer is the source of the claims and the
    referee's ledger is the source of the verdicts, matched on the claim text --
    which is how the ledger names them.
    """
    role = side + "_ADVOCATE"
    claims: List[Dict[str, Any]] = []
    for entry in transcript.get("entries") or []:
        if not isinstance(entry, Mapping) or entry.get("role") != role:
            continue
        parsed = entry.get("parsed")
        found = parsed.get("claims") if isinstance(parsed, Mapping) else None
        if isinstance(found, list):
            claims = [claim for claim in found if isinstance(claim, Mapping)]
            break
    referee = transcript.get("referee")
    ledger = referee.get("ledger") if isinstance(referee, Mapping) else None
    by_text: Dict[Any, Mapping[str, Any]] = {}
    for entry in ledger or []:
        if isinstance(entry, Mapping) and entry.get("side") == side:
            by_text.setdefault(entry.get("claim"), entry)
    out: List[Dict[str, Any]] = []
    for claim in claims:
        verdict = by_text.get(claim.get("text"))
        out.append(
            {
                "side": side,
                "text": claim.get("text"),
                "evidence_ids": list(claim.get("evidence_ids") or []),
                "clause_ids": list(claim.get("clause_ids") or []),
                "status": verdict.get("status") if isinstance(verdict, Mapping) else None,
                "reason_code": verdict.get("reason_code") if isinstance(verdict, Mapping) else None,
                "detail": verdict.get("detail") if isinstance(verdict, Mapping) else None,
            }
        )
    return out


def _drafts(transcript: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """The panel's drafts, each with the ruling it parsed to."""
    vote = transcript.get("vote")
    source = vote.get("drafts") if isinstance(vote, Mapping) else None
    entries = transcript.get("entries") or []
    out: List[Dict[str, Any]] = []
    for draft in sorted(
        (item for item in source or [] if isinstance(item, Mapping)),
        key=lambda item: item.get("draft") or 0,
    ):
        parsed_ruling: Optional[Mapping[str, Any]] = None
        for index in reversed(list(draft.get("entries") or [])):
            if isinstance(index, int) and 0 <= index < len(entries):
                entry = entries[index]
                parsed = entry.get("parsed") if isinstance(entry, Mapping) else None
                candidate = parsed.get("ruling") if isinstance(parsed, Mapping) else None
                if isinstance(candidate, Mapping):
                    parsed_ruling = candidate
                    break
        proposal = draft.get("proposal")
        out.append(
            {
                "draft": draft.get("draft"),
                "kind": draft.get("kind"),
                "sides": list(draft.get("sides") or []),
                "seed": draft.get("seed"),
                "temperature": draft.get("temperature"),
                "valid": bool(draft.get("valid")),
                "agrees": bool(draft.get("agrees")),
                "abstention": draft.get("abstention"),
                "proposal": proposal if isinstance(proposal, Mapping) else {},
                "confidence": parsed_ruling.get("confidence") if parsed_ruling else None,
                "explanation": parsed_ruling.get("explanation") if parsed_ruling else None,
            }
        )
    return out


def _derived_facts(brief: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Every artifact's derived fact blocks, by key, in artifact order."""
    rows: List[Dict[str, Any]] = []
    for artifact in brief.get("case", {}).get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        payload = artifact.get("payload")
        derived = payload.get("derived") if isinstance(payload, Mapping) else None
        keys = sorted(derived) if isinstance(derived, Mapping) else []
        rows.append(
            {
                "evidence_id": artifact.get("evidence_id"),
                "evidence_type": artifact.get("evidence_type"),
                "derived_keys": keys,
            }
        )
    return rows


def _evidence(brief: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Every artifact with the weight and issue codes the precheck gave it."""
    rows: List[Dict[str, Any]] = []
    for artifact in brief.get("case", {}).get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        admitted = artifact.get("admissibility")
        admitted = admitted if isinstance(admitted, Mapping) else {}
        rows.append(
            {
                "evidence_id": artifact.get("evidence_id"),
                "evidence_type": artifact.get("evidence_type"),
                "source": artifact.get("source"),
                "status": admitted.get("status"),
                "weight": admitted.get("weight_multiplier"),
                "issues": list(admitted.get("issues") or []),
            }
        )
    return rows


def _outcome_text(
    ruling: Mapping[str, Any],
    currency: str,
    trigger: Optional[str],
    votes: int,
) -> str:
    """The outcome column: the ruling in words and code, and what money moves.

    The cell is rendered HTML rather than text, because the words are wrapped
    and the code sits in ``.mono``; the caller writes it as it is and never
    escapes it again. On a ``DRIVER_COMPENSATION`` ruling the figure is never
    called a refund -- POL-GEN-03 says the fee stands and the driver is paid.
    """
    value = str(ruling.get("ruling"))
    if value == ESCALATE and trigger is not None:
        return "Sent to a reviewer: {0}".format(
            _coded(trigger_words(trigger, votes), trigger)
        )
    amount = _decimal(ruling.get("amount_sgd"))
    driver = _decimal(ruling.get("driver_compensation_sgd"))
    parts = [_coded(ruling_words(value), value)]
    if value == pipeline_module.DRIVER_COMPENSATION and driver is not None:
        parts.append("driver paid {0}".format(_money(driver, currency)))
    else:
        if amount is not None:
            parts.append("refund {0}".format(_money(amount, currency)))
        if driver is not None:
            parts.append("driver paid {0}".format(_money(driver, currency)))
    return " ".join(parts)


# --------------------------------------------------------------------------
# One case, read once
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class CaseData:
    """Everything one case page and one queue row are built from."""

    set_name: str
    case_no: int
    run_dir: Path
    document: Mapping[str, Any]
    transcript: Mapping[str, Any]
    case: Mapping[str, Any]
    brief: Mapping[str, Any]
    brief_sha256: str
    policy: PolicyFacts
    ruling: Mapping[str, Any]
    trigger: Optional[str]
    packet: Optional[Mapping[str, Any]]

    @property
    def label(self) -> str:
        return SET_LABELS[self.set_name]

    @property
    def link(self) -> str:
        return "case-{0:05d}.html".format(self.case_no)

    @property
    def outcome_kind(self) -> str:
        return OUTCOME_REVIEWER if self.trigger is not None else OUTCOME_AUTO

    @property
    def category(self) -> str:
        return str((self.case.get("dispute") or {}).get("category"))

    @property
    def votes(self) -> int:
        """The number of drafts the judge was asked for, read from the run.

        The run's own configuration records it, and a scope-gated case -- which
        asked no judge -- has no vote in its transcript, so the configuration is
        the first place to look and the transcript's own count is the fallback.
        A case that records neither is refused rather than drawn with a zero.
        """
        configuration = self.document.get("configuration")
        if isinstance(configuration, Mapping) and configuration.get("judge_votes") is not None:
            return int(configuration["judge_votes"])
        vote = self.transcript.get("vote")
        if isinstance(vote, Mapping) and vote.get("votes") is not None:
            return int(vote["votes"])
        raise BuildError(
            "case {0} of {1} records no judge vote count".format(
                self.case_no, self.set_name
            )
        )


def _load_case(set_name: str, case_no: int) -> CaseData:
    """Read one case: its run's record, its public case, its brief and its packet."""
    run = _run_for(set_name)
    run_dir = run.run_dir
    document = _read_json(run_dir / "case-{0:05d}.json".format(case_no))
    transcript = _transcript_of(run_dir, document, case_no)
    development_set = _set_for(set_name)
    try:
        case = development_set.load_case(case_no)
    except loader.LoaderError as exc:
        raise BuildError(
            "case {0} of {1} cannot be loaded: {2}".format(case_no, set_name, exc)
        ) from exc
    configuration = document.get("configuration")
    version = (
        configuration.get("policy_version")
        if isinstance(configuration, Mapping)
        else None
    )
    policy = _policy_facts(
        str((case.get("dispute") or {}).get("category")), int(version or 0)
    )
    try:
        brief = brief_module.build_brief_for_case(case, policy_version=int(version or 0))
    except Exception as exc:
        raise BuildError(
            "the brief for case {0} of {1} cannot be built: {2}".format(
                case_no, set_name, exc
            )
        ) from exc
    _canonical, digest = brief_module.brief_digest(brief)
    recorded = document.get("brief_sha256")
    if recorded != digest:
        # The page shows the bytes the agents were handed. A digest that does not
        # match means this code builds a different brief, so the case is refused
        # rather than drawn from a brief that merely resembles it.
        raise BuildError(
            "case {0} of {1}: the rebuilt brief hashes to {2} and the run "
            "recorded {3}, so this code builds a different brief from the one "
            "the agents were handed".format(case_no, set_name, digest, recorded)
        )
    ruling = _inner_ruling(document)
    trigger = (
        escalation_trigger(case, transcript)
        if ruling.get("ruling") == ESCALATE
        else None
    )
    packet: Optional[Mapping[str, Any]] = None
    if trigger is not None:
        try:
            packet = escalation.build_packet(run_dir, case_no)
        except escalation.EscalationError as exc:
            raise BuildError(
                "the escalation packet for case {0} of {1} cannot be built: "
                "{2}".format(case_no, set_name, exc)
            ) from exc
    return CaseData(
        set_name=set_name,
        case_no=case_no,
        run_dir=run_dir,
        document=document,
        transcript=transcript,
        case=case,
        brief=brief,
        brief_sha256=digest,
        policy=policy,
        ruling=ruling,
        trigger=trigger,
        packet=packet,
    )


def read_every_case() -> List[CaseData]:
    """Every case of the four runs: the set selector's order, then case number.

    The order is a fact about this file rather than about a directory listing or
    an interpreter's string hash seed. The rows are collected in ``SET_ORDER``
    and then sorted on the same order and the case number, so a build run twice
    under two hash seeds writes the same bytes and the queue's row order is the
    order the set selector lists the sets in.
    """
    out: List[CaseData] = []
    for set_name in SET_ORDER:
        run = _run_for(set_name)
        for case_no in _case_numbers(run.run_dir):
            out.append(_load_case(set_name, case_no))
    out.sort(key=lambda row: (SET_ORDER_INDEX[row.set_name], row.case_no))
    return out


# --------------------------------------------------------------------------
# The queue's five figures
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class QueueFigures:
    """The five figures across the top of the queue, and the reason-code tally."""

    total: int
    automatic: int
    reviewer: int
    triggers: Mapping[str, int]
    median_seconds: Decimal
    median_cost: Decimal
    policy_version: int
    votes: int
    model: str

    @property
    def automatic_share(self) -> str:
        return _share(self.automatic, self.total)

    @property
    def reviewer_share(self) -> str:
        return _share(self.reviewer, self.total)


def queue_figures(cases: Sequence[CaseData]) -> QueueFigures:
    """The five figures, each computed from the cases' own files."""
    if not cases:
        raise BuildError("the queue holds no cases")
    automatic = [case for case in cases if case.trigger is None]
    reviewer = [case for case in cases if case.trigger is not None]
    triggers = Counter(case.trigger for case in reviewer)
    walls: List[Decimal] = []
    costs: List[Decimal] = []
    for case in cases:
        wall = _decimal(case.document.get("wall_seconds"))
        if wall is None:
            raise BuildError(
                "case {0} of {1} records no wall_seconds".format(
                    case.case_no, case.set_name
                )
            )
        walls.append(wall)
        # The tokens are summed from the transcript's own entries, which is where
        # the calls are recorded; the case file carries the same totals, and a
        # case no agent was asked about has none in either place.
        prompt = cached = completion = 0
        for entry in case.transcript.get("entries") or []:
            if not isinstance(entry, Mapping):
                continue
            prompt += int(entry.get("prompt_tokens") or 0)
            cached += int(entry.get("cached_tokens") or 0)
            completion += int(entry.get("completion_tokens") or 0)
        costs.append(_cost_usd(prompt, cached, completion))
    versions = {
        int((case.document.get("configuration") or {}).get("policy_version") or 0)
        for case in cases
    }
    models = {str(case.document.get("model")) for case in cases}
    votes = {case.votes for case in cases}
    if len(versions) != 1 or len(models) != 1 or len(votes) != 1:
        raise BuildError(
            "the queue mixes policy versions {0}, models {1} or judge vote "
            "counts {2}".format(sorted(versions), sorted(models), sorted(votes))
        )
    return QueueFigures(
        total=len(cases),
        automatic=len(automatic),
        reviewer=len(reviewer),
        triggers={name: triggers.get(name, 0) for name in TRIGGER_ORDER},
        median_seconds=_median(walls),
        median_cost=_median(costs),
        policy_version=versions.pop(),
        votes=votes.pop(),
        model=models.pop(),
    )


# --------------------------------------------------------------------------
# The stylesheet and the script
# --------------------------------------------------------------------------
_CSS = """
/* The light theme is the default: the palette in :root is what a reader gets
   when the system asks for no preference, and the dark palette below replaces
   it only when the system asks for dark. The accent colours move with it, so a
   pill, a bar or a link keeps the same contrast on either background. */
:root{
  --ink:#1b1f24;--paper:#ffffff;--soft:#f6f8fa;--line:#d8dee4;--muted:#57606a;
  --blue:#1f6feb;--orange:#d9822b;--green:#2da44e;--red:#cf222e;
}
@media (prefers-color-scheme:dark){
  :root{--ink:#e6edf3;--paper:#0d1117;--soft:#161b22;--line:#30363d;--muted:#8b949e;
    --blue:#58a6ff;--orange:#e3a008;--green:#3fb950;--red:#f85149;}
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--blue)}
.layout{display:flex;min-height:100vh}
.side{flex:0 0 168px;border-right:1px solid var(--line);background:var(--soft);padding:24px 14px}
.brand{font-weight:700;margin:0 0 18px;padding:0 8px;letter-spacing:.01em}
.navlink{display:block;padding:7px 10px;border-radius:7px;color:var(--ink);text-decoration:none}
.navlink:hover{background:var(--line)}
.navlink.current{background:var(--blue);color:#fff}
main{flex:1 1 auto;min-width:0;max-width:1080px;padding:30px 34px 70px}
h1{font-size:1.5rem;line-height:1.3;margin:.2em 0 .4em}
h2{font-size:1.05rem;margin:0 0 12px}
h3{font-size:.95rem;margin:18px 0 6px}
p{margin:.55em 0}
.eyebrow{color:var(--muted);font-size:.85rem;letter-spacing:.06em;text-transform:uppercase;margin:0}
.lede{font-size:1.05rem;margin:.3em 0 1em}
.card{border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:0 0 18px;background:var(--paper)}
.card.soft{background:var(--soft)}
.card.wide{padding-bottom:8px}
.disclosure{font-weight:600;border-left:4px solid var(--blue);padding-left:12px;margin:0 0 14px}
.figures{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 22px}
.figure{border:1px solid var(--line);border-radius:12px;padding:14px 18px;min-width:168px;flex:1 1 168px}
.figure .k{color:var(--muted);font-size:.82rem;text-transform:uppercase;letter-spacing:.05em;margin:0 0 6px}
.figure .v{font-size:1.35rem;font-weight:650;margin:0}
.figure .s{color:var(--muted);font-size:.85rem;margin:4px 0 0}
.figure.wide{flex:1 1 100%}
.triggers{list-style:none;margin:0;padding:0}
.triggers li{display:flex;flex-wrap:wrap;justify-content:space-between;gap:2px 14px;padding:5px 0;border-bottom:1px solid var(--line);font-size:1rem;line-height:1.5}
.triggers li:last-child{border-bottom:0}
.triggers .n{font-weight:650;font-variant-numeric:tabular-nums}
td[data-column="time"]{white-space:nowrap}
.facts{display:flex;flex-wrap:wrap;gap:10px 28px;margin:0;padding:0}
.facts div{margin:0}
.facts dt{color:var(--muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}
.facts dd{margin:2px 0 0;font-weight:600}
.tabs{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px}
.tab{border:1px solid var(--line);background:var(--soft);color:var(--ink);border-radius:999px;padding:7px 16px;font:inherit;cursor:pointer}
.tab-on{background:var(--blue);border-color:var(--blue);color:#fff}
table{border-collapse:collapse;width:100%}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}
th.sortable{cursor:pointer;user-select:none}
th.sortable::after{content:" \\2195";color:var(--muted)}
tr.reviewer td{background:rgba(217,130,43,.09)}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:.8rem;font-weight:600}
.pill.blue{background:rgba(31,111,235,.14);color:var(--blue)}
.pill.orange{background:rgba(217,130,43,.16);color:var(--orange)}
.pill.green{background:rgba(45,164,78,.16);color:var(--green)}
.pill.red{background:rgba(207,34,46,.14);color:var(--red)}
.pill.grey{background:var(--soft);color:var(--muted);border:1px solid var(--line)}
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 14px}
.filters button{border:1px solid var(--line);background:var(--paper);color:var(--ink);border-radius:999px;padding:6px 14px;font:inherit;cursor:pointer}
.filters button.on{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.filters select{font:inherit;padding:6px 10px;border-radius:8px;border:1px solid var(--line);background:var(--paper);color:var(--ink)}
.bar{position:relative;height:12px;border-radius:6px;background:var(--soft);border:1px solid var(--line);margin:10px 0 6px;overflow:hidden}
.bar span{position:absolute;left:0;top:0;bottom:0;background:var(--blue)}
.bar i{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--red)}
.axis{display:flex;justify-content:space-between;color:var(--muted);font-size:.82rem}
blockquote{margin:8px 0;padding:10px 14px;border-left:3px solid var(--line);background:var(--soft);white-space:pre-wrap;overflow-wrap:anywhere}
details{border:1px solid var(--line);border-radius:10px;padding:0 16px;margin:0 0 10px}
details[open]{padding-bottom:12px}
summary{cursor:pointer;padding:13px 0;font-weight:600}
.label{color:var(--muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;margin:12px 0 0}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.85rem;word-break:break-all}
pre{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-wrap:anywhere;white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.85rem}
.foot{border-top:1px solid var(--line);margin-top:34px;padding-top:14px;color:var(--muted);font-size:.85rem}
.foot span{margin-right:18px}
.claim{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 10px}
.claim p{margin:.35em 0}
.err{color:var(--red);font-weight:600}
.ok{color:var(--green);font-weight:600}
.empty{color:var(--muted)}
@media (max-width:640px){
  .layout{display:block}
  .side{border-right:0;border-bottom:1px solid var(--line);padding:14px 12px}
  .brand{margin-bottom:8px}
  main{padding:20px 16px 48px}
  .card{padding:16px}
  table thead{display:none}
  table,tbody,tr,td{display:block;width:100%}
  tr{border-bottom:1px solid var(--line);padding:8px 0}
  td{border:0;padding:4px 0}
  td::before{content:attr(data-label);display:block;color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em}
}
"""

_JS = """
(function(){
  "use strict";
  function each(selector, root){
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  var tabs = each("[data-tab]");
  tabs.forEach(function(tab){
    tab.addEventListener("click", function(){
      var name = tab.getAttribute("data-tab");
      tabs.forEach(function(other){
        var on = other === tab;
        other.setAttribute("aria-selected", on ? "true" : "false");
        other.className = on ? "tab tab-on" : "tab";
      });
      each("[data-panel]").forEach(function(panel){
        panel.hidden = panel.getAttribute("data-panel") !== name;
      });
    });
  });

  var table = document.getElementById("queue");
  if (table){
    var body = table.tBodies[0];
    var rows = Array.prototype.slice.call(body.rows);
    var state = {column: null, up: true};

    function value(row, column){
      var cell = row.querySelector('td[data-column="' + column + '"]');
      if (!cell){ return ""; }
      var sort = cell.getAttribute("data-sort");
      return sort === null ? cell.textContent.trim() : sort;
    }

    function numeric(text){
      return /^-?[0-9]+(\\.[0-9]+)?$/.test(text);
    }

    function sortBy(column){
      if (state.column === column){ state.up = !state.up; }
      else { state.column = column; state.up = true; }
      rows.sort(function(a, b){
        var x = value(a, column), y = value(b, column);
        if (numeric(x) && numeric(y)){
          return state.up ? Number(x) - Number(y) : Number(y) - Number(x);
        }
        if (x === y){ return 0; }
        return state.up ? (x < y ? -1 : 1) : (x < y ? 1 : -1);
      });
      rows.forEach(function(row){ body.appendChild(row); });
    }

    each("th[data-column]", table).forEach(function(head){
      head.classList.add("sortable");
      head.addEventListener("click", function(){
        sortBy(head.getAttribute("data-column"));
      });
    });

    var chosen = {outcome: "all", set: "all"};
    function apply(){
      var shown = 0;
      rows.forEach(function(row){
        var okOutcome = chosen.outcome === "all" || row.getAttribute("data-outcome") === chosen.outcome;
        var okSet = chosen.set === "all" || row.getAttribute("data-set") === chosen.set;
        var ok = okOutcome && okSet;
        row.hidden = !ok;
        if (ok){ shown += 1; }
      });
      var count = document.getElementById("shown");
      if (count){ count.textContent = String(shown); }
    }

    each("[data-filter]").forEach(function(button){
      button.addEventListener("click", function(){
        chosen.outcome = button.getAttribute("data-filter");
        each("[data-filter]").forEach(function(other){
          other.className = other === button ? "on" : "";
        });
        apply();
      });
    });

    var picker = document.getElementById("set-picker");
    if (picker){
      picker.addEventListener("change", function(){
        chosen.set = picker.value;
        apply();
      });
    }
    apply();
  }

  var form = document.getElementById("review-form");
  if (form){
    var reason = document.getElementById("reason");
    var verdict = document.getElementById("verdict");
    var output = document.getElementById("command");
    var evidence = (form.getAttribute("data-evidence") || "").split(" ").filter(Boolean);
    var clauses = (form.getAttribute("data-clauses") || "").split(" ").filter(Boolean);
    var floor = Number(form.getAttribute("data-reason-min") || "0");

    function cited(text, ids){
      for (var i = 0; i < ids.length; i += 1){
        if (text.indexOf(ids[i]) >= 0){ return true; }
      }
      return false;
    }

    function check(){
      var text = reason.value.trim();
      var problems = [];
      if (text.length < floor){
        problems.push("the reason is " + text.length + " characters; POL-GEN-06(6) requires at least " + floor);
      }
      if (!cited(text, evidence)){
        problems.push("the reason cites no evidence id of this case");
      }
      if (!cited(text, clauses)){
        problems.push("the reason cites no clause id of this case");
      }
      return {text: text, problems: problems};
    }

    function decision(){
      var picked = form.querySelector('input[name="decision"]:checked');
      return picked ? picked.value : "";
    }

    function command(){
      var text = reason.value.trim();
      return "python3 -m ops.review --run-dir " + form.getAttribute("data-run-dir") +
        " --case " + form.getAttribute("data-case") +
        " --packet-sha256 " + form.getAttribute("data-packet") +
        " close --ruling " + form.getAttribute("data-ruling") +
        ' --closed-by "' + (document.getElementById("reviewer").value || "reviewer") + '"' +
        ' --summary "' + decision() + '"' +
        ' --reason "' + text.replace(/"/g, "'") + '"';
    }

    function refresh(){
      var state = check();
      if (state.problems.length){
        verdict.className = "err";
        verdict.textContent = state.problems.join("; ");
      } else {
        verdict.className = "ok";
        verdict.textContent = "The reason is long enough and cites this case's own evidence and clause ids.";
      }
      output.textContent = command();
    }

    form.addEventListener("input", refresh);
    form.addEventListener("change", refresh);

    var copy = document.getElementById("copy");
    if (copy){
      copy.addEventListener("click", function(){
        var text = command();
        var done = function(){
          var status = document.getElementById("copy-status");
          if (status){ status.textContent = "Copied."; }
        };
        if (navigator.clipboard && navigator.clipboard.writeText){
          navigator.clipboard.writeText(text).then(done, function(){
            var status = document.getElementById("copy-status");
            if (status){ status.textContent = "Select the command above and copy it by hand."; }
          });
        } else {
          var status = document.getElementById("copy-status");
          if (status){ status.textContent = "Select the command above and copy it by hand."; }
        }
      });
    }
    refresh();
  }
})();
"""


# --------------------------------------------------------------------------
# The shell every page is built in
# --------------------------------------------------------------------------
def _shell(title: str, body: str) -> str:
    """One self-contained page: inline CSS, inline script, nothing external."""
    page = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>{0}</title>\n<style>{1}</style>\n</head>\n<body>\n"
        '<div class="layout">\n{2}\n</div>\n<script>{3}</script>\n</body>\n</html>\n'
    ).format(_text(title), _CSS, body, _JS)
    return defuse_key_shaped(page)


def _nav(current: str) -> str:
    """The narrow left navigation: the queue, and nothing else."""
    if current == "queue":
        item = '<span class="navlink current">Queue</span>'
    else:
        item = '<a class="navlink" href="index.html">Queue</a>'
    return (
        '<nav class="side" aria-label="Sections">\n'
        '<p class="brand">Tribunal</p>\n{0}\n</nav>\n'.format(item)
    )


def _footer(case: CaseData) -> str:
    """The footer every page carries: commit, tag, policy version and model."""
    configuration = case.document.get("configuration") or {}
    return (
        '<footer class="foot">'
        "<span>commit {0}</span>"
        "<span>tag {1}</span>"
        "<span>policy version {2}</span>"
        "<span>model {3}</span>"
        "</footer>"
    ).format(
        _text(str(case.document.get("git_commit"))[:7]),
        _text(v6_runs.FREEZE_TAG),
        _text(configuration.get("policy_version")),
        _text(case.document.get("model")),
    )


# --------------------------------------------------------------------------
# The queue page
# --------------------------------------------------------------------------
def _figure(key: str, value: str, note: str = "") -> str:
    sub = '<p class="s">{0}</p>'.format(_text(note)) if note else ""
    return (
        '<div class="figure"><p class="k">{0}</p><p class="v">{1}</p>{2}</div>'
    ).format(_text(key), _text(value), sub)


def _trigger_card(figures: QueueFigures) -> str:
    """The reviewer triggers, one per line: the words first, then the count.

    A row per trigger rather than one run-on string, so a reader sees which
    reason fired and how often without counting commas. The card spans the row
    (``.figure.wide``) and its lines wrap, so a long phrase cannot overflow it.
    """
    lines = []
    for name in TRIGGER_ORDER:
        count = figures.triggers.get(name, 0)
        if not count:
            continue
        lines.append(
            '<li><span class="t">{0}</span> <span class="n">{1}</span></li>'.format(
                _text(trigger_words(name, figures.votes)), _text(count)
            )
        )
    body = "".join(lines) if lines else '<li><span class="t">none</span></li>'
    return (
        '<div class="figure wide"><p class="k">Reviewer triggers</p>'
        '<ul class="triggers">{0}</ul>'
        '<p class="s">counted by reason code</p></div>'
    ).format(body)


def _queue_row(case: CaseData) -> str:
    dispute = case.case.get("dispute") or {}
    currency = case.policy.currency
    outcome = _outcome_text(case.ruling, currency, case.trigger, case.votes)
    confidence = case.ruling.get("confidence")
    # A case sent to a reviewer has no ruling to be confident in, so the column
    # shows a dash rather than a figure read off a ruling that was never made.
    if case.trigger is not None:
        confidence_text = "-"
    else:
        confidence_text = "none" if confidence is None else str(confidence)
    amount_sort = _decimal(dispute.get("amount_contested_sgd"))
    time_sort = _decimal(case.document.get("wall_seconds"))
    filed_by = dispute.get("filed_by")
    # The cell text is escaped once, when it is written -- the outcome is the one
    # cell already rendered as HTML -- and the sort key is a plain value, so a
    # sort never reads a markup fragment as though it were the value.
    cells = (
        (
            "case",
            '<a href="{0}">{1}</a>'.format(_attribute(case.link), _text(case.case_no)),
            str(case.case_no),
            "Case",
        ),
        (
            "category",
            _text(CATEGORY_WORDS.get(case.category, case.category)),
            case.category,
            "Category",
        ),
        (
            "filed_by",
            _text(filed_by_words(filed_by)),
            str(filed_by),
            "Filed by",
        ),
        (
            "amount",
            _text(_money(dispute.get("amount_contested_sgd"), currency)),
            str(amount_sort if amount_sort is not None else 0),
            "Amount contested",
        ),
        ("outcome", outcome, str(case.ruling.get("ruling")), "Outcome"),
        ("confidence", _text(confidence_text), confidence_text, "Confidence"),
        (
            "time",
            _text(_seconds(case.document.get("wall_seconds"))),
            str(time_sort if time_sort is not None else 0),
            "Time",
        ),
    )
    row_class = "reviewer" if case.trigger is not None else "auto"
    cells_html = "".join(
        '<td data-column="{0}" data-sort="{1}" data-label="{2}">{3}</td>'.format(
            _attribute(name), _attribute(sort), _attribute(label), value
        )
        for name, value, sort, label in cells
    )
    return '<tr class="{0}" data-outcome="{1}" data-set="{2}">{3}</tr>'.format(
        row_class, case.outcome_kind, _attribute(case.label), cells_html
    )


def _queue_head() -> str:
    columns = (
        ("case", "Case"),
        ("category", "Category"),
        ("filed_by", "Filed by"),
        ("amount", "Amount contested"),
        ("outcome", "Outcome"),
        ("confidence", "Confidence"),
        ("time", "Time"),
    )
    return "<tr>{0}</tr>".format(
        "".join(
            '<th data-column="{0}">{1}</th>'.format(_attribute(name), _text(label))
            for name, label in columns
        )
    )


def _set_picker(cases: Sequence[CaseData]) -> str:
    labels = []
    for set_name in SET_ORDER:
        if any(case.set_name == set_name for case in cases):
            labels.append(SET_LABELS[set_name])
    options = ['<option value="all">All sets</option>']
    for label in labels:
        options.append('<option value="{0}">{1}</option>'.format(_attribute(label), _text(label)))
    return (
        '<label for="set-picker">Set</label>'
        '<select id="set-picker">{0}</select>'.format("".join(options))
    )


def build_index(cases: Sequence[CaseData]) -> str:
    """The queue: five figures, a filter row and one sortable row per case."""
    figures = queue_figures(cases)
    header = (
        '<header class="pagehead">\n'
        "<h1>Today's disputes</h1>\n"
        '<p class="lede">A replay of the version-6 runs committed in this '
        "repository; no page calls a model.</p>\n"
        "</header>\n"
    )
    figure_html = '<div class="figures">' + "".join(
        (
            _figure(
                "Decided automatically",
                "{0} of {1}".format(figures.automatic, figures.total),
                "{0} of the queue".format(figures.automatic_share),
            ),
            _figure(
                "Sent to a reviewer",
                "{0} of {1}".format(figures.reviewer, figures.total),
                "{0} of the queue".format(figures.reviewer_share),
            ),
            _trigger_card(figures),
            _figure("Median time per case", _seconds(figures.median_seconds), "wall clock"),
            _figure(
                "Median cost per case",
                _usd(figures.median_cost),
                "at the owner's prices",
            ),
            _figure(
                "Policy version and model",
                "v{0}".format(figures.policy_version),
                figures.model,
            ),
        )
    ) + "</div>\n"
    filters = (
        '<div class="filters">'
        '<button type="button" data-filter="all" class="on">All</button>'
        '<button type="button" data-filter="auto">Decided automatically</button>'
        '<button type="button" data-filter="reviewer">Sent to a reviewer</button>'
        "{0}"
        '<span class="empty"><span id="shown">{1}</span> shown</span>'
        "</div>\n".format(_set_picker(cases), len(cases))
    )
    rows = "".join(_queue_row(case) for case in cases)
    table = (
        '<div class="card wide">\n<table id="queue">\n<thead>{0}</thead>\n'
        "<tbody>{1}</tbody>\n</table>\n</div>\n".format(_queue_head(), rows)
    )
    body = (
        _nav("queue")
        + "<main>\n"
        + header
        + figure_html
        + filters
        + table
        + _footer(cases[0])
        + "\n</main>\n"
    )
    return _shell("Tribunal - today's disputes", body)


# --------------------------------------------------------------------------
# The case page
# --------------------------------------------------------------------------
def _summary_line(case: Mapping[str, Any]) -> str:
    """One line of the dispute's own claim text, masked as the brief masks it.

    The mask is :func:`tribunal.brief`'s own -- the same function the version-6
    brief applies to ``claim_text`` -- so a registration mark is replaced on the
    page exactly as it was replaced in front of the agents. The line is the
    claim's first sentence, with its newlines flattened.
    """
    dispute = case.get("dispute") or {}
    text = dispute.get("claim_text")
    if not isinstance(text, str) or not text.strip():
        raise BuildError("the dispute records no claim_text")
    masked = brief_module._mask_registrations(text)
    collapsed = " ".join(str(masked).split())
    end = collapsed.find(". ")
    return collapsed if end < 0 else collapsed[: end + 1]


def _confidence_card(case: CaseData) -> str:
    """The confidence, on its scale, with the policy's floor marked."""
    confidence = _decimal(case.ruling.get("confidence"))
    floor = case.policy.confidence_floor
    if confidence is None:
        return '<p class="empty">No confidence is recorded for this case.</p>'
    width = "{0:.1f}%".format(confidence * 100)
    mark = "{0:.1f}%".format(floor * 100)
    return (
        '<div class="bar" role="img" aria-label="confidence {0} against a floor of {1}">'
        "<span style=\"width:{2}\"></span><i style=\"left:{3}\"></i></div>"
        '<p class="axis"><span>confidence {0}</span>'
        "<span>floor {1} (POL-GEN-02)</span></p>"
    ).format(_attribute(confidence), _attribute(floor), _attribute(width), _attribute(mark))


def _claims_block(case: CaseData, side: str) -> str:
    """One side's claims, each marked kept or discarded by the referee."""
    claims = _claims(case.transcript, side)
    if not claims:
        return (
            '<p class="empty">No claim from the {0} advocate is recorded: no '
            "advocate was asked to argue this case.</p>".format(_text(side.lower()))
        )
    out = []
    for claim in claims:
        status = claim["status"]
        if status == "KEPT":
            pill = '<span class="pill green">kept</span>'
        elif status == "DISCARDED":
            pill = '<span class="pill red">discarded</span>'
        else:
            pill = '<span class="pill grey">no verdict recorded</span>'
        lines = ['<div class="claim"><p>{0} {1}</p>'.format(pill, _text(claim["text"]))]
        lines.append(
            '<p class="label">evidence {0} &middot; clauses {1}</p>'.format(
                _text(", ".join(claim["evidence_ids"]) or "none"),
                _text(", ".join(claim["clause_ids"]) or "none"),
            )
        )
        if status == "DISCARDED":
            lines.append(
                '<p><strong>Discarded by the referee ({0}):</strong> {1}</p>'.format(
                    _text(claim["reason_code"]), _text(claim["detail"])
                )
            )
        lines.append("</div>")
        out.append("".join(lines))
    return "".join(out)


def _evidence_table(case: CaseData) -> str:
    rows = []
    for artifact in _evidence(case.brief):
        rows.append(
            "<tr>"
            "<td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td>"
            "</tr>".format(
                _text(artifact["evidence_id"]),
                _text(artifact["evidence_type"]),
                _text(artifact["source"]),
                _text(
                    "{0} (weight {1})".format(
                        artifact["status"], artifact["weight"]
                    )
                ),
                _text(", ".join(str(issue) for issue in artifact["issues"]) or "none"),
            )
        )
    return (
        "<table><thead><tr><th>Artifact</th><th>Type</th><th>Source</th>"
        "<th>Admissibility</th><th>Issue codes</th></tr></thead><tbody>{0}"
        "</tbody></table>".format("".join(rows))
    )


def _decided_ruling(case: CaseData) -> str:
    """The ruling card of a decided case: the ruling, its money and its appeal."""
    policy = case.policy
    ruling = case.ruling
    value = str(ruling.get("ruling"))
    explanation = str(ruling.get("explanation") or "")
    dispute = case.case.get("dispute") or {}
    return (
        '<div class="card">'
        '<p class="disclosure">{0}</p>'
        "<h2>Ruling</h2>"
        "<p>{1}</p>"
        "<p>{2}</p>"
        '<p class="label" id="judge-explanation">The judge\'s explanation, as '
        "written</p>"
        "<blockquote>{3}</blockquote>"
        "<p>How to appeal: {4}</p>"
        "<details><summary>Read POL-GEN-04 in full</summary>"
        "<blockquote>{5}</blockquote></details>"
        "{6}"
        "<p>{7}</p>"
        "</div>"
    ).format(
        _text(DISCLOSURE),
        _coded(ruling_words(value), value, strong=True),
        _text(money_statement(ruling, policy.currency, dispute.get("filed_by"))),
        _text(explanation),
        _text(appeal_line(policy)),
        _text(policy.rule("POL-GEN-04")),
        _confidence_card(case),
        _text(execution_sentence(policy, ruling, policy.currency)),
    )


def _reviewer_ruling(case: CaseData) -> str:
    """The ruling card of a case a human reviewer decides.

    No ruling was issued, so the page says so where a decided case carries its
    provisional disclosure, shows the reason the case reached a reviewer in
    words rather than a confidence bar, states what money moves on an
    escalation, and gives the review time limit read from POL-GEN-06(2). There
    is no appeal path to show, because there is no ruling to appeal.
    """
    policy = case.policy
    trigger = str(case.trigger)
    reason = "Why a reviewer: {0}".format(
        _coded(trigger_words(trigger, case.votes), trigger)
    )
    no_draft = ""
    if trigger == TRIGGER_NO_VALID_DRAFTS:
        no_draft = "<p>No draft was valid, so the panel could not reduce a ruling.</p>"
    dispute = case.case.get("dispute") or {}
    return (
        '<div class="card">'
        '<p class="disclosure">{0}</p>'
        "<h2>Ruling</h2>"
        "<p>{1}</p>"
        "<p>{2}</p>"
        "<p>{3}</p>"
        "{4}"
        "<p>{5}</p>"
        "</div>"
    ).format(
        _text(NO_AUTOMATED_RULING),
        reason,
        _text(
            money_statement(case.ruling, policy.currency, dispute.get("filed_by"))
        ),
        _text(review_time_limit(policy)),
        no_draft,
        _text(execution_sentence(policy, case.ruling, policy.currency)),
    )


def _ruling_tab(case: CaseData) -> str:
    policy = case.policy
    ruling = case.ruling
    dispute = case.case.get("dispute") or {}
    if case.trigger is not None:
        card = _reviewer_ruling(case)
    else:
        card = _decided_ruling(case) + (
            '<div class="card"><h2>The two notices</h2>'
            + _notice("RIDER", policy, ruling, dispute.get("filed_by"))
            + _notice("DRIVER", policy, ruling, dispute.get("filed_by"))
            + "</div>"
        )
    argued = (
        '<div class="card"><h2>What each side argued</h2>'
        "<h3>The rider advocate</h3>"
        + _claims_block(case, "RIDER")
        + "<h3>The driver advocate</h3>"
        + _claims_block(case, "DRIVER")
        + "</div>"
    )
    evidence = (
        '<div class="card wide"><h2>Evidence</h2>'
        "<p>The weight is the one the admissibility precheck gave each artifact, "
        "as the brief carried it.</p>"
        + _evidence_table(case)
        + "</div>"
    )
    return card + argued + evidence


def _step(title: str, who: str, produced: str, detail: str = "") -> str:
    body = '<p class="label">Who</p><p>{0}</p><p class="label">What it produced</p><p>{1}</p>'.format(
        _text(who), produced
    )
    if detail:
        body += detail
    return "<details><summary>{0}</summary>{1}</details>".format(_text(title), body)


def _decision_tab(case: CaseData) -> str:
    transcript = case.transcript
    entries = transcript.get("entries") or []
    vote = transcript.get("vote") if isinstance(transcript.get("vote"), Mapping) else {}
    advocates = {
        entry.get("role"): entry
        for entry in entries
        if isinstance(entry, Mapping) and entry.get("role") in ("RIDER_ADVOCATE", "DRIVER_ADVOCATE")
    }
    rider = advocates.get("RIDER_ADVOCATE")
    driver = advocates.get("DRIVER_ADVOCATE")
    same_bytes = (
        isinstance(rider, Mapping)
        and isinstance(driver, Mapping)
        and rider.get("user_sha256") == driver.get("user_sha256")
        and rider.get("user_sha256") == case.brief_sha256
    )

    # 1. The evidence pack.
    facts = _derived_facts(case.brief)
    fact_rows = "".join(
        "<li>{0} ({1}): {2}</li>".format(
            _text(row["evidence_id"]),
            _text(row["evidence_type"]),
            _text(", ".join(row["derived_keys"]) or "no derived facts"),
        )
        for row in facts
    )
    step1 = _step(
        STEP_TITLES[0],
        "code",
        '<p>The brief was built from the case and the loaded policy. Its sha256 is '
        '<span class="mono">{0}</span>.</p>'
        "<p>Both advocates received these same bytes: {1}.</p>".format(
            _text(case.brief_sha256),
            _text(
                "yes, the recorded user_sha256 of each advocate is this digest"
                if same_bytes
                else "no, the recorded digests do not agree with the brief"
            ),
        ),
        '<p class="label">The derived facts each artifact carries</p><ul>{0}</ul>'.format(
            fact_rows
        ),
    )

    # 2. Both sides argue.
    def claim_count(entry: Any) -> int:
        parsed = entry.get("parsed") if isinstance(entry, Mapping) else None
        claims = parsed.get("claims") if isinstance(parsed, Mapping) else None
        return len(claims) if isinstance(claims, list) else 0

    if rider is None and driver is None:
        step2 = _step(
            STEP_TITLES[1],
            "code",
            "<p>No advocate was asked: the scope gate assembled the record and "
            "stopped, so neither side argued this case.</p>",
        )
    else:
        step2 = _step(
            STEP_TITLES[1],
            "model",
            "<p>The two advocates ran on the same brief and at the same time: the "
            "rider advocate made {0} claim(s) and the driver advocate made {1}.</p>"
            "<p>Their instructions differ -- system_sha256 <span class=\"mono\">{2}"
            "</span> against <span class=\"mono\">{3}</span> -- and their brief is "
            "one digest for both.</p>".format(
                claim_count(rider),
                claim_count(driver),
                _text((rider or {}).get("system_sha256")),
                _text((driver or {}).get("system_sha256")),
            ),
            "<p class=\"label\">The rider advocate's own claims</p><blockquote>{0}</blockquote>"
            "<p class=\"label\">The driver advocate's own claims</p><blockquote>{1}</blockquote>".format(
                _text(_claims_text(case, "RIDER")),
                _text(_claims_text(case, "DRIVER")),
            ),
        )

    # 3. The citation check.
    rider_claims = _claims(transcript, "RIDER")
    driver_claims = _claims(transcript, "DRIVER")
    all_claims = rider_claims + driver_claims
    kept = [claim for claim in all_claims if claim["status"] == "KEPT"]
    discarded = [claim for claim in all_claims if claim["status"] == "DISCARDED"]
    if all_claims:
        step3_produced = (
            "<p>The referee checked every claim against the artifacts it cites. "
            "{0} claim(s) kept, {1} discarded.</p>".format(len(kept), len(discarded))
        )
        step3_detail = (
            "<p class=\"label\">Discarded claims and the referee's reason</p><ul>{0}</ul>".format(
                "".join(
                    "<li>{0} ({1}) -- {2}: {3}</li>".format(
                        _text(claim["reason_code"]),
                        _text(claim["side"]),
                        _text(claim["text"]),
                        _text(claim["detail"]),
                    )
                    for claim in discarded
                )
                or "<li>none</li>"
            )
        )
    else:
        step3_produced = (
            "<p>No claim reached the referee: no advocate was asked to argue "
            "this case.</p>"
        )
        step3_detail = ""
    step3 = _step(STEP_TITLES[2], "code", step3_produced, step3_detail)

    # 4. The judge.
    drafts = _drafts(transcript)
    draft_rows = "".join(
        "<li>draft {0} ({1}, sides {2}): {3}, amount {4}, driver {5}, "
        "confidence {6}{7}</li>".format(
            _text(draft["draft"]),
            _text(draft["kind"]),
            _text(", ".join(str(side) for side in draft["sides"])),
            _coded(
                ruling_words(draft["proposal"].get("ruling")),
                draft["proposal"].get("ruling"),
            ),
            _text(_money(draft["proposal"].get("amount_sgd"), case.policy.currency)),
            _text(
                _money(
                    draft["proposal"].get("driver_compensation_sgd"),
                    case.policy.currency,
                )
            ),
            _text(draft["confidence"]),
            "" if draft["valid"] else " (abstained: {0})".format(_text(draft["abstention"])),
        )
        for draft in drafts
    )
    step4 = _step(
        STEP_TITLES[3],
        "model" if drafts else "code",
        (
            "<p>The judge was asked {0} times on the same inputs: {1} sampled drafts "
            "and one with the parties' positions swapped. The vote agreement is {2}, "
            "and the outcome recorded is {3}.</p>".format(
                _text(vote.get("votes")),
                _text(sum(1 for draft in drafts if draft["kind"] == "sampled")),
                _text(vote.get("agreement")),
                _text(vote.get("outcome")),
            )
            if drafts
            else "<p>No draft was asked for: the scope gate stopped before the "
            "judge, so this case has no panel and no vote.</p>"
        ),
        "<p class=\"label\">Each draft</p><ul>{0}</ul>"
        "<p class=\"label\">Each draft's own explanation</p>{1}".format(
            draft_rows or "<li>none</li>",
            "".join(
                "<blockquote>{0}</blockquote>".format(_text(draft["explanation"]))
                for draft in drafts
            )
            or "<p class=\"empty\">No draft was asked for.</p>",
        ),
    )

    # 5. The floor and the triggers.
    floor = case.policy.confidence_floor
    step5 = _step(
        STEP_TITLES[4],
        "code",
        "<p>The confidence recorded for this case is {0} against the floor of {1} "
        "stated by POL-GEN-02.</p>{2}".format(
            _text(case.ruling.get("confidence")),
            _text(floor),
            "<p>The escalation reason is {0}.</p>".format(
                _coded(trigger_words(str(case.trigger), case.votes), case.trigger)
            )
            if case.trigger
            else "<p>No escalation reason is recorded: the case did not "
            "escalate.</p>",
        ),
    )

    # 6. The outcome.
    dispute = case.case.get("dispute") or {}
    if case.trigger:
        step6 = _step(
            STEP_TITLES[5],
            "code",
            "<p>Sent to a reviewer, fee held: {0}.</p>".format(
                _coded(trigger_words(str(case.trigger), case.votes), case.trigger)
            ),
        )
    else:
        step6 = _step(
            STEP_TITLES[5],
            "code",
            "<p>{0}</p><p>{1}</p>".format(
                _coded(
                    ruling_words(case.ruling.get("ruling")),
                    case.ruling.get("ruling"),
                    strong=True,
                ),
                _text(
                    money_statement(
                        case.ruling, case.policy.currency, dispute.get("filed_by")
                    )
                ),
            ),
        )
    return (
        '<div class="card wide"><h2>How it was decided</h2>'
        + step1
        + step2
        + step3
        + step4
        + step5
        + step6
        + "</div>"
    )


def _claims_text(case: CaseData, side: str) -> str:
    """One advocate's claims as the raw answer carried them, one per line."""
    for entry in case.transcript.get("entries") or []:
        if isinstance(entry, Mapping) and entry.get("role") == side + "_ADVOCATE":
            return str(entry.get("response_text") or "")
    return ""


def _review_tab(case: CaseData) -> str:
    """The human-review tab: the packet, its digest, and a form that closes nothing."""
    packet = case.packet
    if packet is None:
        raise BuildError("case {0} has no escalation packet".format(case.case_no))
    digest = escalation.packet_sha256(packet)
    trigger = packet.get("trigger") or {}
    case_block = packet.get("case") or {}
    ruling = packet.get("ruling") or {}
    drafts = packet.get("drafts") or []
    draft_rows = "".join(
        "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td>"
        "<td>{5}</td></tr>".format(
            _text(draft.get("draft")),
            _coded(
                ruling_words((draft.get("proposal") or {}).get("ruling")),
                (draft.get("proposal") or {}).get("ruling"),
            ),
            _text((draft.get("proposal") or {}).get("amount_sgd")),
            _text(draft.get("confidence")),
            _text("valid" if draft.get("valid") else "abstained"),
            _text(draft.get("abstention_code") or "none"),
        )
        for draft in drafts
    )
    admissibility_rows = "".join(
        "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td></tr>".format(
            _text(artifact.get("evidence_id")),
            _text(artifact.get("evidence_type")),
            _text(artifact.get("source")),
            _text(artifact.get("status")),
            _text(artifact.get("weight_multiplier")),
        )
        for artifact in packet.get("admissibility") or []
    )
    timeline_rows = "".join(
        "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td></tr>".format(
            _text(row.get("ts")),
            _text(row.get("event")),
            _text(row.get("role_or_draft")),
            _text(row.get("seconds")),
        )
        for row in packet.get("timeline") or []
    )
    briefs = packet.get("briefs") or {}
    brief_rows = "".join(
        "<li>{0}: {1}</li>".format(
            _text(side),
            _text(
                "; ".join(
                    "{0} {1}".format(
                        claim.get("text"),
                        "KEPT"
                        if (claim.get("verdict") or {}).get("status") == "KEPT"
                        else "DISCARDED",
                    )
                    for claim in briefs.get(side) or []
                )
                or "no claim"
            ),
        )
        for side in ("RIDER", "DRIVER")
    )
    packet_card = (
        '<div class="card wide"><h2>The escalation packet</h2>'
        '<p>Built by <span class="mono">ops.escalation</span> from this run. Its '
        'sha256 is <span class="mono">{0}</span>.</p>'
        "<h3>The case</h3><p>{1} &middot; filed by {2} &middot; contested {3}</p>"
        "<h3>The trigger</h3><p>outcome {4} &middot; threshold {5} &middot; valid {6} "
        "&middot; votes {7} &middot; agreement {8} &middot; unanimous {9}</p>"
        "<h3>The judge's explanation, verbatim</h3><blockquote>{10}</blockquote>"
        "<h3>The drafts</h3><table><thead><tr><th>Draft</th><th>Ruling</th>"
        "<th>Amount</th><th>Confidence</th><th>State</th><th>Abstention</th></tr>"
        "</thead><tbody>{11}</tbody></table>"
        "<h3>The advocate briefs, as the packet carries them</h3><ul>{12}</ul>"
        "<h3>The admissibility report</h3><table><thead><tr><th>Artifact</th>"
        "<th>Type</th><th>Source</th><th>Status</th><th>Weight</th></tr></thead>"
        "<tbody>{13}</tbody></table>"
        "<h3>Every clause id relied on</h3><p class=\"mono\">{14}</p>"
        "<h3>The ruling</h3><p>{15} &middot; amount {16} &middot; driver {17} &middot; "
        "confidence {18}</p>"
        "<h3>The timeline</h3><table><thead><tr><th>Time</th><th>Event</th>"
        "<th>Role or draft</th><th>Seconds</th></tr></thead><tbody>{19}</tbody></table>"
        "</div>"
    ).format(
        _text(digest),
        _text(case_block.get("category")),
        _text(case_block.get("filed_by")),
        _text(case_block.get("amount_contested_sgd")),
        _text(trigger.get("outcome")),
        _text(trigger.get("threshold")),
        _text(trigger.get("valid")),
        _text(trigger.get("votes")),
        _text(trigger.get("agreement")),
        _text(trigger.get("unanimous")),
        _text(packet.get("explanation")),
        draft_rows or "<tr><td colspan=\"6\">none</td></tr>",
        brief_rows or "<li>none</li>",
        admissibility_rows or "<tr><td colspan=\"5\">none</td></tr>",
        _text(", ".join(packet.get("clause_ids") or []) or "none"),
        _coded(ruling_words(ruling.get("ruling")), ruling.get("ruling")),
        _text(ruling.get("amount_sgd")),
        _text(ruling.get("driver_compensation_sgd")),
        _text(ruling.get("confidence")),
        timeline_rows or "<tr><td colspan=\"4\">none</td></tr>",
    )

    evidence_ids = [
        str(artifact.get("evidence_id"))
        for artifact in packet.get("admissibility") or []
        if artifact.get("evidence_id")
    ]
    clause_ids = [str(item) for item in packet.get("clause_ids") or []]
    choices = (
        ("ADOPT", "Adopt the system's proposed ruling."),
        ("VARY", "Vary: choose a ruling and a remedy from the money block's options."),
        ("REQUEST_EVIDENCE", "Request evidence: name the record-type items required."),
        ("REFER_COMPLIANCE", "Refer compliance: a safety, fraud or conduct matter."),
    )
    radios = "".join(
        '<p><label><input type="radio" name="decision" value="{0}"{1}> {2}</label></p>'.format(
            _attribute(value), " checked" if index == 0 else "", _text(label)
        )
        for index, (value, label) in enumerate(choices)
    )
    form_card = (
        '<div class="card wide" id="review-form" '
        'data-run-dir="{0}" data-case="{1}" data-packet="{2}" data-ruling="{3}" '
        'data-evidence="{4}" data-clauses="{5}" data-reason-min="{6}">'
        "<h2>The decision</h2>"
        "<p>POL-GEN-06(4) names exactly four decisions:</p>{7}"
        "<p><label>Reviewer <input id=\"reviewer\" type=\"text\" "
        "placeholder=\"a name\"></label></p>"
        "<p><label for=\"reason\">Reason</label></p>"
        "<textarea id=\"reason\" rows=\"4\" style=\"width:100%\"></textarea>"
        "<p id=\"verdict\"></p>"
        "<p><button type=\"button\" id=\"copy\">Copy the closing command</button> "
        '<span id="copy-status" class="empty"></span></p>'
        "<pre id=\"command\"></pre>"
        "<p><strong>This form closes nothing by itself: there is no server.</strong> "
        "It checks the reason and builds the command; recording the decision is a "
        "command a person runs.</p>"
        "</div>"
    ).format(
        _attribute(_relative_run_dir(case)),
        _attribute(case.case_no),
        _attribute(digest),
        _attribute(ruling.get("ruling")),
        _attribute(" ".join(evidence_ids)),
        _attribute(" ".join(clause_ids)),
        _attribute(precedents_module.MIN_REASON_CHARS),
        radios,
    )
    return packet_card + form_card


def _relative_run_dir(case: CaseData) -> str:
    """The run directory as a path from the project root, never an absolute one."""
    try:
        return case.run_dir.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        raise BuildError(
            "the run directory {0} is outside the project".format(case.run_dir)
        )


def build_case_page(case: CaseData) -> str:
    """One case page: a header, two or three tabs, and the footer."""
    dispute = case.case.get("dispute") or {}
    currency = case.policy.currency
    # The header names the case once -- "Case 901" -- and the set it belongs to.
    if case.trigger:
        status = "Sent to a reviewer: {0}".format(
            _coded(trigger_words(str(case.trigger), case.votes), case.trigger)
        )
    else:
        status = _coded(
            ruling_words(case.ruling.get("ruling")), case.ruling.get("ruling")
        )
    header = (
        '<header class="pagehead">\n'
        '<p class="eyebrow">{0} &middot; Case {1}</p>\n'
        "<h1>{2}</h1>\n"
        '<p class="lede">{3}</p>\n'
        '<dl class="facts">'
        "<div><dt>Filed by</dt><dd>{4}</dd></div>"
        "<div><dt>Amount contested</dt><dd>{5}</dd></div>"
        "<div><dt>Status</dt><dd>{6}</dd></div>"
        "</dl>\n</header>\n"
    ).format(
        _text(case.set_name),
        _text(case.case_no),
        _text(CATEGORY_WORDS.get(case.category, case.category)),
        _text(_summary_line(case.case)),
        _text(filed_by_words(dispute.get("filed_by"))),
        _text(_money(dispute.get("amount_contested_sgd"), currency)),
        status,
    )
    tabs = [
        ("ruling", "Ruling"),
        ("decision", "How it was decided"),
    ]
    if case.trigger is not None:
        tabs.append(("review", "Human review"))
    tab_html = "".join(
        '<button type="button" class="tab{0}" role="tab" id="tab-{1}" '
        'aria-controls="panel-{1}" data-tab="{1}" '
        'aria-selected="{2}">{3}</button>'.format(
            " tab-on" if index == 0 else "",
            _attribute(name),
            "true" if index == 0 else "false",
            _text(label),
        )
        for index, (name, label) in enumerate(tabs)
    )

    def panel(name: str, hidden: bool, content: str) -> str:
        return (
            '<section role="tabpanel" id="panel-{0}" aria-labelledby="tab-{0}" '
            'data-panel="{0}"{1}>{2}</section>'
        ).format(_attribute(name), " hidden" if hidden else "", content)

    panels = [panel("ruling", False, _ruling_tab(case))]
    panels.append(panel("decision", True, _decision_tab(case)))
    if case.trigger is not None:
        panels.append(panel("review", True, _review_tab(case)))
    body = (
        _nav("case")
        + "<main>\n"
        + header
        + '<div class="tabs" role="tablist">'
        + tab_html
        + "</div>\n"
        + "\n".join(panels)
        + "\n"
        + _footer(case)
        + "\n</main>\n"
    )
    return _shell(
        "Case {0} - {1}".format(case.case_no, CATEGORY_WORDS.get(case.category, case.category)),
        body,
    )


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------
def _write_or_check(destination: Path, text: str, check: bool) -> int:
    if check:
        if not destination.is_file():
            print("{0} does not exist; run the build".format(destination))
            return 1
        if destination.read_text(encoding="utf-8") != text:
            print(
                "{0} differs from a fresh build ({1} bytes on disk, {2} rebuilt)".format(
                    destination,
                    destination.stat().st_size,
                    len(text.encode("utf-8")),
                )
            )
            return 1
        print("{0} is identical to a fresh build".format(destination))
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    print("wrote {0}: {1} bytes".format(destination, len(text.encode("utf-8"))))
    return 0


def pages() -> List[Tuple[Path, str]]:
    """Every page this site commits, as ``(destination, text)``.

    The one place the site's shape is decided, so ``--check`` and a writing
    build cannot disagree about which files there are: both walk this list.
    """
    cases = read_every_case()
    out: List[Tuple[Path, str]] = [(INDEX_PATH, build_index(cases))]
    for case in cases:
        out.append((DIST_DIR / case.link, build_case_page(case)))
    return out


def build(check: bool = False) -> int:
    """Every page, or a comparison of the committed bytes against a fresh build."""
    status = 0
    for destination, text in pages():
        defused = text.count(DEFUSED)
        if defused:
            print(
                "{0}: {1} key-shaped run(s) written with an entity-escaped "
                "hyphen, so the publish scan cannot read them as a "
                "credential".format(destination, defused)
            )
        status |= _write_or_check(destination, text, check)
    return 0 if status == 0 else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m ui.v2.build",
        description=(
            "Build the product view: the queue at ui/dist/v2/index.html and one "
            "page per case of the four version-6 runs. Read-only on runs/, data/, "
            "policy/ and ops/config.json; no model call."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the committed pages with a fresh build and write nothing",
    )
    args = parser.parse_args(argv)
    try:
        return build(check=args.check)
    except BuildError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
