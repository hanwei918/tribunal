"""The policy Ji Guofang drafted is kept here as a roadmap, and nothing reads it.

``docs/roadmap/policy-v2/`` holds the policy base Ji Guofang drafted on
2026-10-07 against published platform rules. It arrived as an archive and is kept
here byte for byte. On 2026-10-08 the same policy was **added to the runtime as
policy version 3**, under ``policy/v3/``: a separate base, not the default, and
**not measured** -- no run exists at version 3. ``policy/`` still holds the
version-1 bytes and amendment ``0001``, ``BASE_VERSION`` is still 1, and no
figure in this repository was produced under the draft. This module holds the
folder to the archive it came from, and holds the repository to reading
``policy/v3/`` rather than this folder.

Five things are asserted:

* **The folder is the archive, byte for byte.** Every file the archive carried
  except the two that are deliberately left out is here, each one's digest is
  the digest the folder's README states, and the two omissions are named in that
  README and absent from the folder.
* **The two omissions are the right two.** `eval/backfill_platform_policy.py`
  rewrites case files in all four sets, including the held-out set's and the
  second sealed set's, so it must not be in this repository even as a document;
  `policy/history/v1/` is byte-identical to the live `policy/` files and
  amendment `0001`, so a second copy of it would be a copy that can drift.
* **The draft is not the version in force.** The live `policy/` files are not
  the draft's, `BASE_VERSION` is still 1, and the draft's own clause counts
  (8 / 10 / 13) are not the live ones (3 / 9 / 12). The draft's files here still
  carry `2.0.0`, because this folder is the archive as received; the runtime copy
  at `policy/v3/` carries `3.0.0`.
* **Nothing reads it.** No module under `tribunal/`, `eval/` or `ops/` names
  `docs/roadmap/`, and the backfill script's name appears nowhere in the tree.
* **The README says what it is.** The folder's README says who drafted it and
  when, that it is now added as policy version 3 and is not the default and not
  yet measured, and what making it the default would take; and the repository's
  own README carries the one roadmap line.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import policy_versions  # noqa: E402

ROADMAP = PROJECT_ROOT / "docs" / "roadmap" / "policy-v2"
ROADMAP_README = ROADMAP / "README.md"
REPOSITORY_README = PROJECT_ROOT / "README.md"

# The archive the folder was unpacked from, and its digest. Named here because
# the README's claim about it is a claim worth being able to check.
ARCHIVE = "tribunal-policy-v2.zip"
ARCHIVE_SHA256 = "78488e85363e8289a9aecf93e93d929205094433069922b8a2eec135b5c33aed"

# The files the archive carried and this folder keeps.
KEPT_FILES = (
    "case901/case-00901.json",
    "case901/mapping-v2-additions.json",
    "docs/PUBLIC-CONTRACT-additions.md",
    "docs/README-policy-sources.md",
    "policy/POLICY-V2-CHANGES.md",
    "policy/amendments/README.md",
    "policy/general.json",
    "policy/no_show.json",
    "policy/route_deviation.json",
)

# The backfill script the archive carried and this folder leaves out, as a glob
# pattern of its own. It is a constant and not a literal at the call site because
# a listing that names the policy directory is what
# ``tests.test_policy_versions.NothingGlobsThePolicyDirectoryTests`` forbids: the
# pattern's own line is not a listing, and the line that lists is the one that
# carries the call.
BACKFILL_SCRIPT_PATTERN = "backfill_platform_policy*"

# The two paths the archive carried and this folder leaves out.
LEFT_OUT = (
    "eval/backfill_platform_policy.py",
    "policy/history/v1/general.json",
    "policy/history/v1/no_show.json",
    "policy/history/v1/route_deviation.json",
    "policy/history/v1/0001-pol-rd-13.json",
)

# The clause counts the draft states for its three files, and the live ones.
DRAFT_CLAUSE_COUNTS = {"general.json": 8, "no_show.json": 10, "route_deviation.json": 13}
LIVE_CLAUSE_COUNTS = {"general.json": 3, "no_show.json": 9, "route_deviation.json": 12}

# The directories whose modules must not reach the roadmap.
READERS = ("tribunal", "eval", "ops")

DIGEST_TABLE_HEADER = ("file", "sha256")

# The directories that are not repository content, as ``tests/test_language.py``
# has them: version control, the agent's own local state, caches, scratch roots,
# and the recorded runs.
NOT_REPOSITORY_CONTENT = frozenset(
    {".git", ".workbuddy-ai", "__pycache__", ".venv", "tmp", "output", "runs"}
)


@functools.lru_cache(maxsize=None)
def text_files() -> Tuple[Path, ...]:
    """Every tracked text file outside ``runs/``, in path order.

    Cached because three tests scan the tree and the tree does not change under
    a test run; without it the same few hundred files would be read three times.
    """
    found: List[Path] = []
    for path in sorted(PROJECT_ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if any(part in NOT_REPOSITORY_CONTENT for part in relative.parts[:-1]):
            continue
        try:
            path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found.append(path)
    return tuple(found)


@functools.lru_cache(maxsize=None)
def contents(path: Path) -> str:
    """One file's text, read once."""
    return path.read_text(encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def roadmap_files() -> List[str]:
    return sorted(
        str(path.relative_to(ROADMAP))
        for path in ROADMAP.rglob("*")
        if path.is_file() and path != ROADMAP_README
    )


def digest_table(text: str) -> Dict[str, str]:
    """``{file: sha256}`` from the folder README's own table."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.strip().startswith("|") and tuple(cells) == DIGEST_TABLE_HEADER:
            start = index
            break
    if start is None:
        raise AssertionError("the roadmap README has no {0} table".format(DIGEST_TABLE_HEADER))
    found: Dict[str, str] = {}
    for line in lines[start + 2 :]:
        if not line.strip().startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2:
            continue
        found[cells[0].strip("`")] = cells[1].strip("`")
    return found


class TheRoadmapFolderTests(unittest.TestCase):
    """The folder is the archive, byte for byte, minus the two omissions."""

    @classmethod
    def setUpClass(cls):
        cls.text = ROADMAP_README.read_text(encoding="utf-8")

    def test_the_folder_holds_exactly_the_files_it_lists(self):
        self.assertEqual(list(KEPT_FILES), roadmap_files())

    def test_every_listed_digest_is_the_file_s_digest(self):
        table = digest_table(self.text)
        self.assertEqual(set(KEPT_FILES), set(table))
        for name, recorded in sorted(table.items()):
            with self.subTest(file=name):
                self.assertEqual(digest(ROADMAP / name), recorded)

    def test_the_table_is_not_empty_and_every_digest_is_a_digest(self):
        """A table that listed nothing would pass the check above."""
        table = digest_table(self.text)
        self.assertEqual(len(KEPT_FILES), len(table))
        for name, recorded in table.items():
            with self.subTest(file=name):
                self.assertRegex(recorded, r"^[0-9a-f]{64}$")

    def test_the_two_omissions_are_absent(self):
        for name in LEFT_OUT:
            with self.subTest(path=name):
                self.assertFalse((ROADMAP / name).exists())

    def test_the_readme_names_the_omissions_and_says_why(self):
        for needle in (
            "eval/backfill_platform_policy.py",
            "policy/history/v1/",
            "even as a document",
            "cmp",
            "byte-identical",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.text)

    def test_the_backfill_script_is_not_in_the_repository(self):
        """It rewrites case files in all four sets, so it is not even a document."""
        for path in sorted(PROJECT_ROOT.rglob(BACKFILL_SCRIPT_PATTERN)):
            with self.subTest(path=str(path)):
                self.fail("{0} is in the repository".format(path))

    def test_no_module_refers_to_the_backfill_script(self):
        """No code names it, so nothing could run or import it.

        The scan is over ``.py`` files and skips this module, which has to name
        the script in order to forbid it. A **document** that names it is
        required, not forbidden: the folder's README says it was left out and
        why, and the draft's own notes describe what it did.
        """
        for path in text_files():
            if path.suffix != ".py" or path == Path(__file__).resolve():
                continue
            with self.subTest(module=str(path.relative_to(PROJECT_ROOT))):
                self.assertNotIn("backfill_platform_policy", contents(path))

    def test_the_documents_that_name_it_are_the_ones_that_should(self):
        """The control for the scan above: the name is present where it belongs.

        Four documents, and each one has a reason to name the script:

        * the folder's README says the script was left out and why;
        * the draft's own ``POLICY-V2-CHANGES.md`` describes what it did;
        * ``docs/buddy-log/README.md`` records the session that unpacked the
          bundle and left the script out, so it names it in the same breath;
        * ``policy/v3/CHANGES.md`` is that same draft text as the runtime keeps
          it, with a note saying the script was not added and why.

        The buddy log and ``policy/v3/CHANGES.md`` were added on 2026-10-08. The
        buddy log is a record of what a session did, and the session
        legitimately wrote down that the script was left out of the repository;
        the row was written after the module was last run, so the set this test
        computes had one more member than the set it expected. ``CHANGES.md`` is
        the draft's own account, which names the script in its own text, and the
        note above it names it again. The scan itself is unchanged -- the control
        is widened, not loosened, and a fifth document that names the script
        still fails.
        """
        naming = {
            str(path.relative_to(PROJECT_ROOT))
            for path in text_files()
            if path.suffix != ".py" and "backfill_platform_policy" in contents(path)
        }
        self.assertEqual(
            {"docs/roadmap/policy-v2/README.md",
             "docs/roadmap/policy-v2/policy/POLICY-V2-CHANGES.md",
             "docs/buddy-log/README.md",
             "policy/v3/CHANGES.md"},
            naming,
        )


class TheDraftIsNotTheVersionInForceTests(unittest.TestCase):
    """The version in force is version 1 plus amendment 0001, and not this draft.

    The draft is now available to the runtime as version 3, so "not applied"
    would be the wrong words. What is still true, and what these tests hold, is
    that the draft is not the **default** and not what ``policy/`` holds: the
    live three files are version 1's, ``BASE_VERSION`` is 1, and the draft's
    files in this folder are untouched.
    """

    def test_the_live_policy_files_are_not_the_draft_s(self):
        for name in ("general.json", "no_show.json", "route_deviation.json"):
            with self.subTest(file=name):
                self.assertNotEqual(
                    digest(PROJECT_ROOT / "policy" / name),
                    digest(ROADMAP / "policy" / name),
                )

    def test_the_clause_counts_are_the_live_ones_and_not_the_draft_s(self):
        for name, live in sorted(LIVE_CLAUSE_COUNTS.items()):
            with self.subTest(file=name):
                loaded = json.loads((PROJECT_ROOT / "policy" / name).read_text(encoding="utf-8"))
                self.assertEqual(live, len(loaded["clauses"]))
                drafted = json.loads((ROADMAP / "policy" / name).read_text(encoding="utf-8"))
                self.assertEqual(DRAFT_CLAUSE_COUNTS[name], len(drafted["clauses"]))
                self.assertNotEqual(live, DRAFT_CLAUSE_COUNTS[name])

    def test_base_version_is_still_one(self):
        self.assertEqual(1, policy_versions.BASE_VERSION)

    def test_the_live_amendments_directory_still_holds_amendment_0001(self):
        self.assertTrue((PROJECT_ROOT / "policy" / "amendments" / "0001-pol-rd-13.json").is_file())
        self.assertFalse((ROADMAP / "policy" / "amendments" / "0001-pol-rd-13.json").exists())

    def test_the_draft_s_policy_files_are_valid_json(self):
        for name in sorted(DRAFT_CLAUSE_COUNTS):
            with self.subTest(file=name):
                loaded = json.loads((ROADMAP / "policy" / name).read_text(encoding="utf-8"))
                self.assertEqual("2.0.0", loaded["version"])


class TheNothingReadsItTests(unittest.TestCase):
    """No module under ``tribunal/``, ``eval/`` or ``ops/`` reaches the roadmap."""

    def modules(self) -> List[Path]:
        found: List[Path] = []
        for package in READERS:
            found.extend(sorted((PROJECT_ROOT / package).rglob("*.py")))
        return found

    def test_the_walk_finds_the_packages(self):
        """The check below cannot pass by finding nothing to check."""
        found = self.modules()
        self.assertTrue(found)
        names = {path.name for path in found}
        for required in ("loader.py", "grade.py", "risk.py"):
            with self.subTest(module=required):
                self.assertIn(required, names)

    def test_no_module_names_the_roadmap(self):
        for path in self.modules():
            text = path.read_text(encoding="utf-8")
            with self.subTest(module=str(path.relative_to(PROJECT_ROOT))):
                self.assertIsNone(
                    re.search(r"roadmap", text, re.IGNORECASE),
                    "{0} names the roadmap".format(path.name),
                )

    def test_the_search_can_fail(self):
        """A control: the pattern is capable of matching."""
        self.assertIsNotNone(re.search(r"roadmap", "docs/roadmap/policy-v2", re.IGNORECASE))


class TheReadmeSaysWhatItIsTests(unittest.TestCase):
    """The folder's README, and the repository's one roadmap line."""

    @classmethod
    def setUpClass(cls):
        cls.text = ROADMAP_README.read_text(encoding="utf-8")
        cls.repository = REPOSITORY_README.read_text(encoding="utf-8")

    def test_the_readme_names_the_drafter_and_the_date(self):
        self.assertIn("Ji Guofang", self.text)
        self.assertIn("2026-10-07", self.text)

    def test_the_readme_says_it_is_added_but_not_the_default_and_not_measured(self):
        # Compared with the README's own line wrapping removed, so that a
        # sentence reflowed by an editor is not a failing test. The repository
        # README's roadmap line is read the same way, below.
        normalised = " ".join(self.text.split())
        for needle in (
            "Drafted, added as policy version 3, not the default, and not yet measured",
            "no figure anywhere in this repository was produced under this draft",
            "no run exists at version 3",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, normalised)

    def test_the_readme_says_what_making_it_the_default_would_take(self):
        normalised = " ".join(self.text.split())
        for needle in (
            "a development run at version 3",
            "the default moves to version 3 only if it does no worse",
            "a freeze tag",
            "one sealed run",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, normalised)

    def test_the_readme_says_the_sources_note_describes_the_draft_as_in_force(self):
        self.assertIn("as if it were in force", self.text)
        self.assertIn("README-policy-sources.md", self.text)

    def test_the_readme_carries_the_archive_and_its_digest(self):
        self.assertIn(ARCHIVE, self.text)
        self.assertIn(ARCHIVE_SHA256, self.text)

    def test_the_repository_readme_carries_the_one_roadmap_line(self):
        """The line is one sentence, wherever the README wraps it.

        It named the draft as a roadmap and said it was not applied and not
        measured. On 2026-10-08 the draft was added as policy version 3, so the
        line now says what is true of it: it is added, it is not the default, and
        no run has been made at it.
        """
        sentence = (
            "A policy base version 3 aligned with published platform rules is "
            "added as `policy/v3/`; it is not the default and no run has been "
            "made at it."
        )
        self.assertIn(sentence, " ".join(self.repository.split()))

    def test_the_repository_readme_does_not_call_the_corpus_an_official_sample(self):
        """The corpus is this team's; the organisers supplied one case."""
        lowered = self.repository.lower()
        for phrase in ("official corpus", "organiser corpus", "organiser sample corpus"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, lowered)


if __name__ == "__main__":
    unittest.main()
