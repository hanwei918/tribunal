"""The 151 version-6 case pages ``ui.v6.build`` writes, in both languages.

What is held here:

* the set of pages: one English and one Chinese page per case of the four
  version-6 runs, 302 in all, each byte for byte a fresh build;
* every page is ASCII (non-ASCII text is written as character references), as
  the repository's language rule asks of everything outside ``runs/``;
* the Chinese page is a Chinese page: ``lang="zh-Hans"``, its own language switch
  pointing at the English twin, and the page's own words in Chinese;
* the money on each page is the record's own: the ruling's amount and the
  driver's share appear exactly as the run recorded them;
* nothing the brief masks comes back: no vehicle registration in a chat line;
* every local link on a page resolves to a file under ``ui/dist/``.
"""

from __future__ import annotations

import html
import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import portability  # noqa: E402
from ui.v2 import build as v2  # noqa: E402
from ui.v6 import build as v6  # noqa: E402

PLATE_RE = re.compile(r"\bS[A-Z]{1,2}\d{1,4}[A-Z]\b")
HREF_RE = re.compile(r'href="([^"#?]+)')


def visible(markup: str) -> str:
    markup = re.sub(r"<(script|style)\b.*?</\1>", " ", markup, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", markup))


class VersionSixPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        portability.require_the_same_libm()
        cls.cases = v2.read_every_case()
        cls.pages = {path.name: text for path, text in v6.pages()}

    def test_one_page_per_case_and_language(self):
        expected = {
            v6.link(case.case_no, language)
            for case in self.cases
            for language in v6.LANGUAGES
        }
        self.assertEqual(302, len(expected))
        self.assertEqual(expected, set(self.pages))

    def test_the_committed_pages_are_a_fresh_build(self):
        for name, text in self.pages.items():
            with self.subTest(page=name):
                self.assertEqual(
                    text, (v2.DIST_DIR / name).read_text(encoding="utf-8")
                )

    def test_every_page_is_ascii(self):
        for name, text in self.pages.items():
            with self.subTest(page=name):
                self.assertTrue(all(ord(ch) < 128 for ch in text))

    def test_the_chinese_page_is_chinese_and_points_at_its_twin(self):
        for case in self.cases:
            zh = self.pages[v6.link(case.case_no, v6.ZH)]
            en = self.pages[v6.link(case.case_no, v6.EN)]
            with self.subTest(case=case.case_no):
                self.assertIn('lang="zh-Hans"', zh)
                self.assertIn('href="{0}"'.format(v6.link(case.case_no, v6.EN)), zh)
                self.assertIn('href="{0}"'.format(v6.link(case.case_no, v6.ZH)), en)
                # The page's own headings are Chinese on the Chinese page.
                self.assertIn("\u600e\u4e48\u5224\u7684", visible(zh))
                self.assertNotIn("How it was decided.", visible(zh))

    def test_the_money_is_the_records_own(self):
        for case in self.cases:
            ruling = case.ruling
            value = str(ruling.get("ruling"))
            if case.trigger is not None:
                continue
            figure = (
                ruling.get("driver_compensation_sgd")
                if value == "DRIVER_COMPENSATION"
                else ruling.get("amount_sgd")
            )
            if figure is None:
                continue
            text = visible(self.pages[v6.link(case.case_no, v6.EN)])
            with self.subTest(case=case.case_no):
                self.assertIn(v6.money(figure), text)

    def test_no_vehicle_registration_comes_back(self):
        for name, text in self.pages.items():
            with self.subTest(page=name):
                self.assertEqual([], PLATE_RE.findall(visible(text)))

    def test_every_local_link_resolves(self):
        for name, text in self.pages.items():
            for href in HREF_RE.findall(text):
                if href.startswith(("http:", "https:", "mailto:", "data:")):
                    continue
                with self.subTest(page=name, href=href):
                    target = v2.DIST_DIR / href
                    written = href in self.pages
                    self.assertTrue(target.is_file() or written, href)


if __name__ == "__main__":
    unittest.main()
