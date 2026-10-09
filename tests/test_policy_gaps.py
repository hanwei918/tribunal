"""Tests for the policy-gap loop.

The loop finds the cases the policy could not decide, groups them, and -- for a
group a person has closed at least twice -- asks a model to draft **one clause**
that would decide them. Nothing it drafts takes effect on its own: a draft is a
proposal until a person approves it, and ``approve`` is the only writer of
``policy/amendments/``.

Five things are asserted here, and each is the point of its own section:

* **the triggers are a written-down grammar.** Every row is exercised one at a
  time, including the three a single-draft file is classified by, and the floor
  is shown to come from the loaded policy rather than from a number in the code.
* **the signature is about the record.** The noise drop is asserted on the
  parsed tuple, not on a rendered line, and the boundary share is shown to be
  exact.
* **the clusters are deterministic and not duplicated.** The same readings in
  two orders name the same clusters, and a fine cluster whose signature is empty
  is not emitted, because it would be its coarse cluster under a second id.
* **the drafter is given no answer and its draft is checked before it is kept.**
  Every refusal is exercised, and the worked example in the prompt is shown to
  name a clause that does not exist.
* **the diff cannot contradict itself.** ``changed`` is computed from the same
  rendering the two columns show, so a row marked changed always has two sides
  that differ, and money that differs only in its trailing zeros is not one.

What is *not* asserted here is that the loop decides well. Nothing in this file
reads a grade to check a ruling, and the one command that reads the frozen
answer key at all -- ``diff`` -- is exercised over rulings a test chose, with
one end-to-end rerun in its own test. Only ``draft`` and ``rerun`` call a model,
and every test that reaches either injects the scripted transport from
``tests.test_run_benchmark`` or a client that answers with one canned document.
No test reaches the network.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import (  # noqa: E402
    development_sets,
    grade,
    policy_gaps as gaps,
    run_benchmark as runner,
)
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import (  # noqa: E402
    brief,
    llm,
    loader,
    money,
    pipeline,
    policy_versions,
    precedents,
    transcript as transcript_module,
)

MODEL = rig.MODEL
PROMPTS_DIR = rig.PROMPTS_DIR

# The cases whose recorded ruling in the frozen key is ESCALATE, so a rig-built
# run over them is a run of policy gaps: 110 and 112 are route deviation, 207,
# 210 and 213 are no-show charge. The two categories matter here because the
# floor, the clusters and the rerun's regression set are all per category.
GAP_CASES = (110, 112, 207, 210, 213)
ROUTE_GAPS = (110, 112)
NO_SHOW_GAPS = (207, 210, 213)

# The category each of those cases belongs to, read from the manifest rather
# than written down, so a case that moves category moves the fixture with it.
CATEGORY_OF = {case_no: loader.load_case(case_no)["dispute"]["category"] for case_no in GAP_CASES}

# A fixed clock reading, so a proposal and an amendment built twice are the same
# bytes and "the same file" can be asserted rather than described.
FIXED_NOW = "2026-09-29T00:00:00+00:00"

# The next free clause number for each prefix, in the committed policy. Read
# through the module that owns the rule rather than written down, so an
# amendment added to the repository moves this too.
NEXT_FREE = {
    "GEN": gaps.next_free_number(PROJECT_ROOT / "policy" / "general.json", "GEN"),
    "NS": gaps.next_free_number(PROJECT_ROOT / "policy" / "no_show.json", "NS"),
    "RD": gaps.next_free_number(PROJECT_ROOT / "policy" / "route_deviation.json", "RD"),
}

# The committed run directories the submission's figures come from.
CORPUS_RUN = PROJECT_ROOT / "runs" / "deepseek-deepseek-flash"
CODEX_RUN = PROJECT_ROOT / "runs" / "codex" / "deepseek-deepseek-flash"


# --------------------------------------------------------------------------
# Small builders
# --------------------------------------------------------------------------
def canonical(document):
    return money.dumps_canonical(document)


def a_reading(case_no, category, trigger, signature=(), *, set_name="corpus", **overrides):
    """One :class:`gaps.CaseReading`, built by hand.

    Built rather than read so the cluster arithmetic can be asked about cases
    that do not exist: a cluster is a function of ``(category, trigger,
    signature)`` and nothing else, and the tests that are about that function
    should not need a run on disk to have one.
    """
    fields = dict(
        run_dir=Path("/nonexistent") / set_name,
        set_name=set_name,
        case_no=case_no,
        category=category,
        policy_version=1,
        ablation=None,
        ruling=pipeline.ESCALATE,
        confidence=Decimal("0.10"),
        system_outcome={
            "ruling": pipeline.ESCALATE,
            "amount_sgd": None,
            "driver_compensation_sgd": None,
            "referrals": [],
        },
        leading_referral_clause=None,
        vote_outcome="carried",
        valid=3,
        threshold=3,
        abstained=(),
        trigger=trigger,
        signature=tuple(signature),
    )
    fields.update(overrides)
    return gaps.CaseReading(**fields)


def a_trigger(**overrides):
    """``trigger_of`` with every argument named, so a test states only its own."""
    arguments = dict(
        has_vote=True,
        vote_outcome=None,
        ruling=None,
        confidence=None,
        floor=Decimal("0.70"),
        leading_clause=None,
        valid=None,
        threshold=None,
        abstained=(),
    )
    arguments.update(overrides)
    return gaps.trigger_of(**arguments)


def a_brief(*, category_floor=None, general_floor=None):
    """A brief-shaped mapping carrying whatever floors the test wants."""
    category = {} if category_floor is None else {"confidence_floor": category_floor}
    general = {} if general_floor is None else {"confidence_floor": general_floor}
    return {"case": {"evidence": []}, "policies": {"general": general, "category": category}}


def a_case_document(case_no, evidence):
    """A brief-shaped case whose artifacts carry the given statuses and issues."""
    return {
        "case": {
            "case_no": case_no,
            "dispute": {"category": "NO_SHOW_CHARGE"},
            "evidence": evidence,
        },
        "policies": {"general": {}, "category": {}},
    }


def artifact(evidence_id, evidence_type, status, issues):
    return {
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "admissibility": {"status": status, "issues": list(issues)},
    }


def a_closure(store, precedent_id, case_no, *, set_name="corpus", category="NO_SHOW_CHARGE",
              ruling="PARTIAL_REFUND", clause_ids=("POL-NS-02",), closed_by="reviewer"):
    """Append one human closure to a store, and return it as written."""
    entry = {
        "precedent_id": precedent_id,
        "source": {
            "set": set_name,
            "case_no": case_no,
            "dispute_id": "DISP-{0}".format(case_no),
            "run_dir": "runs/{0}".format(MODEL),
            "case_sha256": "0" * 64,
        },
        "category": category,
        "system_outcome": {
            "ruling": pipeline.ESCALATE,
            "amount_sgd": None,
            "driver_compensation_sgd": None,
            "referrals": [],
        },
        "decision": {
            "ruling": ruling,
            "amount_sgd": None,
            "driver_compensation_sgd": None,
            "referrals": [],
        },
        "clause_ids": list(clause_ids),
        "amount_contested_sgd": None,
        "summary": "a person closed this case",
        "closed_by": closed_by,
        "policy_version": 1,
        "supersedes": None,
    }
    precedents.append_entry(entry, store=store, invocation_id="test-closure")
    return entry


def a_store(tmp, name="precedents"):
    store = Path(tmp) / name
    store.mkdir(parents=True, exist_ok=True)
    return store


def a_draft(**overrides):
    """A draft answer the validator accepts, with named parts replaceable."""
    clause = {
        "id": "POL-NS-{0:02d}".format(NEXT_FREE["NS"]),
        "title": "No-show charge where the trace is missing",
        "category": "NO_SHOW_CHARGE",
        "rule": (
            "Where POL-NS-02 applies and the GPS_TRACE artifact is missing, the "
            "no-show charge is not sustained and the fare is refunded in full."
        ),
        "requires": ["GPS_TRACE"],
        "licenses": ["FULL_REFUND"],
        "favours": "RIDER",
        "notes": "Added because the cluster turned on a missing trace. It reads POL-NS-02.",
    }
    document = {
        "clause": clause,
        "reproduces": ["P-0001"],
        "does_not_reproduce": [],
        "interacts_with": ["POL-NS-02"],
    }
    for key, value in overrides.items():
        if key == "clause" and isinstance(value, dict):
            clause.update(value)
        else:
            document[key] = value
    return document


class DrafterClient:
    """A client that answers with one canned document and records its calls."""

    def __init__(self, answer, *, model="test/drafter"):
        self.answer = answer
        self.model = model
        self.calls = []

    def complete(self, system_prompt, user_message, response_format=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_message": user_message,
                "response_format": response_format,
            }
        )
        return llm.LLMResult(
            text=canonical(self.answer),
            json_body=self.answer,
            envelope=None,
            parse_outcome=llm.PARSE_PARSED,
            parse_error=None,
            prompt_tokens=10,
            completion_tokens=5,
            reasoning_tokens=0,
            cached_tokens=0,
            status=200,
            duration_seconds=0.0,
            model=self.model,
            attempts=1,
            request_sha256="0" * 64,
        )


def factory_for(client):
    return lambda sink: client


def a_client_that_must_not_be_built():
    """A client factory that fails the test if anything builds a client."""

    def build(sink):
        raise AssertionError(
            "a client was built for an answer that should have been refused "
            "before any call"
        )

    return build


def build_run(tmp, *, cases=GAP_CASES, judge_votes=4, name="runs", transport=None):
    """One run over the given cases, with a vote block in every transcript.

    ``judge_votes`` is at least two so the transcript carries a vote block,
    which is what the loop reads to tell ``no_majority`` from
    ``too_few_valid_drafts``. A single-draft file has its own test, built from a
    transcript with no vote block at all.
    """
    summary, used = rig.bench(tmp, cases=cases, judge_votes=judge_votes, transport=transport)
    return runner.run_directory(Path(tmp) / name, MODEL), used


# Two of the held-out set's own cases, for the tests that need a run whose path
# says ``wild``. They are the held-out set's and not the corpus's, so a run of
# them read as the corpus cannot find them: the manifest does not list them.
WILD_CASES = (501, 506)


def wild_shaped_run(tmp, *, cases=WILD_CASES, judge_votes=4):
    """One run of the held-out set's cases, under ``runs/wild/<model-slug>/``.

    Drafted through the scripted transport over the held-out set's own key and
    its own loader, so what a test asks about is the run directory's *shape* and
    not the answers a model gave. Nothing here reads the committed held-out run.
    """
    held_out = development_sets.named("wild")
    runs_dir = Path(tmp) / "runs" / held_out.runs_subdir
    rig.bench(
        tmp,
        cases=cases,
        judge_votes=judge_votes,
        runs_dir=runs_dir,
        key=held_out.key(),
        case_loader=held_out.load_case,
        label=held_out.name,
        key_path=held_out.key_path,
    )
    return runner.run_directory(runs_dir, MODEL)


def write_report_file(path, report, store=None):
    """Write the report the way ``report`` writes it, and return the path."""
    path = Path(path)
    path.write_text(
        canonical(gaps.report_document(report, gaps.closure_index(store))) + "\n",
        encoding="utf-8",
    )
    return path


def tree_digest(root):
    """Every file under ``root``, as ``{relative path: sha256}``.

    Used to prove a tree did not move, which is a claim about bytes rather than
    about a listing: a file rewritten with the same name is a different file.
    """
    root = Path(root)
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def known_trigger(trigger):
    """Whether a trigger is one of the grammar's, a single-draft row included."""
    if not isinstance(trigger, str):
        return False
    if trigger.startswith(gaps.TRIGGER_SINGLE_PREFIX):
        trigger = trigger[len(gaps.TRIGGER_SINGLE_PREFIX):]
    if trigger in (
        gaps.TRIGGER_NO_MAJORITY,
        gaps.TRIGGER_TOO_FEW,
        gaps.TRIGGER_TOO_FEW_VERIFIER,
        gaps.TRIGGER_BELOW_FLOOR,
        gaps.TRIGGER_JUDGE_NO_CLAUSE,
    ):
        return True
    return (
        trigger.startswith(gaps.TRIGGER_CLAUSE_PREFIX)
        and precedents.base_clause_id(trigger[len(gaps.TRIGGER_CLAUSE_PREFIX):]) is not None
    )


# --------------------------------------------------------------------------
# The triggers
# --------------------------------------------------------------------------
class TriggerTests(unittest.TestCase):
    """The grammar, one row at a time. No run and no model is involved."""

    def test_a_carried_escalation_under_the_floor_is_below_the_floor(self):
        self.assertEqual(
            gaps.TRIGGER_BELOW_FLOOR,
            a_trigger(
                vote_outcome=pipeline.VOTE_CARRIED,
                ruling=pipeline.ESCALATE,
                confidence=Decimal("0.39"),
            ),
        )

    def test_a_carried_escalation_exactly_at_the_floor_is_not_below_it(self):
        # At the floor is at the floor: the row exists to find the cases the
        # policy left the judge with no number to stand on, and a number that
        # reaches the floor is one to stand on.
        self.assertNotEqual(
            gaps.TRIGGER_BELOW_FLOOR,
            a_trigger(
                vote_outcome=pipeline.VOTE_CARRIED,
                ruling=pipeline.ESCALATE,
                confidence=Decimal("0.70"),
            ),
        )

    def test_a_carried_escalation_at_the_floor_with_a_referral_names_the_clause(self):
        self.assertEqual(
            gaps.TRIGGER_CLAUSE_PREFIX + "POL-NS-07",
            a_trigger(
                vote_outcome=pipeline.VOTE_CARRIED,
                ruling=pipeline.ESCALATE,
                confidence=Decimal("0.90"),
                leading_clause="POL-NS-07",
            ),
        )

    def test_a_carried_escalation_at_the_floor_with_no_referral_is_judge_no_clause(self):
        self.assertEqual(
            gaps.TRIGGER_JUDGE_NO_CLAUSE,
            a_trigger(
                vote_outcome=pipeline.VOTE_CARRIED,
                ruling=pipeline.ESCALATE,
                confidence=Decimal("0.90"),
            ),
        )

    def test_a_confidence_that_was_not_recorded_counts_as_below_the_floor(self):
        # "not recorded" is not "at or above". A result that carries no number
        # is one the policy gave the judge nothing to stand on for.
        self.assertEqual(
            gaps.TRIGGER_BELOW_FLOOR,
            a_trigger(
                vote_outcome=pipeline.VOTE_CARRIED,
                ruling=pipeline.ESCALATE,
                confidence=None,
                leading_clause="POL-NS-07",
            ),
        )

    def test_a_carried_case_that_did_not_escalate_is_no_gap(self):
        for ruling in ("FULL_REFUND", "PARTIAL_REFUND", "NO_ACTION", "DRIVER_COMPENSATION"):
            with self.subTest(ruling=ruling):
                self.assertIsNone(
                    a_trigger(
                        vote_outcome=pipeline.VOTE_CARRIED,
                        ruling=ruling,
                        confidence=Decimal("0.10"),
                    )
                )

    def test_an_escalated_vote_with_a_quorum_of_valid_drafts_is_no_majority(self):
        self.assertEqual(
            gaps.TRIGGER_NO_MAJORITY,
            a_trigger(
                vote_outcome=pipeline.VOTE_ESCALATED,
                valid=3,
                threshold=3,
                ruling=pipeline.ESCALATE,
            ),
        )

    def test_an_escalated_vote_below_the_quorum_is_too_few_valid_drafts(self):
        self.assertEqual(
            gaps.TRIGGER_TOO_FEW,
            a_trigger(
                vote_outcome=pipeline.VOTE_ESCALATED,
                valid=2,
                threshold=3,
                ruling=pipeline.ESCALATE,
            ),
        )

    def test_an_escalated_vote_with_a_verifier_abstention_names_the_verifier(self):
        self.assertEqual(
            gaps.TRIGGER_TOO_FEW_VERIFIER,
            a_trigger(
                vote_outcome=pipeline.VOTE_ESCALATED,
                valid=1,
                threshold=3,
                abstained=(2,),
                ruling=pipeline.ESCALATE,
            ),
        )

    def test_an_escalated_vote_with_no_recorded_quorum_is_too_few_valid_drafts(self):
        # A vote block that records no threshold cannot establish that a quorum
        # was reached, and "cannot establish" is not "reached".
        self.assertEqual(
            gaps.TRIGGER_TOO_FEW,
            a_trigger(vote_outcome=pipeline.VOTE_ESCALATED, ruling=pipeline.ESCALATE),
        )

    def test_a_single_draft_file_is_classified_by_the_three_carried_rows(self):
        rows = {
            a_trigger(has_vote=False, ruling=pipeline.ESCALATE, confidence=Decimal("0.10")):
                "below",
            a_trigger(
                has_vote=False,
                ruling=pipeline.ESCALATE,
                confidence=Decimal("0.90"),
                leading_clause="POL-NS-07",
            ): "clause",
            a_trigger(
                has_vote=False, ruling=pipeline.ESCALATE, confidence=Decimal("0.90")
            ): "no_clause",
        }
        self.assertEqual(
            {
                gaps.TRIGGER_SINGLE_PREFIX + gaps.TRIGGER_BELOW_FLOOR: "below",
                gaps.TRIGGER_SINGLE_PREFIX
                + gaps.TRIGGER_CLAUSE_PREFIX
                + "POL-NS-07": "clause",
                gaps.TRIGGER_SINGLE_PREFIX + gaps.TRIGGER_JUDGE_NO_CLAUSE: "no_clause",
            },
            rows,
        )

    def test_a_single_draft_file_that_did_not_escalate_is_no_gap(self):
        self.assertIsNone(
            a_trigger(has_vote=False, ruling="FULL_REFUND", confidence=Decimal("0.10"))
        )

    def test_a_single_draft_file_ignores_a_recorded_vote_outcome(self):
        # The file has no vote block, so there is no vote to consult; an
        # outcome handed in beside ``has_vote=False`` must not reach the row.
        self.assertEqual(
            gaps.TRIGGER_SINGLE_PREFIX + gaps.TRIGGER_BELOW_FLOOR,
            a_trigger(
                has_vote=False,
                vote_outcome=pipeline.VOTE_ESCALATED,
                valid=4,
                threshold=3,
                ruling=pipeline.ESCALATE,
                confidence=Decimal("0.10"),
            ),
        )


class FloorTests(unittest.TestCase):
    """The floor is read from the loaded policy, and the category one first."""

    def test_the_category_floor_is_read_before_the_general_one(self):
        # The two policy files carry different floors, and the case was briefed
        # under the category's. A case whose confidence falls between them is
        # decided by the category's, which is the whole point of reading it.
        self.assertEqual(
            Decimal("0.60"),
            gaps.confidence_floor(
                a_brief(category_floor="0.60", general_floor="0.90")
            ),
        )

    def test_the_general_floor_is_the_fallback(self):
        self.assertEqual(
            Decimal("0.90"), gaps.confidence_floor(a_brief(general_floor="0.90"))
        )

    def test_a_brief_that_carries_no_floor_has_no_floor(self):
        self.assertIsNone(gaps.confidence_floor(a_brief()))

    def test_a_floor_that_is_a_boolean_is_not_a_number(self):
        # ``isinstance(True, int)`` is true, so a floor recorded as ``true``
        # must be refused before ``Decimal`` sees it, and the general policy's
        # own floor is then the answer.
        self.assertEqual(
            Decimal("0.90"),
            gaps.confidence_floor(
                a_brief(category_floor=True, general_floor="0.90")
            ),
        )

    def test_the_committed_policy_files_carry_a_floor(self):
        # Not a number written down: the claim is that every committed policy
        # file states one, so the fallback chain is never reached in a real run.
        for name in ("general.json", "no_show.json", "route_deviation.json"):
            with self.subTest(policy=name):
                document = runner.read_json(PROJECT_ROOT / "policy" / name)
                self.assertIsNotNone(
                    gaps.as_decimal(document.get("confidence_floor")),
                    "{0} states no confidence_floor".format(name),
                )


# --------------------------------------------------------------------------
# The signature and the noise drop
# --------------------------------------------------------------------------
class SignatureTests(unittest.TestCase):
    """The signature is about what is wrong with the record, on parsed tuples."""

    def test_the_signature_is_the_impaired_pairs_sorted(self):
        brief_object = a_case_document(
            1,
            [
                artifact("EV-GPS", "GPS_TRACE", gaps.MISSING, ["GPS_GAP", "LOW_COVERAGE"]),
                artifact("EV-CHAT", "CHAT_LOG", gaps.IMPAIRED, ["TRUNCATED_LOG"]),
            ],
        )
        self.assertEqual(
            ("CHAT_LOG:TRUNCATED_LOG", "GPS_TRACE:GPS_GAP", "GPS_TRACE:LOW_COVERAGE"),
            gaps.signature_pairs(brief_object),
        )

    def test_a_complete_artifact_contributes_nothing(self):
        brief_object = a_case_document(
            1, [artifact("EV-GPS", "GPS_TRACE", "COMPLETE", ["GPS_GAP"])]
        )
        self.assertEqual((), gaps.signature_pairs(brief_object))

    def test_a_missing_artifact_with_no_issues_contributes_nothing(self):
        brief_object = a_case_document(
            1, [artifact("EV-GPS", "GPS_TRACE", gaps.MISSING, [])]
        )
        self.assertEqual((), gaps.signature_pairs(brief_object))

    def test_a_pair_on_four_of_five_cases_is_dropped(self):
        signatures = {
            1: ("GPS_TRACE:GPS_GAP", "CHAT_LOG:TRUNCATED_LOG"),
            2: ("GPS_TRACE:GPS_GAP",),
            3: ("GPS_TRACE:GPS_GAP",),
            4: ("GPS_TRACE:GPS_GAP",),
            5: (),
        }
        self.assertEqual(("GPS_TRACE:GPS_GAP",), gaps.dropped_noise_pairs(signatures))

    def test_a_pair_on_three_of_five_cases_is_kept(self):
        signatures = {
            1: ("GPS_TRACE:GPS_GAP",),
            2: ("GPS_TRACE:GPS_GAP",),
            3: ("GPS_TRACE:GPS_GAP",),
            4: (),
            5: (),
        }
        self.assertEqual((), gaps.dropped_noise_pairs(signatures))

    def test_the_share_is_a_decimal_so_the_boundary_is_exact(self):
        # Four of five is exactly 0.8, and the comparison is ``>=``. A float
        # would make this depend on how 0.8 rounds.
        signatures = {case_no: ("X:Y",) for case_no in range(1, 5)}
        signatures[5] = ()
        self.assertEqual(Decimal("0.8"), gaps.NOISE_SHARE)
        self.assertEqual(("X:Y",), gaps.dropped_noise_pairs(signatures))
        self.assertEqual(("X:Y",), gaps.dropped_noise_pairs(signatures, share=Decimal("0.80")))

    def test_no_cases_at_all_drops_nothing(self):
        self.assertEqual((), gaps.dropped_noise_pairs({}))

    def test_a_dropped_pair_is_taken_out_of_every_signature(self):
        # The whole point: a pair on almost every case distinguishes none of
        # them, so it must not be left in the signatures the clusters are built
        # from. Asserted on the tuple a reading ends up carrying.
        readings = [
            a_reading(1, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR),
            a_reading(2, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR),
        ]
        signatures = {
            1: ("NOISE:PAIR", "REAL:PAIR"),
            2: ("NOISE:PAIR",),
        }
        dropped = gaps.dropped_noise_pairs(signatures)
        self.assertEqual(("NOISE:PAIR",), dropped)
        kept = [
            tuple(pair for pair in signatures[reading.case_no] if pair not in dropped)
            for reading in readings
        ]
        self.assertEqual([("REAL:PAIR",), ()], kept)


# --------------------------------------------------------------------------
# The clusters
# --------------------------------------------------------------------------
class ClusterTests(unittest.TestCase):
    """Two levels, deterministic ids, and no fine cluster that says nothing."""

    def test_the_two_levels_are_emitted_with_ids_in_sorted_order(self):
        readings = [
            a_reading(1, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR, ("GPS_TRACE:GPS_GAP",)),
            a_reading(2, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR, ("GPS_TRACE:GPS_GAP",)),
            a_reading(3, "ROUTE_DEVIATION", gaps.TRIGGER_BELOW_FLOOR, ()),
        ]
        clusters = gaps.build_clusters(readings, min_cases=2)
        self.assertEqual(
            [
                ("C1", 1, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR, (), (1, 2)),
                ("C2", 1, "ROUTE_DEVIATION", gaps.TRIGGER_BELOW_FLOOR, (), (3,)),
                ("C3", 2, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR, ("GPS_TRACE:GPS_GAP",), (1, 2)),
            ],
            [
                (cluster.cluster_id, cluster.level, cluster.category, cluster.trigger,
                 cluster.signature, cluster.cases)
                for cluster in clusters
            ],
        )

    def test_a_fine_cluster_with_an_empty_signature_is_not_emitted(self):
        # Its cases are exactly its coarse cluster's, and an empty signature
        # adds nothing to say about them. Emitting it would name one set of
        # cases twice under two ids.
        readings = [
            a_reading(1, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR, ()),
            a_reading(2, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR, ()),
        ]
        clusters = gaps.build_clusters(readings, min_cases=2)
        self.assertEqual(1, len(clusters))
        self.assertEqual(
            [(1, gaps.TRIGGER_BELOW_FLOOR, ())],
            [(cluster.level, cluster.trigger, cluster.signature) for cluster in clusters],
        )

    def test_a_fine_cluster_is_emitted_when_the_signature_says_something(self):
        readings = [
            a_reading(1, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR, ("GPS_TRACE:GPS_GAP",)),
            a_reading(2, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR, ("CHAT_LOG:TRUNCATED_LOG",)),
        ]
        clusters = gaps.build_clusters(readings, min_cases=2)
        self.assertEqual(
            [1, 2, 2],
            [cluster.level for cluster in clusters],
        )
        # The fine level is sorted by signature, so the order is the signature's
        # and not the order the readings were handed over in.
        self.assertEqual(
            [("CHAT_LOG:TRUNCATED_LOG",), ("GPS_TRACE:GPS_GAP",)],
            [cluster.signature for cluster in clusters if cluster.level == 2],
        )

    def test_the_same_readings_in_two_orders_name_the_same_clusters(self):
        readings = [
            a_reading(3, "ROUTE_DEVIATION", gaps.TRIGGER_BELOW_FLOOR, ()),
            a_reading(1, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR, ("A:B",)),
            a_reading(2, "NO_SHOW_CHARGE", gaps.TRIGGER_JUDGE_NO_CLAUSE, ()),
            a_reading(4, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR, ("A:B",)),
        ]

        def shape(sequence):
            return [
                (cluster.cluster_id, cluster.level, cluster.category, cluster.trigger,
                 cluster.signature, cluster.cases)
                for cluster in gaps.build_clusters(sequence, min_cases=1)
            ]

        forward = shape(readings)
        backward = shape(list(reversed(readings)))
        shuffled = shape([readings[2], readings[0], readings[3], readings[1]])
        self.assertEqual(forward, backward)
        self.assertEqual(forward, shuffled)

    def test_a_cluster_is_flagged_at_min_cases(self):
        readings = [
            a_reading(case_no, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR)
            for case_no in (1, 2, 3)
        ]
        flagged = gaps.build_clusters(readings, min_cases=3)
        self.assertTrue(all(cluster.flagged for cluster in flagged))

    def test_a_cluster_below_min_cases_is_not_flagged(self):
        readings = [
            a_reading(case_no, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR)
            for case_no in (1, 2)
        ]
        clusters = gaps.build_clusters(readings, min_cases=3)
        self.assertTrue(clusters)
        self.assertFalse(any(cluster.flagged for cluster in clusters))

    def test_moving_min_cases_moves_the_flag_and_not_the_ids(self):
        readings = [
            a_reading(case_no, "NO_SHOW_CHARGE", gaps.TRIGGER_BELOW_FLOOR)
            for case_no in (1, 2)
        ]
        strict = gaps.build_clusters(readings, min_cases=3)
        loose = gaps.build_clusters(readings, min_cases=2)
        self.assertEqual(
            [cluster.cluster_id for cluster in strict],
            [cluster.cluster_id for cluster in loose],
        )
        self.assertEqual([False], [cluster.flagged for cluster in strict])
        self.assertEqual([True], [cluster.flagged for cluster in loose])


# --------------------------------------------------------------------------
# Reading a run
# --------------------------------------------------------------------------
class ReportTests(unittest.TestCase):
    """Reading a recorded run: which cases are gaps, and which cannot be read."""

    def test_every_escalated_case_is_a_gap_and_no_other_case_is(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = build_run(tmp)
            run = gaps.read_run(run_dir)
            self.assertEqual(tuple(sorted(GAP_CASES)), run.cached_cases)
            self.assertEqual([], list(run.not_analysed))
            self.assertEqual(
                sorted(GAP_CASES),
                sorted(reading.case_no for reading in run.readings),
            )

    def test_each_gap_is_classified_with_a_known_trigger_and_its_own_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = build_run(tmp)
            run = gaps.read_run(run_dir)
            self.assertTrue(run.readings)
            for reading in run.readings:
                with self.subTest(case_no=reading.case_no):
                    self.assertTrue(known_trigger(reading.trigger), reading.trigger)
                    self.assertEqual(CATEGORY_OF[reading.case_no], reading.category)
                    self.assertEqual(run.set_name, reading.set_name)
                    self.assertEqual("corpus", reading.set_name)

    def test_a_vote_block_is_read_and_a_case_without_one_is_a_single_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = build_run(tmp, cases=(207,), judge_votes=4)
            reading = gaps.read_run(run_dir).readings[0]
            self.assertEqual("carried", reading.vote_outcome)
            # Four drafts were asked for and all four parsed, so all four are
            # valid; the quorum is 4 // 2 + 1, which is a different number.
            self.assertEqual(4, reading.valid)
            self.assertEqual(3, reading.threshold)
            self.assertEqual((), reading.abstained)
            self.assertFalse(reading.trigger.startswith(gaps.TRIGGER_SINGLE_PREFIX))

    def test_a_transcript_with_no_vote_block_is_a_single_draft_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = build_run(tmp, cases=(207,), judge_votes=1)
            reading = gaps.read_run(run_dir).readings[0]
            self.assertIsNone(reading.vote_outcome)
            self.assertTrue(reading.trigger.startswith(gaps.TRIGGER_SINGLE_PREFIX))

    def test_a_result_the_code_has_moved_past_is_reported_and_not_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = build_run(tmp, cases=(207, 210))
            case_file = runner.case_cache_path(run_dir, 210)
            document = runner.read_json(case_file)
            document["brief_sha256"] = "0" * 64
            runner.write_json(case_file, document)

            run = gaps.read_run(run_dir)
            self.assertEqual(
                [(run.set_name, 210)],
                [(item.set_name, item.case_no) for item in run.not_analysed],
            )
            self.assertEqual([207], [reading.case_no for reading in run.readings])

    def test_a_brief_that_will_not_rebuild_is_reported_rather_than_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = build_run(tmp, cases=(207,))
            case_file = runner.case_cache_path(run_dir, 207)
            document = runner.read_json(case_file)
            # A recorded version this repository does not have: the brief cannot
            # be rebuilt at it, and that is a finding rather than a crash.
            document["configuration"] = dict(document.get("configuration") or {})
            document["configuration"]["policy_version"] = 999
            runner.write_json(case_file, document)

            run = gaps.read_run(run_dir)
            self.assertEqual([], list(run.readings))
            self.assertEqual([207], [item.case_no for item in run.not_analysed])

    def test_a_case_file_that_is_not_a_case_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = build_run(tmp, cases=(207,))
            runner.case_cache_path(run_dir, 207).write_text("not json", encoding="utf-8")
            run = gaps.read_run(run_dir)
            self.assertEqual([], list(run.readings))
            self.assertEqual([207], [item.case_no for item in run.not_analysed])

    def test_the_report_document_holds_the_runs_the_pairs_and_the_clusters(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = build_run(tmp)
            report = gaps.build_report([run_dir])
            document = gaps.report_document(report, gaps.closure_index(None))
            self.assertEqual(
                {"runs", "min_cases", "note", "dropped_signature_pairs", "not_analysed", "clusters"},
                set(document),
            )
            self.assertEqual(gaps.DEFAULT_MIN_CASES, document["min_cases"])
            self.assertEqual(
                [run.set_name for run in report.runs],
                [run["set"] for run in document["runs"]],
            )
            self.assertEqual(
                [cluster.cluster_id for cluster in report.clusters],
                [cluster["cluster_id"] for cluster in document["clusters"]],
            )
            for cluster in document["clusters"]:
                self.assertEqual(
                    {"cluster_id", "level", "category", "trigger", "signature", "cases",
                     "case_count", "flagged", "case_details", "human_decisions",
                     "closures", "awaiting_review"},
                    set(cluster),
                )
                self.assertEqual(cluster["case_count"], len(cluster["cases"]))

    def test_the_report_needs_at_least_one_run(self):
        with self.assertRaises(gaps.PolicyGapError):
            gaps.build_report([])

    def test_the_report_makes_no_model_call(self):
        # A client that cannot even be constructed: if the loop reached for one,
        # this test would fail rather than quietly make a call.
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = build_run(tmp)
            out = Path(tmp) / "policy-gaps"
            with mock.patch.object(
                llm, "LLMClient", side_effect=AssertionError("a model was called")
            ):
                status = gaps.main(
                    ["report", "--run-dir", str(run_dir), "--out-dir", str(out)]
                )
            self.assertEqual(0, status)
            self.assertTrue((out / gaps.REPORT_FILE).is_file())
            self.assertTrue((out / gaps.REPORT_MD).is_file())

    def test_only_the_diff_reads_the_answer_key(self):
        # The key loader is made to fail, and the read-only and the drafting
        # halves of the loop are shown not to reach it. ``diff`` is the one
        # command that does, and it says so in its own output.
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = build_run(tmp)
            store = a_store(tmp)
            a_closure(store, "P-0001", 210)
            a_closure(store, "P-0002", 213)
            report = gaps.build_report([run_dir])
            cluster = report.cluster("C1")
            self.assertIsNotNone(cluster)
            report_file = write_report_file(Path(tmp) / "report.json", report, store)

            with mock.patch.object(
                grade, "load_answer_key", side_effect=AssertionError("the key was read")
            ):
                gaps.build_report([run_dir])
                path, reason = gaps.draft_proposal(
                    report,
                    cluster,
                    store=store,
                    proposals_root=Path(tmp) / "proposals-root",
                    model="test/drafter",
                    client_factory=factory_for(DrafterClient(a_draft())),
                    report_file=report_file,
                    now=lambda: FIXED_NOW,
                )
            self.assertIsNotNone(path, reason)

    def test_the_committed_corpus_run_reads_as_the_whole_corpus(self):
        # The headline run is the one the submission reports, and the loop must
        # be able to read it. The claim is structural -- every case the manifest
        # lists has a result, and every case it has is classified as the corpus
        # -- and deliberately not that a particular number of them are gaps,
        # which is a fact about one model's output and not about this code.
        if not CORPUS_RUN.is_dir():  # pragma: no cover - the run is committed
            self.skipTest("the committed corpus run is not present")
        run = gaps.read_run(CORPUS_RUN)
        self.assertEqual("corpus", run.set_name)
        self.assertEqual(set(development_sets.CORPUS.cases), set(run.cached_cases))
        for reading in run.readings:
            with self.subTest(case_no=reading.case_no):
                self.assertTrue(known_trigger(reading.trigger), reading.trigger)
                self.assertIn(reading.case_no, development_sets.CORPUS.cases)

    def test_the_second_set_is_read_from_its_own_directory(self):
        if not CODEX_RUN.is_dir():  # pragma: no cover - the run is committed
            self.skipTest("the committed second-set run is not present")
        run = gaps.read_run(CODEX_RUN)
        self.assertEqual("codex", run.set_name)
        self.assertEqual(set(development_sets.SECOND_SET.cases), set(run.cached_cases))

    def test_a_wild_shaped_run_is_read_as_the_held_out_set(self):
        """``runs/wild/<model>/`` is read with the held-out set's own loader.

        The set is derived from the run directory's own path, and the held-out
        set's cases are not in the corpus manifest: read as the corpus, every
        brief fails to rebuild and the run analyses nothing at all. Read as
        ``wild``, the cases it holds are the cases that ran.
        """
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = wild_shaped_run(tmp)
            run = gaps.read_run(run_dir)
            self.assertEqual("wild", run.set_name)
            self.assertEqual(set(WILD_CASES), set(run.cached_cases))
            self.assertEqual(
                [],
                [item.reason for item in run.not_analysed],
                "the held-out set's cases did not rebuild against their own loader",
            )

    def test_a_run_that_analysed_nothing_says_so(self):
        """A run with no analysed case never reads as a run with no gap.

        The two are different findings and a reader must not be able to take one
        for the other: "nothing could be analysed" says the report has no
        reading at all, and "no case was left undecided" says the policy decided
        everything it was asked. An entry whose brief digest cannot be checked is
        the first, not the second.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            run_dir = runner.run_directory(runs_dir, MODEL)
            run_dir.mkdir(parents=True)
            (run_dir / "case-00101.json").write_text("{}", encoding="utf-8")

            report = gaps.build_report([run_dir], min_cases=2)
            self.assertEqual(0, sum(len(run.readings) for run in report.runs))
            rendered = gaps.render_report(report, {})
            self.assertIn("nothing could be analysed", rendered)
            self.assertNotIn("was left undecided", rendered)

            out_dir = Path(tmp) / "policy-gaps"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = gaps.main(
                    [
                        "report",
                        "--run-dir", str(run_dir),
                        "--runs-dir", str(runs_dir),
                        "--model", MODEL,
                        "--min-cases", "2",
                        "--out-dir", str(out_dir),
                    ]
                )
            self.assertEqual(0, status)
            self.assertIn("nothing could be analysed", stdout.getvalue())
            self.assertNotIn("was left undecided", stdout.getvalue())
            self.assertIn(
                "nothing could be analysed",
                (out_dir / gaps.REPORT_MD).read_text(encoding="utf-8"),
            )


class ReportDestinationTests(unittest.TestCase):
    """Where the report may not be written, checked rather than intended."""

    def test_a_headline_run_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            destination = runner.run_directory(runs_dir, MODEL)
            destination.mkdir(parents=True)
            with self.assertRaises(gaps.PolicyGapError):
                gaps.assert_not_a_run_directory(destination, runs_dir, MODEL)

    def test_a_headline_directory_spelled_in_another_case_is_refused(self):
        """This volume is case-insensitive, so the guard compares folded.

        ``runs/WILD/<slug>`` names the same directory as ``runs/wild/<slug>``,
        and ``runs/External/`` names the same directory as ``runs/external/``. A
        guard that answered about the spelling would refuse one and accept the
        other while both name the same place, so the comparison is made on
        case-folded components.

        ``runs/<SLUG>/`` is in the list as well as the sealed roots, and it is
        the one destination only this guard covers: the sealed roots are refused
        a second time by the runner's own guard, so a case-folded spelling of
        *those* would be caught even if this comparison were not folded.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            for destination in (
                runs_dir / "WILD" / runner.model_slug(MODEL),
                runs_dir / "Wild" / runner.model_slug(MODEL),
                runs_dir / runner.model_slug(MODEL).upper(),
                runs_dir / "External" / "anything",
                runs_dir / "EXTERNAL",
            ):
                with self.subTest(destination=str(destination.relative_to(runs_dir))):
                    with self.assertRaises(gaps.PolicyGapError):
                        gaps.assert_not_a_run_directory(destination, runs_dir, MODEL)

    def test_a_directory_holding_a_runs_own_results_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            destination = runs_dir / "somewhere" / "else"
            destination.mkdir(parents=True)
            (destination / runner.METADATA_FILE).write_text("{}", encoding="utf-8")
            with self.assertRaises(gaps.PolicyGapError):
                gaps.assert_not_a_run_directory(destination, runs_dir, MODEL)

    def test_a_directory_holding_case_files_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            destination = runs_dir / "somewhere"
            destination.mkdir(parents=True)
            (destination / "case-00101.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(gaps.PolicyGapError):
                gaps.assert_not_a_run_directory(destination, runs_dir, MODEL)

    def test_a_directory_under_the_external_runs_root_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            destination = runs_dir / runner.EXTERNAL_RUNS_SUBDIR / "anything"
            destination.mkdir(parents=True)
            with self.assertRaises(gaps.PolicyGapError):
                gaps.assert_not_a_run_directory(destination, runs_dir, MODEL)

    def test_a_directory_of_its_own_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            destination = runs_dir / gaps.POLICY_GAPS_DIRNAME
            self.assertEqual(
                destination.resolve(),
                gaps.assert_not_a_run_directory(destination, runs_dir, MODEL),
            )

    def test_an_external_run_directory_is_refused_as_a_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            external = runs_dir / runner.EXTERNAL_RUNS_SUBDIR / "ryde"
            external.mkdir(parents=True)
            with self.assertRaises(gaps.PolicyGapError):
                gaps.assert_not_an_external_run_directory(external, runs_dir)

    def test_the_command_line_refuses_a_headline_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = build_run(tmp)
            runs_dir = Path(tmp) / "runs"
            destination = runner.run_directory(runs_dir, MODEL)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                # ``--runs-dir`` is what tells the command which tree the run
                # lives in and ``--model`` whose headline directory it is, so
                # the refusal is asked in the configuration it is built for
                # rather than against the repository's own runs/.
                status = gaps.main(
                    [
                        "report",
                        "--run-dir", str(run_dir),
                        "--runs-dir", str(runs_dir),
                        "--model", MODEL,
                        "--out-dir", str(destination),
                    ]
                )
            self.assertEqual(1, status)
            self.assertIn("headline run directory", stderr.getvalue())
            self.assertFalse((destination / gaps.REPORT_FILE).exists())

    def test_a_sealed_record_the_loop_does_not_read_is_refused_as_a_source(self):
        """The sealed set this loop does not read is refused by name, component-wise.

        ``runs/wild-v2/<model>/`` is a run directory of the second sealed set.
        That set has been run -- once, on 2026-10-04 -- and its run is a sealed
        record. The loop refuses it before reading anything, because with the set
        absent from the frozen ``tribunal`` table a run directory under that root
        reads as the corpus and the report would say "nothing could be analysed".
        The two look-alikes are not caught: ``runs/wild-v2x/`` is a different
        component, and ``runs/wild-dev/`` is the re-runnable twin of the held-out
        set.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            sealed = runs_dir / runner.WILD_V2_SET_RUNS_SUBDIR / runner.model_slug(MODEL)
            sealed.mkdir(parents=True)
            with self.assertRaises(gaps.PolicyGapError):
                gaps.assert_not_a_sealed_record_the_loop_does_not_read(sealed)
            # The component after the last ``runs`` is what is compared, so a
            # directory deeper under the same set is refused too.
            with self.assertRaises(gaps.PolicyGapError):
                gaps.assert_not_a_sealed_record_the_loop_does_not_read(sealed / "nested")
            for lookalike in (
                runs_dir / (runner.WILD_V2_SET_RUNS_SUBDIR + "x") / runner.model_slug(MODEL),
                runs_dir / runner.WILD_DEV_RUNS_SUBDIR / runner.model_slug(MODEL),
            ):
                with self.subTest(lookalike=str(lookalike)):
                    self.assertEqual(
                        lookalike.resolve(),
                        gaps.assert_not_a_sealed_record_the_loop_does_not_read(lookalike),
                    )
            # The held-out set's own root is **not** refused: its 64 cases are
            # development data and the loop reads them as ``wild-dev``. Without
            # this the guard would pass whether it named one root or both.
            held_out = (
                runs_dir / runner.SEALED_SET_RUNS_SUBDIR / runner.model_slug(MODEL)
            )
            self.assertEqual(
                held_out.resolve(),
                gaps.assert_not_a_sealed_record_the_loop_does_not_read(held_out),
                "the held-out set's own root is one the loop does read",
            )

    def test_the_report_command_refuses_the_sealed_record_before_loading_a_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            sealed = runs_dir / runner.WILD_V2_SET_RUNS_SUBDIR / runner.model_slug(MODEL)
            sealed.mkdir(parents=True)
            out_dir = runs_dir / gaps.POLICY_GAPS_DIRNAME
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = gaps.main(
                    [
                        "report",
                        "--run-dir", str(sealed),
                        "--runs-dir", str(runs_dir),
                        "--model", MODEL,
                        "--out-dir", str(out_dir),
                    ]
                )
            self.assertEqual(1, status)
            self.assertIn("sealed", stderr.getvalue())
            # The three things the refusal has to say: the set has been run, it
            # is a sealed record, and this loop is not one of its readers.
            self.assertIn("has been run", stderr.getvalue())
            self.assertIn("sealed record", stderr.getvalue())
            self.assertIn("does not read it", stderr.getvalue())
            self.assertFalse((out_dir / gaps.REPORT_FILE).exists())

    def test_the_rerun_plan_refuses_the_sealed_record_before_the_amendment(self):
        """``rerun`` refuses the directory before it reads the amendment file.

        The refusal is about the directory the caller named, so it must not be
        something a caller reaches only once the amendment has loaded. The
        second half is what makes the order observable: the amendment number
        there names no file, and the directory is still what comes back.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            sealed = (
                runs_dir / runner.WILD_V2_SET_RUNS_SUBDIR / runner.model_slug(MODEL)
            )
            sealed.mkdir(parents=True)

            with self.assertRaises(gaps.PolicyGapError) as caught:
                gaps.plan_rerun(1, [sealed], runs_dir=runs_dir)
            self.assertIn("sealed", str(caught.exception))

            with self.assertRaises(gaps.PolicyGapError) as caught:
                gaps.plan_rerun(9999, [sealed], runs_dir=runs_dir)
            self.assertIn("sealed", str(caught.exception))
            self.assertNotIn(
                "amendment",
                str(caught.exception),
                "the amendment was read before the directory was refused",
            )

    def test_the_diff_refuses_a_record_that_names_the_sealed_record(self):
        """A hand-made record cannot make ``diff`` read a directory it must not.

        ``diff`` takes its run directories from the rerun record rather than
        from the command line, so the guard is asked of the record's own paths
        -- and the record below is written by hand, which is the case the guard
        exists for.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            sealed = (
                runs_dir / runner.WILD_V2_SET_RUNS_SUBDIR / runner.model_slug(MODEL)
            )
            sealed.mkdir(parents=True)
            record_path = (
                runs_dir / runner.policy_v_directory_name(2) / gaps.RERUN_FILE
            )
            record_path.parent.mkdir(parents=True)
            record_path.write_text(
                json.dumps(
                    {
                        "number": 1,
                        "sources": [{"run_dir": str(sealed), "set": "corpus"}],
                        "cases": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(gaps.PolicyGapError) as caught:
                gaps.build_diff(1, runs_dir=runs_dir)
            self.assertIn("sealed", str(caught.exception))


# --------------------------------------------------------------------------
# The drafter's input
# --------------------------------------------------------------------------
class DrafterInputTests(unittest.TestCase):
    """What the drafter is given, and what it is never given."""

    def test_a_forbidden_field_name_anywhere_is_refused(self):
        for name in ("matched", "expected", "grade", "rationale", "difficulty"):
            with self.subTest(field=name):
                poisoned = [{"case_no": 1, "dispute": {}, "artifacts": [{"x": {name: 1}}]}]
                with self.assertRaises(precedents.PrecedentError):
                    gaps.drafter_input({"general": {}, "category": {}}, poisoned, [])

    def test_the_drafter_input_carries_the_policy_the_cases_and_the_closures(self):
        document = gaps.drafter_input(
            {"general": {"a": 1}, "category": {"b": 2}},
            [{"case_no": 1}],
            [{"precedent_id": "P-0001"}],
        )
        self.assertEqual({"policy", "cases", "closures"}, set(document))
        self.assertEqual({"general", "category"}, set(document["policy"]))
        self.assertEqual([{"case_no": 1}], document["cases"])
        self.assertEqual([{"precedent_id": "P-0001"}], document["closures"])

    def test_the_case_for_the_drafter_carries_no_raw_payload(self):
        brief_object = brief.build_brief_for_case(loader.load_case(207))
        case = gaps.case_for_drafter(brief_object)
        self.assertEqual({"case_no", "dispute", "artifacts"}, set(case))
        self.assertTrue(case["artifacts"])
        for item in case["artifacts"]:
            with self.subTest(evidence_id=item["evidence_id"]):
                self.assertEqual(
                    {"evidence_id", "evidence_type", "admissibility", "derived"},
                    set(item),
                )

    def test_the_case_for_the_drafter_carries_the_derived_facts_when_there_are_any(self):
        # The derived block is what a clause can rest on, so it must survive;
        # the raw payload it was derived from must not. It is the *brief* that
        # computes the derived facts, which is why the drafter is handed a brief
        # and not a bundle -- a bundle carries no derived block at all.
        brief_object = brief.build_brief_for_case(loader.load_case(101))
        case = gaps.case_for_drafter(brief_object)
        derived = [
            item["derived"] for item in case["artifacts"] if item["derived"] is not None
        ]
        self.assertTrue(derived, "no artifact of case 101 carries a derived block")

    def test_the_closure_for_the_drafter_carries_the_decision_and_the_clause_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = a_store(tmp)
            entry = a_closure(store, "P-0001", 210, ruling="PARTIAL_REFUND")
            carried = gaps.closure_for_drafter(entry)
            self.assertEqual(
                {"precedent_id", "category", "decision", "clause_ids",
                 "amount_contested_sgd", "summary", "closed_by"},
                set(carried),
            )
            self.assertEqual("P-0001", carried["precedent_id"])
            self.assertEqual("PARTIAL_REFUND", carried["decision"]["ruling"])
            self.assertEqual(["POL-NS-02"], carried["clause_ids"])

    def test_the_message_is_the_canonical_serialisation_of_the_input(self):
        document = gaps.drafter_input({"general": {}, "category": {}}, [], [])
        message = gaps.drafter_user_message(document)
        self.assertEqual(canonical(document), message)
        self.assertEqual(document, json.loads(message))


class DrafterPromptTests(unittest.TestCase):
    """The prompt the drafter is handed, read as prose and as a parsed example."""

    def setUp(self):
        self.path = PROMPTS_DIR / gaps.POLICY_DRAFTER_PROMPT_FILE
        self.lines = self.path.read_text(encoding="utf-8").splitlines()

    def test_the_prompt_is_a_file_of_headings(self):
        # Read line by line rather than searched as one string: the claim is
        # that the prompt has these sections and no others, which a substring
        # search cannot make.
        headings = [line for line in self.lines if line.startswith("#")]
        self.assertEqual(
            [
                "# Policy drafter — system prompt",
                "## Your role",
                "## What you return",
                "## How to write the clause",
                "## One worked example",
            ],
            headings,
        )

    def test_the_prompt_says_the_draft_takes_effect_only_on_approval(self):
        body = [line for line in self.lines if not line.startswith("#")]
        joined = " ".join(body)
        self.assertIn("only their approval puts a clause into the policy", joined)

    def test_the_prompt_says_the_answer_carries_no_answer_field(self):
        # The rule is one bullet of the "How to write the clause" list, so the
        # claim is that a bullet leads with the marker -- not that some line is
        # exactly the marker, which no bullet ever is.
        leads = [
            line.strip()
            for line in self.lines
            if line.strip().startswith("- **No answer field, ever.**")
        ]
        self.assertEqual(1, len(leads))

    def test_the_worked_example_is_exactly_one_parsed_json_block(self):
        fences = [index for index, line in enumerate(self.lines) if line.strip() == "```json"]
        self.assertEqual(1, len(fences))
        start = fences[0]
        end = next(
            index for index in range(start + 1, len(self.lines))
            if self.lines[index].strip() == "```"
        )
        example = json.loads("\n".join(self.lines[start + 1:end]))
        self.assertEqual(
            {"clause", "reproduces", "does_not_reproduce", "interacts_with"}, set(example)
        )
        self.assertEqual(set(policy_versions.CLAUSE_FIELDS), set(example["clause"]))

    def test_the_worked_example_names_a_clause_that_does_not_exist(self):
        # The example must not be a real answer to a real cluster. Its clause id
        # is not in any committed policy file, and its precedent ids are not in
        # the library.
        example = self._example()
        policies = loader.load_policies("NO_SHOW_CHARGE")
        existing = {
            clause.get("id")
            for policy in policies.values()
            for clause in (policy.get("clauses") or ())
        }
        self.assertNotIn(example["clause"]["id"], existing)
        self.assertFalse(
            policy_versions.CLAUSE_ID_RE.match(example["clause"]["id"]),
            "the example's clause id is a real clause id shape",
        )

    def test_the_worked_example_names_a_category_no_policy_file_carries(self):
        example = self._example()
        carried = set(policy_versions.PREFIX_CATEGORY.values())
        self.assertNotIn(example["clause"]["category"], carried)

    def test_the_worked_example_is_marked_as_invented(self):
        """The example is invented, and the prompt says so.

        The prompt calls its precedent ids fictitious. Until 2026-10-01 the
        library was empty and that could be asserted as "the example names no
        id the library holds"; the first full pass then closed 508 and 530 and
        minted ``P-0001`` and ``P-0002``, so the example's ``P-0001`` is now a
        real closure. What still holds, and is what makes the block read as a
        shape rather than as real decisions, is that at least one id the
        example names is not in the library and that its clause id resolves in
        no loaded policy.
        """
        example = self._example()
        named = set(example["reproduces"])
        named.update(item["precedent_id"] for item in example["does_not_reproduce"])
        self.assertTrue(named)
        library = {entry.get("precedent_id") for entry in precedents.read_entries(
            precedents.store_path(None)
        )}
        self.assertTrue(named - library)
        self.assertIsNone(policy_versions.CLAUSE_ID_RE.match(example["clause"]["id"]))

    def _example(self):
        fences = [index for index, line in enumerate(self.lines) if line.strip() == "```json"]
        start = fences[0]
        end = next(
            index for index in range(start + 1, len(self.lines))
            if self.lines[index].strip() == "```"
        )
        return json.loads("\n".join(self.lines[start + 1:end]))


# --------------------------------------------------------------------------
# Validating a draft
# --------------------------------------------------------------------------
class DraftValidationTests(unittest.TestCase):
    """Every way a draft is refused, and the one way it is kept."""

    def setUp(self):
        self.policies = loader.load_policies("NO_SHOW_CHARGE")
        self.category = "NO_SHOW_CHARGE"

    def check(self, answer):
        return gaps.validate_draft(answer, policies=self.policies, category=self.category)

    def assert_refused(self, answer):
        draft, reason = self.check(answer)
        self.assertIsNone(draft)
        self.assertTrue(reason, "a refusal carries a reason")
        return reason

    def test_a_valid_draft_is_kept(self):
        draft, reason = self.check(a_draft())
        self.assertEqual("", reason)
        self.assertEqual(set(a_draft()), set(draft))

    def test_an_answer_that_is_not_an_object_is_refused(self):
        self.assert_refused(["not", "an", "object"])

    def test_a_missing_top_level_field_is_refused(self):
        answer = a_draft()
        del answer["interacts_with"]
        self.assert_refused(answer)

    def test_an_unexpected_top_level_field_is_refused(self):
        self.assert_refused(a_draft(expected_ruling="FULL_REFUND"))

    def test_a_clause_that_is_not_an_object_is_refused(self):
        self.assert_refused(a_draft(clause="POL-NS-10"))

    def test_a_missing_clause_field_is_refused(self):
        answer = a_draft()
        del answer["clause"]["notes"]
        self.assert_refused(answer)

    def test_an_unexpected_clause_field_is_refused(self):
        answer = a_draft()
        answer["clause"]["expected"] = "FULL_REFUND"
        self.assert_refused(answer)

    def test_a_clause_id_of_the_wrong_shape_is_refused(self):
        self.assert_refused(a_draft(clause={"id": "NS-10"}))
        self.assert_refused(a_draft(clause={"id": "POL-XX-10"}))

    def test_a_clause_category_that_is_not_the_prefixs_is_refused(self):
        # POL-RD- names a route-deviation clause, so a clause that declares
        # NO_SHOW_CHARGE under it is refused before the cluster is consulted.
        self.assert_refused(
            a_draft(clause={"id": "POL-RD-{0:02d}".format(NEXT_FREE["RD"])})
        )

    def test_a_clause_category_that_is_not_the_clusters_is_refused(self):
        policies = loader.load_policies("ROUTE_DEVIATION")
        draft, reason = gaps.validate_draft(
            a_draft(clause={"id": "POL-RD-{0:02d}".format(NEXT_FREE["RD"]),
                            "category": "ROUTE_DEVIATION"}),
            policies=policies,
            category="NO_SHOW_CHARGE",
        )
        self.assertIsNone(draft)
        self.assertTrue(reason)

    def test_a_clause_that_is_not_the_next_free_number_is_refused(self):
        self.assert_refused(a_draft(clause={"id": "POL-NS-01"}))
        self.assert_refused(
            a_draft(clause={"id": "POL-NS-{0:02d}".format(NEXT_FREE["NS"] + 1)})
        )

    def test_licenses_that_is_not_a_non_empty_list_is_refused(self):
        self.assert_refused(a_draft(clause={"licenses": []}))
        self.assert_refused(a_draft(clause={"licenses": "FULL_REFUND"}))

    def test_a_license_pol_gen_03_does_not_grant_is_refused(self):
        self.assert_refused(a_draft(clause={"licenses": ["MADE_UP_VALUE"]}))

    def test_a_rule_naming_a_clause_that_does_not_resolve_is_refused(self):
        self.assert_refused(
            a_draft(clause={"rule": "Where POL-NS-99 applies, the charge stands."})
        )

    def test_a_notes_field_naming_a_clause_that_does_not_resolve_is_refused(self):
        self.assert_refused(a_draft(clause={"notes": "It reads POL-RD-99."}))

    def test_interacts_with_that_is_not_a_list_of_clause_ids_is_refused(self):
        self.assert_refused(a_draft(interacts_with="POL-NS-02"))
        self.assert_refused(a_draft(interacts_with=[2]))

    def test_interacts_with_naming_a_clause_that_does_not_resolve_is_refused(self):
        self.assert_refused(a_draft(interacts_with=["POL-NS-99"]))

    def test_reproduces_that_is_not_a_list_of_precedent_ids_is_refused(self):
        self.assert_refused(a_draft(reproduces="P-0001"))
        self.assert_refused(a_draft(reproduces=[1]))

    def test_a_does_not_reproduce_entry_without_a_reason_is_refused(self):
        self.assert_refused(a_draft(does_not_reproduce=[{"precedent_id": "P-0001"}]))
        self.assert_refused(
            a_draft(does_not_reproduce=[{"precedent_id": "P-0001", "reason": "  "}])
        )

    def test_a_does_not_reproduce_entry_without_a_precedent_id_is_refused(self):
        self.assert_refused(a_draft(does_not_reproduce=[{"reason": "it differs"}]))

    def test_a_clause_that_names_itself_is_not_counted_as_unresolved(self):
        # The clause is new, so it is not in the loaded policy; naming itself is
        # how a clause says what it is about, and that is not an error.
        answer = a_draft()
        answer["clause"]["notes"] = "This clause, {0}, reads POL-NS-02.".format(
            answer["clause"]["id"]
        )
        draft, reason = self.check(answer)
        self.assertEqual("", reason)
        self.assertIsNotNone(draft)


# --------------------------------------------------------------------------
# Drafting a proposal
# --------------------------------------------------------------------------
class DraftProposalTests(unittest.TestCase):
    """One model call, one proposal, and a refusal before the call whenever possible."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.run_dir, _ = build_run(self.tmp)
        self.report = gaps.build_report([self.run_dir])
        self.cluster = self.report.cluster("C1")
        self.store = a_store(self.tmp)
        a_closure(self.store, "P-0001", 210)
        a_closure(self.store, "P-0002", 213)
        self.report_file = write_report_file(self.tmp / "report.json", self.report, self.store)

    def tearDown(self):
        self._tmp.cleanup()

    def draft(self, client=None, **overrides):
        arguments = dict(
            store=self.store,
            proposals_root=self.tmp / "policy-root",
            model="test/drafter",
            client_factory=factory_for(client or DrafterClient(a_draft())),
            report_file=self.report_file,
            now=lambda: FIXED_NOW,
        )
        arguments.update(overrides)
        return gaps.draft_proposal(self.report, self.cluster, **arguments)

    def test_the_fixture_is_a_flagged_cluster_of_no_show_cases(self):
        self.assertIsNotNone(self.cluster)
        self.assertTrue(self.cluster.flagged)
        self.assertEqual("NO_SHOW_CHARGE", self.cluster.category)
        self.assertEqual(tuple(sorted(NO_SHOW_GAPS)), self.cluster.cases)

    def test_a_valid_draft_is_written_as_a_proposal_beside_its_transcript(self):
        path, reason = self.draft()
        self.assertEqual("", reason)
        self.assertIsNotNone(path)
        self.assertEqual(
            gaps.proposals_directory(self.tmp / "policy-root"), path.parent
        )
        proposal = runner.read_json(path)
        self.assertEqual(gaps.PROPOSAL_STATUS_PROPOSED, proposal["status"])
        self.assertEqual(self.cluster.cluster_id, proposal["cluster_id"])
        self.assertEqual(list(self.cluster.cases), proposal["cases"])
        self.assertEqual(self.cluster.category, proposal["category"])
        self.assertEqual(self.cluster.trigger, proposal["trigger"])
        self.assertEqual("test/drafter", proposal["model"])
        self.assertEqual(FIXED_NOW, proposal["created_at"])
        self.assertEqual(set(policy_versions.CLAUSE_FIELDS), set(proposal["clause"]))
        self.assertTrue(
            (path.parent / (path.stem + ".transcript.json")).is_file()
        )

    def test_the_proposal_records_the_report_it_came_from_and_its_digest(self):
        path, _ = self.draft()
        proposal = runner.read_json(path)
        self.assertEqual(
            hashlib.sha256(self.report_file.read_bytes()).hexdigest(),
            proposal["report_sha256"],
        )
        self.assertTrue(proposal["report_file"])

    def test_the_drafter_is_asked_once_with_a_json_object_format(self):
        client = DrafterClient(a_draft())
        path, reason = self.draft(client=client)
        self.assertIsNotNone(path, reason)
        self.assertEqual(1, len(client.calls))
        self.assertEqual(llm.JSON_OBJECT_FORMAT, client.calls[0]["response_format"])
        self.assertEqual(
            (PROMPTS_DIR / gaps.POLICY_DRAFTER_PROMPT_FILE).read_text(encoding="utf-8"),
            client.calls[0]["system_prompt"],
        )

    def test_the_drafter_is_given_the_cases_the_closures_and_the_policy(self):
        client = DrafterClient(a_draft())
        self.draft(client=client)
        message = json.loads(client.calls[0]["user_message"])
        self.assertEqual({"policy", "cases", "closures"}, set(message))
        self.assertEqual(
            sorted(self.cluster.cases), sorted(case["case_no"] for case in message["cases"])
        )
        self.assertEqual(
            ["P-0001", "P-0002"],
            [closure["precedent_id"] for closure in message["closures"]],
        )
        self.assertEqual({"general", "category"}, set(message["policy"]))

    def test_a_draft_that_fails_validation_is_recorded_as_rejected_by_code(self):
        client = DrafterClient(a_draft(clause={"id": "POL-NS-01"}))
        path, reason = self.draft(client=client)
        self.assertIsNone(path)
        self.assertTrue(reason)
        directory = gaps.proposals_directory(self.tmp / "policy-root")
        rejected = sorted(directory.glob("*.rejected.json"))
        self.assertEqual(1, len(rejected))
        record = runner.read_json(rejected[0])
        self.assertEqual(gaps.REJECTED_BY_CODE, record["status"])
        self.assertEqual(reason, record["reason"])
        self.assertEqual(self.cluster.cluster_id, record["cluster_id"])
        self.assertTrue(sorted(directory.glob("*.transcript.json")))

    def test_an_unflagged_cluster_is_refused_before_any_call(self):
        small = gaps.build_report([self.run_dir], min_cases=4)
        cluster = small.cluster("C1")
        self.assertFalse(cluster.flagged)
        path, reason = gaps.draft_proposal(
            small,
            cluster,
            store=self.store,
            proposals_root=self.tmp / "policy-root",
            model="test/drafter",
            client_factory=a_client_that_must_not_be_built(),
            report_file=self.report_file,
            now=lambda: FIXED_NOW,
        )
        self.assertIsNone(path)
        self.assertTrue(reason)

    def test_fewer_than_two_closures_is_refused_before_any_call(self):
        store = a_store(self.tmp, name="one-closure")
        a_closure(store, "P-0001", 210)
        path, reason = gaps.draft_proposal(
            self.report,
            self.cluster,
            store=store,
            proposals_root=self.tmp / "policy-root",
            model="test/drafter",
            client_factory=a_client_that_must_not_be_built(),
            report_file=self.report_file,
            now=lambda: FIXED_NOW,
        )
        self.assertIsNone(path)
        self.assertTrue(reason)

    def test_no_closures_at_all_is_refused_before_any_call(self):
        path, reason = gaps.draft_proposal(
            self.report,
            self.cluster,
            store=a_store(self.tmp, name="empty-store"),
            proposals_root=self.tmp / "policy-root",
            model="test/drafter",
            client_factory=a_client_that_must_not_be_built(),
            report_file=self.report_file,
            now=lambda: FIXED_NOW,
        )
        self.assertIsNone(path)
        self.assertTrue(reason)

    def test_a_report_path_that_is_not_named_is_refused_before_any_call(self):
        path, reason = gaps.draft_proposal(
            self.report,
            self.cluster,
            store=self.store,
            proposals_root=self.tmp / "policy-root",
            model="test/drafter",
            client_factory=a_client_that_must_not_be_built(),
            report_file=None,
            now=lambda: FIXED_NOW,
        )
        self.assertIsNone(path)
        self.assertTrue(reason)

    def test_the_next_proposal_number_continues_the_amendment_sequence(self):
        root = self.tmp / "policy-root"
        self.assertEqual(
            policy_versions.current_version(), gaps.next_proposal_number(root)
        )
        directory = gaps.proposals_directory(root)
        directory.mkdir(parents=True)
        (directory / "{0:04d}-something.json".format(policy_versions.current_version())).write_text(
            "{}", encoding="utf-8"
        )
        self.assertEqual(
            policy_versions.current_version() + 1, gaps.next_proposal_number(root)
        )

    def test_the_command_line_refuses_a_cluster_the_report_does_not_hold(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = gaps.main(
                ["draft", "--report", str(self.report_file), "--cluster", "C99",
                 "--store", str(self.store), "--proposals-dir", str(self.tmp / "policy-root")]
            )
        self.assertEqual(1, status)

    def test_the_command_line_refuses_an_unflagged_cluster_before_any_call(self):
        report_file = write_report_file(
            self.tmp / "small-report.json",
            gaps.build_report([self.run_dir], min_cases=4),
            self.store,
        )
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = gaps.main(
                ["draft", "--report", str(report_file), "--cluster", "C1",
                 "--store", str(self.store), "--proposals-dir", str(self.tmp / "policy-root")]
            )
        self.assertEqual(1, status)

    def test_a_report_file_that_is_not_a_report_is_refused(self):
        bad = self.tmp / "bad-report.json"
        bad.write_text('{"clusters": [{"cluster_id": "C1"}]}', encoding="utf-8")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = gaps.main(
                ["draft", "--report", str(bad), "--cluster", "C1",
                 "--store", str(self.store), "--proposals-dir", str(self.tmp / "policy-root")]
            )
        self.assertEqual(1, status)

    def test_a_report_document_rebuilds_into_the_report_it_came_from(self):
        document = runner.read_json(self.report_file)
        rebuilt = gaps._report_from_document(document)
        self.assertEqual(
            [(cluster.cluster_id, cluster.cases, cluster.flagged)
             for cluster in self.report.clusters],
            [(cluster.cluster_id, cluster.cases, cluster.flagged)
             for cluster in rebuilt.clusters],
        )
        self.assertEqual(
            sorted(reading.case_no for reading in self.report.readings),
            sorted(reading.case_no for reading in rebuilt.readings),
        )


# --------------------------------------------------------------------------
# approve / reject
# --------------------------------------------------------------------------
class ApproveTests(unittest.TestCase):
    """The one writer of ``policy/amendments/``, and what it refuses."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.amendments_root = self.tmp / "policy-root"
        self.proposal = self._write_proposal(a_draft())
        self.report_file = self.tmp / "report.json"
        self.report_file.write_text("{}\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _write_proposal(self, clause, *, status=gaps.PROPOSAL_STATUS_PROPOSED):
        directory = gaps.proposals_directory(self.tmp / "proposal-root")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "0001-proposal.json"
        path.write_text(
            canonical(
                {
                    "status": status,
                    "cluster_id": "C1",
                    "cases": list(NO_SHOW_GAPS),
                    "category": "NO_SHOW_CHARGE",
                    "trigger": gaps.TRIGGER_BELOW_FLOOR,
                    "signature": [],
                    "report_file": "runs/policy-gaps/report.json",
                    "report_sha256": "0" * 64,
                    "model": "test/drafter",
                    "created_at": FIXED_NOW,
                    "clause": clause["clause"],
                    "reproduces": clause["reproduces"],
                    "does_not_reproduce": clause["does_not_reproduce"],
                    "interacts_with": clause["interacts_with"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def approve(self, **overrides):
        arguments = dict(approved_by="reviewer", amendments_root=self.amendments_root,
                         now=lambda: FIXED_NOW)
        arguments.update(overrides)
        return gaps.approve_proposal(self.proposal, **arguments)

    def test_approve_writes_the_amendment_and_returns_the_new_version(self):
        version, path = self.approve()
        self.assertEqual(policy_versions.BASE_VERSION + 1, version)
        self.assertTrue(path.is_file())
        self.assertEqual(
            policy_versions.amendments_dir(self.amendments_root), path.parent
        )
        self.assertEqual(
            policy_versions.BASE_VERSION + 1,
            policy_versions.current_version(self.amendments_root),
        )

    def test_the_amendment_carries_exactly_the_amendment_fields_and_one_clause(self):
        _version, path = self.approve()
        document = runner.read_json(path)
        self.assertEqual(
            set(policy_versions.AMENDMENT_FIELDS) | {"clause"}, set(document)
        )
        self.assertEqual(set(policy_versions.CLAUSE_FIELDS), set(document["clause"]))
        self.assertEqual(policy_versions.BASE_VERSION, document["base_version"])
        self.assertEqual("reviewer", document["approved_by"])
        self.assertEqual(FIXED_NOW, document["approved_at"])
        self.assertEqual("C1", document["cluster_id"])
        self.assertEqual(list(NO_SHOW_GAPS), document["cases"])
        self.assertEqual(
            hashlib.sha256(self.proposal.read_bytes()).hexdigest(),
            document["proposal_sha256"],
        )

    def test_the_amendment_re_reads_through_the_policy_version_loader(self):
        _version, path = self.approve()
        loaded = policy_versions.load_amendment(path)
        # The recorded proposal path is resolved as it is written, and on this
        # platform /var is a link to /private/var, so the two are compared as the
        # files they name rather than as the strings they were built from.
        recorded = Path(loaded["proposal_file"])
        if not recorded.is_absolute():
            recorded = PROJECT_ROOT / recorded
        self.assertEqual(self.proposal.resolve(), recorded.resolve())
        self.assertEqual(
            hashlib.sha256(self.proposal.read_bytes()).hexdigest(),
            loaded["proposal_sha256"],
        )

    def test_the_amendment_is_applied_to_the_policy_it_belongs_to(self):
        _version, path = self.approve()
        # ``loader.load_policies`` reads the repository's own policy/amendments/
        # and takes no root, so the application is asked through the module that
        # owns it, at the root the amendment was actually written to.
        applied = policy_versions.apply_amendments(
            loader.load_policies("NO_SHOW_CHARGE", policy_versions.BASE_VERSION),
            policy_versions.BASE_VERSION + 1,
            files={
                "general": loader.GENERAL_POLICY_FILE,
                "category": loader.CATEGORY_POLICY_FILES["NO_SHOW_CHARGE"],
            },
            root=self.amendments_root,
        )
        ids = [clause.get("id") for clause in applied["category"]["clauses"]]
        self.assertIn("POL-NS-{0:02d}".format(NEXT_FREE["NS"]), ids)
        self.assertIn("+amendment.", str(applied["category"]["version"]))
        # It lands in the no-show policy and leaves the general one alone.
        self.assertEqual(
            [
                clause.get("id")
                for clause in loader.load_policies("NO_SHOW_CHARGE")["general"]["clauses"]
            ],
            [clause.get("id") for clause in applied["general"]["clauses"]],
        )

    def test_an_amendment_that_would_compute_a_separate_base_is_refused(self):
        """Amendment 0002 on base 1 would compute version 3, and version 3 is taken.

        Version 3 is a separate policy base of its own since 2026-10-08, kept at
        ``policy/v3/``. An amendment numbered 0002 would compute the same number
        from base 1 -- a second policy under one number, and the one
        ``loader.load_policies`` would read for a version-3 brief would be the
        separate base's files, not this amendment's clause. So the amendment
        sequence stops at 0001, and the refusal names the directory. Nothing is
        written.
        """
        # One amendment in the root, so the next one would be numbered 0002.
        _version, first = self.approve()
        self.assertTrue(first.is_file())
        before = sorted(path.name for path in first.parent.iterdir())

        # The same proposal again: it is still PROPOSED, and its clause is still
        # the next free one, so only the version check can refuse it.
        self.proposal = self._write_proposal(a_draft())
        with self.assertRaises(gaps.PolicyGapError) as caught:
            self.approve()
        message = str(caught.exception)
        self.assertIn("policy/v3/", message)
        self.assertIn("0002", message)
        # Nothing was written: the directory holds exactly what it held.
        self.assertEqual(
            before, sorted(path.name for path in first.parent.iterdir())
        )

    def test_approve_on_base_three_writes_under_the_bases_own_directory(self):
        """The same command, aimed at base 3, writes ``policy/v3/amendments/``.

        ``POL-NS-11`` is the next free no-show clause in the base-3 file, and the
        scratch amendments root holds none on that base, so this is its ``0001``
        -- and it makes version **4**, which is base 3 plus one amendment. Base
        1's own sequence is not touched by it.
        """
        self.proposal = self._write_proposal(a_draft(clause={"id": "POL-NS-11"}))
        version, path = self.approve(base_version=3)

        self.assertEqual(4, version)
        self.assertEqual(
            policy_versions.amendments_dir_for(3, self.amendments_root), path.parent
        )
        self.assertEqual(self.amendments_root / "v3" / "amendments", path.parent)
        self.assertEqual("0001-pol-ns-11.json", path.name)

        document = runner.read_json(path)
        self.assertEqual(3, document["base_version"])
        self.assertEqual("POL-NS-11", document["clause"]["id"])
        self.assertEqual(
            "POL-NS-11",
            policy_versions.load_amendment(path, base_version=3)["clause"]["id"],
        )
        # Nothing was written into base 1's own directory.
        self.assertEqual(
            [], list(policy_versions.amendment_files(self.amendments_root))
        )

    def test_approve_on_base_one_still_refuses_a_second_amendment(self):
        """Base 1's sequence stops at ``0001``: its ``0002`` would compute base 3.

        This is the refusal the sheet leaves in place, and it is made before the
        directory is created, so a refused approval writes nothing.
        """
        _version, first = self.approve()
        before = sorted(entry.name for entry in first.parent.iterdir())
        self.proposal = self._write_proposal(a_draft())
        with self.assertRaises(gaps.PolicyGapError) as caught:
            self.approve()
        message = str(caught.exception)
        self.assertIn("policy/v3/", message)
        self.assertIn("0002", message)
        self.assertEqual(
            before, sorted(entry.name for entry in first.parent.iterdir())
        )

    def test_a_rejected_proposal_cannot_be_approved(self):
        self.proposal = self._write_proposal(
            a_draft(), status=gaps.PROPOSAL_STATUS_REJECTED
        )
        with self.assertRaises(gaps.PolicyGapError):
            self.approve()

    def test_a_proposal_that_is_not_there_is_refused(self):
        with self.assertRaises(gaps.PolicyGapError):
            gaps.approve_proposal(
                self.tmp / "nowhere.json",
                approved_by="reviewer",
                amendments_root=self.amendments_root,
            )

    def test_a_clause_that_is_not_the_next_free_number_is_refused(self):
        self.proposal = self._write_proposal(a_draft(clause={"id": "POL-NS-01"}))
        with self.assertRaises(gaps.PolicyGapError):
            self.approve()

    def test_a_clause_whose_category_is_not_the_prefixs_is_refused(self):
        self.proposal = self._write_proposal(
            a_draft(clause={"id": "POL-RD-{0:02d}".format(NEXT_FREE["RD"]),
                            "category": "NO_SHOW_CHARGE"})
        )
        with self.assertRaises(gaps.PolicyGapError):
            self.approve()

    def test_a_proposal_with_no_clause_is_refused(self):
        path = self.tmp / "no-clause.json"
        path.write_text(
            canonical({"status": gaps.PROPOSAL_STATUS_PROPOSED, "cases": []}) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(gaps.PolicyGapError):
            gaps.approve_proposal(
                path, approved_by="reviewer", amendments_root=self.amendments_root
            )

    def test_an_amendment_that_will_not_re_read_is_removed_and_refused(self):
        # ``approve`` checks the clause's id, prefix and category, and the
        # re-read checks the exact key set. A clause carrying a ninth key gets
        # past the first and is caught by the second, and the half-written
        # amendment must not be left behind.
        clause = a_draft()["clause"]
        clause["expected"] = "FULL_REFUND"
        self.proposal = self._write_proposal(
            {"clause": clause, "reproduces": [], "does_not_reproduce": [],
             "interacts_with": ["POL-NS-02"]}
        )
        with self.assertRaises(policy_versions.AmendmentError):
            self.approve()
        directory = policy_versions.amendments_dir(self.amendments_root)
        self.assertEqual([], sorted(directory.glob("*.json")))
        self.assertEqual(
            policy_versions.BASE_VERSION,
            policy_versions.current_version(self.amendments_root),
        )

    def test_a_broken_amendments_directory_is_refused(self):
        directory = policy_versions.amendments_dir(self.amendments_root)
        directory.mkdir(parents=True)
        (directory / "not-an-amendment.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(policy_versions.AmendmentError):
            self.approve()

    def test_a_hole_in_the_amendment_sequence_is_refused(self):
        directory = policy_versions.amendments_dir(self.amendments_root)
        directory.mkdir(parents=True)
        (directory / "0002-gap.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(policy_versions.AmendmentError):
            self.approve()

    def test_the_next_free_number_is_read_from_the_committed_policy_files(self):
        for prefix, target in policy_versions.PREFIX_FILES.items():
            with self.subTest(prefix=prefix):
                document = runner.read_json(PROJECT_ROOT / "policy" / target)
                numbers = [
                    int(policy_versions.CLAUSE_ID_RE.match(clause["id"]).group(2))
                    for clause in document["clauses"]
                    if policy_versions.CLAUSE_ID_RE.match(clause["id"]).group(1) == prefix
                ]
                self.assertEqual(max(numbers) + 1, NEXT_FREE[prefix])


class RejectTests(unittest.TestCase):
    """A rejection is recorded in the proposal, and the clause is kept."""

    def test_reject_records_the_decision_and_keeps_the_clause(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = gaps.proposals_directory(Path(tmp))
            directory.mkdir(parents=True)
            path = directory / "0001-proposal.json"
            original = {
                "status": gaps.PROPOSAL_STATUS_PROPOSED,
                "cluster_id": "C1",
                "clause": a_draft()["clause"],
            }
            path.write_text(canonical(original) + "\n", encoding="utf-8")

            returned = gaps.reject_proposal(
                path, rejected_by="reviewer", reason="it reads POL-NS-02 wrongly",
                now=lambda: FIXED_NOW,
            )
            self.assertEqual(path, returned)
            document = runner.read_json(path)
            self.assertEqual(gaps.PROPOSAL_STATUS_REJECTED, document["status"])
            self.assertEqual("reviewer", document["rejected_by"])
            self.assertEqual(FIXED_NOW, document["rejected_at"])
            self.assertEqual("it reads POL-NS-02 wrongly", document["rejection_reason"])
            self.assertEqual(original["clause"], document["clause"])

    def test_a_rejection_cannot_be_approved_afterwards(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = gaps.proposals_directory(Path(tmp))
            directory.mkdir(parents=True)
            path = directory / "0001-proposal.json"
            path.write_text(
                canonical({"status": gaps.PROPOSAL_STATUS_PROPOSED,
                           "clause": a_draft()["clause"]}) + "\n",
                encoding="utf-8",
            )
            gaps.reject_proposal(path, rejected_by="reviewer", reason="no", now=lambda: FIXED_NOW)
            with self.assertRaises(gaps.PolicyGapError):
                gaps.approve_proposal(
                    path, approved_by="reviewer", amendments_root=Path(tmp) / "policy-root"
                )

    def test_rejecting_a_proposal_that_is_not_there_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(gaps.PolicyGapError):
                gaps.reject_proposal(
                    Path(tmp) / "nowhere.json", rejected_by="reviewer", reason="no"
                )

    def test_the_command_line_refuses_a_proposal_outside_policy_proposals(self):
        """``reject`` only rewrites a file under ``policy/proposals/``.

        The rejection is written into the file the caller names, so a
        ``--proposal`` pointing anywhere else -- a case file, a run record, any
        JSON file at all -- would be rewritten. The file below holds valid JSON
        and its bytes are asserted unchanged, so a guard that let the command
        through would be seen to have rewritten it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "elsewhere" / "0001-proposal.json"
            path.parent.mkdir(parents=True)
            committed = (
                canonical(
                    {
                        "status": gaps.PROPOSAL_STATUS_PROPOSED,
                        "clause": a_draft()["clause"],
                    }
                )
                + "\n"
            )
            path.write_text(committed, encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = gaps.main(
                    [
                        "reject",
                        "--proposal",
                        str(path),
                        "--by",
                        "reviewer",
                        "--reason",
                        "no",
                    ]
                )
            self.assertEqual(1, status)
            self.assertIn("policy/proposals", stderr.getvalue())
            self.assertEqual(committed, path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# rerun: the plan
# --------------------------------------------------------------------------
class RerunPlanTests(unittest.TestCase):
    """What a rerun would run, worked out with nothing run and nothing written."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.amendments_root = self.tmp / "policy-root"
        self.run_dir, _ = build_run(self.tmp, cases=NO_SHOW_GAPS)
        self.number, self.amendment_path = self._approve(list(NO_SHOW_GAPS[:2]))

    def tearDown(self):
        self._tmp.cleanup()

    def _approve(self, cases):
        directory = gaps.proposals_directory(self.tmp / "proposal-root")
        directory.mkdir(parents=True, exist_ok=True)
        proposal = directory / "0001-proposal.json"
        proposal.write_text(
            canonical(
                {
                    "status": gaps.PROPOSAL_STATUS_PROPOSED,
                    "cluster_id": "C1",
                    "cases": list(cases),
                    "category": "NO_SHOW_CHARGE",
                    "clause": a_draft()["clause"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        version, path = gaps.approve_proposal(
            proposal, approved_by="reviewer", amendments_root=self.amendments_root,
            now=lambda: FIXED_NOW,
        )
        return version - 1, path

    def plan(self, **overrides):
        arguments = dict(amendments_root=self.amendments_root, runs_dir=self.tmp / "runs")
        arguments.update(overrides)
        return gaps.plan_rerun(self.number, [self.run_dir], **arguments)

    def test_an_amendment_that_is_not_on_disk_is_refused_with_the_numbers_that_are(self):
        with self.assertRaises(gaps.PolicyGapError):
            gaps.plan_rerun(
                9, [self.run_dir], amendments_root=self.amendments_root,
                runs_dir=self.tmp / "runs",
            )

    def test_an_amendment_number_that_is_not_four_digits_is_refused(self):
        with self.assertRaises(gaps.PolicyGapError):
            gaps._amendment_number("one")
        self.assertEqual(1, gaps._amendment_number("0001"))
        self.assertEqual(1, gaps._amendment_number(" 0001 "))

    def test_the_plan_names_the_cluster_cases_and_the_regression_cases(self):
        plan = self.plan()
        self.assertEqual(self.number + 1, plan["policy_version"])
        self.assertEqual("NO_SHOW_CHARGE", plan["category"])
        self.assertEqual(list(NO_SHOW_GAPS[:2]), plan["cluster_cases"])
        self.assertEqual(sorted(NO_SHOW_GAPS), plan["affected_cases"])
        self.assertEqual([NO_SHOW_GAPS[2]], plan["regression_cases"])

    def test_the_plan_excludes_the_other_categorys_cases(self):
        with tempfile.TemporaryDirectory() as other:
            run_dir, _ = build_run(other, cases=GAP_CASES)
            plan = gaps.plan_rerun(
                self.number, [run_dir], amendments_root=self.amendments_root,
                runs_dir=Path(other) / "runs",
            )
            self.assertEqual(sorted(NO_SHOW_GAPS), plan["affected_cases"])
            for case_no in ROUTE_GAPS:
                self.assertNotIn(case_no, plan["affected_cases"])

    def test_the_plan_sums_the_recorded_tokens_of_the_affected_cases(self):
        plan = self.plan()
        recorded = {}
        for item in plan["cases"]:
            document = runner.read_json(runner.case_cache_path(self.run_dir, item["case_no"]))
            recorded[item["case_no"]] = gaps.recorded_tokens(document)
            self.assertEqual(recorded[item["case_no"]], item["recorded_tokens"])
        self.assertEqual(sum(recorded.values()), plan["estimate_tokens"])
        self.assertGreater(plan["estimate_tokens"], 0)

    def test_a_cluster_case_from_a_run_that_was_not_named_has_no_set_and_no_cost(self):
        plan = gaps.plan_rerun(
            self.number, [self.run_dir], amendments_root=self.amendments_root,
            runs_dir=self.tmp / "runs",
        )
        self.assertEqual(sorted(NO_SHOW_GAPS), plan["affected_cases"])
        # The regression set comes from the named run and carries its cost.
        by_case = {item["case_no"]: item for item in plan["cases"]}
        self.assertIsNotNone(by_case[NO_SHOW_GAPS[2]]["set"])
        self.assertGreater(by_case[NO_SHOW_GAPS[2]]["recorded_tokens"], 0)

    def test_the_plan_records_one_source_per_named_run(self):
        plan = self.plan()
        self.assertEqual(1, len(plan["sources"]))
        source = plan["sources"][0]
        self.assertEqual("corpus", source["set"])
        self.assertEqual(sorted(NO_SHOW_GAPS), source["regression_cases"])

    def test_a_rerun_without_yes_runs_nothing_and_writes_nothing(self):
        destination_root = self.tmp / "rerun-runs"
        progress = []
        path, reason = gaps.rerun_amendment(
            self.number,
            [self.run_dir],
            model=MODEL,
            runs_dir=destination_root,
            amendments_root=self.amendments_root,
            yes=False,
            client_factory=a_client_that_must_not_be_built(),
            progress=progress.append,
        )
        self.assertIsNone(path)
        self.assertTrue(reason)
        self.assertFalse(destination_root.exists())
        self.assertTrue(progress, "the plan is printed before the refusal")

    def test_an_amendment_whose_version_this_repository_cannot_build_is_refused(self):
        # The amendment is under a temporary root, and a brief is built from the
        # repository's own policy/amendments/. The loop must say so once, naming
        # both directories, rather than let the runner refuse it once per case.
        # The repository has been at version 2 since 2026-10-01, so an amendment
        # it cannot build now has to name version 3: a second amendment is
        # written under the temporary root and the rerun is planned from it.
        number = self._second_amendment()
        destination_root = self.tmp / "rerun-runs"
        with self.assertRaises(gaps.PolicyGapError) as caught:
            gaps.rerun_amendment(
                number,
                [self.run_dir],
                model=MODEL,
                runs_dir=destination_root,
                amendments_root=self.amendments_root,
                yes=True,
                client_factory=a_client_that_must_not_be_built(),
                progress=lambda text: None,
            )
        message = str(caught.exception)
        self.assertIn(str(policy_versions.amendments_dir(self.amendments_root)), message)
        self.assertIn(str(policy_versions.amendments_dir(None)), message)
        self.assertFalse(destination_root.exists())

    def _second_amendment(self):
        """One more amendment under the temporary root, naming version 3.

        ``_approve`` writes ``0001`` there; this writes ``0002`` beside it with
        the next free no-show clause and returns its number. The loop's new
        version is then 3 while the repository is at 2, which is the branch
        under test.
        """
        directory = policy_versions.amendments_dir(self.amendments_root)
        directory.mkdir(parents=True, exist_ok=True)
        clause = dict(a_draft()["clause"])
        clause["id"] = "POL-NS-{0:02d}".format(NEXT_FREE["NS"] + 1)
        document = {
            "base_version": policy_versions.BASE_VERSION + 1,
            "proposal_file": "policy/proposals/0002-proposal.json",
            "proposal_sha256": "0" * 64,
            "report_file": "runs/policy-gaps/report.json",
            "report_sha256": "0" * 64,
            "cluster_id": "C1",
            "cases": list(NO_SHOW_GAPS[:2]),
            "approved_by": "reviewer",
            "approved_at": FIXED_NOW,
            "clause": clause,
        }
        (directory / "0002-second.json").write_text(
            canonical(document) + "\n", encoding="utf-8"
        )
        return 2


# --------------------------------------------------------------------------
# rerun: the run itself, at policy version 2
# --------------------------------------------------------------------------
class RerunTests(unittest.TestCase):
    """One real rerun, at policy version 2, with the repository left alone.

    A policy version exists only where ``policy/amendments/`` is read, and
    ``policy_versions.amendments_dir`` is the one place that path is computed:
    ``loader.load_policies``, ``apply_amendments``, ``current_version`` and the
    runner's own version check all reach the directory through it. So this class
    patches that one function, for the length of each test, to point the
    repository's amendments directory at a temporary one. The whole version
    machinery then runs against the temporary directory, and a real version-2
    rerun is exercised without ``policy/amendments/`` being written to at all --
    which is exactly what ``policy/amendments/README.md`` says of that
    directory, and what keeps a hard-killed test from leaving the repository at
    a version nobody approved.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.repository_amendments = policy_versions.amendments_dir(None)
        # The repository ships amendment 0001 now, so the guard is a snapshot
        # rather than an emptiness check: whatever the directory holds when the
        # test starts, it must hold the same when the test ends.
        self.repository_before = sorted(
            path.name for path in self.repository_amendments.iterdir()
        )
        self.amendments = self._redirect_amendments()
        self.run_dir, _ = build_run(self.tmp, cases=NO_SHOW_GAPS)
        self.destination_root = self.tmp / "rerun-runs"

    def tearDown(self):
        self._assert_the_repository_is_untouched()
        self._tmp.cleanup()

    def _redirect_amendments(self):
        """Point the repository's amendments directory at a temporary one."""
        original = policy_versions.amendments_dir
        temporary = self.tmp / "policy-root" / policy_versions.AMENDMENTS_DIRNAME

        def redirect(root=None):
            return temporary if root is None else original(root)

        patcher = mock.patch.object(policy_versions, "amendments_dir", redirect)
        patcher.start()
        self.addCleanup(patcher.stop)
        return temporary

    def _assert_the_repository_is_untouched(self):
        """The one thing this class must not have done: write to policy/."""
        self.assertEqual(
            self.repository_before,
            sorted(path.name for path in self.repository_amendments.iterdir()),
            "a test wrote into the repository's policy/amendments/",
        )

    def _approve(self, cases):
        directory = gaps.proposals_directory(self.tmp / "proposal-root")
        directory.mkdir(parents=True, exist_ok=True)
        proposal = directory / "0001-proposal.json"
        proposal.write_text(
            canonical(
                {
                    "status": gaps.PROPOSAL_STATUS_PROPOSED,
                    "cluster_id": "C1",
                    "cases": list(cases),
                    "category": "NO_SHOW_CHARGE",
                    "clause": a_draft()["clause"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        version, path = gaps.approve_proposal(
            proposal, approved_by="reviewer", now=lambda: FIXED_NOW
        )
        return version - 1, path

    def _rerun(self, number, **overrides):
        transport = rig.ScriptedTransport(grade.key_as_produced(rig.answer_key()))
        arguments = dict(
            model=MODEL,
            runs_dir=self.destination_root,
            prompts_dir=PROMPTS_DIR,
            yes=True,
            client_factory=rig.client_factory(MODEL, transport),
            git_runner=rig.git_runner(),
            progress=lambda text: None,
            now=lambda: FIXED_NOW,
        )
        arguments.update(overrides)
        return gaps.rerun_amendment(number, [self.run_dir], **arguments), transport

    def test_the_rerun_lands_under_the_version_directory_and_leaves_the_source_alone(self):
        number, _path = self._approve(list(NO_SHOW_GAPS[:2]))
        before = tree_digest(self.run_dir)

        (record_path, reason), transport = self._rerun(number)
        self.assertEqual("", reason)
        self.assertIsNotNone(record_path)
        self.assertEqual(
            self.destination_root / runner.policy_v_directory_name(number + 1),
            record_path.parent,
        )
        self.assertEqual(
            runner.policy_v_run_directory(self.destination_root, number + 1, MODEL),
            record_path.parent / runner.model_slug(MODEL),
        )
        self.assertEqual(before, tree_digest(self.run_dir))
        self.assertTrue(transport.cases_called())

    def test_the_rerun_writes_one_case_file_per_affected_case(self):
        number, _path = self._approve(list(NO_SHOW_GAPS[:2]))
        (_record_path, reason), _transport = self._rerun(number)
        self.assertEqual("", reason)
        destination = runner.policy_v_run_directory(
            self.destination_root, number + 1, MODEL
        )
        written = sorted(
            int(path.stem.split("-")[1])
            for path in destination.glob("case-*.json")
            if not path.name.endswith(".transcript.json")
        )
        self.assertEqual(sorted(NO_SHOW_GAPS), written)

    def test_the_rerun_record_names_the_destination_the_set_and_the_cost(self):
        number, _path = self._approve(list(NO_SHOW_GAPS[:2]))
        (record_path, _reason), _transport = self._rerun(number)
        record = runner.read_json(record_path)
        self.assertEqual(MODEL, record["model"])
        self.assertEqual(number + 1, record["policy_version"])
        self.assertEqual("{0:04d}".format(number), record["amendment"])
        self.assertEqual("C1", record["cluster_id"])
        self.assertEqual(
            {run.set_name for run in [gaps.read_run(self.run_dir)]},
            set(record["destinations"]),
        )
        destination = record["destinations"]["corpus"]
        for item in record["cases"]:
            with self.subTest(case_no=item["case_no"]):
                self.assertEqual(destination, item["destination"])
                self.assertIn(item["case_no"], NO_SHOW_GAPS)
        self.assertEqual(
            sorted(NO_SHOW_GAPS[:2]),
            sorted(item["case_no"] for item in record["cases"] if item["in_cluster"]),
        )
        self.assertEqual(
            [NO_SHOW_GAPS[2]],
            [item["case_no"] for item in record["cases"] if not item["in_cluster"]],
        )

    def test_the_rerun_is_at_the_new_version_and_the_source_stays_at_version_one(self):
        number, _path = self._approve(list(NO_SHOW_GAPS[:2]))
        (_record_path, _reason), _transport = self._rerun(number)
        destination = runner.policy_v_run_directory(
            self.destination_root, number + 1, MODEL
        )
        for case_no in NO_SHOW_GAPS:
            with self.subTest(case_no=case_no):
                new = runner.read_json(runner.case_cache_path(destination, case_no))
                old = runner.read_json(runner.case_cache_path(self.run_dir, case_no))
                self.assertEqual(
                    number + 1, runner.configuration_of(new)["policy_version"]
                )
                self.assertEqual(1, runner.configuration_of(old)["policy_version"])

    def test_the_version_one_run_still_reads_as_current_after_the_amendment(self):
        # An amendment adds a clause to one category's policy. A version-1 run
        # of that category records the version-1 brief digest, and this code
        # rebuilds at the version the file records -- so the headline figure is
        # not invalidated by a later approval, which is the property that makes
        # the loop safe to run at all.
        number, _path = self._approve(list(NO_SHOW_GAPS[:2]))
        self.assertEqual(1, gaps.read_run(self.run_dir).readings[0].policy_version)
        self.assertEqual([], list(gaps.read_run(self.run_dir).not_analysed))
        self.assertEqual(number + 1, policy_versions.current_version())


# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------
class DiffTests(unittest.TestCase):
    """The comparison, over rulings a test chose rather than a model produced.

    ``build_diff`` reads three things: the amendment, the rerun record, and one
    case file on each side. The tree below supplies exactly those, so the
    arithmetic can be asked about values -- including a money value that differs
    only in its trailing zeros -- rather than about whatever a transport
    happened to answer.
    """

    OLD = {
        "ruling": "PARTIAL_REFUND",
        "amount_sgd": "2.00",
        "driver_compensation_sgd": None,
        "referrals": [],
    }
    NEW = {
        "ruling": "FULL_REFUND",
        "amount_sgd": "4.00",
        "driver_compensation_sgd": None,
        "referrals": ["POL-NS-02 the charge is refunded"],
    }

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.runs_root = self.tmp / "runs"
        self.amendments_root = self.tmp / "policy-root"
        self.number = self._build_tree()

    def tearDown(self):
        self._tmp.cleanup()

    def _build_tree(self):
        """A source run, a version-2 run and a rerun record, with no model call."""
        source = runner.run_directory(self.runs_root, MODEL)
        source.mkdir(parents=True)
        destination = runner.policy_v_run_directory(self.runs_root, 2, MODEL)
        destination.mkdir(parents=True)
        for case_no in NO_SHOW_GAPS:
            runner.write_json(
                runner.case_cache_path(source, case_no),
                {
                    "case_no": case_no,
                    "ruling": {"ruling": dict(self.OLD), "discarded_claims": []},
                    "brief_sha256": "0" * 64,
                    "development_set": None,
                    "configuration": {"policy_version": 1},
                },
            )
            runner.write_json(
                runner.case_cache_path(destination, case_no),
                {
                    "case_no": case_no,
                    "ruling": {"ruling": dict(self.NEW), "discarded_claims": []},
                },
            )
        directory = self.runs_root / runner.policy_v_directory_name(2)
        directory.mkdir(parents=True, exist_ok=True)
        runner.write_json(
            directory / gaps.RERUN_FILE,
            {
                "amendment": "0001",
                "policy_version": 2,
                "model": MODEL,
                "cluster_id": "C1",
                "cases": [
                    {
                        "case_no": case_no,
                        "set": "corpus",
                        "source_dir": str(source),
                        "destination": str(destination),
                        "recorded_tokens": 0,
                        "in_cluster": case_no in NO_SHOW_GAPS[:2],
                    }
                    for case_no in NO_SHOW_GAPS
                ],
            },
        )
        self._write_amendment(list(NO_SHOW_GAPS[:2]))
        return 1

    def _write_amendment(self, cases):
        directory = policy_versions.amendments_dir(self.amendments_root)
        directory.mkdir(parents=True, exist_ok=True)
        clause = a_draft()["clause"]
        document = {
            "base_version": policy_versions.BASE_VERSION,
            "proposal_file": "policy/proposals/0001-proposal.json",
            "proposal_sha256": "0" * 64,
            "report_file": "runs/policy-gaps/report.json",
            "report_sha256": "0" * 64,
            "cluster_id": "C1",
            "cases": list(cases),
            "approved_by": "reviewer",
            "approved_at": FIXED_NOW,
            "clause": clause,
        }
        path = directory / "0001-{0}.json".format(gaps.slug_for(clause["id"]))
        path.write_text(canonical(document) + "\n", encoding="utf-8")
        return path

    def diff(self):
        return gaps.build_diff(
            self.number, runs_dir=self.runs_root, amendments_root=self.amendments_root
        )

    def test_the_diff_reports_the_before_and_after_of_every_affected_case(self):
        document = self.diff()
        self.assertEqual(
            sorted(NO_SHOW_GAPS), [case["case_no"] for case in document["cases"]]
        )
        for case in document["cases"]:
            with self.subTest(case_no=case["case_no"]):
                self.assertEqual("corpus", case["set"])
                self.assertEqual("PARTIAL_REFUND", case["old"]["ruling"])
                self.assertEqual("FULL_REFUND", case["new"]["ruling"])

    def test_changed_is_true_exactly_when_the_two_sides_render_differently(self):
        # The invariant the two defects this loop was written against broke: a
        # row marked changed whose two sides read the same, and a row marked
        # unchanged whose two sides read differently. Both are impossible now,
        # because ``changed`` is computed from the same rendering.
        document = self.diff()
        self.assertTrue(document["cases"])
        for case in document["cases"]:
            with self.subTest(case_no=case["case_no"]):
                self.assertEqual(case["old"] != case["new"], case["changed"])

    def test_money_that_differs_only_in_its_trailing_zeros_is_not_a_change(self):
        old = dict(self.OLD, amount_sgd=Decimal("4.00"))
        new = dict(self.OLD, amount_sgd=Decimal("4.0"))
        self.assertFalse(gaps._fields_differ(old, new))
        self.assertEqual(gaps._render_fields(old), gaps._render_fields(new))

    def test_a_null_amount_is_not_a_zero_amount(self):
        old = dict(self.OLD, amount_sgd=None)
        new = dict(self.OLD, amount_sgd=Decimal("0.00"))
        self.assertTrue(gaps._fields_differ(old, new))

    def test_a_referral_that_moved_only_in_its_wording_is_not_a_change(self):
        old = dict(self.OLD, referrals=["POL-NS-02 the charge is refunded"])
        new = dict(self.OLD, referrals=["POL-NS-02 refund the fare"])
        self.assertFalse(gaps._fields_differ(old, new))

    def test_a_referral_that_moved_its_clause_reference_is_a_change(self):
        old = dict(self.OLD, referrals=["POL-NS-02 the charge is refunded"])
        new = dict(self.OLD, referrals=["POL-NS-05 the charge is refunded"])
        self.assertTrue(gaps._fields_differ(old, new))

    def test_a_referral_that_moved_only_its_limb_is_a_change(self):
        # A limb is part of the clause reference, and the grader treats it as
        # significant where the key states one.
        old = dict(self.OLD, referrals=["POL-NS-05(ii) the charge is refunded"])
        new = dict(self.OLD, referrals=["POL-NS-05(iii) the charge is refunded"])
        self.assertTrue(gaps._fields_differ(old, new))

    def test_a_referral_with_no_clause_reference_is_not_the_same_as_none(self):
        self.assertTrue(gaps._fields_differ(dict(self.OLD), dict(self.OLD, referrals=["none here"])))
        self.assertFalse(
            gaps._fields_differ(
                dict(self.OLD, referrals=["none here"]), dict(self.OLD, referrals=["none here"])
            )
        )

    def test_equal_money_renders_equally(self):
        rendered = gaps._render_fields(
            {"ruling": "FULL_REFUND", "amount_sgd": Decimal("4.0"),
             "driver_compensation_sgd": Decimal("4.80"), "referrals": []}
        )
        self.assertEqual("4.00", rendered["amount_sgd"])
        self.assertEqual("4.80", rendered["driver_compensation_sgd"])

    def test_a_money_value_that_is_not_two_places_renders_as_it_stands(self):
        rendered = gaps._render_fields(
            {"ruling": "FULL_REFUND", "amount_sgd": Decimal("4.005"),
             "driver_compensation_sgd": None, "referrals": []}
        )
        self.assertEqual("4.005", rendered["amount_sgd"])
        self.assertEqual("null", rendered["driver_compensation_sgd"])

    def test_a_referral_renders_as_the_clause_reference_it_leads_with(self):
        rendered = gaps._render_fields(
            dict(self.OLD, referrals=["POL-NS-05(ii) a long sentence about the record"])
        )
        self.assertEqual(["POL-NS-05(ii)"], rendered["referrals"])

    def test_the_totals_are_over_the_cases_not_excluded(self):
        document = self.diff()
        self.assertEqual(len(NO_SHOW_GAPS), document["totals"]["cases"])
        self.assertEqual(
            len(NO_SHOW_GAPS) - len(NO_SHOW_GAPS[:2]),
            document["totals_without_the_cluster"]["cases"],
        )
        self.assertEqual(
            sum(1 for case in document["cases"] if case["changed"]),
            document["totals"]["changed"],
        )

    def test_the_totals_count_a_case_that_stopped_escalating(self):
        for case_no in NO_SHOW_GAPS:
            runner.write_json(
                runner.case_cache_path(
                    runner.policy_v_run_directory(self.runs_root, 2, MODEL), case_no
                ),
                {
                    "case_no": case_no,
                    "ruling": {
                        "ruling": dict(
                            self.NEW, ruling="PARTIAL_REFUND",
                            referrals=["POL-NS-02 the charge is refunded"],
                        ),
                        "discarded_claims": [],
                    },
                },
            )
        document = self.diff()
        self.assertEqual(0, document["totals"]["escalations_before"])
        self.assertEqual(0, document["totals"]["escalations_after"])

    def test_the_diff_refuses_without_a_rerun_record(self):
        record = (
            self.runs_root / runner.policy_v_directory_name(2) / gaps.RERUN_FILE
        )
        record.unlink()
        with self.assertRaises(gaps.PolicyGapError):
            self.diff()

    def test_the_diff_refuses_an_amendment_that_is_not_on_disk(self):
        with self.assertRaises(gaps.PolicyGapError):
            gaps.build_diff(
                9, runs_dir=self.runs_root, amendments_root=self.amendments_root
            )

    def test_the_diff_output_says_it_reads_the_frozen_key(self):
        document = self.diff()
        self.assertTrue(document["key_note"])
        rendered = gaps.render_diff(document)
        self.assertIn(document["key_note"], rendered)
        self.assertIn("in-sample", rendered)

    def test_the_diff_writes_both_its_forms_under_the_version_directory(self):
        md, js = gaps.write_diff(
            self.number, runs_dir=self.runs_root, amendments_root=self.amendments_root
        )
        directory = self.runs_root / runner.policy_v_directory_name(2)
        self.assertEqual(directory / gaps.DIFF_MD, md)
        self.assertEqual(directory / gaps.DIFF_JSON, js)
        self.assertTrue(md.is_file() and js.is_file())
        self.assertEqual(self.diff(), runner.read_json(js))

    def test_the_rendered_table_has_one_row_per_case_and_no_ragged_row(self):
        document = self.diff()
        rendered = gaps.render_diff(document)
        rows = [line for line in rendered.splitlines() if line.startswith("| `")]
        self.assertEqual(len(document["cases"]), len(rows))
        widths = {line.count("|") for line in rows}
        self.assertEqual(1, len(widths), "the table rows are not all the same width")


if __name__ == "__main__":
    unittest.main()
