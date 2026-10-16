"""Build the product site into ``ui/dist/``, from sources committed here.

The policy owner, Ji Guofang, designed and built the product site outside
WorkBuddy: 24 pages -- nine real pages and three forwarding pages, each in
English (``*.html``) and Chinese (``*.zh.html``) -- plus the images they carry,
a try-it page with a phone demo, and a small try-it service.
``tools/site_import.py`` transcribed her first package into this repository's
sources, her update of 2026-10-16 came in at part 111, and this module builds
the site out of those sources.

What it reads, and what it writes
---------------------------------
Two trees, both committed:

* ``ui/site/src/`` -- one file per page under ``src/pages/``, each carrying a
  marker where a shared block was, plus the four shared blocks themselves:
  ``site.css``, ``redirect.css``, ``site.en.js``, ``site.zh.js``. The builder
  puts each marker's block back and writes the page to ``ui/dist/<name>``.
* ``ui/site/static/`` -- the files the pages load as files: the fourteen
  ``assets/*.webp`` images, and the try-it page's phone demo -- its script,
  ``try/phone.js``, and its nineteen ``assets/try/*.webp`` images. Each is
  copied to ``ui/dist/`` at the same relative path, byte for byte.

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
evaluation replay's, and the pages and the static files are this one's.

Determinism
-----------
Every file is written from a committed file, so the same tree always produces
the same bytes. ``--check`` rebuilds everything in memory and compares it with
what is committed, naming each file that differs.

Usage::

    python3 -m ui.site.build            # write every file
    python3 -m ui.site.build --check    # compare, change nothing
"""

from __future__ import annotations

import argparse
import re
import sys
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
# beyond the 24 the policy owner designed.

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

# The page count her design fixes: nine pages and three forwarding pages in each
# language. A build that found another number would be a build from other sources.
PAGE_COUNT = 24

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


def assets() -> List[Tuple[Path, bytes]]:
    """Every file this builder writes that is bytes rather than text."""
    return static_files()


def written_paths() -> frozenset:
    """Every path this builder writes, relative to ``ui/dist/``.

    Exposed so a test can hold the three builders apart: the site's paths and
    the queue's and the replay's are disjoint, and this is the site's own list.

    It **lists the paths without building anything**: the page sources' names
    and the static tree's relative paths. It calls
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
            "Build the product site: the 24 pages, and the images and the "
            "try-it page's own files. Read-only on everything outside "
            "ui/site/; no model call, no network."
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
