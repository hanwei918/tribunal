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
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import brief, llm, loader, money, transcript as transcript_module
from .model import resolve_model

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "v1"

ADVOCATE_TEMPLATE = "advocate.system.md"
STANCE_FILES = {
    transcript_module.ROLE_RIDER_ADVOCATE: "stance.rider.md",
    transcript_module.ROLE_DRIVER_ADVOCATE: "stance.driver.md",
}
JUDGE_PROMPT_FILE = "judge.system.md"
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
}
AGENT_PROMPT_FILES: Dict[str, str] = {
    transcript_module.ROLE_RIDER_ADVOCATE: ADVOCATE_TEMPLATE,
    transcript_module.ROLE_DRIVER_ADVOCATE: ADVOCATE_TEMPLATE,
    transcript_module.ROLE_JUDGE: JUDGE_PROMPT_FILE,
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

    @property
    def transcript_json(self) -> str:
        return self.transcript.to_json()

    @property
    def transcript_sha256(self) -> str:
        return self.transcript.sha256()


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

    Returns ``(value, None)`` on success and ``(None, reason)`` when the second
    attempt is unusable too. A spent deadline is not an unusable answer, so it
    raises :class:`CaseDeadlineExceeded` instead of returning a reason.
    """
    reason = ""
    for _attempt in (1, 2):
        if deadline is not None:
            deadline.check()
        result = client.complete(system_prompt, user_message, response_format=JSON_OBJECT_FORMAT)
        value, shape, reason = normalise(result.json_body)
        transcript.record(
            role=role,
            system_prompt=system_prompt,
            user_message=user_message,
            result=result,
            note=None if value is not None else UNUSABLE_RESPONSE_NOTE,
            shape=shape,
        )
        if value is not None:
            return value, None
    return None, reason


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
) -> PipelineResult:
    """Perform one full arbitration and return the ruling with the transcript.

    ``case_deadline_seconds`` bounds the whole case -- all three agent calls and
    any shape retry -- where ``LLMClient``'s own deadline bounds one call. The
    budget is checked before each call and a case that has spent it raises
    :class:`CaseDeadlineExceeded`, which carries the elapsed seconds. The runner
    turns that into a failed case and moves on to the next one, so a hung case
    costs its own budget rather than the run.

    ``clock`` is injectable so the deadline can be exercised without waiting.
    """
    prompts_dir = Path(prompts_dir)

    # The project's second structural claim, checked before any call is made.
    stance_ranges = check_stance_only_difference(prompts_dir)

    # ONE serialisation of the brief, and one digest of those exact bytes.
    case_brief = brief.build_brief(case_no)
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

    if failed_agent is None:
        judge_user = _judge_user_message(rider_claims, driver_claims, brief_json)

        # The judge's message must embed those same brief bytes, and be canonical.
        parsed_judge_user = _parse(judge_user)
        if money.dumps_canonical(parsed_judge_user["brief"]) != brief_json:
            raise BriefIdentityError("the judge was not handed the same brief bytes")
        if money.dumps_canonical(parsed_judge_user) != judge_user:
            raise BriefIdentityError("the judge's user message is not canonical JSON")

        judge_parsed, judge_failure = _call_agent(
            client,
            role=transcript_module.ROLE_JUDGE,
            system_prompt=judge_prompt,
            user_message=judge_user,
            normalise=normalise_judge_result,
            transcript=transcript,
            deadline=deadline,
        )
        if judge_failure is not None:
            failed_agent, failure_reason = transcript_module.ROLE_JUDGE, judge_failure
        else:
            ruling = normalise_ruling(judge_parsed)
            findings = validate_ruling_shape(ruling)

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
    )


def _parse(text: str) -> Any:
    return json.loads(text, parse_float=Decimal)


def _judge_user_message(rider_claims: Any, driver_claims: Any, brief_json: str) -> str:
    """The judge's user message: the same brief bytes plus both claim arrays.

    The brief is spliced in as the exact characters the advocates received,
    rather than re-serialised, so the identity is literal. The result is itself
    canonical JSON, which ``run_case`` checks by parsing and re-serialising.
    """
    claims_json = money.dumps_canonical(
        {
            transcript_module.ROLE_RIDER_ADVOCATE: rider_claims,
            transcript_module.ROLE_DRIVER_ADVOCATE: driver_claims,
        }
    )
    return '{"brief":' + brief_json + ',"claims":' + claims_json + "}"


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
        "--prompts-dir", default=str(PROMPTS_DIR), help="the prompt directory to use"
    )
    args = parser.parse_args(argv)

    client = llm.LLMClient(model=resolve_model(args.model))
    result = run_case(args.case, client, prompts_dir=Path(args.prompts_dir))
    _print_result(result, args.out)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
