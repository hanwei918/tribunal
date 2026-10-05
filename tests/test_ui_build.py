"""Tests for ``ui.build``: the debate viewer, and the artefact it commits.

No network, no browser, no credential. What is under test is not a behaviour of
the system so much as the two properties that make the viewer trustworthy:

* **A stored artefact must not be able to drift from the code that produces it.**
  The built page is committed, so a judge can open it without running Python.
  That is only safe if something goes red when the committed bytes stop being
  what the code produces, which is what the first test class is for.
* **The page must show the evidence the agents actually received.** A brief is
  rebuilt from the repository and checked against the digest the result recorded;
  a case whose digest does not match is refused rather than shown. A guard nobody
  has seen fail is not evidence of anything, so the refusal test also shows the
  case that *is* admitted.

Two things the tests deliberately do not do. They do not search the page for the
text ``http`` to prove it loads nothing external -- the agents' own explanations
discuss URLs as ordinary prose, and a substring search would either fail on
legitimate text or be weakened until it passed on anything. They parse the page
instead, and assert on the attributes and calls that would make a browser fetch
something. And they do not assert the headline figures against numbers typed in
here: the figures are recomputed from the run with ``eval.grade``, so the test
compares two computations rather than one computation against a memory.

One thing they do that they did not, and the reason is worth recording. The
page's script used to be read and never executed, and that is how a defect that
drew *nothing at all* reached a real browser: two panels answer "this run
recorded no data" with ``null``, and ``appendChild`` throws on anything that is
not a node, so the step they are appended to is lost from that point on. So no
function whose own body can answer ``null`` may be handed straight to
``appendChild``, and no string literal may be handed to it either -- both are
guards in ``ChildAdderTests``. **And the script is now executed.** There is
still no browser in the suite, but ``PageScriptRunsTests`` runs every page under
``ui/dist/`` against a minimal DOM in ``tests/support/dom_shim.js``, whose
``appendChild`` throws on a non-node exactly as a browser's does. Reading the
page cannot see this class of defect; running it can.

A third thing they do conditionally. The tests that read the committed run can
only run while that run and this code agree about what the agents were handed.
When every cached brief digest has moved they skip, naming the reason and the
command that clears it, rather than fail about a run that has not been re-made
yet. The tests that build their own run directory are unaffected and keep the
refusal mechanism itself under test.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import grade  # noqa: E402
from tribunal import brief  # noqa: E402
from tribunal import pipeline  # noqa: E402
from tribunal import transcript  # noqa: E402
from ui import build  # noqa: E402

# --------------------------------------------------------------------------
# Whether the committed run can be drawn at all
#
# The viewer rebuilds each case's brief and refuses a case whose rebuilt digest
# is not the digest its result recorded, rather than drawing a regenerated brief
# that merely resembles the one those agents were handed. When that is true of
# **every** cached case the run cannot be drawn: ``build.build_document`` refuses
# the whole run and raises, so the tests that read the committed run have nothing
# to read. Those tests say so and skip. The tests that build their own run
# directory keep running, so the refusal mechanism stays under test, and the skip
# is conditional on exactly this state, so it lifts on its own the moment the run
# is re-made.
# --------------------------------------------------------------------------
SKIP_REASON = (
    "the committed run and this code disagree about every case: every cached "
    "brief digest differs from the brief this code builds, so the viewer refuses "
    "the whole run and raises rather than draw regenerated briefs. The money "
    "facts added to the brief moved all 29 corpus briefs. Two commands clear it, "
    "after which this skip lifts with nothing unskipped by hand: "
    "`python3 -m eval.run_benchmark --force` for the corpus and "
    "`python3 -m eval.development_sets --set codex --force` for the second set, "
    "then `python -m ui.build` to rebuild the committed page."
)

_run_has_moved_on: Optional[bool] = None
_skip_reason_reported = False


def run_has_moved_on() -> bool:
    """Whether every cached case's brief has moved on from this code.

    Read from the run's own result files by ``ui.build``, and memoised: the
    answer cannot change while one test process runs.
    """
    global _run_has_moved_on
    if _run_has_moved_on is None:
        _run_has_moved_on = build.run_has_moved_on()
    return _run_has_moved_on


def skip_unless_the_run_can_be_drawn() -> None:
    """Skip, naming the state and the command that clears it, when it cannot.

    Conditional on exactly "every cached brief digest has moved", so a run this
    code agrees with runs every test as it did before, and a re-run clears the
    skip by itself. The reason is printed as well as raised, because a skipped
    test's reason is only shown by a verbose run and the quiet form is the one
    that gets pasted.
    """
    global _skip_reason_reported
    if not run_has_moved_on():
        return
    if not _skip_reason_reported:
        _skip_reason_reported = True
        print("\n{0}\n".format(SKIP_REASON), file=sys.stderr)
    raise unittest.SkipTest(SKIP_REASON)


def fixture_run_directory(root: Path, case_numbers: Sequence[int]) -> Path:
    """A small run directory, copied from the headline run and made current.

    Two cases rather than twenty-nine, so a refusal can be watched without
    rebuilding the whole corpus to move one digest.

    The copied results carry the digest of the brief *that* run's agents were
    handed, and this code's briefs have moved on. A fixture is not making a claim
    about the headline run -- it is a run directory in the shape the runner
    writes -- so the recorded digests are rewritten to the ones this code builds,
    which is what the runner would have recorded had it run now. Without that,
    every test using a fixture would inherit this session's brief change instead
    of testing the viewer.
    """
    run_dir = Path(root) / "run"
    run_dir.mkdir()
    for name in ("run.json", "invocations.json"):
        shutil.copy2(build.RUN_DIR / name, run_dir / name)
    for case_no in case_numbers:
        for suffix in (".json", ".transcript.json"):
            shutil.copy2(
                build.RUN_DIR / ("case-%05d%s" % (case_no, suffix)),
                run_dir / ("case-%05d%s" % (case_no, suffix)),
            )
    _make_the_fixture_current(run_dir, case_numbers)
    return run_dir


def _make_the_fixture_current(run_dir: Path, case_numbers: Sequence[int]) -> None:
    """Write this code's brief digest where the copied files recorded another.

    Both places the build compares it are written: the result's own
    ``brief_sha256``, and each advocate transcript entry's ``user_sha256``, which
    the stance proof checks against the same digest. The judge's entry is left
    alone -- its user prompt is the judge prompt, not the brief.
    """
    for case_no in case_numbers:
        digest = brief.brief_digest(brief.build_brief(case_no))[1]

        result_path = run_dir / ("case-%05d.json" % case_no)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["brief_sha256"] = digest
        result_path.write_text(json.dumps(result), encoding="utf-8")

        transcript_path = run_dir / ("case-%05d.transcript.json" % case_no)
        record = json.loads(transcript_path.read_text(encoding="utf-8"))
        for entry in record["entries"]:
            if entry.get("role") in (
                transcript.ROLE_RIDER_ADVOCATE,
                transcript.ROLE_DRIVER_ADVOCATE,
            ):
                entry["user_sha256"] = digest
        transcript_path.write_text(json.dumps(record), encoding="utf-8")

# The data block, by the id the page's own script reads it with. The match is
# non-greedy and the build escapes ``<`` inside the JSON, so the first
# ``</script>`` after the opening tag is the one that closes it.
_DATA_BLOCK_RE = re.compile(
    r'<script id="tribunal-data" type="application/json">(.*?)</script>', re.S
)

# The page's own stylesheet. Scoped separately because ``url(...)`` is a resource
# reference in a stylesheet and ordinary text anywhere else.
_STYLE_RE = re.compile(r"<style>(.*?)</style>", re.S)

# An API key as this project's provider writes one: ``sk-`` and at least eight
# identifier characters. The same shape ``runs/README.md`` requires a file to be
# checked against before it enters the run directory.
_API_KEY_RE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")

# The environment variables that hold a credential for this project. If one is
# set, its value must not appear in a published artefact either.
_CREDENTIAL_VARIABLES = ("TOKENHUB_API_KEY", "TOKENHUB_API_KEY_TEAMMATE")

# A limb suffix on a clause reference: POL-NS-06(i), POL-RD-06(c), POL-NS-05(ii).
_LIMB_RE = re.compile(r"\s*\([^)]*\)\s*$")


def embedded_document(page: str) -> dict:
    """The document the page carries, parsed out of its data block."""
    match = _DATA_BLOCK_RE.search(page)
    if match is None:
        raise AssertionError("the page carries no tribunal-data block")
    return json.loads(match.group(1))


class _ResourceScan(HTMLParser):
    """Every attribute that names a resource, and every script body.

    ``srcset`` is a comma-separated candidate list, so its value is split rather
    than treated as one URL. ``style`` attributes and stylesheets are not
    scanned: a ``url(...)`` in a stylesheet is a resource, but this page has no
    stylesheet other than its own inline one and no ``url(`` in it, and the
    assertion below covers that directly.
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

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list = []
        self.script_bodies: list = []
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name not in self.RESOURCE_ATTRIBUTES:
                continue
            text = value or ""
            if name == "srcset":
                for candidate in text.split(","):
                    parts = candidate.strip().split()
                    if parts:
                        self.references.append((tag, name, parts[0]))
            else:
                self.references.append((tag, name, text))
        if tag == "script":
            self._in_script = True

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_script:
            self.script_bodies.append(data)


def is_external_reference(url: str) -> bool:
    """Whether a URL would make the browser fetch something off the page.

    A fragment is not a fetch, a relative path is served from the same place the
    page came from, and a ``data:`` URI is carried by the page itself. Anything
    with another scheme -- ``http``, ``https``, ``file``, a protocol-relative
    ``//host`` -- is external, and so is anything that names a host.
    """
    text = url.strip()
    if not text:
        return False
    if text.startswith("#"):
        return False
    if text.startswith("//"):
        return True
    scheme = re.match(r"^([A-Za-z][A-Za-z0-9+.\-]*):", text)
    if scheme is not None:
        return scheme.group(1).lower() != "data"
    return False


class RunCurrencyTests(unittest.TestCase):
    """The committed run is either drawable, or refused whole and said so.

    This is the guard that stops a page being drawn from a run this code
    disagrees with, asserted positively while the state exists rather than only
    skipped around. It holds on both sides of a re-run: while the run is current
    there is nothing to refuse and the test skips, and while every cached brief
    has moved the build must refuse the run whole and say why.
    """

    def test_a_run_whose_briefs_have_all_moved_on_is_refused_whole(self):
        if not run_has_moved_on():
            self.skipTest("the committed run is current; there is nothing to refuse")

        with self.assertRaises(build.BuildError) as caught:
            build.build_document()

        self.assertIn("every cached case was refused", str(caught.exception))
        self.assertEqual(
            [],
            build.cases_whose_briefs_match(),
            "a case still matches, so the whole-run refusal is not the whole truth",
        )


class CommittedPageTests(unittest.TestCase):
    """The committed page is the one this code builds, and it is one file."""

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.document = build.build_document()
        cls.page = build.render_html(cls.document)

    def test_the_committed_page_equals_a_fresh_build(self):
        """A stored artefact that can drift from its code is a lie waiting to happen.

        The failure message names the command that fixes it, because the fix is
        never to edit the committed file.
        """
        self.assertTrue(
            build.OUTPUT_PATH.is_file(),
            "ui/dist/index.html is not committed; run `python -m ui.build`",
        )
        committed = build.OUTPUT_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            self.page,
            committed,
            "ui/dist/index.html differs from a fresh build; run `python -m ui.build`",
        )

    def test_two_builds_are_byte_identical(self):
        first = build.render_html(build.build_document())
        second = build.render_html(build.build_document())
        self.assertEqual(first, second, "the build is not deterministic")

    def test_the_page_does_not_depend_on_where_the_run_was_made(self):
        """The strongest form of the checkout-independence property.

        The run is copied to a temporary directory laid out the way a fresh
        clone's is -- ``<tmp>/runs/deepseek-deepseek-flash`` -- and its recorded
        prompts path is moved somewhere that does not exist on this machine. The
        page built from that copy must be byte-identical to the committed one,
        because the page is meant to be a function of the repository alone.

        A fresh clone broke exactly this. The run records its prompts directory
        as an absolute path from the machine that produced it; in the author's
        checkout that path sits under the project root and was relativised, and
        in any other checkout it did not, so the absolute path was published
        instead. Both ``test_the_committed_page_equals_a_fresh_build`` and
        ``test_no_absolute_path_is_published`` went red in the clone.
        """
        with tempfile.TemporaryDirectory() as tmp:
            moved_run = Path(tmp) / "runs" / "deepseek-deepseek-flash"
            moved_run.parent.mkdir(parents=True)
            shutil.copytree(build.RUN_DIR, moved_run)

            run_json = moved_run / "run.json"
            recorded = json.loads(run_json.read_text(encoding="utf-8"))
            recorded["prompts_dir"] = "/somewhere/else/entirely/prompts/v1"
            run_json.write_text(json.dumps(recorded), encoding="utf-8")

            moved = build.render_html(build.build_document(run_dir=moved_run))

        self.assertEqual(
            self.page,
            moved,
            "the page depends on where the run was made, so it cannot be "
            "reproduced from the code by anyone else",
        )

    def test_the_page_carries_its_data_css_and_javascript_inline(self):
        """One file, and everything it needs is in it."""
        self.assertIn("<style>", self.page)
        self.assertNotIn("<link", self.page)
        scan = _ResourceScan()
        scan.feed(self.page)
        self.assertTrue(scan.script_bodies, "the page carries no inline script")
        self.assertEqual(
            [],
            [reference for reference in scan.references if reference[1] == "src"],
            "the page names an external src",
        )
        self.assertIsInstance(embedded_document(self.page), dict)

    def test_the_page_loads_no_external_resource(self):
        """Asserted by parsing, not by looking for the text 'http'.

        A substring search for ``http`` would trip on the agents' own prose,
        which discusses URLs legitimately, and the honest response to that is to
        assert on the structure rather than to weaken the search.
        """
        scan = _ResourceScan()
        scan.feed(self.page)

        external = [
            (tag, name, url)
            for tag, name, url in scan.references
            if is_external_reference(url)
        ]
        self.assertEqual([], external, "the page references an external resource")

        script = "\n".join(scan.script_bodies)
        for call in ("fetch(", "XMLHttpRequest", "importScripts(", "new Worker(",
                     "new EventSource(", "new WebSocket("):
            self.assertNotIn(call, script, "the page fetches at runtime: {0}".format(call))

        # The stylesheet is the one place a ``url(...)`` would be a resource
        # rather than prose, so that check is scoped to it. Asserting its
        # absence from the whole file would be the substring search this test
        # exists to avoid: the agents' own text is not ours to constrain.
        style = _STYLE_RE.search(self.page)
        self.assertIsNotNone(style, "the page carries no inline stylesheet")
        self.assertNotIn("url(", style.group(1), "the page's CSS names a resource")
        for tag in ("<iframe", "<object", "<embed", "<link"):
            self.assertNotIn(tag, self.page, "the page embeds something: {0}".format(tag))

    def test_the_scan_is_capable_of_firing(self):
        """A guard nobody has seen fail is not evidence of anything.

        The same scan is pointed at a page that does reference external things,
        including the two cases a naive check would miss: a protocol-relative
        host, and a ``data:`` URI that is legitimately not external.
        """
        scan = _ResourceScan()
        scan.feed(
            '<link rel="stylesheet" href="https://cdn.example/x.css">'
            '<script src="//cdn.example/x.js"></script>'
            '<img src="data:image/gif;base64,R0lGOD">'
            '<script>fetch("/x"); new XMLHttpRequest();</script>'
        )
        external = sorted(
            url for _, _, url in scan.references if is_external_reference(url)
        )
        self.assertEqual(
            ["//cdn.example/x.js", "https://cdn.example/x.css"], external
        )
        script = "\n".join(scan.script_bodies)
        self.assertIn("fetch(", script)
        self.assertIn("XMLHttpRequest", script)

    def test_the_output_carries_no_api_key(self):
        """The repository goes public before submission, so this is a publication check."""
        found = _API_KEY_RE.findall(self.page)
        self.assertEqual([], found, "the page carries what looks like an API key")

        for name in _CREDENTIAL_VARIABLES:
            value = os.environ.get(name)
            if value:
                with self.subTest(variable=name):
                    self.assertNotIn(value, self.page)

    def test_the_page_opens_on_the_demonstration_case(self):
        self.assertEqual(208, self.document["default_case"])
        self.assertIn(208, [case["case_no"] for case in self.document["cases"]])


class TheRunTests(unittest.TestCase):
    """What the viewer shows about the run, asserted on the parsed document."""

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.document = build.build_document()
        cls.cases = {case["case_no"]: case for case in cls.document["cases"]}

    def test_every_case_in_the_run_is_either_shown_or_refused(self):
        """No cached case is dropped silently, and none is refused for nothing.

        A case is refused when the brief this code builds for it is not the brief
        those agents were handed, and the build reports the refusal rather than
        swallowing it. That is the state of the four cases whose fare breakdown
        carries an ERP gantry line, until they are re-run. The assertion below is
        written against the digests rather than against a list typed in here, so
        it holds on both sides of that re-run -- and it still fails a builder
        that refused a case whose brief did not move.
        """
        numbers = build.cached_cases(build.RUN_DIR)
        self.assertEqual(29, len(numbers), "the headline run holds 29 cases")

        shown = sorted(self.cases)
        refused = sorted(entry["case_no"] for entry in self.document["refused_cases"])
        self.assertEqual(numbers, sorted(shown + refused), "a cached case is missing")
        self.assertEqual([], sorted(set(shown) & set(refused)), "shown and refused")

        moved = sorted(
            case_no
            for case_no in numbers
            if json.loads(
                (build.RUN_DIR / ("case-%05d.json" % case_no)).read_text(encoding="utf-8")
            ).get("brief_sha256")
            != brief.brief_digest(brief.build_brief(case_no))[1]
        )
        self.assertEqual(moved, refused, "a case is refused for something other than its brief")

    def test_every_case_carries_the_evidence_it_was_graded_on(self):
        for case_no, case in sorted(self.cases.items()):
            with self.subTest(case=case_no):
                self.assertTrue(case["evidence"], "no evidence carried")
                self.assertEqual(
                    case["brief_sha256"],
                    case["brief_rebuilt_sha256"],
                    "a case is shown whose brief this code did not rebuild identically",
                )
                for artifact in case["evidence"]:
                    self.assertIn("evidence_id", artifact)
                    self.assertIn("evidence_type", artifact)
                    self.assertIn(
                        artifact["admissibility"]["status"],
                        ("COMPLETE", "IMPAIRED", "MISSING"),
                    )
                    self.assertIn("weight_multiplier", artifact["admissibility"])
                    self.assertIn("issues", artifact["admissibility"])

    def test_the_misses_are_shown_as_misses(self):
        """Which cases miss is dated; that every miss is carried as one is not.

        Which cases miss is a fact about the run committed under ``runs/``, and
        the next run moves it: the run before the frozen-prompt run missed 107
        and 211, the frozen-prompt run missed 105 and 211, the referee run missed
        211 alone, and the 2026-09-27 re-run under digest ``83a74310`` misses
        none -- 29 of 29 on all four fields. So the assertion below compares the
        page's miss set with the grader's own, recomputed from the run, rather
        than with a list typed in here, and it holds whether the run misses
        nothing or misses several.

        What is not dated is the rest: that each case carries its expected
        ruling, the ruling the judge produced and the fields that differ, which
        is what makes a miss legible on the page rather than merely counted.
        That legibility is asserted for **every** case rather than for the
        misses, so it cannot pass by having nothing to check.
        """
        produced = {
            case_no: json.loads(
                (build.RUN_DIR / ("case-%05d.json" % case_no)).read_text(encoding="utf-8")
            )["ruling"]
            for case_no in build.cached_cases(build.RUN_DIR)
        }
        report = grade.grade(produced)

        misses = sorted(
            case_no for case_no, case in self.cases.items() if not case["grading"]["exact"]
        )
        self.assertEqual(
            sorted(score.case_no for score in report.failures),
            misses,
            "the page's misses are not the grader's",
        )

        # The legibility of every case, recomputed: the key's ruling, the ruling
        # the judge produced, and the fields that differ.
        self.assertEqual(sorted(report.graded_cases), sorted(self.cases))
        for score in report.cases:
            case = self.cases[score.case_no]
            with self.subTest(case=score.case_no):
                self.assertEqual(score.expected.ruling, case["expected"]["ruling"])
                self.assertEqual(
                    score.produced.ruling, case["judge"]["verdict"]["ruling"]
                )
                self.assertEqual(
                    list(score.failed_fields), case["grading"]["failed_fields"]
                )

        self.assertIn("decision_note", self.document)
        self.assertTrue(
            self.document["decision_note_link"].endswith(self.document["decision_note"]),
            "the miss does not link to the note that records why it is contested",
        )

    def test_every_claim_carries_a_citation_the_viewer_can_open(self):
        """'No citation, no claim' is only visible if every chip resolves.

        A claim that cites an artifact the brief does not carry, or a clause the
        loaded policy does not define, is a chip the viewer cannot open -- so the
        viewer says so rather than drawing a chip that looks like the others.
        This asserts that on this run there is nothing of the kind, which is what
        makes the chips on screen mean what they say.
        """
        clause_ids = set()
        for block in self.document["policies"].values():
            for which in ("general", "category"):
                for clause in block[which].get("clauses", []):
                    clause_ids.add(clause["id"])

        claims = 0
        for case_no, case in sorted(self.cases.items()):
            known = {artifact["evidence_id"] for artifact in case["evidence"]}
            for role, advocate in sorted(case["advocates"].items()):
                for claim in advocate["claims"]:
                    claims += 1
                    with self.subTest(case=case_no, role=role):
                        self.assertTrue(claim["evidence_ids"], "a claim cites no evidence")
                        self.assertTrue(claim["clause_ids"], "a claim cites no clause")
                        for evidence_id in claim["evidence_ids"]:
                            self.assertIn(evidence_id, known)
                        for clause_id in claim["clause_ids"]:
                            self.assertIn(_LIMB_RE.sub("", clause_id), clause_ids)
        # The count is a property of the cases on the page rather than a figure
        # typed in here. A case whose brief has moved is refused, and pinning
        # the run's total would make that refusal look like a missing claim.
        # What must hold either way is that both advocates of every admitted
        # case spoke, and that the loop above counted something.
        self.assertEqual(
            len(self.cases),
            sum(
                1
                for case in self.cases.values()
                if all(advocate["claims"] for advocate in case["advocates"].values())
            ),
            "an admitted case carried no claim from one of its advocates",
        )
        self.assertGreater(claims, 0, "no claim reached the page")

    def test_the_referee_ledger_covers_the_claims_and_discards_are_copied(self):
        """The page exposes the mechanical ledger before the judge's ruling."""
        for case_no, case in sorted(self.cases.items()):
            with self.subTest(case=case_no):
                ledger = case["referee"]["ledger"]
                claim_count = sum(
                    len(advocate["claims"])
                    for advocate in case["advocates"].values()
                )
                self.assertEqual(claim_count, len(ledger))
                self.assertTrue(all(entry["status"] in ("KEPT", "DISCARDED") for entry in ledger))
                self.assertEqual(
                    case["referee"]["discards"],
                    [
                        {
                            "side": entry["side"],
                            "claim": entry["claim"],
                            "reason_code": entry["reason_code"],
                            "detail": entry["detail"],
                        }
                        for entry in ledger
                        if entry["status"] == "DISCARDED"
                    ],
                )

    def test_money_is_carried_as_its_own_decimal_literal(self):
        """A key value of 4.8 must not reach the page as 4.800000000000001.

        The pipeline keeps amounts in ``Decimal``; the page shows the literal.
        Every money value in the document is therefore a string, and the check is
        structural -- the type of the value, not its characters.
        """
        for case_no, case in sorted(self.cases.items()):
            for field in ("amount_sgd", "driver_compensation_sgd"):
                with self.subTest(case=case_no, field=field):
                    self.assertIsInstance(case["expected"][field], str)
                    self.assertIsInstance(case["judge"]["verdict"][field], str)
                    self.assertIsInstance(case["dispute"]["amount_contested_sgd"], str)
                    for artifact in case["evidence"]:
                        self.assertIsInstance(
                            artifact["admissibility"]["weight_multiplier"], str
                        )


class JudgeVoteTests(unittest.TestCase):
    """The vote the judge's drafts took, shown from the run's own record.

    A case's result object looks the same whether four drafts agreed or only
    two did, so the page has to carry the vote itself or a reader cannot tell a
    unanimous ruling from a contested one. These tests read the vote out of the
    transcripts the run wrote and require the page to carry exactly that: the
    drafts, how each was drawn, how each voted, and the outcome.

    Nothing here re-derives a vote. That is the point of the class: a page that
    recomputed the vote could agree with itself while disagreeing with the run,
    and the two would then be indistinguishable from the page alone.
    """

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.document = build.build_document()
        cls.cases = {case["case_no"]: case for case in cls.document["cases"]}
        cls.page = build.render_html(cls.document)
        cls.script = behaviour_script(cls.page)
        cls.stylesheet = "\n".join(_STYLE_RE.findall(cls.page))

    def recorded_vote(self, case_no: int) -> dict:
        """The vote as the run wrote it, read the way the builder reads it.

        ``parse_float=Decimal`` matters here. The document turns a ``Decimal``
        into its literal, so reading the transcript with the default float hook
        would compare a page literal against a binary approximation of it and
        the comparison would be about the reader rather than about the page.
        """
        path = build.RUN_DIR / ("case-%05d.transcript.json" % case_no)
        return build._read_json(path)["vote"]

    def test_every_case_carries_the_vote_the_run_recorded(self):
        """Draft by draft: kind, seed, temperature, proposal and verdict."""
        drafts_seen = 0
        for case_no, case in sorted(self.cases.items()):
            with self.subTest(case=case_no):
                vote = case["vote"]
                self.assertIsNotNone(vote, "an admitted case carries no vote")
                written = self.recorded_vote(case_no)
                for field in ("votes", "threshold", "valid", "outcome", "unanimous"):
                    self.assertEqual(written[field], vote[field], field)
                # A float is carried as its literal, which is what the page
                # shows; the value is still the run's own number.
                self.assertEqual(str(written["agreement"]), vote["agreement"])
                self.assertEqual(len(written["drafts"]), len(vote["drafts"]))
                for source, shown in zip(written["drafts"], vote["drafts"]):
                    for field in ("draft", "kind", "seed"):
                        self.assertEqual(source[field], shown[field], field)
                    self.assertEqual(str(source["temperature"]), shown["temperature"])
                    self.assertEqual(
                        build._normalise(source["proposal"]), shown["proposal"]
                    )
                    # The verdict is the run's own two booleans, not a second
                    # judgement made on the page about what agreeing means.
                    self.assertEqual(
                        "abstained"
                        if not source["valid"]
                        else ("agreed" if source["agrees"] else "dissented"),
                        shown["verdict"],
                    )
                    drafts_seen += 1
        self.assertGreater(drafts_seen, 0, "no draft reached the page")

    def test_the_agreeing_count_is_the_drafts_that_agreed(self):
        for case_no, case in sorted(self.cases.items()):
            vote = case["vote"]
            with self.subTest(case=case_no):
                self.assertEqual(vote["votes"], len(vote["drafts"]))
                self.assertEqual(
                    sum(1 for draft in vote["drafts"] if draft["verdict"] == "agreed"),
                    vote["agreeing"],
                )

    def test_the_two_records_of_the_agreement_are_the_same_number(self):
        """The cache records vote_agreement; the transcript records the vote.

        Both are this run's own files. A page that read one of them and a reader
        who read the other must not be told different numbers.
        """
        for case_no, case in sorted(self.cases.items()):
            record = build._read_json(build.RUN_DIR / ("case-%05d.json" % case_no))
            with self.subTest(case=case_no):
                self.assertIn("vote_agreement", record)
                self.assertEqual(str(record["vote_agreement"]), case["vote"]["agreement"])

    def test_unanimous_is_the_carried_outcome_and_nothing_else(self):
        """The page cannot call a split vote unanimous, or a full house split."""
        for case_no, case in sorted(self.cases.items()):
            vote = case["vote"]
            with self.subTest(case=case_no):
                self.assertEqual(vote["unanimous"], vote["outcome"] == pipeline.VOTE_CARRIED)
                self.assertEqual(
                    vote["agreeing"] == vote["votes"],
                    vote["unanimous"],
                    "the run called a vote unanimous for something other than a full house",
                )

    def test_no_outcome_reaches_the_page_without_a_rule_for_it(self):
        outcomes = {case["vote"]["outcome"] for case in self.cases.values()}
        self.assertTrue(outcomes, "no vote reached the page")
        self.assertLessEqual(
            outcomes,
            {pipeline.VOTE_CARRIED, pipeline.VOTE_CARRIED_NOT_UNANIMOUS, pipeline.VOTE_ESCALATED},
            "the run recorded an outcome the viewer's stylesheet has no rule for",
        )

    def test_the_stylesheet_colours_every_outcome(self):
        """Three outcomes, three colours, named by the outcome string itself.

        The class is the outcome the run recorded rather than a synonym picked
        on the page, so this assertion is what stops the two drifting apart.
        """
        for outcome in (
            pipeline.VOTE_CARRIED,
            pipeline.VOTE_CARRIED_NOT_UNANIMOUS,
            pipeline.VOTE_ESCALATED,
        ):
            with self.subTest(outcome=outcome):
                self.assertIn(".vote-result." + outcome + " {", self.stylesheet)

    def test_the_contested_cases_are_the_ones_the_run_marked(self):
        """Which cases those are is dated; that the page follows the run is not.

        The run committed under ``runs/`` now contests 105, 107, 207 and 211 --
        three at 3 of 4 and 211 at 2 of 4 -- where the voting run before it
        contested only 107, 207 and 211. A dated list here is red on one side of
        every re-run, so there is none. What is asserted instead is the check
        above it -- a case is contested on the page exactly when the run's own
        record says its vote was not unanimous -- plus the two facts that hold of
        any run: that it records at least one contested case, and that a
        contested case is one the run recorded an agreement below 1 for. The
        agreement is read from the run's own transcript through
        ``recorded_vote``, because the page carries the figure as its literal.
        """
        contested = sorted(
            case_no
            for case_no, case in self.cases.items()
            if case["vote"]["unanimous"] is False
        )
        for case_no, case in sorted(self.cases.items()):
            with self.subTest(case=case_no):
                self.assertEqual(
                    not case["vote"]["unanimous"],
                    case_no in contested,
                    "a case is contested for something other than its own vote",
                )
        self.assertTrue(contested, "the run records no contested case at all")
        for case_no in sorted(self.cases):
            with self.subTest(case=case_no):
                self.assertEqual(
                    self.recorded_vote(case_no)["agreement"] < 1,
                    case_no in contested,
                    "a case is contested for something other than its agreement",
                )

    def test_the_drafts_and_the_result_reach_the_page(self):
        """An honest name for a weak check, in the manner of the key test.

        The document carries the vote and the stylesheet colours it; this
        asserts only that the two render paths are wired to that payload -- the
        judge step calls the vote panel, the overview calls the summary, and
        both read the run's own field names. It cannot tell you the panel draws
        anything. What it draws was checked from the built page, and that check
        is recorded in ``docs/notes/2026-09-26-the-voting-run.md``.
        """
        self.assertIn("votePanel(caseDoc)", self.script)
        self.assertIn("voteSummary()", self.script)
        # The panel reads the counts, not the fraction. ``vote.agreement`` is a
        # rounded number the run records, and it stays in the data -- the test
        # above compares it against the run's own record -- but no render path
        # is handed the fraction to draw any more, so it is no longer a name
        # the script reads. ``vote.valid`` is what the panel counts from.
        for field in ("vote.drafts", "vote.valid", "vote.outcome", "vote.unanimous"):
            with self.subTest(field=field):
                self.assertIn(field, self.script)

    def test_a_case_with_no_vote_yields_no_vote_rather_than_a_blank_one(self):
        """A single judge call records no vote; the page must not invent one.

        Every case in this run was decided by four drafts, so this branch is
        exercised directly rather than through the run.
        """
        self.assertIsNone(build._vote_payload(None))
        self.assertIsNone(build._vote_payload("not a vote"))

    def test_an_unusable_draft_is_shown_as_abstaining(self):
        """A draft that could not be parsed votes for nothing, and says so.

        Also a branch this run does not reach: no draft here abstained, so the
        record for one is built by hand.
        """
        raw = {
            "votes": 2,
            "threshold": 2,
            "valid": 1,
            "agreement": 1.0,
            "outcome": pipeline.VOTE_CARRIED,
            "unanimous": True,
            "drafts": [
                {
                    "draft": 1,
                    "kind": "sampled",
                    "seed": 101,
                    "temperature": 0.7,
                    "valid": True,
                    "agrees": True,
                    "abstention": None,
                    "proposal": {
                        "ruling": "ESCALATE",
                        "amount_sgd": None,
                        "driver_compensation_sgd": None,
                        "referrals": [],
                    },
                },
                {
                    "draft": 2,
                    "kind": "sampled",
                    "seed": 202,
                    "temperature": 0.7,
                    "valid": False,
                    "agrees": False,
                    "abstention": "malformed answer",
                    "proposal": None,
                },
            ],
        }
        payload = build._vote_payload(raw)
        self.assertEqual(
            ["agreed", "abstained"], [draft["verdict"] for draft in payload["drafts"]]
        )
        self.assertEqual(1, payload["agreeing"])
        self.assertEqual("malformed answer", payload["drafts"][1]["abstention"])


class HeadlineTests(unittest.TestCase):
    """The figures are computed, and they are the grader's own figures."""

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.document = build.build_document()
        cls.page = build.render_html(cls.document)

    def test_the_headline_numbers_are_the_ones_the_grader_computes(self):
        """Recomputed from the run, so the test compares two computations."""
        produced = {}
        for case_no in build.cached_cases(build.RUN_DIR):
            result = json.loads(
                (build.RUN_DIR / ("case-%05d.json" % case_no)).read_text(encoding="utf-8")
            )
            if "ruling" in result:
                produced[case_no] = result["ruling"]
        report = grade.grade(produced)
        headline = self.document["headline"]

        self.assertEqual(report.total, headline["cases_graded"])
        self.assertEqual(report.exact_matches, headline["exact"]["matched"])
        self.assertEqual(report.total, headline["exact"]["total"])

        for name in grade.GRADED_FIELDS:
            correct, denominator = report.field_tally(name)
            with self.subTest(field=name):
                self.assertEqual(correct, headline["fields"][name]["matched"])
                self.assertEqual(denominator, headline["fields"][name]["total"])

        calibration = report.calibration
        escalation = headline["escalation"]
        self.assertEqual(len(calibration.expected_escalations), escalation["expected"])
        self.assertEqual(len(calibration.produced_escalations), escalation["produced"])
        self.assertEqual(len(calibration.true_positives), escalation["recall"]["matched"])
        self.assertEqual(
            len(calibration.true_positives) + len(calibration.false_negatives),
            escalation["recall"]["total"],
        )
        self.assertEqual(len(calibration.true_positives), escalation["precision"]["matched"])
        self.assertEqual(
            len(calibration.true_positives) + len(calibration.false_positives),
            escalation["precision"]["total"],
        )
        self.assertEqual(
            sorted(calibration.over_escalations), sorted(escalation["over_escalations"])
        )
        self.assertEqual(
            sorted(calibration.under_escalations), sorted(escalation["under_escalations"])
        )
        self.assertEqual(calibration.rate_off_target, escalation["off_target"])

    def test_the_discarded_claim_total_is_summed_from_the_run(self):
        """The one figure the grader does not compute, recomputed here."""
        total = 0
        per_case = {}
        for case_no in build.cached_cases(build.RUN_DIR):
            result = json.loads(
                (build.RUN_DIR / ("case-%05d.json" % case_no)).read_text(encoding="utf-8")
            )
            discarded = (result.get("ruling") or {}).get("discarded_claims") or []
            per_case[str(case_no)] = len(discarded)
            total += len(discarded)

        self.assertEqual(total, self.document["headline"]["discarded_claims"]["total"])
        self.assertEqual(
            per_case, self.document["headline"]["discarded_claims"]["per_case"]
        )
        # The total belongs to this invocation's recorded judge outputs. It is
        # deliberately not pinned to a number, because a rerun can change it.

    def test_the_seconds_and_tokens_are_summed_from_the_run(self):
        seconds = []
        tokens = []
        for case_no in build.cached_cases(build.RUN_DIR):
            result = json.loads(
                (build.RUN_DIR / ("case-%05d.json" % case_no)).read_text(encoding="utf-8")
            )
            seconds.append(float(result["wall_seconds"]))
            tokens.append(int(result["tokens"]["total_tokens"]))

        headline = self.document["headline"]
        self.assertEqual(len(seconds), headline["seconds"]["cases"])
        self.assertEqual(sum(tokens), headline["tokens"]["total"])
        self.assertEqual(len(tokens), headline["tokens"]["cases"])
        self.assertAlmostEqual(
            sum(tokens) / len(tokens), headline["tokens"]["mean_per_case"], places=1
        )

    def test_the_figures_reach_the_page(self):
        """A number computed and not rendered is not on the page."""
        for display in (
            self.document["headline"]["exact"]["display"],
            self.document["headline"]["escalation"]["rate_percent"],
        ):
            self.assertIn(display, self.page)
        self.assertIn(
            str(self.document["headline"]["discarded_claims"]["total"]), self.page
        )


class RefusalTests(unittest.TestCase):
    """A brief that cannot be verified is refused, and said so."""

    # The case whose brief the fixture deliberately alters, and the case beside
    # it that must still be admitted -- without which a builder that refused
    # everything would pass.
    ALTERED = 208
    ADMITTED = 209

    def _fixture_run_directory(self, root: Path) -> Path:
        """A two-case run directory, copied from the headline run.

        Two cases rather than twenty-nine, so the refusal can be shown without
        rebuilding the whole corpus to watch one digest move.
        """
        # Made current rather than inherited: see ``fixture_run_directory`` for
        # why a fixture rewrites the copied digests instead of carrying the
        # headline run's.
        return fixture_run_directory(root, (self.ALTERED, self.ADMITTED))

    @staticmethod
    def _altering_builder(case_no: int, altered: int):
        """The real builder, with one case's claim text changed.

        The alteration is to the case's own content, which is what a moved brief
        means: the facts the agents were handed are not the facts this code
        builds now.
        """
        built = brief.build_brief(case_no)
        if case_no == altered:
            dispute = built["case"]["dispute"]
            dispute["claim_text"] = dispute["claim_text"] + " [altered by the test]"
        return built

    def test_a_case_whose_brief_does_not_match_is_refused_rather_than_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._fixture_run_directory(Path(tmp))
            document = build.build_document(
                run_dir=run_dir,
                brief_builder=lambda case_no: self._altering_builder(
                    case_no, self.ALTERED
                ),
            )

        shown = [case["case_no"] for case in document["cases"]]
        self.assertEqual(
            [self.ADMITTED],
            shown,
            "the case whose brief was altered is still being shown",
        )

        refused = document["refused_cases"]
        self.assertEqual(1, len(refused), "the refusal was not reported")
        entry = refused[0]
        self.assertEqual(self.ALTERED, entry["case_no"])
        self.assertNotEqual(
            entry["recorded_brief_sha256"],
            entry["rebuilt_brief_sha256"],
            "the refusal does not say which two digests disagree",
        )
        self.assertTrue(entry["reason"])

    def test_the_refused_case_is_not_on_the_page(self):
        """Refused means not shown, and the evidence it would have shown is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._fixture_run_directory(Path(tmp))
            document = build.build_document(
                run_dir=run_dir,
                brief_builder=lambda case_no: self._altering_builder(
                    case_no, self.ALTERED
                ),
            )
        page = build.render_html(document)

        self.assertNotIn("[altered by the test]", page)
        self.assertEqual([self.ADMITTED], [case["case_no"] for case in document["cases"]])
        self.assertEqual(1, len(document["refused_cases"]))

    def test_a_brief_that_cannot_be_built_at_all_is_refused_too(self):
        """"Cannot build it" is not "it matches", the same rule the runner applies."""

        def exploding_builder(case_no):
            if case_no == self.ALTERED:
                raise RuntimeError("no such case file")
            return brief.build_brief(case_no)

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._fixture_run_directory(Path(tmp))
            document = build.build_document(
                run_dir=run_dir, brief_builder=exploding_builder
            )

        self.assertEqual([self.ADMITTED], [case["case_no"] for case in document["cases"]])
        self.assertEqual(1, len(document["refused_cases"]))
        self.assertIsNone(document["refused_cases"][0]["rebuilt_brief_sha256"])
        self.assertIn("RuntimeError", document["refused_cases"][0]["reason"])


class ProvenanceTests(unittest.TestCase):
    """A reader must always be able to see which run they are looking at."""

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.document = build.build_document()
        cls.provenance = cls.document["provenance"]
        cls.page = build.render_html(cls.document)

    def test_the_footer_carries_everything_it_should(self):
        for field in (
            "model",
            "git_commit",
            "prompts_sha256",
            "answer_key_sha256",
            "python_version",
            "started_at",
            "ended_at",
        ):
            with self.subTest(field=field):
                self.assertTrue(self.provenance.get(field), "provenance has no " + field)

    def test_the_model_is_the_one_the_runtime_decides(self):
        from tribunal import model

        self.assertEqual(model.RUNTIME_MODEL, self.provenance["runtime_model"])
        self.assertEqual(model.RUNTIME_MODEL, self.provenance["model"])

    def test_the_answer_key_digest_is_the_key_on_disk(self):
        self.assertEqual(
            grade.answer_key_sha256(), self.provenance["answer_key_sha256"]
        )

    def test_the_provenance_reaches_the_footer(self):
        for value in (
            self.provenance["git_commit"],
            self.provenance["answer_key_sha256"],
            self.provenance["started_at"],
        ):
            self.assertIn(value, self.page)

    def test_no_absolute_path_is_published(self):
        """The repository goes public; an absolute path carries a username into it."""
        for value in (
            self.provenance["run_directory"],
            self.provenance["prompts_directory"],
        ):
            with self.subTest(value=value):
                self.assertFalse(
                    str(value).startswith("/"), "an absolute path reached the page"
                )

    def test_a_prompts_path_from_another_checkout_is_not_published(self):
        """The page must be a function of the repository, not of where it was built.

        The run records an absolute prompts path from the machine that produced
        it. In this checkout that path happens to sit under the project root and
        is relativised; in any other checkout it does not. The fallback used to
        return the recorded path unchanged, so a page built anywhere else both
        differed from the committed artefact and carried the author's username
        into a page destined to be published.

        A fresh clone of this repository showed exactly that, and this test is
        the reproduction: ``test_the_committed_page_equals_a_fresh_build`` went
        red, and ``test_no_absolute_path_is_published`` went red naming
        ``/Users/<name>/Desktop/Tribunal/prompts/v1``.
        """
        for foreign in (
            "/somewhere/else/entirely/prompts/v1",
            "/Users/someone/Desktop/Tribunal/prompts/v1",
            "/private/tmp/some-clone/prompts/v1",
        ):
            with self.subTest(prompts_dir=foreign):
                provenance = build._provenance(
                    {"prompts_dir": foreign}, [], build.RUN_DIR, {}
                )
                self.assertEqual("prompts/v1", provenance["prompts_directory"])

    def test_the_runs_own_prompts_path_still_relativises(self):
        """The real run's recorded path yields the value the committed page holds."""
        run = json.loads((build.RUN_DIR / "run.json").read_text(encoding="utf-8"))
        self.assertEqual("prompts/v1", build._repository_relative(run["prompts_dir"]))

    def test_a_path_that_is_not_this_repository_is_dropped_not_published(self):
        """A path from another machine is not this repository's to publish."""
        for value in ("/someone/elses/private/notes", "/etc/passwd", "/var/tmp/x"):
            with self.subTest(value=value):
                self.assertIsNone(build._repository_relative(value))

    def test_no_relative_path_comes_back_absolute(self):
        """The property the leak broke, asserted over every shape that occurs."""
        for value in (
            "/Users/someone/Desktop/Tribunal/prompts/v1",
            "/private/tmp/some-clone/runs/deepseek-deepseek-flash",
            "prompts/v1",
            "runs/deepseek-deepseek-flash",
            "/somewhere/else/private/notes",
        ):
            with self.subTest(value=value):
                result = build._repository_relative(value)
                if result is not None:
                    self.assertFalse(result.startswith("/"), result)
                    self.assertNotIn("\\", result)


# The script that renders the views, as opposed to the data block. The data
# block carries an id and a type, so a bare <script> cannot match it.
_BEHAVIOUR_SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.S)


def behaviour_script(page: str) -> str:
    """The page's behavioural script, parsed out of the page."""
    match = _BEHAVIOUR_SCRIPT_RE.search(page)
    if match is None:
        raise AssertionError("the page carries no behavioural script")
    return match.group(1)


class _IdScan(HTMLParser):
    """Every id on the page, so a view can be required to exist by name."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name == "id" and value:
                self.ids.add(value)


def ids_of(page: str) -> set:
    scan = _IdScan()
    scan.feed(page)
    return scan.ids


class PresentationTests(unittest.TestCase):
    """What a presenter needs: a link to this step, the keys, and a room page.

    Deep links, keyboard navigation, the stance view and projector styling. They
    are tested against the same committed page and in the same spirit as the
    rest: a property is asserted where it can be asserted -- a view exists as an
    element, the stylesheet carries the projector rules, the stance view's two
    kinds of record occur in the data -- and the script's own body is searched
    only for the calls that would break the one guarantee the page makes, that
    it fetches nothing at all.
    """

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.document = build.build_document()
        cls.page = build.render_html(cls.document)
        cls.script = behaviour_script(cls.page)
        cls.ids = ids_of(cls.page)

    def test_the_page_carries_three_views(self):
        """Overview, one case stepped through, and both sides at once."""
        for name in (
            "view-overview", "view-case", "view-stance",
            "nav-overview", "nav-case", "nav-stance",
        ):
            with self.subTest(id=name):
                self.assertIn(name, self.ids)

    def test_the_deep_link_is_a_fragment_and_never_a_navigation(self):
        """A deep link that navigated would be a request, and the page makes none.

        The hash is the one part of a URL a page may write without the browser
        going anywhere, which is why the link to a step lives there and nowhere
        else.
        """
        self.assertIn("location.hash", self.script)
        for call in ("location.href", "location.assign", "location.replace", "window.open"):
            with self.subTest(call=call):
                self.assertNotIn(call, self.script)

    def test_the_script_listens_for_hashchange(self):
        """Only that the listener is named.

        Whether the browser's back button actually walks the steps is a browser
        behaviour, and this suite runs no browser. It was checked by hand and is
        recorded in ``docs/notes/2026-09-23-viewer-manual-check.md``.
        """
        self.assertIn("hashchange", self.script)

    def test_the_page_carries_a_link_input_element(self):
        self.assertIn("link-input", self.ids)

    def test_a_keydown_handler_is_attached(self):
        """Only that a handler is wired, not that a key press does anything."""
        self.assertIn('addEventListener("keydown"', self.script)

    def test_the_script_names_a_key_for_every_step_and_view(self):
        """An honest name for a weak check.

        This asserts the key names occur in the script. It cannot tell you that
        pressing them moves anything -- a string literal ``"o"`` anywhere would
        satisfy it. What the keys do was checked by hand and is recorded in
        ``docs/notes/2026-09-23-viewer-manual-check.md``.
        """
        for key in ("ArrowRight", "ArrowLeft", '"["', '"]"', '"o"', '"c"', '"s"', '"f"', '"?"'):
            with self.subTest(key=key):
                self.assertIn(key, self.script)

    def test_the_projector_is_a_stylesheet_state_not_another_page(self):
        """Scaling the page up must not mean building, or fetching, a second one."""
        styles = _STYLE_RE.findall(self.page)
        self.assertTrue(styles, "the page carries no stylesheet")
        self.assertIn("body.projector", "\n".join(styles))
        self.assertIn('classList.toggle("projector"', self.script)

    def test_every_case_has_both_sides_for_the_stance_view(self):
        for case in self.document["cases"]:
            with self.subTest(case=case["case_no"]):
                for role in ("RIDER_ADVOCATE", "DRIVER_ADVOCATE"):
                    self.assertIn(role, case["advocates"])
                    self.assertIsInstance(
                        case["advocates"][role]["claims"],
                        list,
                        "the stance view reads each side's claims as a list",
                    )

    def test_the_stance_view_has_both_kinds_of_record_to_point_at(self):
        """Shared and one-sided, which is the distinction the view exists to show.

        If no case had the two sides on one artifact, or no case had an artifact
        only one side reached for, the view would have nothing to point at.
        """
        shared = 0
        one_sided = 0

        def cited(case, role):
            found = set()
            for claim in case["advocates"][role]["claims"]:
                found.update(claim.get("evidence_ids") or [])
            return found

        for case in self.document["cases"]:
            rider = cited(case, "RIDER_ADVOCATE")
            driver = cited(case, "DRIVER_ADVOCATE")
            if rider & driver:
                shared += 1
            if rider ^ driver:
                one_sided += 1
        self.assertGreater(shared, 0, "no case has the two sides on one artifact")
        self.assertGreater(one_sided, 0, "no case has an artifact only one side cited")


class StanceProofTests(unittest.TestCase):
    """The proof itself, not its surroundings.

    The side-by-side view shows what each advocate argued. The proof is why
    their disagreement is evidence of anything: they were handed the same bytes
    and differed only in stance. These read the data the built page carries and
    assert the three facts for every case, against the run's own transcript and
    result files -- so they compare two computations rather than one
    computation against a number typed in here.
    """

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.document = build.build_document()
        cls.page = build.render_html(cls.document)
        cls.embedded = embedded_document(cls.page)

    @staticmethod
    def _stored_ranges(case_no: int):
        result = json.loads(
            (build.RUN_DIR / ("case-%05d.json" % case_no)).read_text(encoding="utf-8")
        )
        return result.get("stance_differing_ranges")

    def test_every_case_carries_a_proof(self):
        # Every case the build admitted reaches the page, so a refusal cannot
        # silently shrink the set the proofs are asserted over.
        self.assertEqual(
            sorted(case["case_no"] for case in self.document["cases"]),
            sorted(case["case_no"] for case in self.embedded["cases"]),
        )
        self.assertTrue(self.embedded["cases"], "no case reached the page at all")
        for case in self.embedded["cases"]:
            with self.subTest(case=case["case_no"]):
                self.assertIn("stance_proof", case)

    def test_the_two_advocates_were_handed_the_same_evidence(self):
        """Fact 1: one value, three times."""
        for case in self.embedded["cases"]:
            proof = case["stance_proof"]
            with self.subTest(case=case["case_no"]):
                self.assertEqual(
                    proof["rider"]["user_sha256"], proof["driver"]["user_sha256"]
                )
                self.assertEqual(proof["brief_sha256"], proof["rider"]["user_sha256"])
                self.assertEqual(proof["brief_sha256"], proof["driver"]["user_sha256"])

    def test_the_two_advocates_were_given_different_instructions(self):
        """Fact 2: their system prompts are not identical."""
        for case in self.embedded["cases"]:
            proof = case["stance_proof"]
            with self.subTest(case=case["case_no"]):
                self.assertNotEqual(
                    proof["rider"]["system_sha256"], proof["driver"]["system_sha256"]
                )

    def test_the_embedded_ranges_are_the_ones_the_run_recorded(self):
        """Fact 3: recomputed at build time and equal to what the run stored."""
        for case in self.embedded["cases"]:
            with self.subTest(case=case["case_no"]):
                stored = self._stored_ranges(case["case_no"])
                self.assertEqual(stored, case["stance_proof"]["recorded_differing_ranges"])
                self.assertEqual(stored, case["stance_proof"]["differing_ranges"])

    def test_the_difference_falls_inside_the_stance_block(self):
        region = self.embedded["stance_prompts"]["stance_region"]
        for case in self.embedded["cases"]:
            for lo, hi in case["stance_proof"]["differing_ranges"]:
                with self.subTest(case=case["case_no"], lines=(lo, hi)):
                    self.assertGreaterEqual(lo, region[0])
                    self.assertLessEqual(hi, region[1])

    def test_the_prompts_are_the_ones_the_pipeline_renders(self):
        """Rendered at build time, not quoted into the page.

        If the prompt files change and nothing else does, this fails -- which is
        the point. A proof that quotes a prompt is a proof about the quotation.
        """
        rider, driver, region = pipeline.render_advocate_prompts()
        shared = self.embedded["stance_prompts"]
        self.assertEqual(rider.splitlines(), shared["rider_lines"])
        self.assertEqual(driver.splitlines(), shared["driver_lines"])
        self.assertEqual([region[0], region[1]], shared["stance_region"])

    def test_the_shared_prompts_differ_and_neither_is_empty(self):
        shared = self.embedded["stance_prompts"]
        self.assertGreater(len(shared["rider_lines"]), 0)
        self.assertGreater(len(shared["driver_lines"]), 0)
        self.assertNotEqual(shared["rider_lines"], shared["driver_lines"])

    def test_the_digests_are_carried_in_full(self):
        """A digest you can only partly see is not evidence of equality."""
        for case in self.embedded["cases"]:
            proof = case["stance_proof"]
            for value in (
                proof["brief_sha256"],
                proof["rider"]["user_sha256"],
                proof["driver"]["user_sha256"],
                proof["rider"]["system_sha256"],
                proof["driver"]["system_sha256"],
            ):
                with self.subTest(case=case["case_no"]):
                    self.assertIsInstance(value, str)
                    self.assertEqual(
                        64, len(value), "a truncated digest reached the page"
                    )


class StanceProofRefusalTests(unittest.TestCase):
    """The build stops rather than publish a proof it cannot back."""

    # The case the fixture alters, and the one beside it that must still be
    # admitted -- without which a builder that refused everything would pass.
    ALTERED = 208
    ADMITTED = 209

    def _fixture_run_directory(self, root: Path) -> Path:
        # Made current rather than inherited: see ``fixture_run_directory`` for
        # why a fixture rewrites the copied digests instead of carrying the
        # headline run's.
        return fixture_run_directory(root, (self.ALTERED, self.ADMITTED))

    def test_a_case_whose_stored_ranges_were_altered_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._fixture_run_directory(Path(tmp))
            result_path = run_dir / ("case-%05d.json" % self.ALTERED)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["stance_differing_ranges"] = [[1, 2]]
            result_path.write_text(json.dumps(result), encoding="utf-8")

            with self.assertRaises(build.BuildError) as caught:
                build.build_document(run_dir=run_dir)

        message = str(caught.exception)
        self.assertIn(str(self.ALTERED), message, "the error does not name the case")
        self.assertIn("[[1, 2]]", message, "the error does not say what was recorded")

    def test_a_case_whose_advocate_was_handed_another_brief_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._fixture_run_directory(Path(tmp))
            transcript_path = run_dir / ("case-%05d.transcript.json" % self.ALTERED)
            transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
            for entry in transcript["entries"]:
                if entry.get("role") == "RIDER_ADVOCATE":
                    entry["user_sha256"] = "0" * 64
            transcript_path.write_text(json.dumps(transcript), encoding="utf-8")

            with self.assertRaises(build.BuildError) as caught:
                build.build_document(run_dir=run_dir)

        message = str(caught.exception)
        self.assertIn(str(self.ALTERED), message, "the error does not name the case")
        self.assertIn("RIDER_ADVOCATE", message, "the error does not name the side")

    def test_the_unaltered_case_still_builds_beside_the_altered_one(self):
        """A build that refuses everything would also raise; it must not."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._fixture_run_directory(Path(tmp))
            document = build.build_document(run_dir=run_dir)
        self.assertEqual(
            [self.ALTERED, self.ADMITTED],
            sorted(case["case_no"] for case in document["cases"]),
        )
        self.assertEqual([], document["refused_cases"])


class ReplayTests(unittest.TestCase):
    """A run that reused another run's advocates says so wherever it shows a figure.

    The replay block is written into a copy of the headline run rather than read
    from it. That run called all three agents itself -- it predates the mode that
    borrows another run's advocates -- so a test that waited for a run holding one
    would assert nothing until such a run existed, and would then be asserting
    about whichever run happened to be committed. What is under test is the
    viewer's handling of the block, and the block is written in the shape the
    runner produces.

    The page is a template plus data, and the two halves are asserted separately:
    the source path appears only in the data block, and the sentence that says
    what it means only in the script. A page that carried the fact and never
    rendered it, or rendered a sentence with nothing behind it, fails one half or
    the other. That is why the assertions here are a data check and a script
    check rather than a search for a rendered sentence -- there is no DOM until a
    browser builds one, and a viewer whose behaviour is only in its script can
    only be tested through the script.
    """

    # The case the fixture marks as replayed, and the case beside it that must
    # still be shown as this run's own work -- without which a viewer that
    # labelled every case replayed would pass.
    REPLAYED = 208
    CALLED = 209

    SOURCE = "runs/an-earlier-run"
    # The commit whose run *made* the advocates, which each case's entry records.
    COMMIT = "493beeaf94953943116a25cb74353b3dd2279499"
    # And the commit the source directory records, which after a replay into
    # that directory is the run that *copied* them. The two are different on the
    # committed run, and a footer carrying only the second named the copier as
    # the advocates' provenance.
    COPIED_FROM = "c4c9a06c30bc630e52305a8bf09a14bda83771d5"
    TOKENS = 61753
    OUTSIDE = "/private/tmp/some-clone/runs/an-earlier-run"

    def _fixture_run_directory(self, root: Path, *, source: Optional[str] = SOURCE) -> Path:
        """A two-case run directory, copied from the headline run.

        The copied files are made current first -- see ``fixture_run_directory``
        -- so that what is under test is the viewer's handling of the replay
        block and not the headline run's own staleness. ``source`` of ``None``
        then leaves both files as the run wrote them, which is the "this run
        called every agent itself" case.
        """
        run_dir = fixture_run_directory(root, (self.REPLAYED, self.CALLED))
        # The committed run is itself a replay now, so every copied case arrives
        # already carrying a replay block, and so does its ``run.json``. The
        # fixture therefore starts from a known state: nothing is marked
        # replayed until a test marks it. Without this the negative case -- a
        # run that called its own advocates -- could not be built from the
        # committed run at all, and the positive case would count two replays
        # where it asked for one.
        for name in (
            "run.json",
            "case-%05d.json" % self.REPLAYED,
            "case-%05d.json" % self.CALLED,
        ):
            path = run_dir / name
            document = json.loads(path.read_text(encoding="utf-8"))
            document.pop("replay", None)
            path.write_text(json.dumps(document), encoding="utf-8")

        if source is not None:
            self._mark_replayed(run_dir / ("case-%05d.json" % self.REPLAYED), source)
            self._mark_run(run_dir / "run.json", source)
        return run_dir

    @classmethod
    def _mark_replayed(cls, path: Path, source: str) -> None:
        """The per-case block, in the shape ``ReplayProvenance.as_dict`` writes it."""
        document = json.loads(path.read_text(encoding="utf-8"))
        document["replay"] = {
            "run_dir": source,
            "git_commit": cls.COMMIT,
            "transcript_sha256": "0" * 64,
            "brief_sha256": document["brief_sha256"],
            "model": document["model"],
            "advocate_calls": 2,
            "tokens": {"total_tokens": cls.TOKENS},
            "note": pipeline.REPLAY_NOTE,
        }
        path.write_text(json.dumps(document), encoding="utf-8")

    @classmethod
    def _mark_run(cls, path: Path, source: str) -> None:
        """The run-level block, in the shape ``write_metadata`` writes it.

        ``git_commit`` is the source directory's and ``advocate_commits`` is the
        run that made them, which is the pair the footer has to tell apart.
        """
        document = json.loads(path.read_text(encoding="utf-8"))
        document["replay"] = {
            "run_dir": source,
            "git_commit": cls.COPIED_FROM,
            "advocate_commits": [cls.COMMIT],
            "model": document["model"],
            "prompts_sha256": document["prompts_sha256"],
            "replayed_cases": [cls.REPLAYED],
            "refused_cases": [],
            "tokens": {"total_tokens": cls.TOKENS},
            "note": pipeline.REPLAY_NOTE,
        }
        path.write_text(json.dumps(document), encoding="utf-8")

    def _document(self, *, source: Optional[str] = SOURCE) -> Dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            return build.build_document(
                run_dir=self._fixture_run_directory(Path(tmp), source=source)
            )

    def test_a_replayed_case_carries_the_source_and_what_it_borrowed(self):
        document = self._document()
        cases = {case["case_no"]: case for case in document["cases"]}

        replayed = cases[self.REPLAYED]["replay"]
        self.assertIsNotNone(replayed, "the replayed case does not say so")
        self.assertEqual(self.SOURCE, replayed["run_directory"])
        self.assertEqual(self.COMMIT, replayed["git_commit"])
        self.assertEqual(2, replayed["advocate_calls"])
        self.assertEqual(self.TOKENS, replayed["tokens"]["total_tokens"])
        self.assertIsNone(
            cases[self.CALLED]["replay"],
            "a case this run called itself is shown as replayed",
        )

    def test_the_footer_says_which_run_and_how_many_cases(self):
        document = self._document()
        replay = document["provenance"]["replay"]
        self.assertIsNotNone(replay, "the footer does not say this run replayed")
        self.assertEqual(self.SOURCE, replay["run_directory"])
        self.assertEqual(self.COPIED_FROM, replay["git_commit"])
        self.assertEqual(1, replay["replayed_cases"])
        self.assertEqual(0, replay["refused_cases"])
        self.assertEqual(self.TOKENS, replay["tokens"])

    def test_the_footer_names_the_run_that_made_the_advocates(self):
        """The commit the source directory records is the copying run's.

        The defect, as a regression test. The footer read ``run.json``'s
        ``git_commit`` alone, and a replay into the directory it reads from
        rewrites that file before the next replay reads it: the one commit on
        the page therefore named the run that *copied* the advocates as though
        it were the run that made them. On the committed run the block says
        ``c4c9a06`` while every case's entry says ``493beea``.

        Asserted the way this class asserts everything else -- the value in the
        data block, and the sentence that reads it in the script -- because
        there is no DOM until a browser builds one.
        """
        document = self._document()
        replay = document["provenance"]["replay"]
        page = build.render_html(document)
        script = behaviour_script(page)

        self.assertEqual(self.COPIED_FROM, replay["git_commit"])
        self.assertEqual(
            [self.COMMIT],
            replay["advocate_commits"],
            "the footer does not carry the run that made the advocates",
        )
        self.assertIn(
            self.COMMIT, page, "the run that made the advocates is not on the page"
        )
        self.assertRegex(
            script,
            r"p\.replay\.advocate_commits",
            "the footer does not read the commit that made the advocates",
        )
        self.assertRegex(script, r"were made at ", "no sentence says who made them")

    def test_the_headline_qualifies_the_figure_with_the_replay_and_its_cost(self):
        """The figure is the judge's, and the card a reader sees first has to say so.

        The denominator is asserted against the headline's own, not against a
        number typed here: the point is that the replay block and the figure it
        qualifies are computed over the same set of cases, which is what would
        break if the two were summed from different places.
        """
        document = self._document()
        replay = document["headline"]["replay"]
        self.assertIsNotNone(replay, "the headline does not qualify the figure")
        self.assertEqual(1, replay["cases"])
        self.assertEqual(document["headline"]["cases_graded"], replay["total"])
        self.assertEqual([self.SOURCE], replay["sources"])
        self.assertEqual(self.TOKENS, replay["tokens"])

    def test_the_page_carries_the_source_and_the_sentence_that_reads_it(self):
        document = self._document()
        page = build.render_html(document)
        script = behaviour_script(page)

        self.assertIn(self.SOURCE, page, "the source run is not on the page")
        self.assertIn(str(self.TOKENS), page, "what the borrowed calls cost is not shown")
        self.assertRegex(
            script,
            r"if \(DATA\.headline\.replay\)",
            "the overview does not branch on the replay",
        )
        self.assertRegex(script, r'replayed from "', "no sentence says where from")
        self.assertRegex(
            script, r'"advocates replayed"', "no badge marks the case as replayed"
        )

    def test_a_run_that_called_its_own_advocates_states_that_too(self):
        """An absent field is not an answer; the page needs a branch that answers no."""
        document = self._document(source=None)
        page = build.render_html(document)
        script = behaviour_script(page)

        self.assertIsNone(document["headline"]["replay"])
        self.assertIsNone(document["provenance"]["replay"])
        for case in document["cases"]:
            with self.subTest(case_no=case["case_no"]):
                self.assertIsNone(case["replay"], "a case is shown as replayed")
        self.assertRegex(
            script,
            r'(?s)p\.replay\s*\?\s*"replayed from ".*?:\s*"called by this run"',
            "the footer has no branch that answers no",
        )

    def test_a_source_outside_the_repository_is_named_and_not_published(self):
        """The page is committed; a path from another checkout is not ours to print."""
        document = self._document(source=self.OUTSIDE)
        page = build.render_html(document)

        self.assertEqual(
            ["a run outside this repository"], document["headline"]["replay"]["sources"]
        )
        self.assertNotIn(self.OUTSIDE, page, "a foreign path reached the page")
        self.assertIn("a run outside this repository", page)

    def test_the_source_is_read_from_the_cases_not_from_the_invocation(self):
        """The entries describe the results; ``run.json`` describes the last invocation.

        A directory can hold results from more than one invocation, and only the
        entries say which of them borrowed another run's advocates. Marking the
        run-level block and no case is the state a run.json-only reader would get
        wrong, so it is the state this asserts.
        """
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._fixture_run_directory(Path(tmp), source=None)
            self._mark_run(run_dir / "run.json", self.SOURCE)
            document = build.build_document(run_dir=run_dir)

        self.assertIsNotNone(document["provenance"]["replay"], "the footer lost the block")
        self.assertIsNone(
            document["headline"]["replay"],
            "a case was called replayed because the invocation said so",
        )


# A verification block in the shape the pipeline records: the counts over every
# judged statement, and one entry per statement naming the draft it was charged
# to. Written by hand because the committed run was made with the verifier off,
# so no case in it carries one, and the panel that reads it would otherwise be
# a thing hoped for rather than a thing tested.
VERIFICATION_BLOCK = {
    "called": True,
    "usable": True,
    "reason": "",
    "statements": 3,
    "judged": [
        {
            "n": 1,
            "draft": 1,
            "text": "the driver braked late",
            "kinds": ["fact"],
            "verdict": "supported",
            "evidence": "EV-2",
            "material": None,
            "brief_value": "",
        },
        {
            "n": 2,
            "draft": 1,
            "text": "the fare was 30.00",
            "kinds": ["money"],
            "verdict": "contradicted",
            "evidence": "EV-3",
            "material": True,
            "brief_value": "35.64",
        },
        {
            "n": 3,
            "draft": 2,
            "text": "the rider waited an hour",
            "kinds": ["fact"],
            "verdict": "not_in_evidence",
            "evidence": "",
            "material": None,
            "brief_value": "",
        },
    ],
    "counts": {"supported": 1, "contradicted": 1, "not_in_evidence": 1},
    "material": 1,
    "not_material": 0,
    "abstained": [1],
    "abstain_on": "material",
    "entry": 7,
    "tokens": {"prompt_tokens": 10, "completion_tokens": 5},
}

# Two closure ids, in the shape the runner writes them on the case file when the
# precedents switch is on.
PRECEDENTS_SHOWN = ["P-0001", "P-0002"]


class MoneyAndLabelTests(unittest.TestCase):
    """What the page writes in place of the run's own raw values.

    Money is formatted at display time and nowhere else, so the data block keeps
    the literals the run recorded -- that half is pinned by
    ``TheRunTests.test_money_is_carried_as_its_own_decimal_literal`` and by the
    check below. This class asserts the other half: that every money site on the
    page passes its value through the one formatter, that the string ``"null"``
    reads as ``none``, and that the run's raw tokens survive as class names while
    a reader is shown a label.

    The checks are on the script's own text, which is the limit of what a suite
    that runs no browser can say about a panel drawn in JavaScript. What the
    formatter actually returns for each kind of value was read by running it, and
    the transcript of that run is recorded in
    ``docs/notes/2026-09-29-the-viewer-panels-and-the-money.md``.
    """

    # The run this class reads its page from. Two cases, built by the test, so
    # the class never skips: what it asserts is a property of the code, and it
    # must hold whether or not the committed run is still current.
    CASES = (208, 209)

    # Every money the page shows, as the expression the site holds it in. Each
    # one must be wrapped in ``money(...)`` and none may go straight to
    # ``text(...)``, which is what the page did before and what a reverted site
    # would silently do again.
    MONEY_SITES = (
        "p.amount_sgd",
        "p.driver_compensation_sgd",
        "proposal.amount_sgd",
        "proposal.driver_compensation_sgd",
        "dispute.amount_contested_sgd",
        "verdict.amount_sgd",
        "verdict.driver_compensation_sgd",
        "caseDoc.expected[outcome.field]",
        "caseDoc.judge.verdict[outcome.field]",
    )

    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        run_dir = fixture_run_directory(Path(temporary.name), cls.CASES)
        cls.page = build.render_html(build.build_document(run_dir=run_dir))
        cls.script = behaviour_script(cls.page)

    def test_every_money_site_goes_through_the_one_formatter(self):
        for site in self.MONEY_SITES:
            with self.subTest(site=site):
                self.assertIn(
                    "money(" + site + ")",
                    self.script,
                    "this money site does not use the page's formatter",
                )
                self.assertNotIn(
                    "text(" + site + ")",
                    self.script,
                    "this money site still shows the run's literal as it came",
                )

    def test_the_formatter_rounds_to_two_decimals(self):
        self.assertIn("function money(", self.script)
        self.assertIn("toFixed(2)", self.script)

    def test_a_null_amount_reads_as_none(self):
        """``"null"`` is the grader's word for an unset amount; a reader gets ``none``.

        Read out of the formatter's own body: the literal it compares against and
        the string it returns for it. That the body does what it says was checked
        by running the function, and the note records the run.
        """
        formatter = self.script.split("function money(", 1)[1].split("\n  }", 1)[0]
        self.assertIn('raw === "null"', formatter)
        self.assertIn('return "none"', formatter)

    def test_the_data_still_carries_money_as_its_own_literal(self):
        """The other half of the rule: the formatting is on the page, not in the data."""
        document = embedded_document(self.page)
        self.assertTrue(document["cases"], "the fixture drew no case")
        for case in document["cases"]:
            with self.subTest(case=case["case_no"]):
                for field in ("amount_sgd", "driver_compensation_sgd"):
                    self.assertIsInstance(case["expected"][field], str)
                    self.assertIsInstance(case["judge"]["verdict"][field], str)
                self.assertIsInstance(case["dispute"]["amount_contested_sgd"], str)

    def test_the_outcome_label_replaces_the_token_where_a_reader_looks(self):
        """The grid and the summary show the label; the token stays the class."""
        self.assertIn("text: outcomeLabel(c.vote.outcome)", self.script)
        self.assertNotIn("text: text(c.vote.outcome)", self.script)
        self.assertIn('class: "badge contested " + text(c.vote.outcome)', self.script)

    def test_the_compact_cells_still_count_the_drafts(self):
        """The grid and the summary keep the one-line count; the vote panel is
        the one place that gained the longer sentence, so the one-line count is
        gone from the panel rather than from the page."""
        self.assertIn("agreementLabel(c.vote.agreeing, c.vote.votes)", self.script)
        self.assertIn('" drafts agree"', self.script)
        self.assertNotIn("agreementLabel(vote.agreeing, vote.votes)", self.script)

    def test_the_panel_says_how_the_drafts_voted_in_words(self):
        """The panel's label is the count it reached, in words.

        The raw ``vote_agreement`` badge is gone, and the panel says the count
        instead -- accounting for the drafts that abstained and for the valid
        drafts that disagreed, because the run's ``valid`` count on its own
        cannot tell those two apart. A panel where no draft was valid has no
        count to give and says so.
        """
        self.assertIn("panelSentence(vote)", self.script)
        # The raw badge's own expression, so that a comment naming the fraction
        # is not mistaken for the badge coming back.
        self.assertNotIn('"vote_agreement " +', self.script)
        for fragment in (
            '"judge panel: "',
            '"no valid draft"',
            '" abstained"',
            '" dissented"',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.script)

    def test_the_draft_kind_is_a_label_and_the_token_is_a_class(self):
        self.assertIn("draftKindLabel(draft.kind)", self.script)
        self.assertIn('"badge " + (swapped ? "swapped" : "sampled")', self.script)

    def test_an_abstention_keeps_its_code_as_the_title(self):
        """The code is what the run wrote, so it is kept; the sentence is for a reader."""
        self.assertIn("title: text(draft.abstention)", self.script)
        self.assertIn("abstentionSentence(draft.abstention)", self.script)
        self.assertNotIn('"abstained, and voted for nothing: "', self.script)


class PanelTests(unittest.TestCase):
    """The verifier panel and the precedents panel, and when each is drawn.

    Neither switch is on for the committed run, so no case in it carries the data
    either panel reads. These build their own run directory instead: a copy of the
    committed one with the two blocks the runner would have written added by
    hand. That is what makes each panel a thing under test rather than a thing
    hoped for -- and the state where the data is absent is tested too, because a
    panel drawn for a run that never recorded its data would be a claim about the
    run that the run did not make.
    """

    CASE = 101

    def _fixture(self, *, verification: bool = True, precedents: bool = True) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        run_dir = fixture_run_directory(Path(temporary.name), [self.CASE])
        if verification:
            path = run_dir / ("case-%05d.transcript.json" % self.CASE)
            record = json.loads(path.read_text(encoding="utf-8"))
            record["vote"]["verification"] = VERIFICATION_BLOCK
            path.write_text(json.dumps(record), encoding="utf-8")
        if precedents:
            path = run_dir / ("case-%05d.json" % self.CASE)
            record = json.loads(path.read_text(encoding="utf-8"))
            record["precedents_shown"] = PRECEDENTS_SHOWN
            path.write_text(json.dumps(record), encoding="utf-8")
        return run_dir

    def _case(self, run_dir: Path) -> Dict[str, Any]:
        document = build.build_document(run_dir=run_dir)
        return {case["case_no"]: case for case in document["cases"]}[self.CASE]

    def test_a_recorded_verification_reaches_the_case(self):
        case = self._case(self._fixture())
        self.assertEqual(
            build._normalise(VERIFICATION_BLOCK), case["vote"]["verification"]
        )

    def test_a_recorded_precedents_list_reaches_the_case(self):
        case = self._case(self._fixture())
        self.assertEqual(PRECEDENTS_SHOWN, case["precedents_shown"])

    def test_a_case_that_recorded_neither_carries_neither(self):
        """The absent state, which is the state every case in the committed run is in.

        Both keys must be *absent* rather than present and empty: the page draws
        a panel exactly when its key is there, so an empty key would put a
        verifier panel on a case the verifier never read.
        """
        case = self._case(self._fixture(verification=False, precedents=False))
        self.assertNotIn("verification", case["vote"])
        self.assertIsNone(case["precedents_shown"])

    def test_the_vote_payload_carries_the_verification_only_when_it_is_there(self):
        """The rule the verifier panel's presence rests on, asserted at the payload."""
        raw = {
            "votes": 1,
            "threshold": 1,
            "valid": 1,
            "agreement": 1.0,
            "outcome": pipeline.VOTE_CARRIED,
            "unanimous": True,
            "drafts": [],
        }
        self.assertNotIn("verification", build._vote_payload(raw))
        carried = build._vote_payload(dict(raw, verification=VERIFICATION_BLOCK))
        self.assertEqual(VERIFICATION_BLOCK, carried["verification"])

    def test_the_committed_run_records_neither_panel(self):
        """The committed page carries no panel, because the run it is built from has none."""
        skip_unless_the_run_can_be_drawn()
        for case in build.build_document()["cases"]:
            with self.subTest(case=case["case_no"]):
                self.assertNotIn("verification", case["vote"])
                self.assertIsNone(case["precedents_shown"])

    def test_the_page_draws_each_panel_from_the_run_s_own_data(self):
        """Each panel is wired to its own key, and answers "nothing" with null.

        A panel is appended whether or not it has anything to draw, so the
        function has to return null for the absent case and ``h`` has to skip a
        null child -- otherwise a run with a switch off would show an empty
        heading claiming a panel it never had.
        """
        page = build.render_html(build.build_document(run_dir=self._fixture()))
        script = behaviour_script(page)
        self.assertIn("verifierPanel(caseDoc)", script)
        self.assertIn("precedentsPanel(caseDoc)", script)
        self.assertIn("vote.verification", script)
        self.assertIn("caseDoc.precedents_shown", script)
        self.assertIn("if (!verification) { return null; }", script)
        self.assertIn("if (shown === null || shown === undefined) { return null; }", script)

    def test_the_page_carries_both_blocks(self):
        """The data the panels read is on the page, not only in the document object."""
        page = build.render_html(build.build_document(run_dir=self._fixture()))
        document = embedded_document(page)
        case = {item["case_no"]: item for item in document["cases"]}[self.CASE]
        self.assertEqual(PRECEDENTS_SHOWN, case["precedents_shown"])
        self.assertEqual(
            build._normalise(VERIFICATION_BLOCK), case["vote"]["verification"]
        )


# --------------------------------------------------------------------------
# The page's script, parsed: which functions can answer "nothing"
#
# ``appendChild`` throws when it is handed anything that is not a node, and a
# function that has nothing to draw is the natural place to answer with null.
# Those two facts together cost the owner the whole of step "5. Judge" on all 29
# cases, and the tail of the Overview on every load, in a real browser at
# ``a0fd43e``. No test here could have caught it, because none of them executes
# the page's script.
#
# The guard is therefore a reading of the script rather than a run of it, and it
# cannot be a search for the string ``appendChild(null)``: the call sites name a
# function, not the value it returns. So the script is parsed. Comments and
# string literals are blanked out first, because a brace inside a string or a
# ``//`` inside a comment would move every boundary after it. Function bodies
# are then found by matching brackets, and a nested body is taken out of its
# caller's, so that a callback's ``return null`` is not charged to the function
# that contains it. Argument lists are removed before the returns are read, so
# that the null ``return h("table", null, rows)`` passes to ``h`` is not
# mistaken for a returned one. What remains is the function's own returns.
# --------------------------------------------------------------------------

_RETURNS_NULL = re.compile(r"\breturn\b[^;{}]*\bnull\b")
_DIRECT_CALL = re.compile(r"^([A-Za-z_$][\w$]*)\s*\(")


def blanked(script: str) -> str:
    """The script with every comment and string literal blanked out.

    Blanked rather than removed: one space per character, so an index into the
    result is the same index in the script and a reported line number is the
    line the reader will find.
    """
    out = list(script)
    index, length = 0, len(script)
    while index < length:
        char = script[index]
        if char == "/" and script.startswith("//", index):
            while index < length and script[index] != "\n":
                out[index] = " "
                index += 1
        elif char == "/" and script.startswith("/*", index):
            while index < length and not script.startswith("*/", index):
                if script[index] != "\n":
                    out[index] = " "
                index += 1
            for _ in range(2):
                if index < length:
                    if script[index] != "\n":
                        out[index] = " "
                    index += 1
        elif char in "\"'`":
            quote = char
            out[index] = " "
            index += 1
            while index < length:
                if script[index] == "\\":
                    out[index] = " "
                    if index + 1 < length:
                        out[index + 1] = " "
                    index += 2
                elif script[index] == quote:
                    out[index] = " "
                    index += 1
                    break
                else:
                    if script[index] != "\n":
                        out[index] = " "
                    index += 1
        else:
            index += 1
    return "".join(out)


def closing_bracket(text: str, start: int) -> int:
    """The index just past the bracket that closes the one at ``start``."""
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                return index + 1
    raise AssertionError("the page's script has unbalanced brackets")


def function_bodies(clean: str):
    """``(name, body start, body end)`` for every function that has a body.

    An anonymous callback is yielded with a name of ``None``. It cannot be named
    at a call site, but its body still has to be found, because otherwise the
    ``return null`` inside it would be read as its caller's.
    """
    found = []
    patterns = (
        r"\bfunction\b\s*([A-Za-z_$][\w$]*)?\s*\(",
        r"\b([A-Za-z_$][\w$]*)\s*=\s*function\b\s*\(",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, clean):
            opening = match.end() - 1
            brace = clean.find("{", closing_bracket(clean, opening))
            if brace == -1:
                continue
            found.append((match.group(1), brace, closing_bracket(clean, brace)))
    return found


def own_body(clean: str, spans, start: int, end: int) -> str:
    """A function's body with every nested function body taken out of it."""
    pieces = []
    cursor = start
    for inner_start, inner_end in sorted(spans):
        if start < inner_start and inner_end <= end:
            pieces.append(clean[cursor:inner_start])
            cursor = inner_end
    pieces.append(clean[cursor:end])
    return "".join(pieces)


def without_arguments(text: str) -> str:
    """The text with every balanced ``(...)`` group removed, contents and all.

    ``return h("table", null, rows)`` hands a null to ``h``; it does not return
    one. Removing argument lists before the returns are read keeps the two
    apart, and it is the difference between a guard that names the three real
    call sites and one that also names every table on the page.
    """
    out = []
    index = 0
    while index < len(text):
        if text[index] == "(":
            index = closing_bracket(text, index)
            continue
        out.append(text[index])
        index += 1
    return "".join(out)


def nullable_functions(script: str) -> set:
    """Every named function whose own body can answer ``null``."""
    clean = blanked(script)
    functions = function_bodies(clean)
    spans = [(start, end) for _, start, end in functions]
    return {
        name
        for name, start, end in functions
        if name and _RETURNS_NULL.search(without_arguments(own_body(clean, spans, start, end)))
    }


def function_body(script: str, name: str) -> str:
    """The own body of the named function, with its nested bodies removed."""
    clean = blanked(script)
    functions = function_bodies(clean)
    spans = [(start, end) for _, start, end in functions]
    for found, start, end in functions:
        if found == name:
            return own_body(clean, spans, start, end)
    raise AssertionError("the page's script has no function named " + name)


def _arguments(text: str):
    """The top-level comma-separated arguments of a call's argument list."""
    parts = []
    depth = 0
    current = []
    for char in text:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    parts.append("".join(current).strip())
    return parts


def called_name(argument: str):
    """The function named by ``name(...)``, or ``None`` for anything else."""
    match = _DIRECT_CALL.match(argument)
    return match.group(1) if match else None


def call_arguments(script: str, name: str):
    """``(line, argument)`` for every call of ``name``, as a method or as a function.

    Both forms have to be seen. ``appendChild`` is a DOM method and the helper
    that replaced it at the three call sites is a free function, so a scan that
    knew only one of the two would be a guard over half the page -- and the half
    it missed would be the half the fix is made of.
    """
    clean = blanked(script)
    pattern = re.compile(r"(?:\.|\b)" + re.escape(name) + r"\s*\(")
    found = []
    for match in pattern.finditer(clean):
        opening = clean.index("(", match.end() - 1)
        argument = clean[opening + 1:closing_bracket(clean, opening) - 1].strip()
        found.append((clean[:match.start()].count("\n") + 1, argument))
    return found


def handed_to(script: str, name: str):
    """``(line, function name)`` for every nullable function handed to ``name``.

    A call site counts when a function that can answer null is the whole of one
    of that call's arguments, which is what "handed straight to" means: an
    assignment, a ternary or an array element is a different thing, and the page
    uses all three on purpose.
    """
    nullable = nullable_functions(script)
    found = []
    for line, argument in call_arguments(script, name):
        for part in _arguments(argument):
            called = called_name(part)
            if called in nullable:
                found.append((line, called))
    return found


class ChildAdderTests(unittest.TestCase):
    """Nothing on the page may hand ``appendChild`` a value that can be null.

    This is the defect the owner found in a real browser at ``a0fd43e``, and no
    test in this file could have found it: **the unit tests never execute the
    page's script.** On all 29 cases step "5. Judge" drew nothing, because
    ``verifierPanel`` and ``precedentsPanel`` answer "this run recorded no data"
    with null and ``section.appendChild(null)`` throws. The same throw cut the
    Overview short on every load, from ``root.appendChild(missNote())``, since
    the corpus reached 29/29 and there has been no miss left to note.

    The guard reads the committed page, not a fresh build, because the committed
    page is the artefact a browser loads. A script edited without rebuilding is
    caught by ``CommittedPageTests`` instead, so the two together leave no way
    for the page to keep a call this test would have refused.
    """

    @classmethod
    def setUpClass(cls):
        if not build.OUTPUT_PATH.is_file():
            raise AssertionError("ui/dist/index.html is not committed; run `python -m ui.build`")
        cls.page = build.OUTPUT_PATH.read_text(encoding="utf-8")
        cls.script = behaviour_script(cls.page)

    def test_the_committed_page_carries_a_script_to_scan(self):
        """The scan is worth nothing unless it is reading the real script."""
        self.assertGreater(len(self.script), 10000)
        self.assertGreater(len(call_arguments(self.script, "appendChild")), 100)

    def test_the_scan_finds_the_functions_that_can_answer_null(self):
        """The scan's own control: it must see the functions the fix is about."""
        nullable = nullable_functions(self.script)
        for name in ("missNote", "noRulingBlock", "verifierPanel", "precedentsPanel"):
            with self.subTest(function=name):
                self.assertIn(name, nullable)

    def test_no_string_literal_is_handed_to_append_child(self):
        """``appendChild`` takes a node, and a string literal is not one.

        ``add`` has converted a string to a text node since the page was written
        and ``h`` has always gone through it, so every text append on the page
        goes through ``add``. A call that passes a string literal straight to
        ``appendChild`` is therefore a call that throws in a browser, and two of
        them did: ``missLine`` handed the sentence after a note to
        ``appendChild`` on both of its branches, so every page with a linked miss
        threw out of ``renderOverview`` on load and the last step of every miss
        drew nothing.

        The scan reads the committed page because that is the artefact a browser
        loads. It is not the whole guard -- ``PageScriptRunsTests`` runs the
        script -- but it is the one that names the offending line.
        """
        offenders = [
            (number, line.strip())
            for number, line in enumerate(self.script.splitlines(), 1)
            if re.search(r"appendChild\(\s*[\"']", line)
        ]
        self.assertEqual([], offenders)

    def test_the_scan_can_fire(self):
        """A positive control: a script written to be caught is caught.

        Without this the guard could pass by finding nothing at all, which is
        the failure it exists to prevent one level up. The script below is not
        in the repository; it is written here in exactly the shape that broke.
        """
        script = (
            "function panel(record) {\n"
            "  if (!record) { return null; }\n"
            "  return h('div');\n"
            "}\n"
            "function draw(root) { root.appendChild(panel(record)); }\n"
        )
        self.assertEqual([(5, "panel")], handed_to(script, "appendChild"))
        self.assertEqual([], handed_to(script, "appendNode"))
        self.assertEqual(
            [(5, "panel")], handed_to(script.replace("appendChild", "appendNode"), "appendNode")
        )

    def test_no_nullable_function_is_handed_to_append_child(self):
        """The guard itself, over the page that is committed."""
        self.assertEqual(
            [],
            handed_to(self.script, "appendChild"),
            "a function that can answer null is handed straight to appendChild; "
            "appendChild throws on anything that is not a node, so the one case "
            "where it answers null takes the rest of the step with it",
        )

    def test_every_nullable_function_is_appended_through_the_one_helper(self):
        """Where the null-answering functions are appended, and by what.

        ``noRulingBlock`` joined the list with the held-out set's two cases that
        produced no ruling: it answers "this run could not rule on anything" with
        null, and the overview appends it through the same helper as the rest.
        """
        self.assertEqual(
            ["missNote", "noRulingBlock", "precedentsPanel", "verifierPanel"],
            sorted({name for _, name in handed_to(self.script, "appendNode")}),
        )

    def test_the_scan_runs_over_every_page_that_carries_a_script(self):
        """Every page, not only the corpus's.

        The five pages are built from one ``_JS`` constant, so their scripts are
        byte-identical today and the corpus page's scan is evidence about all of
        them -- ``EveryPageIsSelfContainedTests`` asserts that they are identical,
        and it is the assertion that makes this loop more than ceremony. The loop
        is here anyway, and names the pages that differ, because the day one page
        grows a script of its own is the day the corpus page's scan stops being
        evidence about it.
        """
        scripts = {
            name: behaviour_script(
                build.pages()[name].output_path.read_text(encoding="utf-8")
            )
            for name in PAGE_NAMES
        }
        self.assertIn("corpus", scripts)
        for name, script in sorted(scripts.items()):
            with self.subTest(page=name):
                self.assertEqual(
                    [],
                    handed_to(script, "appendChild"),
                    "a function that can answer null is handed straight to "
                    "appendChild on {0}".format(name),
                )
                self.assertGreater(len(call_arguments(script, "appendChild")), 100)

    def test_the_helper_appends_only_a_real_node(self):
        """``appendNode`` must test for a node before it appends one.

        Asserted on the parsed body of that one function rather than on the
        script at large, so that another function's ``instanceof Node`` cannot
        stand in for it.
        """
        body = function_body(self.script, "appendNode")
        self.assertIn("instanceof Node", body)
        self.assertIn("appendChild", body)


# --------------------------------------------------------------------------
# One page per run, plus the runs index
#
# The viewer used to build one page -- the corpus's -- and fail on any other run.
# ``grade.grade`` was called without the set's own key, so a second set raised
# ``KeyError`` out of ``scores[case_no]``, and the default brief builder knew
# only the corpus manifest. These tests hold the five pages that replaced it:
# what each one takes from its own set, what it refuses, and what it commits.
#
# Two of them exist because of a failure that was *silent* rather than loud.
# ``wild-v2`` must be briefed at policy version 2; at version 1 twelve of its
# twenty cases are refused -- their recorded brief digests are version 2's -- and
# the page still builds, with the twelve missing from a page nothing on it says
# is short. So the version is cross-checked against what the run's own case files
# recorded, and the mismatch stops the build. And a case that produced no ruling
# was graded as a miss while appearing nowhere, so the two held-out cases in that
# state are now in the case list, in the produced column, and in a block of their
# own.
# --------------------------------------------------------------------------

# The five pages, in the order the index lists them.
PAGE_NAMES = ("corpus", "codex", "wild", "wild-v2", "ryde-901")

# The note each set attaches to its misses, where it attaches one. The first is
# about the held-out set's run as a class, so it covers every miss of that set;
# the second names its two cases, so it is attached to those cases only.
THE_SEALED_RUN_NOTE = "docs/notes/2026-09-30-the-sealed-run.md"
THE_SECOND_SEALED_RUN_NOTE = "docs/notes/2026-10-04-the-second-sealed-run.md"

# What every file published under ``ui/dist/`` is scanned for before the
# repository goes public. The label is the whole failure message: a hit names the
# file and the pattern and never prints the text that matched, which would
# republish the very thing the scan exists to keep out.
_PUBLISH_PATTERNS = (
    ("an absolute path under /Users/", re.compile(r"/Users/")),
    ("an absolute path under /private/", re.compile(r"/private/")),
    ("the author's account name", re.compile(r"hanweizhou")),
    ("an email address", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("an API key", re.compile(r"sk-[A-Za-z0-9_\-]{8,}")),
    ("a bearer token", re.compile(r"Bearer ")),
    ("a secret key", re.compile(r"SecretKey")),
    ("an environment file", re.compile(r"\.env")),
)

_built_documents: Optional[Dict[str, dict]] = None


def built_documents() -> Dict[str, dict]:
    """Every page's document, built once for the whole test process.

    Each document replays a run and rebuilds every brief in it, which is about
    forty seconds for the five together, so building them per test would turn
    these classes into minutes. Nothing below mutates a document.
    """
    global _built_documents
    if _built_documents is None:
        _built_documents = {
            name: build.build_document(page=build.pages()[name]) for name in PAGE_NAMES
        }
    return _built_documents


def committed_pages() -> Dict[str, str]:
    """Every committed page under ``ui/dist/``, by path relative to it."""
    return {
        str(path.relative_to(build.DIST_DIR)): path.read_text(encoding="utf-8")
        for path in sorted(build.DIST_DIR.rglob("*"))
        if path.is_file()
    }


class ViewerPageRegistryTests(unittest.TestCase):
    """One page per set, each reading its own run, key and policy version."""

    def test_the_registry_holds_the_five_pages_the_sheet_names(self):
        self.assertEqual(sorted(PAGE_NAMES), sorted(build.pages()))
        # And the order the index lists them in, which is the corpus first
        # because it is the page the submission links to.
        self.assertEqual(tuple(PAGE_NAMES), build._INDEX_ORDER)

    def test_every_page_is_where_the_sheet_says_it_is(self):
        expected = {
            "corpus": "ui/dist/index.html",
            "codex": "ui/dist/codex/index.html",
            "wild": "ui/dist/wild/index.html",
            "wild-v2": "ui/dist/wild-v2/index.html",
            "ryde-901": "ui/dist/ryde-901/index.html",
        }
        for name, path in sorted(expected.items()):
            with self.subTest(page=name):
                self.assertEqual(
                    path,
                    str(build.pages()[name].output_path.relative_to(build.PROJECT_ROOT)),
                )

    def test_the_corpus_page_keeps_the_path_the_submission_links_to(self):
        """The one output path that must not move."""
        self.assertEqual(build.OUTPUT_PATH, build.pages()["corpus"].output_path)
        self.assertEqual(
            "ui/dist/index.html",
            str(build.OUTPUT_PATH.relative_to(build.PROJECT_ROOT)),
        )

    def test_every_page_reads_the_run_the_sheet_names(self):
        expected = {
            "corpus": "runs/deepseek-deepseek-flash",
            "codex": "runs/codex/deepseek-deepseek-flash",
            "wild": "runs/wild/deepseek-deepseek-flash",
            "wild-v2": "runs/wild-v2/deepseek-deepseek-flash",
            "ryde-901": "runs/rerun-2026-09-29/external/ryde",
        }
        for name, path in sorted(expected.items()):
            with self.subTest(page=name):
                self.assertEqual(
                    path,
                    str(build.pages()[name].run_dir.relative_to(build.PROJECT_ROOT)),
                )

    def test_the_organisers_case_is_read_from_the_re_run_not_the_stale_one(self):
        """``runs/external/ryde`` predates the money facts and no longer rebuilds.

        A page built from it would refuse the one case it holds, so the page
        would be an empty shell that still exits zero.
        """
        page = build.pages()["ryde-901"]
        self.assertIn("rerun-2026-09-29", str(page.run_dir))
        self.assertNotEqual(
            build.PROJECT_ROOT / "runs" / "external" / "ryde", page.run_dir
        )

    def test_every_page_but_the_organisers_case_is_graded_against_its_own_key(self):
        expected = {
            "corpus": "eval/answers/ground_truth.json",
            "codex": "eval/answers/codex/ground_truth.json",
            "wild": "eval/answers/wild/ground_truth.json",
            "wild-v2": "eval/answers/wild-v2/ground_truth.json",
        }
        for name, path in sorted(expected.items()):
            with self.subTest(page=name):
                self.assertEqual(
                    path,
                    str(build.pages()[name].key_path.relative_to(build.PROJECT_ROOT)),
                )
        self.assertIsNone(build.pages()["ryde-901"].key_path)

    def test_the_sealed_pages_carry_their_freeze_tags(self):
        pages = build.pages()
        self.assertEqual("freeze-2026-09-30", pages["wild"].freeze_tag)
        self.assertEqual("freeze-2026-10-03", pages["wild-v2"].freeze_tag)
        for name in ("corpus", "codex", "ryde-901"):
            with self.subTest(page=name):
                self.assertIsNone(pages[name].freeze_tag)

    def test_the_corpus_page_sits_at_the_top_and_every_other_one_level_down(self):
        """Depth is what every relative link on a page is computed from."""
        pages = build.pages()
        self.assertEqual(0, pages["corpus"].depth)
        for name in ("codex", "wild", "wild-v2", "ryde-901"):
            with self.subTest(page=name):
                self.assertEqual(1, pages[name].depth)

    def test_an_unknown_set_is_refused_by_name(self):
        self.assertEqual(1, build.main(["--set", "no-such-set"]))

    def test_naming_a_run_or_an_output_without_a_set_is_refused(self):
        """``--run-dir`` and ``--out`` are one page's inputs, so they need a page."""
        self.assertEqual(1, build.main(["--run-dir", "runs/deepseek-deepseek-flash"]))
        self.assertEqual(1, build.main(["--out", "/tmp/whatever.html"]))


class PolicyVersionTests(unittest.TestCase):
    """A set briefed at the wrong policy version must stop the build, not shrink.

    ``wild-v2`` is the case this exists for. At version 1, twelve of its twenty
    cases are refused -- their recorded brief digests are version 2's -- and the
    page still builds with the twelve missing. Twelve missing cases out of twenty
    is not something a reader can tell by looking at the page, so the version is
    checked against what the run's own case files recorded and a disagreement
    stops the build instead.
    """

    def test_the_second_sealed_set_is_registered_at_version_two(self):
        self.assertEqual(2, build.pages()["wild-v2"].policy_version)

    def test_briefing_the_second_sealed_set_at_version_one_is_refused(self):
        page = build.pages()["wild-v2"]
        wrong = dataclasses.replace(page, policy_version=1)
        with self.assertRaises(build.BuildError) as caught:
            build.build_document(page=wrong)
        message = str(caught.exception)
        self.assertIn("policy version", message)
        self.assertIn("wild-v2", message)
        # The cases are named, so the reader sees which records disagree rather
        # than being told only that something does.
        self.assertIn("701", message)

    def test_the_check_reads_the_version_the_run_itself_recorded(self):
        """The control: the guard has something to read, and reads it.

        A page whose version is right is admitted, which is what stops the guard
        from being a rule that refuses everything.
        """
        mismatches = build._policy_version_mismatches(
            {701: {"configuration": {"policy_version": 2}}},
            build.pages()["wild-v2"],
        )
        self.assertEqual([], mismatches)
        self.assertEqual(
            1,
            len(
                build._policy_version_mismatches(
                    {701: {"configuration": {"policy_version": 1}}},
                    build.pages()["wild-v2"],
                )
            ),
        )


class PerSetPageTests(unittest.TestCase):
    """What each page takes from its own set, asserted on the built documents."""

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.documents = built_documents()

    def test_every_page_names_its_own_set(self):
        for name in PAGE_NAMES:
            with self.subTest(page=name):
                self.assertEqual(name, self.documents[name]["set"]["name"])

    def test_every_page_carries_its_own_title_and_brand(self):
        """The two strings that were the corpus's on every page."""
        titles = [self.documents[name]["set"]["title"] for name in PAGE_NAMES]
        brands = [self.documents[name]["set"]["brand"] for name in PAGE_NAMES]
        for name in PAGE_NAMES:
            with self.subTest(page=name):
                self.assertTrue(self.documents[name]["set"]["title"])
                self.assertIn("Tribunal", self.documents[name]["set"]["title"])
        # A reader with two pages open has only the title bar to tell them apart,
        # so no two pages may share one.
        self.assertEqual(len(PAGE_NAMES), len(set(titles)))
        self.assertEqual(len(PAGE_NAMES), len(set(brands)))

    def test_the_sealed_pages_carry_the_caveat_the_registration_already_writes(self):
        """No new caveat text: the words come out of ``eval/development_sets.py``."""
        from eval import development_sets

        for name in ("wild", "wild-v2"):
            with self.subTest(page=name):
                self.assertEqual(
                    development_sets.SEALED_SET_SECTIONS[name][1],
                    self.documents[name]["set"]["caveat"],
                )
        for name in ("corpus", "codex", "ryde-901"):
            with self.subTest(page=name):
                self.assertIsNone(self.documents[name]["set"]["caveat"])

    def test_the_footer_digest_is_the_sets_own_key(self):
        """The corpus key's digest on the held-out page would be a claim about a
        key that run was never graded against."""
        digests = {}
        for name in ("corpus", "codex", "wild", "wild-v2"):
            with self.subTest(page=name):
                digest = self.documents[name]["provenance"]["answer_key_sha256"]
                self.assertEqual(grade.answer_key_sha256(build.pages()[name].key_path), digest)
                digests[name] = digest
        self.assertEqual(
            len(digests), len(set(digests.values())), "two sets share a key digest"
        )
        self.assertIsNone(
            self.documents["ryde-901"]["provenance"]["answer_key_sha256"]
        )

    def test_the_default_case_is_the_one_the_set_names(self):
        self.assertEqual(208, self.documents["corpus"]["default_case"])
        self.assertEqual(901, self.documents["ryde-901"]["default_case"])

    def test_every_other_page_opens_on_a_case_that_matched_four_fields(self):
        """For the three sets that name none, the opening case is a fact about
        the run rather than a number chosen by hand."""
        for name in ("codex", "wild", "wild-v2"):
            with self.subTest(page=name):
                document = self.documents[name]
                cases = {case["case_no"]: case for case in document["cases"]}
                opened = cases[document["default_case"]]
                self.assertTrue(opened["grading"]["exact"])

    def test_the_corpus_target_is_shown_only_on_the_corpus_page(self):
        """The target is a property of the 29-case corpus. A sealed set's rate
        printed beside it would invite a comparison the set is not answerable
        to."""
        self.assertTrue(
            self.documents["corpus"]["headline"]["escalation"]["corpus_target"]
        )
        for name in ("codex", "wild", "wild-v2"):
            with self.subTest(page=name):
                self.assertFalse(
                    self.documents[name]["headline"]["escalation"]["corpus_target"]
                )

    def test_the_organisers_case_has_no_accuracy_figures_at_all(self):
        headline = self.documents["ryde-901"]["headline"]
        self.assertIsNone(headline["exact"])
        self.assertEqual([], headline["exact_bases"])
        self.assertIsNone(headline["escalation"])
        self.assertEqual({}, headline["fields"])

    def test_the_organisers_case_is_shown_beside_its_stated_expectation(self):
        """Not a key: labelled as what it is, and never compared field by field."""
        document = self.documents["ryde-901"]
        stated = document["stated_expectation"]
        self.assertIsNotNone(stated)
        self.assertEqual("Cancellation charge UPHELD", stated["expected_outcome_as_stated"])
        self.assertIn("NOT part of eval/answers/ground_truth.json", stated["not_the_answer_key"])
        self.assertEqual(1, len(document["cases"]))
        self.assertIsNone(document["cases"][0]["grading"])

    def test_the_organisers_case_still_shows_the_ruling_the_run_reached(self):
        """A page with no key is not a page with no result.

        The produced side used to be read out of the grader's parsed ruling, and
        there is no grader here, so all four fields came out ``null`` -- which
        hides a ruling the run did produce.
        """
        verdict = self.documents["ryde-901"]["cases"][0]["judge"]["verdict"]
        self.assertEqual("ESCALATE", verdict["ruling"])
        self.assertEqual([], verdict["referrals"])

    def test_an_invocations_file_whose_cases_is_a_list_is_read(self):
        """The organisers' re-run writes ``cases`` as a list, not a mapping.

        Reading ``.items()`` off it raised ``AttributeError``, so the one page
        with no key could not be built at all.
        """
        run_dir = build.pages()["ryde-901"].run_dir
        invocations = json.loads(
            (run_dir / "invocations.json").read_text(encoding="utf-8")
        )
        self.assertIsInstance(invocations, list)
        self.assertTrue(
            any(isinstance(entry.get("cases"), list) for entry in invocations),
            "the shape this test is about is no longer in the run",
        )
        provenance = build._provenance(
            json.loads((run_dir / "run.json").read_text(encoding="utf-8")),
            invocations,
            run_dir,
            {},
            None,
        )
        self.assertEqual(len(invocations), len(provenance["invocations"]))
        for entry in provenance["invocations"]:
            # The count asked for is the one a bare list can carry; the split
            # into completed and failed is not claimed, because the record does
            # not carry it.
            self.assertEqual(1, entry["requested"])
            self.assertIsNone(entry["completed"])
            self.assertIsNone(entry["failed"])


class HeadlineBasisTests(unittest.TestCase):
    """The two bases of the four-field figure, and the report they must equal."""

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.documents = built_documents()

    def test_the_sealed_sets_report_both_bases_and_label_them(self):
        expected = {"wild": ["55/62", "55/64"], "wild-v2": ["18/20", "18/20"]}
        for name, figures in sorted(expected.items()):
            with self.subTest(page=name):
                bases = self.documents[name]["headline"]["exact_bases"]
                self.assertEqual(figures, [basis["display"] for basis in bases])
                # A case with no ruling is the whole difference between the two,
                # so the labels have to say which is which.
                self.assertIn("produced a ruling", bases[0]["label"])
                self.assertIn("counted as a miss", bases[1]["label"])
                self.assertEqual(
                    figures[1], self.documents[name]["headline"]["exact"]["display"]
                )

    def test_the_two_bases_equal_what_eval_sealed_report_prints(self):
        """Asserted against the report command, not against numbers typed here."""
        for name in ("wild", "wild-v2"):
            with self.subTest(page=name):
                completed = subprocess.run(
                    [sys.executable, "-m", "eval.sealed_report", "--set", name],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)
                self.assertIn("Four-field exact", completed.stdout)
                section = completed.stdout.split("Four-field exact", 1)[1]
                printed = re.findall(r": (\d+/\d+)", section)[:2]
                bases = self.documents[name]["headline"]["exact_bases"]
                self.assertEqual(printed, [basis["display"] for basis in bases])


class NoRulingTests(unittest.TestCase):
    """The two cases the held-out set asked and could not rule on.

    They are graded as misses -- a case that produced nothing is not a case that
    agreed -- and they used to appear nowhere on the page, so the figure counted
    them and nothing let a reader find them.
    """

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.document = built_documents()["wild"]
        cls.cases = {case["case_no"]: case for case in cls.document["cases"]}

    def test_the_run_recorded_two_cases_it_could_not_rule_on(self):
        self.assertEqual(
            [517, 533],
            sorted(case["case_no"] for case in self.document["no_ruling_cases"]),
        )

    def test_each_is_listed_with_the_runs_own_failure_kind_and_detail(self):
        for entry in self.document["no_ruling_cases"]:
            with self.subTest(case=entry["case_no"]):
                self.assertEqual("SHAPE", entry["failure_kind"])
                self.assertEqual("JUDGE", entry["failed_agent"])
                self.assertTrue(entry["detail"], "the failure detail did not reach the page")

    def test_they_are_in_the_case_list_and_graded_as_misses(self):
        """A case with no ruling is a miss, not a case that is absent."""
        for case_no in (517, 533):
            with self.subTest(case=case_no):
                case = self.cases[case_no]
                self.assertFalse(case["has_ruling"])
                self.assertFalse(case["grading"]["exact"])
                self.assertEqual(
                    ["ruling", "amount_sgd", "driver_compensation_sgd", "referrals"],
                    case["grading"]["failed_fields"],
                )
                self.assertIsNone(case["judge"]["verdict"]["ruling"])
                self.assertEqual([], case["judge"]["verdict"]["referrals"])

    def test_the_judge_step_carries_four_abstained_drafts(self):
        for case_no in (517, 533):
            with self.subTest(case=case_no):
                vote = self.cases[case_no]["vote"]
                self.assertEqual(4, len(vote["drafts"]))
                self.assertEqual(0, vote["valid"])
                for draft in vote["drafts"]:
                    self.assertEqual("abstained", draft["verdict"])

    def test_the_stance_proof_says_the_ranges_were_not_recorded(self):
        """An empty list would read as a recorded finding that the two renders
        do not differ, which is the opposite of what the run left behind."""
        for case_no in (517, 533):
            with self.subTest(case=case_no):
                proof = self.cases[case_no]["stance_proof"]
                self.assertIsNone(proof["recorded_differing_ranges"])
                self.assertTrue(proof["differing_ranges"])

    def test_the_brief_is_verified_through_the_advocates_own_digest(self):
        """The route a case with no result file is admitted by.

        There is no ``brief_sha256`` in a result that was never written, so the
        digest comes from the advocates' own transcript entries -- which are the
        same brief by the other place the run records it.
        """
        for case_no in (517, 533):
            with self.subTest(case=case_no):
                case = self.cases[case_no]
                self.assertEqual(64, len(case["brief_sha256"]))
                for role in ("RIDER_ADVOCATE", "DRIVER_ADVOCATE"):
                    self.assertEqual(
                        case["brief_sha256"], case["advocates"][role]["user_sha256"]
                    )

    def test_the_failed_cases_tokens_are_in_the_total(self):
        """The headline is a figure over the run, so the tokens it spent failing
        are part of it."""
        tokens = self.document["headline"]["tokens"]
        self.assertEqual(2, tokens["failed_cases"])
        self.assertEqual(526237, tokens["failed_total"])
        run = json.loads(
            (build.pages()["wild"].run_dir / "run.json").read_text(encoding="utf-8")
        )
        self.assertEqual(run["tokens"]["total_for_the_case_set"], tokens["total"])
        self.assertEqual(64, tokens["cases"])

    def test_the_produced_column_says_no_ruling_rather_than_nothing(self):
        """The data half of the claim, and then the script that draws it.

        A blank cell would read as a ruling of ``null``, which is a token this
        system emits and a different thing from a case that produced nothing.
        """
        for case_no in (517, 533):
            with self.subTest(case=case_no):
                self.assertFalse(self.cases[case_no]["has_ruling"])
        script = behaviour_script(
            build.pages()["corpus"].output_path.read_text(encoding="utf-8")
        )
        self.assertIn('"no ruling"', script)
        self.assertIn("c.has_ruling", script)
        self.assertIn("DATA.no_ruling_cases", script)


class MissNoteTests(unittest.TestCase):
    """Which miss links to which note, and which links to nothing.

    Both ``missNote`` and the last step used to label every miss "a contested
    reading rather than a defect" and link one note that is only about case 211.
    On a page whose misses have no note written about them, that is a claim this
    repository does not make.
    """

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.documents = built_documents()

    @staticmethod
    def _misses(document: dict) -> list:
        return sorted(
            str(case["case_no"])
            for case in document["cases"]
            if case["grading"] and not case["grading"]["exact"]
        )

    def test_the_two_named_cases_of_the_second_sealed_set_link_to_their_note(self):
        notes = self.documents["wild-v2"]["miss_notes"]
        self.assertEqual(["702", "716"], sorted(notes))
        for case_no in ("702", "716"):
            with self.subTest(case=case_no):
                self.assertEqual(THE_SECOND_SEALED_RUN_NOTE, notes[case_no]["note"])
                self.assertTrue(
                    notes[case_no]["link"].endswith(THE_SECOND_SEALED_RUN_NOTE)
                )

    def test_every_miss_of_the_held_out_set_links_to_the_note_about_that_set(self):
        document = self.documents["wild"]
        self.assertEqual(self._misses(document), sorted(document["miss_notes"]))
        for case_no, note in sorted(document["miss_notes"].items()):
            with self.subTest(case=case_no):
                self.assertEqual(THE_SEALED_RUN_NOTE, note["note"])

    def test_a_miss_with_no_note_gets_no_link_and_no_contested_wording(self):
        """The second development set's one miss has no note about it."""
        document = self.documents["codex"]
        self.assertEqual(["9111"], self._misses(document))
        self.assertEqual({}, document["miss_notes"])

    def test_no_note_is_attached_to_a_case_that_is_not_a_miss(self):
        for name in PAGE_NAMES:
            document = self.documents[name]
            with self.subTest(page=name):
                cases = {case["case_no"]: case for case in document["cases"]}
                for case_no in document["miss_notes"]:
                    self.assertFalse(cases[int(case_no)]["grading"]["exact"])

    def test_the_link_is_written_for_the_depth_of_its_own_page(self):
        """A note linked from ``ui/dist/wild/`` needs one more ``../`` than one
        linked from ``ui/dist/``."""
        for note in self.documents["wild"]["miss_notes"].values():
            with self.subTest(link=note["link"]):
                self.assertTrue(note["link"].startswith("../../../docs/notes/"))
        for note in self.documents["wild-v2"]["miss_notes"].values():
            with self.subTest(link=note["link"]):
                self.assertTrue(note["link"].startswith("../../../docs/notes/"))


class EveryPageIsCommittedTests(unittest.TestCase):
    """Each page and the index: the committed bytes are the bytes this code makes."""

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.documents = built_documents()

    def test_every_page_is_committed_and_equals_a_fresh_build(self):
        for name in PAGE_NAMES:
            path = build.pages()[name].output_path
            with self.subTest(page=name):
                self.assertTrue(
                    path.is_file(),
                    "{0} is not committed; run `python3 -m ui.build`".format(path),
                )
                self.assertEqual(
                    build.render_html(self.documents[name]),
                    path.read_text(encoding="utf-8"),
                    "{0} differs from a fresh build; run `python3 -m ui.build`".format(path),
                )

    def test_the_runs_index_is_committed_and_equals_a_fresh_build(self):
        self.assertTrue(
            build.INDEX_PATH.is_file(), "run `python3 -m ui.build`"
        )
        self.assertEqual(
            build.render_index(self.documents),
            build.INDEX_PATH.read_text(encoding="utf-8"),
            "ui/dist/runs/index.html differs from a fresh build; "
            "run `python3 -m ui.build`",
        )

    def test_the_index_lists_one_row_per_page_and_nothing_else(self):
        text = build.INDEX_PATH.read_text(encoding="utf-8")
        # Five rows plus the header row.
        self.assertEqual(1 + len(PAGE_NAMES), text.count("<tr>"))
        for name in PAGE_NAMES:
            with self.subTest(page=name):
                self.assertIn(">" + name + "</a>", text)

    def test_the_index_figures_are_the_figures_its_pages_print(self):
        """Computed from the built documents, never typed in."""
        text = build.INDEX_PATH.read_text(encoding="utf-8")
        for name in ("corpus", "codex", "wild", "wild-v2"):
            with self.subTest(page=name):
                display = self.documents[name]["headline"]["exact"]["display"]
                self.assertIn(display, text)
        self.assertIn("not graded", text)

    def test_the_sealed_sets_stand_alone_and_are_never_summed(self):
        """One figure over 64 cases plus another over 20 is not a measurement of
        84 cases, so no row may say it is.

        The index's own lead says the two are not added, and names the count it
        would have been -- so the check is for a figure *over* that count rather
        than for the number itself.
        """
        text = build.INDEX_PATH.read_text(encoding="utf-8")
        for tag in ("freeze-2026-09-30", "freeze-2026-10-03"):
            with self.subTest(tag=tag):
                self.assertIn(tag, text)
        self.assertNotIn("/84", text, "the index prints a figure over both sealed sets")
        for name in ("wild", "wild-v2"):
            with self.subTest(page=name):
                display = self.documents[name]["headline"]["exact"]["display"]
                self.assertIn(display, text)

    def test_every_page_links_to_the_index_and_the_index_links_back(self):
        index = build.INDEX_PATH.read_text(encoding="utf-8")
        for name in PAGE_NAMES:
            with self.subTest(page=name):
                page = build.pages()[name]
                text = page.output_path.read_text(encoding="utf-8")
                self.assertIn(
                    'href="{0}"'.format(self.documents[name]["set"]["runs_index_link"]),
                    text,
                )
                from_index = "../" + page.output_path.relative_to(build.DIST_DIR).as_posix()
                self.assertIn('href="{0}"'.format(from_index), index)


class EveryPageIsSelfContainedTests(unittest.TestCase):
    """Every published file is one file with nothing external in it."""

    def test_no_published_file_references_an_external_resource(self):
        for relative, text in sorted(committed_pages().items()):
            with self.subTest(page=relative):
                scan = _ResourceScan()
                scan.feed(text)
                external = [
                    url for _, _, url in scan.references if is_external_reference(url)
                ]
                self.assertEqual(
                    [], external, "{0} references an external resource".format(relative)
                )
                for tag in ("<link", "<iframe", "<object", "<embed"):
                    self.assertNotIn(tag, text, "{0} embeds {1}".format(relative, tag))

    def test_no_published_file_fetches_anything_at_runtime(self):
        for relative, text in sorted(committed_pages().items()):
            scan = _ResourceScan()
            scan.feed(text)
            script = "\n".join(scan.script_bodies)
            for call in (
                "fetch(",
                "XMLHttpRequest",
                "importScripts(",
                "new Worker(",
                "new EventSource(",
                "new WebSocket(",
            ):
                with self.subTest(page=relative, call=call):
                    self.assertNotIn(call, script)

    def test_every_page_but_the_index_carries_the_same_script(self):
        """Said out loud, because the ``appendNode`` scan depends on it.

        The pages are built from one ``_JS`` constant, so their scripts are
        byte-identical today and a scan of the corpus page is a scan of all five.
        If that stops being true, this says so, and ``ChildAdderTests`` starts
        scanning each page separately.
        """
        scripts = {
            name: behaviour_script(
                build.pages()[name].output_path.read_text(encoding="utf-8")
            )
            for name in PAGE_NAMES
        }
        differing = sorted(
            name for name, script in scripts.items() if script != scripts["corpus"]
        )
        self.assertEqual([], differing, "these pages carry a script of their own")


class PublishScanTests(unittest.TestCase):
    """Everything under ``ui/dist/`` is scanned before the repository goes public."""

    def test_no_published_file_carries_a_path_a_secret_or_an_address(self):
        published = committed_pages()
        self.assertTrue(published, "ui/dist/ is empty")
        for relative, text in sorted(published.items()):
            for label, pattern in _PUBLISH_PATTERNS:
                with self.subTest(file=relative, pattern=label):
                    self.assertIsNone(
                        pattern.search(text),
                        "{0} matches {1}".format(relative, label),
                    )

    def test_the_scan_can_fire(self):
        """A positive control over every pattern.

        Without it the scan would pass just as well if a pattern were written
        wrong and matched nothing at all, which is the failure it exists to
        prevent one level up.

        The planted text is assembled from pieces rather than written out whole.
        A key-shaped or path-shaped literal in this file would be a false alarm
        for every scan of the repository -- including the one next door, which
        reads this file's own shapes -- and a file that cries wolf about itself
        is a file whose scan nobody trusts.
        """
        home = "/" + "Users" + "/someone"
        account = "hanwei" + "zhou"
        address = "someone" + "@" + "example.com"
        key = "sk-" + "ABCDEFGH1234"
        planted = "\n".join(
            [
                home + "/Desktop/Tribunal",
                "/private/tmp/scratch",
                "the author is " + account,
                "write to " + address,
                key,
                "Authorization: Bearer abcdef",
                "AWSSecretKey = x",
                "read the .env file",
            ]
        )
        caught = [label for label, pattern in _PUBLISH_PATTERNS if pattern.search(planted)]
        self.assertEqual(len(_PUBLISH_PATTERNS), len(caught), caught)


class CheckCoversEveryPageTests(unittest.TestCase):
    """``--check`` is the gate, so it must look at every page and at the index."""

    def test_check_examines_every_page_and_the_index(self):
        completed = subprocess.run(
            [sys.executable, "-m", "ui.build", "--check"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        paths = [build.pages()[name].output_path for name in PAGE_NAMES]
        paths.append(build.INDEX_PATH)
        for path in paths:
            with self.subTest(path=path.name):
                self.assertIn(str(path), completed.stdout)
                self.assertIn("identical to a fresh build", completed.stdout)

    def test_check_fails_when_a_page_on_disk_differs(self):
        """The gate's own control: a changed byte must make it exit non-zero."""
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "one-page.html"
            self.assertEqual(
                0,
                build._write_or_check(destination, "first", False, "a page"),
            )
            self.assertEqual(
                0,
                build._write_or_check(destination, "first", True, "a page"),
            )
            self.assertEqual(
                1,
                build._write_or_check(destination, "second", True, "a page"),
            )


# ---------------------------------------------------------------------------
# Reading the stylesheet as rules, for the tests that have no browser.
# ---------------------------------------------------------------------------

def _media_blocks(stylesheet: str):
    """Every ``@media`` block as ``(condition, body)``.

    A regular expression cannot do this. The bodies carry nested rules, so the
    only way to find where a block ends is to count braces, and a pattern that
    guessed would either stop at the first inner rule or run past the end of the
    block it was looking for.
    """
    blocks = []
    index = 0
    while True:
        start = stylesheet.find("@media", index)
        if start < 0:
            return blocks
        opening = stylesheet.find("{", start)
        if opening < 0:
            return blocks
        depth = 0
        cursor = opening
        while cursor < len(stylesheet):
            if stylesheet[cursor] == "{":
                depth += 1
            elif stylesheet[cursor] == "}":
                depth -= 1
                if depth == 0:
                    break
            cursor += 1
        condition = stylesheet[start + len("@media"):opening].strip()
        blocks.append((condition, stylesheet[opening + 1:cursor]))
        index = cursor + 1


def _outside_media(stylesheet: str) -> str:
    """The stylesheet with every ``@media`` block cut out of it.

    The narrow-width rules are read from the block itself, so the rules that
    apply at every width have to be read from what is left.
    """
    out = []
    index = 0
    while True:
        start = stylesheet.find("@media", index)
        if start < 0:
            out.append(stylesheet[index:])
            return "".join(out)
        out.append(stylesheet[index:start])
        opening = stylesheet.find("{", start)
        depth = 0
        cursor = opening
        while cursor < len(stylesheet):
            if stylesheet[cursor] == "{":
                depth += 1
            elif stylesheet[cursor] == "}":
                depth -= 1
                if depth == 0:
                    break
            cursor += 1
        index = cursor + 1


_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def declarations(stylesheet: str):
    """Every declaration in a stylesheet as ``(selector, property, value)``.

    Comments come out first, and both reasons matter. A comment is not part of
    the selector of the rule that follows it, so leaving it in glues the two
    together and the rule stops being found at all -- which is how the first
    version of this helper read every rule that had a comment above it. And a
    rule that has been commented out must not read as a rule that is in force,
    which is the whole difference between reading a stylesheet and searching it
    for a phrase.
    """
    stylesheet = _COMMENT_RE.sub("", stylesheet)
    out = []
    for selector, body in _RULE_RE.findall(stylesheet):
        for piece in body.split(";"):
            if ":" not in piece:
                continue
            prop, _, value = piece.partition(":")
            out.append((selector.strip(), prop.strip().lower(), value.strip()))
    return out


def declarations_for(stylesheet: str, selector: str):
    """What one selector is declared to do, the last rule winning."""
    found = {}
    for rule, prop, value in declarations(stylesheet):
        if selector in [part.strip() for part in rule.split(",")]:
            found[prop] = value
    return found


class PhoneWidthTests(unittest.TestCase):
    """The page at 375 px: nothing scrolls sideways but a table.

    No browser runs in this suite, so nothing here can measure a width. What it
    can do is read the stylesheet as rules -- not search it for a phrase -- and
    require the rules that make the narrow layout. A substring search would be
    satisfied by a commented-out rule, or by a selector that happened to contain
    the words, and would then prove nothing about what the page is told to do.

    Each rule here answers one measured cause of the sideways scroll at 375 px:
    the overview's seven-column grid table and its card spanning two columns of
    a one-column grid, the evidence tree's ``max-content`` key column under a
    long key, the key step's five-column table with its ``nowrap`` number cells,
    the stance view's ``1fr`` track holding a long ``code``, and a fixed footer
    that wraps to three lines under a fixed 74px of bottom padding.
    """

    PHONE = "(max-width: 600px)"

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        page = build.render_html(build.build_document())
        cls.stylesheet = "\n".join(_STYLE_RE.findall(page))
        cls.top = _outside_media(cls.stylesheet)
        cls.script = behaviour_script(page)
        cls.phone = dict(_media_blocks(cls.stylesheet)).get(cls.PHONE, "")

    def test_the_page_carries_a_block_for_a_phone(self):
        self.assertTrue(self.phone, "no " + self.PHONE + " block in the stylesheet")

    def test_every_table_is_built_inside_a_box_that_scrolls_sideways(self):
        """A table cannot reflow to 375px; the box around it can scroll.

        The check is structural rather than a search for a phrase: the script
        builds a table in exactly one place, and that place is the wrapper. A
        sixth table added straight to the page would be a table with no box
        around it, and this test goes red.
        """
        self.assertEqual(
            1, self.script.count('h("table"'),
            "a table is built outside the wrapper that scrolls it sideways",
        )
        self.assertIn("function tableBox(", self.script)
        self.assertEqual(
            "auto",
            declarations_for(self.top, ".table-wrap").get("overflow-x"),
            "the box a table is built into does not scroll sideways",
        )

    def test_the_tracks_that_hold_a_long_key_can_shrink(self):
        """``max-content`` in the first track is what made the evidence step
        820px wide: one long key set the column's width and the page followed
        it. ``minmax(0, max-content)`` lets the column give way instead, and
        ``minmax(0, 1fr)`` does the same for the track beside it."""
        for selector in (".kv", "dl.tree", "dl.keys", "dl.digests"):
            with self.subTest(selector=selector):
                self.assertEqual(
                    "minmax(0, max-content) minmax(0, 1fr)",
                    declarations_for(self.top, selector).get("grid-template-columns"),
                )
        for selector in (".stance-grid", ".prompt-grid"):
            with self.subTest(selector=selector):
                self.assertEqual(
                    "minmax(0, 1fr) minmax(0, 1fr)",
                    declarations_for(self.top, selector).get("grid-template-columns"),
                )

    def test_a_long_id_breaks_rather_than_widening_the_page(self):
        """An evidence id, a clause id and a digest are single unbreakable
        strings. Breaking one is what keeps a 60-character id from setting the
        width of the column it sits in -- and of the page."""
        for selector in (
            "code",
            ".artifact .id",
            ".record-row .id",
            "dl.tree > dt",
            ".digest",
        ):
            with self.subTest(selector=selector):
                self.assertEqual(
                    "anywhere",
                    declarations_for(self.top, selector).get("overflow-wrap"),
                )

    def test_the_phone_block_stops_the_wide_card_and_the_fixed_footer(self):
        """Two of the causes are not about content at all.

        A card that spans two columns of a one-column grid widens the grid, and
        a fixed footer that wraps to three lines covers the text under it
        because the 74px of bottom padding cannot follow its real height. Below
        600px the card takes one column and the footer stops floating.
        """
        self.assertEqual(
            "span 2", declarations_for(self.top, ".card.wide").get("grid-column"),
            "the wide card no longer spans two columns at any width",
        )
        self.assertEqual(
            "auto", declarations_for(self.phone, ".card.wide").get("grid-column"),
        )
        self.assertEqual(
            "static", declarations_for(self.phone, "footer.prov").get("position"),
        )
        self.assertEqual(
            "0", declarations_for(self.phone, "body").get("padding-bottom"),
        )


# ---------------------------------------------------------------------------
# The page for a reader who is not looking at it.
# ---------------------------------------------------------------------------

class _PageScan(HTMLParser):
    """Every start tag on a page, with its attributes.

    The checks that follow are about what the page carries, so they read it the
    way a browser does rather than searching it for a phrase. ``<style>`` and
    ``<script>`` bodies are CDATA to this parser, so a tag written inside a
    string in the script cannot be mistaken for a tag on the page.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def scan_page(text: str) -> _PageScan:
    scan = _PageScan()
    scan.feed(text)
    return scan


def _srgb_to_linear(channel: float) -> float:
    channel = channel / 255.0
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(colour) -> float:
    red, green, blue = [_srgb_to_linear(channel) for channel in colour]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(one, other) -> float:
    """WCAG 2.1 contrast, from 1.0 to 21.0."""
    first, second = relative_luminance(one), relative_luminance(other)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def hex_colour(value: str):
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def over(foreground, background):
    """A translucent colour composited onto an opaque one, as a browser does."""
    red, green, blue, alpha = foreground
    return tuple(
        round(red * alpha + background[index] * (1 - alpha)) for index in range(3)
    )


class AccessibilityTests(unittest.TestCase):
    """What the page tells a reader who is not looking at it.

    No browser runs in this suite, so nothing here can say what a screen reader
    announces. What it can say is what the page *carries*: one heading to
    navigate by, a nav that is named, a current view and a current step that are
    marked current rather than only coloured, two dialogs that say they are
    dialogs, a row that opens a case which a keyboard can reach, a switch that
    gives the single-character shortcuts back, and text that clears the contrast
    floor the rest of the page is held to.

    The static half of the page is parsed rather than searched. The dialogs, the
    rows and the switch are built by the script at run time and no parser can see
    them, so those are read out of the script -- which is the same bytes on all
    five pages, asserted in ``EveryPageIsCommittedTests``.
    """

    @classmethod
    def setUpClass(cls):
        skip_unless_the_run_can_be_drawn()
        cls.documents = built_documents()
        cls.page = build.render_html(cls.documents["corpus"])
        cls.static = cls.page.split('<script id="tribunal-data"', 1)[0]
        cls.scan = scan_page(cls.static)
        cls.stylesheet = "\n".join(_STYLE_RE.findall(cls.page))
        cls.top = _outside_media(cls.stylesheet)
        cls.root = declarations_for(cls.top, ":root")
        cls.script = behaviour_script(cls.page)
        cls.index = build.render_index(cls.documents)

    def tags(self, name):
        return [attrs for tag, attrs in self.scan.tags if tag == name]

    def colour_of(self, selector):
        """A selector's colour, with the page's own custom properties resolved."""
        value = declarations_for(self.top, selector).get("color")
        self.assertIsNotNone(value, selector + " declares no colour")
        match = re.match(r"var\((--[a-z0-9-]+)\)$", value)
        if match:
            value = self.root.get(match.group(1))
            self.assertIsNotNone(value, selector + " uses a property :root never sets")
        return hex_colour(value)

    def test_every_page_has_exactly_one_heading(self):
        """A page with no h1 has no heading to navigate by; a page with two has
        two answers to what the page is."""
        pages = {
            name: build.render_html(document) for name, document in self.documents.items()
        }
        pages["the runs index"] = self.index
        for name, text in sorted(pages.items()):
            with self.subTest(page=name):
                headings = [tag for tag, _ in scan_page(text).tags if tag == "h1"]
                self.assertEqual(
                    1, len(headings),
                    "a page carrying " + str(len(headings)) + " h1 headings",
                )

    def test_the_heading_is_the_page_s_own_brand(self):
        """The one h1 is the brand, so the heading says which run is on screen."""
        headings = self.tags("h1")
        self.assertEqual(1, len(headings))
        self.assertEqual("brand", headings[0].get("class"))
        match = re.search(r'<h1 class="brand">([^<]+)</h1>', self.static)
        self.assertIsNotNone(match, "the brand heading carries no text")
        self.assertEqual(self.documents["corpus"]["set"]["brand"], match.group(1))

    def test_the_views_nav_is_named(self):
        navs = self.tags("nav")
        self.assertEqual(1, len(navs), "the page carries no nav, or more than one")
        self.assertTrue(navs[0].get("aria-label"), "the nav has no accessible name")

    def test_the_current_view_is_marked_current(self):
        """A class is not something a reader who cannot see it is told."""
        buttons = {attrs.get("id"): attrs for attrs in self.tags("button")}
        self.assertEqual(
            "page", buttons["nav-overview"].get("aria-current"),
            "the view that starts on is not marked as the current one",
        )
        for name in ("nav-case", "nav-stance"):
            with self.subTest(button=name):
                self.assertNotIn(
                    "aria-current", buttons[name],
                    "a view that is not on is marked as the current one",
                )
        self.assertIn('button.setAttribute("aria-current", "page")', self.script)
        self.assertIn('button.removeAttribute("aria-current")', self.script)

    def test_the_current_step_is_marked_current(self):
        self.assertIn(
            '"aria-current": index === state.step ? "step" : null', self.script
        )

    def test_the_question_mark_button_is_named(self):
        """The button's visible text is one character, which is not a name."""
        buttons = {attrs.get("id"): attrs for attrs in self.tags("button")}
        self.assertEqual(
            "keyboard shortcuts", buttons["show-keys"].get("aria-label")
        )

    def test_a_row_that_opens_a_case_can_be_opened_from_the_keyboard(self):
        """A ``tr`` with a click handler cannot be reached by tab and is not
        announced as anything a reader can act on, so the number it holds is a
        button and the row handler stays for the pointer."""
        self.assertEqual(
            2, self.script.count('class: "case-open"'),
            "a clickable row has no control in its first cell",
        )
        self.assertIn('"aria-label": "open case " + c.case_no', self.script)
        self.assertIn("event.stopPropagation(); openCase(c.case_no)", self.script)
        self.assertTrue(
            declarations_for(self.top, ".case-open"),
            "the button in the first cell has no rule of its own",
        )

    def test_the_stepper_keeps_the_focus_on_the_control_that_was_used(self):
        """The stepper is rebuilt on every step, so the button that was pressed
        is detached by the time the new step is on screen."""
        for fragment in (
            'id: "step-" + index',
            'id: "step-back"',
            'id: "step-next"',
            'goToStep(index, "step-" + index)',
            'goToStep(state.step + 1, "step-next")',
            'goToStep(state.step - 1, "step-back")',
            "state.focus = token || null",
            "restoreFocus();",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.script)
        # The control can have become disabled -- "next" is, on the last step --
        # and a disabled control cannot take the focus, so the step the reader
        # landed on takes it instead.
        self.assertIn(
            'if (node && node.disabled) { node = document.getElementById("step-" + state.step); }',
            self.script,
        )

    def test_both_dialogs_say_they_are_dialogs(self):
        """The clause overlay and the keys overlay, each opened through the one
        helper that gives the focus out and takes it back.

        The call sites are counted with their semicolon: the helper's own
        signature is the same characters and counting it would let a dialog that
        never goes through the helper pass.
        """
        self.assertEqual(2, self.script.count('role: "dialog"'))
        self.assertEqual(2, self.script.count('"aria-modal": "true"'))
        self.assertEqual(2, self.script.count("openDialog(overlay, box, opener);"))
        self.assertEqual(1, self.script.count("function openDialog(overlay, box, opener)"))
        self.assertIn("box.focus()", self.script)
        self.assertIn("state.modalOpener = opener || document.activeElement", self.script)
        self.assertIn("giveBackTheFocus()", self.script)

    def test_escape_closes_a_dialog(self):
        self.assertIn(
            'if (event.key === "Escape") { closeHelp(); closeModal(); event.preventDefault(); }',
            self.script,
        )

    def test_the_setting_is_shown_in_the_dialog_that_lists_the_keys(self):
        """The switch belongs beside the list it governs, not somewhere else on
        the page."""
        dialog = self.script.split("function renderHelp(", 1)[1].split(
            "function closeHelp(", 1
        )[0]
        for fragment in ('id: "single-keys"', 'class: "keys"', '"aria-modal": "true"'):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, dialog)

    def test_the_single_key_shortcuts_can_be_turned_off(self):
        """WCAG 2.1.4. Every shortcut on this page is one character, so a reader
        using speech input is otherwise competing with the page for letters."""
        self.assertIn("singleKeys: true", self.script)
        self.assertIn("key.length === 1 && !state.singleKeys", self.script)
        self.assertIn('id: "single-keys-state"', self.script)
        self.assertIn('state.singleKeys ? "on" : "off"', self.script)

    def test_the_escalation_table_has_no_empty_header(self):
        """A ``th`` with no text is a column a reader is not told the name of."""
        self.assertNotIn('h("th", { text: "" })', self.script)
        self.assertIn('h("th", { text: "Measure" })', self.script)

    def test_nothing_on_the_page_is_smaller_than_twelve_pixels(self):
        """11px of monospace on a phone is text that has to be zoomed to be
        read."""
        sizes = [
            (selector, value)
            for selector, prop, value in declarations(self.stylesheet)
            if prop == "font-size"
        ]
        self.assertTrue(sizes, "the stylesheet declares no font size at all")
        for selector, value in sizes:
            with self.subTest(selector=selector, value=value):
                self.assertRegex(
                    value, r"^\d+(\.\d+)?px$",
                    "a size that is not in px cannot be held to a floor",
                )
                self.assertGreaterEqual(float(value[:-2]), 12.0)
        for selector, prop, value in declarations(self.stylesheet):
            if prop != "font":
                continue
            match = re.match(r"(\d+(?:\.\d+)?)px", value)
            if match:
                with self.subTest(selector=selector, shorthand=value):
                    self.assertGreaterEqual(float(match.group(1)), 12.0)

    def test_the_floor_check_catches_a_size_that_is_too_small(self):
        """The control for the test above: run over a stylesheet that still
        carries one of the sizes it replaced."""
        with self.assertRaises(AssertionError):
            for selector, prop, value in declarations("x { font-size: 11.5px; }"):
                if prop == "font-size":
                    self.assertGreaterEqual(float(value[:-2]), 12.0)

    def test_the_two_lowest_contrast_rules_clear_the_floor(self):
        """The line number down a rendered prompt, and the word the page writes
        where the run produced no value.

        Both are text and both were below 4.5:1. The line number measured
        2.87:1 on the plain column and 1.95:1 on the amber highlight of a
        differing line; the null measured 4.28:1 on a panel and 3.63:1 in a miss
        row. The backgrounds below are every one each rule can sit on, the
        translucent washes composited the way a browser composites them.
        """
        page = hex_colour("0e1116")
        panel = hex_colour("161c23")
        panel_2 = hex_colour("1c242d")
        cases = {
            ".plines li .n": [
                panel_2,
                over((121, 192, 255, 0.05), panel_2),
                over((216, 167, 42, 0.15), panel_2),
            ],
            ".null": [
                page,
                panel,
                panel_2,
                over((255, 107, 107, 0.09), panel),
                over((255, 107, 107, 0.16), panel),
                over((255, 107, 107, 0.06), panel),
                over((216, 167, 42, 0.07), panel),
                over((157, 171, 185, 0.05), panel_2),
            ],
        }
        for selector, backgrounds in cases.items():
            colour = self.colour_of(selector)
            for background in backgrounds:
                with self.subTest(selector=selector, background=background):
                    self.assertGreaterEqual(
                        round(contrast_ratio(colour, background), 2),
                        4.5,
                        selector + " is below the contrast floor on " + str(background),
                    )

    def test_the_contrast_floor_would_have_caught_the_colours_it_replaced(self):
        """The control for the test above: the two colours it replaced, measured
        the same way, are below the floor."""
        panel = hex_colour("161c23")
        panel_2 = hex_colour("1c242d")
        self.assertLess(
            round(contrast_ratio(hex_colour("5d6b78"), over((216, 167, 42, 0.15), panel_2)), 2),
            4.5,
        )
        self.assertLess(
            round(contrast_ratio(hex_colour("7b8794"), over((255, 107, 107, 0.09), panel)), 2),
            4.5,
        )


# --------------------------------------------------------------------------
# The page script, executed
#
# Every test above reads the page. This section runs it.
#
# The distinction matters because the defect it was written for is invisible to
# reading: ``ui/build.py --check`` compares bytes, ``CommittedPageTests``
# compares bytes, and the source-text guards look for a phrase. A page whose
# ``renderOverview`` throws on load still builds, still compares byte for byte,
# and still contains every phrase a substring test would look for. The only
# thing that can see it is a script that runs.
#
# There is no browser in this suite, so the page is run under a minimal DOM in
# ``tests/support/dom_shim.js``: no npm package, no network, and an
# ``appendChild`` that throws on a non-node exactly as a browser's does.
# --------------------------------------------------------------------------

# The interpreter the harness runs under. The sheet names the first; the second
# is whatever ``node`` is on the PATH, so the suite still runs where node was
# installed some other way.
NODE_CANDIDATES = ("/usr/local/bin/node",)

# The DOM the page script is run against.
DOM_SHIM = PROJECT_ROOT / "tests" / "support" / "dom_shim.js"

# The page's data block and its stepper, both read out of the page rather than
# typed here. A page that grew a seventh step would otherwise be walked as far as
# the sixth and no further.
DATA_PATTERN = re.compile(
    r'<script id="tribunal-data" type="application/json">(.*?)</script>', re.S
)
STEPS_PATTERN = re.compile(r"var STEPS = \[(.*?)\];", re.S)

# The cases each page is walked over.
CASES_PER_PAGE = 3


def node_executable() -> Optional[str]:
    """The node that will run the shim, or ``None`` when there is not one.

    Absent is not a pass: the caller skips with the reason, so a machine without
    node reports the gap rather than a green run that proved nothing.
    """
    for candidate in NODE_CANDIDATES:
        if os.access(candidate, os.X_OK):
            return candidate
    return shutil.which("node")


def page_document(html: str) -> dict:
    """The document one page carries, as the page itself reads it."""
    match = DATA_PATTERN.search(html)
    if match is None:
        raise AssertionError("the page carries no data block")
    return json.loads(match.group(1))


def step_count(script: str) -> int:
    """How many steps the page's own stepper has."""
    match = STEPS_PATTERN.search(script)
    if match is None:
        raise AssertionError("the script has no STEPS list to walk")
    count = len(re.findall(r"\{\s*id:", match.group(1)))
    if count < 1:
        raise AssertionError("the STEPS list names no step")
    return count


def cases_to_walk(name: str, document: dict, wanted: int = CASES_PER_PAGE) -> list:
    """The cases to walk on one page: every miss it has, up to ``wanted``.

    The miss line is the only place the page hands a plain string to
    ``appendChild``, so the cases that reach it are the ones worth walking: they
    are where this class of defect lives. A page with fewer misses than
    ``wanted`` is topped up from its own case list, so every page is walked over
    three cases rather than only the pages that missed.

    ``wild`` is asked for 517 as well. It is the case the sheet names -- a miss
    that produced no ruling at all -- and it is the state the page has least
    practice drawing: no ruling, no clause, no amount.
    """
    cases = document.get("cases") or []
    chosen = [
        case["case_no"]
        for case in cases
        if (case.get("grading") or {}).get("exact") is False
    ][:wanted]
    if name == "wild" and 517 not in chosen:
        chosen.append(517)
    for case in cases:
        if len(chosen) >= wanted:
            break
        if case["case_no"] not in chosen:
            chosen.append(case["case_no"])
    return chosen


def targets_for(name: str, document: dict, script: str) -> list:
    """Every view the harness renders on one page, in order."""
    steps = step_count(script)
    chosen = cases_to_walk(name, document)
    targets = [
        {"view": "case", "case": case_no, "step": step}
        for case_no in chosen
        for step in range(1, steps + 1)
    ]
    targets.append({"view": "stance", "case": chosen[0]})
    return targets


def run_the_shim(pages: list) -> dict:
    """Run the shim over ``pages`` and return its report.

    A job file and a temporary directory rather than a command line, because a
    page's data block is megabytes and an argument list is not where megabytes
    belong.
    """
    node = node_executable()
    if node is None:
        raise AssertionError("no node to run the shim with")
    with tempfile.TemporaryDirectory() as scratch:
        job = Path(scratch) / "job.json"
        job.write_text(json.dumps({"pages": pages}), encoding="utf-8")
        done = subprocess.run(
            [node, str(DOM_SHIM), str(job)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
    if done.returncode != 0:
        raise AssertionError(
            "the shim exited {0}:\n{1}".format(done.returncode, done.stderr[-4000:])
        )
    return json.loads(done.stdout)


class PageScriptRunsTests(unittest.TestCase):
    """The page script is executed against a minimal DOM.

    Every other test in this file reads the page as text, and a defect that only
    shows when the script runs is invisible to all of them. This class runs it:
    for every page under ``ui/dist/`` it loads the page's own data block and its
    own behaviour script into ``tests/support/dom_shim.js`` and renders the views.

    What is rendered is chosen from the page rather than typed here. The three
    cases are the page's own misses -- the miss line is where a plain string was
    handed to ``appendChild`` -- topped up from the page's case list so every
    page is walked over three, and ``wild`` is walked over 517 as well because
    the sheet names it. Every step of each case is rendered, and then the stance
    view.

    The overview is rendered by the load itself, so it is measured rather than
    driven: the shim reports how many children ``renderOverview`` built, and a
    load that threw part-way leaves that short and sets ``load_error``.

    **The shim throws on a string, as a browser does**, which is what makes the
    first test able to fail at all. ``test_the_harness_can_fail`` shows that it
    does.
    """

    @classmethod
    def setUpClass(cls):
        if node_executable() is None:
            raise unittest.SkipTest(
                "node is not installed, so the page script cannot be run: tried "
                + ", ".join(NODE_CANDIDATES)
                + " and node on the PATH"
            )
        cls.relative = sorted(
            str(path.relative_to(build.DIST_DIR))
            for path in build.DIST_DIR.rglob("*.html")
        )
        cls.html = {}
        cls.script = {}
        cls.document = {}
        cls.targets = {}
        for relative in cls.relative:
            text = (build.DIST_DIR / relative).read_text(encoding="utf-8")
            cls.html[relative] = text
            if "<script>" not in text:
                continue
            cls.script[relative] = behaviour_script(text)
            cls.document[relative] = page_document(text)
            cls.targets[relative] = targets_for(
                cls.name_of(relative), cls.document[relative], cls.script[relative]
            )

    @staticmethod
    def name_of(relative: str) -> str:
        """The set a page belongs to, from the path it sits at."""
        return "corpus" if relative == "index.html" else relative.split("/")[0]

    def test_every_page_under_ui_dist_is_accounted_for(self):
        """The five viewer pages, and the runs index beside them.

        The index is static -- it links to the pages and carries no data of its
        own -- so there is nothing in it to run. That is asserted rather than
        assumed, because a page that quietly stopped carrying a script would
        otherwise be a page this class silently stopped covering.
        """
        self.assertEqual(
            [
                "codex/index.html",
                "index.html",
                "runs/index.html",
                "ryde-901/index.html",
                "wild-v2/index.html",
                "wild/index.html",
            ],
            self.relative,
        )
        self.assertEqual(
            [
                "codex/index.html",
                "index.html",
                "ryde-901/index.html",
                "wild-v2/index.html",
                "wild/index.html",
            ],
            sorted(self.script),
        )

    def test_the_pages_run_without_throwing(self):
        """The point of the class: nothing throws, on any page, in any view."""
        jobs = [
            {
                "name": self.name_of(relative),
                "path": str(build.DIST_DIR / relative),
                "targets": self.targets[relative],
            }
            for relative in sorted(self.script)
        ]
        report = run_the_shim(jobs)
        self.assertEqual(
            [job["name"] for job in jobs],
            [page["name"] for page in report["pages"]],
        )
        for job, page in zip(jobs, report["pages"]):
            with self.subTest(page=page["name"]):
                self.assertIsNone(
                    page["load_error"],
                    "the page threw while it was loading: "
                    + str(page["load_error"]),
                )
                self.assertGreater(
                    page["overview_children"],
                    0,
                    "the overview rendered nothing",
                )
                self.assertEqual(
                    [],
                    page["exceptions"],
                    "a view threw: " + json.dumps(page["exceptions"]),
                )
                self.assertEqual(len(job["targets"]), page["rendered"])

    def test_the_walk_covers_the_cases_the_sheet_names(self):
        """The walk is over the misses, and over ``wild`` 517 by name.

        A page with fewer cases than the walk asks for is walked over the cases
        it has: ``ryde-901`` is one case. ``wild`` is one longer than the others,
        because 517 is asked for by name.
        """
        for relative in sorted(self.script):
            name = self.name_of(relative)
            cases = self.document[relative].get("cases") or []
            chosen = cases_to_walk(name, self.document[relative])
            misses = [
                case["case_no"]
                for case in cases
                if (case.get("grading") or {}).get("exact") is False
            ]
            with self.subTest(page=name):
                self.assertEqual(
                    misses[:CASES_PER_PAGE], chosen[: len(misses[:CASES_PER_PAGE])]
                )
                self.assertEqual(
                    min(CASES_PER_PAGE, len(cases)) + (1 if name == "wild" else 0),
                    len(chosen),
                )
                if name == "wild":
                    self.assertIn(517, chosen)
                self.assertEqual(
                    len(chosen) * step_count(self.script[relative]) + 1,
                    len(self.targets[relative]),
                )

    def test_the_harness_can_fail(self):
        """The control: a page that hands ``appendChild`` a string is caught.

        Without this the class above could pass because the shim accepts
        anything. The page is written here rather than mutated out of a real one,
        so the control does not depend on which line of the real script happens
        to run first: it is the defect in miniature -- the same call, the same
        argument type, the same throw.
        """
        control = (
            '<!DOCTYPE html>\n<html lang="en">\n<head><meta charset="utf-8">'
            "<title>control</title></head>\n<body>\n"
            '<section id="view-overview"></section>\n'
            '<script id="tribunal-data" type="application/json">{"cases": []}'
            "</script>\n<script>\n"
            "(function () {\n"
            '  document.getElementById("view-overview").appendChild("text");\n'
            "})();\n"
            "</script>\n</body>\n</html>\n"
        )
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "control.html"
            path.write_text(control, encoding="utf-8")
            report = run_the_shim(
                [
                    {
                        "name": "control",
                        "path": str(path),
                        "targets": [{"view": "overview"}],
                    }
                ]
            )
        page = report["pages"][0]
        self.assertIsNotNone(
            page["load_error"], "a page that throws on load was called fine"
        )
        self.assertIn("appendChild", page["load_error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
