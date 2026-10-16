"""Import the policy owner's product site into this repository's own sources.

The policy owner, Ji Guofang, designed and built the product site outside
WorkBuddy: 22 pages -- sixteen real pages and six forwarding pages, each in
English (``*.html``) and Chinese (``*.zh.html``) -- with images, a try-it page
that runs this repository's own code in the browser, and a small try-it service.
Her files are the design; this repository builds the site from sources committed
here, and the built pages come out **byte for byte identical** to hers.

This module is the transcription step, and it runs once. It reads the directory
named by ``--src`` -- an argument and never a constant, so nothing in this
repository has to name a path outside it -- and writes two trees:

* ``ui/site/src/`` -- the four shared blocks factored out once each
  (``site.css``, ``redirect.css``, ``site.en.js``, ``site.zh.js``) and one file
  per page under ``src/pages/``, each carrying a fixed marker where a shared
  block was: ``<style>/*@include site.css*/</style>``. A page's **own** script
  stays in the page: only a block that more than one page carries is factored
  out. ``ui/site/build.py`` puts the blocks back.
* ``ui/site/static/`` -- every file the pages load as a file rather than as
  text, at the same relative path: the fourteen ``assets/*.webp`` images,
  ``try-config.js``, ``try/try.js``, ``try/recorded.json``,
  ``try/templates.json`` and the six unmodified Pyodide 0.27.7 files under
  ``try/pyodide/``.

Four things in her directory are deliberately **not** copied, and each has a
reason: ``assets/README.txt`` is a deploy note rather than part of the site;
``og-image.png`` is committed as ``ui/assets/og-image.png`` for the builder that
already copies it; ``cover-1280.jpg`` and the four ``architecture/*.svg`` views
are already built by ``ui/v2/build.py`` and are byte-identical to hers; and
``try/tribunal-core.zip`` is built from this repository by ``ui/site/build.py``
rather than copied.

**The round trip is the check.** After writing, the importer reassembles every
page from the sources it just wrote -- markers replaced by the shared blocks --
and compares the bytes with her file. A page that does not come back identical is
named and the exit status is non-zero, so a transcription that loses a byte is
reported by the tool that lost it rather than by a reader comparing two trees by
hand.

**It ran on her first package, of 2026-10-13, and is not run again.** Her
update of 2026-10-16 came in at part 111 by hand, and the earlier try-it page's
files it lists left the site at part 116; running it again would undo both.

Usage::

    python3 tools/site_import.py --src DIR [--out ui/site]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The four shared blocks, by the name each is written under. The two stylesheets
# are told apart by how many pages carry them -- sixteen pages carry the site's
# own, six forwarding pages carry the small one -- and the two scripts by the
# language of the pages that carry them.
SITE_CSS = "site.css"
REDIRECT_CSS = "redirect.css"
SITE_EN_JS = "site.en.js"
SITE_ZH_JS = "site.zh.js"
SHARED_BLOCKS: Tuple[str, ...] = (SITE_CSS, REDIRECT_CSS, SITE_EN_JS, SITE_ZH_JS)

# The marker a page carries where a shared block was. It is written inside the
# ``<style>`` or ``<script>`` tag the block came from, so a page's own markup is
# otherwise untouched and the reassembly is a substitution and nothing else.
INCLUDE_RE = re.compile(r"/\*@include ([A-Za-z0-9._-]+)\*/")
INCLUDE = "/*@include {0}*/"

STYLE_RE = re.compile(r"<style>(.*?)</style>", re.S)
# An inline script only: the negative lookahead skips ``<script src="...">``,
# whose body belongs to a file rather than to the page.
SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S)

# The page file names, as they arrive and as they are written. The set is fixed
# by her design: eight pages per language, plus six forwarding pages.
PAGE_COUNT = 22

# What ``static/`` holds, as the rule that copies it and the number of files each
# part of the rule must find. A count that moves is reported rather than copied
# silently, because the numbers are part of what was transcribed.
STATIC_RULES: Tuple[Tuple[str, str, int], ...] = (
    ("assets", "*.webp", 14),
    (".", "try-config.js", 1),
    ("try", "try.js", 1),
    ("try", "recorded.json", 1),
    ("try", "templates.json", 1),
    ("try/pyodide", "*", 6),
)

# Her files that are not part of the site's own static set. Each is named rather
# than reached by a wildcard, so a file that appears beside them later is copied
# and noticed rather than skipped in silence.
NOT_STATIC: Tuple[str, ...] = (
    "assets/README.txt",
    "og-image.png",
    "cover-1280.jpg",
    "try/tribunal-core.zip",
)


class TranscriptionError(Exception):
    """The import cannot be made; the message names what was wrong."""


def page_paths(src: Path) -> List[Path]:
    """Every page in her directory: the ``*.html`` files at its top."""
    found = sorted(path for path in src.glob("*.html") if path.is_file())
    if len(found) != PAGE_COUNT:
        raise TranscriptionError(
            "expected {0} pages in {1}, found {2}".format(PAGE_COUNT, src, len(found))
        )
    return found


def shared_style(contents: Dict[str, str]) -> Dict[str, List[str]]:
    """Each distinct ``<style>`` body, and the pages that carry it."""
    groups: Dict[str, List[str]] = {}
    for name, text in contents.items():
        for body in STYLE_RE.findall(text):
            groups.setdefault(body, []).append(name)
    return groups


def shared_script(contents: Dict[str, str]) -> Dict[str, List[str]]:
    """Each distinct inline ``<script>`` body, and the pages that carry it."""
    groups: Dict[str, List[str]] = {}
    for name, text in contents.items():
        for body in SCRIPT_RE.findall(text):
            groups.setdefault(body, []).append(name)
    return groups


def is_chinese(name: str) -> bool:
    """Whether a page is one of the Chinese ones."""
    return name.endswith(".zh.html")


def name_the_blocks(contents: Dict[str, str]) -> Dict[str, str]:
    """The four shared blocks' bodies, under the name each is written as.

    The stylesheets are told apart by width -- the one the site's own pages
    carry is ``site.css``, the one the forwarding pages carry is
    ``redirect.css`` -- and the scripts by language. A directory that does not
    hold exactly one block of each kind is refused rather than guessed at.
    """
    styles = shared_style(contents)
    if len(styles) != 2:
        raise TranscriptionError(
            "expected two shared <style> blocks, found {0}".format(len(styles))
        )
    widest, narrowest = sorted(styles.items(), key=lambda item: len(item[1]), reverse=True)
    if len(widest[1]) <= len(narrowest[1]):
        raise TranscriptionError("the two shared <style> blocks cover the same number of pages")

    scripts = {
        body: pages for body, pages in shared_script(contents).items() if len(pages) > 1
    }
    if len(scripts) != 2:
        raise TranscriptionError(
            "expected two shared inline <script> blocks, found {0}".format(len(scripts))
        )
    english = [body for body, pages in scripts.items() if not any(map(is_chinese, pages))]
    chinese = [body for body, pages in scripts.items() if all(map(is_chinese, pages))]
    if len(english) != 1 or len(chinese) != 1:
        raise TranscriptionError(
            "the two shared <script> blocks are not one English and one Chinese block"
        )
    return {
        SITE_CSS: widest[0],
        REDIRECT_CSS: narrowest[0],
        SITE_EN_JS: english[0],
        SITE_ZH_JS: chinese[0],
    }


def rewrite(text: str, blocks: Dict[str, str]) -> str:
    """One page, with every shared block it carries replaced by its marker.

    A page carries the blocks it carries: the site's own pages carry the large
    stylesheet and one of the two scripts, the forwarding pages carry the small
    stylesheet and a script of their own. A block a page does not carry is
    simply not there to replace.
    """
    for name, body in blocks.items():
        tag = "style" if name.endswith(".css") else "script"
        before = "<{0}>{1}</{0}>".format(tag, body)
        after = "<{0}>{1}</{0}>".format(tag, INCLUDE.format(name))
        text = text.replace(before, after)
    return text


def reassemble(text: str, blocks: Dict[str, str]) -> str:
    """A page's sources put back together: every marker replaced by its block."""

    def replacement(match: "re.Match") -> str:
        name = match.group(1)
        if name not in blocks:
            raise TranscriptionError("a page carries a marker for an unknown block {0!r}".format(name))
        return blocks[name]

    return INCLUDE_RE.sub(replacement, text)


def static_files(src: Path) -> List[Tuple[str, Path]]:
    """Every static file, as ``(relative path, source)``, in sorted order.

    The rules are the ones in ``STATIC_RULES``, each held to its own count, and
    ``NOT_STATIC`` is refused by name so a rule that widened is reported rather
    than obeyed.
    """
    found: List[Tuple[str, Path]] = []
    for directory, pattern, expected in STATIC_RULES:
        source = src / directory
        matches = sorted(
            path for path in source.glob(pattern) if path.is_file()
        )
        if len(matches) != expected:
            raise TranscriptionError(
                "expected {0} file(s) at {1}/{2}, found {3}".format(
                    expected, directory, pattern, len(matches)
                )
            )
        for path in matches:
            relative = path.relative_to(src).as_posix()
            if relative in NOT_STATIC:
                raise TranscriptionError(
                    "{0} is excluded from the static set but a rule reached it".format(relative)
                )
            found.append((relative, path))
    return sorted(found)


def write_import(src: Path, out: Path) -> int:
    """Write both trees, then reassemble every page and compare the bytes."""
    contents = {path.name: path.read_text(encoding="utf-8") for path in page_paths(src)}
    blocks = name_the_blocks(contents)

    src_dir = out / "src"
    pages_dir = src_dir / "pages"
    static_dir = out / "static"
    pages_dir.mkdir(parents=True, exist_ok=True)

    for name in SHARED_BLOCKS:
        (src_dir / name).write_text(blocks[name], encoding="utf-8")
        print("{0}: {1} bytes".format((src_dir / name).relative_to(PROJECT_ROOT), len(blocks[name])))

    written: Dict[str, str] = {}
    for name, text in contents.items():
        page = rewrite(text, blocks)
        written[name] = page
        (pages_dir / name).write_text(page, encoding="utf-8")
    print("{0}: {1} pages".format(pages_dir.relative_to(PROJECT_ROOT), len(written)))

    # Every shared block has to be gone from every page, or the same bytes are
    # carried twice -- once in ``src/`` and once in a page -- and the next edit
    # to the block reaches only one of them.
    left = [
        name
        for name, body in blocks.items()
        if any(body in page for page in written.values())
    ]
    if left:
        raise TranscriptionError(
            "a shared block is still carried by a page: {0}".format(", ".join(sorted(left)))
        )
    unused = [
        name
        for name, body in blocks.items()
        if not any(INCLUDE.format(name) in page for page in written.values())
    ]
    if unused:
        raise TranscriptionError(
            "a shared block is carried by no page: {0}".format(", ".join(sorted(unused)))
        )

    copied = static_files(src)
    for relative, path in copied:
        destination = static_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
    print("{0}: {1} files".format(static_dir.relative_to(PROJECT_ROOT), len(copied)))

    differing: List[str] = []
    for name, page in sorted(written.items()):
        back = reassemble(page, blocks)
        if back.encode("utf-8") != (src / name).read_bytes():
            differing.append(name)
    if differing:
        print(
            "round trip: {0} page(s) do not come back byte for byte: {1}".format(
                len(differing), ", ".join(differing)
            ),
            file=sys.stderr,
        )
        return 1
    print("round trip: {0} pages, every one byte for byte identical".format(len(written)))
    return 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 tools/site_import.py",
        description=(
            "Transcribe the policy owner's product site into ui/site/src/ and "
            "ui/site/static/, and check every page against her file."
        ),
    )
    parser.add_argument("--src", required=True, help="the directory her pages are in")
    parser.add_argument(
        "--out",
        default="ui/site",
        help="where the sources are written (default: ui/site)",
    )
    args = parser.parse_args(list(argv)[1:])
    try:
        return write_import(Path(args.src), PROJECT_ROOT / args.out)
    except TranscriptionError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
