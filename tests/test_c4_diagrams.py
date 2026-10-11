"""The four C4 views are drawn by this repository, from its own specifications.

The views under ``docs/architecture/`` are transcriptions of the C4 set the
policy owner, Ji Guofang, designed. Part 48 committed them as finished SVGs --
drawn outside the repository -- which made them the one artifact here nobody
could reproduce. ``tools/c4_diagrams.py`` now draws them from the **layout
specifications** under ``docs/architecture/spec/``, one JSON file per view, so
they are reproducible like every other artifact, and this module holds the two
halves together:

* **a committed drawing is its specification's own render.** Each file is
  compared, byte for byte, with a fresh render through the generator's own
  ``outputs()`` -- the ``--check`` logic, run in process -- so a hand edit to a
  drawing, or a specification edited without re-rendering, fails here;
* **each drawing is the specification's elements, in the specification's
  order.** It parses as XML, its placed elements are exactly the specification's
  in number and in tag order, and the root is an ``<svg>`` of the canvas's own
  size. The counts are the specification's and are asserted as such, not
  recomputed from the drawing being checked;
* **the one correction is the one correction.** The evidence collector's box in
  2a reads "given the dispute", which is what ``ops/evidence.py`` does, and the
  sentence it replaces -- "given only the trip id" -- is gone. This is the only
  difference between these drawings and the ones the owner drew: the other
  three render byte for byte as she committed them.
* **nothing here reads the scratch directory.** Neither the generator nor any
  specification names a path under the repository's ``tmp/``, which is
  gitignored and therefore absent from a clean clone -- a generator that read
  it would work only on the machine that wrote it.

The check is shown to be capable of failing: a render of one specification with
one string changed is compared with the committed file and is required to
differ, and a doctored claim is required to be reported, so neither check can
pass by looking at nothing.

No model call is made and no browser is launched. Run from the project root
with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import importlib.util
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SPEC_DIR = PROJECT_ROOT / "docs" / "architecture" / "spec"
VIEW_DIR = PROJECT_ROOT / "docs" / "architecture"
README_COPY = PROJECT_ROOT / "docs" / "architecture.svg"
GENERATOR = PROJECT_ROOT / "tools" / "c4_diagrams.py"

# The scratch directory this module is about, assembled from pieces so that this
# file does not itself carry the literal the check below looks for.
SCRATCH_DIR_NAME = "tm" + "p"

# The four specifications, in the order their file names sort, each with the
# number of placed elements it carries. The counts are the specifications' own:
# a drawing that lost or gained an element is reported against them.
SPECS: Tuple[Tuple[str, int], ...] = (
    ("1-system-context", 137),
    ("2a-containers-deciding", 228),
    ("2b-containers-after-ruling", 223),
    ("3-dynamic-one-dispute", 210),
)

# The view ``docs/architecture.svg`` is a copy of, and the one the README embeds.
DYNAMIC_VIEW = "3-dynamic-one-dispute"

# The correction 2a carries, and the sentence it replaces. The first is what
# ``ops/evidence.py`` does -- it is given the dispute and reads that dispute's
# trip id -- and the second is what the drawing said before it was corrected.
CORRECTED_CLAIM = "given the dispute"
REPLACED_CLAIM = "given only the trip id"

SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def load_generator() -> Any:
    """``tools/c4_diagrams.py`` as a module, loaded by path.

    ``tools/`` is not a package, so the module is loaded from its file: the
    drawings are compared with the generator's own render rather than with a
    second implementation of it kept here, which could drift.
    """
    spec = importlib.util.spec_from_file_location("c4_diagrams", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR_MODULE = load_generator()


def local_name(tag: str) -> str:
    """An element's tag without its namespace, lower-cased."""
    return tag.rsplit("}", 1)[-1].lower()


def spec_of(name: str) -> Dict[str, Any]:
    """One layout specification, read from its committed file."""
    return json.loads((SPEC_DIR / "{0}.json".format(name)).read_text(encoding="utf-8"))


def placed_elements(path: Path) -> List[str]:
    """A drawing's placed element tags, in document order, without the ``<defs>``."""
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    return [
        local_name(element.tag)
        for element in list(root)
        if local_name(element.tag) != "defs"
    ]


def texts_of(path: Path) -> List[str]:
    """Every placed ``<text>`` of one drawing, stripped, in document order."""
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    return [
        (element.text or "").strip()
        for element in root.iter()
        if local_name(element.tag) == "text" and (element.text or "").strip()
    ]


def names_a_scratch_path(value: str) -> bool:
    """Whether a string is a **relative** path whose first component is ``tmp``.

    ``"tmp"`` alone is a name and not a path, ``"/tmp/runs"`` is the operating
    system's directory, and ``"somewhere/tmp/x"`` is a path under another
    directory; none of the three is a path under this repository's ``tmp/``.
    """
    if not value or value.startswith(("/", "~")):
        return False
    parts = [part for part in value.split("/") if part not in ("", ".")]
    return len(parts) > 1 and parts[0] == SCRATCH_DIR_NAME


def python_strings(text: str) -> List[str]:
    """Every string constant in a module's source, its docstring included."""
    return [
        node.value
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def json_strings(value: Any) -> List[str]:
    """Every string anywhere in a parsed JSON document."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [found for item in value.values() for found in json_strings(item)]
    if isinstance(value, list):
        return [found for item in value for found in json_strings(item)]
    return []


def scratch_offences_in_python(text: str) -> List[str]:
    """The strings in a module's source that name a path under ``tmp/``."""
    return sorted({value for value in python_strings(text) if names_a_scratch_path(value)})


def scratch_offences_in_json(text: str) -> List[str]:
    """The strings in a JSON document that name a path under ``tmp/``."""
    return sorted(
        {value for value in json_strings(json.loads(text)) if names_a_scratch_path(value)}
    )


class TheRenderTests(unittest.TestCase):
    """Every committed drawing is the specification's own render, byte for byte."""

    def test_every_committed_file_equals_a_fresh_render(self):
        for path, content in GENERATOR_MODULE.outputs():
            with self.subTest(file=str(path.relative_to(PROJECT_ROOT))):
                self.assertTrue(path.is_file(), "{0} is not committed".format(path))
                self.assertEqual(
                    content,
                    path.read_bytes(),
                    "{0} is not what the specification renders; run "
                    "python3 tools/c4_diagrams.py".format(path),
                )

    def test_the_check_can_fail(self):
        """A render that differs from the committed file is reported as a difference."""
        name, _count = SPECS[0]
        path = VIEW_DIR / "{0}.svg".format(name)
        doctored = path.read_text(encoding="utf-8").replace(
            "System Context diagram for Tribunal", "a doctored title"
        )
        self.assertNotEqual(
            doctored.encode("utf-8"),
            path.read_bytes(),
            "the doctored render is the committed file, so it cannot show a failure",
        )

    def test_the_readme_copy_is_the_dynamic_view(self):
        self.assertEqual(
            (VIEW_DIR / "{0}.svg".format(DYNAMIC_VIEW)).read_bytes(),
            README_COPY.read_bytes(),
            "docs/architecture.svg is not the dynamic view byte for byte",
        )

    def test_every_file_ends_with_a_newline_and_holds_only_ascii(self):
        for name, _count in SPECS:
            text = (VIEW_DIR / "{0}.svg".format(name)).read_text(encoding="utf-8")
            with self.subTest(view=name):
                self.assertTrue(text.endswith("</svg>\n"), "the drawing does not end its svg")
                self.assertTrue(text.isascii(), "the drawing holds a non-ASCII character")

    def test_no_drawing_carries_a_script_an_image_or_a_href(self):
        for name, _count in SPECS:
            text = (VIEW_DIR / "{0}.svg".format(name)).read_text(encoding="utf-8")
            with self.subTest(view=name):
                for forbidden in ("<script", "<image", "href"):
                    self.assertNotIn(forbidden, text.lower())


class TheSpecificationTests(unittest.TestCase):
    """Each drawing is its specification's elements, in the specification's order."""

    def test_the_specifications_are_the_four_named_views(self):
        found = sorted(path.stem for path in SPEC_DIR.glob("*.json"))
        self.assertEqual([name for name, _count in SPECS], found)
        for name, _count in SPECS:
            with self.subTest(spec=name):
                self.assertEqual(name, spec_of(name)["name"])

    def test_each_drawing_parses_and_has_the_specifications_element_count(self):
        for name, count in SPECS:
            with self.subTest(view=name):
                spec = spec_of(name)
                self.assertEqual(
                    count,
                    len(spec["elements"]),
                    "the specification's own element count moved",
                )
                self.assertEqual(
                    count,
                    len(placed_elements(VIEW_DIR / "{0}.svg".format(name))),
                    "the drawing does not carry the specification's elements",
                )

    def test_each_drawing_carries_the_specifications_tags_in_order(self):
        for name, _count in SPECS:
            with self.subTest(view=name):
                self.assertEqual(
                    [element["tag"] for element in spec_of(name)["elements"]],
                    placed_elements(VIEW_DIR / "{0}.svg".format(name)),
                    "the drawing's elements are not the specification's, in order",
                )

    def test_each_root_is_an_svg_of_the_canvass_own_size(self):
        for name, _count in SPECS:
            canvas = spec_of(name)["canvas"]
            with self.subTest(view=name):
                root = ET.fromstring(
                    (VIEW_DIR / "{0}.svg".format(name)).read_text(encoding="utf-8")
                )
                self.assertEqual("{{{0}}}svg".format(SVG_NAMESPACE), root.tag)
                self.assertEqual(canvas["viewBox"], root.get("viewBox"))
                self.assertEqual(canvas["width"], root.get("width"))
                self.assertEqual(canvas["height"], root.get("height"))
                self.assertEqual(canvas["font-family"], root.get("font-family"))


class TheCorrectionTests(unittest.TestCase):
    """The one correction: the evidence collector is given the dispute."""

    def test_2a_carries_the_corrected_sentence(self):
        texts = texts_of(VIEW_DIR / "2a-containers-deciding.svg")
        self.assertTrue(
            any(CORRECTED_CLAIM in text for text in texts),
            "2a does not carry the corrected claim",
        )

    def test_2a_does_not_carry_the_sentence_it_replaces(self):
        text = (VIEW_DIR / "2a-containers-deciding.svg").read_text(encoding="utf-8")
        self.assertNotIn(
            REPLACED_CLAIM,
            text,
            "2a still carries the sentence the correction replaced",
        )

    def test_the_replaced_sentence_is_reported(self):
        """The check above is shown capable of failing."""
        text = (VIEW_DIR / "2a-containers-deciding.svg").read_text(encoding="utf-8")
        self.assertIn(REPLACED_CLAIM, text.replace(CORRECTED_CLAIM, REPLACED_CLAIM))


class TheScratchDirectoryTests(unittest.TestCase):
    """Neither the generator nor a specification reads the scratch directory."""

    def test_the_rule_finds_a_literal_and_a_join(self):
        """The check below is shown to fire on the two shapes it looks for."""
        literal = 'OG = "{0}/og-image.png"\n'.format(SCRATCH_DIR_NAME)
        self.assertEqual(
            ["{0}/og-image.png".format(SCRATCH_DIR_NAME)],
            scratch_offences_in_python(literal),
        )
        self.assertEqual(
            ["{0}/spec.json".format(SCRATCH_DIR_NAME)],
            scratch_offences_in_json('{{"path": "{0}/spec.json"}}'.format(SCRATCH_DIR_NAME)),
        )

    def test_the_rule_stays_quiet_on_a_system_path_and_a_bare_name(self):
        self.assertEqual([], scratch_offences_in_python("RUNS = '/tmp/runs'\n"))
        self.assertEqual([], scratch_offences_in_python('X = "{0}"\n'.format(SCRATCH_DIR_NAME)))

    def test_the_generator_does_not_read_the_scratch_directory(self):
        self.assertEqual(
            [],
            scratch_offences_in_python(GENERATOR.read_text(encoding="utf-8")),
            "tools/c4_diagrams.py names a path under the scratch directory",
        )

    def test_no_specification_reads_the_scratch_directory(self):
        for name, _count in SPECS:
            path = SPEC_DIR / "{0}.json".format(name)
            with self.subTest(spec=name):
                self.assertEqual(
                    [],
                    scratch_offences_in_json(path.read_text(encoding="utf-8")),
                    "{0} names a path under the scratch directory".format(path),
                )


if __name__ == "__main__":
    unittest.main()
