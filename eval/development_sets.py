"""The development sets the judge prompt is measured on.

There are two of them, and they are not the same kind of thing:

* **the corpus** -- the 29 cases listed in ``data/index.json``, keyed by
  ``eval/answers/ground_truth.json``. This is the set the submission's headline
  figure is computed on, and it stays exactly 29 cases.
* **the second development set** -- fifteen cases drafted by OpenAI Codex on
  2026-09-24, copied in by the owner under ``data/external/codex/``, keyed by
  ``eval/answers/codex/ground_truth.json``. It is deliberately absent from
  ``data/index.json``, because adding it there would change the corpus.

Both are **development data**. Neither is a test set. A test set has to be
drafted without access to this repository and seen beforehand by nobody who
works on the prompt, and the set that meets that description is now in the
repository: the held-out set, 64 cases under ``data/external/wild/``, keyed by
``eval/answers/wild/ground_truth.json``. It is **not** a third development
set and it is never combined with the two above. It is run exactly once, from
the commit tagged ``freeze-2026-09-30``, and that single run is the only
figure the submission reports as generalisation. Nothing here produces that
figure.

From 2026-10-01 those same 64 cases are registered a second time as
``wild-dev``: the same cases and the same key, run into
``runs/wild-dev/<model-slug>/`` and **runnable again**. Its answers were read so
that the system could be changed to fix what the held-out run exposed, so it is
development data from that date and no figure from it is a generalisation
figure. It is in neither of the two tuples the combined figure and ``--set all``
read.

What this module is for
-----------------------
Running either set through the *same* runner the corpus goes through --
:func:`eval.run_benchmark.run_benchmark` -- so the caching, the provenance, both
deadlines, the token budget and the advocate replay are not reimplemented for
the second set and cannot drift from the corpus's. The four graded fields are
compared against each set's own key, and the two sets are reported separately
and then combined.

Nothing here makes a model call. ``--report`` reads cached runs only.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_ROOT / "runs"
ANSWER_DIR = EVAL_DIR / "answers"
CORPUS_KEY_PATH = ANSWER_DIR / "ground_truth.json"

# The one thing that unlocks a sealed run, and the only thing that does.
#
# A sealed set is run by the owner, once, and the run is the measurement the
# submission reports. An invocation that reached the runner by accident -- a
# probe, a test, a mistyped command -- must not be able to start it, so a
# ``--set <sealed set>`` invocation that would run anything is refused unless
# this variable names that set. It is checked in ``main`` after every refusal
# and before any client is built or any directory is created, so the refusal
# costs nothing and writes nothing.
#
# Nothing in this repository sets it. The owner sets it for the one command.
SEALED_RUN_ENV_VAR = "TRIBUNAL_SEALED_RUN"

# Imported after the paths, and only for the runner the sets are run through.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import grade, run_benchmark  # noqa: E402
from tribunal import events, loader  # noqa: E402

# The model id is a live value in exactly one module, and this is not it: the
# registration below names the model its run is fixed at by reading the decision
# rather than by repeating it, so there is one place to change it and
# ``tests/test_model.py`` can see that there is.
from tribunal.model import RUNTIME_MODEL  # noqa: E402


# --------------------------------------------------------------------------
# The arguments a run is fixed at, for the sets whose single run is a figure
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class RunArguments:
    """The arguments one set's run is fixed at, as its registration records them.

    Only ``wild-v2`` carries one, and only because its single run is the
    submission's generalisation figure: the freeze note fixes the arguments the
    run is made with, so an invocation that differed in one of them would
    produce a *different* measurement under the same name. It is refused by
    name rather than silently honoured, which is the rule ``--force`` and the
    switches that change what a run measures already follow for a sealed set.

    ``None`` means **the default**. The note fixes the prompts directory, the
    case deadline and the token budget as "the default" rather than as a value,
    and a registration that recorded today's number would be refusing the
    default the day the default moved. Every other field is a value, because
    the note fixes it as one -- ``judge_votes`` is the number 4, not "whatever
    the default happens to be".
    """

    model: str
    judge_votes: int
    verify_drafts: bool
    timeout_seconds: float
    concurrency: int
    prompts_dir: Optional[Path] = None
    case_deadline_seconds: Optional[float] = None
    token_budget: Optional[int] = None


@dataclass(frozen=True)
class DevelopmentSet:
    """One set of development cases, its key, and where its results live.

    ``runs_subdir`` is the directory the set's runs go under, and it is ``None``
    for the corpus because the corpus's run directory *is*
    ``runs/<model>/``. A second set is never given ``None``: its results must
    not land in a model's corpus run directory, and a distinct subdirectory is
    what makes that checkable rather than merely intended.

    ``sealed`` marks the one set that is run **once** and whose single run is
    the generalisation figure. It is the only field a set carries because of
    what its results *mean* rather than where they live, and it is what lets a
    switch that would replace that run be refused for this set and no other.

    ``policy_version`` is the version the set's **registration** fixes, and it
    is 1 for every set whose version is the command line's to choose. A set
    registered at a later version briefs every case at that version without a
    flag, refuses an explicit ``--policy-version``, and keeps its own run
    directory rather than moving one level down into a ``policy-v<N>`` one: its
    version is part of what the set *is*, not a switch on the invocation.

    ``run_arguments`` is the configuration the set's run is fixed at, and it is
    ``None`` for every set whose run may be made with whatever arguments the
    invocation gives. Where it is set, the freeze note has fixed the arguments
    and an invocation that differs in one of them is refused by name: the run
    is one measurement, and the arguments are part of what the measurement is.
    """

    name: str
    cases: Tuple[int, ...]
    key_path: Path
    runs_subdir: Optional[str]
    case_root: Optional[Path]
    summary: str
    sealed: bool = False
    policy_version: int = 1
    run_arguments: Optional[RunArguments] = None

    def key(self) -> Dict[int, grade.Ruling]:
        """This set's own answer key. Never the corpus key."""
        return grade.load_answer_key(self.key_path)

    def load_case(self, case_no: int) -> Mapping[str, Any]:
        """One of this set's cases, by number.

        The corpus is loaded through the manifest. A second set is loaded
        through its own index, which is what
        :func:`tribunal.loader.load_external_set_case` is for; the manifest
        cannot name a case it does not list.
        """
        if self.case_root is None:
            return loader.load_case(case_no)
        return loader.load_external_set_case(self.case_root, case_no)

    def runs_dir(self, runs_dir: Path = RUNS_DIR) -> Path:
        """Where this set's run directories live, under ``runs_dir``."""
        base = Path(runs_dir)
        return base if self.runs_subdir is None else base / self.runs_subdir

    def run_dir(self, model: str, runs_dir: Path = RUNS_DIR) -> Path:
        """This set's run directory for one model."""
        return run_benchmark.run_directory(self.runs_dir(runs_dir), model)


CORPUS = DevelopmentSet(
    name="corpus",
    cases=tuple(
        entry["case_no"] for entry in loader._read_json(PROJECT_ROOT / "data" / "index.json")
    ),
    key_path=CORPUS_KEY_PATH,
    runs_subdir=None,
    case_root=None,
    summary="the 29-case corpus the submission's headline figure is computed on",
)

SECOND_SET = DevelopmentSet(
    name="codex",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(
            loader.EXTERNAL_DIR / run_benchmark.SECOND_SET_RUNS_SUBDIR
        )
    ),
    key_path=ANSWER_DIR / "codex" / "ground_truth.json",
    runs_subdir=run_benchmark.SECOND_SET_RUNS_SUBDIR,
    case_root=loader.EXTERNAL_DIR / run_benchmark.SECOND_SET_RUNS_SUBDIR,
    summary=(
        "fifteen cases drafted by OpenAI Codex on 2026-09-24, copied in by the "
        "owner; development data, not a test set"
    ),
)

# The held-out set. It is deliberately **not** in ``DEVELOPMENT_SETS``: that
# tuple is what ``--report`` combines and what ``--set all`` runs, and neither
# may include a set that is run once. Its runs root is
# ``runs/wild/<model-slug>/`` and its key is its own file, so nothing of it is
# ever written into, or graded against, the two development sets' own.
SEALED_SET = DevelopmentSet(
    name="wild",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(
            loader.EXTERNAL_DIR / run_benchmark.SEALED_SET_RUNS_SUBDIR
        )
    ),
    key_path=ANSWER_DIR / run_benchmark.SEALED_SET_RUNS_SUBDIR / "ground_truth.json",
    runs_subdir=run_benchmark.SEALED_SET_RUNS_SUBDIR,
    case_root=loader.EXTERNAL_DIR / run_benchmark.SEALED_SET_RUNS_SUBDIR,
    summary=(
        "the held-out set (wild-v1): 64 cases derived from real complaints, "
        "prepared by their author as a development set; nobody who changed the "
        "system opened them before the freeze tagged freeze-2026-09-30, and they "
        "were run once from that tag; that single run is the only generalisation "
        "figure the submission reports"
    ),
    sealed=True,
)

# ``wild-dev`` -- the same 64 cases and the same key as the held-out set, as
# **development data**. From 2026-10-01 its answers may be read and the system
# may be changed to fix what they exposed, so it needs a set that can be run
# again. It is deliberately not a third development set and not a second sealed
# one: it is in neither ``DEVELOPMENT_SETS`` (what ``--set all`` runs and what
# the combined figure sums) nor ``ALL_SETS`` (what the recorded-drafts
# measurement reads), and its runs go to ``runs/wild-dev/<model-slug>/`` so that
# the single run under ``runs/wild/`` is never written again.
#
# It carries ``sealed=False``, and that is the whole of what makes re-running,
# ``--force`` and the advocate replay allowed for it: every one of those is
# refused by :func:`assert_not_sealed`, which refuses by name and for the one
# set marked sealed.
WILD_DEV = DevelopmentSet(
    name="wild-dev",
    cases=SEALED_SET.cases,
    key_path=SEALED_SET.key_path,
    runs_subdir=run_benchmark.WILD_DEV_RUNS_SUBDIR,
    case_root=SEALED_SET.case_root,
    summary=(
        "wild-v1 as development data: the same 64 cases and the same key as the "
        "held-out set, whose answers were read on 2026-10-01; it may be run "
        "again, and it is never combined with the development sets or with the "
        "held-out set's single run"
    ),
)

DEVELOPMENT_SETS: Tuple[DevelopmentSet, ...] = (CORPUS, SECOND_SET)

# The second sealed set, imported on 2026-10-03 and run once from a commit whose
# ``tribunal/``, ``prompts/`` and ``policy/`` trees equal those at the tag
# ``freeze-2026-10-03`` -- which need not be the tagged commit itself, and every
# event the run writes records the commit it was made from. It is the same kind
# of thing as the held-out set -- drafted without access to this repository,
# keyed by its own file, run once, and reported on its own -- and it is **not**
# the held-out set: 20 cases over a range of its own, and its single run is never
# added to ``wild``'s, to the combined figure or to ``--set all``.
#
# Its registration fixes policy version 2, which the held-out set's did not:
# ``POL-RD-13`` was approved through the policy-gap loop and the ``POL-RD-11``
# upfront remedy was published from version 2 on, so version 2 is the policy the
# submission now stands behind. Running ``--set wild-v2`` therefore uses version
# 2 without any flag, an explicit ``--policy-version`` is refused for it, and
# its runs go to ``runs/wild-v2/<model>/`` rather than to a ``policy-v2``
# directory inside that root.
WILD_V2 = DevelopmentSet(
    name="wild-v2",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(
            loader.EXTERNAL_DIR / run_benchmark.WILD_V2_SET_RUNS_SUBDIR
        )
    ),
    key_path=ANSWER_DIR / run_benchmark.WILD_V2_SET_RUNS_SUBDIR / "ground_truth.json",
    runs_subdir=run_benchmark.WILD_V2_SET_RUNS_SUBDIR,
    case_root=loader.EXTERNAL_DIR / run_benchmark.WILD_V2_SET_RUNS_SUBDIR,
    summary=(
        "the second sealed set (wild-v2): 20 cases prepared by OpenAI Codex for "
        "the owner and imported on 2026-10-03; nobody who changed the system has "
        "seen them, they are run once from a commit whose tribunal/, prompts/ "
        "and policy/ trees equal those at freeze-2026-10-03, at the policy "
        "version 2 this registration fixes, and that single run is the "
        "submission's generalisation figure"
    ),
    sealed=True,
    policy_version=2,
    # The arguments the run is made with, from the configuration table in
    # ``docs/notes/2026-10-03-the-second-freeze.md``. The model, the judge vote
    # count, the timeout and the concurrency are values there, so they are
    # values here; the prompts directory, the case deadline and the token budget
    # are "the default" there, so they are ``None`` here and are compared
    # against whatever the default is at the time of the run.
    run_arguments=RunArguments(
        model=RUNTIME_MODEL,
        judge_votes=4,
        verify_drafts=False,
        timeout_seconds=900.0,
        concurrency=2,
    ),
)

# The sets that are run **once**, in the order the report prints them. Each is
# printed in a section of its own and is never part of ``--set all`` or of the
# combined figure.
SEALED_SETS: Tuple[DevelopmentSet, ...] = (SEALED_SET, WILD_V2)

# The sets that exist to be run again. They are registered by name and are
# deliberately outside the tuples above: ``--set all``, the combined figure
# and the recorded-drafts measurement each read one of those, and a set whose
# cases are development data must not enter any of them by being named here.
RERUN_SETS: Tuple[DevelopmentSet, ...] = (WILD_DEV,)

# The sets whose **recorded runs** the measurements read. ``wild-v2`` is
# deliberately not one of them, and the reason is not that it has no run: its
# single run was committed on 2026-10-04 and it has drafts, brief digests and
# amounts to re-reduce. It is excluded because the amount-rule measurement and
# the recorded-drafts measurement have committed results over these three runs,
# and adding a fourth would change figures the submission reports -- which is a
# decision about measurement coverage, and not one a registration should settle
# by being edited.
ALL_SETS: Tuple[DevelopmentSet, ...] = DEVELOPMENT_SETS + (SEALED_SET,)

BY_NAME = {
    development_set.name: development_set
    for development_set in DEVELOPMENT_SETS + SEALED_SETS + RERUN_SETS
}


def named(name: str) -> DevelopmentSet:
    """One set by name. An unknown name raises rather than defaulting."""
    try:
        return BY_NAME[name]
    except KeyError:
        raise run_benchmark.BenchmarkError(
            "unknown development set {0!r}; known sets: {1}".format(
                name, ", ".join(sorted(BY_NAME))
            )
        ) from None


# The development-data caveat, in one place because two reports print it: this
# module's own and the baselines'. It is a paragraph rather than two sentences
# because it has to read correctly wherever it lands, and it names the corpus
# figure as the reported one and denies that either figure is the generalisation
# number. A reader who took a combined or a baseline figure for the submission's
# generalisation figure would be reading a number the submission does not make.
DEVELOPMENT_DATA_CAVEAT = (
    "Both development sets are development data, and neither is a test set. The "
    "corpus figure is the figure the submission reports; the combined figure is "
    "a sum over two sets that were drafted differently and share one template, "
    "so it is not a generalisation figure and does not replace the corpus "
    "number. The generalisation figures the submission reports belong to the "
    "two sealed sets, each drafted without access to this repository and each "
    "run exactly once: the held-out set's, from the commit tagged "
    "freeze-2026-09-30, and the second sealed set's, from a commit whose "
    "tribunal/, prompts/ and policy/ trees equal those at freeze-2026-10-03. "
    "Neither figure here is either of them, and the two are "
    "never added to each other either."
)

# The held-out set is printed on its own, and this is why. A sum of a
# development figure and the generalisation figure is neither, so the two are
# never added; and the sealed figure is a single run that has not happened when
# the development figures are read, so it is reported as ``not run`` rather
# than as zero.
SEALED_SET_CAVEAT = (
    "The held-out set is not a development set and is never added to the "
    "combined figure above. It was drafted without access to this repository "
    "and is run exactly once from the commit tagged freeze-2026-09-30; that "
    "single run is the only generalisation figure the submission reports. It "
    "is absent from data/index.json and is graded against "
    "eval/answers/wild/ground_truth.json, which is neither development key."
)

# The second sealed set is printed on its own for the held-out set's reasons and
# with two of its own: it is run once too, and its registration fixes the policy
# version it is run at, so its figure is a measurement of version 2 and of
# nothing else.
WILD_V2_CAVEAT = (
    "The second sealed set is not a development set and is never added to the "
    "combined figure above or to the held-out set's figure. It was prepared by "
    "OpenAI Codex for the owner and imported on 2026-10-03; it is run exactly "
    "once from a commit whose tribunal/, prompts/ and policy/ trees equal those "
    "at freeze-2026-10-03 -- every event the run writes records the commit it "
    "was made from -- at the policy version 2 its registration fixes, and that "
    "single run is the submission's generalisation "
    "figure. It is absent from data/index.json and is graded against "
    "eval/answers/wild-v2/ground_truth.json, which is neither development key "
    "and not the held-out set's key either."
)

# The heading and the caveat each sealed set is printed under, so a set added to
# ``SEALED_SETS`` cannot be printed without both.
SEALED_SET_SECTIONS = {
    SEALED_SET.name: (
        "The held-out set (wild-v1), on its own and never in the combined figure:",
        SEALED_SET_CAVEAT,
    ),
    WILD_V2.name: (
        "The second sealed set (wild-v2), on its own and never in the combined "
        "figure:",
        WILD_V2_CAVEAT,
    ),
}

# The re-runnable set is printed on its own for the same reason the held-out set
# is, and with one more that only it has: its cases *are* the held-out set's
# cases, so a reader who found its figure beside the held-out set's could take
# the second reading of one set for a second measurement of it.
RERUN_SET_CAVEAT = (
    "The re-runnable set is development data. It holds the held-out set's own "
    "64 cases and grades them against the held-out set's own key, whose answers "
    "were read on 2026-10-01 so that the system could be changed to fix what "
    "they exposed; a figure here is a reading of a set the system has now seen, "
    "and it is not a generalisation figure. Its runs go to "
    "runs/wild-dev/<model>/, which is not the directory holding the held-out "
    "set's single run. Re-running it, --force and the advocate replay are all "
    "allowed for it. It is never part of the combined figure and never part of "
    "--set all."
)


def assert_set_run_directory(
    run_dir: Path, development_set: DevelopmentSet, runs_dir: Path = RUNS_DIR
) -> Path:
    """Refuse a set's run directory that is not the set's own.

    ``runs/deepseek-deepseek-flash/`` holds the 29-case corpus result the
    submission reports. A second set's results are not corpus results, and a
    case written there would change what that directory means while leaving
    every file a reader would look at apparently intact. The check is made
    rather than intended, so a caller cannot ask for the headline directory by
    accident and get it.

    The corpus's own set is exempt because ``runs/<model>/`` *is* its
    directory; only a set with a subdirectory of its own is constrained.
    """
    resolved = Path(run_dir).resolve()
    if development_set.runs_subdir is None:
        return resolved
    root = development_set.runs_dir(runs_dir).resolve()
    if not resolved.is_relative_to(root):
        raise run_benchmark.BenchmarkError(
            "development set {0!r} may only be written under {1}, and this one "
            "would go to {2}".format(development_set.name, root, resolved)
        )
    return resolved


def assert_not_sealed(development_set: DevelopmentSet, switch: str) -> None:
    """Refuse a switch that would replace or re-take a sealed set's single run.

    A sealed set is run once from the frozen trees and that run must not be
    replaced. A switch that overwrote a case's result, or that produced one from
    a run already recorded, would make the figure a different measurement from
    the one the freeze names. It is refused **by the set's own name** rather than
    left to convention: the message used to say "the held-out set" whichever set
    it refused, which is not true of the second sealed set, and it used to call
    the run "the only generalisation figure the submission reports", which is
    true of neither set now that there are two. It is refused for the named set
    and for no other.
    """
    if development_set.sealed:
        raise run_benchmark.BenchmarkError(
            "the sealed set {0} is run once, so {1} is refused for it: its "
            "single run must not be replaced".format(development_set.name, switch)
        )


def _render_argument(value: Any) -> str:
    """One argument's value, as the refusal message spells it."""
    if value is True:
        return "on"
    if value is False:
        return "off"
    return str(value)


def run_argument_differences(
    development_set: DevelopmentSet,
    *,
    model: str,
    prompts_dir: Path,
    judge_votes: int,
    verify_drafts: bool,
    timeout_seconds: float,
    concurrency: int,
    case_deadline_seconds: float,
    token_budget: Optional[int],
) -> List[str]:
    """Every argument this invocation gives that the set is not registered for.

    Empty when the set fixes no arguments (every set but ``wild-v2``) and empty
    when the invocation is the one the set is registered for. Each entry names
    the argument, the value asked for and the registered value, because the
    point of the refusal is that a reader can see *which* argument would have
    made this a different measurement.

    The three settings the freeze note fixes as "the default" are stored as
    ``None`` and compared against the default itself, so the message says "the
    default" rather than repeating a number that is not the frozen thing.
    """
    frozen = development_set.run_arguments
    if frozen is None:
        return []

    differences = []
    for switch, asked, registered, default in (
        ("--model", model, frozen.model, None),
        ("--judge-votes", judge_votes, frozen.judge_votes, None),
        ("--verify-drafts", verify_drafts, frozen.verify_drafts, None),
        ("--timeout", timeout_seconds, frozen.timeout_seconds, None),
        ("--concurrency", concurrency, frozen.concurrency, None),
        ("--prompts-dir", prompts_dir, frozen.prompts_dir, run_benchmark.PROMPTS_DIR),
        (
            "--case-deadline",
            case_deadline_seconds,
            frozen.case_deadline_seconds,
            run_benchmark.pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
        ),
        ("--token-budget", token_budget, frozen.token_budget, None),
    ):
        if registered is None:
            registered, registered_text = default, "the default"
        else:
            registered_text = _render_argument(registered)
        if asked != registered:
            differences.append(
                "{0} is {1} and {2} is registered at {3}".format(
                    switch,
                    _render_argument(asked),
                    development_set.name,
                    registered_text,
                )
            )
    return differences


# --------------------------------------------------------------------------
# The sealed protocol: which cases a second invocation retries
# --------------------------------------------------------------------------
# A sealed set is run once, plainly. A failure caused by the infrastructure is
# retried once -- re-running the same command is the retry -- and a failure in
# which the model answered is not retried, because retrying it only re-samples
# the model. Before this existed, a second invocation re-attempted every case
# with no ``case-<NNNNN>.json``, SHAPE failures included: that is exactly what
# ``wild-v1``'s second invocation did to 517 and 533.
#
# The rule, in the terms ``docs/notes/2026-10-03-the-sealed-protocol-addendum.md``
# states it:
#
# * an **attempt** of a case is one invocation in which that case has at least
#   one ``agent_call`` event -- or, for the failures that make no call at all, one
#   in which it recorded a terminal event. A transport failure raises before the
#   transcript entry exists, so its ``case_failed`` is the only marker the
#   invocation tried the case, and without this the third-attempt cap could never
#   bind on TRANSPORT, TIMEOUT, DEADLINE or INTERRUPTED;
# * a case is **not retried** when its last attempt ended in a ``case_failed``
#   event with ``failure_kind`` SHAPE **and** every ``agent_call`` of that case
#   in that invocation has ``status`` 200;
# * a case is **retried once** when its last attempt ended in TRANSPORT,
#   TIMEOUT, DEADLINE or INTERRUPTED, or in SHAPE with any ``agent_call``
#   ``status`` other than 200;
# * no case gets a third attempt -- two attempts and no result is no ruling;
# * an attempt that ended with no terminal event does not count: the process was
#   killed, so this invocation cannot say the case failed. It is printed, so the
#   record shows it;
# * a case with a result is never re-run, which the cache already enforces.
#
# Nothing here reaches ``tribunal/``: the rule reads the run's own event log,
# and the package that builds the runtime bundle never sees a run.
HTTP_OK = 200
RETRYABLE_FAILURE_KINDS = frozenset(
    {
        run_benchmark.FAILURE_TRANSPORT,
        run_benchmark.FAILURE_TIMEOUT,
        run_benchmark.FAILURE_DEADLINE,
        run_benchmark.FAILURE_INTERRUPTED,
    }
)

# The two errors that say no model was reached: the key was absent, or the model
# was not provisioned. A ``case_failed`` whose ``detail`` starts with one of these
# names a configuration error and not an attempt -- nothing was called and
# nothing was sampled, so retrying re-samples nothing. The detail is written by
# the runner as ``"<type name>: <message>"``, so the type name is what is read.
CONFIGURATION_ERROR_TYPES = (
    "MissingAPIKeyError",
    "ModelNotProvisionedError",
)


@dataclass(frozen=True)
class _SealedAttempt:
    """One invocation of a case, as that case's own events describe it."""

    invocation: Any
    statuses: Tuple[Any, ...]
    # ``None`` when the invocation recorded neither a ruling nor a case_failed
    # for the case: the process was killed and this attempt does not count.
    terminal: Optional[str]
    failure_kind: Optional[str]
    # The ``case_failed`` detail, read for its leading type name alone.
    detail: Optional[str] = None

    @property
    def is_a_configuration_error(self) -> bool:
        """True when this attempt never reached a model.

        A terminal-only attempt -- no ``agent_call`` at all -- whose failure is
        one of the two configuration errors says the key was absent or the model
        was not provisioned. Nothing was called, so this is not an attempt: it is
        not counted toward a case's two, and it is not printed as an attempt that
        does not count either, because it reached a decision rather than being
        interrupted.
        """
        if self.terminal != events.EVENT_CASE_FAILED or self.statuses:
            return False
        return any(
            (self.detail or "").startswith(name) for name in CONFIGURATION_ERROR_TYPES
        )


def _sealed_attempts(run_dir: Path, case_no: int) -> List["_SealedAttempt"]:
    """Every attempt of one case, oldest first, read off the run's event log.

    An attempt is an invocation that called an agent for this case, or that
    recorded a terminal event for it. The second half is not a convenience: a
    transport failure makes **no** ``agent_call`` -- the call raised before the
    transcript entry existed -- so its ``case_failed`` is the only thing that
    says the invocation tried the case. An invocation that only began the case,
    because it found it cached, is neither and is not an attempt.

    A configuration error is not an attempt and is left out of the list
    entirely, so neither the two-attempt cap nor the printed record sees it.
    """
    order: List[Any] = []
    buckets: Dict[Any, Dict[str, Any]] = {}
    for event in events.read_events(Path(run_dir) / events.EVENTS_FILE):
        if event.get("case") != case_no:
            continue
        invocation = event.get("invocation")
        bucket = buckets.get(invocation)
        if bucket is None:
            bucket = {
                "statuses": [],
                "terminal": None,
                "failure_kind": None,
                "detail": None,
            }
            buckets[invocation] = bucket
            order.append(invocation)
        name = event.get("event")
        if name == events.EVENT_AGENT_CALL:
            bucket["statuses"].append(event.get("status"))
        elif name == events.EVENT_RULING:
            bucket["terminal"] = events.EVENT_RULING
        elif name == events.EVENT_CASE_FAILED:
            bucket["terminal"] = events.EVENT_CASE_FAILED
            bucket["failure_kind"] = event.get("failure_kind")
            bucket["detail"] = event.get("detail")
    attempts: List["_SealedAttempt"] = []
    for invocation in order:
        bucket = buckets[invocation]
        if not bucket["statuses"] and bucket["terminal"] is None:
            continue
        attempt = _SealedAttempt(
            invocation=invocation,
            statuses=tuple(bucket["statuses"]),
            terminal=bucket["terminal"],
            failure_kind=bucket["failure_kind"],
            detail=bucket["detail"],
        )
        if attempt.is_a_configuration_error:
            continue
        attempts.append(attempt)
    return attempts


def _sealed_case_has_a_result(run_dir: Path, case_no: int) -> bool:
    """True when the run already holds this case's result.

    Asked of the cache, and asked *before* the events, because the cache is what
    the runner itself consults: a case with a case file is one the runner will not
    call, so the protocol keeps it in ``selected`` and the invocation's own
    reporting says it was cached. A case the protocol had dropped instead would
    be reported as absent rather than as cached, which is a different statement
    about the run.
    """
    return run_benchmark.load_cached(Path(run_dir), case_no) is not None


def _refuse_a_broken_sealed_chain(run_dir: Path) -> None:
    """Refuse to apply the protocol to a log whose chain does not verify.

    The protocol is a reading of the run's own record, so a record that does not
    verify is not a record to decide from: a line could have been added, removed
    or edited, and the decision would rest on it. The broken line is named, so a
    reader can look at it rather than being told only that something is wrong.

    One break is tolerated, and it is the one a killed run leaves: a **last** line
    that is not a JSON object at all. A process stopped mid-write ends the file
    part-way through a record, and that is an incomplete write rather than an
    edited record -- the attempt it belongs to has no terminal event, which the
    protocol already reads as an attempt that does not count. An edited line
    still parses, so it is never tolerated, and neither is anything in the middle
    of the file.
    """
    path = Path(run_dir) / events.EVENTS_FILE
    if not path.exists():
        return
    broken = events.verify_chain(path)
    if broken is None:
        return
    if broken.kind == "malformed" and broken.line_number == len(
        events.read_lines(path)
    ):
        return
    raise run_benchmark.BenchmarkError(
        "the sealed run's event log does not verify, so the sealed protocol "
        "is not applied to it: {0}".format(broken.describe())
    )


def _sealed_verdict(attempts: Sequence["_SealedAttempt"]) -> Optional[str]:
    """Why a case is **not** run again, or ``None`` when it is.

    The reason is one of the ones the protocol prints. An attempt with no
    terminal event does not count toward the two, so a case killed mid-call is
    run again; a configuration error is not in ``attempts`` at all.
    """
    counted = [attempt for attempt in attempts if attempt.terminal is not None]
    if len(counted) >= 2:
        return "two attempts"
    if len(counted) == 1:
        last = counted[0]
        if last.terminal == events.EVENT_RULING:
            # A ``ruling`` event with no case file. A case file holding a result
            # is kept before this is reached, so this is a record that a ruling
            # was made and nothing was written for it: the model answered, so it
            # is not re-sampled twice -- it is retried once, and the two-attempt
            # cap is what stops the second retry.
            return None
        if last.failure_kind == run_benchmark.FAILURE_SHAPE:
            if last.statuses and all(status == HTTP_OK for status in last.statuses):
                return "SHAPE, every call answered 200"
            # A server error that exhausted the client's own retries reaches the
            # runner as SHAPE with a call that was not answered 200, and it is
            # retried once.
            return None
        if last.failure_kind in RETRYABLE_FAILURE_KINDS:
            return None
        # Everything else, including a kind this code does not know, is not
        # retried: the model answered, so retrying would only re-sample it, and
        # the reason names the kind so the record says which one it was.
        return "{0}, which is not a retried kind".format(last.failure_kind or "FAILED")
    return None


def cases_the_sealed_protocol_will_not_retry(
    development_set: DevelopmentSet,
    selected: Sequence[int],
    model: str,
    runs_dir: Path = RUNS_DIR,
    *,
    progress: Callable[[str], None] = lambda text: print(text, flush=True),
) -> List[int]:
    """The cases of ``selected`` a second sealed invocation runs again.

    Reads the run's own ``events.jsonl``, read-only, and applies the rule above.
    Every case it drops, and every attempt it does not count, is printed so the
    record shows what happened.

    The decision itself is :func:`sealed_protocol_plan`'s, and it is called
    rather than copied: ``--check`` renders that function's data and this
    function prints it, so the plan a reader is shown and the run that follows it
    are one predicate. A second copy of the loop here would be a second place for
    the two to disagree, and the disagreement would be silent -- a run whose plan
    said one thing and whose selection said another.

    A case the run already holds a result for is kept without being looked at:
    the cache is what the runner consults, and a case the protocol dropped would
    be reported as absent rather than as cached. A log whose chain does not
    verify is refused rather than read.
    """
    would_run, not_retried, do_not_count = sealed_protocol_plan(
        development_set, selected, model, runs_dir
    )
    for case_no in do_not_count:
        progress(
            "attempt with no terminal event, so it does not count under "
            "the sealed protocol: {0}".format(case_no)
        )
    for case_no, verdict in not_retried:
        progress(
            "not retried under the sealed protocol: {0} ({1})".format(case_no, verdict)
        )
    return would_run


def sealed_protocol_plan(
    development_set: DevelopmentSet,
    selected: Sequence[int],
    model: str,
    runs_dir: Path = RUNS_DIR,
) -> Tuple[List[int], List[Tuple[int, str]], List[int]]:
    """The one implementation of the rule, as data rather than as printed lines.

    Returns ``(would_run, not_retried, do_not_count)``: the cases a plain
    invocation runs; the cases it drops, each with the reason, in set order; and
    the cases with an attempt that ended with no terminal event. The caller
    decides what to do with the three -- a run prints them, ``--check`` renders
    them as the plan -- so the plan a reader is shown and the run that follows it
    are the same predicate and cannot drift apart.

    A case the run already holds a result for is in ``would_run``, because the
    invocation does select it and the runner's cache is what then reports it as
    cached, and it prints no reason of its own.
    """
    run_dir = development_set.run_dir(model, runs_dir)
    _refuse_a_broken_sealed_chain(run_dir)
    would_run: List[int] = []
    not_retried: List[Tuple[int, str]] = []
    do_not_count: List[int] = []
    for case_no in selected:
        if _sealed_case_has_a_result(run_dir, case_no):
            would_run.append(case_no)
            continue
        attempts = _sealed_attempts(run_dir, case_no)
        for attempt in attempts:
            if attempt.terminal is None:
                do_not_count.append(case_no)
        verdict = _sealed_verdict(attempts)
        if verdict is None:
            would_run.append(case_no)
        else:
            not_retried.append((case_no, verdict))
    return would_run, not_retried, do_not_count


def render_sealed_plan(
    development_set: DevelopmentSet,
    would_run: Sequence[int],
    not_retried: Sequence[Tuple[int, str]],
    do_not_count: Sequence[int],
) -> str:
    """The plan ``--check`` prints, as one string, so a test can assert all of it."""
    lines = [
        "sealed set {0} -- what one plain invocation would run".format(
            development_set.name
        ),
        "  would run ({0}): {1}".format(
            len(would_run),
            ", ".join(str(case_no) for case_no in would_run) or "nothing",
        ),
        "  would not run ({0}):".format(len(not_retried)),
    ]
    if not_retried:
        lines.extend(
            "    not retried under the sealed protocol: {0} ({1})".format(
                case_no, verdict
            )
            for case_no, verdict in not_retried
        )
    else:
        lines.append("    nothing")
    lines.append("  attempts that do not count ({0}):".format(len(do_not_count)))
    if do_not_count:
        lines.extend(
            "    attempt with no terminal event, so it does not count under the "
            "sealed protocol: {0}".format(case_no)
            for case_no in do_not_count
        )
    else:
        lines.append("    nothing")
    return "\n".join(lines)


def _nothing_left_to_run(
    development_set: DevelopmentSet, model: str, runs_dir: Path = RUNS_DIR
) -> "run_benchmark.RunSummary":
    """An empty summary for an invocation of a sealed set that had nothing to run.

    A second or third invocation can find every case already decided, already
    out of attempts, or answered by the model. Nothing is called and nothing is
    written, and the summary carries ``sealed_nothing_to_run`` so the printer
    says that in one line: the ordinary summary would show this invocation's
    limits and no case at all, which reads as a run that produced nothing rather
    than as one that correctly called nothing.
    """
    stamp = datetime.now(timezone.utc).isoformat()
    return run_benchmark.RunSummary(
        model=model,
        run_dir=development_set.run_dir(model, runs_dir),
        started_at=stamp,
        ended_at=stamp,
        stop_reason=run_benchmark.STOP_COMPLETED,
        sealed_protocol=True,
        sealed_nothing_to_run=True,
    )


def run_set(
    development_set: DevelopmentSet,
    model: str,
    *,
    runs_dir: Path = RUNS_DIR,
    cases: Optional[Sequence[int]] = None,
    force: bool = False,
    **kwargs: Any,
) -> "run_benchmark.RunSummary":
    """Run one development set through the corpus runner.

    Everything the corpus runner does, it does here, because this *is* the
    corpus runner: the cache, the provenance, both deadlines, the token budget
    and the replay check all come from :func:`run_benchmark.run_benchmark` and
    are not reimplemented. Four things are supplied that the corpus run does not
    supply -- the set's cases, its own key, its own loader and its own runs
    directory -- and, for a set with a subdirectory of its own, a label, so the
    metadata names the set. The corpus carries none: ``runs/<model>/`` *is* its
    directory, and the runner refuses a labelled run aimed there.

    The destination is checked before anything is written, and ``force`` is
    refused outright for the held-out set, whose single run must not be replaced.

    For a **sealed** set with ``force`` false, the sealed protocol decides which
    of ``selected`` this invocation runs: a failure caused by the infrastructure
    is retried once, a failure in which the model answered is not, no case gets a
    third attempt, and an attempt that ended with no terminal event does not
    count. It is stated in
    ``docs/notes/2026-10-03-the-sealed-protocol-made-executable.md`` and applied
    by :func:`cases_the_sealed_protocol_will_not_retry`. When nothing is left,
    no call is made and an empty summary is returned.
    """
    if force:
        assert_not_sealed(development_set, "--force")

    selected = list(development_set.cases if cases is None else cases)
    unknown = [case_no for case_no in selected if case_no not in set(development_set.cases)]
    if unknown:
        raise run_benchmark.BenchmarkError(
            "case(s) {0} are not in development set {1!r}".format(
                ", ".join(str(case_no) for case_no in unknown), development_set.name
            )
        )

    if development_set.sealed and not force:
        # The sealed protocol, and it is applied here rather than in the runner
        # because it is a property of a *sealed set's second invocation* and not
        # of a run: re-running the same command retries only what the
        # infrastructure failed, and a case the model answered is not
        # re-sampled. A case the rule keeps is run by the runner below exactly as
        # before, and the cache still skips a case that already has a result.
        selected = cases_the_sealed_protocol_will_not_retry(
            development_set, selected, model, runs_dir
        )
        if not selected:
            return _nothing_left_to_run(development_set, model, runs_dir)

    set_runs_dir = development_set.runs_dir(runs_dir)
    assert_set_run_directory(
        development_set.run_dir(model, runs_dir), development_set, runs_dir
    )
    # A set whose registration fixes the policy version briefs at that version
    # whatever the invocation says, and its run keeps the set's own directory
    # rather than moving one level down into a ``policy-v<N>`` one: the version
    # is part of what the set is, not a switch on the run. ``wild-v2`` is the one
    # set that uses this.
    if development_set.policy_version != run_benchmark.DEFAULT_POLICY_VERSION:
        kwargs["policy_version"] = development_set.policy_version
        kwargs["policy_version_moves_the_run"] = False
    summary = run_benchmark.run_benchmark(
        model,
        selected,
        runs_dir=set_runs_dir,
        # The top-level root, not the set's: the guard that closes the held-out
        # set's own root has to compare against ``<runs root>/wild``, and for the
        # held-out set ``set_runs_dir`` *is* that root.
        held_out_root=Path(runs_dir),
        # The permit for an un-run sealed root is issued *here* and nowhere else,
        # and only for the set whose registration names that root. The runner
        # compares this name against the sealed root it is about to write under,
        # so ``python3 -m eval.run_benchmark --runs-dir runs/wild-v2`` issues no
        # permit at all and is refused, and so is any other set pointed at the
        # same root. Passing the name rather than a boolean is what makes the
        # permit a statement about *which set* is running, so the runner cannot
        # be talked into opening a sealed root by a caller that merely wants it
        # open -- and a name that matches no sealed root opens nothing.
        sealed_permit_set=development_set.name,
        key=development_set.key(),
        key_path=development_set.key_path,
        case_loader=development_set.load_case,
        force=force,
        # The corpus is run unlabelled, exactly as ``python -m
        # eval.run_benchmark`` runs it, and its case files record
        # ``development_set: null``. Labelling it "corpus" made the set that
        # owns ``runs/<model>/`` the one set that could not run into it: the
        # runner refuses a labelled run whose destination is the corpus
        # directory, and that refusal is right for every other set.
        label=None if development_set.runs_subdir is None else development_set.name,
        **kwargs,
    )
    # The sealed protocol is what chose this invocation's cases, so the summary
    # says so and the end-of-run failures header points at the protocol instead of
    # at the plain cache line. For a development set the flag is False and that
    # header is what it always was.
    summary.sealed_protocol = development_set.sealed
    return summary


# --------------------------------------------------------------------------
# Reporting the sets separately and combined
# --------------------------------------------------------------------------
def cached_cases(
    development_set: DevelopmentSet, model: str, runs_dir: Path = RUNS_DIR
) -> List[int]:
    """The set's cases this model has a cached ruling for, in set order."""
    present = set(run_benchmark.cached_case_numbers(development_set.run_dir(model, runs_dir)))
    return [case_no for case_no in development_set.cases if case_no in present]


def _rulings(run_dir: Path, case_nos: Sequence[int]) -> Dict[int, Any]:
    produced: Dict[int, Any] = {}
    for case_no in case_nos:
        document = run_benchmark.load_cached(run_dir, case_no)
        if document is not None:
            produced[case_no] = document.get("ruling")
    return produced


@dataclass(frozen=True)
class SetFigures:
    """One set's numbers, read off disk, graded against that set's own key."""

    name: str
    run_dir: Path
    expected: int
    produced: int
    report: Optional[grade.GradeReport]

    @property
    def exact(self) -> Optional[int]:
        return None if self.report is None else self.report.exact_matches

    @property
    def graded(self) -> int:
        return 0 if self.report is None else self.report.total

    def field(self, name: str) -> Optional[Tuple[int, int]]:
        return None if self.report is None else self.report.field_tally(name)


def figures_for(
    development_set: DevelopmentSet, model: str, runs_dir: Path = RUNS_DIR
) -> SetFigures:
    """Grade one set over the cases it has produced, against its own key.

    Over the cases the set has actually produced a ruling for, so a set that has
    not been run reports nothing rather than reporting every case as a miss.
    """
    run_dir = development_set.run_dir(model, runs_dir)
    produced_cases = cached_cases(development_set, model, runs_dir)
    if not produced_cases:
        return SetFigures(
            name=development_set.name,
            run_dir=run_dir,
            expected=len(development_set.cases),
            produced=0,
            report=None,
        )
    report = run_benchmark.grade_run(
        run_dir,
        development_set.key(),
        produced_cases,
        # The set's own loader, so each case's brief can be rebuilt for the
        # amount provenance the report prints. Without it every case of this set
        # would report an unavailable brief, because the corpus manifest cannot
        # name a case it does not list.
        case_loader=development_set.load_case,
        # And at the set's own registered version, so that brief is the one the
        # run was decided under rather than the version-1 brief of the same case.
        policy_version=development_set.policy_version,
    )
    return SetFigures(
        name=development_set.name,
        run_dir=run_dir,
        expected=len(development_set.cases),
        produced=len(produced_cases),
        report=report,
    )


def combined_figures(
    model: str,
    runs_dir: Path = RUNS_DIR,
    sets: Sequence[DevelopmentSet] = DEVELOPMENT_SETS,
) -> Tuple[int, Optional[grade.GradeReport]]:
    """Every case of every set, each graded against the key it belongs to.

    One produced mapping and one key, built by merging the sets: a case number
    is in exactly one set's key, so the merge is a union and no case is counted
    twice. Cases no set has produced a ruling for are left out, so a combined
    figure is over what has actually been run.

    ``staleness`` and ``replay`` are deliberately not carried here. Both are
    properties of a *run directory* rather than of a case, and two sets live in
    two directories; folding them into one report would either drop one set's or
    claim a uniformity that does not exist. The per-set reports carry both.
    """
    produced: Dict[int, Any] = {}
    key: Dict[int, grade.Ruling] = {}
    for development_set in sets:
        run_dir = development_set.run_dir(model, runs_dir)
        for case_no in cached_cases(development_set, model, runs_dir):
            document = run_benchmark.load_cached(run_dir, case_no)
            if document is not None:
                produced[case_no] = document.get("ruling")
        key.update(development_set.key())
    if not produced:
        return 0, None
    # Scored over the cases that were produced, so a combined figure is over
    # what has actually been run rather than counting an unrun set's cases as
    # misses. ``corpus`` is the union of both keys, so the report can still say
    # whether the whole of both was covered.
    subset = {case_no: key[case_no] for case_no in produced}
    return len(produced), grade.grade(produced, subset, corpus=key)


def currency_for(
    development_set: DevelopmentSet,
    model: str,
    runs_dir: Path = RUNS_DIR,
    prompts_dir: Path = run_benchmark.PROMPTS_DIR,
) -> grade.Staleness:
    """Whether one set's cached results still belong to this code.

    Checked with **this set's own loader**, because a development set handed the
    corpus loader reads ``unknown`` on every one of its cases: the manifest
    cannot name a case it does not list, so no brief is rebuilt and nothing is
    established. The prompt channel is answered from each case's own transcript
    by :class:`run_benchmark.BriefStaleness`, the same checker the runner builds
    for a set it is about to run.

    Checked at **this set's registered policy version** too, and for the same
    reason: a set whose registration fixes a later version briefs every case at
    that version, so a checker that rebuilt the briefs at version 1 would report
    every case of a correct run as a moved brief -- a set that reads as stale
    when nothing has moved.
    """
    run_dir = development_set.run_dir(model, runs_dir)
    checker = run_benchmark.BriefStaleness(
        run_benchmark.brief_digest_for(
            development_set.load_case, policy_version=development_set.policy_version
        ),
        run_dir=run_dir,
        prompts_dir=prompts_dir,
        policy_version=development_set.policy_version,
    )
    return run_benchmark.brief_staleness(
        run_dir, cached_cases(development_set, model, runs_dir), checker
    )


def currency_line(
    development_set: DevelopmentSet, model: str, runs_dir: Path = RUNS_DIR
) -> str:
    """One set's currency, as the four counts the report prints.

    ``current`` is the rest of what the set has produced. The two stale counts
    are the two channels and are never merged, and ``unknown`` is a result this
    code could not answer for -- which is not a result it agrees with.
    """
    produced = len(cached_cases(development_set, model, runs_dir))
    staleness = currency_for(development_set, model, runs_dir)
    current = produced - len(staleness.stale) - len(staleness.unknown)
    return "  {0:<8} current {1:>3}, stale_brief {2:>3}, stale_prompts {3:>3}, unknown {4:>3}".format(
        development_set.name,
        current,
        len(staleness.stale_brief),
        len(staleness.stale_prompts),
        len(staleness.unknown),
    )


def _render_row(figures: SetFigures) -> str:
    if figures.report is None:
        return "  {0:<8} {1:<40} {2:>5}  {3:>9}".format(
            figures.name,
            _relative(figures.run_dir),
            "{0}/{1}".format(0, figures.expected),
            "not run",
        )
    cells = []
    for name in grade.GRADED_FIELDS:
        tally = figures.field(name)
        cells.append("{0}/{1}".format(tally[0], tally[1]) if tally else "-")
    return "  {0:<8} {1:<40} {2:>5}  {3:>9}  {4:>6} {5:>6} {6:>6} {7:>6}".format(
        figures.name,
        _relative(figures.run_dir),
        "{0}/{1}".format(figures.produced, figures.expected),
        "{0}/{1}".format(figures.exact, figures.graded),
        cells[0],
        cells[1],
        cells[2],
        cells[3],
    )


def _relative(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return Path(path).name


def _render_case_facts_section(figures: Sequence[SetFigures]) -> List[str]:
    """The per-case cost, provenance and tag table, one per set that has one.

    The same columns a run report prints, filled from the same rows:
    :func:`eval.grade.case_fact_rows` is the one place the values are computed,
    so the two reports cannot come to show different figures under the same
    heading. Every value is code's -- a token split summed off a transcript, a
    wall clock and a vote read off a cache entry, a provenance computed from the
    brief this code builds, and four pattern matches over an explanation.

    A set that has not been run has no report and contributes nothing, which is
    what keeps an unrun set from printing a table of dashes that a reader could
    mistake for a run that produced nothing.
    """
    populated = [
        item
        for item in figures
        if item.report is not None and item.report.facts_checked
    ]
    if not populated:
        return []
    lines = [
        "",
        "Per case — cost, provenance and explanation tags",
        "",
        "Computed by code from each case's own artifacts: the token split summed "
        "off its transcript by role, the wall clock and the vote agreement read "
        "off its cache entry, the amount provenance computed from the brief this "
        "code builds, and the four tags matched over the ruling's explanation by "
        "regular expression and keyword. No model is involved. A dash means the "
        "artifact does not record the figure. `vote agreement` is the share of "
        "the judge's drafts that agreed on the published ruling, and it is not "
        "the judge's own `confidence`. The patterns, and what each is known to "
        "miss and to mistake, are documented in "
        "`docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.",
    ]
    for item in populated:
        lines.append("")
        lines.append("{0} — {1}".format(item.name, _relative(item.run_dir)))
        lines.append("")
        lines.append("| {0} |".format(" | ".join(grade.CASE_FACTS_COLUMNS)))
        lines.append("|{0}|".format("|".join("---" for _ in grade.CASE_FACTS_COLUMNS)))
        for row in grade.case_fact_rows(item.report):
            lines.append("| {0} |".format(" | ".join(row)))
    return lines


# The column header both set tables carry. One string, so the development table
# and the held-out set's cannot come to show different columns under the same
# heading.
_SET_TABLE_HEADER = "  {0:<8} {1:<40} {2:>5}  {3:>9}  {4:>6} {5:>6} {6:>6} {7:>6}".format(
    "set", "run directory", "cases", "exact", "ruling", "amount", "driver", "refs"
)


def render_development_sets(model: str, runs_dir: Path = RUNS_DIR) -> str:
    """The sets separately, then combined, then each separate set on its own.

    Reads cached runs only. The corpus figure and the combined figure are
    different claims and the text says so. The combined figure sums two sets that
    were drafted differently and share one template; it is not a generalisation
    figure and it does not replace the corpus number. The generalisation figures
    belong to the two sealed sets -- the held-out set, run once from the commit
    tagged ``freeze-2026-09-30``, and the second sealed set, run once from a
    commit whose ``tribunal/``, ``prompts/`` and ``policy/`` trees equal those at
    ``freeze-2026-10-03`` -- and each is therefore printed in a
    section of its own, never as a third row of the table above, never inside the
    combined line and never added to the other. The re-runnable set is printed in
    a section of its own too, because it holds the held-out set's own cases read
    as development data.

    The per-case block carries the same cost, provenance and explanation columns
    a run's own ``report.md`` carries, for every case of every set that has been
    run, so a figure in the summary can be traced to the case it came from
    without opening a cache entry.
    """
    lines = [
        "Development sets — {0}".format(model),
        "",
        "Separately, each set graded against its own key:",
        "",
        _SET_TABLE_HEADER,
    ]
    figures = [figures_for(development_set, model, runs_dir) for development_set in DEVELOPMENT_SETS]
    for item in figures:
        lines.append(_render_row(item))

    lines.append("")
    lines.append("Currency, each set checked with its own loader and its own briefs:")
    lines.append("")
    for development_set in DEVELOPMENT_SETS:
        lines.append(currency_line(development_set, model, runs_dir))

    total_expected = sum(item.expected for item in figures)
    produced_total, combined = combined_figures(model, runs_dir)
    lines.append("")
    lines.append("Combined, every case graded against the key it belongs to:")
    lines.append("")
    if combined is None:
        lines.append("  no case of any development set has been run for this model")
    else:
        per_set = "; ".join(
            "{0} {1} of {2}".format(item.name, item.produced, item.expected) for item in figures
        )
        lines.append(
            "  produced  {0} of {1} cases  ({2})".format(
                produced_total, total_expected, per_set
            )
        )
        lines.append(
            "  exact     {0}/{1} over the cases produced".format(
                combined.exact_matches, combined.total
            )
        )
    lines.extend(_render_case_facts_section(figures))

    # The held-out set is printed on its own and never inside the combined figure
    # above. It is not a third development set: that line is a sum over two sets
    # that were drafted the same way, and adding the one set whose single run is
    # the generalisation figure would make it a sum of two different claims.
    #
    # Each sealed set gets a section of its own. They are two different sets --
    # two case ranges, two keys, two freeze tags, two policy versions -- and one
    # table under one heading would read as one set measured twice.
    for development_set in SEALED_SETS:
        heading, caveat = SEALED_SET_SECTIONS[development_set.name]
        sealed_figures = [figures_for(development_set, model, runs_dir)]
        lines.append("")
        lines.append(heading)
        lines.append("")
        lines.append(_SET_TABLE_HEADER)
        for item in sealed_figures:
            lines.append(_render_row(item))
        lines.append("")
        lines.append("Currency, checked with the set's own loader and its own briefs:")
        lines.append("")
        lines.append(currency_line(development_set, model, runs_dir))
        lines.append("")
        lines.append(caveat)
        lines.extend(_render_case_facts_section(sealed_figures))

    # The re-runnable set, printed on its own and for the same reason. It is not
    # a third development set -- the combined line above is a sum over two sets
    # that were drafted the same way -- and it is not the held-out set either:
    # it is the held-out set's cases read as development data, in a run
    # directory of its own, so the two figures are never added and never
    # presented as one set measured twice.
    rerun_figures = [
        figures_for(development_set, model, runs_dir) for development_set in RERUN_SETS
    ]
    lines.append("")
    lines.append(
        "The re-runnable set, on its own, never in the combined figure and never "
        "in the held-out set's section:"
    )
    lines.append("")
    lines.append(_SET_TABLE_HEADER)
    for item in rerun_figures:
        lines.append(_render_row(item))
    lines.append("")
    lines.append("Currency, checked with the set's own loader and its own briefs:")
    lines.append("")
    for development_set in RERUN_SETS:
        lines.append(currency_line(development_set, model, runs_dir))
    lines.append("")
    lines.append(RERUN_SET_CAVEAT)
    lines.extend(_render_case_facts_section(rerun_figures))

    lines.append("")
    lines.append(DEVELOPMENT_DATA_CAVEAT)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.development_sets",
        description=(
            "Run a development set through the corpus runner, or report the sets "
            "from their cached runs. The second development set is the fifteen "
            "cases under data/external/codex/, keyed separately from the corpus. "
            "The held-out set -- the 64 cases under data/external/wild/ -- is "
            "registered here as well, but it is run once: it is never part of "
            "--set all and never part of the combined figure. The re-runnable "
            "set, wild-dev, holds those same 64 cases and that same key as "
            "development data and may be run again, into runs/wild-dev/; it is "
            "likewise never part of --set all and never part of the combined "
            "figure. The second sealed set, wild-v2 -- the 20 cases under "
            "data/external/wild-v2/ -- is registered here too and is run once "
            "from a commit whose tribunal/, prompts/ and policy/ trees equal "
            "those at freeze-2026-10-03, at the policy version 2 its "
            "registration fixes and with no --policy-version flag; it is "
            "never part of --set all and never part of the combined figure."
        ),
    )
    parser.add_argument("--model", default=None, help="the model id; defaults to tribunal/model.py")
    parser.add_argument(
        "--set",
        dest="set_name",
        default="all",
        help=(
            "which set: {0}, or all. all means the development sets and never "
            "includes the held-out set, which is run once and only by name".format(
                ", ".join(sorted(BY_NAME))
            )
        ),
    )
    parser.add_argument(
        "--cases",
        default=None,
        help="comma-separated case numbers within the set; default is the whole set",
    )
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--prompts-dir", type=Path, default=run_benchmark.PROMPTS_DIR)
    parser.add_argument("--force", action="store_true", help="re-run cases that are already cached")
    parser.add_argument("--token-budget", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=run_benchmark.DEFAULT_CONCURRENCY)
    parser.add_argument("--timeout", type=float, default=run_benchmark.llm.DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--case-deadline",
        type=float,
        default=run_benchmark.pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
    )
    parser.add_argument(
        "--judge-votes",
        type=int,
        default=run_benchmark.pipeline.DEFAULT_JUDGE_VOTES,
        metavar="K",
        help=(
            "how many times to ask each case's judge on the same inputs; the "
            "majority decides, and 1 is the single-draft behaviour"
        ),
    )
    parser.add_argument(
        "--replay-advocates",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help="reuse the advocates recorded in RUN_DIR and call only the judge",
    )
    parser.add_argument(
        "--replay-check",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help="report whether --replay-advocates RUN_DIR would accept each case; reads only",
    )
    parser.add_argument(
        "--verify-drafts",
        action="store_true",
        help=(
            "after each case's drafts pass the code checks, ask a verifier once per "
            "case whether the brief supports every factual statement the drafts "
            "state; only a material contradiction makes a draft abstain"
        ),
    )
    parser.add_argument(
        "--ablate",
        choices=list(run_benchmark.brief.ABLATIONS),
        default=None,
        metavar="NAME",
        help=(
            "build every case's brief with one thing removed, so the run measures "
            "the pipeline without it: {0}. Off by default. The run writes to "
            "runs/ablation/<name>/<model>/ -- under the set's own root, so the "
            "second set's go to runs/codex/ablation/<name>/<model>/ -- and never "
            "into a run directory holding an unablated result".format(
                ", ".join(run_benchmark.brief.ABLATIONS)
            )
        ),
    )
    parser.add_argument(
        "--precedents",
        action="store_true",
        help=(
            "show the judge up to three earlier human closures from the "
            "precedent library, chosen because they share clauses with the case. "
            "Off by default. Results go to runs/precedents/<model>/ -- under the "
            "set's own root, so the second set's go to "
            "runs/codex/precedents/<model>/ -- and never into a run directory "
            "holding a run whose judge saw no block. Figures with precedents on "
            "are not comparable to the headline: the library is built by people "
            "who have seen these sets"
        ),
    )
    parser.add_argument(
        "--policy-version",
        type=run_benchmark.policy_version_argument,
        default=None,
        metavar="N",
        help=(
            "brief every case against policy version N: version 1 is the three "
            "policy files exactly as committed, and version N adds the "
            "amendments 0001..N-1 from policy/amendments/. Off by default "
            "(version 1), and refused outright for a set whose registration "
            "fixes its version -- wild-v2 is version 2 by registration and takes "
            "no flag. The run writes to runs/policy-v<N>/<model>/ -- under the "
            "set's own root, so the second set's go to "
            "runs/codex/policy-v<N>/<model>/ -- and never into a run directory "
            "holding a version-1 result"
        ),
    )
    parser.add_argument(
        "--amount-rule",
        choices=list(run_benchmark.pipeline.AMOUNT_RULES),
        default=run_benchmark.pipeline.DEFAULT_AMOUNT_RULE,
        metavar="RULE",
        help=(
            "which rule reads a draft's amount off the brief's money block: "
            "published (the default) accepts a published figure or the sum of two "
            "or three of them, and signed also accepts a signed combination of "
            "two or three with the leading term positive and the result above "
            "zero. Off by default -- signed is measured, not adopted. The run "
            "writes to runs/amount-rule/<rule>/<model>/ -- under the set's own "
            "root, so the second set's go to "
            "runs/codex/amount-rule/<rule>/<model>/ -- and never into a run "
            "directory holding a result judged by another rule"
        ),
    )
    parser.add_argument(
        "--verify-recorded-drafts",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help=(
            "reuse RUN_DIR's recorded judge drafts and call only the verifier, so on "
            "and off are compared on the same drafts. The set's results go to "
            "runs/<set>/verify-recorded-drafts/<model>/, never into the set's own "
            "run directory"
        ),
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="print the sets separately and combined from cached runs; makes no model call",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "for a sealed set, print what one plain invocation would run and what "
            "it would not, applying the sealed protocol to the existing "
            "events.jsonl if there is one. Runs every refusal and every "
            "frozen-argument check first, builds no client, writes nothing, "
            "creates no directory, and does not need the sealed-run opt-in"
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    model = run_benchmark.resolve_model(args.model)

    # ``--policy-version`` defaults to ``None`` rather than to version 1, so
    # "not given" is told apart from "given as version 1": a set whose
    # registration fixes its version refuses the flag outright, and a default of
    # 1 would make an explicit ``--policy-version 1`` indistinguishable from no
    # flag at all.
    explicit_policy_version = args.policy_version
    policy_version = (
        run_benchmark.DEFAULT_POLICY_VERSION
        if explicit_policy_version is None
        else explicit_policy_version
    )

    if args.ablate is not None:
        # An ablation changes what every agent is given, so it cannot be
        # combined with a mode that reads a recorded run or reports one: those
        # modes would be describing results produced without the ablation, and
        # naming the switch beside them would look as though it had been
        # applied. Refused before any of them runs, and before any call.
        for present, name in (
            (args.report, "--report"),
            (args.replay_advocates is not None, "--replay-advocates"),
            (args.replay_check is not None, "--replay-check"),
            (args.verify_recorded_drafts is not None, "--verify-recorded-drafts"),
        ):
            if present:
                print(
                    "FATAL: --ablate builds an ablated brief and takes no {0}".format(name),
                    file=sys.stderr,
                )
                return 1

    if args.precedents:
        # The same rule the ablation follows: a run that shows the judge earlier
        # closures cannot be combined with a mode that reads a run recorded
        # without them or that reports one, because each of those would look as
        # though the block had been shown when it had not. Refused before any of
        # them runs, and before any call.
        if args.ablate is not None:
            print(
                "FATAL: at most one of --ablate and --precedents may be given per "
                "invocation: each changes what the agents are given, and a run "
                "with both on measures neither",
                file=sys.stderr,
            )
            return 1
        for present, name in (
            (args.report, "--report"),
            (args.replay_advocates is not None, "--replay-advocates"),
            (args.replay_check is not None, "--replay-check"),
            (args.verify_recorded_drafts is not None, "--verify-recorded-drafts"),
        ):
            if present:
                print(
                    "FATAL: --precedents shows the judge earlier closures and "
                    "takes no {0}".format(name),
                    file=sys.stderr,
                )
                return 1

    if policy_version != run_benchmark.DEFAULT_POLICY_VERSION:
        # A later policy version changes what every agent is given, so it follows
        # the rule the ablation and the precedent block follow: it cannot be
        # combined with another switch that changes the agents' input, nor with a
        # mode that reads or reports a run produced without it. This block runs
        # after the other two, so it is the one that catches a version named
        # beside either of them as well as one named alone.
        if args.ablate is not None or args.precedents:
            print(
                "FATAL: at most one of --ablate, --precedents, "
                "--policy-version N>=2 and --amount-rule may be given per "
                "invocation: each changes what the run measures, and a run with "
                "two of them on measures neither",
                file=sys.stderr,
            )
            return 1
        for present, name in (
            (args.report, "--report"),
            (args.replay_advocates is not None, "--replay-advocates"),
            (args.replay_check is not None, "--replay-check"),
            (args.verify_recorded_drafts is not None, "--verify-recorded-drafts"),
        ):
            if present:
                print(
                    "FATAL: --policy-version N>=2 briefs every case against the "
                    "amended policy and takes no {0}".format(name),
                    file=sys.stderr,
                )
                return 1

    if args.amount_rule != run_benchmark.pipeline.DEFAULT_AMOUNT_RULE:
        # The amount rule is the fourth switch that changes what a run measures,
        # and it follows the rule the other three follow. It changes what a
        # draft's amount is held to rather than what an agent is given, so a mode
        # that reads or reports a run judged by the published rule cannot be
        # combined with it: naming the switch beside one would look as though it
        # had been applied. This block runs last, so it is the one that catches a
        # rule named beside any of the other switches as well as one alone.
        if (
            args.ablate is not None
            or args.precedents
            or policy_version != run_benchmark.DEFAULT_POLICY_VERSION
        ):
            print(
                "FATAL: at most one of --ablate, --precedents, "
                "--policy-version N>=2 and --amount-rule may be given per "
                "invocation: each changes what the run measures, and a run with "
                "two of them on measures neither",
                file=sys.stderr,
            )
            return 1
        for present, name in (
            (args.report, "--report"),
            (args.replay_check is not None, "--replay-check"),
            (args.verify_recorded_drafts is not None, "--verify-recorded-drafts"),
        ):
            if present:
                print(
                    "FATAL: --amount-rule names the rule a draft's amount is read "
                    "off the brief's money block by and takes no {0}".format(name),
                    file=sys.stderr,
                )
                return 1
        # ``--replay-advocates`` is deliberately not in that list. A replay
        # calls only the judge, and the rule is passed down the replay path like
        # every other path that judges a panel, so naming it there is a request
        # this pipeline can honour rather than one it would silently drop. The
        # other three read a run, or reuse recorded drafts, without judging
        # anything: the rule would not be applied and would look as though it
        # had been.

    if args.report:
        if args.replay_advocates is not None or args.replay_check is not None:
            print("FATAL: --report reads cached runs and takes no replay arguments", file=sys.stderr)
            return 1
        if args.verify_drafts or args.verify_recorded_drafts is not None:
            print(
                "FATAL: --report reads cached runs and takes no verification argument",
                file=sys.stderr,
            )
            return 1
        print(render_development_sets(model, args.runs_dir))
        return 0

    # "all" is the two development sets. The held-out set is deliberately not in
    # that list: it is run once, and an invocation that ran it as a side effect
    # of running everything would be a run nobody chose to make.
    selected = [named(args.set_name)] if args.set_name != "all" else list(DEVELOPMENT_SETS)

    # The run root, for a set whose registration fixes its command line. Its
    # single run has to land in the directory the six destinations read, and
    # ``--runs-dir`` is what would put it somewhere nothing reads while the
    # invocation still looked like the sealed run. It is checked **before**
    # anything that reasons about the destination, because the switch refusals
    # below compare ``args.runs_dir`` with the sealed roots: a root that is not
    # the repository's own would make them answer about the wrong tree. The
    # comparison is case-folded, because this volume is case-insensitive and
    # ``runs/`` and ``RUNS/`` are one directory here.
    #
    # A set that registers no arguments keeps the flag, as it always has: the
    # held-out set's single run is already made and committed, and the guard
    # that protects it is the sealed root's own.
    for development_set in selected:
        if development_set.run_arguments is None:
            continue
        if (
            run_benchmark.path_components(args.runs_dir)
            == run_benchmark.path_components(RUNS_DIR)
        ):
            continue
        print(
            "FATAL: --set {0} is run at the arguments its registration fixes, and "
            "--runs-dir is one of them: {1} is not the repository's own {2}, which "
            "is where its single run is read from".format(
                development_set.name, args.runs_dir, RUNS_DIR
            ),
            file=sys.stderr,
        )
        return 1

    # ``--cases`` too: the run is one command over the set's whole case list, and
    # a subset of a sealed set is a different measurement under the same name.
    # ``--check`` is not a run, but it applies every refusal before it prints its
    # plan, so this is refused for it as well.
    for development_set in selected:
        if development_set.run_arguments is None or args.cases is None:
            continue
        print(
            "FATAL: --set {0} is run as one command over all of its cases, so "
            "--cases is refused for it".format(development_set.name),
            file=sys.stderr,
        )
        return 1

    # A set whose registration fixes the policy version refuses the flag. The
    # version is part of what the set *is* -- ``wild-v2`` is version 2 by
    # registration, and briefing its cases at another version would measure a
    # set that does not exist -- so naming the flag beside it is refused rather
    # than silently ignored.
    if explicit_policy_version is not None:
        for development_set in selected:
            if development_set.policy_version != run_benchmark.DEFAULT_POLICY_VERSION:
                print(
                    "FATAL: {0} fixes policy version {1} in its registration, so "
                    "--policy-version is refused for it".format(
                        development_set.name, development_set.policy_version
                    ),
                    file=sys.stderr,
                )
                return 1

    # The four switches that move a set's run one level down under the set's own
    # root. For the held-out set every one of them would write under
    # ``runs/wild/``, which holds the single run the submission reports and is
    # never written again. Refused here as well as at the destination, so that
    # the message can name the set to use instead of it.
    for present, switch in (
        (args.ablate is not None, "--ablate"),
        (args.precedents, "--precedents"),
        (policy_version != run_benchmark.DEFAULT_POLICY_VERSION, "--policy-version"),
        (args.amount_rule != run_benchmark.pipeline.DEFAULT_AMOUNT_RULE, "--amount-rule"),
    ):
        if not present:
            continue
        for development_set in selected:
            try:
                run_benchmark.assert_not_under_the_held_out_root(
                    development_set.runs_dir(args.runs_dir),
                    args.runs_dir,
                    remedy=(
                        "{0} is the switch that moves a run one level down under "
                        "its own set's root. Name --set wild-dev instead: those "
                        "are the same 64 cases as development data, and their "
                        "runs go under runs/wild-dev/".format(switch)
                    ),
                )
            except run_benchmark.BenchmarkError as exc:
                print("FATAL: {0}".format(exc), file=sys.stderr)
                return 1

    try:
        for development_set in selected:
            for present, name in (
                # ``--force`` is named here as well as in ``run_set``, because it
                # is the one switch in this family that the run loop used to
                # refuse rather than this list: the frozen-arguments check below
                # would otherwise answer first, and "this invocation asks for a
                # different timeout" is not what a reader who typed ``--force``
                # against a sealed set needs to be told.
                (args.force, "--force"),
                (args.replay_advocates is not None, "--replay-advocates"),
                (args.replay_check is not None, "--replay-check"),
                (args.verify_recorded_drafts is not None, "--verify-recorded-drafts"),
            ):
                if present:
                    assert_not_sealed(development_set, name)
    except run_benchmark.BenchmarkError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1

    try:
        cases = run_benchmark.parse_cases(args.cases)
    except run_benchmark.BenchmarkError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1

    # A selection that names no case of any selected set runs nothing, and the
    # run loop below would then find every subset empty and report success --
    # exit 0 with no case run and nothing said. That is an error about the
    # selection, so it is refused here for every set, before a client exists.
    known = {
        case_no for development_set in selected for case_no in development_set.cases
    }
    unknown = [case_no for case_no in cases if case_no not in known]
    if unknown:
        print(
            "FATAL: --cases names case(s) {0}, which {1} does not hold".format(
                ", ".join(str(case_no) for case_no in unknown),
                " and ".join(development_set.name for development_set in selected),
            ),
            file=sys.stderr,
        )
        return 1

    if args.verify_recorded_drafts is not None:
        if args.replay_advocates is not None or args.replay_check is not None:
            print(
                "FATAL: --verify-recorded-drafts reuses recorded drafts and takes "
                "no replay arguments",
                file=sys.stderr,
            )
            return 1
        from eval import verify_drafts

        status = 0
        for development_set in selected:
            subset = [
                case_no
                for case_no in development_set.cases
                if not cases or case_no in cases
            ]
            if not subset:
                continue
            try:
                report = verify_drafts.verify_recorded_run(
                    args.verify_recorded_drafts,
                    subset,
                    model=model,
                    runs_dir=development_set.runs_dir(args.runs_dir),
                    prompts_dir=args.prompts_dir,
                    timeout_seconds=args.timeout,
                    case_loader=development_set.load_case,
                    label=development_set.name,
                )
            except run_benchmark.llm.ModelNotProvisionedError as exc:
                print("FATAL: {0}".format(exc), file=sys.stderr)
                return 1
            except run_benchmark.llm.MissingAPIKeyError as exc:
                print("FATAL: {0}".format(exc), file=sys.stderr)
                return 1
            except run_benchmark.BenchmarkError as exc:
                print("FATAL: {0}".format(exc), file=sys.stderr)
                return 1
            print("development set {0}".format(development_set.name))
            print(verify_drafts.render_report(report))
            if not report.ok:
                status = 1
        return status

    if args.replay_check is not None:
        if args.verify_drafts:
            print("FATAL: --replay-check reads a run and takes no --verify-drafts", file=sys.stderr)
            return 1
        # One check per set, because the cases of two sets are loaded by two
        # different loaders and a replay is only replayable if this code builds
        # the same brief for the case.
        status = 0
        for development_set in selected:
            subset = [case_no for case_no in development_set.cases if not cases or case_no in cases]
            if not subset:
                continue
            try:
                check = run_benchmark.check_replay(
                    args.replay_check,
                    subset,
                    model=model,
                    prompts_dir=args.prompts_dir,
                    policy_version=policy_version,
                    case_loader=development_set.load_case,
                )
            except run_benchmark.BenchmarkError as exc:
                print("FATAL: {0}".format(exc), file=sys.stderr)
                return 1
            print("development set {0}".format(development_set.name))
            print(run_benchmark.render_replay_check(check))
            if check.refused:
                status = 1
        return status

    # The arguments the run is fixed at, for a set whose registration records
    # them. A sealed set's single run is one measurement and the arguments are
    # part of what the measurement is, so an invocation that differed in one of
    # them would produce a different figure under the same name. Refused here
    # rather than in ``run_set``, because it is the *command line* that is
    # frozen: the read-only modes above judge nothing and are not runs, and a
    # caller who runs a set through ``run_set`` directly is writing a test or a
    # measurement of its own and is not claiming to be the sealed run.
    for development_set in selected:
        differences = run_argument_differences(
            development_set,
            model=model,
            prompts_dir=args.prompts_dir,
            judge_votes=args.judge_votes,
            verify_drafts=args.verify_drafts,
            timeout_seconds=args.timeout,
            concurrency=args.concurrency,
            case_deadline_seconds=args.case_deadline,
            token_budget=args.token_budget,
        )
        if differences:
            print(
                "FATAL: --set {0} is run at the arguments its registration "
                "fixes, and this invocation asks for something else: {1}".format(
                    development_set.name, "; ".join(differences)
                ),
                file=sys.stderr,
            )
            return 1

    # ``--check``: every refusal above has now been applied, so what is left is
    # the plan. It applies the sealed protocol to the run's own event log if
    # there is one, prints the cases this invocation would run and the cases it
    # would not with their reasons, and returns. It builds no client, writes
    # nothing and creates no directory, so the owner can run it as often as they
    # like before the one run.
    if args.check:
        for development_set in selected:
            if not development_set.sealed:
                continue
            subset = [
                case_no for case_no in development_set.cases if not cases or case_no in cases
            ]
            if not subset:
                continue
            would_run, not_retried, do_not_count = sealed_protocol_plan(
                development_set, subset, model, args.runs_dir
            )
            print(
                render_sealed_plan(
                    development_set, would_run, not_retried, do_not_count
                )
            )
        return 0

    # The lock on a sealed run, and the last thing before any call. A sealed set
    # is run by the owner, once, and that run is the figure the submission
    # reports; this is what makes "by the owner" true rather than intended. It
    # is checked after every refusal above, so an invocation that names a switch
    # the set refuses is told about the switch, and before ``run_set``, so no
    # client is built and no directory is created for an invocation that is not
    # the owner's.
    opt_in = os.environ.get(SEALED_RUN_ENV_VAR)
    for development_set in selected:
        if not development_set.sealed:
            continue
        subset = [
            case_no for case_no in development_set.cases if not cases or case_no in cases
        ]
        if not subset:
            continue
        if opt_in != development_set.name:
            print(
                "FATAL: {0} is a sealed set, and its single run is made by the "
                "owner only. To make it, set {1}={0} for that one command; "
                "nothing else may set it, and nothing in this repository does".format(
                    development_set.name, SEALED_RUN_ENV_VAR
                ),
                file=sys.stderr,
            )
            return 1
        # And the run must be able to call a model at all. Checked after the
        # opt-in, so an invocation that is not the owner's is still told about the
        # opt-in, and before ``run_set``, so a keyless invocation writes nothing.
        # Without a key every case would fail with a configuration error, and a
        # configuration error is not an attempt under the protocol, so the run
        # would leave the sealed root as it found it while reporting that it had
        # run -- the one outcome the sealed set cannot survive.
        if not run_benchmark.llm.load_api_key():
            print(
                "FATAL: {0} is a sealed set and no API key loads, so a run would "
                "call no model and record a configuration error for every case; "
                "nothing has been written".format(development_set.name),
                file=sys.stderr,
            )
            return 1

    summaries = []
    for development_set in selected:
        subset = [case_no for case_no in development_set.cases if not cases or case_no in cases]
        if not subset:
            continue
        try:
            summary = run_set(
                development_set,
                model,
                runs_dir=args.runs_dir,
                cases=subset,
                prompts_dir=args.prompts_dir,
                force=args.force,
                token_budget=args.token_budget,
                concurrency=args.concurrency,
                timeout_seconds=args.timeout,
                case_deadline_seconds=args.case_deadline,
                judge_votes=args.judge_votes,
                replay_dir=args.replay_advocates,
                verify_drafts=args.verify_drafts,
                ablation=args.ablate,
                precedents=(
                    run_benchmark.PRECEDENTS_STORE if args.precedents else None
                ),
                policy_version=policy_version,
                amount_rule=args.amount_rule,
            )
        except run_benchmark.llm.ModelNotProvisionedError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        except run_benchmark.llm.MissingAPIKeyError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        except run_benchmark.BenchmarkError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        run_benchmark.print_summary(summary)
        summaries.append(summary)

    if summaries:
        print("")
        print(render_development_sets(model, args.runs_dir))
    return 0 if all(summary.ok for summary in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
