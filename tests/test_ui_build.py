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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import grade  # noqa: E402
from tribunal import brief  # noqa: E402
from ui import build  # noqa: E402

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


class CommittedPageTests(unittest.TestCase):
    """The committed page is the one this code builds, and it is one file."""

    @classmethod
    def setUpClass(cls):
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
        cls.document = build.build_document()
        cls.cases = {case["case_no"]: case for case in cls.document["cases"]}

    def test_every_case_in_the_run_is_present(self):
        numbers = build.cached_cases(build.RUN_DIR)
        self.assertEqual(29, len(numbers), "the headline run holds 29 cases")
        self.assertEqual(numbers, sorted(self.cases))
        self.assertEqual([], self.document["refused_cases"])

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

    def test_the_single_miss_is_shown_as_a_miss(self):
        misses = sorted(
            case_no for case_no, case in self.cases.items() if not case["grading"]["exact"]
        )
        self.assertEqual([211], misses, "the run has one four-field miss and it is 211")

        case = self.cases[211]
        self.assertEqual("PARTIAL_REFUND", case["expected"]["ruling"])
        self.assertEqual("ESCALATE", case["judge"]["verdict"]["ruling"])
        self.assertEqual(["ruling", "amount_sgd"], case["grading"]["failed_fields"])
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
        self.assertEqual(500, claims, "the run's two advocates made 500 claims")

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


class HeadlineTests(unittest.TestCase):
    """The figures are computed, and they are the grader's own figures."""

    @classmethod
    def setUpClass(cls):
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
        self.assertEqual(37, total, "the run's judges discarded 37 claims")

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
        run_dir = root / "run"
        run_dir.mkdir()
        for name in ("run.json", "invocations.json"):
            shutil.copy2(build.RUN_DIR / name, run_dir / name)
        for case_no in (self.ALTERED, self.ADMITTED):
            for suffix in (".json", ".transcript.json"):
                shutil.copy2(
                    build.RUN_DIR / ("case-%05d%s" % (case_no, suffix)),
                    run_dir / ("case-%05d%s" % (case_no, suffix)),
                )
        return run_dir

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
