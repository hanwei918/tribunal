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
  cannot be rebuilt is unknown rather than current, and a grading over a mixed
  set says on its face that its exact-match figure is not one measurement —
  with the digest shown to be the one the pipeline itself recorded, so the
  check cannot be satisfied by comparing against a constant;
* per-case provenance: every cache entry carries the commit and the prompts
  digest it was produced under, beside the brief digest it already kept;
* the run record: a second invocation over a different case set leaves the
  first invocation's own record — its case list and its token total — intact in
  ``invocations.json``, while ``run.json`` describes only the invocation that
  wrote it and its directory block says what the directory actually holds;
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
import io
import json
import re
import sys
import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import grade  # noqa: E402
from eval import run_benchmark as runner  # noqa: E402
from tests import test_answer_isolation as isolation  # noqa: E402
from tribunal import llm, money, transcript  # noqa: E402

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
CLAIM_ARRAY = '[{"claim_id": "C1", "evidence_id": "E1", "clause_id": "POL-GEN-03"}]'

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
    ``brief`` and ``claims``; the advocates are handed the brief itself.
    """
    system = request["messages"][0]["content"]
    parsed = json.loads(request["messages"][1]["content"])

    if isinstance(parsed, dict) and set(parsed) == {"brief", "claims"}:
        return parsed["brief"]["case"]["case_no"], transcript.ROLE_JUDGE

    case_no = parsed["case"]["case_no"]
    if RIDER_STANCE in system:
        return case_no, transcript.ROLE_RIDER_ADVOCATE
    if DRIVER_STANCE in system:
        return case_no, transcript.ROLE_DRIVER_ADVOCATE
    raise AssertionError("a request is neither an advocate's nor the judge's")


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
        self._lock = threading.Lock()

    def __call__(self, url, headers, body, timeout):
        request = json.loads(body.decode("utf-8"))
        case_no, role = role_of(request)
        with self._lock:
            self.requests.append(request)
            self.roles.append((case_no, role))

        if (case_no, role) in self.fail:
            return llm.HttpResult(status=self.fail_status, body=b'{"error": "scripted failure"}')

        if role == transcript.ROLE_JUDGE:
            ruling = dict(self.produced[case_no]["ruling"])
            if self.mutate is not None:
                ruling = self.mutate(case_no, ruling)
            content = money.dumps_canonical({"ruling": ruling, "discarded_claims": []})
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
                        # Per-case provenance, beside the digest it belongs to.
                        # The commit and the prompts a result was produced under
                        # must survive in the result's own file: a run-level
                        # record is overwritten by the next invocation, so
                        # provenance that lives only there dies with it.
                        "git_commit",
                        "matched",
                        "model",
                        "prompts_sha256",
                        "recorded_at",
                        "ruling",
                        "ruling_findings",
                        "schema_version",
                        "stance_differing_ranges",
                        "tokens",
                        "transcript_file",
                        "transcript_sha256",
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
# Progress
# --------------------------------------------------------------------------
class ProgressTests(unittest.TestCase):
    """One line per case, printed as it lands rather than at the end."""

    def test_one_line_per_case_names_the_number_verdict_clock_and_tokens(self):
        lines = []
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp, progress=lines.append)

        self.assertEqual(len(CASE_SET), len(lines), "a case printed no line")
        for case_no, line in zip(CASE_SET, lines):
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
        lines = []
        cases = (101, 102, 103, 105)
        with tempfile.TemporaryDirectory() as tmp:
            bench(tmp, cases=cases, concurrency=4, progress=lines.append)
        self.assertEqual(len(cases), len(lines))

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
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._cached_run(tmp)
            staleness = runner.brief_staleness(run_dir, CASE_SET)

            self.assertTrue(staleness.checked, "the check must say it was made")
            self.assertEqual((), staleness.stale)
            self.assertEqual((), staleness.unknown)
            self.assertFalse(staleness.mixed)
            for case_no in CASE_SET:
                with self.subTest(case=case_no):
                    self.assertEqual(
                        grade.STALENESS_CURRENT,
                        runner.BriefStaleness().status_of(
                            case_no, runner.load_cached(run_dir, case_no)
                        ),
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
                runner.BriefStaleness().status_of(
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
            self.assertIn("| **STALE** |", text)
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
            self.assertIn("stale", table.splitlines()[0])
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

    def test_the_summary_says_when_a_reused_result_is_stale(self):
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

            self.assertIn("stale briefs", text)
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


class NoteCouplingTests(unittest.TestCase):
    """The note states a count about the cache; the code computes that count.

    Nothing compared them, and the note carried a figure the implementation
    cannot produce for a day. These tests read the numbers out of the note and
    hold them against ``grade_run`` over the same directories, so the two cannot
    drift apart again without a test going red.

    The cache under ``runs/`` is untracked, so on a checkout without it there is
    nothing to compare against: that comparison is skipped and the skip says so.
    What is asserted unconditionally is that the note's own numbers agree with
    each other — which is the check that would have caught the earlier figure.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = STALE_NOTE.read_text(encoding="utf-8")
        cls.claim = parse_cached_claim(cls.text)

    def test_the_note_states_a_count_for_at_least_one_directory(self):
        self.assertTrue(
            self.claim, "the note no longer states a cached count for any directory"
        )

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
        """The coupling itself: the note's numbers against the code's."""
        compared = []
        absent = []
        for directory, block in sorted(self.claim.items()):
            run_dir = PROJECT_ROOT / "runs" / directory
            if not run_dir.is_dir():
                absent.append(directory)
                continue
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
            compared.append(directory)

        if not compared:
            self.skipTest(
                "no cached run directory is present ({0}); the note's numbers are "
                "re-derived by the command it states".format(", ".join(absent))
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

    def test_a_run_without_a_model_is_refused(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as raised:
                runner.main(["--cases", "101"])
        self.assertEqual(2, raised.exception.code)
        self.assertIn("--model is required", errors.getvalue())

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


if __name__ == "__main__":
    unittest.main()
