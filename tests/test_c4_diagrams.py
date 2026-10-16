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

The set draws **version 8**, so three more things are asserted here: no
specification states a version-6 rule -- a clause, a path, a figure -- except
inside a label that says version 6 for itself, the one exception being the
pipeline box's switch list, which names ``prompts/v1`` to say which directory a
version-8 run has to be handed instead (:data:`VERSION_SIX_PLACES`); the dynamic
view's boxes are numbered in the order the sheet lists the steps, with the
advocates before the authority gate; and every path a specification writes is a
path that is here.

Five more checks hold the drawings to the facts they state, each with a control:
no specification carries the name of the archive the team passed around; the
three call counts a version-8 case really makes -- two, six or seven, read off
the 42 committed transcripts through ``ui.v8.build.read_every_case()`` -- are
the counts the two views state, and no label or page line states six alone; the
upload arrow and the container that builds the pages name every builder that
uploads; the number of external sets the case store states is the number of
directories under ``data/external/``; and the pipeline box carries the
``--prompts-dir`` switch every version-8 run needs.

The check is shown to be capable of failing: a render of one specification with
one string changed is compared with the committed file and is required to
differ, and a doctored claim is required to be reported, so neither check can
pass by looking at nothing. Three more controls do the same for the version-6
rule, for the step order and for the path check.

No model call is made and no browser is launched. Run from the project root
with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.v8 import build as v8  # noqa: E402

SPEC_DIR = PROJECT_ROOT / "docs" / "architecture" / "spec"
VIEW_DIR = PROJECT_ROOT / "docs" / "architecture"
README_COPY = PROJECT_ROOT / "docs" / "architecture.svg"
GENERATOR = PROJECT_ROOT / "tools" / "c4_diagrams.py"

# The page that reads the drawings out to a reader, whose lines are held to the
# same call counts the two views state.
PAGE = PROJECT_ROOT / "docs" / "architecture.md"

# The name of the archive the team passed around, which no specification may
# carry: a reader who wants the source is sent to the tag and the commit.
ARCHIVE_NAME = "tribunal-main_4"

# The external sets, and the phrase the case store states their number in.
EXTERNAL_DIR = PROJECT_ROOT / "data" / "external"
MORE_SETS = re.compile(r"(\d+) more sets in")

# The builders that upload static HTML, and the two labels that must name them:
# sheet 1's upload arrow and sheet 2b's container.
BUILDERS: Tuple[str, ...] = ("ui/site", "ui/v8")
UPLOAD_LABEL = "1-system-context"
BUILD_CONTAINER = "2b-containers-after-ruling"
BUILD_CONTAINER_BOX = "site"

# The switch a version-8 run needs, which the pipeline box carries.
PROMPTS_SWITCH = "--prompts-dir prompts/v2"

# The phrase that states a case's call count, and the two counts that must stand
# beside it. A version-8 case makes two, six or seven model calls, so a label
# that says six alone is stating the version-6 count as the rule in force.
SIX_CALLS = re.compile(r"\b(?:6|six) calls a case", re.IGNORECASE)
TWO_CALLS = re.compile(r"\b(?:2|two)\b", re.IGNORECASE)
SEVEN_CALLS = re.compile(r"\b(?:7|seven)\b", re.IGNORECASE)

# The scratch directory this module is about, assembled from pieces so that this
# file does not itself carry the literal the check below looks for.
SCRATCH_DIR_NAME = "tm" + "p"

# The four specifications, in the order their file names sort, each with the
# number of placed elements it carries. The counts are the specifications' own:
# a drawing that lost or gained an element is reported against them.
SPECS: Tuple[Tuple[str, int], ...] = (
    ("1-system-context", 137),
    ("2a-containers-deciding", 229),
    ("2b-containers-after-ruling", 227),
    ("3-dynamic-one-dispute", 208),
)

# The view ``docs/architecture.svg`` is a copy of, and the one the README embeds.
DYNAMIC_VIEW = "3-dynamic-one-dispute"

# The dynamic view's eleven steps, in the order the sheet lists them: the boxes
# are numbered as that list numbers them, so the two advocates come before the
# authority gate and the gate before the citation referee. The number each box
# carries is read off the specification and compared with this list.
DYNAMIC_STEPS: Tuple[str, ...] = (
    "1.  Load the case",
    "2.  Weigh the evidence",
    "3.  Derive facts and money",
    "4.  Build one brief",
    "5.  Rider + Driver Advocate agents",
    "6.  Authority gate",
    "7.  Citation referee",
    "8.  Judge Agent, four drafts",
    "9.  Draft checks",
    "10.  Vote and the bar",
    "11.  Publish and record",
)

# A step's own label: a number, a period and a space. Nothing else in the
# dynamic view opens that way.
STEP_LABEL = re.compile(r"^(\d+)\.\s")

# A repository path as a specification writes one, in the shape
# ``tests/test_architecture.py`` reads the drawings' paths in, so the two read
# one path the same way. The longer extension is listed first so ``.jsonl`` is
# not read as ``.json`` with a trailing letter, and the lookahead stops a match
# in the middle of a word.
PATH_TOKEN = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_./-]*"
    r"\.(?:jsonl|json|py|md|svg|html)(?![A-Za-z0-9])"
)

# The phrases that state a **version-6** rule -- the freeze the drawings were
# first made from, the scope gate, the floor, the policy and prompt directories
# and the release threshold -- and the words a label must carry to state one for
# itself. The list is the support site's own (``tests/test_site_figures.py``),
# because the same rule holds of a drawing: a specification may name a
# version-6 clause, path or figure, but only where it says version 6.
VERSION_SIX_PHRASES: Tuple[str, ...] = (
    "freeze-2026-10-11",
    "--policy-version 6",
    "policy/v3",
    "prompts/v1",
    "0.70",
    "POL-GEN-08",
    "SGD 8",
)

VERSION_SIX_WORDS: Tuple[str, ...] = (
    "version 6",
    "version-6",
    "Version 6",
    "Version-6",
)

# The one version-6 path a specification still names, and the label that names
# it. The pipeline box's switch list states ``--prompts-dir``'s default, so that
# a reader knows which directory a version-8 run has to be handed instead; the
# label names no version of its own, so the rule above needs the exception
# spelled out here rather than read out of the box. A label that names
# ``prompts/v1`` anywhere else is still an offence, and the test below holds
# this table to what the specifications actually carry.
VERSION_SIX_PLACES: Tuple[Tuple[str, str], ...] = (
    ("2a-containers-deciding", "needs it (the default is prompts/v1)."),
)

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


def spec_texts(name: str) -> List[str]:
    """Every string one specification carries, in drawing order.

    A label is the unit the version-6 rule is stated in: the ``<text>``'s own
    string, and not the box it sits in, so a phrase cannot lean on a heading
    somewhere above it to say which version it belongs to.
    """
    return [
        element["text"]
        for element in spec_of(name)["elements"]
        if element.get("text")
    ]


def step_labels(elements: Any) -> List[str]:
    """Every text that opens as a step label: a number, a period, a space."""
    return [
        element["text"]
        for element in elements
        if element.get("text") and STEP_LABEL.match(element["text"])
    ]


def unnamed_version_six_phrases(
    elements: Any, allowed: Sequence[str] = ()
) -> List[str]:
    """Every version-6 phrase a specification states without naming version 6.

    A label that says version 6 for itself may name the freeze, the clause, the
    directory or the figure it belongs to -- that is what a history is. A label
    that does not is stating one as the rule in force, which is what the four
    views were drawn at version 8 to stop doing. ``allowed`` is the labels one
    specification's own exception covers: a label in it states the default a
    version-8 run overrides rather than the rule in force.
    """
    offences: List[str] = []
    for element in elements:
        text = element.get("text")
        if (
            not text
            or text in allowed
            or any(word in text for word in VERSION_SIX_WORDS)
        ):
            continue
        for phrase in VERSION_SIX_PHRASES:
            if phrase in text:
                offences.append("{0}: {1}".format(phrase, text))
    return offences


def allowed_version_six_labels(name: str) -> Tuple[str, ...]:
    """The labels one specification may state a version-6 phrase in."""
    return tuple(text for spec, text in VERSION_SIX_PLACES if spec == name)


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


def page_text() -> str:
    """``docs/architecture.md``, as it is committed."""
    return PAGE.read_text(encoding="utf-8")


def page_sentences() -> List[str]:
    """The page's prose as sentences, with its own wrapping joined.

    The page is wrapped at eighty columns, so a source line is not the unit a
    reader meets: a sentence is, and it is the unit the call counts are stated
    in. The wrapping is joined before the split, so a sentence that was rewrapped
    still reads as one.
    """
    joined = " ".join(page_text().split())
    return [part.strip() for part in re.split(r"(?<=\.)\s+", joined) if part.strip()]


def archive_name_offences(texts: Sequence[str]) -> List[str]:
    """Every text that carries the archive's name."""
    return [text for text in texts if ARCHIVE_NAME in text]


def calls_offences(texts: Sequence[str]) -> List[str]:
    """Every text that states six calls a case without the other two counts.

    A version-8 case makes two, six or seven model calls -- at version 8, 34 of
    the 42 cases made six, two made seven and six made two -- so a label or a
    page line that says six alone is stating the version-6 count as the one in
    force.
    """
    offences: List[str] = []
    for text in texts:
        if not SIX_CALLS.search(text):
            continue
        if TWO_CALLS.search(text) and SEVEN_CALLS.search(text):
            continue
        offences.append(text)
    return offences


def missing_builders(texts: Sequence[str]) -> List[str]:
    """The builders one label does not name."""
    joined = " ".join(texts)
    return [name for name in BUILDERS if name not in joined]


def more_sets_stated(texts: Sequence[str]) -> List[str]:
    """Every number a text states as the count of the extra external sets."""
    return MORE_SETS.findall(" ".join(texts))


def external_set_count() -> int:
    """The number of sets: the directories under ``data/external/``."""
    return len([path for path in EXTERNAL_DIR.iterdir() if path.is_dir()])


def upload_label_texts() -> List[str]:
    """Sheet 1's upload arrow: the tech label naming what is uploaded."""
    return [text for text in spec_texts(UPLOAD_LABEL) if text.startswith("[HTML")]


def container_texts(name: str, box: str) -> List[str]:
    """One container's own texts: its title, its tech line and its lines."""
    return [
        element["text"]
        for element in spec_of(name)["elements"]
        if element.get("text") and element["attrs"].get("data-box") == box
    ]


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


class TheVersionSixTests(unittest.TestCase):
    """No specification states a version-6 rule as the one in force.

    The four views draw version 8: v2.1's authority gate in place of the scope
    gate, v2.1's bar in place of the 0.70 floor, ``policy/v7`` and ``policy/v8``
    in place of ``policy/v3``, ``prompts/v2`` in place of ``prompts/v1``, and
    the freeze of 2026-10-14 in place of the freeze of 2026-10-11. Where a
    version-6 fact still stands -- the operations layer reads version-6 runs,
    and its release threshold is version 6's -- it stands inside a label that
    says so. The one path named without a version is ``--prompts-dir``'s
    default, which the switch list states so that a reader knows which directory
    a version-8 run has to be handed instead; that one label is
    :data:`VERSION_SIX_PLACES`, and the test below holds the table to it.
    """

    def test_no_specification_states_one_without_naming_version_six(self):
        for name, _count in SPECS:
            with self.subTest(spec=name):
                self.assertEqual(
                    [],
                    unnamed_version_six_phrases(
                        spec_of(name)["elements"],
                        allowed=allowed_version_six_labels(name),
                    ),
                    "{0} states a version-6 rule as the one in force".format(name),
                )

    def test_a_phrase_that_lost_its_label_is_reported(self):
        """The check above is shown capable of failing."""
        elements = copy.deepcopy(spec_of("2b-containers-after-ruling")["elements"])
        for element in elements:
            if element.get("text") == "review; kill switch; version 6: above SGD 8.00":
                element["text"] = "review; kill switch; above SGD 8.00 listed"
        self.assertEqual(
            1, len(unnamed_version_six_phrases(elements)), "the control did not fire"
        )

    def test_the_version_six_labels_that_remain_are_labelled(self):
        """A control: the exception is exercised, so the rule is not vacuous."""
        texts = spec_texts("2b-containers-after-ruling")
        self.assertIn("Version 6 = policy/v3 + 0001-0003 by hand", texts)
        self.assertIn("review; kill switch; version 6: above SGD 8.00", texts)

    def test_the_allowed_labels_are_the_ones_the_specifications_carry(self):
        """The exception is a fact about the drawings, not a way round the rule.

        A table that named a label no specification carries would excuse
        nothing, and a specification that stopped carrying it would be excused
        by a rule that no longer had anything to do with it.
        """
        for spec, text in VERSION_SIX_PLACES:
            with self.subTest(spec=spec, label=text):
                self.assertIn(text, spec_texts(spec))
                self.assertNotEqual(
                    [],
                    [
                        phrase
                        for phrase in VERSION_SIX_PHRASES
                        if phrase in text
                    ],
                    "the exception names a label that states no version-6 phrase",
                )
        for name, _count in SPECS:
            with self.subTest(spec=name):
                for text in allowed_version_six_labels(name):
                    self.assertIn(text, spec_texts(name))


class TheDynamicOrderTests(unittest.TestCase):
    """The dynamic view's boxes are numbered in the order the sheet lists."""

    def test_the_steps_are_the_order_the_sheet_lists(self):
        self.assertEqual(
            list(DYNAMIC_STEPS),
            step_labels(spec_of(DYNAMIC_VIEW)["elements"]),
            "the dynamic view's steps are not numbered in the sheet's order",
        )

    def test_the_steps_are_eleven_and_the_drawing_carries_them(self):
        """The numbers are the specification's and the drawing's alike."""
        numbers = [
            int(STEP_LABEL.match(text).group(1))
            for text in step_labels(spec_of(DYNAMIC_VIEW)["elements"])
        ]
        self.assertEqual(list(range(1, 12)), numbers)

    def test_a_spec_with_five_and_six_swapped_back_is_reported(self):
        """The control: the order is a fact about the specification.

        Version 6's drawing had the scope gate at step 5 and the two advocates
        at step 6. A specification that put them back that way -- the drawing
        this part replaces -- must fail the test above.
        """
        elements = copy.deepcopy(spec_of(DYNAMIC_VIEW)["elements"])
        five = [e for e in elements if e.get("text") == DYNAMIC_STEPS[4]][0]
        six = [e for e in elements if e.get("text") == DYNAMIC_STEPS[5]][0]
        five["text"], six["text"] = six["text"], five["text"]
        self.assertNotEqual(list(DYNAMIC_STEPS), step_labels(elements))


class TheFilesNamedTests(unittest.TestCase):
    """Every box that names a file names one that is here."""

    def test_every_path_a_specification_writes_exists(self):
        for name, _count in SPECS:
            written = sorted(set(PATH_TOKEN.findall(json.dumps(spec_of(name)))))
            self.assertTrue(written, "{0} names no file at all".format(name))
            for token in written:
                with self.subTest(spec=name, path=token):
                    self.assertTrue(
                        (PROJECT_ROOT / token).exists(),
                        "{0} names {1}, which is not in the repository".format(name, token),
                    )

    def test_a_path_that_is_not_here_is_reported(self):
        """The check above is shown capable of failing."""
        absent = "docs/notes/this-note-does-not-exist.md"
        self.assertEqual([absent], PATH_TOKEN.findall("see {0} for it".format(absent)))
        self.assertFalse((PROJECT_ROOT / absent).exists())


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


class TheArchiveNameTests(unittest.TestCase):
    """No specification sends a reader to the archive the team passed around.

    ``tribunal-main_4`` was a working archive, not a source a reader can find.
    Each view now says which trees it was checked against -- the annotated tag
    ``freeze-2026-10-14-v8`` and its commit -- so the name is gone from all four.
    """

    def test_no_specification_carries_the_archive_name(self):
        for name, _count in SPECS:
            with self.subTest(spec=name):
                self.assertEqual(
                    [],
                    archive_name_offences(spec_texts(name)),
                    "{0} still names the archive".format(name),
                )

    def test_a_specification_carrying_it_is_reported(self):
        """The control: the check above is shown capable of failing."""
        texts = [
            text + " " + ARCHIVE_NAME
            if text.startswith("Checked against the code")
            else text
            for text in spec_texts(SPECS[0][0])
        ]
        self.assertEqual(1, len(archive_name_offences(texts)))
        self.assertNotEqual([], archive_name_offences(texts))


class TheCallCountTests(unittest.TestCase):
    """The two views state the counts a version-8 case really makes.

    The transcripts are the record of how many calls each case made, so the
    counts are read off the committed runs rather than stated here: 34 of the 42
    cases made six calls, two made seven (a judge draft retried) and six made
    two (the authority gate stopped them after the advocates).
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.counts: Dict[int, int] = {}
        for case in v8.read_every_case():
            calls = len(case.transcript["entries"])
            cls.counts[calls] = cls.counts.get(calls, 0) + 1

    def test_the_counts_are_the_42_committed_transcripts(self):
        self.assertEqual(
            {2: 6, 6: 34, 7: 2},
            self.counts,
            "the version-8 transcripts do not hold the counts the views state",
        )

    def test_the_two_views_state_the_three_counts(self):
        for name in ("1-system-context", "2a-containers-deciding"):
            with self.subTest(spec=name):
                self.assertTrue(
                    any("2, 6 or 7" in text for text in spec_texts(name)),
                    "{0} does not state the three counts".format(name),
                )

    def test_no_label_and_no_page_line_states_six_alone(self):
        for name, _count in SPECS:
            with self.subTest(spec=name):
                self.assertEqual(
                    [],
                    calls_offences(spec_texts(name)),
                    "{0} states six calls a case without the other two".format(name),
                )
        with self.subTest(page="docs/architecture.md"):
            self.assertEqual([], calls_offences(page_sentences()))

    def test_a_label_stating_six_alone_is_reported(self):
        """The control: the check above is shown capable of failing."""
        texts = list(spec_texts("2a-containers-deciding")) + ["6 calls a case"]
        self.assertEqual(["6 calls a case"], calls_offences(texts))


class TheBuildersTests(unittest.TestCase):
    """The drawings name every builder that uploads static HTML.

    Three builders write the pages that are uploaded by hand: the product site
    (``ui/site/build.py``), the 42 version-8 case pages (``ui/v8/build.py``) and
    the version-6 queue and case pages (``ui/v2/build.py``). Sheet 1's upload
    arrow names them, and sheet 2b's container is the box that builds them.
    """

    def test_the_upload_label_names_the_builders(self):
        self.assertEqual([], missing_builders(upload_label_texts()))

    def test_the_container_names_the_builders(self):
        texts = container_texts(BUILD_CONTAINER, BUILD_CONTAINER_BOX)
        self.assertTrue(texts, "sheet 2b carries no site-build container")
        self.assertEqual([], missing_builders(texts))

    def test_a_label_without_ui_site_is_reported(self):
        """The control: the check above is shown capable of failing."""
        texts = [
            text.replace("ui/site", "ui/other") for text in upload_label_texts()
        ]
        self.assertEqual(["ui/site"], missing_builders(texts))

    def test_a_container_without_ui_v8_is_reported(self):
        """The other half of the control."""
        texts = [
            text.replace("ui/v8", "ui/other")
            for text in container_texts(BUILD_CONTAINER, BUILD_CONTAINER_BOX)
        ]
        self.assertEqual(["ui/v8"], missing_builders(texts))


class TheExternalSetCountTests(unittest.TestCase):
    """The case store's number is the number of directories under data/external/.

    The number is a count of the tree, not a figure copied from somewhere else,
    so a set imported without the label moving fails here.
    """

    def test_the_number_sheet_2a_states_is_the_tree(self):
        self.assertEqual(
            [str(external_set_count())],
            more_sets_stated(spec_texts("2a-containers-deciding")),
            "the case store's number is not the number of sets on disk",
        )

    def test_the_old_number_is_reported(self):
        """The control: the check above is shown capable of failing."""
        texts = [
            text.replace("16 more sets in", "12 more sets in")
            for text in spec_texts("2a-containers-deciding")
        ]
        self.assertEqual(["12"], more_sets_stated(texts))
        self.assertNotEqual(
            [str(external_set_count())],
            more_sets_stated(texts),
            "the control states the number the tree holds, so it cannot fail",
        )


class TheSwitchTests(unittest.TestCase):
    """The pipeline box carries the switch every version-8 run needs.

    ``--prompts-dir prompts/v2`` is the one switch that is not simply off by
    default: a version-8 run handed the default directory is refused, so the box
    states both the switch and the default it replaces.
    """

    def test_sheet_2a_carries_the_prompts_switch(self):
        texts = spec_texts("2a-containers-deciding")
        self.assertTrue(
            any(PROMPTS_SWITCH in text for text in texts),
            "the pipeline box does not carry {0!r}".format(PROMPTS_SWITCH),
        )
        self.assertTrue(
            any("the default is prompts/v1" in text for text in texts),
            "the pipeline box does not state the default the switch replaces",
        )

    def test_a_box_without_the_switch_is_reported(self):
        """The control: the check above is shown capable of failing."""
        texts = [
            text.replace(PROMPTS_SWITCH, "--prompts-dir prompts/v1")
            for text in spec_texts("2a-containers-deciding")
        ]
        self.assertFalse(any(PROMPTS_SWITCH in text for text in texts))


if __name__ == "__main__":
    unittest.main()
