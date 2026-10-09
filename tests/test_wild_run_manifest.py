"""Every file of the held-out set's single run is still what its commit holds.

``runs/wild/`` holds the held-out set's single run, made once by the owner and
committed byte for byte at ``2e527d6``. The second sealed set's run carries a
manifest the owner wrote when the run ended, and this repository carries it as a
note; this run does not, so its manifest is **built from the commit** instead:
``git ls-tree -r`` names the blobs under the run root at that commit and ``git
cat-file --batch`` hands back their bytes, which are hashed here. Nothing is
added to the repository for it, and the record cannot drift from the commit it
describes.

The question is asked in both directions, exactly as the second sealed set's is:
every file the commit names still hashes as it did, and the run directory holds
no file the commit does not name -- a file added after the run ended leaves
every listed digest intact, so a one-way check would not see it. A name the
repository's ``.gitignore`` matches is not a change and is skipped.

**A failure names the file and nothing else.** A digest is a property of sealed
bytes and a test's output is not where those belong; neither is a file's
content. So the assertion messages carry repository-relative paths only, and
every digest is compared rather than printed.

**The check is shown able to fail.** A file whose bytes differ from the commit's
and a file added under the run directory are each built in a temporary directory
and the checkers are shown to report the file, so the green result over the real
run is evidence of something. The fixtures live under the system's temporary
directory, never under ``runs/``, and nothing here writes anything.
"""

from __future__ import annotations

import functools
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import test_wild_v2_run_manifest as rig  # noqa: E402
from tests import portability  # noqa: E402

# The commit the run is committed at, as ``runs/README.md`` and the note state
# it. The listing is taken from the commit rather than from the working tree, so
# this test says what the run is at that commit and not what it is right now.
RUN_COMMIT = "2e527d6"

# Every file of the run lives under this root, and there are 131 of them. The
# count is stated here so a listing that silently parsed to nothing fails on the
# count rather than passing on an empty comparison.
RUN_ROOT = "runs/wild"
RUN_FILES = 131


@functools.lru_cache(maxsize=None)
def manifest() -> Tuple[Tuple[str, str], ...]:
    """``((path, sha256), ...)`` for every file under the run root at the commit.

    ``git ls-tree -r -z`` is the listing of the commit's own tree, which is the
    commit-time equivalent of ``git ls-files``; ``git cat-file --batch`` then
    hands back every blob in one call rather than one call per file. The parse
    is positional: each response is a header line, the bytes it declares, and a
    newline.

    **A machine without the repository's history is told so, not measured.**
    Every test that asks this question skips when ``git rev-parse
    --show-toplevel`` fails -- a zip download has no ``.git``, and a machine may
    have no ``git`` -- rather than failing on a listing that cannot be read.
    """
    portability.require_git_history()
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "-z", RUN_COMMIT, "--", RUN_ROOT],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    blobs: List[Tuple[str, str]] = []
    for entry in listing.split("\0"):
        if not entry:
            continue
        meta, _tab, path = entry.partition("\t")
        _mode, _kind, oid = meta.split()
        blobs.append((path, oid))

    request = "".join(oid + "\n" for _path, oid in blobs).encode("utf-8")
    batch = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=PROJECT_ROOT,
        input=request,
        capture_output=True,
        check=True,
    ).stdout

    entries: List[Tuple[str, str]] = []
    position = 0
    for path, _oid in blobs:
        header, _newline, rest = batch[position:].partition(b"\n")
        _name, _kind, size = header.split()
        length = int(size)
        entries.append((path, hashlib.sha256(rest[:length]).hexdigest()))
        position += len(header) + 1 + length + 1
    return tuple(entries)


class ManifestShapeTests(unittest.TestCase):
    """The manifest the commit implies, over the one root."""

    def test_it_lists_the_run_s_131_files(self):
        self.assertEqual(
            RUN_FILES,
            len(manifest()),
            "the commit does not hold the run's 131 files",
        )

    def test_every_listed_path_is_under_the_run_directory(self):
        """The manifest is about one directory, so a path outside it is a defect."""
        outside = [
            path for path, _digest in manifest() if not path.startswith(RUN_ROOT + "/")
        ]
        self.assertEqual([], outside, "a listed path is outside the run")

    def test_every_digest_is_a_sha256(self):
        malformed = [
            path
            for path, digest in manifest()
            if len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ]
        self.assertEqual([], malformed, "a listed file does not carry a sha256")

    def test_the_paths_are_unique(self):
        listed = [path for path, _digest in manifest()]
        self.assertEqual(
            sorted(set(listed)), sorted(listed), "the commit lists a file twice"
        )


class ManifestIntegrityTests(unittest.TestCase):
    """The run, as committed, against what the commit holds."""

    def test_every_listed_file_still_hashes_as_it_did_at_the_commit(self):
        """The measurement. A failure names the file and nothing else."""
        wrong = rig.mismatches(manifest(), PROJECT_ROOT)
        self.assertEqual(
            [],
            wrong,
            "these files no longer hash as the commit holds them: {0}".format(
                ", ".join(wrong)
            ),
        )

    def test_the_run_directory_holds_no_file_the_commit_does_not_name(self):
        """The other direction: a file added after the run ended is a change."""
        extra = rig.unlisted(manifest(), PROJECT_ROOT, RUN_ROOT)
        self.assertEqual(
            [],
            extra,
            "the run directory holds files the commit does not name: {0}".format(
                ", ".join(extra)
            ),
        )


class TheCheckCanFailTests(unittest.TestCase):
    """A green result is evidence only if the check has been seen to go red."""

    def test_it_reports_a_file_whose_bytes_differ_from_the_commit(self):
        listed = manifest()[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / listed[0]
            target.parent.mkdir(parents=True)
            target.write_bytes(b"not what the commit holds\n")

            self.assertEqual(
                [listed[0]],
                rig.mismatches([listed], root),
                "a file whose bytes changed was not reported",
            )

    def test_a_file_of_the_commit_s_own_bytes_is_not_reported(self):
        """The control: the same fixture, holding what the commit holds."""
        listed = manifest()[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / listed[0]
            target.parent.mkdir(parents=True)
            target.write_bytes((PROJECT_ROOT / listed[0]).read_bytes())

            self.assertEqual(
                [], rig.mismatches([listed], root), "a clean fixture was reported"
            )

    def test_it_reports_a_file_added_under_the_run_directory(self):
        entries = [("runs/wild/case-00501.json", "0" * 64)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / RUN_ROOT
            run_dir.mkdir(parents=True)
            (run_dir / "case-00999.json").write_bytes(
                b"a file the run did not produce\n"
            )

            self.assertEqual(
                ["runs/wild/case-00999.json"],
                rig.unlisted(entries, root, RUN_ROOT),
                "a file the commit does not name was not reported",
            )


if __name__ == "__main__":
    unittest.main()
