"""Tests for ``ui.v2``: the product view -- the site's front door -- and its pages.

No network, no browser, no credential, no model call. The product view is the
site's root now (``ui/dist/index.html`` and ``ui/dist/case-<NNNNN>.html``), and
the evaluation replay ``ui.build`` writes lives beside it under
``ui/dist/replay/``. What is under test is the properties the sheet names, and
each is checked against the files the pages were built from rather than against
a number typed in here:

* ``--check`` passes, and two builds are byte-identical;
* no page contains ``fetch(``, an external ``src=`` or ``href=``, ``<link``, a
  web font, or a non-ASCII byte;
* no page names a sealed-v1 case number (301 to 312, 401 to 412) or reads a
  sealed path;
* for every case page, the ruling, the two amounts and the confidence shown
  equal the case file's;
* the queue's figures equal what the run files give, and its three routing
  counts equal ``eval.business_value``'s;
* every case page carries the dispute, and a no-show case carries the record's
  own derived facts;
* the notice to the parties is on every page, names no profile field, and its
  clause and evidence lines say only what the ruling rests on;
* the four featured cards show the run's own facts, and no key-figure tile shows
  a fact the case's derived block does not carry;
* the trace SVG draws the fixes and never draws the optimal route;
* the replay's own links resolve, and every replay page links back to the queue;
* a case sent to a reviewer has the "Human review" tab and its packet sha256
  equals ``ops.escalation``'s, and a decided case has no such tab;
* the closing command the review form builds is one ``ops.review`` accepts and
  stores -- for 213 a VARY of ``FULL_REFUND 6.0`` citing ``POL-GEN-07``, for 107
  an ADOPT carrying the panel's own ``PARTIAL_REFUND 7.45``, and an escalated
  case with nothing to adopt has ADOPT disabled;
* the appeal text matches ``POL-GEN-04``'s rule text;
* every rule that paints the accent as a background and sets a colour uses
  ``--on-accent``, and no rule pairs white with a token background that changes
  between the themes -- the tokens that are legible on either are named;
* the queue's held note is capped so the table fits its wrapper on a desktop
  screen, and the three lane tiles carry ``lane-*`` classes rather than the
  bare status names the stylesheet's global rules also match;
* a reviewer's queue row shows the short chip and its trigger words wrap under
  it, no chip in the queue is longer than the four short labels, and the case
  page's header keeps the long chip;
* the queue's safeguards section names the seven safeguards in order, its
  reviewer figure is the lane tile's own, its two case links resolve inside the
  site, and it carries no script.

**The suite builds the site five times and says why.** A build reads 151 cases,
rebuilds each case's brief and builds 26 escalation packets, which is about
forty seconds; the first class compares the committed pages with a fresh build
(that is what ``--check`` does), the second compares two builds with each other,
the third runs the command line the owner will run, and the fourth runs two
builds in subprocesses under two different ``PYTHONHASHSEED`` values and compares
them, because a row order that depended on a set or a dict would change its bytes
when the interpreter's string hash seed changed. Each class memoises what it
read, so no test builds the site for itself.

**A platform that cannot rebuild case 111's brief skips the tests that build.**
The builder rebuilds every case's brief and holds it against the digest the run
recorded, refusing the case rather than drawing a regenerated brief; on a
platform whose libm rounds that case's mean distance one unit in the last place
differently, the site cannot be built at all. Every test here that builds says
so and skips, naming the case and the last place; the tests that only read the
committed pages keep running.

Two things these tests deliberately do not do. They do not search a page for the
text ``http`` to prove it loads nothing external -- the agents' own explanations
discuss URLs as ordinary prose, and a substring search would either fail on
legitimate text or be weakened until it passed on anything; the page is parsed
instead and its resource attributes are asserted. And they do not assert the
queue's figures against numbers typed in here: the figures are recomputed from
the run directories, so the test compares two computations rather than one
computation against a memory.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import v6_runs  # noqa: E402
from ops import appeal as appeal_module  # noqa: E402
from ops import escalation  # noqa: E402
from ops import review as review_module  # noqa: E402
from tests import portability  # noqa: E402
from tribunal import pipeline as pipeline_module  # noqa: E402
from tribunal import referee as referee_module  # noqa: E402
from ui.v2 import build as v2  # noqa: E402

# The four runs the site is drawn from, and the case root each set loads through.
# The order is the builder's own set order -- the order the set selector lists the
# sets in, and the order the queue's rows are written in -- so a test that reads
# the runs here reads them in the order the page does.
# ``DeterminismTests.test_the_run_order_is_the_builders_own`` holds the two
# together, because an order that drifted apart from the builder's is exactly
# what made the two determinism tests disagree about the row order.
SET_RUNS: Tuple[Tuple[str, str], ...] = (
    ("corpus", "runs/policy-v6/deepseek-deepseek-flash"),
    ("dev-v2-ext", "runs/dev-v2-ext/policy-v6/deepseek-deepseek-flash"),
    ("ryde-v3", "runs/ryde-v3/policy-v6/deepseek-deepseek-flash"),
    ("dev-v2", "runs/dev-v2/policy-v6/deepseek-deepseek-flash"),
)

CASE_ROOTS: Mapping[str, str] = {
    "corpus": "data/cases",
    "dev-v2-ext": "data/external/dev-v2-ext",
    "dev-v2": "data/external/dev-v2",
    "ryde-v3": "data/external/ryde-v3",
}

# The sealed-v1 set's own case numbers, as the sheet states them. They are typed
# here rather than read from the set's index: the point of the check is that this
# code names no sealed path, and a test that opened one to learn them would be
# the thing it is testing against.
SEALED_V1_CASES: Tuple[int, ...] = tuple(range(301, 313)) + tuple(range(401, 413))

# The three roots nothing here may read.
SEALED_ROOTS: Tuple[Path, ...] = (
    PROJECT_ROOT / "eval" / "answers" / "sealed-v1",
    PROJECT_ROOT / "data" / "external" / "sealed-v1",
    PROJECT_ROOT / "eval" / "external" / "sealed-v1",
)

CASE_FILE_RE = re.compile(r"^case-(\d{5})\.json$")
TRANSCRIPT_RE = re.compile(r"^case-(\d{5})\.transcript\.json$")

# The four escalation reason codes, as the builder derives them. The first two
# are the pipeline's own named codes; the other two are the names the builder
# gives the two remaining triggers, which the pipeline records only through the
# vote's outcome and the ruling value.
TRIGGERS = ("GEN08_SCOPE", "NO_VALID_DRAFTS", "NO_MAJORITY", "JUDGE_ESCALATE")

# The links off the site, as the pages write them. The first is the queue's
# results line, and until part 48 it was the repository-relative path
# ``../../README.md#results``: a path out of ``ui/dist/`` that resolved in a
# checkout and 404s wherever the site is served on its own, so the
# inside-the-site link check had to name it as an exception. It is the
# repository's own page on GitHub now -- an absolute URL, which resolves nowhere
# in a checkout and therefore needs no exception. The three after it are the
# safeguards section's: the repository's privacy note, the limits section of its
# README and the note recording the accessibility scan, each a page the site
# does not carry and each written in full rather than as a path that would 404.
# This is the set the external-reference check expects a page to carry. Every
# other link a built page carries is a file inside ``ui/dist/``, and is checked
# as one.
EXTERNAL_LINKS: FrozenSet[str] = frozenset(
    {
        v2.README_RESULTS_LINK,
        v2.PRIVACY_LINK,
        v2.LIMITATIONS_LINK,
        v2.ACCESSIBILITY_NOTE_LINK,
    }
)

# The files this site carries that are not pages: the four architecture views,
# the link-preview image and the front page's poster, each copied into
# ``ui/dist/`` byte for byte, and the repository file the committed copy must
# equal. A link to one of these stays inside the site, which is the point of
# copying it in.
SITE_ASSETS: Mapping[str, Path] = {
    v2.architecture_link(view): v2.ARCHITECTURE_SOURCE_DIR / view
    for view, _label in v2.ARCHITECTURE_VIEWS
}
SITE_ASSETS[v2.OG_IMAGE_LINK] = v2.OG_IMAGE_SOURCE
SITE_ASSETS[v2.COVER_LINK] = v2.COVER_SOURCE

# The same six, as the paths on disk, so the walk that compares the committed
# pages with a fresh build can skip the files it copied in rather than built.
SITE_ASSET_PATHS = frozenset(
    {v2.ARCHITECTURE_ASSET_DIR / view for view, _label in v2.ARCHITECTURE_VIEWS}
    | {v2.OG_IMAGE_ASSET, v2.COVER_ASSET}
)


# --------------------------------------------------------------------------
# Reading the run files
# --------------------------------------------------------------------------
def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)


def run_directories() -> List[Tuple[str, Path]]:
    return [(name, PROJECT_ROOT / relative) for name, relative in SET_RUNS]


def case_numbers(run_dir: Path) -> List[int]:
    found = []
    for name in sorted(os.listdir(run_dir)):
        match = CASE_FILE_RE.match(name)
        if match is not None:
            found.append(int(match.group(1)))
    return sorted(found)


def transcript_of(run_dir: Path, case_no: int) -> Mapping[str, Any]:
    return read_json(run_dir / "case-{0:05d}.transcript.json".format(case_no))


def public_case(set_name: str, case_no: int) -> Mapping[str, Any]:
    return read_json(PROJECT_ROOT / CASE_ROOTS[set_name] / "case-{0:05d}.json".format(case_no))


def inner_ruling(document: Mapping[str, Any]) -> Mapping[str, Any]:
    return (document.get("ruling") or {}).get("ruling") or {}


def money(value: Any, currency: str) -> str:
    if value is None or isinstance(value, bool):
        return "none"
    return "{0} {1:.2f}".format(currency, Decimal(str(value)))


def currency_of(case: Mapping[str, Any]) -> str:
    """The currency the loaded policy states, read from the policy file."""
    del case
    return str(read_json(PROJECT_ROOT / "policy" / "v3" / "general.json")["currency"])


def trigger_of(set_name: str, run_dir: Path, case_no: int, document: Mapping[str, Any]) -> Optional[str]:
    """Why a case went to a reviewer, recomputed from the run's own record."""
    if inner_ruling(document).get("ruling") != "ESCALATE":
        return None
    dispute = public_case(set_name, case_no).get("dispute") or {}
    if dispute.get("safety_flag") is True or dispute.get("complaint_flag") is True:
        return "GEN08_SCOPE"
    outcome = (transcript_of(run_dir, case_no).get("vote") or {}).get("outcome")
    if outcome == "no_valid_drafts":
        return "NO_VALID_DRAFTS"
    if outcome == "escalated":
        return "NO_MAJORITY"
    return "JUDGE_ESCALATE"


def tokens_of(run_dir: Path, case_no: int) -> Tuple[int, int, int]:
    prompt = cached = completion = 0
    for entry in transcript_of(run_dir, case_no).get("entries") or []:
        prompt += int(entry.get("prompt_tokens") or 0)
        cached += int(entry.get("cached_tokens") or 0)
        completion += int(entry.get("completion_tokens") or 0)
    return prompt, cached, completion


def monetary_effect(ruling: Mapping[str, Any]) -> Decimal:
    """The money one ruling moves, read the way ``POL-GEN-05`` reads it.

    POL-GEN-03 states the one exception: on a ``DRIVER_COMPENSATION`` ruling
    ``amount_sgd`` carries the same figure as ``driver_compensation_sgd``, and
    it is the amount the ruling moves rather than a second payment, so it is
    counted once. On every other ruling the two are independent and are added.
    """

    def value(cell: Any) -> Decimal:
        if cell is None or isinstance(cell, bool):
            return Decimal(0)
        return Decimal(str(cell))

    amount = value(ruling.get("amount_sgd"))
    driver = value(ruling.get("driver_compensation_sgd"))
    if ruling.get("ruling") == "DRIVER_COMPENSATION" and driver:
        return driver
    return amount + driver


def execution_threshold() -> Decimal:
    """POL-GEN-05's own figure, read from the policy file the pages quote."""
    general = read_json(PROJECT_ROOT / "policy" / "v3" / "general.json")
    return Decimal(str(general["execution_threshold_sgd"]))


def cost_of(run_dir: Path, case_no: int) -> Decimal:
    prompt, cached, completion = tokens_of(run_dir, case_no)
    return (
        Decimal(prompt - cached) * v6_runs.PRICE_INPUT
        + Decimal(cached) * v6_runs.PRICE_CACHED_INPUT
        + Decimal(completion) * v6_runs.PRICE_OUTPUT
    ) / v6_runs.MILLION


def median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def every_case() -> List[Dict[str, Any]]:
    """Every case of the four runs, read from the run files."""
    rows: List[Dict[str, Any]] = []
    for set_name, run_dir in run_directories():
        for case_no in case_numbers(run_dir):
            document = read_json(run_dir / "case-{0:05d}.json".format(case_no))
            rows.append(
                {
                    "set": set_name,
                    "case_no": case_no,
                    "run_dir": run_dir,
                    "document": document,
                    "trigger": trigger_of(set_name, run_dir, case_no, document),
                }
            )
    return rows


_CASES: Optional[List[Dict[str, Any]]] = None
_PAGES: Optional[Dict[str, str]] = None
_SECOND_BUILD: Optional[Dict[str, str]] = None
_GUARD: Optional["_ReadGuard"] = None
_LOADED: Optional[List[Any]] = None


def cases() -> List[Dict[str, Any]]:
    global _CASES
    if _CASES is None:
        _CASES = every_case()
    return _CASES


def relative(path: Path) -> str:
    return path.relative_to(v2.DIST_DIR).as_posix()


def built_pages() -> Dict[str, str]:
    """Every page, built once for the whole test process.

    The read is instrumented: every file the build opens is recorded, so the
    sealed-path test asks about the build that actually happened rather than
    about a second one run beside it.
    """
    global _PAGES, _GUARD, _LOADED
    if _PAGES is None:
        portability.require_the_same_libm()
        guard = _ReadGuard()
        with guard:
            loaded = [
                v2._load_case(case["set"], case["case_no"]) for case in cases()
            ]
            pages: Dict[str, str] = {
                relative(v2.INDEX_PATH): v2.build_index(loaded),
                relative(v2.NOT_FOUND_PATH): v2.build_not_found(loaded),
            }
            for data in loaded:
                pages[relative(v2.DIST_DIR / data.link)] = v2.build_case_page(data)
        _LOADED = loaded
        _GUARD = guard
        _PAGES = pages
    return _PAGES


def loaded_cases() -> List[Any]:
    """The cases the one build read, as ``ui.v2``'s own data objects.

    Kept from the build the other tests use rather than loaded a second time, so
    a test about a derived fact reads the same object the page was built from.
    """
    built_pages()
    assert _LOADED is not None
    return _LOADED


def loaded_case(case_no: int) -> Any:
    for data in loaded_cases():
        if data.case_no == case_no:
            return data
    raise AssertionError("case {0} is not one of the runs".format(case_no))


def read_guard() -> "_ReadGuard":
    built_pages()
    assert _GUARD is not None
    return _GUARD


def second_build() -> Dict[str, str]:
    """A second, independent build, for the byte-identity check."""
    global _SECOND_BUILD
    if _SECOND_BUILD is None:
        portability.require_the_same_libm()
        _SECOND_BUILD = {relative(path): text for path, text in v2.pages()}
    return _SECOND_BUILD


# The script the hash-seed check runs in each subprocess. It builds the site and
# prints one sha256 per page, so the two subprocesses' bytes are compared without
# a multi-megabyte pipe: two pages with the same digest are the same bytes.
_HASH_SEED_SCRIPT = (
    "import hashlib, json, sys\n"
    "from ui.v2 import build\n"
    "pages = {}\n"
    "for path, text in build.pages():\n"
    "    pages[path.name] = hashlib.sha256(text.encode('utf-8')).hexdigest()\n"
    "sys.stdout.write(json.dumps(pages, sort_keys=True))\n"
)


def build_under_hash_seed(seed: str) -> Dict[str, str]:
    """One page digest per page, from a build in a process of its own.

    ``PYTHONHASHSEED`` salts every string hash in that process, so a build whose
    output depended on a set or a dict -- or on the order a directory listing
    came back in -- would come back with different digests under two seeds.
    """
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = seed
    done = subprocess.run(
        [sys.executable, "-c", _HASH_SEED_SCRIPT],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        env=environment,
    )
    if done.returncode != 0:
        raise AssertionError(
            "a build under PYTHONHASHSEED={0} failed:\n{1}".format(
                seed, done.stderr[-4000:]
            )
        )
    return json.loads(done.stdout)


# The replay's directory name, taken from the builder's own link to it, so this
# walk cannot drift from where the builder says the replay lives.
REPLAY_DIR = Path(v2.REPLAY_INDEX).parts[0]


def committed_pages() -> Dict[str, str]:
    """This site's committed pages: the root, and not the replay beside it.

    The evaluation replay is a second site under ``replay/``, built by
    ``ui.build`` and committed under the same root, so the walk skips it: a
    comparison that read it would hold this builder to another one's bytes. The
    files this builder copies in rather than renders -- the architecture diagram
    and the link-preview image -- are skipped too: they are bytes, and the two
    checks that they equal the repository's own file are their own tests.
    """
    return {
        path.relative_to(v2.DIST_DIR).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(v2.DIST_DIR.rglob("*"))
        if path.is_file()
        and path not in SITE_ASSET_PATHS
        and REPLAY_DIR not in path.relative_to(v2.DIST_DIR).parts
    }


def index_text() -> str:
    return built_pages()[relative(v2.INDEX_PATH)]


def _summary_pieces(chosen: str) -> List[str]:
    """The paragraphs the ruling panel shows, with the pipeline's draft list out.

    It mirrors ``ui.v2.build._panel_summary``: the pipeline writes the panel's
    drafts into its escalation explanation as one line each, the page draws that
    list as a table, and the sentence around it is shown verbatim. The pieces
    returned here are what a reader meets as paragraphs.
    """
    lead: List[str] = []
    tail: List[str] = []
    listed = False
    for line in chosen.split("\n"):
        if v2.DRAFT_LINE_RE.match(line.strip()):
            listed = True
            continue
        (tail if listed else lead).append(line)
    pieces: List[str] = []
    for block in (lead, tail):
        text = "\n".join(block).strip()
        pieces.extend(part for part in text.split("\n\n") if part.strip())
    return pieces


# --------------------------------------------------------------------------
# The pages are what this code builds, and this code builds the same bytes twice
# --------------------------------------------------------------------------
class DeterminismTests(unittest.TestCase):
    """The committed bytes, and the two properties that make them trustworthy."""

    def test_check_passes_on_the_command_line(self):
        """The command the owner runs: a fresh build against the committed files."""
        portability.require_the_same_libm()
        result = subprocess.run(
            [sys.executable, "-m", "ui.v2.build", "--check"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("differs from a fresh build", result.stdout)
        self.assertNotIn("does not exist", result.stdout)

    def test_two_builds_are_byte_identical(self):
        first = built_pages()
        again = second_build()
        self.assertEqual(sorted(first), sorted(again), "the two builds made different files")
        differing = sorted(name for name in first if first[name] != again[name])
        self.assertEqual([], differing, "two builds of one site produced different bytes")

    def test_two_builds_under_different_hash_seeds_are_byte_identical(self):
        """The row order is the files', not the interpreter's.

        A row order that came out of a set or a dict -- or out of an unsorted
        directory listing -- would move when the interpreter's string hash seed
        moved, because a Python string hash is salted per process. Two builds run
        in their own processes under two seeds, and every page's digest is
        compared. This is the check that caught the queue's row order.
        """
        portability.require_the_same_libm()
        first = build_under_hash_seed("0")
        second = build_under_hash_seed("1")
        self.assertEqual(sorted(first), sorted(second))
        differing = sorted(name for name in first if first[name] != second[name])
        self.assertEqual([], differing, "two hash seeds produced different bytes")

    def test_the_run_order_is_the_builders_own(self):
        """The test reads the runs in the order the queue writes them.

        The order here is typed in this file, so it can drift from the builder's
        own; that drift is what made the two determinism tests disagree about
        whether 901 came before 1779.
        """
        self.assertEqual(tuple(v2.SET_ORDER), tuple(name for name, _ in SET_RUNS))

    def test_every_committed_page_equals_a_fresh_build(self):
        committed = committed_pages()
        built = built_pages()
        self.assertEqual(sorted(built), sorted(committed))
        for name in sorted(built):
            with self.subTest(page=name):
                self.assertEqual(
                    built[name],
                    committed[name],
                    "{0} differs from a fresh build; run `python3 -m ui.v2.build`".format(name),
                )

    def test_the_site_is_the_queue_and_one_page_per_case(self):
        pages = built_pages()
        self.assertEqual(2 + len(cases()), len(pages))
        self.assertIn("index.html", pages)
        self.assertIn(v2.NOT_FOUND_LINK, pages)
        for case in cases():
            with self.subTest(case=case["case_no"]):
                self.assertIn(
                    "case-{0:05d}.html".format(case["case_no"]), pages
                )


# --------------------------------------------------------------------------
# Every page is one file with nothing external in it
# --------------------------------------------------------------------------
class _ResourceScan(HTMLParser):
    """Every attribute that names a resource, and every script body."""

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
        self.anchors: List[Tuple[str, str]] = []
        self.script_bodies: List[str] = []
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name not in self.RESOURCE_ATTRIBUTES:
                continue
            if name == "href" and tag in self.NAVIGATION_TAGS:
                self.anchors.append((tag, value or ""))
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
    """Whether a URL would make the browser fetch something off the page."""
    text = url.strip()
    if not text or text.startswith("#"):
        return False
    if text.startswith("//"):
        return True
    scheme = re.match(r"^([A-Za-z][A-Za-z0-9+.\-]*):", text)
    if scheme is not None:
        return scheme.group(1).lower() != "data"
    return False


# The one ``<link>`` a page may carry: the tab icon, as an inline ``data:`` SVG.
# A stylesheet, a preload, a font or an icon fetched over the network is what the
# check below is for, and each of those is a ``<link>`` this pattern does not
# match.
ICON_LINK_RE = re.compile(r'<link rel="icon" href="data:image/svg\+xml,')


def links_other_than_the_icon(text: str) -> List[str]:
    """Every ``<link>`` on a page that is not the inline tab icon."""
    return [
        match.group(0)
        for match in re.finditer(r"<link\b[^>]*>", text)
        if not ICON_LINK_RE.match(match.group(0))
    ]


class SelfContainedTests(unittest.TestCase):
    """One file, no request, no web font, and ASCII throughout."""

    def test_no_page_references_an_external_resource(self):
        for name, text in sorted(built_pages().items()):
            with self.subTest(page=name):
                scan = _ResourceScan()
                scan.feed(text)
                external = [
                    url for _tag, _attr, url in scan.references if is_external_reference(url)
                ]
                self.assertEqual([], external, "{0} references an external resource".format(name))
                self.assertEqual(
                    [],
                    links_other_than_the_icon(text),
                    "{0} carries a <link> that is not the inline tab icon".format(name),
                )
                for tag in ("<iframe", "<object", "<embed"):
                    self.assertNotIn(tag, text, "{0} embeds {1}".format(name, tag))

    def test_every_link_stays_inside_the_site(self):
        """A link is a page here, the replay, a copied asset, one named URL, or a
        fragment.

        Every page carries a link to the evaluation replay beside it. That link
        is checked against the file on disk, because the replay is a second site
        this builder does not write. The queue's results line points at the
        repository's own page, and is the one link a page carries that leaves the
        site; it is named in ``EXTERNAL_LINKS`` rather than passed over silently,
        and every other link is a file the builder copies in, one of the pages
        this site commits, or a fragment, which is checked against the page that
        carries it, so a link to an anchor that is not there is still a failure.
        """
        names = set(built_pages())
        for name, text in sorted(built_pages().items()):
            scan = _ResourceScan()
            scan.feed(text)
            for _tag, url in scan.anchors:
                with self.subTest(page=name, url=url):
                    if url in EXTERNAL_LINKS:
                        # The one link out of the site, named rather than
                        # skipped: it is an absolute URL, so there is no file
                        # here to resolve it against.
                        self.assertTrue(is_external_reference(url))
                        continue
                    self.assertFalse(is_external_reference(url))
                    if url.startswith("#"):
                        self.assertIn(
                            'id="{0}"'.format(url[1:]),
                            text,
                            "{0} links to {1}, an anchor it does not carry".format(name, url),
                        )
                        continue
                    if url == v2.REPLAY_INDEX:
                        self.assertTrue(
                            (v2.DIST_DIR / url).is_file(),
                            "the replay page {0} is not committed".format(url),
                        )
                        continue
                    if url in SITE_ASSETS:
                        # A file the builder copies into the site: it is inside
                        # ``ui/dist/`` and must be the repository file's own bytes.
                        target = (v2.DIST_DIR / url).resolve()
                        self.assertTrue(
                            target.is_file(),
                            "the site asset {0} is not committed".format(url),
                        )
                        self.assertEqual(SITE_ASSETS[url].read_bytes(), target.read_bytes())
                        continue
                    self.assertIn(url, names, "{0} links to {1}, which is not a page".format(name, url))

    def test_no_page_fetches_anything_at_runtime(self):
        for name, text in sorted(built_pages().items()):
            with self.subTest(page=name):
                self.assertNotIn("fetch(", text)
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
                    self.assertNotIn(call, script)

    def test_every_page_is_ascii(self):
        for name, text in sorted(built_pages().items()):
            with self.subTest(page=name):
                self.assertTrue(
                    text.isascii(),
                    "{0} holds a byte outside ASCII".format(name),
                )
                committed = (v2.DIST_DIR / name).read_bytes()
                self.assertTrue(committed.isascii(), "{0} is not ASCII on disk".format(name))

    def test_no_page_carries_a_key_shaped_run(self):
        """The publish scan's rule, asserted where this site's own pages are.

        Case 2738's transcript says "ask-to-cancel", which the rule reads as a
        key. The builder writes that run's hyphen as a numeric entity, so the
        bytes cannot match; this is the assertion that it did.
        """
        pattern = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
        for name, text in sorted(built_pages().items()):
            with self.subTest(page=name):
                self.assertIsNone(pattern.search(text))

    def test_the_key_scan_can_fire(self):
        """A positive control, assembled from pieces so it is not a literal."""
        pattern = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
        planted = "the token " + "sk" + "-" + "abcdefgh1234" + " was pasted"
        self.assertIsNotNone(pattern.search(planted))
        self.assertIsNone(pattern.search(v2.defuse_key_shaped(planted)))

    def test_no_page_carries_a_raw_agent_answer(self):
        """No page prints the advocates' or the judge's answer as JSON.

        The agents answer in JSON, and the transcript keeps that answer verbatim.
        A page that printed it would show a judge
        ``{"text":"...","evidence_ids":[...],"clause_ids":[...]}`` instead of a
        debate -- which is what the "How it was decided" tab did before part 44.
        Every page is read for the two runs of characters a dumped claim always
        carries.
        """
        markers = ('{"text":', '"evidence_ids":')
        for name, text in sorted(built_pages().items()):
            with self.subTest(page=name):
                for marker in markers:
                    self.assertNotIn(
                        marker,
                        text,
                        "{0} prints a raw agent answer".format(name),
                    )

    def test_the_raw_answer_scan_can_fire(self):
        """A positive control, assembled from pieces so it is not a literal."""
        markers = ('{"text":', '"evidence_ids":')
        planted = (
            'a claim dumped whole: '
            + "{"
            + '"text"'
            + ":"
            + '"the driver never came", '
            + '"evidence_ids"'
            + ":"
            + '["EV-GPS-00208"]}'
        )
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, planted)


# --------------------------------------------------------------------------
# The files the site carries that are not pages
# --------------------------------------------------------------------------
class SiteAssetTests(unittest.TestCase):
    """The architecture set and the two images travel with the site, and no link
    leaves it.

    The queue's architecture link used to be ``../../docs/architecture.md``:
    inside a checkout it resolved, and on a site served from ``ui/dist/`` alone
    it was a 404. The builder now copies the four views of
    ``docs/architecture/`` in byte for byte, and the two images under
    ``ui/assets/`` the same way, so every link is a file beside the pages. These
    tests hold that: each committed copy is the repository's own bytes, and every
    relative href a built page carries resolves to a file inside ``ui/dist/``.
    The one link that leaves the site is an absolute URL, and it is named in
    ``EXTERNAL_LINKS`` rather than passed over silently.
    """

    def test_the_architecture_views_are_committed_byte_for_byte(self):
        """A copy that could drift from its source is the bug it replaced."""
        for view, _label in v2.ARCHITECTURE_VIEWS:
            with self.subTest(view=view):
                committed = v2.ARCHITECTURE_ASSET_DIR / view
                self.assertTrue(
                    committed.is_file(),
                    "{0} is not committed; run `python3 -m ui.v2.build`".format(
                        committed.relative_to(v2.DIST_DIR)
                    ),
                )
                self.assertEqual(
                    (v2.ARCHITECTURE_SOURCE_DIR / view).read_bytes(),
                    committed.read_bytes(),
                    "the committed copy is not the repository's own view",
                )

    def test_the_front_pages_poster_is_committed_byte_for_byte(self):
        """51a.2: the poster is the owner's file, and the site carries its bytes.

        It is copied the way the link-preview image is, so ``--check`` covers
        it: the file under ``ui/dist/`` must be the committed file under
        ``ui/assets/`` and not a re-encode of it.
        """
        committed = v2.COVER_ASSET
        self.assertTrue(
            committed.is_file(),
            "{0} is not committed; run `python3 -m ui.v2.build`".format(
                committed.relative_to(v2.DIST_DIR)
            ),
        )
        self.assertTrue(
            v2.COVER_SOURCE.is_file(),
            "ui/assets/cover-1280.jpg is not committed",
        )
        self.assertEqual(v2.COVER_SOURCE.read_bytes(), committed.read_bytes())

    def test_every_relative_link_resolves_inside_the_site(self):
        """A relative href is a file in ``ui/dist/``, not a path out of the site.

        Every anchor a built page carries that is not a fragment and not an
        external URL must resolve to a file inside the published root. The
        architecture link is the case this test was written for. There is no
        exception left: the queue's results link was the one repository-relative
        path a page carried, and since part 48 it is an absolute URL to the
        repository's own page, so this check covers every relative link again.
        """
        published = v2.DIST_DIR.resolve()
        for name, text in sorted(built_pages().items()):
            scan = _ResourceScan()
            scan.feed(text)
            for _tag, url in scan.anchors:
                with self.subTest(page=name, url=url):
                    if not url or url.startswith("#") or is_external_reference(url):
                        continue
                    target = (v2.DIST_DIR / url.split("#", 1)[0]).resolve()
                    self.assertTrue(
                        target.is_file(),
                        "{0} links to {1}, which is not a file".format(name, url),
                    )
                    self.assertTrue(
                        published == target or published in target.parents,
                        "{0} links to {1}, which is outside ui/dist".format(name, url),
                    )


# --------------------------------------------------------------------------
# The sealed set is not shown, and is not read
# --------------------------------------------------------------------------
class _ReadGuard:
    """Records every file a build opens, so "it reads no sealed path" is checked."""

    def __init__(self) -> None:
        self.opened: List[str] = []
        self.scanned: List[str] = []
        self._open = None
        self._scandir = None

    def __enter__(self) -> "_ReadGuard":
        self._open = pathlib.Path.open
        self._scandir = os.scandir

        def opened(path, *args, **kwargs):
            self.opened.append(str(path))
            return self._open(path, *args, **kwargs)

        def scandir(path=".", *args, **kwargs):
            self.scanned.append(str(path))
            return self._scandir(path, *args, **kwargs)

        pathlib.Path.open = opened
        os.scandir = scandir
        return self

    def __exit__(self, *exc) -> None:
        pathlib.Path.open = self._open
        os.scandir = self._scandir


def is_under_a_sealed_root(path_text: str) -> bool:
    try:
        resolved = Path(path_text).resolve()
    except OSError:  # pragma: no cover - a path that cannot be resolved is not read
        return False
    for root in SEALED_ROOTS:
        if resolved == root or root in resolved.parents:
            return True
    return False


class SealedSetTests(unittest.TestCase):
    """No page names a sealed case, and the build opens no sealed path."""

    def test_no_page_names_a_sealed_case_number(self):
        numbers = [str(number) for number in SEALED_V1_CASES]
        link = re.compile(r"case-00(" + "|".join(numbers) + r")\.html")
        phrase = re.compile(r"[Cc]ase (?:no\.? )?(" + "|".join(numbers) + r")(?![0-9])")
        cell = re.compile(r">(" + "|".join(numbers) + r")<")
        for name, text in sorted(built_pages().items()):
            with self.subTest(page=name):
                self.assertIsNone(link.search(text))
                self.assertIsNone(phrase.search(text))
                self.assertIsNone(cell.search(text))

    def test_no_page_mentions_the_sealed_set(self):
        for name, text in sorted(built_pages().items()):
            with self.subTest(page=name):
                self.assertNotIn("sealed-v1", text.lower())
                self.assertNotIn("sealed_v1", text.lower())

    def test_the_sealed_case_detector_can_fire(self):
        """A control over all three forms, on text this file assembles itself."""
        link = re.compile(r"case-00(301)\.html")
        phrase = re.compile(r"[Cc]ase (?:no\.? )?(301)(?![0-9])")
        cell = re.compile(r">(301)<")
        planted = 'a link to case-' + "00301" + ".html, and " + "Case " + "301" + ", and >" + "301<"
        self.assertIsNotNone(link.search(planted))
        self.assertIsNotNone(phrase.search(planted))
        self.assertIsNotNone(cell.search(planted))

    def test_the_builder_reads_no_sealed_path(self):
        """Every open the whole build made, against the three sealed roots."""
        guard = read_guard()
        self.assertEqual(151, len(cases()))
        offenders = [
            path for path in guard.opened + guard.scanned if is_under_a_sealed_root(path)
        ]
        self.assertEqual([], offenders, "the build opened a sealed path")
        self.assertGreater(len(guard.opened), 300, "too few reads recorded; the guard is broken")

    def test_the_read_guard_can_catch_a_sealed_path(self):
        """A control, on a name that is not in the repository.

        The path is never a real file, so nothing under a sealed root is read:
        what is asserted is that the guard records the attempt.
        """
        missing = SEALED_ROOTS[0] / "not-a-file-in-this-repository"
        guard = _ReadGuard()
        with guard:
            with self.assertRaises(OSError):
                missing.read_text(encoding="utf-8")
        self.assertTrue(
            any(is_under_a_sealed_root(path) for path in guard.opened),
            "the guard did not record a read under a sealed root",
        )
        self.assertTrue(is_under_a_sealed_root(str(missing)))
        self.assertFalse(is_under_a_sealed_root(str(PROJECT_ROOT / "README.md")))


# --------------------------------------------------------------------------
# What each case page shows
# --------------------------------------------------------------------------
class CasePageFiguresTests(unittest.TestCase):
    """The ruling, the money and the confidence, against the case file."""

    def expected_money(self, case: Mapping[str, Any]) -> str:
        """What the page must say about money, chosen by the ruling value.

        POL-GEN-03's single exception is the one that matters: on a
        ``DRIVER_COMPENSATION`` ruling ``amount_sgd`` carries the same figure as
        ``driver_compensation_sgd`` and is the amount the ruling moves, not a
        refund, so a page that called it one would be stating a policy the
        policy does not state.
        """
        ruling = inner_ruling(case["document"])
        value = str(ruling.get("ruling"))
        currency = currency_of(case["document"])
        filed_by = (
            public_case(case["set"], case["case_no"]).get("dispute") or {}
        ).get("filed_by")
        if value in ("FULL_REFUND", "PARTIAL_REFUND"):
            return "Refund to the {0}: {1}".format(
                str(filed_by).lower(), money(ruling.get("amount_sgd"), currency)
            )
        if value == "DRIVER_COMPENSATION":
            return "The fee stands. The driver is paid {0}. No refund.".format(
                money(ruling.get("driver_compensation_sgd"), currency)
            )
        if value == "NO_ACTION":
            return "No money moves. The charge stands."
        if value == "ESCALATE":
            return "No money moves. The disputed amount is held."
        raise AssertionError("no money rule is stated for " + value)

    def test_every_case_page_shows_its_own_ruling_and_money(self):
        """The ruling in words and code, and the money by ruling value.

        A case sent to a reviewer is the one shape that differs: no ruling was
        issued, so the page headlines the reason the case reached a reviewer
        rather than a ruling, and the ruling value ``ESCALATE`` appears where the
        packet carries it.
        """
        for case in cases():
            value = str(inner_ruling(case["document"]).get("ruling"))
            page = built_pages()["case-{0:05d}.html".format(case["case_no"])]
            with self.subTest(case=case["case_no"]):
                if case["trigger"] is None:
                    self.assertIn(
                        "<strong>{0}</strong>".format(v2.ruling_words(value)),
                        page,
                        "the ruling is not shown in words",
                    )
                else:
                    votes = int(
                        (case["document"].get("configuration") or {}).get("judge_votes")
                    )
                    self.assertIn(
                        TRIGGER_WORDS[case["trigger"]].format(votes=votes),
                        page,
                        "the reason is not shown in words",
                    )
                    self.assertIn(
                        '<span class="mono">{0}</span>'.format(case["trigger"]),
                        page,
                        "the reason code is not shown after the words",
                    )
                self.assertIn(
                    '<span class="mono">{0}</span>'.format(value),
                    page,
                    "the ruling code is not shown",
                )
                self.assertIn(
                    self.expected_money(case),
                    page,
                    "the money is not stated by the ruling value",
                )

    def test_case_901_says_the_fee_stands_and_the_driver_is_paid(self):
        """The case the sheet names: its amount is not a refund.

        901 is a ``DRIVER_COMPENSATION`` ruling whose ``amount_sgd`` is the same
        figure as its ``driver_compensation_sgd``. POL-GEN-03 says that figure is
        the amount the ruling moves and not a refund, so the page must not offer
        it as one.
        """
        rows = [
            row for row in cases() if row["set"] == "ryde-v3" and row["case_no"] == 901
        ]
        self.assertEqual(1, len(rows))
        case = rows[0]
        ruling = inner_ruling(case["document"])
        self.assertEqual("DRIVER_COMPENSATION", ruling.get("ruling"))
        currency = currency_of(case["document"])
        page = built_pages()["case-00901.html"]
        self.assertIn(
            "The fee stands. The driver is paid {0}. No refund.".format(
                money(ruling.get("driver_compensation_sgd"), currency)
            ),
            page,
        )
        self.assertNotIn(
            "Refund to the rider: {0}".format(money(ruling.get("amount_sgd"), currency)),
            page,
        )
        self.assertNotIn("Refund to the filing party", page)

    def test_every_case_page_shows_its_own_confidence_and_the_floor(self):
        floor = read_json(PROJECT_ROOT / "policy" / "v3" / "general.json")["confidence_floor"]
        for case in cases():
            page = built_pages()["case-{0:05d}.html".format(case["case_no"])]
            with self.subTest(case=case["case_no"]):
                if case["trigger"] is not None:
                    # A case sent to a reviewer has no ruling to be confident in,
                    # so the bar is replaced by the reason in words -- and the
                    # disclosure says no ruling was made, rather than describing
                    # a provisional ruling that does not exist.
                    self.assertIn(v2.NO_AUTOMATED_RULING, page)
                    self.assertNotIn(v2.DISCLOSURE, page)
                    self.assertNotIn(
                        'aria-label="confidence ',
                        page,
                        "a confidence is shown for a ruling that was never made",
                    )
                    continue
                confidence = inner_ruling(case["document"]).get("confidence")
                if confidence is None:
                    self.assertIn("No confidence is recorded", page)
                    continue
                self.assertIn(
                    'aria-label="confidence {0} against a floor of {1}"'.format(
                        confidence, floor
                    ),
                    page,
                    "the confidence or the floor is not the policy's own figure",
                )

    def test_a_scope_gated_case_says_no_advocate_was_asked(self):
        """The two flagged disputes of dev-v2-ext, and what their page shows."""
        gated = [case for case in cases() if case["trigger"] == "GEN08_SCOPE"]
        self.assertEqual([2735, 2759], sorted(case["case_no"] for case in gated))
        for case in gated:
            page = built_pages()["case-{0:05d}.html".format(case["case_no"])]
            with self.subTest(case=case["case_no"]):
                self.assertIn("No advocate was asked", page)
                self.assertIn("GEN08_SCOPE", page)


# --------------------------------------------------------------------------
# The queue's five figures
# --------------------------------------------------------------------------
# The words the sheet gives for each reason code. They are typed here, in the
# test, rather than read from the builder, so a page that showed a code where the
# words belong is caught. The no-majority phrase names the panel size, which is
# the run's own judge_votes rather than a number typed anywhere.
TRIGGER_WORDS: Mapping[str, str] = {
    "GEN08_SCOPE": "safety or complaint flag",
    "NO_VALID_DRAFTS": "no judge draft passed the code checks",
    "NO_MAJORITY": "the {votes} drafts did not agree",
    "JUDGE_ESCALATE": "the judge escalated under the policy",
}


class QueueFiguresTests(unittest.TestCase):
    """The figures, recomputed from the run files and compared."""

    def held(self, row: Mapping[str, Any]) -> bool:
        """Whether POL-GEN-05 holds this case's money for a person to release."""
        if row["trigger"] is not None:
            return False
        return monetary_effect(inner_ruling(row["document"])) > execution_threshold()

    def figures(self) -> Dict[str, Any]:
        rows = cases()
        total = len(rows)
        reviewer = [row for row in rows if row["trigger"] is not None]
        decided = [row for row in rows if row["trigger"] is None]
        held = [row for row in decided if self.held(row)]
        executed = len(decided) - len(held)
        counts = {name: 0 for name in TRIGGERS}
        for row in reviewer:
            counts[row["trigger"]] += 1
        walls = [
            Decimal(str(row["document"]["wall_seconds"])) for row in rows
        ]
        costs = [cost_of(row["run_dir"], row["case_no"]) for row in rows]
        models = {str(row["document"]["model"]) for row in rows}
        versions = {
            int((row["document"].get("configuration") or {}).get("policy_version"))
            for row in rows
        }
        votes = {
            int((row["document"].get("configuration") or {}).get("judge_votes"))
            for row in rows
        }
        self.assertEqual(1, len(models))
        self.assertEqual(1, len(versions))
        self.assertEqual(1, len(votes))
        vote_count = votes.pop()
        return {
            "total": str(total),
            "executed": "{0} of {1}".format(executed, total),
            "executed_share": "{0:.1f}%".format(
                Decimal(executed) * 100 / Decimal(total)
            ),
            "held": "{0} of {1}".format(len(held), total),
            "held_share": "{0:.1f}%".format(Decimal(len(held)) * 100 / Decimal(total)),
            "reviewer": "{0} of {1}".format(len(reviewer), total),
            "reviewer_share": "{0:.1f}%".format(Decimal(len(reviewer)) * 100 / Decimal(total)),
            "triggers": [
                (TRIGGER_WORDS[name].format(votes=vote_count), counts[name])
                for name in TRIGGERS
                if counts[name]
            ],
            "median_time": "{0:.1f} s".format(median(walls)),
            "median_cost": "{0:.4f} USD".format(median(costs)),
            "version": "v{0}".format(versions.pop()),
            "model": models.pop(),
        }

    def test_the_queue_shows_the_figures_the_run_files_give(self):
        figures = self.figures()
        text = index_text()
        for key, value in sorted(figures.items()):
            if key in ("total", "triggers"):
                continue
            with self.subTest(figure=key):
                self.assertIn(value, text, "{0} is not on the queue page".format(key))

    def test_the_three_routing_counts_are_business_values_own_numbers(self):
        """The queue's three counts, against the command that prints them.

        The page counted the 13 cases whose money POL-GEN-05 holds as decided
        automatically, so the queue said 125 where ``python3 -m
        eval.business_value --report`` says 112 decided, 13 held and 26 with no
        ruling. The test reads that command's own reading of the same four runs
        and holds the page to it, so the two cannot drift apart again.
        """
        from eval import business_value

        automatic, human, escalations, held = business_value.lanes()
        figures = self.figures()
        self.assertEqual("{0} of 151".format(automatic), figures["executed"])
        self.assertEqual("{0} of 151".format(held), figures["held"])
        self.assertEqual("{0} of 151".format(escalations), figures["reviewer"])
        # The three counts partition the queue, which is what makes them the
        # three tiles rather than three readings of two overlapping sets.
        self.assertEqual(151, automatic + held + escalations)
        self.assertEqual(human, held + escalations)
        text = index_text()
        for count in (automatic, held, escalations):
            with self.subTest(count=count):
                self.assertIn("{0} of 151".format(count), text)

    def test_the_three_tiles_say_what_each_count_is(self):
        text = index_text()
        for label in (
            "Decided and executed",
            "Decided, amount held for a person to release",
            "Sent to a reviewer",
        ):
            with self.subTest(label=label):
                self.assertIn('<p class="k">{0}</p>'.format(label), text)
        self.assertIn("POL-GEN-05", text)

    def test_the_queue_says_what_executed_and_confidence_mean(self):
        """The two loaded words a reader can take wrongly, said once in one line.

        "Decided and executed" reads as a payment and the table's "confidence"
        reads as a measured accuracy; neither is what the figures are. The line
        under the tiles says what each word means, and the executed tile's small
        print carries the same words as the line.
        """
        text = index_text()
        self.assertIn(v2.EXECUTED_MEANS, v2.QUEUE_WORDS_NOTE)
        self.assertIn(v2.CONFIDENCE_MEANS, v2.QUEUE_WORDS_NOTE)
        self.assertIn(
            '<p class="figurewords">{0}</p>'.format(v2._text(v2.QUEUE_WORDS_NOTE)),
            text,
            "the queue does not say what the two words mean",
        )
        self.assertIn(
            v2._text(
                "{0} of the queue: {1} (POL-GEN-05)".format(
                    self.figures()["executed_share"], v2.EXECUTED_MEANS
                )
            ),
            text,
            "the executed tile's small print does not use the line's own words",
        )
        self.assertIn("README", text)

    def test_the_queue_prints_the_held_reason_in_the_row(self):
        """The reason is text in the row, not only a tooltip.

        The figure and the threshold it crossed were in the status cell's
        ``title``, which a reader who cannot hover is never told.
        """
        held = [case for case in loaded_cases() if v2._money_is_held(case)]
        self.assertTrue(held, "no case has a held amount to check")
        queue = built_pages()["index.html"]
        for case in held:
            with self.subTest(case=case.case_no):
                self.assertIn(
                    '<span class="held-why">{0}</span>'.format(
                        v2._text(v2.held_reason(case))
                    ),
                    queue,
                    "the queue row does not print why the amount is held",
                )

    def test_the_reviewer_triggers_card_lists_one_trigger_per_line(self):
        """Each trigger on a line of its own: the words first, then the count."""
        text = index_text()
        for words, count in self.figures()["triggers"]:
            with self.subTest(trigger=words):
                self.assertIn(
                    '<li><span class="t">{0}</span> <span class="n">{1}</span></li>'.format(
                        words, count
                    ),
                    text,
                    "the reviewer-triggers card does not list {0}".format(words),
                )

    def test_the_figures_are_not_the_whole_of_it(self):
        """The three tiles are one queue cut three ways, not three queues."""
        figures = self.figures()
        self.assertEqual("151", figures["total"])
        self.assertEqual("112 of 151", figures["executed"])
        self.assertEqual("13 of 151", figures["held"])
        self.assertEqual("26 of 151", figures["reviewer"])
        self.assertEqual("74.2%", figures["executed_share"])
        self.assertEqual("8.6%", figures["held_share"])
        self.assertEqual("17.2%", figures["reviewer_share"])

    def test_the_two_medians_are_the_size_the_run_files_say(self):
        """A guard on the magnitude of both, and it is here because it was needed.

        The first build of this site divided the cost by a million twice and
        printed ``0.0000 USD``, and the check above did not catch it: the page
        and the test agreed, because both divided by a million twice. A figure
        per case is a fraction of a dollar and a couple of minutes, so that is
        what is asserted -- not a number typed in here, but the size the run
        files say it has, against the run's own total.
        """
        figures = self.figures()
        median_cost = Decimal(figures["median_cost"].split()[0])
        total_cost = sum(cost_of(row["run_dir"], row["case_no"]) for row in cases())
        self.assertGreater(total_cost, Decimal("1"), "the run's total cost is not a dollar")
        self.assertGreater(median_cost, Decimal("0.001"))
        self.assertLess(median_cost, total_cost)
        median_time = Decimal(figures["median_time"].split()[0])
        self.assertGreater(median_time, Decimal("1"))
        self.assertLess(median_time, Decimal("100000"))


# --------------------------------------------------------------------------
# The human-review tab
# --------------------------------------------------------------------------
class HumanReviewTests(unittest.TestCase):
    """A reviewer's tab is there for a reviewer's case, and its packet is the packet."""

    def test_a_case_sent_to_a_reviewer_carries_the_tab_and_the_packet_digest(self):
        reviewer = [case for case in cases() if case["trigger"] is not None]
        self.assertEqual(26, len(reviewer))
        for case in reviewer:
            page = built_pages()["case-{0:05d}.html".format(case["case_no"])]
            packet = escalation.build_packet(case["run_dir"], case["case_no"])
            with self.subTest(case=case["case_no"]):
                self.assertIn('data-panel="review"', page)
                self.assertIn("Human review", page)
                self.assertIn(
                    escalation.packet_sha256(packet),
                    page,
                    "the packet digest on the page is not ops.escalation's",
                )

    def test_a_decided_case_has_no_human_review_tab(self):
        decided = [case for case in cases() if case["trigger"] is None]
        self.assertEqual(125, len(decided))
        for case in decided:
            page = built_pages()["case-{0:05d}.html".format(case["case_no"])]
            with self.subTest(case=case["case_no"]):
                self.assertNotIn('data-panel="review"', page)

    def test_the_review_form_names_the_four_decisions_and_closes_nothing(self):
        case = [row for row in cases() if row["trigger"] is not None][0]
        page = built_pages()["case-{0:05d}.html".format(case["case_no"])]
        for decision in ("ADOPT", "VARY", "REQUEST_EVIDENCE", "REFER_COMPLIANCE"):
            with self.subTest(decision=decision):
                self.assertIn('value="{0}"'.format(decision), page)
        self.assertIn("closes nothing by itself", page)
        self.assertIn("python3 -m ops.review", page)
        self.assertIn("--packet-sha256", page)

    def test_no_decision_is_preselected(self):
        """The form opens on no decision, and builds nothing until one is chosen.

        The first enabled radio used to be ``checked``, so on 1779 -- the
        prompt-injection case -- the form opened on "Vary" with the ruling
        select on "Full refund", which is the outcome the injected message asked
        for.
        """
        for case in [row for row in cases() if row["trigger"] is not None]:
            page = built_pages()["case-{0:05d}.html".format(case["case_no"])]
            with self.subTest(case=case["case_no"]):
                for control in re.finditer(r"<input\b[^>]*>", page):
                    self.assertNotIn("checked", control.group(0))
                self.assertIn(
                    "the command is built once a decision is chosen", page
                )

    def test_the_ruling_selects_open_on_no_ruling(self):
        """A select whose first option is a real ruling decides for the reviewer."""
        for case in [row for row in cases() if row["trigger"] is not None]:
            page = built_pages()["case-{0:05d}.html".format(case["case_no"])]
            for select_id in ("vary-ruling", "refer-ruling"):
                with self.subTest(case=case["case_no"], select=select_id):
                    start = page.index('id="{0}"'.format(select_id))
                    block = page[start : page.index("</select>", start)]
                    self.assertIn('<option value="">choose a ruling</option>', block)
                    self.assertEqual(1, block.count('<option value="">'))

    def test_the_command_quotes_every_value_so_a_shell_cannot_rewrite_it(self):
        """A reason may hold ``$HOME``, a backtick, ``!`` and ``'``.

        Double quotes leave all four to the shell, so the value a reviewer typed
        is not the value that runs -- the bug part 38c fixed in ``ops/``. The
        page single-quotes each value and closes, escapes and reopens an
        apostrophe, and the command line the builder writes does the same.
        """
        case = v2._load_case("corpus", 213)
        reason = (
            "The reviewer varies to NO_ACTION: EV-FARE-00213 and POL-GEN-07 are "
            "cited, and $HOME, a `backtick`, an ! and an ' are literal."
        )
        command = v2.closing_command(
            case,
            "VARY",
            ruling="NO_ACTION",
            clauses=["POL-GEN-07"],
            closed_by="a reviewer",
            reason=reason,
        )
        self.assertNotIn('"', command, "a value is still double-quoted")
        parts = shlex.split(command)
        self.assertIn(reason, parts)
        self.assertIn("a reviewer", parts)
        self.assertIn("VARY", parts)
        page = v2.build_case_page(case)
        self.assertIn(r"'\\''", page, "the page's own quoting rule is not there")
        self.assertIn("String(text).replace(/'/g,", page)

    def test_the_packet_values_reach_the_page_as_words_and_figures(self):
        """``contested 10.5``, ``unanimous False`` and a null agreement, in words."""
        case = v2._load_case("dev-v2", 1779)
        page = v2.build_case_page(case)
        packet = case.packet
        assert packet is not None
        currency = case.policy.currency
        self.assertIn(
            v2._text(
                v2._money(packet["case"]["amount_contested_sgd"], currency)
            ),
            page,
        )
        self.assertIn("unanimous: no", page)
        self.assertIn("agreement: no vote", page)
        # The drafts' own proposals, which the packet drops for a voided draft.
        self.assertIn(v2._money("5.70", currency), page)
        # The event log is a collapsed table of clocks and tenths of a second.
        self.assertIn("<details><summary>Show the event log</summary>", page)
        row = packet["timeline"][1]
        self.assertIn(v2._text(v2._clock(row["ts"])), page)
        self.assertIn(v2._text(v2._seconds(row["seconds"])), page)

    def test_the_advocate_briefs_are_a_list_of_claims_each_tagged(self):
        """One claim per item, each kept or discarded -- and no "KEPT;" separators."""
        case = v2._load_case("corpus", 107)
        page = v2.build_case_page(case)
        packet = case.packet
        assert packet is not None
        self.assertNotIn("KEPT;", page)
        self.assertNotIn("DISCARDED;", page)
        for side in ("RIDER", "DRIVER"):
            claims = packet["briefs"].get(side) or []
            self.assertTrue(claims)
            for claim in claims[:2]:
                with self.subTest(side=side, text=str(claim.get("text"))[:40]):
                    self.assertIn(v2._text(claim.get("text")), page)
        self.assertIn('<span class="pill green">kept</span>', page)
        self.assertIn('<span class="pill red">discarded</span>', page)


# --------------------------------------------------------------------------
# The appeal text is the policy's
# --------------------------------------------------------------------------
class AppealTextTests(unittest.TestCase):
    """POL-GEN-04's rule text, as ``policy/v3/general.json`` carries it."""

    def rule_text(self, clause_id: str) -> str:
        general = read_json(PROJECT_ROOT / "policy" / "v3" / "general.json")
        for clause in general["clauses"]:
            if clause["id"] == clause_id:
                return str(clause["rule"])
        raise AssertionError("policy/v3/general.json carries no " + clause_id)

    def escaped(self, text: str) -> str:
        """The page is ASCII, so a non-ASCII character is a numeric entity."""
        out = []
        for character in text:
            out.append(character if ord(character) < 128 else "&#{0};".format(ord(character)))
        return "".join(out).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # POL-GEN-04's own sentence about the route: "may appeal it once, within 30
    # days". The line the page carries is built from those two numbers, so the
    # test reads them from the clause rather than typing them.
    APPEAL_LINE_RE = re.compile(
        r"may appeal it (once|twice|[0-9]+ times), within ([0-9]+) days"
    )

    def appeal_line(self) -> str:
        """POL-GEN-04's route in one line, from the clause's own numbers.

        The words lead and the clause id follows them in brackets, which is the
        shape the notice's code-carrying lines take since part 48.
        """
        match = self.APPEAL_LINE_RE.search(self.rule_text("POL-GEN-04"))
        self.assertIsNotNone(match, "POL-GEN-04 no longer states the route")
        return (
            "You may appeal {0} within {1} days (POL-GEN-04). A different human "
            "reviewer hears it, and only record evidence may be added.".format(
                match.group(1), match.group(2)
            )
        )

    def test_the_appeal_text_is_pol_gen_04(self):
        clause = self.escaped(self.rule_text("POL-GEN-04"))
        self.assertIn("30 days", clause)
        line = self.appeal_line()
        for case in cases():
            page = built_pages()["case-{0:05d}.html".format(case["case_no"])]
            with self.subTest(case=case["case_no"]):
                if case["trigger"] is not None:
                    # No ruling was issued, so there is no appeal path to show.
                    self.assertNotIn(line, page)
                    self.assertNotIn("Read POL-GEN-04 in full", page)
                    continue
                self.assertIn(line, page, "the appeal is not POL-GEN-04's route")
                self.assertIn("Read POL-GEN-04 in full", page)
                self.assertIn(clause, page, "the full clause is not on the page")

    def test_the_execution_text_is_pol_gen_05(self):
        """And the execution sentence carries the policy's own threshold."""
        threshold = read_json(PROJECT_ROOT / "policy" / "v3" / "general.json")[
            "execution_threshold_sgd"
        ]
        currency = currency_of(cases()[0]["document"])
        for case in cases():
            page = built_pages()["case-{0:05d}.html".format(case["case_no"])]
            with self.subTest(case=case["case_no"]):
                self.assertIn("POL-GEN-05", page)
                if case["trigger"] is not None:
                    self.assertIn("Escalation is terminal", page)
                else:
                    self.assertIn(
                        money(threshold, currency), page, "the execution threshold is missing"
                    )


# --------------------------------------------------------------------------
# The front door: the product view at the root, the replay beside it
# --------------------------------------------------------------------------
class FrontDoorTests(unittest.TestCase):
    """The site's root is the product view, and the replay is one level down."""

    def test_the_builders_paths_are_the_site_root(self):
        self.assertEqual(PROJECT_ROOT / "ui" / "dist", v2.DIST_DIR)
        self.assertEqual(v2.DIST_DIR / "index.html", v2.INDEX_PATH)
        self.assertEqual("replay/index.html", v2.REPLAY_INDEX)
        self.assertTrue(
            (v2.DIST_DIR / "replay" / "index.html").is_file(),
            "the evaluation replay is not committed under replay/",
        )
        self.assertFalse(
            (v2.DIST_DIR / "v2").exists(),
            "the old ui/dist/v2/ directory is still committed",
        )

    def test_every_page_carries_the_top_bar_and_a_link_to_the_replay(self):
        """The header carries the queue; the replay is named in the footer.

        The header used to carry the replay too, labelled for what it is, and a
        judge who followed it went to the historical version-1 figures first.
        It sits in the footer now, under the words that say which pipeline it
        is, and the header keeps the queue.
        """
        self.assertEqual("Earlier benchmark replay (policy v1 runs)", v2.REPLAY_LABEL)
        for name, text in sorted(built_pages().items()):
            with self.subTest(page=name):
                self.assertIn('<header class="top">', text)
                self.assertIn(
                    '<a href="{0}">{1}</a>'.format(
                        v2.REPLAY_INDEX, v2._text(v2.REPLAY_LABEL)
                    ),
                    text,
                    "the footer does not carry the replay link",
                )
                self.assertIn('href="replay/index.html"', text)
                self.assertIn(v2.REPLAY_LABEL, text)
                self.assertNotIn("Evaluation replay", text)
                self.assertIn(">Queue</a>", text)
                self.assertIn('class="mark"', text)
                # The nav is the queue alone: the replay link is not in it.
                nav = text[text.index('<nav class="nav"'):text.index("</nav>")]
                self.assertNotIn(v2.REPLAY_LABEL, nav)

    def test_the_top_bar_names_the_run_every_page_replays(self):
        """The bar says what the pages are; the model is named in the footer."""
        first = cases()[0]["document"]
        expected = "Recorded runs, policy version {0}".format(
            (first.get("configuration") or {}).get("policy_version")
        )
        for name, text in sorted(built_pages().items()):
            with self.subTest(page=name):
                self.assertIn(expected, text)
                self.assertNotIn("Replay - policy", text)
                self.assertIn(
                    '<span>model {0}</span>'.format(first.get("model")),
                    text,
                    "the footer does not name the model",
                )

    def test_every_case_header_carries_its_own_ids_and_chips(self):
        for case in loaded_cases():
            page = built_pages()[case.link]
            dispute = case.case.get("dispute") or {}
            with self.subTest(case=case.case_no):
                self.assertIn(str(dispute.get("dispute_id")), page)
                self.assertIn(str(dispute.get("trip_id")), page)
                self.assertIn(str(dispute.get("filed_at")), page)
                self.assertIn(
                    v2.status_chip(case, with_time=True, title=True), page
                )
                self.assertIn(
                    v2._text(v2._summary_line(case.case)),
                    page,
                    "the masked first sentence of the claim is not the title",
                )

    def test_every_case_page_carries_the_opening_of_the_explanation(self):
        """The summary is the explanation's opening, and it is never one line.

        Some explanations open with a one-line salutation -- 104's is "To the
        rider and the driver: this is a provisional automated ruling." -- so the
        summary takes paragraphs until it is at least the sheet's 120 characters.
        Every paragraph it shows is the explanation's own, verbatim. The label
        says whose reasoning the text is: the judge's, on a decided case; the
        panel's drafts', where a panel ran; and the pipeline's own routing
        sentence, where the scope gate stopped before any judge was asked.

        The one exception is the pipeline's list of the drafts, one line each,
        which the ruling panel draws as a table: ``_summary_pieces`` removes it
        the way the page does, and what is left must still be the explanation's
        own words.
        """
        for case in loaded_cases():
            explanation = str(case.ruling.get("explanation") or "").strip()
            if not explanation:
                continue
            page = built_pages()[case.link]
            chosen = v2._summary_paragraphs(explanation)
            whole = len(" ".join(explanation.split()))
            if case.trigger is None:
                label = v2.JUDGE_TEXT_LABEL
            elif v2._drafts(case.transcript):
                label = v2.DRAFTS_TEXT_LABEL
            else:
                label = v2.ROUTING_TEXT_LABEL
            with self.subTest(case=case.case_no):
                self.assertTrue(chosen, "no summary is shown")
                self.assertGreaterEqual(
                    len(" ".join(chosen.split())),
                    min(v2.SUMMARY_MINIMUM_CHARS, whole),
                    "the summary is shorter than the sheet's minimum",
                )
                self.assertIn('<p class="lbl">{0}</p>'.format(v2._text(label)), page)
                pieces = _summary_pieces(chosen)
                self.assertTrue(pieces, "the summary rendered nothing")
                for paragraph in pieces:
                    self.assertIn(
                        v2._text(paragraph),
                        page,
                        "the summary is not the explanation's own words",
                    )

    def test_the_summary_is_never_a_one_line_salutation(self):
        """104's own opening is one line; the page shows the sentence after it."""
        case = loaded_case(104)
        explanation = str(case.ruling.get("explanation") or "")
        first = re.split(r"\n\s*\n", explanation.strip())[0].strip()
        chosen = v2._summary_paragraphs(explanation)
        self.assertLess(len(" ".join(first.split())), v2.SUMMARY_MINIMUM_CHARS)
        self.assertGreater(len(" ".join(chosen.split())), len(" ".join(first.split())))
        self.assertTrue(chosen.startswith(first), "the opening is not verbatim")


# --------------------------------------------------------------------------
# The four featured cases
# --------------------------------------------------------------------------
# The fixed titles, typed here so a page that changed one is caught.
FEATURED_CASES: Tuple[Tuple[int, str], ...] = (
    (901, "The organisers' sample"),
    (208, "A no-show the evidence settles"),
    (1779, "A prompt injection, refused"),
    (2735, "A safety flag: straight to a human"),
)


def card_html(text: str, case_no: int) -> str:
    """The featured card for one case, cut out of the queue page.

    The card is found by its own opening tag. Part 44b added the links row's
    "How it was decided: see case 208" above the cards, and that link carries
    the same ``href="case-00208.html"`` as the card, so searching back from the
    href found the links row's anchor and no card opening tag at all.
    """
    start = text.index(
        '<a class="fcard" href="case-{0:05d}.html"'.format(case_no)
    )
    return text[start : text.index("</a>", start)]


class FeaturedCardTests(unittest.TestCase):
    """The four featured cases: fixed titles, and facts read from the run."""

    def test_the_queue_carries_the_four_cards(self):
        text = index_text()
        self.assertEqual(4, text.count('class="fcard"'))
        for case_no, title in FEATURED_CASES:
            with self.subTest(case=case_no):
                self.assertIn(title, card_html(text, case_no))

    def test_every_featured_card_is_one_link_to_an_existing_case_page(self):
        """51b.9: the whole card is the link, and it opens the case it names.

        The card carries its way in at the foot -- "Open case" and an arrow --
        so the link's own words say what following it does, and every one of the
        four resolves to a page this site commits.
        """
        text = index_text()
        cards = re.findall(r'<a class="fcard" href="([^"]+)">', text)
        self.assertEqual(len(v2.FEATURED_CASES), len(cards))
        self.assertEqual(
            len(v2.FEATURED_CASES),
            text.count('<span class="fopen">Open case'),
            "a featured card carries no way in",
        )
        pages = set(built_pages())
        for href in cards:
            with self.subTest(href=href):
                self.assertRegex(href, r"^case-\d{5}\.html$")
                self.assertIn(href, pages, "{0} is not a page this site commits".format(href))
                self.assertTrue((v2.DIST_DIR / href).is_file())

    def test_901_shows_its_outcome_and_its_confidence(self):
        case = [row for row in cases() if row["case_no"] == 901][0]
        ruling = inner_ruling(case["document"])
        card = card_html(index_text(), 901)
        self.assertIn(v2.ruling_words(ruling.get("ruling")), card)
        self.assertIn(str(ruling.get("confidence")), card)

    def test_208_shows_its_outcome_and_the_records_own_answer(self):
        """The second line is the record's answer, not the amounts twice.

        The outcome line already carries the ruling and the money, so the card's
        second line is the three facts the no-show record turns on, built from
        the same derived blocks the case page's "What the record shows" table
        reads.
        """
        case = [row for row in cases() if row["case_no"] == 208][0]
        ruling = inner_ruling(case["document"])
        card = card_html(index_text(), 208)
        self.assertIn(v2.ruling_words(ruling.get("ruling")), card)
        loaded = loaded_case(208)
        answer = v2._featured_answer(loaded)
        self.assertEqual(
            "driver inside the arrival radius 585 s; her phone 634-646 m away; "
            "a 34 s answered call",
            answer,
            "the one-line answer is not the record's own facts",
        )
        self.assertIn(v2._text(answer), card)
        self.assertNotIn("<b>Amounts</b>", card)

    def test_1779_shows_the_reason_in_words_and_the_panel_that_refused_it(self):
        """The injection was refused; the code check is what escalated the case.

        The four recorded drafts each refused the planted clause and reached the
        same ruling, and the code check voided them because they quoted the
        invented clause id -- to that check a quoted clause id is a citation --
        so the card says a person decides and never says the panel was misled.
        The reason is in words: the card is a summary, and a bare ``NO_VALID_
        DRAFTS`` on it is the code a reader is not yet owed.
        """
        case = [row for row in cases() if row["case_no"] == 1779][0]
        vote = transcript_of(case["run_dir"], 1779).get("vote") or {}
        drafts = list(vote.get("drafts") or [])
        self.assertTrue(drafts, "1779 has no drafts to count")
        card = card_html(index_text(), 1779)
        self.assertIn("no judge draft passed the code checks", card)
        self.assertNotIn(
            "NO_VALID_DRAFTS",
            card,
            "the card still prints the reason code",
        )
        self.assertIn("refused the planted clause", card)
        self.assertIn(
            "All {0} drafts".format(len(drafts)),
            card,
            "the card does not say the whole panel refused the clause",
        )
        self.assertIn("voided them", card)
        self.assertIn("a person decides", card)
        self.assertNotIn(
            "rejected by the code checks",
            card,
            "the card still reads as though the drafts were the failure",
        )

    def test_2735_shows_the_reason_and_that_no_model_was_called(self):
        case = [row for row in cases() if row["case_no"] == 2735][0]
        votes = int((case["document"].get("configuration") or {}).get("judge_votes"))
        card = card_html(index_text(), 2735)
        self.assertIn(TRIGGER_WORDS["GEN08_SCOPE"].format(votes=votes), card)
        self.assertIn("0 - the scope gate asked no model", card)


# --------------------------------------------------------------------------
# The landing page explains itself, and the case page shows a debate
# --------------------------------------------------------------------------
class LandingPageTests(unittest.TestCase):
    """The queue's own words: the strip, the intro, and the links row."""

    def test_the_strip_names_the_five_steps_in_order(self):
        text = index_text()
        self.assertIn('class="how"', text)
        positions = []
        for _who, what, note in v2.HOW_IT_WORKS:
            with self.subTest(step=what):
                self.assertIn(v2._text(what), text)
                self.assertIn(v2._text(note), text)
                positions.append(text.index(v2._text(what)))
        self.assertEqual(
            sorted(positions), positions, "the strip's steps are out of order"
        )

    def test_the_strip_is_numbered_and_the_case_page_keeps_the_three_colours(self):
        """51b.7: the five steps are numbered violet circles now.

        The strip used to carry the case page's three colours on three dots.
        The poster's palette is one accent, so each step is a circle in it with
        its number on it. The case page keeps the three -- its stepper circles
        and its legend -- and that is the half held here, so the two pages
        cannot drift apart about the vocabulary they share.
        """
        self.assertEqual({"code", "model", "outcome"}, set(v2.STEP_COLOURS))
        text = index_text()
        for number in range(1, len(v2.HOW_IT_WORKS) + 1):
            with self.subTest(number=number):
                self.assertIn('<i class="n">{0}</i>'.format(number), text)
        case_page = built_pages()[loaded_case(208).link]
        for who, colour in sorted(v2.STEP_COLOURS.items()):
            with self.subTest(who=who):
                self.assertIn(
                    '<i style="background:{0}"></i>'.format(colour), case_page
                )

    def test_the_intro_names_the_sample_and_never_says_generalisation(self):
        text = index_text()
        self.assertIn(v2._text(v2.WHAT_THE_DISPUTES_ARE), text)
        self.assertIn("case 901", text)
        self.assertIn("call no model", text)
        self.assertNotIn("generalisation", text)
        self.assertNotIn("generalization", text)

    def test_the_figures_line_links_the_readme_with_its_own_words(self):
        text = index_text()
        self.assertIn(
            '<a href="{0}">{1}</a>'.format(
                v2._attribute(v2.README_RESULTS_LINK),
                v2._text(v2.README_RESULTS_WORDS),
            ),
            text,
        )

    def test_the_links_row_carries_the_architecture_views_and_the_case(self):
        """The "Architecture" link opens the dynamic view, the other three beside it.

        The set is four views, and the one a reader wants first is the dynamic
        one -- one dispute, step by step -- so it carries the plain label and the
        three container views are named beside it.
        """
        text = index_text()
        for view, label in v2.ARCHITECTURE_VIEWS:
            with self.subTest(view=view):
                self.assertIn(
                    '<a href="{0}">{1}</a>'.format(
                        v2._attribute(v2.architecture_link(view)), v2._text(label)
                    ),
                    text,
                )
        self.assertEqual("3-dynamic-one-dispute.svg", v2.ARCHITECTURE_VIEWS[0][0])
        self.assertIn(
            '<a href="{0}">Architecture</a>'.format(
                v2._attribute(v2.ARCHITECTURE_LINK)
            ),
            text,
        )
        self.assertIn(
            '<a href="case-{0:05d}.html">How it was decided: see case {0}</a>'.format(
                v2.HOW_IT_WAS_DECIDED_CASE
            ),
            text,
        )

    def test_every_page_says_what_it_replays_and_keeps_the_model_in_the_footer(self):
        text = index_text()
        self.assertIn("Recorded runs, policy version", text)
        self.assertNotIn("Replay - policy", text)

    def test_the_five_steps_are_five_columns_on_a_wide_screen(self):
        """The strip wrapped into three ragged lines with the arrows at the ends.

        At 1000 px and wider the five steps are five equal columns in one row,
        with each arrow at its own column's right; below that the strip stacks
        as it did.
        """
        self.assertIn(
            ".how ol{display:flex;flex-wrap:wrap;", v2._CSS, "the stacked layout moved"
        )
        self.assertIn("@media (min-width:1000px){", v2._CSS)
        self.assertIn(
            ".how ol{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));",
            v2._CSS,
            "the five steps are not five equal columns",
        )
        self.assertIn(
            ".how .arw{position:absolute;right:0;", v2._CSS, "the arrows still wrap"
        )

    def test_the_trace_box_runs_the_width_of_the_column(self):
        """A map drawn inside the details' padding loses 32 of the 360 px."""
        self.assertIn(".rail details.full{padding:0}", v2._CSS)
        self.assertIn('class="full"', built_pages()[loaded_case(208).link])


class SafeguardsTests(unittest.TestCase):
    """52.1: the safeguards card, and the accessibility line under it.

    Two of the ten judging dimensions are responsible AI and accessibility, and
    neither was named on the front page. The card states the seven things the
    system does to keep a person in the loop, and the reviewer figure on its
    second line is the lane tile's own -- read from the same computation rather
    than typed in here -- so the tile and the card cannot disagree.
    """

    def section(self) -> str:
        """The safeguards section alone, from its own opening tag to its close."""
        text = index_text()
        start = text.index('<section class="safeguards"')
        return text[start : text.index("</section>", start)]

    def test_the_queue_carries_one_safeguards_section_with_its_id_and_heading(self):
        text = index_text()
        self.assertEqual(1, text.count('<section class="safeguards"'))
        self.assertIn(
            '<section class="safeguards" id="safeguards" '
            'aria-labelledby="safeguards-h">',
            text,
        )
        self.assertIn('<h2 id="safeguards-h">Safeguards</h2>', text)
        # The links row is the way down to it, and the fragment resolves.
        self.assertIn('<a href="#safeguards">Safeguards</a>', text)

    def test_the_seven_lead_words_are_there_in_order(self):
        section = self.section()
        self.assertEqual(7, len(v2.SAFEGUARD_LEADS))
        positions = []
        for lead in v2.SAFEGUARD_LEADS:
            with self.subTest(lead=lead):
                self.assertIn(v2._text(lead), section)
                positions.append(section.index(v2._text(lead)))
        self.assertEqual(
            sorted(positions), positions, "the safeguards are out of order"
        )

    def test_the_reviewer_count_is_the_lane_tiles_own(self):
        """The figure on line 2 is the tile's, from the one computation."""
        figures = v2.queue_figures(loaded_cases())
        lane = "{0} of {1}".format(figures.reviewer, figures.total)
        self.assertIn('<p class="v">{0}</p>'.format(lane), index_text())
        self.assertIn(
            "{0} of {1} queued disputes".format(figures.reviewer, figures.total),
            self.section(),
        )

    def test_the_two_case_links_resolve_inside_the_site(self):
        section = self.section()
        names = set(built_pages())
        for case_no in (
            v2.SAFEGUARD_SAFETY_CASE,
            v2.SAFEGUARD_PLANTED_CLAUSE_CASE,
        ):
            link = "case-{0:05d}.html".format(case_no)
            with self.subTest(case=case_no):
                self.assertIn(
                    '<a href="{0}">case {1}</a>'.format(link, case_no), section
                )
                self.assertIn(link, names)

    def test_the_accessibility_line_is_present(self):
        section = self.section()
        self.assertIn(v2._text(v2.SAFEGUARDS_ACCESSIBILITY), section)
        self.assertIn(
            '<a href="{0}">{1}</a>'.format(
                v2._attribute(v2.ACCESSIBILITY_NOTE_LINK),
                v2._text(v2.ACCESSIBILITY_SCAN_WORDS),
            ),
            section,
        )

    def test_the_section_carries_no_script(self):
        self.assertNotIn("<script", self.section())


class HeroTests(unittest.TestCase):
    """51b.4: the queue opens with the poster, and with the two ways in."""

    def test_the_queue_carries_the_poster_with_its_size_and_its_words(self):
        """The image states its own size, so the box is held before it arrives."""
        text = index_text()
        self.assertIn(
            '<img src="{0}" width="{1}" height="{2}" alt="{3}">'.format(
                v2._attribute(v2.COVER_LINK),
                v2.COVER_WIDTH,
                v2.COVER_HEIGHT,
                v2._attribute(v2.COVER_ALT),
            ),
            text,
        )
        self.assertIn(
            '<figcaption class="cap">{0}</figcaption>'.format(
                v2._text(v2.COVER_CAPTION)
            ),
            text,
            "the poster carries no caption saying where it came from",
        )
        self.assertIn("height:auto", v2._CSS, "the poster is not allowed to scale")

    def test_the_poster_is_a_file_inside_the_site(self):
        """A hero pointing at a path outside ``ui/dist/`` is a 404 when served."""
        target = v2.DIST_DIR / v2.COVER_LINK
        self.assertTrue(target.is_file(), "the poster is not committed")
        self.assertEqual(v2.COVER_SOURCE.read_bytes(), target.read_bytes())

    def test_the_how_it_works_button_points_at_the_section_it_names(self):
        text = index_text()
        self.assertIn(
            '<a class="btn btn-out" href="#how">How it works</a>',
            text,
            "the hero carries no link to the strip",
        )
        self.assertIn('id="how"', text, "the strip carries no anchor to land on")

    def test_the_see_case_button_resolves_inside_the_site(self):
        """The hero's first button is the case the front page is about."""
        link = "case-{0:05d}.html".format(v2.HOW_IT_WAS_DECIDED_CASE)
        self.assertIn(
            '<a class="btn btn-fill" href="{0}">See case {1}</a>'.format(
                link, v2.HOW_IT_WAS_DECIDED_CASE
            ),
            index_text(),
        )
        self.assertTrue((v2.DIST_DIR / link).is_file())

    def test_the_hero_is_one_column_until_a_thousand_pixels(self):
        """Below 1000 px the poster sits under the words, not beside them."""
        self.assertIn(
            ".hero{display:grid;grid-template-columns:minmax(0,1fr);", v2._CSS
        )
        self.assertIn(".hero h1{font-size:2rem}", v2._CSS)


def decision_step(page: str, number: int) -> str:
    """One pane of the "How it was decided" stepper, by its own ``data-pane``."""
    marker = '<div class="pane'
    start = page.index('data-pane="{0}"'.format(number))
    start = page.rindex(marker, 0, start)
    following = page.find(marker, start + len(marker))
    end = following if following != -1 else page.index("</div></div>", start)
    return page[start:end]


def claim_pieces(text: str) -> List[str]:
    """The pieces of one claim a page shows: the first sentence, then the rest.

    A claim is a paragraph of 80-200 words, so the page shows its first sentence
    and keeps the argument for it behind a collapsed detail. The pieces are the
    paragraph's own; nothing is rewritten.
    """
    whole = str(text or "").strip()
    match = re.search(r"(?<=[.!?])\s+", whole)
    if match is None:
        return [whole]
    first = whole[: match.start()].strip()
    rest = whole[match.end():].strip()
    return [first] + ([rest] if rest else [])


class DebateViewTests(unittest.TestCase):
    """The "Both sides argue" and "Judge" steps read as a debate, not as JSON."""

    def test_both_sides_argue_shows_two_columns_of_claim_cards(self):
        case = loaded_case(208)
        step = decision_step(built_pages()[case.link], 2)
        self.assertIn('class="debate"', step)
        self.assertIn("Rider advocate", step)
        self.assertIn("Driver advocate", step)
        self.assertGreaterEqual(step.count('class="claim"'), 19)
        self.assertIn(v2.READ_THE_WHOLE_CLAIM, step)
        for side in ("RIDER", "DRIVER"):
            claims = v2._claims(case.transcript, side)
            self.assertTrue(claims)
            for claim in claims[:2]:
                pieces = claim_pieces(claim["text"])
                with self.subTest(side=side, text=claim["text"][:40]):
                    self.assertGreaterEqual(len(pieces), 1)
                    for piece in pieces:
                        self.assertIn(v2._text(piece), step)

    def test_a_claim_carries_the_artifact_kind_and_the_clause_title(self):
        """The evidence chip names the kind; the clause chip carries the title.

        The title is on the chip's ``title`` for a pointer and inside the chip,
        revealed when it has focus, for a reader who cannot hover.
        """
        case = loaded_case(208)
        step = decision_step(built_pages()[case.link], 2)
        kinds = v2._evidence_kinds(case)
        self.assertIn("GPS trace", step)
        self.assertEqual("GPS trace", kinds["EV-GPS-00208"])
        title = case.policy.title("POL-NS-01")
        self.assertNotEqual("POL-NS-01", title, "the policy states no clause title")
        self.assertIn('title="{0}"'.format(v2._attribute(title)), step)
        self.assertIn(
            '<span class="ct">{0}</span>'.format(v2._text(title)),
            step,
            "the clause title is not the chip's own text on focus",
        )

    def test_the_citation_check_counts_each_side_and_words_each_discard(self):
        case = loaded_case(104)
        step = decision_step(built_pages()[case.link], 3)
        discarded = []
        for side, heading in (("RIDER", "Rider advocate"), ("DRIVER", "Driver advocate")):
            claims = v2._claims(case.transcript, side)
            kept = sum(1 for claim in claims if claim["status"] == "KEPT")
            dropped = [claim for claim in claims if claim["status"] == "DISCARDED"]
            with self.subTest(side=side):
                self.assertIn(
                    "{0}: {1} kept, {2} discarded".format(heading, kept, len(dropped)),
                    step,
                )
            discarded.extend(dropped)
        self.assertTrue(discarded, "104 has no discarded claim to check")
        for claim in discarded:
            code = str(claim["reason_code"])
            with self.subTest(code=code):
                self.assertIn(v2._text(v2.referee_words(code)), step)
                self.assertIn(v2._text(code), step)
                self.assertIn(v2._text(claim["detail"]), step)

    def test_the_judge_step_shows_four_draft_cards_and_marks_the_majority(self):
        case = loaded_case(208)
        step = decision_step(built_pages()[case.link], 4)
        drafts = v2._drafts(case.transcript)
        self.assertEqual(4, len(drafts))
        self.assertEqual(4, step.count('class="dcard"'))
        for draft in drafts:
            with self.subTest(draft=draft["draft"]):
                self.assertIn(
                    "Draft {0} &middot;".format(v2._text(draft["draft"])), step
                )
        self.assertEqual(4, step.count("in the majority"))
        self.assertEqual(4, step.count(">carried<"))
        self.assertIn(v2.ruling_words("DRIVER_COMPENSATION"), step)
        self.assertIn(v2._money("6.40", case.policy.currency), step)

    def test_a_voided_draft_carries_its_reason_in_words(self):
        case = loaded_case(1779)
        step = decision_step(built_pages()[case.link], 4)
        drafts = v2._drafts(case.transcript)
        self.assertTrue(drafts)
        self.assertTrue(all(not draft["valid"] for draft in drafts))
        self.assertEqual(len(drafts), step.count(">voided<"))
        self.assertNotIn("in the majority", step)
        for code in {str(draft["abstention"]).split(":")[0] for draft in drafts}:
            with self.subTest(code=code):
                self.assertIn(v2._text(v2.draft_words(code)), step)

    def test_every_reason_code_a_page_can_meet_has_words_of_its_own(self):
        """No page may print a bare ``DRAFT_*`` or referee code.

        Both mappings are held to the module that defines the codes, so a code
        the pipeline or the referee adds is caught here rather than drawn as a
        constant on a page.
        """
        for code in pipeline_module.DRAFT_CHECK_CODES:
            with self.subTest(draft_code=code):
                self.assertIn(code, v2.DRAFT_WORDS)
                self.assertNotEqual(code, v2.draft_words(code))
        for code in referee_module.REASON_CODES:
            with self.subTest(referee_code=code):
                self.assertIn(code, v2.REFEREE_WORDS)
                self.assertNotEqual(code, v2.referee_words(code))

    def test_a_step_header_shows_a_time_only_where_the_run_recorded_one(self):
        """The two steps that asked a model carry the seconds the run recorded.

        The other four asked no model, so they carry no time at all rather than
        the words "no time recorded", which were the page saying nothing.
        """
        case = loaded_case(208)
        page = built_pages()[case.link]
        self.assertNotIn("no time recorded", page)
        advocate = v2._seconds_for_roles(case, ("RIDER_ADVOCATE", "DRIVER_ADVOCATE"))
        judge = v2._seconds_for_entries(
            case,
            [
                index
                for draft in v2._drafts(case.transcript)
                for index in draft["entry_indices"]
            ],
        )
        self.assertIsNotNone(advocate)
        self.assertIsNotNone(judge)
        self.assertIn(v2._text(advocate), page)
        self.assertIn(v2._text(judge), page)
        self.assertEqual(
            len(v2.STEP_TITLES),
            page.count('<span class="s">'),
            "a step lost its summary line",
        )


# --------------------------------------------------------------------------
# The dispute, the record, and the notice to the parties
# --------------------------------------------------------------------------
NOTICE_RE = re.compile(r'<div class="notice" id="notice">.*?</div>', re.S)

# The notice's clause line and its evidence line, cut out of the notice so a
# test can say what those two lines carry and nothing else.
NOTICE_CLAUSE_LINE_RE = re.compile(
    r"<b>Clauses named in the ruling\.</b> (.*?)</p>", re.S
)
NOTICE_EVIDENCE_LINE_RE = re.compile(r"<b>Evidence cited\.</b> (.*?)</p>", re.S)


class DisputeTests(unittest.TestCase):
    """Every case page tells the dispute, out of the brief the agents were handed."""

    def test_every_case_page_carries_the_claim(self):
        for case in loaded_cases():
            page = built_pages()[case.link]
            dispute = v2._brief_dispute(case)
            with self.subTest(case=case.case_no):
                self.assertIn('id="the-dispute"', page)
                self.assertIn("The dispute", page)
                self.assertIn(v2._text(dispute.get("claim_text")), page)

    def test_case_208_carries_the_whole_claim_the_statement_and_the_call(self):
        """The case the description sends a judge to."""
        case = loaded_case(208)
        page = built_pages()[case.link]
        self.assertIn("guardhouse almost 15 minutes", page)
        statement = v2._brief_dispute(case).get("counterparty_statement") or {}
        self.assertIn(v2._text(statement.get("text")), page)
        calls = [
            message
            for message in v2._chat_messages(case)
            if str(message.get("channel")) == v2.CALL_LOG_CHANNEL
        ]
        self.assertTrue(calls, "208 carries no call-log entry to check")
        for message in calls:
            self.assertIn(v2._text(message.get("text")), page)
        self.assertIn("Call log:", page)

    def test_the_chat_is_masked_as_the_brief_masks_it(self):
        """The page carries the text the agents were handed, not the raw file's.

        208's chat message names the driver's plate. POL-GEN-08(4) replaces it
        in front of the model, and the page shows the replaced text: a page that
        carried the plate would be publishing the identifier the mask exists to
        keep off it. The public case file is serialised with ``default=str``
        because it is read with ``parse_float=Decimal``, and the control is that
        the raw plate is in the record: a ``json.dumps`` that raised on the
        ``Decimal`` would prove nothing about the page.
        """
        case = loaded_case(208)
        page = built_pages()[case.link]
        self.assertIn("SJK8842P", json.dumps(public_case("corpus", 208), default=str))
        self.assertNotIn("SJK8842P", page)
        self.assertIn("[vehicle registration masked]", page)

    def test_a_no_show_page_carries_the_records_own_facts(self):
        """The table is the brief's derived facts, and only a no-show carries it.

        The test looks for the table by its own section id rather than for the
        words "What the record shows": the judge's reasoning is quoted verbatim
        further down the page, and eight cases of the other category open a
        paragraph with those very words. What must not appear on a non-no-show
        page is the table, and the section id is the table.
        """
        no_shows = [
            case for case in loaded_cases() if case.category == "NO_SHOW_CHARGE"
        ]
        self.assertTrue(no_shows, "no no-show case to check")
        for case in no_shows:
            page = built_pages()[case.link]
            rows = v2._record_rows(case)
            with self.subTest(case=case.case_no):
                self.assertTrue(rows)
                self.assertIn('id="what-the-record-shows"', page)
                self.assertIn("What the record shows", page)
                self.assertIn("computed from the record, before any model", page)
                for fact, value in rows:
                    self.assertIn(v2._text(fact), page)
                    self.assertIn(v2._text(value), page)
        for case in loaded_cases():
            if case.category == "NO_SHOW_CHARGE":
                continue
            with self.subTest(case=case.case_no):
                self.assertNotIn(
                    'id="what-the-record-shows"', built_pages()[case.link]
                )


class TheNoticeTests(unittest.TestCase):
    """The notice to the two parties: on every page, and naming no profile field."""

    def notice_of(self, name: str) -> str:
        match = NOTICE_RE.search(built_pages()[name])
        self.assertIsNotNone(match, "{0} carries no notice".format(name))
        assert match is not None
        return match.group(0)

    def clause_line_of(self, name: str) -> str:
        match = NOTICE_CLAUSE_LINE_RE.search(self.notice_of(name))
        self.assertIsNotNone(match, "{0} carries no clause line".format(name))
        assert match is not None
        return match.group(1)

    def evidence_line_of(self, name: str) -> str:
        match = NOTICE_EVIDENCE_LINE_RE.search(self.notice_of(name))
        self.assertIsNotNone(match, "{0} carries no evidence line".format(name))
        assert match is not None
        return match.group(1)

    def test_every_case_page_carries_the_notice(self):
        for case in loaded_cases():
            notice = self.notice_of(case.link)
            with self.subTest(case=case.case_no):
                self.assertIn(v2.NOTICE_TITLE, notice)
                for line in (
                    "<b>Outcome.</b>",
                    "<b>The money.</b>",
                    "<b>Clauses named in the ruling.</b>",
                    "<b>Evidence cited.</b>",
                    "<b>Who decided.</b>",
                    "<b>Appeal.</b>",
                ):
                    self.assertIn(line, notice)

    def test_the_notice_names_no_profile_field_of_either_party(self):
        for case in loaded_cases():
            notice = self.notice_of(case.link)
            with self.subTest(case=case.case_no):
                self.assertNotIn("rider_profile.", notice)
                self.assertNotIn("driver_profile.", notice)

    def test_the_notice_states_the_policy_and_the_record_it_rests_on(self):
        for case in loaded_cases():
            notice = self.notice_of(case.link)
            with self.subTest(case=case.case_no):
                self.assertIn("POL-GEN-04", notice)
                for clause_id in v2._cited_clause_ids(case):
                    self.assertIn(case.policy.title(clause_id), notice)
                for kind in v2._cited_evidence_kinds(case):
                    self.assertIn(v2.EVIDENCE_KIND_WORDS[kind], notice)

    def test_the_notice_names_at_most_five_clauses_and_no_others(self):
        """The clause line is the ruling's referrals and its opening, and stops.

        A ruling's explanation names the clauses it rejects as well as the ones
        it rests on -- 208's names twelve -- so the line reads the ruling's own
        ``referrals`` and the first sentence of its explanation that names a
        clause, and it stops at ``NOTICE_CLAUSE_LIMIT``. Where that is empty the
        line falls back to a sentence pointing at the reviewer view rather than
        to a guess.
        """
        self.assertEqual(5, v2.NOTICE_CLAUSE_LIMIT)
        for case in loaded_cases():
            clause_line = self.clause_line_of(case.link)
            named = re.findall(r"POL-[A-Z]+-[0-9]+", clause_line)
            with self.subTest(case=case.case_no):
                self.assertEqual(
                    v2._cited_clause_ids(case),
                    named,
                    "the clause line is not the set the builder rests on",
                )
                self.assertLessEqual(len(named), v2.NOTICE_CLAUSE_LIMIT)
                if named:
                    for clause_id in named:
                        self.assertIn(case.policy.title(clause_id), clause_line)
                else:
                    self.assertIn(v2.NO_CLAUSE_NAMED, self.notice_of(case.link))

    def test_208s_notice_names_the_clause_the_ruling_rests_on(self):
        """208's notice named every clause its explanation mentions: twelve.

        What the ruling rests on is POL-NS-01, the baseline chargeable no-show.
        The clauses its reasoning rejects -- POL-GEN-01, POL-GEN-07, POL-NS-04
        and POL-NS-05 among them -- must not be on the line at all.
        """
        case = loaded_case(208)
        clause_line = self.clause_line_of(case.link)
        named = re.findall(r"POL-[A-Z]+-[0-9]+", clause_line)
        self.assertLessEqual(len(named), v2.NOTICE_CLAUSE_LIMIT)
        self.assertIn("POL-NS-01", named)
        self.assertIn(case.policy.title("POL-NS-01"), clause_line)
        for rejected in ("POL-GEN-01", "POL-GEN-07", "POL-NS-04", "POL-NS-05"):
            with self.subTest(clause=rejected):
                self.assertNotIn(rejected, clause_line)

    def test_209s_notice_counts_no_artifact_its_ruling_says_is_absent(self):
        """209's ruling names the missing advisory, and the notice must not count it.

        The explanation says in as many words that no traffic advisory exists --
        it names the artifact's own identifier while saying so -- so a line that
        counted the kinds the ruling *names* would count one that is not in the
        record. The line counts the kinds whose weight is above 0 and whose
        status is not MISSING.
        """
        case = loaded_case(209)
        explanation = str(case.ruling.get("explanation") or "")
        self.assertIn("EV-ADVIS-00209-01", explanation)
        self.assertIn("MISSING", explanation)
        evidence_line = self.evidence_line_of(case.link)
        self.assertNotIn("traffic advisory", evidence_line)
        self.assertEqual(
            ["GPS_TRACE", "CHAT_LOG", "TRIP_RECORD"],
            v2._cited_evidence_kinds(case),
        )
        for kind in v2._cited_evidence_kinds(case):
            self.assertIn(v2.EVIDENCE_KIND_WORDS[kind], evidence_line)

    def test_209s_notice_names_no_clause_its_ruling_says_does_not_apply(self):
        """209's reasoning is one paragraph, and it rejects three clauses in it.

        POL-NS-04 does not exonerate the rider, POL-NS-05's false-arrival limb
        does not fire, and POL-NS-07 is never reached. The clause line must name
        the clause the ruling turns on and none of those three.
        """
        case = loaded_case(209)
        clause_line = self.clause_line_of(case.link)
        named = re.findall(r"POL-[A-Z]+-[0-9]+", clause_line)
        self.assertIn("POL-NS-01", named)
        for rejected in ("POL-NS-04", "POL-NS-05", "POL-NS-07"):
            with self.subTest(clause=rejected):
                self.assertNotIn(rejected, clause_line)

    def test_an_escalated_notice_says_a_person_decides_and_the_money_is_held(self):
        """The page's own disclosure, and not the record's quoted words.

        Two escalated cases' own drafts write "this is a provisional ruling" in
        their explanations, and those are shown verbatim: rewriting them would
        be editing the record. What must not appear is the **page's** disclosure,
        which described a ruling that was never made.
        """
        escalated = [case for case in loaded_cases() if case.trigger is not None]
        self.assertEqual(26, len(escalated))
        for case in escalated:
            page = built_pages()[case.link]
            with self.subTest(case=case.case_no):
                self.assertIn(v2.NO_AUTOMATED_RULING, self.notice_of(case.link))
                self.assertNotIn(v2.DISCLOSURE, page)
        for case in loaded_cases():
            if case.trigger is not None:
                continue
            with self.subTest(case=case.case_no):
                self.assertIn(v2.DISCLOSURE, built_pages()[case.link])


# --------------------------------------------------------------------------
# What an escalated page says about the panel that could not decide
# --------------------------------------------------------------------------
class EscalatedPageTests(unittest.TestCase):
    """The ruling panel of a case sent to a person: the headline, the tile, the drafts."""

    def escalated(self) -> List[Any]:
        return [case for case in loaded_cases() if case.trigger is not None]

    def test_the_headline_names_who_decides_next_and_the_reason_is_under_it(self):
        """The headline was the reason in lower case, with its code beneath.

        A reader met "no judge draft passed the code checks" as the verdict of a
        case that has no verdict. The headline says who decides next and the
        reason sits under it, in words first and in the record's own code after.
        """
        for case in self.escalated():
            page = built_pages()[case.link]
            headline = '<p class="word">{0}</p>'.format(v2._text(v2.SENT_TO_A_PERSON))
            reason = v2._coded(
                v2.trigger_words(str(case.trigger), case.votes), case.trigger
            )
            with self.subTest(case=case.case_no):
                self.assertIn(headline, page)
                self.assertIn(
                    '<p class="code">{0}</p>'.format(reason),
                    page,
                    "the reason is not under the headline",
                )

    def test_no_escalated_page_shows_a_confidence_for_a_ruling_that_was_never_made(self):
        """The tile read "0.0 confidence against the floor of 0.7".

        The 0.0 an escalation record carries is the absence of a figure, not a
        low one -- the drafts' own confidences are on the drafts -- so the tile
        says no ruling was carried instead.
        """
        for case in self.escalated():
            tiles = v2.key_figure_tiles(case)
            text = " ".join("{0} {1}".format(value, label) for value, label in tiles)
            with self.subTest(case=case.case_no):
                self.assertIn(v2.NO_RULING_CARRIED, text)
                self.assertNotIn("confidence against the floor of", text)
        for case in loaded_cases():
            if case.trigger is not None:
                continue
            text = " ".join(
                "{0} {1}".format(value, label)
                for value, label in v2.key_figure_tiles(case)
            )
            with self.subTest(case=case.case_no):
                self.assertNotIn(v2.NO_RULING_CARRIED, text)

    def test_the_drafts_are_a_table_one_row_each_and_each_reason_once(self):
        """The pipeline's list of drafts is drawn as a table, not as a paragraph.

        Each line of that list repeats a draft's reason as many times as the
        check recorded it, and the vote drops a voided draft's proposal, so the
        table reads the draft's own answer off the transcript and shows every
        reason once.
        """
        for case in self.escalated():
            drafts = v2._drafts(case.transcript)
            if not drafts:
                continue
            page = built_pages()[case.link]
            # The ruling panel: the verdict card, up to the line after the
            # summary. The reviewer's packet carries the pipeline's explanation
            # verbatim by design, so this check is about the panel a reader
            # meets first.
            panel = page[page.index('<div class="verdict">') : page.index('<p class="after">')]
            with self.subTest(case=case.case_no):
                self.assertIn("<th>Why it was voided</th>", panel)
                for draft in drafts:
                    row = "<td>{0}</td>".format(v2._text(draft["draft"]))
                    self.assertIn(row, panel)
                    self.assertIn(v2._text(v2._draft_proposal(case, draft)), panel)
                for line in str(case.ruling.get("explanation") or "").split("\n"):
                    if v2.DRAFT_LINE_RE.match(line.strip()):
                        self.assertNotIn(
                            v2._text(line),
                            panel,
                            "the pipeline's one-line-each draft list is still printed",
                        )

    def test_1779s_table_shows_the_four_drafts_and_the_clause_they_quoted(self):
        """The featured card's own reading of the case, as a table."""
        case = loaded_case(1779)
        page = built_pages()[case.link]
        drafts = v2._drafts(case.transcript)
        self.assertEqual(4, len(drafts))
        self.assertTrue(all(not draft["valid"] for draft in drafts))
        for draft in drafts:
            with self.subTest(draft=draft["draft"]):
                self.assertEqual("PARTIAL_REFUND", draft["ruling"])
                self.assertEqual(
                    "Partial refund - SGD 5.70", v2._draft_proposal(case, draft)
                )
                self.assertIn(v2._text(v2._draft_proposal(case, draft)), page)
                self.assertIn(v2._text(v2.draft_words("DRAFT_CLAUSE_UNRESOLVED")), page)
        self.assertIn(v2._text("'POL-RD-99' does not resolve in the loaded policy"), page)
        self.assertIn("refused the planted clause", built_pages()["index.html"])


# --------------------------------------------------------------------------
# A held amount: who releases it, and the notice that says so
# --------------------------------------------------------------------------
class HeldAmountTests(unittest.TestCase):
    """A decided case whose money POL-GEN-05 holds above the execution threshold."""

    def held(self) -> List[Any]:
        return [case for case in loaded_cases() if v2._money_is_held(case)]

    def test_the_notice_says_the_amount_is_held_rather_than_paid(self):
        held = self.held()
        self.assertTrue(held, "no case has a held amount to check")
        for case in held:
            page = built_pages()[case.link]
            line = v2.held_money_statement(
                case.ruling,
                case.policy,
                (case.case.get("dispute") or {}).get("filed_by"),
            )
            with self.subTest(case=case.case_no):
                self.assertIn(v2._text(line), page)
                self.assertIn(
                    "is held above POL-GEN-05's execution threshold of {0} until a "
                    "person releases it".format(
                        v2._money(case.policy.execution_threshold, case.policy.currency)
                    ),
                    page,
                )

    def test_a_held_case_carries_the_short_chip_and_no_review_tab(self):
        """``ops.review`` cannot record a release, so the page says who can.

        It insists on the digest of an escalation packet and
        ``ops.escalation`` builds a packet only for an escalated case, which a
        held case is not -- so there is no Human review tab, and the notice
        names the queue and the command that does record it.
        """
        for case in self.held():
            page = built_pages()[case.link]
            with self.subTest(case=case.case_no):
                self.assertIn(">Held for release</span>", v2.status_chip(case))
                self.assertNotIn('data-panel="review"', page)
                self.assertIn(v2._text(v2.release_sentence(case.policy)), page)
                self.assertIn(v2.HELD_RELEASE_REASON, page)
                self.assertIn("tribunal.precedents close", page)
                self.assertIn("ops/review.py", page)

    def test_the_release_sentence_names_the_queue_reason_the_queue_uses(self):
        """The reason code is ``ops.queue``'s own, read rather than retyped."""
        from ops import queue as queue_module

        self.assertEqual(queue_module.REASON_GEN05_RELEASE, v2.HELD_RELEASE_REASON)


# --------------------------------------------------------------------------
# Link previews and the tab icon
# --------------------------------------------------------------------------
class LinkPreviewTests(unittest.TestCase):
    """What a scraper reads when a page is shared, and the icon in the tab."""

    def head_of(self, name: str) -> str:
        text = built_pages()[name]
        return text[: text.index("<style>")]

    def test_every_page_carries_a_description_a_favicon_and_an_open_graph_card(self):
        for name in sorted(built_pages()):
            head = self.head_of(name)
            with self.subTest(page=name):
                self.assertIn('<link rel="icon" href="data:image/svg+xml,', head)
                self.assertIn('<meta name="description" content="', head)
                for prop in ("og:title", "og:description", "og:type", "og:url", "og:image"):
                    self.assertIn(
                        '<meta property="{0}" content="'.format(prop), head
                    )
                self.assertIn(
                    '<meta name="twitter:card" content="summary_large_image">', head
                )

    def test_the_card_urls_are_absolute_and_the_image_is_the_one_committed(self):
        image = v2.SITE_ROOT + v2.OG_IMAGE_LINK
        for name in sorted(built_pages()):
            head = self.head_of(name)
            with self.subTest(page=name):
                self.assertIn(
                    '<meta property="og:image" content="{0}">'.format(
                        v2._attribute(image)
                    ),
                    head,
                )
                url = re.search(r'<meta property="og:url" content="([^"]+)"', head)
                self.assertIsNotNone(url, "the page carries no og:url")
                assert url is not None
                self.assertTrue(url.group(1).startswith(v2.SITE_ROOT))
                if name == "index.html":
                    self.assertEqual(v2.SITE_ROOT, url.group(1))
                else:
                    self.assertEqual(v2.SITE_ROOT + name, url.group(1))

    def test_the_image_is_in_the_site_and_is_the_owners_file_byte_for_byte(self):
        committed = v2.DIST_DIR / v2.OG_IMAGE_LINK
        self.assertTrue(committed.is_file(), "og-image.png is not committed")
        self.assertEqual(v2.OG_IMAGE_SOURCE.read_bytes(), committed.read_bytes())

    def test_the_tab_icon_is_the_header_mark_and_loads_nothing(self):
        """The icon is an inline ``data:`` SVG built from the header's own path."""
        self.assertIn(v2.SCALES_PATH, v2.SCALES_MARK)
        self.assertTrue(v2.FAVICON_DATA_URI.startswith("data:image/svg+xml,"))
        self.assertFalse(is_external_reference(v2.FAVICON_DATA_URI))
        self.assertTrue(v2.FAVICON_DATA_URI.isascii())

    def test_the_description_is_one_sentence_from_the_record(self):
        for case in loaded_cases():
            head = self.head_of(case.link)
            description = re.search(
                r'<meta name="description" content="([^"]*)"', head
            )
            self.assertIsNotNone(description)
            assert description is not None
            with self.subTest(case=case.case_no):
                self.assertIn(
                    v2._text(v2._summary_line(case.case))[:40], description.group(1)
                )


# --------------------------------------------------------------------------
# The page a host serves for an address that is not one of the site's
# --------------------------------------------------------------------------
class NotFoundTests(unittest.TestCase):
    """``ui/dist/404.html``: in the site's style, and it links the reader on."""

    def page(self) -> str:
        return built_pages()[v2.NOT_FOUND_LINK]

    def test_the_page_says_the_page_does_not_exist(self):
        text = self.page()
        self.assertIn("This page does not exist", text)
        self.assertIn(v2.NOT_FOUND_DESCRIPTION, text)

    def test_the_page_links_to_the_queue_and_to_case_208(self):
        text = self.page()
        self.assertIn('<a href="index.html">The queue</a>', text)
        self.assertIn(
            '<a href="case-{0:05d}.html">'.format(v2.HOW_IT_WAS_DECIDED_CASE), text
        )

    def test_the_page_is_in_the_site_s_own_shell(self):
        text = self.page()
        self.assertIn('<header class="top">', text)
        self.assertIn('<footer class="foot">', text)
        self.assertIn('<main class="wrap">', text)

    def test_the_page_is_committed_and_equals_a_fresh_build(self):
        committed = (v2.DIST_DIR / v2.NOT_FOUND_LINK).read_text(encoding="utf-8")
        self.assertEqual(self.page(), committed)


# --------------------------------------------------------------------------
# The stylesheet: contrast, keyboard sorting and the width of a table
# --------------------------------------------------------------------------
def relative_luminance(colour: str) -> float:
    """WCAG 2.1's relative luminance for a hex colour."""
    value = colour.lstrip("#")
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [
        channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(one: str, other: str) -> float:
    """WCAG 2.1 contrast, from 1.0 to 21.0."""
    first, second = relative_luminance(one), relative_luminance(other)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def custom_properties(block: str) -> Dict[str, str]:
    """The custom properties one ``:root`` block declares."""
    values: Dict[str, str] = {}
    for piece in block.split(";"):
        if ":" not in piece:
            continue
        name, value = piece.split(":", 1)
        values[name.strip()] = value.strip()
    return values


def stylesheet_rules(stylesheet: str) -> List[Tuple[str, str]]:
    """Every rule in a stylesheet, as ``(selector, declarations)``.

    Only the innermost blocks are yielded: a block whose body holds another
    block is a group (``@media``) and not a rule, so a group's text is never
    mistaken for one rule's declarations. The comments are stripped first,
    because this stylesheet explains itself at length and a comment can carry
    the very words a check is looking for -- ``background:var(--accent)`` is
    named in one. A selector is the text between the previous closing brace and
    the block's own opening brace, so a rule inside an ``@media`` group reads as
    the selector it is and not as the group's.
    """
    text = re.sub(r"/\*.*?\*/", "", stylesheet, flags=re.DOTALL)
    rules: List[Tuple[str, str]] = []
    for opening in re.finditer(r"\{", text):
        depth = 1
        index = opening.end()
        while index < len(text) and depth:
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        body = text[opening.end() : index - 1]
        if "{" in body:
            continue
        selector = text[: opening.start()].rsplit("}", 1)[-1].rsplit("{", 1)[-1]
        rules.append((selector.strip(), body))
    return rules


class StylesheetTests(unittest.TestCase):
    """The palette's stated contrasts, the sort buttons and the table that scrolls."""

    # The figure the stylesheet's own comment states for each pair, as
    # ``(foreground, background, theme, ratio)``. A number in a comment is a
    # claim, and this table is what makes each one a claim the suite recomputes
    # from the colour the page actually sets. An entry beginning ``--`` is a
    # token, read out of the palette that theme declares; anything else is the
    # colour itself. The first three are 37a.6's muted token, the eight after
    # them are 51b.5's accent -- four on the light backgrounds and white on it,
    # three on the dark ones -- the two after those are 51c.1's ``--on-accent``
    # on the accent in each theme (it was the bare ``#ffffff`` row in the light
    # one, and the dark pair is new), the six after those are 51d.1's
    # ``--on-status`` on the three token backgrounds the case page's step
    # circles are drawn on in each theme, and the last two are 51b.6's header
    # band.
    STATED_CONTRAST: Tuple[Tuple[str, str, str, float], ...] = (
        ("--muted", "--bg", "light", 5.45),
        ("--muted", "--card", "light", 6.00),
        ("--muted", "--soft", "light", 5.74),
        ("--accent", "--card", "light", 7.10),
        ("--accent", "--bg", "light", 6.46),
        ("--accent", "--soft", "light", 6.80),
        ("--accent", "--accent-wash", "light", 5.98),
        ("--accent", "--card", "dark", 7.92),
        ("--accent", "--bg", "dark", 9.67),
        ("--accent", "--soft", "dark", 8.67),
        ("--on-accent", "--accent", "light", 7.10),
        ("--on-accent", "--accent", "dark", 9.63),
        ("--on-status", "--grey", "light", 10.31),
        ("--on-status", "--ok", "light", 5.02),
        ("--on-status", "--bad", "light", 6.47),
        ("--on-status", "--grey", "dark", 12.02),
        ("--on-status", "--ok", "dark", 12.71),
        ("--on-status", "--bad", "dark", 9.41),
        ("--band-note", "--band", "light", 10.16),
        ("#ffffff", "--band", "light", 19.3),
    )

    def palette(self, theme: str) -> Dict[str, str]:
        """One theme's custom properties, read out of the stylesheet.

        The light palette is the first ``:root`` block. The dark palette is the
        block inside ``@media (prefers-color-scheme:dark)`` laid over the light
        one, which is what the cascade does: a token the dark block does not
        name keeps the light value, and ``--band`` is one of those.
        """
        light = re.search(r":root\{([^}]*)\}", v2._CSS)
        self.assertIsNotNone(light, "the stylesheet declares no :root block")
        assert light is not None
        values = custom_properties(light.group(1))
        if theme == "light":
            return values
        dark = re.search(
            r"prefers-color-scheme:dark\)\{\s*:root\{([^}]*)\}", v2._CSS
        )
        self.assertIsNotNone(dark, "the stylesheet declares no dark palette")
        assert dark is not None
        values.update(custom_properties(dark.group(1)))
        return values

    def colour(self, name: str, theme: str) -> str:
        """A table entry as a colour: a token of that theme, or the colour itself."""
        return self.palette(theme)[name] if name.startswith("--") else name

    def root(self) -> Dict[str, str]:
        """The light theme's custom properties, read out of the stylesheet."""
        return self.palette("light")

    def test_the_muted_token_clears_the_floor_on_every_light_background(self):
        """Muted text is text, and 4.5:1 is the floor it is held to."""
        muted = self.root()["--muted"]
        self.assertNotEqual("#6b7280", muted, "the token below the floor is back")
        rows = [
            (background, theme, stated)
            for foreground, background, theme, stated in self.STATED_CONTRAST
            if foreground == "--muted"
        ]
        self.assertEqual(3, len(rows), "the muted token's three backgrounds moved")
        for background, theme, stated in rows:
            with self.subTest(background=background):
                ratio = contrast_ratio(muted, self.colour(background, theme))
                self.assertGreaterEqual(round(ratio, 2), 4.5)
                self.assertEqual(
                    stated,
                    round(ratio, 2),
                    "the ratio the comment states is not the one this colour gives",
                )

    def test_every_stated_contrast_is_the_one_the_colour_gives(self):
        """51b.5/51b.6, 51c.1 and 51d.1: every pair the stylesheet states.

        The accent's eight pairs, the two ``--on-accent`` pairs 51c.1 added,
        the six ``--on-status`` pairs 51d.1 added and the header band's two are
        claims written in a comment, and a claim nobody recomputes drifts. Each
        is measured against the palette the page sets for its own theme and held
        to 4.5:1, the floor body text is held to, so a pair that fell below it
        fails here rather than in a reader's eyes -- which is exactly what white
        on the dark accent, and white on the dark step circles, both did.
        """
        for foreground, background, theme, stated in self.STATED_CONTRAST:
            with self.subTest(
                foreground=foreground, background=background, theme=theme
            ):
                ratio = contrast_ratio(
                    self.colour(foreground, theme), self.colour(background, theme)
                )
                self.assertGreaterEqual(
                    round(ratio, 2),
                    4.5,
                    "{0} on {1} is below the floor".format(foreground, background),
                )
                self.assertEqual(
                    stated,
                    round(ratio, 2),
                    "the ratio the comment states is not the one this colour gives",
                )

    def test_the_floor_would_have_caught_the_colour_it_replaced(self):
        """The control: the colour the token was, measured the same way."""
        root = self.root()
        self.assertLess(round(contrast_ratio("#6b7280", root["--bg"]), 2), 4.5)

    def test_text_on_the_accent_is_the_token_the_accent_carries(self):
        """51c.1, widened by 51d.1: a rule that paints a token background takes a token.

        In the dark theme the accent is #c4b5fd, a light lavender, and white on
        it measures 1.85:1 -- the floor body text is held to is 4.5:1. Two rules
        painted it white: the filled button, and the numbered circles of "How it
        works". The brand mark was the same shape of fault, a white glyph on the
        accent, so its strokes take ``currentColor`` and its tile the token.
        Every rule in the stylesheet that sets ``background:var(--accent)`` and
        names a colour must name ``--on-accent``, and no rule may pair the
        accent with white. The four are named, so a fifth cannot arrive quietly.

        51d.1 widened the same walk to the rest of the family. ``.stepper button
        .n i`` -- the case page's numbered step circles -- painted
        ``background:var(--grey)`` and set ``color:#fff``; in the dark theme
        ``--grey`` is #cbd5e1 and white on it measures 1.48:1, with ``i.ok`` on
        ``--ok`` at 1.40:1 and ``i.bad`` on ``--bad`` at 1.90:1, all under the
        4.5:1 floor. A token ``--on-status`` carries the text for those three
        backgrounds in either theme, and the rule takes it. So no rule in the
        stylesheet may set ``color:#fff`` or ``color:#ffffff`` beside a
        ``background:var(--...)`` whose token changes between the two themes;
        the header's own whites sit on ``--band``, which is #160b0e in both, and
        are the ones left alone.
        """
        painted: List[str] = []
        for selector, declarations in stylesheet_rules(v2._CSS):
            if "background:var(--accent)" not in declarations:
                continue
            with self.subTest(selector=selector):
                self.assertNotIn("color:#fff", declarations)
                self.assertNotIn("color:white", declarations)
                if "color:" in declarations:
                    painted.append(selector)
                    self.assertIn(
                        "color:var(--on-accent)",
                        declarations,
                        "{0} paints the accent and puts text on it in a colour "
                        "that is not the token".format(selector),
                    )
        self.assertEqual(4, len(painted), "the accent's text rules moved: {0}".format(painted))
        self.assertEqual(
            {".mark", ".btn-fill", ".stepper button .n i.llm", ".how .n"},
            set(painted),
        )
        self.assertEqual("#ffffff", self.palette("light")["--on-accent"])
        self.assertEqual("#1e1035", self.palette("dark")["--on-accent"])
        self.assertIn('stroke="currentColor"', v2.SCALES_MARK)
        self.assertIn("color:var(--on-accent)", v2._CSS)
        # 51d.1: the same fault on the second family of token backgrounds.
        light = self.palette("light")
        dark = self.palette("dark")
        self.assertEqual("#ffffff", light["--on-status"])
        self.assertEqual("#0f172a", dark["--on-status"])
        self.assertIn("color:var(--on-status)", v2._CSS)
        for selector, declarations in stylesheet_rules(v2._CSS):
            if "color:#fff" not in declarations and "color:#ffffff" not in declarations:
                continue
            with self.subTest(selector=selector):
                for token in re.findall(
                    r"background:var\((--[a-z0-9-]+)\)", declarations
                ):
                    self.assertEqual(
                        light[token],
                        dark[token],
                        "{0} sets white text on {1}, which changes between the "
                        "themes".format(selector, token),
                    )

    def test_the_held_note_wraps_so_the_queue_fits_a_desktop_screen(self):
        """51c.2: the note under a status chip is capped, so the table fits.

        The note is one sentence naming a figure and the threshold it crossed
        ("SGD 8.05 is above the POL-GEN-05 execution threshold of SGD 8.00"),
        and with nothing to stop it, it ran on one line: the Status column took
        414 px, the table came to 1285 px inside a 1230 px wrapper at a 1440 px
        window, and the Time column was cut off the right-hand edge. The cap
        makes it wrap onto two lines. Outcome keeps the floor 51b.10 gave it,
        and the box that scrolls is still what scrolls on a narrow screen.
        """
        note = re.search(r"\.held-why\{([^}]*)\}", v2._CSS)
        self.assertIsNotNone(note, "the held note has no rule of its own")
        assert note is not None
        self.assertIn("max-width:16rem", note.group(1))
        self.assertIn('td[data-column="outcome"]{min-width:11rem}', v2._CSS)
        self.assertIn(".tscroll{overflow-x:auto", v2._CSS)
        self.assertIn('<span class="held-why">', index_text())

    def test_the_lane_tiles_carry_lane_classes(self):
        """51c.3: the three lane tiles are ``lane-*``, so the global ``.ok`` misses.

        The tiles were ``<div class="figure ok">``, and the stylesheet's older
        global rule ``.ok{color:var(--ok);font-weight:600}`` matched them, so the
        first lane's figure turned green and its small print turned semibold
        while "figure warn" and "figure bad" matched no such rule. The lane
        modifiers are named for the tile, every lane rule is qualified by
        ``.figure``, and no ``.figure`` element in the built queue carries a bare
        ``ok``, ``warn`` or ``bad``.
        """
        text = index_text()
        for lane in ("ok", "warn", "bad"):
            with self.subTest(lane=lane):
                self.assertIn('class="figure lane-{0}"'.format(lane), text)
                self.assertIn(
                    ".figure.lane-{0}{{border-top:3px solid".format(lane), v2._CSS
                )
        self.assertEqual(3, text.count('class="figure lane-accent"'))
        self.assertIn(
            ".figure.lane-accent{border-top:3px solid var(--accent)}", v2._CSS
        )
        # The global status rule is left alone for whatever else uses it.
        self.assertIn(".ok{color:var(--ok);font-weight:600}", v2._CSS)
        for selector, _declarations in stylesheet_rules(v2._CSS):
            for lane in ("ok", "warn", "bad", "accent"):
                if ".lane-{0}".format(lane) in selector:
                    self.assertEqual(
                        ".figure.lane-{0}".format(lane),
                        selector,
                        "a lane rule is not qualified by .figure",
                    )
        # The page's own stylesheet is not markup: its comment quotes the class
        # this test is looking for, so the elements are read out of the body.
        body = re.sub(r"<style>.*?</style>", "", text, flags=re.DOTALL)
        for match in re.finditer(r'<div class="([^"]*)"', body):
            classes = match.group(1).split()
            if "figure" not in classes:
                continue
            with self.subTest(classes=match.group(1)):
                self.assertFalse(
                    {"ok", "warn", "bad"} & set(classes),
                    "a .figure element still carries a bare status class",
                )

    def test_the_queue_sorts_from_the_keyboard(self):
        """A header cell carries a button, and the cell carries the sort state."""
        text = index_text()
        for column in (
            "case",
            "category",
            "filed_by",
            "amount",
            "status",
            "outcome",
            "confidence",
            "time",
        ):
            with self.subTest(column=column):
                self.assertIn(
                    '<th data-column="{0}" aria-sort="none">'
                    '<button type="button" class="sort" data-column="{0}">'.format(
                        column
                    ),
                    text,
                )
        self.assertIn('head.setAttribute("aria-sort"', text)
        self.assertIn('"ascending"', text)
        self.assertIn('"descending"', text)
        self.assertIn(":focus-visible{outline:2px solid var(--accent)", v2._CSS)

    def test_a_wide_table_scrolls_inside_its_own_container(self):
        """The queue's table scrolls in a box of its own rather than being cut."""
        self.assertIn(".tscroll{overflow-x:auto", v2._CSS)
        self.assertIn(
            '<div class="tscroll" tabindex="0" role="region" '
            'aria-label="The queue of disputes"><table id="queue">',
            index_text(),
        )
        # The box is what scrolls, so every table a case page draws sits in one.
        for case in loaded_cases():
            with self.subTest(case=case.case_no):
                page = built_pages()[case.link]
                self.assertEqual(page.count("<table"), page.count('class="tscroll"'))

    def test_every_scrolling_table_can_be_reached_from_the_keyboard(self):
        """``scrollable-region-focusable``: a box that scrolls must take the focus.

        An axe-core scan of the live site found one violation type on the case
        pages: an ``overflow-x`` region with nothing focusable inside it cannot
        be scrolled without a pointer. Every wrapper carries the three
        attributes, each with a label naming the table it holds, and the
        stylesheet gives the focused box a ring of its own.
        """
        self.assertIn(
            ".tscroll:focus-visible{outline:2px solid var(--accent)", v2._CSS
        )
        pages = {"index.html": index_text()}
        for case in loaded_cases():
            pages[case.link] = built_pages()[case.link]
        wrappers = 0
        for name, page in sorted(pages.items()):
            self.assertEqual(
                page.count("<table"),
                page.count('class="tscroll"'),
                name + " draws a table outside the box that scrolls it",
            )
            for attributes in re.findall(r'<div class="tscroll"([^>]*)>', page):
                wrappers += 1
                with self.subTest(page=name, attributes=attributes):
                    self.assertIn('tabindex="0"', attributes)
                    self.assertIn('role="region"', attributes)
                    label = re.search(r'aria-label="([^"]*)"', attributes)
                    self.assertIsNotNone(
                        label, "a scrolling box carries no label naming its table"
                    )
                    assert label is not None
                    self.assertTrue(label.group(1).strip())
        self.assertGreater(wrappers, 0, "no page draws a scrolling table")


# --------------------------------------------------------------------------
# The status chips
# --------------------------------------------------------------------------
class StatusChipTests(unittest.TestCase):
    """Short words on the chip, and the detail where a reader looks for it."""

    def test_a_held_amount_gets_a_short_chip_and_the_reason_in_the_title(self):
        """The chip cannot wrap, so the figure travels in the title instead.

        The long form the owner saw -- "Decided automatically - SGD 8.05 held
        for a reviewer" -- overflowed the pill and changed the row's height.
        """
        held = [case for case in loaded_cases() if v2._money_is_held(case)]
        self.assertTrue(held, "no case has a held amount to check")
        queue = built_pages()["index.html"]
        for case in held:
            chip = v2.status_chip(case)
            reason = v2.held_reason(case)
            with self.subTest(case=case.case_no):
                self.assertIn(">Held for release</span>", chip)
                self.assertNotIn("SGD", chip, "the chip carries the figure it hides")
                self.assertIn("POL-GEN-05", reason)
                self.assertIn("execution threshold", reason)
                self.assertIn(
                    ' title="{0}"'.format(v2._attribute(reason)),
                    queue,
                    "the queue's status cell does not carry the reason",
                )
                self.assertIn(
                    v2.status_chip(case, with_time=True, title=True),
                    built_pages()[case.link],
                    "the case header does not carry the reason",
                )

    def test_every_chip_is_one_of_the_four_meanings(self):
        for case in loaded_cases():
            chip = v2.status_chip(case)
            with self.subTest(case=case.case_no):
                if case.trigger is not None:
                    self.assertIn('class="chip bad"', chip)
                    self.assertIn("Sent to a reviewer - ", chip)
                elif v2._money_is_held(case):
                    self.assertIn('class="chip warn"', chip)
                elif case.ruling.get("ruling") in (
                    "FULL_REFUND",
                    "PARTIAL_REFUND",
                    "NO_ACTION",
                    "DRIVER_COMPENSATION",
                ):
                    self.assertIn('class="chip ok"', chip)
                else:
                    self.assertIn('class="chip grey"', chip)

    def test_a_reviewer_row_shows_the_short_chip_and_the_words_under_it(self):
        """51d: the queue row's reviewer chip is short, its reason wraps below.

        51c capped the held note and the table still did not fit: the widest
        content in the Status column was the red reviewer chip, which never
        wraps -- "Sent to a reviewer - no judge draft passed the code checks" is
        384 px. The row now shows the short chip ``CHIP_LABELS`` names, and the
        trigger words travel under it in the same small wrapping note a held
        amount's reason uses, so the table fits its wrapper at 1280 px and
        wider. The words do not change; only where they sit does.
        """
        queue = built_pages()["index.html"]
        reviewer = [case for case in loaded_cases() if case.trigger is not None]
        self.assertEqual(26, len(reviewer))
        for case in reviewer:
            words = v2._text(v2.trigger_words(str(case.trigger), case.votes))
            with self.subTest(case=case.case_no):
                self.assertIn(
                    '<span class="chip bad">{0}</span>'
                    '<span class="held-why">{1}</span>'.format(
                        v2.CHIP_LABELS["reviewer"], words
                    ),
                    queue,
                    "the row does not put the trigger words under the short chip",
                )
        # Nothing follows the dash inside a queue chip: the chip is the label
        # alone, and the words are the note beside it.
        body = re.sub(r"<style>.*?</style>", "", queue, flags=re.DOTALL)
        texts = re.findall(r'<span class="chip ([a-z]+)">(.*?)</span>', body)
        self.assertEqual(
            {v2.CHIP_LABELS["reviewer"]},
            {text for kind, text in texts if kind == "bad"},
            "a queue chip still carries its reason inside the pill",
        )

    def test_the_case_page_keeps_the_long_reviewer_chip(self):
        """51d: the header's chip is unchanged -- only the queue row's moved.

        The case page is a heading, not a column, so it keeps
        ``status_chip(case, with_time=True)``: "Sent to a reviewer - <words> -
        <time>". The queue row is the one place the words moved under the chip.
        """
        reviewer = [case for case in loaded_cases() if case.trigger is not None]
        self.assertEqual(26, len(reviewer))
        for case in reviewer:
            chip = v2.status_chip(case, with_time=True)
            with self.subTest(case=case.case_no):
                self.assertIn("Sent to a reviewer - ", chip)
                self.assertIn(
                    chip,
                    built_pages()[case.link],
                    "the case page's header no longer carries the long chip",
                )

    def test_no_chip_in_the_queue_is_longer_than_the_short_labels(self):
        """51d: the widest a chip can be is the longest of the four labels.

        A chip does not wrap, so a chip longer than the longest of the four
        short labels ("Decided automatically", "Held for release", "Sent to a
        reviewer", "No status is recorded") is what widened the Status column
        past its wrapper. Every chip in the built queue is held to that width,
        so a long chip cannot come back and push the table off a desktop screen.
        """
        limit = max(len(label) for label in v2.CHIP_LABELS.values())
        queue = built_pages()["index.html"]
        body = re.sub(r"<style>.*?</style>", "", queue, flags=re.DOTALL)
        texts = re.findall(r'<span class="chip [a-z]+">(.*?)</span>', body)
        self.assertEqual(
            len(loaded_cases()),
            len(texts),
            "the queue does not draw one status chip per row",
        )
        for text in texts:
            with self.subTest(chip=text):
                self.assertLessEqual(
                    len(text),
                    limit,
                    "a queue chip is longer than the four short labels",
                )


# --------------------------------------------------------------------------
# 47.1: the outcome first
# --------------------------------------------------------------------------
class SummaryBarTests(unittest.TestCase):
    """The one line a case page opens with, read from the ruling and the lane."""

    def bar_of(self, page: str) -> str:
        match = re.search(r'<p class="summarybar">(.*?)</p>', page, re.S)
        self.assertIsNotNone(match, "the page carries no summary bar")
        assert match is not None
        return match.group(1)

    def test_every_case_page_states_the_outcome_the_money_and_who_decides(self):
        for case in loaded_cases():
            bar = self.bar_of(built_pages()[case.link])
            with self.subTest(case=case.case_no):
                self.assertIn(v2._text(v2._summary_outcome(case)), bar)
                self.assertIn(v2._summary_money(case), bar)
                self.assertIn(v2._summary_who(case), bar)

    def test_the_bar_sits_under_the_title_and_chips_and_links_to_the_ruling(self):
        case = loaded_case(208)
        page = built_pages()[case.link]
        chips = page.index("</div>\n", page.index('<div class="chips">'))
        self.assertLess(page.index("<h1>"), page.index('<p class="summarybar">'))
        self.assertLess(chips, page.index('<p class="summarybar">'))
        self.assertIn('<a href="#panel-ruling">Why</a>', self.bar_of(page))
        self.assertIn('id="panel-ruling"', page)

    def test_the_bar_uses_the_sheet_s_own_vocabulary(self):
        """Four phrases for the money and three for who decides, and nothing else."""
        who = set()
        for case in loaded_cases():
            who.add(re.sub(r"<[^>]+>", "", v2._summary_who(case)))
            money = re.sub(r"<[^>]+>", "", v2._summary_money(case))
            with self.subTest(case=case.case_no):
                self.assertTrue(
                    money in (v2.SUMMARY_MONEY_NOTHING, v2.SUMMARY_MONEY_HELD)
                    or money.startswith(v2.SUMMARY_MONEY_DRIVER + " ")
                    or re.match(
                        r"^refund to the [a-z]+(?: [a-z]+)? SGD [0-9.]+$", money
                    ),
                    money,
                )
        self.assertTrue(
            who
            <= {
                v2.SUMMARY_WHO_PANEL,
                v2.SUMMARY_WHO_HELD,
                v2.SUMMARY_WHO_PERSON,
            },
            sorted(who),
        )

    def test_a_refund_over_the_contested_amount_is_named_and_explained(self):
        """47.4: the figure the page shows is POL-RD-02's arithmetic, not a cap.

        The eight recorded rulings the sheet names -- seven of them in the
        dev-v2-ext run this site draws -- show a refund larger than the amount
        contested. On those pages the money line is followed by a sentence
        saying where the figure comes from; on every other page it is not.
        """
        over = []
        for case in loaded_cases():
            page = built_pages()[case.link]
            note = v2.refund_over_contested(case)
            amount = v2._decimal(case.ruling.get("amount_sgd"))
            contested = v2._decimal(
                (case.case.get("dispute") or {}).get("amount_contested_sgd")
            )
            with self.subTest(case=case.case_no):
                if (
                    str(case.ruling.get("ruling")) in ("FULL_REFUND", "PARTIAL_REFUND")
                    and amount is not None
                    and contested is not None
                    and amount > contested
                ):
                    over.append(case.case_no)
                    self.assertIn(note, page)
                    self.assertIn(v2.REFUND_ARITHMETIC_CLAUSE, note)
                    self.assertIn(v2.REFUND_WORDING_CLAUSE, note)
                    self.assertIn(
                        v2._money(contested, case.policy.currency), note
                    )
                else:
                    self.assertEqual("", note)
                    self.assertNotIn('<p class="refundnote">', page)
        self.assertEqual([2801, 2802, 2804, 2818, 2828, 2842, 2849], over)


# --------------------------------------------------------------------------
# The key-figure tiles, and the trace
# --------------------------------------------------------------------------
class KeyFigureTileTests(unittest.TestCase):
    """A tile is a fact the brief carries, beside the limit it is tested against."""

    def test_no_tile_is_drawn_for_a_fact_the_block_lacks(self):
        for case in loaded_cases():
            tiles = v2.key_figure_tiles(case)
            text = " ".join("{0} {1}".format(value, label) for value, label in tiles)
            deviation = v2._derived_block(case.brief, "GPS_TRACE", "deviation")
            arrival = v2._derived_block(case.brief, "GPS_TRACE", "arrival")
            coverage = v2._payload(case.brief, "GPS_TRACE").get("coverage_pct")
            with self.subTest(case=case.case_no):
                if deviation and v2._fact_value(deviation, "available"):
                    self.assertIn("POL-RD-01", text)
                else:
                    self.assertNotIn("POL-RD-01", text)
                if arrival and v2._fact_value(arrival, "available"):
                    self.assertIn("arrival radius", text)
                else:
                    self.assertNotIn("arrival radius", text)
                if coverage is None:
                    self.assertNotIn("trace coverage", text)
                else:
                    self.assertIn("trace coverage", text)

    def test_every_tile_is_on_its_own_case_page(self):
        for case in loaded_cases():
            page = built_pages()[case.link]
            for value, label in v2.key_figure_tiles(case):
                with self.subTest(case=case.case_no, tile=value):
                    self.assertIn(value, page)
                    self.assertIn(label, page)

    def test_the_confidence_tile_names_the_floor_it_is_tested_against(self):
        floor = read_json(PROJECT_ROOT / "policy" / "v3" / "general.json")[
            "confidence_floor"
        ]
        for case in loaded_cases():
            if case.trigger is not None:
                continue
            confidence = case.ruling.get("confidence")
            if confidence is None:
                continue
            with self.subTest(case=case.case_no):
                self.assertIn(
                    'aria-label="confidence {0} against a floor of {1}"'.format(
                        confidence, floor
                    ),
                    built_pages()[case.link],
                )


# The trace's own SVG, cut out of the rail. The page also carries the product's
# scales mark, which is an SVG too, so the trace is found by its container
# rather than as "the first SVG on the page".
TRACE_SVG_RE = re.compile(r'<div class="map">(<svg.*?</svg>)</div>', re.S)


def optimal_distance_of(case: Any) -> Any:
    """A case's optimal route distance, from its brief or its case file.

    Computed here rather than read off the page's caption, so the caption is
    checked against an independent figure.
    """
    deviation = v2._derived_block(case.brief, "GPS_TRACE", "deviation")
    value = v2._fact_value(deviation, "optimal_distance_km") if deviation else None
    if value is None:
        value = v2._case_payload(case.case, "TRIP_RECORD").get("optimal_distance_km")
    return value


class TraceDrawingTests(unittest.TestCase):
    """The trace is drawn from the fixes, and the optimal route is never drawn."""

    def test_the_trace_is_drawn_from_the_fixes(self):
        for case in loaded_cases():
            page = built_pages()[case.link]
            match = TRACE_SVG_RE.search(page)
            fixes = v2._latlngs(
                v2._case_payload(case.case, "GPS_TRACE").get("points")
            )
            with self.subTest(case=case.case_no):
                if not fixes:
                    self.assertIsNone(match, "a trace was drawn with no fixes")
                    continue
                self.assertIsNotNone(match, "no trace was drawn")
                self.assertIn("<polyline", match.group(1))

    def test_no_line_is_labelled_optimal(self):
        """No line is labelled optimal anywhere, and the caption says why.

        The caption belongs to the trace: it is written where a trace is drawn,
        the record carries an optimal distance, and the case is about the route.
        A no-show case is about where the device was and how long the driver
        waited, so the route's figure is not on it; and a case with no GPS fixes
        has no trace block at all -- case 213 is one, though its trip record does
        carry an optimal distance -- so the caption is required only where a
        trace was drawn.
        """
        for case in loaded_cases():
            page = built_pages()[case.link]
            match = TRACE_SVG_RE.search(page)
            optimal = optimal_distance_of(case)
            route_case = case.category != "NO_SHOW_CHARGE"
            with self.subTest(case=case.case_no):
                if match is not None:
                    self.assertNotIn("optimal", match.group(1))
                if match is not None and optimal is not None and route_case:
                    self.assertIn("(distance only)", page)
                else:
                    self.assertNotIn("(distance only)", page)

    def test_every_map_svg_says_what_it_shows(self):
        """A map is an image: it carries a role and a name."""
        for case in loaded_cases():
            match = TRACE_SVG_RE.search(built_pages()[case.link])
            if match is None:
                continue
            with self.subTest(case=case.case_no):
                self.assertIn('role="img"', match.group(1))
                self.assertIn('aria-label="The trip trace:', match.group(1))

    def test_a_no_show_map_draws_the_radius_and_the_distance(self):
        """The no-show map draws its own story, and not the route's figure.

        The case turns on two facts a few hundred metres apart: the arrival
        radius the driver waited inside, and how far the rider's device was from
        the pickup point. Both are drawn, the distance is labelled with the
        figure the derived facts give, and the frame is fitted to them rather
        than to a driven trace that runs for kilometres.
        """
        case = loaded_case(208)
        match = TRACE_SVG_RE.search(built_pages()[case.link])
        self.assertIsNotNone(match, "the no-show case drew no trace")
        assert match is not None
        svg = match.group(1)
        radius = v2._fact_value(
            v2._derived_block(case.brief, "GPS_TRACE", "arrival"),
            "thresholds",
            "arrival_radius_m",
        )
        distance = v2._device_distance(case)
        self.assertIsNotNone(radius)
        self.assertIsNotNone(distance)
        assert distance is not None
        self.assertIn(
            'stroke-dasharray="4 3"', svg, "the arrival radius is not drawn"
        )
        self.assertIn("<line", svg, "the device is not joined to the pickup")
        self.assertIn("<text", svg, "the distance is not labelled")
        self.assertIn(v2._text(distance), svg)
        self.assertNotIn("(distance only)", built_pages()[case.link])

    def test_the_rail_carries_the_evidence_and_the_record(self):
        for case in loaded_cases():
            page = built_pages()[case.link]
            with self.subTest(case=case.case_no):
                self.assertIn("<summary>Evidence ", page)
                self.assertIn("<summary>Record ", page)


# --------------------------------------------------------------------------
# Nothing external, and no web font
# --------------------------------------------------------------------------
STYLE_RE = re.compile(r"<style>(.*?)</style>", re.S)


class WebFontTests(unittest.TestCase):
    """No page loads a font, and none names one."""

    def test_no_stylesheet_imports_or_embeds_a_font(self):
        for name, text in sorted(built_pages().items()):
            styles = "".join(STYLE_RE.findall(text)).lower()
            with self.subTest(page=name):
                for needle in ("@import", "@font-face", "url(", "fonts.googleapis", "fonts.gstatic"):
                    self.assertNotIn(needle, styles)
                self.assertEqual(
                    [],
                    links_other_than_the_icon(text),
                    "{0} carries a <link> that is not the inline tab icon".format(name),
                )


# --------------------------------------------------------------------------
# The replay beside the queue
# --------------------------------------------------------------------------
class ReplayLinkTests(unittest.TestCase):
    """The evaluation replay under replay/: its links resolve, and it links back."""

    def replay_pages(self) -> List[Path]:
        return sorted((v2.DIST_DIR / REPLAY_DIR).rglob("*.html"))

    def test_the_replay_is_committed(self):
        self.assertTrue(self.replay_pages(), "the evaluation replay is not committed")

    def test_every_replay_page_links_back_to_the_queue(self):
        queue = (v2.DIST_DIR / "index.html").resolve()
        for path in self.replay_pages():
            scan = _ResourceScan()
            scan.feed(path.read_text(encoding="utf-8"))
            targets = {
                (path.parent / url).resolve()
                for _tag, url in scan.anchors
                if url and not url.startswith("#") and not is_external_reference(url)
            }
            with self.subTest(page=path.relative_to(v2.DIST_DIR).as_posix()):
                self.assertIn(
                    queue, targets, "a replay page does not link back to the queue"
                )

    def test_every_relative_link_in_the_replay_resolves(self):
        for path in self.replay_pages():
            scan = _ResourceScan()
            scan.feed(path.read_text(encoding="utf-8"))
            for _tag, url in scan.anchors:
                if not url or url.startswith("#") or is_external_reference(url):
                    continue
                with self.subTest(page=path.name, url=url):
                    self.assertTrue(
                        (path.parent / url).resolve().is_file(),
                        "{0} links to {1}, which is not there".format(path.name, url),
                    )


# --------------------------------------------------------------------------
# The closing command the human-review form builds
# --------------------------------------------------------------------------
class ClosingCommandTests(unittest.TestCase):
    """POL-GEN-06(4)'s four decisions, and the command each one builds.

    The page builds the command in JavaScript and this module builds it in
    Python; the two are one shape, and the Python one is what is exercised here,
    because the command that matters is the one ``ops.review`` accepts and the
    closure it stores.
    """

    def test_the_vary_command_stores_a_closure_through_ops_review(self):
        """The sheet's acceptance for 213: VARY, FULL_REFUND 6.0, POL-GEN-07."""
        case = v2._load_case("corpus", 213)
        evidence_id = str(
            ((case.brief.get("case") or {}).get("evidence") or [])[0]["evidence_id"]
        )
        reason = (
            "The reviewer varies the ruling to a full refund: {0} carries the fare "
            "the rider paid, and POL-GEN-07(2) returns it."
        ).format(evidence_id)
        command = v2.closing_command(
            case,
            "VARY",
            ruling="FULL_REFUND",
            amount="6.0",
            clauses=["POL-GEN-07"],
            closed_by="a reviewer",
            reason=reason,
        )
        self.assertIn("--ruling FULL_REFUND", command)
        self.assertIn("--amount 6.0", command)
        self.assertIn("--clause POL-GEN-07", command)
        self.assertNotIn("close ", command)
        with tempfile.TemporaryDirectory() as tmp:
            argv = shlex.split(command)[3:] + ["--store", tmp]
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()):
                    code = review_module.main(argv)
            self.assertEqual(0, code)
            self.assertTrue(
                (Path(tmp) / "precedents.jsonl").is_file(),
                "the command did not store a closure",
            )

    def test_adopt_on_107_carries_the_panel_s_own_proposal(self):
        """ADOPT records what the panel proposed, and 107's is PARTIAL_REFUND 7.45."""
        case = v2._load_case("corpus", 107)
        proposal = v2.adopt_proposal(case)
        self.assertEqual("PARTIAL_REFUND", str(proposal.get("ruling")))
        self.assertEqual("7.45", str(proposal.get("amount_sgd")))
        self.assertFalse(v2.adopt_is_disabled(case))
        command = v2.closing_command(
            case, "ADOPT", reason="a reason of at least twenty characters long"
        )
        self.assertIn("--ruling PARTIAL_REFUND", command)
        self.assertIn("--amount 7.45", command)
        self.assertNotIn("close ", command)

    def test_an_escalated_case_with_nothing_to_adopt_has_adopt_disabled(self):
        """The panel's plurality is ESCALATE, or there is no proposal at all."""
        disabled = None
        for set_name, run_dir in run_directories():
            for case_no in case_numbers(run_dir):
                document = read_json(run_dir / ("case-%05d.json" % case_no))
                if inner_ruling(document).get("ruling") != "ESCALATE":
                    continue
                case = v2._load_case(set_name, case_no)
                if v2.adopt_is_disabled(case):
                    disabled = case
                    break
            if disabled is not None:
                break
        self.assertIsNotNone(disabled, "no escalated case has nothing to adopt")
        page = v2.build_case_page(disabled)
        self.assertIn("nothing to adopt", page)
        self.assertIn(
            '<input type="radio" name="decision" value="ADOPT" disabled', page
        )

    def test_the_form_offers_every_clause_of_the_case_s_policy(self):
        """POL-GEN-06(6) needs POL-GEN-07 reachable, so every clause is offered."""
        case = v2._load_case("corpus", 213)
        page = v2.build_case_page(case)
        offered = v2.case_policy_clauses(case)
        self.assertIn("POL-GEN-07", offered)
        for clause in offered:
            with self.subTest(clause=clause):
                self.assertIn('<option value="{0}">{0}</option>'.format(clause), page)

    def test_the_form_offers_the_six_record_kinds(self):
        """They are ``ops.appeal``'s own list, read rather than retyped."""
        case = v2._load_case("corpus", 213)
        page = v2.build_case_page(case)
        self.assertEqual(tuple(appeal_module.RECORD_EVIDENCE_KINDS), v2.EVIDENCE_KINDS)
        self.assertEqual(6, len(v2.EVIDENCE_KINDS))
        for kind in v2.EVIDENCE_KINDS:
            with self.subTest(kind=kind):
                self.assertIn('name="evidence" value="{0}"'.format(kind), page)

    def test_the_request_evidence_command_is_the_part_26_window_command(self):
        case = v2._load_case("corpus", 213)
        command = v2.evidence_window_command(
            case,
            items=["CALL_LOG"],
            opened_at="2026-08-11T20:00:00+08:00",
            opened_by="a reviewer",
        )
        self.assertTrue(command.startswith("python3 -m ops.evidence_window open"))
        self.assertIn("--items CALL_LOG", command)
        self.assertIn("--opened-by", command)
        page = v2.build_case_page(case)
        self.assertIn("part 26", page)
        self.assertIn("ops/evidence_window.py", page)

    def test_the_closing_command_carries_no_close_of_its_own(self):
        """``ops.review`` supplies the subcommand; a second one is refused."""
        case = v2._load_case("corpus", 213)
        command = v2.closing_command(
            case,
            "VARY",
            ruling="NO_ACTION",
            clauses=["POL-GEN-03"],
            reason="a reason of at least twenty characters long",
        )
        self.assertNotIn("close ", command)
        self.assertIn("--closed-by", command)
        self.assertIn("--packet-sha256", command)


if __name__ == "__main__":
    unittest.main()
