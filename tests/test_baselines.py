"""The baselines: what they are computed from, and that they call nothing.

Every figure the baselines publish comes off a recorded run, so the fixture is a
real cached run produced by the same runner the corpus goes through, over a
scripted transport. Nothing here reaches a model: the transport answers from the
answer key, and the test that matters most for safety drives
:func:`eval.baselines.main` with ``tribunal.llm.LLMClient`` patched to raise, so
a module that built a client would fail there rather than spend the owner's
balance.

The rows are also tested directly, on hand-built sections, because the row
arithmetic is what a reader compares figures with and it should not need a run
to be checked.
"""

from __future__ import annotations

import ast
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import baselines, development_sets as sets, grade, run_benchmark  # noqa: E402
from tribunal import llm, money, pipeline, transcript  # noqa: E402

MODEL = "deepseek/deepseek-flash"
# The house fake credential, deliberately not ``sk-`` prefixed so that it never
# matches the credential scan this repository runs over new files.
FAKE_KEY = "tok-live-FAKEKEY-0123456789abcdef-DO-NOT-LEAK"
PROMPTS_DIR = run_benchmark.PROMPTS_DIR

PROMPT_TOKENS = 120
COMPLETION_TOKENS = 30
CLAIM_ARRAY = '[{"claim_id": "C1", "evidence_id": "E1", "clause_id": "POL-GEN-03"}]'

RIDER_STANCE = (PROMPTS_DIR / "stance.rider.md").read_text(encoding="utf-8").rstrip("\n")
DRIVER_STANCE = (PROMPTS_DIR / "stance.driver.md").read_text(encoding="utf-8").rstrip("\n")

# The corpus cases the integration fixture runs. Three of them require
# PARTIAL_REFUND and two require ESCALATE, so the modal ruling is not the same
# answer as always ESCALATE and the two rows can be told apart.
FIXTURE_CASES = (101, 102, 103, 104, 110)
# The same, for the second development set.
SECOND_FIXTURE_CASES = (9101, 9102, 9103)


class VirtualClock:
    """A clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.now = 0.0

    def clock(self) -> float:
        with self._lock:
            return self.now

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.now += seconds


def role_of(request):
    """``(case_no, role)`` for one recorded request body."""
    system = request["messages"][0]["content"]
    parsed = json.loads(request["messages"][1]["content"])

    if isinstance(parsed, dict) and "brief" in parsed and "claims" in parsed:
        return parsed["brief"]["case"]["case_no"], transcript.ROLE_JUDGE

    case_no = parsed["case"]["case_no"]
    if RIDER_STANCE in system:
        return case_no, transcript.ROLE_RIDER_ADVOCATE
    if DRIVER_STANCE in system:
        return case_no, transcript.ROLE_DRIVER_ADVOCATE
    raise AssertionError("a request is neither an advocate's nor the judge's")


class ScriptedTransport:
    """Answers by role from a produced mapping.

    ``wrong`` maps a seed to the case numbers that draft answers with a bare
    ESCALATE instead of the key's answer, which is how a fixture gets a panel
    whose drafts disagree with each other without a second run.
    """

    def __init__(self, produced, wrong=None) -> None:
        self.produced = produced
        self.wrong = {} if wrong is None else dict(wrong)
        self.requests = []
        self._lock = threading.Lock()

    def __call__(self, url, headers, body, timeout):
        request = json.loads(body.decode("utf-8"))
        case_no, role = role_of(request)
        with self._lock:
            self.requests.append(request)

        if role == transcript.ROLE_JUDGE:
            ruling = dict(self.produced[case_no]["ruling"])
            if case_no in self.wrong.get(request.get("seed"), ()):
                ruling = {
                    "ruling": grade.ESCALATE,
                    "amount_sgd": None,
                    "driver_compensation_sgd": None,
                    "referrals": [],
                }
            content = money.dumps_canonical({"ruling": ruling, "discarded_claims": []})
        else:
            content = CLAIM_ARRAY

        payload = {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": PROMPT_TOKENS,
                "completion_tokens": COMPLETION_TOKENS,
                "completion_tokens_details": {"reasoning_tokens": 8},
                "prompt_tokens_details": {"cached_tokens": 0},
            },
        }
        return llm.HttpResult(status=200, body=json.dumps(payload).encode("utf-8"))

    def calls(self) -> int:
        return len(self.requests)


def client_factory(transport):
    """A real ``LLMClient`` over the scripted transport, with no real sleeping."""
    clock = VirtualClock()

    def build(sink):
        return llm.LLMClient(
            model=MODEL,
            api_key=FAKE_KEY,
            transport=transport,
            record_sink=sink,
            max_attempts=1,
            clock=clock.clock,
            sleep=clock.sleep,
        )

    return build


def git_runner(commit="0b20a66deadbeefcafe0123456789abcdef01234"):
    return lambda arguments: commit if arguments[0] == "rev-parse" else ""


def run_corpus(
    tmp_path, *, cases=FIXTURE_CASES, judge_votes=4, transport=None, runs_dir=None
):
    """One invocation of the set runner over the corpus, on the scripted transport."""
    if transport is None:
        transport = ScriptedTransport(grade.key_as_produced(sets.CORPUS.key()))
    arguments = dict(
        runs_dir=Path(runs_dir) if runs_dir is not None else Path(tmp_path) / "runs",
        client_factory=client_factory(transport),
        git_runner=git_runner(),
        progress=lambda text: None,
        judge_votes=judge_votes,
        cases=list(cases),
    )
    return sets.run_set(sets.CORPUS, MODEL, **arguments), transport


def run_second_set(
    tmp_path, *, cases=SECOND_FIXTURE_CASES, judge_votes=4, transport=None, runs_dir=None
):
    """The same, for the second development set."""
    if transport is None:
        transport = ScriptedTransport(grade.key_as_produced(sets.SECOND_SET.key()))
    arguments = dict(
        runs_dir=Path(runs_dir) if runs_dir is not None else Path(tmp_path) / "runs",
        client_factory=client_factory(transport),
        git_runner=git_runner(),
        progress=lambda text: None,
        judge_votes=judge_votes,
        cases=list(cases),
    )
    return sets.run_set(sets.SECOND_SET, MODEL, **arguments), transport


# The two headline run directories: the corpus result the submission reports and
# the second development set's. A refusal must leave every byte of both alone.
HEADLINE_DIRS = (
    run_benchmark.RUNS_DIR / "deepseek-deepseek-flash",
    run_benchmark.RUNS_DIR / "codex" / "deepseek-deepseek-flash",
)


def headline_digests():
    """The sha256 of every file under both headline directories."""
    digests = {}
    for directory in HEADLINE_DIRS:
        for path in sorted(Path(directory).rglob("*")):
            if path.is_file():
                digests[str(path)] = run_benchmark.file_sha256(path)
    return digests


def quiet(argv) -> int:
    """``baselines.main`` with its report of what it wrote suppressed.

    Both streams, so a refusal test's own ``FATAL:`` line does not sit in the
    log of a passing run looking like a failure. The return code is what a test
    asserts on.
    """
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return baselines.main(argv)


# --------------------------------------------------------------------------
# Hand-built sections, for the row arithmetic
# --------------------------------------------------------------------------
def a_ruling(case_no, ruling, *, amount=None, referrals=()):
    """One expected ruling, with only the money a test needs."""
    return grade.Ruling(
        case_no=case_no,
        ruling=ruling,
        amount_sgd=amount,
        driver_compensation_sgd=None,
        referrals=tuple(referrals),
    )


def a_draft(seed, ruling, *, amount=None, valid=True, kind=pipeline.DRAFT_SAMPLED):
    """One judge draft, as ``recorded_judge_drafts`` would rebuild it."""
    inner = {
        "ruling": ruling,
        "amount_sgd": amount,
        "driver_compensation_sgd": None,
        "referrals": [],
    }
    result = {"ruling": inner, "discarded_claims": []}
    return pipeline.JudgeDraft(
        index=1,
        kind=kind,
        temperature=0.7,
        seed=seed,
        sides=tuple(pipeline.DRIVER_FIRST),
        entries=(0,),
        ruling=result if valid else None,
        key=pipeline.vote_key(result) if valid else None,
    )


def a_section(
    name="corpus",
    *,
    key: Mapping[int, Any],
    drafts: Optional[Mapping[int, Sequence[Any]]] = None,
    carried: Optional[Mapping[int, Any]] = None,
    analysed: Optional[Sequence[int]] = None,
    expected: Optional[int] = None,
) -> baselines.Section:
    """One section, built by hand, with only the cases a test names analysed.

    A key entry is either a ruling name, which is read with no money and no
    referrals, or a :class:`eval.grade.Ruling` for a test that needs one.
    """
    rulings = {
        case_no: value if isinstance(value, grade.Ruling) else a_ruling(case_no, value)
        for case_no, value in key.items()
    }
    return baselines.Section(
        name=name,
        run_dir=Path("/nowhere") / name,
        key=rulings,
        expected=len(rulings) if expected is None else expected,
        analysed=tuple(sorted(rulings)) if analysed is None else tuple(analysed),
        drafts={case_no: tuple(items) for case_no, items in (drafts or {}).items()},
        carried=dict(carried or {}),
    )


def rows_by_key(section: baselines.Section) -> Dict[str, baselines.Row]:
    return {row.key: row for row in baselines.rows_for(section)}


# --------------------------------------------------------------------------
# No model call
# --------------------------------------------------------------------------
class NoModelCallTests(unittest.TestCase):
    """The baselines read what a run recorded. They never ask a model anything."""

    def test_main_runs_with_the_client_patched_to_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs)
            out = Path(tmp) / "out"
            with mock.patch.object(
                llm, "LLMClient", side_effect=AssertionError("a model was called")
            ):
                code = quiet(
                    [
                        "--model",
                        MODEL,
                        "--set",
                        "all",
                        "--runs-dir",
                        str(runs),
                        "--out-dir",
                        str(out),
                    ]
                )
            self.assertEqual(0, code)
            self.assertTrue((out / baselines.REPORT_FILE).is_file())
            self.assertTrue((out / baselines.DATA_FILE).is_file())

    def test_the_module_never_names_a_client_or_a_live_measurement(self):
        """Parsed, not grepped: the names the module actually binds and reads."""
        source = (PROJECT_ROOT / "eval" / "baselines.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        named = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                named.add(node.id)
            elif isinstance(node, ast.Attribute):
                named.add(node.attr)
            elif isinstance(node, ast.alias):
                named.add(node.name.split(".")[-1])
                if node.asname:
                    named.add(node.asname)
        for forbidden in (
            "verify_recorded_case",
            "verify_recorded_run",
            "_default_client_factory",
            "LLMClient",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, named)

    def test_the_module_builds_drafts_only_through_the_recorded_reconstruction(self):
        source = (PROJECT_ROOT / "eval" / "baselines.py").read_text(encoding="utf-8")
        named = {
            node.attr
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Attribute)
        }
        self.assertIn("recorded_drafts_for_case", named)
        self.assertIn("recorded_judge_drafts", named)

    def test_the_data_document_says_no_model_call_was_made(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs)
            out = Path(tmp) / "out"
            quiet(
                [
                    "--model",
                    MODEL,
                    "--set",
                    "corpus",
                    "--runs-dir",
                    str(runs),
                    "--out-dir",
                    str(out),
                ]
            )
            data = json.loads((out / baselines.DATA_FILE).read_text(encoding="utf-8"))
            self.assertIn("No model call was made", data["note"])


# --------------------------------------------------------------------------
# Where the output may go
# --------------------------------------------------------------------------
class DestinationTests(unittest.TestCase):
    """A headline run directory is refused in code, not by convention."""

    def test_the_default_destination_is_the_baselines_directory(self):
        runs = Path("/tmp") / "somewhere" / "runs"
        self.assertEqual(
            runs / baselines.BASELINES_DIRNAME, baselines.baselines_directory(runs)
        )

    def test_a_run_directory_is_refused_and_the_baselines_directory_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            own = run_benchmark.run_directory(runs, MODEL)
            own.mkdir(parents=True)
            (own / run_benchmark.METADATA_FILE).write_text("{}", encoding="utf-8")
            with self.assertRaises(baselines.BaselineError):
                baselines.assert_not_a_run_directory(own, runs, MODEL)

            clean = baselines.baselines_directory(runs)
            self.assertEqual(
                clean.resolve(), baselines.assert_not_a_run_directory(clean, runs, MODEL)
            )

    def test_another_models_run_directory_is_refused_by_what_it_holds(self):
        """Not a name list: a directory with a run's own files is a run directory."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            other = run_benchmark.run_directory(runs, "someone/other-model")
            other.mkdir(parents=True)
            (other / "case-00001.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(baselines.BaselineError):
                baselines.assert_not_a_run_directory(other, runs, MODEL)
            # And a destination inside one, which would land these figures
            # beside that run's own.
            with self.assertRaises(baselines.BaselineError):
                baselines.assert_not_a_run_directory(other / "baselines", runs, MODEL)

    def test_a_destination_under_the_external_runs_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            external = runs / run_benchmark.EXTERNAL_RUNS_SUBDIR / "ryde"
            with self.assertRaises(baselines.BaselineError):
                baselines.assert_not_a_run_directory(external, runs, MODEL)

    def test_a_scratch_runs_root_does_not_make_another_root_safe(self):
        """``--runs-dir`` and ``--out-dir`` are separate arguments.

        Pointing the runs root at a scratch directory used to be enough to write
        into a headline directory under the repository's own ``runs/``: the
        guard asked only about the root it was given, and a destination that
        resolved under the other one was accepted. Both roots are walked now.
        The second root here is a temporary one rather than the repository's, so
        the guard is shown to be about the *other* root and nothing in this test
        reads or writes the committed run.
        """
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            repository = Path(tmp) / "repository-runs"
            headline = run_benchmark.run_directory(repository, MODEL)
            headline.mkdir(parents=True)
            (headline / run_benchmark.METADATA_FILE).write_text("{}", encoding="utf-8")

            with mock.patch.object(baselines, "RUNS_DIR", repository):
                # The headline directory itself, refused by name.
                with self.assertRaises(baselines.BaselineError):
                    baselines.assert_not_a_run_directory(headline, scratch, MODEL)
                # And a destination inside it, refused by what that directory
                # holds -- which is the structural half of the same guard.
                with self.assertRaises(baselines.BaselineError):
                    baselines.assert_not_a_run_directory(
                        headline / "baselines", scratch, MODEL
                    )
                # The scratch root's own baselines directory is still fine, so
                # the refusal is about the other root and not about the argument.
                clean = baselines.baselines_directory(scratch)
                self.assertEqual(
                    clean.resolve(),
                    baselines.assert_not_a_run_directory(clean, scratch, MODEL),
                )

    def test_a_refused_run_writes_nothing_and_leaves_the_headline_dirs_alone(self):
        before = headline_digests()
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            dirty = run_benchmark.run_directory(runs, MODEL)
            dirty.mkdir(parents=True)
            code = quiet(
                [
                    "--model",
                    MODEL,
                    "--set",
                    "all",
                    "--runs-dir",
                    str(runs),
                    "--out-dir",
                    str(dirty),
                ]
            )
            self.assertEqual(1, code)
            self.assertEqual([], sorted(path.name for path in dirty.iterdir()))
        self.assertEqual(before, headline_digests())

    def test_an_unknown_set_name_is_refused_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            out = Path(tmp) / "out"
            code = quiet(
                [
                    "--model",
                    MODEL,
                    "--set",
                    "no-such-set",
                    "--runs-dir",
                    str(runs),
                    "--out-dir",
                    str(out),
                ]
            )
            self.assertEqual(1, code)
            self.assertFalse(out.exists())


# --------------------------------------------------------------------------
# Refused cases
# --------------------------------------------------------------------------
class RefusalTests(unittest.TestCase):
    """A case that cannot be scored is refused with its reason, not counted as a miss."""

    def test_a_case_with_no_vote_block_is_refused_with_its_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs, judge_votes=1)
            section = baselines.build_section(sets.CORPUS, MODEL, runs)
            self.assertEqual(0, section.produced)
            self.assertEqual(29, section.expected)
            self.assertEqual(sorted(FIXTURE_CASES), sorted(n for n, _ in section.refusals))
            for case_no, reason in section.refusals:
                with self.subTest(case_no=case_no):
                    self.assertIn("asked the judge once", reason)

    def test_a_refused_case_is_left_out_of_every_figure(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs, judge_votes=1)
            section = baselines.build_section(sets.CORPUS, MODEL, runs)
            for key, row in rows_by_key(section).items():
                with self.subTest(row=key):
                    self.assertEqual(0, row.total)
                    self.assertEqual("-", row.cell("exact"))

    def test_a_stale_case_is_refused_with_the_channel_that_moved(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs)
            moved = Path(tmp) / "prompts"
            shutil.copytree(PROMPTS_DIR, moved)
            target = moved / "judge.system.md"
            target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            section = baselines.build_section(sets.CORPUS, MODEL, runs, moved)
            self.assertEqual(0, section.produced)
            self.assertEqual(sorted(FIXTURE_CASES), sorted(n for n, _ in section.refusals))
            for case_no, reason in section.refusals:
                with self.subTest(case_no=case_no):
                    self.assertTrue(reason.startswith("stale:"))
                    self.assertIn(grade.MOVED_PROMPTS, reason)

    def test_a_case_that_was_never_run_is_not_refused_it_is_simply_absent(self):
        """There is no result to refuse. The set reads 0 of 29, not 29 misses."""
        with tempfile.TemporaryDirectory() as tmp:
            section = baselines.build_section(sets.CORPUS, MODEL, Path(tmp) / "runs")
            self.assertEqual(0, section.produced)
            self.assertEqual(29, section.expected)
            self.assertEqual((), section.refusals)

    def test_every_refused_case_is_listed_with_its_reason_in_the_report_and_the_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs, judge_votes=1)
            out = Path(tmp) / "out"
            self.assertEqual(
                0,
                quiet(
                    [
                        "--model",
                        MODEL,
                        "--set",
                        "corpus",
                        "--runs-dir",
                        str(runs),
                        "--out-dir",
                        str(out),
                    ]
                ),
            )
            data = json.loads((out / baselines.DATA_FILE).read_text(encoding="utf-8"))
            refused = [
                (item["case_no"], item["reason"])
                for item in data["sections"][0]["refused"]
            ]
            self.assertEqual(sorted(FIXTURE_CASES), sorted(n for n, _ in refused))
            for case_no, reason in refused:
                with self.subTest(case_no=case_no):
                    self.assertTrue(reason)
            text = (out / baselines.REPORT_FILE).read_text(encoding="utf-8")
            self.assertIn("Refused cases, and why:", text)
            for case_no, _ in refused:
                with self.subTest(case_no=case_no):
                    self.assertIn("`{0}`".format(case_no), text)


# --------------------------------------------------------------------------
# The rows
# --------------------------------------------------------------------------
class AlwaysEscalateTests(unittest.TestCase):
    def test_it_answers_null_amounts_and_no_referrals_on_every_case(self):
        section = a_section(key={101: "PARTIAL_REFUND", 110: "ESCALATE"})
        row = rows_by_key(section)["always_escalate"]
        # Only the case that is an escalation with no referrals is right.
        self.assertEqual("1/2", row.cell("exact"))
        self.assertEqual("1/2", row.cell("ruling"))

    def test_a_case_that_escalates_with_a_referral_is_not_an_exact_match(self):
        section = a_section(
            key={
                207: a_ruling(
                    207,
                    "ESCALATE",
                    referrals=("POL-RD-06(c) driver-conduct review",),
                )
            }
        )
        row = rows_by_key(section)["always_escalate"]
        self.assertEqual("0/1", row.cell("exact"))
        self.assertEqual("1/1", row.cell("ruling"))


class MajorityRulingTests(unittest.TestCase):
    def test_the_majority_ruling_is_the_most_frequent_expected_ruling(self):
        section = a_section(
            key={
                101: a_ruling(101, "PARTIAL_REFUND", amount=Decimal("8.05")),
                103: a_ruling(103, "PARTIAL_REFUND", amount=Decimal("4.00")),
                110: "ESCALATE",
            }
        )
        self.assertEqual("PARTIAL_REFUND", baselines.majority_ruling(section))
        row = rows_by_key(section)["majority_ruling"]
        self.assertEqual("2/3", row.cell("ruling"))
        # The row publishes null amounts, so a case that requires money cannot
        # be an exact match however often its ruling is the modal one.
        self.assertEqual("0/3", row.cell("exact"))

    def test_a_tie_goes_to_the_ruling_that_sorts_first(self):
        section = a_section(key={101: "PARTIAL_REFUND", 110: "ESCALATE"})
        self.assertEqual("ESCALATE", baselines.majority_ruling(section))

    def test_a_section_with_nothing_analysed_falls_back_to_escalate(self):
        section = a_section(key={101: "PARTIAL_REFUND"}, analysed=())
        self.assertEqual(grade.ESCALATE, baselines.majority_ruling(section))


class SingleDraftTests(unittest.TestCase):
    """Each draft scored alone, with an abstention counted as a miss."""

    def section(self):
        return a_section(
            key={101: "ESCALATE", 102: "NO_ACTION"},
            drafts={
                101: (
                    a_draft(101, "ESCALATE"),
                    a_draft(202, "NO_ACTION"),
                    a_draft(303, "ESCALATE", valid=False),
                    a_draft(42, "ESCALATE", kind=pipeline.DRAFT_POSITION_SWAPPED),
                ),
                102: (
                    a_draft(101, "ESCALATE"),
                    a_draft(202, "NO_ACTION"),
                    a_draft(303, "NO_ACTION", valid=False),
                    a_draft(42, "ESCALATE", kind=pipeline.DRAFT_POSITION_SWAPPED),
                ),
            },
        )

    def test_each_single_draft_row_scores_that_draft_alone(self):
        rows = rows_by_key(self.section())
        self.assertEqual("1/2", rows["single_draft:seed 101"].cell("exact"))
        self.assertEqual("1/2", rows["single_draft:seed 202"].cell("exact"))
        self.assertEqual("0/2", rows["single_draft:seed 303"].cell("exact"))
        self.assertEqual("1/2", rows["single_draft:position-swapped"].cell("exact"))

    def test_an_abstained_draft_counts_as_a_miss(self):
        """Seed 303 abstains on both cases, so neither is scored as an answer."""
        rows = rows_by_key(self.section())
        self.assertEqual("0/2", rows["single_draft:seed 303"].cell("exact"))
        self.assertEqual("0/2", rows["single_draft:seed 303"].cell("ruling"))

    def test_the_mean_is_the_mean_of_the_four_single_draft_rows(self):
        rows = rows_by_key(self.section())
        singles = [
            rows["single_draft:seed 101"],
            rows["single_draft:seed 202"],
            rows["single_draft:seed 303"],
            rows["single_draft:position-swapped"],
        ]
        mean = rows["single_draft:mean"]
        self.assertEqual("0.75/2", mean.cell("exact"))
        for name in grade.GRADED_FIELDS:
            with self.subTest(field=name):
                counted = [row.report.field_tally(name)[0] for row in singles]
                self.assertEqual(sum(counted) / 4, float(mean.means[name]))

    def test_a_section_with_nothing_analysed_has_no_mean_row(self):
        section = a_section(key={101: "ESCALATE"}, analysed=())
        self.assertNotIn("single_draft:mean", rows_by_key(section))


class UpperBoundTests(unittest.TestCase):
    """At least one draft right is a ceiling for every row that publishes a draft."""

    def section(self):
        return a_section(
            key={101: "ESCALATE", 102: "NO_ACTION"},
            drafts={
                101: (
                    a_draft(101, "ESCALATE"),
                    a_draft(202, "NO_ACTION"),
                    a_draft(303, "ESCALATE", valid=False),
                    a_draft(42, "NO_ACTION", kind=pipeline.DRAFT_POSITION_SWAPPED),
                ),
                102: (
                    a_draft(101, "ESCALATE"),
                    a_draft(202, "NO_ACTION"),
                    a_draft(303, "ESCALATE"),
                    a_draft(42, "NO_ACTION", kind=pipeline.DRAFT_POSITION_SWAPPED),
                ),
            },
        )

    def test_it_is_never_below_the_best_single_draft(self):
        rows = rows_by_key(self.section())
        upper = rows["at_least_one_draft_right"]
        for key, row in rows.items():
            if not key.startswith("single_draft:") or key.endswith(":mean"):
                continue
            with self.subTest(row=key):
                self.assertGreaterEqual(
                    upper.report.exact_matches, row.report.exact_matches
                )
                self.assertGreaterEqual(
                    upper.report.field_tally("ruling")[0],
                    row.report.field_tally("ruling")[0],
                )

    def test_it_gets_both_cases_right_where_no_single_draft_gets_more_than_one(self):
        rows = rows_by_key(self.section())
        for key, expected in (
            ("single_draft:seed 101", "1/2"),
            ("single_draft:seed 202", "1/2"),
            ("single_draft:seed 303", "0/2"),
            ("single_draft:position-swapped", "1/2"),
        ):
            with self.subTest(row=key):
                self.assertEqual(expected, rows[key].cell("exact"))
        self.assertEqual("2/2", rows["at_least_one_draft_right"].cell("exact"))

    def test_it_carries_the_stated_label(self):
        rows = rows_by_key(self.section())
        self.assertEqual(
            baselines.AT_LEAST_ONE_LABEL, rows["at_least_one_draft_right"].note
        )
        self.assertEqual(
            "an upper bound for any rule that publishes one of the drafts' "
            "answers; a no-majority escalation can exceed it",
            baselines.AT_LEAST_ONE_LABEL,
        )


class CarriedVoteTests(unittest.TestCase):
    def test_the_carried_vote_scores_what_the_run_published(self):
        def published(ruling):
            return {
                "ruling": {
                    "ruling": ruling,
                    "amount_sgd": None,
                    "driver_compensation_sgd": None,
                    "referrals": [],
                },
                "discarded_claims": [],
            }

        section = a_section(
            key={101: "ESCALATE", 102: "NO_ACTION"},
            carried={101: published("ESCALATE"), 102: published("ESCALATE")},
        )
        row = rows_by_key(section)["carried_vote"]
        self.assertEqual("1/2", row.cell("exact"))
        self.assertEqual("1/2", row.cell("ruling"))

    def test_a_case_with_no_published_ruling_is_a_miss(self):
        section = a_section(key={101: "ESCALATE"}, carried={101: None})
        self.assertEqual("0/1", rows_by_key(section)["carried_vote"].cell("exact"))


class RowShapeTests(unittest.TestCase):
    def test_every_row_is_present_and_keyed_by_a_stable_name(self):
        section = a_section(
            key={101: "ESCALATE"},
            drafts={101: (a_draft(101, "ESCALATE"),)},
            carried={101: None},
        )
        self.assertEqual(
            [
                "always_escalate",
                "majority_ruling",
                "single_draft:seed 101",
                "single_draft:seed 202",
                "single_draft:seed 303",
                "single_draft:position-swapped",
                "single_draft:mean",
                "at_least_one_draft_right",
                "carried_vote",
            ],
            [row.key for row in baselines.rows_for(section)],
        )

    def test_a_row_that_was_measured_over_no_case_renders_a_dash_not_a_zero(self):
        section = a_section(key={101: "ESCALATE"}, analysed=())
        for row in baselines.rows_for(section):
            with self.subTest(row=row.key):
                self.assertEqual("-", row.cell("exact"))
                self.assertEqual("-", row.cell("ruling"))

    def test_the_data_document_keeps_every_count_it_rendered(self):
        section = a_section(key={101: "ESCALATE", 110: "ESCALATE"})
        row = rows_by_key(section)["always_escalate"].as_dict()
        self.assertEqual("always_escalate", row["row"])
        self.assertEqual(2, row["cases"])
        self.assertEqual(2, row["exact"])
        self.assertEqual(
            {
                "ruling": 2,
                "amount_sgd": 2,
                "driver_compensation_sgd": 2,
                "referrals": 2,
            },
            row["fields"],
        )
        self.assertIsNone(row["means"])


# --------------------------------------------------------------------------
# Sections and the combined section
# --------------------------------------------------------------------------
class SectionTests(unittest.TestCase):
    def test_the_combined_section_is_the_union_of_the_sets(self):
        one = a_section("corpus", key={101: "ESCALATE"}, expected=29)
        two = a_section("codex", key={9101: "NO_ACTION"}, expected=15)
        combined = baselines.combine_sections([one, two], MODEL, Path("/nowhere"))
        self.assertEqual("combined", combined.name)
        self.assertEqual((101, 9101), combined.analysed)
        self.assertEqual(44, combined.expected)

    def test_a_case_is_in_exactly_one_sets_key_so_the_merge_never_double_counts(self):
        corpus = sets.CORPUS.key()
        codex = sets.SECOND_SET.key()
        self.assertEqual(set(), set(corpus) & set(codex))
        self.assertEqual(29, len(corpus))
        self.assertEqual(15, len(codex))


class RecordedRunTests(unittest.TestCase):
    """The integration path: a real cached run, rebuilt into a section."""

    def test_a_section_holds_the_four_drafts_the_vote_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs)
            section = baselines.build_section(sets.CORPUS, MODEL, runs)
            self.assertEqual(29, section.expected)
            self.assertEqual(FIXTURE_CASES, section.analysed)
            self.assertEqual((), section.refusals)
            for case_no in FIXTURE_CASES:
                with self.subTest(case_no=case_no):
                    drafts = section.drafts[case_no]
                    self.assertEqual(4, len(drafts))
                    self.assertEqual(
                        {101, 202, 303},
                        {
                            draft.seed
                            for draft in drafts
                            if draft.kind == pipeline.DRAFT_SAMPLED
                        },
                    )
                    self.assertEqual(
                        1,
                        len(
                            [
                                draft
                                for draft in drafts
                                if draft.kind == pipeline.DRAFT_POSITION_SWAPPED
                            ]
                        ),
                    )
                    self.assertTrue(all(draft.valid for draft in drafts))

    def test_a_panel_that_answers_the_key_scores_every_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs)
            section = baselines.build_section(sets.CORPUS, MODEL, runs)
            rows = rows_by_key(section)
            for key in (
                "single_draft:seed 101",
                "single_draft:seed 202",
                "single_draft:seed 303",
                "single_draft:position-swapped",
                "at_least_one_draft_right",
                "carried_vote",
            ):
                with self.subTest(row=key):
                    self.assertEqual("5/5", rows[key].cell("exact"))
            self.assertEqual("5.00/5", rows["single_draft:mean"].cell("exact"))
            # The two constant rules are told apart: the section's modal ruling
            # is PARTIAL_REFUND, which is not what always-ESCALATE answers.
            self.assertEqual(
                "Majority ruling: PARTIAL_REFUND", rows["majority_ruling"].label
            )
            self.assertEqual("3/5", rows["majority_ruling"].cell("ruling"))
            self.assertEqual("1/5", rows["always_escalate"].cell("exact"))

    def test_a_draft_that_answers_wrongly_under_one_seed_is_that_rows_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            transport = ScriptedTransport(
                grade.key_as_produced(sets.CORPUS.key()), wrong={202: {101}}
            )
            run_corpus(tmp, runs_dir=runs, transport=transport)
            section = baselines.build_section(sets.CORPUS, MODEL, runs)
            rows = rows_by_key(section)
            self.assertEqual("4/5", rows["single_draft:seed 202"].cell("exact"))
            self.assertEqual("5/5", rows["single_draft:seed 101"].cell("exact"))
            self.assertEqual("4.75/5", rows["single_draft:mean"].cell("exact"))
            # The panel still carries every case, because three drafts agreed.
            self.assertEqual("5/5", rows["carried_vote"].cell("exact"))

    def test_each_set_is_scored_against_its_own_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs)
            run_second_set(tmp, runs_dir=runs)
            corpus = baselines.build_section(sets.CORPUS, MODEL, runs)
            codex = baselines.build_section(sets.SECOND_SET, MODEL, runs)
            self.assertEqual(FIXTURE_CASES, corpus.analysed)
            self.assertEqual(SECOND_FIXTURE_CASES, codex.analysed)
            self.assertEqual(29, len(corpus.key))
            self.assertEqual(15, len(codex.key))
            self.assertEqual(set(), set(corpus.key) & set(codex.key))
            self.assertEqual(29, corpus.expected)
            self.assertEqual(15, codex.expected)

    def test_a_second_set_is_read_from_its_own_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_second_set(tmp, runs_dir=runs)
            self.assertEqual(
                runs / "codex" / run_benchmark.model_slug(MODEL),
                sets.SECOND_SET.run_dir(MODEL, runs),
            )
            self.assertFalse((runs / run_benchmark.model_slug(MODEL)).exists())


# --------------------------------------------------------------------------
# The two output files
# --------------------------------------------------------------------------
class OutputTests(unittest.TestCase):
    def test_the_report_carries_the_development_data_caveat(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs)
            out = Path(tmp) / "out"
            quiet(
                [
                    "--model",
                    MODEL,
                    "--set",
                    "corpus",
                    "--runs-dir",
                    str(runs),
                    "--out-dir",
                    str(out),
                ]
            )
            data = json.loads((out / baselines.DATA_FILE).read_text(encoding="utf-8"))
            self.assertEqual(sets.DEVELOPMENT_DATA_CAVEAT, data["caveat"])
            self.assertIn("the figure the submission reports", data["caveat"])
            self.assertIn("sealed set", data["caveat"])
            text = (out / baselines.REPORT_FILE).read_text(encoding="utf-8")
            self.assertIn(sets.DEVELOPMENT_DATA_CAVEAT, text)
            self.assertIn("No model call was made", text)

    def test_the_data_document_has_one_section_per_set_and_a_combined_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs)
            run_second_set(tmp, runs_dir=runs)
            out = Path(tmp) / "out"
            quiet(
                [
                    "--model",
                    MODEL,
                    "--set",
                    "all",
                    "--runs-dir",
                    str(runs),
                    "--out-dir",
                    str(out),
                ]
            )
            data = json.loads((out / baselines.DATA_FILE).read_text(encoding="utf-8"))
            self.assertEqual(
                ["corpus", "codex", "combined"], [s["name"] for s in data["sections"]]
            )
            self.assertEqual(["corpus", "codex", "combined"], data["sets"])
            combined = data["sections"][2]
            self.assertEqual(44, combined["expected"])
            self.assertEqual(
                len(FIXTURE_CASES) + len(SECOND_FIXTURE_CASES), combined["analysed"]
            )
            self.assertEqual(
                sorted(FIXTURE_CASES + SECOND_FIXTURE_CASES), combined["analysed_cases"]
            )

    def test_a_single_set_is_reported_without_a_combined_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs)
            out = Path(tmp) / "out"
            quiet(
                [
                    "--model",
                    MODEL,
                    "--set",
                    "corpus",
                    "--runs-dir",
                    str(runs),
                    "--out-dir",
                    str(out),
                ]
            )
            data = json.loads((out / baselines.DATA_FILE).read_text(encoding="utf-8"))
            self.assertEqual(["corpus"], data["sets"])

    def test_the_table_has_a_header_cell_for_every_column_it_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs)
            out = Path(tmp) / "out"
            quiet(
                [
                    "--model",
                    MODEL,
                    "--set",
                    "corpus",
                    "--runs-dir",
                    str(runs),
                    "--out-dir",
                    str(out),
                ]
            )
            lines = (
                (out / baselines.REPORT_FILE).read_text(encoding="utf-8").splitlines()
            )
            header = next(line for line in lines if line.startswith("| row |"))
            separator = lines[lines.index(header) + 1]
            row = lines[lines.index(header) + 2]
            self.assertEqual(len(header.split("|")), len(separator.split("|")))
            self.assertEqual(len(header.split("|")), len(row.split("|")))

    def test_the_output_goes_where_it_is_told_and_defaults_under_the_runs_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_corpus(tmp, runs_dir=runs)
            quiet(["--model", MODEL, "--set", "corpus", "--runs-dir", str(runs)])
            default = baselines.baselines_directory(runs)
            self.assertTrue((default / baselines.REPORT_FILE).is_file())
            self.assertTrue((default / baselines.DATA_FILE).is_file())


if __name__ == "__main__":
    unittest.main()
