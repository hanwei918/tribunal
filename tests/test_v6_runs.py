"""The version-6 development runs: the manifest, the provenance check and the note.

Four claims, and each is checked against the files rather than restated:

* **The manifest describes the tree.** ``runs/policy-v6-manifest.json`` lists
  every copied file under the five run directories and the console directory,
  with its size and sha256, sorted by path — and no file under those roots is
  missing from it. The check is shown capable of firing: one byte changed in a
  copy of a committed run file is reported.
* **The provenance check passes.** Every case file and every event of the five
  runs records the freeze commit, every run recorded a clean tree and the freeze
  configuration, and the case counts are the registered sizes.
* **The figures are the grader's own.** Each set's four-field figure, and the
  precedent measurement's two, are recomputed through :mod:`eval.grade` from the
  committed runs and keys and held against what the report prints.
* **The note pastes the report verbatim.** The report is a document a reader
  reproduces with one command, so the note carries it as it prints, and every
  figure the note states is therefore a figure the report computes.

No model call is made. Nothing here writes under ``runs/``.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, grade, v6_runs  # noqa: E402

NOTE = PROJECT_ROOT / "docs" / "notes" / "2026-10-10-the-version-6-development-runs.md"

# The one fenced block the note carries: the report, as it prints.
REPORT_BLOCK_RE = re.compile(r"```\n(.*?)\n```", re.S)

# A small committed run directory, used whole as the fixture for the
# one-byte-changed control. Seven files, so copying it is instant.
FIXTURE_RUN = PROJECT_ROOT / "runs" / "ryde-v3" / "policy-v6"


def _manifest_for(root: Path, base: Path) -> Dict[str, Any]:
    """A manifest for a fixture tree, in the committed manifest's shape."""
    entries: List[Dict[str, Any]] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            path = Path(dirpath) / name
            entries.append(
                {
                    "path": str(path.relative_to(base)),
                    "size": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    entries.sort(key=lambda entry: entry["path"])
    return {"files": entries}


class ManifestTests(unittest.TestCase):
    """The manifest and the files under the roots it names."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = v6_runs.load_manifest()

    def test_the_manifest_matches_the_files_on_disk(self):
        problems = v6_runs.manifest_problems(self.manifest)
        self.assertEqual([], problems, "\n".join(problems))

    def test_the_manifest_lists_every_root(self):
        listed = [entry["path"] for entry in self.manifest["files"]]
        for run in v6_runs.RUNS:
            root = str(run.run_dir.relative_to(PROJECT_ROOT)) + "/"
            with self.subTest(root=root):
                self.assertTrue(
                    any(path.startswith(root) for path in listed),
                    "no file under {0} is in the manifest".format(root),
                )
        console = str(v6_runs.CONSOLE_DIR.relative_to(PROJECT_ROOT)) + "/"
        for name in v6_runs.CONSOLE_LOGS:
            with self.subTest(log=name):
                self.assertIn(console + name, listed)

    def test_the_manifest_is_sorted_by_path(self):
        listed = [entry["path"] for entry in self.manifest["files"]]
        self.assertEqual(sorted(listed), listed)

    def test_every_entry_names_a_size_and_a_sha256(self):
        for entry in self.manifest["files"]:
            with self.subTest(path=entry["path"]):
                self.assertIsInstance(entry["size"], int)
                self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")

    def test_the_fixture_run_is_committed(self):
        """The control below is over a real run directory, so it must be there."""
        self.assertTrue((FIXTURE_RUN / "deepseek-deepseek-flash" / "run.json").is_file())

    def test_a_run_file_with_one_byte_changed_fails_the_check(self):
        """The check is shown to fire: one byte is enough."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            destination = base / "ryde-v3" / "policy-v6"
            shutil.copytree(FIXTURE_RUN, destination)
            roots = [destination]
            manifest = _manifest_for(destination, base)

            self.assertEqual(
                [],
                v6_runs.manifest_problems(manifest, roots=roots, base=base),
                "the fixture was reported as broken before anything was changed",
            )

            case_file = destination / "deepseek-deepseek-flash" / "case-00901.json"
            data = bytearray(case_file.read_bytes())
            data[0] = data[0] ^ 0x01
            case_file.write_bytes(bytes(data))

            problems = v6_runs.manifest_problems(manifest, roots=roots, base=base)
            self.assertTrue(problems, "one changed byte was not reported")
            self.assertTrue(
                any("case-00901.json" in problem for problem in problems),
                problems,
            )

    def test_a_file_the_manifest_does_not_name_is_reported(self):
        """The other half: a file added under a root is a finding too."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            destination = base / "ryde-v3" / "policy-v6"
            shutil.copytree(FIXTURE_RUN, destination)
            roots = [destination]
            manifest = _manifest_for(destination, base)
            (destination / "deepseek-deepseek-flash" / "case-00999.json").write_text(
                "{}", encoding="utf-8"
            )

            problems = v6_runs.manifest_problems(manifest, roots=roots, base=base)
            self.assertTrue(
                any("case-00999.json" in problem for problem in problems), problems
            )


class CheckTests(unittest.TestCase):
    """The provenance check, over the committed runs."""

    def test_the_check_passes(self):
        ok, lines = v6_runs.check()
        text = "\n".join(lines)
        self.assertTrue(ok, text)
        self.assertNotIn("<--", text, "a run failed a check it should have passed")
        self.assertIn("check: PASS", text)

    def test_every_run_holds_its_registered_number_of_cases(self):
        for run in v6_runs.RUNS:
            with self.subTest(run=run.name):
                self.assertEqual(
                    run.registered_size,
                    len(v6_runs.case_files(run.run_dir)),
                )

    def test_every_case_and_event_records_the_freeze_commit(self):
        for run in v6_runs.RUNS:
            for case_no, path in sorted(v6_runs.case_files(run.run_dir).items()):
                with self.subTest(run=run.name, case=case_no):
                    self.assertEqual(
                        v6_runs.FREEZE_COMMIT,
                        v6_runs.read_json(path).get("git_commit"),
                    )
            for event in v6_runs.event_lines(run.run_dir):
                with self.subTest(run=run.name, seq=event.get("seq")):
                    self.assertEqual(v6_runs.FREEZE_COMMIT, event.get("commit"))


class ReportFigureTests(unittest.TestCase):
    """The report's figures, recomputed through the grader."""

    @classmethod
    def setUpClass(cls):
        cls.text = v6_runs.report()

    def _exact(self, run: v6_runs.V6Run, key: Mapping[int, Any]) -> str:
        documents = v6_runs.documents(run.run_dir, run.cases)
        produced = {
            case_no: document.get("ruling") for case_no, document in documents.items()
        }
        subset = {case_no: key[case_no] for case_no in documents if case_no in key}
        report = grade.grade(produced, subset, corpus=subset)
        return "{0}/{1}".format(report.exact_matches, report.total)

    def test_every_sets_four_field_figure_is_the_graders_own(self):
        for run in v6_runs.RUNS:
            if run.key_path is None:
                continue
            with self.subTest(run=run.name):
                key = grade.load_answer_key(run.key_path)
                figure = self._exact(run, key)
                self.assertIn(
                    "four-field exact  {0} ".format(figure),
                    self.text,
                    "the report does not print {0}'s four-field figure {1}".format(
                        run.name, figure
                    ),
                )

    def test_the_precedent_figures_are_the_graders_own(self):
        key = grade.load_answer_key(v6_runs.PRECEDENTS_RUN.key_path)
        subset = {
            case_no: key[case_no] for case_no in v6_runs.ROUTE_DEVIATION_CASES
        }
        with_precedents = self._exact(v6_runs.PRECEDENTS_RUN, key)
        corpus = v6_runs.run_by_name("corpus")
        documents = v6_runs.documents(corpus.run_dir, v6_runs.ROUTE_DEVIATION_CASES)
        without = grade.grade(
            {
                case_no: document.get("ruling")
                for case_no, document in documents.items()
            },
            subset,
            corpus=subset,
        )
        without_figure = "{0}/{1}".format(without.exact_matches, without.total)
        self.assertIn("with precedents     four-field exact {0} ".format(with_precedents), self.text)
        self.assertIn("without precedents  four-field exact {0} ".format(without_figure), self.text)

    def test_the_report_is_deterministic(self):
        self.assertEqual(self.text, v6_runs.report())


class NoteTests(unittest.TestCase):
    """The note, and the figures it states."""

    @classmethod
    def setUpClass(cls):
        cls.text = NOTE.read_text(encoding="utf-8")
        # The prose is matched with its whitespace collapsed, so a phrase the
        # note wraps across two lines is still one phrase. The pasted report is
        # matched against the raw text, because it is the bytes a reader copies.
        cls.flat = " ".join(cls.text.split())
        match = REPORT_BLOCK_RE.search(cls.text)
        if match is None:
            raise AssertionError("the note carries no fenced report block")
        cls.block = match.group(1) + "\n"

    def test_the_note_pastes_the_report_verbatim(self):
        self.assertEqual(
            v6_runs.report(),
            self.block,
            "the report the note pastes is not what the command prints",
        )

    def test_the_note_states_the_freeze_tag_and_the_commit(self):
        self.assertIn(v6_runs.FREEZE_TAG, self.text)
        self.assertIn(v6_runs.FREEZE_COMMIT, self.text)
        self.assertIn(v6_runs.FREEZE_COMMIT, self.block)

    def test_the_note_states_every_registered_size(self):
        match = re.search(
            r"registered sizes — ([0-9, and]+), with the precedents arm's ([0-9]+)",
            self.flat,
        )
        self.assertIsNotNone(match, "the note does not state the registered sizes")
        stated = [int(part) for part in re.findall(r"[0-9]+", match.group(1))]
        self.assertEqual([run.registered_size for run in v6_runs.RUNS], stated)
        self.assertEqual(v6_runs.PRECEDENTS_RUN.registered_size, int(match.group(2)))

    def test_the_note_counts_the_sets_that_are_not_here(self):
        sealed = re.search(r"its ([0-9]+) cases are registered at policy version 6", self.flat)
        self.assertIsNotNone(sealed)
        self.assertEqual(len(development_sets.SEALED_V1.cases), int(sealed.group(1)))

        dev_v2_size = len(development_sets.DEV_V2.cases)
        omitted = re.search(r"other ([0-9]+) cases\*\* are not here", self.flat)
        self.assertIsNotNone(omitted)
        self.assertEqual(dev_v2_size - 1, int(omitted.group(1)))
        self.assertIn("{0}-case set".format(dev_v2_size), self.flat)

        held_out = re.search(r"`wild`'s ([0-9]+) cases and `wild-v2`'s ([0-9]+)", self.flat)
        self.assertIsNotNone(held_out)
        self.assertEqual(len(development_sets.SEALED_SET.cases), int(held_out.group(1)))
        self.assertEqual(len(development_sets.WILD_V2.cases), int(held_out.group(2)))

    def test_the_note_names_the_five_run_directories(self):
        for run in v6_runs.RUNS:
            relative = str(run.run_dir.relative_to(PROJECT_ROOT))
            with self.subTest(run=run.name):
                self.assertIn(relative, self.text)


if __name__ == "__main__":
    unittest.main()
