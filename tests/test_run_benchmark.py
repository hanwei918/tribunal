"""Tests for ``eval/run_benchmark.py``.

No network, no credential, no model call. The pipeline is driven end to end —
the real :func:`tribunal.pipeline.run_case`, the real :class:`tribunal.llm.LLMClient`,
the real rate limiter, real files on disk — over an injected transport that
answers out of a script and records every request body it was handed. Nothing
here reaches TokenHub, and no benchmark is executed: the runner is exercised on
three to five cases, not on the corpus.

Why the rig is checked before the runner
----------------------------------------
A test rig that could not tell the judge from an advocate would make every
assertion below meaningless, and a rig that answered a case it was never
scripted for would hide a runner that ran the wrong set.
:class:`TransportShapeTests` therefore checks the rig first.

What is covered
---------------
* a clean run of three cases: every case completes, every case matches, the
  cache and the transcripts are written, and the metadata accounts for the
  tokens;
* resumption: a second invocation makes no call at all, ``--force`` redoes the
  work, and a cache entry that is present but unusable is re-run rather than
  trusted;
* failure: a case that fails after the client's retries is recorded, the run
  **continues**, nothing is cached for it, and a re-run retries exactly that
  case and no other;
* the token budget: it stops new work, lets the work already in flight finish,
  and says on its face that it stopped on budget rather than completing;
* provenance: the commit, the tri-state clean-tree flag, the prompts digest and
  the answer key's digest, with ``unknown`` never reading as ``clean``;
* concurrency: ``--concurrency`` defaults to 1, and N threads calling together
  still do not exceed the configured rate — with the same workload shown to go
  RED against an unguarded limiter, because a guard nobody has seen fail is not
  evidence of anything;
* ``--compare``: two cached runs tabulated off disk, making no model call;
* staleness: a cached result whose brief this code still builds reports current,
  one whose brief has changed reports stale **and is named**, a brief that
  cannot be rebuilt is unknown rather than current, and so is a result whose
  recorded calls cannot say which prompts they were given: the prompt channel
  compares, per role, the digests those calls carry against what this code
  renders now, so a prompt no recorded call used is not a finding about any case
  while a one-byte change to one a call did use is, and a grading over a mixed
  set says on its face that its exact-match figure is not one measurement —
  with the digest shown to be the one the pipeline itself recorded, so the
  check cannot be satisfied by comparing against a constant;
* per-case provenance: every cache entry carries the commit, the prompts digest
  and the interpreter it was produced under, beside the brief digest it already
  kept -- the interpreter because that digest was once a function of it;
* the run record: a second invocation over a different case set leaves the
  first invocation's own record — its case list and its token total — intact in
  ``invocations.json``, while ``run.json`` describes only the invocation that
  wrote it and its directory block says what the directory actually holds;
* the cost record: every invocation writes its prompt and completion tokens
  separately rather than as a single total, because output is priced at four
  times input and a total cannot be turned into a price; reasoning is inside the
  completion rather than added to it; a case that failed after its calls were
  made counts towards what the invocation consumed and not towards what the
  budget bought; and the window it ran in is carried into the history as well as
  into ``run.json``, so which price band applied is still recoverable after the
  next invocation has overwritten that file;
* isolation: a completed run's cached artifacts and transcripts carry no
  answer-key field name, scanned with the same needles
  ``tests/test_answer_isolation.py`` uses — and that scan is shown to be capable
  of firing.

Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import grade  # noqa: E402
from eval import run_benchmark as runner  # noqa: E402
from tests import portability  # noqa: E402
from tests import test_answer_isolation as isolation  # noqa: E402
from tribunal import events, llm, money, pipeline, transcript  # noqa: E402
from tribunal.model import RUNTIME_MODEL  # noqa: E402

PROMPTS_DIR = PROJECT_ROOT / "prompts" / "v1"

# A key that is unmistakable if it ever turns up where it should not.
FAKE_KEY = "tok-live-FAKEKEY-0123456789abcdef-DO-NOT-LEAK"

MODEL = "hy4-preview"
OTHER_MODEL = "deepseek/deepseek-flash"

# The clean-run set. All three carry no referral and none escalates, so a
# perturbation of one money field cannot disturb the escalation block.
CASE_SET = (101, 102, 103)

# A set with a referral and two escalations, for the calibration block.
WIDER_SET = (101, 105, 110, 207)

# Per call, and three calls per case: the two advocates and the judge.
PROMPT_TOKENS = 120
COMPLETION_TOKENS = 30
REASONING_TOKENS = 8
TOKENS_PER_CALL = PROMPT_TOKENS + COMPLETION_TOKENS
CALLS_PER_CASE = 3
TOKENS_PER_CASE = TOKENS_PER_CALL * CALLS_PER_CASE

# A bare claim array, which is all the pipeline's advocate validator asks for.
CLAIM_ARRAY = '[{"claim_id": "C1", "evidence_id": "EV-GPS-00101", "clause_id": "POL-RD-01"}]'

# What the rig's verifier says it rested every verdict on. The verifier is a
# fourth call when the switch is on, and this rig answers it so a case can reach
# the vote with the verifier on and its call appear in ``calls.json``.
VERIFIER_EVIDENCE = "the brief states it"

COMMIT = "0b20a66deadbeefcafe0123456789abcdef01234"
DIRTY_STATUS = " M eval/run_benchmark.py\n?? tests/test_run_benchmark.py"

# Read once: the advocate system prompts are the rendered template with one of
# these substituted, so each is a substring of exactly one of the two.
RIDER_STANCE = (PROMPTS_DIR / "stance.rider.md").read_text(encoding="utf-8").rstrip("\n")
DRIVER_STANCE = (PROMPTS_DIR / "stance.driver.md").read_text(encoding="utf-8").rstrip("\n")


# --------------------------------------------------------------------------
# The rig
# --------------------------------------------------------------------------
class VirtualClock:
    """A clock that only moves when something sleeps.

    The runner's fake client is used from several threads, so the clock keeps
    its own lock. It is a different lock from the rate limiter's on purpose:
    the limiter's lock is the thing under test, and a clock that quietly
    serialised the callers itself would make the test pass for the wrong
    reason.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.now = 0.0
        self.sleeps: list = []

    def clock(self) -> float:
        with self._lock:
            return self.now

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.sleeps.append(seconds)
            self.now += seconds


def role_of(request):
    """``(case_no, role)`` for one recorded request body.

    The role is read off the request rather than counted, because the pipeline
    retries an unusable answer once and a call counter would misalign after the
    first retry. The judge's user message is the one whose keys are exactly
    ``brief`` and ``claims``; the verifier's is the one whose keys are ``brief``
    and ``statements``; the advocates are handed the brief itself.
    """
    system = request["messages"][0]["content"]
    parsed = json.loads(request["messages"][1]["content"])

    if isinstance(parsed, dict) and "brief" in parsed and "claims" in parsed:
        return parsed["brief"]["case"]["case_no"], transcript.ROLE_JUDGE
    if isinstance(parsed, dict) and "brief" in parsed and "statements" in parsed:
        return parsed["brief"]["case"]["case_no"], transcript.ROLE_VERIFIER

    case_no = parsed["case"]["case_no"]
    if RIDER_STANCE in system:
        return case_no, transcript.ROLE_RIDER_ADVOCATE
    if DRIVER_STANCE in system:
        return case_no, transcript.ROLE_DRIVER_ADVOCATE
    raise AssertionError(
        "a request is neither an advocate's, the judge's nor the verifier's"
    )


class ScriptedTransport:
    """A transport that answers by role, and records every request it received.

    ``fail`` names ``(case_no, role)`` pairs to answer with an error status, so
    a case can be made to fail at the judge — after both advocates succeeded —
    rather than at the first call. ``mutate`` changes the ruling a judge
    response carries, which is how a miss is produced without touching the key.
    """

    def __init__(
        self,
        produced,
        *,
        prompt_tokens: int = PROMPT_TOKENS,
        completion_tokens: int = COMPLETION_TOKENS,
        reasoning_tokens: int = REASONING_TOKENS,
        fail=(),
        fail_status: int = 500,
        mutate=None,
    ) -> None:
        self.produced = produced
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.reasoning_tokens = reasoning_tokens
        self.fail = set(fail)
        self.fail_status = fail_status
        self.mutate = mutate
        self.requests = []
        self.roles = []
        # The position each request was made at, read off the pipeline's own
        # context as the request goes out. A body does not carry the role, the
        # draft or the attempt, so this is the only place a test can learn them.
        self.contexts = []
        self._lock = threading.Lock()

    def __call__(self, url, headers, body, timeout):
        request = json.loads(body.decode("utf-8"))
        case_no, role = role_of(request)
        with self._lock:
            self.requests.append(request)
            self.roles.append((case_no, role))
            self.contexts.append(pipeline.CALL_CONTEXT.get())

        if (case_no, role) in self.fail:
            return llm.HttpResult(status=self.fail_status, body=b'{"error": "scripted failure"}')

        if role == transcript.ROLE_JUDGE:
            ruling = dict(self.produced[case_no]["ruling"])
            if self.mutate is not None:
                ruling = self.mutate(case_no, ruling)
            content = money.dumps_canonical({"ruling": ruling, "discarded_claims": []})
        elif role == transcript.ROLE_VERIFIER:
            # Every statement supported, so the switch adds the verifier's call
            # and changes no draft's vote.
            statements = json.loads(request["messages"][1]["content"])["statements"]
            content = json.dumps(
                {
                    "verdicts": [
                        {
                            "statement": item["n"],
                            "verdict": pipeline.VERDICT_SUPPORTED,
                            "evidence": VERIFIER_EVIDENCE,
                        }
                        for item in statements
                    ]
                }
            )
        else:
            content = CLAIM_ARRAY

        payload = {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "completion_tokens_details": {"reasoning_tokens": self.reasoning_tokens},
                "prompt_tokens_details": {"cached_tokens": 0},
            },
        }
        return llm.HttpResult(status=200, body=json.dumps(payload).encode("utf-8"))

    # -- what the run did -------------------------------------------------
    def cases_called(self):
        return sorted({case_no for case_no, _ in self.roles})

    def roles_for(self, case_no):
        return [role for number, role in self.roles if number == case_no]

    def calls(self) -> int:
        return len(self.requests)


class DelayingTransport(ScriptedTransport):
    """The scripted transport, with the answers coming back out of call order.

    Every request sleeps for a fixed slice that depends on what it is -- the
    rider longer than the driver, the first draft longer than the last -- so the
    answers finish in roughly the reverse of the order they were asked in. A
    ``calls.json`` written in completion order would then be in that reversed
    order, which is what makes an ordering test bite; one written in call order
    is not. The sleeps are real but short, and the client's own rate limiter
    sleeps on the virtual clock, so nothing here waits on a network.

    ``requests`` is still the order the transport *answered* in, which is what
    ``ScriptedTransport`` means by it. That is the order the sink sees, so a test
    can assert the answers did not come back in call order -- without which the
    ordering assertion below would be a test that cannot fail.
    """

    def __call__(self, url, headers, body, timeout):
        request = json.loads(body.decode("utf-8"))
        _case_no, role = role_of(request)
        if role == transcript.ROLE_RIDER_ADVOCATE:
            time.sleep(0.08)
        elif role == transcript.ROLE_JUDGE:
            # The last draft answers first, and the position-swapped draft --
            # the one whose seed is not a sampled one -- is the last position.
            time.sleep(0.08 - 0.02 * call_position(request)[2])
        return super().__call__(url, headers, body, timeout)


# The order the calls of one case are *made* in. The role names sort
# ``driver``, ``judge``, ``rider`` -- ASCII order puts the rider last when the
# case reads it first -- so a position is a rank and not a name.
CALL_RANK = {
    transcript.ROLE_RIDER_ADVOCATE: 0,
    transcript.ROLE_DRIVER_ADVOCATE: 1,
    transcript.ROLE_JUDGE: 2,
    transcript.ROLE_VERIFIER: 3,
}


def call_position(request, votes=4):
    """``(case, role rank, draft)`` for one recorded request body.

    The draft is read off the request rather than counted: a sampled draft
    carries its own seed, the position-swapped draft carries the client's
    defaults, and the verifier is one call per case rather than a draft. This is
    the position the runner sorts ``calls.json`` by, so a test can check the
    file against the calls instead of against the order they happened to arrive
    in.
    """
    case_no, role = role_of(request)
    if role != transcript.ROLE_JUDGE:
        return (case_no, CALL_RANK[role], 0)
    seed = request.get("seed")
    position = (
        pipeline.JUDGE_VOTE_SEEDS.index(seed) + 1
        if seed in pipeline.JUDGE_VOTE_SEEDS[: votes - 1]
        else votes
    )
    return (case_no, CALL_RANK[role], position)


def call_order(records, transport, positions):
    """The position of every record in ``calls.json``, in the file's own order.

    A record carries the digest of the body it was made from and nothing that
    names the call -- no role, no draft, no attempt -- so the records are paired
    with the arrivals **by digest and in order**: the n-th record carrying a
    digest is the n-th arrival that carried it. Each arrival's position was read
    off ``pipeline.CALL_CONTEXT`` by the transport, which is the only place the
    role, the draft and the attempt are visible, and the case is then mapped to
    its place in the **requested** list, which is the first element of the key
    the runner sorts by.
    """
    arrivals = {}
    for request, context in zip(transport.requests, transport.contexts):
        digest = hashlib.sha256(
            json.dumps(request, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        arrivals.setdefault(digest, []).append(context)
    order = []
    for record in records:
        case_no, role, draft, attempt = arrivals[record["request_sha256"]].pop(0)
        order.append((positions[case_no], CALL_RANK[role], draft, attempt))
    return order


def client_factory(model, transport, clock=None):
    """A real ``LLMClient`` over the scripted transport, with no real sleeping.

    ``max_attempts=1`` so a scripted failure is a failure rather than three
    more scripted failures; the retry-once behaviour under test belongs to the
    pipeline, not to the client's HTTP retry.
    """
    clock = VirtualClock() if clock is None else clock

    def build(sink):
        return llm.LLMClient(
            model=model,
            api_key=FAKE_KEY,
            transport=transport,
            record_sink=sink,
            max_attempts=1,
            clock=clock.clock,
            sleep=clock.sleep,
        )

    return build


def git_runner(commit: str = COMMIT, status: str = ""):
    """A stand-in for ``git`` that answers the two questions the runner asks."""

    def run(arguments):
        return commit if arguments[0] == "rev-parse" else status

    return run


def git_that_cannot_be_asked():
    """A stand-in for a machine where git is absent: the answer is ``None``."""
    return lambda arguments: None


def answer_key():
    return grade.load_answer_key()


def produced_from_key(key):
    return grade.key_as_produced(key)


def bench(
    tmp_path,
    *,
    cases=CASE_SET,
    model=MODEL,
    transport=None,
    key=None,
    runs_dir=None,
    git=None,
    **overrides,
):
    """One invocation of the runner over the scripted transport.

    Returns ``(summary, transport)`` so a test can ask both what the runner
    recorded and what it actually sent.
    """
    key = answer_key() if key is None else key
    if transport is None:
        transport = ScriptedTransport(produced_from_key(key))

    arguments = dict(
        runs_dir=Path(runs_dir) if runs_dir is not None else Path(tmp_path) / "runs",
        prompts_dir=PROMPTS_DIR,
        client_factory=client_factory(model, transport),
        key=key,
        git_runner=git_runner() if git is None else git,
        progress=lambda text: None,
        # One judge draft. The rig pins the single-draft configuration so that
        # every test in this file measures what it always measured -- one judge
        # call per case, and the role sequence, call counts and token totals that
        # follow from it. The vote has its own tests, which ask for it by name.
        judge_votes=1,
    )
    arguments.update(overrides)
    return runner.run_benchmark(model, cases, **arguments), transport


def run_dir_of(tmp_path, model=MODEL, name="runs"):
    return runner.run_directory(Path(tmp_path) / name, model)


# --------------------------------------------------------------------------
# The rig itself
# --------------------------------------------------------------------------
class TransportShapeTests(unittest.TestCase):
    """The rig can tell the three agents apart, and fails loudly when it cannot."""

    def test_the_three_roles_are_distinguished(self):
        key = answer_key()
        transport = ScriptedTransport(produced_from_key(key))
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp, cases=(101,), transport=transport)
        self.assertEqual(
            [
                transcript.ROLE_RIDER_ADVOCATE,
                transcript.ROLE_DRIVER_ADVOCATE,
                transcript.ROLE_JUDGE,
            ],
            transport.roles_for(101),
            "the three calls of a case are not the two advocates and the judge",
        )

    def test_a_request_that_is_neither_agent_is_refused(self):
        """A role the rig cannot identify is an error, not a guess."""
        request = {
            "messages": [
                {"role": "system", "content": "no stance block here"},
                {"role": "user", "content": '{"case": {"case_no": 101}}'},
            ]
        }
        with self.assertRaises(AssertionError):
            role_of(request)

    def test_the_rig_refuses_a_case_it_was_not_given(self):
        """A scripted transport that has no answer says so rather than inventing one.

        The refusal surfaces as a failed case rather than an exception, because a
        transport blowing up is exactly the shape of failure the runner is built
        to survive — which is why the case must not end up in the cache.
        """
        transport = ScriptedTransport({})
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=(101,), transport=transport)

            self.assertEqual(1, len(summary.failures))
            self.assertIn("KeyError", summary.failures[0].failure_reason or "")
            self.assertEqual([], runner.cached_case_numbers(summary.run_dir))

    def test_a_case_can_be_made_to_fail_at_the_judge(self):
        """The failure the tests need is a late one, after both advocates."""
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key), fail={(101, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=(101,), transport=transport)
        self.assertEqual(1, len(summary.failures))
        self.assertEqual(transcript.ROLE_JUDGE, summary.failures[0].failed_agent)


# --------------------------------------------------------------------------
# A clean run
# --------------------------------------------------------------------------
class CleanRunTests(unittest.TestCase):
    """Three cases, one model, every one of them a four-field match."""

    def test_every_case_completes_and_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, transport = bench(tmp)

            self.assertEqual(runner.STOP_COMPLETED, summary.stop_reason)
            self.assertTrue(summary.completed)
            self.assertTrue(summary.ok)
            self.assertEqual([], summary.failures)
            self.assertEqual(list(CASE_SET), summary.completed_cases)
            self.assertEqual([], summary.cached_cases)
            self.assertEqual(len(CASE_SET), summary.matched)

            self.assertEqual(CASE_SET, tuple(transport.cases_called()))
            self.assertEqual(len(CASE_SET) * CALLS_PER_CASE, transport.calls())

    def test_the_run_grades_itself_through_eval_grade(self):
        """The report is the grader's, not a second scoring path."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)

            self.assertIsNotNone(summary.report)
            self.assertEqual(len(CASE_SET), summary.report.total)
            self.assertEqual(len(CASE_SET), summary.report.exact_matches)
            for field in grade.GRADED_FIELDS:
                with self.subTest(field=field):
                    self.assertEqual((len(CASE_SET), len(CASE_SET)), summary.report.field_tally(field))

    def test_the_report_is_written_to_the_run_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            path = summary.run_dir / runner.REPORT_FILE
            self.assertTrue(path.is_file(), "no report was written")
            self.assertEqual(
                grade.render_report(
                    summary.report, "Benchmark report — {0}".format(MODEL)
                ),
                path.read_text(encoding="utf-8"),
            )

    def test_each_case_leaves_a_cache_entry_and_a_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)

            for case_no in CASE_SET:
                with self.subTest(case_no=case_no):
                    self.assertTrue(
                        runner.case_cache_path(summary.run_dir, case_no).is_file(),
                        "case {0} has no cache entry".format(case_no),
                    )
                    self.assertTrue(
                        runner.transcript_path(summary.run_dir, case_no).is_file(),
                        "case {0} has no transcript".format(case_no),
                    )
            self.assertEqual(list(CASE_SET), runner.cached_case_numbers(summary.run_dir))

    def test_the_cache_entry_carries_the_run_it_came_from(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            document = runner.load_cached(summary.run_dir, 101)

            self.assertEqual(runner.CACHE_SCHEMA_VERSION, document["schema_version"])
            self.assertEqual(101, document["case_no"])
            self.assertEqual(MODEL, document["model"])
            self.assertIsNotNone(document["brief_sha256"])
            self.assertIsNotNone(document["transcript_sha256"])
            self.assertTrue(document["matched"])
            self.assertEqual(
                sorted(
                    [
                        "brief_sha256",
                        "call_seconds",
                        "case_no",
                        # The run's own configuration: how many drafts the
                        # judge was asked for, whether the verifier ran, and
                        # the three switches, each at its default today.
                        "configuration",
                        # Which development set the result belongs to, or
                        # ``None`` for the corpus. Per case and not only in the
                        # run's metadata, because the metadata file describes
                        # the last invocation while this entry describes this
                        # result: a result read out of its directory has to be
                        # able to say which key it was graded against.
                        "development_set",
                        # Per-case provenance, beside the digest it belongs to.
                        # The commit, the prompts and the interpreter a result
                        # was produced under must survive in the result's own
                        # file: a run-level record is overwritten by the next
                        # invocation, so provenance that lives only there dies
                        # with it.
                        "git_commit",
                        "matched",
                        "model",
                        "prompts_sha256",
                        "python_version",
                        "recorded_at",
                        # Present only when another run's advocates were reused,
                        # and ``None`` otherwise. A reader has to be able to tell
                        # "this run called all three agents" from "this file does
                        # not say", which is exactly what an absent key leaves
                        # open.
                        "replay",
                        "referee",
                        "ruling",
                        "ruling_findings",
                        "schema_version",
                        "stance_differing_ranges",
                        "tokens",
                        "transcript_file",
                        "transcript_sha256",
                        # How many of the judge's drafts agreed on the ruling
                        # this entry carries, or ``None`` for a single-draft
                        # run. Its own field beside the ruling, never folded
                        # into the judge's own confidence.
                        "vote_agreement",
                        "wall_seconds",
                    ]
                ),
                sorted(document),
                "the cache entry's shape changed; a new field is a deliberate act",
            )
            self.assertEqual(COMMIT, document["git_commit"])
            self.assertEqual(runner.hash_directory(PROMPTS_DIR), document["prompts_sha256"])

    def test_the_cache_entry_is_the_only_place_the_ruling_lives(self):
        """One copy of the ruling per case, and it is the one the report used.

        The cached value is the judge's result object — the POL-GEN-03 object
        under a ``ruling`` key, beside the discarded claims — kept exactly as
        the pipeline produced it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            document = runner.load_cached(summary.run_dir, 101)
            expected = produced_from_key(answer_key())[101]["ruling"]

            self.assertEqual(expected["ruling"], document["ruling"]["ruling"]["ruling"])
            self.assertEqual(
                expected["amount_sgd"], document["ruling"]["ruling"]["amount_sgd"]
            )
            self.assertEqual([], document["ruling"]["discarded_claims"])

    def test_the_contract_findings_are_kept_rather_than_corrected(self):
        """The scripted judge omits confidence and explanation; that is recorded."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            document = runner.load_cached(summary.run_dir, 101)
            self.assertTrue(
                document["ruling_findings"],
                "a ruling that breaks its own contract was recorded as clean",
            )

    def test_the_calls_file_records_one_entry_per_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, transport = bench(tmp)
            document = runner.read_json(summary.run_dir / runner.CALLS_FILE)
            self.assertEqual(transport.calls(), len(document["calls"]))
            self.assertEqual(
                {"attempts", "cached_tokens", "completion_tokens", "duration_seconds",
                 "model", "parse_outcome", "prompt_tokens", "reasoning_tokens",
                 "request_sha256", "status", "timestamp"},
                set(document["calls"][0]),
            )

    def test_a_cache_file_is_written_atomically(self):
        """No ``.part`` file is left behind, and none is ever read as a result."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            leftovers = sorted(path.name for path in summary.run_dir.glob("*.part"))
            self.assertEqual([], leftovers)

    def test_a_missed_field_does_not_hide_behind_the_other_three(self):
        """One wrong amount: the four-field match drops and the field tally says why."""
        with tempfile.TemporaryDirectory() as tmp:
            key = answer_key()

            def bump(case_no, ruling):
                if case_no == 103:
                    ruling["amount_sgd"] = (ruling["amount_sgd"] or Decimal("0")) + Decimal("0.05")
                return ruling

            transport = ScriptedTransport(produced_from_key(key), mutate=bump)
            summary, _ = bench(tmp, transport=transport)

            self.assertEqual(len(CASE_SET) - 1, summary.matched)
            self.assertEqual(2, summary.report.exact_matches)
            self.assertEqual((3, 3), summary.report.field_tally("ruling"))
            self.assertEqual((2, 3), summary.report.field_tally("amount_sgd"))
            self.assertEqual((3, 3), summary.report.field_tally("driver_compensation_sgd"))
            self.assertEqual((3, 3), summary.report.field_tally("referrals"))
            verdicts = {outcome.case_no: outcome.verdict for outcome in summary.outcomes}
            self.assertEqual("MISS", verdicts[103])
            self.assertEqual("match", verdicts[101])


# --------------------------------------------------------------------------
# The configuration object
# --------------------------------------------------------------------------
class ConfigurationTests(unittest.TestCase):
    """What produced a result, written on every artifact and read two ways.

    ``judge_votes`` and ``verify_drafts`` used to appear only on the
    ``invocation_start`` event, which is a line in a log. They are on the run's
    metadata, on each invocation's entry in the history and on each case file
    now, so one case file says what produced it without the invocation around
    it. A file written before the object existed is read as the run it in fact
    was -- no ablation, no precedents, policy version 1 -- and its two switches
    as unknown rather than as defaults, because nothing in the file says them.
    """

    def test_a_case_file_carries_the_configuration_it_was_run_under(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, judge_votes=1)
            document = runner.load_cached(summary.run_dir, 101)
            self.assertEqual(
                runner.configuration_document(judge_votes=1, verify_drafts=False),
                document["configuration"],
            )
            self.assertEqual(
                sorted(runner.CONFIGURATION_FIELDS),
                sorted(document["configuration"]),
            )

    def test_the_run_record_and_every_invocation_entry_carry_it_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, judge_votes=1)
            expected = runner.configuration_document(judge_votes=1, verify_drafts=False)
            run = runner.read_json(summary.run_dir / runner.METADATA_FILE)
            self.assertEqual(expected, run["configuration"])
            history = runner.read_json(summary.run_dir / runner.INVOCATIONS_FILE)
            self.assertEqual(1, len(history))
            self.assertEqual(expected, history[0]["configuration"])

    def test_the_draft_count_in_force_is_the_one_recorded(self):
        """Not a constant: a run asked for two drafts records two."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, judge_votes=2)
            document = runner.load_cached(summary.run_dir, 101)
            self.assertEqual(2, document["configuration"]["judge_votes"])
            run = runner.read_json(summary.run_dir / runner.METADATA_FILE)
            self.assertEqual(2, run["configuration"]["judge_votes"])

    def test_a_file_without_the_object_reads_as_the_run_it_was(self):
        """The dirty fixture: a record written before the object existed."""
        old = {"case_no": 101, "ruling": {"ruling": {}}}
        read = runner.configuration_of(old)
        self.assertIsNone(read["ablation"])
        self.assertIsNone(read["precedents"])
        self.assertEqual(runner.DEFAULT_POLICY_VERSION, read["policy_version"])
        # For display the two switches are unknown, not a default.
        self.assertIsNone(read["judge_votes"])
        self.assertIsNone(read["verify_drafts"])

    def test_the_object_is_read_back_exactly_as_written(self):
        """The clean fixture: every field present and read as itself."""
        written = runner.configuration_document(
            judge_votes=4,
            verify_drafts=True,
            ablation="clause-notes",
            precedents={"chain_head": "abc"},
            policy_version=2,
        )
        self.assertEqual(written, runner.configuration_of({"configuration": written}))

    def test_a_configuration_that_is_not_an_object_is_not_trusted(self):
        read = runner.configuration_of({"configuration": ["not", "an", "object"]})
        self.assertEqual(runner.DEFAULT_POLICY_VERSION, read["policy_version"])
        self.assertIsNone(read["ablation"])


# --------------------------------------------------------------------------
# Progress
# --------------------------------------------------------------------------
class ProgressTests(unittest.TestCase):
    """One result line per case, printed as it lands rather than at the end."""

    def test_one_line_per_case_names_the_number_verdict_clock_and_tokens(self):
        lines = []
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp, progress=lines.append)

        # Two lines per case: one when it starts and one when it lands. The
        # result line is the one carrying the verdict, the clock and the tokens,
        # so it is the one held to all three; the start line carries what is
        # known before a result exists, which is only the case and its position.
        started = [line for line in lines if line.endswith("started")]
        done = [line for line in lines if not line.endswith("started")]
        self.assertEqual(len(CASE_SET), len(started), "a case was not announced as starting")
        self.assertEqual(len(CASE_SET), len(done), "a case printed no result line")
        for case_no, line in zip(CASE_SET, done):
            with self.subTest(case_no=case_no):
                self.assertIn("case {0}".format(case_no), line)
                self.assertIn("match", line)
                self.assertIn("tokens", line)
                self.assertIn("s", line)

    def test_a_failed_case_prints_its_kind_the_agent_and_the_reason(self):
        """The line names the KIND, not a generic FAILED.

        A reader watching the terminal has to be able to tell a case the client
        stopped waiting for from a case the model answered badly — the two call
        for opposite responses, and a single word for both hides that.
        """
        lines = []
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key), fail={(102, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp, transport=transport, progress=lines.append)

        failed = [line for line in lines if runner.FAILURE_SHAPE in line]
        self.assertEqual(1, len(failed), "the failure did not print one line")
        self.assertIn("case 102", failed[0])
        self.assertIn(transcript.ROLE_JUDGE, failed[0])
        self.assertNotIn("FAILED", failed[0], "the kind should stand in for the generic word")

    def test_the_verdict_word_names_the_failure_kind_when_there_is_one(self):
        """``FAILED`` is only the fallback for a failure nobody classified."""
        classified = runner.CaseOutcome(
            case_no=109,
            status=runner.STATUS_FAILED,
            failure_kind=runner.FAILURE_TIMEOUT,
        )
        unclassified = runner.CaseOutcome(case_no=109, status=runner.STATUS_FAILED)

        self.assertEqual(runner.FAILURE_TIMEOUT, classified.verdict)
        self.assertEqual("FAILED", unclassified.verdict)

    def test_a_cached_case_is_printed_before_the_run_starts(self):
        lines = []
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp, progress=lines.append)
            lines.clear()
            bench(tmp, progress=lines.append)

        self.assertEqual(len(CASE_SET), len(lines))
        self.assertTrue(all("cached" in line for line in lines))

    def test_the_verdict_word_covers_all_four_states(self):
        cases = [
            (runner.STATUS_FAILED, None, "FAILED"),
            (runner.STATUS_CACHED, True, "cached"),
            (runner.STATUS_COMPLETED, True, "match"),
            (runner.STATUS_COMPLETED, False, "MISS"),
        ]
        for status, matched, expected in cases:
            with self.subTest(status=status, matched=matched):
                outcome = runner.CaseOutcome(case_no=101, status=status, matched=matched)
                self.assertEqual(expected, outcome.verdict)


# --------------------------------------------------------------------------
# Resumption
# --------------------------------------------------------------------------
class ResumptionTests(unittest.TestCase):
    """An instrument that loses everything when case 27 fails is not an instrument."""

    def test_a_second_invocation_makes_no_call_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, _ = bench(tmp)
            second, transport = bench(tmp)

            self.assertEqual(0, transport.calls(), "a cached run still called the model")
            self.assertEqual(list(CASE_SET), second.cached_cases)
            self.assertEqual([], second.completed_cases)
            self.assertEqual(runner.STOP_COMPLETED, second.stop_reason)
            self.assertEqual(first.tokens_spent, second.tokens_reused)
            self.assertEqual(0, second.tokens_spent)

    def test_the_cached_cases_are_graded_again_rather_than_copied(self):
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp)
            second, _ = bench(tmp)
            self.assertEqual(len(CASE_SET), second.report.exact_matches)
            self.assertEqual(len(CASE_SET), second.report.total)

    def test_force_redoes_the_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp)
            forced, transport = bench(tmp, force=True)

            self.assertEqual(len(CASE_SET) * CALLS_PER_CASE, transport.calls())
            self.assertEqual(list(CASE_SET), forced.completed_cases)
            self.assertEqual([], forced.cached_cases)

    def test_a_case_not_yet_cached_is_the_only_one_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = answer_key()
            transport = ScriptedTransport(
                produced_from_key(key), fail={(102, transcript.ROLE_JUDGE)}
            )
            bench(tmp, transport=transport)

            retry = ScriptedTransport(produced_from_key(key))
            second, _ = bench(tmp, transport=retry)

            self.assertEqual([102], retry.cases_called(), "a re-run did not retry exactly the failure")
            self.assertEqual([101, 103], second.cached_cases)
            self.assertEqual([102], second.completed_cases)

    def test_a_cache_entry_without_a_ruling_is_not_a_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            path = runner.case_cache_path(summary.run_dir, 102)
            document = json.loads(path.read_text(encoding="utf-8"))
            del document["ruling"]
            path.write_text(json.dumps(document), encoding="utf-8")

            self.assertIsNone(runner.load_cached(summary.run_dir, 102))

            transport = ScriptedTransport(produced_from_key(answer_key()))
            second, _ = bench(tmp, transport=transport)
            self.assertEqual([102], transport.cases_called())
            self.assertEqual([101, 103], second.cached_cases)

    def test_a_corrupt_cache_entry_is_re_run_rather_than_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            runner.case_cache_path(summary.run_dir, 102).write_text("{not json", encoding="utf-8")

            transport = ScriptedTransport(produced_from_key(answer_key()))
            second, _ = bench(tmp, transport=transport)
            self.assertEqual([102], transport.cases_called())
            self.assertEqual([101, 103], second.cached_cases)

    def test_a_cache_entry_for_another_case_is_not_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            source = runner.case_cache_path(summary.run_dir, 101)
            target = runner.case_cache_path(summary.run_dir, 102)
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

            self.assertIsNone(
                runner.load_cached(summary.run_dir, 102),
                "a cache entry belonging to case 101 was read as case 102's",
            )

    def test_transcripts_are_not_counted_as_cached_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            present = sorted(path.name for path in summary.run_dir.glob("case-*.json"))
            self.assertEqual(
                2 * len(CASE_SET), len(present), "the transcripts are not sitting beside the cache"
            )
            self.assertEqual(list(CASE_SET), runner.cached_case_numbers(summary.run_dir))


# --------------------------------------------------------------------------
# Failure
# --------------------------------------------------------------------------
class FailureTests(unittest.TestCase):
    """A failed case is recorded, the run continues, and nothing is cached for it."""

    def test_the_run_continues_past_a_failed_case(self):
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key), fail={(102, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, transport=transport)

            self.assertEqual(runner.STOP_COMPLETED, summary.stop_reason)
            self.assertFalse(summary.ok, "a run with a failed case reported itself as fine")
            self.assertEqual([101, 103], summary.completed_cases)
            self.assertEqual([102], [outcome.case_no for outcome in summary.failures])
            self.assertEqual(
                [101, 102, 103],
                transport.cases_called(),
                "the run stopped at the failure instead of continuing past it",
            )

    def test_the_failed_case_is_absent_from_the_cache(self):
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key), fail={(102, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, transport=transport)

            self.assertFalse(
                runner.case_cache_path(summary.run_dir, 102).exists(),
                "a failed case was cached, so a re-run would never retry it",
            )
            self.assertEqual([101, 103], runner.cached_case_numbers(summary.run_dir))

    def test_the_failed_case_still_leaves_its_transcript(self):
        """The raw bodies are the evidence for why it failed."""
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key), fail={(102, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, transport=transport)
            self.assertTrue(runner.transcript_path(summary.run_dir, 102).is_file())

    def test_the_metadata_names_the_failure(self):
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key), fail={(102, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, transport=transport)
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))

            self.assertEqual([102], metadata["cases"]["failed"])
            self.assertEqual([101, 103], metadata["cases"]["completed"])
            self.assertEqual(1, len(metadata["failures"]))
            self.assertEqual(102, metadata["failures"][0]["case_no"])
            self.assertEqual(transcript.ROLE_JUDGE, metadata["failures"][0]["failed_agent"])
            self.assertIsNotNone(metadata["failures"][0]["reason"])

    def test_the_report_covers_what_ran_and_not_what_was_asked_for(self):
        """A failed case is not a wrong answer; it is not an answer at all."""
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key), fail={(102, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, transport=transport)
            self.assertEqual(2, summary.report.total)
            self.assertEqual(2, summary.report.exact_matches)
            self.assertNotIn(
                102,
                [score.case_no for score in summary.report.cases],
                "a case that produced no ruling was scored as though it had",
            )

    def test_a_run_with_no_usable_case_reports_nothing_rather_than_zero_percent(self):
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key),
            fail={(case_no, transcript.ROLE_RIDER_ADVOCATE) for case_no in CASE_SET},
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, transport=transport)

            self.assertEqual(0, summary.report.total, "an empty run reported a denominator")
            self.assertEqual(0, summary.report.exact_matches)
            self.assertEqual([], runner.cached_case_numbers(summary.run_dir))

    def test_a_missing_credential_is_not_a_case_failure(self):
        """It is the same failure for every case, so it is raised, not recorded."""

        def build(sink):
            raise llm.MissingAPIKeyError("no credential")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(llm.MissingAPIKeyError):
                bench(tmp, client_factory=build)


# --------------------------------------------------------------------------
# The request timeout
# --------------------------------------------------------------------------
class ReadTimeoutTransport:
    """A transport whose every call raises a read timeout.

    This is the shape the real failure took. ``TimeoutError: The read operation
    timed out`` escapes ``response.read()`` as a bare ``TimeoutError`` rather
    than being wrapped in a ``URLError``, so the adapter's ``TransportError``
    conversion never sees it and it reaches the runner unconverted. It is the
    failure that cost case 109 on ``hy3`` at 120.1 s.
    """

    def __init__(
        self,
        exception=TimeoutError,
        message: str = "The read operation timed out",
    ) -> None:
        self.exception = exception
        self.message = message
        self.timeouts = 0

    def __call__(self, url, headers, body, timeout):
        self.timeouts += 1
        raise self.exception(self.message)


class UnreachableTransport:
    """A transport that never reaches the endpoint, for a reason that is not waiting.

    The contrast case. A transport failure is retried; a timeout is answered
    with a longer timeout or a faster model. If these two collapsed into one
    reason the record would be telling a reader to do the wrong thing.
    """

    def __call__(self, url, headers, body, timeout):
        raise llm.TransportError("could not reach the endpoint: connection refused")


class RequestTimeoutTests(unittest.TestCase):
    """The timeout is derived from measurement, threaded through, and classified.

    A real benchmark run lost a case to the 120-second default, so there are
    three things to hold in place: the default itself, the flag that reaches the
    client, and the failure kind that lets a reader tell a case the client
    stopped waiting for from a case the model answered unusably.
    """

    def test_the_runner_defaults_to_the_clients_own_default(self):
        """One source for the number, so the runner cannot drift from the client."""
        import inspect

        parameters = inspect.signature(runner.run_benchmark).parameters
        self.assertEqual(
            llm.DEFAULT_TIMEOUT_SECONDS, parameters["timeout_seconds"].default
        )
        self.assertEqual(600.0, llm.DEFAULT_TIMEOUT_SECONDS)

    def test_the_timeout_in_force_is_recorded_in_the_run_metadata(self):
        """A run under 120 s is not the same measurement as one under 600 s."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))

        self.assertEqual(llm.DEFAULT_TIMEOUT_SECONDS, metadata["timeout_seconds"])
        self.assertEqual(llm.DEFAULT_TIMEOUT_SECONDS, summary.timeout_seconds)

    def test_a_shortened_timeout_is_recorded_as_the_one_in_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, timeout_seconds=15.0)
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))

        self.assertEqual(15.0, metadata["timeout_seconds"])

    def test_the_factory_builds_the_client_with_the_timeout_it_was_given(self):
        """The flag is not decorative: it is what the client is constructed with."""
        built = {}

        def fake_client(**kwargs):
            built.update(kwargs)
            return mock.Mock()

        with mock.patch.object(runner.llm, "LLMClient", side_effect=fake_client):
            runner._default_client_factory(MODEL, 12.5)(lambda record: None)

        self.assertEqual(12.5, built["timeout_seconds"])
        self.assertEqual(MODEL, built["model"])

    def test_a_shortened_timeout_reaches_the_client_end_to_end(self):
        """Through ``run_benchmark``, not only through the factory directly."""
        built = []

        def fake_client(**kwargs):
            built.append(kwargs)
            client = mock.Mock()
            client.complete.side_effect = RuntimeError("this test never calls a model")
            return client

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(runner.llm, "LLMClient", side_effect=fake_client):
                bench(tmp, cases=(101,), timeout_seconds=9.0, client_factory=None)

        self.assertEqual([9.0], [item["timeout_seconds"] for item in built])

    def test_the_timeout_flag_overrides_the_default(self):
        """A caller can shorten it deliberately for a probe without editing code."""
        built = []

        def fake_client(**kwargs):
            built.append(kwargs)
            client = mock.Mock()
            client.complete.side_effect = RuntimeError("this test never calls a model")
            return client

        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                with mock.patch.object(runner.llm, "LLMClient", side_effect=fake_client):
                    status = runner.main(
                        [
                            "--model", MODEL,
                            "--cases", "101",
                            "--timeout", "5",
                            "--runs-dir", str(Path(tmp) / "runs"),
                        ]
                    )

        self.assertEqual([5.0], [item["timeout_seconds"] for item in built])
        self.assertEqual(1, status, "a run whose only case failed exits non-zero")

    def test_the_timeout_flag_defaults_to_the_clients_default(self):
        built = []

        def fake_client(**kwargs):
            built.append(kwargs)
            client = mock.Mock()
            client.complete.side_effect = RuntimeError("this test never calls a model")
            return client

        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                with mock.patch.object(runner.llm, "LLMClient", side_effect=fake_client):
                    runner.main(
                        [
                            "--model", MODEL,
                            "--cases", "101",
                            "--runs-dir", str(Path(tmp) / "runs"),
                        ]
                    )

        self.assertEqual(
            [llm.DEFAULT_TIMEOUT_SECONDS], [item["timeout_seconds"] for item in built]
        )

    def test_a_timeout_is_recorded_under_its_own_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=(101,), transport=ReadTimeoutTransport())
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))

        failure = summary.failures[0]
        self.assertEqual(runner.FAILURE_TIMEOUT, failure.failure_kind)
        self.assertEqual(
            runner.FAILURE_TIMEOUT, metadata["failures"][0]["failure_kind"]
        )
        # The kind and the note lead, and the exception's own text still follows
        # as the evidence. Both are in the one reason string on purpose.
        self.assertIn("TimeoutError", failure.failure_detail or "")
        self.assertIn("The read operation timed out", failure.failure_reason or "")
        self.assertIn(runner.FAILURE_NOTE[runner.FAILURE_TIMEOUT], failure.failure_reason)

    def test_a_timeout_and_a_transport_failure_are_told_apart(self):
        """The whole point of the kind: these two call for opposite responses."""
        with tempfile.TemporaryDirectory() as tmp:
            timed_out, _ = bench(tmp, cases=(101,), transport=ReadTimeoutTransport())

        with tempfile.TemporaryDirectory() as tmp:
            unreachable, _ = bench(tmp, cases=(101,), transport=UnreachableTransport())

        self.assertEqual(runner.FAILURE_TIMEOUT, timed_out.failures[0].failure_kind)
        self.assertEqual(
            runner.FAILURE_TRANSPORT, unreachable.failures[0].failure_kind
        )
        self.assertNotEqual(
            timed_out.failures[0].failure_reason,
            unreachable.failures[0].failure_reason,
            "a timeout and a dead connection must not read alike",
        )
        self.assertEqual(1, len(timed_out.timeouts))
        self.assertEqual([], unreachable.timeouts)

    def test_a_shape_failure_is_not_recorded_as_a_timeout(self):
        """The run already contains one of each, so they must not collapse."""
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key), fail={(101, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=(101,), transport=transport)

        self.assertEqual(runner.FAILURE_SHAPE, summary.failures[0].failure_kind)
        self.assertEqual([], summary.timeouts)

    def test_the_run_continues_after_a_timed_out_case(self):
        """A timeout is a failed case, not a failed run — the same as any other."""
        key = answer_key()
        scripted = ScriptedTransport(produced_from_key(key))

        def times_out_for_102(url, headers, body, timeout):
            request = json.loads(body.decode("utf-8"))
            if role_of(request)[0] == 102:
                raise TimeoutError("The read operation timed out")
            return scripted(url, headers, body, timeout)

        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=CASE_SET, transport=times_out_for_102)
            cached = runner.cached_case_numbers(summary.run_dir)

        self.assertEqual(runner.STOP_COMPLETED, summary.stop_reason)
        self.assertEqual([102], [outcome.case_no for outcome in summary.timeouts])
        self.assertEqual([101, 103], sorted(summary.completed_cases))
        self.assertEqual([101, 103], sorted(cached))
        self.assertNotIn(102, cached, "a timed-out case must not be cached")
        self.assertFalse(summary.ok, "a run with a failed case is not ok")

    def test_a_timeout_is_visible_in_the_summary_block(self):
        """A reader of the terminal should not have to open the metadata."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=(101,), transport=ReadTimeoutTransport())

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runner.print_summary(summary)
        text = output.getvalue()

        self.assertIn("timeout", text)
        self.assertIn(runner.FAILURE_TIMEOUT, text)
        self.assertIn("case 101", text)
        self.assertIn("The read operation timed out", text)

    def test_a_socket_timeout_is_a_timeout_too(self):
        """``socket.timeout`` is not ``TimeoutError`` on every interpreter.

        On 3.10 and later the two are the same class; on 3.9 they are separate
        ``OSError`` subclasses, and ``urlopen``'s read timeout is the socket one.
        Checking only ``TimeoutError`` would quietly demote a real timeout to
        the transport kind on 3.9 — the very confusion this change exists to
        remove.

        **Measured**: dropping ``socket.timeout`` from the classifier turns this
        test RED on 3.9.6 (2 failures) and changes nothing on 3.13.12, where the
        two names are one class. So this guard is only falsifiable on 3.9, and
        the suite has to be run there to demonstrate it.
        """
        import socket

        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(
                tmp,
                cases=(101,),
                transport=ReadTimeoutTransport(exception=socket.timeout),
            )

        self.assertEqual(runner.FAILURE_TIMEOUT, summary.failures[0].failure_kind)

    def test_the_kind_is_read_off_the_exception_type(self):
        """The classifier itself, without a run in the way."""
        import socket

        cases = [
            (TimeoutError("read timed out"), runner.FAILURE_TIMEOUT),
            (socket.timeout("read timed out"), runner.FAILURE_TIMEOUT),
            (llm.TransportError("could not reach the endpoint"), runner.FAILURE_TRANSPORT),
            (ConnectionResetError("connection reset"), runner.FAILURE_TRANSPORT),
            (KeyboardInterrupt(), runner.FAILURE_INTERRUPTED),
        ]
        for exc, expected in cases:
            with self.subTest(exception=type(exc).__name__):
                self.assertEqual(expected, runner.failure_kind_for(exc))

    def test_a_non_positive_timeout_is_refused(self):
        """Refused rather than clamped: a caller who passed one meant something else."""
        for value in (0.0, -1.0):
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaises(runner.BenchmarkError):
                        bench(tmp, cases=(101,), timeout_seconds=value)


# --------------------------------------------------------------------------
# The deadline
# --------------------------------------------------------------------------
class DeadlineTests(unittest.TestCase):
    """The bound on one case, and the failure kind it produces.

    Two limits are in force and the runner must not merge them: the per-attempt
    timeout says one request waited too long, and the deadline says the run
    stopped itself before starting work it had no time to finish. On 2026-09-22
    a run wrote its last case at 07:25 and was still alive at 09:13 with no
    output, while the provider answered a direct probe in 0.95 s -- so this is a
    defect found by measurement, not a hypothetical one.
    """

    def test_both_deadlines_are_classified_under_their_own_kind(self):
        """Two layers raise it and a reader acts on them the same way."""
        cases = [
            (
                llm.DeadlineExceededError(
                    "gave up", elapsed_seconds=1201.0, attempts=1
                ),
                runner.FAILURE_DEADLINE,
            ),
            (
                pipeline.CaseDeadlineExceeded(
                    "case 106 exceeded its deadline", elapsed_seconds=2401.0, case_no=106
                ),
                runner.FAILURE_DEADLINE,
            ),
        ]
        for exc, expected in cases:
            with self.subTest(exception=type(exc).__name__):
                self.assertEqual(expected, runner.failure_kind_for(exc))
                self.assertNotEqual(
                    runner.FAILURE_TIMEOUT,
                    runner.failure_kind_for(exc),
                    "the client giving up is not one request waiting too long",
                )

    def test_the_deadline_kind_has_its_own_note(self):
        """The note is what tells a reader what to DO, so it must not be shared."""
        self.assertIn(runner.FAILURE_DEADLINE, runner.FAILURE_NOTE)
        self.assertNotEqual(
            runner.FAILURE_NOTE[runner.FAILURE_DEADLINE],
            runner.FAILURE_NOTE[runner.FAILURE_TIMEOUT],
        )
        reason = runner.failure_reason_for(runner.FAILURE_DEADLINE, "detail")
        self.assertTrue(reason.startswith(runner.FAILURE_DEADLINE + ": "))

    def test_a_case_that_hit_its_deadline_is_failed_and_the_run_continues(self):
        """A deadline is a failed case, not a failed run, and it carries the time."""
        key = answer_key()
        scripted = ScriptedTransport(produced_from_key(key))

        def deadline_for_102(url, headers, body, timeout):
            request = json.loads(body.decode("utf-8"))
            if role_of(request)[0] == 102:
                raise pipeline.CaseDeadlineExceeded(
                    "case 102 exceeded its 2400 s deadline after 2401.0 s",
                    elapsed_seconds=2401.0,
                    case_no=102,
                )
            return scripted(url, headers, body, timeout)

        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=CASE_SET, transport=deadline_for_102)
            cached = runner.cached_case_numbers(summary.run_dir)

        self.assertEqual(runner.STOP_COMPLETED, summary.stop_reason)
        self.assertEqual([102], [outcome.case_no for outcome in summary.failures])
        self.assertEqual(runner.FAILURE_DEADLINE, summary.failures[0].failure_kind)
        self.assertEqual([], summary.timeouts, "a deadline is not a timeout")
        self.assertEqual([101, 103], sorted(summary.completed_cases))
        self.assertEqual([101, 103], sorted(cached))
        self.assertNotIn(102, cached, "a case that ran out of time must not be cached")
        # Named, with the elapsed time: the figure the limit was measured
        # against, not only the limit.
        self.assertIn("2401.0 s", summary.failures[0].failure_reason or "")
        self.assertFalse(summary.ok, "a run with a failed case is not ok")

    def test_the_pipelines_own_deadline_reaches_the_runner(self):
        """End to end, through the real pipeline, with no model call at all.

        A deadline already spent when the case begins stops it at its first
        check, so the transport is never called. That is the property the
        pre-attempt check exists for, and it is visible here as zero requests.
        """
        key = answer_key()
        transport = ScriptedTransport(produced_from_key(key))

        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(
                tmp, cases=(101,), transport=transport, case_deadline_seconds=1e-9
            )
            cached = runner.cached_case_numbers(summary.run_dir)

        self.assertEqual(runner.FAILURE_DEADLINE, summary.failures[0].failure_kind)
        self.assertEqual(0, transport.calls(), "no call may start once the budget is gone")
        self.assertEqual([], cached)
        self.assertEqual([], summary.completed_cases)

    def test_the_runner_defaults_to_the_pipelines_own_default(self):
        """One source for the number, so the two layers cannot drift apart."""
        import inspect

        parameters = inspect.signature(runner.run_benchmark).parameters
        self.assertEqual(
            pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
            parameters["case_deadline_seconds"].default,
        )
        self.assertEqual(
            pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
            inspect.signature(runner.run_one_case).parameters["case_deadline_seconds"].default,
        )

    def test_the_deadline_in_force_is_recorded_in_the_run_metadata(self):
        """A case stopped at 2400 s is not the same measurement as one stopped at 241 minutes."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, case_deadline_seconds=99.0)
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))

        self.assertEqual(99.0, metadata["case_deadline_seconds"])
        self.assertEqual(99.0, summary.case_deadline_seconds)

    def test_a_non_positive_case_deadline_is_refused(self):
        """Refused rather than clamped: it would fail every case at the first check."""
        for value in (0.0, -1.0):
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaises(runner.BenchmarkError):
                        bench(tmp, cases=(101,), case_deadline_seconds=value)

    def test_the_default_is_a_bound_and_still_clears_the_slowest_case(self):
        """Derived from measurement, asserted as the derivation rather than the number.

        The slowest completed case in the corpus is 978.8 s, so a default at or
        below that would fail the slowest thing actually seen. It also has to
        accommodate three calls each running into the per-attempt timeout, and
        still be a bound on the 241-minute worst case it was added to remove.
        """
        self.assertGreater(pipeline.DEFAULT_CASE_DEADLINE_SECONDS, 978.8)
        self.assertGreaterEqual(
            pipeline.DEFAULT_CASE_DEADLINE_SECONDS, 3 * llm.DEFAULT_TIMEOUT_SECONDS
        )
        self.assertLess(pipeline.DEFAULT_CASE_DEADLINE_SECONDS, 241 * 60)


class StartLineTests(unittest.TestCase):
    """A hang must be visible while it is happening, not after."""

    def test_the_start_line_names_the_case_and_its_position(self):
        self.assertEqual("[  2/30] case 106  started", runner.format_start(106, 2, 30))

    def test_the_start_line_is_printed_before_the_case_runs(self):
        """The ordering is the whole feature: the last line must name what is in flight.

        On 2026-09-22 the terminal's last line named a case that had already
        finished, so nothing on screen distinguished a hung case from a long one
        and the process had to be probed by hand. A line emitted from inside the
        worker could be scheduled after a later case's completion line, so it is
        emitted on the queue's own thread, before the work is submitted.
        """
        key = answer_key()
        events = []
        scripted = ScriptedTransport(produced_from_key(key))

        def recording_transport(url, headers, body, timeout):
            request = json.loads(body.decode("utf-8"))
            events.append(("call", role_of(request)[0]))
            return scripted(url, headers, body, timeout)

        with tempfile.TemporaryDirectory() as tmp:
            bench(
                tmp,
                cases=CASE_SET,
                transport=recording_transport,
                progress=events.append,
            )

        lines = [event for event in events if isinstance(event, str)]
        # One start and one completion line per case, and nothing else.
        self.assertEqual(2 * len(CASE_SET), len(lines))
        for position, case_no in enumerate(CASE_SET, start=1):
            with self.subTest(case_no=case_no):
                start_line = runner.format_start(case_no, position, len(CASE_SET))
                self.assertIn(start_line, lines)
                first_call = min(
                    index
                    for index, event in enumerate(events)
                    if event == ("call", case_no)
                )
                self.assertLess(
                    events.index(start_line),
                    first_call,
                    "the line must be on the terminal before the work starts",
                )

    def test_the_start_line_is_not_printed_for_a_case_already_cached(self):
        """Nothing starts, so nothing is announced as starting."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            bench(tmp, runs_dir=runs)
            events = []
            bench(tmp, runs_dir=runs, progress=events.append)

        lines = [event for event in events if isinstance(event, str)]
        self.assertEqual([], [line for line in lines if line.endswith("started")])
        self.assertEqual(len(CASE_SET), len(lines), "the reuse lines are still printed")


# --------------------------------------------------------------------------
# Interrupting
# --------------------------------------------------------------------------
class InterruptTests(unittest.TestCase):
    """An interrupt loses at most the case in flight, never the work already done."""

    @staticmethod
    def _interrupt_on(case_no):
        """The real ``run_one_case``, except for one case, which is interrupted."""
        real = runner.run_one_case

        def wrapper(number, **kwargs):
            if number == case_no:
                raise KeyboardInterrupt
            return real(number, **kwargs)

        return wrapper

    def test_an_interrupt_keeps_the_cases_already_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(runner, "run_one_case", self._interrupt_on(102)):
                summary, transport = bench(tmp, cases=(101, 102, 103))

            self.assertEqual(runner.STOP_INTERRUPTED, summary.stop_reason)
            self.assertFalse(summary.completed)
            self.assertFalse(summary.ok)
            self.assertEqual([101], summary.completed_cases)
            self.assertEqual(
                [101],
                runner.cached_case_numbers(summary.run_dir),
                "the case that had already finished was not kept",
            )
            self.assertNotIn(
                103,
                transport.cases_called(),
                "the run carried on issuing cases after the interrupt",
            )

    def test_an_interrupted_run_still_has_correct_provenance_and_totals(self):
        """Written after every case, so an interrupt cannot leave nothing behind."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(runner, "run_one_case", self._interrupt_on(102)):
                summary, _ = bench(tmp, cases=(101, 102, 103))

            metadata = runner.read_json(runner.metadata_path(summary.run_dir))
            self.assertEqual(runner.STOP_INTERRUPTED, metadata["stop_reason"])
            self.assertFalse(metadata["completed"])
            self.assertEqual(COMMIT, metadata["git_commit"])
            self.assertIs(True, metadata["working_tree_clean"])
            self.assertEqual([101], metadata["cases"]["completed"])
            self.assertEqual(TOKENS_PER_CASE, metadata["tokens"]["spent_this_invocation"])
            self.assertEqual(list(CASE_SET), metadata["cases"]["requested"])

    def test_no_case_is_counted_twice_after_an_interrupt(self):
        """The drain after an interrupt must not re-add a case the loop already took."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(runner, "run_one_case", self._interrupt_on(102)):
                summary, _ = bench(tmp, cases=(101, 102, 103))

            numbers = [outcome.case_no for outcome in summary.outcomes]
            self.assertEqual(sorted(set(numbers)), sorted(numbers), "a case was counted twice")

            metadata = runner.read_json(runner.metadata_path(summary.run_dir))
            for name in ("completed", "cached", "failed"):
                with self.subTest(list_name=name):
                    values = metadata["cases"][name]
                    self.assertEqual(sorted(set(values)), sorted(values))

    def test_the_case_in_flight_is_recorded_rather_than_silently_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(runner, "run_one_case", self._interrupt_on(102)):
                summary, _ = bench(tmp, cases=(101, 102, 103))

            self.assertEqual([102], [outcome.case_no for outcome in summary.failures])
            self.assertFalse(
                runner.case_cache_path(summary.run_dir, 102).exists(),
                "the interrupted case was cached, so a re-run would never retry it",
            )


# --------------------------------------------------------------------------
# The token budget
# --------------------------------------------------------------------------
class TokenBudgetTests(unittest.TestCase):
    """A partial run whose limit is stated is useful; an unexpected bill is not."""

    def test_the_budget_stops_new_work_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, transport = bench(tmp, token_budget=700)

            self.assertEqual(runner.STOP_BUDGET, summary.stop_reason)
            self.assertFalse(summary.completed, "a budget stop reported itself as complete")
            self.assertFalse(summary.ok)
            self.assertEqual([101, 102], summary.completed_cases)
            self.assertEqual(2 * TOKENS_PER_CASE, summary.tokens_spent)
            self.assertEqual([103], [case_no for case_no in CASE_SET if case_no not in transport.cases_called()])

    def test_the_budget_is_the_reason_the_metadata_gives(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, token_budget=700)
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))

            self.assertEqual(runner.STOP_BUDGET, metadata["stop_reason"])
            self.assertFalse(metadata["completed"])
            self.assertEqual(700, metadata["token_budget"])

    def test_the_case_the_budget_stopped_has_no_cache_entry(self):
        """So a later run picks it up, which is the whole point of the limit."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, token_budget=700)
            self.assertFalse(runner.case_cache_path(summary.run_dir, 103).exists())
            self.assertEqual([101, 102], runner.cached_case_numbers(summary.run_dir))

    def test_the_report_covers_only_the_cases_that_ran(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, token_budget=700)
            self.assertEqual(2, summary.report.total)
            self.assertEqual(2, summary.report.exact_matches)

    def test_a_budget_that_is_already_spent_stops_before_any_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, transport = bench(tmp, token_budget=0)

            self.assertEqual(runner.STOP_BUDGET, summary.stop_reason)
            self.assertEqual(0, transport.calls(), "the budget was checked after the first call")
            self.assertEqual([], summary.outcomes)
            self.assertEqual([], runner.cached_case_numbers(summary.run_dir))

    def test_tokens_reused_from_cache_are_not_charged_to_the_budget(self):
        """The budget is about what this invocation spends, not what it re-reads."""
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp)
            second, transport = bench(tmp, token_budget=1)

            self.assertEqual(0, transport.calls())
            self.assertEqual(runner.STOP_COMPLETED, second.stop_reason)
            self.assertEqual(0, second.tokens_spent)
            self.assertEqual(len(CASE_SET) * TOKENS_PER_CASE, second.tokens_reused)

    def test_no_budget_means_no_budget_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, token_budget=None)
            self.assertEqual(runner.STOP_COMPLETED, summary.stop_reason)
            self.assertIsNone(summary.token_budget)

    def test_the_budget_lets_the_work_already_in_flight_finish(self):
        """Its tokens are already being spent; cancelling it would lose money.

        Two workers, three cases, and a budget that one case already reaches.
        Both cases that were issued must land — and be cached — while the third
        is never sent. The race is not on the outcome: whichever of the two
        finishes first, the spend is over the budget before a worker frees.
        """
        cases = (101, 102, 103)
        with tempfile.TemporaryDirectory() as tmp:
            summary, transport = bench(
                tmp, cases=cases, token_budget=TOKENS_PER_CASE, concurrency=2
            )

            self.assertEqual(runner.STOP_BUDGET, summary.stop_reason)
            self.assertEqual(2, len(summary.completed_cases), "an in-flight case was abandoned")
            self.assertEqual([103], [case_no for case_no in cases if case_no not in transport.cases_called()])
            for case_no in summary.completed_cases:
                with self.subTest(case_no=case_no):
                    self.assertTrue(
                        runner.case_cache_path(summary.run_dir, case_no).is_file(),
                        "a case that finished was not cached",
                    )
            self.assertFalse(runner.case_cache_path(summary.run_dir, 103).exists())

    def test_a_negative_budget_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(runner.BenchmarkError):
                bench(tmp, token_budget=-1)


class TokenAccountingTests(unittest.TestCase):
    """The billed total is the prompt plus the completion, and nothing else."""

    def test_reasoning_tokens_are_a_breakdown_and_are_not_counted_twice(self):
        """Counting them again would overstate the spend and trip the budget early.

        The figures are per case, summed over its three calls, because that is
        what the cache entry records.
        """
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)

            self.assertEqual(TOKENS_PER_CALL, runner.billed_tokens(PROMPT_TOKENS, COMPLETION_TOKENS))

            for case_no in CASE_SET:
                with self.subTest(case_no=case_no):
                    tokens = runner.load_cached(summary.run_dir, case_no)["tokens"]
                    self.assertEqual(CALLS_PER_CASE * PROMPT_TOKENS, tokens["prompt_tokens"])
                    self.assertEqual(CALLS_PER_CASE * COMPLETION_TOKENS, tokens["completion_tokens"])
                    self.assertEqual(CALLS_PER_CASE * REASONING_TOKENS, tokens["reasoning_tokens"])
                    self.assertEqual(
                        TOKENS_PER_CASE,
                        tokens["total_tokens"],
                        "reasoning tokens were added to the billed total",
                    )
                    self.assertNotEqual(
                        tokens["prompt_tokens"]
                        + tokens["completion_tokens"]
                        + tokens["reasoning_tokens"],
                        tokens["total_tokens"],
                    )

            self.assertEqual(len(CASE_SET) * TOKENS_PER_CASE, summary.tokens_spent)

    def test_an_absent_usage_block_counts_as_zero(self):
        self.assertEqual(0, runner.billed_tokens(None, None))
        self.assertEqual(5, runner.billed_tokens(5, None))
        self.assertEqual(5, runner.billed_tokens(None, 5))

    def test_the_metadata_separates_spent_from_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp)
            second, _ = bench(tmp)
            metadata = runner.read_json(runner.metadata_path(second.run_dir))

            self.assertEqual(0, metadata["tokens"]["spent_this_invocation"])
            self.assertEqual(
                len(CASE_SET) * TOKENS_PER_CASE, metadata["tokens"]["reused_from_cache"]
            )
            self.assertEqual(
                len(CASE_SET) * TOKENS_PER_CASE, metadata["tokens"]["total_for_the_case_set"]
            )


class TokenSplitTests(unittest.TestCase):
    """The split is the record and the total is derived from it, never stored.

    A total cannot be costed. Output is priced at four times input on the
    decided model, so two runs of the same total can differ by a factor in what
    they cost, and a stored total is also a second place the same arithmetic can
    be wrong.
    """

    def test_billed_is_the_prompt_plus_the_completion(self):
        """Reasoning is a breakdown of the completion, not a third quantity."""
        split = runner.TokenSplit(
            prompt_tokens=100,
            completion_tokens=40,
            reasoning_tokens=25,
            cached_tokens=60,
        )

        self.assertEqual(140, split.billed)
        self.assertNotEqual(
            split.prompt_tokens + split.completion_tokens + split.reasoning_tokens,
            split.billed,
        )

    def test_two_splits_add_componentwise(self):
        first = runner.TokenSplit(
            prompt_tokens=1, completion_tokens=2, reasoning_tokens=3, cached_tokens=4
        )
        second = runner.TokenSplit(
            prompt_tokens=10, completion_tokens=20, reasoning_tokens=30, cached_tokens=40
        )

        self.assertEqual(
            runner.TokenSplit(
                prompt_tokens=11,
                completion_tokens=22,
                reasoning_tokens=33,
                cached_tokens=44,
            ),
            first + second,
        )

    def test_a_split_round_trips_through_what_is_written(self):
        split = runner.TokenSplit(
            prompt_tokens=7, completion_tokens=8, reasoning_tokens=9, cached_tokens=10
        )
        written = split.as_dict()

        self.assertEqual(split.billed, written["total_tokens"])
        self.assertEqual(split, runner.TokenSplit.from_mapping(written))

    def test_an_absent_usage_block_is_zero_rather_than_an_error(self):
        self.assertEqual(runner.TokenSplit(), runner.TokenSplit.from_mapping(None))
        self.assertEqual(runner.TokenSplit(), runner.TokenSplit.from_mapping({}))

    def test_a_record_predating_a_field_contributes_zero_for_it(self):
        """An older entry must not drop out of the total it belongs to."""
        older = {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11}

        self.assertEqual(
            runner.TokenSplit(prompt_tokens=5, completion_tokens=6),
            runner.TokenSplit.from_mapping(older),
        )


class InvocationTokenRecordTests(unittest.TestCase):
    """What one invocation cost, split by kind and by how its cases ended.

    Two figures, and they answer different questions. ``spent_this_invocation``
    is what the budget was spent against — the cases that produced a ruling.
    ``consumed_this_invocation`` is every token the provider billed, the cases
    that failed included, because a case that fails at the judge has already had
    both its advocates paid for. A record counting only the first would report a
    run that burned part of its budget on unusable answers as a cheap one.
    """

    def _tokens(self, summary):
        return runner.read_json(runner.metadata_path(summary.run_dir))["tokens"]

    def _judge_failure(self, cases):
        """A transport that fails the named case at the judge, after both advocates."""
        transport = ScriptedTransport(
            produced_from_key(answer_key()),
            fail={(case_no, transcript.ROLE_JUDGE) for case_no in cases},
        )
        return transport

    def test_the_prompt_and_completion_totals_are_recorded_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            tokens = self._tokens(summary)

            self.assertEqual(
                len(CASE_SET) * CALLS_PER_CASE * PROMPT_TOKENS, tokens["prompt_tokens"]
            )
            self.assertEqual(
                len(CASE_SET) * CALLS_PER_CASE * COMPLETION_TOKENS,
                tokens["completion_tokens"],
            )

    def test_the_split_sums_to_the_consumed_total_and_not_past_it(self):
        """Reasoning is inside the completion, so adding it would overstate."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            tokens = self._tokens(summary)

            self.assertEqual(
                tokens["consumed_this_invocation"],
                tokens["prompt_tokens"] + tokens["completion_tokens"],
            )
            self.assertEqual(
                len(CASE_SET) * CALLS_PER_CASE * REASONING_TOKENS,
                tokens["reasoning_tokens"],
            )
            self.assertNotEqual(
                tokens["prompt_tokens"]
                + tokens["completion_tokens"]
                + tokens["reasoning_tokens"],
                tokens["consumed_this_invocation"],
            )

    def test_a_clean_run_consumes_exactly_what_it_charged(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            tokens = self._tokens(summary)

            self.assertEqual(0, tokens["of_which_failed"])
            self.assertEqual(
                tokens["spent_this_invocation"], tokens["consumed_this_invocation"]
            )

    def test_a_failed_case_is_consumed_but_not_charged_to_the_budget(self):
        """Its calls were made and billed before the answer was rejected.

        Case 101 fails at the judge, so both its advocates ran and were paid
        for. Those tokens are part of what the invocation consumed and are not
        part of what the budget was spent on.
        """
        transport = self._judge_failure((101,))
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=(101, 102), transport=transport)
            tokens = self._tokens(summary)

            self.assertEqual(1, len(summary.failures))
            # Two advocate calls were billed; the judge's failed call carried no
            # usage block, so it contributed nothing.
            self.assertEqual(2 * PROMPT_TOKENS, tokens["failed"]["prompt_tokens"])
            self.assertEqual(2 * COMPLETION_TOKENS, tokens["failed"]["completion_tokens"])
            self.assertEqual(2 * TOKENS_PER_CALL, tokens["of_which_failed"])
            self.assertEqual(TOKENS_PER_CASE, tokens["spent_this_invocation"])
            self.assertEqual(
                tokens["spent_this_invocation"] + tokens["of_which_failed"],
                tokens["consumed_this_invocation"],
            )

    def test_the_failure_is_on_the_outcome_as_well_as_in_the_file(self):
        """A caller driving the runner should not have to read the file back."""
        transport = self._judge_failure((101,))
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=(101,), transport=transport)

            failed = summary.failures[0]
            self.assertEqual(2 * PROMPT_TOKENS, failed.tokens.prompt_tokens)
            self.assertEqual(2 * TOKENS_PER_CALL, failed.total_tokens)
            self.assertEqual(summary.tokens_failed.billed, failed.total_tokens)
            self.assertEqual(
                summary.tokens_consumed.billed,
                summary.tokens_charged.billed + summary.tokens_failed.billed,
            )

    def test_a_reused_case_is_not_charged_and_is_still_costable(self):
        """A re-run consumes nothing, and the set's own cost is still readable.

        The split under ``reused`` is what stops a re-run erasing what the
        results cost to produce: this invocation consumed no tokens, so its own
        prompt and completion totals are zero, and the figures that turn the
        reused results into a price are carried beside them.
        """
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp)
            second, _ = bench(tmp)
            tokens = self._tokens(second)

            self.assertEqual(0, tokens["spent_this_invocation"])
            self.assertEqual(0, tokens["consumed_this_invocation"])
            self.assertEqual(0, tokens["prompt_tokens"])
            self.assertEqual(
                len(CASE_SET) * TOKENS_PER_CASE, tokens["reused_from_cache"]
            )
            self.assertEqual(
                len(CASE_SET) * CALLS_PER_CASE * PROMPT_TOKENS,
                tokens["reused"]["prompt_tokens"],
            )
            self.assertEqual(
                len(CASE_SET) * CALLS_PER_CASE * COMPLETION_TOKENS,
                tokens["reused"]["completion_tokens"],
            )

    def test_each_invocation_records_the_window_it_ran_in(self):
        """Peak hours are a property of when the calls were made.

        The window has to survive in the history as well as in ``run.json``,
        because ``run.json`` is overwritten by the next invocation — and it is
        the earlier invocation whose price band can no longer be worked out any
        other way.
        """
        with tempfile.TemporaryDirectory() as tmp:
            first, _ = bench(
                tmp, cases=CASE_SET, now=lambda: "2026-01-01T00:00:00+00:00"
            )
            bench(tmp, cases=(105,), now=lambda: "2026-01-02T00:00:00+00:00")

            history = runner.read_json(first.run_dir / runner.INVOCATIONS_FILE)

            self.assertEqual(2, len(history))
            for entry in history:
                with self.subTest(started_at=entry["started_at"]):
                    self.assertTrue(entry["started_at"])
                    self.assertTrue(entry["ended_at"])


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------
class ProvenanceTests(unittest.TestCase):
    """A number produced from uncommitted code cannot be reproduced by anyone."""

    def test_a_clean_tree_is_recorded_as_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            self.assertIs(True, summary.provenance["working_tree_clean"])
            self.assertIsNone(summary.provenance["working_tree_status"])

    def test_a_dirty_tree_is_recorded_as_dirty(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, git=git_runner(status=DIRTY_STATUS))

            self.assertIs(False, summary.provenance["working_tree_clean"])
            self.assertEqual(DIRTY_STATUS, summary.provenance["working_tree_status"])
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))
            self.assertIs(False, metadata["working_tree_clean"])

    def test_a_tree_whose_state_is_unknown_does_not_read_as_clean(self):
        """The tri-state matters: git that cannot be asked is not git that said yes."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, git=git_that_cannot_be_asked())

            self.assertIsNone(summary.provenance["working_tree_clean"])
            self.assertNotEqual(True, summary.provenance["working_tree_clean"])
            self.assertEqual("unknown", runner._render_tree_flag(None))

    def test_the_three_tree_states_render_apart(self):
        self.assertEqual("clean", runner._render_tree_flag(True))
        self.assertEqual("DIRTY", runner._render_tree_flag(False))
        self.assertEqual("unknown", runner._render_tree_flag(None))

    def test_the_commit_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            self.assertEqual(COMMIT, summary.provenance["git_commit"])

    def test_an_absent_commit_is_recorded_as_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, git=git_that_cannot_be_asked())
            self.assertIsNone(summary.provenance["git_commit"])

    def test_the_prompts_digest_is_the_prompts_directory_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            self.assertEqual(
                runner.hash_directory(PROMPTS_DIR), summary.provenance["prompts_sha256"]
            )

    def test_the_answer_key_digest_comes_from_the_grader(self):
        """The runner records the digest without ever opening the key itself."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            self.assertEqual(
                grade.answer_key_sha256(), summary.provenance["answer_key_sha256"]
            )
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))
            self.assertEqual(grade.answer_key_sha256(), metadata["answer_key_sha256"])

    def test_the_start_and_end_timestamps_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))
            for field in ("started_at", "ended_at"):
                with self.subTest(field=field):
                    self.assertTrue(metadata[field], "{0} is missing".format(field))
                    self.assertIsInstance(metadata[field], str)

    def test_a_very_long_status_is_bounded(self):
        long_status = "\n".join(" M path/{0}".format(index) for index in range(2000))
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, git=git_runner(status=long_status))
            self.assertLessEqual(
                len(summary.provenance["working_tree_status"]), runner.MAX_STATUS_CHARS
            )

    def test_the_tree_check_ignores_the_runners_own_output(self):
        """The cache is not git-ignored, so it must not make every run look dirty."""
        arguments = runner._status_arguments(runner.RUNS_DIR)
        self.assertIn(":(exclude)runs", arguments)

    def test_a_cache_outside_the_repository_needs_no_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            arguments = runner._status_arguments(Path(tmp))
            self.assertNotIn(":(exclude){0}".format(tmp), arguments)
            self.assertEqual(("status", "--porcelain"), arguments)

    def test_the_metadata_puts_provenance_at_the_top_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))
            for field in (
                "model",
                "git_commit",
                "working_tree_clean",
                "working_tree_status",
                "prompts_dir",
                "prompts_sha256",
                "answer_key_sha256",
                "started_at",
                "ended_at",
                "stop_reason",
                "token_budget",
                "concurrency",
                "tokens",
                "cases",
                "failures",
            ):
                with self.subTest(field=field):
                    self.assertIn(field, metadata)


# --------------------------------------------------------------------------
# Digests and cache layout
# --------------------------------------------------------------------------
class DigestTests(unittest.TestCase):
    """The prompts digest changes when the prompts change, and only then."""

    def _directory(self, tmp, files):
        root = Path(tmp) / "prompts"
        root.mkdir()
        for name, text in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return root

    def test_the_digest_changes_when_a_prompt_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._directory(tmp, {"a.md": "one"})
            before = runner.hash_directory(root)
            (root / "a.md").write_text("two", encoding="utf-8")
            self.assertNotEqual(before, runner.hash_directory(root))

    def test_the_digest_changes_when_a_prompt_is_renamed(self):
        """A move changes what was handed to the model even when no byte did."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._directory(tmp, {"a.md": "one"})
            before = runner.hash_directory(root)
            (root / "a.md").rename(root / "b.md")
            self.assertNotEqual(before, runner.hash_directory(root))

    def test_editor_and_interpreter_artefacts_do_not_change_the_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._directory(tmp, {"a.md": "one"})
            before = runner.hash_directory(root)
            (root / ".DS_Store").write_bytes(b"\x00\x01")
            (root / "a.pyc").write_bytes(b"\x00\x01")
            self.assertEqual(before, runner.hash_directory(root))

    def test_a_missing_prompts_directory_is_an_error_not_an_empty_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(runner.BenchmarkError):
                runner.hash_directory(Path(tmp) / "nowhere")

    def test_the_digest_is_stable_across_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._directory(tmp, {"a.md": "one", "nested/b.md": "two"})
            self.assertEqual(runner.hash_directory(root), runner.hash_directory(root))


class ModelSlugTests(unittest.TestCase):
    """One directory per model, and a model id can never name a parent."""

    def test_a_slash_becomes_a_dash(self):
        self.assertEqual("deepseek-deepseek-flash", runner.model_slug("deepseek/deepseek-flash"))

    def test_a_plain_id_is_unchanged(self):
        self.assertEqual("hy4-preview", runner.model_slug("hy4-preview"))

    def test_an_id_with_nothing_usable_is_refused(self):
        for value in ("", "///", "...", "   "):
            with self.subTest(model=value):
                with self.assertRaises(runner.BenchmarkError):
                    runner.model_slug(value)

    def test_an_id_that_names_a_parent_directory_is_refused(self):
        for value in (".", "..", "...", "/"):
            with self.subTest(model=value):
                with self.assertRaises(runner.BenchmarkError):
                    runner.model_slug(value)

    def test_a_slug_never_contains_a_path_separator(self):
        """A model id must not be able to write outside its own directory."""
        for value in ("../etc", "a/b", "a\\b", "./a"):
            with self.subTest(model=value):
                slug = runner.model_slug(value)
                self.assertNotIn("/", slug)
                self.assertNotIn("\\", slug)
                self.assertFalse(slug.startswith("."), "{0!r} starts with a dot".format(slug))

    def test_the_run_directory_is_the_slug_under_the_runs_directory(self):
        self.assertEqual(
            Path("/tmp/runs/hy4-preview"), runner.run_directory(Path("/tmp/runs"), "hy4-preview")
        )

    def test_the_case_files_are_zero_padded_five_digits(self):
        self.assertEqual("case-00101.json", runner.case_cache_path(Path("/x"), 101).name)
        self.assertEqual("case-00101.transcript.json", runner.transcript_path(Path("/x"), 101).name)
        self.assertEqual("run.json", runner.metadata_path(Path("/x")).name)


class CacheReadTests(unittest.TestCase):
    """Reading a cache file back is deliberately forgiving, and never guesses."""

    def test_an_absent_file_reads_as_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(runner.read_json(Path(tmp) / "nothing.json"))
            self.assertIsNone(runner.load_cached(Path(tmp), 101))

    def test_a_directory_is_not_a_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(runner.read_json(Path(tmp)))

    def test_a_decimal_amount_comes_back_as_a_decimal(self):
        """The same hook the loader uses, so 8.05 stays 8.05."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "document.json"
            path.write_text('{"amount": 8.05}', encoding="utf-8")
            self.assertEqual(Decimal("8.05"), runner.read_json(path)["amount"])
            self.assertIsInstance(runner.read_json(path)["amount"], Decimal)

    def test_writing_and_reading_a_document_round_trips_a_decimal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "document.json"
            runner.write_json(path, {"amount": Decimal("65.13")})
            self.assertIn("65.13", path.read_text(encoding="utf-8"))
            self.assertEqual(Decimal("65.13"), runner.read_json(path)["amount"])

    def test_an_empty_run_directory_has_no_cached_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([], runner.cached_case_numbers(Path(tmp)))

    def test_an_unusable_document_is_absent_rather_than_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            for text in ("[]", '"a string"', "{}", '{"case_no": 101}'):
                with self.subTest(text=text):
                    runner.case_cache_path(Path(tmp), 101).write_text(text, encoding="utf-8")
                    self.assertIsNone(runner.load_cached(Path(tmp), 101))


# --------------------------------------------------------------------------
# Concurrency
# --------------------------------------------------------------------------
class ConcurrencyTests(unittest.TestCase):
    """Opt-in, and proven: the limiter is shared state the moment threads appear."""

    def test_the_default_is_one(self):
        self.assertEqual(1, runner.DEFAULT_CONCURRENCY)
        import inspect

        signature = inspect.signature(runner.run_benchmark)
        self.assertEqual(
            runner.DEFAULT_CONCURRENCY, signature.parameters["concurrency"].default
        )

    def test_a_concurrency_below_one_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(runner.BenchmarkError):
                bench(tmp, concurrency=0)

    def test_concurrent_cases_each_complete_exactly_once(self):
        cases = (101, 102, 103, 105, 110)
        with tempfile.TemporaryDirectory() as tmp:
            summary, transport = bench(tmp, cases=cases, concurrency=3)

            self.assertEqual(sorted(cases), sorted(summary.completed_cases))
            self.assertEqual(len(cases), len(summary.outcomes))
            self.assertEqual(sorted(cases), transport.cases_called())
            self.assertEqual(len(cases) * CALLS_PER_CASE, transport.calls())
            self.assertEqual(sorted(cases), runner.cached_case_numbers(summary.run_dir))
            self.assertEqual(len(cases), summary.report.exact_matches)

    def test_concurrent_cases_print_one_line_each(self):
        """Two per case at any concurrency: announced once, reported once.

        The start line is emitted on the thread that owns the queue rather than
        from inside a worker, which is what keeps the count exact however many
        cases are in flight at once.
        """
        lines = []
        cases = (101, 102, 103, 105)
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp, cases=cases, concurrency=4, progress=lines.append)
        started = [line for line in lines if line.endswith("started")]
        done = [line for line in lines if not line.endswith("started")]
        self.assertEqual(len(cases), len(started))
        self.assertEqual(len(cases), len(done))
        self.assertEqual(
            sorted(cases),
            sorted(int(line.split("case ")[1].split()[0]) for line in done),
        )

    # -- the limiter itself ------------------------------------------------
    def _run_together(self, client, threads):
        """Fire ``threads`` calls at once and wait for all of them.

        The barriers carry a timeout so a regression fails the test loudly
        rather than hanging the suite.
        """
        start = threading.Barrier(threads, timeout=30)

        def call():
            start.wait()
            client.complete("system", "user")

        workers = [threading.Thread(target=call) for _ in range(threads)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

    def test_n_threads_calling_together_do_not_exceed_the_configured_rate(self):
        """Ten callers at 60 requests a minute must take nine full intervals.

        The interval is the gap between consecutive requests from this client,
        so nine gaps is the floor however the threads interleave. With a virtual
        clock the answer is exact rather than approximate.
        """
        threads = 10
        interval = 1.0
        clock = VirtualClock()
        client = llm.LLMClient(
            model=MODEL,
            api_key=FAKE_KEY,
            requests_per_minute=60,
            transport=lambda url, headers, body, timeout: llm.HttpResult(200, b"{}"),
            clock=clock.clock,
            sleep=clock.sleep,
        )

        self._run_together(client, threads)

        self.assertEqual(
            [interval] * (threads - 1),
            clock.sleeps,
            "the limiter let callers through together",
        )
        self.assertEqual(interval * (threads - 1), clock.now)

    def test_the_same_workload_goes_red_against_an_unguarded_limiter(self):
        """The guard is what holds, and this is the interleaving it prevents.

        The barrier separates the read of ``_last_request_at`` from the write,
        so every caller reads the same stale timestamp and none of them waits.
        That is a demonstration rather than a plausible implementation: it is
        the reason the assertion above is not vacuous, and it is why the flag
        does not ship without this pair of tests.
        """
        threads = 10
        interval = 1.0
        clock = VirtualClock()
        barrier = threading.Barrier(threads, timeout=30)

        class Unguarded(llm.LLMClient):
            def _respect_rate_limit(self) -> None:
                if self._minimum_interval <= 0:
                    return
                observed = self._last_request_at
                barrier.wait()
                if observed is not None:
                    remaining = self._minimum_interval - (self._clock() - observed)
                    if remaining > 0:
                        self._sleep(remaining)
                self._last_request_at = self._clock()

        client = Unguarded(
            model=MODEL,
            api_key=FAKE_KEY,
            requests_per_minute=60,
            transport=lambda url, headers, body, timeout: llm.HttpResult(200, b"{}"),
            clock=clock.clock,
            sleep=clock.sleep,
        )

        self._run_together(client, threads)

        self.assertNotEqual(
            [interval] * (threads - 1),
            clock.sleeps,
            "the unguarded limiter held the rate, so the test above proves nothing",
        )
        self.assertEqual([], clock.sleeps)

    def test_the_limiter_does_not_serialise_the_transport_call(self):
        """Only the wait is inside the lock; the request is not."""
        source = (PROJECT_ROOT / "tribunal" / "llm.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        holder = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_respect_rate_limit":
                holder = node
        self.assertIsNotNone(holder, "_respect_rate_limit is gone")

        calls = [
            node.func.attr
            for node in ast.walk(holder)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        self.assertNotIn("_transport", calls, "the transport call moved inside the limiter")
        self.assertIn("_clock", calls)

    def test_the_lock_is_taken_before_the_read(self):
        """A guard that wrapped only the write would still let callers through."""
        source = (PROJECT_ROOT / "tribunal" / "llm.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        holder = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_respect_rate_limit"
        )

        lock_lines = [
            node.lineno for node in ast.walk(holder) if isinstance(node, ast.With)
        ]
        self.assertTrue(lock_lines, "_respect_rate_limit takes no lock")

        read_lines = [
            node.lineno
            for node in ast.walk(holder)
            if isinstance(node, ast.If)
            and any(
                isinstance(inner, ast.Attribute) and inner.attr == "_last_request_at"
                for inner in ast.walk(node)
            )
        ]
        self.assertTrue(read_lines, "the limiter does not read _last_request_at")
        self.assertLess(
            min(lock_lines),
            min(read_lines),
            "the lock is entered after the timestamp is read",
        )


# --------------------------------------------------------------------------
# Comparing cached runs
# --------------------------------------------------------------------------
class CompareTests(unittest.TestCase):
    """One table off disk. No model is called, because none needs to be."""

    def _two_runs(self, tmp):
        runs = Path(tmp) / "runs"
        for model in (MODEL, OTHER_MODEL):
            transport = ScriptedTransport(produced_from_key(answer_key()))
            bench(tmp, cases=WIDER_SET, model=model, transport=transport, runs_dir=runs)
        return runs

    def test_two_cached_runs_are_tabulated_without_a_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = self._two_runs(tmp)
            rows = runner.collect_comparison(runs)

            self.assertEqual(sorted([MODEL, OTHER_MODEL]), sorted(row.model for row in rows))
            for row in rows:
                with self.subTest(model=row.model):
                    self.assertEqual(len(WIDER_SET), row.cases_graded)
                    self.assertEqual(len(WIDER_SET), row.exact_matches)
                    self.assertEqual(len(WIDER_SET) * TOKENS_PER_CASE, row.total_tokens)
                    self.assertIsNotNone(row.mean_latency_seconds)

    def test_the_table_carries_accuracy_calibration_latency_and_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = self._two_runs(tmp)
            table = runner.render_comparison(runner.collect_comparison(runs))

            for header in ("model", "tree", "cases", "exact", "esc", "prec", "rec", "over",
                           "under", "s/case", "tokens"):
                with self.subTest(header=header):
                    self.assertIn(header, table)
            self.assertIn("{0}/{1}".format(len(WIDER_SET), len(WIDER_SET)), table)

    def test_the_table_reports_the_four_fields_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = self._two_runs(tmp)
            rows = runner.collect_comparison(runs)
            for row in rows:
                with self.subTest(model=row.model):
                    self.assertEqual(
                        sorted(grade.GRADED_FIELDS), sorted(row.field_correct)
                    )
                    for field in grade.GRADED_FIELDS:
                        self.assertEqual(len(WIDER_SET), row.field_correct[field])

    def test_the_escalation_block_is_present_and_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = self._two_runs(tmp)
            row = runner.collect_comparison(runs)[0]

            self.assertEqual(Decimal("0.172") * 100, row.target_rate)
            self.assertEqual(Decimal("50.0"), row.escalation_rate)
            self.assertEqual(Decimal("1"), row.precision)
            self.assertEqual(Decimal("1"), row.recall)
            self.assertEqual(0, row.over_escalations)
            self.assertEqual(0, row.under_escalations)

    def test_the_escalation_block_knows_its_set_is_not_the_whole_corpus(self):
        # The intersection of two partial runs is a selected set, so its rates
        # may not be compared to the corpus base rate and the target is not
        # printed beside them. Only the counts survive subsetting.
        with tempfile.TemporaryDirectory() as tmp:
            runs = self._two_runs(tmp)
            row = runner.collect_comparison(runs)[0]

            self.assertFalse(row.grades_full_corpus)
            self.assertEqual(WIDER_SET, row.graded_cases)

            table = runner.render_comparison([row])
            self.assertIn("not the whole corpus", table)
            self.assertIn("101, 105, 110, 207", table)
            self.assertIn("never summed", table)
            self.assertNotIn("17.2%", table)
            self.assertNotIn("target;", table)

    def test_a_full_corpus_comparison_prints_the_target(self):
        key = answer_key()
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            bench(tmp, cases=sorted(key), runs_dir=runs)
            rows = runner.collect_comparison(runs)

            self.assertTrue(rows[0].grades_full_corpus)
            self.assertEqual(tuple(sorted(key)), rows[0].graded_cases)

            table = runner.render_comparison(rows)
            self.assertIn("against the 17.2% target", table)
            self.assertNotIn("not the whole corpus", table)

    def test_over_and_under_escalation_are_never_summed_into_one_number(self):
        table = runner.render_comparison([])
        self.assertIn("No cached runs found", table)

        with tempfile.TemporaryDirectory() as tmp:
            runs = self._two_runs(tmp)
            rendered = runner.render_comparison(runner.collect_comparison(runs))
            self.assertIn("never summed", rendered)

    def test_the_tree_flag_is_a_column(self):
        """A row whose tree was dirty carries an accuracy nobody can reproduce."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            bench(tmp, cases=WIDER_SET, runs_dir=runs, git=git_runner(status=DIRTY_STATUS))
            table = runner.render_comparison(runner.collect_comparison(runs))
            self.assertIn("DIRTY", table)

    def test_an_unknown_tree_does_not_read_as_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            bench(tmp, cases=WIDER_SET, runs_dir=runs, git=git_that_cannot_be_asked())
            table = runner.render_comparison(runner.collect_comparison(runs))
            self.assertIn("unknown", table)
            self.assertNotIn("clean", table)

    def test_the_comparison_uses_the_cases_both_runs_hold(self):
        """A table scoring one model over 29 cases and another over 11 is not a comparison."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            bench(tmp, cases=WIDER_SET, runs_dir=runs)
            bench(tmp, cases=(101, 105), model=OTHER_MODEL, runs_dir=runs)

            rows = runner.collect_comparison(runs)
            by_model = {row.model: row for row in rows}

            self.assertEqual(sorted([MODEL, OTHER_MODEL]), sorted(by_model))
            for model in (MODEL, OTHER_MODEL):
                with self.subTest(model=model):
                    self.assertEqual(2, by_model[model].cases_graded)
            # Each row still says how much it holds, so a model that covered
            # less of the corpus is visible rather than hidden.
            self.assertEqual(len(WIDER_SET), by_model[MODEL].cases_cached)
            self.assertEqual(2, by_model[OTHER_MODEL].cases_cached)

    def test_an_empty_runs_directory_says_so_rather_than_printing_a_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([], runner.collect_comparison(Path(tmp) / "runs"))
            self.assertIn("No cached runs found", runner.render_comparison([]))

    def test_comparing_makes_no_model_call(self):
        """The point of the table is that it costs nothing to produce."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = self._two_runs(tmp)

            with mock.patch.object(runner, "_default_client_factory") as build:
                table = runner.render_comparison(runner.collect_comparison(runs))

            build.assert_not_called()
            self.assertIn(MODEL, table)
            self.assertIn(OTHER_MODEL, table)

    def test_a_row_reads_the_tree_flag_from_its_own_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            bench(tmp, cases=WIDER_SET, runs_dir=runs)
            row = runner.collect_comparison(runs)[0]
            self.assertIs(True, row.working_tree_clean)


# --------------------------------------------------------------------------
# Isolation
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Staleness: a cached result is evidence about the code that produced it
# --------------------------------------------------------------------------
class StalenessTests(unittest.TestCase):
    """A cached result the code has moved past must be labelled, not scored away.

    Nothing here re-runs a case and nothing here touches the real cache under
    ``runs/``. A bench writes real entries, and one entry's recorded brief
    digest is then replaced to stand in for a result an earlier version of the
    brief produced. That is the situation the check exists to name, and it is
    what the real cache under ``runs/`` holds: results produced by more than one
    version of the brief, sitting in one directory, with nothing on their face
    saying so.
    """

    def _cached_run(self, tmp):
        bench(tmp, cases=CASE_SET)
        return run_dir_of(tmp)

    def _make_stale(self, run_dir, case_no):
        """Give one cached entry the digest of a brief this code does not build."""
        document = runner.load_cached(run_dir, case_no)
        document["brief_sha256"] = "0" * 64
        runner.write_json(runner.case_cache_path(run_dir, case_no), document)

    def test_a_cached_case_whose_brief_still_matches_reports_current(self):
        """The check is per case, and the checker has to be able to answer both
        channels: the brief digest comes from the builder, and the prompt digests
        come from the case's own transcript, so it is built with the directory it
        is reading.
        """
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            staleness = runner.brief_staleness(run_dir, CASE_SET)
            checker = runner.BriefStaleness(run_dir=run_dir)

            self.assertTrue(staleness.checked, "the check must say it was made")
            self.assertEqual((), staleness.stale)
            self.assertEqual((), staleness.unknown)
            self.assertFalse(staleness.mixed)
            for case_no in CASE_SET:
                with self.subTest(case=case_no):
                    self.assertEqual(
                        grade.STALENESS_CURRENT,
                        checker.status_of(case_no, runner.load_cached(run_dir, case_no)),
                    )

    def test_the_digest_it_rebuilds_is_the_one_the_pipeline_recorded(self):
        """A check against anything else would report a false staleness."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            for case_no in CASE_SET:
                with self.subTest(case=case_no):
                    self.assertEqual(
                        runner.load_cached(run_dir, case_no)["brief_sha256"],
                        runner.current_brief_sha256(case_no),
                    )

    def test_a_cached_case_whose_brief_has_changed_reports_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            stale_case = CASE_SET[1]
            self._make_stale(run_dir, stale_case)

            staleness = runner.brief_staleness(run_dir, CASE_SET)

            self.assertEqual((stale_case,), staleness.stale)
            self.assertEqual((), staleness.unknown)
            self.assertTrue(staleness.mixed)
            # The neighbours are untouched by it: a mixed set, not a stale set.
            self.assertEqual(
                grade.STALENESS_CURRENT,
                runner.BriefStaleness(run_dir=run_dir).status_of(
                    CASE_SET[0], runner.load_cached(run_dir, CASE_SET[0])
                ),
            )

    def test_the_check_compares_the_brief_it_builds_and_not_a_constant(self):
        """The digest must come from the builder, or the check proves nothing.

        A checker that answers differently for every case is what "the code has
        moved on" looks like from the cache's point of view, and every cached
        entry must then come back stale.
        """
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            checker = runner.BriefStaleness(digest=lambda case_no: "f" * 64)

            staleness = runner.brief_staleness(run_dir, CASE_SET, checker)

            self.assertEqual(tuple(sorted(CASE_SET)), staleness.stale)

    def test_a_brief_that_cannot_be_rebuilt_is_unknown_and_not_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            checker = runner.BriefStaleness(digest=lambda case_no: None)

            staleness = runner.brief_staleness(run_dir, CASE_SET, checker)

            self.assertEqual((), staleness.stale)
            self.assertEqual(tuple(sorted(CASE_SET)), staleness.unknown)
            self.assertTrue(
                staleness.mixed,
                "an unverifiable result breaks the single-measurement claim too",
            )

    def test_an_entry_written_before_the_digest_was_recorded_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            document = runner.load_cached(run_dir, CASE_SET[0])
            document.pop("brief_sha256")
            runner.write_json(runner.case_cache_path(run_dir, CASE_SET[0]), document)

            staleness = runner.brief_staleness(run_dir, CASE_SET)

            self.assertEqual((CASE_SET[0],), staleness.unknown)
            self.assertEqual((), staleness.stale)

    def test_a_case_with_no_cache_entry_is_not_checked_at_all(self):
        """There is no result to be stale, so it is neither current nor stale."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            staleness = runner.brief_staleness(run_dir, [*CASE_SET, 104])

            self.assertEqual((), staleness.stale)
            self.assertEqual((), staleness.unknown)

    def test_a_reused_stale_result_says_so_on_its_progress_line(self):
        """The reader watching the terminal is the one who can still re-run."""
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp, cases=CASE_SET)
            run_dir = run_dir_of(tmp)
            self._make_stale(run_dir, CASE_SET[0])

            lines = []
            summary, _ = bench(tmp, cases=CASE_SET, progress=lines.append)

            stale_lines = [line for line in lines if "stale" in line]
            self.assertEqual(1, len(stale_lines))
            self.assertIn(str(CASE_SET[0]), stale_lines[0])
            self.assertEqual((CASE_SET[0],), summary.report.staleness.stale)


class StaleGradingTests(unittest.TestCase):
    """A mixed set is not one run, and must not be tabulated as though it were.

    The assertions on rendered text below are assertions about the deliverable
    itself. Naming the stale case and stating the caveat is the requirement, and
    the rendered report is where that requirement is met or not met.
    """

    def _cached_run(self, tmp):
        bench(tmp, cases=CASE_SET)
        run_dir = run_dir_of(tmp)
        document = runner.load_cached(run_dir, CASE_SET[1])
        document["brief_sha256"] = "0" * 64
        runner.write_json(runner.case_cache_path(run_dir, CASE_SET[1]), document)
        return run_dir

    def test_the_grader_reports_the_stale_case_by_name_and_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            report = runner.grade_run(run_dir, cases=CASE_SET)

            self.assertEqual((CASE_SET[1],), report.staleness.stale)
            self.assertEqual((), report.staleness.unknown)
            self.assertTrue(report.staleness.mixed)

    def test_a_mixed_set_says_its_exact_match_is_not_one_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            text = grade.render_report(runner.grade_run(run_dir, cases=CASE_SET))

            self.assertIn("| {0} |".format(CASE_SET[1]), text, "the stale case is not in the table")
            # The cell names which digest moved. A bare "**STALE**" here would
            # be the merge the report is required not to make: the facts and the
            # instructions are different findings.
            self.assertIn("| **STALE (brief)** |", text)
            self.assertIn("mixed set is not one run", text)
            self.assertIn("not a single measurement", text)
            self.assertIn("**(mixed set — not one measurement)**", text)

    def test_a_set_of_current_results_says_it_is_one_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp, cases=CASE_SET)
            text = grade.render_report(runner.grade_run(run_dir_of(tmp), cases=CASE_SET))

            self.assertIn("one measurement", text)
            self.assertNotIn("mixed set is not one run", text)

    def test_a_report_that_checked_nothing_claims_nothing(self):
        """Silence, not a reassuring zero, when no brief was rebuilt."""
        report = grade.grade(grade.key_as_produced(answer_key()), answer_key())
        text = grade.render_report(report)

        self.assertFalse(report.staleness.checked)
        self.assertNotIn("one measurement", text)
        self.assertNotIn("mixed set", text)
        self.assertNotIn("| exact | brief |", text)

    def test_the_comparison_table_carries_the_stale_count_and_names_the_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            bench(tmp, cases=CASE_SET, runs_dir=runs)
            run_dir = runner.run_directory(runs, MODEL)
            document = runner.load_cached(run_dir, CASE_SET[0])
            document["brief_sha256"] = "0" * 64
            runner.write_json(runner.case_cache_path(run_dir, CASE_SET[0]), document)

            row = runner.collect_comparison(runs)[0]
            table = runner.render_comparison([row])

            self.assertEqual((CASE_SET[0],), row.staleness.stale)
            # The column is headed for what it answers about the cache rather
            # than for one of the two channels. A heading naming the brief, or
            # naming the prompts, would be the merge this report must not make.
            self.assertIn("cached", table.splitlines()[0])
            self.assertIn("brief moved", table)
            self.assertIn(str(CASE_SET[0]), table)
            self.assertIn("mixed set is not one run", table)

    def test_the_stale_count_is_not_a_zero_when_nobody_checked(self):
        row = runner.ComparisonRow(
            model=MODEL,
            working_tree_clean=True,
            cases_graded=1,
            cases_cached=1,
            graded_cases=(101,),
            grades_full_corpus=False,
            exact_matches=1,
            field_correct={name: 1 for name in grade.GRADED_FIELDS},
            escalation_rate=None,
            target_rate=Decimal("17.2"),
            precision=None,
            recall=None,
            over_escalations=0,
            under_escalations=0,
            indeterminate_ruled_confidently=0,
            mean_latency_seconds=None,
            total_tokens=0,
        )
        self.assertFalse(row.staleness.checked)
        self.assertIn("n/a", runner.render_comparison([row]))


class TwoChannelStalenessTests(unittest.TestCase):
    """The brief and the prompts are two findings, and never one word.

    A moved brief means the facts the agents were handed changed. A moved prompt
    means their instructions changed. They call for different responses — go and
    re-read the case, or go and re-read what the agents were told to do with it —
    so a report saying only "stale" leaves the reader unable to tell which one to
    look at. These tests pin the separation on every surface that reports it.

    What each channel reads is what makes them two. The brief channel reads the
    cache entry's own ``brief_sha256``. The prompt channel reads the **calls**:
    every transcript entry records the digest of the system prompt that call was
    given, and an advocate's entry records the brief's digest beside it, so what
    an agent was handed is compared per role against what this code renders now.
    That is why a prompt file no recorded call used is not a finding about any
    case, and why the cache entry's own ``prompts_sha256`` -- a digest of the
    whole directory -- is deliberately not consulted. It is still recorded, as
    history.

    The third answer is the one that matters most here: a call whose system
    prompt digest was never recorded, or whose transcript cannot be read at all,
    is not a call whose instructions are known to match. It is `unknown`, which
    is not a synonym for `current`.

    Nothing here re-runs a case and nothing here touches the real cache under
    ``runs/`` or the real prompt files under ``prompts/``.
    """

    def _cached_run(self, tmp):
        bench(tmp, cases=CASE_SET)
        return run_dir_of(tmp)

    def _set_digest(self, run_dir, case_no, field, value):
        """Record a digest this code does not compute, in one channel only."""
        document = runner.load_cached(run_dir, case_no)
        document[field] = value
        runner.write_json(runner.case_cache_path(run_dir, case_no), document)

    def _checker(self, run_dir, prompts_dir=PROMPTS_DIR):
        """A checker that can answer both channels for one run directory."""
        return runner.BriefStaleness(run_dir=run_dir, prompts_dir=prompts_dir)

    def _move_recorded_prompt(self, run_dir, case_no, value="0" * 64):
        """Give every recorded judge call a prompt digest this code does not render.

        This is what a moved prompt looks like from the transcript's point of
        view, and the transcript is where what an agent was given is recorded.
        """
        path = runner.transcript_path(run_dir, case_no)
        payload = runner.read_json(path)
        for entry in payload["entries"]:
            if entry["role"] == transcript.ROLE_JUDGE:
                entry["system_sha256"] = value
        runner.write_json(path, payload)

    def _drop_recorded_prompt_digest(self, run_dir, case_no):
        """Remove the digest a recorded judge call would have carried."""
        path = runner.transcript_path(run_dir, case_no)
        payload = runner.read_json(path)
        for entry in payload["entries"]:
            if entry["role"] == transcript.ROLE_JUDGE:
                entry.pop("system_sha256", None)
        runner.write_json(path, payload)

    def test_a_prompt_that_moved_reports_stale_and_names_the_prompt(self):
        """A one-byte change to a prompt a recorded call was given.

        The change is made to a **copy** of the prompt set and the run is made
        against that copy, so the prompt the recorded call was given really is
        the one that moved. The shipped files are not touched.

        The judge prompt is one file every case's judge call was given, so the
        byte that moved moves it for all three cases, not for one: the prompt
        channel asks what each recorded call was handed, and all three were
        handed the same file.
        """
        with tempfile.TemporaryDirectory() as tmp:
            prompts = prompts_copy(tmp)
            bench(tmp, cases=CASE_SET, prompts_dir=prompts)
            run_dir = run_dir_of(tmp)
            case_no = CASE_SET[1]
            move_one_byte(prompts / pipeline.JUDGE_PROMPT_FILE)

            checker = self._checker(run_dir, prompts)
            staleness = runner.brief_staleness(run_dir, CASE_SET, checker)

            self.assertEqual(tuple(sorted(CASE_SET)), staleness.stale)
            self.assertEqual((), staleness.stale_brief)
            self.assertEqual(tuple(sorted(CASE_SET)), staleness.stale_prompts)
            self.assertEqual((grade.MOVED_PROMPTS,), staleness.moved_for(case_no))

            text = grade.render_report(
                runner.grade_run(run_dir, cases=CASE_SET, checker=checker)
            )
            self.assertIn("| **STALE (prompt)** |", text)
            self.assertIn(
                "The prompts have moved for 3 of 3: 101, 102, 103",
                text,
            )
            self.assertNotIn(
                "The brief has moved",
                text,
                "a moved prompt was reported as a moved brief",
            )

    def test_a_brief_that_moved_reports_stale_and_names_the_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            case_no = CASE_SET[1]
            self._set_digest(run_dir, case_no, "brief_sha256", "0" * 64)

            staleness = runner.brief_staleness(run_dir, CASE_SET)

            self.assertEqual((case_no,), staleness.stale_brief)
            self.assertEqual((), staleness.stale_prompts)
            self.assertEqual((grade.MOVED_BRIEF,), staleness.moved_for(case_no))

            text = grade.render_report(runner.grade_run(run_dir, cases=CASE_SET))
            self.assertIn("| **STALE (brief)** |", text)
            self.assertNotIn(
                "The prompts have moved",
                text,
                "a moved brief was reported as a moved prompt",
            )

    def test_a_run_where_both_digests_moved_reports_both(self):
        """One case, both channels, and the report keeps them apart.

        The brief is moved through the cache entry that records it. The prompt is
        moved through the **transcript** entry the call is recorded in, so the
        comparison table -- which reads the shipped prompt set through its own
        checker -- sees it too.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            bench(tmp, cases=CASE_SET, runs_dir=runs)
            run_dir = runner.run_directory(runs, MODEL)
            case_no = CASE_SET[1]
            self._set_digest(run_dir, case_no, "brief_sha256", "0" * 64)
            self._move_recorded_prompt(run_dir, case_no)

            staleness = runner.brief_staleness(run_dir, CASE_SET)

            self.assertEqual((case_no,), staleness.stale)
            self.assertEqual((case_no,), staleness.stale_brief)
            self.assertEqual((case_no,), staleness.stale_prompts)
            self.assertEqual(
                (grade.MOVED_BRIEF, grade.MOVED_PROMPTS), staleness.moved_for(case_no)
            )

            text = grade.render_report(runner.grade_run(run_dir, cases=CASE_SET))
            self.assertIn("| **STALE (brief, prompt)** |", text)
            self.assertIn("The brief has moved for 1 of 3", text)
            self.assertIn("The prompts have moved for 1 of 3", text)

            table = runner.render_comparison(runner.collect_comparison(runs))
            self.assertIn("1 stale (brief, prompt)", table)
            self.assertIn("brief moved: {0}".format(case_no), table)
            self.assertIn("prompts moved: {0}".format(case_no), table)

    def test_a_recorded_call_with_no_prompt_digest_reports_unknown_not_current(self):
        """An entry whose instructions cannot be established is not a current one.

        The cache entry is untouched. What is missing is the digest the call
        itself would have carried, and that is the only thing that can say which
        prompt it was given.
        """
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            case_no = CASE_SET[0]
            self._drop_recorded_prompt_digest(run_dir, case_no)

            staleness = runner.brief_staleness(run_dir, CASE_SET)

            self.assertEqual((), staleness.stale)
            self.assertEqual((case_no,), staleness.unknown)
            self.assertEqual((case_no,), staleness.unchecked_prompts)
            self.assertTrue(
                staleness.mixed,
                "a result whose prompts cannot be established is not a current one",
            )
            self.assertEqual((), staleness.moved_for(case_no))

            text = grade.render_report(runner.grade_run(run_dir, cases=CASE_SET))
            self.assertIn("| unknown |", text)
            self.assertIn("The prompts digest was not recorded for 1 of 3 results", text)
            self.assertIn("mixed set", text)

    def test_a_prompt_comparison_that_cannot_be_made_is_unknown_not_current(self):
        """A transcript that cannot be read is "cannot tell", not a match."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            checker = runner.BriefStaleness(
                run_dir=run_dir, entries_for=lambda case_no: None
            )

            staleness = runner.brief_staleness(run_dir, CASE_SET, checker)

            self.assertEqual((), staleness.stale)
            self.assertEqual(tuple(sorted(CASE_SET)), staleness.unknown)
            self.assertEqual(tuple(sorted(CASE_SET)), staleness.unchecked_prompts)

    def test_the_directory_digest_is_still_recorded_over_the_whole_prompt_set(self):
        """Kept as history, and it still covers every prompt in the set.

        The prompt channel no longer asks this question -- it compares what each
        recorded call was given -- but the directory digest is what a run still
        records, so a reader of an older cache can see which prompt set produced
        it. The names are read from the pipeline rather than written here, so a
        prompt added to the set is covered without anyone remembering to add it
        to this list.
        """
        self.assertEqual(
            runner.hash_directory(PROMPTS_DIR), runner.current_prompts_sha256(PROMPTS_DIR)
        )
        names = sorted(
            set(pipeline.AGENT_PROMPT_FILES.values()) | set(pipeline.STANCE_FILES.values())
        )
        self.assertGreater(
            len(names), 1, "the digest is taken over a set, not over one file"
        )
        for name in names:
            with self.subTest(prompt=name):
                self.assertTrue((PROMPTS_DIR / name).is_file(), name)

    def test_an_unused_prompt_file_leaves_every_result_current(self):
        """A file no recorded call used is not a finding about any case.

        This is the whole reason the channel compares per role instead of over
        the directory: a prompt added to the set is not a change to what any
        recorded agent was told, so nothing becomes stale because of it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            prompts = prompts_copy(tmp)
            bench(tmp, cases=CASE_SET, prompts_dir=prompts)
            run_dir = run_dir_of(tmp)
            (prompts / "unused.system.md").write_text(
                "A prompt no run has ever asked for.\n", encoding="utf-8"
            )

            checker = self._checker(run_dir, prompts)
            staleness = runner.brief_staleness(run_dir, CASE_SET, checker)

            self.assertEqual((), staleness.stale)
            self.assertEqual((), staleness.unknown)
            for case_no in CASE_SET:
                with self.subTest(case=case_no):
                    self.assertEqual(
                        grade.STALENESS_CURRENT,
                        checker.status_of(case_no, runner.load_cached(run_dir, case_no)),
                    )

    def test_a_one_byte_change_to_any_prompt_a_call_was_given_makes_it_stale(self):
        """The judge prompt, and each stance, on its own.

        The advocate prompt is the template with one stance substituted, so a
        change to either stance file moves the digest of that side's advocate
        prompt only -- and the transcript holds a call for that side, so the
        change is seen.
        """
        names = [pipeline.JUDGE_PROMPT_FILE] + sorted(set(pipeline.STANCE_FILES.values()))
        self.assertGreater(len(names), 1, "the check is over more than one prompt")
        for name in names:
            with self.subTest(prompt=name), tempfile.TemporaryDirectory() as tmp:
                prompts = prompts_copy(tmp)
                bench(tmp, cases=CASE_SET, prompts_dir=prompts)
                run_dir = run_dir_of(tmp)
                move_one_byte(prompts / name)

                staleness = runner.brief_staleness(
                    run_dir, CASE_SET, self._checker(run_dir, prompts)
                )

                self.assertEqual(tuple(sorted(CASE_SET)), staleness.stale)
                self.assertEqual((), staleness.stale_brief)
                self.assertEqual(tuple(sorted(CASE_SET)), staleness.stale_prompts)


def prompts_copy(root, name="prompts"):
    """A byte-identical copy of the shipped prompt set, under ``root``.

    The shipped files are tracked, so a test that edited one would leave the
    repository changed. The run is made against the copy instead, which is what
    makes "the recorded call was given this prompt" true of the copy.
    """
    destination = Path(root) / name
    destination.mkdir(parents=True)
    for source in sorted(PROMPTS_DIR.iterdir()):
        (destination / source.name).write_bytes(source.read_bytes())
    return destination


def move_one_byte(path):
    """Change exactly one byte of a prompt file, and leave it readable text."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    index = next(
        position
        for position, character in enumerate(text)
        if character.isascii() and character.isalpha()
    )
    path.write_text(
        text[:index] + text[index].swapcase() + text[index + 1 :], encoding="utf-8"
    )


class PerCaseProvenanceTests(unittest.TestCase):
    """Provenance in a file the next invocation overwrites is not provenance."""

    def test_every_case_file_records_the_commit_and_the_prompts_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            for case_no in CASE_SET:
                with self.subTest(case=case_no):
                    document = runner.load_cached(summary.run_dir, case_no)
                    self.assertEqual(COMMIT, document["git_commit"])
                    self.assertEqual(
                        runner.hash_directory(PROMPTS_DIR), document["prompts_sha256"]
                    )

    def test_the_case_files_agree_with_the_runs_own_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))
            for case_no in CASE_SET:
                with self.subTest(case=case_no):
                    document = runner.load_cached(summary.run_dir, case_no)
                    self.assertEqual(metadata["git_commit"], document["git_commit"])
                    self.assertEqual(
                        metadata["prompts_sha256"], document["prompts_sha256"]
                    )

    def test_a_tree_that_could_not_be_read_is_recorded_as_unknown_per_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, git=git_that_cannot_be_asked())
            document = runner.load_cached(summary.run_dir, CASE_SET[0])
            self.assertIsNone(document["git_commit"])

    def test_the_commit_a_case_records_is_the_one_that_was_in_force(self):
        other = "deadbeef" * 5
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, git=git_runner(commit=other))
            document = runner.load_cached(summary.run_dir, CASE_SET[0])
            self.assertEqual(other, document["git_commit"])


def _comparison_row(**overrides):
    """A minimal comparison row, for rendering tests that need no run on disk."""
    fields = dict(
        model=MODEL,
        working_tree_clean=True,
        cases_graded=1,
        cases_cached=1,
        graded_cases=(101,),
        grades_full_corpus=False,
        exact_matches=1,
        field_correct={name: 1 for name in grade.GRADED_FIELDS},
        escalation_rate=None,
        target_rate=Decimal("17.2"),
        precision=None,
        recall=None,
        over_escalations=0,
        under_escalations=0,
        indeterminate_ruled_confidently=0,
        mean_latency_seconds=None,
        total_tokens=0,
    )
    fields.update(overrides)
    return runner.ComparisonRow(**fields)


class InterpreterProvenanceTests(unittest.TestCase):
    """Which Python built a brief, recorded beside the digest of that brief.

    The brief carries an unrounded mean distance, so before the accumulation in
    ``facts.track_summary`` was pinned to a plain left-to-right sum, its bytes --
    and therefore ``brief_sha256`` -- were a function of the interpreter as well
    as of the repository. A cache that does not say which interpreter produced
    it cannot be read afterwards: a digest disagreement may be code drift or
    interpreter drift, and once the run is over there is nothing left to tell
    them apart.
    """

    def test_interpreter_version_is_major_dot_minor_dot_micro(self):
        expected = "{0}.{1}.{2}".format(*sys.version_info[:3])
        self.assertEqual(expected, runner.interpreter_version())
        self.assertRegex(runner.interpreter_version(), r"^\d+\.\d+\.\d+$")

    def test_every_case_file_records_the_interpreter_that_built_its_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            for case_no in CASE_SET:
                with self.subTest(case=case_no):
                    document = runner.load_cached(summary.run_dir, case_no)
                    self.assertEqual(
                        runner.interpreter_version(), document["python_version"]
                    )

    def test_the_runs_own_record_carries_the_interpreter_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))
            self.assertEqual(runner.interpreter_version(), metadata["python_version"])

    def test_the_row_collects_the_interpreters_the_cache_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            bench(tmp, cases=CASE_SET, runs_dir=runs)
            run_dir = runner.run_directory(runs, MODEL)

            self.assertEqual(
                (runner.interpreter_version(),),
                runner.collect_comparison(runs)[0].python_versions,
            )

            # A cache that names an older interpreter says so, rather than
            # being silently read as the one running now.
            for case_no in CASE_SET:
                document = runner.load_cached(run_dir, case_no)
                document["python_version"] = "3.9.6"
                runner.write_json(runner.case_cache_path(run_dir, case_no), document)

            self.assertEqual(
                ("3.9.6",), runner.collect_comparison(runs)[0].python_versions
            )

    def test_a_cache_predating_the_field_reports_no_interpreter(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            bench(tmp, cases=CASE_SET, runs_dir=runs)
            run_dir = runner.run_directory(runs, MODEL)
            for case_no in CASE_SET:
                document = runner.load_cached(run_dir, case_no)
                document.pop("python_version")
                runner.write_json(runner.case_cache_path(run_dir, case_no), document)

            self.assertEqual((), runner.collect_comparison(runs)[0].python_versions)

    def test_the_comparison_table_names_the_interpreter_when_it_differs(self):
        table = runner.render_comparison([_comparison_row(python_versions=("2.7.18",))])

        self.assertIn("2.7.18", table)
        self.assertIn(runner.interpreter_version(), table)
        self.assertIn("interpreter drift", table)

    def test_the_comparison_table_is_silent_when_nothing_was_recorded(self):
        """A cache that predates the field says nothing rather than guessing."""
        table = runner.render_comparison([_comparison_row(python_versions=())])

        self.assertNotIn("interpreter drift", table)
        self.assertNotIn("produced under", table)

    def test_the_comparison_table_is_silent_when_the_interpreter_agrees(self):
        row = _comparison_row(python_versions=(runner.interpreter_version(),))
        self.assertNotIn("interpreter drift", runner.render_comparison([row]))


class RunRecordTests(unittest.TestCase):
    """A new invocation must not destroy the record of an earlier one.

    ``run.json`` is the latest invocation's record and is rewritten after every
    case, so it is right for it to describe only its own invocation. What must
    not happen is that the earlier invocation's commit, case list and token
    total exist nowhere afterwards — which is what a single-case re-run of case
    214 did to a 29-case run.
    """

    def test_a_second_invocation_leaves_the_first_ones_record_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, _ = bench(tmp, cases=CASE_SET, now=lambda: "2026-01-01T00:00:00+00:00")
            bench(tmp, cases=(105,), now=lambda: "2026-01-02T00:00:00+00:00")

            history = runner.read_json(first.run_dir / runner.INVOCATIONS_FILE)

            self.assertEqual(2, len(history))
            self.assertEqual(list(CASE_SET), history[0]["cases"]["requested"])
            self.assertEqual(list(CASE_SET), history[0]["cases"]["completed"])
            self.assertEqual([105], history[1]["cases"]["requested"])
            self.assertEqual(
                3 * TOKENS_PER_CASE, history[0]["tokens"]["spent_this_invocation"]
            )
            self.assertEqual(
                TOKENS_PER_CASE, history[1]["tokens"]["spent_this_invocation"]
            )

    def test_run_json_describes_the_invocation_and_not_the_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp, cases=CASE_SET, now=lambda: "2026-01-01T00:00:00+00:00")
            second, _ = bench(tmp, cases=(105,), now=lambda: "2026-01-02T00:00:00+00:00")

            metadata = runner.read_json(runner.metadata_path(second.run_dir))

            # True of the invocation. It is the directory block that stops it
            # being read as a description of the directory.
            self.assertEqual([105], metadata["cases"]["requested"])
            self.assertEqual([105], metadata["cases"]["completed"])
            self.assertEqual("this invocation only", metadata["cases"]["scope"])
            self.assertEqual(
                sorted([*CASE_SET, 105]), metadata["directory"]["cached_cases"]
            )
            self.assertEqual(
                len(CASE_SET) + 1, metadata["directory"]["cached_case_count"]
            )
            self.assertTrue(
                metadata["directory"]["holds_results_from_earlier_invocations"]
            )

    def test_a_directory_holding_only_this_invocations_cases_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))

            self.assertEqual(sorted(CASE_SET), metadata["directory"]["cached_cases"])
            self.assertFalse(
                metadata["directory"]["holds_results_from_earlier_invocations"]
            )

    def test_the_history_holds_one_entry_per_invocation_not_per_case(self):
        """``run.json`` is rewritten after every case; the history must not be."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            history = runner.read_json(summary.run_dir / runner.INVOCATIONS_FILE)

            self.assertEqual(1, len(history))
            self.assertEqual(list(CASE_SET), history[0]["cases"]["completed"])
            self.assertEqual(summary.started_at, history[0]["started_at"])

    def test_a_corrupt_history_is_restarted_rather_than_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = run_dir_of(tmp)
            run_dir.mkdir(parents=True)
            (run_dir / runner.INVOCATIONS_FILE).write_text("{ not json", encoding="utf-8")

            summary, _ = bench(tmp)
            history = runner.read_json(summary.run_dir / runner.INVOCATIONS_FILE)

            self.assertEqual(1, len(history))

    def test_the_summary_says_which_digest_moved_for_a_reused_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp, cases=CASE_SET)
            run_dir = run_dir_of(tmp)
            document = runner.load_cached(run_dir, CASE_SET[0])
            document["brief_sha256"] = "0" * 64
            runner.write_json(runner.case_cache_path(run_dir, CASE_SET[0]), document)

            summary, _ = bench(tmp, cases=CASE_SET)
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                runner.print_summary(summary)
            text = printed.getvalue()

            # The channel, not a generic "stale": a summary that said only
            # "stale" would leave the reader unable to tell whether to go and
            # re-read the case or go and re-read what the agents were told.
            self.assertIn("brief moved", text)
            self.assertNotIn("prompts moved", text)
            self.assertIn(str(CASE_SET[0]), text)
            self.assertIn("not a single measurement", text)


# --------------------------------------------------------------------------
# The note and the code it describes
# --------------------------------------------------------------------------

STALE_NOTE = PROJECT_ROOT / "docs" / "notes" / "2026-09-22-stale-cached-results.md"

# The block the note quotes, and the only place its numbers are written down.
_CACHED_LINE = re.compile(
    r"^(?P<directory>\S+)\s+cached=(?P<cached>\d+)\s+current=(?P<current>\d+)\s+"
    r"stale=(?P<stale>\d+)\s+unknown=(?P<unknown>\d+)\s*$"
)
_CASES_LINE = re.compile(r"^\s+(?P<label>current|stale|unknown):\s*(?P<cases>.*?)\s*$")
# A long list may be wrapped over several lines. Read the continuation rather
# than silently stopping at the first, or a wrapped list would be counted short
# and the count beneath it would be the only thing that noticed.
_CASES_CONT = re.compile(r"^\s+(?P<cases>\d+(?:\s*,\s*\d+)*)\s*$")
# The cache's digests are only comparable under the interpreter that produced
# them: the brief carries an unrounded mean distance, and sum()'s float semantics
# changed in Python 3.12. The note has to say which interpreter that was.
_INTERPRETER_LINE = re.compile(r"measured under Python (\d+\.\d+\.\d+)")


def _case_numbers(text):
    return tuple(int(part) for part in text.replace(",", " ").split())


def parse_cached_claim(text):
    """Return the counts the note states, as data, keyed by run directory.

    Read rather than searched: the job here is to compare these numbers with what
    the code computes, so they have to come out as integers and tuples and not as
    text that happens to appear somewhere in the file.
    """
    claim = {}
    directory = None
    label = None
    for line in text.splitlines():
        head = _CACHED_LINE.match(line)
        if head:
            directory = head.group("directory")
            label = None
            claim[directory] = {
                "cached": int(head.group("cached")),
                "counts": {
                    "current": int(head.group("current")),
                    "stale": int(head.group("stale")),
                    "unknown": int(head.group("unknown")),
                },
                "cases": {"current": (), "stale": (), "unknown": ()},
            }
            continue
        if directory is None:
            continue
        entry = _CASES_LINE.match(line)
        if entry:
            label = entry.group("label")
            claim[directory]["cases"][label] = _case_numbers(entry.group("cases"))
            continue
        cont = _CASES_CONT.match(line)
        if cont and label is not None:
            claim[directory]["cases"][label] += _case_numbers(cont.group("cases"))
    return claim


# Where the note records which cache its counts describe, and the shape of a
# line in that block. Read out of the fenced block under that heading rather
# than searched for in the file: a stray 64-hex string elsewhere in the note is
# not a statement about a cache.
_FINGERPRINT_HEADING = "### Which cache this note describes"
_FINGERPRINT_LINE = re.compile(r"^(?P<directory>\S+)\s+(?P<fingerprint>[0-9a-f]{64})\s*$")

# Where the note quotes the command that re-derives its numbers.
_REDERIVE_HEADING = "### Re-deriving these numbers"


def parse_cache_fingerprints(text):
    """The fingerprint the note records for each run directory, as data.

    A fingerprint is a statement that the cache it describes is one particular
    cache, so it has to be read structurally: an empty result means the note
    makes no such statement, and the caller can then decline to compare rather
    than assume a match.
    """
    if _FINGERPRINT_HEADING not in text:
        return {}
    section = text.split(_FINGERPRINT_HEADING, 1)[1]
    parts = section.split("```")
    if len(parts) < 2:
        return {}
    recorded = {}
    for line in parts[1].splitlines():
        match = _FINGERPRINT_LINE.match(line)
        if match:
            recorded[match.group("directory")] = match.group("fingerprint")
    return recorded


def note_rederivation_lines(text):
    """The command block the note quotes, as its lines.

    Returned whole -- shell invocation and terminator included -- so a caller can
    check the boundaries as well as run the body. Extracted rather than
    duplicated: a copy in the tests would be a second statement of the same
    command, free to drift from the one the note prints.
    """
    section = text[text.index(_REDERIVE_HEADING):]
    return section.split("```")[1].strip("\n").splitlines()


class CacheIdentity:
    """Whether the cache on disk is the one a note describes.

    ``state`` is one of:

    ``same``        a cache is present and its fingerprint is the recorded one;
    ``absent``      no cached case is present under that directory;
    ``moved``       a cache is present and its fingerprint differs from the
                    recorded one -- the note describes a cache that is gone;
    ``unrecorded``  a cache is present and the note records no fingerprint for
                    it, so the two cannot be shown to be the same.

    ``absent`` and ``unrecorded`` are deliberately not ``same``. The point of
    the value is to withhold a comparison that cannot be made, and a comparison
    made against the wrong cache is worse than one not made at all.
    """

    __slots__ = ("state", "recorded", "present")

    def __init__(self, state, recorded=None, present=None):
        self.state = state
        self.recorded = recorded
        self.present = present


def note_cache_identity(note_text, directory, runs_root):
    """Is the cache under ``runs/<directory>`` the one the note describes?

    Identity comes from the per-case provenance the cache itself recorded -- each
    case's brief digest and its prompts digest -- and never from the counts.
    Taking it from the counts would make the comparison circular: it would assume
    the answer to the question the comparison exists to ask.
    """
    run_dir = Path(runs_root) / directory
    recorded = parse_cache_fingerprints(note_text).get(directory)
    if not run_dir.is_dir() or not runner.cached_case_numbers(run_dir):
        return CacheIdentity("absent", recorded)
    if recorded is None:
        return CacheIdentity("unrecorded")
    present = runner.cache_fingerprint(run_dir)
    if present == recorded:
        return CacheIdentity("same", recorded, present)
    return CacheIdentity("moved", recorded, present)


def note_cache_is_wholly_compared(identities):
    """Whether every directory the note names is the cache the note describes.

    All or nothing on purpose. The note's block is the output of one command over
    every directory it names, so a cache that has changed anywhere in the set is
    enough to stop the block describing the set.
    """
    return bool(identities) and all(
        identity.state == "same" for identity in identities.values()
    )


def cache_mismatch_reasons(identities):
    """Why the cache present is not the one the note describes, as sentences.

    One sentence per directory that is not the note's cache, so a skip says which
    directory to look at rather than that something, somewhere, differs.
    """
    reasons = []
    for directory, identity in sorted(identities.items()):
        if identity.state == "moved":
            reasons.append(
                "the cache under runs/{0} has changed since the note was written: the note "
                "describes {1}, the cache present is {2}".format(
                    directory, identity.recorded, identity.present
                )
            )
        elif identity.state == "absent":
            reasons.append("no cached run directory is present under runs/{0}".format(directory))
        elif identity.state == "unrecorded":
            reasons.append(
                "the note records no fingerprint for runs/{0}, so the cache present cannot "
                "be shown to be the one it describes".format(directory)
            )
    return reasons


def note_cache_skip_message(text, identities):
    """The reason a comparison was withheld, and how to re-derive the numbers.

    The command is the note's own, extracted rather than restated. A reader told
    the cache has moved on needs something to run, and the one command that
    re-derives the note's numbers for whatever the cache holds now is the command
    the note already quotes.
    """
    return (
        "{0}. The note's counts are a dated statement about the cache runs/ held on "
        "2026-09-22, so they are re-derived for whatever the cache now holds rather than "
        "held against a cache they do not describe:\n\n{1}".format(
            "; ".join(cache_mismatch_reasons(identities)),
            "\n".join(note_rederivation_lines(text)),
        )
    )


# --------------------------------------------------------------------------
# Fixtures for the note-identity tests
# --------------------------------------------------------------------------
def write_provenance_cache(runs_root, name, entries):
    """A cache directory whose entries carry the provenance given.

    ``entries`` is a sequence of ``(case_no, brief_sha256, prompts_sha256)``. A
    ruling is written beside them so each entry reads as a result rather than as
    an unusable file; nothing about the ruling reaches a fingerprint, which is
    the property one of the tests below pins.
    """
    run_dir = Path(runs_root) / name
    run_dir.mkdir(parents=True, exist_ok=True)
    for case_no, brief, prompts in entries:
        runner.write_json(
            runner.case_cache_path(run_dir, case_no),
            {
                "case_no": case_no,
                "ruling": {"value": "NO_ACTION"},
                "brief_sha256": brief,
                "prompts_sha256": prompts,
            },
        )
    return run_dir


def note_with_fingerprints(text, fingerprints):
    """The note with the fingerprint for the directories given replaced.

    Used to put a cache built for a test in the place of the note's own, so the
    gate can be exercised on each of its answers without touching ``runs/``. A
    directory the mapping does not name keeps the fingerprint it had.
    """
    out = []
    for line in text.splitlines(True):
        match = _FINGERPRINT_LINE.match(line.rstrip("\n"))
        if match and match.group("directory") in fingerprints:
            out.append(
                "{0}  {1}\n".format(
                    match.group("directory"), fingerprints[match.group("directory")]
                )
            )
        else:
            out.append(line)
    return "".join(out)


def note_without_fingerprint(text, directory):
    """The note with one directory's fingerprint line removed.

    Dropping the record is how a note could quietly stop being checked, so the
    gate has an answer for it rather than reading a missing record as a match.
    """
    kept = []
    for line in text.splitlines(True):
        match = _FINGERPRINT_LINE.match(line.rstrip("\n"))
        if match and match.group("directory") == directory:
            continue
        kept.append(line)
    return "".join(kept)


class NoteCouplingTests(unittest.TestCase):
    """The note states a count about the cache; the code computes that count.

    Nothing compared them, so the note carried a figure nothing checked for a
    day. These tests read the numbers out of the note and hold them against
    ``grade_run`` over the same directories, so the two cannot drift apart again
    without a test going red.

    One limitation, stated rather than papered over: the cache under ``runs/`` is
    untracked, so on a checkout without it there is nothing to compare against
    and the comparison is skipped, naming the directories it wanted.

    **The note's numbers describe one cache, and the comparison is made only
    against that one.** ``runs/`` is mutable: the next full run rewrites every
    count in the block, at which point holding the note's numbers against the
    directory beneath them compares a dated snapshot with present state and goes
    red for a reason that is not a defect. So the note records a fingerprint of
    the cache it describes -- the set of per-case brief and prompts digests,
    which is provenance rather than a count -- and these tests compare only when
    the cache present is that cache. Otherwise they skip, naming which directory
    has moved on and quoting the command that re-derives the note's numbers for
    whatever the cache holds now. An absent cache skips for the reason it always
    did.

    The comparisons used to be skipped under any interpreter but the one that
    produced the cache, because the brief carried an unrounded mean distance and
    ``sum()``'s float semantics changed in Python 3.12. The accumulation is now
    pinned, so they run everywhere. The note still has to name the interpreter
    the cache came from: that is provenance, and a count about a cache is weaker
    without it.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = STALE_NOTE.read_text(encoding="utf-8")
        cls.claim = parse_cached_claim(cls.text)

    def _named_interpreter(self):
        """The interpreter the note says its digests were made under."""
        match = _INTERPRETER_LINE.search(self.text)
        self.assertIsNotNone(
            match,
            "the note no longer says which interpreter its digests were made under",
        )
        return match.group(1)

    def _the_notes_own_cache(self):
        """The directories whose cache is the one the note describes.

        Skips, naming why, when any directory the note counts is not that cache.
        The gate is all-or-nothing on purpose: the note's block is the output of
        one command over every directory it names, so a cache that has moved on
        anywhere in the set is enough to make the block stop describing the set.
        """
        if not self.claim:
            self.skipTest("the note states no cached count, so there is nothing to compare")

        identities = {
            directory: note_cache_identity(self.text, directory, PROJECT_ROOT / "runs")
            for directory in sorted(self.claim)
        }
        if note_cache_is_wholly_compared(identities):
            return sorted(identities)

        self.skipTest(note_cache_skip_message(self.text, identities))

    def test_the_note_names_a_count_for_at_least_one_directory(self):
        self.assertTrue(
            self.claim, "the note no longer states a cached count for any directory"
        )

    def test_the_note_names_the_interpreter_its_digests_came_from(self):
        """Provenance, and still required even though it is no longer a precondition.

        The brief is byte-stable across Python versions now, so the count no
        longer depends on this. What the note records is where the cache came
        from: a result's own file says which interpreter produced it, and a note
        about that cache should be able to say so too.
        """
        self._named_interpreter()

    def test_the_counts_add_up_to_the_cached_total(self):
        for directory, block in sorted(self.claim.items()):
            with self.subTest(directory=directory):
                self.assertEqual(
                    block["cached"],
                    sum(block["counts"].values()),
                    "current + stale + unknown must be the cached total",
                )

    def test_each_count_matches_the_case_list_beneath_it(self):
        for directory, block in sorted(self.claim.items()):
            for label, stated in sorted(block["counts"].items()):
                with self.subTest(directory=directory, label=label):
                    self.assertEqual(stated, len(block["cases"][label]))

    def test_no_case_is_listed_twice_or_out_of_order(self):
        for directory, block in sorted(self.claim.items()):
            listed = []
            for label, cases in sorted(block["cases"].items()):
                with self.subTest(directory=directory, label=label):
                    self.assertEqual(len(set(cases)), len(cases), "a case is listed twice")
                    self.assertEqual(tuple(sorted(cases)), cases, "the list is not ordered")
                listed.extend(cases)
            with self.subTest(directory=directory, label="every list together"):
                self.assertEqual(len(set(listed)), len(listed), "a case is in two lists")

    def test_the_note_agrees_with_the_grader_over_the_real_cache(self):
        """The coupling itself: the note's numbers against the code's.

        Run under whatever interpreter the suite is running. This comparison was
        meaningless under anything but the one that produced the cache — the
        brief carried an unrounded mean distance and ``sum()``'s float semantics
        changed in Python 3.12, so the check reported twenty-one where the cache
        holds twelve — and it is the repair of that which lets the comparison be
        made under any interpreter. A comparison that only runs under one
        interpreter is a comparison that quietly stops being made.

        It is not unconditional in the other direction. The cache is mutable, so
        the comparison is made only against the cache the note describes, and
        skipped with the reason named otherwise: a note's count is a claim about
        one cache, and holding it against another measures the calendar.

        Nor is it unconditional across platforms. The note records the cache's
        staleness, which the checker answers by rebuilding each brief; a
        platform that cannot rebuild case 111's brief reads one case stale where
        the note read none, so the comparison skips there and says why.
        """
        portability.require_the_same_libm()
        directories = self._the_notes_own_cache()
        for directory in directories:
            block = self.claim[directory]
            run_dir = PROJECT_ROOT / "runs" / directory
            report = runner.grade_run(run_dir)
            cached = tuple(runner.cached_case_numbers(run_dir))
            stale = set(report.staleness.stale)
            unknown = set(report.staleness.unknown)
            current = tuple(case for case in cached if case not in stale and case not in unknown)

            with self.subTest(directory=directory):
                self.assertTrue(
                    report.staleness.checked,
                    "the note states a count for a directory the check did not read",
                )
                self.assertEqual(block["cases"]["stale"], report.staleness.stale)
                self.assertEqual(block["cases"]["unknown"], report.staleness.unknown)
                self.assertEqual(block["cases"]["current"], current)
                self.assertEqual(block["cached"], len(cached))

    def test_the_block_the_note_quotes_is_the_output_of_its_own_command(self):
        """The note says the block is that command's output; hold it to that.

        A block written by hand and presented as tool output is exactly how the
        first version of this note went wrong, so the claim is worth running
        rather than reading. The command is extracted from the note, executed,
        and its stdout compared with the block above it.

        Run under whatever interpreter the suite is running. The note's command
        used to refuse under anything but the one that produced the cache; the
        accumulation behind the brief is now pinned, so it no longer does.

        Gated on the same fingerprint as the comparison above, and for the same
        reason: the command reads the cache under ``runs/``, so its output can be
        the note's block only while the cache it reads is the note's.
        """
        self._the_notes_own_cache()

        lines = self.text.splitlines(True)
        first = next(
            index for index, line in enumerate(lines) if _CACHED_LINE.match(line)
        )
        last = next(
            index for index in range(first, len(lines)) if lines[index].strip() == "```"
        )
        block = "".join(lines[first:last])

        command = note_rederivation_lines(self.text)
        self.assertEqual("python3 - <<'PY'", command[0], "the command's first line moved")
        self.assertEqual("PY", command[-1], "the command's terminator moved")
        script = "\n".join(command[1:-1])

        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(block, completed.stdout)


class CacheFingerprintTests(unittest.TestCase):
    """What says whether a statement about a cache is about *this* cache.

    The cache under ``runs/`` is untracked and every run rewrites it, so a note
    that states counts about it is stating something about one particular cache.
    A fingerprint taken from per-case provenance is what lets a reader ask whether
    the cache in front of them is the one the note describes.

    The property it must not have is a dependence on the counts. Taking identity
    from the numbers the comparison is about would assume the answer to the
    question the comparison exists to ask.
    """

    def test_a_brief_digest_alone_distinguishes_two_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            one = write_provenance_cache(tmp, "one", [(101, "a" * 64, "b" * 64)])
            two = write_provenance_cache(tmp, "two", [(101, "c" * 64, "b" * 64)])

            self.assertNotEqual(runner.cache_fingerprint(one), runner.cache_fingerprint(two))

    def test_a_prompts_digest_alone_distinguishes_two_caches(self):
        """The second channel is part of the identity, not a decoration on it."""
        with tempfile.TemporaryDirectory() as tmp:
            one = write_provenance_cache(tmp, "one", [(101, "a" * 64, "b" * 64)])
            two = write_provenance_cache(tmp, "two", [(101, "a" * 64, "c" * 64)])

            self.assertNotEqual(runner.cache_fingerprint(one), runner.cache_fingerprint(two))

    def test_an_entry_that_recorded_no_prompts_digest_is_not_one_that_did(self):
        """An entry written before the field existed records nothing, and that
        absence is part of what the cache is rather than a value to skip over."""
        with tempfile.TemporaryDirectory() as tmp:
            one = write_provenance_cache(tmp, "one", [(101, "a" * 64, None)])
            two = write_provenance_cache(tmp, "two", [(101, "a" * 64, "b" * 64)])

            self.assertNotEqual(runner.cache_fingerprint(one), runner.cache_fingerprint(two))

    def test_the_set_of_cases_is_part_of_the_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            one = write_provenance_cache(tmp, "one", [(101, "a" * 64, "b" * 64)])
            two = write_provenance_cache(
                tmp, "two", [(101, "a" * 64, "b" * 64), (102, "c" * 64, "d" * 64)]
            )

            self.assertNotEqual(runner.cache_fingerprint(one), runner.cache_fingerprint(two))

    def test_the_fingerprint_ignores_the_counts_it_stands_beside(self):
        """The anti-circularity property, pinned as a test.

        Two caches with the same provenance and different results are the same
        cache as far as identity goes: the fingerprint is about where the bytes
        came from, not about what they said. A fingerprint that moved with the
        counts would make the comparison it gates circular.
        """
        with tempfile.TemporaryDirectory() as tmp:
            one = write_provenance_cache(tmp, "one", [(101, "a" * 64, "b" * 64)])
            two = write_provenance_cache(tmp, "two", [(101, "a" * 64, "b" * 64)])
            document = runner.load_cached(two, 101)
            document["ruling"] = {"value": "FULL_REFUND", "confidence": 0.99}
            document["match"] = False
            runner.write_json(runner.case_cache_path(two, 101), document)

            self.assertEqual(
                runner.cache_fingerprint(one),
                runner.cache_fingerprint(two),
                "the fingerprint moved with the counts, which is what makes it circular",
            )

    def test_the_same_cache_fingerprints_the_same_way_every_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = write_provenance_cache(
                tmp, "one", [(101, "a" * 64, "b" * 64), (102, "c" * 64, "d" * 64)]
            )
            first = runner.cache_fingerprint(run_dir)

            self.assertEqual(first, runner.cache_fingerprint(run_dir))
            self.assertRegex(first, r"^[0-9a-f]{64}$")


class NoteCacheIdentityTests(unittest.TestCase):
    """The note's comparisons run only against the cache the note describes.

    A note's counts describe one cache. ``runs/`` is untracked and every full run
    rewrites it, so the comparison has to be withheld when the cache present is
    not the one the note was written about: otherwise the test goes red for the
    calendar rather than for a defect, and a test that goes red for the calendar
    is a test someone deletes.

    What each answer means, and that each is reached, is pinned here on caches
    built for the purpose. The real cache under ``runs/`` is not touched.
    """

    NOTE = STALE_NOTE.read_text(encoding="utf-8")
    DIRECTORY = "deepseek-deepseek-flash"

    def test_a_cache_that_is_the_notes_is_compared(self):
        """The comparison runs when the cache present is the note's own."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = write_provenance_cache(tmp, self.DIRECTORY, [(101, "a" * 64, "b" * 64)])
            fingerprint = runner.cache_fingerprint(run_dir)
            text = note_with_fingerprints(self.NOTE, {self.DIRECTORY: fingerprint})

            identity = note_cache_identity(text, self.DIRECTORY, tmp)

            self.assertEqual("same", identity.state)
            self.assertEqual(fingerprint, identity.recorded)
            self.assertEqual(fingerprint, identity.present)
            self.assertTrue(note_cache_is_wholly_compared({self.DIRECTORY: identity}))

    def test_a_cache_that_moved_on_is_not_compared_and_the_skip_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = write_provenance_cache(tmp, self.DIRECTORY, [(101, "a" * 64, "c" * 64)])
            present = runner.cache_fingerprint(run_dir)

            identity = note_cache_identity(self.NOTE, self.DIRECTORY, tmp)

            self.assertEqual("moved", identity.state)
            self.assertNotEqual(identity.recorded, identity.present)
            self.assertEqual(present, identity.present)
            self.assertFalse(note_cache_is_wholly_compared({self.DIRECTORY: identity}))

            message = note_cache_skip_message(self.NOTE, {self.DIRECTORY: identity})
            self.assertIn("has changed since the note was written", message)
            self.assertIn(identity.recorded, message)
            self.assertIn(present, message)
            self.assertIn("re-derived", message)
            self.assertIn(
                "\n".join(note_rederivation_lines(self.NOTE)),
                message,
                "the skip does not hand the reader the command that re-derives the numbers",
            )

    def test_an_absent_cache_is_not_compared(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity = note_cache_identity(self.NOTE, self.DIRECTORY, tmp)

            self.assertEqual("absent", identity.state)
            self.assertIsNone(identity.present)
            self.assertFalse(note_cache_is_wholly_compared({self.DIRECTORY: identity}))

            message = note_cache_skip_message(self.NOTE, {self.DIRECTORY: identity})
            self.assertIn("no cached run directory is present", message)

    def test_a_run_directory_with_no_cached_case_is_absent_rather_than_moved(self):
        """An empty directory holds no cache, so there is nothing to call moved."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / self.DIRECTORY).mkdir()

            identity = note_cache_identity(self.NOTE, self.DIRECTORY, tmp)

            self.assertEqual("absent", identity.state)

    def test_a_cache_the_note_records_no_fingerprint_for_is_not_compared(self):
        """Dropping the record must not read as a match."""
        with tempfile.TemporaryDirectory() as tmp:
            write_provenance_cache(tmp, self.DIRECTORY, [(101, "a" * 64, "b" * 64)])
            text = note_without_fingerprint(self.NOTE, self.DIRECTORY)
            self.assertNotIn(self.DIRECTORY, parse_cache_fingerprints(text))

            identity = note_cache_identity(text, self.DIRECTORY, tmp)

            self.assertEqual("unrecorded", identity.state)
            message = note_cache_skip_message(text, {self.DIRECTORY: identity})
            self.assertIn("records no fingerprint", message)

    def test_the_gate_is_all_or_nothing_over_the_directories_the_note_names(self):
        """One directory that has moved on withholds the comparison for the set.

        The block is the output of one command over every directory it names, so
        a cache that has changed anywhere in the set stops the block describing
        the set.
        """
        same = CacheIdentity("same", "a" * 64, "a" * 64)
        moved = CacheIdentity("moved", "a" * 64, "b" * 64)
        absent = CacheIdentity("absent", "a" * 64)

        self.assertTrue(note_cache_is_wholly_compared({"one": same, "two": same}))
        self.assertFalse(
            note_cache_is_wholly_compared({"one": same, "two": moved}),
            "one directory that has moved on must withhold the comparison for the set",
        )
        self.assertFalse(note_cache_is_wholly_compared({"one": absent}))
        self.assertFalse(
            note_cache_is_wholly_compared({}),
            "no directory is not the same as every directory being the note's",
        )

    def test_the_note_records_a_fingerprint_for_every_directory_it_counts(self):
        """The coupling is only as good as the record that gates it."""
        claim = parse_cached_claim(self.NOTE)
        recorded = parse_cache_fingerprints(self.NOTE)

        self.assertTrue(claim, "the note states no cached count for any directory")
        for directory in sorted(claim):
            with self.subTest(directory=directory):
                self.assertIn(
                    directory,
                    recorded,
                    "the note states a count for a directory it does not fingerprint, so "
                    "the comparison cannot tell whether the cache is the one it describes",
                )

    def test_the_note_says_its_numbers_are_a_dated_statement(self):
        """A count about a mutable cache is a claim about a date, and must say so.

        This repository is published, and a reader who does not know that
        ``runs/`` is rewritten by every run would otherwise take a historical
        count for a live one.
        """
        self.assertIn(_FINGERPRINT_HEADING, self.NOTE)
        self.assertIn(_REDERIVE_HEADING, self.NOTE)
        section = self.NOTE.split(_FINGERPRINT_HEADING, 1)[1].split("\n### ", 1)[0]

        self.assertIn("2026-09-22", section, "the section does not date the counts it describes")
        self.assertIn(
            "re-derive", section, "the section does not say how to re-derive the counts"
        )


class IsolationTests(unittest.TestCase):
    """The answer key never reaches a brief, a prompt, a transcript or the cache."""

    def _completed_run(self, tmp):
        summary, _ = bench(tmp)
        return summary.run_dir

    def test_the_scan_finds_every_declared_needle_and_nothing_else(self):
        """Not a private copy of the matcher: the needles are the guard's own."""
        self.assertTrue(isolation.DISTINCTIVE_ANSWER_FIELDS)
        for needle in isolation.DISTINCTIVE_ANSWER_FIELDS:
            with self.subTest(needle=needle):
                self.assertEqual([needle], isolation._answer_key_names_in("x {0} y".format(needle)))
        self.assertEqual(
            [],
            isolation._answer_key_names_in("a clean brief about a route deviation"),
        )

    def test_no_cached_artifact_or_transcript_carries_an_answer_key_field_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._completed_run(tmp)

            scanned = 0
            offenders = []
            for path in sorted(run_dir.rglob("*")):
                if not path.is_file():
                    continue
                scanned += 1
                names = isolation._answer_key_names_in(path.read_text(encoding="utf-8"))
                if names:
                    offenders.append((path.name, names))

            # If the run wrote nothing, the scan below would pass for the wrong
            # reason.
            self.assertGreater(scanned, 8, "too few artifacts to scan; the run wrote nothing")
            self.assertEqual([], offenders, "an answer-key field name reached a run artifact")

    def test_the_scan_is_capable_of_firing(self):
        """A guard nobody has seen fail is not evidence of anything."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._completed_run(tmp)
            path = runner.case_cache_path(run_dir, 101)
            original = path.read_text(encoding="utf-8")

            document = json.loads(original)
            document["expected_ruling"] = "NO_ACTION"
            path.write_text(json.dumps(document), encoding="utf-8")

            self.assertEqual(
                ["expected_ruling"],
                isolation._answer_key_names_in(path.read_text(encoding="utf-8")),
                "the scan did not see a needle that was plainly there",
            )

            path.write_text(original, encoding="utf-8")
            self.assertEqual([], isolation._answer_key_names_in(path.read_text(encoding="utf-8")))

    def test_the_cache_entry_does_not_declare_an_expected_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._completed_run(tmp)
            document = runner.load_cached(run_dir, 101)
            for name in isolation.DISTINCTIVE_ANSWER_FIELDS:
                with self.subTest(field=name):
                    self.assertNotIn(name, document)

    def test_a_judge_response_carrying_a_key_field_name_would_be_caught(self):
        """The transcript keeps the raw body, so the scan covers the model too."""
        key = answer_key()

        def leak(case_no, ruling):
            if case_no == 101:
                ruling["expected_ruling"] = ruling["ruling"]
            return ruling

        transport = ScriptedTransport(produced_from_key(key), mutate=leak)
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, transport=transport)
            text = runner.transcript_path(summary.run_dir, 101).read_text(encoding="utf-8")
            self.assertEqual(["expected_ruling"], isolation._answer_key_names_in(text))

    def test_the_runner_names_no_path_under_the_answer_key(self):
        """The runner asks the grader for the digest; it never opens the key."""
        source = (PROJECT_ROOT / "eval" / "run_benchmark.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                segments = [part for part in node.value.replace("\\", "/").split("/") if part]
                if "eval" in segments and "answers" in segments:
                    offenders.append(node.value)
        self.assertEqual([], offenders, "the runner names the answer key's path")

    def test_the_runner_reaches_the_key_only_through_the_grader(self):
        source = (PROJECT_ROOT / "eval" / "run_benchmark.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        reached = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "grade"
        }
        self.assertTrue(reached, "the runner does not use the grader at all")
        self.assertIn("load_answer_key", reached)
        self.assertIn("answer_key_sha256", reached)
        self.assertIn("grade", reached)

    def test_no_package_module_imports_the_runner(self):
        for path in isolation._package_sources():
            source = path.read_text(encoding="utf-8")
            with self.subTest(module=path.name):
                self.assertNotIn("run_benchmark", source)


# --------------------------------------------------------------------------
# The block a person reads at the end
# --------------------------------------------------------------------------
class RefusingTransport:
    """Answers every case but the refused one, and fails if that one is called.

    A refusal is only a refusal if no call was made **for that case**. The other
    cases in the same invocation are replayed normally, so a rig that raised on
    any call at all would also fail a correct run of the other cases -- and
    would pass for a runner that quietly ran the refused one in full. The case
    is read off the request, exactly as the scripted transport reads it.
    """

    def __init__(self, refused=(), produced=None) -> None:
        self.refused = {refused} if isinstance(refused, int) else set(refused)
        self._scripted = ScriptedTransport(
            produced_from_key(answer_key()) if produced is None else produced
        )
        self.refused_calls = 0

    def __call__(self, url, headers, body, timeout):
        case_no, _role = role_of(json.loads(body.decode("utf-8")))
        if case_no in self.refused:
            self.refused_calls += 1
            raise AssertionError(
                "a model call was made for case {0}, which replay should have "
                "refused".format(case_no)
            )
        return self._scripted(url, headers, body, timeout)

    def calls(self) -> int:
        return self._scripted.calls()


class ReplayTests(unittest.TestCase):
    """Replaying the advocates, and re-running only the judge.

    Every test drives the real runner, the real pipeline and the real client
    over the scripted transport, with no network. The acceptance conditions are
    broken one at a time, and each refusal is asserted with a transport that
    raises if it is reached, so "no model call" is a property of the rig rather
    than a count taken afterwards.
    """

    def _source(self, tmp, **overrides):
        """A completed run to replay from: its directory, and its transport."""
        summary, transport = bench(tmp, **overrides)
        return summary.run_dir, transport

    def _replay(self, tmp, source, *, transport=None, runs_dir=None, **overrides):
        """A replay of ``source``, into its own directory by default."""
        if transport is None:
            transport = ScriptedTransport(produced_from_key(answer_key()))
        arguments = dict(
            runs_dir=Path(runs_dir) if runs_dir is not None else Path(tmp) / "replayed",
            force=True,
            replay_dir=source,
            transport=transport,
        )
        arguments.update(overrides)
        summary, _ = bench(tmp, **arguments)
        return summary, transport

    def _refused(self, tmp, source, case_no, break_it, *, refused=None, **overrides):
        """Break the source for one case, replay, and require a refusal.

        The transport raises if the refused case is reached, so a runner that
        called the judge for it anyway fails here rather than being recorded
        under some other failure kind. The rest of the set is replayed normally,
        which is what shows the run continues past a refusal.
        """
        break_it(source, case_no)
        transport = RefusingTransport(refused if refused is not None else case_no)
        summary, _ = self._replay(tmp, source, transport=transport, **overrides)
        self.assertEqual(
            0,
            transport.refused_calls,
            "a refused case reached the transport",
        )
        return summary

    def _rewrite_transcript(self, source, case_no, change):
        """Change one case's recorded transcript, and keep the source's own record of it.

        The cache entry's ``transcript_sha256`` is updated too. Without that the
        transcript-digest condition fires first and the condition under test is
        never exercised -- the two would be indistinguishable, and a test that
        cannot tell them apart does not test either.
        """
        path = runner.transcript_path(source, case_no)
        document = json.loads(path.read_text(encoding="utf-8"))
        change(document["entries"])
        path.write_text(json.dumps(document), encoding="utf-8")
        record = runner.read_json(runner.case_cache_path(source, case_no))
        record["transcript_sha256"] = runner.file_sha256(path)
        runner.write_json(runner.case_cache_path(source, case_no), record)

    # -- what a replay does -----------------------------------------------
    def test_a_replayed_case_makes_one_call_and_it_is_the_judge(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, first = self._source(tmp)
            self.assertEqual(len(CASE_SET) * CALLS_PER_CASE, first.calls())

            summary, transport = self._replay(tmp, source)

            self.assertEqual([], summary.failures)
            self.assertEqual(list(CASE_SET), summary.completed_cases)
            self.assertEqual(list(CASE_SET), summary.replayed_cases)
            # One call per case, and the advocates are not among them.
            self.assertEqual(len(CASE_SET), transport.calls())
            for case_no in CASE_SET:
                with self.subTest(case_no=case_no):
                    self.assertEqual([transcript.ROLE_JUDGE], transport.roles_for(case_no))

    def test_the_judge_is_handed_the_bytes_a_full_run_would_build(self):
        """The replay builds the judge's input through the pipeline's own code.

        Compared against what a full run of the same cases sends, not against a
        string this test composes: a second copy of the message's shape in the
        replay would pass a test written the other way while the two drifted
        apart, which is the whole failure this comparison exists to catch.
        """
        with tempfile.TemporaryDirectory() as tmp:
            source, first = self._source(tmp)
            full = {}
            for request, (case_no, role) in zip(first.requests, first.roles):
                if role == transcript.ROLE_JUDGE:
                    full[case_no] = request["messages"]
            self.assertEqual(sorted(CASE_SET), sorted(full))

            summary, transport = self._replay(tmp, source)

            self.assertEqual(len(CASE_SET), transport.calls())
            for request, (case_no, role) in zip(transport.requests, transport.roles):
                with self.subTest(case_no=case_no):
                    self.assertEqual(transcript.ROLE_JUDGE, role)
                    self.assertEqual(full[case_no], request["messages"])

    def test_the_recorded_advocate_entries_are_copied_and_marked_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary, _ = self._replay(tmp, source)

            for case_no in CASE_SET:
                with self.subTest(case_no=case_no):
                    before = json.loads(
                        runner.transcript_path(source, case_no).read_text(encoding="utf-8")
                    )["entries"]
                    after = json.loads(
                        runner.transcript_path(summary.run_dir, case_no).read_text(
                            encoding="utf-8"
                        )
                    )["entries"]

                    recorded = [
                        entry for entry in before if entry["role"] != transcript.ROLE_JUDGE
                    ]
                    copied = [
                        entry for entry in after if entry["role"] != transcript.ROLE_JUDGE
                    ]
                    self.assertEqual(len(recorded), len(copied))
                    for original, carried in zip(recorded, copied):
                        # Verbatim but for the note: the digests, the timestamp,
                        # the usage figures and the response are the record of a
                        # call that really happened, and re-deriving any of them
                        # would be inventing evidence rather than copying it.
                        for field in (
                            "role",
                            "model",
                            "system_sha256",
                            "user_sha256",
                            "response_text",
                            "parse_outcome",
                            "shape",
                            "prompt_tokens",
                            "completion_tokens",
                            "reasoning_tokens",
                            "cached_tokens",
                            "duration_seconds",
                            "attempts",
                            "status",
                            "timestamp",
                        ):
                            self.assertEqual(original[field], carried[field], field)
                        self.assertIn("replayed", carried["note"])
                        self.assertIn(str(source), carried["note"])
                        self.assertIn("did not call", carried["note"])

                    judge = [entry for entry in after if entry["role"] == transcript.ROLE_JUDGE]
                    self.assertEqual(1, len(judge))
                    self.assertIsNone(
                        judge[0]["note"],
                        "the judge's own entry is this run's and carries no replay note",
                    )

    def test_the_cache_entry_names_the_source_its_commit_and_its_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary, _ = self._replay(tmp, source)

            document = runner.load_cached(summary.run_dir, 101)
            replay = document["replay"]
            self.assertEqual(str(source), replay["run_dir"])
            self.assertEqual(COMMIT, replay["git_commit"])
            self.assertEqual(
                runner.file_sha256(runner.transcript_path(source, 101)),
                replay["transcript_sha256"],
            )
            self.assertEqual(document["brief_sha256"], replay["brief_sha256"])
            self.assertEqual(MODEL, replay["model"])
            self.assertEqual(2, replay["advocate_calls"])
            self.assertIn("replayed", replay["note"])
            # And the result's own tokens are the judge's alone.
            self.assertEqual(
                TOKENS_PER_CALL, document["tokens"]["total_tokens"]
            )

    def test_the_run_record_says_the_advocates_were_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary, _ = self._replay(tmp, source)

            metadata = runner.read_json(runner.metadata_path(summary.run_dir))
            replay = metadata["replay"]
            self.assertEqual(str(source), replay["run_dir"])
            self.assertEqual(COMMIT, replay["git_commit"])
            self.assertEqual(list(CASE_SET), replay["replayed_cases"])
            self.assertEqual([], replay["refused_cases"])
            self.assertEqual(
                len(CASE_SET) * 2 * TOKENS_PER_CALL, replay["tokens"]["total_tokens"]
            )
            self.assertIn("only the judge was called", replay["note"])
            self.assertEqual(
                len(CASE_SET) * 2 * TOKENS_PER_CALL,
                metadata["tokens"]["billed_to_another_run"],
            )
            # The invocation's own figures, which the borrowed tokens are not in.
            self.assertEqual(
                len(CASE_SET) * TOKENS_PER_CALL, metadata["tokens"]["spent_this_invocation"]
            )

    def test_the_borrowed_tokens_are_reported_and_never_charged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary, _ = self._replay(tmp, source)

            # This run's bill: the judge, one call per case.
            self.assertEqual(len(CASE_SET) * TOKENS_PER_CALL, summary.tokens_spent)
            # The two advocates per case, reported beside it.
            self.assertEqual(
                len(CASE_SET) * 2 * TOKENS_PER_CALL, summary.tokens_replayed.billed
            )
            # And never added to it. A run that summed them would claim to have
            # spent tokens it never spent, which is the one thing this split
            # exists to prevent.
            self.assertEqual(
                len(CASE_SET) * TOKENS_PER_CALL, summary.tokens_consumed.billed
            )
            self.assertNotEqual(
                summary.tokens_spent + summary.tokens_replayed.billed,
                summary.tokens_spent,
            )

    def test_the_report_says_the_advocates_were_replayed_and_from_where(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary, _ = self._replay(tmp, source)

            text = (summary.run_dir / runner.REPORT_FILE).read_text(encoding="utf-8")
            self.assertIn("Advocates replayed", text)
            self.assertIn(str(source), text)
            self.assertIn("rather than a measurement of the whole pipeline", text)
            self.assertIn("reused from another run", text)
            self.assertIn("**(advocates replayed)**", text)
            self.assertEqual(tuple(CASE_SET), summary.report.replay.cases)
            self.assertEqual((str(source),), summary.report.replay.sources)
            self.assertEqual(
                len(CASE_SET) * 2 * TOKENS_PER_CALL, summary.report.replay.tokens
            )

    def test_two_replays_into_one_directory_both_name_the_commit_that_made_the_advocates(self):
        """The source commit is the run that produced them, not the one that copied them.

        The defect, as a regression test. The source commit was read from the
        source directory's ``run.json``, which is the last invocation's file, and
        a replay into the directory it reads from rewrites it before the next
        replay reads it. The second of two replays therefore named the first's
        commit -- on the real run, four cases recorded ``74881db`` instead of
        ``493beea``, a commit whose judge produced nothing those cases reused.

        The fixture is the real sequence: a full run, then two replays into that
        same directory under two later commits, the second of them taking the
        cases the first did not reach.
        """
        made = "a" * 40
        first = "b" * 40
        second = "c" * 40
        with tempfile.TemporaryDirectory() as tmp:
            made_run, _ = bench(tmp, git=git_runner(made))
            source = made_run.run_dir
            # Into the source's own directory: runs_dir is the runs root, so the
            # source's parent is what makes the destination the source.
            self._replay(
                tmp,
                source,
                runs_dir=source.parent,
                cases=CASE_SET[:2],
                git=git_runner(first),
            )
            self._replay(
                tmp,
                source,
                runs_dir=source.parent,
                cases=CASE_SET[2:3],
                git=git_runner(second),
            )

            document = runner.read_json(runner.case_cache_path(source, CASE_SET[2]))

        self.assertEqual(
            made,
            document["replay"]["git_commit"],
            "a case names as its source the commit of a run that only copied "
            "these advocates",
        )

    def test_the_run_record_names_the_commit_that_made_the_advocates(self):
        """The run-level block carries both commits, and the summary prints both.

        The defect, as a regression test, and the run-level half of the one
        above. ``ReplayCheck.provenance`` fills its ``git_commit`` from the
        source directory's ``run.json``, which a replay into that directory
        rewrites before the next replay reads it -- so the block named the
        commit that *copied* the advocates, and the printed summary said
        "advocates from ... (commit <that one>)", which reads as the run that
        made them. On the real run every case's entry recorded ``493beea`` as
        the commit that made its advocates while the block said ``c4c9a06``.

        The fixture is that sequence: a full run, then two replays into the same
        directory under two later commits, the second of them taking the case
        the first did not reach.
        """
        made = "a" * 40
        first = "b" * 40
        second = "c" * 40
        with tempfile.TemporaryDirectory() as tmp:
            made_run, _ = bench(tmp, git=git_runner(made))
            source = made_run.run_dir
            self._replay(
                tmp,
                source,
                runs_dir=source.parent,
                cases=CASE_SET[:2],
                git=git_runner(first),
            )
            summary, _ = self._replay(
                tmp,
                source,
                runs_dir=source.parent,
                cases=CASE_SET[2:3],
                git=git_runner(second),
            )

            metadata = runner.read_json(runner.metadata_path(summary.run_dir))
            replay = metadata["replay"]

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                runner.print_summary(summary)
            text = output.getvalue()

        # The source directory records the *first replay's* commit by the time
        # the second one reads it, and that is what the block has always named.
        self.assertEqual(first, replay["git_commit"])
        # The run that made them is neither replay's, and the block says so.
        self.assertEqual([made], replay["advocate_commits"])
        # Both are printed, so the one commit a reader sees first cannot read as
        # the advocates' own provenance.
        self.assertIn(made[:12], text, "the run that made the advocates is not printed")
        self.assertIn(first[:12], text, "the source directory's commit is not printed")

    def test_a_run_that_stopped_early_counts_the_cases_it_replayed(self):
        """The summary counts this invocation's cases, not the ones it accepted.

        The defect, as a regression test. The line read the source block's
        ``replayed_cases``, which is every case the acceptance check accepted
        *before* the run began, and printed it over the number of outcomes the
        run produced. A replay stopped by its token budget therefore reported
        more cases reused than cases run: on the first real one, "29 of 25 cases
        reused them", where four of the twenty-nine were never reached.

        The fixture asserts the precondition as well as the line. A budget that
        stops the run is only a reproduction while the check accepted more cases
        than the run reached, and a test that could pass with the two equal
        would not have caught this.
        """
        requested = CASE_SET[:3]
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary, _ = self._replay(
                tmp, source, cases=requested, token_budget=TOKENS_PER_CALL
            )

            # The precondition is that the run did not reach every case it asked
            # about. All three were accepted, so three is also the number the
            # old line printed over the one case that actually ran.
            self.assertLess(
                len(summary.outcomes),
                len(requested),
                "the fixture does not reproduce it: the run reached every case "
                "it asked about, so the two counts agree",
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                runner.print_summary(summary)
            text = output.getvalue()

            self.assertIn(
                "{0} of {1} cases reused them".format(
                    len(summary.replayed_cases), len(summary.outcomes)
                ),
                text,
            )
            self.assertNotIn(
                "{0} of {1} cases reused them".format(
                    len(requested), len(summary.outcomes)
                ),
                text,
                "the summary counts cases the run never reached",
            )

    def test_the_record_lists_the_cases_this_invocation_replayed(self):
        """The file and the summary must not disagree about how many were replayed.

        The viewer's footer reads this list out of ``run.json``, so a block left
        as the acceptance check's own would have the page saying the advocates
        were replayed for cases the run never reached.
        """
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary, _ = self._replay(
                tmp, source, cases=CASE_SET[:3], token_budget=TOKENS_PER_CALL
            )
            metadata = runner.read_json(summary.run_dir / runner.METADATA_FILE)

        self.assertEqual(
            [o.case_no for o in summary.outcomes if o.replayed],
            metadata["replay"]["replayed_cases"],
            "the file lists cases the run never reached",
        )
        self.assertEqual(
            metadata["replay"]["replayed_cases"], summary.replay["replayed_cases"]
        )

    def test_every_case_a_completed_replay_ran_is_counted(self):
        """The same line on a run that finished: the count is the run's, and agrees."""
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary, _ = self._replay(tmp, source)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                runner.print_summary(summary)
            text = output.getvalue()

            self.assertEqual(tuple(CASE_SET), tuple(summary.replayed_cases))
            self.assertIn(
                "{0} of {1} cases reused them".format(len(CASE_SET), len(CASE_SET)),
                text,
            )

    def test_a_run_that_replayed_nothing_says_nothing_about_replay(self):
        """A report built from a run that asked its own agents claims nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            text = (summary.run_dir / runner.REPORT_FILE).read_text(encoding="utf-8")
            self.assertNotIn("Advocates replayed", text)
            self.assertNotIn("advocates replayed", text)
            self.assertFalse(summary.report.replay.any)
            self.assertEqual((), summary.report.replay.sources)

    # -- what a replay refuses --------------------------------------------
    def test_a_brief_that_moved_refuses_the_case_and_makes_no_call(self):
        def break_it(source, case_no):
            path = runner.case_cache_path(source, case_no)
            document = runner.read_json(path)
            document["brief_sha256"] = "0" * 64
            runner.write_json(path, document)

        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary = self._refused(tmp, source, 102, break_it)

            self.assertEqual([102], [outcome.case_no for outcome in summary.refusals])
            self.assertEqual([101, 103], summary.completed_cases)
            self.assertIn("brief this code builds", summary.refusals[0].failure_detail)
            self.assertEqual(runner.FAILURE_REPLAY, summary.refusals[0].failure_kind)

    def test_an_advocate_prompt_that_moved_refuses_the_case_and_makes_no_call(self):
        def break_it(source, case_no):
            def change(entries):
                for entry in entries:
                    if entry["role"] == transcript.ROLE_RIDER_ADVOCATE:
                        entry["system_sha256"] = "b" * 64

            self._rewrite_transcript(source, case_no, change)

        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary = self._refused(tmp, source, 101, break_it)

            self.assertEqual([101], [outcome.case_no for outcome in summary.refusals])
            self.assertIn(
                "system prompt as rendered now", summary.refusals[0].failure_detail
            )

    def test_a_prompt_the_source_never_recorded_refuses_rather_than_assuming(self):
        """The file not saying is not the same as the file saying it matches."""

        def break_it(source, case_no):
            def change(entries):
                for entry in entries:
                    if entry["role"] == transcript.ROLE_DRIVER_ADVOCATE:
                        entry.pop("system_sha256", None)

            self._rewrite_transcript(source, case_no, change)

        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary = self._refused(tmp, source, 103, break_it)

            self.assertEqual([103], [outcome.case_no for outcome in summary.refusals])
            self.assertIn(
                "recorded no system prompt digest", summary.refusals[0].failure_detail
            )

    def test_a_model_mismatch_refuses_the_case_and_makes_no_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            # The source was produced by another model, so its advocates answer
            # for that model and not for the one this run would use. Every case
            # is refused, so the transport may not be reached at all.
            source, _ = self._source(tmp, model=OTHER_MODEL)
            transport = RefusingTransport(refused=CASE_SET)
            summary, _ = bench(
                tmp,
                runs_dir=Path(tmp) / "replayed",
                force=True,
                replay_dir=source,
                transport=transport,
                model=MODEL,
            )
            self.assertEqual(0, transport.refused_calls)
            self.assertEqual(0, transport.calls())
            self.assertEqual(list(CASE_SET), [o.case_no for o in summary.refusals])
            self.assertIn("was made on", summary.refusals[0].failure_detail)
            self.assertIn(OTHER_MODEL, summary.refusals[0].failure_detail)

    def test_an_unparsed_recorded_answer_refuses_the_case_and_makes_no_call(self):
        def break_it(source, case_no):
            def change(entries):
                for entry in entries:
                    if entry["role"] == transcript.ROLE_RIDER_ADVOCATE:
                        entry["parsed"] = None
                        entry["parse_outcome"] = "NO_JSON"

            self._rewrite_transcript(source, case_no, change)

        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary = self._refused(tmp, source, 102, break_it)

            self.assertEqual([102], [outcome.case_no for outcome in summary.refusals])
            self.assertIn("did not parse", summary.refusals[0].failure_detail)

    def test_a_source_transcript_edited_since_it_was_written_is_refused(self):
        """The source's own record of its transcript is checked, not assumed."""

        def break_it(source, case_no):
            path = runner.transcript_path(source, case_no)
            path.write_text(
                path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
            )

        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary = self._refused(tmp, source, 101, break_it)

            self.assertEqual([101], [outcome.case_no for outcome in summary.refusals])
            self.assertIn(
                "does not hash to what that run recorded",
                summary.refusals[0].failure_detail,
            )

    def test_a_case_the_source_never_ran_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp, cases=(101, 102))
            transport = RefusingTransport(refused=103)
            summary, _ = bench(
                tmp,
                runs_dir=Path(tmp) / "replayed",
                force=True,
                replay_dir=source,
                transport=transport,
                cases=(101, 102, 103),
            )
            self.assertEqual(0, transport.refused_calls)
            self.assertEqual([103], [outcome.case_no for outcome in summary.refusals])
            self.assertEqual([101, 102], summary.completed_cases)

    def test_a_refused_case_leaves_no_cache_entry_and_no_transcript(self):
        """Nothing is written for a refusal, so a later run refuses it the same way."""

        def break_it(source, case_no):
            path = runner.case_cache_path(source, case_no)
            document = runner.read_json(path)
            document["brief_sha256"] = "0" * 64
            runner.write_json(path, document)

        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            summary = self._refused(tmp, source, 102, break_it)

            self.assertFalse(
                runner.case_cache_path(summary.run_dir, 102).is_file(),
                "a refused case was cached",
            )
            self.assertFalse(
                runner.transcript_path(summary.run_dir, 102).is_file(),
                "a refused case left a transcript",
            )

    def test_a_missing_source_directory_is_refused_rather_than_reported_case_by_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(runner.BenchmarkError):
                runner.check_replay(
                    Path(tmp) / "no-such-run", (101, 102, 103), model=MODEL
                )

    # -- the check itself --------------------------------------------------
    def test_the_check_reads_only_and_reports_each_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            before = sorted(path.name for path in source.iterdir())

            check = runner.check_replay(source, CASE_SET, model=MODEL)

            self.assertEqual(list(CASE_SET), check.accepted_cases)
            self.assertEqual([], check.refused_cases)
            self.assertTrue(check.replayable)
            self.assertEqual(str(source), check.provenance()["run_dir"])
            self.assertEqual(COMMIT, check.provenance()["git_commit"])
            # Nothing was written anywhere: the check reads.
            self.assertEqual(before, sorted(path.name for path in source.iterdir()))
            self.assertFalse((Path(tmp) / "replayed").exists())

            text = runner.render_replay_check(check)
            for case_no in CASE_SET:
                self.assertIn("case {0}  accepted".format(case_no), text)
            self.assertIn("3 accepted, 0 refused", text)
            self.assertIn("No model was called and nothing was written", text)

    def test_the_check_names_a_refusal_and_its_reason(self):
        def break_it(source, case_no):
            path = runner.case_cache_path(source, case_no)
            document = runner.read_json(path)
            document["brief_sha256"] = "0" * 64
            runner.write_json(path, document)

        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            break_it(source, 102)

            check = runner.check_replay(source, CASE_SET, model=MODEL)

            self.assertEqual([101, 103], check.accepted_cases)
            self.assertEqual([102], check.refused_cases)
            text = runner.render_replay_check(check)
            self.assertIn("case 102  REFUSED", text)
            self.assertIn("brief this code builds", text)
            self.assertIn("2 accepted, 1 refused", text)

    def test_every_source_is_read_before_anything_is_written(self):
        """The check completes before the first write, which is what makes a
        replay into the source run's own directory safe."""
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            order = []
            real_check = runner.check_replay
            real_write = runner._write_text_atomic

            def check(*args, **kwargs):
                order.append("check")
                return real_check(*args, **kwargs)

            def write(*args, **kwargs):
                order.append("write")
                return real_write(*args, **kwargs)

            with mock.patch.object(runner, "check_replay", check), mock.patch.object(
                runner, "_write_text_atomic", write
            ):
                # ``runs_dir`` is the runs *root*, so passing the source's own
                # parent is what makes this a replay into the directory it reads
                # from rather than into a nested one.
                summary, transport = self._replay(
                    tmp, source, runs_dir=source.parent, cases=CASE_SET
                )

            self.assertEqual("check", order[0], "something was written before the check")
            self.assertIn("write", order)
            self.assertEqual(list(CASE_SET), summary.completed_cases)
            self.assertEqual(len(CASE_SET), transport.calls())

    def test_a_replay_into_its_own_directory_reads_the_original_entries(self):
        """Replayed in place, the run still reuses the advocates it recorded.

        If the check ran after the first case was rewritten, the later cases
        would be reading this run's output rather than the run it was asked to
        replay -- and the transcripts would be a copy of a copy.
        """
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            original = {
                case_no: runner.file_sha256(runner.transcript_path(source, case_no))
                for case_no in CASE_SET
            }

            summary, transport = self._replay(tmp, source, runs_dir=source.parent)

            self.assertEqual(list(CASE_SET), summary.completed_cases)
            self.assertEqual([], summary.failures)
            self.assertEqual(len(CASE_SET), transport.calls())
            for case_no in CASE_SET:
                with self.subTest(case_no=case_no):
                    document = runner.load_cached(source, case_no)
                    self.assertEqual(
                        original[case_no], document["replay"]["transcript_sha256"]
                    )
                    # The entry the replay recorded is the one it read, not the
                    # one it had just written.
                    self.assertNotEqual(
                        document["replay"]["transcript_sha256"],
                        document["transcript_sha256"],
                    )

    def test_an_external_case_is_never_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)
            check = runner.check_replay(source, (101,), model=MODEL)

            with self.assertRaises(runner.BenchmarkError):
                runner.run_one_case(
                    101,
                    client=None,
                    prompts_dir=PROMPTS_DIR,
                    expected=None,
                    loaded_case={"case_no": 101},
                    replay=check.accepted[101],
                )

    def test_the_command_line_refuses_replay_for_an_external_case(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                runner.main(
                    [
                        "--external",
                        "data/external/ryde/case-901.json",
                        "--replay-advocates",
                        "runs/deepseek-deepseek-flash",
                    ]
                )

    def test_the_check_flag_reports_the_list_and_exits_non_zero_on_a_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._source(tmp)

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = runner.main(
                    [
                        "--model",
                        MODEL,
                        "--replay-check",
                        str(source),
                        "--cases",
                        "101,102,103",
                    ]
                )
            self.assertEqual(0, code)
            self.assertIn("3 accepted, 0 refused", out.getvalue())

            path = runner.case_cache_path(source, 102)
            document = runner.read_json(path)
            document["brief_sha256"] = "0" * 64
            runner.write_json(path, document)

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = runner.main(
                    [
                        "--model",
                        MODEL,
                        "--replay-check",
                        str(source),
                        "--cases",
                        "101,102,103",
                    ]
                )
            # Non-zero, because a partial acceptance means those cases would be
            # run in full rather than replayed, and a caller gating a paid run on
            # this must be able to see that without reading the text.
            self.assertEqual(1, code)
            self.assertIn("2 accepted, 1 refused", out.getvalue())

    def test_compare_takes_no_replay_arguments(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                runner.main(["--compare", "--replay-advocates", "runs/x"])


class SummaryOutputTests(unittest.TestCase):
    """The run's own summary, printed rather than only written to a file."""

    def _printed(self, summary):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            runner.print_summary(summary)
        return output.getvalue()

    def test_the_summary_names_the_provenance_and_the_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            text = self._printed(summary)

            self.assertIn(MODEL, text)
            self.assertIn(COMMIT[:12], text)
            self.assertIn("clean", text)
            self.assertIn("{0} completed".format(len(CASE_SET)), text)
            self.assertIn(
                "{0}/{1}".format(len(CASE_SET), len(CASE_SET)), text
            )
            for field in grade.GRADED_FIELDS:
                with self.subTest(field=field):
                    self.assertIn(field, text)
            self.assertIn("precision", text)
            self.assertIn("recall", text)
            self.assertIn(runner.REPORT_FILE, text)

    def test_a_subset_summary_does_not_print_the_corpus_target(self):
        # The defect, as a regression test: a run over a hand-picked set used to
        # print "escalation  2/3 = 66.7%  (target 17.2%)", comparing the
        # subset's rate to the whole corpus's base rate and inviting the
        # conclusion that the system over-escalates when the set was selected
        # to contain escalations.
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=WIDER_SET)
            text = self._printed(summary)

            self.assertFalse(summary.report.grades_full_corpus)
            self.assertIn("a selected subset", text)
            self.assertIn(", ".join(str(case_no) for case_no in WIDER_SET), text)
            self.assertIn("not comparable to the corpus base rate", text)
            # The target is not printed beside the rate, in either form.
            self.assertNotIn("(target", text)
            self.assertNotIn(
                grade.render_percent(summary.report.calibration.target_rate), text
            )
            # The counts are, because they are what survives subsetting.
            for label in (
                "true positives",
                "false positives",
                "false negatives",
                "over-escalations",
                "under-escalations",
            ):
                with self.subTest(label=label):
                    self.assertIn(label, text)

    def test_a_full_corpus_summary_prints_the_target(self):
        key = answer_key()
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=sorted(key))
            text = self._printed(summary)

            self.assertTrue(summary.report.grades_full_corpus)
            self.assertIn("the whole corpus", text)
            self.assertIn("(target 17.2%)", text)
            self.assertNotIn("not comparable to the corpus base rate", text)

    def test_a_budget_stop_is_visible_in_the_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, token_budget=0)
            text = self._printed(summary)

            self.assertIn("stopped on budget: True", text)
            self.assertIn(runner.STOP_BUDGET, text)

    def test_a_dirty_tree_is_visible_in_the_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, git=git_runner(status=DIRTY_STATUS))
            self.assertIn("tree DIRTY", self._printed(summary))

    def test_the_failed_cases_are_listed_with_the_reason(self):
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key), fail={(102, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, transport=transport)
            text = self._printed(summary)

            self.assertIn("failed cases", text)
            self.assertIn("case 102", text)
            self.assertIn("not cached", text)

    def test_an_indeterminate_case_ruled_confidently_is_named(self):
        """The failure this block exists to keep visible, not averaged away."""
        key = answer_key()
        produced = produced_from_key(key)

        def rule_confidently(case_no, ruling):
            if case_no == 110:
                ruling["ruling"] = "NO_ACTION"
                ruling["amount_sgd"] = None
                ruling["driver_compensation_sgd"] = None
            return ruling

        transport = ScriptedTransport(produced, mutate=rule_confidently)
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=WIDER_SET, transport=transport)
            text = self._printed(summary)

            self.assertEqual((110,), summary.report.calibration.indeterminate_ruled_confidently)
            self.assertIn("INDETERMINATE cases ruled confidently: 110", text)
            self.assertEqual((110,), summary.report.calibration.under_escalations)
            self.assertEqual(0, len(summary.report.calibration.over_escalations))


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------
class CommandLineTests(unittest.TestCase):
    """Argument handling only: the tests never let ``main`` reach a model."""

    def test_a_case_selection_is_parsed(self):
        self.assertEqual([101, 102, 103], runner.parse_cases("101,102,103"))
        self.assertEqual([101, 102], runner.parse_cases(" 101 , 102 "))
        self.assertEqual([], runner.parse_cases(""))
        self.assertEqual([], runner.parse_cases(None))

    def test_a_selection_that_is_not_a_case_number_is_refused(self):
        for text in ("101,abc", "one", "-101", "10.1"):
            with self.subTest(text=text):
                with self.assertRaises(runner.BenchmarkError):
                    runner.parse_cases(text)

    def test_a_trailing_comma_is_tolerated(self):
        """A trailing separator is a slip, not an instruction to run case nothing."""
        self.assertEqual([101, 102], runner.parse_cases("101,102,"))

    def test_compare_reads_the_runs_directory_and_makes_no_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            bench(tmp, cases=WIDER_SET, runs_dir=runs)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = runner.main(["--compare", "--runs-dir", str(runs)])

            self.assertEqual(0, status)
            self.assertIn(MODEL, output.getvalue())
            self.assertIn("exact", output.getvalue())

    def test_compare_on_an_empty_directory_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = runner.main(["--compare", "--runs-dir", str(Path(tmp) / "runs")])
            self.assertEqual(0, status)
            self.assertIn("No cached runs found", output.getvalue())

    def test_compare_takes_no_model(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as raised:
                runner.main(["--compare", "--model", MODEL])
        self.assertEqual(2, raised.exception.code)
        self.assertIn("--compare", errors.getvalue())

    def _model_the_cli_resolved(self, argv):
        """Run the CLI with the runner stubbed out, and report the model it chose.

        The stub is the point: this asserts what the command line decides, and a
        test that reached a real model to find out would be measuring something
        else, slowly and at a price.
        """
        captured = []
        summary = runner.RunSummary(
            model="(stub)",
            run_dir=Path("/nonexistent"),
            started_at="2026-01-01T00:00:00+00:00",
            ended_at="2026-01-01T00:00:01+00:00",
            stop_reason=runner.STOP_COMPLETED,
        )

        def fake_run_benchmark(model, cases, **kwargs):
            captured.append(model)
            return summary

        output = io.StringIO()
        with mock.patch.object(runner, "run_benchmark", fake_run_benchmark):
            with contextlib.redirect_stdout(output):
                status = runner.main(argv)

        self.assertEqual(1, len(captured), "the runner was not driven exactly once")
        return captured[0], status

    def test_a_run_without_a_model_uses_the_decided_one(self):
        """The decision is load-bearing: the flag is an override, not a demand."""
        model, status = self._model_the_cli_resolved(["--cases", "101"])

        self.assertEqual(RUNTIME_MODEL, model)
        self.assertEqual(0, status)

    def test_a_named_model_overrides_the_decision(self):
        model, status = self._model_the_cli_resolved(["--cases", "101", "--model", MODEL])

        self.assertEqual(MODEL, model)
        self.assertNotEqual(RUNTIME_MODEL, model)
        self.assertEqual(0, status)

    def test_the_model_flag_has_no_default_in_the_parser(self):
        import inspect

        signature = inspect.signature(runner.run_benchmark)
        self.assertIs(
            inspect.Parameter.empty, signature.parameters["model"].default
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(runner.BenchmarkError):
                bench(tmp, model="")


# --------------------------------------------------------------------------
# The runner's own contract
# --------------------------------------------------------------------------
class ContractTests(unittest.TestCase):
    """The refusals, and the one place a run can be told to stop early."""

    def test_no_cases_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(runner.BenchmarkError):
                bench(tmp, cases=())

    def test_a_case_outside_the_answer_key_is_refused(self):
        """A run over cases the key does not carry could not be graded."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(runner.BenchmarkError):
                bench(tmp, cases=(99999,))

    def test_a_repeated_case_is_one_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, transport = bench(tmp, cases=(101, 101, 102))
            self.assertEqual([101, 102], summary.completed_cases)
            self.assertEqual([101, 102], transport.cases_called())

    def test_the_summary_counts_agree_with_the_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            self.assertEqual(
                len(CASE_SET),
                len(summary.completed_cases) + len(summary.cached_cases) + len(summary.failures),
            )
            self.assertEqual(len(CASE_SET), len(summary.outcomes))

    def test_a_finished_run_with_a_failed_case_is_not_ok(self):
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key), fail={(102, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, transport=transport)
            self.assertTrue(summary.completed)
            self.assertFalse(summary.ok)

    def test_the_metadata_case_lists_cover_the_requested_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            metadata = runner.read_json(runner.metadata_path(summary.run_dir))
            self.assertEqual(list(CASE_SET), metadata["cases"]["requested"])
            self.assertEqual([], metadata["cases"]["cached"])
            self.assertEqual(list(CASE_SET), metadata["cases"]["completed"])
            self.assertEqual([], metadata["cases"]["failed"])

    def test_the_run_directory_is_created_when_it_does_not_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "deep" / "nested" / "runs"
            summary, _ = bench(tmp, runs_dir=runs)
            self.assertTrue(summary.run_dir.is_dir())

    def test_a_run_stopped_on_budget_exits_non_zero(self):
        """A caller in a shell can see a partial run without reading the report."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, token_budget=0)
            self.assertFalse(summary.ok)
            self.assertFalse(summary.completed)

    def test_the_failure_breakdown_is_by_agent_not_by_case_number_alone(self):
        key = answer_key()
        transport = ScriptedTransport(
            produced_from_key(key), fail={(102, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, transport=transport)
            outcome = summary.failures[0]
            self.assertEqual(transcript.ROLE_JUDGE, outcome.failed_agent)
            self.assertTrue(outcome.failure_reason)
            self.assertEqual(runner.STATUS_FAILED, outcome.status)
            self.assertIsNone(outcome.matched)


class AmountProvenanceTests(unittest.TestCase):
    """Where an amount came from, kept apart from how much it was."""

    def test_a_ruling_that_carries_no_amount_answers_not_applicable(self):
        found = runner.amount_provenance(
            {
                "ruling": {
                    "ruling": "NO_ACTION",
                    "amount_sgd": None,
                    "driver_compensation_sgd": None,
                }
            },
            None,
        )
        self.assertEqual(
            {name: "n/a" for name in pipeline.MONEY_FIELDS}, dict(found)
        )

    def test_no_ruling_object_at_all_answers_not_applicable(self):
        """``ESCALATE`` and a case that produced nothing both carry no amount,
        and neither is a figure that failed to read off."""
        self.assertEqual(
            {name: "n/a" for name in pipeline.MONEY_FIELDS},
            dict(runner.amount_provenance(None, None)),
        )


class DecimalColumnTests(unittest.TestCase):
    """A duration and a vote are carried as ``Decimal``; a non-number is ``None``."""

    def test_a_number_becomes_the_decimal_it_prints_as(self):
        self.assertEqual(Decimal("0.75"), runner._decimal_or_none(0.75))
        self.assertEqual(Decimal("12.3"), runner._decimal_or_none("12.3"))
        self.assertEqual(Decimal("0"), runner._decimal_or_none(0))

    def test_a_figure_that_was_not_recorded_is_none_rather_than_zero(self):
        for value in (None, "", "n/a", True, False, [1], {"a": 1}, float("nan")):
            self.assertIsNone(runner._decimal_or_none(value), repr(value))


class PerCaseColumnTests(unittest.TestCase):
    """The new columns, over a run the runner actually made."""

    def test_the_token_split_is_the_transcript_s_own_by_role(self):
        """Two advocate calls and one judge call per case at K = 1."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            document = runner.load_cached(summary.run_dir, 102)
            facts = runner.case_facts(summary.run_dir, 102, document)

            self.assertEqual(2 * TOKENS_PER_CALL, facts.advocate_tokens)
            self.assertEqual(TOKENS_PER_CALL, facts.judge_tokens)

    def test_a_case_with_no_transcript_has_no_split_rather_than_zero(self):
        """A replayed case's advocates were never called here, and ``0 / 0``
        would claim they were called and cost nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            document = runner.load_cached(summary.run_dir, 102)
            runner.transcript_path(summary.run_dir, 102).unlink()
            facts = runner.case_facts(summary.run_dir, 102, document)

            self.assertIsNone(facts.advocate_tokens)
            self.assertIsNone(facts.judge_tokens)

    def test_the_duration_is_a_decimal_and_the_provenance_is_computed(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            document = runner.load_cached(summary.run_dir, 102)
            facts = runner.case_facts(summary.run_dir, 102, document)

            self.assertIsInstance(facts.wall_seconds, Decimal)
            self.assertEqual(
                set(grade.EXPLANATION_TAG_NAMES), set(facts.explanation_tags)
            )
            self.assertNotIn("brief not available", set(facts.amount_provenance.values()))

    def test_a_run_that_asked_the_judge_once_holds_no_vote(self):
        """The column prints a dash, which is not the same as agreement 0.00."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            document = runner.load_cached(summary.run_dir, 102)
            facts = runner.case_facts(summary.run_dir, 102, document)

            self.assertIsNone(facts.vote_agreement)

    def test_the_columns_are_in_the_report_the_runner_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp)
            text = (summary.run_dir / runner.REPORT_FILE).read_text(encoding="utf-8")

            self.assertIn("cost, provenance and explanation tags", text)
            for column in grade.CASE_FACTS_COLUMNS:
                self.assertIn(column, text)

    def test_the_escalated_column_follows_the_ruling(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = bench(tmp, cases=WIDER_SET)
            rows = {row[0]: row for row in grade.case_fact_rows(summary.report)}

            # 0 case, 1 advocates, 2 judge, 3 wall, 4 escalated, 5 vote.
            self.assertEqual("yes", rows["110"][4])
            self.assertEqual("no", rows["101"][4])
            self.assertEqual("-", rows["101"][5])


# --------------------------------------------------------------------------
# Concurrent calls
# --------------------------------------------------------------------------
def invocation_start(run_dir):
    """The invocation's own first line, and the only one it writes."""
    path = Path(run_dir) / events.EVENTS_FILE
    starts = [
        event
        for event in events.read_events(path)
        if event["event"] == events.EVENT_INVOCATION_START
    ]
    assert len(starts) == 1, "expected exactly one invocation_start, found {0}".format(
        len(starts)
    )
    return starts[0]


class ParallelCallsTests(unittest.TestCase):
    """The switch is recorded where it belongs, and nowhere else.

    ``--parallel-calls`` decides *when* a call is made. **No individual request
    body changes**, so it is not part of the case's ``configuration`` object and
    not part of any staleness or cache key: it is named on the invocation's own
    line and on this run's ``run.json``, and that is all. What it can change is
    the *set* of requests -- a parallel run can spend up to two driver requests
    after the rider fails, and the remaining draft requests after a draft raises
    -- and under a case deadline it can send a different set again. And because
    the calls of one case can finish in any order, the ``calls.json`` a run
    writes is sorted by the call's own position -- the case's place in the
    requested list, the role rank, the draft and the attempt -- rather than by
    the order the answers came back.
    """

    def both(self, tmp):
        """One plain run and one parallel run, in two run directories."""
        plain, _ = bench(tmp)
        parallel, _ = bench(
            tmp, runs_dir=Path(tmp) / "parallel", parallel_calls=True
        )
        return plain, parallel

    def test_the_switch_is_not_part_of_the_configuration(self):
        """It is not a switch that says anything about what a result measured."""
        with tempfile.TemporaryDirectory() as tmp:
            plain, parallel = self.both(tmp)

            for summary in (plain, parallel):
                document = runner.load_cached(summary.run_dir, 101)
                self.assertEqual(
                    runner.configuration_document(judge_votes=1, verify_drafts=False),
                    document["configuration"],
                )
                self.assertEqual(
                    sorted(runner.CONFIGURATION_FIELDS),
                    sorted(document["configuration"]),
                )
                self.assertNotIn("parallel_calls", document["configuration"])

    def test_run_json_names_the_switch_only_when_it_is_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain, parallel = self.both(tmp)

            off = runner.read_json(plain.run_dir / runner.METADATA_FILE)
            on = runner.read_json(parallel.run_dir / runner.METADATA_FILE)

            self.assertNotIn("parallel_calls", off)
            self.assertIs(True, on["parallel_calls"])

    def test_the_invocation_start_event_names_it_only_when_it_is_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain, parallel = self.both(tmp)

            self.assertNotIn("parallel_calls", invocation_start(plain.run_dir))
            self.assertIs(True, invocation_start(parallel.run_dir)["parallel_calls"])

    def test_the_calls_file_is_in_call_order_not_completion_order(self):
        """With the calls overlapping, the file is the run's, not the network's.

        Each record is placed by the position of the call that made it -- the
        case's place in the **requested** list, then the role rank, then the
        draft, then the attempt -- which is a function of the run alone. The
        order the answers arrived in is not, so the two are compared here: the
        file is sorted, and the order the transport answered in is not. The
        transport delays the rider past the driver, so this comparison is not
        one that would hold whatever the file said.

        The count is not asserted here:
        ``test_the_calls_file_records_one_entry_per_request`` already holds that
        one record is written per request.
        """
        with tempfile.TemporaryDirectory() as tmp:
            transport = DelayingTransport(produced_from_key(answer_key()))
            summary, transport = bench(
                tmp, transport=transport, parallel_calls=True
            )
            document = runner.read_json(summary.run_dir / runner.CALLS_FILE)

            bodies = {
                hashlib.sha256(
                    json.dumps(request, ensure_ascii=False).encode("utf-8")
                ).hexdigest(): request
                for request in transport.requests
            }
            recorded = [
                call_position(bodies[record["request_sha256"]])
                for record in document["calls"]
            ]
            recorded_roles = [
                role_of(bodies[record["request_sha256"]])[1]
                for record in document["calls"]
            ]
            answered = [call_position(request) for request in transport.requests]

            self.assertEqual(sorted(recorded), recorded, "the file is not in call order")
            self.assertNotEqual(
                answered,
                recorded,
                "the answers came back in call order, so this proves nothing",
            )
            # Written in call order, and the call order is the case's own:
            # rider, then driver, then judge. The role rank is what puts the
            # rider first, because the names sort driver, judge, rider.
            self.assertEqual(
                [
                    (case_no, role)
                    for case_no in CASE_SET
                    for role in (
                        transcript.ROLE_RIDER_ADVOCATE,
                        transcript.ROLE_DRIVER_ADVOCATE,
                        transcript.ROLE_JUDGE,
                    )
                ],
                [
                    (case_no, role)
                    for (case_no, _rank, _draft), role in zip(recorded, recorded_roles)
                ],
            )

    def test_four_drafts_and_a_verifier_are_written_in_call_order(self):
        """The file is the run's order, and the verifier is the last call in it.

        Four drafts, the verifier on and two cases at once, over a transport that
        answers out of order: the rider's answer comes back after the driver's
        and the last draft's before the first's. The file is sorted by the call's
        own position -- the case's place in the **requested** list, then the role
        rank, then the draft, then the attempt -- so it reads in the order the
        calls were *made* in, which is a function of the run and not of the
        network.

        The two cases are asked for in **reverse** number order (102 then 101),
        so a file sorted by case number rather than by requested position would
        be in the wrong order and this test would say so. And both modes are run:
        the switch decides when a call is made, not what the record says, so the
        two files must read the same.
        """

        def stating_a_fact(case_no, ruling):
            ruling["explanation"] = (
                "the fare of 8.05 SGD was charged and EV-GPS-00101 was on the record"
            )
            return ruling

        asked = (102, 101)
        positions = {case_no: index + 1 for index, case_no in enumerate(asked)}
        orders = []
        with tempfile.TemporaryDirectory() as tmp:
            for parallel in (False, True):
                mode = "parallel" if parallel else "sequential"
                transport = DelayingTransport(
                    produced_from_key(answer_key()), mutate=stating_a_fact
                )
                summary, transport = bench(
                    tmp,
                    cases=asked,
                    runs_dir=Path(tmp) / mode,
                    transport=transport,
                    judge_votes=4,
                    verify_drafts=True,
                    parallel_calls=parallel,
                    concurrency=2,
                )
                records = runner.read_json(summary.run_dir / runner.CALLS_FILE)["calls"]
                order = call_order(records, transport, positions)
                arrived = [(case_no, role) for case_no, role in transport.roles]

                with self.subTest(mode=mode):
                    self.assertEqual(
                        2,
                        [role for _case, role in arrived].count(
                            transcript.ROLE_VERIFIER
                        ),
                        "the verifier is one call per case, and both cases are here",
                    )
                    self.assertEqual(
                        sorted(order), order, "the file is not in call order"
                    )
                    if parallel:
                        self.assertNotEqual(
                            [
                                (positions[case_no], CALL_RANK[role])
                                for case_no, role in arrived
                            ],
                            [(key[0], key[1]) for key in order],
                            "the answers came back in call order, so this proves nothing",
                        )
                    for case_no in asked:
                        per_case = [key for key in order if key[0] == positions[case_no]]
                        self.assertEqual(
                            [0, 1, 2, 2, 2, 2, 3],
                            [key[1] for key in per_case],
                            "a case's calls are not in the order they were made",
                        )
                        self.assertEqual(
                            [1, 2, 3, 4],
                            [key[2] for key in per_case if key[1] == 2],
                            "the drafts are not in position order",
                        )
                        self.assertEqual(
                            [1, 1, 1, 1, 1, 1, 1],
                            [key[3] for key in per_case],
                            "nothing here retried, so every attempt is the first",
                        )
                orders.append(order)
            self.assertEqual(
                orders[0], orders[1], "the two modes wrote different orders"
            )

    def test_two_parallel_runs_write_the_same_call_order(self):
        """Two runs of one set differ in the clock and in nothing else.

        Every record carries the instant its call finished, so two files are not
        byte-identical and are not meant to be. What is a function of the run
        alone is the order: the same calls, in the same positions, twice -- which
        is the property a completion order could not have.
        """
        with tempfile.TemporaryDirectory() as tmp:
            first, _ = bench(tmp, runs_dir=Path(tmp) / "a", parallel_calls=True)
            second, _ = bench(tmp, runs_dir=Path(tmp) / "b", parallel_calls=True)

            def order(summary):
                document = runner.read_json(summary.run_dir / runner.CALLS_FILE)
                return [record["request_sha256"] for record in document["calls"]]

            self.assertTrue(order(first))
            self.assertEqual(order(first), order(second))

    def test_the_sort_key_is_the_position_and_carries_the_attempt(self):
        """``call_sort_key`` is ``(case, role rank, draft, attempt)``.

        The last element is the attempt, and it is load-bearing: a retried call
        sends one body twice, so its two records carry the same digest and
        nothing else in ``calls.json`` tells them apart. It is asserted here
        because a file cannot show it -- the sort's own stability puts the two in
        arrival order either way -- so the key is the only place the attempt is
        observable.
        """
        token = pipeline.CALL_CONTEXT.set((101, transcript.ROLE_VERIFIER, 0, 2))
        try:
            self.assertEqual(
                (101, CALL_RANK[transcript.ROLE_VERIFIER], 0, 2),
                pipeline.call_sort_key(),
            )
        finally:
            pipeline.CALL_CONTEXT.reset(token)
        # No call of this pipeline in flight: a client driven by a test directly.
        self.assertEqual((-1, -1, -1, -1), pipeline.call_sort_key())


if __name__ == "__main__":
    unittest.main()
