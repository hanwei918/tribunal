"""The fifth sealed set's stopped run, as it is committed.

``sealed-v3``'s single run was started once, on 2026-10-13, and stopped after 8
of its 30 cases. This module holds the committed record to what it says: every
file of the run matches the manifest beside it, ``run.json`` names the eight
cases that produced a ruling and the two that failed, the reader prints the
stopped state and no agreement rate, and the set's root refuses a plain run and
``--force``.

**The manifest check is shown able to fail.** A copy of the run directory with
one byte flipped is built under the system's temporary directory and the checker
is shown to report the file, so the green result over the real tree is evidence
of something.

No model is called and nothing is written. Every invocation of the command line
here is refused before a client is built, and ``LLMClient`` is patched to raise
so that a guard which let a run start fails the test instead of reaching the
network.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import (  # noqa: E402
    development_sets as sets,
    run_benchmark,
    sealed_report,
    v6_runs,
)

MODEL = "deepseek/deepseek-flash"
SEALED_V3 = sets.SEALED_V3

# The manifest, and the one directory it is about.
MANIFEST = PROJECT_ROOT / "runs" / "sealed-v3-manifest.json"
RUN_ROOT = Path("runs") / "sealed-v3"

# The run's file count, stated here so a manifest that silently parsed to nothing
# fails on the count rather than passing on an empty comparison.
RUN_FILES = 19

# A file the run wrote, used as the one whose bytes the failing fixture changes.
A_CASE_FILE = "case-04001.json"

# What the invocation left, as ``run.json`` records it: eight cases with a
# ruling, two that failed, and twenty that were never reached.
COMPLETED = [4001, 4002, 4003, 4004, 4005, 4006, 4009, 4011]
FAILED = [4007, 4008]


def manifest() -> Dict[str, Any]:
    """The committed manifest, parsed with ``parse_float=Decimal``."""
    return v6_runs.read_json(MANIFEST)


def problems(parsed: Dict[str, Any], base: Path = PROJECT_ROOT) -> List[str]:
    """``eval.v6_runs.manifest_problems`` over this run's root alone."""
    return v6_runs.manifest_problems(parsed, roots=(RUN_ROOT,), base=base)


def run_json() -> Dict[str, Any]:
    """The run's own metadata, parsed."""
    with (PROJECT_ROOT / RUN_ROOT / "deepseek-deepseek-flash" / "run.json").open(
        "r", encoding="utf-8"
    ) as handle:
        return json.load(handle)


def _refuse_to_build_a_client():
    """Patch ``LLMClient`` to raise, so a guard that let a run start fails."""
    original = run_benchmark.llm.LLMClient

    def refuse(*arguments, **keywords):
        raise AssertionError(
            "a client was built, so a switch was accepted that must have been refused"
        )

    return original, refuse


def _run_cli(arguments):
    """``sets.main``, with both streams captured and no client buildable."""
    stdout, stderr = io.StringIO(), io.StringIO()
    original, refuse = _refuse_to_build_a_client()
    run_benchmark.llm.LLMClient = refuse
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = sets.main(arguments)
    finally:
        run_benchmark.llm.LLMClient = original
    return code, stdout.getvalue(), stderr.getvalue()


def _run_report(arguments):
    """``sealed_report.main``, with standard output captured."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = sealed_report.main(arguments)
    return code, buffer.getvalue()


class ManifestShapeTests(unittest.TestCase):
    """The manifest is the one the run's file count implies, over the one root."""

    def test_it_lists_the_runs_19_files(self):
        self.assertEqual(
            RUN_FILES,
            len(manifest()["files"]),
            "the manifest does not list the run's 19 files",
        )

    def test_every_entry_names_a_file_under_the_run_directory(self):
        outside = [
            entry["path"]
            for entry in manifest()["files"]
            if not entry["path"].startswith(str(RUN_ROOT) + "/")
        ]
        self.assertEqual([], outside, "a manifest entry names something outside the run")

    def test_the_paths_are_unique_and_sorted(self):
        listed = [entry["path"] for entry in manifest()["files"]]
        self.assertEqual(
            sorted(set(listed)), listed, "the manifest is not sorted, or repeats a file"
        )


class ManifestIntegrityTests(unittest.TestCase):
    """The record, and every file the record names, as committed."""

    def test_the_manifest_matches_the_files_on_disk(self):
        """Both directions, through the reader the version-6 manifest uses."""
        found = problems(manifest())
        self.assertEqual(
            [],
            found,
            "the manifest and the run directory disagree: {0}".format("; ".join(found)),
        )

    def test_the_run_directory_holds_the_19_files_the_manifest_names(self):
        present = sorted(
            str(path.relative_to(PROJECT_ROOT))
            for path in (PROJECT_ROOT / RUN_ROOT).rglob("*")
            if path.is_file()
        )
        self.assertEqual(RUN_FILES, len(present))


class TheManifestCheckCanFailTests(unittest.TestCase):
    """A green result is evidence only if the check has been seen to go red."""

    def test_a_file_with_one_byte_changed_is_reported(self):
        """The byte flipped is one the file actually has."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            copied = base / RUN_ROOT
            copied.parent.mkdir(parents=True)
            shutil.copytree(PROJECT_ROOT / RUN_ROOT, copied)
            target = copied / "deepseek-deepseek-flash" / A_CASE_FILE
            data = bytearray(target.read_bytes())
            data[0] = data[0] ^ 0xFF
            target.write_bytes(bytes(data))

            found = problems(manifest(), base=base)

            self.assertEqual(
                [str(RUN_ROOT / "deepseek-deepseek-flash" / A_CASE_FILE)],
                [problem.split(" ")[0] for problem in found],
                "a file whose bytes changed was not reported",
            )


class TheStoppedStateTests(unittest.TestCase):
    """``run.json`` and the reader, held to the stopped run the set left."""

    def test_run_json_lists_the_eight_completed_and_the_two_failed(self):
        cases = run_json()["cases"]
        self.assertEqual(COMPLETED, sorted(cases["completed"]))
        self.assertEqual(FAILED, sorted(cases["failed"]))
        self.assertEqual(
            set(SEALED_V3.cases),
            set(cases["requested"]),
            "run.json was not asked for the set's own 30 cases",
        )

    def test_the_reader_prints_the_stopped_state_and_no_rate(self):
        code, text = _run_report(["--set", "sealed-v3"])
        self.assertEqual(0, code)
        self.assertIn("Stopped: 8 of 30 with a ruling, 2 failed, 20 not run.", text)
        self.assertNotIn("%", text, "the stopped report printed a rate")
        self.assertNotIn("Wilson", text, "the stopped report printed an interval")


class TheRootRefusesARunTests(unittest.TestCase):
    """The plain run and ``--force`` are both refused, and nothing is written."""

    def test_the_plain_run_is_refused_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ):
                with mock.patch.dict(os.environ):
                    os.environ.pop(sets.SEALED_RUN_ENV_VAR, None)
                    code, _out, err = _run_cli(
                        ["--set", "sealed-v3", "--concurrency", "2", "--timeout", "900"]
                    )
            self.assertEqual(1, code, "a plain run of the sealed set was accepted")
            self.assertIn("its single run has been made", err)
            self.assertIn("root is closed", err)
            self.assertFalse(runs.exists(), "the refused invocation created the runs root")

    def test_force_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ):
                code, _out, err = _run_cli(["--set", "sealed-v3", "--force"])
            self.assertEqual(1, code, "the sealed set accepted --force")
            self.assertIn("the sealed set sealed-v3 is run once", err)
            self.assertIn("--force", err)
            self.assertFalse(runs.exists(), "the refused invocation created the runs root")


if __name__ == "__main__":
    unittest.main()
