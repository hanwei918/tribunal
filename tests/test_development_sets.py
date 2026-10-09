"""The second development set: loading it, running it, and reporting it.

The set is fifteen cases under ``data/external/codex/``, keyed separately from
the corpus. What is asserted here is that it goes through *the same* runner the
corpus goes through -- the same cache, provenance, deadlines, token budget and
advocate replay -- that its four fields are graded against its own key, and that
neither its cases nor its results can reach the corpus.

No model is called: the transport below answers from the key, as the corpus
runner's own tests do.

The last class is about the other thing a set's registration can fix besides
its cases: the policy version its briefs are built at. It runs a temporary
one-case set registered at version 2, over the same scripted transport.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import baselines, development_sets as sets  # noqa: E402
from eval import grade, run_benchmark  # noqa: E402
from tests import test_upfront_remedy as upfront_rig  # noqa: E402
from tribunal import llm, loader, money, policy_versions, transcript  # noqa: E402

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
    """Answers by role from a produced mapping, and records every request."""

    def __init__(self, produced, mutate=None) -> None:
        self.produced = produced
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


def codex_key():
    return sets.SECOND_SET.key()


def run_codex(tmp_path, *, cases=None, transport=None, runs_dir=None, **overrides):
    """One invocation of the set runner over the scripted transport."""
    key = codex_key()
    if transport is None:
        transport = ScriptedTransport(grade.key_as_produced(key))

    arguments = dict(
        runs_dir=Path(runs_dir) if runs_dir is not None else Path(tmp_path) / "runs",
        client_factory=client_factory(transport),
        git_runner=git_runner(),
        progress=lambda text: None,
        # One judge draft, so every test here measures the single-draft runner it
        # always measured. The vote has its own tests, which ask for it by name.
        judge_votes=1,
    )
    arguments.update(overrides)
    if cases is not None:
        arguments["cases"] = cases
    return sets.run_set(sets.SECOND_SET, MODEL, **arguments), transport


# The two headline run directories: the corpus result the submission reports
# and the second development set's. A refusal must leave every byte of both
# alone, so a refusal test reads them before and after.
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


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------
class SetRegistryTests(unittest.TestCase):
    """Two sets, two keys, two run directories, and no overlap between them."""

    def test_there_are_two_development_sets_and_they_are_the_expected_ones(self):
        self.assertEqual(["corpus", "codex"], [item.name for item in sets.DEVELOPMENT_SETS])
        self.assertEqual(29, len(sets.CORPUS.cases))
        self.assertEqual(15, len(sets.SECOND_SET.cases))
        self.assertEqual(list(range(9101, 9116)), list(sets.SECOND_SET.cases))

    def test_each_set_has_its_own_key_and_they_are_different_files(self):
        self.assertNotEqual(sets.CORPUS.key_path, sets.SECOND_SET.key_path)
        self.assertEqual(29, len(sets.CORPUS.key()))
        self.assertEqual(15, len(sets.SECOND_SET.key()))
        self.assertEqual(set(), set(sets.CORPUS.key()) & set(sets.SECOND_SET.key()))

    def test_the_second_set_is_not_in_the_corpus_manifest(self):
        """Adding it to data/index.json would change the 29-case corpus."""
        manifest = {entry["case_no"] for entry in loader._load_index()}
        self.assertEqual(set(), manifest & set(sets.SECOND_SET.cases))
        self.assertEqual(29, len(manifest))

    def test_the_two_sets_run_into_different_directories(self):
        corpus = sets.CORPUS.run_dir(MODEL)
        second = sets.SECOND_SET.run_dir(MODEL)
        self.assertNotEqual(corpus, second)
        self.assertEqual(run_benchmark.RUNS_DIR / "deepseek-deepseek-flash", corpus)
        self.assertEqual(run_benchmark.RUNS_DIR / "codex" / "deepseek-deepseek-flash", second)

    def test_the_corpus_set_is_the_only_one_that_may_use_the_runs_root(self):
        self.assertIsNone(sets.CORPUS.runs_subdir)
        self.assertEqual("codex", sets.SECOND_SET.runs_subdir)

    def test_an_unknown_set_name_raises_rather_than_defaulting(self):
        with self.assertRaises(run_benchmark.BenchmarkError):
            sets.named("no-such-set")


# --------------------------------------------------------------------------
# Loading the set
# --------------------------------------------------------------------------
class ExternalSetLoaderTests(unittest.TestCase):
    """The set is loaded by number through its own index, with every check."""

    def test_every_case_loads_and_its_number_agrees(self):
        for case_no in sets.SECOND_SET.cases:
            with self.subTest(case_no=case_no):
                case = loader.load_external_set_case(sets.SECOND_SET.case_root, case_no)
                self.assertEqual(case_no, case["case_no"])
                self.assertEqual(case_no, case["dispute"]["case_no"])

    def test_the_index_agrees_with_the_case_files_on_the_fields_it_repeats(self):
        for entry in loader.load_external_index(sets.SECOND_SET.case_root):
            with self.subTest(case_no=entry["case_no"]):
                case = loader.load_external_set_case(
                    sets.SECOND_SET.case_root, entry["case_no"]
                )
                for field in loader.MANIFEST_DISPUTE_FIELDS:
                    self.assertEqual(entry[field], case["dispute"][field])

    def test_a_case_the_set_does_not_list_is_refused(self):
        with self.assertRaises(loader.CaseNotFoundError):
            loader.load_external_set_case(sets.SECOND_SET.case_root, 101)

    def test_a_directory_outside_the_external_root_is_refused(self):
        for path in (PROJECT_ROOT / "data", PROJECT_ROOT / "data" / "cases", PROJECT_ROOT):
            with self.subTest(path=path):
                with self.assertRaises(loader.ManifestMismatchError):
                    loader.load_external_set_case(path, 9101)

    def test_the_external_root_itself_is_not_a_set(self):
        with self.assertRaises(loader.ManifestMismatchError):
            loader.external_set_directory(loader.EXTERNAL_DIR)

    def test_a_case_file_whose_bytes_do_not_match_the_recorded_digest_is_refused(self):
        """The index states a digest, so the index is held to it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codex"
            shutil.copytree(sets.SECOND_SET.case_root, root)
            target = root / "case-09101.json"
            target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaises(loader.ManifestMismatchError):
                loader.load_external_set_case(root, 9101)

    def test_a_case_file_named_for_another_number_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codex"
            shutil.copytree(sets.SECOND_SET.case_root, root)
            shutil.move(str(root / "case-09102.json"), str(root / "case-09103.json"))
            with self.assertRaises(loader.ManifestMismatchError):
                loader.load_external_set_case(root, 9103)

    def test_a_brief_can_be_built_for_every_case_of_the_set(self):
        for case_no in sets.SECOND_SET.cases:
            with self.subTest(case_no=case_no):
                case = sets.SECOND_SET.load_case(case_no)
                canonical, digest = loader.bundle_digest({"case": case})
                self.assertTrue(digest)
                self.assertIn('"case_no":{0}'.format(case_no), canonical)


# --------------------------------------------------------------------------
# Running the set through the corpus runner
# --------------------------------------------------------------------------
class SetRunTests(unittest.TestCase):
    """The same runner, the same cache, the same accounting."""

    def test_the_whole_set_runs_and_caches_every_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, transport = run_codex(tmp)

            self.assertEqual(run_benchmark.STOP_COMPLETED, summary.stop_reason)
            self.assertEqual(15, len(summary.outcomes))
            self.assertEqual(3 * 15, transport.calls())
            self.assertEqual(
                list(sets.SECOND_SET.cases),
                run_benchmark.cached_case_numbers(summary.run_dir),
            )

    def test_the_run_directory_is_the_sets_own_and_holds_no_corpus_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            summary, _ = run_codex(tmp, runs_dir=runs)
            self.assertEqual(
                runs / "codex" / "deepseek-deepseek-flash", Path(summary.run_dir)
            )
            self.assertFalse((runs / "deepseek-deepseek-flash").exists())

    def test_the_provenance_records_the_sets_key_and_not_the_corpus_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = run_codex(tmp)
            metadata = run_benchmark.read_json(
                run_benchmark.metadata_path(summary.run_dir)
            )
            self.assertEqual(
                grade.answer_key_sha256(sets.SECOND_SET.key_path),
                metadata["answer_key_sha256"],
            )
            self.assertNotEqual(grade.answer_key_sha256(), metadata["answer_key_sha256"])
            self.assertEqual("codex", metadata["development_set"])

    def test_every_cached_case_records_the_set_it_belongs_to(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = run_codex(tmp)
            for case_no in sets.SECOND_SET.cases:
                with self.subTest(case_no=case_no):
                    document = run_benchmark.load_cached(summary.run_dir, case_no)
                    self.assertEqual("codex", document.get("development_set"))

    def test_the_cached_results_are_current_against_the_set(self):
        """Staleness is rebuilt through the set's own loader, not the manifest."""
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = run_codex(tmp)
            staleness = summary.report.staleness
            self.assertTrue(staleness.checked)
            self.assertEqual((), staleness.stale)
            self.assertEqual((), staleness.unknown)
            self.assertFalse(staleness.mixed)

    def test_a_second_run_reuses_the_cache_and_makes_no_call(self):
        """``runs_dir`` is the runs *root*: the set appends its own subdirectory.

        Passing the set's own directory would make the second invocation look in
        ``runs/codex/codex/<model>/`` and miss every cached case, which is the
        difference between "the cache works" and "the cache was never asked".
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            first, _ = run_codex(tmp, runs_dir=root)
            self.assertEqual(0, sets.SECOND_SET.run_dir(MODEL, root) != first.run_dir)
            second_transport = ScriptedTransport(grade.key_as_produced(codex_key()))
            second, _ = run_codex(tmp, runs_dir=root, transport=second_transport)
            self.assertEqual(0, second_transport.calls())
            self.assertEqual(first.run_dir, second.run_dir)
            self.assertTrue(
                all(outcome.status == run_benchmark.STATUS_CACHED for outcome in second.outcomes)
            )

    def test_the_token_budget_stops_the_set_the_way_it_stops_the_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = run_codex(tmp, token_budget=1)
            self.assertEqual(run_benchmark.STOP_BUDGET, summary.stop_reason)
            self.assertLess(len(summary.outcomes), 15)
            self.assertGreaterEqual(len(summary.outcomes), 1)

    def test_the_case_deadline_applies_to_the_set_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = run_codex(tmp, case_deadline_seconds=1e-9)
            self.assertTrue(summary.outcomes)
            for outcome in summary.outcomes:
                self.assertEqual(run_benchmark.STATUS_FAILED, outcome.status)
                self.assertEqual(run_benchmark.FAILURE_DEADLINE, outcome.failure_kind)
            self.assertEqual([], run_benchmark.cached_case_numbers(summary.run_dir))

    def test_the_advocates_can_be_replayed_for_the_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            source, first_transport = run_codex(tmp, runs_dir=runs)
            self.assertEqual(45, first_transport.calls())

            replay_transport = ScriptedTransport(grade.key_as_produced(codex_key()))
            summary, _ = run_codex(
                tmp,
                runs_dir=runs / "replay",
                cases=[9101, 9102],
                transport=replay_transport,
                replay_dir=source.run_dir,
            )

            # Only the judge is called: one call per case, not three.
            self.assertEqual(2, replay_transport.calls())
            self.assertEqual([9101, 9102], summary.replayed_cases)
            # The borrowed advocates' tokens are reported and never charged.
            self.assertGreater(summary.tokens_replayed.billed, 0)
            self.assertEqual(2 * (PROMPT_TOKENS + COMPLETION_TOKENS), summary.tokens_charged.billed)

    def test_a_case_not_in_the_set_is_refused_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with self.assertRaises(run_benchmark.BenchmarkError):
                sets.run_set(
                    sets.SECOND_SET,
                    MODEL,
                    runs_dir=runs,
                    cases=[101],
                    client_factory=client_factory(ScriptedTransport({})),
                    progress=lambda text: None,
                )
            self.assertFalse((runs / "codex").exists())


# --------------------------------------------------------------------------
# Grading against the set's own key
# --------------------------------------------------------------------------
class SetGradingTests(unittest.TestCase):
    """All four fields, compared against the answers that belong to the cases."""

    def test_a_perfect_judge_scores_every_case_of_the_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = run_codex(tmp)
            self.assertEqual(15, summary.report.total)
            self.assertEqual(15, summary.report.exact_matches)
            for field in grade.GRADED_FIELDS:
                with self.subTest(field=field):
                    correct, total = summary.report.field_tally(field)
                    self.assertEqual((15, 15), (correct, total))

    def test_the_sets_own_key_is_what_a_wrong_ruling_fails_against(self):
        """The expected ruling for 9101 is read from the set's key, not the corpus's."""

        def flip(case_no, ruling):
            if case_no == 9101:
                ruling["ruling"] = "NO_ACTION"
                ruling["amount_sgd"] = None
            return ruling

        with tempfile.TemporaryDirectory() as tmp:
            key = codex_key()
            transport = ScriptedTransport(grade.key_as_produced(key), mutate=flip)
            summary, _ = run_codex(tmp, transport=transport)

            self.assertEqual(14, summary.report.exact_matches)
            failed = {score.case_no for score in summary.report.failures}
            self.assertEqual({9101}, failed)
            self.assertNotEqual("NO_ACTION", key[9101].ruling)

    def test_the_three_corrected_answers_are_the_ones_the_key_now_carries(self):
        """The corrections are in the key the run is graded against."""
        key = codex_key()
        self.assertEqual("PARTIAL_REFUND", key[9111].ruling)
        self.assertEqual(str(10.15), str(key[9111].amount_sgd))
        self.assertEqual("PARTIAL_REFUND", key[9113].ruling)
        self.assertEqual(str(9.05), str(key[9113].amount_sgd))
        self.assertEqual("FULL_REFUND", key[9114].ruling)
        self.assertEqual(str(3.2), str(key[9114].amount_sgd))


# --------------------------------------------------------------------------
# The corpus directory is protected
# --------------------------------------------------------------------------
class CorpusDirectoryGuardTests(unittest.TestCase):
    """A set's results must never land in the reported run directory."""

    def test_a_labelled_run_cannot_use_the_corpus_run_directory(self):
        """A set aimed at ``runs/<model>/`` is refused, and nothing is written.

        ``RUNS_DIR`` is patched to a scratch root and that same path is passed
        as ``runs_dir``, so the check is exercised without the repository's own
        ``runs/`` being any invocation's destination. Both headline directories
        are hashed before and after, so a refusal that quietly wrote something
        would be caught rather than assumed away.
        """
        before = headline_digests()
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with mock.patch.object(run_benchmark, "RUNS_DIR", runs):
                with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                    run_benchmark.run_benchmark(
                        MODEL,
                        [9101],
                        runs_dir=runs,
                        key=codex_key(),
                        key_path=sets.SECOND_SET.key_path,
                        case_loader=sets.SECOND_SET.load_case,
                        label="codex",
                        progress=lambda text: None,
                        client_factory=lambda sink: None,
                    )
            self.assertIn("corpus results", str(caught.exception))
            # Refused before the directory was created, so nothing was touched.
            self.assertFalse(runs.exists())
        self.assertEqual(before, headline_digests())

    def test_the_corpus_set_runs_into_its_own_directory_like_a_plain_run(self):
        """The set runner may run the corpus, and its case files say so.

        The corpus *is* ``runs/<model>/``, so labelling it made the set that
        owns the directory the one set that could not run into it. It is run
        unlabelled now, exactly as ``python -m eval.run_benchmark`` runs it, and
        each case file records ``development_set: null``.
        """
        before = headline_digests()
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            transport = ScriptedTransport(grade.key_as_produced(sets.CORPUS.key()))
            with mock.patch.object(run_benchmark, "RUNS_DIR", runs):
                summary = sets.run_set(
                    sets.CORPUS,
                    MODEL,
                    runs_dir=runs,
                    cases=[101, 102, 103],
                    client_factory=client_factory(transport),
                    git_runner=git_runner(),
                    progress=lambda text: None,
                    judge_votes=1,
                )
            self.assertTrue(summary.ok)
            self.assertEqual(runs / "deepseek-deepseek-flash", summary.run_dir)
            for case_no in (101, 102, 103):
                with self.subTest(case_no=case_no):
                    document = run_benchmark.load_cached(summary.run_dir, case_no)
                    self.assertIsNotNone(document)
                    self.assertIsNone(document["development_set"])
                    self.assertIn("configuration", document)
        self.assertEqual(before, headline_digests())

    def test_the_set_run_directory_check_refuses_a_directory_that_is_not_the_sets(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with self.assertRaises(run_benchmark.BenchmarkError):
                sets.assert_set_run_directory(
                    runs / "deepseek-deepseek-flash", sets.SECOND_SET, runs
                )
            # The set's own directory is accepted.
            self.assertEqual(
                (runs / "codex" / "deepseek-deepseek-flash").resolve(),
                sets.assert_set_run_directory(
                    runs / "codex" / "deepseek-deepseek-flash", sets.SECOND_SET, runs
                ),
            )

    def test_the_corpus_set_is_not_constrained_to_a_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            self.assertEqual(
                (runs / "deepseek-deepseek-flash").resolve(),
                sets.assert_set_run_directory(
                    runs / "deepseek-deepseek-flash", sets.CORPUS, runs
                ),
            )


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
class DevelopmentSetReportTests(unittest.TestCase):
    """The two sets separately, then combined."""

    def test_each_set_is_checked_for_currency_with_its_own_loader(self):
        """Both sets read all current, and the report prints the four counts."""
        report = sets.render_development_sets(MODEL)
        self.assertIn(
            "Currency, each set checked with its own loader and its own briefs:", report
        )
        for development_set in sets.DEVELOPMENT_SETS:
            with self.subTest(development_set=development_set.name):
                produced = len(sets.cached_cases(development_set, MODEL))
                staleness = sets.currency_for(development_set, MODEL)
                self.assertTrue(staleness.checked)
                self.assertEqual((), staleness.stale)
                self.assertEqual((), staleness.unknown)
                self.assertEqual((), staleness.stale_brief)
                self.assertEqual((), staleness.stale_prompts)
                self.assertGreater(produced, 0)
                expected = (
                    "  {0:<8} current {1:>3}, stale_brief {2:>3}, "
                    "stale_prompts {3:>3}, unknown {4:>3}"
                ).format(development_set.name, produced, 0, 0, 0)
                self.assertIn(expected, report)

    def test_a_set_that_has_not_been_run_reports_nothing_rather_than_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = sets.figures_for(sets.SECOND_SET, MODEL, Path(tmp) / "runs")
            self.assertEqual(0, figures.produced)
            self.assertEqual(15, figures.expected)
            self.assertIsNone(figures.report)

    def test_the_report_names_both_sets_and_says_which_figure_is_the_reported_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_codex(tmp, runs_dir=runs)
            text = sets.render_development_sets(MODEL, runs)

            self.assertIn("corpus", text)
            self.assertIn("codex", text)
            self.assertIn("corpus 0 of 29", text)
            self.assertIn("codex 15 of 15", text)
            self.assertIn("15 of 44 cases", text)
            self.assertIn("15/15 over the cases produced", text)
            # The corpus figure is named as the reported one, and neither figure
            # is offered as the generalisation number.
            self.assertIn("the figure the submission reports", text)
            self.assertIn("held-out set", text)

    def test_the_combined_figure_is_scored_over_what_has_been_produced(self):
        """An unrun set's cases are not counted as misses."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_codex(tmp, runs_dir=runs, cases=[9101, 9102])
            produced, report = sets.combined_figures(MODEL, runs)
            self.assertEqual(2, produced)
            self.assertEqual(2, report.total)
            self.assertEqual(2, report.exact_matches)

    def test_both_sets_together_are_combined_over_the_union_of_their_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_codex(tmp, runs_dir=runs, cases=[9101, 9102])
            corpus_transport = ScriptedTransport(
                grade.key_as_produced(sets.CORPUS.key())
            )
            sets.run_set(
                sets.CORPUS,
                MODEL,
                runs_dir=runs,
                cases=[101, 102],
                client_factory=client_factory(corpus_transport),
                git_runner=git_runner(),
                progress=lambda text: None,
            )
            produced, report = sets.combined_figures(MODEL, runs)
            self.assertEqual(4, produced)
            self.assertEqual(4, report.total)
            self.assertEqual({101, 102, 9101, 9102}, set(report.graded_cases))

    def test_the_cli_reports_without_making_a_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_codex(tmp, runs_dir=runs)
            import io
            from contextlib import redirect_stdout

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = sets.main(["--model", MODEL, "--runs-dir", str(runs), "--report"])
            self.assertEqual(0, code)
            self.assertIn("Development sets", buffer.getvalue())


# --------------------------------------------------------------------------
# The external-case summary prints an expectation only for its own case
# --------------------------------------------------------------------------
class ExternalExpectationTests(unittest.TestCase):
    """One sample's stated answer is not evidence about another case."""

    def test_the_ryde_case_still_finds_its_own_expectation(self):
        path = run_benchmark.external_expected_path(
            loader.EXTERNAL_DIR / "ryde" / "case-00901.json"
        )
        self.assertEqual(run_benchmark.EXTERNAL_EXPECTED_PATH, path)
        self.assertIsNotNone(run_benchmark.read_expected_outcome(path))

    def test_a_codex_case_looks_for_an_expectation_of_its_own(self):
        path = run_benchmark.external_expected_path(
            loader.EXTERNAL_DIR / "codex" / "case-09101.json"
        )
        self.assertNotEqual(run_benchmark.EXTERNAL_EXPECTED_PATH, path)
        self.assertEqual(
            run_benchmark.EXTERNAL_EXPECTED_DIR / "codex" / "expected.json", path
        )
        self.assertIsNone(run_benchmark.read_expected_outcome(path))

    def test_the_ryde_expectation_is_not_printed_beside_a_codex_case(self):
        case = loader.load_external_case(loader.EXTERNAL_DIR / "codex" / "case-09101.json")
        outcome = run_benchmark.CaseOutcome(
            case_no=case["case_no"], status=run_benchmark.STATUS_COMPLETED
        )
        expected_path = run_benchmark.external_expected_path(
            loader.EXTERNAL_DIR / "codex" / "case-09101.json"
        )
        text = run_benchmark.format_external_result(
            outcome,
            case,
            run_benchmark.read_expected_outcome(expected_path),
            Path("runs/external/codex"),
            expected_path=expected_path,
        )
        self.assertIn("no stated expectation on disk", text)
        self.assertNotIn("Cancellation charge UPHELD", text)
        self.assertNotIn("NOT A VERIFIED ANSWER", text)

    def test_the_ryde_case_still_prints_its_own_expectation(self):
        case = loader.load_external_case(loader.EXTERNAL_DIR / "ryde" / "case-00901.json")
        outcome = run_benchmark.CaseOutcome(
            case_no=case["case_no"], status=run_benchmark.STATUS_COMPLETED
        )
        expected_path = run_benchmark.external_expected_path(
            loader.EXTERNAL_DIR / "ryde" / "case-00901.json"
        )
        text = run_benchmark.format_external_result(
            outcome,
            case,
            run_benchmark.read_expected_outcome(expected_path),
            Path("runs/external/ryde"),
            expected_path=expected_path,
        )
        self.assertIn("Cancellation charge UPHELD", text)
        self.assertIn("NOT A VERIFIED ANSWER", text)


class PerCaseColumnTests(unittest.TestCase):
    """The set report carries the same per-case columns a run report carries."""

    def test_the_columns_appear_for_a_set_that_has_been_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_codex(tmp, runs_dir=runs)
            text = sets.render_development_sets(MODEL, runs)

            self.assertIn("Per case — cost, provenance and explanation tags", text)
            for column in grade.CASE_FACTS_COLUMNS:
                self.assertIn(column, text)
            # The set that was run is named over its own table; the corpus was
            # not run here, so it contributes no table rather than a table of
            # dashes a reader could mistake for a run that produced nothing.
            self.assertIn("codex —", text)
            self.assertNotIn("corpus —", text)

    def test_a_set_that_has_not_been_run_contributes_no_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = sets.render_development_sets(MODEL, Path(tmp) / "runs")
            self.assertNotIn("cost, provenance and explanation tags", text)

    def test_the_set_table_is_graded_against_the_set_s_own_key(self):
        """The columns are per case and the cases are this set's, so a corpus
        case appearing here would mean the wrong loader had been used."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_codex(tmp, runs_dir=runs)
            figures = sets.figures_for(sets.SECOND_SET, MODEL, runs)

            rows = grade.case_fact_rows(figures.report)
            self.assertEqual(
                [str(case_no) for case_no in sets.SECOND_SET.cases],
                [row[0] for row in rows],
            )


# --------------------------------------------------------------------------
# A set whose registration fixes the policy version
# --------------------------------------------------------------------------
# The one case the temporary set below holds, and the figure POL-RD-11
# publishes at policy version 2 for it: 25.83 charged against a 22.00 quote.
VERSION_TWO_CASE = 9901
VERSION_TWO_AMOUNT = "3.85"


def a_version_two_set(tmp):
    """A one-case set registered at policy version 2, under a temporary root.

    ``wild-v2`` is the only registered set whose policy version is fixed by its
    registration, and it is run once and must not be run for a test. This set is
    the same kind of thing in every respect that matters to the code under test
    -- a case root of its own, a key of its own, and version 2 in the
    registration -- so the three places the version has to travel can be
    exercised without a model call and without touching a committed run.

    The case is the synthetic upfront one from ``tests.test_upfront_remedy``: a
    fare breakdown whose model is ``UPFRONT_QUOTE`` and whose charge exceeds its
    quote, which is the arithmetic POL-RD-11's remedy is stated over. The key's
    amount is that remedy, so at version 2 the draft's amount reads off
    ``pol_rd_11_remedy.value`` and at version 1 the same amount reads off nothing
    the money block publishes.

    Call this inside ``test_upfront_remedy.version_two_amendments()`` and with
    ``loader.EXTERNAL_DIR`` patched to ``<tmp>/external``: the amendment is what
    makes version 2 exist, and the patch is what lets a case root live outside
    the repository.
    """
    root = Path(tmp) / "external" / "policy-v2-probe"
    (root / "cases").mkdir(parents=True)
    (root / "cases" / "case-09901.json").write_text(
        json.dumps(upfront_rig.synthetic_upfront_case("22.00")), encoding="utf-8"
    )
    (root / "index.json").write_text(
        json.dumps(
            [
                {
                    "case_no": VERSION_TWO_CASE,
                    "dispute_id": "DSP-09901",
                    "trip_id": "TRP-09901",
                    "category": "ROUTE_DEVIATION",
                    "file": "cases/case-09901.json",
                }
            ]
        ),
        encoding="utf-8",
    )
    key_path = Path(tmp) / "policy-v2-probe-key.json"
    key_path.write_text(
        json.dumps(
            [
                {
                    "case_no": VERSION_TWO_CASE,
                    "dispute_id": "DSP-09901",
                    "ground_truth": {
                        "expected_ruling": "PARTIAL_REFUND",
                        "expected_amount_sgd": VERSION_TWO_AMOUNT,
                        "expected_driver_compensation_sgd": None,
                        "expected_referrals": [],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    return sets.DevelopmentSet(
        name="policy-v2-probe",
        cases=(VERSION_TWO_CASE,),
        key_path=key_path,
        runs_subdir="policy-v2-probe",
        case_root=root,
        summary="a temporary one-case set registered at policy version 2",
        policy_version=2,
    )


def case_facts_row(report_text, case_no):
    """One case's row of the per-case facts table, keyed by its own header.

    Read out of the table's own header rather than by counting columns from the
    left, because the row is what a reader reads: a column inserted into the
    table would silently move the cell this returns, and the assertion would
    then be about a different column than the one it names.
    """
    lines = report_text.splitlines()
    header_index = next(
        index for index, line in enumerate(lines) if "amount_sgd from" in line
    )
    columns = [
        cell.strip()
        for cell in lines[header_index].strip().strip("|").split("|")
    ]
    row = next(
        line
        for line in lines[header_index:]
        if line.startswith("| {0} |".format(case_no))
    )
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    return dict(zip(columns, cells))


class PolicyVersionTests(unittest.TestCase):
    """A set registered at version 2 is checked, graded and read at version 2.

    The registration is where a fixed version comes from, so a function that
    takes the set and then briefs at the base version anyway measures something
    other than the set. Three things go wrong when one does, and all three are
    asserted here over one temporary set and one scripted run:

    * ``currency_for`` reports the run's one correct case as a moved brief,
      because the checker rebuilds version-1 briefs and compares them with the
      version-2 digests the run recorded;
    * ``figures_for`` computes the amount provenance from the version-1 brief,
      so the report's provenance column describes a money block no agent of that
      run was ever handed;
    * ``baselines.build_section`` refuses the case for the moved brief. Its
      replay check is the second channel and refuses nothing at all when it is
      given no version -- which is what the call did before the set's version
      travelled into it, so that read refused the case **once** and not twice.

    No model is called and nothing committed is read or written: the set lives
    in a temporary directory and its case is synthetic. The run is made with the
    default judge vote count, because a baselines panel needs more than one
    draft to verify.
    """

    def run_the_set(self, tmp):
        """The temporary set, run once, and the runs root it went into."""
        development_set = a_version_two_set(tmp)
        runs = Path(tmp) / "runs"
        transport = ScriptedTransport(grade.key_as_produced(development_set.key()))
        sets.run_set(
            development_set,
            MODEL,
            runs_dir=runs,
            client_factory=client_factory(transport),
            git_runner=git_runner(),
            progress=lambda text: None,
        )
        return development_set, runs

    def test_a_set_registered_at_version_two_reads_current_and_grades_at_it(self):
        with tempfile.TemporaryDirectory() as tmp, \
                upfront_rig.version_two_amendments(), \
                mock.patch.object(loader, "EXTERNAL_DIR", Path(tmp) / "external"):
            development_set, runs = self.run_the_set(tmp)
            run_dir = development_set.run_dir(MODEL, runs)

            # It produced a ruling at all, which is what version 2 buys this
            # case: the remedy is a figure the draft's amount reads off, so the
            # judge's draft passes the code checks and votes.
            self.assertIsNotNone(run_benchmark.load_cached(run_dir, VERSION_TWO_CASE))

            # Read current. This is the reading the version travels for: with the
            # base version the checker rebuilds the other brief, and the one
            # correct case of this run is reported as stale.
            staleness = sets.currency_for(development_set, MODEL, runs)
            self.assertTrue(staleness.checked)
            self.assertEqual((), staleness.stale)
            self.assertEqual((), staleness.stale_brief)
            self.assertEqual((), staleness.unknown)

            # And the two versions really are two briefs, so the reading above
            # is a finding rather than a check that could not have failed. A
            # version-1 checker over the same run names the case and the channel.
            version_one = run_benchmark.BriefStaleness(
                run_benchmark.brief_digest_for(
                    development_set.load_case,
                    policy_version=run_benchmark.DEFAULT_POLICY_VERSION,
                ),
                run_dir=run_dir,
                prompts_dir=run_benchmark.PROMPTS_DIR,
                policy_version=run_benchmark.DEFAULT_POLICY_VERSION,
            )
            self.assertEqual(
                (VERSION_TWO_CASE,),
                run_benchmark.brief_staleness(
                    run_dir, [VERSION_TWO_CASE], version_one
                ).stale_brief,
            )

            # The provenance is read off the version-2 brief, which is the one
            # this run's judge was handed. The version-1 block publishes no
            # figure for this amount, so the version-1 answer is a different
            # string rather than the same one by accident.
            figures = sets.figures_for(development_set, MODEL, runs)
            self.assertEqual(1, figures.produced)
            self.assertEqual(1, figures.exact)
            self.assertEqual(
                "pol_rd_11_remedy.value",
                figures.report.cases[0].facts.amount_provenance["amount_sgd"],
            )

    def test_the_baselines_section_reads_a_version_two_case_rather_than_refusing_it(self):
        with tempfile.TemporaryDirectory() as tmp, \
                upfront_rig.version_two_amendments(), \
                mock.patch.object(loader, "EXTERNAL_DIR", Path(tmp) / "external"):
            development_set, runs = self.run_the_set(tmp)
            section = baselines.build_section(development_set, MODEL, runs)

            # Analysed, not refused. The staleness checker is the channel that
            # refuses this case with the base version: it calls it a moved brief.
            # The replay check raises on the version as well, but only now that
            # it is given one -- with no version passed the comparison is
            # skipped, which is why the read before this part refused the case
            # once and not twice.
            self.assertEqual((VERSION_TWO_CASE,), section.analysed)
            self.assertEqual((), section.refusals)

    def test_the_run_s_own_report_records_the_version_two_provenance(self):
        """The report the run writes, not only the one the report command builds.

        ``figures_for`` reads the figures back off the cache, so a version that
        never reached the writer would still satisfy the assertion above. This
        reads the file the run itself left: the provenance column of a run's own
        ``report.md`` has to describe the brief that run's judge was handed.
        """
        with tempfile.TemporaryDirectory() as tmp, \
                upfront_rig.version_two_amendments(), \
                mock.patch.object(loader, "EXTERNAL_DIR", Path(tmp) / "external"):
            development_set, runs = self.run_the_set(tmp)
            run_dir = development_set.run_dir(MODEL, runs)
            written = (run_dir / run_benchmark.REPORT_FILE).read_text(
                encoding="utf-8"
            )

            cells = case_facts_row(written, VERSION_TWO_CASE)
            self.assertEqual(
                "pol_rd_11_remedy.value",
                cells["amount_sgd from"],
                "the run's own report describes a brief no agent of it was handed",
            )

    def test_the_run_s_own_report_prints_no_corpus_target(self):
        """The target is the 29-case corpus's, and this set is one case.

        ``grades_full_corpus`` is true here -- the run graded every case of the
        key it was graded against -- and that is a different question from
        whether the key *is* the corpus key. Printing the corpus target beside
        this set's rate would compare two different sets.
        """
        with tempfile.TemporaryDirectory() as tmp, \
                upfront_rig.version_two_amendments(), \
                mock.patch.object(loader, "EXTERNAL_DIR", Path(tmp) / "external"):
            development_set, runs = self.run_the_set(tmp)
            run_dir = development_set.run_dir(MODEL, runs)
            written = (run_dir / run_benchmark.REPORT_FILE).read_text(
                encoding="utf-8"
            )

            self.assertNotIn("| Target |", written)
            self.assertNotIn("| Off target |", written)
            # The counts and the reason are printed instead, and the rate is
            # labelled as computed on this set rather than as the corpus's.
            self.assertIn("**Escalation rate (on these 1 cases)**", written)
            self.assertIn("not comparable to the corpus base rate", written)
            self.assertIn("| True positives (key and run both ESCALATE) |", written)


# --------------------------------------------------------------------------
# The version-3 sets, installed 2026-10-08
# --------------------------------------------------------------------------
# One case of each: a no-show from dev-v2, a route-deviation variant from
# dev-v2-ext, and the organisers' sample.
VERSION_THREE_CASES = (("dev-v2", 1701), ("dev-v2-ext", 2701), ("ryde-v3", 901))

# What the scripted judge answers with for the one set that has no key. It is a
# well-formed POL-GEN-03 ruling of the shape the pipeline emits; the run records
# it and does not grade it, because the organisers' sample carries a stated
# expectation rather than an answer key.
UNSCORED_RULING = {
    "ruling": "DRIVER_COMPENSATION",
    "amount_sgd": 4.0,
    "driver_compensation_sgd": 4.0,
    "referrals": [],
}


def produced_for(development_set, case_no):
    """What the scripted judge answers with for one case of one set."""
    produced = grade.key_as_produced(development_set.key())
    if case_no in produced:
        return produced
    return {case_no: {"case_no": case_no, "ruling": dict(UNSCORED_RULING)}}


class _ReachedTheRunner(Exception):
    """Raised by the patched runner, to prove an invocation got past its refusals."""


class BaseThreeSetRegistrationTests(unittest.TestCase):
    """The three sets written for base 3, and the versions they accept.

    ``dev-v2``, ``dev-v2-ext`` and ``ryde-v3`` are written for policy base 3, so
    they accept any version on that base (3, 4, 5, ...) and run at the **latest**
    one -- today 5 -- when no version is named. Every set registered before
    version 3 keeps the version it fixes.

    No model is called: the transport answers from the set's own key, or -- for
    ``ryde-v3``, which has a stated expectation rather than a key -- from a
    well-formed ruling the run records and does not grade. Every runs root here
    is a temporary directory, so nothing lands under the repository's own
    ``runs/``.
    """

    def test_the_three_sets_are_registered_and_are_not_development_sets(self):
        for name, _case_no in VERSION_THREE_CASES:
            with self.subTest(set=name):
                development_set = sets.named(name)
                self.assertEqual(3, development_set.policy_version)
                self.assertEqual(3, development_set.policy_base)
                self.assertFalse(development_set.sealed)
                self.assertTrue(development_set.cases)
                self.assertNotIn(
                    development_set,
                    sets.DEVELOPMENT_SETS,
                    "{0} is in the tuple --set all runs".format(name),
                )
                self.assertNotIn(development_set, sets.SEALED_SETS)
                self.assertNotIn(development_set, sets.ALL_SETS)

    def test_ryde_v3_has_a_stated_expectation_and_no_key(self):
        """Its expectation is the organisers' word, which is not a ruling."""
        self.assertEqual({}, sets.named("ryde-v3").key())
        self.assertEqual(
            run_benchmark.EXTERNAL_EXPECTED_PATH,
            sets.named("ryde-v3").stated_expectation,
        )
        self.assertEqual(
            "Cancellation charge UPHELD",
            run_benchmark.read_expected_outcome(
                sets.named("ryde-v3").stated_expectation
            )["expected_outcome_as_stated"],
        )

    def test_the_default_version_is_the_latest_on_base_three(self):
        latest = policy_versions.version_on_base(3)
        self.assertEqual(5, latest, "base 3 is at version 5 after amendment 0002")
        for name, _case_no in VERSION_THREE_CASES:
            with self.subTest(set=name):
                self.assertEqual(
                    latest, sets.resolved_policy_version(sets.named(name), None)
                )

    def test_a_version_on_base_three_is_accepted_and_recorded(self):
        for name, case_no in VERSION_THREE_CASES:
            for version in (3, 4, 5):
                with self.subTest(set=name, version=version):
                    development_set = sets.named(name)
                    transport = ScriptedTransport(
                        produced_for(development_set, case_no)
                    )
                    with tempfile.TemporaryDirectory() as tmp:
                        runs = Path(tmp) / "runs"
                        summary = sets.run_set(
                            development_set,
                            MODEL,
                            cases=[case_no],
                            runs_dir=runs,
                            client_factory=client_factory(transport),
                            git_runner=git_runner(),
                            progress=lambda text: None,
                            judge_votes=1,
                            policy_version=version,
                        )
                        self.assertGreater(transport.calls(), 0, "no call was made")
                        run_dir = run_benchmark.policy_v_run_directory(
                            development_set.runs_dir(runs), version, MODEL
                        )
                        self.assertEqual(run_dir, summary.run_dir)
                        recorded = json.loads(
                            (run_dir / "case-{0:05d}.json".format(case_no)).read_text(
                                encoding="utf-8"
                            )
                        )
                        self.assertEqual(
                            version,
                            recorded["configuration"]["policy_version"],
                            "the run did not record the version it used",
                        )

    def test_the_command_line_accepts_a_version_on_base_three(self):
        """Each set reaches the runner with the version the flag named."""
        for name, case_no in VERSION_THREE_CASES:
            for version in (4, 5):
                with self.subTest(set=name, version=version):
                    seen = {}

                    def stop(*args, **kwargs):
                        seen.update(kwargs)
                        raise _ReachedTheRunner()

                    with tempfile.TemporaryDirectory() as tmp:
                        with mock.patch.object(
                            sets.run_benchmark, "run_benchmark", side_effect=stop
                        ):
                            with self.assertRaises(_ReachedTheRunner):
                                sets.main(
                                    [
                                        "--set", name,
                                        "--policy-version", str(version),
                                        "--cases", str(case_no),
                                        "--runs-dir", str(Path(tmp) / "runs"),
                                    ]
                                )
                    self.assertEqual(version, seen.get("policy_version"))

    def test_the_default_run_lands_under_a_policy_v_directory(self):
        for name, case_no in VERSION_THREE_CASES:
            with self.subTest(set=name):
                development_set = sets.named(name)
                with tempfile.TemporaryDirectory() as tmp:
                    runs = Path(tmp) / "runs"
                    sets.run_set(
                        development_set,
                        MODEL,
                        cases=[case_no],
                        runs_dir=runs,
                        client_factory=client_factory(
                            ScriptedTransport(produced_for(development_set, case_no))
                        ),
                        git_runner=git_runner(),
                        progress=lambda text: None,
                        judge_votes=1,
                    )
                    latest = policy_versions.version_on_base(3)
                    expected = (
                        runs
                        / development_set.runs_subdir
                        / "policy-v{0}".format(latest)
                        / run_benchmark.model_slug(MODEL)
                    )
                    self.assertTrue(
                        (expected / "case-{0:05d}.json".format(case_no)).is_file(),
                        "{0} did not write under its own policy-v{1} root".format(
                            name, latest
                        ),
                    )

    def test_an_earlier_policy_version_is_refused_by_name(self):
        """These cases carry the base-3 fields; 1 and 2 would measure nothing."""
        for name, case_no in VERSION_THREE_CASES:
            for version in ("1", "2"):
                with self.subTest(set=name, version=version):
                    with tempfile.TemporaryDirectory() as tmp:
                        with contextlib.redirect_stderr(io.StringIO()) as errors:
                            code = sets.main(
                                [
                                    "--set", name,
                                    "--policy-version", version,
                                    "--cases", str(case_no),
                                    "--runs-dir", str(Path(tmp) / "runs"),
                                ]
                            )
                    self.assertEqual(1, code)
                    self.assertIn(name, errors.getvalue())
                    self.assertIn("policy base 3", errors.getvalue())
                    self.assertFalse((Path(tmp) / "runs").exists())

    def test_the_corpus_and_the_sealed_sets_are_unchanged(self):
        for development_set in (
            sets.CORPUS,
            sets.SECOND_SET,
            sets.SEALED_SET,
            sets.WILD_DEV,
        ):
            with self.subTest(set=development_set.name):
                self.assertIsNone(development_set.policy_base)
                self.assertEqual(
                    run_benchmark.DEFAULT_POLICY_VERSION,
                    sets.resolved_policy_version(development_set, None),
                )
        # ``wild-v2`` fixes version 2 and is untouched by this: it has no base,
        # so it never picks up a later version, and its registration is not a
        # switch on the invocation.
        self.assertIsNone(sets.named("wild-v2").policy_base)
        self.assertEqual(
            2, sets.resolved_policy_version(sets.named("wild-v2"), None)
        )


if __name__ == "__main__":
    unittest.main()
