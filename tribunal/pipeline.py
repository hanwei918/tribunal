"""One full arbitration run.

``run_case`` performs the fixed sequence:

1. build the brief once with ``brief.build_brief(case_no)``;
2. render the advocate system prompt twice from the single template, substituting
   the rider and driver stance blocks at the ``{{STANCE}}`` placeholder;
3. call the rider advocate, then the driver advocate, each with the advocate
   system prompt and the serialised brief as the user message;
4. call the judge with the judge system prompt, and as its user message an object
   carrying the same brief plus both claim arrays;
5. return the ruling and the transcript.

**The advocates run sequentially, not concurrently.** A deterministic transcript
order matters more right now than the wall-clock saving, and running them in
parallel is a later optimisation to be made deliberately — it would change the
order the record is written in, and the record is a deliverable.

Two structural properties are *enforced* here, not described:

* **One brief, byte-identical.** The brief is canonicalised exactly once, and the
  same string object is handed to both advocates; the judge's user message
  embeds those same bytes. ``run_case`` asserts all three agree and exposes the
  brief's sha256 on the result, so a reader can confirm it.
* **The two advocate prompts differ only inside the stance block.**
  ``check_stance_only_difference`` renders both and returns the differing line
  ranges; ``run_case`` raises if any difference falls outside the region the
  substituted stance block occupies. That is the project's central claim: both
  sides read the same evidence and differ only in stance.

A model that answers with the wrong shape is retried once and then reported, and
a ruling that breaks its own output contract is recorded and never repaired. See
the module body for both. The run **stops at the first failed agent**: the judge
cannot be called without both claim arrays, so there is nothing to gain by
calling the second advocate once the first has failed.

The judge's vote
----------------
The judge is called ``judge_votes`` times on the same inputs and the majority
decides, because one sample of a sampled model is a sample. Three corpus cases
(105, 107 and 211) each flipped between runs whose prompts differed in ways
unrelated to those cases, which is what a single call cannot tell you about
itself. The drafts are reduced over the four graded fields together -- ruling,
both amounts, and the set of referral clause references -- because a panel that
agreed on the label while disagreeing on the money has not agreed on anything.

At ``judge_votes == 1`` none of this applies: the judge is called once with the
message it has always been handed and no vote is recorded, so a single-draft run
is byte for byte what it was before the vote existed. See :func:`_run_judge_vote`.

The advocate output contract
----------------------------
Every agent is called with ``response_format: {"type": "json_object"}``. That is
what buys bare JSON with no markdown fence and no surrounding prose, measured
across all three models, and it constrains the response to a top-level **object**.
The judge already returns an object, so for the judge the constraint and the
prompt agree.

The advocates did not. Their prompt asked for "a JSON array of claim objects"
while the request forced an object, so the two requirements could not both be
met and the API-level constraint won: every advocate answer was rejected as
unusable, twice, and the case failed. A paid benchmark run was lost to it before
anyone read what the models had actually returned — ``hy4-preview`` on case 207
answered with ``{"claims": [ ... ]}``, eleven claims with no citation missing,
and was discarded for the wrapper.

The prompt was changed to ask for the object the request can produce, and the
validator now accepts **both** an object carrying a ``claims`` array and a bare
array, normalising either to a list of claims. A model that returns the array
directly has answered the question, and rejecting the wrapper would be measuring
the wrapper. Which shape arrived is recorded per call, so the choice each model
makes is a measurement rather than something a reader has to infer.

``AGENT_RESPONSE_FORMAT`` and ``AGENT_PROMPT_FILES`` exist so that consistency is
checkable: ``tests/test_pipeline.py`` parses each prompt's own worked example and
fails if the shape it asks for is not one the format it is sent can produce. That
is the check whose absence let this reach a paid run.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from . import brief, events, llm, loader, money, referee, transcript as transcript_module
from .model import resolve_model

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "v1"

ADVOCATE_TEMPLATE = "advocate.system.md"
STANCE_FILES = {
    transcript_module.ROLE_RIDER_ADVOCATE: "stance.rider.md",
    transcript_module.ROLE_DRIVER_ADVOCATE: "stance.driver.md",
}
JUDGE_PROMPT_FILE = "judge.system.md"
# The draft verifier's prompt. It is a file of its own rather than a section of
# the judge's, because the verifier is a different question asked of a different
# thing: the judge decides the case, the verifier only says whether the brief
# supports the facts a draft states. Reading it is deferred until the verifier
# is switched on, so a run with the switch off never opens it.
VERIFIER_PROMPT_FILE = "verifier.system.md"
STANCE_PLACEHOLDER = "{{STANCE}}"

# Every agent is sent `json_object`. It is what guarantees bare JSON with no
# markdown fence and no surrounding prose, measured across all three models on
# 2026-09-21, and it constrains the top level to a JSON OBJECT. The judge already
# returns an object, so for the judge this and its prompt agree. The advocates
# had to be brought into line rather than the format given up.
JSON_OBJECT_FORMAT: Dict[str, str] = {"type": "json_object"}

# The top-level shapes a response body can arrive in, named so the record can
# count them instead of leaving each model's choice invisible.
SHAPE_OBJECT = "object"
SHAPE_ARRAY = "array"

# 2400 s, derived rather than chosen. A case is three agent calls, and each of
# them can be retried once when its answer is unusable, so ``LLMClient``'s own
# per-call deadline bounds one call but not the case: three calls at the
# per-call deadline is 3600 s, and before this limit existed the measured worst
# case was 241 minutes. That is what actually happened on 2026-09-22 -- a run
# wrote its last case at 07:25 and was still alive at 09:13 with nothing in
# flight a reader could see.
#
# The floor is what has been measured, not a round number. The slowest completed
# case in the corpus is 978.8 s (case 109 on ``hy4-preview``), so a limit at or
# below that would fail the slowest thing actually seen -- the opposite defect.
# Three calls each running into the per-attempt timeout is 3 x 606 s = 1818 s,
# measured from the 605.8-second TIMEOUT failure recorded that day. 2400 s
# covers both with margin and bounds a case at 40 minutes instead of 241. See
# docs/notes/2026-09-22-bounded-call-and-case-deadlines.md.
DEFAULT_CASE_DEADLINE_SECONDS = 2400.0

# The key the advocate's claim array travels under.
ADVOCATE_CLAIMS_KEY = "claims"

# What each response_format permits at the top level. A prompt that asks for a
# shape absent from this table is asking for something the request cannot
# produce, which is a contract no model can satisfy.
RESPONSE_FORMAT_SHAPES: Dict[str, Tuple[str, ...]] = {
    "json_object": (SHAPE_OBJECT,),
}

# Which format each agent is sent, and which file states what it must return.
# The two together are the contract; `tests/test_pipeline.py` checks they agree.
AGENT_RESPONSE_FORMAT: Dict[str, Dict[str, str]] = {
    transcript_module.ROLE_RIDER_ADVOCATE: JSON_OBJECT_FORMAT,
    transcript_module.ROLE_DRIVER_ADVOCATE: JSON_OBJECT_FORMAT,
    transcript_module.ROLE_JUDGE: JSON_OBJECT_FORMAT,
    transcript_module.ROLE_VERIFIER: JSON_OBJECT_FORMAT,
}
AGENT_PROMPT_FILES: Dict[str, str] = {
    transcript_module.ROLE_RIDER_ADVOCATE: ADVOCATE_TEMPLATE,
    transcript_module.ROLE_DRIVER_ADVOCATE: ADVOCATE_TEMPLATE,
    transcript_module.ROLE_JUDGE: JUDGE_PROMPT_FILE,
    transcript_module.ROLE_VERIFIER: VERIFIER_PROMPT_FILE,
}

# The invariants judge.system.md states, spelled out so they can be checked.
RESULT_FIELDS = ("ruling", "discarded_claims")
POL_GEN_03_FIELDS = (
    "ruling",
    "amount_sgd",
    "driver_compensation_sgd",
    "referrals",
    "confidence",
    "explanation",
)
RULING_VALUES = (
    "NO_ACTION",
    "PARTIAL_REFUND",
    "FULL_REFUND",
    "DRIVER_COMPENSATION",
    "ESCALATE",
)
ESCALATE = "ESCALATE"
DRIVER_COMPENSATION = "DRIVER_COMPENSATION"
MONEY_FIELDS = ("amount_sgd", "driver_compensation_sgd")

UNUSABLE_RESPONSE_NOTE = "response was not the shape the prompt asked for; retried once"

# --------------------------------------------------------------------------
# The judge's vote
# --------------------------------------------------------------------------
# The judge is called K times on the same inputs and the majority decides. The
# reason is measured rather than theoretical: cases 105, 107 and 211 each
# flipped between runs whose prompts differed in ways unrelated to those cases,
# so one sample of the judge is a sample and not the answer.
DEFAULT_JUDGE_VOTES = 4

# The sampled drafts are sampled: a temperature above 0 and a distinct seed
# each, and both are recorded per draft. The position-swapped draft is *not*
# sampled -- it runs at the client's own settings, so the one thing that
# differs about it is the order in which it reads the two sides.
JUDGE_VOTE_TEMPERATURE = 0.7
JUDGE_VOTE_SEEDS = (101, 202, 303, 404, 505, 606)

# The two shapes the judge's ``claims`` value can take.
#
# ``object`` is what every run before the vote produced, and it is still what
# K = 1 produces, byte for byte. ``array`` is what a vote uses: the two sides
# travel as an ordered array of side-tagged claim arrays, so the order the judge
# reads them in is a property of the message rather than something the canonical
# serialiser decides. That is the only way a position-swapped draft can differ
# from a normal one -- canonical JSON sorts an object's keys, and it sorts
# ``DRIVER_ADVOCATE`` before ``RIDER_ADVOCATE``, so a swap written as an object
# would serialise straight back to the same bytes and would not be a swap.
JUDGE_CLAIMS_OBJECT = "object"
JUDGE_CLAIMS_ARRAY = "array"
CLAIMS_SIDE_KEY = "side"

# The order the two sides' kept claims are presented in. A normal draft is
# today's order -- the one canonical JSON already produces -- and the swapped
# draft is the reverse of it.
DRIVER_FIRST = (
    transcript_module.ROLE_DRIVER_ADVOCATE,
    transcript_module.ROLE_RIDER_ADVOCATE,
)
RIDER_FIRST = (
    transcript_module.ROLE_RIDER_ADVOCATE,
    transcript_module.ROLE_DRIVER_ADVOCATE,
)

# What each draft is, so the record can say which draft was which.
DRAFT_SAMPLED = "sampled"
DRAFT_POSITION_SWAPPED = "position_swapped"
# A judge asked once is a panel of one. The event log names that kind too, so
# a reader of the log is not left to infer from an absent ``vote`` event that
# the case ran at K = 1.
SINGLE_DRAFT = "single"

# A referral is free prose, so the machine-checkable part of it is the clause
# reference it leads with -- the limb included, because a referral to the right
# clause with the wrong limb is a different referral. This is the vote's own
# notion of a referral reference; the grader's notion lives in ``eval``, which
# this package does not read.
REFERRAL_CLAUSE_RE = re.compile(r"POL-[A-Z]{2,4}-\d{2}(?:\([a-z0-9]+\))?")

# What a vote's outcome is called, so a reader of the record is not left to
# infer it from the counts.
VOTE_CARRIED = "carried"
VOTE_CARRIED_NOT_UNANIMOUS = "carried_not_unanimous"
VOTE_ESCALATED = "escalated"
VOTE_NO_VALID_DRAFTS = "no_valid_drafts"


class PipelineError(Exception):
    """Base class for every failure the pipeline raises."""


class StanceLeakError(PipelineError):
    """The two advocate prompts differ somewhere other than the stance block."""


class BriefIdentityError(PipelineError):
    """The three agents were not handed the same brief bytes."""


class CaseDeadlineExceeded(PipelineError):
    """One case spent its whole time budget before it was finished.

    Raised rather than returned as an unusable-answer result, because it is a
    different event: nothing was answered badly, the case simply ran out of
    time. It carries the elapsed seconds so the record can name the figure the
    limit was measured against instead of only the limit.

    This is deliberately *not* the same class as
    :class:`tribunal.llm.DeadlineExceededError`, which is one call giving up.
    Both are classified as the same failure kind by the runner, because a
    reader acts on them the same way, but they are raised from different layers
    and a caller that catches one should not accidentally catch the other.
    """

    def __init__(self, message: str, *, elapsed_seconds: float, case_no: int) -> None:
        super().__init__(message)
        self.elapsed_seconds = elapsed_seconds
        self.case_no = case_no


@dataclass(frozen=True)
class CaseDeadline:
    """One case's total time budget, and the check that enforces it.

    A case is three agent calls and each may be retried once, so the check runs
    **before each call**, not only after the last one: a case stops before it
    starts work it has no time to finish, and what reaches the record is this
    deadline rather than a timeout from the call inside it. The two would
    otherwise be indistinguishable, and they call for different responses.

    ``clock`` is injectable for the same reason it is on ``LLMClient``: a test
    has to be able to move time without waiting for it.
    """

    case_no: int
    started_at: float
    limit_seconds: float
    clock: Callable[[], float] = time.monotonic

    @property
    def elapsed_seconds(self) -> float:
        return self.clock() - self.started_at

    def check(self) -> None:
        """Raise if the budget is gone. Called before every agent call."""
        elapsed = self.elapsed_seconds
        if elapsed >= self.limit_seconds:
            raise CaseDeadlineExceeded(
                "case {0} exceeded its {1:g} s deadline after {2:.1f} s".format(
                    self.case_no, self.limit_seconds, elapsed
                ),
                elapsed_seconds=elapsed,
                case_no=self.case_no,
            )


# --------------------------------------------------------------------------
# Prompt rendering, and the stance-only-difference check
# --------------------------------------------------------------------------
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def differing_line_ranges(left: str, right: str) -> List[Tuple[int, int]]:
    """The 0-indexed, half-open line ranges where two documents differ.

    Uses ``difflib`` rather than a line-by-line walk, because the two stance
    blocks are different lengths: a naive comparison would misalign everything
    after the block and report differences that are not there.
    """
    left_lines = left.splitlines()
    right_lines = right.splitlines()
    matcher = difflib.SequenceMatcher(a=left_lines, b=right_lines, autojunk=False)

    ranges: List[Tuple[int, int]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        ranges.append((min(i1, j1), max(i2, j2)))
    return ranges


def render_advocate_prompts(
    prompts_dir: Path = PROMPTS_DIR,
) -> Tuple[str, str, Tuple[int, int]]:
    """Render both advocate system prompts from the one template.

    Returns ``(rider_prompt, driver_prompt, stance_region)``, where
    ``stance_region`` is the half-open line range the substituted stance block
    occupies in either render.
    """
    template = _read(Path(prompts_dir) / ADVOCATE_TEMPLATE)
    if template.count(STANCE_PLACEHOLDER) != 1:
        raise PipelineError(
            "{0} must contain {1} exactly once; found {2}".format(
                ADVOCATE_TEMPLATE, STANCE_PLACEHOLDER, template.count(STANCE_PLACEHOLDER)
            )
        )

    stances = {
        role: _read(Path(prompts_dir) / name).rstrip("\n")
        for role, name in STANCE_FILES.items()
    }
    rendered = {
        role: template.replace(STANCE_PLACEHOLDER, stance) for role, stance in stances.items()
    }

    placeholder_line = next(
        index
        for index, line in enumerate(template.splitlines())
        if STANCE_PLACEHOLDER in line
    )
    tallest = max(len(stance.splitlines()) for stance in stances.values())
    return (
        rendered[transcript_module.ROLE_RIDER_ADVOCATE],
        rendered[transcript_module.ROLE_DRIVER_ADVOCATE],
        (placeholder_line, placeholder_line + tallest),
    )


def rendered_prompt_digests(prompts_dir: Path = PROMPTS_DIR) -> Dict[str, str]:
    """The digest of each agent's system prompt as this code renders it now.

    One entry per role a recorded call can carry, rendered through the same
    functions a run uses, so the value compared with a recorded
    ``system_sha256`` is the value a run would have recorded for that role.
    """
    prompts_dir = Path(prompts_dir)
    rider, driver, _region = render_advocate_prompts(prompts_dir)
    return {
        transcript_module.ROLE_RIDER_ADVOCATE: transcript_module.sha256_text(rider),
        transcript_module.ROLE_DRIVER_ADVOCATE: transcript_module.sha256_text(driver),
        transcript_module.ROLE_JUDGE: transcript_module.sha256_text(
            _read(prompts_dir / JUDGE_PROMPT_FILE)
        ),
    }


# The three answers a prompt comparison can give. ``MATCH`` and ``MOVED`` are
# findings; ``UNCHECKED`` is "cannot tell", and it is not a match.
PROMPT_MATCH = "match"
PROMPT_MOVED = "moved"
PROMPT_UNCHECKED = "unchecked"
PROMPT_COMPARISONS = (PROMPT_MATCH, PROMPT_MOVED, PROMPT_UNCHECKED)

# The roles a transcript can hold a call for, in the order a report reads them.
PROMPT_ROLES = (
    transcript_module.ROLE_RIDER_ADVOCATE,
    transcript_module.ROLE_DRIVER_ADVOCATE,
    transcript_module.ROLE_JUDGE,
)

# The two whose ``user_sha256`` is the brief rather than a prompt.
ADVOCATE_ROLES = (
    transcript_module.ROLE_RIDER_ADVOCATE,
    transcript_module.ROLE_DRIVER_ADVOCATE,
)


def compare_recorded_system_prompts(
    entries: Sequence[Mapping[str, Any]],
    *,
    role: str,
    rendered_sha256: str,
) -> Tuple[str, str]:
    """Whether every recorded call for one role carries the digest rendered now.

    The one comparison, in one place: :func:`replay_verdict` makes it for each
    advocate, the recorded-drafts measurement makes it for the judge, and
    :func:`compare_recorded_prompts` makes it per role over a whole transcript.

    ``PROMPT_MATCH`` when a call for that role was recorded and every one of them
    carries the digest rendered now. ``PROMPT_UNCHECKED`` when no call for that
    role was recorded, or one carries no digest -- neither can be shown to match.
    ``PROMPT_MOVED`` when one carries a different digest.
    """
    found = False
    for entry in entries:
        if entry.get("role") != role:
            continue
        found = True
        recorded = entry.get("system_sha256")
        if not isinstance(recorded, str) or not recorded:
            return PROMPT_UNCHECKED, (
                "the recorded {0} call carries no system prompt digest, so it "
                "cannot be shown that the prompt rendered now is the one that "
                "call was given".format(role)
            )
        if recorded != rendered_sha256:
            return PROMPT_MOVED, (
                "the {0} system prompt as rendered now is not the one the recorded "
                "call was given (recorded {1}, rendered {2})".format(
                    role, recorded[:16], rendered_sha256[:16]
                )
            )
    if not found:
        return PROMPT_UNCHECKED, (
            "the transcript holds no {0} call, so no prompt it was given can be "
            "compared".format(role)
        )
    return PROMPT_MATCH, ""


def compare_recorded_prompts(
    entries: Sequence[Mapping[str, Any]],
    *,
    prompts_dir: Path = PROMPTS_DIR,
    advocate_user_sha256: Optional[str] = None,
) -> Tuple[str, str]:
    """Whether the prompt digests a transcript recorded are what this code renders now.

    Compared **per role**, and only for the roles the transcript holds a call
    for: a prompt file no recorded call used cannot make a result stale, while a
    one-byte change to any prompt a recorded call did use must. The directory
    digest a run also records is kept for history and is deliberately not what
    this asks -- it moves when a file is merely added to the directory, which is
    not a statement about what any agent was given.

    Each role's system prompt is compared through
    :func:`compare_recorded_system_prompts`, and an advocate's recorded
    ``user_sha256`` is compared with the digest of the brief this code builds.
    ``advocate_user_sha256`` is that brief digest; when it is omitted, only the
    system prompts are compared.

    Returns ``(state, reason)``, with the state one of
    :data:`PROMPT_COMPARISONS`. The first role that does not match decides it.
    """
    by_role: Dict[str, List[Mapping[str, Any]]] = {}
    for entry in entries:
        role = entry.get("role")
        if role in PROMPT_ROLES:
            by_role.setdefault(role, []).append(entry)
    if not by_role:
        return PROMPT_UNCHECKED, (
            "the transcript holds no call for any of {0}, so no prompt an agent "
            "was given can be compared".format(", ".join(PROMPT_ROLES))
        )

    rendered = rendered_prompt_digests(prompts_dir)
    for role in PROMPT_ROLES:
        recorded_entries = by_role.get(role)
        if not recorded_entries:
            # A role this transcript never called. Nothing was given that
            # prompt, so nothing about it can make this result stale.
            continue
        state, reason = compare_recorded_system_prompts(
            recorded_entries, role=role, rendered_sha256=rendered[role]
        )
        if state != PROMPT_MATCH:
            return state, reason
        if role in ADVOCATE_ROLES and advocate_user_sha256 is not None:
            for entry in recorded_entries:
                recorded_user = entry.get("user_sha256")
                if recorded_user != advocate_user_sha256:
                    return PROMPT_MOVED, (
                        "the recorded {0} call was not handed the brief this code "
                        "builds (recorded {1}, built {2})".format(
                            role,
                            str(recorded_user or "nothing")[:16],
                            advocate_user_sha256[:16],
                        )
                    )
    return PROMPT_MATCH, ""


def assert_stance_only(rider: str, driver: str, region: Tuple[int, int]) -> List[Tuple[int, int]]:
    """Raise unless two rendered advocate prompts differ only inside ``region``.

    Split out from :func:`check_stance_only_difference` so the guarantee can be
    exercised directly on a pair of prompts, including a pair that deliberately
    breaks it.
    """
    ranges = differing_line_ranges(rider, driver)
    start, end = region
    outside = [(lo, hi) for lo, hi in ranges if lo < start or hi > end]
    if outside:
        raise StanceLeakError(
            "the advocate prompts differ outside the stance block: differing ranges {0}, "
            "stance block occupies lines [{1}, {2})".format(ranges, start, end)
        )
    return ranges


def check_stance_only_difference(prompts_dir: Path = PROMPTS_DIR) -> List[Tuple[int, int]]:
    """Raise unless the shipped advocate prompts differ only inside the stance block.

    Returns the differing line ranges when the check passes, so a caller can
    record what the difference was rather than merely that it was acceptable.
    """
    rider, driver, region = render_advocate_prompts(prompts_dir)
    return assert_stance_only(rider, driver, region)


# --------------------------------------------------------------------------
# The ruling shape, checked and never corrected
# --------------------------------------------------------------------------
def _finding(invariant: str, detail: str, **extra: Any) -> Dict[str, Any]:
    finding = {"invariant": invariant, "detail": detail}
    finding.update(extra)
    return finding


def as_money(value: Any) -> Optional[Decimal]:
    """A money field as ``Decimal``, or ``None``.

    JSON numbers already arrive as ``Decimal`` because ``llm`` parses with
    ``parse_float=Decimal``, the same path ``loader`` uses. This closes the
    remaining doors — a string, or an integer written without a point — so a
    float can never reach a money field.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except InvalidOperation:
            return None
    return None


def normalise_ruling(ruling: Any) -> Any:
    """Return the ruling with its money fields as ``Decimal``. Never repairs shape."""
    if not isinstance(ruling, dict):
        return ruling
    inner = ruling.get("ruling")
    if not isinstance(inner, dict):
        return ruling
    normalised = dict(inner)
    for field_name in MONEY_FIELDS:
        if field_name in normalised:
            normalised[field_name] = as_money(normalised[field_name])
    outer = dict(ruling)
    outer["ruling"] = normalised
    return outer


def validate_ruling_shape(ruling: Any) -> List[Dict[str, Any]]:
    """Every invariant ``judge.system.md`` states, as structured findings.

    Findings are recorded and never acted on. A model that breaks its own output
    contract is a measurement about that model; repairing it here would erase
    the measurement.
    """
    findings: List[Dict[str, Any]] = []

    if not isinstance(ruling, dict):
        return [
            _finding(
                "result_object",
                "the judge's answer is not a JSON object",
                found_type=type(ruling).__name__,
            )
        ]

    extra = sorted(set(ruling) - set(RESULT_FIELDS))
    missing = sorted(set(RESULT_FIELDS) - set(ruling))
    if missing:
        findings.append(
            _finding("exactly_two_top_level_fields", "required field(s) missing", missing=missing)
        )
    if extra:
        findings.append(
            _finding("exactly_two_top_level_fields", "unexpected field(s) present", extra=extra)
        )

    inner = ruling.get("ruling")
    if not isinstance(inner, dict):
        findings.append(
            _finding(
                "ruling_is_the_pol_gen_03_object",
                "the ruling field is not a JSON object",
                found_type=type(inner).__name__,
            )
        )
        return findings

    inner_extra = sorted(set(inner) - set(POL_GEN_03_FIELDS))
    inner_missing = sorted(set(POL_GEN_03_FIELDS) - set(inner))
    if inner_missing:
        findings.append(
            _finding("six_pol_gen_03_fields", "field(s) missing from ruling", missing=inner_missing)
        )
    if inner_extra:
        findings.append(
            _finding("six_pol_gen_03_fields", "unexpected field(s) in ruling", extra=inner_extra)
        )

    value = inner.get("ruling")
    if value not in RULING_VALUES:
        findings.append(
            _finding("ruling_value_is_known", "not one of the five ruling values", value=value)
        )

    if value == ESCALATE:
        offenders = [
            name for name in MONEY_FIELDS if inner.get(name) is not None
        ]
        if offenders:
            findings.append(
                _finding(
                    "escalate_has_null_money_fields",
                    "an ESCALATE ruling must carry null money fields",
                    non_null=offenders,
                )
            )

    if value == DRIVER_COMPENSATION:
        amount = inner.get("amount_sgd")
        compensation = inner.get("driver_compensation_sgd")
        if amount != compensation:
            findings.append(
                _finding(
                    "driver_compensation_mirrors_amount",
                    "amount_sgd must equal driver_compensation_sgd on a DRIVER_COMPENSATION ruling",
                    amount_sgd=str(amount),
                    driver_compensation_sgd=str(compensation),
                )
            )

    return findings


# --------------------------------------------------------------------------
# The result
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PipelineResult:
    """What one full arbitration produced."""

    case_no: int
    model: str
    ok: bool
    brief_sha256: str
    transcript: Any
    ruling: Optional[Any] = None
    ruling_findings: List[Dict[str, Any]] = field(default_factory=list)
    failed_agent: Optional[str] = None
    failure_reason: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    duration_seconds: float = 0.0
    stance_differing_ranges: List[Tuple[int, int]] = field(default_factory=list)
    # The deterministic mechanical citation ledger handed to the judge and
    # carried into the cache/viewer. It is empty only when an advocate failed
    # before the referee could run.
    referee: Dict[str, Any] = field(default_factory=dict)
    # Set only by :func:`replay_case`, and ``None`` for every arbitration this
    # invocation performed in full. Its presence is the whole difference between
    # "these agents were asked and answered" and "these answers were borrowed":
    # the token figures above then describe the judge alone, and the borrowed
    # calls' own usage travels here instead of being added to this run's bill.
    replay: Optional["ReplayProvenance"] = None
    # The judge's vote, present only when the judge was asked more than once.
    # ``None`` for a single-draft run, which is one of the things that makes a
    # K = 1 result exactly the result it was before the vote existed. It travels
    # into the transcript bytes as ``vote``, beside the referee ledger, so a
    # result read out of its directory can say how many drafts it rests on.
    judge_vote: Optional[Dict[str, Any]] = None
    # The share of the drafts that agreed on the published ruling -- 0.75 for
    # three of four. It is recorded as its own field and never in place of
    # ``confidence``: the two answer different questions, and folding the vote
    # into the confidence would make the judge's own number unreadable.
    vote_agreement: Optional[float] = None
    # The draft verifier's one call and its verdicts, or ``None`` when the
    # verifier was not switched on. ``None`` is the whole of the difference a
    # run with the switch off shows: no entry, no event and no field, so every
    # existing behaviour is byte for byte what it was.
    verification: Optional[Dict[str, Any]] = None

    @property
    def replayed(self) -> bool:
        return self.replay is not None

    @property
    def transcript_json(self) -> str:
        """The call record, the deterministic referee ledger, the vote, the verdicts."""
        payload = self.transcript.as_dict()
        if self.referee:
            payload["referee"] = self.referee
        if self.judge_vote:
            payload["vote"] = self.judge_vote
        if self.verification is not None:
            payload["verification"] = self.verification
        return money.dumps_canonical(payload)

    @property
    def transcript_sha256(self) -> str:
        """The digest of the exact transcript bytes this result writes."""
        return hashlib.sha256(self.transcript_json.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# One agent call, with a single retry when the answer is unusable
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# The two response contracts, and the shape each answer arrived in
# --------------------------------------------------------------------------
def json_shape(parsed: Any) -> str:
    """The top-level JSON shape a body arrived in, named so the record can count it.

    A body that never parsed is ``None``, and its shape is reported as the type
    name rather than being folded into one of the two JSON shapes. That keeps a
    malformed answer countable as its own outcome instead of being counted as a
    wrong wrapper.
    """
    if isinstance(parsed, dict):
        return SHAPE_OBJECT
    if isinstance(parsed, list):
        return SHAPE_ARRAY
    return type(parsed).__name__


def normalise_claims(parsed: Any) -> Tuple[Optional[List[Any]], str, str]:
    """The claims in an advocate's answer, the shape they arrived in, and why not.

    Two shapes are accepted, and both normalise to a list of claim objects:

    * an object carrying a ``claims`` array — what the prompt asks for, and the
      only thing ``json_object`` can actually produce;
    * a bare array — accepted because a model that returns one has answered the
      question, and rejecting it would be measuring the wrapper instead of the
      work. The request constrains the top level, but that constraint is the
      provider's to enforce, and a project should not fail a correct answer on
      the strength of a guarantee it does not itself control.

    An object is accepted as long as its ``claims`` value is an array of objects.
    Extra keys beside ``claims`` are deliberately not policed here: the raw body
    is on the transcript in full, so anything this function declines to look at
    is still recoverable, and "exactly one key" is the prompt's contract to
    state. Policing it in two places is how the two places come to disagree.

    Returns ``(claims, shape, reason)``. ``claims`` is ``None`` when the answer
    is unusable, and then ``reason`` says why; otherwise ``reason`` is empty.
    """
    shape = json_shape(parsed)

    if isinstance(parsed, list):
        claims = parsed
    elif isinstance(parsed, dict):
        if ADVOCATE_CLAIMS_KEY not in parsed:
            return None, shape, (
                "the advocate returned a JSON object with no {0!r} key; the claim "
                "array must travel under that key".format(ADVOCATE_CLAIMS_KEY)
            )
        claims = parsed[ADVOCATE_CLAIMS_KEY]
        if not isinstance(claims, list):
            return None, shape, (
                "the advocate's {0!r} value is not a JSON array".format(ADVOCATE_CLAIMS_KEY)
            )
    else:
        return None, shape, (
            "the advocate returned {0}, not a JSON object carrying a {1!r} array".format(
                type(parsed).__name__, ADVOCATE_CLAIMS_KEY
            )
        )

    for position, claim in enumerate(claims):
        if not isinstance(claim, dict):
            return None, shape, "claim {0} is not a JSON object".format(position)
    return claims, shape, ""


def normalise_judge_result(parsed: Any) -> Tuple[Optional[Any], str, str]:
    """The judge's result object, its shape, and why not.

    The judge's contract is unchanged and already matches ``json_object``: one
    object carrying ``ruling`` and ``discarded_claims``.
    """
    shape = json_shape(parsed)
    if not isinstance(parsed, dict):
        return None, shape, "the judge did not return a JSON object"
    missing = [name for name in RESULT_FIELDS if name not in parsed]
    if missing:
        return None, shape, "the judge's object is missing {0}".format(", ".join(missing))
    return parsed, shape, ""


def _call_agent(
    client: Any,
    *,
    role: str,
    system_prompt: str,
    user_message: str,
    normalise: Callable[[Any], Tuple[Optional[Any], str, str]],
    transcript: Any,
    deadline: Optional["CaseDeadline"] = None,
    temperature: Any = llm._UNSET,
    seed: Any = llm._UNSET,
    events_log: Optional[Any] = None,
    case_no: Optional[int] = None,
) -> Tuple[Optional[Any], Optional[str]]:
    """One agent call, retried once when the answer is unusable.

    Each attempt is its own transcript entry, so when both attempts are unusable
    **both raw bodies stay on the record**. The shape each attempt arrived in is
    recorded alongside it, which is what makes a model's choice between the two
    accepted advocate shapes a measurement rather than something to be inferred
    from the raw text. It is not returned: the transcript entry is where a shape
    belongs, and returning it as well would give two copies to keep in step.

    ``deadline`` is checked **before each attempt**, the shape retry included, so
    a case that has run out of time stops instead of starting a call it cannot
    finish. It is passed in rather than held as module state because the budget
    belongs to one case.

    ``temperature`` and ``seed`` are per-call overrides handed straight to the
    client. Both default to ``llm._UNSET``, which means "use whatever this client
    was built with", so a call that names neither is the same request it has
    always been -- byte for byte. They exist so that one client can be asked the
    same question under several seeds without its own settings being rewritten
    between calls.

    ``events_log`` is the run's append-only event log, and it is optional so
    that every existing caller -- and every test that drives this function
    directly -- keeps working without one. When it is given, each attempt
    appends one ``agent_call`` event carrying the role, the request digest, the
    usage split, the seconds and the parse outcome, read off the transcript
    entry the attempt just wrote. Recording it here rather than at the call
    site is what makes a retried call two events instead of one, which is the
    distinction the transcript has always drawn.

    Returns ``(value, None)`` on success and ``(None, reason)`` when the second
    attempt is unusable too. A spent deadline is not an unusable answer, so it
    raises :class:`CaseDeadlineExceeded` instead of returning a reason.
    """
    reason = ""
    for _attempt in (1, 2):
        if deadline is not None:
            deadline.check()
        result = client.complete(
            system_prompt,
            user_message,
            response_format=JSON_OBJECT_FORMAT,
            temperature=temperature,
            seed=seed,
        )
        value, shape, reason = normalise(result.json_body)
        entry = transcript.record(
            role=role,
            system_prompt=system_prompt,
            user_message=user_message,
            result=result,
            note=None if value is not None else UNUSABLE_RESPONSE_NOTE,
            shape=shape,
        )
        if events_log is not None:
            events_log.record(
                events.EVENT_AGENT_CALL,
                case_no=case_no,
                role=role,
                attempt=_attempt,
                # The digest of the user message this attempt was actually
                # handed, not of the message the caller meant to send: the two
                # are the same bytes by construction, and recording the one the
                # entry carries is what lets the event be checked against the
                # transcript rather than against an intention.
                request_sha256=entry.user_sha256,
                system_sha256=entry.system_sha256,
                shape=shape,
                parse_outcome=entry.parse_outcome,
                status=entry.status,
                prompt_tokens=entry.prompt_tokens,
                completion_tokens=entry.completion_tokens,
                reasoning_tokens=entry.reasoning_tokens,
                cached_tokens=entry.cached_tokens,
                total_tokens=entry.prompt_tokens + entry.completion_tokens,
                seconds=entry.duration_seconds,
            )
        if value is not None:
            return value, None
    return None, reason


# --------------------------------------------------------------------------
# The judge's vote: K drafts, and the majority decides
# --------------------------------------------------------------------------
def leading_clause_reference(referral: Any) -> str:
    """The clause reference one referral string leads with.

    ``judge.system.md`` requires every referral to lead with the clause that
    produces it, so the leading reference is the referral's subject and a clause
    named later in the same sentence is a passing mention. A string that leads
    with no clause reference at all answers :data:`NO_LEADING_CLAUSE`, which is a
    value of its own rather than an absence, so it never silently matches a
    referral that does lead with one.
    """
    if not isinstance(referral, str):
        return NO_LEADING_CLAUSE
    match = REFERRAL_CLAUSE_RE.search(referral)
    return match.group(0) if match else NO_LEADING_CLAUSE


def referral_clause_references(referrals: Any) -> Tuple[str, ...]:
    """The clause references a referral list leads with, as a sorted tuple.

    A referral is free prose, so two of them cannot be compared as strings. What
    can be compared is the clause reference each one **leads with**, the limb
    included, because a referral to the right clause with the wrong limb is a
    different referral.

    One value per referral string, rather than the union of every clause the
    string mentions. A referral whose prose cites a second clause in passing --
    "the amount is already comprehended in the POL-RD-02 figure" -- is still a
    referral about the clause it leads with, and two drafts proposing the same
    referral must not be split by the mention. Order is dropped and duplicates
    collapse: two drafts that propose the same referrals in a different order
    have proposed the same referrals.
    """
    if not isinstance(referrals, (list, tuple)):
        return ()
    found = {leading_clause_reference(item) for item in referrals}
    return tuple(sorted(found))


def vote_key(ruling: Any) -> Optional[Tuple[Any, ...]]:
    """One draft's four graded fields, together, as a single comparable value.

    The four are voted on as a unit rather than one at a time. A ruling of
    ``PARTIAL_REFUND`` carrying the wrong amount is not three-quarters of an
    answer, and a panel that agreed on the label while disagreeing on the money
    has not agreed on anything a reader can act on.

    ``None`` when the draft carries no POL-GEN-03 object at all, which is how an
    unshaped answer is kept out of the vote instead of being counted as a
    proposal of "nothing".
    """
    if not isinstance(ruling, Mapping):
        return None
    inner = ruling.get("ruling")
    if not isinstance(inner, Mapping):
        return None
    return (
        inner.get("ruling"),
        as_money(inner.get("amount_sgd")),
        as_money(inner.get("driver_compensation_sgd")),
        referral_clause_references(inner.get("referrals")),
    )


def render_vote_key(key: Optional[Tuple[Any, ...]]) -> str:
    """One draft's four graded fields, as a person reads them."""
    if key is None:
        return "no ruling"
    ruling, amount, compensation, referrals = key

    def text(value: Any) -> str:
        return "null" if value is None else str(value)

    return "{0}, amount_sgd {1}, driver_compensation_sgd {2}, referrals {3}".format(
        ruling, text(amount), text(compensation), list(referrals)
    )


def proposal_from_key(key: Optional[Tuple[Any, ...]]) -> Optional[Dict[str, Any]]:
    """A draft's proposal as the event log writes it, from its vote key.

    One function rather than three copies: a full run's single draft, every
    draft of a vote and a replayed draft all propose the same four fields, and
    the record they write must be the same shape in all three. ``None`` for a
    draft that proposed nothing, which is a fact and not an empty object.
    """
    if key is None:
        return None
    return {
        "ruling": key[0],
        "amount_sgd": key[1],
        "driver_compensation_sgd": key[2],
        "referrals": list(key[3]),
    }


# --------------------------------------------------------------------------
# The code checks a draft must pass before it may vote
#
# A draft is a model's answer, and the vote counts answers. A draft whose ruling
# is not one of the five POL-GEN-03 values, whose money is not a figure the
# brief's own calculator publishes, or whose referrals send the reviewer to a
# clause the loaded policy does not carry is not an answer a panel can be asked
# to agree with. It abstains -- with a reason code, exactly like an unparseable
# one -- and the majority is taken over the drafts that remain, so a majority of
# a panel that could not sit is still not a decision.
#
# This is the same division of labour the referee makes for the advocates'
# claims: code checks what code can check, and the judge decides the rest.
# Nothing here reads ``eval``, which this package must not import.
# --------------------------------------------------------------------------

# A referral with no clause reference in it at all. It is a value rather than an
# empty set so that a draft which leads with nothing cannot pass for a draft
# which leads with a clause.
NO_LEADING_CLAUSE = "(no leading clause reference)"

# The block's two non-money keys. ``constants`` are the policy's own numbers,
# copied into the block rather than computed by it, and ``not_structured`` names
# the figures the policy states only in prose, for which the calculator computes
# nothing.
MONEY_BLOCK_CONSTANTS = "constants"
MONEY_BLOCK_NOT_STRUCTURED = "not_structured"

# The numeric leaves of the block that are not amounts: kilometres, minutes, a
# multiplier, a share, a quantum, a distance in metres, a fix index. Adding
# kilometres to dollars is not reading an amount off a calculator. The list is
# the one the answer-key check used, so a draft is held to the standard the
# answer keys were.
NOT_MONEY_FIGURES = frozenset(
    (
        "optimal_distance_km",
        "optimal_duration_min",
        "adjusted_optimal_distance_km",
        "adjusted_optimal_duration_min",
        "amended_optimal_duration_min",
        "measured_excess_km",
        "additional_distance_km",
        "cap_km",
        "justified_excess_km",
        "shortest_lawful_alternative_km",
        "surge_multiplier",
        "cap_ratio",
        "tolerance_km",
        "full_refund_share",
        "refund_share_of_charged",
        "quantum",
        "on_optimal_route",
        "distance_m",
        "across_gap_distance_m",
        "index",
    )
)

# The figure a DRIVER_COMPENSATION ruling's amounts are governed by, as the
# block names it. POL-GEN-03 makes ``amount_sgd`` carry the same figure as
# ``driver_compensation_sgd`` on that ruling, so one name covers both fields.
# Every other money field is a refund, and the block computes the refunds it
# publishes.
DRIVER_COMPENSATION_FIGURE = "driver_compensation"

# What a money field is recorded as when the figure governing it is one the
# block marks as prose-only. It is **not** a failure: the block publishes no
# figure to check the draft against, so the draft still votes and the record
# says why the amount could not be checked.
UNVERIFIABLE_NOT_STRUCTURED = "unverifiable: not structured"

# The reason codes a draft can abstain on, as a closed set so a reader of the
# record is not left to parse the prose.
DRAFT_RULING_NOT_AN_OBJECT = "DRAFT_RULING_NOT_AN_OBJECT"
DRAFT_UNKNOWN_RULING = "DRAFT_UNKNOWN_RULING"
DRAFT_ESCALATE_WITH_MONEY = "DRAFT_ESCALATE_WITH_MONEY"
DRAFT_AMOUNT_FIELD_ABSENT = "DRAFT_AMOUNT_FIELD_ABSENT"
DRAFT_AMOUNT_REQUIRED_MISSING = "DRAFT_AMOUNT_REQUIRED_MISSING"
DRAFT_AMOUNT_DOES_NOT_MIRROR = "DRAFT_AMOUNT_DOES_NOT_MIRROR"
DRAFT_CLAUSE_MALFORMED = "DRAFT_CLAUSE_MALFORMED"
DRAFT_CLAUSE_UNRESOLVED = "DRAFT_CLAUSE_UNRESOLVED"
DRAFT_AMOUNT_NOT_READ_OFF = "DRAFT_AMOUNT_NOT_READ_OFF"
DRAFT_CHECK_CODES = (
    DRAFT_RULING_NOT_AN_OBJECT,
    DRAFT_UNKNOWN_RULING,
    DRAFT_ESCALATE_WITH_MONEY,
    DRAFT_AMOUNT_FIELD_ABSENT,
    DRAFT_AMOUNT_REQUIRED_MISSING,
    DRAFT_AMOUNT_DOES_NOT_MIRROR,
    DRAFT_CLAUSE_MALFORMED,
    DRAFT_CLAUSE_UNRESOLVED,
    DRAFT_AMOUNT_NOT_READ_OFF,
)

# Which amount fields POL-GEN-03 requires each ruling to populate. ESCALATE is
# terminal and carries neither amount; NO_ACTION leaves the present state
# standing and moves no money. A key for every ruling value, so a value added to
# RULING_VALUES without a decision here fails the test that pins the two
# together rather than silently skipping the check.
REQUIRED_AMOUNTS: Dict[str, Tuple[str, ...]] = {
    "NO_ACTION": (),
    "PARTIAL_REFUND": ("amount_sgd",),
    "FULL_REFUND": ("amount_sgd",),
    DRIVER_COMPENSATION: ("driver_compensation_sgd",),
    ESCALATE: (),
}

# A clause reference as the judge writes one, which may be malformed: the strict
# form is ``referee.CLAUSE_ID_RE``. Finding the loose form first is what lets a
# malformed reference be reported instead of silently not being seen.
CLAUSE_MENTION_RE = re.compile(r"POL-[A-Za-z]{1,6}-\d+")


def money_block(brief_object: Any) -> Optional[Mapping[str, Any]]:
    """The money block the brief publishes, or ``None`` when it publishes none.

    The block hangs off the fare breakdown, the artifact the money was charged
    on. A case with no fare breakdown gets no block, because there is nothing to
    compute on -- and then no amount can be checked against a calculator, which
    the caller has to handle rather than treat as a failure.
    """
    if not isinstance(brief_object, Mapping):
        return None
    case = brief_object.get("case")
    if not isinstance(case, Mapping):
        return None
    for artifact in case.get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        if artifact.get("evidence_type") != brief.FARE_EVIDENCE_TYPE:
            continue
        payload = artifact.get("payload")
        if not isinstance(payload, Mapping):
            continue
        derived = payload.get(brief.DERIVED_KEY)
        if not isinstance(derived, Mapping):
            continue
        block = derived.get(brief.MONEY_KEY)
        if isinstance(block, Mapping):
            return block
    return None


def _money_leaves(node: Any, path: str = "") -> List[Tuple[str, Decimal]]:
    """Every numeric leaf of the block, with the path it sits at.

    A payable is a two-place decimal string and a computed amount is a number,
    so both are read; a string that does not parse as a number is not a figure,
    which is what keeps a currency code, a fare model and a timestamp out.
    """
    found: List[Tuple[str, Decimal]] = []
    if isinstance(node, Mapping):
        for key, value in node.items():
            found.extend(_money_leaves(value, "{0}.{1}".format(path, key) if path else str(key)))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            found.extend(_money_leaves(value, "{0}[{1}]".format(path, index)))
    else:
        amount = as_money(node)
        if amount is not None:
            found.append((path, amount))
    return found


def _figure_name(path: str) -> str:
    """``closure[0].refund.payable.value`` -> ``payable``."""
    stem = path[:-6] if path.endswith(".value") else path
    return stem.split(".")[-1].split("[")[0]


def published_money_figures(block: Any) -> Tuple[Tuple[str, Decimal], ...]:
    """The money figures a block publishes, as ``(path, amount)`` pairs.

    A figure is a numeric leaf that is not under ``constants`` and is not one of
    the named quantities that are not amounts. A block that is absent or is not
    a mapping publishes nothing, which is a fact about the brief and not about
    the draft.
    """
    if not isinstance(block, Mapping):
        return ()
    found: List[Tuple[str, Decimal]] = []
    for path, amount in _money_leaves(block):
        if path.startswith(MONEY_BLOCK_CONSTANTS + "."):
            continue
        if path.startswith(MONEY_BLOCK_NOT_STRUCTURED + "."):
            continue
        if _figure_name(path) in NOT_MONEY_FIGURES:
            continue
        found.append((path, amount))
    return tuple(found)


def amount_reads_off(
    amount: Decimal, figures: Sequence[Tuple[str, Decimal]]
) -> Optional[str]:
    """How an amount is read off the block's figures, or ``None``.

    A published figure on its own, or the sum of two or three of them, and
    nothing else. Three is the bound the answer-key check used: a figure that
    needs four published operands added together is not a figure the block
    publishes. The path -- or the sum of paths -- is returned so the record can
    say which figures the amount came from.
    """
    for path, value in figures:
        if value == amount:
            return path
    for first in range(len(figures)):
        for second in range(first + 1, len(figures)):
            if figures[first][1] + figures[second][1] == amount:
                return "{0} + {1}".format(figures[first][0], figures[second][0])
    for first in range(len(figures)):
        for second in range(first + 1, len(figures)):
            for third in range(second + 1, len(figures)):
                total = figures[first][1] + figures[second][1] + figures[third][1]
                if total == amount:
                    return "{0} + {1} + {2}".format(
                        figures[first][0], figures[second][0], figures[third][0]
                    )
    return None


def governing_figure_prefix(ruling_value: Any) -> Optional[str]:
    """The block's name for the figure that governs a ruling's amounts.

    ``None`` for every ruling but DRIVER_COMPENSATION. Only the driver
    compensation figure can be one the policy states only in prose: a refund is
    computed by the calculator, and the prose-only figures around a refund are
    the caps and the ceiling that bound one, not the refund itself.
    """
    if ruling_value == DRIVER_COMPENSATION:
        return DRIVER_COMPENSATION_FIGURE
    return None


def unverifiable_amount_reason(
    ruling_value: Any,
    block: Any,
    figures: Sequence[Tuple[str, Decimal]],
) -> Optional[str]:
    """``UNVERIFIABLE_NOT_STRUCTURED`` where the governing figure is prose-only.

    POL-RD-04's per-kilometre driver compensation is the figure this exists for:
    the policy states the rate and its cap only in prose, so the calculator
    computes nothing for it and the block publishes no figure to hold a draft's
    amount against. The block says as much in ``not_structured``, and both halves
    must hold -- the block publishes no driver compensation **and** names the
    figure as prose-only -- before an unreadable amount is recorded rather than
    rejected. Where the block does publish one, as POL-NS-07's compensation is
    published on a no-show dispute, the amount is checkable and an unreadable one
    is the draft's own.
    """
    prefix = governing_figure_prefix(ruling_value)
    if prefix is None:
        return None
    for path, _ in figures:
        if prefix in path:
            return None
    for entry in (block or {}).get(MONEY_BLOCK_NOT_STRUCTURED) or []:
        figure = entry.get("figure") if isinstance(entry, Mapping) else None
        if isinstance(figure, str) and prefix in figure:
            return UNVERIFIABLE_NOT_STRUCTURED
    return None


def _clause_mentions(inner: Mapping[str, Any]) -> List[str]:
    """Every clause reference a ruling states, the referrals first.

    The referrals are where a ruling states a clause as an instruction and the
    explanation is where it states one as a reason. Both are checked: a ruling
    that sends the reviewer to a clause the loaded policy does not carry has
    referred to nothing, and one that reasons from such a clause has read
    nothing.
    """
    texts: List[Any] = []
    referrals = inner.get("referrals")
    if isinstance(referrals, (list, tuple)):
        texts.extend(referrals)
    texts.append(inner.get("explanation"))
    found: List[str] = []
    for text in texts:
        if isinstance(text, str):
            found.extend(CLAUSE_MENTION_RE.findall(text))
    return found


def check_judge_draft(
    ruling: Any, brief_object: Any
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """The code checks one draft must pass before it may vote.

    Returns the reasons it failed -- each ``"CODE: detail"`` -- and the money
    fields recorded as unverifiable, which are not failures. An empty first
    tuple means the draft votes.

    The four checks are the ruling value, the amount fields the ruling value
    requires and the ones it forbids, the clause references it states, and the
    amounts it states against the brief's own calculator. Nothing here judges
    the reasoning: a draft that passes has not been found right, only found
    well-formed.
    """
    failures: List[str] = []
    unverifiable: List[str] = []

    inner = ruling.get("ruling") if isinstance(ruling, Mapping) else None
    if not isinstance(inner, Mapping):
        return (
            (
                "{0}: the ruling field is not a POL-GEN-03 object".format(
                    DRAFT_RULING_NOT_AN_OBJECT
                ),
            ),
            (),
        )

    value = inner.get("ruling")
    if value not in RULING_VALUES:
        failures.append(
            "{0}: {1!r} is not one of the five POL-GEN-03 values".format(
                DRAFT_UNKNOWN_RULING, value
            )
        )

    if value == ESCALATE:
        carried = [name for name in MONEY_FIELDS if inner.get(name) is not None]
        if carried:
            failures.append(
                "{0}: ESCALATE must carry both amounts null; non-null: {1}".format(
                    DRAFT_ESCALATE_WITH_MONEY, ", ".join(carried)
                )
            )
    elif value in RULING_VALUES:
        absent = [name for name in MONEY_FIELDS if name not in inner]
        if absent:
            failures.append(
                "{0}: POL-GEN-03 requires {1} on the ruling object".format(
                    DRAFT_AMOUNT_FIELD_ABSENT, ", ".join(absent)
                )
            )
        missing = [
            name for name in REQUIRED_AMOUNTS[value] if as_money(inner.get(name)) is None
        ]
        if missing:
            failures.append(
                "{0}: {1} requires {2} and the field is null".format(
                    DRAFT_AMOUNT_REQUIRED_MISSING, value, ", ".join(missing)
                )
            )
        if value == DRIVER_COMPENSATION:
            # POL-GEN-03's one exception, and it is a requirement on an amount
            # field: on this ruling the two carry the same figure, because it is
            # the amount the ruling moves rather than a refund and a payment.
            amount = as_money(inner.get("amount_sgd"))
            compensation = as_money(inner.get("driver_compensation_sgd"))
            if amount != compensation:
                failures.append(
                    "{0}: POL-GEN-03 makes amount_sgd carry the same figure as "
                    "driver_compensation_sgd on a DRIVER_COMPENSATION ruling; they are "
                    "{1} and {2}".format(DRAFT_AMOUNT_DOES_NOT_MIRROR, amount, compensation)
                )

    clauses = referee.policy_clauses(brief_object)
    for token in _clause_mentions(inner):
        if referee.CLAUSE_ID_RE.fullmatch(token) is None:
            failures.append(
                "{0}: {1!r} is not a well-formed clause id".format(
                    DRAFT_CLAUSE_MALFORMED, token
                )
            )
        elif token not in clauses:
            failures.append(
                "{0}: {1!r} does not resolve in the loaded policy".format(
                    DRAFT_CLAUSE_UNRESOLVED, token
                )
            )

    block = money_block(brief_object)
    figures = published_money_figures(block)
    for field_name in MONEY_FIELDS:
        amount = as_money(inner.get(field_name))
        if amount is None:
            continue
        if amount_reads_off(amount, figures) is not None:
            continue
        reason = unverifiable_amount_reason(value, block, figures)
        if reason is not None:
            unverifiable.append("{0}={1} ({2})".format(field_name, amount, reason))
        else:
            failures.append(
                "{0}: {1}={2} is not a figure the brief's money block publishes, "
                "nor the sum of two or three of them".format(
                    DRAFT_AMOUNT_NOT_READ_OFF, field_name, amount
                )
            )

    return (tuple(failures), tuple(unverifiable))


@dataclass(frozen=True)
class JudgeDraft:
    """One draft of the judge's ruling, and what the vote made of it."""

    index: int
    kind: str
    temperature: Optional[Any]
    seed: Optional[Any]
    sides: Tuple[str, ...]
    entries: Tuple[int, ...]
    ruling: Optional[Any] = None
    key: Optional[Tuple[Any, ...]] = None
    abstention: Optional[str] = None
    unverifiable: Tuple[str, ...] = ()
    # The verifier's findings about this draft's own factual statements, or
    # ``None`` when the verifier was not switched on. It is carried per draft
    # rather than only in the vote's own block because a contradiction is
    # charged to the draft that stated it, and the record has to be able to show
    # which draft that was.
    verification: Optional[Dict[str, Any]] = None

    @property
    def valid(self) -> bool:
        return self.key is not None

    def as_dict(self, agreeing: bool) -> Dict[str, Any]:
        proposal = None
        if self.key is not None:
            proposal = {
                "ruling": self.key[0],
                "amount_sgd": self.key[1],
                "driver_compensation_sgd": self.key[2],
                "referrals": list(self.key[3]),
            }
        written = {
            "draft": self.index,
            "kind": self.kind,
            "temperature": self.temperature,
            "seed": self.seed,
            "sides": list(self.sides),
            # The transcript entries this draft occupies. An entry index rather
            # than a copy of the call, because the call is already on the
            # transcript in full and a second copy is a second thing to keep in
            # step. A draft whose first answer was unusable occupies two.
            "entries": list(self.entries),
            "valid": self.valid,
            "abstention": self.abstention,
            # The amounts whose governing figure the block marks as prose-only.
            # Recorded rather than acted on: the draft still votes, and the
            # record says which of its figures could not be checked.
            "unverifiable": list(self.unverifiable),
            "proposal": proposal,
            "agrees": agreeing if self.valid else None,
        }
        if self.verification is not None:
            # Written only when the verifier ran. "The verifier read this
            # draft's facts and found nothing wrong" and "the verifier was
            # never asked" are different findings, and a run with the switch
            # off has to stay byte for byte what it was.
            written["verification"] = self.verification
        return written



@dataclass(frozen=True)
class JudgeVote:
    """What a panel of judge drafts produced: one ruling, or the reason for none."""

    ruling: Optional[Any] = None
    findings: Tuple[Dict[str, Any], ...] = ()
    failure_reason: Optional[str] = None
    record: Dict[str, Any] = field(default_factory=dict)


def _recorded_setting(client: Any, name: str, requested: Any) -> Any:
    """The value a draft's request really carried, read rather than assumed.

    A draft that named no override ran at whatever the client was built with, so
    the record has to read that value off the client. Recording the absence
    instead would leave a reader unable to tell what the draft actually ran at.
    """
    if requested is llm._UNSET:
        return getattr(client, name, None)
    return requested


def _assemble_ruling(judge_result: Any, referee_result: Any) -> Any:
    """One judge answer as the result object the record carries.

    The referee's entries are copied verbatim **first**, then whatever the judge
    added on its own authority, and the money fields are normalised to
    ``Decimal``. This is the single place that assembly happens, so a
    single-draft run and every draft of a vote cannot assemble it two ways.
    """
    assembled = dict(judge_result)
    additions = assembled.get("discarded_claims") or []
    assembled["discarded_claims"] = list(referee_result.discards) + list(additions)
    return normalise_ruling(assembled)


def _checked_judge_message(
    rider_claims: Any,
    driver_claims: Any,
    brief_json: str,
    referee_result: Any,
    *,
    shape: str,
    sides: Sequence[str],
) -> str:
    """The judge's user message, built and then proved: same brief, canonical.

    Both proofs are the ones a single-draft run has always made. They are made
    here for every shape so that the ordered-array message is held to the same
    standard as the object one, and the brief bytes are spliced rather than
    re-serialised in either case.
    """
    message = _judge_user_message(
        rider_claims,
        driver_claims,
        brief_json,
        referee_result.discards,
        referee_result.flags,
        shape=shape,
        sides=sides,
    )
    parsed = _parse(message)
    if money.dumps_canonical(parsed["brief"]) != brief_json:
        raise BriefIdentityError("the judge was not handed the same brief bytes")
    if money.dumps_canonical(parsed) != message:
        raise BriefIdentityError("the judge's user message is not canonical JSON")
    return message


def _vote_record(
    drafts: Sequence[JudgeDraft],
    votes: int,
    threshold: int,
    agreement: Optional[float],
    agreeing: Sequence[int],
    outcome: str,
) -> Dict[str, Any]:
    """The vote as it is written into the transcript, beside the ledger."""
    agreed = set(agreeing)
    return {
        "votes": votes,
        "threshold": threshold,
        "valid": sum(1 for draft in drafts if draft.valid),
        "agreement": agreement,
        "outcome": outcome,
        "unanimous": outcome == VOTE_CARRIED,
        "drafts": [draft.as_dict(draft.index in agreed) for draft in drafts],
    }


def _with_vote_sentence(ruling: Any, votes: int, agreeing: int, agreement: float) -> Any:
    """The winning draft's ruling, with the vote result stated at its end.

    Nothing but the explanation is touched. The amounts, the referrals and the
    confidence are the draft's own, because the vote selects an answer rather
    than averaging one, and a confidence that had been blended across drafts
    would no longer be the number the judge's own Step 2 produced.
    """
    if not isinstance(ruling, Mapping):
        return ruling
    inner = ruling.get("ruling")
    if not isinstance(inner, Mapping):
        return ruling
    if agreeing == votes:
        sentence = (
            "The judge was asked {0} times on the same inputs and every draft "
            "agreed on this ruling, so it is carried unanimously (vote agreement "
            "{1:.2f}).".format(votes, agreement)
        )
    else:
        sentence = (
            "The judge was asked {0} times on the same inputs and {1} of the {0} "
            "drafts agreed on this ruling, so it is carried, not unanimous (vote "
            "agreement {2:.2f}).".format(votes, agreeing, agreement)
        )
    amended = dict(inner)
    existing = amended.get("explanation")
    text = existing if isinstance(existing, str) else ""
    amended["explanation"] = (text + "\n\n" + sentence) if text else sentence
    outer = dict(ruling)
    outer["ruling"] = amended
    return outer


def _vote_escalation(
    drafts: Sequence[JudgeDraft],
    valid: Sequence[JudgeDraft],
    referee_result: Any,
    votes: int,
    agreeing: int,
    agreement: float,
    threshold: int,
) -> Any:
    """The ruling a panel that could not agree produces, and why.

    Both money fields are ``null`` because the vote carried no ruling for an
    amount to attach to, and ``referrals`` is empty for the same reason: a
    referral is a clause-mandated instruction, and the panel agreed on none.
    ``confidence`` is 0.0, because no draft's confidence attaches to a ruling
    the panel did not reach -- the vote's own agreement is recorded separately,
    as ``vote_agreement``, and the two must not be confused.

    ``discarded_claims`` carries the referee's entries and nothing else. The
    referee's ledger is code-assembled and identical for every draft; the
    judge's own additions belong to a ruling, and there is no ruling. They are
    not lost: each draft's raw answer, additions included, is on the transcript.

    Every draft's proposal is named, because "the drafts disagreed" is only
    actionable if a reader can see what they disagreed about.
    """
    lines = [
        "The judge was asked {0} times on the same inputs and the drafts did not "
        "agree, so no ruling was carried and the dispute is escalated. Each "
        "draft proposed:".format(votes)
    ]
    for draft in drafts:
        if draft.valid:
            lines.append(
                "- draft {0} ({1}): {2}".format(
                    draft.index, draft.kind, render_vote_key(draft.key)
                )
            )
        else:
            lines.append(
                "- draft {0} ({1}): abstained -- {2}".format(
                    draft.index, draft.kind, draft.abstention or "no reason recorded"
                )
            )
    lines.append(
        "At most {0} of {1} valid drafts agreed and {2} were needed. The best "
        "supported answer is not published as a ruling: a ruling has to be the "
        "panel's, not one draft's.".format(agreeing, len(valid), threshold)
    )
    return {
        "ruling": {
            "ruling": ESCALATE,
            "amount_sgd": None,
            "driver_compensation_sgd": None,
            "referrals": [],
            "confidence": 0.0,
            "explanation": "\n".join(lines),
        },
        "discarded_claims": list(referee_result.discards),
    }


def _reduce_vote(drafts: Sequence[JudgeDraft], votes: int, referee_result: Any) -> JudgeVote:
    """Reduce K drafts to one ruling, or to the reason there is none.

    The quorum and the threshold are both a strict majority of the panel --
    ``K // 2 + 1``, which is three of four. At least that many drafts must have
    produced a usable ruling, and at least that many must agree, before an
    answer is published. Anything less escalates, because a plurality of a
    panel that could not sit is not a decision.

    Zero valid drafts is not a disagreement and is not reported as one. Nothing
    was answered, so there is nothing to disagree about, and the judge failed --
    the event this pipeline has always reported as a failure. Publishing an
    ESCALATE there would invent a ruling the judge never gave.
    """
    valid = [draft for draft in drafts if draft.valid]
    threshold = votes // 2 + 1

    if not valid:
        first = drafts[0].abstention or "no reason recorded"
        return JudgeVote(
            failure_reason=(
                "all {0} judge drafts were unusable, so no ruling was produced; "
                "the first said: {1}".format(votes, first)
            ),
            record=_vote_record(
                drafts, votes, threshold, None, (), VOTE_NO_VALID_DRAFTS
            ),
        )

    groups: Dict[Tuple[Any, ...], List[JudgeDraft]] = {}
    for draft in valid:
        groups.setdefault(draft.key, []).append(draft)

    # The most votes wins; on a tie the answer whose first draft came earliest,
    # so the reduction is a function of the drafts and not of dict ordering.
    winner_key, winner_drafts = max(
        groups.items(), key=lambda item: (len(item[1]), -item[1][0].index)
    )
    agreeing = len(winner_drafts)
    agreement = round(agreeing / votes, 6)
    carried = agreeing >= threshold and len(valid) >= threshold
    agreed_indexes = tuple(draft.index for draft in winner_drafts)

    if carried:
        outcome = VOTE_CARRIED if agreeing == votes else VOTE_CARRIED_NOT_UNANIMOUS
        published = _with_vote_sentence(winner_drafts[0].ruling, votes, agreeing, agreement)
    else:
        outcome = VOTE_ESCALATED
        published = _vote_escalation(
            drafts, valid, referee_result, votes, agreeing, agreement, threshold
        )

    return JudgeVote(
        ruling=published,
        findings=tuple(validate_ruling_shape(published)),
        record=_vote_record(drafts, votes, threshold, agreement, agreed_indexes, outcome),
    )


def _run_judge_vote(
    *,
    client: Any,
    judge_prompt: str,
    referee_result: Any,
    brief_json: str,
    transcript: Any,
    deadline: Optional["CaseDeadline"],
    votes: int,
    events_log: Optional[Any] = None,
    case_no: Optional[int] = None,
    verify: bool = False,
    verifier_prompt: str = "",
) -> JudgeVote:
    """Ask the judge ``votes`` times on the same inputs and reduce the answers.

    ``votes - 1`` drafts are sampled -- a temperature above 0 and a distinct
    seed each, both recorded -- and the last is the position-swapped draft: the
    same content with the two sides' kept claims presented in the opposite
    order, run at the client's own settings so that order is the only thing that
    differs about it.

    Every draft goes through the checks a single call goes through: the message
    is built by :func:`_judge_user_message` and proved by
    :func:`_checked_judge_message`, the answer is parsed and shape-checked by
    :func:`normalise_judge_result`, and the referee's entries are copied into its
    ``discarded_claims`` by :func:`_assemble_ruling`. A draft whose answer is
    unusable after its retry is recorded as an abstention and votes for nothing.

    A draft that parses is then held to :func:`check_judge_draft` before it may
    vote, because the vote counts answers and a malformed one is not an answer
    the panel can be asked to agree with. It abstains with its reason codes,
    exactly as an unparseable one does, and the quorum is taken over the drafts
    that remain. An amount whose governing figure the money block marks as
    prose-only is recorded as unverifiable and the draft still votes: the block
    publishes no figure to hold it against, and rejecting the draft would be
    measuring the brief rather than the answer.

    Every draft is a real call, so every draft is billed and every draft is on
    the transcript in full.
    """
    sampled = votes - 1
    if sampled > len(JUDGE_VOTE_SEEDS):
        raise PipelineError(
            "a judge vote of {0} needs {1} distinct seeds and JUDGE_VOTE_SEEDS "
            "declares {2}".format(votes, sampled, len(JUDGE_VOTE_SEEDS))
        )

    rider_claims = referee_result.kept_claims[referee.SIDE_RIDER]
    driver_claims = referee_result.kept_claims[referee.SIDE_DRIVER]
    brief_object = _parse(brief_json)
    drafts: List[JudgeDraft] = []

    def _proposal(item: JudgeDraft) -> Optional[Dict[str, Any]]:
        """What a draft proposed, as the record writes it."""
        return proposal_from_key(item.key)

    def _checks(parsed_ok: bool, failures: Sequence[str]) -> Dict[str, bool]:
        """Every code the draft checks for, and whether this draft tripped it.

        The codes that are ``False`` are recorded as well as the ones that are
        ``True``. "The check ran and passed" and "the check never ran" are
        different findings, and only one of them is evidence about the draft.
        """
        tripped = {
            code
            for code in DRAFT_CHECK_CODES
            if any(item.startswith(code + ":") for item in failures)
        }
        result: Dict[str, bool] = {"parse": parsed_ok}
        for code in DRAFT_CHECK_CODES:
            result[code] = code in tripped
        return result

    for position in range(votes):
        if position < sampled:
            kind = DRAFT_SAMPLED
            sides: Tuple[str, ...] = DRIVER_FIRST
            temperature: Any = JUDGE_VOTE_TEMPERATURE
            seed: Any = JUDGE_VOTE_SEEDS[position]
        else:
            kind = DRAFT_POSITION_SWAPPED
            sides = RIDER_FIRST
            temperature = llm._UNSET
            seed = llm._UNSET

        message = _checked_judge_message(
            rider_claims,
            driver_claims,
            brief_json,
            referee_result,
            shape=JUDGE_CLAIMS_ARRAY,
            sides=sides,
        )
        started = len(transcript)
        parsed, failure = _call_agent(
            client,
            role=transcript_module.ROLE_JUDGE,
            system_prompt=judge_prompt,
            user_message=message,
            normalise=normalise_judge_result,
            transcript=transcript,
            deadline=deadline,
            temperature=temperature,
            seed=seed,
            events_log=events_log,
            case_no=case_no,
        )
        entries = tuple(range(started, len(transcript)))
        common = dict(
            index=position + 1,
            kind=kind,
            temperature=_recorded_setting(client, "_temperature", temperature),
            seed=_recorded_setting(client, "_seed", seed),
            sides=sides,
            entries=entries,
        )
        failures: Tuple[str, ...] = ()
        if parsed is None:
            draft = JudgeDraft(abstention=failure, **common)
        else:
            ruling = _assemble_ruling(parsed, referee_result)
            failures, unverifiable = check_judge_draft(ruling, brief_object)
            if failures:
                # A malformed draft abstains with its reason codes, which is
                # what an unparseable one does: it is not an answer the panel
                # can be asked to agree with.
                draft = JudgeDraft(
                    abstention="; ".join(failures),
                    unverifiable=unverifiable,
                    **common
                )
            else:
                draft = JudgeDraft(
                    ruling=ruling,
                    key=vote_key(ruling),
                    unverifiable=unverifiable,
                    **common
                )
        drafts.append(draft)
        if events_log is not None:
            events_log.record(
                events.EVENT_JUDGE_DRAFT,
                case_no=case_no,
                draft=draft.index,
                kind=draft.kind,
                seed=draft.seed,
                temperature=draft.temperature,
                sides=list(draft.sides),
                proposal=_proposal(draft),
                checks=_checks(parsed is not None, failures),
                abstention=draft.abstention,
                unverifiable=list(draft.unverifiable),
                valid=draft.valid,
            )

    # The verifier runs here, after every draft has been checked and before the
    # vote is reduced, so a contradiction can keep a draft out of the count. It
    # is one call over all the valid drafts, whatever their number.
    verification: Optional[Dict[str, Any]] = None
    if verify:
        drafts, verification = verify_draft_statements(
            client,
            brief_json=brief_json,
            drafts=drafts,
            verifier_prompt=verifier_prompt,
            transcript=transcript,
            deadline=deadline,
            events_log=events_log,
            case_no=case_no,
        )

    vote = _reduce_vote(drafts, votes, referee_result)
    if verification is not None:
        # The verdicts ride on the vote's own record, beside the drafts they
        # were charged to, so a reader of the transcript sees the two together.
        vote = JudgeVote(
            ruling=vote.ruling,
            findings=vote.findings,
            failure_reason=vote.failure_reason,
            record=dict(vote.record, verification=verification),
        )
    if events_log is not None:
        events_log.record(
            events.EVENT_VOTE,
            case_no=case_no,
            votes=vote.record.get("votes"),
            threshold=vote.record.get("threshold"),
            valid=vote.record.get("valid"),
            agreement=vote.record.get("agreement"),
            outcome=vote.record.get("outcome"),
            unanimous=vote.record.get("unanimous"),
            proposals=[_proposal(draft) for draft in drafts if draft.valid],
        )
    return vote


# --------------------------------------------------------------------------
# The draft verifier
#
# Off by default. When it is on, one extra call per case -- never one per draft
# and never one per statement -- asks whether the brief supports the facts a
# draft states. Code extracts the statements; the model only judges them, and it
# judges them against the brief and nothing else. It decides no part of the
# ruling: a draft whose facts are contradicted abstains, and a draft whose facts
# are merely absent from the record is recorded and still votes.
# --------------------------------------------------------------------------
VERIFIER_TEMPERATURE = 0.0

# The three verdicts a statement can receive.
VERDICT_SUPPORTED = "supported"
VERDICT_CONTRADICTED = "contradicted"
VERDICT_NOT_IN_EVIDENCE = "not_in_evidence"
VERDICTS = (VERDICT_SUPPORTED, VERDICT_CONTRADICTED, VERDICT_NOT_IN_EVIDENCE)

# The reason a draft abstains when the verifier contradicts one of its facts.
ABSTENTION_CONTRADICTED = "CONTRADICTED_BY_EVIDENCE"

# A contradicted verdict also says what the brief holds and whether the
# difference could change a conclusion. Rounding is not material: a draft
# writing "22.6%" where the brief holds 22.47% leaves every threshold, amount,
# ordering and question of who did what exactly where it was, and stopping a
# correct draft over it turns a unanimous ruling into an escalation. Material
# means the brief's value would move a conclusion the statement draws.
VERDICT_MATERIAL = "material"
VERDICT_BRIEF_VALUE = "brief_value"

# Which contradictions stop a draft. ``ABSTAIN_ON_MATERIAL`` is what the
# pipeline does. ``ABSTAIN_ON_ANY`` exists so the recorded-drafts report can
# show both readings of one set of verdicts without asking the verifier twice,
# and it is the stricter of the two: it is what the pass did before materiality
# existed.
ABSTAIN_ON_MATERIAL = "material"
ABSTAIN_ON_ANY = "any"
ABSTAIN_ON = (ABSTAIN_ON_MATERIAL, ABSTAIN_ON_ANY)

# What kind of checkable fact a sentence carries. A sentence with none of these
# is not a factual statement and is never sent to the verifier.
STATEMENT_KIND_NUMBER = "number"
STATEMENT_KIND_TIME = "time"
STATEMENT_KIND_DISTANCE = "distance"
STATEMENT_KIND_MONEY = "money"
STATEMENT_KIND_EVIDENCE_ID = "evidence_id"
STATEMENT_KINDS = (
    STATEMENT_KIND_NUMBER,
    STATEMENT_KIND_TIME,
    STATEMENT_KIND_DISTANCE,
    STATEMENT_KIND_MONEY,
    STATEMENT_KIND_EVIDENCE_ID,
)

# The detectors, one per kind. Each is deliberately narrow: a sentence with no
# fact in it is better left out than sent, because every statement sent is a
# line the model must answer and a reader must read. They are code, not the
# model's, so which statements are checked is reproducible from the text alone.
_EVIDENCE_ID_RE = re.compile(r"\bEV-[A-Za-z0-9]+-\d+\b")
_CLOCK_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_DURATION_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:s|sec|secs|seconds|min|mins|minute|minutes|h|hr|hrs|hour|hours)\b",
    re.IGNORECASE,
)
_DISTANCE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:m|km|metres?|meters?|miles?|mi)\b", re.IGNORECASE
)
_MONEY_RE = re.compile(
    r"(?:SGD|S\$|\$)\s*\d+(?:\.\d+)?|\b\d+(?:\.\d+)?\s*(?:SGD|dollars?|cents?)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")

# A sentence ends at terminal punctuation followed by whitespace. The lookbehind
# keeps the decimal point inside a number ("4.35 SGD") from being read as the
# end of a sentence, because the character after that period is a digit.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> List[str]:
    """The sentences of a passage, in order, with whitespace stripped.

    Split on newlines first, then on terminal punctuation followed by
    whitespace, so a paragraph, a bulleted list and a single line are all read
    the same way. An empty fragment is dropped rather than returned.
    """
    if not isinstance(text, str):
        return []
    found: List[str] = []
    for line in re.split(r"[\r\n]+", text):
        for piece in _SENTENCE_SPLIT_RE.split(line):
            piece = piece.strip()
            if piece:
                found.append(piece)
    return found


def statement_kinds(sentence: str) -> Tuple[str, ...]:
    """Which kinds of checkable fact a sentence carries, in a fixed order.

    The kinds are the ones the verifier exists for: a number, a time, a
    distance, a money figure and an evidence id. They overlap on purpose -- an
    evidence id and a money figure are also numbers -- because the question here
    is only whether the sentence states a fact at all, and the named kinds are
    what the record shows a reader about why it was sent.
    """
    kinds: List[str] = []
    if _NUMBER_RE.search(sentence):
        kinds.append(STATEMENT_KIND_NUMBER)
    if _MONEY_RE.search(sentence):
        kinds.append(STATEMENT_KIND_MONEY)
    if _EVIDENCE_ID_RE.search(sentence):
        kinds.append(STATEMENT_KIND_EVIDENCE_ID)
    if (
        _CLOCK_TIME_RE.search(sentence)
        or _DATE_RE.search(sentence)
        or _DURATION_RE.search(sentence)
    ):
        kinds.append(STATEMENT_KIND_TIME)
    if _DISTANCE_RE.search(sentence):
        kinds.append(STATEMENT_KIND_DISTANCE)
    return tuple(kinds)


def extract_factual_statements(text: str) -> List[Tuple[str, Tuple[str, ...]]]:
    """Every sentence that states a checkable fact, with the kinds it states.

    A sentence is returned only when at least one detector matches it. A
    sentence with no number, time, distance, money figure or evidence id states
    no fact this verifier can check, so it is not returned and is never sent.
    """
    found: List[Tuple[str, Tuple[str, ...]]] = []
    for sentence in split_sentences(text):
        kinds = statement_kinds(sentence)
        if kinds:
            found.append((sentence, kinds))
    return found


def numbered_statements(drafts: Sequence[JudgeDraft]) -> List[Dict[str, Any]]:
    """The statements of every valid draft, numbered once across the case.

    The numbering is global so a verdict names exactly one statement, and each
    entry carries the draft it came from so a contradiction can be charged to
    the draft that stated it. Only valid drafts contribute: a draft that already
    abstained is not an answer the panel is weighing, and there is nothing to
    verify about it.
    """
    numbered: List[Dict[str, Any]] = []
    for draft in drafts:
        if not draft.valid:
            continue
        inner = draft.ruling.get("ruling") if isinstance(draft.ruling, Mapping) else None
        text = inner.get("explanation") if isinstance(inner, Mapping) else None
        for sentence, kinds in extract_factual_statements(text if isinstance(text, str) else ""):
            numbered.append(
                {
                    "n": len(numbered) + 1,
                    "draft": draft.index,
                    "text": sentence,
                    "kinds": list(kinds),
                }
            )
    return numbered


def verifier_user_message(brief_json: str, statements: Sequence[Mapping[str, Any]]) -> str:
    """The verifier's user message: the judge's own brief bytes and the list.

    The brief is spliced rather than re-serialised, so the verifier reads the
    same characters the judge read. Only the number, the draft and the text
    travel: the kinds are this package's own bookkeeping and are not part of
    what the model is asked.
    """
    listed = [
        {"n": item["n"], "draft": item["draft"], "text": item["text"]}
        for item in statements
    ]
    return (
        '{"brief":' + brief_json + ',"statements":' + money.dumps_canonical(listed) + "}"
    )


def normalise_verifier_result(parsed: Any) -> Tuple[Optional[List[Dict[str, Any]]], str, str]:
    """The verdicts in the verifier's answer, the shape it arrived in, and why not.

    Strict on purpose. The contract is one entry per statement, so a body that
    is not an object, that has no ``verdicts`` list, or whose every entry does
    not carry an integer ``statement``, one of the three verdicts and a string
    ``evidence`` is unusable -- and an unusable body is treated as no
    verification at all rather than as a partial one, because a verdict set with
    a hole in it is not a check.

    A ``contradicted`` verdict carries two more things, and one of them is
    required: a boolean ``material``, because whether the difference could move
    a conclusion is the whole of what decides whether the draft keeps its vote,
    and an answer that leaves it out cannot be guessed at. ``brief_value`` is
    what the brief holds instead; it is recorded rather than required, since a
    contradiction whose evidence is a derived-fact path may have no single value
    to quote.
    """
    shape = json_shape(parsed)
    if not isinstance(parsed, dict):
        return None, shape, "the verifier did not return a JSON object"
    if "verdicts" not in parsed:
        return None, shape, "the verifier's object has no 'verdicts' key"
    entries = parsed["verdicts"]
    if not isinstance(entries, list):
        return None, shape, "the verifier's 'verdicts' value is not a list"
    verdicts: List[Dict[str, Any]] = []
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            return None, shape, "verdict {0} is not a JSON object".format(position)
        number = entry.get("statement")
        if isinstance(number, bool) or not isinstance(number, int):
            return None, shape, (
                "verdict {0} carries no integer 'statement'".format(position)
            )
        verdict = entry.get("verdict")
        if verdict not in VERDICTS:
            return None, shape, (
                "verdict {0} names {1!r}, which is not one of {2}".format(
                    position, verdict, ", ".join(VERDICTS)
                )
            )
        evidence = entry.get("evidence")
        if evidence is None:
            evidence = ""
        if not isinstance(evidence, str):
            return None, shape, (
                "verdict {0}'s 'evidence' is not a string".format(position)
            )
        material: Any = None
        brief_value: Any = ""
        if verdict == VERDICT_CONTRADICTED:
            material = entry.get(VERDICT_MATERIAL)
            # ``isinstance(True, int)`` is true, so the check is for a real
            # boolean and not for something merely truthy: "material": 1 is an
            # answer that does not say whether the difference matters.
            if not isinstance(material, bool):
                return None, shape, (
                    "verdict {0} contradicts statement {1} without a boolean "
                    "'{2}', so whether the difference could change a conclusion "
                    "is not stated".format(position, number, VERDICT_MATERIAL)
                )
            brief_value = entry.get(VERDICT_BRIEF_VALUE)
            if brief_value is None:
                brief_value = ""
            elif not isinstance(brief_value, (str, int, float)):
                # A JSON number arrives as a ``Decimal`` here, and a value the
                # record's encoder cannot write would break the record rather
                # than the check. This is a display value, so rendering it as
                # text loses nothing a reader needs.
                brief_value = str(brief_value)
        verdicts.append(
            {
                "statement": number,
                "verdict": verdict,
                "evidence": evidence,
                VERDICT_MATERIAL: material,
                VERDICT_BRIEF_VALUE: brief_value,
            }
        )
    return verdicts, shape, ""


def _verifier_call(
    client: Any,
    *,
    system_prompt: str,
    user_message: str,
    transcript: Any,
    deadline: Optional["CaseDeadline"],
    events_log: Optional[Any],
    case_no: Optional[int],
) -> Tuple[Optional[List[Dict[str, Any]]], str, Any]:
    """Ask the verifier once. Returns ``(verdicts, reason, entry)``.

    Exactly one call and no retry, which is the difference between this and
    every other agent: the verifier's contract is one call per case, and a
    malformed answer is treated as no verification rather than chased with a
    second call. The call is on the transcript and on the event log like any
    other, so a reader can see what was asked and what came back.
    """
    if deadline is not None:
        deadline.check()
    result = client.complete(
        system_prompt,
        user_message,
        response_format=JSON_OBJECT_FORMAT,
        temperature=VERIFIER_TEMPERATURE,
    )
    verdicts, shape, reason = normalise_verifier_result(result.json_body)
    entry = transcript.record(
        role=transcript_module.ROLE_VERIFIER,
        system_prompt=system_prompt,
        user_message=user_message,
        result=result,
        note=None if verdicts is not None else UNUSABLE_RESPONSE_NOTE,
        shape=shape,
    )
    if events_log is not None:
        events_log.record(
            events.EVENT_AGENT_CALL,
            case_no=case_no,
            role=transcript_module.ROLE_VERIFIER,
            attempt=1,
            request_sha256=entry.user_sha256,
            system_sha256=entry.system_sha256,
            shape=shape,
            parse_outcome=entry.parse_outcome,
            status=entry.status,
            prompt_tokens=entry.prompt_tokens,
            completion_tokens=entry.completion_tokens,
            reasoning_tokens=entry.reasoning_tokens,
            cached_tokens=entry.cached_tokens,
            total_tokens=entry.prompt_tokens + entry.completion_tokens,
            seconds=entry.duration_seconds,
        )
    return verdicts, reason, entry


def _tokens_of(entry: Any) -> Dict[str, int]:
    """One transcript entry's usage, as the split the record writes."""
    return {
        "prompt_tokens": entry.prompt_tokens,
        "completion_tokens": entry.completion_tokens,
        "reasoning_tokens": entry.reasoning_tokens,
        "cached_tokens": entry.cached_tokens,
        "total_tokens": entry.prompt_tokens + entry.completion_tokens,
    }


def apply_verification(
    drafts: Sequence[JudgeDraft],
    statements: Sequence[Mapping[str, Any]],
    verdicts: Sequence[Mapping[str, Any]],
    *,
    abstain_on: str = ABSTAIN_ON_MATERIAL,
) -> Tuple[List[JudgeDraft], List[Dict[str, Any]]]:
    """Charge every verdict to the draft that stated it.

    A draft with a contradiction that could change a conclusion abstains, with
    the reason code and the statement quoted, so a reader can see which fact was
    rejected. A contradiction that changes nothing -- a difference of rounding
    or precision, where every threshold, amount, ordering and question of who did
    what comes out the same either way -- is recorded on the draft and the draft
    **keeps its vote**. A draft whose statements are merely absent from the
    record keeps its vote too, and those are recorded as flags. A draft with no
    statements is untouched.

    ``abstain_on`` chooses which contradictions stop a draft. The default is
    what the pipeline does. ``ABSTAIN_ON_ANY`` is the stricter reading the
    recorded-drafts report shows beside it, so one set of verdicts can be read
    both ways without a second call.

    Returns the drafts and the flat list of judged statements, each carrying its
    verdict, its materiality and the value the brief holds, which is what the
    record and the report read.
    """
    if abstain_on not in ABSTAIN_ON:
        raise PipelineError(
            "abstain_on must be one of {0}; found {1!r}".format(
                ", ".join(ABSTAIN_ON), abstain_on
            )
        )
    by_number = {item["statement"]: item for item in verdicts}
    judged: List[Dict[str, Any]] = []
    for item in statements:
        verdict = by_number.get(item["n"])
        contradicted = verdict is not None and verdict["verdict"] == VERDICT_CONTRADICTED
        judged.append(
            {
                "n": item["n"],
                "draft": item["draft"],
                "text": item["text"],
                "kinds": list(item["kinds"]),
                "verdict": None if verdict is None else verdict["verdict"],
                "evidence": "" if verdict is None else verdict["evidence"],
                VERDICT_MATERIAL: (
                    bool(verdict[VERDICT_MATERIAL]) if contradicted else None
                ),
                VERDICT_BRIEF_VALUE: (
                    "" if verdict is None else verdict.get(VERDICT_BRIEF_VALUE, "")
                ),
            }
        )

    by_draft: Dict[int, List[Dict[str, Any]]] = {}
    for item in judged:
        by_draft.setdefault(item["draft"], []).append(item)

    updated: List[JudgeDraft] = []
    for draft in drafts:
        items = by_draft.get(draft.index)
        if not items:
            updated.append(draft)
            continue
        contradicted = [
            item for item in items if item["verdict"] == VERDICT_CONTRADICTED
        ]
        material = [item for item in contradicted if item[VERDICT_MATERIAL]]
        not_in_evidence = [
            item for item in items if item["verdict"] == VERDICT_NOT_IN_EVIDENCE
        ]
        stops = contradicted if abstain_on == ABSTAIN_ON_ANY else material
        verification = {
            "statements": len(items),
            "contradicted": contradicted,
            "material": material,
            "not_in_evidence": not_in_evidence,
        }
        if stops:
            updated.append(
                JudgeDraft(
                    index=draft.index,
                    kind=draft.kind,
                    temperature=draft.temperature,
                    seed=draft.seed,
                    sides=draft.sides,
                    entries=draft.entries,
                    ruling=draft.ruling,
                    key=None,
                    abstention='{0}: "{1}"'.format(
                        ABSTENTION_CONTRADICTED, stops[0]["text"]
                    ),
                    unverifiable=draft.unverifiable,
                    verification=verification,
                )
            )
        else:
            updated.append(
                JudgeDraft(
                    index=draft.index,
                    kind=draft.kind,
                    temperature=draft.temperature,
                    seed=draft.seed,
                    sides=draft.sides,
                    entries=draft.entries,
                    ruling=draft.ruling,
                    key=draft.key,
                    abstention=draft.abstention,
                    unverifiable=draft.unverifiable,
                    verification=verification,
                )
            )
    return updated, judged


def verify_draft_statements(
    client: Any,
    *,
    brief_json: str,
    drafts: Sequence[JudgeDraft],
    verifier_prompt: str,
    transcript: Any,
    deadline: Optional["CaseDeadline"],
    events_log: Optional[Any] = None,
    case_no: Optional[int] = None,
) -> Tuple[List[JudgeDraft], Dict[str, Any]]:
    """One verifier call over every valid draft, and the drafts it leaves.

    Called once per case, after the drafts have passed the code checks and
    before the vote is reduced. Returns the drafts with the verdicts applied and
    the record the transcript, the event log and the cache all carry.

    Three outcomes, and the record says which happened. No statements at all:
    no call is made, because there is nothing to ask. A call whose answer is
    unusable: every draft keeps its vote and the record says the verification
    could not be made, so a broken verifier cannot silently change a ruling. A
    usable answer: the verdicts are applied, and only a contradiction that could
    change a conclusion stops a draft.
    """
    statements = numbered_statements(drafts)
    if not statements:
        return list(drafts), {
            "called": False,
            "usable": False,
            "reason": "the valid drafts state no checkable facts",
            "statements": [],
            "judged": [],
            "counts": {
                VERDICT_SUPPORTED: 0,
                VERDICT_CONTRADICTED: 0,
                VERDICT_NOT_IN_EVIDENCE: 0,
            },
            "material": 0,
            "not_material": 0,
            "abstained": [],
            "abstain_on": ABSTAIN_ON_MATERIAL,
            "entry": None,
            "tokens": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "reasoning_tokens": 0,
                "cached_tokens": 0,
                "total_tokens": 0,
            },
        }

    message = verifier_user_message(brief_json, statements)
    verdicts, reason, entry = _verifier_call(
        client,
        system_prompt=verifier_prompt,
        user_message=message,
        transcript=transcript,
        deadline=deadline,
        events_log=events_log,
        case_no=case_no,
    )
    entry_index = len(transcript) - 1
    tokens = _tokens_of(entry)

    expected = [item["n"] for item in statements]
    if verdicts is not None:
        returned = [item["statement"] for item in verdicts]
        if len(set(returned)) != len(returned) or sorted(returned) != sorted(expected):
            # One entry per statement is the contract. A set that does not cover
            # every statement exactly once is not a check, so it is treated like
            # an unparseable answer rather than applied to part of the drafts.
            verdicts = None
            reason = (
                "the verifier answered statements {0} where {1} were asked".format(
                    sorted(returned), expected
                )
            )

    if verdicts is None:
        return list(drafts), {
            "called": True,
            "usable": False,
            "reason": reason,
            "statements": statements,
            "judged": [],
            "counts": {
                VERDICT_SUPPORTED: 0,
                VERDICT_CONTRADICTED: 0,
                VERDICT_NOT_IN_EVIDENCE: 0,
            },
            "material": 0,
            "not_material": 0,
            "abstained": [],
            "abstain_on": ABSTAIN_ON_MATERIAL,
            "entry": entry_index,
            "tokens": tokens,
        }

    updated, judged = apply_verification(drafts, statements, verdicts)
    counts = {
        verdict: sum(1 for item in judged if item["verdict"] == verdict)
        for verdict in VERDICTS
    }
    material = sum(
        1
        for item in judged
        if item["verdict"] == VERDICT_CONTRADICTED and item[VERDICT_MATERIAL]
    )
    abstained = [
        draft.index
        for draft in updated
        if draft.abstention is not None
        and draft.abstention.startswith(ABSTENTION_CONTRADICTED + ":")
    ]
    record: Dict[str, Any] = {
        "called": True,
        "usable": True,
        "reason": "",
        "statements": statements,
        "judged": judged,
        "counts": counts,
        "material": material,
        "not_material": counts[VERDICT_CONTRADICTED] - material,
        "abstained": abstained,
        "abstain_on": ABSTAIN_ON_MATERIAL,
        "entry": entry_index,
        "tokens": tokens,
    }
    if events_log is not None:
        events_log.record(
            events.EVENT_VERIFICATION,
            case_no=case_no,
            called=True,
            usable=True,
            statements=len(statements),
            supported=counts[VERDICT_SUPPORTED],
            contradicted=counts[VERDICT_CONTRADICTED],
            material=material,
            not_material=counts[VERDICT_CONTRADICTED] - material,
            not_in_evidence=counts[VERDICT_NOT_IN_EVIDENCE],
            abstained=abstained,
        )
    return updated, record


def reduce_vote(
    drafts: Sequence[JudgeDraft], votes: int, referee_result: Any
) -> JudgeVote:
    """The public name for the reduction, so a caller outside this module can
    reduce a set of drafts it rebuilt rather than one it just called for."""
    return _reduce_vote(drafts, votes, referee_result)


def recorded_judge_drafts(
    vote_block: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    referee_result: Any,
    brief_object: Any,
) -> List[JudgeDraft]:
    """Rebuild the drafts a recorded vote was reduced from.

    The recorded transcript carries the vote it produced, and the vote names the
    transcript entries each draft occupies. This reads those entries back and
    runs each through the same assembly and the same code checks a live draft
    runs through, so the drafts a recorded-drafts measurement verifies are the
    drafts the recorded vote counted -- not a second reconstruction that could
    differ from them.
    """
    rebuilt: List[JudgeDraft] = []
    for record in vote_block.get("drafts") or []:
        if not isinstance(record, Mapping):
            continue
        indices = tuple(
            int(item) for item in (record.get("entries") or []) if isinstance(item, int)
        )
        parsed = None
        if indices and 0 <= indices[-1] < len(entries):
            parsed = entries[indices[-1]].get("parsed")
        common: Dict[str, Any] = dict(
            index=record.get("draft"),
            kind=record.get("kind"),
            temperature=record.get("temperature"),
            seed=record.get("seed"),
            sides=tuple(record.get("sides") or ()),
            entries=indices,
        )
        if parsed is None:
            rebuilt.append(
                JudgeDraft(
                    abstention=record.get("abstention") or "no reason recorded",
                    **common
                )
            )
            continue
        ruling = _assemble_ruling(parsed, referee_result)
        failures, unverifiable = check_judge_draft(ruling, brief_object)
        if failures:
            rebuilt.append(
                JudgeDraft(
                    abstention="; ".join(failures), unverifiable=unverifiable, **common
                )
            )
        else:
            rebuilt.append(
                JudgeDraft(
                    ruling=ruling,
                    key=vote_key(ruling),
                    unverifiable=unverifiable,
                    **common
                )
            )
    return rebuilt


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------
def _user_digest(transcript: Any, role: str) -> Optional[str]:
    """The user-message digest of the first entry recorded for ``role``."""
    for entry in transcript.entries:
        if entry.role == role:
            return entry.user_sha256
    return None


def run_case(
    case_no: int,
    client: Any,
    *,
    prompts_dir: Path = PROMPTS_DIR,
    now: Optional[Callable[[], str]] = None,
    case_deadline_seconds: float = DEFAULT_CASE_DEADLINE_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    case_loader: Optional[Callable[[int], Dict[str, Any]]] = None,
    judge_votes: int = DEFAULT_JUDGE_VOTES,
    events_log: Optional[Any] = None,
    verify_drafts: bool = False,
    ablate: Optional[str] = None,
) -> PipelineResult:
    """Perform one full arbitration of a case named by its manifest number.

    The case is loaded from the manifest and handed to
    :func:`run_loaded_case`, which holds the whole of the arbitration. This
    function exists only to name a case by number and has no logic of its own,
    so there cannot be a second path that applies a weaker guard.

    ``case_loader`` is how a case that is deliberately not in the manifest is
    still named by number. It defaults to ``loader.load_case``, so the corpus
    path is unchanged; a development set carrying its own index passes its own
    loader, and everything below the load is the same code either way. The
    alternative -- a set that reaches :func:`run_loaded_case` directly -- would
    be a second by-number entry point, which is what this parameter exists to
    avoid.

    ``judge_votes`` is how many times the judge is asked, and it is passed
    straight through for the same reason: there is one arbitration body and this
    is not a second one.

    ``ablate`` names one ablation of the brief, or ``None`` for none, and it is
    passed straight through for that same reason. It is applied in exactly one
    place -- :func:`tribunal.brief.build_brief_for_case` -- so an ablated run
    differs from a plain one in what the agents were given and in nothing else.
    """
    load = loader.load_case if case_loader is None else case_loader
    return run_loaded_case(
        load(case_no),
        client,
        prompts_dir=prompts_dir,
        now=now,
        case_deadline_seconds=case_deadline_seconds,
        clock=clock,
        judge_votes=judge_votes,
        events_log=events_log,
        verify_drafts=verify_drafts,
        ablate=ablate,
    )


def run_loaded_case(
    case: Dict[str, Any],
    client: Any,
    *,
    prompts_dir: Path = PROMPTS_DIR,
    now: Optional[Callable[[], str]] = None,
    case_deadline_seconds: float = DEFAULT_CASE_DEADLINE_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    judge_votes: int = DEFAULT_JUDGE_VOTES,
    events_log: Optional[Any] = None,
    verify_drafts: bool = False,
    ablate: Optional[str] = None,
) -> PipelineResult:
    """Perform one full arbitration of a case already in hand.

    Every guard is the one :func:`run_case` has always applied, because this is
    the body that function runs. The brief is serialised exactly once and those
    same bytes are handed to both advocates and embedded in the judge's message;
    the stance-only difference is checked before the first call is made; and
    ``case_deadline_seconds`` bounds the whole case -- every agent call and any
    shape retry -- where ``LLMClient``'s own deadline bounds one call. The
    budget is checked before each call and a case that has spent it raises
    :class:`CaseDeadlineExceeded`, which carries the elapsed seconds.

    Split out so a converted external case can be arbitrated without being added
    to ``data/index.json``. It is loaded through its own explicit path by
    ``loader.load_external_case``, and adding it to the manifest would change the
    29-case corpus the submission reports. The alternative -- a second entry
    point carrying its own copy of these guards -- is what this split exists to
    avoid: there is one implementation, and both callers run it.

    ``clock`` is injectable so the deadline can be exercised without waiting.

    ``judge_votes`` is how many times the judge is asked. At 1 -- what every run
    before the vote used, and what a caller who wants a single sample still gets
    -- the judge is called once with the message it has always been handed and
    the result carries no vote at all, so a single-draft run is byte for byte
    what it was. At 2 or more the judge is called that many times on the same
    inputs and the majority decides; see :func:`_run_judge_vote`.

    ``ablate`` names one ablation of the brief, or ``None`` for none. It is
    checked here rather than only inside the builder, so an unknown name is one
    refusal naming the names that do exist instead of a per-case failure; and it
    is applied in exactly one place, the single call to
    :func:`tribunal.brief.build_brief_for_case` below, so there is one brief and
    an ablated run is that brief built without part of it rather than a second
    builder that could differ from the first. The bytes are still serialised
    once and handed to both advocates and the judge, ablated or not.
    """
    case_no = case["case_no"]
    prompts_dir = Path(prompts_dir)
    if judge_votes < 1:
        raise PipelineError("judge_votes must be at least 1, got {0}".format(judge_votes))
    if verify_drafts and judge_votes < 2:
        # Refused rather than ignored. The verifier is asked over the drafts of
        # a panel; a single-draft run has no panel to verify and its one call is
        # preserved byte for byte as it always was, so naming the verifier here
        # is a request this pipeline cannot honour and says so.
        raise PipelineError(
            "verify_drafts needs a judge vote of at least 2, got {0}: the verifier "
            "is asked over a panel of drafts".format(judge_votes)
        )
    if ablate is not None and not brief.ablation_known(ablate):
        raise PipelineError(
            "no ablation called {0!r}; the ablations are {1}".format(
                ablate, ", ".join(brief.ABLATIONS)
            )
        )

    # The project's second structural claim, checked before any call is made.
    stance_ranges = check_stance_only_difference(prompts_dir)

    # Read only when the verifier is on, so a run with the switch off never
    # opens the file and is byte for byte what it was.
    verifier_prompt = _read(prompts_dir / VERIFIER_PROMPT_FILE) if verify_drafts else ""

    # ONE serialisation of the brief, and one digest of those exact bytes. The
    # ablation is applied here and nowhere else: this is the one builder, and
    # ``ablate=None`` -- what every caller before the switch passed, and what
    # :func:`build_brief` still passes -- builds the bytes it always built.
    case_brief = brief.build_brief_for_case(case, ablate=ablate)
    brief_json = money.dumps_canonical(case_brief)
    brief_sha256 = hashlib.sha256(brief_json.encode("utf-8")).hexdigest()
    advocate_user_message = brief_json

    if advocate_user_message is not brief_json:
        raise BriefIdentityError("the brief was serialised more than once for the advocates")

    rider_prompt, driver_prompt, _region = render_advocate_prompts(prompts_dir)
    judge_prompt = _read(prompts_dir / JUDGE_PROMPT_FILE)

    transcript = transcript_module.Transcript(now=now)
    # One budget for the whole case, started before the first call. Before this
    # existed the only bound was the client's per-attempt timeout, and the
    # product of that with the retries is what let a case hang for 1 h 48 m.
    deadline = CaseDeadline(
        case_no=case_no,
        started_at=clock(),
        limit_seconds=case_deadline_seconds,
        clock=clock,
    )

    rider_claims, rider_failure = _call_agent(
        client,
        role=transcript_module.ROLE_RIDER_ADVOCATE,
        system_prompt=rider_prompt,
        user_message=advocate_user_message,
        normalise=normalise_claims,
        transcript=transcript,
        deadline=deadline,
        events_log=events_log,
        case_no=case_no,
    )

    driver_claims = None
    driver_failure = None
    if rider_failure is None:
        # The run stops at the first failed agent. The judge cannot be called
        # without both claim arrays, so continuing would spend a call on a run
        # that has already failed, and would put a driver response on the record
        # that the judge never saw.
        driver_claims, driver_failure = _call_agent(
            client,
            role=transcript_module.ROLE_DRIVER_ADVOCATE,
            system_prompt=driver_prompt,
            user_message=advocate_user_message,
            normalise=normalise_claims,
            transcript=transcript,
            deadline=deadline,
            events_log=events_log,
            case_no=case_no,
        )

        # PROOF 1 — one brief, byte-identical. Both advocates were handed the
        # same bytes, and the digest of what each was actually given is on the
        # record, so the claim is checkable rather than asserted.
        if _user_digest(transcript, transcript_module.ROLE_RIDER_ADVOCATE) != _user_digest(
            transcript, transcript_module.ROLE_DRIVER_ADVOCATE
        ):
            raise BriefIdentityError("the two advocates were not handed the same brief bytes")

    failed_agent = None
    failure_reason = None
    if rider_failure is not None:
        failed_agent, failure_reason = transcript_module.ROLE_RIDER_ADVOCATE, rider_failure
    elif driver_failure is not None:
        failed_agent, failure_reason = transcript_module.ROLE_DRIVER_ADVOCATE, driver_failure

    ruling = None
    findings: List[Dict[str, Any]] = []
    referee_record: Dict[str, Any] = {}
    vote_record: Optional[Dict[str, Any]] = None
    verification_record: Optional[Dict[str, Any]] = None

    if failed_agent is None:
        referee_result = referee.referee(case_brief, rider_claims, driver_claims)
        referee_record = referee_result.as_dict()
        if events_log is not None:
            # One event per claim, in the order the referee checked them. The
            # ledger is the referee's own record and it travels on the result;
            # the event log is where the same decisions can be read in the
            # order they happened, beside the calls that produced the claims.
            for entry in referee_result.ledger:
                events_log.record(
                    events.EVENT_REFEREE_DECISION,
                    case_no=case_no,
                    side=entry.get("side"),
                    status=entry.get("status"),
                    reason_code=entry.get("reason_code"),
                    detail=entry.get("detail"),
                )

        if judge_votes == 1:
            # The single-draft path, unchanged: one call, one message, and the
            # object shape the judge has always been handed.
            judge_user = _checked_judge_message(
                referee_result.kept_claims[referee.SIDE_RIDER],
                referee_result.kept_claims[referee.SIDE_DRIVER],
                brief_json,
                referee_result,
                shape=JUDGE_CLAIMS_OBJECT,
                sides=DRIVER_FIRST,
            )
            judge_parsed, judge_failure = _call_agent(
                client,
                role=transcript_module.ROLE_JUDGE,
                system_prompt=judge_prompt,
                user_message=judge_user,
                normalise=normalise_judge_result,
                transcript=transcript,
                deadline=deadline,
                events_log=events_log,
                case_no=case_no,
            )
            if judge_failure is not None:
                failed_agent, failure_reason = transcript_module.ROLE_JUDGE, judge_failure
            else:
                ruling = _assemble_ruling(judge_parsed, referee_result)
                findings = validate_ruling_shape(ruling)
            if events_log is not None:
                events_log.record(
                    events.EVENT_JUDGE_DRAFT,
                    case_no=case_no,
                    draft=1,
                    kind=SINGLE_DRAFT,
                    seed=None,
                    temperature=None,
                    sides=list(DRIVER_FIRST),
                    proposal=proposal_from_key(vote_key(ruling)),
                    # The pre-vote code checks are a property of the vote. At
                    # K = 1 there is no panel for a malformed draft to abstain
                    # from and the ruling is recorded exactly as the judge gave
                    # it, so the checks are ``None`` -- which says they did not
                    # run, rather than reporting every one of them as passed.
                    checks=None,
                    abstention=judge_failure,
                    unverifiable=[],
                    valid=judge_failure is None,
                )
        else:
            vote = _run_judge_vote(
                client=client,
                judge_prompt=judge_prompt,
                referee_result=referee_result,
                brief_json=brief_json,
                transcript=transcript,
                deadline=deadline,
                votes=judge_votes,
                events_log=events_log,
                case_no=case_no,
                verify=verify_drafts,
                verifier_prompt=verifier_prompt,
            )
            vote_record = vote.record
            if vote.failure_reason is not None:
                # Not one draft was usable, so there is no ruling and no
                # disagreement: the judge failed, which is the event this
                # pipeline has always reported as a failure.
                failed_agent, failure_reason = (
                    transcript_module.ROLE_JUDGE,
                    vote.failure_reason,
                )
            else:
                ruling = vote.ruling
                findings = list(vote.findings)

    if vote_record is not None:
        # Read back off the vote so the result and the transcript cannot say two
        # different things about what the verifier found.
        verification_record = vote_record.get("verification")

    if events_log is not None:
        # The final ruling, whatever became of it. A case whose judge failed
        # records the failure here as well as on the outcome, so a reader
        # following one case through the log sees where it stopped.
        inner = ruling.get("ruling") if isinstance(ruling, Mapping) else None
        events_log.record(
            events.EVENT_RULING,
            case_no=case_no,
            failed_agent=failed_agent,
            failure_reason=failure_reason,
            ruling=inner if isinstance(inner, Mapping) else None,
            findings=len(findings),
        )

    totals = transcript.totals()
    return PipelineResult(
        case_no=case_no,
        model=getattr(client, "_model", ""),
        ok=failed_agent is None,
        brief_sha256=brief_sha256,
        transcript=transcript,
        ruling=ruling,
        ruling_findings=findings,
        failed_agent=failed_agent,
        failure_reason=failure_reason,
        prompt_tokens=totals["prompt_tokens"],
        completion_tokens=totals["completion_tokens"],
        reasoning_tokens=totals["reasoning_tokens"],
        cached_tokens=totals["cached_tokens"],
        duration_seconds=totals["duration_seconds"],
        stance_differing_ranges=stance_ranges,
        referee=referee_record,
        judge_vote=vote_record,
        vote_agreement=None if vote_record is None else vote_record.get("agreement"),
        verification=verification_record,
    )


def _parse(text: str) -> Any:
    return json.loads(text, parse_float=Decimal)


def _judge_user_message(
    rider_claims: Any,
    driver_claims: Any,
    brief_json: str,
    referee_discards: Optional[Sequence[Mapping[str, Any]]] = None,
    referee_flags: Optional[Sequence[Mapping[str, Any]]] = None,
    *,
    shape: str = JUDGE_CLAIMS_OBJECT,
    sides: Sequence[str] = DRIVER_FIRST,
) -> str:
    """Build the judge input from kept claims and the referee audit.

    The brief is spliced in as the exact characters the advocates received,
    rather than re-serialised, so the identity is literal. The judge sees no
    mechanically discarded claim in ``claims``; it sees that claim only in the
    referee ledger. The result is itself canonical JSON, which the pipeline
    checks by parsing and re-serialising.

    ``shape`` says how the two sides travel. ``JUDGE_CLAIMS_OBJECT`` is the
    object keyed by role that every run before the vote produced, and it is what
    K = 1 still produces, byte for byte. ``JUDGE_CLAIMS_ARRAY`` is an ordered
    array of ``{"side": ..., "claims": [...]}`` entries in the order ``sides``
    gives, and it exists because canonical JSON sorts an object's keys: it sorts
    ``DRIVER_ADVOCATE`` before ``RIDER_ADVOCATE``, so a position swap written as
    an object would serialise straight back to the bytes it started from. In an
    array, order is content.
    """
    by_side = {
        transcript_module.ROLE_RIDER_ADVOCATE: rider_claims,
        transcript_module.ROLE_DRIVER_ADVOCATE: driver_claims,
    }
    if shape == JUDGE_CLAIMS_OBJECT:
        claims_json = money.dumps_canonical(by_side)
    elif shape == JUDGE_CLAIMS_ARRAY:
        claims_json = money.dumps_canonical(
            [
                {CLAIMS_SIDE_KEY: side, ADVOCATE_CLAIMS_KEY: by_side[side]}
                for side in sides
            ]
        )
    else:
        raise PipelineError(
            "the judge's claims value has no shape called {0!r}".format(shape)
        )
    referee_json = money.dumps_canonical(
        {
            "ledger": list(referee_discards or []),
            "flags": list(referee_flags or []),
        }
    )
    return (
        '{"brief":' + brief_json + ',"claims":' + claims_json
        + ',"referee":' + referee_json + "}"
    )


# --------------------------------------------------------------------------
# Replaying the advocates
# --------------------------------------------------------------------------
# One sentence, stated once, for every place the record has to say that the
# advocates were not called by the run reporting the result. It says both halves
# -- what was not done, and what that costs the figure -- because a reader who
# learns only the first will read the accuracy as a whole-pipeline number.
REPLAY_NOTE = (
    "the advocates' outputs were replayed from an earlier run and not "
    "regenerated by this one: only the judge was called, so the figures here "
    "measure the judge's behaviour on fixed inputs and not the whole pipeline"
)


@dataclass(frozen=True)
class ReplaySource:
    """One earlier run's advocate outputs for one case, as they are on disk.

    ``entries`` is every recorded entry for the case, in order: both roles, and
    both attempts where a role's first answer was unusable. They are held as the
    recorded mappings rather than as rebuilt objects so that what is verified is
    exactly what the file contains -- a round trip through this package's own
    dataclass would accept a record this file does not actually hold.

    ``recorded_transcript_sha256`` is what the source run wrote beside the
    result, and it is compared with ``transcript_sha256``, the digest of the
    file as it stands now. The second is computed rather than assumed, so a
    transcript edited since it was written is refused rather than replayed.
    """

    run_dir: str
    git_commit: Optional[str] = None
    model: Optional[str] = None
    brief_sha256: Optional[str] = None
    transcript_sha256: Optional[str] = None
    recorded_transcript_sha256: Optional[str] = None
    entries: Tuple[Mapping[str, Any], ...] = ()

    def for_role(self, role: str) -> Tuple[Mapping[str, Any], ...]:
        """Every recorded entry for one role, in the order it was recorded."""
        return tuple(entry for entry in self.entries if entry.get("role") == role)


@dataclass(frozen=True)
class ReplayProvenance:
    """What a replayed case reused, and what the run that made it was billed.

    ``prompt_tokens`` and its companions are the borrowed calls' own usage,
    which this run did not pay. They are carried so the record can say what the
    advocates cost, and kept apart from the result's own figures so that nothing
    adds them to a bill this invocation never received.
    """

    run_dir: str
    git_commit: Optional[str]
    transcript_sha256: Optional[str]
    brief_sha256: str
    model: str
    advocate_calls: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0

    @property
    def billed(self) -> int:
        """What the borrowed calls cost, in the provider's own terms."""
        return self.prompt_tokens + self.completion_tokens

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_dir": self.run_dir,
            "git_commit": self.git_commit,
            "transcript_sha256": self.transcript_sha256,
            "brief_sha256": self.brief_sha256,
            "model": self.model,
            "advocate_calls": self.advocate_calls,
            "note": REPLAY_NOTE,
            "tokens": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "reasoning_tokens": self.reasoning_tokens,
                "cached_tokens": self.cached_tokens,
                "total_tokens": self.billed,
            },
        }


@dataclass(frozen=True)
class Replayable:
    """A recorded case accepted for replay, with everything the judge needs.

    Returned by :func:`replay_verdict` only when every acceptance condition
    holds, so a caller holding one has already established that the brief, both
    advocate prompts, the model and both recorded answers agree with this code.

    The judge's message is built from ``brief_json`` and the two claim arrays by
    the same :func:`_judge_user_message` a full run uses, so the two paths
    cannot hand the judge different bytes.
    """

    case_no: int
    brief_json: str
    brief_sha256: str
    rider_prompt: str
    driver_prompt: str
    judge_prompt: str
    rider_claims: Any
    driver_claims: Any
    rider_entries: Tuple[Mapping[str, Any], ...]
    driver_entries: Tuple[Mapping[str, Any], ...]
    stance_differing_ranges: Tuple[Tuple[int, int], ...]
    source: ReplaySource
    note: str


def replay_note(run_dir: str, git_commit: Optional[str]) -> str:
    """What a copied entry says in place of its own note."""
    return "replayed from {0} at {1}; this run did not call this agent".format(
        run_dir, (git_commit or "an unrecorded commit")[:12]
    )


def replay_verdict(
    case: Mapping[str, Any],
    source: ReplaySource,
    *,
    model: str,
    prompts_dir: Path = PROMPTS_DIR,
) -> Tuple[Optional[Replayable], str]:
    """Whether one case's advocates can be replayed, and when not, why not.

    Returns ``(replayable, "")`` when every condition holds, and ``(None,
    reason)`` otherwise. Every reason names the condition and both values, so a
    refusal can be acted on without re-deriving it, and a caller can ask this
    question before it writes anything or makes any call.

    The conditions, in the order they are cheapest to answer: the source run
    holds a transcript for this case and it still hashes to what that run
    recorded for it; the brief this code builds is the brief that run handed its
    agents; each advocate's system prompt as rendered now is the one that run
    recorded for that role; the recorded calls were made on the model this run
    would use; and both recorded answers parsed.

    "The run did not record it" is a refusal and never an assumption. A run that
    kept no prompt digest cannot be shown to have given its agents the prompt
    this code renders, and a replay that assumed it had would be manufacturing
    the very fact the check exists to establish.
    """
    case_no = case["case_no"]
    prompts_dir = Path(prompts_dir)

    # The project's second structural claim, checked here for the reason a full
    # run checks it: a replay is about to rely on the rendered prompts being the
    # ones that produced the recorded answers, so it is the wrong moment to take
    # them on trust.
    stance_ranges = tuple(check_stance_only_difference(prompts_dir))

    case_brief = brief.build_brief_for_case(case)
    brief_json = money.dumps_canonical(case_brief)
    brief_sha256 = hashlib.sha256(brief_json.encode("utf-8")).hexdigest()

    if not source.entries:
        return None, (
            "the source run holds no transcript for case {0}, so there are no "
            "advocate outputs to replay".format(case_no)
        )

    if source.recorded_transcript_sha256 and (
        source.recorded_transcript_sha256 != source.transcript_sha256
    ):
        return None, (
            "the source transcript for case {0} does not hash to what that run "
            "recorded for it (recorded {1}, found {2}), so it has changed since "
            "and these are not the entries that run produced".format(
                case_no,
                str(source.recorded_transcript_sha256)[:16],
                str(source.transcript_sha256)[:16],
            )
        )

    if source.brief_sha256 != brief_sha256:
        return None, (
            "the brief this code builds for case {0} is not the brief that run "
            "handed its agents (recorded {1}, built {2}), so its advocate outputs "
            "answer a different question".format(
                case_no,
                str(source.brief_sha256 or "nothing")[:16],
                brief_sha256[:16],
            )
        )

    rider_prompt, driver_prompt, _region = render_advocate_prompts(prompts_dir)
    judge_prompt = _read(prompts_dir / JUDGE_PROMPT_FILE)

    accepted: Dict[str, Tuple[Tuple[Mapping[str, Any], ...], Any]] = {}
    for role, rendered in (
        (transcript_module.ROLE_RIDER_ADVOCATE, rider_prompt),
        (transcript_module.ROLE_DRIVER_ADVOCATE, driver_prompt),
    ):
        entries = source.for_role(role)
        if not entries:
            return None, (
                "the source run recorded no {0} call for case {1}, so half of the "
                "judge's input does not exist".format(role, case_no)
            )
        rendered_sha = transcript_module.sha256_text(rendered)
        for entry in entries:
            recorded_system = entry.get("system_sha256")
            if not isinstance(recorded_system, str) or not recorded_system:
                return None, (
                    "that run recorded no system prompt digest for {0} on case {1}, "
                    "so it cannot be shown that the prompt rendered now is the one "
                    "the agent was given".format(role, case_no)
                )
            if recorded_system != rendered_sha:
                return None, (
                    "the {0} system prompt as rendered now is not the one that run "
                    "recorded for case {1} (recorded {2}, rendered {3}), so the "
                    "recorded claims answer a different instruction".format(
                        role, case_no, recorded_system[:16], rendered_sha[:16]
                    )
                )
            recorded_user = entry.get("user_sha256")
            if recorded_user != brief_sha256:
                return None, (
                    "the recorded {0} call on case {1} was not handed the brief "
                    "this code builds (recorded {2}, built {3})".format(
                        role,
                        case_no,
                        str(recorded_user or "nothing")[:16],
                        brief_sha256[:16],
                    )
                )
            recorded_model = entry.get("model")
            if recorded_model != model:
                return None, (
                    "the recorded {0} call on case {1} was made on {2} and this run "
                    "would use {3}, so the two are not the same measurement".format(
                        role, case_no, recorded_model or "an unrecorded model", model
                    )
                )
        # The answer that was used is the last one that parsed; an earlier
        # malformed attempt is part of the record and is replayed with it.
        claims, _shape, reason = normalise_claims(entries[-1].get("parsed"))
        if claims is None:
            return None, (
                "the recorded {0} answer on case {1} did not parse, so there is no "
                "claim array to hand the judge: {2}".format(role, case_no, reason)
            )
        accepted[role] = (entries, claims)

    rider_entries, rider_claims = accepted[transcript_module.ROLE_RIDER_ADVOCATE]
    driver_entries, driver_claims = accepted[transcript_module.ROLE_DRIVER_ADVOCATE]

    return (
        Replayable(
            case_no=case_no,
            brief_json=brief_json,
            brief_sha256=brief_sha256,
            rider_prompt=rider_prompt,
            driver_prompt=driver_prompt,
            judge_prompt=judge_prompt,
            rider_claims=rider_claims,
            driver_claims=driver_claims,
            rider_entries=rider_entries,
            driver_entries=driver_entries,
            stance_differing_ranges=stance_ranges,
            source=source,
            note=replay_note(source.run_dir, source.git_commit),
        ),
        "",
    )


def replay_case(
    client: Any,
    *,
    replay: Replayable,
    now: Optional[Callable[[], str]] = None,
    case_deadline_seconds: float = DEFAULT_CASE_DEADLINE_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    judge_votes: int = DEFAULT_JUDGE_VOTES,
    events_log: Optional[Any] = None,
    prompts_dir: Path = PROMPTS_DIR,
    verify_drafts: bool = False,
) -> PipelineResult:
    """Arbitrate one case from a recorded run's advocates, calling only the judge.

    The advocates are not called. Their recorded entries are copied into this
    run's transcript verbatim -- every field, the timestamp and the usage
    figures included, because they record calls that really happened -- with the
    note replaced by one that says this run did not make them.

    Everything from the judge onward is the code path a full arbitration takes:
    the message is built by the same :func:`_judge_user_message` and proved by
    the same :func:`_checked_judge_message`, the same single retry and the same
    deadline guard apply, and the ruling is normalised and validated by the same
    functions. What differs is only which agents were asked.

    ``judge_votes`` is the parameter :func:`run_loaded_case` takes, and it means
    the same thing here: only the judge side changes, so a replay votes exactly
    as a full run would. Every draft is a call this run makes, so every draft is
    on this run's bill -- and a case whose judge never produced a usable draft
    still had its advocates replayed, which is why the borrowed totals are
    filled in for both branches.

    The token figures on the result are this run's bill, which is the judge's
    alone. The borrowed calls' usage is reported separately on
    :class:`ReplayProvenance`, because a run that reported the sum would claim
    to have spent tokens it never spent.
    """
    if judge_votes < 1:
        raise PipelineError("judge_votes must be at least 1, got {0}".format(judge_votes))
    if verify_drafts and judge_votes < 2:
        raise PipelineError(
            "verify_drafts needs a judge vote of at least 2, got {0}: the verifier "
            "is asked over a panel of drafts".format(judge_votes)
        )
    verifier_prompt = (
        _read(Path(prompts_dir) / VERIFIER_PROMPT_FILE) if verify_drafts else ""
    )

    transcript = transcript_module.Transcript(now=now)
    copied = [
        transcript.add_recorded(entry, note=replay.note)
        for entry in (*replay.rider_entries, *replay.driver_entries)
    ]

    # One budget for the case, and it starts before the judge is called. The
    # advocates cost this run no time, so the whole of the bound is available to
    # the calls that are actually made.
    deadline = CaseDeadline(
        case_no=replay.case_no,
        started_at=clock(),
        limit_seconds=case_deadline_seconds,
        clock=clock,
    )

    replay_brief = _parse(replay.brief_json)
    referee_result = referee.referee(
        replay_brief,
        replay.rider_claims,
        replay.driver_claims,
    )
    if events_log is not None:
        # The referee's decisions are recorded here exactly as a full run
        # records them, because a replay runs the same referee over the same
        # claims. The advocates' own calls are not recorded: they were not made
        # by this invocation, and the log says what this invocation did.
        for entry in referee_result.ledger:
            events_log.record(
                events.EVENT_REFEREE_DECISION,
                case_no=replay.case_no,
                side=entry.get("side"),
                status=entry.get("status"),
                reason_code=entry.get("reason_code"),
                detail=entry.get("detail"),
            )

    failed_agent = None
    failure_reason = None
    ruling = None
    findings: List[Dict[str, Any]] = []
    referee_record = referee_result.as_dict()
    vote_record: Optional[Dict[str, Any]] = None
    verification_record: Optional[Dict[str, Any]] = None

    if judge_votes == 1:
        judge_user = _checked_judge_message(
            referee_result.kept_claims[referee.SIDE_RIDER],
            referee_result.kept_claims[referee.SIDE_DRIVER],
            replay.brief_json,
            referee_result,
            shape=JUDGE_CLAIMS_OBJECT,
            sides=DRIVER_FIRST,
        )
        judge_parsed, judge_failure = _call_agent(
            client,
            role=transcript_module.ROLE_JUDGE,
            system_prompt=replay.judge_prompt,
            user_message=judge_user,
            normalise=normalise_judge_result,
            transcript=transcript,
            deadline=deadline,
            events_log=events_log,
            case_no=replay.case_no,
        )
        if judge_failure is not None:
            failed_agent, failure_reason = transcript_module.ROLE_JUDGE, judge_failure
        else:
            ruling = _assemble_ruling(judge_parsed, referee_result)
            findings = validate_ruling_shape(ruling)
        if events_log is not None:
            events_log.record(
                events.EVENT_JUDGE_DRAFT,
                case_no=replay.case_no,
                draft=1,
                kind=SINGLE_DRAFT,
                seed=None,
                temperature=None,
                sides=list(DRIVER_FIRST),
                proposal=proposal_from_key(vote_key(ruling)),
                # ``None`` for the same reason a full single-draft run records
                # ``None``: the pre-vote checks are a property of the vote.
                checks=None,
                abstention=judge_failure,
                unverifiable=[],
                valid=judge_failure is None,
            )
    else:
        vote = _run_judge_vote(
            client=client,
            judge_prompt=replay.judge_prompt,
            referee_result=referee_result,
            brief_json=replay.brief_json,
            transcript=transcript,
            deadline=deadline,
            votes=judge_votes,
            events_log=events_log,
            case_no=replay.case_no,
            verify=verify_drafts,
            verifier_prompt=verifier_prompt,
        )
        vote_record = vote.record
        if vote.failure_reason is not None:
            failed_agent, failure_reason = transcript_module.ROLE_JUDGE, vote.failure_reason
        else:
            ruling = vote.ruling
            findings = list(vote.findings)

    if vote_record is not None:
        verification_record = vote_record.get("verification")

    if events_log is not None:
        inner = ruling.get("ruling") if isinstance(ruling, Mapping) else None
        events_log.record(
            events.EVENT_RULING,
            case_no=replay.case_no,
            failed_agent=failed_agent,
            failure_reason=failure_reason,
            ruling=inner if isinstance(inner, Mapping) else None,
            findings=len(findings),
        )

    # Two sums, and they are never added. The identity comparison is what keeps
    # a copied entry out of this run's bill: equality would be enough for these
    # values, but a judge entry that happened to match a copied one would then
    # be charged to the source run.
    billed = [
        entry
        for entry in transcript.entries
        if all(entry is not borrowed for borrowed in copied)
    ]
    totals = transcript.totals(billed)
    borrowed_totals = transcript.totals(copied)
    model = getattr(client, "_model", "")

    return PipelineResult(
        case_no=replay.case_no,
        model=model,
        ok=failed_agent is None,
        brief_sha256=replay.brief_sha256,
        transcript=transcript,
        ruling=ruling,
        ruling_findings=findings,
        failed_agent=failed_agent,
        failure_reason=failure_reason,
        prompt_tokens=totals["prompt_tokens"],
        completion_tokens=totals["completion_tokens"],
        reasoning_tokens=totals["reasoning_tokens"],
        cached_tokens=totals["cached_tokens"],
        duration_seconds=totals["duration_seconds"],
        stance_differing_ranges=list(replay.stance_differing_ranges),
        referee=referee_record,
        judge_vote=vote_record,
        vote_agreement=None if vote_record is None else vote_record.get("agreement"),
        verification=verification_record,
        replay=ReplayProvenance(
            run_dir=replay.source.run_dir,
            git_commit=replay.source.git_commit,
            transcript_sha256=replay.source.transcript_sha256,
            brief_sha256=replay.brief_sha256,
            model=model,
            advocate_calls=len(copied),
            prompt_tokens=borrowed_totals["prompt_tokens"],
            completion_tokens=borrowed_totals["completion_tokens"],
            reasoning_tokens=borrowed_totals["reasoning_tokens"],
            cached_tokens=borrowed_totals["cached_tokens"],
        ),
    )


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def _format_seconds(value: float) -> str:
    return "{0:.1f}s".format(value)


def _print_result(result: PipelineResult, out_path: Optional[str]) -> None:
    """A summary a person can read during a demo."""
    print("case {0}  model {1}".format(result.case_no, result.model))
    print("brief sha256   {0}".format(result.brief_sha256))
    print("stance ranges  {0}".format(result.stance_differing_ranges))
    print("")

    for entry in result.transcript.entries:
        marker = "ok " if entry.note is None else "retry"
        print(
            "  {0} {1:<16} {2:>3} {3:>6} in {4:>6} out {5:>6} reason {6:>6} cached {7}".format(
                marker,
                entry.role,
                entry.status,
                entry.prompt_tokens,
                entry.completion_tokens,
                entry.reasoning_tokens,
                entry.cached_tokens,
                _format_seconds(entry.duration_seconds),
            )
        )

    totals = result.transcript.totals()
    print("")
    print(
        "totals         {0} calls, {1} in, {2} out, {3} reasoning, {4} cached, {5}".format(
            totals["calls"],
            totals["prompt_tokens"],
            totals["completion_tokens"],
            totals["reasoning_tokens"],
            totals["cached_tokens"],
            _format_seconds(totals["duration_seconds"]),
        )
    )
    print("transcript sha256 {0}".format(result.transcript_sha256))
    print("")

    if not result.ok:
        print("RUN FAILED: {0} — {1}".format(result.failed_agent, result.failure_reason))
    elif result.ruling is None:
        print("RUN INCOMPLETE: no ruling was produced")
    else:
        inner = result.ruling.get("ruling", {})
        print("ruling         {0}".format(inner.get("ruling")))
        print("amount_sgd     {0}".format(inner.get("amount_sgd")))
        print("driver_comp     {0}".format(inner.get("driver_compensation_sgd")))
        print("referrals      {0}".format(inner.get("referrals")))
        print("confidence     {0}".format(inner.get("confidence")))
        print("")
        print("explanation")
        for line in str(inner.get("explanation", "")).splitlines() or [""]:
            print("  " + line)
        print("")
        print("discarded claims {0}".format(len(result.ruling.get("discarded_claims", []) or [])))
        if result.ruling_findings:
            print("")
            print("CONTRACT FINDINGS (recorded, not corrected)")
            for finding in result.ruling_findings:
                print("  - {0}: {1}".format(finding["invariant"], finding["detail"]))

    if result.judge_vote:
        vote = result.judge_vote
        agreed = sum(1 for draft in vote["drafts"] if draft.get("agrees"))
        print("")
        print(
            "judge vote     {0} of {1} drafts agreed, {2} needed, {3}{4}".format(
                agreed,
                vote["votes"],
                vote["threshold"],
                vote["outcome"],
                " (unanimous)" if vote["unanimous"] else "",
            )
        )
        for draft in vote["drafts"]:
            if not draft["valid"]:
                verdict = "abstained"
            elif draft["agrees"]:
                verdict = "agrees"
            else:
                verdict = "differs"
            print(
                "  draft {0} {1:<16} temp {2} seed {3} {4}".format(
                    draft["draft"],
                    draft["kind"],
                    draft["temperature"],
                    draft["seed"],
                    verdict,
                )
            )
        print("vote agreement {0}".format(result.vote_agreement))

    if out_path:
        Path(out_path).write_text(result.transcript_json, encoding="utf-8")
        print("")
        print("transcript written to {0}".format(out_path))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tribunal.pipeline",
        description="Run one Tribunal arbitration and print the ruling and a per-call summary.",
    )
    parser.add_argument("--case", type=int, required=True, help="the case number, e.g. 208")
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "the model id; when omitted the runtime model recorded in "
            "tribunal/model.py is used, and naming one here overrides it"
        ),
    )
    parser.add_argument("--out", help="write the full transcript JSON to this path")
    parser.add_argument(
        "--verify-drafts",
        action="store_true",
        help=(
            "after the drafts pass the code checks, ask a verifier once per case "
            "whether the brief supports each factual statement a draft states; a "
            "draft with a contradicted statement abstains. Off by default, and it "
            "needs --judge-votes of at least 2"
        ),
    )
    parser.add_argument(
        "--prompts-dir", default=str(PROMPTS_DIR), help="the prompt directory to use"
    )
    parser.add_argument(
        "--judge-votes",
        type=int,
        default=DEFAULT_JUDGE_VOTES,
        help=(
            "how many times to ask the judge on the same inputs; the majority "
            "decides, and 1 is the single-draft behaviour (default {0})".format(
                DEFAULT_JUDGE_VOTES
            )
        ),
    )
    args = parser.parse_args(argv)

    client = llm.LLMClient(model=resolve_model(args.model))
    result = run_case(
        args.case,
        client,
        prompts_dir=Path(args.prompts_dir),
        judge_votes=args.judge_votes,
        verify_drafts=args.verify_drafts,
    )
    _print_result(result, args.out)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
