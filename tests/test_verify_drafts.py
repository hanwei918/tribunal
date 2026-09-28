"""Tests for ``eval.verify_drafts``.

The recorded-drafts measurement reuses a run's own judge drafts and calls only
the verifier, so on and off can be compared on the SAME drafts. Every test here
scripts the transport: no network, and no model call.

The source run each test measures is a real run, produced by
``eval.run_benchmark`` over a scripted transport, so the drafts under
measurement are the ones the project's own code records rather than a fixture
written by hand that could drift from the format. Nothing here reads or writes
the committed ``runs/`` directory.

Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import grade, run_benchmark, verify_drafts  # noqa: E402
from tribunal import llm, money, pipeline, transcript as transcript_module  # noqa: E402

MODEL = "deepseek/deepseek-flash"
COMMIT = "0b20a66deadbeefcafe0123456789abcdef01234"
FAKE_KEY = "tok-live-FAKEKEY-0123456789abcdef-DO-NOT-LEAK"
CASE_SET = (101, 102)

# A bare claim array, which is all the pipeline's advocate validator asks for.
CLAIM_ARRAY = (
    '[{"claim_id": "C1", "evidence_id": "EV-GPS-00101", "clause_id": "POL-RD-01"}]'
)

# A judge explanation that states a fact the extractor knows, so the recorded
# draft is one the verifier is actually asked about.
FACTUAL_EXPLANATION = "The fare was S$4.35 per EV-GPS-00101."

# Per call, and the figures the runner's own rig uses.
PROMPT_TOKENS = 120
COMPLETION_TOKENS = 30
REASONING_TOKENS = 8


def envelope(answer: str) -> llm.HttpResult:
    body = json.dumps(
        {
            "choices": [{"message": {"content": answer}}],
            "usage": {
                "prompt_tokens": PROMPT_TOKENS,
                "completion_tokens": COMPLETION_TOKENS,
                "completion_tokens_details": {"reasoning_tokens": REASONING_TOKENS},
                "prompt_tokens_details": {"cached_tokens": 0},
            },
        }
    )
    return llm.HttpResult(status=200, body=body.encode("utf-8"))


def answer_key():
    return grade.load_answer_key()


def produced_from_key(key):
    return grade.key_as_produced(key)


def git_runner(commit: str = COMMIT):
    """A stand-in for ``git`` that answers the two questions the runner asks."""

    def run(arguments):
        return commit if arguments[0] == "rev-parse" else ""

    return run


class SourceTransport:
    """Answers a full run: advocates, judges from the key, and the verifier.

    The judge answers carry the key's own ruling -- so the drafts pass the code
    checks -- with an explanation added, because the key is a ruling and not a
    piece of prose and the verifier exists to read prose. Every request is
    recorded with the role it was made for, so a test can ask what the
    measurement actually sent.
    """

    def __init__(
        self,
        produced,
        explanation=FACTUAL_EXPLANATION,
        verdict_for=None,
        material_for=None,
        brief_value_for=None,
        raw=None,
    ):
        self.produced = produced
        self.explanation = explanation
        self.verdict_for = verdict_for or (lambda item: pipeline.VERDICT_SUPPORTED)
        # A contradiction stops its draft only when it is said to be able to
        # change a conclusion, so a scripted verdict carries that answer too. The
        # default is the stricter reading, which is what this pass measured
        # before materiality existed.
        self.material_for = material_for or (lambda item: True)
        self.brief_value_for = brief_value_for or (
            lambda item: "the figure the brief holds"
        )
        self.raw = raw
        self.roles = []
        self.verifier_requests = []

    def __call__(self, url, headers, body, timeout):
        request = json.loads(body.decode("utf-8"))
        parsed = json.loads(request["messages"][1]["content"])

        if isinstance(parsed, dict) and "statements" in parsed:
            case_no = parsed["brief"]["case"]["case_no"]
            self.roles.append((case_no, transcript_module.ROLE_VERIFIER))
            self.verifier_requests.append(parsed)
            return envelope(self._verifier_answer(parsed["statements"]))

        if isinstance(parsed, dict) and "claims" in parsed:
            case_no = parsed["brief"]["case"]["case_no"]
            self.roles.append((case_no, transcript_module.ROLE_JUDGE))
            inner = dict(self.produced[case_no]["ruling"])
            inner["confidence"] = 0.85
            inner["explanation"] = self.explanation
            return envelope(
                money.dumps_canonical({"ruling": inner, "discarded_claims": []})
            )

        case_no = parsed["case"]["case_no"]
        self.roles.append((case_no, transcript_module.ROLE_RIDER_ADVOCATE))
        return envelope(CLAIM_ARRAY)

    def _verifier_answer(self, statements):
        if self.raw is not None:
            return self.raw
        verdicts = []
        for item in statements:
            verdict = self.verdict_for(item)
            entry = {
                "statement": item["n"],
                "verdict": verdict,
                "evidence": "EV-GPS-00101",
            }
            if verdict == pipeline.VERDICT_CONTRADICTED:
                entry[pipeline.VERDICT_MATERIAL] = bool(self.material_for(item))
                entry[pipeline.VERDICT_BRIEF_VALUE] = self.brief_value_for(item)
            verdicts.append(entry)
        return json.dumps({"verdicts": verdicts})

    def verifier_calls(self) -> int:
        return sum(
            1 for _, role in self.roles if role == transcript_module.ROLE_VERIFIER
        )

    def other_calls(self) -> int:
        return sum(
            1 for _, role in self.roles if role != transcript_module.ROLE_VERIFIER
        )


class RefusingTransport:
    """A transport that fails if it is ever used, and counts the attempts."""

    def __init__(self):
        self.calls = 0

    def __call__(self, url, headers, body, timeout):
        self.calls += 1
        raise AssertionError("no call may be made for a case that is refused")


def client_factory(model, transport):
    """A real ``LLMClient`` over the scripted transport, with no real sleeping."""

    def build(sink):
        return llm.LLMClient(
            model=model,
            api_key=FAKE_KEY,
            transport=transport,
            record_sink=sink,
            max_attempts=1,
            clock=lambda: 0.0,
            sleep=lambda seconds: None,
        )

    return build


def source_run(root, *, cases=CASE_SET, judge_votes=4, explanation=FACTUAL_EXPLANATION):
    """A real run of the corpus cases, over the scripted transport."""
    runs = Path(root) / "runs"
    transport = SourceTransport(produced_from_key(answer_key()), explanation=explanation)
    run_benchmark.run_benchmark(
        MODEL,
        list(cases),
        runs_dir=runs,
        prompts_dir=run_benchmark.PROMPTS_DIR,
        client_factory=client_factory(MODEL, transport),
        key=answer_key(),
        git_runner=git_runner(),
        progress=lambda text: None,
        judge_votes=judge_votes,
    )
    return runs, run_benchmark.run_directory(runs, MODEL), transport


def measure(runs, source, *, cases=CASE_SET, transport=None, **options):
    """Run the recorded-drafts measurement and return ``(report, transport)``."""
    transport = (
        SourceTransport(produced_from_key(answer_key()))
        if transport is None
        else transport
    )
    report = verify_drafts.verify_recorded_run(
        source,
        list(cases),
        model=MODEL,
        runs_dir=runs,
        client_factory=client_factory(MODEL, transport),
        progress=lambda text: None,
        **options,
    )
    return report, transport


def directory_state(root: Path):
    """Every file under ``root`` with its bytes, for a before-and-after check."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(Path(root).rglob("*"))
        if path.is_file()
    }


class RecordedDraftMeasurementTests(unittest.TestCase):
    """One verifier call per case, on the drafts the source run recorded."""

    def test_one_verifier_call_per_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            report, transport = measure(runs, source)

        self.assertEqual(len(CASE_SET), transport.verifier_calls())
        self.assertEqual(CASE_SET, tuple(report.verified_cases))
        self.assertTrue(report.ok, report.refused)

    def test_the_measurement_calls_only_the_verifier(self):
        """The advocates and the judge are reused, not asked again."""
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            report, transport = measure(runs, source)

        self.assertEqual(0, transport.other_calls())

    def test_the_verifier_reads_the_statements_the_recorded_drafts_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            report, transport = measure(runs, source)

        asked = [item["text"] for item in transport.verifier_requests[0]["statements"]]
        self.assertEqual([FACTUAL_EXPLANATION] * 4, asked)
        self.assertEqual(
            [FACTUAL_EXPLANATION] * 4,
            [item["text"] for item in report.cases[0].judged],
        )

    def test_one_set_of_verdicts_yields_all_three_votes(self):
        """The rule, read three ways on one call's verdicts.

        Draft 1's fact is contradicted **materially** and draft 2's **not**, so
        the two rules part company on this case and the report has to show both:
        the strict rule stops two drafts and leaves too few to carry a ruling,
        while the pipeline's own stops one and the ruling survives. Nothing is
        sampled twice -- the three readings are three reductions of one answer.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            report, transport = measure(
                runs,
                source,
                transport=SourceTransport(
                    produced_from_key(answer_key()),
                    verdict_for=lambda item: (
                        pipeline.VERDICT_CONTRADICTED
                        if item["draft"] <= 2
                        else pipeline.VERDICT_SUPPORTED
                    ),
                    material_for=lambda item: item["draft"] == 1,
                ),
            )

        self.assertEqual(len(CASE_SET), transport.verifier_calls(), "one call per case")

        for case in report.cases:
            with self.subTest(case=case.case_no):
                # Without the verifier: the source run's own vote.
                self.assertEqual("carried", case.without.outcome)
                self.assertEqual(1.0, case.without.agreement)
                # The strict rule: every contradiction stops its draft, so two
                # stand and the threshold of three is not met. The agreement is
                # still the winner's share of the whole panel, which is why it
                # reads 0.5 rather than nothing.
                self.assertEqual("escalated", case.any_contradiction.outcome)
                self.assertEqual(0.5, case.any_contradiction.agreement)
                self.assertEqual("ESCALATE", case.any_contradiction.ruling)
                # Materiality only: the pipeline's own rule.
                self.assertEqual("carried_not_unanimous", case.material_only.outcome)
                self.assertEqual(0.75, case.material_only.agreement)
                self.assertEqual(case.without.ruling, case.material_only.ruling)

                self.assertTrue(case.matches_recorded, "the recorded vote was reproduced")
                self.assertTrue(case.changed, "the verifier moved the vote")
                self.assertTrue(case.strict_changed)
                self.assertEqual((1,), case.abstained)
                self.assertEqual(2, len(case.contradicted))
                self.assertEqual(1, len(case.material))

        self.assertEqual(list(CASE_SET), report.changed_cases)
        self.assertEqual(list(CASE_SET), report.strict_changed_cases)
        self.assertEqual([], report.saved_cases, "materiality changed no case here")

    def test_materiality_alone_keeps_the_vote_the_strict_rule_would_have_moved(self):
        """The case the field exists for, and the one the report must name.

        Every draft is contradicted and every contradiction is immaterial, so
        the strict rule leaves no draft standing while the pipeline's own rule
        leaves the vote exactly as the run recorded it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            report, _ = measure(
                runs,
                source,
                transport=SourceTransport(
                    produced_from_key(answer_key()),
                    verdict_for=lambda item: pipeline.VERDICT_CONTRADICTED,
                    material_for=lambda item: False,
                ),
            )
            text = verify_drafts.render_report(report)

        for case in report.cases:
            with self.subTest(case=case.case_no):
                self.assertEqual("carried", case.without.outcome)
                self.assertEqual(1.0, case.without.agreement)
                self.assertEqual("no_valid_drafts", case.any_contradiction.outcome)
                self.assertIsNone(case.any_contradiction.ruling)
                self.assertEqual("carried", case.material_only.outcome)
                self.assertEqual(1.0, case.material_only.agreement)

                self.assertFalse(case.changed, "materiality kept the vote")
                self.assertTrue(case.strict_changed, "the strict rule would not have")
                self.assertEqual((), case.abstained)
                self.assertEqual(4, len(case.contradicted))
                self.assertEqual(0, len(case.material))

        self.assertEqual([], report.changed_cases)
        self.assertEqual(list(CASE_SET), report.strict_changed_cases)
        self.assertEqual(list(CASE_SET), report.saved_cases)
        self.assertIn("materiality alone keeps the vote on:", text)
        self.assertIn("the verifier moved the vote on: no case", text)

    def test_the_report_quotes_every_contradicted_statement(self):
        """Quoted with the draft, the materiality, and what the brief holds."""
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            report, _ = measure(
                runs,
                source,
                transport=SourceTransport(
                    produced_from_key(answer_key()),
                    verdict_for=lambda item: pipeline.VERDICT_CONTRADICTED,
                    material_for=lambda item: item["draft"] % 2 == 1,
                    brief_value_for=lambda item: "the figure the brief holds",
                ),
            )
            text = verify_drafts.render_report(report)

        for case in report.cases:
            with self.subTest(case=case.case_no):
                self.assertEqual(4, len(case.contradicted))
                self.assertEqual(2, len(case.material))
                self.assertEqual(2, len(case.abstained))
        self.assertIn(FACTUAL_EXPLANATION, text)
        self.assertIn("draft 1, material", text)
        self.assertIn("draft 2, not material", text)
        self.assertIn('the brief holds: "the figure the brief holds"', text)
        for case_no in CASE_SET:
            self.assertIn(str(case_no), text)

    def test_a_malformed_answer_leaves_every_draft_voting(self):
        """All three readings coincide, because there is nothing to reduce."""
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            report, _ = measure(
                runs,
                source,
                transport=SourceTransport(
                    produced_from_key(answer_key()), raw="not a json object"
                ),
            )

        self.assertFalse(report.ok, "a case whose verifier could not answer is not ok")
        self.assertEqual([], report.changed_cases)
        self.assertEqual([], report.strict_changed_cases)
        for case in report.cases:
            with self.subTest(case=case.case_no):
                self.assertTrue(case.called)
                self.assertFalse(case.usable)
                self.assertEqual(case.without, case.material_only)
                self.assertEqual(case.without, case.any_contradiction)
                self.assertEqual((), case.abstained)

    def test_the_verifier_tokens_are_the_measurements_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            report, _ = measure(runs, source)

        per_case = PROMPT_TOKENS + COMPLETION_TOKENS
        self.assertEqual(per_case * len(CASE_SET), report.tokens["total_tokens"])
        for case in report.cases:
            with self.subTest(case=case.case_no):
                self.assertEqual(per_case, case.tokens["total_tokens"])

    def test_the_verifier_call_and_its_verdicts_are_on_the_event_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            report, _ = measure(
                runs,
                source,
                transport=SourceTransport(
                    produced_from_key(answer_key()),
                    verdict_for=lambda item: (
                        pipeline.VERDICT_CONTRADICTED
                        if item["draft"] == 1
                        else pipeline.VERDICT_SUPPORTED
                    ),
                ),
            )
            lines = [
                json.loads(line)
                for line in (report.run_dir / "events.jsonl").read_text().splitlines()
                if line.strip()
            ]

        calls = [
            line
            for line in lines
            if line["event"] == "agent_call"
            and line.get("role") == transcript_module.ROLE_VERIFIER
        ]
        self.assertEqual(len(CASE_SET), len(calls))
        for line in calls:
            with self.subTest(case=line["case"]):
                self.assertEqual(PROMPT_TOKENS, line["prompt_tokens"])
        verdicts = [line for line in lines if line["event"] == "verification"]
        self.assertEqual(len(CASE_SET), len(verdicts))
        for line in verdicts:
            with self.subTest(case=line["case"]):
                self.assertTrue(line["usable"])
                self.assertEqual(4, line["statements"])
                self.assertEqual(1, line["contradicted"])
                self.assertEqual(1, line["material"])
                self.assertEqual(0, line["not_material"])
                self.assertEqual([1], line["abstained"])


class RecordedDraftDestinationTests(unittest.TestCase):
    """The results go to their own directory, and never to the headline one."""

    def test_the_destination_is_never_the_headline_directory(self):
        """The separation is a property of the path, not a promise."""
        for runs_dir in (Path("/tmp/runs"), Path("/tmp"), Path("/")):
            with self.subTest(runs_dir=runs_dir):
                headline = run_benchmark.run_directory(runs_dir, MODEL)
                destination = verify_drafts.verify_recorded_directory(runs_dir, MODEL)

                self.assertNotEqual(headline, destination)
                self.assertEqual(
                    headline.parent
                    / verify_drafts.VERIFY_RECORDED_SUBDIR
                    / run_benchmark.model_slug(MODEL),
                    destination,
                )

    def test_the_results_are_written_beside_the_run_and_not_into_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)
            headline = directory_state(source)

            report, _ = measure(runs, source)

            self.assertEqual(headline, directory_state(source))
            self.assertNotEqual(source.resolve(), report.run_dir.resolve())
            self.assertEqual(
                runs
                / verify_drafts.VERIFY_RECORDED_SUBDIR
                / run_benchmark.model_slug(MODEL),
                report.run_dir,
            )
            self.assertEqual(
                {
                    "events.jsonl",
                    verify_drafts.VERIFY_RECORDED_JSON,
                    verify_drafts.VERIFY_RECORDED_REPORT,
                },
                {path.name for path in report.run_dir.iterdir()},
            )

    def test_the_report_and_the_json_say_the_same_thing(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            report, _ = measure(runs, source)
            document = json.loads(
                (report.run_dir / verify_drafts.VERIFY_RECORDED_JSON).read_text()
            )
            rendered = (report.run_dir / verify_drafts.VERIFY_RECORDED_REPORT).read_text()

        self.assertEqual(str(source), document["source"])
        self.assertEqual(MODEL, document["model"])
        self.assertEqual([case.as_dict() for case in report.cases], document["cases"])
        self.assertEqual({}, document["refused"])
        self.assertEqual(verify_drafts.render_report(report), rendered)


class RecordedDraftProvenanceTests(unittest.TestCase):
    """A case whose recorded drafts answer a different question is refused.

    Every refusal here is a refusal to compare two different measurements. A
    refused case is never asked, so the transport counts nothing.
    """

    def test_a_source_run_that_asked_the_judge_once_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp, judge_votes=1)

            report, transport = measure(runs, source, transport=RefusingTransport())

        self.assertEqual([], report.verified_cases)
        self.assertEqual(set(CASE_SET), set(report.refused))
        self.assertFalse(report.ok)
        self.assertEqual(0, transport.calls, "a refused case is never asked")
        for case_no, reason in report.refused.items():
            with self.subTest(case=case_no):
                self.assertIn("no panel", reason)

    def test_recorded_drafts_under_a_different_judge_prompt_are_refused(self):
        """The condition a replay of the advocates cannot answer.

        The advocate calls are untouched, the brief is untouched and the
        transcript still hashes to what the run recorded for it -- so
        :func:`eval.run_benchmark.check_replay` accepts the case. What has moved
        is the judge prompt the recorded drafts answer, and that is this mode's
        own check.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)
            case_no = CASE_SET[0]
            self._rewrite_judge_digest(source, case_no)

            check = run_benchmark.check_replay(
                source, list(CASE_SET), model=MODEL, prompts_dir=run_benchmark.PROMPTS_DIR
            )
            self.assertIn(case_no, check.accepted_cases, check.refused)

            report, transport = measure(runs, source)

        self.assertNotIn(case_no, report.verified_cases)
        self.assertIn(case_no, report.refused)
        self.assertIn("judge prompt", report.refused[case_no])
        # The other case is untouched, and is verified as usual.
        self.assertEqual([CASE_SET[1]], report.verified_cases)
        self.assertEqual(1, transport.verifier_calls())

    @staticmethod
    def _rewrite_judge_digest(source: Path, case_no: int):
        """Make the recorded judge entries answer a different system prompt.

        The transcript digest the run recorded is recomputed afterwards, so the
        source stays self-consistent: it is a run that really was produced under
        another judge prompt, not a run that has been tampered with.
        """
        path = run_benchmark.transcript_path(source, case_no)
        payload = run_benchmark.read_json(path)
        for entry in payload["entries"]:
            if entry["role"] == transcript_module.ROLE_JUDGE:
                entry["system_sha256"] = "f" * 64
        run_benchmark.write_json(path, payload)

        document = run_benchmark.load_cached(source, case_no)
        document["transcript_sha256"] = run_benchmark.file_sha256(path)
        run_benchmark.write_json(run_benchmark.case_cache_path(source, case_no), document)

    def test_a_source_run_whose_brief_moved_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)
            case_no = CASE_SET[1]
            document = run_benchmark.load_cached(source, case_no)
            document["brief_sha256"] = "0" * 64
            run_benchmark.write_json(
                run_benchmark.case_cache_path(source, case_no), document
            )

            report, transport = measure(runs, source)

        self.assertIn(case_no, report.refused)
        self.assertIn("brief", report.refused[case_no])
        self.assertEqual([CASE_SET[0]], report.verified_cases)
        self.assertEqual(1, transport.verifier_calls())

    def test_a_run_directory_that_does_not_exist_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"

            with self.assertRaises(run_benchmark.BenchmarkError):
                verify_drafts.verify_recorded_run(
                    Path(tmp) / "nowhere",
                    list(CASE_SET),
                    model=MODEL,
                    runs_dir=runs,
                    client_factory=client_factory(MODEL, RefusingTransport()),
                )

    def test_a_model_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            with self.assertRaises(run_benchmark.BenchmarkError):
                verify_drafts.verify_recorded_run(
                    source,
                    list(CASE_SET),
                    model="",
                    runs_dir=runs,
                    client_factory=client_factory(MODEL, RefusingTransport()),
                )

    def test_no_cases_selected_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)

            with self.assertRaises(run_benchmark.BenchmarkError):
                verify_drafts.verify_recorded_run(
                    source,
                    [],
                    model=MODEL,
                    runs_dir=runs,
                    client_factory=client_factory(MODEL, RefusingTransport()),
                )


class RecordedDraftRefusalTests(unittest.TestCase):
    """A refused case is reported, and the rest of the run still happens."""

    def test_a_refused_case_is_named_with_its_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, source, _ = source_run(tmp)
            # Empty one case's transcript, which is what a run that never got
            # that far leaves behind.
            path = run_benchmark.transcript_path(source, CASE_SET[1])
            path.write_text("{}", encoding="utf-8")
            document = run_benchmark.load_cached(source, CASE_SET[1])
            document["transcript_sha256"] = run_benchmark.file_sha256(path)
            run_benchmark.write_json(
                run_benchmark.case_cache_path(source, CASE_SET[1]), document
            )

            report, transport = measure(runs, source)

        self.assertEqual([CASE_SET[0]], report.verified_cases)
        self.assertEqual({CASE_SET[1]}, set(report.refused))
        self.assertEqual(1, transport.verifier_calls(), "the refused case is not asked")
        self.assertFalse(report.ok)
        text = verify_drafts.render_report(report)
        self.assertIn(str(CASE_SET[1]), text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
