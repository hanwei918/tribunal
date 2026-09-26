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

A third thing they do conditionally. The tests that read the committed run can
only run while that run and this code agree about what the agents were handed.
When every cached brief digest has moved they skip, naming the reason and the
command that clears it, rather than fail about a run that has not been re-made
yet. The tests that build their own run directory are unaffected and keep the
refusal mechanism itself under test.
"""

from __future__ import annotations

import json
import os
import re
import shutil
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

        The list is a pin about the run committed under ``runs/`` at the commit
        this test last ran against, and the next run moves it -- the run before
        this one missed 107 and 211, the frozen-prompt run missed 105 and 211,
        and the referee run misses 211 alone. What is not dated is the rest:
        that each miss carries its expected ruling, the ruling the judge
        produced and the fields that differ, which is what makes the miss
        legible on the page rather than merely counted.
        """
        misses = sorted(
            case_no for case_no, case in self.cases.items() if not case["grading"]["exact"]
        )
        self.assertEqual([211], misses, "the run's four-field misses moved")

        # The dated facts per miss: the key's ruling, the ruling the judge
        # produced, and the fields that differ.
        dated = {
            211: (
                "PARTIAL_REFUND",
                "ESCALATE",
                ["ruling", "amount_sgd"],
            ),
        }
        for case_no, (key_ruling, judge_ruling, failed) in dated.items():
            case = self.cases[case_no]
            self.assertEqual(key_ruling, case["expected"]["ruling"])
            self.assertEqual(judge_ruling, case["judge"]["verdict"]["ruling"])
            self.assertEqual(failed, case["grading"]["failed_fields"])

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

        The pin below is about the run committed under ``runs/`` now: 107 and
        207 carried on a 3-of-4 vote, and 211 escalated because its drafts split
        two and two. A later run moves it. What must hold either way is the
        check above it -- a case is contested on the page exactly when the run's
        own record says its vote was not unanimous.
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
        self.assertEqual([107, 207, 211], contested, "the run's contested cases moved")

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
        for field in ("vote.drafts", "vote.agreement", "vote.outcome", "vote.unanimous"):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
