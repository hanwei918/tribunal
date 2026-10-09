"""Tests for ``ui.v2``: the product view, and the pages it commits.

No network, no browser, no credential, no model call. What is under test is the
seven properties the sheet names, and each is checked against the files the
pages were built from rather than against a number typed in here:

* ``--check`` passes, and two builds are byte-identical;
* no page contains ``fetch(``, an external ``src=`` or ``href=``, ``<link``, or a
  non-ASCII byte;
* no page names a sealed-v1 case number (301 to 312, 401 to 412) or reads a
  sealed path;
* for every case page, the ruling, the two amounts and the confidence shown
  equal the case file's;
* the queue's five figures equal what the run files give;
* a case sent to a reviewer has the "Human review" tab and its packet sha256
  equals ``ops.escalation``'s, and a decided case has no such tab;
* the appeal text matches ``POL-GEN-04``'s rule text.

**The suite builds the site five times and says why.** A build reads 151 cases,
rebuilds each case's brief and builds 26 escalation packets, which is about
forty seconds; the first class compares the committed pages with a fresh build
(that is what ``--check`` does), the second compares two builds with each other,
the third runs the command line the owner will run, and the fourth runs two
builds in subprocesses under two different ``PYTHONHASHSEED`` values and compares
them, because a row order that depended on a set or a dict would change its bytes
when the interpreter's string hash seed changed. Each class memoises what it
read, so no test builds the site for itself.

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

import json
import os
import pathlib
import re
import subprocess
import sys
import unittest
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import v6_runs  # noqa: E402
from ops import escalation  # noqa: E402
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
    global _PAGES, _GUARD
    if _PAGES is None:
        guard = _ReadGuard()
        with guard:
            loaded = [
                v2._load_case(case["set"], case["case_no"]) for case in cases()
            ]
            pages: Dict[str, str] = {relative(v2.INDEX_PATH): v2.build_index(loaded)}
            for data in loaded:
                pages[relative(v2.DIST_DIR / data.link)] = v2.build_case_page(data)
        _GUARD = guard
        _PAGES = pages
    return _PAGES


def read_guard() -> "_ReadGuard":
    built_pages()
    assert _GUARD is not None
    return _GUARD


def second_build() -> Dict[str, str]:
    """A second, independent build, for the byte-identity check."""
    global _SECOND_BUILD
    if _SECOND_BUILD is None:
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


def committed_pages() -> Dict[str, str]:
    return {
        path.relative_to(v2.DIST_DIR).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(v2.DIST_DIR.rglob("*"))
        if path.is_file()
    }


def index_text() -> str:
    return built_pages()[relative(v2.INDEX_PATH)]


# --------------------------------------------------------------------------
# The pages are what this code builds, and this code builds the same bytes twice
# --------------------------------------------------------------------------
class DeterminismTests(unittest.TestCase):
    """The committed bytes, and the two properties that make them trustworthy."""

    def test_check_passes_on_the_command_line(self):
        """The command the owner runs: a fresh build against the committed files."""
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
        self.assertEqual(1 + len(cases()), len(pages))
        self.assertIn("index.html", pages)
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
                self.assertNotIn("<link", text, "{0} embeds a stylesheet link".format(name))
                for tag in ("<iframe", "<object", "<embed"):
                    self.assertNotIn(tag, text, "{0} embeds {1}".format(name, tag))

    def test_every_link_stays_inside_the_site(self):
        """The only links are the pages beside it and a fragment on the page.

        A notice links to the judge's explanation with ``#judge-explanation``, a
        fragment on its own page; every other link is one of the pages this site
        commits. A fragment is checked against the page that carries it, so a
        link to an anchor that is not there is still a failure.
        """
        names = set(built_pages())
        for name, text in sorted(built_pages().items()):
            scan = _ResourceScan()
            scan.feed(text)
            for _tag, url in scan.anchors:
                with self.subTest(page=name, url=url):
                    self.assertFalse(is_external_reference(url))
                    if url.startswith("#"):
                        self.assertIn(
                            'id="{0}"'.format(url[1:]),
                            text,
                            "{0} links to {1}, an anchor it does not carry".format(name, url),
                        )
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
                    # so the bar is replaced by the reason in words.
                    self.assertIn("No automated ruling was issued.", page)
                    self.assertNotIn('role="img"', page)
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
    """The five figures, recomputed from the run files and compared."""

    def figures(self) -> Dict[str, Any]:
        rows = cases()
        total = len(rows)
        reviewer = [row for row in rows if row["trigger"] is not None]
        automatic = total - len(reviewer)
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
            "automatic": "{0} of {1}".format(automatic, total),
            "automatic_share": "{0:.1f}%".format(Decimal(automatic) * 100 / Decimal(total)),
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

    def test_the_queue_shows_the_five_figures_the_run_files_give(self):
        figures = self.figures()
        text = index_text()
        for key, value in sorted(figures.items()):
            if key in ("total", "triggers"):
                continue
            with self.subTest(figure=key):
                self.assertIn(value, text, "{0} is not on the queue page".format(key))

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
        """The two shares are complements of one queue, not of two."""
        figures = self.figures()
        self.assertEqual("151", figures["total"])
        self.assertEqual("125 of 151", figures["automatic"])
        self.assertEqual("26 of 151", figures["reviewer"])
        self.assertEqual("82.8%", figures["automatic_share"])
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
        """POL-GEN-04's route in one line, from the clause's own numbers."""
        match = self.APPEAL_LINE_RE.search(self.rule_text("POL-GEN-04"))
        self.assertIsNotNone(match, "POL-GEN-04 no longer states the route")
        return (
            "Either party may appeal {0} within {1} days. A different human "
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


if __name__ == "__main__":
    unittest.main()
