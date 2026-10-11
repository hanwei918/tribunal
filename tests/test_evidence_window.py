"""The evidence window of ``ops/evidence_window.py``: part 26.

``POL-GEN-06(4)`` lets a reviewer choose ``REQUEST_EVIDENCE``, and part 26 is the
command that executes it: one window opened to both parties at once, into which
each may file a record until it closes, after which the reviewer decides on what
arrived or the default outcome ``POL-GEN-07(1)(2)`` requires.

What is asserted here:

* **The sheet's acceptance, on corpus case 213.** Opening at
  ``2026-08-11T20:00+08:00`` fixes the close at ``2026-08-13T06:40:55+08:00``
  (filing plus 36 hours, the config's own figure) and the decision at
  ``2026-08-13T18:40:55+08:00`` (filing plus ``POL-GEN-06(2)``'s first-review
  limit). The rider's ``STATEMENT`` is refused; ``close`` before the close
  instant is refused; ``submit`` after it is refused; with only a ``CALL_LOG``
  filed, ``close`` gives ``FULL_REFUND`` 6.0 and the printed command is accepted
  by ``ops.review`` against a temporary store; and a tampered store line is
  refused.
* **The three policy sentences.** ``POL-GEN-06``'s ``REQUEST_EVIDENCE`` limb and
  ``POL-GEN-07(1)`` and ``(2)`` are matched word for word, and a sentence that
  has moved is a refusal rather than a default.
* **The store.** One append-only ``jsonl`` per case, each line carrying the
  previous line's hash; a submitted file is stored by its SHA-256; a note is
  capped and marked an argument and not evidence; and a case has one window.
* **The refusals.** An item or a kind outside ``POL-GEN-04(b)``, a case that is
  neither escalated nor held under ``POL-GEN-05``, an opening past the 24-hour
  limit, and a store inside a tree the layer does not write into.
* **The queue block.** ``ops.queue --windows`` reads the same store and shows
  each human-lane case's window.

The rules that bind every module of the layer -- the import graph, the answer
keys, the write guard and determinism -- are asserted once, over every ``ops``
command, in ``tests/test_ops_layer.py``. No test here reads an answer key.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops import evidence_window as ew  # noqa: E402
from ops import queue, review  # noqa: E402
from tribunal import loader  # noqa: E402

# The version-6 corpus run, and the sheet's acceptance case in it.
CORPUS_V6_RUN = PROJECT_ROOT / "runs" / "policy-v6" / "deepseek-deepseek-flash"
CASE = 213

# Case 213's own instants, read off ``data/cases/case-00213.json``.
FILED_AT = "2026-08-11T18:40:55+08:00"
OPEN_AT = "2026-08-11T20:00:00+08:00"
CLOSE_AT = "2026-08-13T06:40:55+08:00"
DECIDE_AT = "2026-08-13T18:40:55+08:00"
AFTER_CLOSE = "2026-08-13T07:00:00+08:00"
PAST_THE_OPEN_LIMIT = "2026-08-12T19:00:00+08:00"

# The item the acceptance's window names, and the artifact the case lacks.
ITEM = "GPS_EXPORT"
MISSING_EVIDENCE_ID = "EV-GPS-00213"

# A case the pipeline decided and that no ``POL-GEN-05`` hold reaches: 102 is
# neither one of the run's five escalations (110, 112, 207, 210, 213) nor one of
# its four held cases (101, 105, 106, 114).
DECIDED_CASE = 102


def instant(text: str) -> datetime:
    return datetime.fromisoformat(text)


def run_command(arguments: Sequence[str]) -> Tuple[int, str, str]:
    """One command's ``main``, with both streams captured."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = ew.main(list(arguments))
    return code, stdout.getvalue(), stderr.getvalue()


def open_arguments(store: Path, items: str = ITEM, now: str = OPEN_AT, case: int = CASE) -> List[str]:
    return [
        "open",
        "--store",
        str(store),
        "--run-dir",
        str(CORPUS_V6_RUN),
        "--case",
        str(case),
        "--now",
        now,
        "--items",
        items,
        "--opened-by",
        "a reviewer",
    ]


def submit_arguments(
    store: Path,
    source: Path,
    kind: str = "CALL_LOG",
    party: str = "rider",
    note: str = "",
    now: str = OPEN_AT,
    case: int = CASE,
) -> List[str]:
    return [
        "submit",
        "--store",
        str(store),
        "--run-dir",
        str(CORPUS_V6_RUN),
        "--case",
        str(case),
        "--now",
        now,
        "--party",
        party,
        "--kind",
        kind,
        "--file",
        str(source),
        "--note",
        note,
    ]


def close_arguments(store: Path, now: str = AFTER_CLOSE, case: int = CASE) -> List[str]:
    return [
        "close",
        "--store",
        str(store),
        "--run-dir",
        str(CORPUS_V6_RUN),
        "--case",
        str(case),
        "--now",
        now,
    ]


def open_the_window(store: Path, items: str = ITEM) -> None:
    code, out, err = run_command(open_arguments(store, items=items))
    if code != 0:
        raise AssertionError("opening the window failed: {0}".format(err or out))


def write_record(directory: Path, name: str = "call-log.txt", body: bytes = b"a call log\n") -> Path:
    path = Path(directory) / name
    path.write_bytes(body)
    return path


def events_of(store: Path, case: int = CASE) -> List[Mapping[str, Any]]:
    return list(ew.read_events(Path(store), case))


# --------------------------------------------------------------------------
# The sheet's acceptance, on case 213
# --------------------------------------------------------------------------
class TheAcceptanceTests(unittest.TestCase):
    """The four sub-commands on the sheet's case, at the sheet's instants."""

    def test_open_fixes_the_close_and_the_decision_instants(self):
        """Filing plus 36 hours, and filing plus POL-GEN-06(2)'s 48 hours."""
        with tempfile.TemporaryDirectory() as tmp:
            open_the_window(Path(tmp))
            window = ew.window_state(Path(tmp), CASE)
            self.assertIsNotNone(window)
            self.assertEqual(instant(CLOSE_AT), window.close_at)
            self.assertEqual(instant(DECIDE_AT), window.decide_at)
            self.assertEqual(instant(FILED_AT), window.filed_at)
            self.assertEqual((ITEM,), window.items)
            self.assertEqual("a reviewer", window.opened_by)

    def test_the_rider_s_statement_is_refused(self):
        """POL-GEN-06(5) refuses a statement made after filing as evidence."""
        with tempfile.TemporaryDirectory() as tmp:
            open_the_window(Path(tmp))
            source = write_record(Path(tmp))
            code, out, err = run_command(
                submit_arguments(Path(tmp), source, kind="STATEMENT")
            )
            self.assertEqual(1, code)
            self.assertIn("STATEMENT", err)
            self.assertEqual(1, len(events_of(tmp)), "a refused filing was written")

    def test_close_before_the_close_instant_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            open_the_window(Path(tmp))
            code, out, err = run_command(
                close_arguments(Path(tmp), now="2026-08-13T06:00:00+08:00")
            )
            self.assertEqual(1, code)
            self.assertIn(CLOSE_AT, err)

    def test_submit_after_the_close_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            open_the_window(Path(tmp))
            source = write_record(Path(tmp))
            code, out, err = run_command(
                submit_arguments(Path(tmp), source, now=AFTER_CLOSE)
            )
            self.assertEqual(1, code)
            self.assertIn("closed", err)

    def test_a_call_log_filed_leaves_the_named_item_missing(self):
        """The window named GPS_EXPORT; a CALL_LOG does not satisfy it."""
        with tempfile.TemporaryDirectory() as tmp:
            open_the_window(Path(tmp))
            source = write_record(Path(tmp))
            code, out, err = run_command(submit_arguments(Path(tmp), source))
            self.assertEqual(0, code, err)
            window = ew.window_state(Path(tmp), CASE)
            self.assertEqual(
                (ITEM,), ew.missing_items(window, events_of(tmp))
            )

    def test_close_gives_the_default_outcome_the_policy_requires(self):
        """No-show fee disputed by the rider: FULL_REFUND of the fare's total."""
        with tempfile.TemporaryDirectory() as tmp:
            open_the_window(Path(tmp))
            source = write_record(Path(tmp))
            run_command(submit_arguments(Path(tmp), source))
            code, out, err = run_command(close_arguments(Path(tmp)))
            self.assertEqual(0, code, err)
            self.assertIn("FULL_REFUND 6.0", out)
            self.assertIn(MISSING_EVIDENCE_ID, out)

    def test_the_printed_command_cites_pol_gen_07(self):
        with tempfile.TemporaryDirectory() as tmp:
            open_the_window(Path(tmp))
            code, out, err = run_command(close_arguments(Path(tmp)))
            self.assertEqual(0, code, err)
            command = [
                line for line in out.splitlines() if line.startswith("python3 -m ops.review")
            ]
            self.assertEqual(1, len(command), out)
            self.assertIn("--clause POL-GEN-07", command[0])
            self.assertIn("--ruling FULL_REFUND", command[0])
            self.assertIn("--amount 6.0", command[0])
            self.assertNotIn(" close ", command[0])

    def test_the_printed_command_is_accepted_by_ops_review(self):
        """The command the close prints stores a closure through ops.review."""
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "windows"
            open_the_window(store)
            code, out, err = run_command(close_arguments(store))
            self.assertEqual(0, code, err)
            command = [
                line for line in out.splitlines() if line.startswith("python3 -m ops.review")
            ][0]
            precedent_store = Path(tmp) / "precedents"
            argv = shlex.split(command)[3:] + ["--store", str(precedent_store)]
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = review.main(argv)
            self.assertEqual(0, code, stderr.getvalue())
            self.assertTrue(
                (precedent_store / "precedents.jsonl").is_file(),
                "the printed command stored no closure",
            )

    def test_a_reason_a_shell_would_rewrite_is_quoted_safely(self):
        """The printed command is copy-pasted, so a shell must not rewrite it.

        A reason is free text and may hold `$`, a backtick or `!`. Wrapped in
        double quotes a shell expands the first, runs the second as a command
        and history-expands the third, so the value that reached ``close`` would
        not be the value the reviewer wrote. ``shlex.quote`` single-quotes it
        instead, and this test hands the printed argument to a real POSIX shell
        to show the round trip.
        """
        reason = "refund $4.50 `per POL-RD-09` and NO! action"
        command = ew.review_command(
            Path("/tmp/tribunal-run"),
            CASE,
            {"case_no": CASE},
            "FULL_REFUND",
            Decimal("4.50"),
            reason,
            "a reviewer",
        )
        quoted = command.split("--reason ", 1)[1]
        completed = subprocess.run(
            ["/bin/sh", "-c", "printf '%s' " + quoted],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(reason, completed.stdout)
        argv = shlex.split(command)
        self.assertEqual(reason, argv[argv.index("--reason") + 1])

    def test_a_tampered_store_line_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            open_the_window(store)
            source = write_record(store)
            run_command(submit_arguments(store, source))
            path = ew.window_path(store, CASE)
            lines = path.read_text(encoding="utf-8").splitlines()
            record = json.loads(lines[0])
            record["opened_by"] = "somebody else"
            lines[0] = json.dumps(record, sort_keys=True, separators=(",", ":"))
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(ew.EvidenceWindowError):
                ew.read_events(store, CASE)


# --------------------------------------------------------------------------
# The policy sentences, and the two figures
# --------------------------------------------------------------------------
class ThePolicyTests(unittest.TestCase):
    """The sentences are the policy's, and the figures are read from them."""

    def policies(self, category: str = "NO_SHOW_CHARGE") -> Mapping[str, Any]:
        return loader.load_policies(category, 6)

    def test_the_two_limits_are_pol_gen_06_s_own_numbers(self):
        self.assertEqual((24, 48), ew.read_window_limits(self.policies()))

    def test_the_three_sentences_are_in_the_loaded_policy(self):
        burden, charge = ew.read_residual_sentences(self.policies())
        self.assertEqual(ew.BURDEN_SENTENCE, burden)
        self.assertEqual(ew.CHARGE_DEFAULT_SENTENCE, charge)
        text = self.policies()["general"]
        self.assertIn(
            "REQUEST_EVIDENCE, naming the record-type items required",
            json.dumps(text, default=str),
        )

    def test_a_moved_sentence_is_refused(self):
        """A POL-GEN-06 that no longer names the decision is a refusal."""
        doctored = copy.deepcopy(self.policies())
        for clause in doctored["general"]["clauses"]:
            if clause["id"] == "POL-GEN-06":
                clause["rule"] = clause["rule"].replace(
                    ew.REQUEST_EVIDENCE_SENTENCE, "REQUEST_EVIDENCE"
                )
        with self.assertRaises(ew.EvidenceWindowError):
            ew.read_window_limits(doctored)

    def test_a_moved_residual_principle_is_refused(self):
        doctored = copy.deepcopy(self.policies())
        for clause in doctored["general"]["clauses"]:
            if clause["id"] == "POL-GEN-07":
                clause["rule"] = clause["rule"].replace(ew.BURDEN_SENTENCE, "Something else.")
        with self.assertRaises(ew.EvidenceWindowError):
            ew.read_residual_sentences(doctored)

    def test_the_close_figure_is_the_config_s_own(self):
        self.assertEqual(Decimal(36), ew.read_close_hours())

    def test_a_config_without_the_figure_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"auto_rulings_enabled": True}), encoding="utf-8")
            with self.assertRaises(ew.EvidenceWindowError):
                ew.read_close_hours(path)


# --------------------------------------------------------------------------
# The store
# --------------------------------------------------------------------------
class TheStoreTests(unittest.TestCase):
    """One append-only chain per case, and the files a party files."""

    def test_each_line_carries_the_previous_line_s_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            open_the_window(store)
            source = write_record(store)
            run_command(submit_arguments(store, source))
            raw = ew.window_path(store, CASE).read_text(encoding="utf-8").splitlines()
            self.assertEqual(2, len(raw))
            self.assertIsNone(json.loads(raw[0])["prev_sha256"])
            self.assertEqual(
                hashlib.sha256(raw[0].encode("utf-8")).hexdigest(),
                json.loads(raw[1])["prev_sha256"],
            )

    def test_a_broken_chain_is_refused_by_the_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            open_the_window(store)
            path = ew.window_path(store, CASE)
            path.write_text(path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
            with self.assertRaises(ew.EvidenceWindowError):
                ew.read_events(store, CASE)

    def test_one_window_per_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            open_the_window(Path(tmp))
            code, out, err = run_command(open_arguments(Path(tmp)))
            self.assertEqual(1, code)
            self.assertIn("one window", err)
            self.assertEqual(1, len(events_of(tmp)))

    def test_the_submitted_file_is_stored_by_its_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            open_the_window(store)
            body = b"an ERP gantry record\n"
            source = write_record(store, "erp.txt", body)
            code, out, err = run_command(
                submit_arguments(store, source, kind="ERP_GANTRY_RECORD")
            )
            self.assertEqual(0, code, err)
            digest = hashlib.sha256(body).hexdigest()
            stored = ew.files_dir(store) / digest
            self.assertTrue(stored.is_file())
            self.assertEqual(body, stored.read_bytes())

    def test_a_note_is_capped(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            open_the_window(store)
            source = write_record(store)
            code, out, err = run_command(
                submit_arguments(store, source, note="x" * (ew.NOTE_MAX_CHARS + 1))
            )
            self.assertEqual(1, code)
            self.assertIn(str(ew.NOTE_MAX_CHARS), err)

    def test_a_note_is_marked_an_argument_not_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            open_the_window(store)
            source = write_record(store)
            run_command(submit_arguments(store, source, note="the driver was late"))
            filing = events_of(store)[1]
            self.assertEqual("the driver was late", filing["note"])
            self.assertEqual("argument, not evidence", filing["note_label"])


# --------------------------------------------------------------------------
# The refusals
# --------------------------------------------------------------------------
class TheRefusalTests(unittest.TestCase):
    """What a window will not open for, take, or be read from."""

    def test_open_refuses_an_item_outside_pol_gen_04_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_command(open_arguments(Path(tmp), items="CHAT_LOG"))
            self.assertEqual(1, code)
            self.assertIn("CHAT_LOG", err)
            self.assertFalse(ew.window_path(Path(tmp), CASE).exists())

    def test_open_refuses_a_case_with_no_human_review(self):
        """102 is neither escalated nor held under POL-GEN-05."""
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_command(open_arguments(Path(tmp), case=DECIDED_CASE))
            self.assertEqual(1, code)
            self.assertIn("POL-GEN-05", err)
            self.assertFalse(ew.window_path(Path(tmp), DECIDED_CASE).exists())

    def test_open_refuses_more_than_the_open_limit_after_filing(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_command(open_arguments(Path(tmp), now=PAST_THE_OPEN_LIMIT))
            self.assertEqual(1, code)
            self.assertIn("24 hours of filing", err)

    def test_submit_refuses_a_kind_outside_pol_gen_04_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            open_the_window(store)
            source = write_record(store)
            code, out, err = run_command(
                submit_arguments(store, source, kind="GPS_TRACE")
            )
            self.assertEqual(1, code)
            self.assertIn("GPS_TRACE", err)
            self.assertEqual(1, len(events_of(store)))

    def test_the_store_is_refused_inside_a_forbidden_tree(self):
        forbidden = PROJECT_ROOT / "runs" / "evidence-windows"
        with self.assertRaises(ew.EvidenceWindowError):
            ew.store_path(forbidden)
        self.assertFalse(forbidden.exists())

    def test_status_says_when_there_is_no_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_command(
                [
                    "status",
                    "--store",
                    tmp,
                    "--run-dir",
                    str(CORPUS_V6_RUN),
                    "--case",
                    str(CASE),
                    "--now",
                    OPEN_AT,
                ]
            )
            self.assertEqual(0, code, err)
            self.assertIn("no evidence window", out)

    def test_status_names_what_is_still_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            open_the_window(store, items="GPS_EXPORT,CALL_LOG")
            source = write_record(store)
            run_command(submit_arguments(store, source))
            code, out, err = run_command(
                [
                    "status",
                    "--store",
                    str(store),
                    "--run-dir",
                    str(CORPUS_V6_RUN),
                    "--case",
                    str(CASE),
                    "--now",
                    OPEN_AT,
                ]
            )
            self.assertEqual(0, code, err)
            self.assertIn("still missing: GPS_EXPORT", out)


# --------------------------------------------------------------------------
# The default outcomes
# --------------------------------------------------------------------------
class TheDefaultOutcomeTests(unittest.TestCase):
    """POL-GEN-07(1)(2), read per category and per filing party."""

    def packet(self, category: str, filed_by: str, total: Any = Decimal("6.0")) -> Mapping[str, Any]:
        return {
            "case_no": 213,
            "case": {"category": category, "filed_by": filed_by},
            "fare_lines": [{"line": "total_charged", "value": total}],
        }

    def test_a_no_show_fee_disputed_by_the_rider_is_refunded_in_full(self):
        ruling, amount = ew.default_outcome(self.packet("NO_SHOW_CHARGE", "RIDER"))
        self.assertEqual("FULL_REFUND", ruling)
        self.assertEqual(Decimal("6.0"), amount)

    def test_a_no_show_fee_disputed_by_the_driver_is_no_action(self):
        ruling, amount = ew.default_outcome(self.packet("NO_SHOW_CHARGE", "DRIVER"))
        self.assertEqual("NO_ACTION", ruling)
        self.assertIsNone(amount)

    def test_a_route_deviation_claim_is_no_action(self):
        ruling, amount = ew.default_outcome(self.packet("ROUTE_DEVIATION", "RIDER"))
        self.assertEqual("NO_ACTION", ruling)
        self.assertIsNone(amount)

    def test_a_category_with_no_stated_outcome_is_refused(self):
        with self.assertRaises(ew.EvidenceWindowError):
            ew.default_outcome(self.packet("PROPERTY_DAMAGE", "RIDER"))

    def test_the_reason_names_the_missing_evidence_and_cites_the_clause(self):
        window = ew.Window(
            case_no=CASE,
            set_name="corpus",
            category="NO_SHOW_CHARGE",
            filed_by="RIDER",
            filed_at=instant(FILED_AT),
            opened_at=instant(OPEN_AT),
            opened_by="a reviewer",
            items=(ITEM,),
            close_at=instant(CLOSE_AT),
            decide_at=instant(DECIDE_AT),
        )
        reason = ew.default_reason(
            window, (ITEM,), MISSING_EVIDENCE_ID, "FULL_REFUND", Decimal("6.0")
        )
        self.assertIn(MISSING_EVIDENCE_ID, reason)
        self.assertIn("POL-GEN-07", reason)
        self.assertGreaterEqual(len(reason), 20)


# --------------------------------------------------------------------------
# The disclosure
# --------------------------------------------------------------------------
class TheDisclosureTests(unittest.TestCase):
    """The window's clock is an operations rule, and every output says so."""

    def test_every_output_carries_the_operations_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            outputs: List[str] = []
            outputs.append(run_command(open_arguments(store))[1])
            source = write_record(store)
            outputs.append(run_command(submit_arguments(store, source))[1])
            outputs.append(
                run_command(
                    [
                        "status",
                        "--store",
                        str(store),
                        "--run-dir",
                        str(CORPUS_V6_RUN),
                        "--case",
                        str(CASE),
                        "--now",
                        OPEN_AT,
                    ]
                )[1]
            )
            outputs.append(run_command(close_arguments(store))[1])
            for text in outputs:
                self.assertIn(ew.OPS_RULE_NOTE, text)
                self.assertIn("not frozen policy", text)

    def test_the_evidence_arrived_output_carries_it_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            open_the_window(store, items=ITEM)
            source = write_record(store)
            run_command(submit_arguments(store, source, kind=ITEM))
            code, out, err = run_command(close_arguments(store))
            self.assertEqual(0, code, err)
            self.assertIn("decide on the evidence", out)
            self.assertIn(ew.OPS_RULE_NOTE, out)

    def test_the_config_note_names_the_operations_rule(self):
        document = json.loads(
            (PROJECT_ROOT / "ops" / "config.json").read_text(encoding="utf-8")
        )
        note = document["evidence_window"]["note"]
        self.assertIn("OPS-EW-01", note)
        self.assertIn("not frozen policy", note)


# --------------------------------------------------------------------------
# The queue block
# --------------------------------------------------------------------------
class TheQueueWindowsTests(unittest.TestCase):
    """``ops.queue --windows`` reads the same store, and reads nothing else."""

    def entries(self) -> Sequence[queue.Entry]:
        disputes = queue.disputes_from_run(CORPUS_V6_RUN)
        return queue.build_queue(disputes, queue.load_config())

    def test_the_block_shows_a_human_case_s_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            open_the_window(Path(tmp))
            text = queue.render_windows(self.entries(), Path(tmp))
            self.assertIn("evidence windows: {0}".format(tmp), text)
            self.assertIn("closes {0}".format(CLOSE_AT), text)
            self.assertIn("still missing: {0}".format(ITEM), text)

    def test_the_block_says_when_a_case_has_no_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = queue.render_windows(self.entries(), Path(tmp))
            self.assertIn("no evidence window", text)


if __name__ == "__main__":
    unittest.main()
