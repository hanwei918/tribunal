"""Every file of the fourth sealed set's single run still hashes as recorded.

The run was made once, on 2026-10-11, and its 29 files are committed exactly as
they were produced. The manifest is ``runs/sealed-v2-manifest.json``: every file
under ``runs/sealed-v2/`` with its size and sha256, sorted by path. This module
is what makes "exactly as produced" a measurement rather than a claim, and it
asks the question in both directions -- it hashes every listed file and compares
it with the digest the manifest states, and it fails if the run directory holds a
file the manifest does not name, because a file added after the run ended leaves
every listed digest intact and a one-way check would not see it.

**The checker is the version-6 reader, not a second copy of it.** The manifest has
the same shape as ``runs/policy-v6-manifest.json`` and is held to the same
``eval.v6_runs.manifest_problems``, so one manifest shape has one checker. A
failure names the file and what disagreed, never a digest.

**The check is shown able to fail.** A copy of the run directory with one byte
flipped is built under the system's temporary directory and the checker is shown
to report the file, so the green result over the real tree is evidence of
something. Nothing here writes anything.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import run_benchmark, v6_runs  # noqa: E402

# The manifest, and the one directory it is about.
MANIFEST = PROJECT_ROOT / "runs" / "sealed-v2-manifest.json"
RUN_ROOT = Path("runs") / "sealed-v2"

# The run's file count, stated here so a manifest that silently parsed to nothing
# fails on the count rather than passing on an empty comparison.
RUN_FILES = 29

# A file the run wrote, used as the one whose bytes the failing fixture changes.
A_CASE_FILE = "case-00801.json"


def manifest() -> Dict[str, Any]:
    """The committed manifest, parsed with ``parse_float=Decimal``."""
    return v6_runs.read_json(MANIFEST)


def problems(parsed: Dict[str, Any], base: Path = PROJECT_ROOT) -> List[str]:
    """``eval.v6_runs.manifest_problems`` over this run's root alone."""
    return v6_runs.manifest_problems(parsed, roots=(RUN_ROOT,), base=base)


class ManifestShapeTests(unittest.TestCase):
    """The manifest is the one the run's file count implies, over the one root."""

    def test_it_lists_the_runs_29_files(self):
        self.assertEqual(
            RUN_FILES,
            len(manifest()["files"]),
            "the manifest does not list the run's 29 files",
        )

    def test_every_entry_names_a_file_under_the_run_directory(self):
        """The manifest is about one directory, so an entry outside it is a defect."""
        outside = [
            entry["path"]
            for entry in manifest()["files"]
            if not entry["path"].startswith(str(RUN_ROOT) + "/")
        ]
        self.assertEqual([], outside, "a manifest entry names something outside the run")

    def test_every_entry_names_a_size_and_a_sha256(self):
        malformed = [
            entry["path"]
            for entry in manifest()["files"]
            if not isinstance(entry.get("size"), int)
            or len(str(entry.get("sha256"))) != 64
            or any(
                character not in "0123456789abcdef"
                for character in str(entry.get("sha256"))
            )
        ]
        self.assertEqual([], malformed, "an entry does not carry a size and a sha256")

    def test_the_paths_are_unique_and_sorted(self):
        listed = [entry["path"] for entry in manifest()["files"]]
        self.assertEqual(sorted(set(listed)), listed, "the manifest is not sorted, or repeats a file")


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

    def test_the_run_directory_holds_the_29_files_the_manifest_names(self):
        present = sorted(
            str(path.relative_to(PROJECT_ROOT))
            for path in (PROJECT_ROOT / RUN_ROOT).rglob("*")
            if path.is_file()
        )
        self.assertEqual(RUN_FILES, len(present))


class TheCheckCanFailTests(unittest.TestCase):
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

    def test_a_file_the_manifest_does_not_name_is_reported(self):
        """A file added after the run ended leaves every listed digest intact."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            copied = base / RUN_ROOT
            copied.parent.mkdir(parents=True)
            shutil.copytree(PROJECT_ROOT / RUN_ROOT, copied)
            added = copied / "deepseek-deepseek-flash" / "case-00999.json"
            added.write_text("{}\n", encoding="utf-8")

            found = problems(manifest(), base=base)

            self.assertIn(
                "{0} is on disk but not in the manifest".format(
                    RUN_ROOT / "deepseek-deepseek-flash" / "case-00999.json"
                ),
                found,
                "a file the manifest does not name was not reported",
            )

    def test_the_clean_control_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            copied = base / RUN_ROOT
            copied.parent.mkdir(parents=True)
            shutil.copytree(PROJECT_ROOT / RUN_ROOT, copied)

            self.assertEqual(
                [], problems(manifest(), base=base), "a clean copy was reported"
            )


if __name__ == "__main__":
    unittest.main()
