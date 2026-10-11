"""One refusal, in one place, for the paths a command is asked to write to.

Several commands write to a path the caller names: ``run_benchmark --external``,
``eval.grade --out``, ``ui.build --out``, ``policy_gaps draft
--proposals-dir``, ``policy_gaps approve --amendments-dir`` and ``policy_gaps
reject --proposal``. Four more derive a destination of their own and reach this
helper through their own guard: the recorded-drafts measurement, the baselines,
the amount-rule measurement and the policy-gap report. Each of those paths can
land somewhere it must not. Two places are refused:

**A sealed set's root.** ``runs/wild/`` holds the held-out set's single run,
``runs/wild-v2/`` the second sealed set's, ``runs/sealed-v1/`` the third's and
``runs/sealed-v2/`` the fourth's. The first three runs have been made; the
fourth's has not, and its root accepts exactly one destination -- the plain
sealed run's own directory -- for the one set that names it. Every root is one
of the submission's generalisation figures, so nothing else is created under any
of them -- not a case, not an ablated run, not a run at a later policy version,
not a report -- because a second thing written there changes what the directory
means while leaving every file a reader would look at apparently intact.

**A headline run directory.** ``runs/<model-slug>/``, ``runs/codex/<model-slug>/``,
``runs/wild/<model-slug>/``, ``runs/wild-v2/<model-slug>/``,
``runs/sealed-v1/<model-slug>/`` and ``runs/sealed-v2/<model-slug>/`` hold the
figures
the submission reports, and a command's own output written there would be read
as that run's.

The comparison is **component by component**, not a prefix test on the string,
and the components are case-folded, because this volume is case-insensitive:
``runs/WILD-V2`` names the same directory as ``runs/wild-v2``, and
``runs/wild-dev/`` is a different component from ``runs/wild/`` and is
deliberately not caught.

**Two runs roots are asked, not one.** ``--runs-dir`` and the repository's own
``runs/`` are separate things, so a caller who points the first at a scratch
root has not thereby made the repository's sealed roots safe to write into.
Every refusal is made against both.

The rule is stated once, here, so a command added later refuses the same paths
as the commands already here rather than restating them. The message names the
**path** and nothing else: which root it fell under, which set owns that root
and what to do instead are the caller's to say, because they differ per command.

**Two write paths do not come through here.** ``tribunal.pipeline --out`` and
``tribunal.precedents --store`` both write to a path the caller names, and
neither is stopped by anything in ``eval/``: ``tribunal/`` imports nothing from
``eval/`` and the evaluated system stays byte-identical to the tag it was frozen
at, so those guards are their callers' own. A write that reaches a sealed root
through one of them is not prevented. It is **caught**: every committed file
under a sealed root is checked file by file against its manifest by
``tests.test_wild_run_manifest`` and ``tests.test_wild_v2_run_manifest``, and git
shows any change to one, so the guard is what stops a command and the manifest
and the diff are what notice anything the guard did not.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class SealedDestinationError(Exception):
    """A destination no command may write to: a sealed root, or a headline one."""


def _message(resolved: Path) -> str:
    """The refusal, naming the path and nothing else.

    Not the root it fell under and not the set that owns the root: a caller
    reads this message and adds its own sentence, and a command that named a set
    it was not asked about would be saying more than it knows.
    """
    return (
        "{0} is sealed: no command writes into a sealed root or into a headline "
        "run directory".format(resolved)
    )


def refuse_a_sealed_destination(
    destination: Path, runs_dir: Optional[Path] = None
) -> Path:
    """Refuse a destination under a sealed root, or a headline run directory.

    ``runs_dir`` is the runs root the caller was given, when it was given one --
    ``--runs-dir``, or the root ``--external`` writes under. The repository's own
    ``runs/`` is asked about as well and whether or not ``runs_dir`` is given,
    because the two are separate things: a scratch runs root does not make the
    committed sealed roots safe to write into. A caller that has no runs root --
    ``eval.grade --out`` and ``ui.build --out`` write outside ``runs/``
    altogether -- passes none, and the repository's own is still asked.

    Returns the destination unchanged when nothing refuses it, so a caller can
    build and check it in one expression.

    Raises:
        SealedDestinationError: the destination lies under a sealed root, or is
            a headline run directory or lies inside one.
    """
    # Imported here rather than at the top: ``eval.run_benchmark`` imports
    # ``eval.grade``, and ``eval.grade`` imports this module, so a module-level
    # import of the runner would be a cycle. Nothing in this module reads the
    # runner at import time, and the runner is fully loaded by the time any
    # command calls this.
    from eval import run_benchmark

    resolved = Path(destination).resolve()
    model = run_benchmark.resolve_model(None)

    roots = [] if runs_dir is None else [Path(runs_dir).resolve()]
    repository = Path(run_benchmark.RUNS_DIR).resolve()
    if repository not in roots:
        roots.append(repository)

    folded = run_benchmark.path_components(resolved)
    for root in roots:
        base = run_benchmark.path_components(root)
        for subdir in run_benchmark.SEALED_RUNS_SUBDIRS:
            sealed = base + (subdir.casefold(),)
            if folded == sealed or folded[: len(sealed)] == sealed:
                raise SealedDestinationError(_message(resolved))
        for headline in run_benchmark.headline_run_directories(root, model):
            parts = run_benchmark.path_components(headline)
            if folded == parts or folded[: len(parts)] == parts:
                raise SealedDestinationError(_message(resolved))
    return Path(destination)
