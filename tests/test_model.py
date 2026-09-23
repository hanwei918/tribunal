"""Tests for ``tribunal.model``: the one place the runtime model is decided.

No network, no credential, no model call. What is under test here is not a
behaviour of the system so much as the shape of a decision: that it is written
down once, that the entry points read it, and that the note it points at is
there. A decision recorded in three places is three decisions, and the third one
is the one that surprises somebody.
"""

from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import model  # noqa: E402

# The one file allowed to hold the model id as a live value.
DECLARATION = "tribunal/model.py"

# Where a live value would matter. ``docs/`` is prose and is covered by the note
# test below, which requires the note to name the decision it is evidence for.
SOURCE_DIRS = ("tribunal", "eval", "ui")


def _docstring_constants(tree):
    """The ids of Constant nodes that are docstrings rather than values.

    A docstring may name the model as an example; an assignment may not, because
    that is a second place the decision would live. The two are the same kind of
    node in the tree, so they are told apart by position: a docstring is the
    first statement of a module, class or function.
    """
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                found.add(id(body[0].value))
    return found


def live_mentions_of(value, directories=None, base=None):
    """Every place a string equal to ``value`` is a live value, not prose.

    Returns ``"<path>:<line>"`` entries, sorted, so a failure names the places
    to look at rather than only the fact that there is more than one. Paths are
    shown relative to ``base`` (the project root by default); a scan rooted
    outside ``base`` falls back to the absolute path rather than raising, so the
    self-test below can point the scan at a temporary package.
    """
    roots = (
        [PROJECT_ROOT / name for name in SOURCE_DIRS]
        if directories is None
        else [Path(directory) for directory in directories]
    )
    base_path = PROJECT_ROOT if base is None else Path(base)
    offenders = []
    for root in roots:
        for path in sorted(Path(root).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = _docstring_constants(tree)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and node.value == value
                    and id(node) not in docstrings
                ):
                    try:
                        shown = path.relative_to(base_path).as_posix()
                    except ValueError:
                        shown = path.as_posix()
                    offenders.append("%s:%d" % (shown, node.lineno))
    return sorted(offenders)


class OnePlaceTests(unittest.TestCase):
    """The model id is a live value in exactly one module."""

    def test_the_model_id_is_a_live_value_in_one_module_only(self):
        offenders = live_mentions_of(model.RUNTIME_MODEL)

        self.assertEqual(
            {DECLARATION},
            {entry.split(":")[0] for entry in offenders},
            "the model id is a live value somewhere other than the module that "
            "declares it, so there is more than one place to change it: {0}".format(
                offenders
            ),
        )

    def test_the_scan_is_capable_of_firing(self):
        """A guard nobody has seen fail is not evidence of anything.

        Two temporary modules: one that assigns the model id, which must be
        reported, and one that only mentions it in a docstring and a comment,
        which must not. Without the second half, a scan that flagged every
        mention of the string would look like a stronger guard than it is.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "pkg"
            root.mkdir()
            (root / "decides_it.py").write_text(
                'MODEL = "{0}"\n'.format(model.RUNTIME_MODEL), encoding="utf-8"
            )
            (root / "talks_about_it.py").write_text(
                '"""A docstring naming {0} as an example."""\n'
                "# and a comment naming {0} too\n"
                "OTHER = 1\n".format(model.RUNTIME_MODEL),
                encoding="utf-8",
            )

            found = live_mentions_of(model.RUNTIME_MODEL, directories=[root], base=tmp)

        self.assertEqual(
            ["pkg/decides_it.py:1"],
            found,
            "the scan did not report the assignment, or reported prose as though "
            "it were a value",
        )

    def test_the_module_declares_the_model_exactly_once(self):
        """Two assignments would make the value depend on where a reader stops."""
        source = (PROJECT_ROOT / DECLARATION).read_text(encoding="utf-8")
        tree = ast.parse(source)

        assignments = []
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            if "RUNTIME_MODEL" in targets:
                assignments.append(node.lineno)

        self.assertEqual(
            1,
            len(assignments),
            "RUNTIME_MODEL is assigned {0} times".format(len(assignments)),
        )

    def test_the_note_the_module_points_at_exists_and_names_the_decision(self):
        """The pointer is load-bearing: a decision with no evidence is a preference."""
        note = PROJECT_ROOT / model.DECISION_NOTE

        self.assertTrue(note.is_file(), "the decision note the module names is not there")
        text = note.read_text(encoding="utf-8")
        self.assertIn(model.RUNTIME_MODEL, text)
        self.assertIn(model.MODEL_PROVIDER, text)
        self.assertIn(model.MODEL_REGION, text)


class ResolveModelTests(unittest.TestCase):
    """The decision is the fallback; a caller's choice always wins."""

    def test_no_model_given_means_the_decided_one(self):
        self.assertEqual(model.RUNTIME_MODEL, model.resolve_model(None))
        self.assertEqual(model.RUNTIME_MODEL, model.resolve_model(""))

    def test_a_blank_name_counts_as_no_name(self):
        """A name that names nothing is not a model, so it is not used as one."""
        for blank in (" ", "   ", "\t", "\n"):
            with self.subTest(blank=repr(blank)):
                self.assertEqual(model.RUNTIME_MODEL, model.resolve_model(blank))

    def test_a_named_model_is_returned_unchanged(self):
        for named in ("hy3", "hy4-preview", "deepseek/deepseek-flash", "some/other-model"):
            with self.subTest(named=named):
                self.assertEqual(named, model.resolve_model(named))

    def test_surrounding_whitespace_is_not_part_of_the_name(self):
        self.assertEqual("hy4-preview", model.resolve_model("  hy4-preview  "))

    def test_the_answer_is_always_a_usable_model_id(self):
        for given in (None, "", "   ", "hy3"):
            with self.subTest(given=repr(given)):
                resolved = model.resolve_model(given)
                self.assertIsInstance(resolved, str)
                self.assertEqual(resolved, resolved.strip())
                self.assertTrue(resolved)

    def test_the_decision_is_not_an_empty_placeholder(self):
        """A placeholder default is how a decision quietly fails to be made."""
        self.assertNotEqual("", model.RUNTIME_MODEL.strip())
        self.assertEqual(model.RUNTIME_MODEL, model.RUNTIME_MODEL.strip())
        self.assertNotIn(" ", model.RUNTIME_MODEL)
        self.assertTrue(model.MODEL_PROVIDER.strip())
        self.assertTrue(model.MODEL_REGION.strip())


if __name__ == "__main__":
    unittest.main(verbosity=2)
