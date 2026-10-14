"""The version-8 case pages, held to the runs they are drawn from.

``ui/v8/build.py`` gives each of the 42 version-8 cases a page of its own, in
English and in Chinese, plus an index. This module holds it to five things:

* **The pages are there, and they are the ones the builder writes.** 42 case
  pages in each language plus the two index pages, every one of them committed
  byte for byte, and the set of names the build writes is the set the cheap path
  list states.
* **Nothing on a page is invented.** Every page states its own run's ruling, its
  amounts and its confidence; a gated case names the gate that fired; and the
  drafts are the ones the transcript records, kind by kind and validity by
  validity -- 903's two escalations, its one upheld fee and its one draft voided
  for citing ``POL-NS-08`` among them.
* **The index's counts are the rows'.** The four figures above the table are
  recomputed here from the committed runs and asserted against the page.
* **The pages stay inside their own corner of ``ui/dist/``.** Every path this
  builder writes is disjoint from the product site's and from the version-6
  queue's, and the version-6 case pages are not touched.
* **The check can fail.** A temporary copy of the ``dev-v8`` run with one case's
  ruling changed makes that case's page differ, which is what shows the page is
  drawn from the run document rather than written down.

**No model call is made and no network is reached**: every reading is a
committed run, a committed key or a committed case file. The build reads every
brief, so the classes that build skip on a machine whose libm rounds case 111's
recorded digest away (``tests/portability.py``). Run from the project root
with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, grade, run_benchmark  # noqa: E402
from tests import portability  # noqa: E402
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
    return re.findall(r'<table class="dt">.*?</table>', page, re.S)


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
                    if case.confidence is not None:
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
        # And the page states exactly those.
        for language, expects in (
            (
                v8.EN,
                (
                    "42 cases",
                    "28 of 42 decided with no person",
                    "dev-v8 28 of 40, ryde-v8 0 of 2",
                    "6 gates",
                    "dev-v8 5, ryde-v8 1",
                    "dev-v8 39 of 40; ryde-v8 1 of 2",
                    "The two sets are never pooled.",
                ),
            ),
            (
                v8.ZH,
                (
                    "42 \u4e2a\u6848\u4ef6",
                    "dev-v8 28 / 40\uff0cryde-v8 0 / 2",
                    "6 \u4e2a\u95f8\u95e8",
                    "dev-v8 39 / 40\uff1bryde-v8 1 / 2",
                ),
            ),
        ):
            page = text_of(
                built_pages()[
                    v8.INDEX_PAGE
                    if language == v8.EN
                    else v8.INDEX_PAGE.replace(".html", ".zh.html")
                ]
            )
            for expected in expects:
                with self.subTest(language=language, text=expected):
                    self.assertIn(expected, page)

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
