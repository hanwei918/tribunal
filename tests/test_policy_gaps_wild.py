"""The policy-gap loop over the held-out set's cases as development data (part D).

``wild-v1`` was run once and its answers were read on 2026-10-01. From then on
its 64 cases are development data, and the policy-gap loop has to be able to
work over them without touching ``runs/wild/``. Six things are asserted here,
each the point of its own class:

* **a source under ``runs/wild/<model>/`` is re-run as ``wild-dev``**, into
  ``runs/wild-dev/policy-v<N>/<model>/``, and the record says so;
* **the affected cases come from the set's own case list**, not from the cached
  case files, so a case that produced only a transcript is still run — and its
  cost is estimated from the tokens that transcript recorded, which the plan
  says;
* **a `wild` run and a `wild-dev` run are never read together**, by `report`,
  `rerun` or `diff`;
* **a missing destination case file is a miss**, shown as "no ruling" and
  counted as newly missing rather than silently graded as nothing;
* **a version-2 diff says what it carries**, because version 2 holds both the
  amendment and part B's POL-RD-11 remedy and its gains cannot be attributed to
  the amendment alone;
* **a no-show brief at version 2 is byte-identical to version 1**, so a
  route-deviation amendment cannot move a no-show case's brief.

The version-2 runs are exercised against a **temporary** amendments root, and
``policy_versions.amendments_dir`` is patched for the length of each test, so
``policy/amendments/`` is never written to and the repository's own version
stays 1. Every run is built by the rig over a scripted transport: no test
reaches the network and no test reads the committed held-out run.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, policy_gaps as gaps, run_benchmark as runner  # noqa: E402
from tests import test_policy_gaps as loop_rig  # noqa: E402
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import brief, loader, policy_versions  # noqa: E402

MODEL = rig.MODEL
PROMPTS_DIR = rig.PROMPTS_DIR
FIXED_NOW = loop_rig.FIXED_NOW

WILD = development_sets.named("wild")
WILD_DEV = development_sets.named("wild-dev")

# Two of the held-out set's own cases, and one no-show case from the corpus.
WILD_CASES = loop_rig.WILD_CASES
NO_SHOW_CASE = loop_rig.NO_SHOW_GAPS[0]


def wild_shaped_run(tmp, cases=WILD_CASES):
    """A run of the held-out set's cases under ``runs/wild/<model-slug>/``."""
    return loop_rig.wild_shaped_run(tmp, cases=cases)


def wild_dev_shaped_run(tmp, cases=WILD_CASES):
    """A run of the same cases under ``runs/wild-dev/<model-slug>/``."""
    runs_dir = Path(tmp) / "runs" / WILD_DEV.runs_subdir
    rig.bench(
        tmp,
        cases=cases,
        runs_dir=runs_dir,
        key=WILD_DEV.key(),
        case_loader=WILD_DEV.load_case,
        label=WILD_DEV.name,
        key_path=WILD_DEV.key_path,
    )
    return runner.run_directory(runs_dir, MODEL)


def transcript_tokens(path):
    """The tokens a transcript records, summed the way the run sums them.

    ``prompt_tokens + completion_tokens`` is what a case file's ``total_tokens``
    is, so the estimate for a case that has only a transcript is computed the
    same way and is comparable with the estimate for a case that has a file.
    """
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return sum(
        int(entry.get("prompt_tokens") or 0) + int(entry.get("completion_tokens") or 0)
        for entry in document.get("entries") or []
    )


def route_clause(**overrides):
    """A route-deviation clause for a temporary amendment, never committed."""
    clause = {
        "id": "POL-RD-{0:02d}".format(loop_rig.NEXT_FREE["RD"]),
        "title": "Route deviation where the trace is missing",
        "category": "ROUTE_DEVIATION",
        "rule": (
            "Where the gps_trace artifact is missing the deviation is not established "
            "and the outcome is ESCALATE."
        ),
        "requires": ["gps_trace"],
        "licenses": ["ESCALATE"],
        "favours": "NEUTRAL",
        "notes": "A clause a test writes into a temporary amendments root.",
    }
    clause.update(overrides)
    return clause


class LoopCase(unittest.TestCase):
    """A temporary runs root, a temporary amendments root, and one amendment."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.runs_root = self.tmp / "runs"
        self.amendments_root = self.tmp / "policy-root"
        self._redirect_amendments()

    def _redirect_amendments(self):
        """Point the repository's amendments directory at a temporary one.

        A policy version exists only where ``policy/amendments/`` is read, and
        ``policy_versions.amendments_dir`` is the one place that path is
        computed -- ``loader.load_policies``, ``current_version`` and the
        runner's own version check all reach the directory through it. It is
        patched for the length of each test, so a real version-2 rerun is
        exercised without ``policy/amendments/`` being written to at all.
        """
        self.repository_amendments = policy_versions.amendments_dir(None)
        temporary = self.amendments_root / policy_versions.AMENDMENTS_DIRNAME
        temporary.mkdir(parents=True, exist_ok=True)
        original = policy_versions.amendments_dir

        def redirect(root=None):
            return temporary if root is None else original(root)

        patcher = mock.patch.object(policy_versions, "amendments_dir", redirect)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._assert_the_repository_is_untouched)

    def _assert_the_repository_is_untouched(self):
        """The one thing these tests must not have done: write into policy/."""
        self.assertEqual(
            [policy_versions.README_FILE],
            sorted(path.name for path in self.repository_amendments.iterdir()),
            "a test wrote into the repository's policy/amendments/",
        )

    def write_amendment(self, cases, clause=None, number=1):
        clause = route_clause() if clause is None else clause
        directory = policy_versions.amendments_dir(self.amendments_root)
        directory.mkdir(parents=True, exist_ok=True)
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
        path = directory / "{0:04d}-{1}.json".format(number, gaps.slug_for(clause["id"]))
        path.write_text(loop_rig.canonical(document) + "\n", encoding="utf-8")
        return number, path

    def write_rerun_record(self, sources, *, cases=()):
        directory = self.runs_root / runner.policy_v_directory_name(2)
        directory.mkdir(parents=True, exist_ok=True)
        runner.write_json(
            directory / gaps.RERUN_FILE,
            {
                "amendment": "0001",
                "policy_version": 2,
                "model": MODEL,
                "cluster_id": "C1",
                "sources": list(sources),
                "cases": list(cases),
            },
        )
        return directory / gaps.RERUN_FILE


# --------------------------------------------------------------------------
# The rerun source
# --------------------------------------------------------------------------
class WildSourceRerunTests(LoopCase):
    """A source under ``runs/wild/<model>/`` is re-run as ``wild-dev``."""

    def setUp(self):
        super().setUp()
        self.run_dir = wild_shaped_run(self.tmp)
        self.number, _path = self.write_amendment(WILD_CASES)

    def plan(self):
        return gaps.plan_rerun(
            self.number,
            [self.run_dir],
            amendments_root=self.amendments_root,
            runs_dir=self.runs_root,
        )

    def rerun(self):
        transport = rig.ScriptedTransport(rig.produced_from_key(WILD_DEV.key()))
        return (
            gaps.rerun_amendment(
                self.number,
                [self.run_dir],
                model=MODEL,
                runs_dir=self.runs_root,
                amendments_root=self.amendments_root,
                prompts_dir=PROMPTS_DIR,
                yes=True,
                client_factory=rig.client_factory(MODEL, transport),
                git_runner=rig.git_runner(),
                progress=lambda text: None,
                now=lambda: FIXED_NOW,
            ),
            transport,
        )

    def test_the_plan_reads_a_wild_source_as_the_re_runnable_set(self):
        plan = self.plan()
        self.assertEqual(1, len(plan["sources"]))
        source = plan["sources"][0]
        self.assertEqual("wild-dev", source["set"])
        self.assertEqual("wild", source["source_set"])
        self.assertEqual(sorted(WILD_CASES), source["regression_cases"])
        for item in plan["cases"]:
            with self.subTest(case_no=item["case_no"]):
                self.assertEqual("wild-dev", item["set"])

    def test_the_run_lands_under_the_re_runnable_sets_root(self):
        (_record_path, reason), transport = self.rerun()
        self.assertEqual("", reason)
        destination = runner.policy_v_run_directory(
            self.runs_root / "wild-dev", self.number + 1, MODEL
        )
        self.assertTrue(destination.is_dir())
        self.assertEqual(
            sorted(WILD_CASES),
            sorted(
                int(path.stem.split("-")[1])
                for path in destination.glob("case-*.json")
                if not path.name.endswith(".transcript.json")
            ),
        )
        self.assertTrue(transport.cases_called())

    def test_nothing_is_created_under_the_held_out_sets_root(self):
        before = loop_rig.tree_digest(self.runs_root / "wild")
        self.rerun()
        self.assertEqual(before, loop_rig.tree_digest(self.runs_root / "wild"))

    def test_the_record_names_the_mapping_and_the_destination(self):
        (record_path, _reason), _transport = self.rerun()
        record = runner.read_json(record_path)
        self.assertEqual(["wild-dev"], list(record["destinations"]))
        self.assertEqual(
            gaps._relative(
                runner.policy_v_run_directory(self.runs_root / "wild-dev", 2, MODEL)
            ),
            record["destinations"]["wild-dev"],
        )
        self.assertEqual(1, len(record["sources"]))
        self.assertEqual("wild-dev", record["sources"][0]["set"])
        self.assertEqual("wild", record["sources"][0]["source_set"])


# --------------------------------------------------------------------------
# The affected cases
# --------------------------------------------------------------------------
class TranscriptOnlyCaseTests(LoopCase):
    """A case the run recorded only a transcript for is still an affected case."""

    def setUp(self):
        super().setUp()
        self.run_dir = wild_shaped_run(self.tmp)
        self.transcript_only = WILD_CASES[1]
        runner.case_cache_path(self.run_dir, self.transcript_only).unlink()
        self.transcript = runner.transcript_path(self.run_dir, self.transcript_only)
        # The amendment names only the other case, so the transcript-only case
        # is a regression case: an affected case that the cluster does not hold,
        # which is where a case with no case file is easiest to lose.
        self.number, _path = self.write_amendment([WILD_CASES[0]])

    def plan(self):
        return gaps.plan_rerun(
            self.number,
            [self.run_dir],
            amendments_root=self.amendments_root,
            runs_dir=self.runs_root,
        )

    def test_the_fixture_really_has_only_a_transcript(self):
        self.assertTrue(self.transcript.is_file())
        self.assertFalse(runner.case_cache_path(self.run_dir, self.transcript_only).exists())

    def test_the_case_is_affected_even_though_it_has_no_case_file(self):
        plan = self.plan()
        self.assertEqual(sorted(WILD_CASES), plan["affected_cases"])
        self.assertIn(self.transcript_only, plan["regression_cases"])

    def test_its_cost_comes_from_the_transcript_and_the_plan_says_so(self):
        plan = self.plan()
        by_case = {item["case_no"]: item for item in plan["cases"]}
        missing = by_case[self.transcript_only]
        self.assertEqual("transcript", missing["recorded_tokens_from"])
        self.assertEqual(transcript_tokens(self.transcript), missing["recorded_tokens"])
        self.assertGreater(missing["recorded_tokens"], 0)
        present = by_case[WILD_CASES[0]]
        self.assertEqual("case_file", present["recorded_tokens_from"])
        self.assertEqual(
            sum(item["recorded_tokens"] for item in plan["cases"]), plan["estimate_tokens"]
        )


# --------------------------------------------------------------------------
# Wild and wild-dev together
# --------------------------------------------------------------------------
class BothWildSetsTests(LoopCase):
    """The two wild sets are never read in one report, rerun or diff."""

    def setUp(self):
        super().setUp()
        self.wild = wild_shaped_run(self.tmp)
        self.wild_dev = wild_dev_shaped_run(self.tmp)

    def test_a_report_over_both_is_refused(self):
        with self.assertRaises(gaps.PolicyGapError) as caught:
            gaps.build_report([self.wild, self.wild_dev], min_cases=1, prompts_dir=PROMPTS_DIR)
        self.assertIn("wild-dev", str(caught.exception))

    def test_a_rerun_over_both_is_refused(self):
        number, _path = self.write_amendment(WILD_CASES)
        with self.assertRaises(gaps.PolicyGapError) as caught:
            gaps.plan_rerun(
                number,
                [self.wild, self.wild_dev],
                amendments_root=self.amendments_root,
                runs_dir=self.runs_root,
            )
        self.assertIn("wild-dev", str(caught.exception))

    def test_a_diff_whose_record_names_both_is_refused(self):
        self.write_amendment(WILD_CASES)
        self.write_rerun_record(
            [
                {"run_dir": str(self.wild), "set": "wild", "source_set": "wild",
                 "regression_cases": list(WILD_CASES)},
                {"run_dir": str(self.wild_dev), "set": "wild-dev", "source_set": "wild-dev",
                 "regression_cases": list(WILD_CASES)},
            ]
        )
        with self.assertRaises(gaps.PolicyGapError) as caught:
            gaps.build_diff(1, runs_dir=self.runs_root, amendments_root=self.amendments_root)
        self.assertIn("wild-dev", str(caught.exception))

    def test_either_set_alone_is_accepted(self):
        for run_dir in (self.wild, self.wild_dev):
            with self.subTest(run_dir=str(run_dir)):
                gaps.build_report([run_dir], min_cases=1, prompts_dir=PROMPTS_DIR)


# --------------------------------------------------------------------------
# diff: a missing destination case file, and what version 2 carries
# --------------------------------------------------------------------------
class DiffTreeCase(LoopCase):
    """A source run, a version-2 run and a rerun record, with no model call."""

    CASES = (110, 112)

    def setUp(self):
        super().setUp()
        self.produced = rig.produced_from_key(rig.answer_key())
        self.source = runner.run_directory(self.runs_root, MODEL)
        self.source.mkdir(parents=True)
        self.destination = runner.policy_v_run_directory(self.runs_root, 2, MODEL)
        self.destination.mkdir(parents=True)
        for case_no in self.CASES:
            runner.write_json(
                runner.case_cache_path(self.source, case_no),
                {
                    "case_no": case_no,
                    "ruling": {
                        "ruling": dict(self.produced[case_no]["ruling"]),
                        "discarded_claims": [],
                    },
                    "brief_sha256": "0" * 64,
                    "development_set": None,
                    "configuration": {"policy_version": 1},
                },
            )
        self.number, _path = self.write_amendment(list(self.CASES))

    def write_destination(self, case_no):
        runner.write_json(
            runner.case_cache_path(self.destination, case_no),
            {
                "case_no": case_no,
                "ruling": {
                    "ruling": dict(self.produced[case_no]["ruling"]),
                    "discarded_claims": [],
                },
            },
        )

    def write_record(self):
        self.write_rerun_record(
            [
                {"run_dir": str(self.source), "set": "corpus", "source_set": "corpus",
                 "regression_cases": list(self.CASES)}
            ],
            cases=[
                {
                    "case_no": case_no,
                    "set": "corpus",
                    "source_dir": str(self.source),
                    "destination": str(self.destination),
                    "recorded_tokens": 0,
                    "in_cluster": case_no in self.CASES[:1],
                }
                for case_no in self.CASES
            ],
        )

    def diff(self):
        return gaps.build_diff(1, runs_dir=self.runs_root, amendments_root=self.amendments_root)


class MissingDestinationTests(DiffTreeCase):
    """A destination case file that is not there is a miss, not a blank."""

    def setUp(self):
        super().setUp()
        self.write_destination(self.CASES[0])
        self.write_record()
        self.document = self.diff()
        self.by_case = {case["case_no"]: case for case in self.document["cases"]}

    def test_the_missing_case_is_marked_and_the_present_one_is_not(self):
        self.assertTrue(self.by_case[self.CASES[1]]["new_no_ruling"])
        self.assertFalse(self.by_case[self.CASES[0]]["new_no_ruling"])

    def test_the_missing_case_counts_as_newly_missing(self):
        self.assertIs(False, self.by_case[self.CASES[1]]["new_exact"])
        self.assertIs(True, self.by_case[self.CASES[0]]["new_exact"])
        self.assertEqual(1, self.document["totals"]["newly_missing"])

    def test_the_rendered_row_says_no_ruling(self):
        rendered = gaps.render_diff(self.document)
        rows = [line for line in rendered.splitlines() if line.startswith("| `{0}`".format(self.CASES[1]))]
        self.assertEqual(1, len(rows))
        self.assertIn("no ruling", rows[0])


class VersionTwoNoteTests(DiffTreeCase):
    """A version-2 diff says that version 2 carries the amendment and part B."""

    def setUp(self):
        super().setUp()
        for case_no in self.CASES:
            self.write_destination(case_no)
        self.write_record()
        self.document = self.diff()

    def test_the_document_carries_the_note(self):
        self.assertEqual(2, self.document["policy_version"])
        self.assertEqual(gaps.VERSION_TWO_NOTE, self.document["version_note"])

    def test_the_note_says_the_gains_are_not_the_amendment_s_alone(self):
        note = self.document["version_note"]
        self.assertIn("part B", note)
        self.assertIn("POL-RD-11", note)
        self.assertIn("cannot be attributed to the amendment alone", note)
        self.assertIn(note, gaps.render_diff(self.document))


# --------------------------------------------------------------------------
# A no-show brief at version 2
# --------------------------------------------------------------------------
class NoShowBriefAtVersionTwoTests(unittest.TestCase):
    """A POL-RD amendment does not reach a no-show brief.

    ``loader.load_policies`` takes no root, so the amendments directory is
    patched for the length of the test; the repository's own
    ``policy/amendments/`` is never written to.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        directory = Path(self._tmp.name) / "amendments"
        directory.mkdir(parents=True)
        clause = route_clause()
        document = {
            "base_version": policy_versions.BASE_VERSION,
            "proposal_file": "policy/proposals/0001-proposal.json",
            "proposal_sha256": "0" * 64,
            "report_file": "runs/policy-gaps/report.json",
            "report_sha256": "0" * 64,
            "cluster_id": "C1",
            "cases": [NO_SHOW_CASE],
            "approved_by": "reviewer",
            "approved_at": FIXED_NOW,
            "clause": clause,
        }
        (directory / "0001-{0}.json".format(gaps.slug_for(clause["id"]))).write_text(
            json.dumps(document) + "\n", encoding="utf-8"
        )
        original = policy_versions.amendments_dir

        def redirect(root=None):
            return directory if root is None else original(root)

        patcher = mock.patch.object(policy_versions, "amendments_dir", redirect)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_case_really_is_a_no_show_case(self):
        self.assertEqual("NO_SHOW_CHARGE", loop_rig.CATEGORY_OF[NO_SHOW_CASE])

    def test_the_brief_is_byte_identical_at_version_two(self):
        self.assertEqual(2, policy_versions.current_version())
        case = loader.load_case(NO_SHOW_CASE)
        one = brief.brief_digest(brief.build_brief_for_case(case))[1]
        two = brief.brief_digest(brief.build_brief_for_case(case, policy_version=2))[1]
        self.assertEqual(one, two)


if __name__ == "__main__":
    unittest.main()
