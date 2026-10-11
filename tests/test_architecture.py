"""The architecture set is a self-contained, honest document.

The set is the policy owner's: four C4-style views, drawn from the code at the
final freeze and committed under ``docs/architecture/``. ``docs/architecture.svg``
is a byte-for-byte copy of the dynamic view, because the README embeds that file
and the queue's own "Architecture" link opens it. ``docs/architecture.md``
explains the four views element by element, in the same order. Four properties
make the set worth committing, and each is asserted here rather than assumed:

* **Each drawing is a well-formed drawing.** It parses as XML and declares the
  viewBox the set fixes, so a renderer has something to lay out.
* **Each drawing is self-contained and portable.** It carries no script, no
  embedded image, no hyperlink and no character outside ASCII, so it renders the
  same way everywhere and needs no network.
* **Each drawing says what it is.** It carries the title the sheet fixes and its
  own legend of the kinds of element, and the dynamic view is eleven numbered
  steps. Each is read off the parsed drawing.
* **Every path it names is a path that is here.** A box that names the file
  implementing it is only worth the reader's trust if the file exists, so every
  path written in the four drawings and in the page is resolved against the
  repository and checked. This is the claim the set makes about itself, and it
  is the one this module holds it to.

**The path check is shown to be capable of failing.** The extractor is run over
a fixture that names a file that is not here, and the check is shown to go red on
it -- the lesson ``START-HERE.md`` records is that a guard nobody has seen fail
is not evidence of anything. A control also asserts the extractor finds the
paths these drawings are actually made of, so a harvest that silently stopped
working fails instead of passing.

No model call is made and no browser is launched. Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE_DIR = PROJECT_ROOT / "docs" / "architecture"
SVG_PATH = PROJECT_ROOT / "docs" / "architecture.svg"
PAGE_PATH = PROJECT_ROOT / "docs" / "architecture.md"

# The four views, in the order the page walks them, each with the title its own
# first line carries. The dynamic view is the one ``docs/architecture.svg`` is a
# copy of, and it is checked in both places.
VIEWS: Tuple[Tuple[str, str], ...] = (
    ("1-system-context.svg", "System Context diagram for Tribunal"),
    (
        "2a-containers-deciding.svg",
        "Container diagram for Tribunal - 2a. Deciding and measuring",
    ),
    (
        "2b-containers-after-ruling.svg",
        "Container diagram for Tribunal - 2b. After a ruling: operations, "
        "learning loop, publishing",
    ),
    (
        "3-dynamic-one-dispute.svg",
        "Dynamic diagram for Tribunal - how one dispute is decided",
    ),
)

# The kinds of element each view's legend names. Every drawing carries its own
# legend, and the labels differ between them -- the container views name a
# container and the dynamic view names a component -- so each set is pinned
# against the file that carries it.
LEGENDS: Mapping[str, Tuple[str, ...]] = {
    "1-system-context.svg": (
        "Person",
        "Software system in scope",
        "External software system",
        "calls a large language model",
    ),
    "2a-containers-deciding.svg": (
        "Person",
        "Container",
        "Container: data store",
        "External software system",
        "calls a large language model",
    ),
    "2b-containers-after-ruling.svg": (
        "Person",
        "Container",
        "Data store",
        "External system",
        "calls an LLM",
    ),
    "3-dynamic-one-dispute.svg": (
        "Component; number = order",
        "Container",
        "Data store",
        "External system",
        "calls the LLM",
    ),
}

# The files the set is made of: the four views, and the copy the README embeds.
DRAWINGS: Tuple[Path, ...] = tuple(
    ARCHITECTURE_DIR / name for name, _title in VIEWS
) + (SVG_PATH,)

# The diagram's own namespace, and the tag name the root element must carry.
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
SVG_TAG = "{{{0}}}svg".format(SVG_NAMESPACE)

# The size the set fixes for every drawing.
EXPECTED_VIEWBOX = (0.0, 0.0, 1920.0, 1080.0)

# A repository path as the drawings and the page write one: at least two
# segments, ending in a file extension this repository uses. The longer
# extension is listed first so ``.jsonl`` is not read as ``.json`` with a
# trailing letter, and the lookahead stops a match in the middle of a word.
PATH_TOKEN = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_./-]*"
    r"\.(?:jsonl|json|py|md|svg|html)(?![A-Za-z0-9])"
)

# An href of any kind, external or internal. The drawings need none.
HREF_ATTRIBUTE = re.compile(r"\bhref\s*=", re.IGNORECASE)

# A tag the self-contained rule forbids, matched on the raw text so a tag split
# across a namespace prefix is still caught.
FORBIDDEN_TAG = re.compile(r"<\s*(?:script|image)\b", re.IGNORECASE)

# The dynamic view's step labels: a number, a period and a space, and then the
# step's own words. Nothing else in the drawing opens with a digit and a period.
STEP_LABEL = re.compile(r"^(\d+)\.\s")


def svg_text() -> str:
    """The embedded copy's bytes, read as text."""
    return SVG_PATH.read_text(encoding="utf-8")


def page_text() -> str:
    """The page's bytes, read as text."""
    return PAGE_PATH.read_text(encoding="utf-8")


def view_text(name: str) -> str:
    """One view's bytes, read as text."""
    return (ARCHITECTURE_DIR / name).read_text(encoding="utf-8")


def paths_in(text: str) -> List[str]:
    """Every repository path written in ``text``, sorted and deduplicated."""
    return sorted(set(PATH_TOKEN.findall(text)))


def resolve(token: str, source: Path) -> Path:
    """Where a written path points: the repository root first, then the writer's own directory.

    The drawings write repository-rooted paths, and the page's own links are
    relative to the page, so both readings are tried. A token that resolves
    under neither is what the check below reports.
    """
    rooted = PROJECT_ROOT / token
    if rooted.exists():
        return rooted
    return source.parent / token


def local_name(tag: str) -> str:
    """An element's tag without its namespace, lower-cased."""
    return tag.rsplit("}", 1)[-1].lower()


def texts_of(text: str) -> List[str]:
    """Every placed ``<text>`` of one drawing, stripped, in document order."""
    return [
        (element.text or "").strip()
        for element in ET.fromstring(text).iter()
        if local_name(element.tag) == "text" and (element.text or "").strip()
    ]


class TheDrawingsParseTests(unittest.TestCase):
    """Each drawing is well-formed XML and declares the viewBox the set fixes."""

    def test_each_drawing_parses_as_xml(self):
        """A parse failure is reported as itself and not as a later assertion."""
        for path in DRAWINGS:
            with self.subTest(drawing=path.name):
                try:
                    ET.fromstring(path.read_text(encoding="utf-8"))
                except ET.ParseError as exc:
                    self.fail("{0} is not well-formed XML: {1}".format(path, exc))

    def test_each_root_is_an_svg_with_the_expected_viewbox(self):
        for path in DRAWINGS:
            with self.subTest(drawing=path.name):
                root = ET.fromstring(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    SVG_TAG,
                    root.tag,
                    "the root element is not an svg in the svg namespace",
                )
                viewbox = root.get("viewBox")
                self.assertIsNotNone(viewbox, "the svg declares no viewBox")
                numbers = tuple(float(part) for part in viewbox.replace(",", " ").split())
                self.assertEqual(
                    EXPECTED_VIEWBOX,
                    numbers,
                    "the viewBox is {0!r}, and the set fixes 1920 by 1080".format(
                        viewbox
                    ),
                )


class TheDrawingsAreSelfContainedTests(unittest.TestCase):
    """No script, no image, no hyperlink, and nothing outside ASCII."""

    def test_no_drawing_carries_a_script_or_an_image(self):
        for path in DRAWINGS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(drawing=path.name):
                match = FORBIDDEN_TAG.search(text)
                self.assertIsNone(
                    match,
                    "the drawing carries a forbidden tag: {0!r}".format(
                        match.group(0) if match else ""
                    ),
                )
                for element in ET.fromstring(text).iter():
                    self.assertNotIn(
                        local_name(element.tag),
                        ("script", "image"),
                        "the drawing carries a {0} element".format(
                            local_name(element.tag)
                        ),
                    )

    def test_no_drawing_carries_an_href(self):
        for path in DRAWINGS:
            with self.subTest(drawing=path.name):
                self.assertIsNone(
                    HREF_ATTRIBUTE.search(path.read_text(encoding="utf-8")),
                    "the drawing carries an href, so it is not self-contained",
                )

    def test_no_drawing_holds_a_non_ascii_character(self):
        for path in DRAWINGS:
            text = path.read_text(encoding="utf-8")
            if text.isascii():
                continue
            offenders = sorted(
                {
                    "U+{0:04X}".format(ord(character))
                    for character in text
                    if not character.isascii()
                }
            )
            self.fail(
                "{0} holds non-ASCII characters: {1}".format(path, ", ".join(offenders))
            )

    def test_the_page_holds_no_non_ascii_character(self):
        text = page_text()
        if text.isascii():
            return
        offenders = sorted(
            {"U+{0:04X}".format(ord(character)) for character in text if not character.isascii()}
        )
        self.fail("docs/architecture.md holds non-ASCII characters: {0}".format(", ".join(offenders)))


class TheDrawingsSayWhatTheyAreTests(unittest.TestCase):
    """The titles, the four legends and the dynamic view's eleven steps.

    The sheet fixes the four titles and the kinds each legend names, and the
    dynamic view is eleven numbered steps. Each is read off the parsed drawing
    rather than described, so a redraw that drops one fails here instead of
    passing as a drawing nobody checked.
    """

    def test_each_drawing_carries_the_title_the_sheet_fixes(self):
        for name, title in VIEWS:
            with self.subTest(drawing=name):
                self.assertIn(
                    title,
                    texts_of(view_text(name)),
                    "the drawing does not carry the sheet's title",
                )

    def test_each_legend_names_the_kinds_of_element(self):
        for name, labels in sorted(LEGENDS.items()):
            found = set(texts_of(view_text(name)))
            for label in labels:
                with self.subTest(drawing=name, label=label):
                    self.assertIn(
                        label, found, "the legend does not name {0!r}".format(label)
                    )

    def test_the_dynamic_view_is_eleven_numbered_steps(self):
        """Read as structure, not by searching the text.

        A step's own label is the only text in the drawing that opens with a
        digit and a period, so the set of them is the view's own numbering.
        """
        numbers: List[int] = []
        for content in texts_of(view_text("3-dynamic-one-dispute.svg")):
            match = STEP_LABEL.match(content)
            if match is not None:
                numbers.append(int(match.group(1)))
        self.assertEqual(
            list(range(1, 12)),
            numbers,
            "the dynamic view's steps are not numbered 1 to 11 in order",
        )


class TheExtractorTests(unittest.TestCase):
    """The path extractor is shown to work, and to be able to fail."""

    def test_it_finds_the_paths_the_drawings_are_made_of(self):
        """A harvest that silently stopped working would otherwise pass."""
        found: Dict[str, set] = {
            path.name: set(paths_in(path.read_text(encoding="utf-8")))
            for path in DRAWINGS
        }
        for name, required in (
            ("1-system-context.svg", "eval/run_benchmark.py"),
            ("1-system-context.svg", "ui/v2/build.py"),
            ("2a-containers-deciding.svg", "ops/evidence.py"),
            ("2a-containers-deciding.svg", "ui/build.py"),
            ("2b-containers-after-ruling.svg", "eval/policy_gaps.py"),
            ("2b-containers-after-ruling.svg", "precedents/precedents.jsonl"),
            ("3-dynamic-one-dispute.svg", "tribunal/pipeline.py"),
            ("3-dynamic-one-dispute.svg", "tribunal/loader.py"),
            ("3-dynamic-one-dispute.svg", "prompts/v1/judge.system.md"),
            ("3-dynamic-one-dispute.svg", "data/index.json"),
            ("architecture.svg", "tribunal/brief.py"),
            ("architecture.svg", "tribunal/referee.py"),
        ):
            with self.subTest(drawing=name, path=required):
                self.assertIn(required, found[name], "{0} was not extracted".format(required))

    def test_it_reads_a_longer_extension_whole(self):
        """``.jsonl`` is not ``.json`` with a trailing letter."""
        self.assertEqual(
            ["precedents/precedents.jsonl"],
            paths_in("see precedents/precedents.jsonl for the chain"),
        )

    def test_a_missing_path_is_reported(self):
        """The check the tests below apply is capable of going red."""
        source = PROJECT_ROOT / "docs" / "architecture.md"
        absent = "docs/notes/this-note-does-not-exist.md"
        found = paths_in("see {0} for the record".format(absent))
        self.assertEqual([absent], found)
        self.assertFalse(
            resolve(found[0], source).exists(),
            "the fixture path unexpectedly exists, so it cannot show a failure",
        )


class TheWrittenPathsExistTests(unittest.TestCase):
    """Every path the drawings and the page write is a path in this repository."""

    def _missing(self, text: str, source: Path) -> List[str]:
        return [token for token in paths_in(text) if not resolve(token, source).exists()]

    def test_every_path_in_every_drawing_exists(self):
        for path in DRAWINGS:
            with self.subTest(drawing=path.name):
                self.assertEqual(
                    [],
                    self._missing(path.read_text(encoding="utf-8"), path),
                    "a path written in {0} is not in the repository".format(path),
                )

    def test_every_path_in_the_page_exists(self):
        self.assertEqual(
            [],
            self._missing(page_text(), PAGE_PATH),
            "a path written in docs/architecture.md is not in the repository",
        )

    def test_the_page_embeds_the_diagram_and_it_is_there(self):
        self.assertIn(
            "![Tribunal architecture](architecture.svg)",
            page_text(),
            "the page does not embed the diagram",
        )
        self.assertTrue(
            SVG_PATH.is_file(),
            "docs/architecture.svg is not a file in this repository",
        )


if __name__ == "__main__":
    unittest.main()
