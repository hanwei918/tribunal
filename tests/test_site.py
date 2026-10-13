"""Tests for ``ui.site``: the policy owner's product site, built from this repository.

The policy owner, Ji Guofang, designed the product site outside WorkBuddy --
22 pages, each in English and Chinese, with the images they carry and a try-it
page that runs this repository's own Python in the browser.
``tools/site_import.py`` transcribed her files into ``ui/site/src/`` and
``ui/site/static/``, and ``ui/site/build.py`` builds the site back out of them
into ``ui/dist/``. What is under test here is that the build is the one the
sources say it is, that the pages hold together as a site, and that the bundle
the browser runs is this repository's own code.

No network, no browser, no credential, no model call, and no read of the
gitignored scratch directory her files arrived in: every check below reads a
committed file.

**What this module does not do.** It does not compare the built pages with her
originals -- those are the importer's own round trip, which it reports when it
runs, and a test that read them would be a test that needs the machine that
wrote them. What it holds instead is that every built page equals a fresh build
from the committed sources, which is the property that survives a clean clone.

Run from the project root with::

    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import io
import re
import sys
import unittest
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import portability  # noqa: E402
from ui import build as replay_build  # noqa: E402
from ui.site import build as site  # noqa: E402
from ui.v2 import build as v2  # noqa: E402

# The one file the pages name that the site does not carry: the film, which has
# not been delivered, and which the front page shows as "Film coming soon"
# without. It is named rather than skipped in silence, so a second missing file
# is a failure rather than a second exception.
MISSING_FILM = "assets/tribunal-film.mp4"

# The links off the site, by name. Every other link a page carries is a file
# inside ``ui/dist/``, and is checked as one. The three are the sources the
# safety page cites.
EXTERNAL_LINKS = frozenset(
    {
        "https://arxiv.org/abs/2403.14720",
        "https://arxiv.org/abs/1803.09010",
        "https://aclanthology.org/2020.acl-main.442",
    }
)

# The four files her try-it service arrives as, and the path each is committed
# at. They travel in the bundle the browser runs, and they are hers: this
# repository imports them and does not edit them.
TRYIT_FILES = (
    "tryit/__init__.py",
    "tryit/build_bundle.py",
    "tryit/case.py",
    "tryit/server.py",
)


def pages() -> Dict[str, str]:
    """Every page this builder writes, by name, built once for the process."""
    global _PAGES
    if _PAGES is None:
        _PAGES = {path.name: text for path, text in site.pages()}
    return _PAGES


_PAGES: "Dict[str, str] | None" = None


# --------------------------------------------------------------------------
# Reading a page's references
# --------------------------------------------------------------------------
class _ResourceScan(HTMLParser):
    """Every attribute that names a resource, and every anchor's target.

    ``href`` on an anchor is **not** a resource: an anchor is a navigation
    target, and nothing is fetched when the page loads. The two lists are kept
    apart because the two rules are different -- a page may link to another
    host by name, and may not load from one.
    """

    RESOURCE_ATTRIBUTES = (
        "src",
        "srcset",
        "href",
        "data",
        "poster",
        "action",
        "formaction",
        "background",
        "manifest",
        "cite",
    )

    NAVIGATION_TAGS = frozenset({"a", "area"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: List[Tuple[str, str, str]] = []
        self.anchors: List[str] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name not in self.RESOURCE_ATTRIBUTES:
                continue
            text = value or ""
            if name == "href" and tag in self.NAVIGATION_TAGS:
                self.anchors.append(text)
                continue
            if name == "srcset":
                for candidate in text.split(","):
                    parts = candidate.strip().split()
                    if parts:
                        self.references.append((tag, name, parts[0]))
            else:
                self.references.append((tag, name, text))


def scan(text: str) -> _ResourceScan:
    scanner = _ResourceScan()
    scanner.feed(text)
    return scanner


def is_external(url: str) -> bool:
    """Whether a URL names another host -- ``data:`` is the page's own bytes."""
    text = url.strip()
    if not text or text.startswith("#"):
        return False
    if text.startswith("//"):
        return True
    scheme = re.match(r"^([A-Za-z][A-Za-z0-9+.\-]*):", text)
    return scheme is not None and scheme.group(1).lower() != "data"


def is_relative(url: str) -> bool:
    """Whether a URL names a file beside the page rather than a host or its own bytes."""
    return not is_external(url) and not url.strip().startswith(("data:", "#"))


def file_part(url: str) -> str:
    """A URL's path, with its fragment and query off: what has to be a file."""
    return url.strip().split("#", 1)[0].split("?", 1)[0]


def unresolved_links() -> List[Tuple[str, str]]:
    """Every relative link or source in the 22 pages that is not a file in the site."""
    found: List[Tuple[str, str]] = []
    for name, text in sorted(pages().items()):
        scanner = scan(text)
        urls = [url for _tag, _attr, url in scanner.references] + scanner.anchors
        for url in urls:
            if not is_relative(url):
                continue
            target = file_part(url)
            if not target or (site.DIST_DIR / target).is_file():
                continue
            found.append((name, target))
    return sorted(set(found))


# --------------------------------------------------------------------------
# What the other two builders write into the same root
# --------------------------------------------------------------------------
def queue_paths() -> Set[str]:
    """Every path ``ui.v2.build`` writes, relative to ``ui/dist/``.

    Its two fixed pages, the six files it copies in and its architecture views
    come from its own constants; its one-page-per-case files come from its own
    case registry, which lists the run directories rather than loading the
    cases, so the check costs a directory listing rather than a build.
    """
    names = {v2.INDEX_PATH.name, v2.NOT_FOUND_PATH.name}
    names |= {path.relative_to(v2.DIST_DIR).as_posix() for path, _ in v2.assets()}
    names |= {
        "case-{0:05d}.html".format(case_no)
        for set_name in v2.SET_ORDER
        for case_no in v2._case_numbers(v2._run_for(set_name).run_dir)
    }
    return names


def replay_paths() -> Set[str]:
    """Every path ``ui.build`` writes: its five pages and the runs index."""
    written = {Path(page.output_path) for page in replay_build.pages().values()}
    written.add(replay_build.INDEX_PATH)
    return {path.relative_to(v2.DIST_DIR).as_posix() for path in written}


# --------------------------------------------------------------------------
# The build is the one the sources say it is
# --------------------------------------------------------------------------
class TheBuildIsCurrentTests(unittest.TestCase):
    """What ``python3 -m ui.site.build --check`` checks, in process."""

    def test_every_page_equals_a_fresh_build(self):
        portability.require_the_same_libm()
        for destination, text in site.pages():
            with self.subTest(page=destination.name):
                self.assertTrue(
                    destination.is_file(),
                    "{0} is not committed; run `python3 -m ui.site.build`".format(destination),
                )
                self.assertEqual(
                    text,
                    destination.read_text(encoding="utf-8"),
                    "{0} differs from a fresh build; run `python3 -m ui.site.build`".format(
                        destination
                    ),
                )

    def test_every_static_file_and_the_bundle_equal_a_fresh_build(self):
        for destination, data in site.assets():
            with self.subTest(file=destination.relative_to(site.DIST_DIR).as_posix()):
                self.assertTrue(
                    destination.is_file(),
                    "{0} is not committed; run `python3 -m ui.site.build`".format(destination),
                )
                self.assertEqual(
                    data,
                    destination.read_bytes(),
                    "{0} differs from a fresh build; run `python3 -m ui.site.build`".format(
                        destination
                    ),
                )

    def test_every_static_file_is_its_source_byte_for_byte(self):
        """The images and the try-it page's own files are copied, not rendered."""
        for source in sorted(site.STATIC_DIR.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(site.STATIC_DIR)
            with self.subTest(path=relative.as_posix()):
                self.assertEqual(
                    source.read_bytes(), (site.DIST_DIR / relative).read_bytes()
                )


class TheBuildersShareTheRootTests(unittest.TestCase):
    """Three builders write into ``ui/dist/``, and no file is written by two."""

    def test_the_site_writes_no_path_the_queue_writes(self):
        self.assertEqual(set(), site.written_paths() & queue_paths())

    def test_the_site_writes_no_path_the_replay_writes(self):
        self.assertEqual(set(), site.written_paths() & replay_paths())

    def test_the_other_two_lists_name_files_that_are_there(self):
        """A list that named nothing would make the two checks above vacuous."""
        for name in sorted(queue_paths() | replay_paths()):
            with self.subTest(path=name):
                self.assertTrue(
                    (site.DIST_DIR / name).is_file(),
                    "{0} is not in the site root".format(name),
                )


# --------------------------------------------------------------------------
# The pages
# --------------------------------------------------------------------------
class ThePagesTests(unittest.TestCase):
    """Twenty-two pages, assembled from the sources with every marker put back."""

    def test_the_site_is_the_pages_her_design_names(self):
        portability.require_the_same_libm()
        self.assertEqual(22, site.PAGE_COUNT)
        self.assertEqual(22, len(pages()))
        self.assertEqual(22, len(site.page_sources()))

    def test_every_page_carries_her_two_languages(self):
        portability.require_the_same_libm()
        english = {name for name in pages() if not name.endswith(".zh.html")}
        self.assertEqual(11, len(english), sorted(english))
        self.assertEqual(22, len(pages()))

    def test_no_page_carries_a_marker_left_over(self):
        portability.require_the_same_libm()
        for name, text in sorted(pages().items()):
            with self.subTest(page=name):
                self.assertNotIn("/*@include ", text)
                self.assertNotIn("@include", text)
                self.assertNotIn("@queue-rows", text)

    def test_the_sources_do_carry_the_markers(self):
        """The control: the check above would pass on a page with no block at all."""
        marked = {
            path.name
            for path in site.page_sources()
            if "/*@include " in path.read_text(encoding="utf-8")
        }
        self.assertEqual(22, len(marked), sorted(marked))

    def test_the_shared_blocks_are_the_four_the_importer_factored_out(self):
        self.assertEqual(
            {"site.css", "redirect.css", "site.en.js", "site.zh.js"},
            set(site.shared_blocks()),
        )

    def test_a_page_whose_marker_names_nothing_is_refused(self):
        """A marker is a promise that the block is there, and it is kept."""
        with self.assertRaises(site.BuildError):
            site.assemble("<style>/*@include not-a-block.css*/</style>", site.shared_blocks())

    def test_a_queue_marker_for_a_language_the_builder_does_not_write_is_refused(self):
        """A marker naming a language with no rows would otherwise stay in the page."""
        with self.assertRaises(site.BuildError):
            site.assemble(
                "<tbody>/*@queue-rows fr*/</tbody>",
                site.shared_blocks(),
                {"en": "<tr></tr>", "zh": "<tr></tr>"},
            )

    def test_a_queue_marker_is_put_back_with_the_rows_it_names(self):
        """The mechanism, on a fixture, so the rows are the builder's own."""
        rows = {"en": "<tr><td>en</td></tr>", "zh": "<tr><td>zh</td></tr>"}
        self.assertEqual(
            "<tbody><tr><td>zh</td></tr></tbody>",
            site.assemble(
                "<tbody>/*@queue-rows zh*/</tbody>", site.shared_blocks(), rows
            ),
        )


# --------------------------------------------------------------------------
# The queue table, built from the queue's own rows
# --------------------------------------------------------------------------
# One table cell, and one status chip. The cells are read by column so the two
# languages' rows can be compared column by column rather than as markup.
QUEUE_CELL_RE = re.compile(r'<td data-column="([a-z_]+)"([^>]*)>(.*?)</td>', re.S)
QUEUE_CHIP_RE = re.compile(r'<span class="chip ([a-z]+)"')

# The English vocabulary the queue writes into a row. None of it may appear in a
# Chinese row: a translated table that left one word behind would be a table that
# reads in two languages at once.
ENGLISH_QUEUE_WORDS = frozenset(
    set(v2.CATEGORY_WORDS.values())
    | set(v2.FILED_BY_WORDS.values())
    | set(v2.CHIP_LABELS.values())
    | set(v2.RULING_WORDS.values())
    | set(v2.TRIGGER_WORDS.values())
    | {"Sent to a reviewer", "Sent to a person", "driver paid"}
    | {
        "Case",
        "Category",
        "Filed by",
        "Amount contested",
        "Status",
        "Outcome",
        "Confidence",
        "Time",
    }
)

# The four columns whose cells are the run's own values and are written the same
# in both languages.
SAME_IN_BOTH = ("case", "amount", "confidence", "time")


class TheQueueTableTests(unittest.TestCase):
    """``cases.html``'s table body and ``cases.zh.html``'s, built not copied.

    Until part 53b the Chinese body was a copy of the English one, so every
    category, the filing party, the status and the outcome were English on a
    Chinese page. The builder now writes both from ``ui.v2.build``'s own row
    function, and these are the checks that say so.
    """

    def body_of(self, markup: str) -> str:
        match = re.search(r"<tbody>(.*)</tbody>", markup, re.S)
        self.assertIsNotNone(match, "the page carries no table body")
        assert match is not None
        return match.group(1)

    def rows_of(self, markup: str) -> List[str]:
        return re.findall(r"<tr\b.*?</tr>", self.body_of(markup), re.S)

    def cells_of(self, row: str) -> Dict[str, str]:
        return {
            name: value
            for name, _attributes, value in QUEUE_CELL_RE.findall(row)
        }

    def sorts_of(self, row: str) -> Dict[str, str]:
        found = {}
        for name, attributes, _value in QUEUE_CELL_RE.findall(row):
            match = re.search(r'data-sort="([^"]*)"', attributes)
            found[name] = match.group(1) if match else ""
        return found

    def chip_classes_of(self, row: str) -> List[str]:
        return QUEUE_CHIP_RE.findall(row)

    def test_the_sources_carry_a_marker_rather_than_the_rows(self):
        for name, language in (("cases.html", "en"), ("cases.zh.html", "zh")):
            source = (site.PAGES_DIR / name).read_text(encoding="utf-8")
            with self.subTest(page=name):
                self.assertIn("/*@queue-rows {0}*/".format(language), source)
                self.assertLess(
                    len(source),
                    30_000,
                    "the 151 rows are still written out in the source",
                )

    def test_the_english_table_is_the_queue_pages_own_rows(self):
        """The queue page's table body, row for row and byte for byte."""
        portability.require_the_same_libm()
        queue = (site.DIST_DIR / v2.INDEX_PATH.name).read_text(encoding="utf-8")
        self.assertEqual(self.body_of(queue), self.body_of(pages()["cases.html"]))

    def test_the_english_table_is_the_rows_the_row_function_writes(self):
        """The same equality, against the function rather than the built page."""
        portability.require_the_same_libm()
        expected = "".join(v2._queue_row(case) for case in v2.read_every_case())
        self.assertEqual(expected, self.body_of(pages()["cases.html"]))
        self.assertEqual(151, len(self.rows_of(pages()["cases.html"])))

    def test_the_chinese_table_is_the_same_rows_with_the_values_unchanged(self):
        """Same case, amount, confidence, time and status class as the English row."""
        portability.require_the_same_libm()
        english = self.rows_of(pages()["cases.html"])
        chinese = self.rows_of(pages()["cases.zh.html"])
        self.assertEqual(151, len(chinese))
        self.assertEqual(len(english), len(chinese))
        for one, other in zip(english, chinese):
            cells = self.cells_of(one)
            with self.subTest(case=cells["case"]):
                self.assertEqual(self.sorts_of(one), self.sorts_of(other))
                self.assertEqual(self.chip_classes_of(one), self.chip_classes_of(other))
                for column in SAME_IN_BOTH:
                    self.assertEqual(cells[column], self.cells_of(other)[column])

    def test_no_english_word_from_the_queue_is_left_in_a_chinese_row(self):
        portability.require_the_same_libm()
        for row in self.rows_of(pages()["cases.zh.html"]):
            with self.subTest(case=self.cells_of(row)["case"]):
                for word in sorted(ENGLISH_QUEUE_WORDS):
                    self.assertNotIn(
                        word,
                        row,
                        "a Chinese row still carries the English word {0!r}".format(word),
                    )

    def test_the_english_rows_do_carry_the_words_the_chinese_ones_do_not(self):
        """The control: the words the check looks for are in the English rows.

        Every word the vocabulary states that this table actually draws is
        named. Two are not: no case in the four runs reaches the grey chip, so
        "No status is recorded" is never drawn, and every ``ESCALATE`` case has a
        trigger, so the outcome column never falls through to the ruling words
        "Sent to a human reviewer".
        """
        portability.require_the_same_libm()
        english = self.body_of(pages()["cases.html"])
        for word in (
            "Route deviation",
            "No-show fee",
            "Rider",
            "Driver",
            "Decided automatically",
            "Held for release",
            "Sent to a reviewer",
            "Full refund",
            "Partial refund",
            "No change",
            "Fee stands, driver compensated",
            "safety or complaint flag",
            "no judge draft passed the code checks",
            "the judge escalated under the policy",
            "driver paid",
            "Case",
            "Category",
            "Filed by",
            "Amount contested",
            "Status",
            "Outcome",
            "Confidence",
            "Time",
        ):
            with self.subTest(word=word):
                self.assertIn(word, english)
                self.assertIn(word, ENGLISH_QUEUE_WORDS)


# --------------------------------------------------------------------------
# The pages hold together as a site
# --------------------------------------------------------------------------
class TheLinksTests(unittest.TestCase):
    """Every link inside the site resolves, and nothing is loaded from outside it."""

    def test_every_relative_link_and_source_resolves_inside_the_site(self):
        portability.require_the_same_libm()
        unresolved = [
            (name, url) for name, url in unresolved_links() if url != MISSING_FILM
        ]
        self.assertEqual(
            [],
            unresolved,
            "a page links to a file the site does not carry: {0}".format(unresolved),
        )

    def test_the_one_file_the_site_does_not_carry_is_the_film(self):
        """Exactly one, and named: a second missing file is a failure."""
        portability.require_the_same_libm()
        missing = sorted({url for _name, url in unresolved_links()})
        self.assertEqual([MISSING_FILM], missing)

    def test_no_page_loads_a_script_a_stylesheet_an_image_or_a_font_from_another_host(self):
        portability.require_the_same_libm()
        found: List[Tuple[str, str, str]] = []
        for name, text in sorted(pages().items()):
            for tag, attribute, url in scan(text).references:
                if is_external(url):
                    found.append((name, tag, url))
        self.assertEqual(
            [],
            found,
            "a page loads a resource from another host: {0}".format(found),
        )

    def test_the_only_links_off_the_site_are_the_three_named_ones(self):
        portability.require_the_same_libm()
        found: Set[str] = set()
        for text in pages().values():
            for url in scan(text).anchors:
                if is_external(url):
                    found.add(url.strip())
        self.assertEqual(EXTERNAL_LINKS, found)

    def test_the_film_is_the_one_file_a_page_names_but_does_not_have(self):
        """The exception is real: the page names it, and the site does not hold it."""
        portability.require_the_same_libm()
        named = {url for _name, url in unresolved_links()}
        self.assertIn(MISSING_FILM, named)
        self.assertFalse((site.DIST_DIR / MISSING_FILM).exists())


# --------------------------------------------------------------------------
# The bundle the browser runs
# --------------------------------------------------------------------------
class TheBundleTests(unittest.TestCase):
    """``try/tribunal-core.zip``: this repository's own Python, and nothing else."""

    def test_the_list_is_the_thirty_nine_paths(self):
        self.assertEqual(39, len(site.BUNDLE_PATHS))
        self.assertEqual(sorted(site.BUNDLE_PATHS), list(site.BUNDLE_PATHS))
        self.assertEqual(len(set(site.BUNDLE_PATHS)), len(site.BUNDLE_PATHS))

    def test_the_list_is_what_her_own_bundle_builder_would_put_in_it(self):
        """Her ``tryit/build_bundle.py`` computes the same paths, from this tree.

        The constant in the builder is written out rather than globbed, so a
        module that appeared beside the others cannot slip into the bundle; this
        is what holds it to the set her own code would choose.
        """
        from tryit import build_bundle

        expected = sorted(
            path.relative_to(PROJECT_ROOT).as_posix() for path in build_bundle.core_files()
        )
        self.assertEqual(39, len(expected), expected)
        self.assertEqual(expected, sorted(site.BUNDLE_PATHS))

    def test_every_entry_is_the_repositorys_own_file(self):
        with zipfile.ZipFile(io.BytesIO(site.bundle_bytes())) as archive:
            self.assertEqual(sorted(site.BUNDLE_PATHS), archive.namelist())
            for relative in site.BUNDLE_PATHS:
                with self.subTest(path=relative):
                    self.assertEqual(
                        (PROJECT_ROOT / relative).read_bytes(),
                        archive.read(relative),
                        "{0} is not the repository's file".format(relative),
                    )

    def test_two_builds_give_the_same_bytes(self):
        self.assertEqual(site.bundle_bytes(), site.bundle_bytes())

    def test_the_committed_bundle_is_the_one_this_code_builds(self):
        self.assertTrue(site.BUNDLE_PATH.is_file(), "the bundle is not committed")
        self.assertEqual(site.bundle_bytes(), site.BUNDLE_PATH.read_bytes())

    def test_every_entry_carries_the_same_fixed_time(self):
        """A zip stamped from the files' own mtimes differs on every checkout."""
        with zipfile.ZipFile(io.BytesIO(site.bundle_bytes())) as archive:
            stamps = {info.date_time for info in archive.infolist()}
        self.assertEqual({site.BUNDLE_TIMESTAMP}, stamps)


# --------------------------------------------------------------------------
# The try-it service
# --------------------------------------------------------------------------
class TheTryItServiceTests(unittest.TestCase):
    """Her service is committed unchanged, and the live one is off."""

    def test_the_committed_config_leaves_the_address_empty(self):
        """The live service stays off until an owner sets the address."""
        config = site.STATIC_DIR / "try-config.js"
        text = config.read_text(encoding="utf-8")
        self.assertIn('window.TRIBUNAL_TRY_API = "";', text)

    def test_the_site_ships_the_config_it_is_checked_against(self):
        self.assertEqual(
            (site.STATIC_DIR / "try-config.js").read_bytes(),
            (site.DIST_DIR / "try-config.js").read_bytes(),
        )

    def test_the_try_it_page_loads_her_script_and_the_config(self):
        portability.require_the_same_libm()
        page = pages()["try.html"]
        self.assertIn('src="try/try.js"', page)
        self.assertIn('src="try-config.js"', page)

    def test_her_service_is_committed_and_travels_in_the_bundle(self):
        for relative in TRYIT_FILES:
            with self.subTest(path=relative):
                self.assertTrue((PROJECT_ROOT / relative).is_file(), relative)
                self.assertIn(relative, site.BUNDLE_PATHS)

    def test_the_service_is_the_four_files_and_nothing_else(self):
        found = sorted(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in (PROJECT_ROOT / "tryit").glob("*.py")
        )
        self.assertEqual(sorted(TRYIT_FILES), found)


if __name__ == "__main__":
    unittest.main()
