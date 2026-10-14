"""No file under ``runs/`` carries the path of the checkout a run was launched from.

Most of the runs this repository reports were launched from a temporary checkout
of it under the system's temporary folder, and the runner wrote that checkout's
absolute path into the run's own records: `run_dir`, the `directory` block's
`path` and `prompts_dir` in ``run.json`` and ``invocations.json``, and the
console logs. The path names a directory that exists on the machine that
launched the run and nowhere else, and it names a personal folder besides, so on
2026-10-14 every occurrence of it was replaced by the placeholder ``<checkout>``.
This module is what makes that a measurement rather than a claim: a launch path
put back into a record -- by a re-run, by a hand edit, or by a tool that wrote
one in again -- is reported.

**The files are read as bytes.** A run record is a record of bytes, and the
check is about the bytes in the file rather than about a value some parser
recovers from them, so nothing here parses a record to look for a path.

**The list is the repository's own.** ``git ls-files runs`` is the list the
replacement was made over, so it is the list this check reads. **When there is
no checkout to ask** -- a zip download has no ``.git``, and a machine without
``git`` cannot run the command -- the walk over ``runs/`` stands in for it, so
the check reads the records rather than skipping them.

**The second half is the manifests.** The replacement moved two files' bytes, so
the ``sha256`` and ``size`` of those files' entries in four manifests were
updated with them; a manifest left stale would be a record that disagrees with
its subject. Every entry of every ``runs/*manifest*.json`` is therefore compared
with its file, in both directions that matter here: the digest and the size.

**The check is shown able to fail.** One ``<checkout>`` is put back into one
``run.json`` as a launch path, in a copy under the system's temporary directory,
and the check is shown to report that file and no other. Nothing here writes
anything under ``runs/``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = PROJECT_ROOT / "runs"

# The prefix of the path the replacement removed, and the placeholder that
# stands in for it. Both are bytes, because the files are read as bytes.
LAUNCH_PATH = b"/private/tmp/"
PLACEHOLDER = b"<checkout>"

# The manifests, by the name the four of them share under ``runs/``.
MANIFEST_GLOB = "*manifest*.json"

# One manifest the walk must find. A glob that silently matched nothing would
# otherwise pass on an empty comparison, which is the shape of a check that has
# stopped checking.
MANIFEST_THE_WALK_MUST_FIND = "policy-v6-manifest.json"

# One committed record that carries the placeholder, used by the control.
A_RECORD_WITH_THE_PLACEHOLDER = "runs/policy-v6/deepseek-deepseek-flash/run.json"


def run_record_paths() -> List[str]:
    """Every file under ``runs/`` the repository tracks, repository-relative.

    ``git ls-files runs`` answers it when there is a checkout to ask. When the
    command cannot be run at all -- no ``git`` on the machine -- or answers with
    a failure -- no ``.git``, which is what a zip download looks like -- the walk
    over ``runs/`` stands in for it, so the records are still read.
    """
    try:
        done = subprocess.run(
            ["git", "ls-files", "runs"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
    except OSError:
        done = None
    if done is not None and done.returncode == 0:
        return [line for line in done.stdout.splitlines() if line.strip()]
    return sorted(
        str(path.relative_to(PROJECT_ROOT))
        for path in RUNS_ROOT.rglob("*")
        if path.is_file()
    )


def manifests(root: Path = PROJECT_ROOT) -> List[Path]:
    """Every manifest under the given root's ``runs/``, sorted by name."""
    return sorted((Path(root) / "runs").glob(MANIFEST_GLOB))


def files_carrying_a_launch_path(
    paths: List[str], root: Path = PROJECT_ROOT, needle: bytes = LAUNCH_PATH
) -> List[str]:
    """The files whose bytes contain ``needle``, repository-relative and sorted.

    A path that is not there is not reported: this check is about what a file
    contains, and a missing file is what the manifest check above is for.
    """
    base = Path(root)
    return sorted(
        relative
        for relative in paths
        if (base / relative).is_file() and needle in (base / relative).read_bytes()
    )


def manifest_problems(root: Path = PROJECT_ROOT) -> List[str]:
    """Every manifest entry that does not match its file's bytes.

    A failure names the manifest and the file and says which of the two values
    moved. A digest is a property of the file's bytes and a test's output is not
    where those belong, so the digests themselves are compared rather than
    printed. A file the manifest names and the tree does not have is a problem
    too: the manifest says it is there.
    """
    base = Path(root)
    problems: List[str] = []
    for manifest in manifests(base):
        entries = json.loads(manifest.read_text(encoding="utf-8"))["files"]
        for entry in entries:
            path = base / entry["path"]
            if not path.is_file():
                problems.append(
                    "{0}: {1} is missing".format(manifest.name, entry["path"])
                )
                continue
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                problems.append(
                    "{0}: {1} does not hash as recorded".format(
                        manifest.name, entry["path"]
                    )
                )
            elif len(raw) != entry["size"]:
                problems.append(
                    "{0}: {1} is not the recorded size".format(
                        manifest.name, entry["path"]
                    )
                )
    return sorted(problems)


class TheRunRecordsTests(unittest.TestCase):
    """The committed records, and the manifests that describe them."""

    def test_the_walk_finds_the_records(self):
        """A list that silently came back empty would pass on nothing."""
        self.assertTrue(run_record_paths(), "no file under runs/ was listed")
        self.assertTrue(
            (PROJECT_ROOT / A_RECORD_WITH_THE_PLACEHOLDER).is_file(),
            "the record the control reads is not there",
        )

    def test_the_manifest_walk_finds_the_manifests(self):
        names = [path.name for path in manifests()]
        self.assertIn(
            MANIFEST_THE_WALK_MUST_FIND,
            names,
            "the manifest walk did not find the manifests under runs/",
        )

    def test_no_run_record_carries_a_launch_path(self):
        """The measurement: the bytes of every listed file, read as bytes."""
        found = files_carrying_a_launch_path(run_record_paths())
        self.assertEqual(
            [],
            found,
            "these files under runs/ carry the path of the checkout the run was "
            "launched from: {0}".format(", ".join(found)),
        )

    def test_every_manifest_entry_matches_its_file(self):
        """Both directions the manifest states: the digest and the size."""
        problems = manifest_problems()
        self.assertEqual(
            [],
            problems,
            "these manifest entries do not match their files: {0}".format(
                "; ".join(problems)
            ),
        )


class TheCheckCanFailTests(unittest.TestCase):
    """A green result is evidence only if the check has been seen to go red."""

    def test_a_launch_path_put_back_into_one_run_record_is_reported(self):
        """One placeholder put back as a launch path names exactly that file.

        The fixture is a copy of a committed record with one ``<checkout>``
        restored to a launch path, and it lives under the system's temporary
        directory: nothing here writes anything under ``runs/``.
        """
        source = (PROJECT_ROOT / A_RECORD_WITH_THE_PLACEHOLDER).read_bytes()
        self.assertIn(
            PLACEHOLDER,
            source,
            "the record the control reads does not carry the placeholder",
        )
        restored = source.replace(PLACEHOLDER, LAUNCH_PATH + b"a-checkout", 1)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy = root / A_RECORD_WITH_THE_PLACEHOLDER
            copy.parent.mkdir(parents=True)
            copy.write_bytes(restored)

            self.assertEqual(
                [A_RECORD_WITH_THE_PLACEHOLDER],
                files_carrying_a_launch_path(
                    [A_RECORD_WITH_THE_PLACEHOLDER], root=root
                ),
                "a launch path put back into a run record was not reported",
            )

    def test_a_record_carrying_only_the_placeholder_is_not_reported(self):
        """The control for the control: the same file, unreplaced, is clean."""
        source = (PROJECT_ROOT / A_RECORD_WITH_THE_PLACEHOLDER).read_bytes()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy = root / A_RECORD_WITH_THE_PLACEHOLDER
            copy.parent.mkdir(parents=True)
            copy.write_bytes(source)

            self.assertEqual(
                [],
                files_carrying_a_launch_path(
                    [A_RECORD_WITH_THE_PLACEHOLDER], root=root
                ),
                "a record carrying only the placeholder was reported",
            )

    def test_a_manifest_entry_whose_digest_moved_is_reported(self):
        """A stale entry is reported, so the green result over the real ones means something."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "runs").mkdir()
            record = root / "runs" / "run.json"
            record.write_bytes(b'{"run_dir": "<checkout>"}\n')

            manifest = root / "runs" / "policy-v6-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "runs/run.json",
                                "sha256": hashlib.sha256(
                                    b'{"run_dir": "somewhere else"}\n'
                                ).hexdigest(),
                                "size": len(b'{"run_dir": "somewhere else"}\n'),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                [
                    "{0}: runs/run.json does not hash as recorded".format(
                        manifest.name
                    )
                ],
                manifest_problems(root),
                "an entry whose digest moved was not reported",
            )

            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "runs/run.json",
                                "sha256": hashlib.sha256(record.read_bytes()).hexdigest(),
                                "size": len(record.read_bytes()),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                [],
                manifest_problems(root),
                "an entry that matches its file was reported",
            )


if __name__ == "__main__":
    unittest.main()
