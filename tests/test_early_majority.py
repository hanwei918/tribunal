"""The early-majority switch: the panel publishes once a majority has settled.

``--early-majority`` is off by default and needs ``--parallel-calls``. On, the
judge's panel publishes as soon as the position-swapped draft and two sampled
drafts are back **and** three of the returned drafts are valid and agree on all
four graded fields; otherwise it waits for every draft, exactly as it did before
the switch existed.

Every test here drives the real :func:`tribunal.pipeline.run_case` -- the real
:class:`tribunal.llm.LLMClient`, the real rate limiter, the real code checks and
the real four-field reduction -- over a transport that answers each draft after
a **fixed delay**. The delay is the point: with the calls in flight together
there is no arrival order to script against, so the order the drafts come back
in has to be the script's rather than the network's. A draft's delay is keyed by
its position in the panel -- the three sampled drafts by their seed, the
position-swapped draft by the client's own settings -- and the transport records
the order its answers were returned in, so a test can assert that three drafts
really were back before the panel published.

No network, no credential, no model call, no browser. Run from the project root
with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import json
import sys
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, run_benchmark  # noqa: E402
from tribunal import llm, pipeline, transcript as transcript_module  # noqa: E402

FAKE_KEY = "tok-live-FAKEKEY-0123456789abcdef-DO-NOT-LEAK"
PINNED_NOW = "2026-09-21T12:00:00+00:00"

# The corpus case the fixtures are built for. Its brief publishes a
# POL-NS-03(ii) pin-ambiguity goodwill of 4.00, which is the amount a draft must
# state to pass the code checks -- see :func:`panel_ruling`.
CASE = 208
VOTES = pipeline.DEFAULT_JUDGE_VOTES
SAMPLED = pipeline.DRAFT_SAMPLED
POSITION_SWAPPED = pipeline.DRAFT_POSITION_SWAPPED

RIDER = transcript_module.ROLE_RIDER_ADVOCATE
DRIVER = transcript_module.ROLE_DRIVER_ADVOCATE
JUDGE = transcript_module.ROLE_JUDGE

RIDER_CLAIMS = json.dumps(
    [{"text": "rider point", "evidence_ids": ["EV-GPS-00208"], "clause_ids": ["POL-NS-01"]}]
)
DRIVER_CLAIMS = json.dumps(
    [{"text": "driver point", "evidence_ids": ["EV-GPS-00208"], "clause_ids": ["POL-NS-02"]}]
)

# The shape a draft's answer arrives in when the checks must reject it. It is
# unusable twice, so the draft it belongs to makes both of its attempts.
UNUSABLE = json.dumps({"not": "a judge answer"})


class _Writer:
    """A file-like sink for ``redirect_stdout``/``redirect_stderr``."""

    def __init__(self) -> None:
        self.text: List[str] = []

    def write(self, text: str) -> int:
        self.text.append(text)
        return len(text)

    def flush(self) -> None:
        return None

    def __str__(self) -> str:
        return "".join(self.text)


def envelope(answer: str) -> llm.HttpResult:
    body = json.dumps(
        {
            "choices": [{"message": {"content": answer}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "completion_tokens_details": {"reasoning_tokens": 0},
                "prompt_tokens_details": {"cached_tokens": 0},
            },
        }
    )
    return llm.HttpResult(status=200, body=body.encode("utf-8"))


def panel_ruling(
    value: str = "PARTIAL_REFUND",
    amount: Optional[float] = 4.0,
    confidence: float = 0.85,
    explanation: str = "because",
) -> str:
    """One judge answer, as the scripted transport hands it back.

    ``amount`` defaults to 4.0 because that is a figure the brief for
    :data:`CASE` publishes -- POL-NS-03(ii)'s pin-ambiguity goodwill of 4.00 --
    and a draft is held to the brief's own calculator before it may vote. A
    fixture the checks would reject would measure the check and not the rule.
    ``NO_ACTION`` with no amount is the other valid proposal the fixtures use,
    and it is what a dissenting draft says.
    """
    return json.dumps(
        {
            "ruling": {
                "ruling": value,
                "amount_sgd": amount,
                "driver_compensation_sgd": None,
                "referrals": [],
                "confidence": confidence,
                "explanation": explanation,
            },
            "discarded_claims": [],
        }
    )


DISSENT = panel_ruling("NO_ACTION", amount=None)


class DelayedTransport:
    """Answers each draft after a fixed delay, and records the answer order.

    ``delays`` maps a draft's position in the panel -- 1 to ``votes``, the
    position-swapped draft being the last -- to the seconds its answer takes.
    ``answers`` overrides the answer for a position, so one draft can be made to
    disagree or to be unusable.

    ``answered`` is the position of each draft's **first** answer, in the order
    the answers came back -- usable or not, because a draft whose first answer
    was unusable made a second call and the point of the record is when the
    panel first heard from it. It is what lets a test say that three drafts had
    answered before the panel published rather than only that it did not publish
    at three.
    """

    def __init__(
        self,
        delays: Mapping[int, float],
        *,
        answers: Optional[Mapping[int, str]] = None,
    ) -> None:
        self.delays = dict(delays)
        self.answers = dict(answers or {})
        self.answered: List[int] = []
        self.requests: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._prompts = self._read_prompts()

    @staticmethod
    def _read_prompts() -> Tuple[str, str, str]:
        rider, driver, _region = pipeline.render_advocate_prompts()
        judge = (pipeline.PROMPTS_DIR / pipeline.JUDGE_PROMPT_FILE).read_text(
            encoding="utf-8"
        )
        return rider, driver, judge

    @staticmethod
    def position_of(request: Mapping[str, Any]) -> int:
        """Which draft of the panel a request is, read off the request itself.

        A sampled draft carries its own seed, and the position-swapped draft
        carries the client's defaults, so the two are told apart by the seed and
        by nothing else -- which is exactly how the runner's own call order
        reads them.
        """
        seed = request.get("seed")
        if seed in pipeline.JUDGE_VOTE_SEEDS[: VOTES - 1]:
            return pipeline.JUDGE_VOTE_SEEDS.index(seed) + 1
        return VOTES

    def __call__(self, url, headers, body, timeout):
        request = json.loads(body.decode("utf-8"))
        rider, driver, judge = self._prompts
        system = request["messages"][0]["content"]
        if system == rider:
            return envelope(RIDER_CLAIMS)
        if system == driver:
            return envelope(DRIVER_CLAIMS)
        if system != judge:
            raise AssertionError("a request carried a system prompt no agent sends")

        position = self.position_of(request)
        with self._lock:
            self.requests.append(request)
        time.sleep(self.delays.get(position, 0.0))
        with self._lock:
            if position not in self.answered:
                self.answered.append(position)
        return envelope(self.answers.get(position, panel_ruling()))

    def first_three(self) -> List[int]:
        """The positions of the first three drafts to answer, sorted.

        Sorted because the two answers that come back within a few milliseconds
        of each other can arrive in either order; which three they are is the
        fact the tests rest on, and the order within them is the scheduler's.
        """
        return sorted(self.answered[:3])


def client_for(transport) -> llm.LLMClient:
    return llm.LLMClient(
        model="hy4-preview",
        api_key=FAKE_KEY,
        transport=transport,
        sleep=lambda seconds: None,
        clock=lambda: 0.0,
    )


def run_the_case(transport, **overrides) -> pipeline.PipelineResult:
    arguments: Dict[str, Any] = dict(
        now=lambda: PINNED_NOW,
        judge_votes=VOTES,
        parallel_calls=True,
    )
    arguments.update(overrides)
    return pipeline.run_case(CASE, client_for(transport), **arguments)


def vote_of(result: pipeline.PipelineResult) -> Mapping[str, Any]:
    return json.loads(result.transcript_json).get("vote") or {}


def draft_records(result: pipeline.PipelineResult) -> List[Mapping[str, Any]]:
    return list(vote_of(result).get("drafts") or [])


def four_fields(ruling: Any) -> Optional[Tuple[Any, ...]]:
    """The four graded fields of a published ruling, and nothing else.

    The explanation is deliberately not among them: the vote sentence states the
    panel's agreement, and a panel that stopped at three states a different
    sentence from one that waited -- which is the whole of what changes.
    """
    if not isinstance(ruling, Mapping):
        return None
    inner = ruling.get("ruling")
    if not isinstance(inner, Mapping):
        return None
    return (
        inner.get("ruling"),
        inner.get("amount_sgd"),
        inner.get("driver_compensation_sgd"),
        tuple(inner.get("referrals") or []),
    )


class EarlyMajorityRuleTests(unittest.TestCase):
    """The rule, over transports whose answer order is the script's."""

    def test_three_agreeing_drafts_stop_the_panel_early(self):
        """Three drafts agree and the swapped draft is among them: stop there.

        The fourth draft is slow -- 0.60 s against the others' 0.05 to 0.25 --
        so a panel that waited for it would take three times as long and would
        write its answer down. It is not written, and the vote block says why.
        """
        transport = DelayedTransport({1: 0.20, 2: 0.25, 3: 0.60, 4: 0.05})

        result = run_the_case(transport, early_majority=True)

        self.assertTrue(result.ok, result.failure_reason)
        vote = vote_of(result)
        self.assertIs(True, vote["early_majority"])
        self.assertEqual(VOTES, vote["votes"])
        self.assertEqual(3, vote["valid"])
        self.assertEqual("carried_not_unanimous", vote["outcome"])
        self.assertFalse(vote["unanimous"])

        by_index = {record["draft"]: record for record in draft_records(result)}
        # The swapped draft is one of the three that agreed, and it was waited
        # for: the fairness measurement reads it.
        self.assertEqual(POSITION_SWAPPED, by_index[4]["kind"])
        self.assertTrue(by_index[4]["valid"])
        # The fourth-positioned *sampled* draft -- the slow one -- is the one the
        # panel did not wait for. It was not written, and it does not count.
        self.assertIs(True, by_index[3]["not_awaited"])
        self.assertFalse(by_index[3]["valid"])
        self.assertEqual([], by_index[3]["entries"])
        self.assertIsNone(by_index[3]["agrees"])
        for index in (1, 2, 4):
            self.assertNotIn("not_awaited", by_index[index])
            self.assertTrue(by_index[index]["entries"], "a waited-for draft was not written")

        # Two advocates and three drafts, and not four.
        self.assertEqual(5, len(result.transcript))

        # Three answers were back before the panel published, and the slow one
        # was not among them.
        self.assertEqual([1, 2, 4], transport.first_three())
        self.assertNotIn(3, transport.answered[:3])

    def test_the_ruling_is_the_one_the_whole_panel_would_have_published(self):
        """The saving is a saving and not a different answer."""
        early = run_the_case(
            DelayedTransport({1: 0.20, 2: 0.25, 3: 0.60, 4: 0.05}), early_majority=True
        )
        whole = run_the_case(DelayedTransport({}), early_majority=False)

        self.assertIs(True, vote_of(early)["early_majority"])
        self.assertNotIn("early_majority", vote_of(whole))
        self.assertEqual(four_fields(whole.ruling), four_fields(early.ruling))
        self.assertEqual(Decimal("4.0"), early.ruling["ruling"]["amount_sgd"])
        # The sentence is not the same: the whole panel was unanimous and the
        # early panel reports three of four.
        self.assertIn("carried unanimously", whole.ruling["ruling"]["explanation"])
        self.assertIn("carried, not unanimous", early.ruling["ruling"]["explanation"])

    def test_the_swapped_draft_is_always_waited_for(self):
        """The swapped draft slowest: the panel waits for it, as it must.

        It is the one draft the rule may never skip -- the fairness measurement
        reads it -- so a panel whose three fastest drafts are all sampled waits.
        """
        transport = DelayedTransport({1: 0.05, 2: 0.06, 3: 0.07, 4: 0.30})

        result = run_the_case(transport, early_majority=True)

        self.assertTrue(result.ok, result.failure_reason)
        vote = vote_of(result)
        self.assertNotIn("early_majority", vote)
        self.assertEqual(VOTES, vote["valid"])
        self.assertEqual("carried", vote["outcome"])
        self.assertTrue(vote["unanimous"])
        for record in draft_records(result):
            self.assertNotIn("not_awaited", record)
            self.assertTrue(record["entries"], "a draft was not written")
        self.assertEqual(6, len(result.transcript))

    def test_a_dissent_among_the_first_three_waits_for_all_four(self):
        """Three drafts back, one of them dissenting: the panel waits.

        The swapped draft and two sampled drafts are the first three to answer,
        and only two of them agree, so the majority is not there. The fourth
        draft is slow and is still waited for.
        """
        transport = DelayedTransport(
            {1: 0.05, 2: 0.06, 3: 0.60, 4: 0.07}, answers={2: DISSENT}
        )

        result = run_the_case(transport, early_majority=True)

        self.assertTrue(result.ok, result.failure_reason)
        vote = vote_of(result)
        self.assertNotIn("early_majority", vote)
        self.assertEqual(VOTES, vote["valid"])
        self.assertEqual("carried_not_unanimous", vote["outcome"])
        by_index = {record["draft"]: record for record in draft_records(result)}
        self.assertFalse(by_index[2]["agrees"])
        self.assertTrue(by_index[2]["entries"], "the dissenting draft was not written")
        self.assertTrue(by_index[3]["entries"], "the slow draft was not waited for")
        for record in draft_records(result):
            self.assertNotIn("not_awaited", record)
        self.assertEqual(6, len(result.transcript))
        self.assertEqual([1, 2, 4], transport.first_three())
        self.assertNotIn(3, transport.answered[:3])

    def test_an_invalid_draft_among_the_first_three_does_not_count(self):
        """Three drafts back is not three drafts agreeing.

        The unusable draft answers first -- it retries, so its call is over
        almost at once -- and the swapped draft and one sampled draft follow it,
        so the panel has three back while the fourth is still out. It must wait
        anyway, because only two of those three can vote.
        """
        transport = DelayedTransport(
            {1: 0.20, 2: 0.01, 3: 0.60, 4: 0.03}, answers={2: UNUSABLE}
        )

        result = run_the_case(transport, early_majority=True)

        self.assertTrue(result.ok, result.failure_reason)
        vote = vote_of(result)
        self.assertNotIn("early_majority", vote)
        self.assertEqual(3, vote["valid"])
        by_index = {record["draft"]: record for record in draft_records(result)}
        self.assertFalse(by_index[2]["valid"])
        self.assertIsNotNone(by_index[2]["abstention"])
        # It retried, so it occupies two entries.
        self.assertEqual(2, len(by_index[2]["entries"]))
        # The fourth draft was waited for: it was written.
        self.assertTrue(by_index[3]["entries"], "the slow draft was not waited for")
        for record in draft_records(result):
            self.assertNotIn("not_awaited", record)
        # Three drafts had answered when the panel would have published -- the
        # unusable one, the swapped one and one sampled one -- and the panel
        # waited anyway.
        self.assertEqual([1, 2, 4], transport.first_three())
        self.assertNotIn(3, transport.answered[:3])
        self.assertEqual(7, len(result.transcript))

    def test_the_switch_off_writes_the_block_it_always_wrote(self):
        """Off is off: the vote block is the one a run without the switch wrote.

        Two runs of one case, differing only in whether the switch was named at
        all, produce the same vote block -- no ``early_majority`` key, no
        ``not_awaited`` on any draft, every draft written.
        """
        named = run_the_case(DelayedTransport({}), early_majority=False)
        unnamed = run_the_case(DelayedTransport({}))

        self.assertNotIn("early_majority", vote_of(named))
        self.assertEqual(vote_of(unnamed), vote_of(named))
        for record in draft_records(named):
            self.assertNotIn("not_awaited", record)
            self.assertTrue(record["entries"])
        self.assertEqual("carried", vote_of(named)["outcome"])
        self.assertTrue(vote_of(named)["unanimous"])

    def test_the_switch_off_ignores_a_script_that_would_have_stopped_it(self):
        """The same slow fourth draft, with the switch off, is waited for."""
        transport = DelayedTransport({1: 0.20, 2: 0.25, 3: 0.60, 4: 0.05})

        result = run_the_case(transport, early_majority=False)

        vote = vote_of(result)
        self.assertNotIn("early_majority", vote)
        self.assertEqual(VOTES, vote["valid"])
        self.assertEqual(6, len(result.transcript))
        for record in draft_records(result):
            self.assertNotIn("not_awaited", record)


class EarlyMajorityRefusalTests(unittest.TestCase):
    """Where the switch is refused, and what the refusal says."""

    def test_the_pipeline_refuses_it_without_parallel_calls(self):
        with self.assertRaises(pipeline.PipelineError) as caught:
            pipeline.run_case(
                CASE,
                client_for(DelayedTransport({})),
                now=lambda: PINNED_NOW,
                judge_votes=VOTES,
                parallel_calls=False,
                early_majority=True,
            )

        self.assertIn("needs parallel_calls", str(caught.exception))

    def test_the_runner_refuses_it_without_parallel_calls(self):
        with self.assertRaises(run_benchmark.BenchmarkError) as caught:
            run_benchmark.run_benchmark(
                "some-model",
                [CASE],
                parallel_calls=False,
                early_majority=True,
                client_factory=lambda sink: client_for(DelayedTransport({})),
            )

        self.assertIn("needs --parallel-calls", str(caught.exception))

    def test_the_command_line_refuses_it_without_parallel_calls(self):
        with self.assertRaises(SystemExit) as caught:
            with redirect_stderr(io.StringIO()):
                run_benchmark.main(["--early-majority"])

        self.assertEqual(2, caught.exception.code)

    def test_the_command_line_refuses_it_with_the_verifier(self):
        with self.assertRaises(SystemExit) as caught:
            with redirect_stderr(io.StringIO()):
                run_benchmark.main(
                    ["--early-majority", "--parallel-calls", "--verify-drafts"]
                )

        self.assertEqual(2, caught.exception.code)

    def test_the_pipeline_refuses_it_with_the_verifier(self):
        with self.assertRaises(pipeline.PipelineError) as caught:
            pipeline.run_case(
                CASE,
                client_for(DelayedTransport({})),
                now=lambda: PINNED_NOW,
                judge_votes=VOTES,
                verify_drafts=True,
                parallel_calls=True,
                early_majority=True,
            )

        self.assertIn("draft verifier", str(caught.exception))

    def test_the_runner_refuses_it_with_the_verifier(self):
        with self.assertRaises(run_benchmark.BenchmarkError) as caught:
            run_benchmark.run_benchmark(
                "some-model",
                [CASE],
                parallel_calls=True,
                early_majority=True,
                verify_drafts=True,
                client_factory=lambda sink: client_for(DelayedTransport({})),
            )

        self.assertIn("--verify-drafts", str(caught.exception))

    def test_the_sealed_set_refuses_it_by_its_own_name(self):
        """A sealed set's single run is one measurement and is not re-taken."""
        for name in ("wild", "wild-v2", "sealed-v1"):
            with self.subTest(set=name):
                development_set = development_sets.named(name)
                with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                    development_sets.run_set(
                        development_set,
                        "some-model",
                        parallel_calls=True,
                        early_majority=True,
                    )

                self.assertIn(name, str(caught.exception))
                self.assertIn("--early-majority", str(caught.exception))

    def test_the_sealed_set_refuses_it_at_the_command_line(self):
        for name in ("wild-v2", "sealed-v1"):
            with self.subTest(set=name):
                out, err = _Writer(), _Writer()
                with redirect_stdout(out), redirect_stderr(err):
                    status = development_sets.main(
                        [
                            "--set",
                            name,
                            "--parallel-calls",
                            "--early-majority",
                            "--check",
                        ]
                    )

                self.assertEqual(1, status)
                self.assertIn("--early-majority", str(err))
                self.assertIn(name, str(err))
                self.assertEqual("", str(out))

    def test_the_sealed_set_still_runs_its_read_only_plan(self):
        """The control: the same invocation without the switch is not refused.

        Without it the command reaches ``--check``'s own refusals and prints
        them, so the refusal above is the switch's and not the mode's.
        """
        out, err = _Writer(), _Writer()
        with redirect_stdout(out), redirect_stderr(err):
            status = development_sets.main(["--set", "wild-v2", "--check"])

        self.assertEqual(1, status)
        self.assertNotIn("--early-majority", str(err))


if __name__ == "__main__":
    unittest.main()
