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
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from eval import sealed_roots

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
