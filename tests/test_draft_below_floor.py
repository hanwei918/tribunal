"""``DRAFT_BELOW_FLOOR``: the gate, and the proof that it changes no recorded outcome.

The policy states a platform-wide confidence floor, and says a ruling below it
must be escalated to a human reviewer rather than decided. It is stated twice --
``POL-RD-10(1)`` for a route-deviation dispute and ``POL-NS-09(a)`` for a no-show
-- and each says in its own words that it is identical to the other. The floor is
therefore **read out of the loaded policy text** by :func:`tribunal.pipeline.
confidence_floor` and never typed into the pipeline as a number, which is what
``policy/no_show.json``'s own notes on ``POL-NS-09`` ask for: the sentence that
once let the Judge's configuration govern where the two clauses diverge was
deleted because "it authorised a hardcoded constant to override written policy
silently".

A draft that proposes anything but an ``ESCALATE`` and says it is less sure than
the floor is not an answer the panel can be asked to agree with, so it abstains
with ``DRAFT_BELOW_FLOOR`` -- exactly as a malformed draft does. The gate is a
**new check on a record that already exists**, so the thing worth proving is not
that it fires but that it fires nowhere that would have changed an answer. That
is what this module measures, over every recorded judge draft of the four sets
the offline replay covers: each is rebuilt, re-reduced with the gate on, and held
against the outcome the run recorded.

No model call is made. Every reading is a committed transcript, a committed
result or the loaded policy.
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, run_benchmark, verify_drafts  # noqa: E402
from tests import portability  # noqa: E402
from tribunal import pipeline  # noqa: E402

# The model every recorded run was made on, and the two trees the replay reads
# its prompts from. A run directory is ``runs/<set>/<model>/``.
MODEL = "deepseek/deepseek-flash"
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "v1"
RUNS_DIR = PROJECT_ROOT / "runs"

# The four sets whose main recorded runs this module reads, in the order the
# replay reports them.
SET_NAMES = ("corpus", "codex", "wild", "wild-v2")

# The drafts the four sets' transcripts hold, the ones this module can rebuild,
# and the ones of them below the floor. The difference between the first two is
# the four drafts each of the two held-out cases that produced no ruling -- 517
# and 533 -- which ``check_replay`` refuses because there is no result for them
# to be replayed against. All three numbers are asserted rather than described,
# so a set that stopped loading fails here instead of quietly measuring less.
RECORDED_DRAFTS = 512
REBUILT_DRAFTS = 504
DRAFTS_BELOW_THE_FLOOR = 44


def drafts_the_platform_leaves_out() -> int:
    """The drafts of case 111, or ``0`` when this platform can rebuild them.

    Case 111's brief cannot be rebuilt where the libm rounds its mean distance
    one unit in the last place differently, so ``check_replay`` refuses it and
    its drafts are not among the ones this module can rebuild. The count is read
    from the run's own transcript rather than typed in here, so the three counts
    below are over the set the platform can rebuild and they say which case they
    left out.
    """
    if not portability.the_case_111_platform_difference():
        return 0
    run_dir = development_sets.BY_NAME["corpus"].run_dir(MODEL, RUNS_DIR)
    transcript = run_benchmark.read_json(
        run_benchmark.transcript_path(run_dir, portability.CASE_111)
    )
    vote_block = (transcript or {}).get("vote") or {}
    return len(vote_block.get("drafts") or [])


def _last_answer(record: Mapping[str, Any], entries: Sequence[Mapping[str, Any]]):
    """One recorded draft's last answer: its confidence and its ruling value.

    The confidence is read from the draft's **parsed** answer -- the entry the
    draft's last attempt wrote -- because it is not a field of the draft record
    itself. A draft whose last entry carries no parsed answer (an answer that
    never parsed) answers ``(None, None)``: it has no confidence to read and it
    is not this check's business.
    """
    indices = [
        int(item) for item in (record.get("entries") or []) if isinstance(item, int)
    ]
    if not indices or not 0 <= indices[-1] < len(entries):
        return None, None
    parsed = entries[indices[-1]].get("parsed")
    inner = parsed.get("ruling") if isinstance(parsed, Mapping) else None
    if not isinstance(inner, Mapping):
        return None, None
    return inner.get("confidence"), inner.get("ruling")


class RecordedDraftFloorTests(unittest.TestCase):
    """Every recorded draft, rebuilt and re-reduced with the gate on.

    The work is done once in ``setUpClass``: for each set, the run's transcripts
    are checked against this code by :func:`eval.run_benchmark.check_replay`, the
    drafts of every accepted case are rebuilt by
    :func:`tribunal.pipeline.recorded_judge_drafts` -- which is where the gate
    lives -- and each vote is reduced again by
    :func:`tribunal.pipeline.reduce_vote`.
    """

    @classmethod
    def setUpClass(cls):
        cls.sets: Dict[str, Any] = {}
        for name in SET_NAMES:
            development_set = development_sets.BY_NAME[name]
            run_dir = development_set.run_dir(MODEL, RUNS_DIR)
            check = run_benchmark.check_replay(
                run_dir,
                development_set.cases,
                model=MODEL,
                prompts_dir=PROMPTS_DIR,
                policy_version=development_set.policy_version,
                case_loader=development_set.load_case,
            )
            cases: List[Tuple[int, Dict[str, Any], List[Any], Any, Any]] = []
            for case_no in development_set.cases:
                replayable = check.accepted.get(case_no)
                if replayable is None:
                    continue
                found, _reason = verify_drafts.recorded_drafts_for_case(
                    case_no,
                    replayable,
                    source_dir=run_dir,
                    prompts_dir=PROMPTS_DIR,
                )
                if found is None:
                    continue
                vote_block = found["vote"]
                entries = found["entries"]
                votes = vote_block.get("votes") or len(vote_block.get("drafts") or [])
                drafts = pipeline.recorded_judge_drafts(
                    vote_block,
                    entries,
                    found["referee_result"],
                    found["brief_object"],
                )
                vote = pipeline.reduce_vote(
                    drafts,
                    votes,
                    found["referee_result"],
                    found["brief_object"],
                )
                cases.append(
                    (
                        case_no,
                        {
                            "vote": vote_block,
                            "entries": entries,
                            "brief_object": found["brief_object"],
                            "referee_result": found["referee_result"],
                            "drafts": drafts,
                            "reduced": vote,
                            "result": run_benchmark.load_cached(run_dir, case_no),
                        },
                        drafts,
                        vote,
                        run_benchmark.load_cached(run_dir, case_no),
                    )
                )
            cls.sets[name] = (development_set, run_dir, cases)

    def each_case(self):
        for name in SET_NAMES:
            _set, _run_dir, cases = self.sets[name]
            for case in cases:
                yield (name,) + case

    # -- the counts --------------------------------------------------------
    def test_the_recorded_drafts_are_the_ones_the_task_counted(self):
        """512 in the transcripts, 504 rebuildable, and the difference is named.

        The eight that cannot be rebuilt are the four drafts each of the two
        held-out cases that produced no ruling, 517 and 533. ``check_replay``
        refuses them because there is no result for their advocates to be
        replayed against, which is the same refusal the offline replay records.
        A platform whose libm moves case 111's mean distance adds that case's
        four drafts to the difference; the count below is then over the set the
        platform can rebuild, and the case it left out is named.
        """
        left_out = drafts_the_platform_leaves_out()
        rebuilt = sum(
            len(drafts)
            for _set, _dir, cases in self.sets.values()
            for _case_no, _found, drafts, _vote, _result in cases
        )
        drafts = 0
        refused = []
        for name in SET_NAMES:
            development_set, run_dir, cases = self.sets[name]
            accepted = {case[0] for case in cases}
            for case_no in development_set.cases:
                transcript = run_benchmark.read_json(
                    run_benchmark.transcript_path(run_dir, case_no)
                )
                vote_block = (transcript or {}).get("vote") or {}
                held = len(vote_block.get("drafts") or [])
                drafts += held
                if case_no not in accepted:
                    refused.append((name, case_no, held))
        expected_refused = [("wild", 517, 4), ("wild", 533, 4)]
        if left_out:
            expected_refused.append(("corpus", portability.CASE_111, left_out))
        self.assertEqual(REBUILT_DRAFTS - left_out, rebuilt)
        self.assertEqual(RECORDED_DRAFTS, drafts)
        self.assertEqual(sorted(expected_refused), sorted(refused))

    def test_every_recorded_draft_carries_a_confidence(self):
        """The gate is about a number, so the record has to hold one."""
        seen = 0
        for name, case_no, found, _drafts, _vote, _result in self.each_case():
            for record in found["vote"].get("drafts") or []:
                confidence, _value = _last_answer(record, found["entries"])
                with self.subTest(set=name, case=case_no, draft=record.get("draft")):
                    self.assertIsInstance(
                        confidence, (int, float, Decimal),
                        "a recorded draft carries no confidence",
                    )
                seen += 1
        self.assertEqual(REBUILT_DRAFTS - drafts_the_platform_leaves_out(), seen)

    def test_the_drafts_below_the_floor_are_escalates_or_already_invalid(self):
        """What makes the gate's zero effect a fact rather than a coincidence.

        A draft below the floor is one the gate would reject. Every one of them
        is either a draft that already proposed an ``ESCALATE`` -- which is what
        the floor asks for, so the gate has nothing to add -- or a draft that was
        already invalid and so was never counted. That is why turning the gate on
        cannot move an outcome.
        """
        below = 0
        for name, case_no, found, _drafts, _vote, _result in self.each_case():
            floor, _references = pipeline.confidence_floor(found["brief_object"])
            for record in found["vote"].get("drafts") or []:
                confidence, value = _last_answer(record, found["entries"])
                if not isinstance(confidence, (int, float, Decimal)):
                    continue
                if Decimal(str(confidence)) >= floor:
                    continue
                below += 1
                with self.subTest(set=name, case=case_no, draft=record.get("draft")):
                    self.assertTrue(
                        value == pipeline.ESCALATE or record.get("valid") is False,
                        "a draft below the floor that is neither an ESCALATE nor "
                        "already invalid would have been rejected by the gate",
                    )
        self.assertEqual(DRAFTS_BELOW_THE_FLOOR, below)

    # -- the effect --------------------------------------------------------
    def test_the_gate_changes_no_recorded_outcome(self):
        """The whole point: re-reduce every recorded vote with the gate on.

        The drafts are rebuilt by ``recorded_judge_drafts``, which runs the gate,
        and reduced by ``reduce_vote``, which runs the floor again after the
        vote. Every outcome, every agreement, every valid count and -- where the
        run wrote a result file -- every ruling must be what the run recorded.
        """
        checked = 0
        for name, case_no, found, _drafts, vote, result in self.each_case():
            recorded = found["vote"]
            with self.subTest(set=name, case=case_no, what="record"):
                self.assertEqual(recorded.get("outcome"), vote.record.get("outcome"))
                self.assertEqual(recorded.get("agreement"), vote.record.get("agreement"))
                self.assertEqual(recorded.get("valid"), vote.record.get("valid"))
                self.assertEqual(
                    recorded.get("threshold"), vote.record.get("threshold")
                )
            if result is not None:
                with self.subTest(set=name, case=case_no, what="ruling"):
                    self.assertEqual(result["ruling"], vote.ruling)
            checked += 1
        self.assertEqual(
            (REBUILT_DRAFTS - drafts_the_platform_leaves_out()) // 4, checked
        )

    def test_the_same_drafts_reduce_to_a_ruling_above_the_floor_or_none(self):
        """No published ruling of the four sets is below the floor.

        This is the property the gate protects, stated over the record rather
        than over one synthetic draft: every ruling the four runs published is
        either an ``ESCALATE`` -- which is what the floor asks for -- or carries
        a confidence at or above it.
        """
        for name, case_no, found, _drafts, vote, result in self.each_case():
            if result is None or vote.ruling is None:
                continue
            inner = vote.ruling.get("ruling") or {}
            if inner.get("ruling") == pipeline.ESCALATE:
                continue
            floor, _references = pipeline.confidence_floor(found["brief_object"])
            with self.subTest(set=name, case=case_no):
                self.assertGreaterEqual(Decimal(str(inner.get("confidence"))), floor)

    def test_the_measurement_can_see_the_gate_fire(self):
        """A positive control, so the zero above is a measurement.

        **The tests above cannot fail by removing the gate.** They assert that
        the gate changes nothing, and a gate that is not there changes nothing
        either: the recorded drafts below the floor are already ``ESCALATE``s or
        already invalid, so the real floor rejects none of them and there is no
        draft whose treatment differs. That is the claim, and it is also why the
        claim needs a control.

        So the floor is raised -- patched to ``0.95`` -- and the same rebuild and
        reduction are run again. Drafts below *that* are rejected, the outcomes
        move, and the machinery is shown to be able to report the change it
        reports nothing of at the floor the policy states.
        """
        changed = 0
        rejected = 0
        with mock.patch.object(
            pipeline, "confidence_floor", lambda _brief: (Decimal("0.95"), ("POL-NS-09(a)",))
        ):
            for name, case_no, found, _drafts, vote, result in self.each_case():
                drafts = pipeline.recorded_judge_drafts(
                    found["vote"],
                    found["entries"],
                    found["referee_result"],
                    found["brief_object"],
                )
                rejected += sum(
                    1
                    for draft in drafts
                    if draft.abstention
                    and draft.abstention.startswith(pipeline.DRAFT_BELOW_FLOOR)
                )
                raised = pipeline.reduce_vote(
                    drafts,
                    found["vote"].get("votes") or len(drafts),
                    found["referee_result"],
                    found["brief_object"],
                )
                if raised.record.get("outcome") != found["vote"].get("outcome"):
                    changed += 1

        self.assertGreater(
            rejected, 0, "raising the floor rejected no recorded draft at all"
        )
        self.assertGreater(
            changed, 0, "raising the floor moved no recorded outcome at all"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
