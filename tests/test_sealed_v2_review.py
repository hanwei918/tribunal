"""The fourth sealed set's post-run review, and the sentences that said "pending".

``sealed-v2`` was run once, on 2026-10-11, and scored 12/12. Its manifest's
first release gate -- a case-by-case sign-off by the policy owner *before* the
run -- was not met, and the documents said so in the word "pending". Part 57
records the review made afterwards, and what the documents say now.

* **The review is committed as it was written, and the copy is proved.** The
  note at ``docs/notes/2026-10-13-sealed-v2-post-run-review.md`` is the
  reviewer's own text byte for byte, with one section appended after it. The
  note's own text is held to its sha256, so an edit inside it fails here rather
  than passing as a tidy copy, and the appended section is held to the facts it
  states.
* **No document still calls the sign-off pending.** The five documents part 57
  rewrites say what is now true instead, in one sentence, and the word
  "pending" is gone from all five.
* **The key the review read is unchanged.** A key corrected after the score is
  known would be a key fitted to the score, so the digest of
  ``eval/answers/sealed-v2/ground_truth.json`` is pinned here as well.

**The provenance note is checked differently, on purpose.** It is a dated note
(2026-10-12) whose body records what was true when it was written, so its
"the review is pending" sentences are left standing and part 57 gives it one
update line at the top instead. That line is what this module checks, and
rewriting the note in place would be a record of a different day.

**The pending check is shown capable of failing**, on a copy of one document
that still carries the sentence part 57 replaced, for the reason
``START-HERE.md`` gives: a guard nobody has seen fail is not evidence of
anything.

No model call is made and no network is reached: every reading is a committed
document, a committed key or a built page. Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# The review, and the section part 57 appends after the reviewer's own text.
NOTE = PROJECT_ROOT / "docs" / "notes" / "2026-10-13-sealed-v2-post-run-review.md"
NOTE_RELATIVE = "docs/notes/2026-10-13-sealed-v2-post-run-review.md"
APPENDED_HEADING = "## Adopted (2026-10-13)"
APPENDED_MARKER = "\n" + APPENDED_HEADING

# The reviewer's own note, as it was delivered. Everything before the marker
# above is that note, so the digest is taken over the text before the marker.
REVIEW_SHA256 = "29447cb2d6c52865c9c84c59518a31613446dec5636b3caf04e55559d0f8b6be"

# What the appended section states. Each is a phrase of it rather than the whole
# section, so the section may be re-wrapped without failing here.
ADOPTED_FACTS = (
    "adopted this review as her case-by-case",
    "sign-off on 2026-10-13, after the run",
    "which knew the 12/12 result",
    "does not meet the MANIFEST's",
    "pre-run release gate, and the key it reviewed is unchanged (sha256 above)",
)

# The key the review read, and the digest it must still have.
KEY = PROJECT_ROOT / "eval" / "answers" / "sealed-v2" / "ground_truth.json"
KEY_SHA256 = "d3a09c08f06c8eb328e251e618cba7b035fdb54c7614b041781fd6d564fe3e6f"

# The dated provenance note, and the one line part 57 adds at its top.
PROVENANCE_NOTE = PROJECT_ROOT / "docs" / "notes" / "2026-10-12-sealed-v2-provenance.md"
PROVENANCE_TITLE = "# The fourth sealed set's provenance, said exactly (2026-10-12)"
PROVENANCE_UPDATE = (
    "Update 2026-10-13: reviewed after the run and adopted by the policy owner "
    "-- see 2026-10-13-sealed-v2-post-run-review.md"
)

# What every place that said the sign-off was pending says instead, verbatim in
# both languages. The English stops at the sentence's last word so a place may
# end it its own way -- the record closes it with a full stop, the README's table
# cell with the cell, the questions with the two notes it cites -- and the
# Chinese is escaped so this module stays ASCII.
NEW_EN = (
    "Reviewed case by case after the run (2026-10-13) and adopted by the policy "
    "owner as her sign-off; the review was made with her AI assistant (Claude), "
    "which knew the 12/12 result. All 12 answers were found consistent with the "
    "version-6 policy, and none was changed. The pre-run sign-off the manifest "
    "asked for was not made"
)
NEW_ZH = (
    "\u8dd1\u5206\u540e\uff082026-10-13\uff09\u9010\u6848\u590d\u6838\uff0c"
    "\u5e76\u7531\u653f\u7b56\u8d1f\u8d23\u4eba\u8ba4\u53ef\u4e3a\u5979\u7684"
    "\u7b7e\u6838\uff1b\u590d\u6838\u501f\u52a9\u5979\u7684 AI \u52a9\u624b"
    "\uff08Claude\uff09\u5b8c\u6210\uff0c\u590d\u6838\u65f6\u5df2\u77e5\u9053 "
    "12/12 \u7684\u7ed3\u679c\u300212 \u4e2a\u7b54\u6848\u90fd\u4e0e\u7b2c 6 "
    "\u7248\u653f\u7b56\u4e00\u81f4\uff0c\u6ca1\u6709\u4efb\u4f55\u6539\u52a8"
    "\u3002\u6e05\u5355\u8981\u6c42\u7684\u8fd0\u884c\u524d\u7b7e\u6838"
    "\u6ca1\u6709\u505a\u5230\u3002"
)

# The five documents part 57 rewrites, and the sentence each no longer carries.
# Two documents carry the sentence twice, so a document may appear twice.
PENDING: Tuple[Tuple[str, str], ...] = (
    ("README.md", "the case-by-case sign-off is still pending"),
    ("docs/record.md", "the review is still pending"),
    (
        "docs/submission/qa.md",
        "the sign-off is still pending and will be made after the run if it is made",
    ),
    (
        "ui/site/src/pages/results.html",
        "Its case-by-case review before the run is still pending.",
    ),
    (
        "ui/site/src/pages/results.html",
        "its manifest's case-by-case sign-off before the run was not met and is pending.",
    ),
    (
        "ui/site/src/pages/results.zh.html",
        "\u5176\u8fd0\u884c\u524d\u7684\u9010\u9898\u5ba1\u6838\u4ecd\u5728"
        "\u8fdb\u884c\u3002",
    ),
    ("ui/site/src/pages/results.zh.html", "\u4ecd\u5f85\u5904\u7406"),
)

# The word a document may no longer use of this set's sign-off, in either
# language.
PENDING_WORDS = ("pending", "\u5f85\u5904\u7406")

# The documents that must carry the new sentence, by language.
ENGLISH_DOCUMENTS = (
    "README.md",
    "docs/record.md",
    "docs/submission/qa.md",
    "ui/site/src/pages/results.html",
)
CHINESE_DOCUMENTS = ("ui/site/src/pages/results.zh.html",)

# The built copies of the two results pages. Part 57 rebuilds the site, so the
# sentence must have reached the pages a reader is served and not only the
# sources it was written in.
BUILT_ENGLISH = "ui/dist/results.html"
BUILT_CHINESE = "ui/dist/results.zh.html"


# --------------------------------------------------------------------------
# Reading the documents
# --------------------------------------------------------------------------
def text_of(relative: str) -> str:
    """One repository-relative file, read as text."""
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def flat(text: str) -> str:
    """A document's text with every run of whitespace collapsed to one space.

    A sentence the markdown wraps is one sentence, so a check written against
    the unwrapped wording must not depend on where the line breaks fell.
    """
    return " ".join(text.split())


def digest_of(data: bytes) -> str:
    """The sha256 of some bytes, as the lower-case hex a manifest records."""
    return hashlib.sha256(data).hexdigest()


def the_documents() -> Dict[str, str]:
    """The five documents part 57 rewrites, read once, keyed by path."""
    return {relative: text_of(relative) for relative, _sentence in PENDING}


def still_pending(texts: Mapping[str, str]) -> List[Tuple[str, str]]:
    """The named sentences, of the documents given, that are still there.

    Takes the texts rather than reading them, so the control below can hand it
    a copy with one sentence put back.
    """
    return [
        (relative, sentence)
        for relative, sentence in PENDING
        if sentence in flat(texts[relative])
    ]


# --------------------------------------------------------------------------
# The note
# --------------------------------------------------------------------------
class TheNoteTests(unittest.TestCase):
    """The review, committed as written, with one section appended after it."""

    def test_the_note_exists(self):
        self.assertTrue(
            NOTE.is_file(), "{0} is missing".format(NOTE_RELATIVE)
        )

    def test_the_notes_own_text_is_the_text_that_was_reviewed(self):
        """The copy is proved rather than asserted: the digest is over it."""
        text = NOTE.read_text(encoding="utf-8")
        before, marker, _after = text.partition(APPENDED_MARKER)
        self.assertTrue(marker, "the appended section is not in the note")
        self.assertEqual(
            REVIEW_SHA256,
            digest_of(before.encode("utf-8")),
            "the note's own text is not the text that was reviewed",
        )

    def test_the_appended_section_is_there_and_states_its_facts(self):
        text = NOTE.read_text(encoding="utf-8")
        self.assertIn(APPENDED_HEADING, text)
        appended = text.partition(APPENDED_MARKER)[2]
        self.assertTrue(appended.strip(), "the appended section is empty")
        for fact in ADOPTED_FACTS:
            with self.subTest(fact=fact):
                self.assertIn(
                    fact,
                    flat(appended),
                    "the appended section does not state {0!r}".format(fact),
                )

    def test_the_section_is_appended_and_not_woven_into_the_note(self):
        """The section is after the note's last line, not inside its text."""
        text = NOTE.read_text(encoding="utf-8")
        before, marker, _after = text.partition(APPENDED_MARKER)
        self.assertTrue(marker, "the appended section is not in the note")
        self.assertTrue(before.startswith("# The fourth sealed set, reviewed"))
        self.assertNotIn(APPENDED_HEADING, before)
        self.assertTrue(
            before.endswith("against the key as imported.\n"),
            "the note's own text does not end where the reviewer left it",
        )


# --------------------------------------------------------------------------
# The sentences
# --------------------------------------------------------------------------
class TheSentencesTests(unittest.TestCase):
    """What the documents said, and what they say instead."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = the_documents()

    def test_no_document_still_says_the_sign_off_is_pending(self):
        self.assertEqual(
            [],
            still_pending(self.documents),
            "a document still carries a sentence part 57 replaced",
        )
        for relative, text in sorted(self.documents.items()):
            lowered = flat(text).lower()
            for word in PENDING_WORDS:
                with self.subTest(document=relative, word=word):
                    self.assertNotIn(
                        word,
                        lowered,
                        "{0} still says {1!r} of the sealed-v2 sign-off".format(
                            relative, word
                        ),
                    )

    def test_the_pending_check_is_shown_capable_of_failing(self):
        """The check above is against text that is there, not a blank."""
        relative, sentence = PENDING[0]
        self.assertNotIn(sentence, flat(self.documents[relative]))
        altered = dict(self.documents)
        altered[relative] = "The sentence it used to carry: {0}\n".format(sentence)
        self.assertEqual([(relative, sentence)], still_pending(altered))
        self.assertIn("pending", flat(altered[relative]).lower())

    def test_every_english_document_says_what_is_now_true(self):
        for relative in ENGLISH_DOCUMENTS:
            with self.subTest(document=relative):
                self.assertIn(
                    NEW_EN,
                    flat(self.documents[relative]),
                    "{0} does not carry the sentence that replaced it".format(relative),
                )

    def test_the_chinese_page_says_what_is_now_true_in_both_places(self):
        text = flat(self.documents[CHINESE_DOCUMENTS[0]])
        self.assertEqual(
            2,
            text.count(NEW_ZH),
            "the Chinese page states the new sentence in one place, not two",
        )

    def test_the_built_pages_carry_it_too(self):
        """Part 57 rebuilds the site, so the pages a reader is served carry it."""
        for relative, sentence in ((BUILT_ENGLISH, NEW_EN), (BUILT_CHINESE, NEW_ZH)):
            with self.subTest(page=relative):
                self.assertIn(
                    sentence,
                    flat(text_of(relative)),
                    "{0} is stale: rebuild with ui.site.build".format(relative),
                )

    def test_the_provenance_note_carries_the_update_line_at_its_top(self):
        """The dated note is left standing, and the line is where a reader starts."""
        lines = PROVENANCE_NOTE.read_text(encoding="utf-8").splitlines()
        self.assertEqual(PROVENANCE_TITLE, lines[0])
        after_title = [line for line in lines[1:] if line.strip()]
        self.assertTrue(after_title, "the note has nothing after its title")
        self.assertEqual(
            PROVENANCE_UPDATE,
            after_title[0],
            "the update line is not the first line of the note's text",
        )


# --------------------------------------------------------------------------
# The key
# --------------------------------------------------------------------------
class TheKeyTests(unittest.TestCase):
    """The key the review read, still the key the run was scored against."""

    def test_the_key_is_unchanged(self):
        self.assertTrue(KEY.is_file(), "the sealed-v2 key is missing")
        self.assertEqual(
            KEY_SHA256,
            digest_of(KEY.read_bytes()),
            "eval/answers/sealed-v2/ground_truth.json is not the key as imported",
        )


if __name__ == "__main__":
    unittest.main()
