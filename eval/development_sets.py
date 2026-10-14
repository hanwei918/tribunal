"""The development sets the judge prompt is measured on.

There are two of them, and they are not the same kind of thing:

* **the corpus** -- the 29 cases listed in ``data/index.json``, keyed by
  ``eval/answers/ground_truth.json``. This is the set the submission's headline
  figure is computed on, and it stays exactly 29 cases.
* **the second development set** -- fifteen cases drafted by OpenAI Codex on
  2026-09-24, copied in by the owner under ``data/external/codex/``, keyed by
  ``eval/answers/codex/ground_truth.json``. It is deliberately absent from
  ``data/index.json``, because adding it there would change the corpus.

Both are **development data**. Neither is a test set. A third kind of set is in
the repository too: the held-out set, 64 cases under ``data/external/wild/``,
keyed by ``eval/answers/wild/ground_truth.json``, and run exactly once from the
commit tagged ``freeze-2026-09-30``. **On 2026-10-12 the owner settled that this
set is development and regression data**, so that single run is history -- the
held-out run made before the set was opened for development on 2026-10-01 -- and
it is not a generalisation figure. The generalisation figures the submission
reports belong to the three sealed sets, each run exactly once. Nothing here
produces one.

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
from dataclasses import dataclass, replace
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
from tribunal import events, loader, policy_versions  # noqa: E402

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

    Only ``wild-v2`` carries one, and only because its single run is one of the
    two generalisation figures: the freeze note fixes the arguments the
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

    ``sealed`` marks a set that is run **once** and whose single run is one of
    the two generalisation figures. It is the only field a set carries because
    of what its results *mean* rather than where they live, and it is what lets
    a switch that would replace that run be refused for this set and no other.

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
    # The policy **base** a set's versions belong to, for a set written for a
    # separate base rather than for one fixed version. Where it is set, the set
    # accepts any version on that base (3, 4, 5, ...), runs at the **latest** one
    # when no version is named, and the version moves the run one level down
    # under the set's own root -- ``runs/<set>/policy-v<N>/<model>/``. Where it is
    # ``None`` the set either fixes one version (``wild-v2`` is version 2) or
    # takes whatever the command line gives, exactly as before.
    policy_base: Optional[int] = None
    run_arguments: Optional[RunArguments] = None
    # Where a set's **stated expectation** lives, for a set that has one and no
    # answer key. ``ryde-v3`` is that set: the organisers' sample carries a word
    # (``UPHELD``) that is not one of POL-GEN-03's, and the file says in its own
    # text that it is not the answer key. Such a set's run is not scored -- see
    # :meth:`key` -- and the path is carried so the result can be shown beside
    # the expectation, which is what ``eval.run_benchmark --external`` does for
    # the same case.
    stated_expectation: Optional[Path] = None

    def key(self) -> Dict[int, grade.Ruling]:
        """This set's own answer key. Never the corpus key.

        A set with a **stated expectation** has no key: the organisers' word is
        not a POL-GEN-03 ruling, and grading a case against a token it never had
        would invent one. Its key is therefore empty, and :func:`run_set` tells
        the runner the cases are unscored, which is what lets them run and be
        reported as unscored rather than refused.
        """
        if self.stated_expectation is not None:
            return {}
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
    summary=(
        "the 29-case corpus at policy version 1, run on 2026-09-27; it is a "
        "historical benchmark replay and not the product view -- 28 of the 29 "
        "cases are a judge-only replay, where the advocates' outputs were "
        "replayed from an earlier run and only the judge was called"
    ),
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
        "the held-out set (wild-v1): 64 cases whose author says its traps come "
        "from real complaints; nobody who changed the system opened them before "
        "the freeze tagged freeze-2026-09-30, and they were run once from that "
        "tag. The owner settled on 2026-10-12 that the set is development and "
        "regression data, so that single run is history and it is not a "
        "generalisation figure"
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

# The policy version the sets below are written for. Their cases carry the
# version-3 record fields, so it is part of what each set *is* rather than a
# switch on the invocation -- the same reason ``wild-v2`` fixes version 2.
VERSION_THREE = 3

# The policy version Ryde's own Dispute Resolution Policy v2.1 is published as,
# and the base the three version-7 sets below are written for. Named here rather
# than typed three times, for the reason every other version in this file is.
V7_POLICY_VERSION = 7

# They are registered with their own runs subdirectory and their own loader, and
# they are deliberately **outside** ``DEVELOPMENT_SETS``: that tuple is what
# ``--set all`` runs, what the combined figure sums and what ``ALL_SETS`` (the
# recorded-drafts measurement) reads, and these sets have no run yet. Naming one
# of them is how it is run: ``--set dev-v2``.
#
# They are development data that is tuned against, so neither is ever a sealed
# set and neither ever contributes a generalisation figure.
DEV_V2 = DevelopmentSet(
    name="dev-v2",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(loader.EXTERNAL_DIR / "dev-v2")
    ),
    key_path=ANSWER_DIR / "dev-v2" / "ground_truth.json",
    runs_subdir="dev-v2",
    case_root=loader.EXTERNAL_DIR / "dev-v2",
    summary=(
        "eighty synthetic development cases for policy version 3, generated by "
        "eval/synth/make_dev_set.py (seed 20261007): forty no-show (1701-1740) "
        "and forty route-deviation (1751-1790). Development data that is tuned "
        "against, so it is never a generalisation figure"
    ),
    policy_version=VERSION_THREE,
    policy_base=VERSION_THREE,
)

DEV_V2_EXT = DevelopmentSet(
    name="dev-v2-ext",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(loader.EXTERNAL_DIR / "dev-v2-ext")
    ),
    key_path=ANSWER_DIR / "dev-v2-ext" / "ground_truth.json",
    runs_subdir="dev-v2-ext",
    case_root=loader.EXTERNAL_DIR / "dev-v2-ext",
    summary=(
        "a hundred and twenty variants of the dev-v2 scenarios, for policy "
        "version 3: 2701-2760 and 2801-2860, made by moving the parameters the "
        "eighty cases turn on. Development data, never a generalisation figure"
    ),
    policy_version=VERSION_THREE,
    policy_base=VERSION_THREE,
)

# The organisers' sample converted for policy version 3, as a one-case
# development set. It exists because ``eval.run_benchmark`` refuses
# ``--external`` together with ``--policy-version N>=2``, so before this
# registration case 901 could not be run at version 3 at all -- and that refusal
# is deliberate and stays. Its expectation is the organisers' own stated
# outcome, which is not a POL-GEN-03 token and is not an answer key, so its run
# is not scored: see :meth:`DevelopmentSet.key`.
RYDE_V3 = DevelopmentSet(
    name="ryde-v3",
    cases=(901,),
    key_path=run_benchmark.EXTERNAL_EXPECTED_PATH,
    runs_subdir="ryde-v3",
    case_root=loader.EXTERNAL_DIR / "ryde-v3",
    summary=(
        "the organisers' sample case, converted for policy version 3 by "
        "eval/external/ryde/convert.py --policy-version 3. Its stated "
        "expectation is eval/external/ryde/expected.json, which is not an answer "
        "key; the run is not scored"
    ),
    policy_version=VERSION_THREE,
    policy_base=VERSION_THREE,
    stated_expectation=run_benchmark.EXTERNAL_EXPECTED_PATH,
)

# The sets written for policy version 3, and their names.
VERSION_THREE_SETS: Tuple[DevelopmentSet, ...] = (DEV_V2, DEV_V2_EXT, RYDE_V3)
VERSION_THREE_SET_NAMES = tuple(
    development_set.name for development_set in VERSION_THREE_SETS
)

# The four functional sets, imported on 2026-10-10: three case sets and the
# chat-signals fixture. They are **not** a fifth development set and not a
# sealed one: they exist to exercise one functional property each -- injection
# resistance, personal-data masking, cross-case collusion -- beside the
# chat-message labels the ops layer routes on. They are registered exactly as
# ``dev-v2-ext`` is: written for policy base 3, so they accept any version on
# that base and run at the **latest** one -- today 6 -- when no version is
# named, which is why their runs go to ``runs/<set>/policy-v6/<model>/`` rather
# than to a plain ``runs/<set>/<model>/``. They are deliberately **outside**
# ``DEVELOPMENT_SETS``: that tuple is what ``--set all`` runs and what the
# combined figure sums, and these sets are development data that is tuned
# against, so neither is ever a generalisation figure. Naming one is how it is
# run: ``--set inject-v1``.
#
# ``chat-signals-v1`` is not registered here at all. It is not a case set: it is
# a fixture of 32 labelled chat messages under ``eval/fixtures/``, and the
# checks over it need no case, no key and no run.
INJECT_V1 = DevelopmentSet(
    name="inject-v1",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(loader.EXTERNAL_DIR / "inject-v1")
    ),
    key_path=ANSWER_DIR / "inject-v1" / "ground_truth.json",
    runs_subdir="inject-v1",
    case_root=loader.EXTERNAL_DIR / "inject-v1",
    summary=(
        "twelve cases in six invariance pairs for policy version 6: 3101-3106 "
        "clean and 3107-3112 the same trips with one adversarial instruction "
        "added to party text, made by eval/synth/make_func_sets.py (seed "
        "20261009). Development data that is tuned against, so it is never a "
        "generalisation figure"
    ),
    policy_version=VERSION_THREE,
    policy_base=VERSION_THREE,
)

PII_V1 = DevelopmentSet(
    name="pii-v1",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(loader.EXTERNAL_DIR / "pii-v1")
    ),
    key_path=ANSWER_DIR / "pii-v1" / "ground_truth.json",
    runs_subdir="pii-v1",
    case_root=loader.EXTERNAL_DIR / "pii-v1",
    summary=(
        "eight cases for policy version 6 whose party text carries personal "
        "names, telephone numbers, e-mail addresses and vehicle plates, with "
        "place names containing surnames as hard negatives (3201-3208), made by "
        "eval/synth/make_func_sets.py (seed 20261009). Development data, never a "
        "generalisation figure"
    ),
    policy_version=VERSION_THREE,
    policy_base=VERSION_THREE,
)

COLLUSION_V1 = DevelopmentSet(
    name="collusion-v1",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(loader.EXTERNAL_DIR / "collusion-v1")
    ),
    key_path=ANSWER_DIR / "collusion-v1" / "ground_truth.json",
    runs_subdir="collusion-v1",
    case_root=loader.EXTERNAL_DIR / "collusion-v1",
    summary=(
        "eight cases for policy version 6 read together as one case root "
        "(3301-3308): a repeated pair, a farming driver and its control, a rider "
        "abuse flag and its lifetime-counter decoy, and a pattern driver, made "
        "by eval/synth/make_func_sets.py (seed 20261009). Development data, "
        "never a generalisation figure"
    ),
    policy_version=VERSION_THREE,
    policy_base=VERSION_THREE,
)

# The three case sets of the functional family, and their names. They are
# registered beside the version-3 sets and share their version behaviour; the
# fourth functional set, ``chat-signals-v1``, is a fixture rather than a set of
# cases and is deliberately absent.
FUNCTIONAL_SETS: Tuple[DevelopmentSet, ...] = (INJECT_V1, PII_V1, COLLUSION_V1)
FUNCTIONAL_SET_NAMES = tuple(
    development_set.name for development_set in FUNCTIONAL_SETS
)

# --------------------------------------------------------------------------
# The version-7 sets
# --------------------------------------------------------------------------
# Policy version 7 is Ryde's own Dispute Resolution Policy v2.1, a separate base
# whose clause ids start at 21 (see ``policy/v7/``). The organisers' two samples
# are converted into it at ``data/external/ryde-v7/`` by
# ``eval/external/ryde/convert.py --policy-version 7``: DISP-001, the
# route-deviation sample, as case 902, and DISP-002, the no-show sample, as case
# 903.
#
# It is registered exactly as ``ryde-v3`` is -- a development set that is tuned
# against, never a generalisation figure -- and it carries ``policy_base=7`` and
# ``policy_version=7`` for the same reason ``dev-v2`` carries version 3: the
# cases are written for that base, so the set accepts any version on it and runs
# at the latest one when no version is named. It is outside ``DEVELOPMENT_SETS``
# (what ``--set all`` runs and the combined figure sums) and outside ``ALL_SETS``
# (what the recorded-drafts measurement reads).
RYDE_V7 = DevelopmentSet(
    name="ryde-v7",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(loader.EXTERNAL_DIR / "ryde-v7")
    ),
    key_path=ANSWER_DIR / "ryde-v7" / "ground_truth.json",
    runs_subdir="ryde-v7",
    case_root=loader.EXTERNAL_DIR / "ryde-v7",
    summary=(
        "the organisers' two samples converted for policy version 7 by "
        "eval/external/ryde/convert.py --policy-version 7: DISP-001 as case 902 "
        "(a route deviation) and DISP-002 as case 903 (a no-show). Ryde's own "
        "stated outcomes are the set's key. Development data that is tuned "
        "against, so it is never a generalisation figure"
    ),
    policy_version=V7_POLICY_VERSION,
    policy_base=V7_POLICY_VERSION,
)

# The two version-7 sets, **declared here and registered only when their data is
# present**. A set with no case files has no case numbers to list and no index to
# read, so registering one before its data arrives would be a registration that
# fails at import; and an empty directory would be a set that runs nothing while
# looking as though it ran. So the two constants are written here, in the shape
# they are registered in, and the tuples below take them the moment
# ``data/external/<name>/index.json`` exists -- which both did on 2026-10-13,
# when part 73 imported them.
#
# Their run arguments are sealed-v2's, which is the configuration of every
# sealed run since 2026-10-03, and their prompts directory is ``prompts/v2``,
# which is the version-7 prompt set -- ``eval.run_benchmark`` refuses a version-7
# run with any other.
V7_RUN_ARGUMENTS = RunArguments(
    model=RUNTIME_MODEL,
    judge_votes=4,
    verify_drafts=False,
    timeout_seconds=900.0,
    concurrency=2,
    prompts_dir=Path("prompts/v2"),
)

DEV_V7 = DevelopmentSet(
    name="dev-v7",
    cases=(),
    # The set's whole archive-B tree was extracted into ``eval/answers/dev-v7/``
    # byte for byte, so its ``answers/``, ``generator/`` and ``notes/`` folders
    # sit under that root and the key is one level down from it.
    key_path=ANSWER_DIR / "dev-v7" / "answers" / "ground_truth.json",
    runs_subdir="dev-v7",
    case_root=loader.EXTERNAL_DIR / "dev-v7",
    summary=(
        "the version-7 development set: 40 cases, 5001-5020 and 5051-5070, "
        "written for Ryde's Dispute Resolution Policy v2.1 by Claude (Opus 5.5) "
        "in a fresh claude.ai chat with no project folder or repository access. "
        "Declared here and registered when its data is present; development data "
        "that is tuned against, so it is never a generalisation figure"
    ),
    policy_version=V7_POLICY_VERSION,
    policy_base=V7_POLICY_VERSION,
    run_arguments=V7_RUN_ARGUMENTS,
)

SEALED_V4 = DevelopmentSet(
    name="sealed-v4",
    cases=(),
    # The set's whole archive-B tree was extracted into ``eval/answers/sealed-v4/``
    # byte for byte and never opened, so its ``answers/``, ``generator/`` and
    # ``notes/`` folders sit under that root and the key is one level down from it.
    key_path=ANSWER_DIR / "sealed-v4" / "answers" / "ground_truth.json",
    runs_subdir="sealed-v4",
    case_root=loader.EXTERNAL_DIR / "sealed-v4",
    summary=(
        "the sixth sealed set (sealed-v4): 30 cases made by Claude (Opus 5.5) in "
        "a fresh claude.ai chat with no project folder or repository access, from "
        "the owner's prompt, Ryde's Dispute Resolution Policy v2.1, the version-7 "
        "policy files, the public contract, a format checker and the organisers' "
        "public sample case; no human reviewed its answers; nobody on the "
        "development side has seen them; it is run once, at policy version 7; its "
        "run was made once on 2026-10-14 from the commit 8157af8, the commit the "
        "annotated tag freeze-2026-10-14 points at"
    ),
    sealed=True,
    policy_version=V7_POLICY_VERSION,
    run_arguments=V7_RUN_ARGUMENTS,
)

# Policy version 8 is version 7 with Ryde's answers of 2026-10-14 applied (see
# ``policy/v8/``): the 2 km limb of v2.1 6.2 applies, so a route deviation over
# 2 km is escalated, and the no-show free wait runs from the driver's arrival.
#
# The two version-8 sets are **the version-7 sets briefed at version 8**, not new
# case files: there is no ``data/external/dev-v8/`` or ``data/external/ryde-v8/``,
# and each set's ``case_root`` is the version-7 directory its 40 or 2 case files
# already live in. Only the key moves, because only the expected outcomes move.
# They are declared and registered exactly where the version-7 pair is, and like
# it they are development data that is tuned against, so no figure from them is
# ever a generalisation figure.
V8_POLICY_VERSION = 8

# The same configuration the version-7 runs are made with -- the same model,
# votes, timeout, concurrency and ``prompts/v2`` -- because a version-8 run is a
# version-7 run against a later policy on the same base.
V8_RUN_ARGUMENTS = V7_RUN_ARGUMENTS

DEV_V8 = DevelopmentSet(
    name="dev-v8",
    cases=(),
    key_path=ANSWER_DIR / "dev-v8" / "ground_truth.json",
    runs_subdir="dev-v8",
    # The same 40 case files ``dev-v7`` lists: 5001-5020 and 5051-5070.
    case_root=loader.EXTERNAL_DIR / "dev-v7",
    summary=(
        "the dev-v7 cases at policy version 8: 40 cases, 5001-5020 and "
        "5051-5070, written for Ryde's Dispute Resolution Policy v2.1 and "
        "briefed against version 8, which is version 7 with Ryde's answers of "
        "2026-10-14 applied. Development data that is tuned against, so it is "
        "never a generalisation figure"
    ),
    policy_version=V8_POLICY_VERSION,
    policy_base=V8_POLICY_VERSION,
    run_arguments=V8_RUN_ARGUMENTS,
)

RYDE_V8 = DevelopmentSet(
    name="ryde-v8",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(loader.EXTERNAL_DIR / "ryde-v7")
    ),
    key_path=ANSWER_DIR / "ryde-v8" / "ground_truth.json",
    runs_subdir="ryde-v8",
    case_root=loader.EXTERNAL_DIR / "ryde-v7",
    summary=(
        "the organisers' two samples at policy version 8: DISP-001 as case 902 "
        "(a route deviation) and DISP-002 as case 903 (a no-show). Keyed by "
        "Ryde's stated outcomes as amended by Ryde's answer of 2026-10-14. "
        "Development data that is tuned against, so it is never a "
        "generalisation figure"
    ),
    policy_version=V8_POLICY_VERSION,
    policy_base=V8_POLICY_VERSION,
)


def external_set_data_present(development_set: DevelopmentSet) -> bool:
    """Whether a declared set's own data is on disk yet.

    Read off the set's ``case_root`` -- the directory its case files and its index
    sit in -- rather than ``EXTERNAL_DIR / name``, because a later policy version
    of a set **reuses the earlier version's case files**: ``dev-v8`` and
    ``ryde-v8`` are the version-7 cases briefed at version 8, so their root is
    ``data/external/dev-v7`` and ``data/external/ryde-v7`` and there is no
    directory named after them at all. For every set registered before those two
    the two paths are the same one, so nothing about them moves.

    The index rather than the directory, because a directory with no index is a
    set that cannot be loaded and not one that can.
    """
    if development_set.case_root is None:
        return False
    return (development_set.case_root / loader.EXTERNAL_INDEX_FILE).is_file()


def registered(development_set: DevelopmentSet) -> DevelopmentSet:
    """A declared set with the case numbers its index lists.

    Returns the set unchanged when its data is not present, so the two tuples
    below can be written as one expression each and the declaration above stays
    the single place a set's name, root, key and arguments are written down.

    The index it reads is the one at the set's own ``case_root``, which is what
    lets a later policy version of a set be registered without a second copy of
    its case files: ``dev-v8`` reads ``data/external/dev-v7/index.json`` and lists
    the same 40 cases ``dev-v7`` does.
    """
    if not external_set_data_present(development_set):
        return development_set
    return replace(
        development_set,
        cases=tuple(
            entry["case_no"]
            for entry in loader.load_external_index(development_set.case_root)
        ),
    )


# The sets that are run by name and are in none of the tuples above: ``--set
# all`` does not run them, the combined figure does not sum them, and the
# recorded-drafts measurement does not read them.
NAMED_SETS: Tuple[DevelopmentSet, ...] = (
    VERSION_THREE_SETS + FUNCTIONAL_SETS + (RYDE_V7, RYDE_V8)
) + ((registered(DEV_V7),) if external_set_data_present(DEV_V7) else ()) + (
    (registered(DEV_V8),) if external_set_data_present(DEV_V8) else ()
)

# The second sealed set, imported on 2026-10-03 and run once, on 2026-10-04, from
# a commit whose ``tribunal/``, ``prompts/`` and ``policy/`` trees equal those at
# the tag ``freeze-2026-10-03`` -- which need not be the tagged commit itself,
# and every event the run writes records the commit it was made from. It is the
# same kind of thing as the held-out set -- keyed by its own file, run once, and
# reported on its own -- and it is **not** the held-out set: 20 cases over a
# range of its own, and its single run is never added to ``wild``'s, to the
# combined figure or to ``--set all``. Its provenance differs from the held-out
# set's: it was prepared by OpenAI Codex for the owner, and whether Codex could
# read this repository while preparing it is not recorded.
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
        "the owner and imported on 2026-10-03; it was run once from a commit "
        "whose tribunal/, prompts/ and policy/ trees equal those at "
        "freeze-2026-10-03, at the policy version 2 this registration fixes, and "
        "that single run is one of the three sealed generalisation figures the "
        "submission reports"
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

# The third sealed set, imported on 2026-10-09 and run once, on 2026-10-10. Its
# 24 cases are 301-312 and 401-412; its own manifest records that it was prepared
# by "Claude (independent of prompt tuning; never saw dev-set misses or
# prompts)". Its registration fixes policy version 6, the version frozen at the
# tag ``freeze-2026-10-09``, and its single run was made from the commit
# ``feb7174``, whose ``tribunal/``, ``prompts/`` and ``policy/`` trees equal those
# at that tag, at the arguments recorded below -- the configuration of the two
# earlier sealed runs. It is a different set from ``wild`` and ``wild-v2`` and is
# never added to either, to the combined figure or to ``--set all``.
#
# The key in this archive was written under policy version 1 and was re-derived
# under version 6 by the key owner before the run; the registration reads the
# key's digest from the key file rather than pinning it here, so that replacement
# touched only ``eval/answers/sealed-v1/``.
SEALED_V1 = DevelopmentSet(
    name="sealed-v1",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(
            loader.EXTERNAL_DIR / run_benchmark.SEALED_V1_SET_RUNS_SUBDIR
        )
    ),
    key_path=ANSWER_DIR / run_benchmark.SEALED_V1_SET_RUNS_SUBDIR / "ground_truth.json",
    runs_subdir=run_benchmark.SEALED_V1_SET_RUNS_SUBDIR,
    case_root=loader.EXTERNAL_DIR / run_benchmark.SEALED_V1_SET_RUNS_SUBDIR,
    summary=(
        "the third sealed set (sealed-v1): 24 cases prepared by Claude, "
        "independent of prompt tuning, and opened by the policy owner's assistant "
        "before the freeze (see README), and imported on 2026-10-09; it is run "
        "once, plainly, from a "
        "commit whose tribunal/, prompts/ and policy/ trees equal those at "
        "freeze-2026-10-09, at the policy version 6 this registration fixes, and "
        "that single run is the submission's third generalisation figure"
    ),
    sealed=True,
    policy_version=6,
    run_arguments=RunArguments(
        model=RUNTIME_MODEL,
        judge_votes=4,
        verify_drafts=False,
        timeout_seconds=900.0,
        concurrency=2,
    ),
)

# The fourth sealed set, imported on 2026-10-11 and run once, on 2026-10-11. Its
# 12 cases are 801-806 and 851-856; it was made by the policy owner with OpenAI
# Codex (model stated by her as GPT-6; not recorded by the tool) from a written
# brief, the version-6 policy text and the public contract, with
# no repository code, prompts or run results, and nobody on the development side
# has seen its answers. Its registration fixes policy version 6, the version
# frozen at the tag ``freeze-2026-10-11``, and its single run was made from the
# commit ``19c7e5a``, whose ``tribunal/``, ``prompts/`` and ``policy/`` trees
# equal those at that tag, at the arguments recorded below -- the configuration
# of the three earlier sealed runs. It is a different set from ``wild``,
# ``wild-v2`` and ``sealed-v1`` and is never added to any of them, to the
# combined figure or to ``--set all``.
SEALED_V2 = DevelopmentSet(
    name="sealed-v2",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(
            loader.EXTERNAL_DIR / run_benchmark.SEALED_V2_SET_RUNS_SUBDIR
        )
    ),
    key_path=ANSWER_DIR / run_benchmark.SEALED_V2_SET_RUNS_SUBDIR / "ground_truth.json",
    runs_subdir=run_benchmark.SEALED_V2_SET_RUNS_SUBDIR,
    case_root=loader.EXTERNAL_DIR / run_benchmark.SEALED_V2_SET_RUNS_SUBDIR,
    summary=(
        "the fourth sealed set (sealed-v2): 12 cases made by the policy owner "
        "with OpenAI Codex (model stated by her as GPT-6; not recorded by the "
        "tool) from a written brief, the version-6 policy text and the "
        "public contract, with no repository code, prompts or run results; "
        "nobody on the development side has seen its answers; it is run once, "
        "from a commit whose tribunal/, prompts/ and policy/ trees equal those "
        "at freeze-2026-10-11, at policy version 6"
    ),
    sealed=True,
    policy_version=6,
    run_arguments=RunArguments(
        model=RUNTIME_MODEL,
        judge_votes=4,
        verify_drafts=False,
        timeout_seconds=900.0,
        concurrency=2,
    ),
)

# The fifth sealed set, imported on 2026-10-13. Its 30 cases are 4001-4015 and
# 4051-4065; it was made by Claude (Opus 5.5) in a fresh Claude Code session with
# no project folder or repository access, from the owner's prompt, the version-6
# policy text, the public contract, a format checker and the organisers' public
# sample case, and nobody on the development side has seen its answers. Its
# registration fixes policy version 6, the version frozen at the tag
# ``freeze-2026-10-11``, and its single run was started once on 2026-10-13 from
# the commit ``9b70387``, whose ``tribunal/``, ``prompts/`` and ``policy/`` trees
# equal those at that tag, at the arguments recorded below -- the configuration of
# the four earlier sealed runs -- and was stopped after 8 of its 30 cases. It is
# not a sealed figure and is never run again. It is a different set from
# ``wild``, ``wild-v2``, ``sealed-v1`` and ``sealed-v2`` and is never added to any
# of them, to the combined figure or to ``--set all``.
SEALED_V3 = DevelopmentSet(
    name="sealed-v3",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(
            loader.EXTERNAL_DIR / run_benchmark.SEALED_V3_SET_RUNS_SUBDIR
        )
    ),
    key_path=ANSWER_DIR / run_benchmark.SEALED_V3_SET_RUNS_SUBDIR / "ground_truth.json",
    runs_subdir=run_benchmark.SEALED_V3_SET_RUNS_SUBDIR,
    case_root=loader.EXTERNAL_DIR / run_benchmark.SEALED_V3_SET_RUNS_SUBDIR,
    summary=(
        "the fifth sealed set (sealed-v3): 30 cases made by Claude (Opus 5.5) in a "
        "fresh Claude Code session with no project folder or repository access, "
        "from the owner's prompt, the version-6 policy text, the public contract, a "
        "format checker and the organisers' public sample case; no human reviewed "
        "its answers; nobody on the development side has seen them; it is run once, "
        "from a commit whose tribunal/, prompts/ and policy/ trees equal those at "
        "freeze-2026-10-11, at policy version 6; its run was started once on "
        "2026-10-13 and stopped after 8 of its 30 cases (a network drop, then the "
        "switch to Ryde's policy v2.1); it is not a sealed figure and is never run "
        "again"
    ),
    sealed=True,
    policy_version=6,
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
SEALED_SETS: Tuple[DevelopmentSet, ...] = (
    SEALED_SET,
    WILD_V2,
    SEALED_V1,
    SEALED_V2,
    SEALED_V3,
) + ((registered(SEALED_V4),) if external_set_data_present(SEALED_V4) else ())

# The sets that exist to be run again. They are registered by name and are
# deliberately outside the tuples above: ``--set all``, the combined figure
# and the recorded-drafts measurement each read one of those, and a set whose
# cases are development data must not enter any of them by being named here.
RERUN_SETS: Tuple[DevelopmentSet, ...] = (WILD_DEV,)

# The sets whose **recorded runs** the measurements read. ``wild-v2``,
# ``sealed-v1`` and ``sealed-v2`` are deliberately not among them, and the reason
# is not that they have no run: their single runs were committed, on 2026-10-04,
# 2026-10-10 and 2026-10-11, and they have drafts, brief digests and amounts to
# re-reduce. They are excluded because the amount-rule measurement and the
# recorded-drafts measurement have committed results over these three runs, and
# adding a fourth would change figures the submission reports -- which is a
# decision about measurement coverage, and not one a registration should settle
# by being edited.
ALL_SETS: Tuple[DevelopmentSet, ...] = DEVELOPMENT_SETS + (SEALED_SET,)

BY_NAME = {
    development_set.name: development_set
    for development_set in DEVELOPMENT_SETS + SEALED_SETS + RERUN_SETS + NAMED_SETS
}


# The sets that are declared above and are **not** registered, by name. A set
# with no case files is not one this layer can run, and naming one is told that
# rather than told it does not exist: "its data is not there yet" and "there is
# no such set" are different answers, and only one of them is true.
DECLARED_SETS: Dict[str, DevelopmentSet] = {
    development_set.name: development_set
    for development_set in (DEV_V7, SEALED_V4)
    if not external_set_data_present(development_set)
}


def render_declared_set(development_set: DevelopmentSet) -> str:
    """What a set that is declared but not registered is told.

    One sentence per thing a reader needs: which set, where its data would be,
    and that nothing is created for it -- because the failure this message
    replaces is a run that creates an empty directory and reports a set with no
    cases in it.
    """
    root = loader.EXTERNAL_DIR / development_set.name
    return (
        "FATAL: {0} is declared but not registered: {1} does not exist, so there "
        "is no case to list, no plan to print and nothing to run. It is "
        "registered when that file arrives, and nothing is created for it "
        "before then.".format(development_set.name, root / loader.EXTERNAL_INDEX_FILE)
    )


def named(name: str) -> DevelopmentSet:
    """One set by name. An unknown name raises rather than defaulting."""
    try:
        return BY_NAME[name]
    except KeyError:
        waiting = DECLARED_SETS.get(name)
        if waiting is not None:
            raise run_benchmark.BenchmarkError(
                "{0} is declared but not registered: {1} does not exist, so "
                "there is no case to list and no plan to print. It is registered "
                "when its own index.json arrives".format(
                    name, loader.EXTERNAL_DIR / name / loader.EXTERNAL_INDEX_FILE
                )
            ) from None
        raise run_benchmark.BenchmarkError(
            "unknown development set {0!r}; known sets: {1}".format(
                name, ", ".join(sorted(BY_NAME))
            )
        ) from None


def resolved_policy_version(
    development_set: DevelopmentSet, named: Optional[int]
) -> int:
    """The policy version one set's invocation briefs at.

    ``named`` is the version the **command line** carries: version 1, the
    default, when it named none -- or ``None`` for a caller that gave none at
    all. Both mean "not named", so both are treated the same, and that is why
    this takes the command line's version rather than an "explicit or None" flag:
    the layer that replaces it is the one that knows the registration.

    Three cases, and they are the three a registration can be in:

    * a set written for a **base** (``dev-v2`` and its two siblings) accepts any
      version on that base; with no version named it runs at the base's
      **latest**, which today is 6;
    * a set that **fixes** one version (``wild-v2`` is version 2) briefs at it
      whatever the invocation says, because the version is part of what the set
      is;
    * every other set takes the version the command line gives, and version 1
      when it gives none -- the behaviour the corpus has always had.
    """
    if named is None:
        named = run_benchmark.DEFAULT_POLICY_VERSION
    if development_set.policy_base is not None:
        if named == run_benchmark.DEFAULT_POLICY_VERSION:
            return policy_versions.version_on_base(development_set.policy_base)
        return named
    if development_set.policy_version != run_benchmark.DEFAULT_POLICY_VERSION:
        return development_set.policy_version
    return named


def version_moves_the_run(
    development_set: DevelopmentSet, named: Optional[int]
) -> bool:
    """Whether this set's version moves its run one level down under its root.

    A set written for a base moves its run at any version above 1, so
    ``--set dev-v2`` with no flag is a versioned run at
    ``runs/dev-v2/policy-v6/<model>/``. A set that **fixes** its version keeps
    the set's own directory -- ``wild-v2`` runs into ``runs/wild-v2/<model>/``
    and never into a ``policy-v2`` directory inside it. Every other set moves its
    run only when a version above 1 was named.
    """
    if resolved_policy_version(development_set, named) == (
        run_benchmark.DEFAULT_POLICY_VERSION
    ):
        return False
    if development_set.policy_base is not None:
        return True
    return development_set.policy_version == run_benchmark.DEFAULT_POLICY_VERSION


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
    "five sealed sets, each run exactly once: "
    "the second sealed set's, prepared by OpenAI Codex -- whether Codex could "
    "read this repository while preparing it is not recorded -- from a commit "
    "whose tribunal/, prompts/ and policy/ trees equal those at "
    "freeze-2026-10-03; the third sealed set's, prepared by Claude, "
    "independent of prompt tuning, and opened by the policy owner's assistant "
    "before the freeze (see README), and imported on 2026-10-09, from a commit "
    "whose tribunal/, prompts/ and policy/ trees equal those at freeze-2026-10-09; "
    "the fourth sealed set's, made by the policy owner with OpenAI Codex "
    "(model stated by her as GPT-6; not recorded by the tool) from a "
    "written brief, the version-6 policy text and the public contract, with no "
    "repository code, prompts or run results, and imported on 2026-10-11, from a "
    "commit whose tribunal/, prompts/ and policy/ trees equal those at "
    "freeze-2026-10-11; "
    "and the fifth sealed set's, made by Claude (Opus 5.5) in a fresh Claude Code "
    "session with no project folder or repository access, from the owner's "
    "prompt, the version-6 policy text, the public contract, a format checker and "
    "the organisers' public sample case, and imported on 2026-10-13, from a "
    "commit whose tribunal/, prompts/ and policy/ trees equal those at "
    "freeze-2026-10-11; "
    "and the sixth sealed set's, made by Claude (Opus 5.5) in a fresh claude.ai "
    "chat with no project folder or repository access, from the owner's prompt, "
    "Ryde's Dispute Resolution Policy v2.1, the version-7 policy files, the "
    "public contract, a format checker and the organisers' public sample case, "
    "and imported on 2026-10-13, at policy version 7. "
    "The held-out set is not one of them: the owner settled on 2026-10-12 that it "
    "is development and regression data, so its single run, from the commit "
    "tagged freeze-2026-09-30, is history. "
    "Neither figure here is any of them, and no two of the five are "
    "ever added to each other."
)

# The held-out set is printed on its own, and this is why. Its single run is
# history rather than a generalisation figure -- the owner settled on 2026-10-12
# that the set is development and regression data -- and a figure over a set the
# system has since been developed against must not be read as one it has not; a
# run is also reported as ``not run`` rather than as zero where it is absent.
SEALED_SET_CAVEAT = (
    "The held-out set is never added to the "
    "combined figure above. Its 64 cases were drafted without access to this "
    "repository and were run exactly once from the commit tagged "
    "freeze-2026-09-30; the owner settled on 2026-10-12 that the set is "
    "development and regression data, so that single run is history -- the "
    "held-out run made before the set was opened for development on 2026-10-01 "
    "-- and it is not a generalisation figure. It "
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
    "OpenAI Codex for the owner and imported on 2026-10-03, and it was run "
    "exactly once, on 2026-10-04, from a commit whose tribunal/, prompts/ and "
    "policy/ trees equal those at freeze-2026-10-03 -- every event the run "
    "wrote records the commit it was made from -- at the policy version 2 its "
    "registration fixes; that single run is one of the three sealed figures the "
    "submission reports. It is absent from data/index.json and is "
    "graded against eval/answers/wild-v2/ground_truth.json, which is neither "
    "development key and not the held-out set's key either."
)

# The third sealed set is printed on its own for the same reasons and with one
# of its own: its registration fixes policy version 6, so its figure is a
# measurement of version 6 and of nothing else.
SEALED_V1_CAVEAT = (
    "The third sealed set is not a development set and is never added to the "
    "combined figure above, to the held-out set's figure or to the second "
    "sealed set's. It was prepared by Claude, independent of prompt tuning, and "
    "opened by the policy owner's assistant before the freeze (see README); it "
    "was imported on "
    "2026-10-09, and it was run exactly once, on 2026-10-10, from the commit "
    "feb7174, whose tribunal/, prompts/ and policy/ trees equal those at "
    "freeze-2026-10-09 -- every event the run wrote records the commit it was "
    "made from -- at the policy version 6 its registration fixes; that single "
    "run is the third generalisation figure the submission reports. It is absent "
    "from data/index.json and is graded against "
    "eval/answers/sealed-v1/ground_truth.json, which is neither development key "
    "and not either other sealed set's key."
)

# The fourth sealed set is printed on its own for the same reasons and with the
# same one of its own: its registration fixes policy version 6, so its figure is
# a measurement of version 6 and of nothing else.
SEALED_V2_CAVEAT = (
    "The fourth sealed set is not a development set and is never added to the "
    "combined figure above, to the held-out set's figure, to the second sealed "
    "set's or to the third's. It was made by the policy owner with OpenAI Codex "
    "(model stated by her as GPT-6; not recorded by the tool) from a "
    "written brief, the version-6 policy text and the public contract, with no "
    "repository code, prompts or run results, and nobody on the development side "
    "has seen its answers; it was imported on "
    "2026-10-11, and it was run exactly once, on 2026-10-11, from the commit "
    "19c7e5a, whose tribunal/, prompts/ and policy/ trees equal those at "
    "freeze-2026-10-11 -- every event the run wrote records the commit it was "
    "made from -- at the policy version 6 its registration fixes; that single "
    "run is the fourth generalisation figure the submission reports. It is absent "
    "from data/index.json and is graded against "
    "eval/answers/sealed-v2/ground_truth.json, which is neither development key "
    "and not either other sealed set's key."
)

# The fifth sealed set is printed on its own for the same reasons and with the
# same one of its own: its registration fixes policy version 6, so its figure is
# a measurement of version 6 and of nothing else.
SEALED_V3_CAVEAT = (
    "The fifth sealed set is not a development set and is never added to the "
    "combined figure above, to the held-out set's figure, to the second sealed "
    "set's, to the third's or to the fourth's. It was made by Claude (Opus 5.5) "
    "in a fresh Claude Code session with no project folder or repository access, "
    "from the owner's prompt, the version-6 policy text, the public contract, a "
    "format checker and the organisers' public sample case, and nobody on the "
    "development side has seen its answers; it was imported on "
    "2026-10-13, and its single run is made from a commit whose tribunal/, "
    "prompts/ and policy/ trees equal those at freeze-2026-10-11 -- every event "
    "the run writes records the commit it was made from -- at the policy "
    "version 6 its registration fixes; that single run is the fifth "
    "generalisation figure the submission reports. It is absent from "
    "data/index.json and is graded against "
    "eval/answers/sealed-v3/ground_truth.json, which is neither development key "
    "and not either other sealed set's key."
)

# The sixth sealed set is printed on its own for the same reasons and with the
# same one of its own: its registration fixes policy version 7, so its figure is
# a measurement of version 7 and of nothing else.
SEALED_V4_CAVEAT = (
    "The sixth sealed set is not a development set and is never added to the "
    "combined figure above, to the held-out set's figure, to the second sealed "
    "set's, to the third's, to the fourth's or to the fifth's. It was made by "
    "Claude (Opus 5.5) in a fresh claude.ai chat with no project folder or "
    "repository access, from the owner's prompt, Ryde's Dispute Resolution "
    "Policy v2.1, the version-7 policy files, the public contract, a format "
    "checker and the organisers' public sample case, and nobody on the "
    "development side has seen its answers; it was imported on 2026-10-13, and "
    "its single run is made at the policy version 7 its registration fixes; that "
    "single run is the sixth generalisation figure the submission reports. It is "
    "absent from data/index.json and is graded against "
    "eval/answers/sealed-v4/answers/ground_truth.json, which is neither "
    "development key and not either other sealed set's key."
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
    SEALED_V1.name: (
        "The third sealed set (sealed-v1), on its own and never in the combined "
        "figure:",
        SEALED_V1_CAVEAT,
    ),
    SEALED_V2.name: (
        "The fourth sealed set (sealed-v2), on its own and never in the combined "
        "figure:",
        SEALED_V2_CAVEAT,
    ),
    SEALED_V3.name: (
        "The fifth sealed set (sealed-v3), on its own and never in the combined "
        "figure:",
        SEALED_V3_CAVEAT,
    ),
    SEALED_V4.name: (
        "The sixth sealed set (sealed-v4), on its own and never in the combined "
        "figure:",
        SEALED_V4_CAVEAT,
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


def sealed_root_is_closed(development_set: DevelopmentSet) -> bool:
    """Whether a sealed set's root is closed outright.

    A sealed root is closed once its single run has been made: nothing is
    created under it again, the plain run included. **The fact is the root's
    registration, not a file under it.** The question is asked of
    ``run_benchmark.MADE_SEALED_RUNS_SUBDIRS`` -- the one list that says which
    sealed runs have been made -- and not of one model's ``run.json``, because a
    run made under another model is the same root and closes it just as much:
    ``--set wild --model <anything> --check`` is looking at a root whose single
    run is committed, and asking a file named after the model would have printed
    a plan for an invocation that cannot happen.
    """
    return development_set.runs_subdir in run_benchmark.MADE_SEALED_RUNS_SUBDIRS


def render_closed_sealed_root(development_set: DevelopmentSet) -> str:
    """What ``--check`` prints for a sealed set whose root is closed.

    There is nothing to plan: the root holds its single run and no case will be
    run again, so a list of cases that "would run" would describe an invocation
    that cannot happen. What is left to say is the closure itself, and the three
    empty counts are printed rather than left out, so the shape of the output
    does not depend on whether the root is closed.
    """
    return "\n".join(
        [
            "sealed set {0} -- its root is closed: the single run is "
            "committed".format(development_set.name),
            "  would run (0): nothing",
            "  would not run (0):",
            "    nothing",
            "  attempts that do not count (0):",
            "    nothing",
        ]
    )


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

    ``parallel_calls`` arrives through ``kwargs`` like every other runner
    argument, and it is the one of them that changes nothing the run measures:
    it asks the calls that depend on nothing at the same time and leaves every
    request byte-identical. It is therefore not refused for a sealed set and it
    is not part of the arguments that set's registration fixes.

    ``early_majority`` arrives the same way and is the other switch that changes
    nothing the run measures, so it too is not part of a set's registered
    arguments. It is refused here for a **sealed** set, and not merely left to
    the runner's destination guard: a sealed set's single run is one measurement
    and the owner's note fixes how it was made, so a switch that would have made
    the panel publish at three drafts is refused by name. It is also refused
    without ``parallel_calls``, because what it stops waiting for is a call
    already in flight.

    ``integrity_gate`` arrives through ``kwargs`` on the same rule and is refused
    for a **sealed** set by the set's own name for the same reason: a sealed
    set's single run is one measurement, and a switch that would have escalated a
    record without asking the model is a different measurement.

    ``advocate_effort`` arrives the same way and is the one of these switches
    that changes what a run measures: ``none`` makes the two advocate requests
    carry ``reasoning_effort``, so it is passed to the runner like the ablation
    and a later policy version, and it is refused for a **sealed** set by the
    set's own name. The refusal is made here rather than left to the runner's
    destination guard, because the switched run goes to a root of its own --
    ``runs/advocate-effort-<effort>/`` at the top of the runs tree -- and never
    near the sealed root, so no destination guard would notice it.
    """
    if force:
        assert_not_sealed(development_set, "--force")

    early_majority = bool(kwargs.get("early_majority"))
    if early_majority:
        if not kwargs.get("parallel_calls"):
            raise run_benchmark.BenchmarkError(
                "--early-majority needs --parallel-calls: the rule stops waiting "
                "for a draft that is already in flight, and a sequential panel "
                "has none"
            )
        # By the set's own name, as ``--force`` is refused, so the message says
        # which set cannot be run with it rather than only that something is
        # wrong.
        assert_not_sealed(development_set, "--early-majority")

    if kwargs.get("integrity_gate"):
        # By the set's own name, on the same rule: a sealed set's single run is
        # one measurement and a switch that would have escalated a record
        # without asking the model is a different one.
        assert_not_sealed(development_set, "--integrity-gate")

    if (
        kwargs.get("advocate_effort", run_benchmark.pipeline.ADVOCATE_EFFORT_DEFAULT)
        != run_benchmark.pipeline.ADVOCATE_EFFORT_DEFAULT
    ):
        # By the set's own name, on the same rule once more. Unlike the other
        # switches refused here, this one **does** change request bodies -- the
        # two advocate requests gain ``reasoning_effort`` -- so a sealed set's
        # single run would be a different measurement from the one the freeze
        # names, and the switch is refused rather than left to the destination
        # guard: the switched run goes to a root of its own, outside the sealed
        # root, so no destination guard would notice it.
        assert_not_sealed(development_set, "--advocate-effort")

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
    # The version this invocation briefs at, resolved from the set's own
    # registration and the version the command line named (version 1, the
    # default, when it named none). A set written for a base runs at the latest
    # version on it when no flag names one; a set that fixes its version briefs
    # at it whatever the invocation says; and every other set takes the version
    # given, or version 1.
    named = kwargs.pop("policy_version", None)
    kwargs["policy_version"] = resolved_policy_version(development_set, named)
    # Whether the version moves the run one level down under the set's own root:
    # ``runs/<set>/policy-v<N>/<model>/``. Two versions of one set are then two
    # directories and neither can be mistaken for the other's results. A set that
    # fixes its version keeps the set's own directory instead.
    kwargs["policy_version_moves_the_run"] = version_moves_the_run(
        development_set, named
    )
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
        # A set with a stated expectation rather than a key has nothing to be
        # scored against, so its cases are run unscored: the runner reports them
        # as unscored instead of refusing them for having no key entry.
        unscored=development_set.stated_expectation is not None,
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
    if development_set.stated_expectation is not None:
        _print_stated_expectation(development_set)
    return summary


def _print_stated_expectation(development_set: DevelopmentSet) -> None:
    """The set's stated expectation, printed beside the result it is not scored on.

    An unscored run produces a ruling and a run directory; what it cannot
    produce is a score, because the organisers stated a word rather than one of
    POL-GEN-03's rulings. Printing the expectation beside the run is what
    ``eval.run_benchmark --external`` does for the same case, and it is labelled
    so the two cannot be read as one number.
    """
    path = development_set.stated_expectation
    expected = run_benchmark.read_expected_outcome(path)
    if expected is None:
        print("stated expectation: none on disk at {0}".format(path))
        return
    print(
        "stated expectation ({0}): {1}".format(
            path, expected.get("expected_outcome_as_stated")
        )
    )
    print(
        "  this run is not scored against it: the organisers' word is not one of "
        "POL-GEN-03's rulings"
    )


# --------------------------------------------------------------------------
# Reporting the sets separately and combined
# --------------------------------------------------------------------------
def run_dir_at_its_version(
    development_set: DevelopmentSet, model: str, runs_dir: Path = RUNS_DIR
) -> Path:
    """Where one set's run for one model **actually is**, version level included.

    :meth:`DevelopmentSet.run_dir` is the set's own root one level under
    ``runs/``, and that is deliberately the un-versioned path: ``run_set``
    asserts *that* path is not a headline directory, because a set whose results
    landed in a model's corpus directory would change what the reported figure
    covers. It is not, however, always where the run is. A set registered for a
    policy **base** moves its run one level down at any version above 1 --
    ``runs/dev-v7/policy-v7/<model>/`` -- which is what
    :func:`version_moves_the_run` decides, what ``run_set`` passes the runner as
    ``policy_version_moves_the_run``, and what
    :func:`eval.func_sets.run_directory` already builds for its three sets.

    The report reads a run to grade it, so it has to read the directory the run
    was written to: a versioned run read from the un-versioned path is a set the
    report calls not run while its 40 cases sit one level below, and a figure
    read from the wrong directory is not a figure. Every set whose version does
    not move its run -- every set registered before the version-3 bases, and the
    sealed sets, whose version is part of what the set *is* -- gets
    :meth:`DevelopmentSet.run_dir` unchanged.
    """
    if version_moves_the_run(development_set, None):
        return run_benchmark.policy_v_run_directory(
            development_set.runs_dir(runs_dir),
            resolved_policy_version(development_set, None),
            model,
        )
    return development_set.run_dir(model, runs_dir)


def cached_cases(
    development_set: DevelopmentSet, model: str, runs_dir: Path = RUNS_DIR
) -> List[int]:
    """The set's cases this model has a cached ruling for, in set order."""
    present = set(
        run_benchmark.cached_case_numbers(
            run_dir_at_its_version(development_set, model, runs_dir)
        )
    )
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
    run_dir = run_dir_at_its_version(development_set, model, runs_dir)
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


def registered_prompts_dir(development_set: DevelopmentSet) -> Path:
    """The prompts directory one set's cached results belong to.

    Two answers, in this order, and both of them name **the prompts directory
    the run used**.

    * A set whose registration records the arguments its run is made with
      records the prompt set that run uses, and that is the directory its
      results were produced under -- ``prompts/v2`` for ``dev-v7`` and
      ``sealed-v4``.
    * A set that records none is answered by its **policy version**, through
      :func:`eval.run_benchmark.prompts_directory_for`. That is the pairing the
      runner itself enforces -- a version-7 run with any prompts directory but
      ``prompts/v2`` is refused before a client is built, and versions 1 to 6
      are run with ``prompts/v1`` -- so the version is enough to say which
      directory a set's results came from. ``ryde-v7`` is the set this reaches:
      it is development data and fixes no run arguments, so its registration
      names no prompts directory, while its committed run was made with
      ``prompts/v2`` like every other version-7 run.

    For every set registered before the version-7 pair existed the second
    answer is :data:`eval.run_benchmark.PROMPTS_DIR` itself, which is the
    directory those sets were run with, so their readings do not move.
    """
    arguments = development_set.run_arguments
    if arguments is not None and arguments.prompts_dir is not None:
        return Path(arguments.prompts_dir)
    return run_benchmark.prompts_directory_for(
        resolved_policy_version(development_set, None)
    )


def currency_for(
    development_set: DevelopmentSet,
    model: str,
    runs_dir: Path = RUNS_DIR,
    prompts_dir: Optional[Path] = None,
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

    ``prompts_dir`` is the same decision one channel further on, and its default
    is the set's own rather than a constant: the two prompt sets are not
    interchangeable, and a version-7 run is run with ``prompts/v2``, so a
    checker handed ``prompts/v1`` compares every case's recorded prompt digests
    with a directory no call of that run was ever given. ``None`` means the
    prompts directory this set's registration fixes
    (:func:`registered_prompts_dir`); an explicit argument still wins.
    """
    if prompts_dir is None:
        prompts_dir = registered_prompts_dir(development_set)
    run_dir = run_dir_at_its_version(development_set, model, runs_dir)
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


def render_development_sets(
    model: str,
    runs_dir: Path = RUNS_DIR,
    sets: Optional[Sequence[DevelopmentSet]] = None,
) -> str:
    """The sets separately, then combined, then each separate set on its own.

    ``sets`` is which sets the summary reports, and defaults to
    :data:`DEVELOPMENT_SETS`. A named set is reported the same way -- its own row,
    its own currency line and its own per-case block -- so
    ``--set dev-v2 --report`` grades that set against its own key. The combined
    figure is printed only when the sets reported are the development sets
    themselves: it is a sum over those two and not over any other selection.

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
    reported = list(DEVELOPMENT_SETS) if sets is None else list(sets)
    lines = [
        "Development sets — {0}".format(model),
        "",
        "Separately, each set graded against its own key:",
        "",
        _SET_TABLE_HEADER,
    ]
    figures = [figures_for(development_set, model, runs_dir) for development_set in reported]
    for item in figures:
        lines.append(_render_row(item))

    lines.append("")
    lines.append("Currency, each set checked with its own loader and its own briefs:")
    lines.append("")
    for development_set in reported:
        lines.append(currency_line(development_set, model, runs_dir))

    total_expected = sum(item.expected for item in figures)
    produced_total, combined = combined_figures(model, runs_dir)
    lines.append("")
    lines.append("Combined, every case graded against the key it belongs to:")
    lines.append("")
    if reported != list(DEVELOPMENT_SETS):
        lines.append(
            "  not computed: this report covers {0}, and the combined figure is a "
            "sum over the development sets".format(
                ", ".join(development_set.name for development_set in reported)
            )
        )
    elif combined is None:
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
    # that were drafted the same way, and adding a set whose single run is one of
    # the two generalisation figures would make it a sum of two different claims.
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
        "--parallel-calls",
        action="store_true",
        help=(
            "ask the calls that depend on nothing at the same time: the two "
            "advocates, and the judge's drafts when there is a panel of them. "
            "Off by default, so every run before this switch is the run it was. "
            "No individual request body changes -- the same brief, the same "
            "prompts and the same messages are sent -- so it is not part of a "
            "case's configuration, it moves no run directory, and it is not one "
            "of the arguments a sealed set's run is fixed at. It can still send "
            "requests a sequential run would not: up to two driver requests "
            "after the rider fails, the remaining draft requests after a draft "
            "raises, and a different set of requests under a case deadline. The "
            "client's rate limiter is unchanged, so up to concurrency × "
            "max(2, votes) requests queue at one a second whatever this is set "
            "to"
        ),
    )
    parser.add_argument(
        "--early-majority",
        action="store_true",
        help=(
            "publish the judge's panel as soon as a majority of its drafts have "
            "agreed, instead of waiting for every draft. Off by default, so "
            "every run before this switch waited for the whole panel. It needs "
            "--parallel-calls -- what it stops waiting for is a call already in "
            "flight -- and it is refused for every sealed set, whose single run "
            "is one measurement and is not re-taken. The position-swapped draft "
            "is always waited for, because the fairness measurement reads it; a "
            "draft the panel did not wait for is recorded as not_awaited and "
            "does not count. No individual request body changes, so it is not "
            "part of a case's configuration, it moves no run directory and it is "
            "not one of the arguments a sealed set's run is fixed at. It is "
            "refused with --verify-drafts, because the verifier can take a vote "
            "away after the panel has stopped waiting"
        ),
    )
    parser.add_argument(
        "--integrity-gate",
        action="store_true",
        help=(
            "hold the record itself to POL-RD-10's own limbs (2) and (4) before "
            "the model is asked. Off by default, so every run before this switch "
            "asked the model exactly as it did. On, a route-deviation dispute "
            "whose trip identifiers do not all match across the trip record, the "
            "GPS trace and the fare breakdown -- or whose trip record is absent "
            "-- or whose pickup and dropoff timestamps two admitted artifacts "
            "disagree on by more than the clause's own minutes, or whose "
            "timestamps run backwards, is escalated by code with the reason code "
            "RD10_RECORD_INTEGRITY and no call made. No individual request body "
            "changes -- a gated case sends none -- so it is not part of a case's "
            "configuration, it moves no run directory and it is not one of the "
            "arguments a sealed set's run is fixed at. It is refused for every "
            "sealed set, whose single run is one measurement and is not re-taken"
        ),
    )
    parser.add_argument(
        "--advocate-effort",
        choices=list(run_benchmark.pipeline.ADVOCATE_EFFORTS),
        default=run_benchmark.pipeline.ADVOCATE_EFFORT_DEFAULT,
        metavar="EFFORT",
        help=(
            "which reasoning effort the two advocates' requests carry: default "
            "(the default) leaves every request exactly as it is today, and none "
            "makes the two advocate requests carry reasoning_effort \"none\" "
            "while the judge's drafts and the verifier are untouched. It is a "
            "switch that changes what a run measures, so results go to "
            "runs/advocate-effort-<effort>/<set>/[policy-v<N>/]<model>/ -- the "
            "switch's own root at the top of the runs tree, with the set's own "
            "subdirectory under it -- and never into a run directory holding a "
            "default result. It may be given with --policy-version, whose "
            "directory sits under the switch's root, and it is refused beside "
            "--ablate, --precedents, --amount-rule and a replay. It is refused "
            "for every sealed set, whose single run is one measurement and is "
            "not re-taken"
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
    # The version the command line carries: version 1, the default, when it named
    # none. ``run_set`` is what replaces it with a set's own registration, because
    # that is the layer that knows the registration.
    policy_version = (
        run_benchmark.DEFAULT_POLICY_VERSION
        if explicit_policy_version is None
        else explicit_policy_version
    )

    # A later policy version **named on the command line**, which is the switch
    # the refusals below are keyed on. It is deliberately the command line's
    # version and not a set's **resolved** one: a set written for a base resolves
    # to the latest version on that base when no flag names one, but that is what
    # the set *is* rather than a second switch the invocation gave. Keying on the
    # resolved version instead would refuse ``--set wild-v2 --report`` and
    # ``--set wild-v2 --replay-check``, and hand ``wild-v2``'s own sealed-root
    # refusals to the wrong block -- which is exactly what it did before this
    # predicate was narrowed back.
    version_named = policy_version != run_benchmark.DEFAULT_POLICY_VERSION

    # "all" is the two development sets. The held-out set is deliberately not in
    # that list: it is run once, and an invocation that ran it as a side effect
    # of running everything would be a run nobody chose to make.
    # A set that is declared and whose data is not on disk is told that before
    # anything else: it is not a set this invocation can plan, run or report,
    # and "its data is not there yet" is not the same answer as "there is no
    # such set". ``--check`` prints it too, because a plan is exactly what there
    # is not one of.
    waiting = DECLARED_SETS.get(args.set_name)
    if waiting is not None:
        print(render_declared_set(waiting), file=sys.stderr)
        return 1

    selected = (
        [named(args.set_name)] if args.set_name != "all" else list(DEVELOPMENT_SETS)
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

    if version_named:
        # A later policy version changes what every agent is given, so it follows
        # the rule the ablation follows: it cannot be combined with another switch
        # that changes the agents' input, nor with a mode that reads or reports a
        # run produced without it. This block runs after the other two, so it is
        # the one that catches a version named beside either of them as well as
        # one named alone.
        #
        # ``--precedents`` is **not** in that list any more: the precedents block
        # is the same whatever the policy version, so the two may be given
        # together, and the run goes to ``runs/precedents/policy-vN/<model>/``.
        if args.ablate is not None:
            print(
                "FATAL: at most one of --ablate, --policy-version N>=2 "
                "and --amount-rule may be given per invocation: each changes "
                "what the run measures, and a run with two of them on measures "
                "neither",
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
            or version_named
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

    if args.advocate_effort != run_benchmark.pipeline.ADVOCATE_EFFORT_DEFAULT:
        # The fifth switch that changes what a run measures, and it follows the
        # rule the other four follow. It **does** change request bodies -- the
        # two advocate requests gain ``reasoning_effort`` -- so a mode that reads
        # or reports a run whose advocates reasoned as they always did cannot be
        # combined with it: naming the switch beside one would look as though it
        # had been applied. This block runs last, so it is the one that catches
        # the switch named beside any of the other four as well as one alone.
        #
        # ``--policy-version`` is deliberately **not** in that list: the
        # version's directory sits under the switch's own root, so the two may be
        # given together and the run goes to
        # ``runs/advocate-effort-<effort>/policy-v<N>/<model>/``.
        if (
            args.ablate is not None
            or args.precedents
            or args.amount_rule != run_benchmark.pipeline.DEFAULT_AMOUNT_RULE
        ):
            print(
                "FATAL: at most one of --ablate, --precedents, --policy-version "
                "N>=2, --amount-rule and --advocate-effort may be given per "
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
                    "FATAL: --advocate-effort names the reasoning effort the two "
                    "advocates' requests carry and takes no {0}".format(name),
                    file=sys.stderr,
                )
                return 1

    if args.early_majority:
        # The early-majority switch's own two conditions, refused before any
        # mode runs and before any call. It is **not** one of the four switches
        # that change what a run measures -- it changes no request body and
        # moves no directory -- so it is not refused beside them; it is refused
        # beside ``--parallel-calls``, which it needs, and beside
        # ``--verify-drafts``, which would make it unsound.
        if not args.parallel_calls:
            print(
                "FATAL: --early-majority needs --parallel-calls: the rule stops "
                "waiting for a draft that is already in flight, and a sequential "
                "panel has none",
                file=sys.stderr,
            )
            return 1
        if args.verify_drafts:
            print(
                "FATAL: --early-majority cannot be used with --verify-drafts: "
                "the verifier runs over every valid draft and a contradiction "
                "can take a vote away, so a panel that published at three could "
                "publish a ruling the full panel would not have carried",
                file=sys.stderr,
            )
            return 1

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
        print(
            render_development_sets(
                model,
                args.runs_dir,
                sets=(
                    list(DEVELOPMENT_SETS)
                    if args.set_name == "all"
                    else [named(args.set_name)]
                ),
            )
        )
        return 0

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
    #
    # A set written for a **base** (``dev-v2`` and its two siblings) is the other
    # kind: it accepts any version on that base -- 3, 4, 5, ... -- and refuses
    # one that belongs to another base, so ``--set dev-v2 --policy-version 4``
    # runs the set at version 4 and ``--policy-version 2`` is told which base the
    # set is written for.
    if explicit_policy_version is not None:
        for development_set in selected:
            if development_set.policy_base is not None:
                if (
                    policy_versions.separate_base_of(explicit_policy_version)
                    == development_set.policy_base
                ):
                    continue
                print(
                    "FATAL: {0} is written for policy base {1}, so "
                    "--policy-version {2} is refused for it".format(
                        development_set.name,
                        development_set.policy_base,
                        explicit_policy_version,
                    ),
                    file=sys.stderr,
                )
                return 1
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
        (version_named, "--policy-version"),
        (args.amount_rule != run_benchmark.pipeline.DEFAULT_AMOUNT_RULE, "--amount-rule"),
    ):
        if not present:
            continue
        for development_set in selected:
            # The remedy is the set's own. Naming ``--set wild-dev`` is right
            # only for the held-out set, whose 64 cases have a development twin;
            # the second sealed set has none, so its refusal says so rather than
            # offering a set that does not hold its cases.
            if development_set.runs_subdir == run_benchmark.SEALED_SET_RUNS_SUBDIR:
                remedy = (
                    "{0} is the switch that moves a run one level down under "
                    "its own set's root. Name --set wild-dev instead: those "
                    "are the same 64 cases as development data, and their "
                    "runs go under runs/wild-dev/".format(switch)
                )
            else:
                remedy = (
                    "{0} is the switch that moves a run one level down under "
                    "its own set's root. This set is a sealed record with no "
                    "development twin: its cases are not development data and "
                    "are never re-run, so nothing is created under its root "
                    "again.".format(switch)
                )
            try:
                run_benchmark.assert_not_under_the_held_out_root(
                    development_set.runs_dir(args.runs_dir),
                    args.runs_dir,
                    remedy=remedy,
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
                (args.early_majority, "--early-majority"),
                (args.integrity_gate, "--integrity-gate"),
                # The advocate-effort switch by name too. It is refused in
                # ``run_set`` as well, and here as well for the reason
                # ``--force`` is: the message should name the switch a reader
                # typed rather than the frozen-arguments check that would
                # otherwise answer first.
                (
                    args.advocate_effort
                    != run_benchmark.pipeline.ADVOCATE_EFFORT_DEFAULT,
                    "--advocate-effort",
                ),
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
                    policy_version=resolved_policy_version(
                        development_set, policy_version
                    ),
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
    # like before the one run. A set whose root is already closed has no plan to
    # print -- no case will be run again -- so the closure is printed instead,
    # and the event log is not read to print it.
    if args.check:
        for development_set in selected:
            if not development_set.sealed:
                continue
            subset = [
                case_no for case_no in development_set.cases if not cases or case_no in cases
            ]
            if not subset:
                continue
            if sealed_root_is_closed(development_set):
                print(render_closed_sealed_root(development_set))
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
            if development_set.runs_subdir in run_benchmark.MADE_SEALED_RUNS_SUBDIRS:
                # The run has been made, so there is nothing to opt in to: the
                # root is closed, and this invocation cannot open it.
                print(
                    "FATAL: {0} is a sealed set and its single run has been "
                    "made. Its root is closed: nothing is created under it "
                    "again, {1}={0} included".format(
                        development_set.name, SEALED_RUN_ENV_VAR
                    ),
                    file=sys.stderr,
                )
            else:
                print(
                    "FATAL: {0} is a sealed set, and its single run is made by "
                    "the owner only. To make it, set {1}={0} for that one "
                    "command; nothing else may set it, and nothing in this "
                    "repository does".format(
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
                parallel_calls=args.parallel_calls,
                early_majority=args.early_majority,
                integrity_gate=args.integrity_gate,
                advocate_effort=args.advocate_effort,
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
