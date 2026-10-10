"""The architecture diagram is a self-contained, honest document.

``docs/architecture.svg`` is drawn by hand from the code at the freeze tag, as a
container view (C4 style): one dispute's path down the middle, the model
provider and the measurement tooling on the left, the learning loop and the
human operations on the right. ``docs/architecture.md`` explains it element by
element, in the same order. Four properties make the pair worth committing, and
each is asserted here rather than assumed:

* **The diagram is a well-formed drawing.** It parses as XML and declares the
  viewBox the sheet fixes, so a renderer has something to lay out.
* **The diagram is self-contained and portable.** It carries no script, no
  embedded image, no hyperlink and no character outside ASCII, so it renders the
  same way everywhere and needs no network.
* **The diagram says what it is.** It carries the title and the subtitle the
  sheet fixes, the legend names the six kinds of element, and the middle column
  is eleven numbered steps. Each is read off the parsed drawing.
* **Every path it names is a path that is here.** A box that names the file
  implementing it is only worth the reader's trust if the file exists, so every
  path written in the SVG and in the page is resolved against the repository and
  checked. This is the claim the diagram makes about itself, and it is the one
  this module holds it to.

**The path check is shown to be capable of failing.** The extractor is run over
a fixture that names a file that is not here, and the check is shown to go red on
it -- the lesson ``START-HERE.md`` records is that a guard nobody has seen fail
is not evidence of anything. A control also asserts the extractor finds the
paths this diagram is actually made of, so a harvest that silently stopped
working fails instead of passing.

No model call is made and no browser is launched. Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = PROJECT_ROOT / "docs" / "architecture.svg"
PAGE_PATH = PROJECT_ROOT / "docs" / "architecture.md"

# The diagram's own namespace, and the tag name the root element must carry.
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
SVG_TAG = "{{{0}}}svg".format(SVG_NAMESPACE)

# The size the sheet fixes for the drawing.
EXPECTED_VIEWBOX = (0.0, 0.0, 1600.0, 1000.0)

# A repository path as the diagram and the page write one: at least two
# segments, ending in a file extension this repository uses. The longer
# extension is listed first so ``.jsonl`` is not read as ``.json`` with a
# trailing letter, and the lookahead stops a match in the middle of a word.
PATH_TOKEN = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_./-]*"
    r"\.(?:jsonl|json|py|md|svg|html)(?![A-Za-z0-9])"
)

# An href of any kind, external or internal. The diagram needs none.
HREF_ATTRIBUTE = re.compile(r"\bhref\s*=", re.IGNORECASE)

# A tag the self-contained rule forbids, matched on the raw text so a tag split
# across a namespace prefix is still caught.
FORBIDDEN_TAG = re.compile(r"<\s*(?:script|image)\b", re.IGNORECASE)


def svg_text() -> str:
    """The diagram's bytes, read as text."""
    return SVG_PATH.read_text(encoding="utf-8")


def page_text() -> str:
    """The page's bytes, read as text."""
    return PAGE_PATH.read_text(encoding="utf-8")


def paths_in(text: str) -> List[str]:
    """Every repository path written in ``text``, sorted and deduplicated."""
    return sorted(set(PATH_TOKEN.findall(text)))


def resolve(token: str, source: Path) -> Path:
    """Where a written path points: the repository root first, then the writer's own directory.

    The diagram writes repository-rooted paths, and the page's own link is
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


class TheDiagramParsesTests(unittest.TestCase):
    """The drawing is well-formed XML and declares the viewBox the sheet fixes."""

    def test_it_parses_as_xml(self):
        """A parse failure is reported as itself and not as a later assertion."""
        try:
            ET.fromstring(svg_text())
        except ET.ParseError as exc:
            self.fail("docs/architecture.svg is not well-formed XML: {0}".format(exc))

    def test_the_root_is_an_svg_with_the_expected_viewbox(self):
        root = ET.fromstring(svg_text())
        self.assertEqual(
            SVG_TAG, root.tag, "the root element is not an svg in the svg namespace"
        )
        viewbox = root.get("viewBox")
        self.assertIsNotNone(viewbox, "the svg declares no viewBox")
        numbers = tuple(float(part) for part in viewbox.replace(",", " ").split())
        self.assertEqual(
            EXPECTED_VIEWBOX,
            numbers,
            "the viewBox is {0!r}, and the sheet fixes 1600 by 1000".format(viewbox),
        )


class TheDiagramIsSelfContainedTests(unittest.TestCase):
    """No script, no image, no hyperlink, and nothing outside ASCII."""

    def test_it_carries_no_script_and_no_image(self):
        text = svg_text()
        match = FORBIDDEN_TAG.search(text)
        self.assertIsNone(
            match,
            "the diagram carries a forbidden tag: {0!r}".format(
                match.group(0) if match else ""
            ),
        )
        for element in ET.fromstring(text).iter():
            self.assertNotIn(
                local_name(element.tag),
                ("script", "image"),
                "the diagram carries a {0} element".format(local_name(element.tag)),
            )

    def test_it_carries_no_href(self):
        match = HREF_ATTRIBUTE.search(svg_text())
        self.assertIsNone(
            match,
            "the diagram carries an href, so it is not self-contained",
        )

    def test_it_holds_no_non_ascii_character(self):
        text = svg_text()
        if text.isascii():
            return
        offenders = sorted(
            {"U+{0:04X}".format(ord(character)) for character in text if not character.isascii()}
        )
        self.fail("docs/architecture.svg holds non-ASCII characters: {0}".format(", ".join(offenders)))

    def test_the_page_holds_no_non_ascii_character(self):
        text = page_text()
        if text.isascii():
            return
        offenders = sorted(
            {"U+{0:04X}".format(ord(character)) for character in text if not character.isascii()}
        )
        self.fail("docs/architecture.md holds non-ASCII characters: {0}".format(", ".join(offenders)))


class TheDiagramSaysWhatItIsTests(unittest.TestCase):
    """The title, the subtitle, the legend and the eleven numbered steps.

    The sheet fixes the title, the subtitle and the six kinds the legend names,
    and the middle column is eleven numbered steps. Each is read off the parsed
    drawing rather than described, so a redraw that drops one fails here instead
    of passing as a drawing nobody checked.
    """

    TITLE = "Tribunal - how one dispute is decided, and what happens after"
    SUBTITLE = (
        "Container view (C4 style) at freeze-2026-10-09, policy version 6, "
        "plus the post-sealed changes of 2026-10-10. Each element names the "
        "file that implements it."
    )
    LEGEND = (
        "Code, deterministic",
        "LLM call",
        "Human / operations",
        "Data / records",
        "Learning loop",
        "External system",
    )

    def _texts(self) -> List[str]:
        return [
            (element.text or "").strip()
            for element in ET.fromstring(svg_text()).iter()
            if local_name(element.tag) == "text"
        ]

    def test_it_carries_the_title_and_the_subtitle_the_sheet_fixes(self):
        found = self._texts()
        self.assertIn(self.TITLE, found, "the diagram does not carry the sheet's title")
        self.assertIn(
            self.SUBTITLE, found, "the diagram does not carry the sheet's subtitle"
        )

    def test_the_legend_names_the_six_kinds_of_element(self):
        found = set(self._texts())
        for label in self.LEGEND:
            with self.subTest(label=label):
                self.assertIn(
                    label, found, "the legend does not name {0!r}".format(label)
                )

    def test_the_middle_column_is_eleven_numbered_steps(self):
        """Read as structure, not by searching the text.

        A step's number is the only middle-anchored white text that is a bare
        digit -- the legend's swatch labels are not centred, and the LLM badges
        carry letters -- so the set of them is the diagram's own numbering.
        """
        numbers: List[int] = []
        for element in ET.fromstring(svg_text()).iter():
            if local_name(element.tag) != "text":
                continue
            if element.get("text-anchor") != "middle":
                continue
            if (element.get("fill") or "").lower() != "#ffffff":
                continue
            content = (element.text or "").strip()
            if content.isdigit():
                numbers.append(int(content))
        self.assertEqual(
            list(range(1, 12)),
            sorted(numbers),
            "the diagram's step badges are not numbered 1 to 11",
        )


class TheExtractorTests(unittest.TestCase):
    """The path extractor is shown to work, and to be able to fail."""

    def test_it_finds_the_paths_the_diagram_is_made_of(self):
        """A harvest that silently stopped working would otherwise pass."""
        found = set(paths_in(svg_text()))
        for required in (
            "tribunal/pipeline.py",
            "tribunal/brief.py",
            "prompts/v1/advocate.system.md",
            "precedents/precedents.jsonl",
            "ops/evidence.py",
            "ops/queue.py",
            "ops/evidence_window.py",
            "ops/chat_signals.py",
            "eval/policy_gaps.py",
            "eval/func_sets.py",
            "eval/early_majority.py",
            "ui/build.py",
            "ui/v2/build.py",
        ):
            self.assertIn(required, found, "{0} was not extracted".format(required))

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
    """Every path the diagram and the page write is a path in this repository."""

    def _missing(self, text: str, source: Path) -> List[str]:
        return [token for token in paths_in(text) if not resolve(token, source).exists()]

    def test_every_path_in_the_diagram_exists(self):
        self.assertEqual(
            [],
            self._missing(svg_text(), SVG_PATH),
            "a path written in docs/architecture.svg is not in the repository",
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
