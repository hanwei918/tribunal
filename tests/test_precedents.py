"""Tests for the precedent library.

A human reviewer's closing decisions are stored in ``precedents/precedents.jsonl``
-- append-only and hash-chained, one ``closure`` event per entry -- and, when a
run asks for it, up to three of them are shown to the judge: a ``precedent_id``,
a category, clause ids and a ruling, and **no amount and no summary**.

Three things are asserted here, and each is the point of its own section:

* **the store is a chain.** Appending continues it rather than restarting it, an
  edit to any line is reported at that line, and an entry cannot carry a name
  that would let an answer reach a file a later task might read back.
* **the matching is a written-down rule.** Its seven steps are exercised one at a
  time, and the filters are shown to fire rather than merely to exist.
* **the switch is off by default and off is byte-identical.** With no library
  named, the judge's user message, the transcript, the case file and the run
  metadata are what they were; the key is absent rather than empty.

Nothing here reaches a real model. Every test that runs a runner or the pipeline
either injects the scripted transport from ``tests.test_run_benchmark`` or
patches ``tribunal.llm.LLMClient`` to raise, and a real key sits in the
repository's ``.env``.
"""

from __future__ import annotations

import contextlib
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

from eval import development_sets, run_benchmark as runner  # noqa: E402
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import (  # noqa: E402
    brief,
    events,
    loader,
    money,
    pipeline,
    precedents,
    referee,
)

MODEL = rig.MODEL
PROMPTS_DIR = rig.PROMPTS_DIR

# A fixed clock reading, so two pipeline runs over the same case produce the same
# transcript bytes and "byte-identical" can be asserted rather than described.
FIXED_NOW = "2026-09-28T00:00:00+00:00"

# A sentinel distinct from ``None``: it says "this caller never named the
# parameter at all", which is the case the byte-identity tests are about.
OMIT = object()

# The case a closure is made about, and the case it is matched against. Both are
# ROUTE_DEVIATION, so the category filter passes and the other filters are what
# the matching tests actually exercise.
SOURCE_CASE = 102
TARGET_CASE = 101

# One of the held-out set's own cases, for the test that closes a case out of a
# run directory shaped like ``runs/wild/<model-slug>/``. It is ROUTE_DEVIATION
# and its policy carries ``POL-RD-02``, so the closure's clause resolves.
WILD_CASE = 501

# Real clause ids, so the matching is asked about ids the loaded policy holds.
# ``POL-RD-02`` is kept for the target case by the claims built below, which is
# what makes an entry resting on it a precedent for it.
RD_01 = "POL-RD-01"
RD_02 = "POL-RD-02"
RD_06 = "POL-RD-06"
RD_09 = "POL-RD-09"
RD_11 = "POL-RD-11"
NS_02 = "POL-NS-02"
GEN_03 = "POL-GEN-03"

# The clause id that does not resolve anywhere: ``POL-RD-12`` is the last one the
# route-deviation policy holds, so this is one past it.
UNRESOLVABLE = "POL-RD-99"

# The eleven fields an entry carries, in the order ``close`` builds them.
ENTRY_FIELDS = (
    "precedent_id",
    "source",
    "category",
    "system_outcome",
    "decision",
    "clause_ids",
    "amount_contested_sgd",
    "summary",
    "closed_by",
    "policy_version",
    "supersedes",
)

# The five fields a closure reads from a case file, and no sixth.
CASE_FIELDS_READ = ("case_no", "ruling", "brief_sha256", "development_set", "configuration")


def canonical(document):
    return money.dumps_canonical(document)


def store_dir(tmp):
    """A store root under a temporary directory, per the queue's rule 7."""
    return Path(tmp) / precedents.PRECEDENTS_DIRNAME


def claims_citing(case_no, clause_id=RD_02):
    """An advocate answer whose one claim cites ``clause_id``.

    The rig's own ``CLAIM_ARRAY`` carries no ``clause_ids`` at all, which is
    enough for every other test in the suite but not for these: the precedents
    are matched on the clause ids the referee KEPT, so a claim that cites none
    matches nothing and the switch would look inert.
    """
    return canonical(
        [
            {
                "claim_id": "C1",
                "evidence_id": "EV-GPS-{0:05d}".format(case_no),
                "clause_ids": [clause_id],
            }
        ]
    )


def transport_for(key=None, claims=None):
    key = rig.answer_key() if key is None else key
    return rig.ScriptedTransport(rig.produced_from_key(key))


@contextlib.contextmanager
def claiming(claims):
    """The scripted transport, with advocate claims that cite a clause."""
    with mock.patch.object(rig, "CLAIM_ARRAY", claims):
        yield


def entry(
    precedent_id="P-0001",
    case_no=SOURCE_CASE,
    *,
    set_name=precedents.SET_CORPUS,
    category="ROUTE_DEVIATION",
    clause_ids=(RD_02,),
    ruling="PARTIAL_REFUND",
    amount="10.0",
    summary="A reviewer closed this case on the plain reading of the clause.",
    supersedes=None,
    dispute_id=None,
):
    """One closure entry, shaped as ``close`` builds it."""
    return {
        "precedent_id": precedent_id,
        "source": {
            "set": set_name,
            "case_no": case_no,
            "dispute_id": "DSP-{0:05d}".format(case_no) if dispute_id is None else dispute_id,
            "run_dir": "runs/<model>",
            "case_sha256": "0" * 64,
        },
        "category": category,
        "system_outcome": {
            "ruling": "ESCALATE",
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
        "amount_contested_sgd": None if amount is None else Decimal(amount),
        "summary": summary,
        "closed_by": "A Reviewer",
        "policy_version": 1,
        "supersedes": supersedes,
    }


def write_entries(store, entries):
    for item in entries:
        precedents.append_entry(item, store=store)
    return store


class StubReferee:
    """The one attribute the matching reads: the claims the referee kept."""

    def __init__(self, rider=(), driver=()):
        self.kept_claims = {
            referee.SIDE_RIDER: [{"clause_ids": list(rider)}] if rider else [],
            referee.SIDE_DRIVER: [{"clause_ids": list(driver)}] if driver else [],
        }


class StubLibrary:
    """A library that answers with a fixed block.

    Used where the question is what the PIPELINE does with a block, not which
    entries were chosen: the choice has its own tests, and a stub keeps those
    two questions apart.
    """

    def __init__(self, block_value=None, ids=(), set_name=precedents.SET_CORPUS, entries=()):
        self._block = block_value
        self._ids = tuple(ids)
        self.set_name = set_name
        self.entries = tuple(entries)
        self.chain_head = "a" * 64
        self.calls = []

    def configuration(self):
        return {"chain_head": self.chain_head, "note_sha256": precedents.note_sha256()}

    def block_for(self, brief_object, referee_result, *, case_no, dispute_id):
        self.calls.append((case_no, dispute_id))
        return self._block, self._ids


def run_pipeline_once(case, precedents_sentinel=OMIT, transport=None, claims=None):
    """One ``run_loaded_case`` over the scripted transport, at a fixed clock."""
    transport = transport_for() if transport is None else transport
    client = rig.client_factory(MODEL, transport)(lambda record: None)
    arguments = dict(
        prompts_dir=PROMPTS_DIR,
        now=lambda: FIXED_NOW,
        judge_votes=1,
    )
    if precedents_sentinel is not OMIT:
        arguments["precedents"] = precedents_sentinel
    return pipeline.run_loaded_case(case, client, **arguments)


def judge_messages(transport):
    """Every judge user message the transport was handed, parsed."""
    found = []
    for request in transport.requests:
        parsed = json.loads(request["messages"][1]["content"])
        if isinstance(parsed, dict) and "brief" in parsed and "claims" in parsed:
            found.append(parsed)
    return found


def precedents_run_dir(root, model=MODEL, subdir=None):
    base = Path(root) / "runs" if subdir is None else Path(root) / "runs" / subdir
    return base / runner.PRECEDENTS_DIRNAME / runner.model_slug(model)


# --------------------------------------------------------------------------
# The store
# --------------------------------------------------------------------------
class PrecedentStoreTests(unittest.TestCase):
    def test_an_entry_is_appended_and_read_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(store_dir(tmp), [entry()])
            read = precedents.read_entries(precedents.store_path(store))
            self.assertEqual(1, len(read))
            self.assertEqual(entry(), read[0])

    def test_an_empty_store_has_a_head_that_is_a_value_and_not_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            head = precedents.chain_head(precedents.store_path(store_dir(tmp)))
            self.assertEqual(events.GENESIS, head)
            self.assertIsNotNone(head)

    def test_the_chain_head_moves_with_each_entry_and_the_chain_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_dir(tmp)
            first = precedents.chain_head(precedents.store_path(store))
            write_entries(store, [entry("P-0001")])
            second = precedents.chain_head(precedents.store_path(store))
            write_entries(store, [entry("P-0002", case_no=103)])
            third = precedents.chain_head(precedents.store_path(store))
            self.assertEqual(3, len({first, second, third}))
            self.assertIsNone(events.verify_chain(precedents.store_path(store)))

    def test_the_store_is_append_only_so_the_first_line_never_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(store_dir(tmp), [entry("P-0001")])
            path = precedents.store_path(store)
            before = path.read_bytes().split(b"\n")[0]
            precedents.append_entry(entry("P-0002", case_no=103), store=store)
            after = path.read_bytes().split(b"\n")[0]
            self.assertEqual(before, after)
            self.assertEqual(2, len(precedents.read_entries(path)))

    def test_an_edit_to_a_line_is_reported_at_that_line(self):
        # The dirty fixture: the chain is seen to fail before it is seen to
        # pass. An entry's own bytes are rewritten and the verifier names the
        # line that was touched rather than the one after it.
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(store_dir(tmp), [entry("P-0001")])
            path = precedents.store_path(store)
            lines = path.read_text(encoding="utf-8").splitlines()
            body = json.loads(lines[0], parse_float=Decimal)
            body["summary"] = "An edit that the chain should notice."
            lines[0] = canonical(body)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            broken = events.verify_chain(path)
            self.assertIsNotNone(broken)
            self.assertEqual(1, broken.line_number)
            self.assertEqual("content", broken.kind)

    def test_the_reserved_fields_do_not_become_part_of_the_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(store_dir(tmp), [entry()])
            read = precedents.read_entries(precedents.store_path(store))
            self.assertEqual(set(ENTRY_FIELDS), set(read[0]))
            for name in events.RESERVED_FIELDS:
                self.assertNotIn(name, read[0])

    def test_an_event_that_is_not_a_closure_is_not_an_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = store_dir(tmp)
            log = events.EventLog(
                precedents.store_path(store), invocation_id="a-test"
            )
            log.record(events.EVENT_CASE_START, case_no=101)
            write_entries(store, [entry()])
            self.assertEqual(1, len(precedents.read_entries(precedents.store_path(store))))

    def test_the_ids_run_in_order_and_a_junk_id_is_ignored(self):
        self.assertEqual("P-0001", precedents.next_precedent_id([]))
        self.assertEqual(
            "P-0002", precedents.next_precedent_id([entry("P-0001")])
        )
        self.assertEqual(
            "P-0010", precedents.next_precedent_id([entry("P-0009")])
        )
        self.assertEqual(
            "P-0002",
            precedents.next_precedent_id([entry("not-an-id"), entry("P-0001")]),
        )

    def test_only_the_latest_entry_per_source_case_is_offered(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(
                store_dir(tmp),
                [entry("P-0001"), entry("P-0002"), entry("P-0003", case_no=103)],
            )
            entries = precedents.read_entries(precedents.store_path(store))
            latest = precedents.latest_by_source(entries)
            self.assertEqual(["P-0002", "P-0003"], [item["precedent_id"] for item in latest])

    def test_a_superseded_entry_stays_in_the_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(
                store_dir(tmp),
                [entry("P-0001"), entry("P-0002", supersedes="P-0001")],
            )
            entries = precedents.read_entries(precedents.store_path(store))
            self.assertEqual(2, len(entries))
            self.assertEqual("P-0001", entries[1]["supersedes"])


class PrecedentEntryTests(unittest.TestCase):
    """An entry may not carry a name that would let an answer into the store."""

    def refuse(self, bad):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(precedents.PrecedentError):
                precedents.append_entry(bad, store=store_dir(tmp))

    def test_the_forbidden_names_are_the_loaders_plus_the_graders_vocabulary(self):
        self.assertEqual(
            tuple(loader.FORBIDDEN_KEYS)
            + (
                "rationale",
                "difficulty",
                "governing_clauses",
                "matched",
                "expected",
                "grade",
            ),
            precedents.FORBIDDEN_FIELD_NAMES,
        )

    def test_every_forbidden_name_is_refused_at_the_top_level(self):
        for name in precedents.FORBIDDEN_FIELD_NAMES:
            with self.subTest(name=name):
                self.refuse(dict(entry(), **{name: "anything"}))

    def test_a_forbidden_name_is_refused_wherever_it_sits(self):
        for name in ("matched", "expected", "grade", "rationale"):
            with self.subTest(name=name):
                nested = entry()
                nested["decision"] = dict(nested["decision"], **{name: True})
                self.refuse(nested)

                deeper = entry()
                deeper["source"] = dict(deeper["source"], extra=[{name: 1}])
                self.refuse(deeper)

    def test_a_clean_entry_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            precedents.append_entry(entry(), store=store_dir(tmp))
            self.assertEqual(
                1, len(precedents.read_entries(precedents.store_path(store_dir(tmp))))
            )

    def test_the_reader_takes_five_fields_from_a_case_file_and_no_sixth(self):
        # ``matched`` is the grade, and a library built from grades would be
        # built from the answer key. The file is read as a whole and narrowed,
        # so what is read is one list in one place.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case-00101.json"
            path.write_text(
                canonical(
                    {
                        "case_no": TARGET_CASE,
                        "ruling": {"ruling": {"ruling": "NO_ACTION"}},
                        "brief_sha256": "b" * 64,
                        "development_set": None,
                        "configuration": {"policy_version": 1},
                        "matched": True,
                        "expected": "PARTIAL_REFUND",
                        "events": ["a log line"],
                    }
                ),
                encoding="utf-8",
            )
            document = precedents.read_case_document(path)
            self.assertEqual(set(CASE_FIELDS_READ), set(document))

    def test_a_missing_case_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(precedents.PrecedentError):
                precedents.read_case_document(Path(tmp) / "case-00101.json")


# --------------------------------------------------------------------------
# Closing a case
# --------------------------------------------------------------------------
class CliCloseTests(unittest.TestCase):
    """``close`` stores one decision, and refuses every case it cannot store."""

    def closed_run(self, tmp, cases=(TARGET_CASE,)):
        """A real run directory over the scripted transport, so a case file exists."""
        rig.bench(tmp, cases=cases)
        return rig.run_dir_of(tmp)

    def wild_run(self, tmp, cases=(WILD_CASE,)):
        """A run of the held-out set's own cases, under ``runs/wild/<model>/``.

        The set is the held-out set's, so the run directory's *shape* is what a
        test asks about: the cases, the key and the loader are that set's own and
        nothing here reads the committed held-out run.
        """
        held_out = development_sets.named("wild")
        runs_dir = Path(tmp) / "runs" / held_out.runs_subdir
        rig.bench(
            tmp,
            cases=cases,
            runs_dir=runs_dir,
            key=held_out.key(),
            case_loader=held_out.load_case,
            label=held_out.name,
            key_path=held_out.key_path,
        )
        return runner.run_directory(runs_dir, MODEL)

    def close(self, tmp, run_dir, arguments=(), **options):
        command = [
            "--store",
            str(store_dir(tmp)),
            "close",
            "--run-dir",
            str(run_dir),
            "--case",
            str(options.get("case", TARGET_CASE)),
            "--ruling",
            options.get("ruling", "PARTIAL_REFUND"),
            "--clause",
            options.get("clause", RD_02),
            "--closed-by",
            options.get("closed_by", "A Reviewer"),
            "--summary",
            options.get("summary", "A reviewer closed this case."),
        ]
        for extra in options.get("extra", ()):
            command.extend(extra)
        command.extend(arguments)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = precedents.main(command)
        return code, out.getvalue(), err.getvalue()

    def test_a_closure_is_stored_and_can_be_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            code, out, _err = self.close(tmp, run_dir)
            self.assertEqual(0, code)
            self.assertIn("P-0001", out)

            entries = precedents.read_entries(precedents.store_path(store_dir(tmp)))
            self.assertEqual(1, len(entries))
            stored = entries[0]
            self.assertEqual(set(ENTRY_FIELDS), set(stored))
            self.assertEqual("PARTIAL_REFUND", stored["decision"]["ruling"])
            self.assertEqual([RD_02], stored["clause_ids"])
            self.assertEqual("A Reviewer", stored["closed_by"])
            self.assertEqual("corpus", stored["source"]["set"])
            self.assertEqual(TARGET_CASE, stored["source"]["case_no"])
            self.assertEqual("DSP-00101", stored["source"]["dispute_id"])
            self.assertEqual("ROUTE_DEVIATION", stored["category"])
            self.assertEqual(Decimal("10.0"), stored["amount_contested_sgd"])
            self.assertEqual(1, stored["policy_version"])
            self.assertIsNone(stored["supersedes"])
            # The system's own outcome, read out of the case file one level down.
            self.assertEqual(
                {"ruling", "amount_sgd", "driver_compensation_sgd", "referrals"},
                set(stored["system_outcome"]),
            )

            with contextlib.redirect_stdout(io.StringIO()) as listing:
                self.assertEqual(
                    0, precedents.main(["--store", str(store_dir(tmp)), "list"])
                )
            self.assertIn("P-0001", listing.getvalue())
            self.assertIn("1 entry", listing.getvalue())

    def test_verify_says_the_chain_is_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            self.close(tmp, run_dir)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = precedents.main(["--store", str(store_dir(tmp)), "verify"])
            self.assertEqual(0, code)
            self.assertIn("intact", out.getvalue())

    def test_an_absent_case_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "runs" / runner.model_slug(MODEL)
            run_dir.mkdir(parents=True)
            code, _out, err = self.close(tmp, run_dir)
            self.assertEqual(1, code)
            self.assertIn("FATAL", err)

    def test_a_wild_shaped_run_closes_against_the_held_out_sets_loader(self):
        """``close`` on ``runs/wild/<model>/`` reads the case the run actually ran.

        ``close`` derives the set from the run directory's own path and loads the
        case through that set's loader. The held-out set's cases are not in the
        corpus manifest, so a wild run read as the corpus cannot find its own
        case and every closure of it fails with ``CaseNotFoundError``. The set
        the closure records is the one the path names.
        """
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.wild_run(tmp)
            code, out, err = self.close(tmp, run_dir, case=WILD_CASE)
            self.assertEqual(0, code, err)
            self.assertIn("P-0001", out)

            entries = precedents.read_entries(precedents.store_path(store_dir(tmp)))
            self.assertEqual(1, len(entries))
            self.assertEqual("wild", entries[0]["source"]["set"])
            self.assertEqual(WILD_CASE, entries[0]["source"]["case_no"])

    def test_a_brief_that_does_not_rebuild_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            case_file = runner.case_cache_path(run_dir, TARGET_CASE)
            document = runner.read_json(case_file)
            document["brief_sha256"] = "c" * 64
            runner.write_json(case_file, document)

            code, _out, err = self.close(tmp, run_dir)
            self.assertEqual(1, code)
            self.assertIn("does not rebuild", err)
            self.assertEqual(
                0, len(precedents.read_entries(precedents.store_path(store_dir(tmp))))
            )

    def test_a_ruling_the_policy_does_not_license_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            code, _out, err = self.close(tmp, run_dir, ruling="BANANA")
            self.assertEqual(1, code)
            self.assertIn("POL-GEN-03", err)

    def test_escalate_is_refused_because_it_is_the_absence_of_a_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            code, _out, err = self.close(tmp, run_dir, ruling="ESCALATE")
            self.assertEqual(1, code)
            self.assertIn("ESCALATE", err)

    def test_an_amount_with_more_than_two_places_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            code, _out, err = self.close(
                tmp, run_dir, extra=[("--amount", "1.234")]
            )
            self.assertEqual(1, code)
            self.assertIn("two decimal places", err)

    def test_an_amount_that_is_not_a_decimal_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            code, _out, err = self.close(
                tmp, run_dir, extra=[("--amount", "not-a-number")]
            )
            self.assertEqual(1, code)
            self.assertIn("not a decimal", err)

    def test_a_clause_that_does_not_resolve_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            code, _out, err = self.close(tmp, run_dir, clause=UNRESOLVABLE)
            self.assertEqual(1, code)
            self.assertIn("does not resolve", err)

    def test_a_clause_that_is_not_a_clause_id_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            code, _out, err = self.close(tmp, run_dir, clause="banana")
            self.assertEqual(1, code)
            self.assertIn("not a clause id", err)

    def test_a_referral_whose_leading_clause_does_not_resolve_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            code, _out, err = self.close(
                tmp,
                run_dir,
                extra=[("--referral", "{0}(1) the driver should be asked".format(UNRESOLVABLE))],
            )
            self.assertEqual(1, code)
            self.assertIn("leads with", err)

    def test_a_referral_that_leads_with_a_real_clause_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            code, _out, _err = self.close(
                tmp,
                run_dir,
                extra=[("--referral", "{0}(1) the driver should be asked".format(RD_06))],
            )
            self.assertEqual(0, code)
            stored = precedents.read_entries(precedents.store_path(store_dir(tmp)))[0]
            self.assertEqual(
                ["{0}(1) the driver should be asked".format(RD_06)],
                stored["decision"]["referrals"],
            )

    def test_an_empty_summary_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            code, _out, err = self.close(tmp, run_dir, summary="   ")
            self.assertEqual(1, code)
            self.assertIn("summary", err)

    def test_a_summary_over_the_limit_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            too_long = "x" * (precedents.MAX_SUMMARY_CHARS + 1)
            code, _out, err = self.close(tmp, run_dir, summary=too_long)
            self.assertEqual(1, code)
            self.assertIn(str(precedents.MAX_SUMMARY_CHARS), err)

    def test_a_second_closure_of_one_case_needs_supersedes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            self.assertEqual(0, self.close(tmp, run_dir)[0])

            code, _out, err = self.close(tmp, run_dir)
            self.assertEqual(1, code)
            self.assertIn("--supersedes", err)

            code, _out, _err = self.close(
                tmp, run_dir, extra=[("--supersedes", "P-0001")]
            )
            self.assertEqual(0, code)
            entries = precedents.read_entries(precedents.store_path(store_dir(tmp)))
            self.assertEqual(["P-0001", "P-0002"], [item["precedent_id"] for item in entries])
            self.assertEqual("P-0001", entries[1]["supersedes"])
            # And only the later one is what a run would be shown.
            self.assertEqual(
                ["P-0002"],
                [item["precedent_id"] for item in precedents.latest_by_source(entries)],
            )

    def test_supersedes_naming_something_else_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.closed_run(tmp)
            self.close(tmp, run_dir)
            code, _out, err = self.close(
                tmp, run_dir, extra=[("--supersedes", "P-9999")]
            )
            self.assertEqual(1, code)
            self.assertIn("already has a closure", err)

    def test_a_closure_of_the_second_set_reads_its_own_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = transport_for(development_sets.SECOND_SET.key())
            development_sets.run_set(
                development_sets.SECOND_SET,
                MODEL,
                runs_dir=Path(tmp) / "runs",
                cases=(9101,),
                prompts_dir=PROMPTS_DIR,
                client_factory=rig.client_factory(MODEL, transport),
                git_runner=rig.git_runner(),
                progress=lambda text: None,
                judge_votes=1,
            )
            run_dir = Path(tmp) / "runs" / "codex" / runner.model_slug(MODEL)
            self.assertTrue(runner.case_cache_path(run_dir, 9101).is_file())

            code, _out, err = self.close(
                tmp, run_dir, case=9101, ruling="NO_ACTION", clause=NS_02
            )
            self.assertEqual(0, code, err)
            stored = precedents.read_entries(precedents.store_path(store_dir(tmp)))[0]
            self.assertEqual("codex", stored["source"]["set"])
            self.assertEqual(9101, stored["source"]["case_no"])


# --------------------------------------------------------------------------
# The matching rule
# --------------------------------------------------------------------------
class MatchingTests(unittest.TestCase):
    """Seven steps, exercised one at a time."""

    def setUp(self):
        self.brief = brief.build_brief_for_case(loader.load_case(TARGET_CASE))

    def choose(self, entries, kept=(RD_02,), category="ROUTE_DEVIATION", amount="10.0",
               case_no=TARGET_CASE, dispute_id="DSP-00101", set_name=precedents.SET_CORPUS):
        return precedents.matches(
            entries,
            brief_object=self.brief,
            kept_clause_ids_=kept,
            category=category,
            amount_contested=Decimal(amount) if amount is not None else None,
            case_no=case_no,
            dispute_id=dispute_id,
            set_name=set_name,
        )

    def ids(self, chosen):
        return [item["precedent_id"] for item in chosen]

    def test_an_entry_sharing_a_kept_clause_is_chosen(self):
        self.assertEqual(["P-0001"], self.ids(self.choose([entry()])))

    def test_an_entry_sharing_no_kept_clause_is_not_chosen(self):
        # The kept clause is RD_02; the entry rests on RD_06, which resolves but
        # is not one of the clauses a kept claim cites.
        self.assertEqual([], self.choose([entry(clause_ids=(RD_06,))]))

    def test_an_entry_of_another_category_is_not_chosen(self):
        self.assertEqual(
            [], self.choose([entry(category="NO_SHOW_CHARGE")])
        )

    def test_the_case_being_judged_is_excluded_by_set_and_case_number(self):
        same = entry(case_no=TARGET_CASE, dispute_id="DSP-99999")
        self.assertEqual([], self.choose([same]))

    def test_the_case_being_judged_is_excluded_by_dispute_id(self):
        same = entry(case_no=999, dispute_id="DSP-00101")
        self.assertEqual([], self.choose([same]))

    def test_an_entry_resting_on_a_clause_that_does_not_resolve_is_excluded(self):
        self.assertEqual(
            [], self.choose([entry(clause_ids=(RD_02, UNRESOLVABLE))])
        )

    def test_an_entry_resting_on_no_clause_at_all_is_excluded(self):
        self.assertEqual([], self.choose([entry(clause_ids=())]))

    def test_an_entry_resting_on_an_id_that_is_not_a_clause_is_excluded_whole(self):
        # It shares RD_02 with the kept claim and also rests on a string that is
        # not a clause id. Dropping the bad id would have chosen it -- on a
        # shorter clause list than the one a human closed it on, and with a
        # different score, because the score is how many of its ids a kept claim
        # cites.
        self.assertEqual(
            [], self.choose([entry(clause_ids=(RD_02, "not-a-clause-id"))])
        )

    def test_the_ranking_is_by_how_many_kept_clauses_are_shared(self):
        one = entry("P-0001", case_no=201, clause_ids=(RD_02,))
        two = entry("P-0002", case_no=202, clause_ids=(RD_01, RD_02))
        chosen = self.choose([one, two], kept=(RD_01, RD_02))
        self.assertEqual(["P-0002", "P-0001"], self.ids(chosen))

    def test_ties_break_on_the_relative_amount_difference(self):
        far = entry("P-0001", case_no=201, amount="100.0")
        near = entry("P-0002", case_no=202, amount="11.0")
        chosen = self.choose([far, near], amount="10.0")
        self.assertEqual(["P-0002", "P-0001"], self.ids(chosen))

    def test_a_zero_contested_amount_falls_back_to_the_absolute_difference(self):
        # ``|a-b|/b`` against zero is not a number, so the absolute difference
        # decides instead. The arithmetic is in Decimal, so 1.1 and 0.9 are not
        # equal and the order is not a floating-point accident.
        close = entry("P-0001", case_no=201, amount="0.9")
        far = entry("P-0002", case_no=202, amount="1.1")
        chosen = self.choose([far, close], amount="0")
        self.assertEqual(["P-0001", "P-0002"], self.ids(chosen))

    def test_an_equal_amount_breaks_the_tie_on_the_earlier_entry(self):
        first = entry("P-0001", case_no=201, amount="10.0")
        second = entry("P-0002", case_no=202, amount="10.0")
        self.assertEqual(["P-0001", "P-0002"], self.ids(self.choose([first, second])))

    def test_the_tie_break_is_the_chosen_entry_s_own_position_in_the_log(self):
        # Case 201 is closed twice: the first entry is superseded by the third,
        # so 201's *chosen* entry is written after case 202's. With equal scores
        # the earlier line wins, and that is 202's entry. Ordering by where each
        # source case first appeared would have put 201 first instead, because
        # 201's case number is the first one the log names.
        superseded = entry("P-0001", case_no=201, clause_ids=(RD_06,))
        other = entry("P-0002", case_no=202, amount="10.0")
        chosen = entry("P-0003", case_no=201, amount="10.0")
        self.assertEqual(
            ["P-0002", "P-0003"], self.ids(self.choose([superseded, other, chosen]))
        )

    def test_at_most_three_are_chosen(self):
        entries = [
            entry("P-000{0}".format(n), case_no=200 + n, amount="10.0")
            for n in range(1, 6)
        ]
        self.assertEqual(3, len(self.choose(entries)))

    def test_the_latest_entry_per_source_is_the_one_scored(self):
        old = entry("P-0001", case_no=201, clause_ids=(RD_02,))
        new = entry("P-0002", case_no=201, clause_ids=(RD_06,))
        # The later entry for that source shares nothing, so nothing is chosen:
        # the earlier one is superseded rather than considered alongside it.
        self.assertEqual([], self.choose([old, new]))

    def test_the_choice_is_deterministic_under_a_shuffled_store(self):
        entries = [
            entry("P-0001", case_no=201, amount="12.0"),
            entry("P-0002", case_no=202, amount="10.0"),
            entry("P-0003", case_no=203, amount="14.0"),
        ]
        straight = self.ids(self.choose(entries))
        self.assertEqual(
            straight, self.ids(self.choose(list(reversed(entries))))
        )
        self.assertEqual(["P-0002", "P-0001", "P-0003"], straight)

    def test_the_kept_clauses_are_read_off_the_referee_and_sorted(self):
        stub = StubReferee(rider=(RD_02, RD_02, "not-a-clause"), driver=(RD_01,))
        self.assertEqual((RD_01, RD_02), precedents.kept_clause_ids(stub))
        self.assertEqual((), precedents.kept_clause_ids(object()))

    def test_a_limb_is_dropped_before_matching(self):
        self.assertEqual(RD_02, precedents.base_clause_id("{0}(b)".format(RD_02)))
        self.assertEqual(RD_02, precedents.base_clause_id(RD_02))
        for value in ("banana", "POL-RD-2", "POLRD02", "", None, 7):
            with self.subTest(value=value):
                self.assertIsNone(precedents.base_clause_id(value))

    def test_block_for_returns_nothing_when_nothing_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(store_dir(tmp), [entry(category="NO_SHOW_CHARGE")])
            library = precedents.Library.load(store)
            block, ids = library.block_for(
                self.brief,
                StubReferee(rider=(RD_02,)),
                case_no=TARGET_CASE,
                dispute_id="DSP-00101",
            )
            self.assertIsNone(block)
            self.assertEqual((), ids)

    def test_block_for_returns_the_block_and_the_ids_when_something_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(store_dir(tmp), [entry("P-0001")])
            library = precedents.Library.load(store)
            block, ids = library.block_for(
                self.brief,
                StubReferee(rider=(RD_02,)),
                case_no=TARGET_CASE,
                dispute_id="DSP-00101",
            )
            self.assertEqual(("P-0001",), ids)
            self.assertEqual(precedents.NOTE, block["note"])
            self.assertEqual(1, len(block["items"]))


class BlockShapeTests(unittest.TestCase):
    """What the judge sees: a fixed note, and no amount and no summary."""

    def test_the_item_carries_exactly_four_fields(self):
        items = precedents.block([entry()])["items"]
        self.assertEqual(
            {"precedent_id", "category", "clause_ids", "ruling"}, set(items[0])
        )
        self.assertEqual("P-0001", items[0]["precedent_id"])
        self.assertEqual("ROUTE_DEVIATION", items[0]["category"])
        self.assertEqual([RD_02], items[0]["clause_ids"])
        self.assertEqual("PARTIAL_REFUND", items[0]["ruling"])

    def test_no_amount_and_no_summary_travel_in_the_block(self):
        # Asserted over the parsed block rather than over its text: a figure in
        # the block would be a figure to copy, and a summary is prose about a
        # different case.
        block = precedents.block([entry(amount="1234.56")])
        leaves = []

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    leaves.append(("key", key))
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
            else:
                leaves.append(("leaf", node))

        walk(block)
        self.assertNotIn("summary", [value for kind, value in leaves if kind == "key"])
        self.assertNotIn(
            "amount_contested_sgd", [value for kind, value in leaves if kind == "key"]
        )
        for kind, value in leaves:
            if kind == "leaf":
                self.assertNotIsInstance(value, Decimal)

    def test_the_block_carries_at_most_three_items(self):
        entries = [entry("P-000{0}".format(n)) for n in range(1, 6)]
        self.assertEqual(3, len(precedents.block(entries)["items"]))

    def test_the_note_is_fixed_text_in_code_and_says_what_it_is(self):
        # Not evidence and not policy, and the judge is told to rest its
        # findings on this case's own ids. The note is one constant, so the
        # digest recorded in a run's configuration is a digest of this text.
        self.assertEqual(precedents.NOTE, precedents.block([])["note"])
        self.assertTrue(precedents.NOTE.strip())
        self.assertIn("not evidence", precedents.NOTE)
        self.assertIn("clause ids", precedents.NOTE)
        self.assertIn("precedent", precedents.NOTE)
        self.assertEqual(
            precedents.note_sha256(),
            precedents.library_document(store=None)["note_sha256"],
        )


# --------------------------------------------------------------------------
# The pipeline: the key, and the switch off
# --------------------------------------------------------------------------
class PipelinePrecedentsTests(unittest.TestCase):
    def test_the_key_is_absent_with_the_switch_off(self):
        transport = transport_for()
        run_pipeline_once(loader.load_case(TARGET_CASE), transport=transport)
        messages = judge_messages(transport)
        self.assertEqual(1, len(messages))
        self.assertEqual({"brief", "claims", "referee"}, set(messages[0]))

    def test_a_library_that_matches_nothing_shows_the_judge_the_same_bytes(self):
        """The judge's message is unchanged; the record now says ``[]``.

        The switch on with nothing matched wrote no ``precedents_shown`` key on
        the transcript while the case file wrote ``[]`` -- two records of one
        case disagreeing about whether the question had been asked. What must
        not change is the judge's message, and it does not: with nothing
        matching there is no ``precedents`` key on it, byte for byte, exactly as
        with the switch off.
        """
        case = loader.load_case(TARGET_CASE)
        plain_transport = transport_for()
        empty_transport = transport_for()
        with claiming(claims_citing(TARGET_CASE)):
            plain = run_pipeline_once(case, transport=plain_transport)
            empty = run_pipeline_once(
                case, precedents_sentinel=StubLibrary(), transport=empty_transport
            )
        plain_message = judge_messages(plain_transport)[0]
        empty_message = judge_messages(empty_transport)[0]
        self.assertEqual(canonical(plain_message), canonical(empty_message))
        self.assertNotIn("precedents", plain_message)
        self.assertNotIn("precedents", empty_message)
        # The switch off: no key at all, which is the bytes it always wrote.
        self.assertNotIn("precedents_shown", plain.transcript.as_dict())
        self.assertIsNone(plain.precedents_shown)
        # The switch on with nothing matched: an empty list, which is what the
        # case file writes for the same case.
        self.assertEqual([], empty.transcript.as_dict()["precedents_shown"])
        self.assertEqual((), empty.precedents_shown)

    def test_the_key_is_present_and_canonically_ordered_when_a_block_is_shown(self):
        block = precedents.block([entry("P-0001")])
        library = StubLibrary(block_value=block, ids=("P-0001",))
        transport = transport_for()
        with claiming(claims_citing(TARGET_CASE)):
            result = run_pipeline_once(
                loader.load_case(TARGET_CASE),
                precedents_sentinel=library,
                transport=transport,
            )
        messages = judge_messages(transport)
        self.assertEqual(1, len(messages))
        self.assertEqual(
            ["brief", "claims", "precedents", "referee"], list(messages[0])
        )
        self.assertEqual(block, messages[0]["precedents"])
        self.assertEqual(("P-0001",), result.precedents_shown)
        self.assertEqual(
            ["P-0001"], result.transcript.as_dict()["precedents_shown"]
        )
        self.assertEqual([(TARGET_CASE, "DSP-00101")], library.calls)

    def test_the_block_is_chosen_after_the_referee_has_kept_its_claims(self):
        # The matching rests on the clauses the referee kept, so a library that
        # answered before the referee ran could not answer at all. The stub
        # records the order by refusing to be asked twice.
        library = StubLibrary(block_value=precedents.block([entry()]), ids=("P-0001",))
        transport = transport_for()
        with claiming(claims_citing(TARGET_CASE)):
            run_pipeline_once(
                loader.load_case(TARGET_CASE),
                precedents_sentinel=library,
                transport=transport,
            )
        self.assertEqual(1, len(library.calls))

    def test_a_forbidden_key_in_a_block_is_refused_at_runtime(self):
        # Two boundaries, and they know different lists. The library refuses its
        # own names -- ``matched`` among them -- when it writes an entry. This
        # test is the other one: the parsed judge message is walked by
        # ``brief._assert_no_forbidden_keys``, which knows the five
        # ``loader.FORBIDDEN_KEYS``. So the spliced name has to be one of those
        # five, or the walk would pass and prove nothing.
        spliced = {
            "note": precedents.NOTE,
            "items": [
                {
                    "precedent_id": "P-0001",
                    "category": "ROUTE_DEVIATION",
                    "clause_ids": [RD_02],
                    "ruling": "PARTIAL_REFUND",
                    "ground_truth": "PARTIAL_REFUND",
                }
            ],
        }
        library = StubLibrary(block_value=spliced, ids=("P-0001",))
        transport = transport_for()
        with claiming(claims_citing(TARGET_CASE)):
            with self.assertRaises(loader.ForbiddenKeyError):
                run_pipeline_once(
                    loader.load_case(TARGET_CASE),
                    precedents_sentinel=library,
                    transport=transport,
                )

    def test_a_run_with_a_real_library_matches_end_to_end(self):
        # The whole path: a store holding one closure for case 102, a claim for
        # case 101 that cites the same clause, and the block that comes out.
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(store_dir(tmp), [entry("P-0001", case_no=SOURCE_CASE)])
            library = precedents.Library.load(store)
            transport = transport_for()
            with claiming(claims_citing(TARGET_CASE)):
                result = run_pipeline_once(
                    loader.load_case(TARGET_CASE),
                    precedents_sentinel=library,
                    transport=transport,
                )
            self.assertEqual(("P-0001",), result.precedents_shown)
            message = judge_messages(transport)[0]
            self.assertEqual(
                [{"precedent_id": "P-0001",
                  "category": "ROUTE_DEVIATION",
                  "clause_ids": [RD_02],
                  "ruling": "PARTIAL_REFUND"}],
                message["precedents"]["items"],
            )


# --------------------------------------------------------------------------
# Where a run with the switch on writes
# --------------------------------------------------------------------------
class SetFromRunDirectoryTests(unittest.TestCase):
    """Which set a run directory belongs to, and where its cases are loaded from.

    The set is derived from the run directory's own path, and nothing from
    ``eval/`` may be imported into ``tribunal/``, so this module's table and the
    set registry in ``eval.development_sets`` are two statements of one layout.
    Both are asserted here, which is what keeps them from drifting: a set whose
    cases are loaded from the wrong directory is a set whose briefs are rebuilt
    from cases that did not run.
    """

    def test_every_registered_set_is_derived_from_its_own_component(self):
        for development_set in (
            development_sets.DEVELOPMENT_SETS
            + development_sets.SEALED_SETS
            + development_sets.RERUN_SETS
        ):
            if development_set.runs_subdir is None:
                continue
            with self.subTest(development_set=development_set.name):
                run_dir = Path("/tmp/runs") / development_set.runs_subdir / "a-model"
                self.assertEqual(
                    development_set.name, precedents.set_from_run_directory(run_dir)
                )

    def test_every_registered_set_is_filed_under_the_directory_it_loads_from(self):
        for development_set in (
            development_sets.DEVELOPMENT_SETS
            + development_sets.SEALED_SETS
            + development_sets.RERUN_SETS
        ):
            if development_set.case_root is None:
                continue
            with self.subTest(development_set=development_set.name):
                self.assertEqual(
                    development_set.case_root,
                    loader.EXTERNAL_DIR / precedents.EXTERNAL_SET_DIRS[development_set.name],
                )

    def test_the_corpus_is_the_fallback(self):
        """A run directory naming no set is the corpus, whatever else it holds.

        The corpus's own run directory carries no component of its own, and every
        switched run lives under a directory of its own: read as a set, an
        ablated run's cases would be loaded from the wrong place.
        """
        for run_dir in (
            Path("/tmp/runs/a-model"),
            Path("/tmp/runs/precedents/a-model"),
            Path("/tmp/runs/ablation/no_precedents/a-model"),
            Path("/tmp/runs/policy-v2/a-model"),
            Path("/tmp/runs/amount-rule/signed/a-model"),
        ):
            with self.subTest(run_dir=str(run_dir)):
                self.assertEqual(
                    precedents.SET_CORPUS, precedents.set_from_run_directory(run_dir)
                )

    def test_the_two_wild_sets_are_told_apart_and_share_one_case_directory(self):
        """``wild-dev`` records itself and loads the held-out set's own cases."""
        wild = Path("/tmp/runs") / precedents.SET_WILD / "a-model"
        wild_dev = Path("/tmp/runs") / precedents.SET_WILD_DEV / "a-model"
        self.assertEqual(precedents.SET_WILD, precedents.set_from_run_directory(wild))
        self.assertEqual(
            precedents.SET_WILD_DEV, precedents.set_from_run_directory(wild_dev)
        )
        self.assertEqual(
            precedents.EXTERNAL_SET_DIRS[precedents.SET_WILD],
            precedents.EXTERNAL_SET_DIRS[precedents.SET_WILD_DEV],
        )

    def test_a_wild_shaped_run_loads_the_held_out_sets_own_case(self):
        run_dir = Path("/tmp/runs") / precedents.SET_WILD / "a-model"
        case = precedents.load_case_for_run(run_dir, WILD_CASE)
        self.assertEqual(WILD_CASE, case["case_no"])

    def test_a_corpus_shaped_run_loads_the_manifest(self):
        run_dir = Path("/tmp/runs/a-model")
        case = precedents.load_case_for_run(run_dir, TARGET_CASE)
        self.assertEqual(TARGET_CASE, case["case_no"])


class RunDestinationTests(unittest.TestCase):
    def test_the_precedents_directory_is_built_from_the_runs_root(self):
        runs = Path("/tmp/scratch/runs")
        self.assertEqual(
            runs / "precedents" / "deepseek-deepseek-flash",
            runner.precedents_run_directory(runs, "deepseek/deepseek-flash"),
        )

    def test_the_precedents_directory_is_not_the_plain_run_directory(self):
        runs = Path("/tmp/scratch/runs")
        self.assertNotEqual(
            runner.run_directory(runs, MODEL),
            runner.precedents_run_directory(runs, MODEL),
        )

    def test_the_destination_guard_fails_on_a_dirty_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            dirty = runner.run_directory(runs, MODEL)
            with self.assertRaises(runner.BenchmarkError):
                runner.assert_precedents_destination(dirty, runs, MODEL)
            # The held-out set's run directory is a headline one too, so a
            # precedents run must not be able to land there either.
            sealed = runs / runner.SEALED_SET_RUNS_SUBDIR / runner.model_slug(MODEL)
            with self.assertRaises(runner.BenchmarkError):
                runner.assert_precedents_destination(sealed, runs, MODEL)
            # And a name that climbs out of the precedents root, which is what
            # a ``..`` would be if the name were ever allowed to be one. It
            # climbs to the runs root, which is not a headline directory, so
            # what refuses it here is the precedents root rather than the
            # headline check that runs first.
            climbing = runner.precedents_run_directory(runs, MODEL) / ".." / ".."
            with self.assertRaises(runner.BenchmarkError) as caught:
                runner.assert_precedents_destination(climbing, runs, MODEL)
            self.assertIn("may only be written under", str(caught.exception))
            clean = runner.precedents_run_directory(runs, MODEL)
            self.assertEqual(
                clean, runner.assert_precedents_destination(clean, runs, MODEL)
            )

    def test_a_run_with_precedents_on_writes_under_its_own_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(store_dir(tmp), [entry("P-0001")])
            with claiming(claims_citing(TARGET_CASE)):
                summary, transport = rig.bench(
                    tmp, cases=(TARGET_CASE,), precedents=store
                )
            self.assertEqual([TARGET_CASE], summary.completed_cases)
            self.assertTrue(transport.calls() > 0)
            own = precedents_run_dir(tmp)
            self.assertTrue((own / "case-00101.json").is_file())
            self.assertTrue((own / "run.json").is_file())
            self.assertFalse(rig.run_dir_of(tmp).exists())

    def test_a_second_set_run_writes_under_the_sets_own_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(
                store_dir(tmp), [entry("P-0001", set_name=precedents.SET_CODEX)]
            )
            transport = transport_for(development_sets.SECOND_SET.key())
            summary = development_sets.run_set(
                development_sets.SECOND_SET,
                MODEL,
                runs_dir=Path(tmp) / "runs",
                cases=(9101,),
                prompts_dir=PROMPTS_DIR,
                client_factory=rig.client_factory(MODEL, transport),
                git_runner=rig.git_runner(),
                progress=lambda text: None,
                judge_votes=1,
                precedents=store,
            )
            self.assertEqual([9101], summary.completed_cases)
            own = precedents_run_dir(tmp, subdir="codex")
            self.assertTrue((own / "case-09101.json").is_file())
            self.assertFalse(
                (Path(tmp) / "runs" / "codex" / runner.model_slug(MODEL)).exists()
            )

    def test_the_runner_refuses_precedents_together_with_an_ablation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
            ):
                with self.assertRaises(runner.BenchmarkError):
                    rig.bench(
                        tmp,
                        cases=(TARGET_CASE,),
                        precedents=store_dir(tmp),
                        ablation=brief.ABLATION_CLAUSE_NOTES,
                    )

    def test_the_runner_refuses_precedents_together_with_a_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
            ):
                with self.assertRaises(runner.BenchmarkError):
                    rig.bench(
                        tmp,
                        cases=(TARGET_CASE,),
                        precedents=store_dir(tmp),
                        replay_dir=Path(tmp) / "runs" / runner.model_slug(MODEL),
                    )


class ConfigurationTests(unittest.TestCase):
    def test_a_run_with_precedents_on_records_the_chain_head_and_note_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(store_dir(tmp), [entry("P-0001")])
            head = precedents.chain_head(precedents.store_path(store))
            with claiming(claims_citing(TARGET_CASE)):
                rig.bench(tmp, cases=(TARGET_CASE,), precedents=store)
            run_dir = precedents_run_dir(tmp)
            for label, document in (
                ("run.json", runner.read_json(runner.metadata_path(run_dir))),
                ("case file", runner.read_json(runner.case_cache_path(run_dir, TARGET_CASE))),
            ):
                with self.subTest(artifact=label):
                    recorded = runner.configuration_of(document)["precedents"]
                    self.assertEqual(
                        {"chain_head": head, "note_sha256": precedents.note_sha256()},
                        recorded,
                    )
            history = runner.read_json(run_dir / runner.INVOCATIONS_FILE)
            for item in history:
                self.assertEqual(set(runner.CONFIGURATION_FIELDS), set(item["configuration"]))

    def test_a_plain_run_records_a_null_precedents(self):
        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(tmp, cases=(TARGET_CASE,))
            run_dir = rig.run_dir_of(tmp)
            for document in (
                runner.read_json(runner.metadata_path(run_dir)),
                runner.read_json(runner.case_cache_path(run_dir, TARGET_CASE)),
            ):
                self.assertIsNone(runner.configuration_of(document)["precedents"])
                self.assertNotIn("precedents_shown", document)


class StalenessPrecedentsTests(unittest.TestCase):
    def checker_for(self, run_dir, store):
        """The checker ``run_benchmark`` builds, over the library as it is now."""
        return runner.BriefStaleness(
            run_dir=run_dir,
            precedents=precedents.Library.load(store).configuration(),
        )

    def test_a_moved_library_makes_a_cached_case_stale_and_a_steady_one_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(store_dir(tmp), [entry("P-0001")])
            with claiming(claims_citing(TARGET_CASE)):
                rig.bench(tmp, cases=(TARGET_CASE,), precedents=store)
                run_dir = precedents_run_dir(tmp)

                # The same library: every case is found cached and current, so
                # the transport is never asked again and the third channel is
                # silent rather than merely empty.
                summary, transport = rig.bench(
                    tmp, cases=(TARGET_CASE,), precedents=store
                )
                self.assertEqual([], summary.completed_cases)
                self.assertEqual([TARGET_CASE], sorted(summary.cached_cases))
                self.assertEqual(0, transport.calls())
                document = runner.load_cached(run_dir, TARGET_CASE)
                steady = self.checker_for(run_dir, store)
                self.assertEqual((), steady.moved_for(TARGET_CASE, document))
                self.assertEqual(
                    runner.grade.STALENESS_CURRENT,
                    steady.status_of(TARGET_CASE, document),
                )

                # The dirty fixture: one more closure moves the chain head, so a
                # result produced against the earlier library is stale -- and the
                # channel names itself rather than leaving the reader to guess
                # which of the three digests moved.
                precedents.append_entry(entry("P-0002", case_no=103), store=store)
                moved = self.checker_for(run_dir, store)
                self.assertEqual(
                    (runner.grade.MOVED_PRECEDENTS,),
                    moved.moved_for(TARGET_CASE, document),
                )
                self.assertEqual(
                    runner.grade.STALENESS_STALE,
                    moved.status_of(TARGET_CASE, document),
                )

                # And the ordinary rule, which this channel joins rather than
                # replaces: a stale cached result is reported and reused, never
                # re-run behind the operator's back. The run below makes no call,
                # which is the half of the queue's "is stale and is re-run" that
                # is about this code; ``--force`` is the half that re-runs it.
                summary, transport = rig.bench(
                    tmp, cases=(TARGET_CASE,), precedents=store
                )
                self.assertEqual([], summary.completed_cases)
                self.assertEqual([TARGET_CASE], sorted(summary.cached_cases))
                self.assertEqual(0, transport.calls())

                summary, transport = rig.bench(
                    tmp, cases=(TARGET_CASE,), precedents=store, force=True
                )
                self.assertEqual([TARGET_CASE], summary.completed_cases)
                self.assertTrue(transport.calls() > 0)

    def test_the_third_channel_is_silent_when_the_switch_is_off(self):
        # ``None`` is what keeps a plain run's staleness reading exactly what it
        # was: the channel is silent rather than empty, so a case that recorded
        # no library at all is not stale for that reason.
        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(tmp, cases=(TARGET_CASE,))
            run_dir = rig.run_dir_of(tmp)
            checker = runner.BriefStaleness(run_dir=run_dir)
            document = runner.read_json(runner.case_cache_path(run_dir, TARGET_CASE))
            self.assertFalse(checker.precedents_moved(TARGET_CASE, document))

            switched = runner.BriefStaleness(
                run_dir=run_dir,
                precedents={"chain_head": "a" * 64, "note_sha256": precedents.note_sha256()},
            )
            self.assertTrue(switched.precedents_moved(TARGET_CASE, document))

    def test_a_moved_library_reaches_the_report_and_the_summary(self):
        """The channel has to survive the trip out of the checker.

        ``BriefStaleness.precedents_moved`` answered correctly from the day the
        channel was added, and the tests above prove it. What they could not see
        is that ``brief_staleness`` -- the function that turns the checker into
        the ``grade.Staleness`` a report is built from -- collected the brief and
        the prompt channels and not this one, so ``stale_precedents`` was ``()``
        in every report ever written and both lines asserted below were
        unreachable. A case could be stale for the library alone and the report
        would name no channel at all.
        """
        with tempfile.TemporaryDirectory() as tmp:
            store = write_entries(store_dir(tmp), [entry("P-0001")])
            with claiming(claims_citing(TARGET_CASE)):
                rig.bench(tmp, cases=(TARGET_CASE,), precedents=store)
                # One more closure moves the chain head, and nothing else moves:
                # the brief and the prompts are this code's, so the library is
                # the only channel this case is stale on.
                precedents.append_entry(entry("P-0002", case_no=103), store=store)
                summary, transport = rig.bench(
                    tmp, cases=(TARGET_CASE,), precedents=store
                )

            staleness = summary.report.staleness
            self.assertEqual((TARGET_CASE,), staleness.stale_precedents)
            self.assertEqual((), staleness.stale_brief)
            self.assertEqual((), staleness.stale_prompts)
            self.assertEqual((TARGET_CASE,), staleness.stale)

            # Reused, not re-run: a stale cached result is reported, and only
            # ``--force`` re-runs it.
            self.assertEqual([], summary.completed_cases)
            self.assertEqual([TARGET_CASE], sorted(summary.cached_cases))
            self.assertEqual(0, transport.calls())

            report_text = (precedents_run_dir(tmp) / runner.REPORT_FILE).read_text(
                encoding="utf-8"
            )
            self.assertIn("The precedent library has moved for 1 of 1", report_text)
            self.assertIn(str(TARGET_CASE), report_text)

            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                runner.print_summary(summary)
            self.assertIn("library moved: {0}".format(TARGET_CASE), printed.getvalue())

    def test_every_channel_that_can_move_has_a_phrase_of_its_own(self):
        # The progress line names which digest moved. A channel with no phrase
        # falls through to the fallback -- "produced by an earlier version of
        # this code" -- which is true of a moved brief and false of a moved
        # library, because the code did not move at all. The set is compared
        # rather than the one phrase, so a fourth channel cannot be added
        # without a phrase either.
        self.assertEqual(
            {
                runner.grade.MOVED_BRIEF,
                runner.grade.MOVED_PROMPTS,
                runner.grade.MOVED_PRECEDENTS,
            },
            {name for name, _phrase in runner._STALE_PHRASES},
        )
        self.assertEqual(
            "the library has moved",
            runner._describe_moved((runner.grade.MOVED_PRECEDENTS,)),
        )


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
class ReportingExclusionTests(unittest.TestCase):
    def run_it(self, tmp):
        store = write_entries(store_dir(tmp), [entry("P-0001", case_no=SOURCE_CASE)])
        with claiming(claims_citing(TARGET_CASE)):
            summary, _transport = rig.bench(
                tmp, cases=(TARGET_CASE, SOURCE_CASE), precedents=store
            )
        return summary

    def test_the_source_case_is_left_out_of_the_figures_and_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = self.run_it(tmp)
            self.assertEqual([SOURCE_CASE], summary.precedents_excluded)

            run_dir = precedents_run_dir(tmp)
            report = (run_dir / runner.REPORT_FILE).read_text(encoding="utf-8")
            self.assertIn(str(SOURCE_CASE), report)
            self.assertIn(runner.PRECEDENTS_INCOMPARABLE_NOTE, report)

    def test_the_printed_summary_says_the_figures_are_not_comparable(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = self.run_it(tmp)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                runner.print_summary(summary)
            text = out.getvalue()
            self.assertIn("precedents", text)
            self.assertIn(str(SOURCE_CASE), text)
            self.assertIn(runner.PRECEDENTS_INCOMPARABLE_NOTE, text)

    def test_a_plain_run_prints_no_precedents_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _transport = rig.bench(tmp, cases=(TARGET_CASE,))
            self.assertIsNone(summary.precedents_excluded)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                runner.print_summary(summary)
            self.assertNotIn("precedents", out.getvalue())

    def test_the_invocation_end_event_names_the_excluded_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_it(tmp)
            path = precedents_run_dir(tmp) / "events.jsonl"
            ends = [
                json.loads(line, parse_float=Decimal)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            ends = [item for item in ends if item.get("event") == events.EVENT_INVOCATION_END]
            self.assertEqual(1, len(ends))
            self.assertEqual([SOURCE_CASE], ends[0]["precedents_excluded"])

    def test_the_case_file_carries_the_ids_the_judge_was_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_it(tmp)
            run_dir = precedents_run_dir(tmp)
            document = runner.read_json(runner.case_cache_path(run_dir, TARGET_CASE))
            self.assertEqual(["P-0001"], document["precedents_shown"])
            source = runner.read_json(runner.case_cache_path(run_dir, SOURCE_CASE))
            self.assertEqual([], source["precedents_shown"])


# --------------------------------------------------------------------------
# Refusals on both command lines
# --------------------------------------------------------------------------
class RunBenchmarkCommandLineTests(unittest.TestCase):
    def refuse(self, arguments):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit):
                    runner.main(arguments)
        return errors.getvalue()

    def test_it_is_refused_with_every_mode_that_reads_or_replays_a_run(self):
        for arguments in (
            ["--precedents", "--ablate", brief.ABLATION_CLAUSE_NOTES],
            ["--precedents", "--compare"],
            ["--precedents", "--replay-advocates", "runs/x"],
            ["--precedents", "--replay-check", "runs/x"],
            ["--precedents", "--verify-recorded-drafts", "runs/x"],
            ["--precedents", "--external", "data/external/ryde/case-901.json"],
        ):
            with self.subTest(arguments=arguments):
                message = self.refuse(arguments)
                self.assertIn("precedents", message)
                self.assertIn(arguments[1], message)

    def test_the_refusal_is_about_the_combination_and_not_about_the_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = transport_for()
            with claiming(claims_citing(TARGET_CASE)):
                summary = runner.run_benchmark(
                    MODEL,
                    (TARGET_CASE,),
                    runs_dir=Path(tmp) / "runs",
                    prompts_dir=PROMPTS_DIR,
                    client_factory=rig.client_factory(MODEL, transport),
                    key=rig.answer_key(),
                    git_runner=rig.git_runner(),
                    progress=lambda text: None,
                    judge_votes=1,
                    precedents=store_dir(tmp),
                )
            self.assertEqual([TARGET_CASE], summary.completed_cases)
            self.assertTrue(
                (precedents_run_dir(tmp) / "case-00101.json").is_file()
            )


class DevelopmentSetsCommandLineTests(unittest.TestCase):
    def refuse(self, arguments):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                code = development_sets.main(arguments)
        return code, errors.getvalue()

    def test_it_is_refused_with_every_mode_that_reads_or_reports(self):
        for arguments in (
            ["--precedents", "--ablate", brief.ABLATION_CLAUSE_NOTES],
            ["--precedents", "--report"],
            ["--precedents", "--replay-advocates", "runs/x"],
            ["--precedents", "--replay-check", "runs/x"],
            ["--precedents", "--verify-recorded-drafts", "runs/x"],
        ):
            with self.subTest(arguments=arguments):
                code, errors = self.refuse(arguments)
                self.assertEqual(1, code)
                self.assertIn("precedents", errors)
                self.assertIn(arguments[1], errors)

    def test_the_switch_alone_reaches_the_runner(self):
        # The default store is the repository's own path, so it is redirected at
        # a temporary directory before the command line is run: a test never
        # writes into ``precedents/``.
        with tempfile.TemporaryDirectory() as tmp:
            transport = transport_for()
            with claiming(claims_citing(TARGET_CASE)):
                with mock.patch.object(
                    runner, "PRECEDENTS_STORE", store_dir(tmp)
                ):
                    with mock.patch.object(
                        runner,
                        "_default_client_factory",
                        return_value=rig.client_factory(MODEL, transport),
                    ):
                        with contextlib.redirect_stdout(io.StringIO()):
                            code = development_sets.main(
                                [
                                    "--model",
                                    MODEL,
                                    "--set",
                                    "corpus",
                                    "--cases",
                                    str(TARGET_CASE),
                                    "--precedents",
                                    "--runs-dir",
                                    str(Path(tmp) / "runs"),
                                ]
                            )
            self.assertEqual(0, code)
            self.assertTrue(transport.calls() > 0)
            self.assertTrue(
                (precedents_run_dir(tmp) / "case-00101.json").is_file()
            )


# --------------------------------------------------------------------------
# The shipped store
# --------------------------------------------------------------------------
class ShippedStoreTests(unittest.TestCase):
    def test_the_repository_ships_the_store_the_owner_closed(self):
        """The store shipped empty until 2026-10-01.

        The policy-gap loop's first full pass closed two held-out cases -- 508
        and 530 -- and the owner wrote them here as ``P-0001`` and ``P-0002``.
        The directory therefore holds a README and a chain now, and the claims
        that matter are that the chain verifies and that the sequence runs
        ``0001`` upward with no hole -- the shape ``append_entry`` keeps.
        """
        directory = PROJECT_ROOT / precedents.PRECEDENTS_DIRNAME
        self.assertTrue(directory.is_dir())
        self.assertEqual(
            ["README.md", precedents.PRECEDENTS_FILE],
            sorted(path.name for path in directory.iterdir()),
        )
        store = precedents.store_path(directory)
        self.assertTrue(store.is_file())
        self.assertIsNone(events.verify_chain(store))
        entries = precedents.read_entries(store)
        self.assertEqual(
            ["P-0001", "P-0002"], [entry["precedent_id"] for entry in entries]
        )
        self.assertEqual(
            [508, 530], [entry["source"]["case_no"] for entry in entries]
        )

    def test_the_module_reads_a_run_and_never_the_harness(self):
        """Five fields from a case file, and no run's event log is ever opened.

        The test this replaces asserted that the string ``events.jsonl`` appears
        in the module's source. It does -- in the docstring four lines above the
        code, which says the module never reads one -- so the assertion could
        not have failed on a module that read one. A substring search cannot see
        a read. This runs a real closure with ``Path.read_text`` patched to
        raise on any file called ``events.jsonl``: a closure that opened a run's
        log would not return 0.
        """
        self.assertEqual(
            ("case_no", "ruling", "brief_sha256", "development_set", "configuration"),
            precedents.CASE_FIELDS_READ,
        )
        for name in ("matched", "expected", "grade"):
            with self.subTest(name=name):
                self.assertNotIn(name, precedents.CASE_FIELDS_READ)

        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(tmp, cases=(TARGET_CASE,))
            run_dir = rig.run_dir_of(tmp)
            # The log is there to be opened, which is what makes the guard mean
            # something: a directory holding none would pass for the wrong
            # reason.
            self.assertTrue((run_dir / "events.jsonl").is_file())
            real_read_text = Path.read_text

            def guarded(path, *args, **kwargs):
                if path.name == "events.jsonl":
                    raise AssertionError("a closure opened {0}".format(path))
                return real_read_text(path, *args, **kwargs)

            with mock.patch.object(Path, "read_text", guarded):
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    code = precedents.main(
                        [
                            "--store", str(store_dir(tmp)),
                            "close",
                            "--run-dir", str(run_dir),
                            "--case", str(TARGET_CASE),
                            "--ruling", "PARTIAL_REFUND",
                            "--clause", RD_02,
                            "--closed-by", "A Reviewer",
                            "--summary", "A reviewer closed this case.",
                        ]
                    )
        self.assertEqual(0, code)
        self.assertIn("P-0001", out.getvalue())

    def test_the_default_store_is_the_repository_one(self):
        self.assertEqual(
            PROJECT_ROOT / precedents.PRECEDENTS_DIRNAME / precedents.PRECEDENTS_FILE,
            precedents.store_path(None),
        )


if __name__ == "__main__":
    unittest.main()
