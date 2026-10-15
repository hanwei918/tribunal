"""The version-8 case pages, held to the runs they are drawn from.

``ui/v8/build.py`` gives each of the 42 version-8 cases a page of its own, in
English and in Chinese, plus an index. This module holds it to eleven things:

* **The pages are there, and they are the ones the builder writes.** 42 case
  pages in each language plus the two index pages, every one of them committed
  byte for byte, and the set of names the build writes is the set the cheap path
  list states.
* **Nothing on a page is invented.** Every page states its own run's ruling, its
  amounts and its confidence; a gated case names the gate that fired; and the
  drafts are the ones the transcript records, kind by kind and validity by
  validity -- 903's two escalations, its one upheld fee and its one draft voided
  for citing ``POL-NS-08`` among them.
* **Nothing on a page is Python.** No page prints a dictionary's ``repr`` --
  ``{'`` and ``'value':`` are the shape a ``{value, evidence_id}`` leaf takes
  when it is printed rather than rendered -- and no element's whole text is a
  bare ``None``, ``True`` or ``False``. 903's driver deadline is the leaf that
  was printed, and its page now shows the time and the evidence id instead.
* **Every table scrolls in its own box.** Each ``table.dt`` on every page is the
  only child of a ``div.scroll-x``, the class ``ui/site/src/site.css`` defines,
  so the five-column drafts table and the run's 40-character commit cannot make
  the page wider than a phone.
* **The index's counts are the rows'.** The four figures above the table are
  recomputed here from the committed runs and asserted against the page.
* **The pages stay inside their own corner of ``ui/dist/``.** Every path this
  builder writes is disjoint from the product site's and from the version-6
  queue's, and the version-6 case pages are not touched.
* **The code's own sentences are printed in Chinese.** The brief's authority
  block, the version-8 gate's basis, a trip record's reason for having no driver
  deadline, the vote the pipeline appends to the judge's explanation and a gated
  case's whole explanation are sentences the code wrote, not the model, and a
  Chinese page prints them in Chinese. Only the places the builder fills from
  those fields are checked, because the parties' and the judge's own words stay
  English and may quote them.
* **The eight escalations that carry no ruling say so.** The six the gate
  stopped and the two without a majority record a confidence of 0.0 because
  there is no ruling for one to belong to, and their published line says
  "\u2014 (no ruling carried)" rather than "0.0"; the eighteen no-show cases whose
  band makes the AI's ruling final say "No bar" and name the clause.
* **Every code on a page has words beside it.** The words come first and the
  code follows in the small parenthesis, for the value band, the category, the
  rulings, the referee's verdicts and every evidence code the 42 cases carry.
* **The index's four cards state a number.** The big line is the count alone --
  ``42``, ``28/42``, ``6``, ``39/40`` -- and what it counts is the kicker above
  it and the line below it.
* **The check can fail.** A temporary copy of the ``dev-v8`` run with one case's
  ruling changed makes that case's page differ, which is what shows the page is
  drawn from the run document rather than written down; a page string with the
  dictionary put back is reported by the check for printed Python; and an
  unknown recorded text, evidence code or index card is refused or reported.

**No model call is made and no network is reached**: every reading is a
committed run, a committed key or a committed case file. The build reads every
brief, so the classes that build skip on a machine whose libm rounds case 111's
recorded digest away (``tests/portability.py``). Run from the project root
with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import copy
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Set
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, grade, run_benchmark  # noqa: E402
from tests import portability  # noqa: E402
from tribunal import brief as brief_module  # noqa: E402
from ui.site import build as site_build  # noqa: E402
from ui.v2 import build as v2  # noqa: E402
from ui.v8 import build as v8  # noqa: E402

MODEL = v8.MODEL

# The cases the sheet names, and what each one's page has to say.
GATED_BY_THE_AI_LIMIT = (902, 5010, 5015)
GATED_BY_THE_VALUE = (5012,)
GATED_BY_THE_FLAG = (5013, 5068)

# The case the control rewrites, and the ruling it is given: 5017's run published
# a ``NO_ACTION``, so a copy whose ruling is a ``FULL_REFUND`` is a copy whose
# page must differ.
CONTROL_CASE = 5017
CONTROL_RULING = {
    "ruling": "FULL_REFUND",
    "amount_sgd": 0.86,
    "driver_compensation_sgd": None,
    "referrals": [],
}

# The page every check reads the drafts off, and the table that carries them.
DRAFTS_HEADER = "Kind"

# What a page looks like when a Python value is printed instead of rendered: a
# dictionary's own repr, and a bare ``None``, ``True`` or ``False`` standing as
# an element's whole text. A page's prose may say the English word "None"
# ("None of the six chat entries"), so the bare token is only an offence when it
# is all an element holds; the dictionary's repr is one wherever it appears.
PYTHON_REPR_TOKENS = ("{'", "'value':", "{&#x27;")
PYTHON_WORD_RE = re.compile(r"\A(?:None|True|False)\Z")
SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
TABLE_RE = re.compile(r'<table class="dt">.*?</table>', re.S)
SCROLL_OPEN = '<div class="scroll-x">'
SCROLL_CLOSE = "</div>"

_CASES: "List[v8.V8Case] | None" = None
_PAGES: "Dict[str, str] | None" = None


def cases() -> List["v8.V8Case"]:
    """Every version-8 case, read once for the whole test process."""
    global _CASES
    if _CASES is None:
        portability.require_the_same_libm()
        _CASES = v8.read_every_case()
    return _CASES


def built_pages() -> Dict[str, str]:
    """Every page the builder makes, built once for the whole test process."""
    global _PAGES
    if _PAGES is None:
        loaded = cases()
        pages: Dict[str, str] = {}
        for case in loaded:
            for language in v8.LANGUAGES:
                name = case.link if language == v8.EN else case.zh_link
                pages[name] = v8.case_page(case, language)
        pages[v8.INDEX_PAGE] = v8.index_page(loaded, v8.EN)
        pages[v8.INDEX_PAGE.replace(".html", ".zh.html")] = v8.index_page(
            loaded, v8.ZH
        )
        _PAGES = pages
    return _PAGES


def committed(name: str) -> str:
    """One committed page, read from ``ui/dist/``."""
    return (v8.DIST_DIR / name).read_text(encoding="utf-8")


def text_of(page: str) -> str:
    """A page as a reader meets it: tags out, character references decoded."""
    return html.unescape(re.sub(r"<[^>]+>", " ", page))


def tables_of(page: str) -> List[str]:
    """Every ``.dt`` table on a page."""
    return TABLE_RE.findall(page)


def without_scripts(page: str) -> str:
    """A page with every ``<script>`` element taken out, tags and all.

    A ``<script>`` element's content is raw text, so stripping tags alone would
    leave it in the visible text; what a reader meets is the page without it.
    """
    return SCRIPT_RE.sub(" ", page)


def visible_text(page: str) -> str:
    """A page as a reader meets it: scripts out, tags out, references decoded."""
    return html.unescape(TAG_RE.sub(" ", without_scripts(page)))


def printed_python(page: str) -> List[str]:
    """Every place a page prints a Python value instead of the fact it holds.

    Two shapes, both of which a reader would meet as punctuation soup: a
    dictionary's ``repr`` (``{'``, ``'value':``), which is what a
    ``{value, evidence_id}`` leaf looks like when it is printed rather than
    rendered, and a bare ``None``, ``True`` or ``False`` that is an element's
    whole text. The first is looked for in the visible text and in the source
    (a reference-escaped apostrophe spells it ``{&#x27;``); the second only when
    the token is everything the element holds, because a page quotes the run's
    own prose and that prose says "None of the six chat entries".
    """
    source = without_scripts(page)
    text = visible_text(page)
    out = [token for token in PYTHON_REPR_TOKENS if token in text or token in source]
    for element in TAG_RE.split(source):
        word = html.unescape(element).strip()
        if PYTHON_WORD_RE.match(word):
            out.append(word)
    return out


def scroll_box_offenders(page: str) -> List[str]:
    """Every ``table.dt`` that is not the only child of a ``div.scroll-x``."""
    out: List[str] = []
    for match in TABLE_RE.finditer(page):
        before = page[max(0, match.start() - len(SCROLL_OPEN)):match.start()]
        after = page[match.end():match.end() + len(SCROLL_CLOSE)]
        if before != SCROLL_OPEN or after != SCROLL_CLOSE:
            out.append(match.group(0)[:60])
    return out


def row_with_label(page: str, label: str) -> List[str]:
    """The first body row of any ``.dt`` table whose label cell is ``label``."""
    for table in tables_of(page):
        for row in rows_of(table):
            if row and row[0] == label:
                return row
    raise AssertionError("no table row is labelled {0!r}".format(label))


def rows_of(table: str) -> List[List[str]]:
    """One table's body rows, each as its cells' text."""
    body = table.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    out: List[List[str]] = []
    for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        out.append(
            [
                html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
                for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
            ]
        )
    return out


def drafts_rows(page: str) -> List[List[str]]:
    """The drafts table's rows: the one ``.dt`` table whose header says Kind."""
    for table in tables_of(page):
        if ">{0}<".format(DRAFTS_HEADER) in table:
            return rows_of(table)
    raise AssertionError("the page carries no drafts table")


def index_rows(page: str) -> List[List[str]]:
    """The index table's rows, each as its cells' text."""
    body = page.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    return rows_of('<table class="dt"><tbody>{0}</tbody></table>'.format(body))


def page_for(case: "v8.V8Case", language: str = v8.EN) -> str:
    return built_pages()[case.link if language == v8.EN else case.zh_link]


# The nine sentences the code wrote rather than the model: the brief's authority
# block, the version-8 gate's own basis, and a trip record's reason for having no
# driver deadline. On a Chinese page every one of them is printed in Chinese, and
# the check below reads only the places the builder fills from them -- the
# parties' and the judge's own words stay as they were written and may quote any
# of the nine (an advocate on case 5051 quotes "on-demand trip: no scheduled
# time"), so the whole page is never scanned.
RECORDED_TEXTS = (
    "a route deviation (POL-RD-25)",
    "a no-show below POL-GEN-22's first band, where POL-NS-26 makes the AI "
    "ruling final",
    "a fraud flag on a party's profile (POL-GEN-22)",
    "neither a safety flag nor a value above POL-GEN-22's second band",
    "a safety flag on the dispute (POL-GEN-21)",
    "a dispute value above POL-GEN-22's second band",
    "the deviation is over the POL-RD-25 ceiling this policy applies to an AI "
    "ruling, so the ruling does not stand",
    "the dispute carries dispute.safety_flag, and POL-GEN-21 makes a flagged "
    "dispute a person's whatever the category and whatever the value",
    "on-demand trip: no scheduled time",
)

# The eight escalations that carry no ruling at all: the six the version-8 gate
# stopped and the two the panel could not agree on. And the eighteen no-show
# cases whose band makes the AI's ruling final, so the policy sets no bar.
NO_RULING_CASES = (902, 903, 5009, 5010, 5012, 5013, 5015, 5068)
NO_BAR_CASES = 18

SECTION_OPEN = '<section class="paper">'
LEDE_RE = re.compile(r'<p class="lede">(.*?)</p>', re.S)
BIG_RE = re.compile(r'<p class="big">(.*?)</p>')
BIG_LINE_RE = re.compile(r"\A\d+(/\d+)?\Z")


def as_written(text: str) -> "re.Pattern[str]":
    """A pattern that finds ``text`` however a page writes a non-ASCII character.

    A page writes a non-ASCII character as a numeric reference, and two writers
    spell one: ``ui.v2.build``'s decimal ``&#8212;`` and ``ui.v8.build``'s own
    hexadecimal ``&#x2014;``. Both render as the same character.
    """
    parts = []
    for character in text:
        if ord(character) < 128:
            parts.append(re.escape(character))
        else:
            parts.append("&#(?:x{0:x}|{0});".format(ord(character)))
    return re.compile("".join(parts))


def case_parts(page: str) -> List[str]:
    """A case page's seven numbered parts, in order."""
    return page.split(SECTION_OPEN)[1:]


def rows_labelled(page: str, label: str) -> List[List[str]]:
    """Every ``.dt`` body row whose label cell is ``label`` (there may be none)."""
    out: List[List[str]] = []
    for table in tables_of(page):
        for row in rows_of(table):
            if row and row[0] == label:
                out.append(row)
    return out


def builder_filled(page: str, language: str) -> List[str]:
    """The places a page is filled from the run's recorded sentences.

    Only these: the part 1 table and the sentence that says how the case was
    decided, the authority block (the last table of part 3), the driver-deadline
    row, and part 6, where the vote sentence or a gated case's whole explanation
    is printed. The parties' and the judge's own text is not one of them and is
    never read.
    """
    parts = case_parts(page)
    placed = [tables_of(parts[0])[0]]
    placed.extend(LEDE_RE.findall(parts[0]))
    placed.append(tables_of(parts[2])[-1])
    placed.extend(
        " ".join(row) for row in rows_labelled(page, v8.label("Driver deadline", language))
    )
    placed.append(parts[5])
    return placed


def driver_deadline_reason(case: "v8.V8Case") -> str:
    """The reason a trip record gives for having no deadline, or ``""``."""
    trip = v8._derived(case.brief, "TRIP_RECORD", brief_module.V7_KEY) or {}
    deadline = trip.get("driver_deadline")
    if isinstance(deadline, Mapping) and not deadline.get("deadline"):
        return str(deadline.get("reason") or "")
    return ""


def zero_confidence_rows(page: str, language: str) -> List[str]:
    """Every published-ruling row that still prints a confidence of 0.0."""
    label = v8.label("Published ruling", language)
    out: List[str] = []
    for table in tables_of(page):
        for row in rows_of(table):
            if row and row[0] == label and "0.0" in row[1]:
                out.append(row[1])
    return out


def evidence_table(page: str, language: str) -> Dict[str, str]:
    """Every evidence row: the artifact's id to the words and codes beside it."""
    wanted = as_written(">" + v8.label("Evidence id", language) + "<")
    for table in tables_of(page):
        if wanted.search(table):
            return {row[0]: row[1] for row in rows_of(table)}
    raise AssertionError("the page carries no evidence table")


def big_lines(page: str) -> List[str]:
    """The index's four big lines, as a reader meets them."""
    return [html.unescape(value) for value in BIG_RE.findall(page)]


def index_card_offenders(page: str) -> List[str]:
    """Every big line that is not a bare number, as the sentence it is."""
    return [
        value for value in big_lines(page) if not BIG_LINE_RE.match(value)
    ]


class ThePagesTests(unittest.TestCase):
    """The pages exist, they are the builder's own, and each is well-formed."""

    @classmethod
    def setUpClass(cls):
        portability.require_the_same_libm()
        cls.loaded = cases()
        cls.pages = built_pages()

    def test_the_builder_writes_a_page_for_every_case_in_both_languages(self):
        """42 cases, two languages each, plus the index in each language."""
        self.assertEqual(42, len(self.loaded))
        case_pages = [name for name in self.pages if name.startswith("v8-0")]
        self.assertEqual(84, len(case_pages))
        self.assertIn(v8.INDEX_PAGE, self.pages)
        self.assertIn(v8.INDEX_PAGE.replace(".html", ".zh.html"), self.pages)
        self.assertEqual(sorted(v8.written_paths()), sorted(self.pages))
        self.assertEqual(86, len(v8.written_paths()))

    def test_every_page_is_committed_and_equals_a_fresh_build(self):
        for name in sorted(self.pages):
            with self.subTest(page=name):
                path = v8.DIST_DIR / name
                self.assertTrue(path.is_file(), "ui/dist/{0} is not committed".format(name))
                self.assertEqual(
                    self.pages[name].encode("utf-8"),
                    path.read_bytes(),
                    "ui/dist/{0} differs from a fresh build".format(name),
                )

    def test_every_page_is_ascii(self):
        """These pages are this repository's own writing, so they are ASCII."""
        for name in sorted(self.pages):
            with self.subTest(page=name):
                offenders = sorted(
                    {ord(character) for character in self.pages[name] if ord(character) >= 128}
                )
                self.assertEqual([], offenders, "a page carries a non-ASCII character")

    def test_no_page_prints_a_python_value(self):
        """No page shows a dictionary's repr or a bare ``None``/``True``/``False``.

        A ``{value, evidence_id}`` leaf printed rather than rendered is what put
        ``{'value': ..., 'evidence_id': ...}`` on 903's page, and the builder now
        refuses a mapping or a list that reaches text, so this is the property
        the refusal buys.
        """
        for name in sorted(self.pages):
            with self.subTest(page=name):
                self.assertEqual([], printed_python(self.pages[name]))

    def test_every_table_is_the_only_child_of_a_scroll_box(self):
        """Every ``table.dt`` sits in the site's own ``.scroll-x`` box.

        The drafts table's five columns and the run's 40-character commit are
        wider than a phone; without the box the whole page scrolls sideways.
        """
        for name in sorted(self.pages):
            with self.subTest(page=name):
                self.assertIn('<table class="dt">', self.pages[name])
                self.assertEqual([], scroll_box_offenders(self.pages[name]))

    def test_every_link_on_every_page_resolves(self):
        for name in sorted(self.pages):
            page = self.pages[name]
            for url in re.findall(r'(?:href|src)="([^"]+)"', page):
                if url.startswith(("http", "#", "mailto:", "data:")):
                    continue
                with self.subTest(page=name, url=url):
                    target = (v8.DIST_DIR / url.split("#", 1)[0]).resolve()
                    self.assertTrue(
                        target.is_file(),
                        "ui/dist/{0} links to {1}, which is not there".format(name, url),
                    )

    def test_the_language_attribute_is_the_pages_own(self):
        for name in sorted(self.pages):
            with self.subTest(page=name):
                found = re.search(r'<html lang="([^"]+)"', self.pages[name])
                self.assertIsNotNone(found, "ui/dist/{0} states no lang".format(name))
                self.assertEqual(
                    "zh-Hans" if name.endswith(".zh.html") else "en",
                    found.group(1),
                )

    def test_the_language_switch_points_at_the_other_language(self):
        """The header's own two switches, which is what a reader clicks."""
        for case in self.loaded:
            with self.subTest(case=case.case_no):
                english = page_for(case, v8.EN)
                chinese = page_for(case, v8.ZH)
                self.assertEqual(
                    2,
                    english.count(
                        '<a href="{0}" lang="zh" hreflang="zh">'.format(case.zh_link)
                    ),
                )
                self.assertEqual(
                    2,
                    chinese.count(
                        '<a href="{0}" lang="en" hreflang="en">EN</a>'.format(case.link)
                    ),
                )
                # And the head's own alternates name the same two pages.
                self.assertIn(
                    '<link rel="alternate" hreflang="zh" href="{0}">'.format(
                        case.zh_link
                    ),
                    english,
                )
                self.assertIn(
                    '<link rel="alternate" hreflang="en" href="{0}">'.format(case.link),
                    chinese,
                )


class TheOutcomeTests(unittest.TestCase):
    """Every page states its own run's ruling, its amounts and its confidence."""

    @classmethod
    def setUpClass(cls):
        portability.require_the_same_libm()
        cls.loaded = cases()

    def test_every_page_states_the_runs_own_ruling(self):
        for case in self.loaded:
            for language in v8.LANGUAGES:
                page = text_of(page_for(case, language))
                with self.subTest(case=case.case_no, language=language):
                    self.assertIn(case.ruling_value, page)
                    self.assertIn(v8.ruling_words(case.ruling_value, language), page)
                    for field in ("amount_sgd", "driver_compensation_sgd"):
                        value = case.ruling.get(field)
                        if value is not None:
                            self.assertIn(
                                v2._money(value, case.currency), page, field
                            )
                    if case.confidence is not None and not v8.carries_no_ruling(case):
                        self.assertIn(str(case.confidence), page, "confidence")

    def test_the_gate_is_named_for_every_case_it_fired_on(self):
        """The three limbs, named on the pages of the cases they sent to a person."""
        gated = [case for case in self.loaded if case.gate is not None]
        self.assertEqual(6, len(gated))
        for case in self.loaded:
            page = text_of(page_for(case))
            with self.subTest(case=case.case_no):
                if case.gate is None:
                    self.assertNotIn("were not asked", page)
                    continue
                self.assertIn("were not asked", page)
                if case.case_no in GATED_BY_THE_AI_LIMIT:
                    self.assertIn("the 2 km limb of POL-RD-25", page)
                if case.case_no in GATED_BY_THE_VALUE:
                    self.assertIn("a value above SGD 50 under POL-GEN-22", page)
                if case.case_no in GATED_BY_THE_FLAG:
                    self.assertIn("a safety flag under POL-GEN-21", page)

    def test_the_gate_cases_carry_no_drafts_and_no_referee_verdict(self):
        for case in self.loaded:
            if case.gate is None:
                continue
            with self.subTest(case=case.case_no):
                page = text_of(page_for(case))
                self.assertIn("No drafts: the judge was not asked.", page)
                self.assertIn("No referee verdict was recorded.", page)

    def test_the_drafts_are_the_ones_the_transcript_records(self):
        for case in self.loaded:
            if case.gate is not None:
                continue
            rows = drafts_rows(page_for(case))
            drafts = case.drafts
            with self.subTest(case=case.case_no):
                self.assertEqual(len(drafts), len(rows))
                for draft, row in zip(drafts, rows):
                    self.assertEqual(str(draft["draft"]), row[0])
                    self.assertEqual(
                        v8.draft_kind_words(draft["kind"], v8.EN), row[1]
                    )
                    self.assertEqual(
                        "none" if draft["confidence"] is None else str(draft["confidence"]),
                        row[3],
                    )
                    if draft["valid"]:
                        self.assertEqual("valid", row[4])
                    else:
                        self.assertTrue(row[4].startswith("voided: "), row[4])
                        for code, _detail in v2._void_reasons(draft["abstention"]):
                            self.assertIn(code, row[4])

    def test_case_903_records_two_escalations_a_fee_and_a_voided_draft(self):
        """The four drafts the sheet names, exactly as the transcript has them."""
        case = next(case for case in self.loaded if case.case_no == 903)
        rows = drafts_rows(page_for(case))
        self.assertEqual(4, len(rows))
        self.assertEqual(
            [
                "sent to a human reviewer",
                "fee stands, driver compensated",
                "sent to a human reviewer",
                "no ruling was carried",
            ],
            [row[2].split(" (", 1)[0].lower() for row in rows],
        )
        self.assertEqual(["sampled", "sampled", "sampled", "position-swapped"],
                         [row[1] for row in rows])
        self.assertIn("SGD 5.00", rows[1][2])
        self.assertEqual(["valid", "valid", "valid"], [row[4] for row in rows[:3]])
        self.assertIn("DRAFT_CLAUSE_UNRESOLVED", rows[3][4])
        self.assertIn("POL-NS-08", rows[3][4])

    def test_case_903s_driver_deadline_is_the_time_and_its_evidence_id(self):
        """The one leaf that printed as a dictionary, in both languages.

        The brief wraps the deadline as ``{value, evidence_id}``. Its page shows
        the time of day and the evidence id beside it -- ``08:50:00
        (EV-TRIP-00903)`` -- and not the wrapper it arrives in.
        """
        case = next(case for case in self.loaded if case.case_no == 903)
        for language in v8.LANGUAGES:
            page = page_for(case, language)
            row = row_with_label(page, v8.label("Driver deadline", language))
            with self.subTest(language=language):
                self.assertEqual("08:50:00 (EV-TRIP-00903)", row[1])
                self.assertIn("08:50:00", text_of(page))
                self.assertIn("EV-TRIP-00903", text_of(page))

    def test_every_page_quotes_the_ruling_explanation_the_run_published(self):
        for case in self.loaded:
            first = str(case.ruling.get("explanation") or "").split("\n")[0].strip()
            if not first:
                continue
            with self.subTest(case=case.case_no):
                self.assertIn(html.unescape(first), text_of(page_for(case)))


class TheIndexTests(unittest.TestCase):
    """The index: one row per case, and four counts the rows add up to."""

    @classmethod
    def setUpClass(cls):
        portability.require_the_same_libm()
        cls.loaded = cases()

    def graded(self, set_name: str) -> "grade.GradeReport":
        """The set's committed run graded, read here rather than taken on trust."""
        development_set = development_sets.named(set_name)
        return run_benchmark.grade_run(
            development_sets.run_dir_at_its_version(development_set, MODEL),
            development_set.key(),
            case_loader=development_set.load_case,
            policy_version=development_set.policy_version,
        )

    def test_the_index_has_one_row_per_case(self):
        for language in v8.LANGUAGES:
            page = built_pages()[
                v8.INDEX_PAGE
                if language == v8.EN
                else v8.INDEX_PAGE.replace(".html", ".zh.html")
            ]
            with self.subTest(language=language):
                self.assertEqual(42, len(index_rows(page)))

    def test_the_index_counts_equal_the_rows(self):
        """Recomputed from the committed runs, then read off the page."""
        dev = self.graded("dev-v8")
        ryde = self.graded("ryde-v8")
        documents = {}
        for set_name in v8.SET_ORDER:
            development_set = development_sets.named(set_name)
            run_dir = development_sets.run_dir_at_its_version(development_set, MODEL)
            for case_no in development_set.cases:
                documents[case_no] = (
                    set_name,
                    json.loads(
                        (run_dir / "case-{0:05d}.json".format(case_no)).read_text(
                            encoding="utf-8"
                        )
                    ),
                    json.loads(
                        (
                            run_dir
                            / "case-{0:05d}.transcript.json".format(case_no)
                        ).read_text(encoding="utf-8")
                    ),
                )

        def escalated(case_no: int) -> bool:
            return documents[case_no][1]["ruling"]["ruling"]["ruling"] == "ESCALATE"

        def gated(case_no: int) -> bool:
            return "vote" not in documents[case_no][2]

        dev_cases = [no for no, row in documents.items() if row[0] == "dev-v8"]
        ryde_cases = [no for no, row in documents.items() if row[0] == "ryde-v8"]
        figures = {
            "total": len(documents),
            "no_person": sum(1 for no in documents if not escalated(no)),
            "gates": sum(1 for no in documents if gated(no)),
            "dev_total": len(dev_cases),
            "dev_no_person": sum(1 for no in dev_cases if not escalated(no)),
            "dev_gates": sum(1 for no in dev_cases if gated(no)),
            "ryde_total": len(ryde_cases),
            "ryde_no_person": sum(1 for no in ryde_cases if not escalated(no)),
            "ryde_gates": sum(1 for no in ryde_cases if gated(no)),
        }
        # The figures the sheet states, from the runs rather than from the page.
        self.assertEqual(42, figures["total"])
        self.assertEqual(40, figures["dev_total"])
        self.assertEqual(2, figures["ryde_total"])
        self.assertEqual(28, figures["dev_no_person"])
        self.assertEqual(6, figures["gates"])
        self.assertEqual(5, figures["dev_gates"])
        self.assertEqual(1, figures["ryde_gates"])
        self.assertEqual(39, dev.exact_matches)
        self.assertEqual(40, dev.total)
        self.assertEqual(1, ryde.exact_matches)
        self.assertEqual(2, ryde.total)
        # And the page states exactly those: each of the four big lines is a
        # bare number, and the words that say what it counts are the kicker above
        # it and the line below it.
        counts = v8.counts(self.loaded)
        bigs = [
            str(counts["total"]),
            "{0}/{1}".format(counts["no_person"], counts["total"]),
            str(counts["gates"]),
            "{0}/{1}".format(
                counts["sets"]["dev-v8"]["agree"], counts["sets"]["dev-v8"]["total"]
            ),
        ]
        self.assertEqual(["42", "28/42", "6", "39/40"], bigs)
        for language, lines in (
            (
                v8.EN,
                (
                    "dev-v8 40, ryde-v8 2",
                    "dev-v8 28 of 40, ryde-v8 0 of 2",
                    "dev-v8 5, ryde-v8 1",
                    "ryde-v8 1 of 2; the two sets are never pooled.",
                ),
            ),
            (
                v8.ZH,
                (
                    "dev-v8 40 \u4e2a\uff0cryde-v8 2 \u4e2a",
                    "dev-v8 28 / 40\uff0cryde-v8 0 / 2",
                    "dev-v8 5 \u4e2a\uff0cryde-v8 1 \u4e2a",
                    "ryde-v8 1 / 2\uff1b\u4e24\u4e2a\u6570\u636e\u96c6\u4ece\u4e0d\u5408\u5e76\u3002",
                ),
            ),
        ):
            page = built_pages()[
                v8.INDEX_PAGE
                if language == v8.EN
                else v8.INDEX_PAGE.replace(".html", ".zh.html")
            ]
            with self.subTest(language=language):
                self.assertEqual([], index_card_offenders(page))
                self.assertEqual(bigs, big_lines(page))
                for expected in lines:
                    self.assertIn(expected, text_of(page))

    def test_the_index_agrees_column_is_the_graders_own(self):
        """A row's yes/no is the four-field verdict, not the ruling alone."""
        rows = {int(row[0]): row for row in index_rows(built_pages()[v8.INDEX_PAGE])}
        self.assertEqual(len(self.loaded), len(rows))
        for case in self.loaded:
            with self.subTest(case=case.case_no):
                row = rows[case.case_no]
                self.assertEqual(case.set_name, row[1])
                self.assertEqual(str(case.value_band), row[4])
                self.assertEqual(
                    "yes" if case.score.exact else "no", row[7]
                )
                self.assertEqual(case.ruling_value, row[5].split("(", 1)[1].rstrip(")"))


class TheRecordedSentencesTests(unittest.TestCase):
    """The code's own sentences are printed in Chinese, and only they are."""

    @classmethod
    def setUpClass(cls):
        portability.require_the_same_libm()
        cls.loaded = cases()

    def test_the_nine_recorded_texts_are_the_ones_the_builder_knows(self):
        """The sheet's nine, and the builder's own table, are the same nine."""
        self.assertEqual(9, len(RECORDED_TEXTS))
        self.assertEqual(sorted(RECORDED_TEXTS), sorted(v8.RECORDED))

    def test_no_english_recorded_sentence_survives_on_a_chinese_page(self):
        """In the places the builder fills, on every one of the 42 pages."""
        for case in self.loaded:
            page = page_for(case, v8.ZH)
            with self.subTest(case=case.case_no):
                for place in builder_filled(page, v8.ZH):
                    for text in RECORDED_TEXTS:
                        self.assertNotIn(text, place)
                    self.assertIsNone(v8.VOTE_UNANIMOUS_EN.search(place))
                    self.assertIsNone(v8.VOTE_SPLIT_EN.search(place))
                    self.assertIsNone(v8.GATED_EN.search(place))

    def test_every_english_page_still_carries_the_recorded_text(self):
        """The control for the line above: the English is what was recorded."""
        for case in self.loaded:
            places = " ".join(builder_filled(page_for(case, v8.EN), v8.EN))
            with self.subTest(case=case.case_no):
                self.assertIn(case.required_basis, places)
                self.assertIn(
                    str(case.authority.get("human_only_basis") or ""), places
                )
                if case.gate is not None:
                    self.assertIn(str(case.gate.get("basis") or ""), places)

    def test_a_chinese_page_says_the_recorded_sentence_in_chinese(self):
        """And the Chinese it says it in is the table's own."""
        for case in self.loaded:
            page = text_of(page_for(case, v8.ZH))
            with self.subTest(case=case.case_no):
                self.assertIn(v8.recorded_words(case.required_basis, v8.ZH), page)
                self.assertIn(
                    v8.recorded_words(case.authority.get("human_only_basis"), v8.ZH),
                    page,
                )
                if case.gate is not None:
                    self.assertIn(
                        v8.recorded_words(case.gate.get("basis"), v8.ZH), page
                    )

    def test_the_driver_deadline_row_is_the_reason_in_each_language(self):
        """The 16 cases whose trip record gives a reason instead of a deadline."""
        checked = 0
        for case in self.loaded:
            reason = driver_deadline_reason(case)
            if not reason:
                continue
            checked += 1
            for language in v8.LANGUAGES:
                row = row_with_label(
                    page_for(case, language), v8.label("Driver deadline", language)
                )
                with self.subTest(case=case.case_no, language=language):
                    self.assertEqual(
                        reason
                        if language == v8.EN
                        else v8.recorded_words(reason, v8.ZH),
                        row[1],
                    )
        self.assertEqual(16, checked)

    def test_an_unknown_recorded_text_is_refused_on_a_chinese_page(self):
        """The control: a text the table does not know stops the build."""
        case = next(case for case in self.loaded if case.case_no == 5051)
        unknown = "an authority basis this builder does not know"
        authority = dict(case.authority)
        authority["required_confidence_basis"] = unknown
        broken = replace(case, authority=authority)
        with self.assertRaises(v8.BuildError):
            v8.case_page(broken, v8.ZH)
        # The English page still builds, and carries the text it was handed.
        self.assertIn(unknown, text_of(v8.case_page(broken, v8.EN)))


class TheNoRulingTests(unittest.TestCase):
    """The eight escalations with no ruling, and the eighteen with no bar."""

    @classmethod
    def setUpClass(cls):
        portability.require_the_same_libm()
        cls.loaded = cases()

    def no_ruling(self) -> List["v8.V8Case"]:
        return [case for case in self.loaded if v8.carries_no_ruling(case)]

    def test_eight_escalations_carry_no_ruling(self):
        """The six the gate stopped and the two without a majority."""
        self.assertEqual(
            list(NO_RULING_CASES),
            sorted(case.case_no for case in self.no_ruling()),
        )
        self.assertEqual(
            6, len([case for case in self.no_ruling() if case.gate is not None])
        )

    def test_the_published_line_says_so_and_never_zero(self):
        for case in self.no_ruling():
            for language in v8.LANGUAGES:
                page = page_for(case, language)
                row = row_with_label(
                    page, v8.label("Published ruling", language)
                )
                with self.subTest(case=case.case_no, language=language):
                    self.assertEqual([], zero_confidence_rows(page, language))
                    self.assertIn(v8.label("No ruling carried", language), row[1])

    def test_the_judges_own_escalations_keep_their_confidence(self):
        """A carried ruling still shows the confidence it carries."""
        judge = [
            case for case in self.loaded if v8.decision_of(case).kind == "judge"
        ]
        self.assertEqual(6, len(judge))
        for case in judge:
            for language in v8.LANGUAGES:
                row = row_with_label(
                    page_for(case, language), v8.label("Published ruling", language)
                )
                with self.subTest(case=case.case_no, language=language):
                    self.assertIn(str(case.confidence), row[1])
                    self.assertNotIn(
                        v8.label("No ruling carried", language), row[1]
                    )

    def test_the_check_reports_a_page_that_still_carries_zero(self):
        """The control: the same check on a page carrying "Confidence 0.0"."""
        page = page_for(self.no_ruling()[0], v8.EN)
        self.assertEqual([], zero_confidence_rows(page, v8.EN))
        put_back = as_written(v8.label("No ruling carried", v8.EN)).sub(
            "0.0", page, count=1
        )
        self.assertNotEqual(page, put_back, "the published line was not found")
        self.assertTrue(zero_confidence_rows(put_back, v8.EN))

    def test_the_eighteen_no_bar_pages_say_no_bar(self):
        no_bar = [case for case in self.loaded if v8.no_bar(case)]
        self.assertEqual(NO_BAR_CASES, len(no_bar))
        for case in no_bar:
            for language in v8.LANGUAGES:
                page = page_for(case, language)
                expected = v8.sentence(
                    "no bar",
                    language,
                    basis=v8.recorded_words(case.required_basis, language),
                )
                with self.subTest(case=case.case_no, language=language):
                    self.assertEqual(
                        expected,
                        row_with_label(
                            page, v8.label("Required confidence", language)
                        )[1],
                    )
                    # Part 1 and the authority block both say it.
                    self.assertEqual(2, text_of(page).count(expected))

    def test_the_other_bars_keep_their_number(self):
        for case in self.loaded:
            if v8.no_bar(case):
                continue
            for language in v8.LANGUAGES:
                row = row_with_label(
                    page_for(case, language),
                    v8.label("Required confidence", language),
                )
                with self.subTest(case=case.case_no, language=language):
                    self.assertTrue(row[1].startswith(str(case.required_confidence)))
                    self.assertIn(
                        v8.recorded_words(case.required_basis, language), row[1]
                    )


class TheEvidenceWordsTests(unittest.TestCase):
    """Every evidence code on the 42 cases has words in both languages."""

    @classmethod
    def setUpClass(cls):
        portability.require_the_same_libm()
        cls.loaded = cases()

    def codes(self) -> Set[str]:
        out: Set[str] = set()
        for case in self.loaded:
            for artifact in case.brief["case"]["evidence"]:
                out.add(str(artifact.get("evidence_type")))
                admissibility = artifact.get("admissibility") or {}
                out.add(str(admissibility.get("status")))
                for issue in admissibility.get("issues") or []:
                    out.add(str(issue))
        return out

    def test_every_code_the_cases_carry_has_words(self):
        self.assertEqual(sorted(v8.EVIDENCE), sorted(self.codes()))

    def test_every_evidence_row_is_the_words_and_the_code(self):
        for case in self.loaded:
            for language in v8.LANGUAGES:
                rows = evidence_table(page_for(case, language), language)
                with self.subTest(case=case.case_no, language=language):
                    for artifact in case.brief["case"]["evidence"]:
                        admissibility = artifact.get("admissibility") or {}
                        expected = "{0} ({1}) \u00b7 {2} ({3})".format(
                            v8.evidence_words(
                                artifact.get("evidence_type"), language
                            ),
                            artifact.get("evidence_type"),
                            v8.evidence_words(
                                admissibility.get("status"), language
                            ),
                            admissibility.get("status"),
                        )
                        for issue in admissibility.get("issues") or []:
                            expected += "; {0} ({1})".format(
                                v8.evidence_words(issue, language), issue
                            )
                        self.assertEqual(
                            expected, rows[artifact.get("evidence_id")]
                        )

    def test_an_unknown_evidence_code_is_refused(self):
        """The control: a code with no words stops the build."""
        case = next(case for case in self.loaded if case.case_no == 5051)
        brief = copy.deepcopy(case.brief)
        brief["case"]["evidence"][0]["evidence_type"] = "NO_SUCH_CODE"
        with self.assertRaises(v8.BuildError):
            v8.dispute_body(replace(case, brief=brief), v8.EN)


class TheIndexCardTests(unittest.TestCase):
    """The index's four cards: a number in the figure face, not a sentence."""

    @classmethod
    def setUpClass(cls):
        portability.require_the_same_libm()
        cls.loaded = cases()

    def index_page(self, language: str) -> str:
        name = (
            v8.INDEX_PAGE
            if language == v8.EN
            else v8.INDEX_PAGE.replace(".html", ".zh.html")
        )
        return built_pages()[name]

    def test_the_four_big_lines_are_the_counts(self):
        counts = v8.counts(self.loaded)
        expected = [
            str(counts["total"]),
            "{0}/{1}".format(counts["no_person"], counts["total"]),
            str(counts["gates"]),
            "{0}/{1}".format(
                counts["sets"]["dev-v8"]["agree"], counts["sets"]["dev-v8"]["total"]
            ),
        ]
        for language in v8.LANGUAGES:
            page = self.index_page(language)
            with self.subTest(language=language):
                self.assertEqual([], index_card_offenders(page))
                self.assertEqual(expected, big_lines(page))

    def test_the_check_reports_the_old_sentence(self):
        """The control: a big line that is a sentence again is reported."""
        page = self.index_page(v8.EN)
        self.assertEqual([], index_card_offenders(page))
        old = page.replace(
            '<p class="big">42</p>', '<p class="big">42 cases</p>', 1
        )
        self.assertNotEqual(page, old, "the first big line was not found")
        self.assertEqual(["42 cases"], index_card_offenders(old))


class TheBuildTests(unittest.TestCase):
    """``--check`` is clean, and the pages stay inside their own corner."""

    def test_check_passes_on_the_command_line(self):
        portability.require_the_same_libm()
        done = subprocess.run(
            [sys.executable, "-m", "ui.v8.build", "--check"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertNotIn("differs", done.stdout)
        self.assertNotIn("FATAL", done.stderr)

    def test_the_path_list_is_the_list_the_build_writes(self):
        portability.require_the_same_libm()
        self.assertEqual(
            frozenset(built_pages()),
            v8.written_paths(),
            "the cheap path list and the built pages disagree",
        )

    def test_no_page_this_builder_writes_is_one_another_builder_writes(self):
        """The version-6 queue's pages and the product site's are not touched."""
        mine = v8.written_paths()
        self.assertEqual(set(), mine & site_build.written_paths())
        self.assertEqual(set(), mine & version_six_paths())
        self.assertFalse([name for name in mine if name.startswith("replay/")])

    def test_a_version_six_page_is_still_byte_identical(self):
        """The control for the line above: the queue's own page has not moved."""
        portability.require_the_same_libm()
        case = v2._load_case("corpus", 208)
        self.assertEqual(
            v2.build_case_page(case).encode("utf-8"),
            (v2.DIST_DIR / case.link).read_bytes(),
        )


def version_six_paths() -> set:
    """Every page ``ui.v2.build`` writes, relative to ``ui/dist/``, cheaply.

    The queue, the page a host serves for an unknown address, the two images it
    copies, the four architecture views, and one page per case of its four runs.
    The case numbers are read off the run directories rather than from a build,
    so this answers without rebuilding a brief.
    """
    names = {
        v2.INDEX_PATH.name,
        v2.NOT_FOUND_PATH.name,
        v2.OG_IMAGE_LINK,
        v2.COVER_LINK,
    }
    names |= {
        "{0}/{1}".format(v2.ARCHITECTURE_DIRNAME, view)
        for view, _label in v2.ARCHITECTURE_VIEWS
    }
    for set_name in v2.SET_ORDER:
        run = v2._run_for(set_name)
        for case_no in v2._case_numbers(run.run_dir):
            names.add("case-{0:05d}.html".format(case_no))
    return names


class TheControlTests(unittest.TestCase):
    """A changed ruling in the run makes that case's page differ."""

    def test_the_check_for_printed_python_reports_a_dictionary_put_back(self):
        """The control: the page check sees the shape it is written to see.

        ``v8-00903.html``'s driver-deadline cell is read, the dictionary that
        was there before this part is put back in its place, and the check for
        printed Python is asked about the result. The bare-token limb is shown
        the same way, with an index cell's ``no`` replaced by ``None``.
        """
        page = committed("v8-00903.html")
        self.assertEqual([], printed_python(page))
        put_back = page.replace(
            "<td>08:50:00 (EV-TRIP-00903)</td>",
            "<td>{'value': '2026-09-13T08:50:00+08:00', "
            "'evidence_id': 'EV-TRIP-00903'}</td>",
            1,
        )
        self.assertNotEqual(page, put_back, "the deadline cell was not found")
        self.assertIn("{'", printed_python(put_back))
        self.assertIn("'value':", printed_python(put_back))

        index = committed(v8.INDEX_PAGE)
        self.assertEqual([], printed_python(index))
        self.assertIn("<td>no</td>", index)
        self.assertIn(
            "None",
            printed_python(index.replace("<td>no</td>", "<td>None</td>", 1)),
        )

    def test_a_changed_ruling_changes_that_cases_page(self):
        portability.require_the_same_libm()
        committed_page = committed("v8-{0:05d}.html".format(CONTROL_CASE))
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self._control_run(Path(directory))
            changed = self._page_from(run_dir, CONTROL_CASE)
        self.assertNotEqual(
            committed_page,
            changed,
            "case {0}'s ruling was changed in the run and its page did not "
            "move".format(CONTROL_CASE),
        )
        self.assertIn("Full refund (FULL_REFUND)", text_of(changed))
        self.assertIn("SGD 0.86", text_of(changed))

    @staticmethod
    def _control_run(root: Path) -> Path:
        """A copy of the ``dev-v8`` run with one case's ruling changed.

        The whole run is copied, so the copy can be graded and read exactly as
        the committed one is: only the one document's ``ruling`` object differs,
        and the brief the page checks itself against is untouched.
        """
        development_set = development_sets.named("dev-v8")
        source = development_sets.run_dir_at_its_version(development_set, MODEL)
        run_dir = root / "run"
        shutil.copytree(source, run_dir)
        path = run_dir / "case-{0:05d}.json".format(CONTROL_CASE)
        document = json.loads(path.read_text(encoding="utf-8"))
        document["ruling"]["ruling"].update(CONTROL_RULING)
        path.write_text(json.dumps(document), encoding="utf-8")
        return run_dir

    @staticmethod
    def _page_from(run_dir: Path, case_no: int) -> str:
        """One page, with the builder's own reader pointed at ``run_dir``.

        ``read_every_case`` reaches the run through
        ``eval.development_sets.run_dir_at_its_version``, so pointing that one
        call at the copy is what makes the build read the changed document --
        and nothing else about the build is replaced.
        """
        real = development_sets.run_dir_at_its_version

        def pointed(development_set: Any, model: str, runs_dir: Any = None) -> Path:
            if development_set.name == "dev-v8":
                return run_dir
            if runs_dir is None:
                return real(development_set, model)
            return real(development_set, model, runs_dir)

        with mock.patch.object(
            development_sets, "run_dir_at_its_version", pointed
        ):
            loaded = v8.read_every_case()
        case = next(case for case in loaded if case.case_no == case_no)
        return v8.case_page(case, v8.EN)


if __name__ == "__main__":
    unittest.main()
