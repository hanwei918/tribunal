"""Draw the four C4 views from their layout specifications.

The four views under ``docs/architecture/`` are transcriptions of the C4 set the
policy owner, Ji Guofang, designed. Part 48 committed her drawings as finished
SVGs, which made them the one artifact in this repository nobody could
reproduce. This module is the repository drawing them itself: every view is
written from a **layout specification** under ``docs/architecture/spec/``, one
JSON file per view, which carries the canvas, the arrow markers and every
element in drawing order. Nothing here reads the drawings to write them, and
nothing here reads ``tmp/``.

**What a specification holds.** ``canvas`` is the ``<svg>`` root's own
attributes -- the ``viewBox``, the size and the font family -- written in the
order the root carries them. ``markers`` is the two arrow heads, ``a`` and
``ao``, each a ``<marker>`` around one ``<path>``. ``elements`` is every placed
element in drawing order: a ``tag``, its ``attrs`` in the order the element
writes them, and, for a ``<text>``, its string.

**What this writes.** ``docs/architecture/<name>.svg`` for each specification,
and then a copy of the dynamic view at ``docs/architecture.svg``, which is the
file the README embeds and the queue's "Architecture" link opens. Every value
in the output is the specification's: no geometry is computed here and no label
is retyped, so a corrected specification is a corrected drawing and nothing
else moves. One element per line, a trailing newline, ASCII, and the same bytes
on every machine.

``--check`` renders each specification afresh and compares it with the committed
file, printing ``identical`` or ``differs`` for each and exiting non-zero on a
difference. The four views are then copied into the support site by
``python3 -m ui.v2.build``, which reads ``docs/architecture/`` and not this
module.

Usage::

    python3 tools/c4_diagrams.py            # write the five files
    python3 tools/c4_diagrams.py --check    # compare, change nothing
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = PROJECT_ROOT / "docs" / "architecture" / "spec"
VIEW_DIR = PROJECT_ROOT / "docs" / "architecture"
README_COPY = PROJECT_ROOT / "docs" / "architecture.svg"

# The view ``docs/architecture.svg`` is a copy of: the one-dispute view the
# README embeds. Its name is the specification's own ``name``.
DYNAMIC_VIEW = "3-dynamic-one-dispute"

# The root's namespace. It is written first, before the canvas's own
# attributes, because an SVG without it is not an SVG.
SVG_NAMESPACE = "http://www.w3.org/2000/svg"

# The XML characters that must not appear literally. ``&`` is replaced first or
# it would rewrite the escapes the others introduce. The two quote characters
# are escaped in text as the policy owner's own drawings escape them --
# ``&#x27;`` for an apostrophe -- so that a string transcribed into a
# specification writes the same bytes the drawing it was transcribed from
# carries, and the drawings come out the same as hers.
ESCAPES: Tuple[Tuple[str, str], ...] = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ('"', "&quot;"),
    ("'", "&#x27;"),
)


def escape_text(value: str) -> str:
    """A text node's string, escaped for XML."""
    for character, replacement in ESCAPES:
        value = value.replace(character, replacement)
    return value


def escape_attribute(value: str) -> str:
    """An attribute value, escaped for XML and wrapped in double quotes."""
    return '"{0}"'.format(escape_text(value))


def attributes(pairs: Any) -> str:
    """A mapping's items as `` name="value"``, in the order the mapping carries."""
    return "".join(
        " {0}={1}".format(name, escape_attribute(str(value)))
        for name, value in pairs.items()
    )


def root_line(canvas: Dict[str, Any]) -> str:
    """The ``<svg>`` root: the namespace, then the canvas's own attributes."""
    return "<svg xmlns={0}{1}>".format(
        escape_attribute(SVG_NAMESPACE), attributes(canvas)
    )


def defs_line(markers: List[Dict[str, Any]]) -> str:
    """The ``<defs>`` line: every marker, each around its own path."""
    parts: List[str] = ["<defs>"]
    for marker in markers:
        parts.append("<marker{0}>".format(attributes(marker["marker_attrs"])))
        parts.append("<path{0}/>".format(attributes(marker["path"])))
        parts.append("</marker>")
    parts.append("</defs>")
    return "".join(parts)


def element_line(element: Dict[str, Any]) -> str:
    """One placed element: self-closing, or a ``<text>`` around its string."""
    tag = element["tag"]
    written = "<{0}{1}".format(tag, attributes(element["attrs"]))
    if tag == "text":
        return "{0}>{1}</{2}>".format(written, escape_text(element["text"]), tag)
    return written + "/>"


def render(spec: Dict[str, Any]) -> str:
    """One specification as the SVG's bytes, decoded as text."""
    lines: List[str] = [root_line(spec["canvas"]), defs_line(spec["markers"])]
    lines.extend(element_line(element) for element in spec["elements"])
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def read_spec(path: Path) -> Dict[str, Any]:
    """One layout specification, with the markers flattened for writing."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec["markers"] = [
        {"marker_attrs": {k: v for k, v in marker.items() if k != "path"},
         "path": marker["path"]}
        for marker in spec["markers"]
    ]
    return spec


def specifications() -> List[Path]:
    """Every layout specification, in the order its file name sorts."""
    return sorted(SPEC_DIR.glob("*.json"))


def views() -> List[Tuple[str, bytes]]:
    """Each view's name and its freshly rendered bytes, in specification order."""
    rendered: List[Tuple[str, bytes]] = []
    for path in specifications():
        spec = read_spec(path)
        rendered.append((spec["name"], render(spec).encode("utf-8")))
    return rendered


def dynamic_view(rendered: List[Tuple[str, bytes]]) -> bytes:
    """The dynamic view's bytes, which ``docs/architecture.svg`` is a copy of."""
    for name, content in rendered:
        if name == DYNAMIC_VIEW:
            return content
    raise SystemExit(
        "no view named {0!r} in {1}".format(DYNAMIC_VIEW, SPEC_DIR)
    )


def outputs() -> List[Tuple[Path, bytes]]:
    """Every file this module writes, and the bytes it writes there."""
    rendered = views()
    written = [(VIEW_DIR / "{0}.svg".format(name), content) for name, content in rendered]
    written.append((README_COPY, dynamic_view(rendered)))
    return written


def write_all() -> int:
    """Write every file, and say which changed."""
    changed = 0
    for path, content in outputs():
        before = path.read_bytes() if path.exists() else None
        path.write_bytes(content)
        state = "identical" if before == content else "written"
        changed += before != content
        print("{0}: {1}".format(path.relative_to(PROJECT_ROOT), state))
    print("{0} file(s) changed".format(changed))
    return 0


def check_all() -> int:
    """Compare every committed file with a fresh render. Non-zero on a difference."""
    differing = 0
    for path, content in outputs():
        committed = path.read_bytes() if path.exists() else None
        if committed == content:
            print("{0}: identical".format(path.relative_to(PROJECT_ROOT)))
            continue
        differing += 1
        print("{0}: differs".format(path.relative_to(PROJECT_ROOT)))
    if differing:
        print(
            "{0} file(s) differ from a fresh render; run "
            "python3 tools/c4_diagrams.py".format(differing)
        )
        return 1
    return 0


def main(argv: List[str]) -> int:
    """Write the five files, or, with ``--check``, compare them and change nothing."""
    arguments = [argument for argument in argv[1:] if argument != "--check"]
    if arguments:
        print("usage: python3 tools/c4_diagrams.py [--check]", file=sys.stderr)
        return 2
    if "--check" in argv[1:]:
        return check_all()
    return write_all()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
