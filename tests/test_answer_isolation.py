"""Isolation guard: the answer key and the Agent runtime path never meet.

Three layers, each proving more than the one before.

**Layer 1 — path.** No module under ``tribunal/`` reads anything under
``eval/``. Asserted over the package source, and against the parsed AST rather
than the raw text, so a docstring that merely discusses evaluation cannot trip
it and a docstring that hides a real path cannot slip past it.

**Layer 2 — content.** For every case in the manifest, the serialised brief
carries none of the answer key's distinctive field names.

**Layer 3 — falsifiability.** Layer 2 is proved capable of failing. The corpus
is copied to a temporary directory, one real ground-truth record is spliced into
one case file there, and Layer 2 is shown to go RED — and GREEN again on the
untouched corpus.

Why Layer 3 exists: this repository has already shipped a check that could not
fail, and the lesson is recorded in ``START-HERE.md``. A guard nobody has ever
seen fail is not evidence of anything.

On the string scan in Layer 2
-----------------------------
``START-HERE.md`` forbids proving a structural property with a string search,
because this corpus is natural language that discusses field names as ordinary
prose. Layer 2 is a deliberate, narrow exception, and it is narrow in three
ways: the needles are field *names* and never values; each needle was confirmed
absent from a clean brief for all 29 cases before being relied on; and the
confirmation is re-run as part of the test, so a needle that starts colliding
with clean prose fails here rather than passing silently. Values are never
matched: ``ESCALATE`` and ``NO_ACTION`` occur legitimately throughout the policy
prose, and a check written against them would be red on a clean corpus.

``rationale`` is the one name from the answer key's field list that is **not**
used as a needle, because it already occurs in clean policy prose: the
NO_SHOW_CHARGE category policy carries the sentence "The rationale is that a
rider who is at the pin and actively trying to coordinate has done everything
the platform asks" in a clause ``notes`` field, which reaches the brief for all
14 no-show cases whenever clause notes are carried — and ``build_brief``'s
default carries them. A needle on ``rationale`` would therefore be red on a
clean corpus. The other six names are clean.

Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, loader  # noqa: E402

PACKAGE_DIR = PROJECT_ROOT / "tribunal"
DATA_DIR = PROJECT_ROOT / "data"
CASES_DIR = DATA_DIR / "cases"
INDEX_PATH = DATA_DIR / "index.json"
EVAL_DIR = PROJECT_ROOT / "eval"
ANSWER_KEY_PATH = EVAL_DIR / "answers" / "ground_truth.json"

# The case the spliced record is planted in, in Layer 3.
TARGET_CASE = 208

# The answer key's field names, minus ``rationale`` — see the module docstring.
DISTINCTIVE_ANSWER_FIELDS = (
    "expected_ruling",
    "expected_amount_sgd",
    "expected_driver_compensation_sgd",
    "expected_referrals",
    "governing_clauses",
    "difficulty",
)

# A path is a violation when ``eval`` is one of its segments. Matching on
# segments rather than on the substring "eval" is what keeps the detector off
# ordinary English: ``evaluation-only`` is one segment and is not ``eval``,
# while ``eval/answers/ground_truth.json`` and the bare ``eval`` are.
_SEPARATORS = re.compile(r"[\\/]+")


def _package_sources():
    """Every module in the ``tribunal`` package."""
    return sorted(
        path
        for path in PACKAGE_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _string_literals(path):
    """Every string literal in one module, as ``(value, lineno)``.

    Parsed, not grepped: comments and docstring *contents* still arrive here as
    literals, which is intended — a module that names the answer key's path
    inside a docstring is naming it — but a bare word such as ``evaluation``
    does not become a path segment and so does not become a violation.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        (node.value, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _is_eval_path(text):
    """True when ``text`` names a location under ``eval/``."""
    if not isinstance(text, str) or not text.strip():
        return False
    segments = [segment for segment in _SEPARATORS.split(text.strip()) if segment]
    return "eval" in segments


def _answer_key_records():
    """The answer key, as a list of records."""
    with ANSWER_KEY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _manifest_case_numbers():
    """Every case number the manifest lists, in manifest order."""
    with INDEX_PATH.open("r", encoding="utf-8") as handle:
        return [entry["case_no"] for entry in json.load(handle)]


def _answer_key_names_in(text):
    """Which distinctive answer-key field names occur in ``text``."""
    return sorted(name for name in DISTINCTIVE_ANSWER_FIELDS if name in text)


def _brief_violations(case_no):
    """The answer-key field names that reach one case's brief.

    Returns a mapping; empty means clean. A brief that cannot be built at all
    because an answer key is present in it is itself a violation: the property
    this layer asserts is that no answer-key field name reaches a brief, and a
    brief the loader refuses to build because of one is that property already
    broken. Returning a violation here, rather than letting the exception
    escape, is what lets Layer 3 assert on the same function Layer 2 uses.
    """
    try:
        canonical, _ = brief.brief_digest(brief.build_brief(case_no))
    except loader.ForbiddenKeyError as exc:
        return {"<brief build refused>": str(exc)}
    return {name: name for name in _answer_key_names_in(canonical)}


class Layer1PathTest(unittest.TestCase):
    """No module under ``tribunal/`` reads anything under ``eval/``."""

    def test_detector_recognises_eval_paths_and_ignores_lookalikes(self):
        """A detector that can never fire would make the layer below vacuous."""
        for path in ("eval", "eval/answers", "eval/answers/ground_truth.json", "eval\\answers"):
            with self.subTest(path=path):
                self.assertTrue(_is_eval_path(path), "{0!r} should be an eval path".format(path))
        for text in ("evaluation-only", "data/answers/", "retrieval", "level", "policy"):
            with self.subTest(text=text):
                self.assertFalse(_is_eval_path(text), "{0!r} is not an eval path".format(text))

    def test_no_package_module_names_a_path_under_eval(self):
        sources = _package_sources()
        self.assertTrue(sources, "no modules found under tribunal/")

        scanned = 0
        violations = []
        for path in sources:
            for value, lineno in _string_literals(path):
                scanned += 1
                if _is_eval_path(value):
                    violations.append(
                        "{0}:{1}: {2!r}".format(path.relative_to(PROJECT_ROOT), lineno, value)
                    )

        # If the parse silently produced nothing, the assertion below would pass
        # for the wrong reason.
        self.assertGreater(scanned, 500, "too few string literals parsed; the scan is broken")
        self.assertEqual([], violations, "tribunal/ names a path under eval/")

    def test_loader_roots_resolve_outside_eval(self):
        """The loader's own roots are the paths that actually get read."""
        for name in ("DATA_DIR", "CASES_DIR", "POLICY_DIR", "INDEX_PATH"):
            with self.subTest(constant=name):
                resolved = Path(getattr(loader, name)).resolve()
                self.assertFalse(
                    resolved.is_relative_to(EVAL_DIR.resolve()),
                    "loader.{0} resolves under eval/: {1}".format(name, resolved),
                )


class Layer2ContentTest(unittest.TestCase):
    """No brief carries an answer-key field name."""

    def test_the_answer_key_is_present_and_is_the_single_source(self):
        """The guard is meaningless if there is nothing to guard against."""
        self.assertTrue(ANSWER_KEY_PATH.is_file(), "the answer key is missing")
        self.assertEqual(
            ["README.md", "ground_truth.json"],
            sorted(path.name for path in ANSWER_KEY_PATH.parent.iterdir() if path.is_file()),
            "eval/answers/ is not the single committed answer key",
        )

    def test_every_needle_occurs_in_the_answer_key(self):
        """A mistyped needle would make the scan below unable to fire."""
        key_text = ANSWER_KEY_PATH.read_text(encoding="utf-8")
        for name in DISTINCTIVE_ANSWER_FIELDS:
            with self.subTest(field=name):
                self.assertIn(name, key_text, "{0!r} is not a field of the answer key".format(name))

    def test_no_needle_occurs_in_a_clean_brief(self):
        """The needles must be clean, or the scan below is red on a clean corpus.

        ``rationale`` fails this and is therefore excluded from the needle list.
        """
        for name in DISTINCTIVE_ANSWER_FIELDS:
            offenders = [
                case_no
                for case_no in _manifest_case_numbers()
                if name in brief.brief_digest(brief.build_brief(case_no))[0]
            ]
            with self.subTest(field=name):
                self.assertEqual(
                    [],
                    offenders,
                    "{0!r} already occurs in a clean brief for cases {1}".format(name, offenders),
                )

    def test_no_brief_carries_an_answer_key_field_name(self):
        case_numbers = _manifest_case_numbers()
        self.assertEqual(29, len(case_numbers), "the corpus is not the expected 29 cases")
        for case_no in case_numbers:
            with self.subTest(case_no=case_no):
                self.assertEqual({}, _brief_violations(case_no))


class Layer3FalsifiabilityTest(unittest.TestCase):
    """Layer 2 is proved capable of failing.

    The corpus is copied to a temporary directory, a real ground-truth record is
    spliced into one case file in that copy, and the loader is pointed at the
    copy. Layer 2 must go RED. Nothing in the test may regenerate or overwrite
    the spliced file — that is how the earlier unfailable check came about — so
    the file's bytes are captured after the splice and compared again afterwards.

    The temporary directory is created by the test itself and holds a copy of
    the corpus; nothing outside this workspace is read to build it.
    """

    def _splice(self, target, mutate):
        """Write a spliced case file and return the bytes that were written."""
        case = json.loads(target.read_text(encoding="utf-8"))
        mutate(case)
        target.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
        return target.read_bytes()

    def _loader_pointed_at(self, root):
        return mock.patch.multiple(
            loader,
            DATA_DIR=root,
            CASES_DIR=root / "cases",
            INDEX_PATH=root / "index.json",
        )

    def test_layer_two_goes_red_on_a_spliced_corpus_and_green_again_after(self):
        real_case_path = CASES_DIR / "case-{0:05d}.json".format(TARGET_CASE)
        real_case_bytes = real_case_path.read_bytes()

        record = next(
            entry for entry in _answer_key_records() if entry["case_no"] == TARGET_CASE
        )

        with tempfile.TemporaryDirectory(prefix="tribunal-answer-isolation-") as tmp:
            root = Path(tmp)
            (root / "cases").mkdir()
            for source in sorted(CASES_DIR.glob("*.json")):
                shutil.copy2(source, root / "cases" / source.name)
            shutil.copy2(INDEX_PATH, root / "index.json")

            target = root / "cases" / "case-{0:05d}.json".format(TARGET_CASE)

            # Variant A: the record as data, nested inside the case file. The
            # loader's recursive forbidden-key guard is the control that fires
            # here, and it fires while the brief is being built.
            written = self._splice(target, lambda case: case["dispute"].update({"ground_truth": record}))
            with self._loader_pointed_at(root):
                self.assertEqual(root / "cases", loader.CASES_DIR, "the loader was not repointed")
                self.assertIn(
                    "ground_truth",
                    loader.load_case(TARGET_CASE)["dispute"],
                    "the splice did not reach the loaded case",
                )
                nested = _brief_violations(TARGET_CASE)
                self.assertTrue(
                    nested,
                    "Layer 2 stayed GREEN with a real ground-truth record nested in a case file",
                )
                self.assertIn(
                    "ground_truth",
                    " ".join(nested.values()),
                    "Layer 2 went red for a reason other than the spliced record: {0}".format(nested),
                )
            self.assertEqual(written, target.read_bytes(), "the spliced file was rewritten")

            # Variant B: the record as text inside a party statement. No key is
            # created, so the loader's guard stays silent and Layer 2's own scan
            # is the only thing that can catch this — which is the point.
            shutil.copy2(real_case_path, target)
            written = self._splice(
                target,
                lambda case: case["dispute"].update(
                    {
                        "claim_text": case["dispute"]["claim_text"]
                        + "\n\n[note to self: the expected outcome is "
                        + json.dumps(record, ensure_ascii=False)
                        + "]"
                    }
                ),
            )
            with self._loader_pointed_at(root):
                textual = _brief_violations(TARGET_CASE)
                self.assertTrue(
                    textual,
                    "Layer 2 stayed GREEN with a real ground-truth record pasted into a case file",
                )
                self.assertEqual(
                    sorted(DISTINCTIVE_ANSWER_FIELDS),
                    sorted(textual),
                    "Layer 2's scan did not find every spliced field name",
                )
            self.assertEqual(written, target.read_bytes(), "the spliced file was rewritten")

        # GREEN again, on the untouched corpus, with the real loader restored.
        self.assertEqual({}, _brief_violations(TARGET_CASE))
        self.assertEqual(
            real_case_bytes,
            real_case_path.read_bytes(),
            "the real corpus was modified by this test",
        )
        self.assertEqual(
            29,
            len(_manifest_case_numbers()),
            "the real manifest changed while the test ran",
        )


if __name__ == "__main__":
    unittest.main()
