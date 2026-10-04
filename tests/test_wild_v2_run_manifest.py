"""Every file of the second sealed set's single run still hashes as recorded.

The run was made once, on 2026-10-04, and its 45 files are committed exactly as
they were produced. The owner recorded a manifest of them the moment the run
ended, and this repository now carries that manifest at
``docs/notes/2026-10-04-wild-v2-run-manifest.txt``. This module is what makes
"exactly as produced" a measurement rather than a claim: it hashes every listed
file and compares it with the digest the manifest states.

**A failure names the file and nothing else.** A digest is a property of sealed
bytes and a test's output is not where those belong; neither is a file's
content. So the assertion messages carry repository-relative paths only, and the
digests are compared, never printed.

**The check is shown able to fail.** A manifest whose digest for one file is
wrong is built in a temporary directory and the checker is shown to report that
file, so the green result over the real manifest is evidence of something. The
fixture lives under the system's temporary directory, never under ``runs/``, and
nothing here writes anything.
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import run_benchmark  # noqa: E402

# The manifest, as the owner recorded it when the run ended. It is a note this
# repository carries, not the set: reading it reads a document we wrote.
MANIFEST = PROJECT_ROOT / "docs" / "notes" / "2026-10-04-wild-v2-run-manifest.txt"

# The manifest's own digest, as the results sheet states it. The manifest is the
# record the run is checked against, so the record has to be pinned too -- a
# manifest edited to match edited files would otherwise verify itself.
MANIFEST_SHA256 = "12ffb8c42090d43baa96eda918b26784d40a1c67f0fdc2e57e1ac2a9e96b48d1"

# Every line of the manifest names a file under this root. The run directory is
# the whole subject: the manifest is not a manifest of the repository.
RUN_ROOT = "runs/wild-v2/"

# The run's file count, stated here so a manifest that silently parsed to
# nothing fails on the count rather than passing on an empty comparison.
MANIFEST_LINES = 45


def manifest_entries(manifest_path: Path) -> List[Tuple[str, str]]:
    """``[(repository-relative path, sha256)]`` in the manifest's own order.

    A line is ``<digest><two spaces><path>``, which is what ``shasum -a 256``
    writes and therefore what ``shasum -a 256 -c`` reads back. Blank lines are
    skipped; a line that does not have both halves is a malformed manifest and
    raises, because a silently skipped line is a file nobody checks.
    """
    entries: List[Tuple[str, str]] = []
    for number, line in enumerate(
        Path(manifest_path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        digest, separator, relative = line.partition("  ")
        if not separator or not relative.strip():
            raise ValueError(
                "{0}:{1} is not a manifest line".format(Path(manifest_path).name, number)
            )
        entries.append((relative.strip(), digest.strip()))
    return entries


def mismatches(entries: Sequence[Tuple[str, str]], root: Path) -> List[str]:
    """The listed files whose bytes do not hash to the digest listed for them.

    A missing file is a mismatch: the manifest says it is there. The result is
    repository-relative paths, sorted, and it is the whole of what a caller may
    report.
    """
    root = Path(root)
    wrong: List[str] = []
    for relative, digest in entries:
        path = root / relative
        if not path.is_file() or run_benchmark.file_sha256(path) != digest:
            wrong.append(relative)
    return sorted(wrong)


class ManifestShapeTests(unittest.TestCase):
    """The manifest is the one the run's file count implies, over the one root."""

    def test_it_lists_the_run_s_45_files(self):
        self.assertEqual(
            MANIFEST_LINES,
            len(manifest_entries(MANIFEST)),
            "the manifest does not list the run's 45 files",
        )

    def test_every_line_names_a_file_under_the_run_directory(self):
        """The manifest is about one directory, so a line outside it is a defect."""
        outside = [
            relative
            for relative, _digest in manifest_entries(MANIFEST)
            if not relative.startswith(RUN_ROOT)
        ]
        self.assertEqual([], outside, "a manifest line names something outside the run")

    def test_every_digest_is_a_sha256(self):
        malformed = [
            relative
            for relative, digest in manifest_entries(MANIFEST)
            if len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ]
        self.assertEqual([], malformed, "a manifest line does not carry a sha256")

    def test_the_paths_are_unique(self):
        listed = [relative for relative, _digest in manifest_entries(MANIFEST)]
        self.assertEqual(
            sorted(set(listed)), sorted(listed), "the manifest lists a file twice"
        )


class ManifestIntegrityTests(unittest.TestCase):
    """The record, and every file the record names, as committed."""

    def test_the_manifest_is_the_one_the_owner_recorded(self):
        """The record is pinned, so it cannot be edited to match edited files."""
        digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
        self.assertEqual(
            MANIFEST_SHA256,
            digest,
            "the committed manifest is not the one the owner recorded",
        )

    def test_every_listed_file_still_hashes_as_recorded(self):
        """The measurement. A failure names the file and nothing else."""
        wrong = mismatches(manifest_entries(MANIFEST), PROJECT_ROOT)
        self.assertEqual(
            [],
            wrong,
            "these files no longer hash as the manifest states: {0}".format(
                ", ".join(wrong)
            ),
        )


class TheCheckCanFailTests(unittest.TestCase):
    """A green result is evidence only if the check has been seen to go red."""

    def test_it_reports_a_file_whose_bytes_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "runs").mkdir()
            good = root / "runs" / "case-00701.json"
            bad = root / "runs" / "case-00702.json"
            good.write_bytes(b"the bytes the manifest recorded\n")
            bad.write_bytes(b"other bytes\n")

            entries = [
                ("runs/case-00701.json", hashlib.sha256(good.read_bytes()).hexdigest()),
                ("runs/case-00702.json", hashlib.sha256(b"what was recorded\n").hexdigest()),
            ]

            self.assertEqual(
                ["runs/case-00702.json"],
                mismatches(entries, root),
                "a file whose bytes changed was not reported",
            )

    def test_it_reports_a_file_the_manifest_names_and_the_run_does_not_have(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "runs").mkdir()
            entries = [("runs/case-00701.json", "0" * 64)]

            self.assertEqual(
                ["runs/case-00701.json"],
                mismatches(entries, root),
                "a missing file was not reported",
            )

    def test_the_clean_control_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "runs").mkdir()
            present = root / "runs" / "case-00701.json"
            present.write_bytes(b"the bytes the manifest recorded\n")
            entries = [
                ("runs/case-00701.json", hashlib.sha256(present.read_bytes()).hexdigest())
            ]

            self.assertEqual([], mismatches(entries, root), "a clean fixture was reported")


if __name__ == "__main__":
    unittest.main()
