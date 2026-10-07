"""The operations layer: what a support team runs around the pipeline.

``ops/`` reads the pipeline's inputs -- the public case files and the loaded
policy -- and the pipeline's recorded outputs, and it never feeds anything back
into a brief or a prompt. Nothing in ``tribunal/`` or ``eval/`` imports it, and
no module here imports ``tribunal.llm`` or any network client, so a run made
through this layer is the same run the pipeline would have made.

**The three rules the whole layer is held to.** They are stated once, here, so a
module added later is held to the same ones rather than to a fresh reading of
them:

* **It never reads an answer.** No module opens an answer key, a ``grade``
  event, or anything under an ``answers`` directory.
* **It writes nothing unless it is given ``--out``.** And an ``--out`` is
  refused inside ``runs/``, ``data/``, ``policy/``, ``prompts/``, ``tribunal/``,
  ``eval/answers/`` or either sealed root, through
  :func:`refuse_a_forbidden_destination`.
* **Every threshold it applies is read from the loaded policy text.** A sentence
  that has moved or changed is refused rather than resolved against a number
  written in Python.

The write guard is the one piece of shared code the layer needs, and it lives
here so every command that takes an ``--out`` refuses the same paths rather than
restating them. It refuses in two halves and both are needed: the six trees this
layer does not write into, and the sealed roots and headline run directories,
which are :func:`eval.sealed_roots.refuse_a_sealed_destination`'s rule. The
second half is a call to that helper rather than a copy of it, so the two cannot
drift apart.

**Which set a run directory belongs to** is the other thing more than one
command needs, and it is here for the same reason: ``ops.escalation`` builds a
packet from a run directory and ``ops.queue`` routes the disputes of one, and
both have to find the cases the run was made from. The rule is the registry's
own -- see :func:`development_set_for` -- so a set added to
``eval.development_sets`` is one this layer can read without being edited.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, Type

from eval import development_sets, sealed_roots
from tribunal import loader

# ``ops/`` sits directly under the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The trees an ops command does not write into. ``runs/`` is here in full and not
# only at its sealed roots: a run directory holds what a run recorded, and a
# second thing written into one is read as part of that record. ``eval/answers/``
# is the one tree under ``eval/`` that is answer-bearing.
FORBIDDEN_DESTINATIONS = (
    "runs",
    "data",
    "policy",
    "prompts",
    "tribunal",
    "eval/answers",
)


class OpsError(Exception):
    """Base class for every failure this layer reports."""


class OpsWriteError(OpsError):
    """A destination the layer does not write to."""


def refuse_a_forbidden_destination(
    destination: Path, runs_dir: Optional[Path] = None
) -> Path:
    """Refuse an ``--out`` inside a tree this layer does not write into.

    ``runs_dir`` is the runs root the command was given, when it was given one,
    and is passed straight through to
    :func:`eval.sealed_roots.refuse_a_sealed_destination`, which asks about the
    repository's own ``runs/`` as well.

    Returns the resolved destination when nothing refuses it, so a caller can
    build and check it in one expression.

    Raises:
        OpsWriteError: the destination is inside one of
            :data:`FORBIDDEN_DESTINATIONS`, or is a sealed root or a headline
            run directory.
    """
    resolved = Path(destination).resolve()
    for name in FORBIDDEN_DESTINATIONS:
        root = (PROJECT_ROOT / name).resolve()
        if resolved == root or root in resolved.parents:
            raise OpsWriteError(
                "{0} is inside {1}/, which an ops command does not write "
                "into".format(resolved, name)
            )
    try:
        sealed_roots.refuse_a_sealed_destination(resolved, runs_dir)
    except sealed_roots.SealedDestinationError as exc:
        raise OpsWriteError(str(exc)) from exc
    return resolved


def development_set_for(run_dir: Path):
    """Which set a run directory belongs to, read off its path.

    The rule is the registry's own: the path component that follows the last
    ``runs`` segment names a set when it is one of the registered runs
    subdirectories, and everything else is the corpus -- whose run directory is
    ``runs/<model>/`` and carries no component of its own. The registry is read
    rather than restated, so a set added there is one this layer can read
    without being edited.

    The mapping is deliberately not ``tribunal.precedents``' own: its table
    names the sets that existed when the precedent library was built and does
    not know ``wild-v2``, so a run directory under it would be answered as the
    corpus and its cases loaded through the wrong manifest.
    """
    parts = Path(run_dir).resolve().parts
    indices = [index for index, part in enumerate(parts) if part == "runs"]
    if indices:
        following = indices[-1] + 1
        if following < len(parts):
            for development_set in development_sets.BY_NAME.values():
                if development_set.runs_subdir == parts[following]:
                    return development_set
    return development_sets.CORPUS


def case_root_of(development_set) -> Path:
    """Where a set's public case files live.

    The corpus is loaded through the manifest under ``data/cases/``; a second
    set carries its own directory. It is the root a case is read from, and the
    root a repeated party id would be looked for in.
    """
    if development_set.case_root is None:
        return Path(loader.CASES_DIR)
    return Path(development_set.case_root)


def read_json_document(path: Path, error: Type[OpsError] = OpsError) -> Any:
    """Read one UTF-8 JSON document, with amounts as ``Decimal``.

    ``parse_float=Decimal`` fixes the money representation at the parse
    boundary, which is where the literal is still available -- the same hook
    ``tribunal.loader`` uses, so a figure read here is the figure the file
    wrote rather than the nearest binary float.

    A missing file, an unreadable one and one that is not JSON are all reported
    the same way, because to a caller they are one thing: the document that was
    named is not there to be read.

    ``error`` is the exception class to raise, so each module can report a
    document it could not read as its own error type while the reading itself
    stays in one place.
    """
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)
    except FileNotFoundError as exc:
        raise error("no file at {0}".format(path)) from exc
    except OSError as exc:
        raise error("{0} cannot be read: {1}".format(path, exc)) from exc
    except ValueError as exc:
        raise error("invalid JSON in {0}: {1}".format(path, exc)) from exc
