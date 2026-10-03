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

The second development set
--------------------------
There is a second answer key, ``eval/answers/codex/ground_truth.json``, for the
fifteen cases under ``data/external/codex/``. The same three layers apply to it
and are asserted over it, because the property is about *any* answer key
reaching *any* brief: a second key is a second way for an answer to reach the
agent, and the cases it grades are briefed by the same
``brief.build_brief_for_case``. The needles are the same six names, checked
against that key too, and the second set gets its own falsifiability check for
the same reason the corpus has one -- a guard nobody has seen fail is not
evidence of anything.

The held-out set
--------------
There is a third answer key, ``eval/answers/wild/ground_truth.json``, for the 64
cases under ``data/external/wild/``. It is not a development set: it was drafted
without access to this repository, it is run exactly once from the commit tagged
``freeze-2026-09-30``, and that single run is the only generalisation figure the
submission reports. It is covered by the same three layers, because the property
is about *any* answer key reaching *any* brief and this is the key whose run the
submission's headline claim rests on. Its answer-bearing material sits under
``eval/external/wild/``, which is a fourth way for an answer to reach the agent,
and the two paths are named in the tests rather than left to Layer 1's general
rule. The held-out set gets its own falsifiability checks for the same reason the
other two have them.

The second sealed set
---------------------
There is a fourth answer key, ``eval/answers/wild-v2/ground_truth.json``, for
the 20 cases under ``data/external/wild-v2/``. It is a sealed set on the
held-out set's terms and not the held-out set: it was prepared by OpenAI Codex
for the owner and imported on 2026-10-03, it is run exactly once from the commit
tagged ``freeze-2026-10-03``, and its single run is the submission's
generalisation figure at the policy version 2 its registration fixes. It is
covered by the same three layers for the held-out set's reason -- this is a key
whose run a headline claim rests on -- and its answer-bearing material sits under
``eval/external/wild-v2/``, which is named in the tests rather than left to Layer
1's general rule. It gets its own falsifiability checks too, for the same reason
the other three have them.

The precedent library
---------------------
``tribunal/precedents.py`` is a fourth place an answer could reach an agent: it
reads a run's case file, and a case file is where a grade lives. It is covered
by Layer 1 like every other package module, and it gets three further checks of
its own. No forbidden field name appears in a store it writes; the case being
judged never appears in its own block; and a judge message that carries a
precedents block carries no answer field either. Each check is shown to go RED
on a deliberately dirty fixture before it is shown to be GREEN on the clean one.
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

from eval import development_sets as sets  # noqa: E402
from tribunal import brief, events, loader, pipeline, precedents  # noqa: E402

PACKAGE_DIR = PROJECT_ROOT / "tribunal"
DATA_DIR = PROJECT_ROOT / "data"
CASES_DIR = DATA_DIR / "cases"
INDEX_PATH = DATA_DIR / "index.json"
EVAL_DIR = PROJECT_ROOT / "eval"
ANSWER_KEY_PATH = EVAL_DIR / "answers" / "ground_truth.json"

# The second development set, and its own key. A second key is a second way for
# an answer to reach a brief, so it is guarded by the same layers.
SECOND_KEY_PATH = EVAL_DIR / "answers" / "codex" / "ground_truth.json"
SECOND_SET_DIR = DATA_DIR / "external" / "codex"

# The held-out set, and its own key. It is not a development set: it is run once
# from the commit tagged ``freeze-2026-09-30`` and that single run is the only
# generalisation figure the submission reports. Its key is a third way for an
# answer to reach a brief, so it is guarded by the same layers -- and its
# answer-bearing material sits under ``eval/external/wild/``, which Layer 1
# covers for every package module and which is named explicitly below.
SEALED_KEY_PATH = EVAL_DIR / "answers" / "wild" / "ground_truth.json"
SEALED_SET_DIR = DATA_DIR / "external" / "wild"
SEALED_EXTERNAL_DIR = EVAL_DIR / "external" / "wild"

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


def _named_paths_in_module(path, needles):
    """Every ``(needle, lineno)`` where one module's string literals name a needle.

    The predicate the named-path checks and their dirty fixtures both ask. A
    dirty fixture put through a *different* predicate would show that some
    detector fires without showing that *this* check can.
    """
    return sorted(
        {
            (needle, lineno)
            for value, lineno in _string_literals(path)
            for needle in needles
            if needle in value
        }
    )


def _named_paths_in_package(needles):
    """``(violations, scanned)`` over every module in the ``tribunal`` package.

    ``violations`` is ``(module name, needle, lineno)``; ``scanned`` is the
    number of string literals parsed, so a caller can assert the scan is not
    silently empty.
    """
    violations = []
    scanned = 0
    for path in _package_sources():
        literals = _string_literals(path)
        scanned += len(literals)
        for value, lineno in literals:
            for needle in needles:
                if needle in value:
                    violations.append((path.name, needle, lineno))
    return sorted(violations), scanned


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


def _second_key_records():
    """The second development set's answer key, as a list of records."""
    with SECOND_KEY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _second_set_case_numbers():
    """Every case number the second set's own index lists, in index order."""
    with (SECOND_SET_DIR / "index.json").open("r", encoding="utf-8") as handle:
        return [entry["case_no"] for entry in json.load(handle)]


def _second_set_case(case_no):
    """One second-set case, loaded through its own index."""
    return loader.load_external_set_case(SECOND_SET_DIR, case_no)


def _sealed_key_records():
    """The held-out set's answer key, as a list of records."""
    with SEALED_KEY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sealed_set_case_numbers():
    """Every case number the held-out set's own index lists, in index order."""
    with (SEALED_SET_DIR / "index.json").open("r", encoding="utf-8") as handle:
        return [entry["case_no"] for entry in json.load(handle)]


def _sealed_set_case(case_no):
    """One sealed-set case, loaded through its own index.

    Through ``load_external_set_case``, the loader the set is run with, and
    never through the corpus manifest -- the sealed cases are absent from
    ``data/index.json`` on purpose, so the manifest path would not find them.
    """
    return loader.load_external_set_case(SEALED_SET_DIR, case_no)


# The second sealed set, and its own key. It is a sealed set on the held-out
# set's terms -- prepared without access to this repository, run exactly once
# from the commit tagged ``freeze-2026-10-03``, and that single run is the
# submission's generalisation figure -- and it is a different set, with its own
# case range, its own key and its own answer-bearing directory. Its key is a
# fourth way for an answer to reach a brief, so it is guarded by the same layers
# and its two paths are named explicitly below.
WILD_V2_KEY_PATH = EVAL_DIR / "answers" / "wild-v2" / "ground_truth.json"
WILD_V2_SET_DIR = DATA_DIR / "external" / "wild-v2"
WILD_V2_EXTERNAL_DIR = EVAL_DIR / "external" / "wild-v2"

# The two paths the second sealed set's answers live at, named so a reader can
# see which ones the set added rather than only that Layer 1 covers all of
# ``eval/``.
WILD_V2_ANSWER_PATHS = (
    "eval/answers/wild-v2/ground_truth.json",
    "eval/external/wild-v2",
)


def _wild_v2_key_records():
    """The second sealed set's answer key, as a list of records."""
    with WILD_V2_KEY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _wild_v2_set_case_numbers():
    """Every case number the set's own index lists, in index order."""
    with (WILD_V2_SET_DIR / "index.json").open("r", encoding="utf-8") as handle:
        return [entry["case_no"] for entry in json.load(handle)]


def _wild_v2_set_case(case_no):
    """One case of the second sealed set, loaded through its own index.

    Through ``load_external_set_case``, the loader the set is run with, and never
    through the corpus manifest -- these cases are absent from ``data/index.json``
    on purpose, so the manifest path would not find them.
    """
    return loader.load_external_set_case(WILD_V2_SET_DIR, case_no)


def _brief_violations(case_no):
    """The answer-key field names that reach one case's brief.

    Returns a mapping; empty means clean. A brief that cannot be built at all
    because an answer key is present in it is itself a violation: the property
    this layer asserts is that no answer-key field name reaches a brief, and a
    brief the loader refuses to build because of one is that property already
    broken. Returning a violation here, rather than letting the exception
    escape, is what lets Layer 3 assert on the same function Layer 2 uses.
    """
    return _brief_violations_for_case(loader.load_case(case_no))


def _brief_violations_for_case(case, policy_version=None):
    """The same question, for a case already in hand.

    Split out so a set that is not in the manifest can be asked it, and so the
    falsifiability checks can ask it of a case built in memory rather than
    written to disk. ``policy_version`` is passed through to the brief builder
    when it is given, so a set whose registration fixes a version is asked the
    question about the brief its run will actually be handed rather than about
    version 1's.
    """
    try:
        if policy_version is None:
            built = brief.build_brief_for_case(case)
        else:
            built = brief.build_brief_for_case(case, policy_version=policy_version)
        canonical, _ = brief.brief_digest(built)
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


class SecondDevelopmentSetTest(unittest.TestCase):
    """The guard covers the second answer key, not only the corpus's."""

    def test_the_second_key_is_present_and_is_not_the_corpus_key(self):
        self.assertTrue(SECOND_KEY_PATH.is_file(), "the second answer key is missing")
        self.assertNotEqual(ANSWER_KEY_PATH, SECOND_KEY_PATH)
        self.assertEqual(15, len(_second_key_records()))

    def test_every_needle_occurs_in_the_second_key(self):
        """A mistyped needle would make the scan below unable to fire."""
        key_text = SECOND_KEY_PATH.read_text(encoding="utf-8")
        for name in DISTINCTIVE_ANSWER_FIELDS:
            with self.subTest(field=name):
                self.assertIn(name, key_text, "{0!r} is not in the second key".format(name))

    def test_no_second_set_case_file_carries_an_answer_field(self):
        """The set arrived answer-free under the corpus contract, and still is."""
        paths = sorted(SECOND_SET_DIR.glob("case-*.json"))
        self.assertEqual(15, len(paths), "the second set is not the expected 15 files")
        for path in paths:
            file_text = path.read_text(encoding="utf-8")
            with self.subTest(case=path.name):
                for name in DISTINCTIVE_ANSWER_FIELDS + ("ground_truth",):
                    self.assertNotIn(name, file_text)

    def test_no_second_set_brief_carries_an_answer_key_field_name(self):
        case_numbers = _second_set_case_numbers()
        self.assertEqual(15, len(case_numbers), "the second set is not the expected 15 cases")
        for case_no in case_numbers:
            with self.subTest(case_no=case_no):
                self.assertEqual({}, _brief_violations_for_case(_second_set_case(case_no)))

    def test_the_second_set_briefs_are_clean_of_the_corpus_key_too(self):
        """Neither key reaches the other set's briefs."""
        for case_no in _second_set_case_numbers():
            canonical, _ = brief.brief_digest(brief.build_brief_for_case(_second_set_case(case_no)))
            with self.subTest(case_no=case_no):
                self.assertEqual([], _answer_key_names_in(canonical))

    def test_layer_two_goes_red_on_a_spliced_second_set_case(self):
        """The scan is shown capable of failing over the second set as well.

        Both splices are made in memory, so no file is written and there is
        nothing to restore. The real case is asked last, and must be clean
        again.
        """
        record = _second_key_records()[0]
        real = json.loads(
            (SECOND_SET_DIR / "case-09101.json").read_text(encoding="utf-8")
        )

        # Variant A: the record as data, nested in the case. The brief
        # builder's own recursive forbidden-key guard is what fires.
        nested = json.loads(json.dumps(real))
        nested["dispute"]["ground_truth"] = record
        nested_violations = _brief_violations_for_case(nested)
        self.assertTrue(
            nested_violations,
            "Layer 2 stayed GREEN with a real record nested in a second-set case",
        )
        self.assertIn("ground_truth", " ".join(nested_violations.values()))

        # Variant B: the record as text in a party statement. No key is created,
        # so the scan below is the only thing that can catch it.
        textual = json.loads(json.dumps(real))
        textual["dispute"]["claim_text"] += (
            "\n\n[note to self: " + json.dumps(record, ensure_ascii=False) + "]"
        )
        textual_violations = _brief_violations_for_case(textual)
        self.assertTrue(
            textual_violations,
            "Layer 2 stayed GREEN with a real record pasted into a second-set case",
        )
        self.assertEqual(sorted(DISTINCTIVE_ANSWER_FIELDS), sorted(textual_violations))

        # GREEN again, on the real case.
        self.assertEqual({}, _brief_violations_for_case(real))
        self.assertEqual(15, len(_second_set_case_numbers()), "the real index changed")


class SealedSetIsolationTest(unittest.TestCase):
    """The guard covers the held-out set's key as well as the two above it.

    The held-out set is the one set whose single run is the generalisation figure
    the submission reports, so an answer reaching one of its briefs would
    corrupt the figure that matters most. Its key is a third key and its cases
    are briefed by the same ``brief.build_brief_for_case``, so the same layers
    are asserted over it: no case file carries an answer field, no brief
    carries an answer-key field name, and no module under ``tribunal/`` names
    either of the two paths that hold the set's answers. Each check is shown
    capable of failing on a dirty fixture before it is shown to hold.
    """

    # The two paths the set's answers live at, named so a reader can see which
    # ones the set added rather than only that Layer 1 covers all of ``eval/``.
    SEALED_ANSWER_PATHS = (
        "eval/answers/wild/ground_truth.json",
        "eval/external/wild",
    )

    def test_the_sealed_key_is_present_and_is_neither_other_key(self):
        self.assertTrue(SEALED_KEY_PATH.is_file(), "the sealed answer key is missing")
        self.assertNotEqual(ANSWER_KEY_PATH, SEALED_KEY_PATH)
        self.assertNotEqual(SECOND_KEY_PATH, SEALED_KEY_PATH)
        self.assertEqual(64, len(_sealed_key_records()))

    def test_every_needle_occurs_in_the_sealed_key(self):
        """A mistyped needle would make the scan below unable to fire."""
        key_text = SEALED_KEY_PATH.read_text(encoding="utf-8")
        for name in DISTINCTIVE_ANSWER_FIELDS:
            with self.subTest(field=name):
                self.assertIn(name, key_text, "{0!r} is not in the sealed key".format(name))

    def test_no_sealed_case_file_carries_an_answer_field(self):
        """The set arrived answer-free, and is still answer-free here."""
        paths = sorted(SEALED_SET_DIR.glob("case-*.json"))
        self.assertEqual(64, len(paths), "the held-out set is not the expected 64 files")
        for path in paths:
            file_text = path.read_text(encoding="utf-8")
            with self.subTest(case=path.name):
                for name in DISTINCTIVE_ANSWER_FIELDS + ("ground_truth",):
                    self.assertNotIn(name, file_text)

    def test_no_sealed_brief_carries_an_answer_key_field_name(self):
        case_numbers = _sealed_set_case_numbers()
        self.assertEqual(64, len(case_numbers), "the held-out set is not the expected 64 cases")
        for case_no in case_numbers:
            with self.subTest(case_no=case_no):
                self.assertEqual({}, _brief_violations_for_case(_sealed_set_case(case_no)))

    def test_the_sealed_briefs_are_clean_of_both_development_keys_too(self):
        """No key reaches another set's briefs, and neither reaches this one's."""
        for case_no in _sealed_set_case_numbers():
            canonical, _ = brief.brief_digest(
                brief.build_brief_for_case(_sealed_set_case(case_no))
            )
            with self.subTest(case_no=case_no):
                self.assertEqual([], _answer_key_names_in(canonical))

    def test_no_package_module_names_either_path_that_holds_the_sets_answers(self):
        """The two paths, named, over and above Layer 1's general rule.

        Layer 1 already forbids *any* path under ``eval/`` in a package module.
        This states the same property over the two directories the held-out set's
        answers actually live in, so the set's own contribution to the boundary
        is visible rather than only implied. The predicate is
        :func:`_named_paths_in_package`, which the dirty fixture below asks too,
        so what is shown to fire is this check and not one that resembles it.
        """
        self.assertTrue(SEALED_KEY_PATH.is_file())
        self.assertTrue(SEALED_EXTERNAL_DIR.is_dir())

        violations, scanned = _named_paths_in_package(self.SEALED_ANSWER_PATHS)
        self.assertGreater(scanned, 500, "too few string literals parsed; the scan is broken")
        self.assertEqual(
            [],
            violations,
            "tribunal/{0} names {1}".format(
                ", ".join(sorted({module for module, _needle, _line in violations})),
                ", ".join(sorted({needle for _module, needle, _line in violations})),
            ),
        )

    def test_that_check_goes_red_on_a_dirty_fixture(self):
        """A detector that can never fire would make the check above vacuous."""
        with tempfile.TemporaryDirectory() as tmp:
            dirty = Path(tmp) / "dirty.py"
            dirty.write_text(
                'KEY = "eval/answers/wild/ground_truth.json"\n'
                'GEN = "eval/external/wild/gen"\n',
                encoding="utf-8",
            )
            found = _named_paths_in_module(dirty, self.SEALED_ANSWER_PATHS)
            self.assertEqual(
                {needle for needle in self.SEALED_ANSWER_PATHS},
                {needle for needle, _lineno in found},
                "the dirty fixture's paths were not all reported",
            )

    def test_layer_two_goes_red_on_a_spliced_sealed_case(self):
        """The scan is shown capable of failing over the held-out set as well.

        Both splices are made in memory, so no file is written and there is
        nothing to restore. The real case is asked last, and must be clean
        again.
        """
        record = _sealed_key_records()[0]
        real = json.loads(
            (SEALED_SET_DIR / "case-00501.json").read_text(encoding="utf-8")
        )

        # Variant A: the record as data, nested in the case. The brief
        # builder's own recursive forbidden-key guard is what fires.
        nested = json.loads(json.dumps(real))
        nested["dispute"]["ground_truth"] = record
        nested_violations = _brief_violations_for_case(nested)
        self.assertTrue(
            nested_violations,
            "Layer 2 stayed GREEN with a real record nested in a sealed case",
        )
        self.assertIn("ground_truth", " ".join(nested_violations.values()))

        # Variant B: the record as text in a party statement. No key is created,
        # so the scan below is the only thing that can catch it.
        textual = json.loads(json.dumps(real))
        textual["dispute"]["claim_text"] += (
            "\n\n[note to self: " + json.dumps(record, ensure_ascii=False) + "]"
        )
        textual_violations = _brief_violations_for_case(textual)
        self.assertTrue(
            textual_violations,
            "Layer 2 stayed GREEN with a real record pasted into a sealed case",
        )
        self.assertEqual(sorted(DISTINCTIVE_ANSWER_FIELDS), sorted(textual_violations))

        # GREEN again, on the real case.
        self.assertEqual({}, _brief_violations_for_case(real))
        self.assertEqual(64, len(_sealed_set_case_numbers()), "the real index changed")


class WildV2IsolationTest(unittest.TestCase):
    """The guard covers the second sealed set's key as well as the three above it.

    ``wild-v2`` is the set whose single run is taken *after* everything the
    first four keys measure, at the policy version its registration fixes, so an
    answer reaching one of its briefs would corrupt the figure the submission
    leads with. Its key is a fourth key and its cases are briefed by the same
    ``brief.build_brief_for_case`` -- at the version its run will brief them at,
    which is why every brief below is built at the registration's version and
    not at the default. The same layers are asserted over it: no file of the set
    carries an answer field, no brief carries an answer-key field name, and no
    module under ``tribunal/`` names either of the two paths that hold the set's
    answers. Each check is shown capable of failing on a dirty fixture before it
    is shown to hold.
    """

    def test_the_second_sealed_key_is_present_and_is_no_other_key(self):
        self.assertTrue(WILD_V2_KEY_PATH.is_file(), "the second sealed key is missing")
        for other in (ANSWER_KEY_PATH, SECOND_KEY_PATH, SEALED_KEY_PATH):
            with self.subTest(other=other.name):
                self.assertNotEqual(other, WILD_V2_KEY_PATH)
        self.assertEqual(20, len(_wild_v2_key_records()))

    def test_every_needle_occurs_in_the_second_sealed_key(self):
        """A mistyped needle would make the scan below unable to fire."""
        key_text = WILD_V2_KEY_PATH.read_text(encoding="utf-8")
        for name in DISTINCTIVE_ANSWER_FIELDS:
            with self.subTest(field=name):
                self.assertTrue(
                    name in key_text,
                    "{0!r} is not a field of the second sealed key".format(name),
                )

    def test_no_file_of_the_second_sealed_set_carries_an_answer_field(self):
        """The set arrived answer-free, and is still answer-free here.

        ``index.json`` is scanned with the case files: it is the one file under
        the set's own directory this repository re-serialised on import, so it is
        a file this repository wrote and not one the archive shipped -- and it is
        under the set's directory either way.
        """
        paths = sorted(WILD_V2_SET_DIR.glob("case-*.json")) + [
            WILD_V2_SET_DIR / "index.json"
        ]
        self.assertEqual(21, len(paths), "the second sealed set is not 20 cases and an index")
        for path in paths:
            file_text = path.read_text(encoding="utf-8")
            with self.subTest(case=path.name):
                for name in DISTINCTIVE_ANSWER_FIELDS + ("ground_truth",):
                    self.assertTrue(
                        name not in file_text,
                        "{0} carries {1!r}".format(path.name, name),
                    )

    def test_no_second_sealed_brief_carries_an_answer_key_field_name(self):
        case_numbers = _wild_v2_set_case_numbers()
        self.assertEqual(20, len(case_numbers), "the second sealed set is not 20 cases")
        for case_no in case_numbers:
            with self.subTest(case_no=case_no):
                self.assertEqual(
                    {},
                    _brief_violations_for_case(
                        _wild_v2_set_case(case_no),
                        policy_version=sets.WILD_V2.policy_version,
                    ),
                )

    def test_no_package_module_names_either_path_that_holds_the_sets_answers(self):
        """The two paths, named, over and above Layer 1's general rule.

        Layer 1 already forbids *any* path under ``eval/`` in a package module.
        This states the same property over the two directories the second sealed
        set's answers actually live in, so the set's own contribution to the
        boundary is visible rather than only implied. The predicate is
        :func:`_named_paths_in_package`, which the dirty fixture below asks too,
        so what is shown to fire is this check and not one that resembles it.
        """
        self.assertTrue(WILD_V2_KEY_PATH.is_file())
        self.assertTrue(WILD_V2_EXTERNAL_DIR.is_dir())

        violations, scanned = _named_paths_in_package(WILD_V2_ANSWER_PATHS)
        self.assertGreater(scanned, 500, "too few string literals parsed; the scan is broken")
        self.assertEqual(
            [],
            violations,
            "tribunal/{0} names {1}".format(
                ", ".join(sorted({module for module, _needle, _line in violations})),
                ", ".join(sorted({needle for _module, needle, _line in violations})),
            ),
        )

    def test_that_check_goes_red_on_a_dirty_fixture(self):
        """A detector that can never fire would make the check above vacuous."""
        with tempfile.TemporaryDirectory() as tmp:
            dirty = Path(tmp) / "dirty.py"
            dirty.write_text(
                'KEY = "eval/answers/wild-v2/ground_truth.json"\n'
                'GEN = "eval/external/wild-v2/gen"\n',
                encoding="utf-8",
            )
            found = _named_paths_in_module(dirty, WILD_V2_ANSWER_PATHS)
            self.assertEqual(
                {needle for needle in WILD_V2_ANSWER_PATHS},
                {needle for needle, _lineno in found},
                "the dirty fixture's paths were not all reported",
            )

    def test_layer_two_goes_red_on_a_spliced_second_sealed_case(self):
        """The scan is shown capable of failing over the second sealed set too.

        Both splices are made in memory, so no file is written and there is
        nothing to restore. The briefs are built at the registration's version,
        as the check above builds them. The real case is asked last, and must be
        clean again.
        """
        version = sets.WILD_V2.policy_version
        record = _wild_v2_key_records()[0]
        real = json.loads((WILD_V2_SET_DIR / "case-00701.json").read_text(encoding="utf-8"))

        # Variant A: the record as data, nested in the case. The brief
        # builder's own recursive forbidden-key guard is what fires.
        nested = json.loads(json.dumps(real))
        nested["dispute"]["ground_truth"] = record
        nested_violations = _brief_violations_for_case(nested, policy_version=version)
        self.assertTrue(
            nested_violations,
            "Layer 2 stayed GREEN with a real record nested in a second sealed case",
        )
        self.assertIn("ground_truth", " ".join(nested_violations.values()))

        # Variant B: the record as text in a party statement. No key is created,
        # so the scan below is the only thing that can catch it.
        textual = json.loads(json.dumps(real))
        textual["dispute"]["claim_text"] += (
            "\n\n[note to self: " + json.dumps(record, ensure_ascii=False) + "]"
        )
        textual_violations = _brief_violations_for_case(textual, policy_version=version)
        self.assertTrue(
            textual_violations,
            "Layer 2 stayed GREEN with a real record pasted into a second sealed case",
        )
        self.assertEqual(sorted(DISTINCTIVE_ANSWER_FIELDS), sorted(textual_violations))

        # GREEN again, on the real case.
        self.assertEqual({}, _brief_violations_for_case(real, policy_version=version))
        self.assertEqual(20, len(_wild_v2_set_case_numbers()), "the real index changed")


# --------------------------------------------------------------------------
# The precedent library
# --------------------------------------------------------------------------
# The names a precedents store, a precedents block, or a judge message carrying
# one may never carry. ``rationale`` is deliberately not among them: the clause
# notes that reach every brief contain that word as ordinary prose, and a needle
# on it would be red on a clean message.
PRECEDENT_NEEDLES = (
    DISTINCTIVE_ANSWER_FIELDS
    + tuple(loader.FORBIDDEN_KEYS)
    + ("matched", "expected", "grade")
)

PRECEDENTS_MODULE = PACKAGE_DIR / "precedents.py"

# The case whose closure is in the store, and the case it is matched against.
PRECEDENT_SOURCE_CASE = 102
PRECEDENT_TARGET_CASE = 101


def _keys_in(node, path=""):
    """Every key of a parsed document, with its path."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = "{0}.{1}".format(path, key)
            yield here
            yield from _keys_in(value, here)
    elif isinstance(node, list):
        for position, value in enumerate(node):
            yield from _keys_in(value, "{0}[{1}]".format(path, position))


def _needles_in(text):
    """Which answer-field needles occur as a KEY in the parsed document.

    Asserted over the parsed keys rather than over the raw text. This corpus is
    natural language that discusses field names as ordinary prose -- ``expected``
    and ``matched`` both occur inside policy wording -- so a substring search
    would be red on a clean message. The needles are field *names* and never
    values, which is the same narrow reading Layer 2 makes.
    """
    parsed = json.loads(text)
    return sorted(
        key.rsplit(".", 1)[-1]
        for key in _keys_in(parsed)
        if key.rsplit(".", 1)[-1] in PRECEDENT_NEEDLES
    )


def _eval_paths_in_module(path):
    """Every string literal in one module that names a location under ``eval/``."""
    return [
        (value, lineno)
        for value, lineno in _string_literals(path)
        if _is_eval_path(value)
    ]


def _forbidden_keys_in(entries):
    """The forbidden names that occur as a key anywhere in ``entries``."""
    return sorted(
        key.rsplit(".", 1)[-1]
        for key in _keys_in(entries)
        if key.rsplit(".", 1)[-1] in precedents.FORBIDDEN_FIELD_NAMES
    )


def _precedent_entry(case_no, clause_id="POL-RD-02"):
    """One closure entry, shaped as ``close`` builds it."""
    return {
        "precedent_id": "P-0001",
        "source": {
            "set": precedents.SET_CORPUS,
            "case_no": case_no,
            "dispute_id": "DSP-{0:05d}".format(case_no),
            "run_dir": "runs/<model>",
            "case_sha256": "0" * 64,
        },
        "category": "ROUTE_DEVIATION",
        "system_outcome": {
            "ruling": "ESCALATE",
            "amount_sgd": None,
            "driver_compensation_sgd": None,
            "referrals": [],
        },
        "decision": {
            "ruling": "PARTIAL_REFUND",
            "amount_sgd": None,
            "driver_compensation_sgd": None,
            "referrals": [],
        },
        "clause_ids": [clause_id],
        "amount_contested_sgd": None,
        "summary": "A reviewer closed this case.",
        "closed_by": "A Reviewer",
        "policy_version": 1,
        "supersedes": None,
    }


def _store_with(tmp, entries):
    store = Path(tmp) / precedents.PRECEDENTS_DIRNAME
    for item in entries:
        precedents.append_entry(item, store=store)
    return store


def _kept_referee(clause_id):
    """The one attribute the matching reads: the claims the referee kept."""

    class _Kept:
        kept_claims = {"RIDER": [{"clause_ids": [clause_id]}], "DRIVER": []}

    return _Kept()


def _block_for(store, case_no, dispute_id):
    brief_object = brief.build_brief_for_case(loader.load_case(PRECEDENT_TARGET_CASE))
    library = precedents.Library.load(store)
    return library.block_for(
        brief_object,
        _kept_referee("POL-RD-02"),
        case_no=case_no,
        dispute_id=dispute_id,
    )


class PrecedentIsolationTest(unittest.TestCase):
    """A store, a block and a judge message carry no answer field."""

    def test_the_detector_fires_on_a_real_eval_path_and_not_on_prose(self):
        """A detector that can never fire would make the check below vacuous."""
        for text in ("eval", "eval/answers/ground_truth.json"):
            with self.subTest(text=text):
                self.assertTrue(_is_eval_path(text))
        for text in ("evaluation-only", "precedents/precedents.jsonl", "the harness"):
            with self.subTest(text=text):
                self.assertFalse(_is_eval_path(text))

    def test_the_precedents_module_names_no_path_under_eval(self):
        self.assertTrue(PRECEDENTS_MODULE.is_file(), "tribunal/precedents.py is missing")
        self.assertEqual([], _eval_paths_in_module(PRECEDENTS_MODULE))

    def test_that_check_goes_red_on_a_dirty_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirty = Path(tmp) / "dirty.py"
            dirty.write_text(
                'GROUND_TRUTH = "eval/answers/ground_truth.json"\n', encoding="utf-8"
            )
            self.assertEqual(1, len(_eval_paths_in_module(dirty)))

    def test_no_forbidden_field_name_appears_in_the_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store_with(tmp, [_precedent_entry(PRECEDENT_SOURCE_CASE)])
            entries = precedents.read_entries(precedents.store_path(store))
            self.assertEqual(1, len(entries))
            self.assertEqual([], _forbidden_keys_in(entries))

    def test_the_store_check_goes_red_on_a_spliced_entry(self):
        # The dirty fixture. The entry is written past ``append_entry`` -- which
        # is what refuses it -- so what is seen to fail here is the walk's own
        # check and not the writer's.
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / precedents.PRECEDENTS_DIRNAME
            dirty = _precedent_entry(PRECEDENT_SOURCE_CASE)
            dirty["matched"] = True
            log = events.EventLog(
                precedents.store_path(store), invocation_id="a-dirty-fixture"
            )
            log.record(
                precedents.EVENT_CLOSURE,
                case_no=PRECEDENT_SOURCE_CASE,
                **dirty
            )
            entries = precedents.read_entries(precedents.store_path(store))
            self.assertEqual(["matched"], _forbidden_keys_in(entries))

    def test_the_case_being_judged_never_appears_in_its_own_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store_with(tmp, [_precedent_entry(PRECEDENT_TARGET_CASE)])
            block, ids = _block_for(store, PRECEDENT_TARGET_CASE, "DSP-00101")
            self.assertIsNone(block)
            self.assertEqual((), ids)

    def test_another_case_resting_on_the_same_clause_is_shown(self):
        # The clean fixture's other half: the block is empty for the case itself
        # and not empty for a different case resting on the same clause, so the
        # test above is about the exclusion rather than about the matching
        # having failed for some other reason.
        with tempfile.TemporaryDirectory() as tmp:
            store = _store_with(tmp, [_precedent_entry(PRECEDENT_SOURCE_CASE)])
            block, ids = _block_for(store, PRECEDENT_TARGET_CASE, "DSP-00101")
            self.assertEqual(("P-0001",), ids)
            self.assertEqual("ROUTE_DEVIATION", block["items"][0]["category"])
            self.assertEqual("PARTIAL_REFUND", block["items"][0]["ruling"])

    def test_a_judge_message_with_the_switch_on_carries_no_answer_field(self):
        brief_object = brief.build_brief_for_case(loader.load_case(PRECEDENT_TARGET_CASE))
        brief_json, _ = brief.brief_digest(brief_object)
        claims = [
            {
                "claim_id": "C1",
                "evidence_id": "EV-GPS-00101",
                "clause_ids": ["POL-RD-02"],
            }
        ]
        without = pipeline._judge_user_message(claims, [], brief_json)
        block = precedents.block([_precedent_entry(PRECEDENT_SOURCE_CASE)])
        with_block = pipeline._judge_user_message(
            claims, [], brief_json, precedents=block
        )

        # The precondition: every needle is absent from the message WITHOUT the
        # block, so a needle that started colliding with clean prose would fail
        # here rather than passing silently below.
        self.assertEqual([], _needles_in(without))
        self.assertEqual([], _needles_in(with_block))

        # And the block really is in the message, so the assertion above is
        # about the block's own content and not about it being missing.
        parsed = json.loads(with_block)
        self.assertIn("precedents", parsed)
        self.assertEqual(precedents.NOTE, parsed["precedents"]["note"])
        self.assertEqual(
            ["P-0001"], [item["precedent_id"] for item in parsed["precedents"]["items"]]
        )

    def test_that_check_goes_red_on_a_block_carrying_an_answer_field(self):
        brief_object = brief.build_brief_for_case(loader.load_case(PRECEDENT_TARGET_CASE))
        brief_json, _ = brief.brief_digest(brief_object)
        claims = [
            {
                "claim_id": "C1",
                "evidence_id": "EV-GPS-00101",
                "clause_ids": ["POL-RD-02"],
            }
        ]
        spliced = precedents.block([_precedent_entry(PRECEDENT_SOURCE_CASE)])
        spliced["items"][0]["matched"] = True
        message = pipeline._judge_user_message(
            claims, [], brief_json, precedents=spliced
        )
        self.assertEqual(["matched"], _needles_in(message))


if __name__ == "__main__":
    unittest.main()
