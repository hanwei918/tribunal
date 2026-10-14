"""Build the product site into ``ui/dist/``, from sources committed here.

The policy owner, Ji Guofang, designed and built the product site outside
WorkBuddy: 22 pages -- sixteen real pages and six forwarding pages, each in
English (``*.html``) and Chinese (``*.zh.html``) -- plus the images they carry,
a try-it page that runs this repository's own Python in the browser, and a small
try-it service. ``tools/site_import.py`` transcribed her files into this
repository's sources, and this module builds the site back out of them, so the
published pages come out **byte for byte identical** to hers.

What it reads, and what it writes
---------------------------------
Three trees, all committed:

* ``ui/site/src/`` -- one file per page under ``src/pages/``, each carrying a
  marker where a shared block was, plus the four shared blocks themselves:
  ``site.css``, ``redirect.css``, ``site.en.js``, ``site.zh.js``. The builder
  puts each marker's block back and writes the page to ``ui/dist/<name>``.
* ``ui/site/static/`` -- the files the pages load as files: the fourteen
  ``assets/*.webp`` images, ``try-config.js`` and the try-it page's own
  ``try/`` directory (its script, its two data files and the six unmodified
  Pyodide 0.27.7 files). Each is copied to ``ui/dist/`` at the same relative
  path, byte for byte.
* the repository itself, for one file it **builds** rather than copies:
  ``ui/dist/try/tribunal-core.zip``, the Python the browser runs, assembled
  from the 45 paths in :data:`BUNDLE_PATHS` -- this repository's own
  ``tribunal/*.py``, ``tryit/*.py``, ``ops/chat_signals.py``,
  ``policy/**/*.json``, the four template cases and ``data/index.json``.

One part of the front pages is neither copied nor assembled from a block
either: the film. ``ui/site/static/assets/tribunal-film.mp4`` has not been
delivered, and a published page that offered a film the site does not carry
would offer a film that cannot play. The two elements that depend on the file
-- the front page's "Watch the film" button and its ``<video>`` element -- are
marked in the page sources between ``<!--@film-->`` and ``<!--/@film-->``, and
the build keeps them when the file is there and removes them when it is not.
The source pages keep both either way, so delivering the film is a matter of
dropping the file in beside the other assets.

One part of a page is neither copied nor assembled from a block: the 151 rows of
``cases.html``'s queue table, and the same 151 rows in Chinese in
``cases.zh.html``. Both are built at build time from ``ui.v2.build``'s own row
function over the same four version-6 runs the queue page is drawn from -- the
English body is the queue page's own rows, and the Chinese body is those cases
through :mod:`ui.site.queue_rows`' fixed vocabulary. The page sources carry a
``/*@queue-rows en*/`` or ``/*@queue-rows zh*/`` marker where the rows go, in the
same spirit as the include marker beside it.

Nothing here reads a file outside those trees, and nothing here makes a
model call or touches the network.

The site's root, and who owns which page
----------------------------------------
``ui/dist/index.html`` is this builder's front page, and the queue
``ui/v2/build.py`` writes sits beside it at ``ui/dist/queue.html``. The three
builders share ``ui/dist/`` and their path sets are disjoint, which
:func:`written_paths` exists to let a test check: the queue's own pages and the
architecture views are the product view's, ``ui/dist/replay/`` is the
evaluation replay's, and the pages, the static files and the bundle are this
one's.

Determinism
-----------
Every file is written from a committed file, and the bundle's entries are
sorted, stamped with a fixed time and compressed the same way every run, so the
same tree always produces the same bytes. ``--check`` rebuilds everything in
memory and compares it with what is committed, naming each file that differs.

Usage::

    python3 -m ui.site.build            # write every file
    python3 -m ui.site.build --check    # compare, change nothing
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.site import queue_rows as site_rows  # noqa: E402
from ui.v2 import build as v2  # noqa: E402

# The site's own trees, and the published root the three builders share.
SITE_DIR = PROJECT_ROOT / "ui" / "site"
SRC_DIR = SITE_DIR / "src"
PAGES_DIR = SRC_DIR / "pages"
STATIC_DIR = SITE_DIR / "static"
DIST_DIR = PROJECT_ROOT / "ui" / "dist"

# The page a host serves for an address that is not one of the site's is the
# product view's (``ui/dist/404.html``); this builder writes no page of its own
# beyond the 22 the policy owner designed.

# The marker a page carries where a shared block was. It names one file directly
# under ``src/``, which is what is put back in its place.
INCLUDE_RE = re.compile(r"/\*@include ([A-Za-z0-9._-]+)\*/")

# The marker a page carries where its queue table's rows go. It names a language,
# and the rows are built from the queue's own row function rather than copied
# into the source: the two tables are 151 rows each and a copy is a copy that can
# drift away from the page it was taken from. A language the builder does not
# write is refused rather than left in the page.
QUEUE_ROWS_RE = re.compile(r"/\*@queue-rows ([A-Za-z0-9_-]+)\*/")

# The marker a page carries around the elements that depend on the film, and the
# file they depend on. The file is absent today, so the built pages carry
# neither element; the markers come off a page either way.
FILM_MARKER_RE = re.compile(r"<!--@film-->(.*?)<!--/@film-->", re.DOTALL)

# The bundle the try-it page loads, and the 45 paths it holds. The list is the
# one her own bundle carried, read off its listing and written out here rather
# than globbed, so the bundle's contents are a fact this repository states and a
# file that appeared beside them cannot slip in. It is sorted, and the entries
# are written in this order.
#
# The three ``policy/v7/*.json`` files were added when version 7 was published,
# and the three ``policy/v8/*.json`` files when version 8 was: her builder globs
# ``policy/**/*.json``, so her own list grew by exactly those three each time and
# this one has to grow with it.
BUNDLE_PATH = DIST_DIR / "try" / "tribunal-core.zip"
BUNDLE_PATHS: Tuple[str, ...] = (
    "data/cases/case-00103.json",
    "data/cases/case-00208.json",
    "data/external/dev-v2/case-01779.json",
    "data/external/ryde-v3/case-00901.json",
    "data/index.json",
    "ops/chat_signals.py",
    "policy/amendments/0001-pol-rd-13.json",
    "policy/general.json",
    "policy/no_show.json",
    "policy/proposals/0001-pol-rd-13.json",
    "policy/proposals/0001-pol-rd-13.transcript.json",
    "policy/route_deviation.json",
    "policy/v3/amendments/0001-pol-ns-11.json",
    "policy/v3/amendments/0002-pol-rd-14.json",
    "policy/v3/amendments/0003-pol-ns-12.json",
    "policy/v3/general.json",
    "policy/v3/no_show.json",
    "policy/v3/proposals/0001-pol-ns-11.json",
    "policy/v3/proposals/0002-pol-rd-14.json",
    "policy/v3/proposals/0003-pol-ns-12.json",
    "policy/v3/route_deviation.json",
    "policy/v7/general.json",
    "policy/v7/no_show.json",
    "policy/v7/route_deviation.json",
    "policy/v8/general.json",
    "policy/v8/no_show.json",
    "policy/v8/route_deviation.json",
    "tribunal/__init__.py",
    "tribunal/brief.py",
    "tribunal/events.py",
    "tribunal/facts.py",
    "tribunal/llm.py",
    "tribunal/loader.py",
    "tribunal/model.py",
    "tribunal/money.py",
    "tribunal/pipeline.py",
    "tribunal/policy_versions.py",
    "tribunal/precedents.py",
    "tribunal/prepass.py",
    "tribunal/referee.py",
    "tribunal/transcript.py",
    "tryit/__init__.py",
    "tryit/build_bundle.py",
    "tryit/case.py",
    "tryit/server.py",
)

# The one timestamp every entry carries, and the one compression every entry
# uses. A zip written from a file's own mtime is a zip that differs on every
# checkout, so the time is fixed and the compression is stated rather than left
# to the platform's default.
BUNDLE_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
BUNDLE_COMPRESSION = zipfile.ZIP_DEFLATED
BUNDLE_COMPRESS_LEVEL = 9

# The page count her design fixes: eight pages per language plus six forwarding
# pages. A build that found another number would be a build from other sources.
PAGE_COUNT = 22

# The film the front page's button and <video> element name, if it is ever
# delivered. Its absence is not an error: it is what the build reads to decide
# whether those two elements belong on the published page.
FILM_PATH = STATIC_DIR / "assets" / "tribunal-film.mp4"


class BuildError(Exception):
    """A source is not the shape this builder can assemble."""


def shared_blocks() -> Dict[str, str]:
    """The four shared blocks, by the name a marker refers to them by.

    Every file directly under ``src/`` is a shared block; ``src/pages/`` is the
    pages. The names are the marker's, so a marker that names a file which is
    not there is reported when the page carrying it is assembled.
    """
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(SRC_DIR.iterdir())
        if path.is_file()
    }


def film_is_here() -> bool:
    """Whether the film file is committed beside the pages."""
    return FILM_PATH.is_file()


def film_elements(text: str, film: Optional[bool] = None) -> str:
    """A page with the film's two elements kept or removed, markers gone.

    ``None`` asks the file itself, which is what a build does. The markers come
    off either way, so a built page never carries one.
    """
    if film is None:
        film = film_is_here()
    return FILM_MARKER_RE.sub(
        (lambda match: match.group(1)) if film else (lambda match: ""), text
    )


def assemble(
    text: str,
    blocks: Dict[str, str],
    rows: Optional[Mapping[str, str]] = None,
    film: Optional[bool] = None,
) -> str:
    """One page's sources with every marker replaced by what it names.

    Three markers are put back or taken out: a shared block, the queue table's
    rows, and the film's two elements. The rows are built only when a page
    carries their marker, so a page that does not is assembled without reading
    the runs; the film's elements are kept only when the film is there.
    """

    def replacement(match: "re.Match") -> str:
        name = match.group(1)
        if name not in blocks:
            raise BuildError(
                "a page carries a marker for {0!r}, which is not a shared "
                "block under {1}".format(name, SRC_DIR)
            )
        return blocks[name]

    assembled = INCLUDE_RE.sub(replacement, text)
    if QUEUE_ROWS_RE.search(assembled):
        table = queue_table_bodies() if rows is None else rows
        assembled = QUEUE_ROWS_RE.sub(
            lambda match: rows_for(match.group(1), table), assembled
        )
    return film_elements(assembled, film)


def rows_for(language: str, table: Mapping[str, str]) -> str:
    """One language's queue rows, refusing a language this builder does not write."""
    if language not in table:
        raise BuildError(
            "a page carries a queue-rows marker for {0!r}, which is not one of "
            "the languages this builder writes: {1}".format(
                language, ", ".join(sorted(table))
            )
        )
    return table[language]


# The two queue table bodies, built once for the process. The English body is the
# queue page's own rows, read through the function that writes them, and the
# Chinese body is the same cases through the fixed vocabulary beside this module.
_QUEUE_TABLE_BODIES: "Dict[str, str] | None" = None


def queue_table_bodies() -> Dict[str, str]:
    """The 151 queue rows in each language, keyed by the marker's language."""
    global _QUEUE_TABLE_BODIES
    if _QUEUE_TABLE_BODIES is None:
        cases = v2.read_every_case()
        _QUEUE_TABLE_BODIES = {
            "en": "".join(v2._queue_row(case) for case in cases),
            "zh": site_rows.rows(cases),
        }
    return _QUEUE_TABLE_BODIES


def page_sources() -> List[Path]:
    """Every page source, in the order its file name sorts."""
    found = sorted(path for path in PAGES_DIR.iterdir() if path.is_file())
    if len(found) != PAGE_COUNT:
        raise BuildError(
            "expected {0} page sources under {1}, found {2}".format(
                PAGE_COUNT, PAGES_DIR, len(found)
            )
        )
    return found


def pages() -> List[Tuple[Path, str]]:
    """Every page this builder writes, as ``(destination, text)``.

    The one place the site's pages are decided, so a writing build and
    ``--check`` cannot disagree about which files there are.
    """
    blocks = shared_blocks()
    rows = queue_table_bodies()
    return [
        (
            DIST_DIR / source.name,
            assemble(source.read_text(encoding="utf-8"), blocks, rows),
        )
        for source in page_sources()
    ]


def static_files() -> List[Tuple[Path, bytes]]:
    """Every static file, as ``(destination, bytes)``, at its relative path.

    Read from ``ui/site/static/`` and written to the same place under
    ``ui/dist/``, byte for byte, in the order the relative paths sort.
    """
    found = sorted(path for path in STATIC_DIR.rglob("*") if path.is_file())
    return [
        (DIST_DIR / path.relative_to(STATIC_DIR), path.read_bytes()) for path in found
    ]


def bundle_bytes() -> bytes:
    """The try-it bundle, built from this repository.

    Each entry's bytes are the repository file's, the entries are written in the
    constant's order, and every entry carries the same fixed time and the same
    compression -- so two builds of the same tree give the same bytes.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer, "w", BUNDLE_COMPRESSION, compresslevel=BUNDLE_COMPRESS_LEVEL
    ) as archive:
        for relative in BUNDLE_PATHS:
            source = PROJECT_ROOT / relative
            if not source.is_file():
                raise BuildError(
                    "the bundle's path {0} is not a file in this repository".format(relative)
                )
            info = zipfile.ZipInfo(relative, date_time=BUNDLE_TIMESTAMP)
            info.compress_type = BUNDLE_COMPRESSION
            archive.writestr(info, source.read_bytes())
    return buffer.getvalue()


def assets() -> List[Tuple[Path, bytes]]:
    """Every file this builder writes that is bytes rather than text."""
    return static_files() + [(BUNDLE_PATH, bundle_bytes())]


def written_paths() -> frozenset:
    """Every path this builder writes, relative to ``ui/dist/``.

    Exposed so a test can hold the three builders apart: the site's paths and
    the queue's and the replay's are disjoint, and this is the site's own list.

    It **lists the paths without building anything**: the page sources' names,
    the static tree's relative paths, and the bundle's own path. It calls
    neither :func:`pages` nor :func:`assets`, and it reads no case, so it
    answers on a machine whose libm cannot rebuild a recorded brief -- where
    the pages themselves cannot be built at all. The set is the one the build
    writes; ``tests/test_linux_runners.py`` holds it to the paths
    :func:`pages` and :func:`assets` give.
    """
    static = sorted(path for path in STATIC_DIR.rglob("*") if path.is_file())
    return frozenset(
        [source.name for source in page_sources()]
        + [path.relative_to(STATIC_DIR).as_posix() for path in static]
        + [BUNDLE_PATH.relative_to(DIST_DIR).as_posix()]
    )


def _write_or_check_bytes(path: Path, data: bytes, check: bool) -> int:
    committed = path.read_bytes() if path.is_file() else None
    if check:
        if committed == data:
            print("{0}: identical".format(path.relative_to(PROJECT_ROOT)))
            return 0
        print("{0}: differs".format(path.relative_to(PROJECT_ROOT)))
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return 0


def _write_or_check_text(path: Path, text: str, check: bool) -> int:
    return _write_or_check_bytes(path, text.encode("utf-8"), check)


def build(check: bool = False) -> int:
    """Write every file, or compare the committed bytes with a fresh build."""
    status = 0
    for destination, text in pages():
        status |= _write_or_check_text(destination, text, check)
    for destination, data in assets():
        status |= _write_or_check_bytes(destination, data, check)
    if check and status:
        print(
            "the site differs from a fresh build; run `python3 -m ui.site.build`",
            file=sys.stderr,
        )
    return 0 if status == 0 else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m ui.site.build",
        description=(
            "Build the product site: the 22 pages, the images and the try-it "
            "page's own files, and the bundle the browser runs. Read-only on "
            "everything outside ui/site/; no model call, no network."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the committed files with a fresh build and write nothing",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return build(check=args.check)
    except BuildError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
