"""Tests for ``tribunal/events.py`` and ``eval/events.py``.

No network, no credential, no model call. Every log under test is written by the
real runner over the scripted transport ``tests/test_run_benchmark.py`` already
uses, so what is checked is the log a real invocation leaves behind rather than a
log assembled by hand. The rig is imported rather than copied so the two files
cannot drift into testing two different runners.

What is covered
---------------
* the shape of one invocation's log: it opens with ``invocation_start`` and
  closes with ``invocation_end``, and every line carries its own timestamp,
  sequence number, invocation id, case number, commit and prompts digest;
* the append rule: a second invocation into the same directory adds lines and
  leaves the first invocation's lines byte-identical, and ``--force`` skips the
  cache without clearing the log;
* the chain: an edited line is reported **at that line**, a deleted line is
  reported at the line that no longer agrees with its predecessor, and a
  re-hashed edit is caught one line later -- plus the CLI's exit status and the
  line it names;
* a case's history: reconstructed in the order it happened, with the advocates
  before the referee's decisions and the judge after them;
* failures: a transport failure, a timeout and an unprovisioned model are each
  recorded with their own kind, and a run that died says so on its last line;
* the credential scan, with a positive control that proves the needles bite.

Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import events as events_cli  # noqa: E402
from eval import run_benchmark as runner  # noqa: E402
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import events, llm, transcript  # noqa: E402

CASE = 102


def log_path(run_dir):
    return Path(run_dir) / events.EVENTS_FILE


def event_names(log, case_no=None):
    rows = events.read_events(log)
    if case_no is not None:
        rows = [row for row in rows if row.get("case") == case_no]
    return [row["event"] for row in rows]


def names_of(log, case_no):
    return event_names(log, case_no)


class NotProvisionedTransport:
    """A transport whose every answer is the 402 the provisioning error comes from.

    This is the shape the 2026-09-27 replay took: the model was not provisioned
    for the account, so the first attempt raised rather than returning a body.
    """

    def __call__(self, url, headers, body, timeout):
        return llm.HttpResult(status=402, body=b'{"error": {"code": "401006"}}')


# --------------------------------------------------------------------------
# The shape of one invocation's log
# --------------------------------------------------------------------------
class LogShapeTests(unittest.TestCase):
    """One invocation brackets itself, and every line stands on its own."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name
        self.summary, _ = rig.bench(self.tmp)
        self.log = log_path(self.summary.run_dir)

    def test_the_run_writes_a_log_beside_its_other_records(self):
        self.assertTrue(self.log.is_file(), "no event log was written")
        self.assertGreater(len(events.read_lines(self.log)), 0)

    def test_the_invocation_opens_and_closes_the_log(self):
        names = event_names(self.log)
        self.assertEqual(events.EVENT_INVOCATION_START, names[0])
        self.assertEqual(events.EVENT_INVOCATION_END, names[-1])

    def test_every_line_carries_its_own_context(self):
        """A line that only said which invocation wrote it at the head of the
        file would be unreadable once a second invocation had appended."""
        rows = events.read_events(self.log)
        self.assertGreater(len(rows), 0)
        for number, row in enumerate(rows, start=1):
            for field in events.RESERVED_FIELDS:
                self.assertIn(field, row, "line {0} has no {1}".format(number, field))
            self.assertTrue(row["ts"], "line {0} has no timestamp".format(number))
            self.assertEqual(number - 1, row["seq"], "seq is not 0-based and dense")
            self.assertEqual(1, len({row["invocation"]}) if row["invocation"] else 0)

    def test_the_case_column_is_set_on_the_case_events_and_null_on_the_others(self):
        rows = events.read_events(self.log)
        for row in rows:
            if row["event"] in (events.EVENT_INVOCATION_START, events.EVENT_INVOCATION_END):
                self.assertIsNone(row["case"])
            else:
                self.assertIn(row["case"], (101, 102, 103))

    def test_the_commit_and_prompts_digest_are_the_run_s_own(self):
        rows = events.read_events(self.log)
        self.assertEqual({rig.COMMIT}, {row["commit"] for row in rows})
        metadata = runner.read_json(runner.metadata_path(self.summary.run_dir))
        self.assertEqual({metadata["prompts_sha256"]}, {row["prompts"] for row in rows})

    def test_the_invocation_id_is_on_the_lines_and_in_the_metadata(self):
        """So the two can be joined without matching timestamps."""
        metadata = runner.read_json(runner.metadata_path(self.summary.run_dir))
        ids = {row["invocation"] for row in events.read_events(self.log)}
        self.assertEqual(1, len(ids))
        self.assertEqual({metadata["invocation_id"]}, ids)

    def test_the_end_line_says_what_the_invocation_did(self):
        last = events.read_events(self.log)[-1]
        self.assertEqual(runner.STOP_COMPLETED, last["stop_reason"])
        self.assertEqual(self.summary.report.total, last["cases_graded"])
        self.assertEqual(self.summary.report.exact_matches, last["exact_matches"])

    def test_the_log_carries_no_raw_prompt(self):
        """A digest of the request is recorded; the request is not."""
        text = self.log.read_text(encoding="utf-8")
        self.assertNotIn(rig.RIDER_STANCE, text)
        self.assertNotIn(rig.DRIVER_STANCE, text)


# --------------------------------------------------------------------------
# Append-only
# --------------------------------------------------------------------------
class AppendOnlyTests(unittest.TestCase):
    """A second invocation adds lines. Nothing rewrites or truncates."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name
        self.runs = Path(self.tmp) / "runs"
        self.first, _ = rig.bench(self.tmp, runs_dir=self.runs)
        self.log = log_path(self.first.run_dir)
        self.before = events.read_lines(self.log)

    def test_a_second_invocation_appends_rather_than_truncating(self):
        self.second, _ = rig.bench(self.tmp, runs_dir=self.runs)

        after = events.read_lines(self.log)
        self.assertGreater(len(after), len(self.before), "the second run wrote nothing")
        self.assertEqual(
            self.before,
            after[: len(self.before)],
            "the second invocation rewrote the first invocation's lines",
        )

    def test_the_two_invocations_are_told_apart_on_the_lines(self):
        rig.bench(self.tmp, runs_dir=self.runs)
        ids = [row["invocation"] for row in events.read_events(self.log)]
        self.assertEqual(2, len(set(ids)), "the invocations share an id")
        # The first invocation's lines keep their own id: the id travels per
        # line rather than being read off the head of the file.
        first_id = events.read_events(self.log)[0]["invocation"]
        self.assertEqual(
            {first_id},
            {row["invocation"] for row in events.read_events(self.log)[: len(self.before)]},
        )

    def test_force_skips_the_cache_and_does_not_clear_the_log(self):
        """Forcing a re-run is not licence to erase the record of the first."""
        rig.bench(self.tmp, runs_dir=self.runs, force=True)
        after = events.read_lines(self.log)
        self.assertEqual(self.before, after[: len(self.before)])

    def test_a_second_invocation_continues_the_sequence(self):
        rig.bench(self.tmp, runs_dir=self.runs)
        seq = events.sequence_of(self.log)
        self.assertEqual(list(range(len(seq))), seq, "the sequence restarted or skipped")

    def test_a_cached_case_is_recorded_as_begun_and_reused(self):
        """A fully cached run still says which cases it was asked for."""
        rig.bench(self.tmp, runs_dir=self.runs)
        rows = events.read_events(self.log)
        cached = [
            row
            for row in rows
            if row["event"] == events.EVENT_CASE_START and row.get("cached")
        ]
        self.assertEqual([101, 102, 103], [row["case"] for row in cached])

    def test_a_run_case_is_recorded_as_work(self):
        rows = events.read_events(self.log)
        worked = [
            row
            for row in rows
            if row["event"] == events.EVENT_CASE_START and row.get("cached") is False
        ]
        self.assertEqual([101, 102, 103], [row["case"] for row in worked])


# --------------------------------------------------------------------------
# Tamper evidence
# --------------------------------------------------------------------------
class ChainTests(unittest.TestCase):
    """The chain names the first line that no longer agrees with it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.summary, _ = rig.bench(self._tmp.name)
        self.log = log_path(self.summary.run_dir)
        self.original = events.read_lines(self.log)

    def _write(self, lines):
        self.log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_an_intact_log_verifies(self):
        self.assertIsNone(events.verify_chain(self.log))

    def test_an_edited_line_is_reported_at_that_line(self):
        target = 5
        row = json.loads(self.original[target - 1])
        row["role"] = "tampered"
        lines = list(self.original)
        lines[target - 1] = json.dumps(row, ensure_ascii=False, sort_keys=True)
        self._write(lines)

        break_at = events.verify_chain(self.log)
        self.assertIsNotNone(break_at, "an edited line went unreported")
        self.assertEqual(target, break_at.line_number)
        self.assertEqual("content", break_at.kind)

    def test_a_re_hashed_edit_is_caught_at_the_next_line(self):
        """Recomputing the edited line's own hash cannot hide it: the line after
        it still names the old one."""
        target = 5
        row = json.loads(self.original[target - 1])
        row["role"] = "tampered"
        body = {key: value for key, value in row.items() if key != "hash"}
        row["hash"] = events.digest_of(body)
        lines = list(self.original)
        lines[target - 1] = events.canonical(row)
        self._write(lines)

        break_at = events.verify_chain(self.log)
        self.assertIsNotNone(break_at)
        self.assertEqual(target + 1, break_at.line_number)
        self.assertEqual("chain", break_at.kind)

    def test_a_deleted_line_is_reported_at_the_line_that_follows_it(self):
        target = 5
        lines = self.original[: target - 1] + self.original[target:]
        self._write(lines)

        break_at = events.verify_chain(self.log)
        self.assertIsNotNone(break_at)
        self.assertEqual(target, break_at.line_number)
        self.assertEqual("chain", break_at.kind)

    def test_only_the_first_break_is_reported(self):
        lines = list(self.original)
        for target in (5, 7):
            row = json.loads(lines[target - 1])
            row["role"] = "tampered"
            lines[target - 1] = json.dumps(row, ensure_ascii=False, sort_keys=True)
        self._write(lines)

        break_at = events.verify_chain(self.log)
        self.assertEqual(5, break_at.line_number)

    def test_a_line_that_is_not_json_is_reported_as_malformed(self):
        lines = list(self.original)
        lines[3] = "{not json"
        self._write(lines)
        break_at = events.verify_chain(self.log)
        self.assertEqual(4, break_at.line_number)
        self.assertEqual("malformed", break_at.kind)

    def test_a_first_line_that_is_not_the_beginning_is_caught(self):
        """The genesis sentinel is a value no digest can take, so a first line
        that was moved down cannot pass itself off as the start of the chain."""
        lines = self.original[1:]
        self._write(lines)
        break_at = events.verify_chain(self.log)
        self.assertEqual(1, break_at.line_number)
        self.assertEqual("chain", break_at.kind)


# --------------------------------------------------------------------------
# A case's history, and the two commands that print it
# --------------------------------------------------------------------------
class CaseHistoryTests(unittest.TestCase):
    """One case, followed from the invocation that issued it to its grade."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.summary, _ = rig.bench(self._tmp.name)
        self.log = log_path(self.summary.run_dir)

    def test_the_history_is_in_the_order_it_happened(self):
        names = names_of(self.log, CASE)
        self.assertEqual(events.EVENT_CASE_START, names[0])
        self.assertEqual(events.EVENT_GRADE, names[-1])

        seq = [row["seq"] for row in events.events_for_case(self.log, CASE)]
        self.assertEqual(sorted(seq), seq, "a case's events are out of order")

    def test_the_advocates_precede_the_referee_and_the_judge_follows_it(self):
        rows = events.events_for_case(self.log, CASE)
        roles = [
            row["role"] for row in rows if row["event"] == events.EVENT_AGENT_CALL
        ]
        self.assertEqual(
            [transcript.ROLE_RIDER_ADVOCATE, transcript.ROLE_DRIVER_ADVOCATE,
             transcript.ROLE_JUDGE],
            roles,
        )
        referee_at = [
            number for number, row in enumerate(rows)
            if row["event"] == events.EVENT_REFEREE_DECISION
        ]
        judge_at = [
            number for number, row in enumerate(rows)
            if row["event"] == events.EVENT_AGENT_CALL
            and row["role"] == transcript.ROLE_JUDGE
        ]
        self.assertTrue(referee_at, "the referee's decisions were not recorded")
        self.assertGreater(min(judge_at), max(referee_at))

    def test_every_advocate_call_records_what_it_cost_and_how_it_parsed(self):
        rows = [
            row for row in events.events_for_case(self.log, CASE)
            if row["event"] == events.EVENT_AGENT_CALL
        ]
        for row in rows:
            self.assertEqual(rig.PROMPT_TOKENS + rig.COMPLETION_TOKENS, row["total_tokens"])
            self.assertTrue(row["request_sha256"])
            self.assertIn("seconds", row)
            self.assertIn("parse_outcome", row)

    def test_the_referee_records_a_side_a_verdict_and_a_reason_code(self):
        rows = [
            row for row in events.events_for_case(self.log, CASE)
            if row["event"] == events.EVENT_REFEREE_DECISION
        ]
        for row in rows:
            self.assertIn(row["side"], ("RIDER", "DRIVER"))
            self.assertIn("status", row)
            self.assertTrue(row["reason_code"])

    def test_the_single_draft_and_the_ruling_are_between_the_judge_and_the_grade(self):
        names = names_of(self.log, CASE)
        self.assertIn(events.EVENT_JUDGE_DRAFT, names)
        self.assertIn(events.EVENT_RULING, names)
        draft = names.index(events.EVENT_JUDGE_DRAFT)
        self.assertEqual(events.EVENT_RULING, names[draft + 1])
        self.assertEqual(events.EVENT_GRADE, names[draft + 2])

    def test_the_single_draft_says_the_checks_did_not_run(self):
        """At K = 1 there is no panel to abstain from, so the pre-vote checks are
        not a property of this draft. ``None`` says that; reporting them as
        passed would claim a check that was never made."""
        rows = [
            row for row in events.events_for_case(self.log, CASE)
            if row["event"] == events.EVENT_JUDGE_DRAFT
        ]
        self.assertEqual(1, len(rows))
        self.assertEqual("single", rows[0]["kind"])
        self.assertIsNone(rows[0]["checks"])
        self.assertTrue(rows[0]["valid"])

    def test_a_case_the_log_does_not_hold_reports_nothing(self):
        self.assertEqual([], events.events_for_case(self.log, 999))

    def test_the_case_command_prints_the_history(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = events_cli.main(["--path", str(self.log), "--case", str(CASE)])
        self.assertEqual(0, status)
        text = out.getvalue()
        self.assertIn("case {0}".format(CASE), text)
        for name in names_of(self.log, CASE):
            self.assertIn(name, text)

    def test_the_case_command_is_non_zero_for_a_case_it_does_not_hold(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            status = events_cli.main(["--path", str(self.log), "--case", "999"])
        self.assertEqual(1, status)
        self.assertIn("999", err.getvalue())

    def test_the_json_form_prints_the_payloads(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = events_cli.main(["--path", str(self.log), "--case", str(CASE), "--json"])
        self.assertEqual(0, status)
        printed = [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(names_of(self.log, CASE)), len(printed))
        self.assertEqual(names_of(self.log, CASE), [row["event"] for row in printed])

    def test_the_verify_command_reports_an_intact_chain_and_exits_zero(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = events_cli.main(["--path", str(self.log), "--verify"])
        self.assertEqual(0, status)
        self.assertIn("intact", out.getvalue())

    def test_the_verify_command_names_the_first_break_and_exits_non_zero(self):
        lines = events.read_lines(self.log)
        row = json.loads(lines[4])
        row["role"] = "tampered"
        lines[4] = json.dumps(row, ensure_ascii=False, sort_keys=True)
        self.log.write_text("\n".join(lines) + "\n", encoding="utf-8")

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            status = events_cli.main(["--path", str(self.log), "--verify"])
        self.assertEqual(1, status)
        self.assertIn("line 5", err.getvalue())

    def test_the_default_path_is_the_run_directory_the_runner_writes_to(self):
        resolved = events_cli.default_log_path(rig.MODEL, runs_dir=Path(self._tmp.name) / "runs")
        self.assertEqual(self.log, resolved)


# --------------------------------------------------------------------------
# Failures
# --------------------------------------------------------------------------
class FailureTests(unittest.TestCase):
    """Every way a call can fail is on the log, with its own kind."""

    def test_a_transport_failure_is_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = rig.bench(tmp, transport=rig.UnreachableTransport())
            rows = [
                row for row in events.read_events(log_path(summary.run_dir))
                if row["event"] == events.EVENT_CASE_FAILED
            ]
            self.assertTrue(rows, "a transport failure left no event")
            self.assertEqual({runner.FAILURE_TRANSPORT}, {row["failure_kind"] for row in rows})

    def test_a_timeout_is_logged_as_a_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = rig.bench(tmp, transport=rig.ReadTimeoutTransport())
            kinds = {
                row["failure_kind"]
                for row in events.read_events(log_path(summary.run_dir))
                if row["event"] == events.EVENT_CASE_FAILED
            }
            self.assertEqual({runner.FAILURE_TIMEOUT}, kinds)

    def test_a_case_that_produced_no_ruling_is_logged(self):
        key = rig.answer_key()
        transport = rig.ScriptedTransport(
            rig.produced_from_key(key), fail={(CASE, transcript.ROLE_JUDGE)}
        )
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = rig.bench(tmp, transport=transport)
            rows = [
                row for row in events.read_events(log_path(summary.run_dir))
                if row["event"] == events.EVENT_CASE_FAILED
            ]
            self.assertEqual([CASE], [row["case"] for row in rows])
            self.assertEqual(transcript.ROLE_JUDGE, rows[0]["failed_agent"])

    def test_an_unprovisioned_model_is_logged_and_ends_the_invocation(self):
        """The failure the 2026-09-27 replay hit: raised, not recorded per case,
        and the run's last line says the invocation stopped on it."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(llm.ModelNotProvisionedError):
                rig.bench(tmp, transport=NotProvisionedTransport())

            log = log_path(runner.run_directory(Path(tmp) / "runs", rig.MODEL))
            rows = events.read_events(log)
            failed = [row for row in rows if row["event"] == events.EVENT_CASE_FAILED]
            self.assertTrue(failed, "the provisioning failure left no event")
            self.assertEqual(runner.FAILURE_TRANSPORT, failed[0]["failure_kind"])
            self.assertIn("not provisioned", failed[0]["detail"])
            self.assertEqual(events.EVENT_INVOCATION_END, rows[-1]["event"])
            self.assertEqual(runner.STOP_FATAL, rows[-1]["stop_reason"])

    def test_a_run_that_died_still_verifies(self):
        """A log written on the way out of an exception is still a chain."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(llm.ModelNotProvisionedError):
                rig.bench(tmp, transport=NotProvisionedTransport())
            log = log_path(runner.run_directory(Path(tmp) / "runs", rig.MODEL))
            self.assertIsNone(events.verify_chain(log))

    def test_a_missing_credential_is_logged_before_it_is_raised(self):
        def build(sink):
            raise llm.MissingAPIKeyError("no credential")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(llm.MissingAPIKeyError):
                rig.bench(tmp, client_factory=build)
            log = log_path(runner.run_directory(Path(tmp) / "runs", rig.MODEL))
            rows = events.read_events(log)
            self.assertEqual(events.EVENT_INVOCATION_END, rows[-1]["event"])
            self.assertEqual(runner.STOP_FATAL, rows[-1]["stop_reason"])
            self.assertIn("MissingAPIKeyError", rows[-1]["detail"])


# --------------------------------------------------------------------------
# The credential
# --------------------------------------------------------------------------
class CredentialTests(unittest.TestCase):
    """The log is scanned for the house credential, and the scan is shown to bite."""

    NEEDLES = ("sk-", rig.FAKE_KEY)

    def test_the_produced_log_carries_no_credential(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _ = rig.bench(tmp)
            text = log_path(summary.run_dir).read_text(encoding="utf-8")
            for needle in self.NEEDLES:
                self.assertNotIn(needle, text)

    def test_the_scan_can_fire(self):
        """The positive control. A scan that cannot fail proves nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / events.EVENTS_FILE
            log = events.EventLog(path, invocation_id="inv")
            log.record(events.EVENT_AGENT_CALL, case_no=CASE, detail=rig.FAKE_KEY)
            text = path.read_text(encoding="utf-8")
            self.assertIn(rig.FAKE_KEY, text)

    def test_a_payload_may_not_shadow_a_reserved_field(self):
        """The fields the chain is built on cannot be overwritten by a payload."""
        with tempfile.TemporaryDirectory() as tmp:
            log = events.EventLog(Path(tmp) / events.EVENTS_FILE, invocation_id="inv")
            with self.assertRaises(ValueError):
                log.record(events.EVENT_AGENT_CALL, case_no=CASE, prev="forged")
            with self.assertRaises(ValueError):
                log.record(events.EVENT_AGENT_CALL, case_no=CASE, hash="forged")


if __name__ == "__main__":
    unittest.main(verbosity=2)
