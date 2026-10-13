"""The benchmark runner: one model, many cases, resumable.

Runs a set of cases against ONE named model through
:func:`tribunal.pipeline.run_case` and a real :class:`tribunal.llm.LLMClient`,
caches every completed result under ``runs/``, and grades the set through
:mod:`eval.grade`.

Why resumability is the central requirement
-------------------------------------------
Measured on 2026-09-21: two HTTP 502 responses in 48 calls, and a single
``hy4-preview`` advocate call taking 199.9 s and 221.6 s on the real case 208
brief. A 29-case run is therefore hours long and will meet transport failures on
the way. An instrument that loses everything when case 27 fails is not an
instrument. So:

* each completed ``(model, case)`` result is cached under
  ``runs/<model>/case-<NNNNN>.json``, keyed by model directory and case number,
  and a re-run skips it unless ``--force``;
* a case that fails after ``LLMClient`` has exhausted its retries is recorded as
  a failed case, the run **continues**, and nothing is cached for it — so a
  later re-run retries exactly the failures and nothing else;
* every result is written as it completes, through a temporary file and a
  rename, so an interrupt can lose at most the case in flight and can never
  leave a half-written cache file behind;
* the run's metadata file is rewritten after every case, so an interrupted run
  still has correct provenance and correct totals.

The token budget
----------------
Each model carries a 1,000,000-token free allowance and one 29-case run on
``hy4-preview`` is projected at roughly three times that. ``--token-budget``
stops the run issuing NEW cases once the spend has reached the limit, lets the
cases already in flight finish, and says on its face that it stopped on budget
rather than completing. A partial run whose limit is stated is useful; an
unexpected bill is not.

The request timeout
-------------------
``--timeout`` defaults to ``llm.DEFAULT_TIMEOUT_SECONDS`` — the client's own
default, not a second copy of the number — and is passed through to the client
this module builds. Before that parameter existed the runner had no way to set
it, so every call inherited the client default of 120 s and a slow model lost
cases to it: case 109 on ``hy3`` died at 120.1 s with ``TimeoutError: The read
operation timed out``, while ``hy4-preview`` advocate calls on the same brief
took 199.9 s and 221.6 s. The default is now 600 s and the flag exists so a
caller can shorten it deliberately for a quick probe without editing code.

A timeout is recorded as its own failure kind rather than as transport text, so
``runs/<model>/run.json`` distinguishes a case the client stopped waiting for
from a case the model answered unusably. The two call for opposite responses —
a longer timeout or a faster model, against a prompt or model change — and the
first real run contains one of each.

The answer key
--------------
The key is read by :mod:`eval.grade` and by nothing else. This module asks
``eval.grade`` to load it, to hash it, and to score with it; it never opens the
answer key's own directory, and no key value reaches a brief, a prompt or a
transcript. ``tests/test_run_benchmark.py`` asserts that a completed run's cached
artifacts and transcripts carry no answer-key field name, reusing the scan in
``tests/test_answer_isolation.py``.

A cached result is evidence about the code that produced it
----------------------------------------------------------
Every case file records the digest of the exact brief bytes its agents were
handed, so a result can be checked against the brief this code builds now. The
runner does that check whenever it reads a cached result — in ``grade_run``, and
therefore in ``--compare`` — and reports what it finds: a case whose brief has
changed is *stale*, named and counted, and never folded silently into a score.

This is not decoration. The cache under ``runs/`` holds results produced by more
than one version of the brief, and until this check existed nothing said so:
``--compare`` tabulated all of them as one run, and a single-case re-run had
replaced the 29-case run's own ``run.json``, so the commit and the case list
that produced those results existed nowhere afterwards.

``stale`` is one of three answers and the third is not the first. A brief that
cannot be rebuilt — a case file that has since moved, a policy that no longer
parses — is ``unknown``, not current, for the same reason an unreadable working
tree is not clean.

Per-case provenance, and per-invocation metadata
------------------------------------------------
A cache entry records the commit and the prompts digest it was produced under,
beside the brief digest it already kept. Provenance that lives only in a file
the next invocation overwrites is not provenance.

``run.json`` still describes the invocation that wrote it, which is right: it is
rewritten after every case, so an interrupted run has correct totals rather than
none. That makes it the invocation's record and not the directory's, so the
directory gets a block of its own saying what it holds, and every invocation's
record is appended to ``invocations.json`` — keyed by the invocation's start
time — so an earlier one stays reconstructable after its own file is gone.

Concurrency is opt-in and proven
--------------------------------
``--concurrency`` defaults to 1 because that is the ordering that is
deterministic. Above 1 the client's rate limiter becomes shared mutable state
across threads, so :meth:`tribunal.llm.LLMClient._respect_rate_limit` guards its
read-modify-write with a lock, and ``tests/test_run_benchmark.py`` proves that N
threads calling together still do not exceed the configured rate — and that the
check can fail, by running the same workload against an unguarded limiter.

Which model to use is decided in ``tribunal/model.py`` and nowhere else. The
library entry point :func:`run_benchmark` still takes ``model`` as a required
argument — a caller that drives this function directly must say which model it
means — while the command line reads the decided one when ``--model`` is
omitted. ``LLMClient`` keeps no default of its own, so the transport stays
model-agnostic and the decision lives in one place a reader can find.

Replaying the advocates
-----------------------
A case costs three agent calls, and the two advocate calls are the expensive
half: on the shipped run they are about 62% of the tokens. When the only thing
that has changed is ``prompts/v1/judge.system.md``, re-asking the advocates
spends that money regenerating inputs the judge already has, and adds advocate
sampling variance to a comparison whose whole purpose is to isolate one change.

``--replay-advocates RUN_DIR`` therefore reads the recorded rider and driver
answers out of another run's transcripts, refuses any case whose recorded inputs
no longer agree with this code, and calls only the judge. What is refused is
refused *before* anything is written, and that is not a nicety: the obvious use
is to replay a run back into its own directory, where every source entry is a
file this run is about to overwrite. Every source is read and verified first, so
a case that cannot be replayed is still on disk afterwards to be run in full.

The acceptance conditions are each a different way for the recorded answers to
be answers to a different question: the brief this code builds must hash to the
brief that run recorded, each advocate's system prompt as rendered now must hash
to what that run recorded *for that role*, the recorded calls must have been
made on the model this run would use, and both answers must have parsed. A run
that recorded no prompt digest is refused rather than assumed — "the file does
not say" is not "the same".

Replay is for the corpus. A converted external case is never replayed, and
``--external`` runs it in full as it always has: that case's own brief has
changed, so there is nothing byte-identical left to reuse.

The tokens are counted twice and never added. A replayed case's result carries
only the judge's usage; the borrowed calls' own usage is reported beside it as
provenance, because a run that summed them would claim to have spent tokens it
never spent. Everywhere the figures appear — the terminal summary, the report,
the page — says that the advocates were replayed and from which run.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from eval import grade
from eval import sealed_roots
from tribunal import (
    brief,
    events,
    llm,
    loader,
    money,
    pipeline,
    policy_versions,
    transcript,
)
from tribunal import precedents as precedents_library
from tribunal.model import resolve_model

__all__ = [
    "BenchmarkError",
    "case_facts",
    "BriefStaleness",
    "CaseOutcome",
    "ComparisonRow",
    "ReplayCheck",
    "RunSummary",
    "STATUS_COMPLETED",
    "STATUS_CACHED",
    "STATUS_FAILED",
    "STOP_COMPLETED",
    "STOP_BUDGET",
    "STOP_INTERRUPTED",
    "STOP_FATAL",
    "FAILURE_TIMEOUT",
    "FAILURE_TRANSPORT",
    "FAILURE_SHAPE",
    "FAILURE_INTERRUPTED",
    "FAILURE_DEADLINE",
    "FAILURE_REPLAY",
    "FAILURE_NOTE",
    "INVOCATIONS_FILE",
    "CONFIGURATION_FIELDS",
    "DEFAULT_POLICY_VERSION",
    "configuration_document",
    "configuration_of",
    "failure_kind_for",
    "failure_reason_for",
    "billed_tokens",
    "model_slug",
    "run_directory",
    "SECOND_SET_RUNS_SUBDIR",
    "SEALED_SET_RUNS_SUBDIR",
    "WILD_V2_SET_RUNS_SUBDIR",
    "SEALED_V1_SET_RUNS_SUBDIR",
    "SEALED_V2_SET_RUNS_SUBDIR",
    "SEALED_V3_SET_RUNS_SUBDIR",
    "SET_RUNS_SUBDIRS",
    "headline_run_directories",
    "assert_not_a_headline_directory",
    "ABLATION_DIRNAME",
    "ablation_run_directory",
    "assert_ablation_destination",
    "PRECEDENTS_DIRNAME",
    "precedents_run_directory",
    "assert_precedents_destination",
    "precedents_policy_v_run_directory",
    "assert_precedents_policy_v_destination",
    "POLICY_V_DIRNAME",
    "policy_v_directory_name",
    "policy_v_run_directory",
    "assert_policy_v_destination",
    "AMOUNT_RULE_DIRNAME",
    "amount_rule_run_directory",
    "assert_amount_rule_destination",
    "case_cache_path",
    "transcript_path",
    "metadata_path",
    "read_json",
    "write_json",
    "file_sha256",
    "load_cached",
    "cached_case_numbers",
    "CACHE_FINGERPRINT_FIELDS",
    "cache_fingerprint",
    "current_brief_sha256",
    "current_prompts_sha256",
    "brief_staleness",
    "read_replay_source",
    "source_advocate_commit",
    "check_replay",
    "render_replay_check",
    "hash_directory",
    "git_state",
    "interpreter_version",
    "provenance",
    "run_one_case",
    "format_progress",
    "format_start",
    "grade_run",
    "run_benchmark",
    "collect_comparison",
    "render_comparison",
    "parse_cases",
    "print_summary",
    "main",
]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "v1"
RUNS_DIR = PROJECT_ROOT / "runs"

# Where a converted external case runs. **Never** into a model's run directory:
# ``runs/deepseek-deepseek-flash/`` holds the 29-case result the submission
# reports, and an external case has no answer-key entry and is not one of the
# 29, so writing it there would silently change what that directory means -- a
# reader would find a thirtieth case in a run that reports 29.
EXTERNAL_RUNS_SUBDIR = "external"

# The organisers' own stated expectation for their sample case. Read only to
# print beside the produced ruling, never as a grade: it is not an entry in the
# frozen answer key and must never be merged into one.
EXTERNAL_EXPECTED_PATH = PROJECT_ROOT / "eval" / "external" / "ryde" / "expected.json"

# The expectation belonging to an external case lives beside that case's own
# name under eval/external/. One file per case set, so a case is printed beside
# the expectation that belongs to it and never beside another case's.
EXTERNAL_EXPECTED_DIR = PROJECT_ROOT / "eval" / "external"
EXTERNAL_EXPECTED_FILE = "expected.json"

# Bumped when the cache layout changes, so an old cache is visibly old rather
# than silently misread. 2 adds ``vote_agreement`` to the entry: a result now
# says how many of the judge's drafts agreed on the ruling it carries, which a
# schema-1 entry cannot answer at all.
CACHE_SCHEMA_VERSION = 2

METADATA_FILE = "run.json"
# Every invocation's own metadata record, appended to. ``run.json`` is the
# latest invocation's record and the next invocation overwrites it, so it cannot
# be the only place an invocation's provenance lives: a run whose commit and
# token total exist only in a file the next run destroys has no provenance at
# all. This file is the list of them.
INVOCATIONS_FILE = "invocations.json"
CALLS_FILE = "calls.json"
REPORT_FILE = "report.md"

DEFAULT_CONCURRENCY = 1

# Where the case cache and its transcript live.
_CASE_FILE_RE = re.compile(r"^case-([0-9]{5})\.json$")
_CASE_FILE_FORMAT = "case-{0:05d}.json"
_TRANSCRIPT_FORMAT = "case-{0:05d}.transcript.json"

# One outcome per case.
STATUS_COMPLETED = "completed"
STATUS_CACHED = "cached"
STATUS_FAILED = "failed"

# Why the run stopped. ``completed`` is the only one that means everything asked
# for was done.
STOP_COMPLETED = "completed"
STOP_BUDGET = "token budget reached"
STOP_INTERRUPTED = "interrupted"
STOP_FATAL = "fatal error"

# Why a case failed. These are separate kinds because they call for opposite
# responses, and a run can contain one of each: the real hy3 run recorded case
# 108 as a shape failure and case 109 as a timeout.
#
# A timeout says the client stopped waiting for an answer the provider may have
# generated anyway, and whose tokens are billed whether or not anyone read it —
# the response is a longer timeout, or a faster model. A shape failure says the
# run finished without a usable ruling — the response is in the prompt or the
# model, and raising the timeout would change nothing. A transport failure says
# no answer was ever produced, for some other reason, so retrying is the obvious
# move.
#
# The grouping is by what a reader should DO, not by who is at fault, which is
# why one case that looks like it belongs elsewhere is grouped deliberately: a
# server error that exhausts the client's own retries reaches the runner as a
# run with no ruling, so it lands in SHAPE. Waiting longer would not fix it, and
# that is the property the grouping exists to express.
FAILURE_TIMEOUT = "TIMEOUT"
FAILURE_TRANSPORT = "TRANSPORT"
FAILURE_SHAPE = "SHAPE"
FAILURE_INTERRUPTED = "INTERRUPTED"
# A fourth kind, because "the client gave up after its deadline" is a different
# event from "one request waited too long" and the run metadata must not merge
# them. A timeout is a property of one request; a deadline is a bound the run
# put on itself, so the response is to change the bound rather than the model.
FAILURE_DEADLINE = "DEADLINE"
# A fifth kind, and unlike the other four it says nothing about the model. A case
# refused for replay produced no ruling because the recorded run could not
# supply its advocates: the brief, a prompt, the model or an answer no longer
# agrees. That is a statement about the source run and this code, so the
# response is to run the case in full rather than to change anything about the
# model under measurement.
FAILURE_REPLAY = "REPLAY"

# What each kind means, in the words the record carries. Short, because a reader
# scanning a failures list needs to tell the three apart at a glance.
FAILURE_NOTE = {
    FAILURE_TIMEOUT: (
        "the client stopped waiting for a response; the provider may have "
        "generated the answer anyway, and its tokens are billed either way, so "
        "the response is a longer timeout rather than a retry"
    ),
    FAILURE_TRANSPORT: (
        "the request produced no response for a reason other than waiting too "
        "long"
    ),
    FAILURE_SHAPE: (
        "the run finished without a usable ruling; the response is in the "
        "prompt or the model, and a longer timeout would change nothing"
    ),
    FAILURE_INTERRUPTED: (
        "the run was interrupted while this case was in flight, so it says "
        "nothing about the model"
    ),
    FAILURE_DEADLINE: (
        "the client or the case reached its own total deadline and stopped "
        "rather than starting work it had no time to finish; this is a bound the "
        "run put on itself and not a property of the model, so the answer is a "
        "larger deadline or a faster model, and neither a retry nor a longer "
        "per-attempt timeout would change it"
    ),
    FAILURE_REPLAY: (
        "the advocates were to be replayed from an earlier run and that run "
        "could not supply them, so no model was called and this says nothing "
        "about the model; the response is to run the case in full"
    ),
}

# Files that must never contribute to a digest: they are editor or interpreter
# artefacts, not prompt content, and one of them appearing would change the
# digest without any prompt having changed.
_DIGEST_EXCLUDED_NAMES = (".DS_Store",)
_DIGEST_EXCLUDED_SUFFIXES = (".pyc",)

GIT_TIMEOUT_SECONDS = 10.0

# A run's provenance status string can be long; this bounds it.
MAX_STATUS_CHARS = 4000


# --------------------------------------------------------------------------
# The run's configuration
# --------------------------------------------------------------------------
# What produced a result, as opposed to what it was produced from. Every
# artifact a run writes carries it: the run's metadata, each invocation's entry
# in the history, and each case file. It is written whether or not any switch is
# on, so a reader of one case file can say what produced that case without the
# run directory around it.
#
# ``ablation``, ``precedents`` and ``policy_version`` name the three switches
# that change what an agent is given. All three are written at their defaults
# here -- no ablation, no precedents, policy version 1 -- so the object's shape
# does not move when a later switch is added.
CONFIGURATION_FIELDS = (
    "judge_votes",
    "verify_drafts",
    "ablation",
    "precedents",
    "policy_version",
)

# Version 1 is the three policy files exactly as committed, with no amendment
# applied. A file that records no configuration at all was produced under it.
DEFAULT_POLICY_VERSION = 1


def configuration_document(
    *,
    judge_votes: int,
    verify_drafts: bool,
    ablation: Optional[str] = None,
    precedents: Optional[Any] = None,
    policy_version: int = DEFAULT_POLICY_VERSION,
) -> Dict[str, Any]:
    """The configuration object every artifact a run writes carries.

    ``judge_votes`` and ``verify_drafts`` used to appear only on the
    ``invocation_start`` event, which is a line in a log rather than something a
    case file can be read against. They are here so one case file says how many
    drafts its judge was asked for and whether the verifier ran, without the
    reader needing the invocation that produced it.
    """
    return {
        "judge_votes": judge_votes,
        "verify_drafts": verify_drafts,
        "ablation": ablation,
        "precedents": precedents,
        "policy_version": policy_version,
    }


def configuration_of(document: Any) -> Dict[str, Any]:
    """The configuration a file was produced under, read two ways.

    A file written before the object existed is not an error and not a blank.
    For staleness, replay and reports it counts as what it in fact was: no
    ablation, no precedents, policy version 1. Its ``judge_votes`` and
    ``verify_drafts`` are ``None``, which is "unknown" rather than a value --
    nothing in the file says how many drafts that judge was asked for, and
    reporting a default there would invent a fact about the run.
    """
    raw = document.get("configuration") if isinstance(document, Mapping) else None
    if not isinstance(raw, Mapping):
        raw = {}
    policy_version = raw.get("policy_version")
    if policy_version is None:
        policy_version = DEFAULT_POLICY_VERSION
    return {
        "judge_votes": raw.get("judge_votes"),
        "verify_drafts": raw.get("verify_drafts"),
        "ablation": raw.get("ablation"),
        "precedents": raw.get("precedents"),
        "policy_version": policy_version,
    }


class BenchmarkError(Exception):
    """The runner was asked for something it cannot do."""


# --------------------------------------------------------------------------
# Cache layout
# --------------------------------------------------------------------------
def model_slug(model: str) -> str:
    """A filesystem-safe directory name for a model id.

    ``deepseek/deepseek-flash`` becomes ``deepseek-deepseek-flash``. Leading and
    trailing dots are stripped so a model id can never name ``.`` or ``..``.
    """
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(model)).strip("-.")
    if not slug:
        raise BenchmarkError("model id {0!r} has no usable characters".format(model))
    return slug


def run_directory(runs_dir: Path, model: str) -> Path:
    """Where one model's run lives: ``runs/<model-slug>/``."""
    return Path(runs_dir) / model_slug(model)


# The run subdirectory each development set keeps its results under, one
# level below the runs root. The corpus is the exception: ``runs/<model-slug>/``
# *is* its directory. This tuple is the one place the layout is named, and
# ``eval.development_sets`` builds its sets from these names, so a set cannot be
# added without its run directory being a headline directory here.
SECOND_SET_RUNS_SUBDIR = "codex"
SEALED_SET_RUNS_SUBDIR = "wild"
# The second sealed set, imported on 2026-10-03. It is run once too, from a
# commit whose ``tribunal/``, ``prompts/`` and ``policy/`` trees equal those at
# the tag ``freeze-2026-10-03`` -- every event the run writes records the commit
# it was made from -- and its single run is one of the two generalisation
# figures; it is a different set from ``wild`` and is never added to it, to the
# combined figure or to ``--set all``.
WILD_V2_SET_RUNS_SUBDIR = "wild-v2"
# The third sealed set, imported on 2026-10-09 and run once, on 2026-10-10. Its
# single run was made from the commit ``feb7174``, whose ``tribunal/``,
# ``prompts/`` and ``policy/`` trees equal those at the tag ``freeze-2026-10-09``,
# at the policy version 6 its registration fixes. It is a different set from
# ``wild`` and ``wild-v2`` and is never added to either, to the combined figure or
# to ``--set all``.
SEALED_V1_SET_RUNS_SUBDIR = "sealed-v1"
# The fourth sealed set, imported on 2026-10-11 and run once, on 2026-10-11. Its
# single run was made from the commit ``19c7e5a``, whose ``tribunal/``,
# ``prompts/`` and ``policy/`` trees equal those at the tag ``freeze-2026-10-11``,
# at the policy version 6 its registration fixes. It is a different set from
# ``wild``, ``wild-v2`` and ``sealed-v1`` and is never added to any of them, to
# the combined figure or to ``--set all``.
SEALED_V2_SET_RUNS_SUBDIR = "sealed-v2"
# The fifth sealed set, imported on 2026-10-13. Its single run was started once,
# on 2026-10-13, from the commit ``9b70387``, whose ``tribunal/``, ``prompts/``
# and ``policy/`` trees equal those at the tag ``freeze-2026-10-11``, at the
# policy version 6 its registration fixes, and was stopped after 8 of its 30
# cases; it is not a sealed figure and is never run again. It is a different set
# from ``wild``, ``wild-v2``, ``sealed-v1`` and ``sealed-v2`` and is never added
# to any of them, to the combined figure or to ``--set all``.
SEALED_V3_SET_RUNS_SUBDIR = "sealed-v3"
SET_RUNS_SUBDIRS: Tuple[str, ...] = (
    SECOND_SET_RUNS_SUBDIR,
    SEALED_SET_RUNS_SUBDIR,
    WILD_V2_SET_RUNS_SUBDIR,
    SEALED_V1_SET_RUNS_SUBDIR,
    SEALED_V2_SET_RUNS_SUBDIR,
    SEALED_V3_SET_RUNS_SUBDIR,
)


def headline_run_directories(runs_dir: Path, model: str) -> Tuple[Path, ...]:
    """Every run directory under one runs root that holds a reported figure.

    The corpus keeps its result at ``<root>/<model-slug>/`` and each set that
    has a directory of its own keeps its at ``<root>/<subdir>/<model-slug>/`` --
``runs/codex/`` for the second development set, ``runs/wild/`` for the
held-out set, ``runs/wild-v2/`` for the second sealed set, ``runs/sealed-v1/``
for the third, ``runs/sealed-v2/`` for the fourth and ``runs/sealed-v3/`` for
the fifth, whose run was started and stopped and reports no figure. Called
with ``runs/`` the seven are the corpus's, the second set's and the five sealed
sets'; called with a set's own root the first is that set's and the other
    six are names no run of that root uses, which is harmless because every
    destination these are checked against lives under a subdirectory of its own
    and so can equal none of them.

    One function rather than seven lists. The ablation, the precedents block, a
    later policy version, the baselines, the policy-gap report and the
    recorded-drafts measurement all refuse a headline directory, and they must
    refuse the same ones; a set added to :data:`SET_RUNS_SUBDIRS` is refused by
    all six without any of them being edited.
    """
    root = Path(runs_dir)
    return tuple(
        [run_directory(root, model)]
        + [root / subdir / model_slug(model) for subdir in SET_RUNS_SUBDIRS]
    )


def assert_not_a_headline_directory(
    destination: Path, runs_dir: Path, model: str
) -> Path:
    """Refuse a destination that is one of the run directories the submission reports.

    The check the three switched runs, the baselines and the policy-gap report
    share. Each of those writes somewhere of its own, and this is what says so
    in one place rather than in six that can drift apart.
    """
    resolved = Path(destination).resolve()
    for headline in headline_run_directories(runs_dir, model):
        if resolved == headline.resolve():
            raise BenchmarkError(
                "{0} is the headline run directory {1}, which holds a figure "
                "the submission reports".format(resolved, headline.resolve())
            )
    return Path(destination)


# The re-runnable set's own root, one component below a runs root. It is
# deliberately **not** in :data:`SET_RUNS_SUBDIRS`: that tuple is the run
# directories a reported figure comes from, and ``wild-dev`` holds the held-out
# set's cases as development data. It is named here because the guard below has
# to tell it apart from the held-out set's root, which is one character away.
WILD_DEV_RUNS_SUBDIR = "wild-dev"

# What to do instead, in the words every refusal of this rule ends with.
HELD_OUT_REMEDY = (
    "The same cases are runnable as development data: --set wild-dev writes "
    "under runs/wild-dev/, which is a different directory."
)

# The second sealed set's own, and it names no twin because there is none: its
# cases are not development data, so no directory holds them again.
WILD_V2_REMEDY = (
    "The set is a sealed record: its cases are not development data and are "
    "never re-run."
)

# The third sealed set's remedy, and it is the second sealed set's sentence
# because the reason is the same: the cases are not development data, so there
# is no twin directory to point at.
SEALED_V1_REMEDY = WILD_V2_REMEDY

# The fourth sealed set's remedy, the same sentence again for the same reason.
SEALED_V2_REMEDY = WILD_V2_REMEDY

# The fifth sealed set's remedy, the same sentence again for the same reason.
SEALED_V3_REMEDY = WILD_V2_REMEDY


def held_out_runs_root(runs_root: Path = RUNS_DIR) -> Path:
    """``<runs root>/wild/``: the held-out set's own runs root."""
    return Path(runs_root) / SEALED_SET_RUNS_SUBDIR


# The roots, one component below a runs root, that hold a single sealed run and
# whose run **has been made**: ``wild``'s once, from the commit tagged
# ``freeze-2026-09-30``; ``wild-v2``'s once, from a commit whose ``tribunal/``,
# ``prompts/`` and ``policy/`` trees equal those at ``freeze-2026-10-03``;
# ``sealed-v1``'s once, from the commit ``feb7174``, whose trees equal those at
# ``freeze-2026-10-09``; ``sealed-v2``'s once, from the commit ``19c7e5a``,
# whose trees equal those at ``freeze-2026-10-11``; and ``sealed-v3``'s once,
# started on 2026-10-13 from the commit ``9b70387``, whose trees equal those at
# ``freeze-2026-10-11``, and stopped after 8 of its 30 cases. So all five are
# closed outright -- nothing is created under any of them again, not a case, not
# an ablated run, not a run at a later policy version, not a report -- because a
# second thing written there changes what the directory means while leaving every
# file a reader would look at apparently intact.
MADE_SEALED_RUNS_SUBDIRS: Tuple[str, ...] = (
    SEALED_SET_RUNS_SUBDIR,
    WILD_V2_SET_RUNS_SUBDIR,
    SEALED_V1_SET_RUNS_SUBDIR,
    SEALED_V2_SET_RUNS_SUBDIR,
    SEALED_V3_SET_RUNS_SUBDIR,
)
# The sealed roots whose single run has **not** been made. It is empty: the fifth
# sealed set's run was started once on 2026-10-13 and stopped, and it is never
# finished or repeated, so no root accepts even the plain sealed run any more.
# The permit below is written against this tuple, and with it empty nothing opens
# a sealed root; it is kept because a further sealed set would need exactly it.
UNRUN_SEALED_RUNS_SUBDIRS: Tuple[str, ...] = ()
SEALED_RUNS_SUBDIRS: Tuple[str, ...] = (
    MADE_SEALED_RUNS_SUBDIRS + UNRUN_SEALED_RUNS_SUBDIRS
)


def path_components(path: Path) -> Tuple[str, ...]:
    """A path's resolved components, case-folded, for comparison on this volume.

    The volume this repository lives on is case-insensitive, so ``runs/WILD-V2``
    and ``runs/wild-v2`` are one directory. Comparing paths as they are written
    would let a guard be walked around by changing a letter's case: the same
    place would be refused under one spelling and accepted under the other, and
    the guard would be answering about the spelling rather than about the
    directory. Every comparison between a destination and a guarded root goes
    through here, and it is a tuple of components rather than a string so that
    ``runs/wild-dev`` is still a different directory from ``runs/wild``.
    """
    return tuple(part.casefold() for part in Path(path).resolve().parts)


def assert_not_under_the_held_out_root(
    destination: Path,
    runs_root: Path = RUNS_DIR,
    *,
    remedy: Optional[str] = None,
    permit: Optional[Path] = None,
) -> Path:
    """Refuse a destination that lies under a sealed set's own root.

    Five roots hold a single sealed run. Four of them -- ``<runs root>/wild/``,
    made once from the commit tagged ``freeze-2026-09-30``,
    ``<runs root>/wild-v2/``, made once on 2026-10-04 from a commit whose
    ``tribunal/``, ``prompts/`` and ``policy/`` trees equal those at
    ``freeze-2026-10-03``, ``<runs root>/sealed-v1/``, made once on 2026-10-10
    from the commit ``feb7174``, whose trees equal those at
    ``freeze-2026-10-09``, and ``<runs root>/sealed-v2/``, made once on
    2026-10-11 from the commit ``19c7e5a``, whose trees equal those at
    ``freeze-2026-10-11`` -- have had their run made, and each is one of the
    submission's generalisation figures, so nothing may be created under any of
    them again -- not a case, not an ablated run, not a run at a later policy
    version, not a report -- because a second thing written there changes what
    the directory means while leaving every file a reader would look at
    apparently intact. The fifth, ``<runs root>/sealed-v3/``, was imported on
    2026-10-13 and its single run was started once on 2026-10-13 from the commit
    ``9b70387``, whose trees equal those at ``freeze-2026-10-11``, and stopped
    after 8 of its 30 cases; it is not a sealed figure and is never run again, so
    it is closed outright like the other four and refuses every destination.

    ``permit`` is the one thing that could open a sealed root, and it is written
    for a root whose single run has **not** been made yet: it names the plain
    sealed run's own directory, exactly one component below the root, and the
    permit is honoured only for that destination. All five roots' runs have been
    made -- ``sealed-v3``'s was started and stopped -- so all five are closed
    outright; ``UNRUN_SEALED_RUNS_SUBDIRS`` is empty, so the permit opens nothing.

    ``permit`` is **not** a licence any caller may issue for itself. It is
    passed by :func:`eval.development_sets.run_set` alone, and only when the set
    it is running is the one whose registration owns that root -- see
    ``run_benchmark``'s ``sealed_permit_set``. A direct invocation of the runner
    and a run of any other set pass no permit at all, so
    ``--runs-dir runs/wild-v2`` is refused however it is reached.

    The permit opens **the plain run directory of a runs root**, and a runs root
    that is itself a sealed root is not one: ``--set wild-v2 --runs-dir
    runs/wild-v2`` would otherwise have the permit open
    ``runs/wild-v2/wild-v2/<slug>/``, a second directory under the sealed root,
    which is the one thing the permit exists to prevent. A base named like a
    sealed root is therefore skipped rather than honoured.

    The comparison is **component by component**, not a prefix test on the
    string: ``runs/wild-dev/`` is a different directory from ``runs/wild/`` and
    is deliberately not caught, because it is where a re-run of the same 64
    cases is meant to go. A prefix test would refuse it. The components are
    compared case-folded, because this volume is case-insensitive and
    ``runs/WILD-V2`` names the same directory as ``runs/wild-v2``.

    **Two roots are walked, not one**, and for the reason
    :func:`baselines.assert_not_a_run_directory` walks two: ``--runs-dir`` and
    the repository's own ``runs/`` are separate arguments, so a caller who
    points the first at a scratch root has not thereby made the repository's
    sealed roots safe to write into. Every sealed root under either is refused,
    so the guard no longer depends on the two agreeing about where the runs are.

    Returns the destination unchanged when it is outside, so a caller can build
    and check it in one expression.
    """
    folded = path_components(destination)
    resolved = Path(destination).resolve()
    permitted = None if permit is None else path_components(permit)
    roots = [Path(runs_root).resolve()]
    repository = Path(RUNS_DIR).resolve()
    if repository not in roots:
        roots.append(repository)
    sealed_names = tuple(name.casefold() for name in SEALED_RUNS_SUBDIRS)
    for base in roots:
        base_parts = path_components(base)
        # A runs root whose own name is a sealed root is a sealed root, not a
        # runs root, so nothing below it is the plain sealed run's directory.
        sealed_base = base_parts[-1] in sealed_names
        for subdir in SEALED_RUNS_SUBDIRS:
            root = (base / subdir).resolve()
            root_parts = base_parts + (subdir.casefold(),)
            if not (folded == root_parts or folded[: len(root_parts)] == root_parts):
                continue
            if (
                subdir in UNRUN_SEALED_RUNS_SUBDIRS
                and permitted is not None
                and folded == permitted
                and not sealed_base
            ):
                # The one destination an un-run sealed root still accepts, and
                # only for the caller that named the set it belongs to. No root
                # is in that tuple today, so this opens nothing; it is kept
                # because a fifth sealed set would need exactly this.
                continue
            # One sentence per root, so a root added to the tuple cannot be
            # refused with another root's reason.
            if subdir == SEALED_SET_RUNS_SUBDIR:
                detail = (
                    "which holds the held-out set's single run: it was made once from "
                    "the commit tagged freeze-2026-09-30 and is one of the two "
                    "generalisation figures the submission reports -- the other is "
                    "the second sealed set's single run -- so nothing is created "
                    "under it again. {0}".format(HELD_OUT_REMEDY if remedy is None else remedy)
                )
            elif subdir == WILD_V2_SET_RUNS_SUBDIR:
                detail = (
                    "which holds the sealed set wild-v2's single run: it was made "
                    "once, plainly, from a commit whose tribunal/, prompts/ and "
                    "policy/ trees equal those at freeze-2026-10-03, and it is the "
                    "other generalisation figure the submission reports, so nothing "
                    "is created under it again. {0}".format(
                        WILD_V2_REMEDY if remedy is None else remedy
                    )
                )
            elif subdir == SEALED_V1_SET_RUNS_SUBDIR:
                detail = (
                    "which holds the sealed set sealed-v1's single run: it was made "
                    "once, plainly, from the commit feb7174, whose tribunal/, "
                    "prompts/ and policy/ trees equal those at freeze-2026-10-09, "
                    "and it is the third generalisation figure the submission "
                    "reports, so nothing is created under it again. {0}".format(
                        SEALED_V1_REMEDY if remedy is None else remedy
                    )
                )
            elif subdir == SEALED_V2_SET_RUNS_SUBDIR:
                detail = (
                    "which holds the sealed set sealed-v2's single run: it was made "
                    "once, plainly, from the commit 19c7e5a, whose tribunal/, "
                    "prompts/ and policy/ trees equal those at freeze-2026-10-11, "
                    "and it is the fourth generalisation figure the submission "
                    "reports, so nothing is created under it again. {0}".format(
                        SEALED_V2_REMEDY if remedy is None else remedy
                    )
                )
            elif subdir == SEALED_V3_SET_RUNS_SUBDIR:
                detail = (
                    "which holds the sealed set sealed-v3's single run: it was "
                    "started once, plainly, on 2026-10-13 from the commit 9b70387, "
                    "whose tribunal/, prompts/ and policy/ trees equal those at "
                    "freeze-2026-10-11, and was stopped after 8 of its 30 cases. It "
                    "is not a sealed figure and is never run again, so nothing is "
                    "created under it. {0}".format(
                        SEALED_V3_REMEDY if remedy is None else remedy
                    )
                )
            else:
                detail = (
                    "which is a sealed set's own root: a single sealed run is all "
                    "that is ever created under one"
                )
            raise BenchmarkError(
                "{0} lies under {1}, {2}".format(resolved, root, detail)
            )
    return Path(destination)


# Where an ablated run lives, one level under the runs root. An ablated result
# is a different measurement from the plain one, and ``runs/<model-slug>/`` is
# where the submission's figure lives: a run with an ablation on must not be
# able to land there, and a directory of its own is what makes that checkable
# rather than merely intended. Under the second set's root the same rule gives
# ``runs/codex/ablation/<name>/<model-slug>/``.
ABLATION_DIRNAME = "ablation"


def ablation_run_directory(runs_dir: Path, ablation: str, model: str) -> Path:
    """Where one ablated run lives: ``runs/ablation/<name>/<model-slug>/``.

    The ablation's name is a path component, so it is the name and not a flag:
    two ablations of one model are two directories, and neither can be mistaken
    for the other's results.
    """
    return Path(runs_dir) / ABLATION_DIRNAME / str(ablation) / model_slug(model)


def assert_ablation_destination(run_dir: Path, runs_dir: Path, model: str) -> Path:
    """Refuse an ablated run's directory that is not under the ablation root.

    ``runs/<model-slug>/``, ``runs/codex/<model-slug>/`` and
    ``runs/wild/<model-slug>/`` hold the figures the submission reports, and an
    ablated result is a different measurement: one
    written there would change what that directory means while leaving every file
    a reader looks at apparently intact. The destination is therefore checked
    rather than merely chosen, so a name that resolved outside
    ``<runs root>/ablation/`` -- ``..``, an absolute path, an empty string --
    cannot put an ablated result where an unablated one lives.

    Returns the directory unchanged when it is where it should be, so a caller
    can build and check it in one expression.
    """
    resolved = Path(run_dir).resolve()
    assert_not_a_headline_directory(resolved, runs_dir, model)
    root = (Path(runs_dir) / ABLATION_DIRNAME).resolve()
    if not resolved.is_relative_to(root):
        raise BenchmarkError(
            "an ablated run may only be written under {0}, and this one would go "
            "to {1}".format(root, resolved)
        )
    return Path(run_dir)


# Where a run with precedents on lives, one level under the runs root. The same
# rule the ablation uses, for the same reason: the library is built by people who
# have seen these development sets, so a figure measured with it on is not
# comparable to the headline, and it must not be able to land where the headline
# figure lives. Under the second set's root the rule gives
# ``runs/codex/precedents/<model-slug>/``.
PRECEDENTS_DIRNAME = "precedents"

# The store a run uses when the switch is on and no other store is named. It is
# a parameter everywhere it is read, so a test can point it at a temporary
# directory; this is only the default the command line passes.
PRECEDENTS_STORE = PROJECT_ROOT / PRECEDENTS_DIRNAME


def precedents_run_directory(runs_dir: Path, model: str) -> Path:
    """Where a run with precedents on lives: ``runs/precedents/<model-slug>/``."""
    return Path(runs_dir) / PRECEDENTS_DIRNAME / model_slug(model)


def assert_precedents_destination(run_dir: Path, runs_dir: Path, model: str) -> Path:
    """Refuse a precedents run's directory that is not under the precedents root.

    ``runs/<model-slug>/``, ``runs/codex/<model-slug>/`` and
    ``runs/wild/<model-slug>/`` hold the figures the submission reports, and a
    run the judge was given precedents in is a
    different measurement. The destination is checked rather than merely chosen,
    so a name that resolved outside ``<runs root>/precedents/`` cannot put such a
    result where the headline figure lives.

    Returns the directory unchanged when it is where it should be.
    """
    resolved = Path(run_dir).resolve()
    assert_not_a_headline_directory(resolved, runs_dir, model)
    root = (Path(runs_dir) / PRECEDENTS_DIRNAME).resolve()
    if not resolved.is_relative_to(root):
        raise BenchmarkError(
            "a run with precedents on may only be written under {0}, and this one "
            "would go to {1}".format(root, resolved)
        )
    return Path(run_dir)


def precedents_policy_v_run_directory(
    runs_dir: Path, policy_version: int, model: str
) -> Path:
    """Where a run with precedents **and** a later version lives.

    ``runs/precedents/policy-v<N>/<model-slug>/``: the precedents block is the
    same whatever the policy version, so the two switches may be given together,
    and their run is a third measurement -- neither the plain precedents run at
    ``runs/precedents/<model-slug>/`` nor the plain version-N run at
    ``runs/policy-v<N>/<model-slug>/`` -- so it gets a directory of its own that
    collides with neither.
    """
    return (
        Path(runs_dir)
        / PRECEDENTS_DIRNAME
        / policy_v_directory_name(policy_version)
        / model_slug(model)
    )


def assert_precedents_policy_v_destination(
    run_dir: Path, runs_dir: Path, policy_version: int, model: str
) -> Path:
    """Refuse a precedents-and-version run's directory that is not under its root.

    Checked against ``<runs root>/precedents/policy-v<N>/`` specifically rather
    than against ``precedents/*`` or ``policy-v*``, so a run at one version
    cannot land in another's and a plain precedents run cannot land in a
    versioned one. ``runs/<model-slug>/``, ``runs/codex/<model-slug>/`` and the
    five sealed roots are refused by :func:`assert_not_a_headline_directory` and
    by :func:`eval.sealed_roots.refuse_a_sealed_destination`, which the callers
    of this helper apply as well.

    Returns the directory unchanged when it is where it should be.
    """
    resolved = Path(run_dir).resolve()
    assert_not_a_headline_directory(resolved, runs_dir, model)
    root = (
        Path(runs_dir) / PRECEDENTS_DIRNAME / policy_v_directory_name(policy_version)
    ).resolve()
    if not resolved.is_relative_to(root):
        raise BenchmarkError(
            "a run with precedents on at policy version {0} may only be written "
            "under {1}, and this one would go to {2}".format(
                policy_version, root, resolved
            )
        )
    return Path(run_dir)


# Where a run at a later policy version lives, one level under the runs root and
# named for the version. The same rule the ablation and the precedent block
# follow, for the same reason: a brief built from amended policy is a different
# measurement from the headline, and it must not be able to land where the
# headline figure lives. Under the second set's root the rule gives
# ``runs/codex/policy-v<N>/<model-slug>/``.
POLICY_V_DIRNAME = "policy-v"


def policy_v_directory_name(policy_version: int) -> str:
    """The one directory name a version's results live under."""
    return "{0}{1}".format(POLICY_V_DIRNAME, policy_version)


def policy_v_run_directory(
    runs_dir: Path, policy_version: int, model: str
) -> Path:
    """Where a run at version N lives: ``runs/policy-v<N>/<model-slug>/``.

    The version is a path component and not a flag, so two versions of one model
    are two directories and neither can be mistaken for the other's results.
    """
    return (
        Path(runs_dir)
        / policy_v_directory_name(policy_version)
        / model_slug(model)
    )


def assert_policy_v_destination(
    run_dir: Path, runs_dir: Path, policy_version: int, model: str
) -> Path:
    """Refuse a version-N run's directory that is not under that version's root.

    ``runs/<model-slug>/``, ``runs/codex/<model-slug>/`` and
    ``runs/wild/<model-slug>/`` hold the figures the submission reports, and a
    run briefed from amended policy is a different
    measurement: one written there would change what that directory means while
    leaving every file a reader looks at apparently intact. The destination is
    therefore checked rather than merely chosen, so a name that resolved outside
    ``<runs root>/policy-v<N>/`` cannot put such a result where the headline
    figure lives. It is checked against *this version's* directory rather than
    against ``policy-v*``, so a version-2 run cannot land in version 3's.

    Returns the directory unchanged when it is where it should be.
    """
    resolved = Path(run_dir).resolve()
    assert_not_a_headline_directory(resolved, runs_dir, model)
    root = (Path(runs_dir) / policy_v_directory_name(policy_version)).resolve()
    if not resolved.is_relative_to(root):
        raise BenchmarkError(
            "a run at policy version {0} may only be written under {1}, and this "
            "one would go to {2}".format(policy_version, root, resolved)
        )
    return Path(run_dir)


# Where a run judged by a non-default amount rule lives, one level under the runs
# root and named for the rule. The same rule the ablation, the precedent block
# and a later policy version follow, for the same reason: a run that read the
# drafts' amounts off by a different rule is a different measurement from the
# headline, and it must not be able to land where the headline figure lives.
# Under the second set's root the rule gives
# ``runs/codex/amount-rule/<rule>/<model-slug>/``.
AMOUNT_RULE_DIRNAME = "amount-rule"


def amount_rule_run_directory(runs_dir: Path, amount_rule: str, model: str) -> Path:
    """Where a run under one amount rule lives: ``runs/amount-rule/<rule>/<model-slug>/``.

    The rule is a path component and not a flag, so two rules are two
    directories and neither can be mistaken for the other's results.
    """
    return (
        Path(runs_dir) / AMOUNT_RULE_DIRNAME / str(amount_rule) / model_slug(model)
    )


def assert_amount_rule_destination(
    run_dir: Path, runs_dir: Path, amount_rule: str, model: str
) -> Path:
    """Refuse an amount-rule run's directory that is not under that rule's root.

    ``runs/<model-slug>/``, ``runs/codex/<model-slug>/`` and
    ``runs/wild/<model-slug>/`` hold the figures the submission reports, and a
    run judged by another amount rule is a different measurement: one written
    there would change what that directory means while leaving every file a
    reader looks at apparently intact. The destination is therefore checked
    rather than merely chosen, so a name that resolved outside
    ``<runs root>/amount-rule/<rule>/`` cannot put such a result where the
    headline figure lives. It is checked against *this rule's* directory rather
    than against ``amount-rule/*``, so a signed run cannot land in the published
    one's.

    Returns the directory unchanged when it is where it should be.
    """
    resolved = Path(run_dir).resolve()
    assert_not_a_headline_directory(resolved, runs_dir, model)
    root = (
        Path(runs_dir) / AMOUNT_RULE_DIRNAME / str(amount_rule)
    ).resolve()
    if not resolved.is_relative_to(root):
        raise BenchmarkError(
            "a run under the {0!r} amount rule may only be written under {1}, and "
            "this one would go to {2}".format(amount_rule, root, resolved)
        )
    return Path(run_dir)


# Where a run made with the advocates' reasoning turned off lives. The two
# advocates are the slowest part of a case, and ``--advocate-effort none``
# changes the two advocate requests and nothing else, so a run made with it is a
# different measurement from the headline and must not be able to land where the
# headline figure lives. The same rule the ablation, the precedent block, a later
# policy version and the amount rule follow, for the same reason.
#
# The root sits at the **top** of the runs tree rather than under a set's own
# root, so one root holds every set's switched runs and a reader can see at a
# glance which runs were made with reasoning off: ``runs/advocate-effort-none/``
# with the set's own subdirectory under it, then the version's and the model's.
ADVOCATE_EFFORT_DIRNAME = "advocate-effort"


def advocate_effort_directory_name(advocate_effort: str) -> str:
    """The one directory name one advocate-effort setting's runs live under."""
    return "{0}-{1}".format(ADVOCATE_EFFORT_DIRNAME, advocate_effort)


def advocate_effort_root(
    runs_dir: Path,
    held_out_root: Optional[Path],
    advocate_effort: str,
) -> Path:
    """``<top-level runs root>/advocate-effort-<effort>/<set>/``.

    ``runs_dir`` is the *set's* root -- ``runs/`` for the corpus, ``runs/codex/``
    for the second set -- and ``held_out_root`` is the top-level root the
    invocation was given, which is what ``eval.development_sets.run_set`` passes
    as the root a sealed set's own root has to be compared against. ``None``
    means the set's root *is* the top-level one, which is what a direct
    invocation of this runner gives: ``python3 -m eval.run_benchmark`` names the
    corpus root and no other.

    The set's part is taken from where ``runs_dir`` sits under the top-level
    root, so the corpus contributes nothing and a development set contributes its
    own name -- ``runs/advocate-effort-none/codex/``, which is the set's switched
    run root. A runs root that is not under the top-level one (a scratch root a
    caller named, with no top-level root of its own) contributes nothing either,
    so the switched run stays inside the root the caller named rather than
    reaching into this repository's ``runs/``.
    """
    top = Path(runs_dir if held_out_root is None else held_out_root)
    base = Path(runs_dir)
    try:
        set_part = base.resolve().relative_to(top.resolve())
    except ValueError:
        set_part = Path("")
    return top / advocate_effort_directory_name(advocate_effort) / set_part


def advocate_effort_run_directory(
    root: Path, advocate_effort: str, policy_version: int, model: str
) -> Path:
    """Where one run under the switch lives, under its own root.

    ``<root>/<model-slug>/`` at version 1 and ``<root>/policy-v<N>/<model-slug>/``
    above it, which is the layout every other run in this tree uses: the version
    is a path component and not a flag, so two versions of one set are two
    directories and neither can be mistaken for the other's results.
    """
    base = Path(root)
    if policy_version != DEFAULT_POLICY_VERSION:
        base = base / policy_v_directory_name(policy_version)
    return base / model_slug(model)


def assert_advocate_effort_destination(
    run_dir: Path, root: Path, model: str
) -> Path:
    """Refuse a switched run's directory that is not under the switch's own root.

    ``runs/<model-slug>/``, ``runs/codex/<model-slug>/`` and the five sealed
    roots hold the figures the submission reports, and a run whose advocates
    reasoned differently is a different measurement: one written there would
    change what that directory means while leaving every file a reader looks at
    apparently intact. The destination is therefore checked rather than merely
    chosen, so a name that resolved outside ``root`` cannot put such a result
    where a reported figure lives.

    The reported directories are asked about against the tree the switch's root
    **sits under** and not against the root itself, and that is not a detail: the
    corpus's switched run belongs at ``<switch root>/<model-slug>/``, which is
    the shape a headline directory has under any root, so asking the question of
    the switch's root would refuse the one destination the switch exists to
    create.

    Returns the directory unchanged when it is where it should be.
    """
    resolved = Path(run_dir).resolve()
    root = Path(root).resolve()
    if not resolved.is_relative_to(root):
        raise BenchmarkError(
            "a run under the {0!r} advocate effort may only be written under {1}, "
            "and this one would go to {2}".format(root.name, root, resolved)
        )
    assert_not_a_headline_directory(resolved, root.parent, model)
    return Path(run_dir)


def case_cache_path(run_dir: Path, case_no: int) -> Path:
    return Path(run_dir) / _CASE_FILE_FORMAT.format(case_no)


def transcript_path(run_dir: Path, case_no: int) -> Path:
    return Path(run_dir) / _TRANSCRIPT_FORMAT.format(case_no)


def metadata_path(run_dir: Path) -> Path:
    return Path(run_dir) / METADATA_FILE


def read_json(path: Path) -> Optional[Any]:
    """Read one JSON document, or ``None`` when it is absent or unreadable.

    ``parse_float=Decimal`` throughout, the hook the loader uses: a money value
    written with a decimal point must come back as the literal that was written.

    An unreadable or corrupt document is reported as absent rather than raised,
    because the caller's choice in every case is the same — re-run that case.
    """
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)
    except (OSError, ValueError):
        return None


def _write_text_atomic(path: Path, text: str) -> None:
    """Write one file through a sibling temporary and a rename.

    A reader therefore never sees a half-written file, and an interrupt can lose
    at most the write in flight — never a file that exists but is truncated.
    Both the cache entry and its transcript go through here.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / (path.name + ".part")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_json(path: Path, document: Any) -> None:
    """Write one JSON document atomically.

    ``money.dumps_canonical`` because the document holds ``Decimal`` amounts and
    because the cache should be byte-stable: two identical results must produce
    two identical files.
    """
    _write_text_atomic(path, money.dumps_canonical(document))


def load_cached(run_dir: Path, case_no: int) -> Optional[Dict[str, Any]]:
    """One cached case result, or ``None`` when there is none to reuse."""
    document = read_json(case_cache_path(run_dir, case_no))
    if not isinstance(document, dict):
        return None
    if document.get("case_no") != case_no:
        return None
    if not document.get("ruling"):
        # A cache entry without a ruling is not a result. Re-running is the only
        # safe reading of it.
        return None
    return document


def cached_case_numbers(run_dir: Path) -> List[int]:
    """Every case number with a cached result, in ascending order.

    The transcript files sit beside the cache files and match the same glob, so
    the name pattern is matched rather than the suffix.
    """
    numbers = []
    for path in sorted(Path(run_dir).glob("case-*.json")):
        match = _CASE_FILE_RE.match(path.name)
        if match:
            numbers.append(int(match.group(1)))
    return sorted(numbers)


# --------------------------------------------------------------------------
# Replaying the advocates
# --------------------------------------------------------------------------
def file_sha256(path: Path) -> Optional[str]:
    """The SHA-256 of one file's bytes, or ``None`` when it cannot be read.

    Over the file rather than over a re-serialisation of it, because the claim
    is about the file. A transcript is written once, in this package's canonical
    form, and any other reading of "its digest" would be a claim about a round
    trip rather than about what is on disk.
    """
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


@dataclass(frozen=True)
class ReplayCheck:
    """What one run directory can supply, case by case, before anything is written.

    ``accepted`` holds a :class:`tribunal.pipeline.Replayable` per case -- the
    proof that every condition was checked and holds -- and ``refused`` holds
    the reason per case. A case in neither is one the source run never ran.

    The whole set is worked out before the caller writes or calls anything, so a
    replay into its own source directory has already read every entry it needs
    by the time the first file is touched.
    """

    source_dir: Path
    git_commit: Optional[str] = None
    model: Optional[str] = None
    prompts_sha256: Optional[str] = None
    accepted: Dict[int, Any] = field(default_factory=dict)
    refused: Dict[int, str] = field(default_factory=dict)

    @property
    def accepted_cases(self) -> List[int]:
        return sorted(self.accepted)

    @property
    def refused_cases(self) -> List[int]:
        return sorted(self.refused)

    @property
    def asked_about(self) -> List[int]:
        return sorted(set(self.accepted) | set(self.refused))

    @property
    def replayable(self) -> bool:
        """Whether any case at all can be replayed."""
        return bool(self.accepted)

    def provenance(self) -> Dict[str, Any]:
        """The source run, as the metadata and the cache entries carry it.

        ``replayed_cases`` here is every case the check **accepted**, which is
        not the same as every case a run replayed: the check runs before the run
        does, and a run stopped on its budget never reaches the rest. Callers
        that know what the run actually did pass the result through
        :func:`replay_block`, which is what the file and the summary carry.
        """
        return {
            "run_dir": str(self.source_dir),
            "git_commit": self.git_commit,
            "model": self.model,
            "prompts_sha256": self.prompts_sha256,
            "replayed_cases": list(self.accepted_cases),
            "refused_cases": list(self.refused_cases),
            "note": pipeline.REPLAY_NOTE,
        }


def replay_block(
    check: "ReplayCheck", outcomes: Sequence["CaseOutcome"]
) -> Dict[str, Any]:
    """The source block, with the case list this invocation actually replayed.

    One place for the correction, because three places read the list: the run's
    own metadata file, the printed summary and the viewer's footer. Left as the
    check's own list it named cases this run never reached -- on the first real
    replay, twenty-nine cases reused on a run that ran twenty-five before its
    token budget stopped it, with the four unrun cases still listed as if their
    advocates had been borrowed. A file and a summary that disagree about how
    many cases were replayed give a reader two answers to one question, and the
    summary is the one they see first.

    ``advocate_commits`` is the same correction applied to the other commit in
    the block. ``git_commit`` is what the source directory recorded, and a
    replay into that directory makes it the commit of the run that *copied* the
    advocates; the commit that *made* them travels per case, so the run-level
    block has to carry it or a reader has only the copying run's name. It is
    collected from the same outcomes as the case list, so the two describe one
    set of cases and a run stopped on its budget names no commit for the cases
    it never reached.
    """
    block = check.provenance()
    replayed = [outcome for outcome in outcomes if outcome.replayed]
    block["replayed_cases"] = [outcome.case_no for outcome in replayed]
    block["advocate_commits"] = sorted(
        {outcome.replayed_made_at for outcome in replayed if outcome.replayed_made_at}
    )
    return block


def read_replay_source(
    source_dir: Path,
    case_no: int,
    *,
    git_commit: Optional[str] = None,
    model: Optional[str] = None,
) -> pipeline.ReplaySource:
    """One case's recorded advocates, as the source directory holds them.

    Every field is read as it stands, and a missing file contributes ``None`` or
    an empty entry list rather than raising: "that run cannot supply this case"
    is a refusal with a reason, which is what the caller needs, and an exception
    would only move the same decision somewhere less visible.

    ``recorded_transcript_sha256`` comes from the source run's own cache entry
    and ``transcript_sha256`` from the file as it stands now, so a transcript
    edited after it was written is refused rather than replayed.
    """
    source_dir = Path(source_dir)
    document = load_cached(source_dir, case_no) or {}
    transcript_file = transcript_path(source_dir, case_no)

    transcript = read_json(transcript_file)
    entries: Tuple[Mapping[str, Any], ...] = ()
    if isinstance(transcript, Mapping):
        recorded = transcript.get("entries")
        if isinstance(recorded, list):
            entries = tuple(entry for entry in recorded if isinstance(entry, Mapping))

    return pipeline.ReplaySource(
        run_dir=str(source_dir),
        git_commit=git_commit,
        model=model,
        brief_sha256=document.get("brief_sha256"),
        policy_version=configuration_of(document)["policy_version"],
        transcript_sha256=file_sha256(transcript_file),
        recorded_transcript_sha256=document.get("transcript_sha256"),
        entries=entries,
    )


def source_advocate_commit(
    source_dir: Path, case_no: int, *, fallback: Optional[str] = None
) -> Optional[str]:
    """The commit whose run produced this case's recorded advocates.

    Read from the invocation history and not from ``run.json``. ``run.json`` is
    the **last** invocation's file, and a replay into the directory it reads from
    rewrites it before the next replay reads it: the second of two replays into
    one directory therefore records the first's commit as the source -- the
    commit that *copied* the advocates rather than the one that made them. That
    is how four cases came to name a commit whose judge produced nothing they
    reused. The history is append-only and is the file that survives, which is
    why it is the one that can answer this.

    An invocation that replayed did not produce the advocates it copied, so the
    answer is the last invocation that completed this case **without** replaying.
    ``fallback`` is used when the history cannot answer -- no such invocation, or
    a directory written before the history existed.
    """
    history = read_json(Path(source_dir) / INVOCATIONS_FILE)
    if not isinstance(history, list):
        return fallback
    found: Optional[str] = None
    for entry in history:
        if not isinstance(entry, Mapping):
            continue
        if entry.get("replay"):
            continue
        completed = (entry.get("cases") or {}).get("completed") or []
        if case_no in completed:
            commit = entry.get("git_commit")
            if isinstance(commit, str) and commit:
                found = commit
    return found if found is not None else fallback


def check_replay(
    source_dir: Path,
    cases: Sequence[int],
    *,
    model: str,
    prompts_dir: Path = PROMPTS_DIR,
    policy_version: Optional[int] = None,
    case_loader: Optional[Callable[[int], Mapping[str, Any]]] = None,
) -> ReplayCheck:
    """Ask, per case, whether a recorded run can supply this run's advocates.

    Reads only. No model is called and nothing is written, which is what makes
    this the question a caller can ask before it spends anything -- and what
    makes :func:`run_benchmark` able to ask it once, for every requested case,
    before the first file is written. A replay into the source run's own
    directory therefore reads everything it needs before it overwrites anything.

    ``policy_version`` is the version **this** run briefs at, and every source
    case's recorded version is compared with it. A replay rebuilds the case's
    brief at the version the source run recorded and hands the judge that brief,
    so the two must agree: a plain run pointed at a version-2 source would hand
    the judge a version-2 brief, record version 1, and write the result into the
    headline directory. The mismatch is a refusal of the whole replay rather
    than one reason per case, for the reason a missing source is -- twenty-nine
    identical findings would read as a property of the corpus instead of one of
    a path.

    ``None`` means the caller has no version of its own to compare the source
    against: the comparison is **skipped** rather than made, which is a different
    finding from a mismatch and refuses nothing. ``eval.verify_drafts`` passes
    nothing today; ``eval.baselines`` passes the registered set's version,
    because a set whose registration fixes a later version records its cases at
    that version and reading it as version 1 would be reading it as a run it is
    not. Every caller that would *write* a run passes its version, and
    :func:`run_benchmark` always does.

    ``case_loader`` is injectable so a test can drive the check without the
    manifest, the same way the brief builder is injectable in ``ui/build.py``.
    """
    source_dir = Path(source_dir)
    load = loader.load_case if case_loader is None else case_loader

    if not source_dir.is_dir():
        # Refused rather than reported case by case. A missing source would
        # otherwise produce one identical refusal per case, which reads as
        # twenty-nine findings about the corpus instead of one about a path.
        raise BenchmarkError(
            "there is no run directory at {0} to replay from".format(source_dir)
        )

    metadata = read_json(metadata_path(source_dir))
    if not isinstance(metadata, Mapping):
        metadata = {}

    check = ReplayCheck(
        source_dir=source_dir,
        git_commit=metadata.get("git_commit"),
        model=metadata.get("model"),
        prompts_sha256=metadata.get("prompts_sha256"),
    )

    for case_no in cases:
        source = read_replay_source(
            source_dir,
            case_no,
            git_commit=source_advocate_commit(
                source_dir, case_no, fallback=check.git_commit
            ),
            model=check.model,
        )
        if policy_version is not None and source.policy_version != policy_version:
            # Refused here rather than as one reason per case, and refused for
            # the whole replay: the source's version is a property of the run
            # being read, so every case would give the same finding. Left to
            # ``replay_verdict`` the refusal would be per case and the run would
            # then run those cases in full -- which is a different measurement
            # again, and the one thing a caller who asked for a replay did not
            # ask for.
            raise BenchmarkError(
                "the run at {0} was briefed at policy version {1} and this run "
                "briefs at version {2}: a replay rebuilds each case's brief at the "
                "version the source run recorded and hands the judge that brief, so "
                "the judge would see version {1} while this run recorded version "
                "{2}".format(source_dir, source.policy_version, policy_version)
            )
        try:
            replayable, reason = pipeline.replay_verdict(
                load(case_no), source, model=model, prompts_dir=prompts_dir
            )
        except Exception as exc:  # noqa: BLE001 - a case that cannot even be
            # loaded is a refusal with a reason, not an abort. The run continues
            # and runs that case in full, which is the whole point of refusing.
            check.refused[case_no] = "{0}: {1}".format(type(exc).__name__, exc)
            continue
        if replayable is None:
            check.refused[case_no] = reason
        else:
            check.accepted[case_no] = replayable

    return check


def render_replay_check(check: ReplayCheck) -> str:
    """The dry check: one line per case, then the totals.

    Printed before a paid replay, because asking costs a file read and not
    asking costs a run that discovers halfway through that it is running cases
    in full for reasons the caller never saw.
    """
    lines = [
        "replay check  {0}".format(check.source_dir),
        "  source commit   {0}".format(check.git_commit or "unrecorded"),
        "  source model    {0}".format(check.model or "unrecorded"),
        "  source prompts  {0}".format(str(check.prompts_sha256 or "unrecorded")[:16]),
        "",
    ]
    for case_no in check.asked_about:
        if case_no in check.accepted:
            replayable = check.accepted[case_no]
            lines.append(
                "  case {0}  accepted  {1} advocate call(s), brief {2}".format(
                    case_no,
                    len(replayable.rider_entries) + len(replayable.driver_entries),
                    replayable.brief_sha256[:16],
                )
            )
        else:
            lines.append(
                "  case {0}  REFUSED   {1}".format(case_no, check.refused[case_no])
            )
    lines.append("")
    lines.append(
        "  {0} accepted, {1} refused, of {2} asked about. No model was called and "
        "nothing was written.".format(
            len(check.accepted),
            len(check.refused),
            len(check.asked_about),
        )
    )
    return "\n".join(lines)


# What identifies a cache: each case's own provenance, never a count. A note that
# states counts about a cache can record this beside them and a reader can then
# ask whether the cache in front of them is the one the note describes. The
# counts cannot answer that question -- comparing a note's counts with the counts
# they are meant to be checked against assumes the answer.
CACHE_FINGERPRINT_FIELDS = ("brief_sha256", "prompts_sha256")


def cache_fingerprint(run_dir: Path, cases: Optional[Sequence[int]] = None) -> str:
    """A SHA-256 over every cached case's brief and prompts digest.

    The cache under ``runs/`` is untracked and mutable: every full run rewrites
    its counts. Anything a note records about those counts is therefore a dated
    statement about one particular cache, and it can only be checked against that
    cache. This is the value that says which cache a statement is about.

    It reads provenance and nothing else. A case whose entry predates a field
    contributes ``None`` for that field rather than dropping out, so the same
    digest set cannot be reached by two caches that recorded different things.
    """
    if cases is None:
        cases = cached_case_numbers(run_dir)

    entries = []
    for case_no in cases:
        document = load_cached(run_dir, case_no)
        if document is None:
            entries.append({"case_no": case_no, "cached": False})
            continue
        entry: Dict[str, Any] = {"case_no": case_no, "cached": True}
        for field_name in CACHE_FINGERPRINT_FIELDS:
            entry[field_name] = document.get(field_name)
        entries.append(entry)

    text = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------
def hash_directory(path: Path) -> str:
    """A SHA-256 over every file under ``path``, relative names and bytes both.

    The relative path is hashed alongside the bytes, so a rename or a move
    changes the digest even though no content did. Files are visited in sorted
    order, so the digest does not depend on directory order.
    """
    root = Path(path)
    if not root.is_dir():
        raise BenchmarkError("prompts directory does not exist: {0}".format(root))

    digest = hashlib.sha256()
    for file in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        if file.name in _DIGEST_EXCLUDED_NAMES or file.suffix in _DIGEST_EXCLUDED_SUFFIXES:
            continue
        digest.update(file.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _default_git_runner(arguments: Sequence[str]) -> Optional[str]:
    """Run one git command in the project root, or ``None`` when git is not there.

    Never raises: a machine without git, or a checkout without a repository,
    must still be able to produce a run — one whose provenance says the commit
    is unknown.
    """
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _status_arguments(runs_dir: Path) -> Tuple[str, ...]:
    """``git status`` arguments that ignore the cache directory.

    The cache lives under ``runs/``, which is not git-ignored, so the first case
    written makes the working tree dirty and every later run would record itself
    as dirty for a reason that has nothing to do with the code under test. The
    flag exists to say whether the **code** that produced the number is
    committed, so the runner's own output is excluded from the check.
    """
    arguments: List[str] = ["status", "--porcelain"]
    try:
        relative = Path(runs_dir).resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        # A cache outside the repository cannot affect the tree; no exclusion.
        return tuple(arguments)
    return tuple(arguments + ["--", ".", ":(exclude){0}".format(relative.as_posix())])


def git_state(
    git_runner: Optional[Callable[[Sequence[str]], Optional[str]]] = None,
    runs_dir: Path = RUNS_DIR,
) -> Dict[str, Any]:
    """The commit, and whether the working tree was clean at the time.

    The clean-tree flag is a tri-state and that matters: ``True`` clean,
    ``False`` dirty, ``None`` unknown because git could not be asked. A number
    produced from uncommitted code cannot be reproduced by anyone, including its
    author, so a report carrying one has to say so on its face — and so does a
    report whose tree state could not be established.
    """
    runner = _default_git_runner if git_runner is None else git_runner

    commit = runner(("rev-parse", "HEAD"))
    status = runner(_status_arguments(runs_dir))

    if isinstance(status, str):
        # Only the line terminators come off. ``strip()`` would also eat the
        # leading space of a porcelain line, and that space is the first of the
        # two status columns — it is what says whether a change is staged.
        detail_text = status.rstrip("\n")
        clean: Optional[bool] = detail_text.strip() == ""
        detail: Optional[str] = detail_text[:MAX_STATUS_CHARS] or None
    else:
        clean = None
        detail = None

    return {
        "git_commit": commit.strip() if isinstance(commit, str) else None,
        "working_tree_clean": clean,
        "working_tree_status": detail,
    }


def interpreter_version() -> str:
    """The Python that built a digest, as ``major.minor.micro``.

    Recorded beside ``git_commit`` because ``brief_sha256`` was once a function
    of the interpreter as well as of the repository: Python 3.12 changed
    ``sum()`` for floats to compensated summation, which moved the last bit of
    a mean that travels unrounded into the brief. Two caches whose digests
    disagree can be read against this field to tell code drift from interpreter
    drift.

    It is provenance and not a gate. The accumulation behind the brief is now
    pinned to a plain left-to-right sum, so a brief no longer varies with the
    interpreter and a mismatch does not make two digests incomparable — it only
    says which of them came from where.
    """
    return "{0}.{1}.{2}".format(*sys.version_info[:3])


def provenance(
    model: str,
    *,
    prompts_dir: Path = PROMPTS_DIR,
    runs_dir: Path = RUNS_DIR,
    git_runner: Optional[Callable[[Sequence[str]], Optional[str]]] = None,
    now: Callable[[], str] = lambda: datetime.now(timezone.utc).isoformat(),
    key_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Everything needed to say what produced a number.

    The answer key's digest comes from :mod:`eval.grade`, which is the only
    module that reads the key, so this function records the digest without
    opening the key itself.

    ``key_path`` is the key this run is graded against, and defaults to the
    corpus key. A run of a second development set records that set's digest
    instead: recording the corpus key's beside results graded against a
    different key would be provenance for the wrong measurement.
    """
    state = git_state(git_runner, runs_dir)
    return {
        "model": model,
        "git_commit": state["git_commit"],
        "working_tree_clean": state["working_tree_clean"],
        "working_tree_status": state["working_tree_status"],
        "prompts_dir": str(prompts_dir),
        "prompts_sha256": hash_directory(prompts_dir),
        "answer_key_sha256": (
            grade.answer_key_sha256() if key_path is None else grade.answer_key_sha256(key_path)
        ),
        "python_version": interpreter_version(),
        "recorded_at": now(),
    }


# --------------------------------------------------------------------------
# Staleness
# --------------------------------------------------------------------------
def current_brief_sha256(
    case_no: int,
    case_loader: Optional[Callable[[int], Mapping[str, Any]]] = None,
    ablate: Optional[str] = None,
    policy_version: int = policy_versions.BASE_VERSION,
) -> Optional[str]:
    """The digest of the brief this code builds for ``case_no`` right now.

    The same three steps :func:`tribunal.pipeline.run_case` takes, in the same
    order: ``brief.build_brief``, ``money.dumps_canonical``, then SHA-256 over
    those exact bytes. The serialiser is not interchangeable — any other
    produces a different digest for the same brief, and every cached case would
    be reported stale.

    ``case_loader`` is how the case is named, and defaults to the corpus
    manifest loader, which is what ``brief.build_brief`` uses. A development set
    passes its own, or the manifest refuses every one of its cases and the
    digest comes back ``None`` for all of them -- which reads as a set whose
    briefs cannot be rebuilt rather than as a set that has been checked.

    ``ablate`` names one ablation, or ``None`` for none, and it is passed to the
    builder so an ablated run's staleness check asks the question that run
    actually asked: the digest of the brief **with** the ablation applied.
    Comparing an ablated result against the unablated brief would report every
    case of it stale, which is a false finding about the run rather than a
    statement about this code.

    ``policy_version`` is the same kind of parameter for the same reason: a run
    at version N was given a brief built from the amended policy, so its
    staleness check has to rebuild that brief rather than version 1's. The
    default is version 1, which is what every caller before the switch asked
    for and what :class:`BriefStaleness` still asks for when no version is
    named.

    ``None`` when the brief cannot be built at all: a case file that has since
    moved, a policy that no longer parses. That is "cannot tell", and it is not
    "matches".
    """
    load = loader.load_case if case_loader is None else case_loader
    try:
        return brief.brief_digest(
            brief.build_brief_for_case(
                load(case_no), ablate=ablate, policy_version=policy_version
            )
        )[1]
    except Exception:  # noqa: BLE001 - a brief that cannot be built is not a match
        return None


def brief_digest_for(
    case_loader: Optional[Callable[[int], Mapping[str, Any]]] = None,
    ablate: Optional[str] = None,
    policy_version: int = policy_versions.BASE_VERSION,
) -> Optional[Callable[[int], Optional[str]]]:
    """The current-brief digest function for one set's cases.

    ``None`` means the corpus loader, which is what :class:`BriefStaleness`
    already defaults to. A development set needs its own: the manifest cannot
    load a case it does not list, so every one of the set's cached results would
    read as a brief that cannot be rebuilt, and the set would report itself as a
    mixed set -- not one measurement -- when in fact every brief matches.

    ``ablate`` travels with the loader rather than being applied afterwards, for
    the reason :func:`current_brief_sha256` gives: the digest has to be of the
    brief that run's agents were given. ``policy_version`` travels with it for
    that same reason. All three default to nothing, and the triple of defaults
    is the only case that returns ``None`` -- "use the built-in corpus digest"
    -- so a caller naming any one of them gets a function.
    """
    if (
        case_loader is None
        and ablate is None
        and policy_version == policy_versions.BASE_VERSION
    ):
        return None
    return lambda case_no: current_brief_sha256(
        case_no,
        case_loader=case_loader,
        ablate=ablate,
        policy_version=policy_version,
    )


def current_prompts_sha256(prompts_dir: Path = PROMPTS_DIR) -> Optional[str]:
    """The digest of the prompt directory as it stands.

    The same value a run records as ``prompts_sha256``, computed the same way
    over the same directory, so the two are comparable. The directory rather than
    one file, because what an agent was given is the prompt set: the advocate
    template, both stances and the judge prompt. Editing any of them changes what
    an agent was told to do.

    ``None`` when the directory cannot be read. That is "cannot tell", and it is
    not "matches".
    """
    try:
        return hash_directory(prompts_dir)
    except Exception:  # noqa: BLE001 - a prompt set that cannot be read is not a match
        return None


class BriefStaleness:
    """Answers "does this cached result still belong to this code?" per case.

    Two channels answer it, not one. The **brief** channel compares
    ``brief_sha256``, the digest of the exact bytes the agents were handed, so a
    moved brief means the facts changed. The **prompt** channel compares, per
    role, the ``system_sha256`` and ``user_sha256`` the recorded calls carry
    against what this code renders now, so a moved prompt means an agent's
    instructions changed. Either one takes the result out of this code's
    measurements, and they are kept apart because they call for different
    responses.

    The cache entry's own ``prompts_sha256`` is a third thing and is neither
    channel: it digests the prompt **directory**, so it moves when a file is
    added that no recorded call ever used. It stays in the record as history and
    is deliberately not what the prompt channel asks.

    Both channels are memoised: the brief digest per case, because rebuilding a
    brief is a file read per case, and each case's transcript entries once,
    however many questions are asked about that case. The brief digest's memo is
    keyed by the case **and the policy version** together, because the digest is
    of a brief built at one version and serving it to a question asked at
    another would answer the wrong question.
    """

    def __init__(
        self,
        digest: Optional[Callable[[int], Optional[str]]] = None,
        run_dir: Optional[Path] = None,
        entries_for: Optional[
            Callable[[int], Optional[Sequence[Mapping[str, Any]]]]
        ] = None,
        prompts_dir: Path = PROMPTS_DIR,
        precedents: Optional[Mapping[str, Any]] = None,
        policy_version: int = policy_versions.BASE_VERSION,
    ) -> None:
        # An injected digest has the version already closed over -- that is what
        # :func:`brief_digest_for` builds -- so it is used as it stands. The
        # built-in one takes the version as an argument, so it is bound here.
        self._digest = (
            (lambda case_no: current_brief_sha256(case_no, policy_version=policy_version))
            if digest is None
            else digest
        )
        self._policy_version = policy_version
        self._run_dir = None if run_dir is None else Path(run_dir)
        self._entries_for = entries_for
        self._prompts_dir = Path(prompts_dir)
        # The precedent library's chain head and note digest as this run knows
        # them, or ``None`` when the switch is off. ``None`` is what keeps a
        # plain run's staleness reading exactly what it was: the third channel
        # is silent rather than empty.
        self._precedents = None if precedents is None else dict(precedents)
        self._current: Dict[Tuple[int, int], Optional[str]] = {}
        self._entries: Dict[int, Optional[Sequence[Mapping[str, Any]]]] = {}

    def current_digest(self, case_no: int) -> Optional[str]:
        key = (case_no, self._policy_version)
        if key not in self._current:
            self._current[key] = self._digest(case_no)
        return self._current[key]

    def recorded_entries(self, case_no: int) -> Optional[Sequence[Mapping[str, Any]]]:
        """The transcript entries recorded for one case, memoised.

        ``None`` when they cannot be read at all, which is a different answer
        from an empty transcript and is kept different: the first is "cannot
        tell", the second is a finding.
        """
        if case_no not in self._entries:
            self._entries[case_no] = self._read_entries(case_no)
        return self._entries[case_no]

    def _read_entries(self, case_no: int) -> Optional[Sequence[Mapping[str, Any]]]:
        if self._entries_for is not None:
            return self._entries_for(case_no)
        if self._run_dir is None:
            return None
        payload = read_json(transcript_path(self._run_dir, case_no))
        entries = payload.get("entries") if isinstance(payload, Mapping) else None
        return entries if isinstance(entries, list) else None

    def prompt_comparison(self, case_no: int) -> Tuple[str, str]:
        """The prompt channel for one case, read from what its calls recorded.

        The recorded calls carry the digest of the system prompt each was given,
        and the advocates carry the digest of the brief beside it. Those are
        compared, **per role**, with what this code renders now -- the same
        comparison a replay makes for the advocates and the recorded-drafts
        measurement makes for the judge. A prompt file no recorded call used is
        therefore not a finding about this case, while a one-byte change to any
        prompt a recorded call did use is.
        """
        entries = self.recorded_entries(case_no)
        if entries is None:
            return pipeline.PROMPT_UNCHECKED, (
                "no transcript for case {0} could be read, so the prompts its "
                "calls were given cannot be compared".format(case_no)
            )
        return pipeline.compare_recorded_prompts(
            entries,
            prompts_dir=self._prompts_dir,
            advocate_user_sha256=self.current_digest(case_no),
        )

    def prompts_moved(self, case_no: int, document: Mapping[str, Any]) -> bool:
        """Whether a prompt a recorded call was given has moved since.

        The cache entry's own ``prompts_sha256`` is deliberately not consulted.
        That is a digest of the prompt **directory**, so it moves when a file is
        merely added to the directory -- which is not a statement about what any
        agent was given. It is still recorded, as history.
        """
        if not isinstance(document, Mapping):
            return False
        return self.prompt_comparison(case_no)[0] == pipeline.PROMPT_MOVED

    def brief_moved(self, case_no: int, document: Mapping[str, Any]) -> bool:
        """Whether the brief digest was recorded and no longer matches."""
        if not isinstance(document, Mapping):
            return False
        recorded = document.get("brief_sha256")
        if not isinstance(recorded, str) or not recorded:
            return False
        current = self.current_digest(case_no)
        return current is not None and recorded != current

    def brief_unchecked(self, case_no: int, document: Mapping[str, Any]) -> bool:
        """Whether the brief half of the check could not be made for this entry.

        Either the entry records no brief digest, so the file cannot say what it
        was built from, or the brief cannot be rebuilt now.
        """
        if not isinstance(document, Mapping):
            return True
        recorded = document.get("brief_sha256")
        if not isinstance(recorded, str) or not recorded:
            return True
        return self.current_digest(case_no) is None

    def prompts_unchecked(self, case_no: int, document: Mapping[str, Any]) -> bool:
        """Whether the prompt half of the check could not be made for this entry.

        Not the same question as whether the entry recorded a directory digest.
        What an agent was given lives in the transcript, so a result whose calls
        carry no digest, or whose transcript cannot be read, is one this code
        cannot answer for. That is "cannot tell", and it is not a match.
        """
        if not isinstance(document, Mapping):
            return True
        return self.prompt_comparison(case_no)[0] == pipeline.PROMPT_UNCHECKED

    def precedents_moved(self, case_no: int, document: Mapping[str, Any]) -> bool:
        """Whether the precedent library this result was produced against moved.

        ``None`` -- the switch off -- never moves, so every cached result in a
        plain run reads exactly as it read before this channel existed. With the
        switch on, a case is stale unless the library it recorded is the library
        this run has, and that includes a case that recorded none at all: a
        result produced without the block is not a result produced with it.
        """
        if self._precedents is None:
            return False
        if not isinstance(document, Mapping):
            return False
        return configuration_of(document)["precedents"] != self._precedents

    def moved_for(self, case_no: int, document: Mapping[str, Any]) -> Tuple[str, ...]:
        """Which recorded digests moved, named, in a fixed order.

        Empty when nothing recorded has moved. More than one may be present: a
        result produced by an older brief under older prompts, against an
        earlier library, is stale for all three reasons.
        """
        moved: List[str] = []
        if self.brief_moved(case_no, document):
            moved.append(grade.MOVED_BRIEF)
        if self.prompts_moved(case_no, document):
            moved.append(grade.MOVED_PROMPTS)
        if self.precedents_moved(case_no, document):
            moved.append(grade.MOVED_PRECEDENTS)
        return tuple(moved)

    def status_of(self, case_no: int, document: Mapping[str, Any]) -> str:
        """``current``, ``stale`` or ``unknown`` for one cache entry.

        A moved digest is a finding, whichever channel it is in, and a finding
        beats not being able to tell. Only when nothing recorded has moved does
        the question become whether every channel could actually be checked -- an
        entry whose transcript cannot be read is not an entry whose prompts are
        known to match.
        """
        if self.moved_for(case_no, document):
            return grade.STALENESS_STALE
        if self.brief_unchecked(case_no, document) or self.prompts_unchecked(
            case_no, document
        ):
            return grade.STALENESS_UNKNOWN
        return grade.STALENESS_CURRENT


def brief_staleness(
    run_dir: Path,
    cases: Sequence[int],
    checker: Optional[BriefStaleness] = None,
) -> grade.Staleness:
    """Check every cached case in ``cases`` against the code as it stands now.

    Returns a :class:`eval.grade.Staleness` with ``checked`` set, so a report
    built from it can say the check happened rather than merely that it found
    nothing. A case with no cache entry is not checked and is not reported: it
    produced no result to be stale.

    The three channels are collected separately as well as as a union, so a
    report can say which of them moved rather than only that something did. The
    prompt channel is answered from each case's own transcript -- from the
    ``system_sha256`` and ``user_sha256`` its calls recorded -- so the default
    checker is built with the run directory it is reading. The precedents
    channel is filled from the checker like the other two: leaving it empty made
    ``stale_precedents`` always ``()``, so the "library has moved" line and the
    ``library moved:`` summary line were unreachable however far the library had
    moved.
    """
    checker = BriefStaleness(run_dir=run_dir) if checker is None else checker
    stale: List[int] = []
    unknown: List[int] = []
    stale_brief: List[int] = []
    stale_prompts: List[int] = []
    stale_precedents: List[int] = []
    unchecked_prompts: List[int] = []
    for case_no in cases:
        document = load_cached(run_dir, case_no)
        if document is None:
            continue
        if checker.prompts_unchecked(case_no, document):
            unchecked_prompts.append(case_no)
        status = checker.status_of(case_no, document)
        if status == grade.STALENESS_STALE:
            stale.append(case_no)
            moved = checker.moved_for(case_no, document)
            if grade.MOVED_BRIEF in moved:
                stale_brief.append(case_no)
            if grade.MOVED_PROMPTS in moved:
                stale_prompts.append(case_no)
            if grade.MOVED_PRECEDENTS in moved:
                stale_precedents.append(case_no)
        elif status == grade.STALENESS_UNKNOWN:
            unknown.append(case_no)
    return grade.Staleness(
        checked=True,
        stale=tuple(sorted(stale)),
        unknown=tuple(sorted(unknown)),
        stale_brief=tuple(sorted(stale_brief)),
        stale_prompts=tuple(sorted(stale_prompts)),
        unchecked_prompts=tuple(sorted(unchecked_prompts)),
        stale_precedents=tuple(sorted(stale_precedents)),
    )


# --------------------------------------------------------------------------
# One case
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class TokenSplit:
    """One measurement's tokens, by kind, as the provider reports them.

    A single total cannot cost a run. Output is priced at four times input on
    the decided model, so two runs that consumed the same number of tokens can
    differ by a factor in what they cost, and only the split tells them apart.
    The split is therefore what is recorded wherever a total is needed, and the
    total is derived from it rather than stored beside it — a stored total is a
    second place the same arithmetic can be wrong.

    ``reasoning_tokens`` is reported by this provider as a *breakdown* of
    ``completion_tokens`` rather than a third quantity, so it is never added in:
    counting it again would overstate the spend and trip a budget early.
    ``cached_tokens`` is a breakdown of the prompt and is likewise not added.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0

    @property
    def billed(self) -> int:
        """The tokens the provider charges for: the prompt plus the completion.

        Delegated rather than re-implemented, because a rule stated twice is a
        rule that can disagree with itself. :func:`billed_tokens` is the one
        statement of it.
        """
        return billed_tokens(self.prompt_tokens, self.completion_tokens)

    def __add__(self, other: "TokenSplit") -> "TokenSplit":
        """Two measurements as one, so a run's total is a sum of its parts."""
        return TokenSplit(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
        )

    def as_dict(self) -> Dict[str, int]:
        """The shape written to disk, with the derived total included.

        ``total_tokens`` keeps the name the per-case cache entries already use,
        so a reader of either file is not made to learn a second name for the
        same number.
        """
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cached_tokens": self.cached_tokens,
            "total_tokens": self.billed,
        }

    @classmethod
    def from_mapping(cls, mapping: Optional[Mapping[str, Any]]) -> "TokenSplit":
        """Read back what :meth:`as_dict` wrote, tolerating an older record.

        A record written before one of these fields was kept contributes zero
        for it rather than dropping out, so a cache holding entries of two ages
        still totals.
        """
        values = mapping or {}
        return cls(
            prompt_tokens=_as_int(values.get("prompt_tokens")),
            completion_tokens=_as_int(values.get("completion_tokens")),
            reasoning_tokens=_as_int(values.get("reasoning_tokens")),
            cached_tokens=_as_int(values.get("cached_tokens")),
        )


@dataclass(frozen=True)
class CaseOutcome:
    """What happened to one case in one invocation of the runner."""

    case_no: int
    status: str
    wall_seconds: float = 0.0
    # The split, not a bare total. A case that failed after its calls were made
    # consumed tokens too, and only the split says how much of that was output.
    tokens: TokenSplit = field(default_factory=TokenSplit)
    matched: Optional[bool] = None
    failed_agent: Optional[str] = None
    failure_reason: Optional[str] = None
    failure_kind: Optional[str] = None
    failure_detail: Optional[str] = None
    ruling: Optional[Any] = None
    # Set only for a case whose result was read back from the cache, and only
    # when the code this builds for it is no longer the code it was produced
    # from. A cached result the reader is told to trust while the code has moved
    # on is the whole defect this field exists to prevent.
    brief_status: Optional[str] = None
    # Which recorded digests moved, named. Carried beside the status rather than
    # folded into it, because "the brief changed" and "the prompt changed" call
    # for different responses, and a progress line that blamed the brief for a
    # moved prompt would send the reader to the wrong file.
    stale_moved: Tuple[str, ...] = ()
    # Set only for a case whose advocates came from another run. ``tokens`` above
    # is then this run's own bill, which is the judge's alone, and
    # ``replayed_tokens`` is what the borrowed calls cost the run that made them.
    # The two are reported apart and never summed: adding them would charge this
    # run for tokens it did not spend.
    replayed_from: Optional[str] = None
    replayed_tokens: TokenSplit = field(default_factory=TokenSplit)
    # The commit whose run *made* the advocates this case reused, which is not
    # always the commit ``replayed_from`` names. A replay into the directory it
    # reads from rewrites that directory's metadata before the next replay reads
    # it, so the directory's recorded commit is then the commit that *copied*
    # them; a reader told only that one would conclude the advocates were
    # produced by the copying run.
    replayed_made_at: Optional[str] = None

    @property
    def replayed(self) -> bool:
        return self.replayed_from is not None

    @property
    def total_tokens(self) -> int:
        """Every token this case was billed for, prompt and completion together."""
        return self.tokens.billed

    @property
    def ok(self) -> bool:
        return self.status in (STATUS_COMPLETED, STATUS_CACHED)

    @property
    def verdict(self) -> str:
        """The short word the progress line prints.

        A failure prints its KIND rather than the word FAILED, because the kind
        is the thing a person watching the terminal needs: ``TIMEOUT`` and
        ``SHAPE`` look identical under a generic label and call for opposite
        responses.
        """
        if self.status == STATUS_FAILED:
            return self.failure_kind or "FAILED"
        if self.status == STATUS_CACHED:
            return "cached"
        if self.matched:
            return "match"
        return "MISS"


def billed_tokens(prompt_tokens: Any, completion_tokens: Any) -> int:
    """The tokens a provider bills for: the prompt plus the completion.

    ``reasoning_tokens`` is reported by the API as a *breakdown* of
    ``completion_tokens`` rather than something added to it, so counting it
    again would overstate the spend and trip a budget early. It is recorded
    separately for exactly that reason.
    """
    return int(prompt_tokens or 0) + int(completion_tokens or 0)


def _as_seconds(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _scoreable(value: Any, case_no: int) -> Optional[grade.Ruling]:
    """A produced ruling as the grader can score it, or ``None`` when it cannot.

    ``eval.grade`` accepts the judge's result object or the bare POL-GEN-03
    object and raises on anything else. A model that returned a JSON array or a
    bare string has broken its output contract, and that is a measurement to
    report rather than an exception to abort the run with — so an unscoreable
    record is handed over as ``None``, which the grader scores as four failed
    fields. The malformed value itself is still in the cache and the raw body is
    still in the transcript; nothing is thrown away, only declined for scoring.
    """
    if value is None:
        return None
    try:
        return grade.produced_from_mapping(value, case_no)
    except grade.GradeError:
        return None


def _match_for(case_no: int, ruling: Any, expected: Optional[grade.Ruling]) -> Optional[bool]:
    """Whether a produced ruling is a four-field match, judged by eval.grade."""
    if ruling is None or expected is None:
        return None
    produced = _scoreable(ruling, case_no)
    if produced is None:
        return False
    return grade.score_case(case_no, expected, produced).exact


def failure_kind_for(exc: BaseException) -> str:
    """Which kind of failure an exception raised by the transport represents.

    A read timeout surfaces as a bare ``TimeoutError`` — ``urlopen`` raises it
    from ``response.read()``, where it is not wrapped in a ``URLError`` and so
    is not converted into a ``TransportError``.

    ``socket.timeout`` is checked as well, and that is not belt-and-braces: on
    Python 3.10 and later it *is* ``TimeoutError``, but on 3.9 it is a separate
    ``OSError`` subclass, so ``isinstance(exc, TimeoutError)`` alone would let a
    real read timeout fall through to the transport kind on an interpreter this
    project still runs on. Measured on 3.9.6: ``socket.timeout is TimeoutError``
    is ``False`` there and ``True`` on 3.13.

    A *connect* timeout arrives as a ``TransportError`` wrapping a ``URLError``
    whose reason is a timeout. It is classified as a transport failure on
    purpose: nothing was generated, so nothing was wasted, and the advice a
    timeout carries — wait longer — would be wrong. The message still says
    "timed out", so the distinction is visible even where the kind does not
    separate it.

    A **deadline** is its own kind, and it is checked first. Two layers raise
    one — ``llm.DeadlineExceededError`` when one call spends its budget, and
    ``pipeline.CaseDeadlineExceeded`` when a whole case does — and a reader acts
    on both the same way. Neither is a timeout: nothing waited too long, the run
    stopped itself, so "wait longer" is the wrong advice and the limit is the
    thing to change. They are also deliberately not subclasses of
    ``TimeoutError``; the isinstance order here is written out anyway so that a
    future subclass of both cannot be demoted into the kind whose advice is
    exactly wrong for it.
    """
    if isinstance(exc, KeyboardInterrupt):
        return FAILURE_INTERRUPTED
    # Both deadlines before the timeout, and deliberately. A deadline is an
    # ``LLMError`` or a ``PipelineError`` rather than a ``TimeoutError``, but the
    # order is stated anyway so a future subclass of either that also inherits
    # from ``TimeoutError`` cannot be demoted into the kind whose advice --
    # "wait longer" -- is exactly wrong for it.
    if isinstance(exc, (llm.DeadlineExceededError, pipeline.CaseDeadlineExceeded)):
        return FAILURE_DEADLINE
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return FAILURE_TIMEOUT
    return FAILURE_TRANSPORT


def failure_reason_for(kind: str, detail: str) -> str:
    """The recorded reason for a failure: the kind leads, the evidence follows.

    The kind leads so a reader scanning a failures list can tell the three apart
    without parsing the message. The detail follows unchanged, because it is the
    evidence and must not be replaced by a summary of it.
    """
    return "{0}: {1}. {2}".format(kind, FAILURE_NOTE[kind], detail)


def run_one_case(
    case_no: int,
    *,
    client: Any,
    prompts_dir: Path,
    expected: Optional[grade.Ruling],
    case_provenance: Optional[Mapping[str, Any]] = None,
    case_deadline_seconds: float = pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
    case_loader: Optional[Callable[[int], Mapping[str, Any]]] = None,
    loaded_case: Optional[Mapping[str, Any]] = None,
    replay: Optional[Any] = None,
    judge_votes: int = pipeline.DEFAULT_JUDGE_VOTES,
    verify_drafts: bool = False,
    ablate: Optional[str] = None,
    precedents: Optional[Any] = None,
    policy_version: int = policy_versions.BASE_VERSION,
    amount_rule: str = pipeline.DEFAULT_AMOUNT_RULE,
    configuration: Optional[Mapping[str, Any]] = None,
    events_log: Optional[Any] = None,
    parallel_calls: bool = False,
    early_majority: bool = False,
    integrity_gate: bool = False,
    advocate_effort: str = pipeline.ADVOCATE_EFFORT_DEFAULT,
) -> Tuple[CaseOutcome, Optional[Dict[str, Any]], Optional[str]]:
    """Run one case. Returns ``(outcome, cache document, transcript json)``.

    A case that fails after the client exhausted its retries comes back as a
    failed outcome with no cache document, so the caller can continue and a
    re-run retries exactly that case. A missing credential or an unprovisioned
    model is raised instead: those are not case failures, they are the same
    failure for every case, and continuing would only waste the wall clock.

    A failure is classified rather than merely described. A timeout and an
    unusable answer call for opposite responses, so the record says which one
    happened instead of leaving it to be read out of the exception's text. A
    deadline is a third kind for the same reason: the client or the case gave up
    at a bound the run set for itself, which is answered by changing the bound.

    ``case_deadline_seconds`` is passed straight through to
    :func:`tribunal.pipeline.run_case`. It is a parameter here rather than a
    module constant so a test can shorten it and see the failure the deadline
    produces.

    ``case_provenance`` is recorded inside the cache entry, beside the brief
    digest it belongs to. Provenance kept only in the run's own metadata file is
    provenance the next invocation destroys.

    ``loaded_case`` is a case already in hand, which is how a converted external
    case is arbitrated: it is loaded through its own explicit path and is absent
    from the manifest, so it cannot be named by number. Only the source of the
    case changes. :func:`tribunal.pipeline.run_loaded_case` is the same body
    :func:`tribunal.pipeline.run_case` runs, so every guard is the same guard and
    there is no second, weaker path through this runner.

    ``case_loader`` is the other half of that: a case that is absent from the
    manifest but *is* named by number, because it belongs to a set carrying its
    own index. It is passed straight to :func:`tribunal.pipeline.run_case` and
    defaults to ``None``, which is the corpus loader, so a corpus case is loaded
    exactly as before. A replayed case takes this path too -- only its advocates
    come from elsewhere.

    ``ablate`` names one ablation of the brief, or ``None`` for none, and it is
    passed straight through for the same reason ``judge_votes`` is: there is one
    arbitration body and this is not a second one. It is refused together with
    ``replay`` below, because a replay hands the judge the brief this code builds
    for the case, and that brief would not be ablated.

    ``replay`` is a :class:`tribunal.pipeline.Replayable`, which only
    :func:`check_replay` produces and which carries the proof that the source
    run's brief, prompts, model and recorded answers all agree with this code.
    When it is given, the advocates are not called and only the judge is, through
    :func:`tribunal.pipeline.replay_case`.

    ``parallel_calls`` and ``early_majority`` are passed straight through on
    every path, the replayed and the external one included, for the same reason
    ``amount_rule`` is: a switch accepted on the command line and dropped on one
    of these paths would be a switch that said it was on and was not. Which of
    the two a case may use, and when the rule fires, is decided in
    :func:`tribunal.pipeline._run_judge_vote`.

    ``integrity_gate`` is passed straight through on every path too, and for the
    same reason: a case whose route-deviation record trips ``POL-RD-10(2)`` or
    ``(4)`` is escalated by code with no call made, and a path that dropped the
    switch would rule on the record the gate exists to refuse.

    ``advocate_effort`` reaches the two full-arbitration paths and not the
    replay. A replay calls no advocate -- it copies a recorded run's advocate
    entries and calls only the judge -- so there is no advocate request for the
    switch to change, and it is refused beside a replay rather than silently
    dropped. On the two paths that do call the advocates it is passed on for the
    reason the others are: a switch this runner accepts is a switch it honours.
    """
    if replay is not None and advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT:
        # Refused for the reason :func:`run_benchmark` refuses it, and checked
        # here as well because this is the layer that would otherwise drop it
        # quietly: :func:`tribunal.pipeline.replay_case` makes no advocate call,
        # so a switched replay would be a run whose directory named a setting its
        # advocates were never asked under.
        raise BenchmarkError(
            "a run under --advocate-effort {0} cannot replay: replay reuses a "
            "recorded run's advocates and calls only the judge".format(
                advocate_effort
            )
        )
    if replay is not None and loaded_case is not None:
        # Refused, not merely unused. Replay reuses another run's advocates for
        # a corpus case whose brief is byte-identical to theirs; an external
        # case has no answer-key entry and its own brief has changed, so there
        # is nothing byte-identical to reuse and no key to score the result
        # against. Saying so is better than silently running it in full, which
        # would look like a replay that found nothing to do.
        raise BenchmarkError(
            "an external case cannot be replayed: replay reuses a recorded "
            "run's advocates, and this case is arbitrated in full"
        )
    if replay is not None and ablate is not None:
        # Refused for the reason the ablation is refused with the replay flags
        # on the command line, and checked here as well because this is the
        # layer that would otherwise do the wrong thing quietly.
        # :func:`tribunal.pipeline.replay_case` builds the case's brief with no
        # ablation -- it must, because the advocates it reuses were given the
        # unablated brief -- so a replay of an ablated run would hand the judge a
        # brief that is not the one the run is measuring.
        raise BenchmarkError(
            "an ablated run cannot replay: replay hands the judge the brief this "
            "code builds for the case, which is not ablated, while the advocates "
            "it reuses were given an ablated brief"
        )

    started = time.monotonic()
    try:
        if replay is not None:
            result = pipeline.replay_case(
                client,
                replay=replay,
                case_deadline_seconds=case_deadline_seconds,
                judge_votes=judge_votes,
                events_log=events_log,
                prompts_dir=prompts_dir,
                verify_drafts=verify_drafts,
                # Only the judge is called here, so the rule is passed on rather
                # than dropped: a switch accepted on the command line and not
                # applied on this path would be a run whose directory names a
                # rule its drafts were not held to.
                amount_rule=amount_rule,
                # And the parallel switch, on the same rule: a replay calls the
                # judge's drafts, so a switch accepted here and dropped on this
                # path would be a switch that said it was on and was not.
                parallel_calls=parallel_calls,
                # And the early-majority switch, for the same reason again: a
                # replay builds a panel of drafts, so the rule has something to
                # say here exactly as it does on a full run.
                early_majority=early_majority,
                # And the record-integrity gate, on the same rule once more: a
                # replay rebuilds the case's brief, so the gate has the record
                # it reads and a switch dropped here would rule on a record a
                # full run would escalate.
                integrity_gate=integrity_gate,
            )
        elif loaded_case is None:
            result = pipeline.run_case(
                case_no,
                client,
                prompts_dir=prompts_dir,
                case_deadline_seconds=case_deadline_seconds,
                case_loader=case_loader,
                judge_votes=judge_votes,
                events_log=events_log,
                verify_drafts=verify_drafts,
                ablate=ablate,
                precedents=precedents,
                policy_version=policy_version,
                amount_rule=amount_rule,
                parallel_calls=parallel_calls,
                early_majority=early_majority,
                integrity_gate=integrity_gate,
                # And which reasoning effort the two advocates' requests carry.
                # Only the judge is called on the replay path above, which is why
                # the switch is refused beside a replay rather than passed here.
                advocate_effort=advocate_effort,
            )
        else:
            # A converted external case, already loaded through its own explicit
            # path. Same pipeline body, same guards: run_loaded_case is the
            # function run_case delegates to, not a parallel implementation.
            result = pipeline.run_loaded_case(
                loaded_case,
                client,
                prompts_dir=prompts_dir,
                case_deadline_seconds=case_deadline_seconds,
                judge_votes=judge_votes,
                events_log=events_log,
                verify_drafts=verify_drafts,
                ablate=ablate,
                precedents=precedents,
                policy_version=policy_version,
                amount_rule=amount_rule,
                parallel_calls=parallel_calls,
                early_majority=early_majority,
                integrity_gate=integrity_gate,
                advocate_effort=advocate_effort,
            )
    except (llm.MissingAPIKeyError, llm.ModelNotProvisionedError) as exc:
        # Not provisioned and no credential are the same failure for every
        # case, so the runner lets them out rather than recording twenty-nine
        # identical failures. They are logged first: the log is the record of
        # what this invocation hit, and a run that died at its first case must
        # still be able to say why. The 2026-09-27 replay died this way.
        if events_log is not None:
            events_log.record(
                events.EVENT_CASE_FAILED,
                case_no=case_no,
                failure_kind=failure_kind_for(exc),
                failed_agent=None,
                detail="{0}: {1}".format(type(exc).__name__, exc),
            )
        raise
    except Exception as exc:  # noqa: BLE001 - any transport or parse failure is a case failure
        kind = failure_kind_for(exc)
        detail = "{0}: {1}".format(type(exc).__name__, exc)
        if events_log is not None:
            events_log.record(
                events.EVENT_CASE_FAILED,
                case_no=case_no,
                failure_kind=kind,
                failed_agent=None,
                detail=detail,
            )
        return (
            CaseOutcome(
                case_no=case_no,
                status=STATUS_FAILED,
                wall_seconds=time.monotonic() - started,
                failure_kind=kind,
                failure_detail=detail,
                failure_reason=failure_reason_for(kind, detail),
            ),
            None,
            None,
        )

    wall = time.monotonic() - started
    tokens = TokenSplit(
        prompt_tokens=_as_int(result.prompt_tokens),
        completion_tokens=_as_int(result.completion_tokens),
        reasoning_tokens=_as_int(result.reasoning_tokens),
        cached_tokens=_as_int(result.cached_tokens),
    )

    # The borrowed advocates' usage, kept apart from ``tokens`` at the moment
    # they are read rather than at the moment they are totalled. A case whose
    # judge failed still had its advocates replayed, so this is filled in for
    # both branches: the run's bill and the run's provenance are different
    # questions and a failure is not a reason to answer only one of them.
    replayed_from = result.replay.run_dir if result.replay is not None else None
    # Recorded apart from ``replayed_from`` because a replay into its own source
    # directory makes the directory's recorded commit the copying run's. The
    # commit that made these advocates is the one the source entry recorded.
    replayed_made_at = result.replay.git_commit if result.replay is not None else None
    replayed_tokens = (
        TokenSplit(
            prompt_tokens=_as_int(result.replay.prompt_tokens),
            completion_tokens=_as_int(result.replay.completion_tokens),
            reasoning_tokens=_as_int(result.replay.reasoning_tokens),
            cached_tokens=_as_int(result.replay.cached_tokens),
        )
        if result.replay is not None
        else TokenSplit()
    )

    if not result.ok or result.ruling is None:
        detail = result.failure_reason or "the run produced no ruling"
        if events_log is not None:
            events_log.record(
                events.EVENT_CASE_FAILED,
                case_no=case_no,
                failure_kind=FAILURE_SHAPE,
                failed_agent=result.failed_agent,
                detail=detail,
            )
        return (
            CaseOutcome(
                case_no=case_no,
                status=STATUS_FAILED,
                wall_seconds=wall,
                # Recorded although this case produced no ruling. Its calls were
                # made and billed before the answer turned out to be unusable,
                # so a run recording nothing here would understate what it cost
                # — and the split is what says how much of that was output.
                tokens=tokens,
                failed_agent=result.failed_agent,
                failure_kind=FAILURE_SHAPE,
                failure_detail=detail,
                failure_reason=failure_reason_for(FAILURE_SHAPE, detail),
                replayed_from=replayed_from,
                replayed_tokens=replayed_tokens,
                replayed_made_at=replayed_made_at,
            ),
            None,
            result.transcript_json,
        )

    matched = _match_for(case_no, result.ruling, expected)
    provenance_fields = dict(case_provenance or {})
    if configuration is None:
        # What this case was run under, so the entry says it on its own.
        configuration = configuration_document(
            judge_votes=judge_votes,
            verify_drafts=verify_drafts,
            ablation=ablate,
            policy_version=policy_version,
        )
        if amount_rule != pipeline.DEFAULT_AMOUNT_RULE:
            configuration = dict(configuration, amount_rule=amount_rule)
        if advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT:
            # Added on the same rule :func:`run_benchmark` adds it: a caller that
            # built its own configuration object has said so already, and one
            # that did not gets the switch named rather than silently omitted.
            configuration = dict(configuration, advocate_effort=advocate_effort)
    document = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "case_no": case_no,
        "model": result.model,
        "configuration": dict(configuration),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "brief_sha256": result.brief_sha256,
        # The commit, the prompts digest and the interpreter under which THIS
        # result was produced, beside the digest of the brief it was given. The
        # four together are what makes the entry self-describing: a later reader
        # can tell both what produced it and whether the code has since moved
        # on. The interpreter earns its place because the brief's bytes were
        # once a function of it, so a digest that disagrees may be interpreter
        # drift rather than code drift.
        "git_commit": provenance_fields.get("git_commit"),
        "prompts_sha256": provenance_fields.get("prompts_sha256"),
        "python_version": provenance_fields.get("python_version"),
        # Which development set this result belongs to, or ``None`` for the
        # corpus. Per case and not only in the run's metadata, because the
        # metadata file describes the last invocation while this entry describes
        # this result, and a result read out of its directory has to be able to
        # say which key it was graded against.
        "development_set": provenance_fields.get("development_set"),
        "transcript_sha256": result.transcript_sha256,
        "transcript_file": transcript_path(Path("."), case_no).name,
        "ruling": result.ruling,
        "ruling_findings": result.ruling_findings,
        "referee": result.referee,
        # The share of the judge's drafts that agreed on the published ruling,
        # or ``None`` for a single-draft run. Its own field beside the ruling
        # and never folded into the judge's own confidence: a ruling that four
        # drafts agreed on and a ruling one draft reached confidently are two
        # different things, and a reader has to be able to tell them apart.
        "vote_agreement": result.vote_agreement,
        "stance_differing_ranges": [list(item) for item in result.stance_differing_ranges],
        # Written from the split rather than from the raw fields, so what lands
        # on disk and what the runner charged against the budget are one piece
        # of arithmetic rather than two copies of it.
        "tokens": tokens.as_dict(),
        # ``None`` when this run called all three agents, so "the advocates were
        # called here" is a fact the file states rather than one a reader infers
        # from a missing key. The entry travels with the result because a result
        # whose advocates came from elsewhere is not the same measurement.
        "replay": None if result.replay is None else result.replay.as_dict(),
        "wall_seconds": wall,
        "call_seconds": result.duration_seconds,
        "matched": matched,
    }
    if result.verification is not None:
        # Present only when the verifier ran, so a cache entry produced with the
        # switch off is the entry it always was. The verdicts travel with the
        # result because a reader of one case file has to be able to see what
        # the verifier found without opening the transcript.
        document["verification"] = result.verification
    if result.precedents_shown is not None:
        # Present only when the precedents switch was on, on the same rule: a
        # case file produced with the switch off is the file it always was. The
        # ids travel with the result because a reader of one case file has to be
        # able to see which earlier closures its judge was reading.
        document["precedents_shown"] = list(result.precedents_shown)
    if result.scope_gate is not None:
        # Present only when POL-GEN-08(1)'s gate fired, on the same rule the
        # verifier's and the library's blocks follow: a case file produced by a
        # case the gate did not fire on is the file it always was. The block
        # names the flags, the clause and the reason code and records ``calls``
        # as 0, so the file says in its own words that no model call was made.
        document["scope_gate"] = result.scope_gate
    if result.record_integrity is not None:
        # Present only when POL-RD-10(2)/(4)'s gate fired, on the same rule the
        # scope gate's block follows: a case file produced by a case the gate
        # did not fire on -- and every case file produced with the switch off --
        # is the file it always was. The block names the limbs, the clause and
        # the reason code and records ``calls`` as 0, so the file says in its own
        # words that no model call was made.
        document["record_integrity"] = result.record_integrity
    if amount_rule != pipeline.DEFAULT_AMOUNT_RULE:
        # Present only when the rule is not the published one, on the same rule
        # the verifier's and the library's blocks follow: a case file produced
        # with the switch off is the file it always was. The rule travels with
        # the result because a reader of one case file has to be able to see
        # what its amounts were held to without the directory around it -- and
        # because the abstention text a rejected draft carries names the rule it
        # was rejected under, which is otherwise a claim the file cannot support.
        document["amount_rule"] = amount_rule
    return (
        CaseOutcome(
            case_no=case_no,
            status=STATUS_COMPLETED,
            wall_seconds=wall,
            tokens=tokens,
            matched=matched,
            ruling=result.ruling,
            replayed_from=replayed_from,
            replayed_tokens=replayed_tokens,
            replayed_made_at=replayed_made_at,
        ),
        document,
        result.transcript_json,
    )


def _outcome_from_cache(
    case_no: int,
    document: Mapping[str, Any],
    expected: Optional[grade.Ruling],
    brief_status: Optional[str] = None,
    stale_moved: Tuple[str, ...] = (),
) -> CaseOutcome:
    """The outcome of a case that was skipped because its result is cached.

    ``brief_status`` and ``stale_moved`` are the staleness of that cached result,
    which the caller has already worked out. They travel on the outcome so the
    progress line says "stale" at the moment the result is reused rather than
    only in the report at the end — the reader watching the terminal is the one
    who can still decide to re-run. ``stale_moved`` names which digest moved, so
    that line can send the reader to the brief or to the prompts.

    The token split is read back rather than only the total, so a case reused
    from the cache can be costed the same way a case run now can. A reused case
    costs nothing *this invocation*, but the run's record still has to be able
    to say what the set cost to produce.

    A cached result whose advocates were replayed says so here too, so a re-run
    that skips the case does not lose the fact that its figures are not a
    whole-pipeline measurement. The borrowed tokens are read back as the split
    they were written as, and stay out of ``tokens``.
    """
    tokens = TokenSplit.from_mapping(document.get("tokens"))
    replay = document.get("replay")
    replayed_from: Optional[str] = None
    replayed_made_at: Optional[str] = None
    replayed_tokens = TokenSplit()
    if isinstance(replay, Mapping):
        recorded_from = replay.get("run_dir")
        replayed_from = recorded_from if isinstance(recorded_from, str) else None
        # The entry's own commit is the run that made these advocates. A cached
        # result is the only record of it left, because ``run.json`` may since
        # have been rewritten by a replay into this very directory.
        recorded_made_at = replay.get("git_commit")
        replayed_made_at = recorded_made_at if isinstance(recorded_made_at, str) else None
        replayed_tokens = TokenSplit.from_mapping(replay.get("tokens"))
    return CaseOutcome(
        case_no=case_no,
        status=STATUS_CACHED,
        wall_seconds=_as_seconds(document.get("wall_seconds")),
        tokens=tokens,
        matched=_match_for(case_no, document.get("ruling"), expected),
        ruling=document.get("ruling"),
        brief_status=brief_status,
        stale_moved=tuple(stale_moved),
        replayed_from=replayed_from,
        replayed_tokens=replayed_tokens,
        replayed_made_at=replayed_made_at,
    )


# --------------------------------------------------------------------------
# Progress
# --------------------------------------------------------------------------
def _format_seconds(value: float) -> str:
    return "{0:>8.1f}s".format(value)


# Which digest moved, as a reader needs to hear it. A phrase rather than one
# word, because they send the reader to different places: a moved brief means
# re-read the case, a moved prompt means re-read what the agents were told, and
# a moved library means re-read the closures the judge was shown. One entry per
# ``grade.MOVED_*``, and a test holds the three together, so a channel added
# later cannot fall through to the fallback below and be described as though the
# code had moved when it had not.
_STALE_PHRASES = (
    (grade.MOVED_BRIEF, "the brief has moved"),
    (grade.MOVED_PROMPTS, "the prompts have moved"),
    (grade.MOVED_PRECEDENTS, "the library has moved"),
)


def _describe_moved(moved: Sequence[str]) -> str:
    """``the brief has moved``, ``the prompts have moved``, ``the library has
    moved``, or any of them joined.

    When nothing was named -- an older cache entry, or a caller that supplied
    only a status -- the fallback says what is known and no more, rather than
    picking one of the three and being wrong two times in three.
    """
    named = [phrase for name, phrase in _STALE_PHRASES if name in moved]
    if not named:
        return "produced by an earlier version of this code"
    return " and ".join(named)


def format_progress(outcome: CaseOutcome, position: int, total: int) -> str:
    """One line per case: number, verdict, wall clock, tokens.

    Printed as each case completes rather than at the end, because a three-hour
    run that prints nothing until it is over is unusable.

    A reused result the code has moved past says so here, on the line that
    announces the reuse, and names which digest moved. A reader who sees a run
    skip twenty-nine cases needs to know how many of them the code has moved on
    from — and why — before the report is written, not after.

    The token count on this line is this run's own bill. A replayed case says
    beside it that its advocates came from another run, because the alternative
    is a line whose tokens silently mean something different from every other
    line's.
    """
    line = "[{0:>3}/{1}] case {2}  {3:<6} {4}  {5:>10} tokens".format(
        position,
        total,
        outcome.case_no,
        outcome.verdict,
        _format_seconds(outcome.wall_seconds),
        "{0:,}".format(outcome.total_tokens),
    )
    if outcome.replayed:
        line += "  — advocates replayed from {0} (+{1:,} not charged here)".format(
            outcome.replayed_from, outcome.replayed_tokens.billed
        )
    if outcome.brief_status == grade.STALENESS_STALE:
        line += "  — stale: {0}".format(_describe_moved(outcome.stale_moved))
    elif outcome.brief_status == grade.STALENESS_UNKNOWN:
        line += "  — not checked: this result cannot be placed against this code"
    if outcome.status == STATUS_FAILED:
        reason = (outcome.failure_reason or "unknown failure").splitlines()[0]
        if outcome.failed_agent:
            reason = "{0}: {1}".format(outcome.failed_agent, reason)
        line += "  — {0}".format(reason[:160])
    return line


def format_start(case_no: int, position: int, total: int) -> str:
    """The line printed when a case **starts**, not when it finishes.

    A run that prints only on completion cannot say what is in flight. That is
    not hypothetical: the run of 2026-09-22 wrote its last line at 07:25 and then
    produced nothing for 1 h 48 m, and the last line of output named a case that
    had already finished — so the terminal could not distinguish a hung case from
    a long one, and the process had to be probed by hand to find out which it
    was. This line makes the last line of output name the case being worked on.

    Deliberately shorter than the completion line: it is emitted before a result
    exists, so it carries only what is known at that moment.
    """
    return "[{0:>3}/{1}] case {2}  started".format(position, total, case_no)


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------
@dataclass
class RunSummary:
    """Everything one invocation of the runner produced."""

    model: str
    run_dir: Path
    started_at: str
    ended_at: str
    stop_reason: str
    outcomes: List[CaseOutcome] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    report: Optional[grade.GradeReport] = None
    token_budget: Optional[int] = None
    concurrency: int = DEFAULT_CONCURRENCY
    timeout_seconds: float = llm.DEFAULT_TIMEOUT_SECONDS
    # The bound on one CASE, beside the bound on one ATTEMPT. Recorded for the
    # same reason: a case that stopped at a 2400-second deadline and one that
    # stopped at a 241-minute one are not the same measurement.
    case_deadline_seconds: float = pipeline.DEFAULT_CASE_DEADLINE_SECONDS
    # The two figures are not the same question. ``tokens_charged`` is what the
    # budget was spent against — the completed cases, which is what the run has
    # always stopped on. ``tokens_failed`` is what this invocation's own
    # failures cost. Their sum is what the invocation consumed, and the two are
    # kept apart so a run cannot look cheap by having thrown answers away.
    tokens_charged: TokenSplit = field(default_factory=TokenSplit)
    tokens_failed: TokenSplit = field(default_factory=TokenSplit)
    tokens_reused: int = 0
    # The third ledger, and the one that is never added to the other two. This is
    # what the borrowed advocates cost the run that made them: reported because a
    # reader needs to know what the replayed half of the case cost, and kept out
    # of every bill because this invocation did not spend it.
    tokens_replayed: TokenSplit = field(default_factory=TokenSplit)
    # The source run, when there was one, and ``None`` otherwise -- so "this
    # invocation called all three agents for every case" is a fact the record
    # states rather than one a reader infers from a zero.
    replay: Optional[Dict[str, Any]] = None
    # The cases left out of every figure because the precedent library holds a
    # closure for them, or ``None`` when the switch was off. ``None`` and an
    # empty list are different findings: the first says the judge was never shown
    # a block, the second that it was and no covered case is a source.
    precedents_excluded: Optional[List[int]] = None
    # Two facts about a *sealed set's* invocation, and both default to False so a
    # development run's summary is exactly what it was. ``sealed_protocol`` says
    # the sealed protocol chose this invocation's cases, so the failures header
    # points at the protocol rather than at the plain cache line. The other says
    # the protocol left nothing to run, and the printer answers that with one line
    # instead of a summary whose only content would be this invocation's limits.
    sealed_protocol: bool = False
    sealed_nothing_to_run: bool = False

    @property
    def tokens_spent(self) -> int:
        """The figure the budget was spent against: the completed cases only."""
        return self.tokens_charged.billed

    @property
    def tokens_consumed(self) -> TokenSplit:
        """Every token this invocation was billed for, failed cases included."""
        return self.tokens_charged + self.tokens_failed

    @property
    def completed(self) -> bool:
        """The runner finished the set it was asked for, stopping early for nothing."""
        return self.stop_reason == STOP_COMPLETED

    @property
    def ok(self) -> bool:
        """The run finished and every case in it produced a ruling.

        Distinct from :attr:`completed` because a run can finish the set while
        one case failed on the transport. That is a successful run of the runner
        and a failure of the benchmark, so it exits non-zero without claiming to
        have stopped early.
        """
        return self.completed and not self.failures

    @property
    def failures(self) -> List[CaseOutcome]:
        return [outcome for outcome in self.outcomes if outcome.status == STATUS_FAILED]

    @property
    def timeouts(self) -> List[CaseOutcome]:
        """The failures the client stopped waiting for, as opposed to other kinds.

        Kept separate because the two call for opposite responses: a timeout is
        answered with a longer timeout or a faster model, and an unusable answer
        is answered in the prompt or the model. Neither is answered by the other.
        """
        return [outcome for outcome in self.failures if outcome.failure_kind == FAILURE_TIMEOUT]

    @property
    def deadlines(self) -> List[CaseOutcome]:
        """The failures where the run stopped itself at a bound it had set.

        Separate from :attr:`timeouts` for the same reason a timeout is separate
        from a shape failure: the two read alike under a generic label and call
        for different responses. A timeout is a property of one request; a
        deadline is a property of the run's own configuration, so the answer is
        to change the configuration.
        """
        return [outcome for outcome in self.failures if outcome.failure_kind == FAILURE_DEADLINE]

    @property
    def completed_cases(self) -> List[int]:
        return [o.case_no for o in self.outcomes if o.status == STATUS_COMPLETED]

    @property
    def cached_cases(self) -> List[int]:
        return [o.case_no for o in self.outcomes if o.status == STATUS_CACHED]

    @property
    def replayed_cases(self) -> List[int]:
        """The cases whose advocates came from another run, whether they succeeded.

        Read off the outcomes rather than off the source run's own case list, so
        a case that was refused for replay is not counted as replayed: it was
        not replayed, and it is reported in :attr:`refusals` instead.
        """
        return [o.case_no for o in self.outcomes if o.replayed]

    @property
    def refusals(self) -> List[CaseOutcome]:
        """The cases replay would not accept, each with the reason it gave.

        A kind of its own rather than a timeout or a transport failure, because
        it says nothing about the model: no call was made. Kept beside
        :attr:`failures` rather than inside a generic count so a reader can see
        that a run which produced 24 rulings refused 5 rather than lost them.
        """
        return [o for o in self.failures if o.failure_kind == FAILURE_REPLAY]

    @property
    def matched(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.matched)


def _default_client_factory(
    model: str, timeout_seconds: float = llm.DEFAULT_TIMEOUT_SECONDS
) -> Callable[[Callable[[Dict[str, Any]], None]], Any]:
    """A real client, built with the run's record sink wired in.

    ``LLMClient.model`` has no default and neither does this: the model is the
    caller's decision and it is passed straight through. The timeout defaults to
    the client's own default rather than repeating the number, so the two cannot
    drift apart.
    """

    def build(sink: Callable[[Dict[str, Any]], None]) -> Any:
        return llm.LLMClient(
            model=model, record_sink=sink, timeout_seconds=timeout_seconds
        )

    return build


# One sentence, stated once, for every place the record has to say that a run
# with precedents on is not the headline measurement. The library is built from
# closures made by people who have read these development sets, so a case whose
# closure is in it is material the system has been shown before, and a figure
# over such cases is in-sample.
PRECEDENTS_INCOMPARABLE_NOTE = (
    "Figures with precedents on are not comparable to the headline figure. The "
    "precedent library is built from closures made by people who have seen these "
    "development sets, so a case the library holds a closure for is material the "
    "system has been shown before."
)


def render_precedents_exclusions(
    excluded: Sequence[int], measured: Sequence[int]
) -> str:
    """The report's own section for a run with precedents on.

    It says two things and neither is optional: which cases were left out of
    every figure above and why, and that the figures are not comparable to the
    headline. A report that dropped the cases silently would report a figure
    over a set it never named.
    """
    lines = ["", "## Precedents", "", PRECEDENTS_INCOMPARABLE_NOTE, ""]
    if excluded:
        lines.append(
            "Left out of every figure above: {0} -- {1} of the {2} covered cases. "
            "The library holds a closure for each of them, so they are cases a "
            "human has already decided and a figure over them is in-sample.".format(
                ", ".join(str(case_no) for case_no in excluded),
                len(excluded),
                len(excluded) + len(measured),
            )
        )
    else:
        lines.append(
            "No covered case is the source of a library entry, so every figure "
            "above is over the whole covered set. The incomparability stands all "
            "the same: the library was built by people who have seen this set."
        )
    lines.append("")
    return "\n".join(lines)


def render_ablation_note(ablation: str) -> str:
    """The report's own section for an ablated run.

    An ablated run's ``report.md`` was indistinguishable from a headline one:
    the same title, the same tables, and no word anywhere that something had
    been taken out of what the agents were given. The ablation is a property of
    the *inputs*, so a reader who compares two reports has to be told which of
    them measured the pipeline without part of it -- and the run's directory
    name, which did say so, is not in the report.

    The sentence itself comes from :func:`tribunal.brief.ablation_note`, so the
    words a report prints are the words of the module that implements the
    ablation, and a report cannot describe an ablation the brief module does not
    have. For ``admissibility`` that includes the sentence that derived text
    computed from a null payload still says MISSING -- the difference between
    the ablated brief carrying no admissibility *object* and carrying no
    admissibility *information*.
    """
    return "\n## Ablation\n\n{0}\n\n{1}\n".format(
        ablation, brief.ablation_note(ablation)
    )


def run_benchmark(
    model: str,
    cases: Sequence[int],
    *,
    runs_dir: Path = RUNS_DIR,
    prompts_dir: Path = PROMPTS_DIR,
    # The top-level runs root this invocation was asked for, which is where the
    # held-out set's own root lives. ``runs_dir`` is the *set's* root and for the
    # held-out set it *is* the held-out root, so the guard cannot read the
    # top-level one off it. ``None`` means this repository's own ``runs/``.
    held_out_root: Optional[Path] = None,
    # The set whose registration owns an un-run sealed root, and the only thing
    # that lets a plain run be written there. ``None`` means no permit: every
    # destination under a sealed root is refused, which is what a direct
    # invocation of this runner and a run of any other set get.
    sealed_permit_set: Optional[str] = None,
    force: bool = False,
    token_budget: Optional[int] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout_seconds: float = llm.DEFAULT_TIMEOUT_SECONDS,
    case_deadline_seconds: float = pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
    replay_dir: Optional[Path] = None,
    judge_votes: int = pipeline.DEFAULT_JUDGE_VOTES,
    verify_drafts: bool = False,
    ablation: Optional[str] = None,
    precedents: Optional[Any] = None,
    policy_version: int = policy_versions.BASE_VERSION,
    # Whether the policy version decides the run's directory as well as its
    # briefs. It does for a version named on the command line: a version-N run
    # is a different measurement and goes to ``runs/policy-v<N>/``. It does
    # **not** for a set whose registration fixes the version -- ``wild-v2`` is
    # version 2 by registration, and its runs go to ``runs/wild-v2/<model>/``
    # and never to a ``policy-v2`` directory inside it.
    policy_version_moves_the_run: bool = True,
    amount_rule: str = pipeline.DEFAULT_AMOUNT_RULE,
    # Whether the calls that depend on nothing are made at the same time. Off by
    # default, so the sequential path is the one every run before the switch
    # took; when it is on the two advocates and the judge's drafts are asked
    # together instead of one after another. **No individual request body
    # changes** -- the same brief, the same prompts and the same messages are
    # sent -- so it is deliberately absent from the ``configuration`` every
    # artifact carries and from every staleness and cache key. It can still send
    # requests a sequential run would not: up to two driver requests after the
    # rider fails, and the remaining draft requests after a draft raises; and
    # under a case deadline it can send a different set of requests.
    parallel_calls: bool = False,
    # Whether the judge's panel publishes as soon as a majority of its drafts
    # have agreed, rather than waiting for every draft. Off by default, so the
    # panel every run before the switch waited for is the panel it still waits
    # for; and it needs ``parallel_calls``, because what it stops waiting for is
    # a call already in flight. It changes no request body and moves no run
    # directory -- the same drafts are asked, and the ones the panel did not
    # wait for are recorded as ``not_awaited`` -- so, like ``parallel_calls``,
    # it is deliberately absent from the ``configuration`` every artifact
    # carries and from every staleness and cache key. It is recorded where the
    # invocation records what it was: the ``invocation_start`` event and this
    # run's ``run.json``. It is refused for every sealed set, whose single run is
    # one measurement and is not re-taken.
    early_majority: bool = False,
    # Whether the record itself is held to POL-RD-10's own limbs (2) and (4)
    # before the model is asked. Off by default, so every run before the switch
    # asked the model exactly as it did; when it is on, a route-deviation record
    # whose trip identifiers do not all match, or whose trip record is absent,
    # or whose pickup and dropoff timestamps two admitted artifacts disagree on
    # by more than the clause's own minutes, or whose timestamps run backwards,
    # is escalated with no call at all. Like ``parallel_calls`` and
    # ``early_majority`` it changes no request body -- a gated case sends none --
    # so it is deliberately absent from the ``configuration`` every artifact
    # carries and from every staleness and cache key, and it moves no run
    # directory. It is recorded where the invocation records what it was: the
    # ``invocation_start`` event and this run's ``run.json``. It is refused for
    # every sealed set, whose single run is one measurement and is not re-taken.
    integrity_gate: bool = False,
    # Which reasoning effort the two advocates' requests carry. ``"default"`` --
    # the default -- leaves every request exactly as it is today, so a run
    # without the switch is byte for byte the run it was; ``"none"`` makes the
    # **two advocate requests** carry ``"reasoning_effort": "none"`` and leaves
    # the judge's drafts and the verifier untouched. Unlike ``parallel_calls``,
    # ``early_majority`` and ``integrity_gate`` this one changes request bodies,
    # so it is a switch that changes what a run measures: it is recorded in the
    # ``configuration`` every artifact carries, it is refused beside the other
    # such switches (``--precedents`` and ``--policy-version`` are the one pair
    # that may be given together, and ``--advocate-effort`` with
    # ``--policy-version`` is the second), and a run under it goes to a root of
    # its own, ``runs/advocate-effort-<effort>/<set>/[policy-v<N>/]<model>/``, so
    # it can never mix with or overwrite a default run. It is refused for every
    # sealed set, whose single run is one measurement and is not re-taken.
    advocate_effort: str = pipeline.ADVOCATE_EFFORT_DEFAULT,
    # Whether the cases are graded against a key at all. An external sample that
    # carries a **stated expectation** rather than a key has nothing to be
    # scored against: the organisers' own word is not one of POL-GEN-03's
    # rulings, and grading a case against a token it never had would invent one.
    # With this on, a case the key does not carry is run and reported as
    # unscored rather than refused before the run. Off by default, so every
    # other caller's cases are still refused when they are not in the key.
    unscored: bool = False,
    client_factory: Optional[Callable[[Callable[[Dict[str, Any]], None]], Any]] = None,
    key: Optional[Mapping[int, grade.Ruling]] = None,
    git_runner: Optional[Callable[[Sequence[str]], Optional[str]]] = None,
    case_loader: Optional[Callable[[int], Mapping[str, Any]]] = None,
    label: Optional[str] = None,
    key_path: Optional[Path] = None,
    progress: Callable[[str], None] = lambda text: print(text, flush=True),
    now: Callable[[], str] = lambda: datetime.now(timezone.utc).isoformat(),
) -> RunSummary:
    """Run ``cases`` against ``model``, cache the results, and grade them.

    ``judge_votes`` is how many times each case's judge is asked, on the same
    inputs, with the majority deciding. It defaults to the value the layer below
    declares rather than repeating the number here, so the two cannot drift
    apart, and 1 is the single-draft behaviour every run before the vote used.
    Every draft is a call, so every draft is billed and every draft is recorded.

    ``model`` is required here and has no default, so a caller that drives this
    function directly must say which model it means; the command line resolves
    the decided one from ``tribunal/model.py`` before calling in. ``client_factory``
    exists so a test can drive the whole runner — real ``LLMClient``, real
    ``pipeline`` — over a fake transport with recorded bodies, and without a
    network.

    Two time limits are in force and they are not the same limit.
    ``timeout_seconds`` bounds one HTTP attempt; ``case_deadline_seconds``
    bounds one whole case, all three agent calls and any shape retry included.
    Both default to the value the layer below declares, rather than repeating
    the number here, so the two cannot drift apart.

    ``replay_dir`` names another run whose recorded advocates are to be reused,
    and only the judge called. It is checked in full before the run directory is
    touched, so a replay into the source run's own directory has read every entry
    it needs before it overwrites anything; a case the source cannot supply is
    recorded as a :data:`FAILURE_REPLAY` failure with the reason the check gave,
    and no call is made for it.

    ``case_loader``, ``key``, ``label`` and ``key_path`` are what let this same
    function run a second development set. ``case_loader`` names those cases by
    number for a set deliberately absent from the manifest; ``key`` is that
    set's own key, so the four graded fields are compared against the answers
    belonging to those cases; ``label`` names the set in the report's title and
    in the run's metadata; and ``key_path`` records that set's key digest as
    this run's provenance rather than the corpus key's. Everything else this
    function does -- the cache, the provenance, both deadlines, the token budget
    and the replay check -- is unchanged and shared, because a set is run by
    this function and not by a second copy of it.

    ``ablation`` names one ablation of the brief, or ``None`` for none, and it
    is applied in exactly one place below and passed straight to the layer under
    this one. Three things follow from it and none of them is optional: the run
    directory moves to ``runs/ablation/<name>/<model-slug>/`` so an ablated
    result cannot land where the submission's figure lives; the ``configuration``
    every artifact carries records which ablation it was; and the staleness
    checker rebuilds each case's brief **the same ablated way**, because
    comparing an ablated result against the unablated brief would report every
    case of it stale. It is refused together with ``replay_dir``: a replay hands
    the judge the brief this code builds, which is not ablated.

    ``parallel_calls`` is off by default and is not one of the switches that
    changes what a run measures, so it does not move the run's directory and it
    is not refused beside them. It reaches the pipeline as one keyword, changes
    no request, and is recorded where the invocation records what it was -- the
    ``invocation_start`` event and this run's ``run.json`` -- and nowhere else.
    It is deliberately **not** in the ``configuration`` object, which is what a
    case file is read against, because a result produced with it on is the same
    result: same requests, same brief, same prompts.

    ``early_majority`` follows ``parallel_calls`` in every respect and for the
    same reasons: it changes no request, moves no directory and is absent from
    the ``configuration`` object. It is refused without ``parallel_calls`` --
    there is nothing in flight to stop waiting for -- and refused for every
    sealed set, whose single run is one measurement and is not re-taken. It is
    also refused with ``--verify-drafts``, because the verifier can take a vote
    away after the panel has stopped waiting.

    ``integrity_gate`` follows ``parallel_calls`` too, and for the same reasons
    again: it changes no request body (a gated case sends none at all), moves no
    directory, and is absent from the ``configuration`` object. It is recorded
    in the ``invocation_start`` event and in this run's ``run.json``, and it is
    refused for every sealed set by the set's own name.

    ``advocate_effort`` is the opposite kind of switch and follows the rule the
    ablation follows instead. It **does** change request bodies -- the two
    advocate requests gain ``"reasoning_effort": "none"`` -- so it changes what a
    run measures: it is written into the ``configuration`` every artifact carries
    (only when it is not the default, so a plain run's artifacts are byte for
    byte what they always were), it is recorded in the ``invocation_start`` event
    and in this run's ``run.json``, and it moves the run directory to
    ``runs/advocate-effort-<effort>/<set>/[policy-v<N>/]<model>/``. It may be
    given with ``--policy-version`` -- the version's directory sits under the
    switch's root -- and it is refused beside the other switches that change what
    a run measures, and beside a replay, which calls no advocate to reason.
    """
    if not model:
        raise BenchmarkError("model is required and has no default; name the model explicitly")
    if concurrency < 1:
        raise BenchmarkError("concurrency must be at least 1, got {0}".format(concurrency))
    if timeout_seconds <= 0:
        # Refused rather than clamped. A zero or negative timeout would fail
        # every call, and a caller who passed one meant something else.
        raise BenchmarkError(
            "timeout_seconds must be positive, got {0}".format(timeout_seconds)
        )
    if case_deadline_seconds <= 0:
        # Same rule, and for the same reason: a non-positive deadline would fail
        # every case at its first check, which is never what a caller meant.
        raise BenchmarkError(
            "case_deadline_seconds must be positive, got {0}".format(case_deadline_seconds)
        )
    if token_budget is not None and token_budget < 0:
        raise BenchmarkError("token_budget cannot be negative")
    if early_majority and not parallel_calls:
        # Refused here as well as at the command line, so a caller driving this
        # function directly is told before a directory is created and before any
        # call. What the rule stops waiting for is a call already in flight, and
        # a sequential panel has none.
        raise BenchmarkError(
            "--early-majority needs --parallel-calls: the rule stops waiting for "
            "a draft that is already in flight, and a sequential panel has none"
        )
    if early_majority and verify_drafts:
        # Refused for the same reason the pipeline refuses it, and here as well
        # so the caller is told before anything is read or written: the verifier
        # can take a vote away after the panel has stopped waiting, so the
        # majority the rule published on would not be the majority the vote was
        # taken over.
        raise BenchmarkError(
            "--early-majority cannot be used with --verify-drafts: the verifier "
            "runs over every valid draft and a contradiction can take a vote "
            "away, so a panel that published at three could publish a ruling the "
            "full panel would not have carried"
        )
    if ablation is not None and not brief.ablation_known(ablation):
        # Refused here as well as at the command line, so a caller driving this
        # function directly is told which names exist rather than getting a
        # directory named after a typo.
        raise BenchmarkError(
            "no ablation called {0!r}; the ablations are {1}".format(
                ablation, ", ".join(brief.ABLATIONS)
            )
        )
    if ablation is not None and replay_dir is not None:
        # The same refusal :func:`run_one_case` makes, one layer up and before
        # anything is written, because this is the layer that decides the run
        # directory and it must not create one for a run that cannot be honest.
        raise BenchmarkError(
            "an ablated run cannot replay: a replay reuses a recorded run's "
            "advocates, which were given the brief without the ablation, and the "
            "judge would then be handed an unablated brief"
        )
    if amount_rule not in pipeline.AMOUNT_RULES:
        # Refused here as well as at the command line, so a caller driving this
        # function directly is told which rules exist rather than getting a
        # directory named after a typo.
        raise BenchmarkError(
            "no amount rule called {0!r}; the rules are {1}".format(
                amount_rule, ", ".join(pipeline.AMOUNT_RULES)
            )
        )
    if advocate_effort not in pipeline.ADVOCATE_EFFORTS:
        # Refused on the same rule and in the same place: a caller driving this
        # function directly is told which settings exist rather than getting a
        # directory named after a typo -- and, because this switch changes
        # request bodies, rather than silently sending the default's.
        raise BenchmarkError(
            "no advocate effort called {0!r}; the settings are {1}".format(
                advocate_effort, ", ".join(pipeline.ADVOCATE_EFFORTS)
            )
        )
    switches_on = [
        name
        for name, on in (
            ("--ablate", ablation is not None),
            ("--precedents", precedents is not None),
            ("--policy-version N>=2", policy_version != policy_versions.BASE_VERSION),
            ("--amount-rule", amount_rule != pipeline.DEFAULT_AMOUNT_RULE),
            (
                "--advocate-effort",
                advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT,
            ),
        )
        if on
    ]
    # The pairs that may be given together, and there are two of them. A run with
    # two switches that change what it measures measures neither, with **one
    # exception each**: ``--precedents`` and ``--policy-version`` may be given
    # together, because the precedents block is the same whatever the policy
    # version; and ``--advocate-effort`` and ``--policy-version`` may be given
    # together, because the version's directory sits under the switch's own root
    # and the two are not confounded -- one changes what the advocates reason
    # over, the other what they are given.
    allowed_pairs = (
        frozenset({"--precedents", "--policy-version N>=2"}),
        frozenset({"--advocate-effort", "--policy-version N>=2"}),
    )
    if len(switches_on) > 1 and frozenset(switches_on) not in allowed_pairs:
        raise BenchmarkError(
            "at most one of --ablate, --precedents, --policy-version N>=2, "
            "--amount-rule and --advocate-effort may be given per invocation, "
            "except --precedents or --advocate-effort with --policy-version: each "
            "changes what the run measures, and a run with two of them on "
            "measures neither"
        )
    if precedents is not None and replay_dir is not None:
        # A replay reuses a recorded run's advocates, and the judge of the run
        # they came from never saw the block, so the two halves of the case would
        # have been produced under different instructions.
        raise BenchmarkError(
            "a run with precedents on cannot replay: a replay reuses a recorded "
            "run's advocates, and the judge that produced them never saw the "
            "precedents block"
        )
    if policy_version != policy_versions.BASE_VERSION and replay_dir is not None:
        # A replay rebuilds the case's brief and compares it with the digest the
        # source run recorded, then hands the judge that rebuilt brief. A run
        # named at a later version would rebuild at that version while the
        # advocates it reuses were given the brief of the version their run
        # recorded, so the two halves of the case would have been produced under
        # different policy. A replay is how a recorded run is reproduced, and it
        # is the source run's version that does the reproducing.
        raise BenchmarkError(
            "a run at a later policy version cannot replay: a replay rebuilds the "
            "brief at the version the source run recorded, and the advocates it "
            "reuses were given that brief, not this version's"
        )
    if advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT and replay_dir is not None:
        # A replay reuses a recorded run's advocates and calls only the judge, so
        # there is no advocate request for this switch to change. Naming it
        # beside a replay is a request this pipeline cannot honour, and honouring
        # it quietly would be a run whose directory names a setting its advocates
        # were never asked under.
        raise BenchmarkError(
            "a run under --advocate-effort {0} cannot replay: a replay reuses a "
            "recorded run's advocates and calls only the judge, so no advocate "
            "request is made for the switch to change".format(advocate_effort)
        )
    if policy_version != policy_versions.BASE_VERSION:
        # Refused here, before a client exists and before any case is issued, so
        # a version this repository does not have is one clear refusal rather
        # than a run directory full of cases that each failed to build a brief.
        # ``apply_amendments`` makes the same check; this one is here because the
        # message belongs to the command line that asked, and because the
        # staleness check would otherwise swallow it into ``None`` per case.
        try:
            available = policy_versions.highest_available_version()
        except policy_versions.AmendmentError as exc:
            raise BenchmarkError(str(exc))
        if policy_version > available:
            raise BenchmarkError(
                "there is no policy version {0}; this repository is at version "
                "{1}, so version {1} is the highest that can be run".format(
                    policy_version, available
                )
            )
    # Loaded once, before anything is written. The chain head travels into the
    # run's configuration, and the staleness check has to compare every cached
    # case against the same head the whole invocation was shown against.
    library: Optional[Any] = None
    if precedents is not None:
        library = precedents_library.Library.load(
            precedents, set_name=precedents_library.set_from_run_directory(runs_dir)
        )

    # De-duplicated but order-preserving: the requested order is the order the
    # progress lines and the report use, and a case named twice is one case.
    requested = list(dict.fromkeys(cases))
    if not requested:
        raise BenchmarkError("no cases were selected")

    resolved_key: Mapping[int, grade.Ruling] = (
        grade.load_answer_key() if key is None else dict(key)
    )
    if not unscored:
        # Refused before a client exists and before any case is issued: a case
        # the key does not carry cannot be graded, and a run over it would be a
        # run whose figures could not be computed. An unscored run is the one
        # exception, and it says so rather than relying on an empty key.
        missing = [case_no for case_no in requested if case_no not in resolved_key]
        if missing:
            raise BenchmarkError(
                "case(s) {0} are not in the answer key, so a run over them could not "
                "be graded".format(", ".join(str(case_no) for case_no in missing))
            )

    # The timeout is threaded through to the client the runner builds, which is
    # the whole point of the parameter: before it existed every call inherited
    # the client's default and a slow model lost cases to it.
    build_client = (
        _default_client_factory(model, timeout_seconds)
        if client_factory is None
        else client_factory
    )

    # The replay check, and it is made HERE: before the run directory is touched,
    # before a client exists and before any case is issued. That ordering is the
    # whole reason it is a separate pass. The natural way to use replay is to
    # point it at the directory it will write into, and a check interleaved with
    # the writing would overwrite the entry it was about to read. Every source
    # entry is therefore in memory before the first file is.
    replay: Optional[ReplayCheck] = None
    if replay_dir is not None:
        replay = check_replay(
            Path(replay_dir),
            requested,
            model=model,
            prompts_dir=prompts_dir,
            policy_version=policy_version,
            case_loader=case_loader,
        )

    # A run with a switch on gets a directory of its own, under the runs root it
    # was given. That root is ``runs/`` for the corpus and ``runs/codex/`` for
    # the second set, so the same rule puts an ablated corpus run at
    # ``runs/ablation/<name>/<model-slug>/``, a precedents corpus run at
    # ``runs/precedents/<model-slug>/``, a version-N corpus run at
    # ``runs/policy-v<N>/<model-slug>/``, a precedents-and-version run at
    # ``runs/precedents/policy-v<N>/<model-slug>/`` and a signed-rule corpus run
    # at ``runs/amount-rule/<rule>/<model-slug>/`` -- and the same under
    # ``runs/codex/`` for the second set. None of them can land where an
    # unswitched result lives, which is what makes the measurements
    # distinguishable by their paths and not only by their contents. At most one
    # switch can be on -- checked above, with ``--precedents`` and
    # ``--policy-version`` the one pair that may be given together -- so the
    # order here decides only which directory a run that cannot happen would have
    # gone to.
    sealed_permit: Optional[Path] = None
    # The root the destination below is built under. It is the runs root this
    # invocation was given, except under the advocate-effort switch: a run whose
    # advocates reasoned differently goes to a root of its own, at the top of the
    # runs tree, with the set's own subdirectory under it, so it can never mix
    # with or overwrite a default run. Every guard below is asked about that root
    # rather than about the one the caller named, so the two cannot disagree.
    destination_root = runs_dir
    if advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT:
        destination_root = advocate_effort_root(
            runs_dir, held_out_root, advocate_effort
        )
    if ablation is not None:
        run_dir = assert_ablation_destination(
            ablation_run_directory(destination_root, ablation, model),
            destination_root,
            model,
        )
    elif (
        precedents is not None
        and policy_version != policy_versions.BASE_VERSION
        and policy_version_moves_the_run
    ):
        run_dir = assert_precedents_policy_v_destination(
            precedents_policy_v_run_directory(
                destination_root, policy_version, model
            ),
            destination_root,
            policy_version,
            model,
        )
    elif precedents is not None:
        run_dir = assert_precedents_destination(
            precedents_run_directory(destination_root, model),
            destination_root,
            model,
        )
    elif (
        advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT
        and policy_version != policy_versions.BASE_VERSION
        and policy_version_moves_the_run
    ):
        # The switch's own root, with the version's directory under it. The pair
        # is one of the two allowed combinations, so it is reached rather than
        # refused: the version decides the briefs and the switch decides what the
        # advocates' requests carry, and neither confounds the other.
        run_dir = assert_advocate_effort_destination(
            advocate_effort_run_directory(
                destination_root, advocate_effort, policy_version, model
            ),
            destination_root,
            model,
        )
    elif policy_version != policy_versions.BASE_VERSION and policy_version_moves_the_run:
        run_dir = assert_policy_v_destination(
            policy_v_run_directory(destination_root, policy_version, model),
            destination_root,
            policy_version,
            model,
        )
    elif amount_rule != pipeline.DEFAULT_AMOUNT_RULE:
        run_dir = assert_amount_rule_destination(
            amount_rule_run_directory(destination_root, amount_rule, model),
            destination_root,
            amount_rule,
            model,
        )
    elif advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT:
        run_dir = assert_advocate_effort_destination(
            advocate_effort_run_directory(
                destination_root, advocate_effort, policy_version, model
            ),
            destination_root,
            model,
        )
    else:
        run_dir = run_directory(destination_root, model)
        # The one destination an un-run sealed root would accept, and only for
        # the caller that named the set which owns it.
        # ``UNRUN_SEALED_RUNS_SUBDIRS`` is empty now that all five sealed sets
        # have had their run -- ``sealed-v3``'s was started and stopped -- so this
        # issues no permit and every sealed root's plain run directory is refused.
        # The machinery is the same one a further sealed set would need:
        # ``sealed_permit_set`` is passed by ``eval.development_sets.run_set``
        # alone and only for the set whose registration names that root, so a
        # direct invocation of this runner -- ``python3 -m eval.run_benchmark
        # --runs-dir runs/wild-v2`` -- issues no permit and is refused, as is any
        # other set pointed at the same root.
        sealed_permit = (
            run_dir if sealed_permit_set in UNRUN_SEALED_RUNS_SUBDIRS else None
        )
    if label is not None and run_dir.resolve() == run_directory(RUNS_DIR, model).resolve():
        # A development set's results are not corpus results, and
        # runs/<model>/ is where the corpus result lives. Refused rather than
        # trusted: a set that reached this directory would change what the
        # reported figure covers while leaving every file a reader looks at
        # apparently intact. The check is against the corpus directory itself
        # and not against the runs root, so a set run in a scratch root is
        # unaffected and only the reported directory is protected.
        raise BenchmarkError(
            "development set {0!r} must be given its own runs directory; "
            "{1} holds the corpus results and a set written there would change "
            "what the reported figure covers".format(label, run_dir)
        )
    if advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT:
        # The switch's destination, checked rather than merely chosen: the two
        # branches above build it, and this is what says a name that resolved
        # anywhere else cannot put such a result where a reported figure lives.
        assert_advocate_effort_destination(run_dir, destination_root, model)
    # All five sealed roots are closed outright now that ``sealed-v3``'s run has
    # been started and stopped. A plain run, an ablated run, a run at a later
    # policy version and a report all refuse a destination under any of them, and
    # this is the one place a run's own destination is decided, so the check is
    # made here and before the directory exists: a refused run leaves nothing
    # behind.
    assert_not_under_the_held_out_root(
        run_dir, held_out_root or RUNS_DIR, permit=sealed_permit
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    started_at = now()
    run_provenance = provenance(
        model,
        prompts_dir=prompts_dir,
        runs_dir=runs_dir,
        git_runner=git_runner,
        now=now,
        key_path=key_path,
    )
    if label is not None:
        # On the provenance rather than only in the metadata writer, because the
        # per-case cache entries copy these fields and a cached case has to be
        # able to say which set it belongs to without its directory.
        run_provenance = dict(run_provenance, development_set=label)

    # What this invocation is, recorded on every artifact it writes. Built
    # once here rather than per case, so the case files and the run's own
    # metadata cannot come to disagree about the run that made them. The
    # precedents half is the library's chain head and note digest, not a flag:
    # "the block was on" says nothing about which closures the judge read.
    configuration = configuration_document(
        judge_votes=judge_votes,
        verify_drafts=verify_drafts,
        ablation=ablation,
        precedents=None if library is None else library.configuration(),
        policy_version=policy_version,
    )
    if amount_rule != pipeline.DEFAULT_AMOUNT_RULE:
        # Added rather than declared in :func:`configuration_document`, so a run
        # with the switch off writes the configuration object it always wrote.
        # The five declared fields are written at their defaults whether or not
        # a switch is on; this one is a sixth only where it is not the default,
        # which is what keeps the plain run's artifacts byte-identical.
        configuration = dict(configuration, amount_rule=amount_rule)
    if advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT:
        # And the advocate-effort switch, on the same rule and for the same
        # reason: a run whose advocates reasoned differently is a different
        # measurement, so the case file has to say so on its own -- but a run
        # with the switch off writes the configuration object it always wrote,
        # which is what keeps the default byte-identical.
        configuration = dict(configuration, advocate_effort=advocate_effort)

    # The invocation's own id, and the append-only log every case appends to.
    # The id is written on every event line and on the invocation's metadata, so
    # a reader can join the two without guessing which invocation a line belongs
    # to. The log is opened in append mode and is never truncated, ``--force``
    # included: forcing a re-run skips the cache, it does not erase the record
    # of the run that filled it.
    invocation_id = events.new_invocation_id(now)
    events_log = events.EventLog(
        run_dir / events.EVENTS_FILE,
        invocation_id=invocation_id,
        git_commit=run_provenance.get("git_commit"),
        prompts_sha256=run_provenance.get("prompts_sha256"),
        now=now,
    )
    events_log.record(
        events.EVENT_INVOCATION_START,
        model=model,
        cases=list(requested),
        concurrency=concurrency,
        timeout_seconds=timeout_seconds,
        case_deadline_seconds=case_deadline_seconds,
        token_budget=token_budget,
        judge_votes=judge_votes,
        development_set=label,
        replay_dir=None if replay_dir is None else str(replay_dir),
        # Recorded only when the verifier is on, so a run with the switch off
        # appends the same line it always appended.
        **({"verify_drafts": True} if verify_drafts else {}),
        # And the ablation, on the same rule: named on the invocation's own line
        # when there is one, and absent from it when there is not, so the line a
        # plain run appends is the line it always appended.
        **({"ablation": ablation} if ablation is not None else {}),
        # And the library's chain head, on the same rule: named on the
        # invocation's own line when the switch is on, and absent from it when it
        # is not, so the line a plain run appends is the line it always appended.
        **({"precedents": library.chain_head} if library is not None else {}),
        # And the policy version, on the same rule again: named only when it is
        # not version 1, so the line a plain run appends is the line it always
        # appended.
        **(
            {"policy_version": policy_version}
            if policy_version != policy_versions.BASE_VERSION
            else {}
        ),
        # And the amount rule, on the same rule once more: named on the
        # invocation's own line only when it is not the published one, so the
        # line a plain run appends is the line it always appended.
        **(
            {"amount_rule": amount_rule}
            if amount_rule != pipeline.DEFAULT_AMOUNT_RULE
            else {}
        ),
        # And the parallel switch, on the same rule: named on the invocation's
        # own line when it is on, and absent from it when it is not, so the line
        # a plain run appends is the line it always appended.
        **({"parallel_calls": True} if parallel_calls else {}),
        # And the early-majority switch, on the same rule once more. It is a
        # switch that says what this invocation did rather than what it measured,
        # so it is named on the invocation's own line beside the parallel one and
        # is absent from a run that did not ask for it.
        **({"early_majority": True} if early_majority else {}),
        # And the record-integrity gate, on the same rule again: a switch that
        # says what this invocation did and not what it measured, so it is named
        # on the invocation's own line when it is on and absent from a run that
        # did not ask for it.
        **({"integrity_gate": True} if integrity_gate else {}),
        # And the advocate-effort switch, named only when it is not the default,
        # so the line a plain run appends is the line it always appended. It is
        # named with its value rather than as a boolean, because "which effort"
        # is the measurement and ``none`` is the only one that exists today.
        **(
            {"advocate_effort": advocate_effort}
            if advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT
            else {}
        ),
    )

    # A shared sink, because the client is shared across every case and, above
    # concurrency 1, across threads. The client calls this from whichever thread
    # is completing a request, so it is the one piece of the runner's state that
    # needs a lock.
    #
    # Each record is kept with the position of the call that made it, read off
    # the thread that call is on (``pipeline.call_sort_key``), and the file is
    # written in that order rather than in the order the calls finished. With
    # calls in flight together the completion order is the network's, and a
    # record whose order moved with the network would not be reproducible. The
    # position is the one thing a record cannot carry itself: this client is
    # shared across every case and knows nothing about cases, roles or drafts.
    #
    # The position is ``(the case's place in this invocation's requested list,
    # role rank, draft, attempt)`` -- the ranks being rider 0, driver 1, judge 2
    # and verifier 3 -- so the order is the order the calls are *made* in, which
    # for a sequential run is the order they appear in the transcript. The
    # **requested position** and not the case number, because ``--cases`` may
    # name them in any order: with the case number first, a run asked for
    # ``--cases 103,101`` would write its file in 101-then-103 order, which is
    # not the order its calls were made in. The role rank rather than the role
    # name, because the names sort ``driver``, ``judge``, ``rider``: ASCII order
    # puts the rider last when the case reads it first.
    positions = {case_no: index + 1 for index, case_no in enumerate(requested)}
    total = len(requested)

    records: List[Tuple[Tuple[int, int, int, int], Dict[str, Any]]] = []
    records_lock = threading.Lock()

    def sink(record: Dict[str, Any]) -> None:
        case_no, rank, draft, attempt = pipeline.call_sort_key()
        with records_lock:
            records.append(
                ((positions.get(case_no, case_no), rank, draft, attempt), record)
            )

    # Every other mutation below happens on the thread that called this
    # function: worker threads run `pipeline.run_case` and return, and the
    # results are folded in here. So `outcomes`, `state` and the file writes
    # need no lock — and adding one would suggest a concurrency that is not
    # there.
    outcomes: List[CaseOutcome] = []
    recorded: set = set()
    pending: List[int] = []
    # Three ledgers, and the first two are not the same ledger.
    #
    # ``charged`` is what the budget is spent against: the cases this invocation
    # completed. The run has always stopped on this figure and it still does —
    # changing it would change when a run stops rather than only what it
    # records.
    #
    # ``failed`` is the cost of this invocation's own failures. A case that
    # failed after its calls were made was billed for them, so a record counting
    # only the completed cases would say a run that burned a third of its budget
    # on unusable answers was cheap.
    #
    # ``reused`` is what the cached cases cost, which is nothing now and was
    # something when they were produced. Kept apart so a re-run is not mistaken
    # for a spend.
    reused = TokenSplit()

    # The fourth ledger, and it is filled in for cases that succeeded and cases
    # that failed alike. It is what the borrowed advocates cost the run that made
    # them. It is reported wherever a figure is, and added to nothing.
    state = {
        "stop_reason": STOP_COMPLETED,
        "charged": TokenSplit(),
        "failed": TokenSplit(),
        "replayed": TokenSplit(),
    }

    # Cached first: a re-run should say what it is skipping before it starts, and
    # whether what it is skipping still belongs to this code. One checker for the
    # whole invocation, because the current brief for a case cannot change while
    # the run is in progress. The checker rebuilds each case's brief the same
    # ablated way this run builds it, so a cached ablated result is compared
    # against an ablated brief and not against the plain one -- which would
    # report every case of it stale.
    checker = BriefStaleness(
        brief_digest_for(case_loader, ablate=ablation, policy_version=policy_version),
        run_dir=run_dir,
        # The library as this invocation has it, so the third staleness channel
        # compares each cached case against the head the whole run was shown
        # against. ``None`` when the switch is off, and the channel is then
        # silent rather than empty.
        precedents=None if library is None else library.configuration(),
        # The version this run briefs at, so a cached case is compared against
        # the brief this invocation would build and not against version 1's.
        policy_version=policy_version,
    )
    for case_no in requested:
        document = None if force else load_cached(run_dir, case_no)
        if document is None:
            pending.append(case_no)
            continue
        outcome = _outcome_from_cache(
            case_no,
            document,
            resolved_key.get(case_no),
            checker.status_of(case_no, document),
            checker.moved_for(case_no, document),
        )
        outcomes.append(outcome)
        recorded.add(case_no)
        # This invocation began this case and found it already decided, which is
        # a fact about the invocation and belongs on the log beside the cases it
        # ran. ``cached`` is what keeps the two apart: a reader following one
        # case sees that it was begun and reused, not that work was done.
        events_log.record(
            events.EVENT_CASE_START,
            case_no=case_no,
            position=positions[case_no],
            total=total,
            cached=True,
        )
        reused = reused + outcome.tokens
        state["replayed"] = state["replayed"] + outcome.replayed_tokens
        progress(format_progress(outcome, positions[case_no], total))

    def write_metadata(stop_reason: str) -> None:
        document = _metadata_document(
            model=model,
            run_dir=run_dir,
            invocation_id=invocation_id,
            started_at=started_at,
            ended_at=now(),
            stop_reason=stop_reason,
            requested=requested,
            outcomes=outcomes,
            run_provenance=run_provenance,
            token_budget=token_budget,
            concurrency=concurrency,
            timeout_seconds=timeout_seconds,
            case_deadline_seconds=case_deadline_seconds,
            tokens_charged=state["charged"],
            tokens_failed=state["failed"],
            tokens_reused=reused,
            tokens_replayed=state["replayed"],
            replay=None if replay is None else replay_block(replay, outcomes),
            configuration=configuration,
            parallel_calls=parallel_calls,
            early_majority=early_majority,
            integrity_gate=integrity_gate,
            advocate_effort=advocate_effort,
        )
        # Both, and the order matters. ``run.json`` is the latest invocation's
        # record at the conventional path; the history is what survives the next
        # invocation overwriting that file.
        write_json(metadata_path(run_dir), document)
        _record_invocation(run_dir, document)

    def accept(outcome: CaseOutcome) -> None:
        """Record one outcome, on disk and on the terminal, the moment it lands.

        Idempotent by case number. The interrupt path drains whatever is still
        in flight after the main loop has stopped, and a case whose result was
        already folded in must not be counted twice — a double count would
        double its tokens against the budget and put it in the metadata twice.
        """
        if outcome.case_no in recorded:
            return
        recorded.add(outcome.case_no)
        outcomes.append(outcome)
        # Every case that reached the transport was billed for its calls, so
        # every one of them counts towards what this invocation cost. Only a
        # completed case counts towards what the budget was spent on.
        if outcome.status == STATUS_COMPLETED:
            state["charged"] = state["charged"] + outcome.tokens
        elif outcome.status == STATUS_FAILED:
            state["failed"] = state["failed"] + outcome.tokens
        # And the borrowed half, which no branch above touches: a replayed case's
        # own ``tokens`` are this run's judge call, and its ``replayed_tokens``
        # were billed to the run the advocates came from.
        state["replayed"] = state["replayed"] + outcome.replayed_tokens
        progress(format_progress(outcome, positions[outcome.case_no], total))
        # Written after every case, so an interrupted run still has correct
        # provenance and correct totals rather than nothing at all.
        write_metadata(state["stop_reason"])

    def end_fatally(exc: BaseException) -> None:
        """Close the invocation's log when it is leaving on an exception.

        Two places can raise out of an invocation before it finishes: building
        the client, and anything a case does. Both call this, because a log whose
        last line is ``invocation_start`` cannot tell a reader whether the run is
        still in flight or died -- which is the question the log exists to
        answer. ``stop_reason`` is set as well as recorded, so the metadata the
        ``finally`` writes agrees with the log.
        """
        state["stop_reason"] = STOP_FATAL
        events_log.record(
            events.EVENT_INVOCATION_END,
            stop_reason=STOP_FATAL,
            detail="{0}: {1}".format(type(exc).__name__, exc),
            cases_seen=len(outcomes),
            cases_completed=len(
                [item for item in outcomes if item.status == STATUS_COMPLETED]
            ),
            cases_failed=len(
                [item for item in outcomes if item.status == STATUS_FAILED]
            ),
        )

    if pending:
        # Built lazily, and only when there is work to do: a re-run whose cases
        # are all cached has no reason to need a credential. Built inside a
        # guard because a machine with no credential raises here rather than
        # inside a case, and that is still a run that has to end its own log.
        try:
            client = build_client(sink)
        except BaseException as exc:  # noqa: BLE001 - logged, then re-raised
            end_fatally(exc)
            raise

        def execute(case_no: int) -> Tuple[CaseOutcome, Optional[Dict[str, Any]], Optional[str]]:
            replayable = None if replay is None else replay.accepted.get(case_no)
            if replay is not None and replayable is None:
                # Refused by the check that ran before anything was written, and
                # turned into an outcome here rather than there so that it lands
                # in the record like every other way a case produces nothing: a
                # failure with a kind and a reason, and no transcript. Nothing is
                # cached for it, so a later run against the same source refuses it
                # in the same words instead of silently skipping it.
                reason = replay.refused.get(
                    case_no, "the source run never ran this case"
                )
                events_log.record(
                    events.EVENT_CASE_FAILED,
                    case_no=case_no,
                    failure_kind=FAILURE_REPLAY,
                    failed_agent=None,
                    detail=reason,
                )
                return (
                    CaseOutcome(
                        case_no=case_no,
                        status=STATUS_FAILED,
                        failure_kind=FAILURE_REPLAY,
                        failure_detail=reason,
                        failure_reason=failure_reason_for(FAILURE_REPLAY, reason),
                    ),
                    None,
                    None,
                )
            return run_one_case(
                case_no,
                client=client,
                prompts_dir=prompts_dir,
                expected=resolved_key.get(case_no),
                case_provenance=run_provenance,
                case_deadline_seconds=case_deadline_seconds,
                case_loader=case_loader,
                replay=replayable,
                judge_votes=judge_votes,
                verify_drafts=verify_drafts,
                ablate=ablation,
                precedents=library,
                policy_version=policy_version,
                amount_rule=amount_rule,
                configuration=configuration,
                events_log=events_log,
                parallel_calls=parallel_calls,
                early_majority=early_majority,
                integrity_gate=integrity_gate,
                advocate_effort=advocate_effort,
            )

        workers = max(1, concurrency)
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
        in_flight: Dict[concurrent.futures.Future, int] = {}
        queue = list(pending)
        try:
            while queue or in_flight:
                while queue and len(in_flight) < workers:
                    if token_budget is not None and state["charged"].billed >= token_budget:
                        # Stop issuing NEW cases. The ones already running are
                        # allowed to finish, because their tokens are already
                        # being spent and their answers are already paid for.
                        state["stop_reason"] = STOP_BUDGET
                        break
                    case_no = queue.pop(0)
                    # Announced here, on the thread that owns the queue, and
                    # before the work is handed to a worker. A line printed from
                    # inside the worker could be scheduled after a later case's
                    # completion line, and the point of the line is that the
                    # last one on the terminal names what is still in flight.
                    progress(format_start(case_no, positions[case_no], total))
                    # And on the event log, from the same thread and at the same
                    # moment, so the log's case_start for a case precedes every
                    # event that case produces -- which is what makes a case's
                    # history readable in the order it happened rather than in
                    # the order two workers happened to finish.
                    events_log.record(
                        events.EVENT_CASE_START,
                        case_no=case_no,
                        position=positions[case_no],
                        total=total,
                        cached=False,
                    )
                    in_flight[pool.submit(execute, case_no)] = case_no

                if not in_flight:
                    break

                done, _ = concurrent.futures.wait(
                    in_flight, return_when=concurrent.futures.FIRST_COMPLETED
                )
                for future in done:
                    outcome, document, transcript_json = future.result()
                    _persist(run_dir, outcome, document, transcript_json)
                    accept(outcome)
                    # Popped only once its result is safely on disk. An
                    # interrupt between here and the next line would otherwise
                    # lose a result whose tokens have already been billed.
                    in_flight.pop(future, None)

        except KeyboardInterrupt:
            state["stop_reason"] = STOP_INTERRUPTED
            progress("")
            progress("interrupted — letting the case(s) already in flight finish")
        except BaseException as exc:  # noqa: BLE001 - logged, then re-raised
            # Recorded before the exception leaves, because a run that died must
            # still be able to say so from its own log. The 2026-09-27 replay
            # ended this way, on an unprovisioned model, and its log's last line
            # is where that is written down.
            end_fatally(exc)
            raise
        finally:
            # Wait for anything still running and keep its result: those tokens
            # have already been spent, so losing the answer would be losing
            # money. This is also what makes an interrupt safe, and why `accept`
            # has to be idempotent — a case the main loop already folded in is
            # still in this dictionary.
            pool.shutdown(wait=True)
            for future, case_no in list(in_flight.items()):
                in_flight.pop(future, None)
                if not future.done() or future.cancelled():
                    continue
                try:
                    outcome, document, transcript_json = future.result()
                except BaseException as exc:  # noqa: BLE001 - recorded, never raised
                    kind = failure_kind_for(exc)
                    detail = "{0}: {1}".format(type(exc).__name__, exc)
                    outcome = CaseOutcome(
                        case_no=case_no,
                        status=STATUS_FAILED,
                        failure_kind=kind,
                        failure_detail=detail,
                        failure_reason=failure_reason_for(kind, detail),
                    )
                    document, transcript_json = None, None
                _persist(run_dir, outcome, document, transcript_json)
                accept(outcome)

    # Written in the order the calls were made, not the order they finished.
    # ``sorted`` is stable, so two records sharing a position keep the order
    # they were appended in; within one invocation a position is one call, so
    # the file is a function of the run and not of the network.
    write_json(
        run_dir / CALLS_FILE,
        {
            "calls": [
                record
                for _position, record in sorted(records, key=lambda item: item[0])
            ]
        },
    )
    write_metadata(state["stop_reason"])

    # Graded over the cases that produced a ruling — whether it was produced by
    # this invocation or reused from the cache — and not over everything that
    # was asked for. A run stopped on budget must report an accuracy over what
    # it ran, not 11/29 for eleven answers.
    covered = sorted(
        outcome.case_no
        for outcome in outcomes
        if outcome.status in (STATUS_COMPLETED, STATUS_CACHED)
        and outcome.case_no in resolved_key
    )
    # A case the library holds a closure for is a case a human has already
    # decided, and it is exactly the case a precedent block is drawn from. Its
    # own result is in-sample in a way no other case's is, so it is left out of
    # every figure and named in the report, rather than quietly counted.
    precedents_excluded: List[int] = []
    if library is not None:
        sources = {
            (
                str((entry.get("source") or {}).get("set")),
                (entry.get("source") or {}).get("case_no"),
            )
            for entry in library.entries
        }
        precedents_excluded = sorted(
            case_no
            for case_no in covered
            if (library.set_name, case_no) in sources
        )
    measured = [
        case_no for case_no in covered if case_no not in set(precedents_excluded)
    ]
    report = grade_run(
        run_dir,
        resolved_key,
        measured,
        checker,
        case_loader,
        # The version this run briefed at, so the report's provenance column
        # describes the brief the cases were decided under rather than the
        # version-1 brief of the same cases.
        policy_version=policy_version,
    )
    report_title = "Benchmark report — {0}".format(model)
    if label is not None:
        report_title = "Benchmark report — {0} — development set {1}".format(
            model, label
        )
    if ablation is not None:
        # The title is the first line a reader sees, and an ablated report's
        # title said nothing about the ablation: two runs of the same model under
        # the same prompts produced two reports that opened identically.
        report_title = "{0} — ablation {1}".format(report_title, ablation)
    report_text = grade.render_report(report, report_title, key_path=key_path)
    if ablation is not None:
        report_text += render_ablation_note(ablation)
    if library is not None:
        report_text += render_precedents_exclusions(precedents_excluded, measured)
    (run_dir / REPORT_FILE).write_text(report_text, encoding="utf-8")

    # The grade, one event per case, and then the end of the invocation. The
    # grade is recorded here rather than inside the grading code because it is
    # this invocation's finding about the cases it covered, and the log is where
    # a reader looks for it. It is written for a case that produced nothing as
    # well as for one that did, so "this case was graded and failed" is on the
    # log beside the failure that produced it.
    for score in report.cases:
        events_log.record(
            events.EVENT_GRADE,
            case_no=score.case_no,
            matched=score.exact,
            expected=score.expected.ruling,
            produced=None if score.produced is None else score.produced.ruling,
            fields={
                name: score.correct_on(name) for name in grade.GRADED_FIELDS
            },
        )
    events_log.record(
        events.EVENT_INVOCATION_END,
        stop_reason=state["stop_reason"],
        cases_graded=report.total,
        exact_matches=report.exact_matches,
        # The two ledgers, named as the metadata file names them and never added
        # together here: ``consumed`` is what was billed, ``reused`` is what the
        # cached cases cost when they were produced, and the second is nothing
        # this invocation spent.
        tokens_consumed=(state["charged"] + state["failed"]).billed,
        tokens_reused=reused.billed,
        tokens_replayed=state["replayed"].billed,
        # Recorded only when the block was on, so a plain run's last line is the
        # line it always appended. ``cases_graded`` above counts the cases the
        # figures were computed from, and the excluded ones are named here so a
        # reader can reconcile the two counts rather than wonder at the gap.
        **(
            {"precedents_excluded": list(precedents_excluded)}
            if library is not None
            else {}
        ),
    )

    return RunSummary(
        model=model,
        run_dir=run_dir,
        started_at=started_at,
        ended_at=now(),
        stop_reason=state["stop_reason"],
        outcomes=outcomes,
        provenance=run_provenance,
        report=report,
        token_budget=token_budget,
        concurrency=concurrency,
        timeout_seconds=timeout_seconds,
        case_deadline_seconds=case_deadline_seconds,
        tokens_charged=state["charged"],
        tokens_failed=state["failed"],
        tokens_reused=reused.billed,
        tokens_replayed=state["replayed"],
        replay=None if replay is None else replay_block(replay, outcomes),
        precedents_excluded=None if library is None else precedents_excluded,
    )


def _persist(
    run_dir: Path,
    outcome: CaseOutcome,
    document: Optional[Dict[str, Any]],
    transcript_json: Optional[str],
) -> None:
    """Write one case's transcript, and its cache entry only when it succeeded.

    A failed case deliberately leaves no ``case-<NNNNN>.json`` behind. That is
    what makes a re-run retry exactly the failures: the cache is the record of
    what succeeded, and nothing else.
    """
    if transcript_json is not None:
        _write_text_atomic(transcript_path(run_dir, outcome.case_no), transcript_json)

    if document is not None:
        write_json(case_cache_path(run_dir, outcome.case_no), document)


def _record_invocation(run_dir: Path, document: Mapping[str, Any]) -> None:
    """Append one invocation's metadata to the run directory's history.

    ``run.json`` describes the invocation that wrote it and is overwritten by
    the next one, which is right for that file and useless as a record: a
    single-case re-run of case 214 replaced a 29-case run's commit, token total
    and case list, and nothing anywhere held them afterwards. This is the list
    of invocations, so an earlier one stays reconstructable.

    Keyed by the invocation's own start time and replaced in place, because
    ``run.json`` is rewritten after every case to keep an interrupted run's
    totals correct — without that, one run would leave one entry per case.
    """
    path = Path(run_dir) / INVOCATIONS_FILE
    history = read_json(path)
    if not isinstance(history, list):
        # Absent, corrupt, or hand-written as an object: the history starts
        # here rather than the write failing. Losing a history file must not
        # also lose the run that discovered it.
        history = []
    started_at = document.get("started_at")
    history = [
        entry
        for entry in history
        if not (isinstance(entry, Mapping) and entry.get("started_at") == started_at)
    ]
    history.append(dict(document))
    write_json(path, history)


def _metadata_document(
    *,
    model: str,
    run_dir: Path,
    invocation_id: str,
    started_at: str,
    ended_at: str,
    stop_reason: str,
    requested: Sequence[int],
    outcomes: Sequence[CaseOutcome],
    run_provenance: Mapping[str, Any],
    token_budget: Optional[int],
    concurrency: int,
    timeout_seconds: float,
    case_deadline_seconds: float,
    tokens_charged: TokenSplit,
    tokens_failed: TokenSplit,
    tokens_reused: TokenSplit,
    tokens_replayed: TokenSplit,
    replay: Optional[Mapping[str, Any]] = None,
    configuration: Mapping[str, Any],
    parallel_calls: bool = False,
    early_majority: bool = False,
    integrity_gate: bool = False,
    advocate_effort: str = pipeline.ADVOCATE_EFFORT_DEFAULT,
) -> Dict[str, Any]:
    """The run's own metadata file.

    Every provenance field the run needs is at the top level, so a reader does
    not have to know the shape to find the commit or the clean-tree flag.

    ``cases`` describes **this invocation**, which is what the file is: a
    single-case re-run sitting in a directory of twenty-nine results says
    ``requested [214]``, and that is true of the invocation. It is misleading
    about the directory, so the directory gets its own block saying what it
    holds. A reader should not have to count files to learn that the two differ.

    The token figures are given as splits rather than as totals, because a total
    cannot be costed: output is priced at four times input on the decided model.
    ``tokens_charged`` is what the budget was spent against, ``tokens_failed``
    is what this invocation's own failures cost, and the two together are what
    the invocation consumed. ``tokens_reused`` is what the cached cases cost
    when they were produced, which is nothing now.

    ``tokens_replayed`` is the one figure here that is not part of what this
    invocation consumed at all: it is what the borrowed advocates cost the run
    that made them. It is reported because a reader has to be able to see what
    the replayed half of the case cost, and it is named so that no reader adds it
    to a total. ``replay`` is the source run itself, and ``None`` when this
    invocation called every agent itself.

    ``parallel_calls`` is written only when it is on, so a plain run's metadata
    is the metadata it always wrote. It is not in ``configuration`` above and
    deliberately so: that object is what a case file is read against, and **no
    individual request body depends on this switch**. The *set* of requests can
    still differ -- a parallel run can spend up to two driver requests after the
    rider fails, and the remaining draft requests after a draft raises, and under
    a case deadline it can send a different set again -- but every body it does
    send is a body the sequential path sends too.

    ``early_majority`` is written on the same rule and for the same reasons: it
    changes no request body and it is not in ``configuration``. What it changes
    is how long a panel waits, which the case files themselves record -- the
    draft the panel did not wait for carries ``not_awaited`` and the vote block
    says ``early_majority``.

    ``advocate_effort`` is the one of these switches that is written **both**
    here and in ``configuration``, and it is written here only when it is not
    the default, so a plain run's metadata is the metadata it always wrote. It
    belongs in both because it does change request bodies -- the two advocate
    requests carry ``"reasoning_effort": "none"`` -- and the metadata file is
    what a reader consults to learn what an invocation did, while the
    ``configuration`` object is what a case file is read against.
    """
    failed = [outcome for outcome in outcomes if outcome.status == STATUS_FAILED]
    consumed = tokens_charged + tokens_failed
    directory_cases = cached_case_numbers(run_dir)
    replay_block: Optional[Dict[str, Any]] = None
    if replay is not None:
        replay_block = dict(replay)
        replay_block["tokens"] = tokens_replayed.as_dict()
        replay_block["note"] = pipeline.REPLAY_NOTE
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "model": model,
        # What produced this invocation's results. Always written, so a run
        # whose case files have been lost still says what the run was.
        "configuration": dict(configuration),
        # The invocation's own id, which every line of this invocation's event
        # log carries. Written here so a reader can join the metadata to the log
        # without matching timestamps, which two invocations can share.
        "invocation_id": invocation_id,
        "run_dir": str(run_dir),
        "started_at": started_at,
        "ended_at": ended_at,
        "stop_reason": stop_reason,
        "completed": stop_reason == STOP_COMPLETED,
        "concurrency": concurrency,
        # Recorded because it changes what the run's failures mean. A case that
        # timed out under a 120-second limit and the same case under a
        # 600-second limit are not the same measurement, and a reader comparing
        # two runs has to be able to see that the limit moved.
        "timeout_seconds": timeout_seconds,
        # And the bound on the whole case, beside the bound on one attempt. A
        # DEADLINE failure is only interpretable against the limit that produced
        # it, so the limit travels with the result.
        "case_deadline_seconds": case_deadline_seconds,
        "token_budget": token_budget,
        # And whether the calls that depend on nothing were made together.
        # Written only when the switch is on, on the rule every switch in this
        # file follows, so a plain run's metadata is the metadata it always
        # wrote. It is not in ``configuration`` above and deliberately so: that
        # object is what a case file is read against, and this changes no
        # request.
        **({"parallel_calls": True} if parallel_calls else {}),
        # And whether the judge's panel published at a majority rather than at
        # every draft, on the same rule and for the same reason: a switch that
        # says what the invocation did and not what it measured.
        **({"early_majority": True} if early_majority else {}),
        # And whether the record was held to POL-RD-10's own limbs before the
        # model was asked, on the same rule once more: a switch that says what
        # the invocation did and not what it measured.
        **({"integrity_gate": True} if integrity_gate else {}),
        # And which reasoning effort the two advocates' requests carried, named
        # only when it is not the default, so a plain run's metadata is the
        # metadata it always wrote. It is the one of these switches that is also
        # in ``configuration`` above, because it is the one of them that changes
        # request bodies.
        **(
            {"advocate_effort": advocate_effort}
            if advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT
            else {}
        ),
        "git_commit": run_provenance.get("git_commit"),
        "working_tree_clean": run_provenance.get("working_tree_clean"),
        "working_tree_status": run_provenance.get("working_tree_status"),
        "prompts_dir": run_provenance.get("prompts_dir"),
        "prompts_sha256": run_provenance.get("prompts_sha256"),
        "answer_key_sha256": run_provenance.get("answer_key_sha256"),
        # Which development set this run is of, or ``None`` for the corpus. A
        # digest alone does not say whose key it is, and a reader who cannot tell
        # a corpus run from a set run cannot read either figure correctly.
        "development_set": run_provenance.get("development_set"),
        # Recorded here as well as per case, so a run whose per-case entries
        # have been lost still says what built its briefs.
        "python_version": run_provenance.get("python_version"),
        "tokens": {
            # Kept at this name and this meaning: the figure the budget was
            # spent against, which is the cases this invocation completed.
            "spent_this_invocation": tokens_charged.billed,
            # Every token the provider billed, failed cases included. A case
            # that failed after its calls were made cost money, so a record
            # counting only the completed cases would report a run that burned a
            # third of its budget on unusable answers as a cheap one.
            "consumed_this_invocation": consumed.billed,
            "of_which_failed": tokens_failed.billed,
            "reused_from_cache": tokens_reused.billed,
            "total_for_the_case_set": consumed.billed + tokens_reused.billed,
            # The split, and it is not decoration. Output is priced at four
            # times input on the decided model, so a total cannot be turned into
            # a cost without it, and two runs of the same total can differ by a
            # factor in what they cost. ``reasoning_tokens`` is a breakdown of
            # ``completion_tokens`` and ``cached_tokens`` a breakdown of the
            # prompt, so neither is added to the billed figure.
            "prompt_tokens": consumed.prompt_tokens,
            "completion_tokens": consumed.completion_tokens,
            "reasoning_tokens": consumed.reasoning_tokens,
            "cached_tokens": consumed.cached_tokens,
            "failed": tokens_failed.as_dict(),
            # And the same for the results that were reused rather than run. A
            # re-run consumes nothing, so without this the figures that turn
            # those results into a price would be gone from the record that
            # describes the invocation reading them.
            "reused": tokens_reused.as_dict(),
            # The borrowed advocates' own usage, which was billed to the run that
            # made the calls. Named apart from every figure above because it is
            # the one number in this block that this invocation did not spend, and
            # a reader who added it to the others would overstate the run.
            "replayed": tokens_replayed.as_dict(),
            "billed_to_another_run": tokens_replayed.billed,
            # The window this invocation ran in is ``started_at``/``ended_at``
            # above, which is what says which price band applied: peak hours are
            # 09:00-12:00 and 14:00-18:00 Singapore time on weekdays.
        },
        # Present only when the advocates were replayed, and ``None`` otherwise so
        # that "this invocation called every agent itself" is a fact this file
        # states rather than one a reader infers from an absent key. It sits at
        # the top level rather than inside the token block because it is not a
        # figure: it is what this run is.
        "replay": replay_block,
        "cases": {
            "scope": "this invocation only",
            "requested": list(requested),
            "completed": [o.case_no for o in outcomes if o.status == STATUS_COMPLETED],
            "cached": [o.case_no for o in outcomes if o.status == STATUS_CACHED],
            "failed": [o.case_no for o in failed],
        },
        # The directory, as opposed to the invocation. These are the results a
        # grader reading this directory will actually find, whoever produced
        # them, and they are what the staleness of the set is measured over.
        "directory": {
            "path": str(run_dir),
            "cached_cases": directory_cases,
            "cached_case_count": len(directory_cases),
            "holds_results_from_earlier_invocations": sorted(directory_cases)
            != sorted(set(requested)),
            "note": (
                "cached_cases is every result in this directory, whoever "
                "produced it. cases.requested is only what this invocation was "
                "asked for, so a directory holding more results than that holds "
                "results from earlier invocations; their provenance is in "
                "{0}.".format(INVOCATIONS_FILE)
            ),
        },
        "failures": [
            {
                "case_no": outcome.case_no,
                "failed_agent": outcome.failed_agent,
                # The kind is a field of its own, not a word inside the reason,
                # so a reader can group and count failures without parsing
                # prose. `reason` still leads with the same word and still
                # carries the exception's own text as evidence.
                "failure_kind": outcome.failure_kind,
                "reason": outcome.failure_reason,
            }
            for outcome in failed
        ],
    }


# --------------------------------------------------------------------------
# Grading a run off disk
# --------------------------------------------------------------------------
def amount_provenance(ruling: Any, brief_object: Any) -> Dict[str, str]:
    """Where each money field's figure came from, as the brief knows it.

    Four answers, and they are kept apart rather than folded together:

    * the path of the money-block figure the amount equals, or the paths of the
      two or three figures it is the sum of -- the figure or figures it reads
      off;
    * ``"unverifiable: not structured"`` when the figure governing the amount
      is one the block names as prose-only, so there is nothing to read it off;
    * ``"n/a"`` when the field carries no amount at all, which is what an
      ``ESCALATE`` and a ``NO_ACTION`` both do;
    * ``"not a published figure"`` when the amount is a number and reads off
      nothing. That is not one of the three answers the report asks for, and it
      is the answer that matters most: it is a draft's own number, and the
      record says so rather than leaving the cell blank.

    It is here rather than beside the explanation tags in :mod:`eval.grade`
    because answering it means reading the money block of a brief, and the
    grader may not import the package that builds one -- its whole dependency
    on ``tribunal`` is the ruling vocabulary, which is what keeps a key value
    from ever reaching a prompt, a brief or a transcript. The tags stay in the
    grader because deciding one needs nothing but a regular expression.
    """
    inner = ruling.get("ruling") if isinstance(ruling, Mapping) else None
    if not isinstance(inner, Mapping):
        return {name: "n/a" for name in pipeline.MONEY_FIELDS}
    block = pipeline.money_block(brief_object)
    figures = pipeline.published_money_figures(block)
    value = inner.get("ruling")
    found: Dict[str, str] = {}
    for name in pipeline.MONEY_FIELDS:
        amount = pipeline.as_money(inner.get(name))
        if amount is None:
            found[name] = "n/a"
            continue
        read = pipeline.amount_reads_off(amount, figures)
        if read is not None:
            found[name] = read
            continue
        reason = pipeline.unverifiable_amount_reason(value, block, figures)
        found[name] = reason if reason is not None else "not a published figure"
    return found


def _decimal_or_none(value: Any) -> Optional[Decimal]:
    """A recorded number as the ``Decimal`` the report renders, or ``None``.

    A wall clock and a vote agreement come off the cache as binary numbers. The
    report carries them as ``Decimal`` -- the same type, and the same single
    conversion path, every other number in this report arrives by. That is not
    a claim that a duration is money; it is what keeps the printed value a
    value a reader can copy. A value that is not a finite number is ``None``
    rather than ``0``: "not recorded" and "recorded as zero" are different
    findings and the report keeps them apart.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        converted = Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return None
    return converted if converted.is_finite() else None


def case_facts(
    run_dir: Path,
    case_no: int,
    document: Mapping[str, Any],
    case_loader: Optional[Callable[[int], Mapping[str, Any]]] = None,
    policy_version: int = policy_versions.BASE_VERSION,
) -> grade.CaseFacts:
    """The cost, the wall clock, the vote and the provenance of one cached case.

    Everything here is read off an artifact the case wrote, and everything is
    computed by code:

    * the token split is summed off the case's own transcript, by role, so the
      advocates' share and the judge's share are the transcript's own figures
      rather than a second accounting of them. A case with no transcript has no
      split, which is ``None`` and not ``0 / 0``;
    * the wall clock and the vote agreement are read off the cache entry, which
      is where the case recorded them;
    * the amount provenance is computed from the brief **this code builds now**,
      so it describes the brief the case would be decided under rather than a
      copy of one. A brief that cannot be built answers so explicitly rather
      than answering a wrong provenance;
    * the explanation tags are matched over the ruling's own explanation text.

    ``policy_version`` is the version that brief is built at, and it is the
    caller's to give: a set whose registration fixes a later version records its
    cases at that version, and a provenance computed from a version-1 brief
    would be the provenance of a brief no agent of that run ever saw. It
    defaults to the base version, which is what every corpus caller passes by
    passing nothing.

    For a replayed case the advocate share is what those calls cost the run that
    made them, because the copied entries carry the usage figures they were
    recorded with. The report's replay block is what says the run did not pay
    for them.
    """
    advocate_tokens = 0
    judge_tokens = 0
    seen = False
    transcript_document = read_json(transcript_path(run_dir, case_no))
    if isinstance(transcript_document, Mapping):
        for entry in transcript_document.get("entries") or []:
            if not isinstance(entry, Mapping):
                continue
            seen = True
            tokens = billed_tokens(
                entry.get("prompt_tokens"), entry.get("completion_tokens")
            )
            if entry.get("role") == transcript.ROLE_JUDGE:
                judge_tokens += tokens
            else:
                advocate_tokens += tokens

    ruling = document.get("ruling")
    inner = ruling.get("ruling") if isinstance(ruling, Mapping) else None
    explanation = inner.get("explanation") if isinstance(inner, Mapping) else None

    load = loader.load_case if case_loader is None else case_loader
    try:
        brief_object: Optional[Mapping[str, Any]] = brief.build_brief_for_case(
            load(case_no), policy_version=policy_version
        )
    except Exception:  # noqa: BLE001 - a brief that cannot be built yields no provenance
        brief_object = None

    if brief_object is None:
        # Named rather than left blank: a reader must be able to tell "the brief
        # could not be rebuilt" from "the ruling carried no amount".
        provenance = {name: "brief not available" for name in pipeline.MONEY_FIELDS}
    else:
        provenance = amount_provenance(ruling, brief_object)

    return grade.CaseFacts(
        advocate_tokens=advocate_tokens if seen else None,
        judge_tokens=judge_tokens if seen else None,
        wall_seconds=_decimal_or_none(document.get("wall_seconds")),
        vote_agreement=_decimal_or_none(document.get("vote_agreement")),
        amount_provenance=provenance,
        explanation_tags=grade.explanation_tags(explanation),
    )


def grade_run(
    run_dir: Path,
    key: Optional[Mapping[int, grade.Ruling]] = None,
    cases: Optional[Sequence[int]] = None,
    checker: Optional[BriefStaleness] = None,
    case_loader: Optional[Callable[[int], Mapping[str, Any]]] = None,
    policy_version: int = policy_versions.BASE_VERSION,
) -> grade.GradeReport:
    """Grade a run's cached rulings, and say which of them the code has moved past.

    Graded over the cases the run actually covers, so a partial run reports an
    accuracy over what it ran rather than over 29 cases of which it produced
    eleven. The key is loaded and used by :mod:`eval.grade`; this function never
    opens the key itself.

    The staleness check belongs here rather than with the caller, because this
    is where a cached result is read as evidence. Each cached case carries the
    digest of the brief its agents were handed, so rebuilding that case's brief
    now and comparing the two digests says whether the result still belongs to
    this code. A case whose brief has changed is reported as stale — named and
    counted — and never silently folded into a score.

    The replay facts are collected here for the same reason and from the same
    place: a cached entry says whether its advocates were reused from another
    run, and the report has to be able to say so beside every figure it prints.
    ``checked`` is True whenever this function ran at all -- it read every entry,
    so "nothing was replayed" is a finding rather than an absence.

    The per-case facts are collected here too, and for the same reason: this is
    the one place every artifact a case wrote is already being read, so the
    report's cost, wall-clock, vote, provenance and explanation columns are
    filled from the same pass that reads the ruling. ``case_loader`` is how a
    development set's cases are named when the brief is rebuilt for the amount
    provenance; the corpus loader is the default, and a set that does not pass
    its own would have every one of its cases report an unavailable brief.

    ``policy_version`` is the version those briefs are rebuilt at, and it is
    passed on to :func:`case_facts` for the reason it is given there: the
    provenance column has to describe the brief the run was actually decided
    under. The base version is the default, so a corpus caller passes nothing.
    The *staleness* channel is not read off this parameter -- it is the
    checker's own -- which is why a caller that wants a later version compared
    passes a checker built at it as well.
    """
    resolved_key: Mapping[int, grade.Ruling] = (
        grade.load_answer_key() if key is None else dict(key)
    )
    covered = (
        sorted(case_no for case_no in cached_case_numbers(run_dir) if case_no in resolved_key)
        if cases is None
        else sorted(case_no for case_no in cases if case_no in resolved_key)
    )

    produced: Dict[int, Any] = {}
    facts: Dict[int, grade.CaseFacts] = {}
    replayed_cases: List[int] = []
    replay_sources: List[str] = []
    replay_tokens = 0
    for case_no in covered:
        document = load_cached(run_dir, case_no)
        if document is None:
            continue
        produced[case_no] = document.get("ruling")
        # Before the replay branch's ``continue``: a replayed case has facts of
        # its own -- a wall clock, a vote, an explanation -- and skipping them
        # would blank its row for a reason that has nothing to do with them.
        facts[case_no] = case_facts(
            run_dir, case_no, document, case_loader, policy_version
        )
        replay = document.get("replay")
        if not isinstance(replay, Mapping):
            continue
        replayed_cases.append(case_no)
        source = replay.get("run_dir")
        if isinstance(source, str) and source and source not in replay_sources:
            replay_sources.append(source)
        replay_tokens += _as_int((replay.get("tokens") or {}).get("total_tokens"))

    staleness = brief_staleness(run_dir, covered, checker)

    subset = {case_no: resolved_key[case_no] for case_no in covered}
    # The whole key travels with the subset so the report knows whether the
    # rates it prints may be compared to the published target. Grading a partial
    # run over the cases it actually ran is right; printing that subset's
    # escalation rate beside the corpus base rate is not, and the report can
    # only withhold the comparison if it is told which set it is describing.
    return grade.grade(
        produced,
        subset,
        corpus=resolved_key,
        staleness=staleness,
        replay=grade.ReplayFacts(
            checked=True,
            sources=tuple(replay_sources),
            cases=tuple(replayed_cases),
            tokens=replay_tokens,
        ),
        facts=facts,
    )


# --------------------------------------------------------------------------
# Comparing cached runs
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ComparisonRow:
    """One model's numbers, read entirely off disk. No model call is made.

    ``grades_full_corpus`` and ``graded_cases`` travel with the row because the
    table's rates are only comparable to the corpus base rate when the graded
    set *is* the corpus, and the intersection of two partial runs is usually not.
    """

    model: str
    working_tree_clean: Optional[bool]
    cases_graded: int
    cases_cached: int
    graded_cases: Tuple[int, ...]
    grades_full_corpus: bool
    exact_matches: int
    field_correct: Dict[str, int]
    escalation_rate: Optional[Decimal]
    target_rate: Decimal
    precision: Optional[Decimal]
    recall: Optional[Decimal]
    over_escalations: int
    under_escalations: int
    indeterminate_ruled_confidently: int
    mean_latency_seconds: Optional[float]
    total_tokens: int
    # The interpreters that produced the results in this directory, as each
    # cached case recorded them. Empty when the cache predates the field.
    # Carried on the row because a digest comparison is only readable against
    # it: the brief's bytes were once a function of the interpreter, so a
    # disagreement may be interpreter drift rather than code drift.
    python_versions: Tuple[str, ...] = ()
    staleness: grade.Staleness = grade.Staleness()
    # The runs whose advocates these results reused, read off the cache entries
    # rather than off ``run.json``: ``run.json`` describes the last invocation and
    # the entries describe the results, which is the question a table of figures
    # is asking. Empty when this run's advocates were all called by it.
    replay_sources: Tuple[str, ...] = ()


def _row_from_run(
    run_dir: Path,
    cases: Sequence[int],
    key: Mapping[int, grade.Ruling],
    checker: Optional[BriefStaleness] = None,
) -> ComparisonRow:
    """Build one comparison row from a run directory."""
    metadata = read_json(metadata_path(run_dir))
    if not isinstance(metadata, dict):
        metadata = {}

    cached = cached_case_numbers(run_dir)
    covered = [case_no for case_no in cases if case_no in set(cached)]

    report = grade_run(run_dir, key, covered, checker)

    durations: List[float] = []
    tokens = 0
    interpreters: List[str] = []
    replay_sources: List[str] = []
    for case_no in covered:
        document = load_cached(run_dir, case_no)
        if document is None:
            continue
        durations.append(_as_seconds(document.get("wall_seconds")))
        tokens += _as_int((document.get("tokens") or {}).get("total_tokens"))
        recorded = document.get("python_version")
        if isinstance(recorded, str) and recorded:
            interpreters.append(recorded)
        # Read per case rather than once from the metadata, because a directory
        # can hold results from more than one invocation and only the entries say
        # which of them reused another run's advocates.
        replayed = document.get("replay")
        if isinstance(replayed, Mapping):
            source = replayed.get("run_dir")
            if isinstance(source, str) and source and source not in replay_sources:
                replay_sources.append(source)

    calibration = report.calibration
    return ComparisonRow(
        model=str(metadata.get("model") or run_dir.name),
        working_tree_clean=metadata.get("working_tree_clean"),
        cases_graded=report.total,
        cases_cached=len(cached),
        graded_cases=report.graded_cases,
        grades_full_corpus=report.grades_full_corpus,
        exact_matches=report.exact_matches,
        field_correct={name: report.field_tally(name)[0] for name in grade.GRADED_FIELDS},
        escalation_rate=calibration.rate,
        target_rate=calibration.target_rate,
        precision=calibration.precision,
        recall=calibration.recall,
        over_escalations=len(calibration.over_escalations),
        under_escalations=len(calibration.under_escalations),
        indeterminate_ruled_confidently=len(calibration.indeterminate_ruled_confidently),
        mean_latency_seconds=(sum(durations) / len(durations)) if durations else None,
        total_tokens=tokens,
        python_versions=tuple(sorted(set(interpreters))),
        staleness=report.staleness,
        replay_sources=tuple(replay_sources),
    )


def collect_comparison(
    runs_dir: Path = RUNS_DIR,
    key: Optional[Mapping[int, grade.Ruling]] = None,
) -> List[ComparisonRow]:
    """One row per cached run, over the case set every run has in common.

    Compared on the intersection rather than each on its own cases, because a
    table that scores one model over 29 cases and another over 11 is not a
    comparison. Each row still reports how many cases it has cached, so a
    model that covered less of the corpus is visible rather than hidden.
    """
    resolved_key: Mapping[int, grade.Ruling] = (
        grade.load_answer_key() if key is None else dict(key)
    )
    if not Path(runs_dir).is_dir():
        return []

    directories = sorted(
        path
        for path in Path(runs_dir).iterdir()
        if path.is_dir() and cached_case_numbers(path)
    )
    per_run = {directory: cached_case_numbers(directory) for directory in directories}
    if not per_run:
        return []

    common = set.intersection(*(set(numbers) for numbers in per_run.values()))
    shared = sorted(case_no for case_no in common if case_no in resolved_key)

    # One checker per row, because the prompt channel is answered from each
    # directory's own transcripts -- but one **shared** brief memo across them
    # all: the current brief for a case is the same question whichever run
    # directory is asking it, and rebuilding it once per directory would be the
    # same answer computed twice.
    memo: Dict[int, Optional[str]] = {}

    def shared_digest(case_no: int) -> Optional[str]:
        if case_no not in memo:
            memo[case_no] = current_brief_sha256(case_no)
        return memo[case_no]

    return [
        _row_from_run(
            directory,
            shared,
            resolved_key,
            BriefStaleness(shared_digest, run_dir=directory),
        )
        for directory in directories
    ]


def _render_tree_flag(clean: Optional[bool]) -> str:
    """The clean-tree flag, spelled out. ``unknown`` is not ``clean``."""
    if clean is True:
        return "clean"
    if clean is False:
        return "DIRTY"
    return "unknown"


def _render_cached_cell(staleness: grade.Staleness) -> str:
    """The ``cached`` cell: what this code can say about the results it reads.

    ``n/a`` when nobody checked, which is not ``0``: a count of zero asserts
    that every cached brief was rebuilt and matched, and that claim is only
    available if it was actually made.

    The cell names which digest moved rather than printing a bare count. A row
    reading ``12`` would be read as "twelve briefs moved", and a result whose
    prompts moved instead is not that: one means the facts the agents were
    handed changed, the other that their instructions did. It reports the
    uncheckable results too, for the same reason -- a row that could say nothing
    about its prompts must not show a bare ``0`` and read as though it had.
    """
    if not staleness.checked:
        return "n/a"
    parts: List[str] = []
    if staleness.stale:
        moved: List[str] = []
        for case_no in staleness.stale:
            for name in staleness.moved_for(case_no):
                if name not in moved:
                    moved.append(name)
        parts.append(
            "{0} stale{1}".format(
                len(staleness.stale),
                " ({0})".format(", ".join(moved)) if moved else "",
            )
        )
    if staleness.unknown:
        parts.append("{0} unknown".format(len(staleness.unknown)))
    if not parts:
        return "current"
    return ", ".join(parts)


def render_comparison(rows: Sequence[ComparisonRow]) -> str:
    """One table: per model, accuracy, calibration, latency and tokens.

    This is the number that decides which model is frozen, so the tree flag is a
    column rather than a footnote: a row whose tree was dirty carries an
    accuracy nobody can reproduce, and the table has to say so on its face.
    """
    if not rows:
        return (
            "No cached runs found. Run a benchmark first, then compare:\n"
            "  python -m eval.run_benchmark --model MODEL --cases 101,102,103\n"
        )

    headers = [
        "model",
        "tree",
        "cases",
        "cached",
        "exact",
        "ruling",
        "amount",
        "driver",
        "refs",
        "esc",
        "prec",
        "rec",
        "over",
        "under",
        "s/case",
        "tokens",
    ]

    cells: List[List[str]] = []
    for row in rows:
        denominator = row.cases_graded
        cells.append(
            [
                row.model,
                _render_tree_flag(row.working_tree_clean),
                str(denominator),
                _render_cached_cell(row.staleness),
                "{0}/{1}".format(row.exact_matches, denominator),
                "{0}/{1}".format(row.field_correct["ruling"], denominator),
                "{0}/{1}".format(row.field_correct["amount_sgd"], denominator),
                "{0}/{1}".format(row.field_correct["driver_compensation_sgd"], denominator),
                "{0}/{1}".format(row.field_correct["referrals"], denominator),
                grade.render_percent(row.escalation_rate),
                grade.render_ratio(row.precision),
                grade.render_ratio(row.recall),
                str(row.over_escalations),
                str(row.under_escalations),
                "n/a" if row.mean_latency_seconds is None else "{0:.1f}".format(row.mean_latency_seconds),
                "{0:,}".format(row.total_tokens),
            ]
        )

    widths = [
        max(len(headers[index]), *(len(row[index]) for row in cells))
        for index in range(len(headers))
    ]

    def render_row(values: Sequence[str]) -> str:
        return "  ".join(
            value.ljust(widths[index]) for index, value in enumerate(values)
        ).rstrip()

    lines = [
        render_row(headers),
        "  ".join("-" * width for width in widths),
    ]
    lines.extend(render_row(values) for values in cells)

    target = rows[0].target_rate
    confidently_wrong = sum(row.indeterminate_ruled_confidently for row in rows)
    lines.append("")
    lines.append(
        "Cases graded is the set every run has cached in common; each run's own "
        "cached count may be larger."
    )
    if all(row.grades_full_corpus for row in rows):
        lines.append(
            "esc is the escalation rate against the {0} target; over and under are "
            "separate counts and are never summed. A run confident on an "
            "INDETERMINATE case is wrong in the way that matters most.".format(
                grade.render_percent(target)
            )
        )
    else:
        lines.append(
            "The set graded here is {0}, which is not the whole corpus, so esc, "
            "prec and rec are rates on that set and the corpus target is not "
            "printed beside them: every rate moves with the base rate of the set "
            "it was computed on, and only the counts survive subsetting. over and "
            "under are separate counts and are never summed. A run confident on "
            "an INDETERMINATE case is wrong in the way that matters most.".format(
                ", ".join(str(case_no) for case_no in rows[0].graded_cases) or "empty"
            )
        )
    if confidently_wrong:
        lines.append(
            "INDETERMINATE cases ruled confidently instead of escalated: {0} "
            "across these runs.".format(confidently_wrong)
        )

    # Which interpreter produced these results, when it is not the one checking.
    # The brief's bytes were once a function of the interpreter, so a reader
    # deciding whether a disagreement is code drift needs this beside it. A
    # cache that predates the field says nothing here rather than guessing.
    running = interpreter_version()
    elsewhere = [
        row for row in rows if row.python_versions and running not in row.python_versions
    ]
    if elsewhere:
        lines.append("")
        lines.append(
            "This check is running under Python {0}; these results were produced "
            "under another interpreter. The brief's accumulation is pinned, so the "
            "digests are still comparable -- but a disagreement between them may be "
            "interpreter drift rather than code drift.".format(running)
        )
        for row in elsewhere:
            lines.append(
                "  {0}  produced under: {1}".format(
                    row.model, ", ".join(row.python_versions)
                )
            )

    mixed_rows = [row for row in rows if row.staleness.mixed]
    if mixed_rows:
        lines.append("")
        lines.append(
            "cached says what this code can establish about the results it read. "
            "Every cached case records the digest of the brief its agents were "
            "handed and the digest of the prompts they were given; both are "
            "rebuilt now and compared with what was recorded. The two are "
            "different findings -- the facts changed, or the instructions did -- "
            "and they are named apart below rather than merged into one word."
        )
        for row in mixed_rows:
            if row.staleness.stale_brief:
                lines.append(
                    "  {0}  brief moved: {1}".format(
                        row.model,
                        ", ".join(str(case_no) for case_no in row.staleness.stale_brief),
                    )
                )
            if row.staleness.stale_prompts:
                lines.append(
                    "  {0}  prompts moved: {1}".format(
                        row.model,
                        ", ".join(str(case_no) for case_no in row.staleness.stale_prompts),
                    )
                )
            if row.staleness.unchecked_prompts:
                lines.append(
                    "  {0}  no prompts digest recorded, so the prompt half of the "
                    "check could not be made: {1}".format(
                        row.model,
                        ", ".join(
                            str(case_no) for case_no in row.staleness.unchecked_prompts
                        ),
                    )
                )
            if row.staleness.unknown:
                lines.append(
                    "  {0}  could not be checked: {1}".format(
                        row.model,
                        ", ".join(str(case_no) for case_no in row.staleness.unknown),
                    )
                )
        lines.append(
            "A mixed set is not one run. The exact-match figure for a row with "
            "stale or uncheckable cases was computed over results produced by more "
            "than one version of the brief or the prompts, so it is not a single "
            "measurement of any one version of this code."
        )

    # Beside the table, not in a footnote, and for the same reason the tree flag
    # is a column: a row whose advocates came from another run is a different
    # measurement, and the numbers above it must not be read as the same kind.
    replayed_rows = [row for row in rows if row.replay_sources]
    if replayed_rows:
        lines.append("")
        lines.append(
            "advocates replayed: for these rows the rider and driver outputs were "
            "reused from another run and only the judge was called, so their "
            "figures measure the judge on fixed inputs and not the whole pipeline. "
            "The borrowed calls' own tokens are not in the token column, which is "
            "this run's own bill."
        )
        for row in replayed_rows:
            lines.append(
                "  {0}  advocates from: {1}".format(
                    row.model, ", ".join(row.replay_sources)
                )
            )

    lines.append(
        "tree is the working-tree flag from the run's own metadata: a number "
        "from a DIRTY tree, or one whose state is unknown, cannot be reproduced."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def parse_cases(text: Optional[str]) -> List[int]:
    """``"101,102,103"`` as case numbers. An empty selection means "all"."""
    if text is None or not text.strip():
        return []
    numbers: List[int] = []
    for token in text.replace(" ", "").split(","):
        if not token:
            continue
        if not token.isdigit():
            raise BenchmarkError(
                "case selection {0!r} is not a case number; use a comma-separated "
                "list such as 101,102,103".format(token)
            )
        numbers.append(int(token))
    return numbers


# What a sealed set's invocation says when the protocol left it nothing to run.
# One line, because there is nothing else to say: no case was called, and the
# summary below would be a list of the limits this invocation was given.
NOTHING_LEFT_TO_RUN = "nothing left to run under the sealed protocol"


def print_summary(summary: RunSummary) -> None:
    """A short block a person reads at the end of a run."""
    if summary.sealed_nothing_to_run:
        # Before anything else, and instead of everything else: an invocation
        # that ran nothing because the sealed protocol left nothing is a
        # different statement from a run that produced nothing, and the block
        # below cannot make it.
        print(NOTHING_LEFT_TO_RUN)
        return
    provenance_ = summary.provenance
    commit = provenance_.get("git_commit")
    tree = _render_tree_flag(provenance_.get("working_tree_clean"))

    print("")
    print("run         {0}  ->  {1}".format(summary.model, summary.run_dir))
    print(
        "provenance  commit {0}, tree {1}, prompts {2}, key {3}".format(
            (commit or "unknown")[:12],
            tree,
            str(provenance_.get("prompts_sha256") or "")[:12],
            str(provenance_.get("answer_key_sha256") or "")[:12],
        )
    )
    # Stated before the figures rather than after them, because it changes what
    # every figure below is a measurement of. A reader who learns it last has
    # already read the accuracy as a whole-pipeline number.
    if summary.replay is not None:
        source = summary.replay
        # The count is this invocation's own, read off its outcomes and not off
        # the source block beside it. The block's ``replayed_cases`` is every
        # case the acceptance check accepted before the run started, and a run
        # that stopped early -- on its token budget, say -- never replayed the
        # cases it did not reach. Counting those printed "29 of 25 cases reused
        # them" on a twenty-five-case run: more cases reused than were run.
        print(
            "replay      advocates from {0}: {1} of {2} cases reused "
            "them and only the judge was called".format(
                source.get("run_dir"),
                len(summary.replayed_cases),
                len(summary.outcomes),
            )
        )
        # Two commits, because the source directory's is not the advocates'.
        # ``git_commit`` is what that directory recorded, and a replay into the
        # directory it reads from makes it the commit of the run that *copied*
        # them; printed alone it would read as the run that made them. The
        # commit that made them travels per case, and this is where the run
        # level collects it.
        made = source.get("advocate_commits") or []
        print(
            "            those advocates were made at commit {0}; the directory "
            "they were copied from records commit {1}".format(
                ", ".join(str(commit)[:12] for commit in made)
                or "an unrecorded commit",
                str(source.get("git_commit") or "unknown")[:12],
            )
        )
        if source.get("refused_cases"):
            print(
                "            refused, and no call made for them: {0}".format(
                    ", ".join(str(case_no) for case_no in source["refused_cases"])
                )
            )
    print(
        "cases       {0} completed, {1} cached, {2} failed".format(
            len(summary.completed_cases),
            len(summary.cached_cases),
            len(summary.failures),
        )
    )
    if summary.precedents_excluded is not None:
        # Printed on every run with the block on, not only when something was
        # left out: a reader has to be able to tell a figure over the whole set
        # from a figure over a subset, and "no case was left out" is a finding
        # rather than silence.
        print(
            "precedents  the judge was shown earlier human closures; {0}".format(
                "no covered case is the source of one"
                if not summary.precedents_excluded
                else "left out of every figure above: {0}".format(
                    ", ".join(str(case_no) for case_no in summary.precedents_excluded)
                )
            )
        )
        print("            {0}".format(PRECEDENTS_INCOMPARABLE_NOTE))
    if summary.refusals:
        print(
            "            {0} of the failures were replay refusals: the source run "
            "could not supply those advocates, so no model was called and they "
            "say nothing about the model".format(len(summary.refusals))
        )
    # The limits are printed on every run, not only when one was hit. A result
    # produced under a 600-second timeout is not the same measurement as one
    # produced under 120 seconds, and a case stopped at a 2400-second deadline is
    # not the same measurement as one stopped at 241 minutes. The reader should
    # not have to open the metadata to find out which they are looking at.
    print(
        "limits      timeout {0:g}s per attempt, case deadline {1:g}s, "
        "concurrency {2}".format(
            summary.timeout_seconds, summary.case_deadline_seconds, summary.concurrency
        )
    )
    if summary.timeouts:
        print(
            "            {0} of the failures were timeouts: the client stopped "
            "waiting, which is answered with a longer timeout or a faster model "
            "rather than a retry".format(len(summary.timeouts))
        )
    if summary.deadlines:
        print(
            "            {0} of the failures hit a deadline: the run stopped "
            "itself rather than starting work it had no time to finish, which is "
            "answered by raising the deadline or using a faster model".format(
                len(summary.deadlines)
            )
        )
    print(
        "tokens      {0:,} charged to the budget, {1:,} reused from cache".format(
            summary.tokens_spent, summary.tokens_reused
        )
    )
    # The split, because it is what a cost is computed from: output is priced at
    # four times input on the decided model, so the total alone says nothing
    # about what the run cost.
    print(
        "            {0:,} in, {1:,} out ({2:,} of the output was reasoning)".format(
            summary.tokens_consumed.prompt_tokens,
            summary.tokens_consumed.completion_tokens,
            summary.tokens_consumed.reasoning_tokens,
        )
    )
    # The fourth figure, and the one no total above contains. A replayed case's
    # advocates were billed to the run they came from, so a reader comparing what
    # this run cost with what the case cost has to be able to see both — and the
    # line says which totals it is not part of, rather than leaving it to be
    # worked out.
    if summary.tokens_replayed.billed:
        print(
            "            plus {0:,} billed to the run the advocates came from, "
            "which this invocation did not spend and no figure above "
            "includes".format(summary.tokens_replayed.billed)
        )
    # Printed only when it is not zero. A line reporting zero on every clean run
    # would train the reader to skip the line that matters on the run where it
    # is not zero.
    if summary.tokens_failed.billed:
        print(
            "            plus {0:,} on cases that failed after their calls were "
            "made, which were billed all the same".format(
                summary.tokens_failed.billed
            )
        )
    if summary.token_budget is not None:
        print("budget      {0:,} (stopped on budget: {1})".format(
            summary.token_budget, summary.stop_reason == STOP_BUDGET
        ))
    print("stop        {0}".format(summary.stop_reason))

    if summary.failures:
        print("")
        if summary.sealed_protocol:
            # A sealed set's re-run is not a plain cache retry: the protocol
            # decides which failures are retried, and only the ones the
            # infrastructure caused are. "A re-run retries exactly these" would
            # promise the opposite of what this set's re-run does.
            print(
                "failed cases (a re-run applies the sealed protocol, which retries "
                "only the failures the infrastructure caused)"
            )
        else:
            print("failed cases (not cached, so a re-run retries exactly these)")
        for outcome in summary.failures:
            # The kind leads, because that is what the reader acts on, and it is
            # what distinguishes a case the client gave up on from a case the
            # model answered badly. The composed reason, note and all, is in the
            # metadata file; the terminal gets the evidence instead.
            print(
                "  case {0}  {1:<12} {2}".format(
                    outcome.case_no,
                    outcome.failure_kind or "FAILED",
                    (
                        outcome.failure_detail
                        or outcome.failure_reason
                        or "unknown failure"
                    ).splitlines()[0],
                )
            )

    if summary.report is not None:
        report = summary.report
        print("")
        print(
            "four-field exact match  {0}/{1} = {2}".format(
                report.exact_matches,
                report.total,
                grade.render_percent(
                    # The rounding mode is named rather than inherited from the
                    # decimal context, so the printed percentage does not depend
                    # on a caller having set one.
                    (
                        Decimal(report.exact_matches) / Decimal(report.total) * 100
                    ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                    if report.total
                    else None
                ),
            )
        )
        # Beside the figure rather than in a footnote, because a replayed run's
        # accuracy is the judge's: it was computed over inputs another run
        # produced, and it is not a measurement of the whole pipeline.
        if summary.replay is not None:
            print(
                "              advocates replayed from {0}: this is the judge's "
                "figure on fixed inputs, not a whole-pipeline measurement".format(
                    summary.replay.get("run_dir")
                )
            )
        for name in grade.GRADED_FIELDS:
            correct, total = report.field_tally(name)
            print("  {0:<24} {1}/{2}".format(name, correct, total))

        # Printed next to the figure it qualifies, and only when the check was
        # actually made. A run that reused a cached result produced by older
        # code is not reporting one measurement, and the number above it must
        # not be read as though it were.
        staleness = report.staleness
        if staleness.checked:
            if staleness.mixed:
                print("")
                print(
                    "cached        {0} of {1} results this code cannot vouch for".format(
                        len(staleness.stale) + len(staleness.unknown), report.total
                    )
                )
                if staleness.stale_brief:
                    print(
                        "              brief moved: {0}".format(
                            ", ".join(str(case_no) for case_no in staleness.stale_brief)
                        )
                    )
                if staleness.stale_prompts:
                    print(
                        "              prompts moved: {0}".format(
                            ", ".join(str(case_no) for case_no in staleness.stale_prompts)
                        )
                    )
                if staleness.stale_precedents:
                    print(
                        "              library moved: {0}".format(
                            ", ".join(
                                str(case_no) for case_no in staleness.stale_precedents
                            )
                        )
                    )
                if staleness.unchecked_prompts:
                    print(
                        "              no prompts digest recorded, so the prompt "
                        "half of the check could not be made: {0}".format(
                            ", ".join(
                                str(case_no) for case_no in staleness.unchecked_prompts
                            )
                        )
                    )
                if staleness.unknown:
                    print(
                        "              could not be checked: {0}".format(
                            ", ".join(str(case_no) for case_no in staleness.unknown)
                        )
                    )
                print(
                    "              a mixed set is not one run, so the exact-match "
                    "figure above is not a single measurement"
                )
            else:
                print(
                    "cached        all {0} results match the brief and the prompts "
                    "this code builds".format(report.total)
                )

        calibration = report.calibration
        print("")
        print(
            "cases graded  {0} of {1} in the corpus — {2}".format(
                calibration.total,
                report.corpus_size,
                "the whole corpus"
                if report.grades_full_corpus
                else "a selected subset: {0}".format(
                    ", ".join(str(case_no) for case_no in report.graded_cases)
                ),
            )
        )
        if report.grades_full_corpus:
            print(
                "escalation  {0}/{1} = {2}  (target {3})  precision {4}  recall {5}  "
                "over {6}  under {7}".format(
                    len(calibration.produced_escalations),
                    calibration.total,
                    grade.render_percent(calibration.rate),
                    grade.render_percent(calibration.target_rate),
                    grade.render_ratio(calibration.precision),
                    grade.render_ratio(calibration.recall),
                    len(calibration.over_escalations),
                    len(calibration.under_escalations),
                )
            )
        else:
            # The rate is printed, labelled with the set it was computed on. The
            # corpus target is not, because a rate moves with the base rate of
            # the set it was computed on and the set here was selected, not
            # sampled -- printing 2/3 = 66.7% beside 17.2% reads as
            # over-escalation when the subset was chosen to contain escalations.
            # The counts are what a reader can act on.
            print(
                "escalation  {0}/{1} = {2}  (on these {1} cases)  precision {3}  "
                "recall {4}  over {5}  under {6}".format(
                    len(calibration.produced_escalations),
                    calibration.total,
                    grade.render_percent(calibration.rate),
                    grade.render_ratio(calibration.precision),
                    grade.render_ratio(calibration.recall),
                    len(calibration.over_escalations),
                    len(calibration.under_escalations),
                )
            )
            print(
                "  rates on a selected subset are not comparable to the corpus "
                "base rate, so the corpus target is not printed beside them"
            )
            print("  raw counts")
            for label, case_numbers in (
                ("true positives", calibration.true_positives),
                ("false positives", calibration.false_positives),
                ("false negatives", calibration.false_negatives),
                ("over-escalations", calibration.over_escalations),
                ("under-escalations", calibration.under_escalations),
            ):
                print(
                    "    {0:<20} {1:>2}  {2}".format(
                        label,
                        len(case_numbers),
                        ", ".join(str(case_no) for case_no in case_numbers) or "none",
                    )
                )
        if calibration.indeterminate_ruled_confidently:
            print(
                "INDETERMINATE cases ruled confidently: {0}".format(
                    ", ".join(
                        str(case_no)
                        for case_no in calibration.indeterminate_ruled_confidently
                    )
                )
            )
    print("")
    print("report written to {0}".format(summary.run_dir / REPORT_FILE))


# --------------------------------------------------------------------------
# One converted external case, in its own place
# --------------------------------------------------------------------------
def external_run_name(case_path: Path) -> str:
    """The directory one external case runs into, under ``runs/external/``.

    A converted case lives at ``data/external/<name>/case-<n>.json`` and runs
    into ``runs/external/<name>/``. The name is taken from the case's own
    directory rather than minted, so a run directory and the case it came from
    are recognisable as each other. A case sitting directly in
    ``data/external/`` falls back to its own filename stem, which keeps two such
    cases from colliding in one directory.
    """
    path = Path(case_path)
    if path.parent.name == loader.EXTERNAL_DIR.name:
        return path.stem
    return path.parent.name


def external_expected_path(case_path: Path) -> Path:
    """The stated expectation belonging to one external case.

    ``eval/external/<name>/expected.json`` for the case at
    ``data/external/<name>/case-<n>.json`` -- the same name the run directory
    takes, so a case, its run and its stated expectation are recognisable as
    each other.

    Until a second external set existed there was one expectation file and it was
    printed beside every external case, which was right by accident because there
    was only one case. With fifteen more it would attribute the Ryde sample's
    stated answer to all of them, so the path is derived from the case and a case
    with no expectation of its own is reported as having none.
    """
    return EXTERNAL_EXPECTED_DIR / external_run_name(Path(case_path)) / EXTERNAL_EXPECTED_FILE


def assert_external_run_directory(run_dir: Path, runs_dir: Path) -> Path:
    """Refuse any external run directory that is not under ``runs/external/``.

    ``runs/deepseek-deepseek-flash/`` holds the 29-case result the submission
    reports. An external case is not one of the 29 and has no answer-key entry,
    so a case written there would change what that directory means while leaving
    every file a reader would look at apparently intact. The check is made
    rather than intended, so a caller cannot ask for the headline directory by
    accident and get it.

    A well-formed external destination is still refused when the runs root it
    belongs to is a sealed set's own root: ``--runs-dir runs/wild-v2`` puts
    ``runs/wild-v2/external/<name>/`` under a sealed root, and this command's
    own rule cannot see that because the destination is exactly where an
    external case belongs. That rule is
    :func:`eval.sealed_roots.refuse_a_sealed_destination`'s, so this command and
    every other one that writes to a named path refuse the same paths.
    """
    resolved = Path(run_dir).resolve()
    external_root = (Path(runs_dir) / EXTERNAL_RUNS_SUBDIR).resolve()
    if not resolved.is_relative_to(external_root):
        raise BenchmarkError(
            "an external case may only be written under runs/{0}/, and this one "
            "would go to {1}".format(EXTERNAL_RUNS_SUBDIR, resolved)
        )
    sealed_roots.refuse_a_sealed_destination(resolved, runs_dir)
    return resolved


def external_run_directory(runs_dir: Path, case_path: Path) -> Path:
    """``runs/external/<name>/`` for one case, checked before it is used."""
    return assert_external_run_directory(
        Path(runs_dir) / EXTERNAL_RUNS_SUBDIR / external_run_name(case_path), runs_dir
    )


def read_expected_outcome(path: Path = EXTERNAL_EXPECTED_PATH) -> Optional[Dict[str, Any]]:
    """The organisers' stated expectation, or ``None`` when it is not on disk."""
    document = read_json(Path(path))
    return document if isinstance(document, Mapping) else None


def format_external_result(
    outcome: CaseOutcome,
    case: Mapping[str, Any],
    expected: Optional[Mapping[str, Any]],
    run_dir: Path,
    expected_path: Optional[Path] = None,
) -> str:
    """The produced ruling beside the stated expectation, and no score.

    There is no four-field grading here and there must not be one. An external
    case has no entry in ``eval/answers/ground_truth.json``; giving it one would
    put a case into the frozen key that the key does not measure, and the key's
    whole value is that it is independent of the cases it grades. What is
    printed instead is what the run produced and what the organisers said they
    expected, labelled so the second cannot be read as a verified answer.

    The judge returns a **result object**, ``{"ruling": {...},
    "discarded_claims": [...]}``, so the four fields a reader wants are one
    level down from the object that arrives here. Reading them off the outer
    object printed ``None`` for all four while still printing the ruling word,
    which is why the ruling word alone is not evidence that they arrived. The
    unwrapping is ``eval.grade``'s, so the fields this prints and the fields the
    grader scores cannot come from different places.
    """
    lines = [
        "external case {0}  ({1})".format(case["case_no"], case["dispute"]["dispute_id"]),
        "  run directory : {0}".format(run_dir),
        "  status        : {0}".format(outcome.status),
    ]

    ruling = outcome.ruling
    if not isinstance(ruling, Mapping):
        lines.append(
            "  produced      : no ruling ({0})".format(
                outcome.failure_reason or outcome.failure_detail or "the case failed"
            )
        )
    else:
        # One level down, and through the grader's own unwrapping: the result
        # object nests the POL-GEN-03 ruling under ``ruling``. The isinstance
        # guard above is what keeps ``produced_from_mapping`` from raising --
        # it raises only on a record that is not an object.
        produced = grade.produced_from_mapping(ruling, case["case_no"])
        lines.append("  produced      : ruling {0}".format(produced.ruling))
        lines.append(
            "                  amount_sgd {0}   driver_compensation_sgd {1}".format(
                produced.amount_sgd, produced.driver_compensation_sgd
            )
        )
        lines.append("                  referrals {0}".format(list(produced.referrals)))
        lines.append("                  confidence {0}".format(produced.confidence))

    lines.append("  tokens billed : {0}".format(outcome.total_tokens))
    lines.append("  wall seconds  : {0:.1f}".format(outcome.wall_seconds))

    if expected is None:
        lines.append(
            "  organisers    : no stated expectation on disk at {0}".format(
                EXTERNAL_EXPECTED_PATH if expected_path is None else expected_path
            )
        )
    else:
        lines.append("  organisers    : {0}".format(expected.get("expected_outcome_as_stated")))
        lines.append(
            "                  ^ THE ORGANISERS' STATED EXPECTATION, NOT A VERIFIED ANSWER. "
            "This case has no entry in eval/answers/ground_truth.json and is not scored "
            "against one."
        )

    lines.append(
        "  score         : none. No answer-key entry exists for an external case, so no "
        "four-field grade is computed and none is reported."
    )
    return "\n".join(lines)


def run_external_case(
    case_path: Path,
    model: str,
    *,
    runs_dir: Path = RUNS_DIR,
    prompts_dir: Path = PROMPTS_DIR,
    timeout_seconds: float = llm.DEFAULT_TIMEOUT_SECONDS,
    case_deadline_seconds: float = pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
    judge_votes: int = pipeline.DEFAULT_JUDGE_VOTES,
    verify_drafts: bool = False,
    token_budget: Optional[int] = None,
    expected_path: Optional[Path] = None,
    client_factory: Optional[Callable[[Callable[[Dict[str, Any]], None]], Any]] = None,
    git_runner: Optional[Callable[[Sequence[str]], Optional[str]]] = None,
    progress: Callable[[str], None] = lambda text: print(text, flush=True),
    now: Callable[[], str] = lambda: datetime.now(timezone.utc).isoformat(),
) -> Tuple[CaseOutcome, Path]:
    """Arbitrate one converted external case, into ``runs/external/<name>/``.

    The case is loaded through its own explicit path, because it is deliberately
    absent from ``data/index.json``: the manifest indexes the 29-case corpus the
    submission reports, and adding a converted case to it would change that
    corpus. Everything after loading is the machinery a corpus case goes
    through -- the same single-case runner, the same cache document and
    transcript, the same provenance, the same case deadline, the same token
    accounting -- because it *is* that machinery, reached with a case in hand
    rather than a case number.

    Two things differ, and only two. The run directory is under
    ``runs/external/`` and is checked before anything is written, so an external
    case cannot land in a model's headline run directory. And the case is not
    graded: it has no answer-key entry, so the produced ruling is printed beside
    the organisers' stated expectation instead of being scored.

    The expectation printed is the one belonging to this case, found beside the
    case's own name under ``eval/external/``; a case with no expectation of its
    own is reported as having none. One sample's stated answer is not evidence
    about another case.

    ``client_factory`` exists for the same reason it does on
    :func:`run_benchmark`: a test can drive this end to end over a fake
    transport, with no network.

    ``token_budget`` is the same budget the corpus runner honours, applied the
    same way: it is checked before a case is issued. With one case there is no
    later case for the budget to be saved for, so a budget that cannot cover the
    case at all is refused rather than quietly ignored, and a budget that can
    cover it is recorded beside what the case spent.
    """
    if not model:
        raise BenchmarkError("model is required and has no default; name the model explicitly")
    if case_deadline_seconds <= 0:
        raise BenchmarkError(
            "case_deadline_seconds must be positive, got {0}".format(case_deadline_seconds)
        )
    if token_budget is not None and token_budget < 0:
        raise BenchmarkError("token_budget cannot be negative")
    if token_budget == 0:
        # The corpus runner would issue nothing and stop with STOP_BUDGET. There
        # is no later case here for the budget to be saved for, so the honest
        # answer is to say so rather than to run the case and ignore the flag.
        raise BenchmarkError(
            "a token budget of 0 cannot cover a case, and an external run is a single "
            "case: there is no later case to save the budget for. Pass a positive "
            "budget, or none."
        )

    case = loader.load_external_case(Path(case_path))
    case_no = case["case_no"]
    # The expectation belonging to THIS case, unless the caller named one. A
    # second external set has no expectation of its own yet, and the honest
    # output for it is "none on disk", not the Ryde sample's.
    if expected_path is None:
        expected_path = external_expected_path(Path(case_path))

    # Checked and created before a single call is made, so a bad destination
    # costs nothing and cannot be discovered after a paid run.
    run_dir = external_run_directory(runs_dir, Path(case_path))
    run_dir.mkdir(parents=True, exist_ok=True)

    run_provenance = provenance(
        model, prompts_dir=prompts_dir, runs_dir=runs_dir, git_runner=git_runner, now=now
    )

    # The same append-only log a corpus run keeps, under this case's own run
    # directory. An external case is not scored, so no ``grade`` event is
    # written; everything else -- the invocation, the case, every call, the
    # referee's decisions, the drafts, the vote and the final ruling -- is, and
    # in the same shape, because this is the same machinery.
    invocation_id = events.new_invocation_id(now)
    events_log = events.EventLog(
        run_dir / events.EVENTS_FILE,
        invocation_id=invocation_id,
        git_commit=run_provenance.get("git_commit"),
        prompts_sha256=run_provenance.get("prompts_sha256"),
        now=now,
    )
    events_log.record(
        events.EVENT_INVOCATION_START,
        model=model,
        cases=[case_no],
        external=True,
        timeout_seconds=timeout_seconds,
        case_deadline_seconds=case_deadline_seconds,
        token_budget=token_budget,
        judge_votes=judge_votes,
    )
    events_log.record(events.EVENT_CASE_START, case_no=case_no, position=1, total=1)

    build_client = (
        _default_client_factory(model, timeout_seconds)
        if client_factory is None
        else client_factory
    )

    # The client reports each call to this sink, exactly as it does for a corpus
    # case; the records are written to calls.json beside the result.
    records: List[Dict[str, Any]] = []
    client = build_client(records.append)

    outcome, document, transcript_json = run_one_case(
        case_no,
        client=client,
        prompts_dir=prompts_dir,
        # No expected ruling, so no match is computed and none is recorded.
        expected=None,
        case_provenance=run_provenance,
        case_deadline_seconds=case_deadline_seconds,
        loaded_case=case,
        judge_votes=judge_votes,
        verify_drafts=verify_drafts,
        events_log=events_log,
    )
    _persist(run_dir, outcome, document, transcript_json)
    events_log.record(
        events.EVENT_INVOCATION_END,
        stop_reason=STOP_COMPLETED if outcome.ok else STOP_FATAL,
        cases_graded=0,
        external=True,
        status=outcome.status,
        tokens_consumed=outcome.total_tokens,
    )

    metadata = dict(run_provenance)
    # _record_invocation keys its history on started_at, so the invocation's own
    # start is carried under that name; recorded_at means the same instant here.
    metadata.setdefault("started_at", metadata.get("recorded_at"))
    metadata.update(
        {
            # The id every line of this case's event log carries, so the
            # metadata and the log can be joined without matching timestamps.
            "invocation_id": invocation_id,
            "configuration": configuration_document(
                judge_votes=judge_votes, verify_drafts=verify_drafts
            ),
            "external": True,
            "external_case_no": case_no,
            "external_case_path": str(Path(case_path)),
            "expected_outcome_path": str(Path(expected_path)),
            "cases": [case_no],
            "token_budget": token_budget,
            "graded": False,
            "note": (
                "One converted external case, run into runs/external/ and never into a "
                "model's run directory. It has no entry in "
                "eval/answers/ground_truth.json, so it is not scored: the organisers' "
                "stated expectation is printed beside the produced ruling and is not an "
                "answer."
            ),
        }
    )
    write_json(metadata_path(run_dir), metadata)
    _record_invocation(run_dir, metadata)
    write_json(Path(run_dir) / CALLS_FILE, records)

    progress(
        format_external_result(
            outcome,
            case,
            read_expected_outcome(expected_path),
            run_dir,
            expected_path=Path(expected_path),
        )
    )
    return outcome, run_dir


# --------------------------------------------------------------------------
# The prompts directory a policy version is run with
# --------------------------------------------------------------------------
# A prompt set states the clause ids its policy carries. ``prompts/v1`` is
# written for versions 1 to 6 and ``prompts/v2`` for version 7 and later, whose
# clause ids start at 21 and none of whose version-6 ids exists. A run that
# pairs them the other way round hands the agents a prompt citing clauses their
# policy does not carry -- a version-7 run with the version-6 judge prompt would
# be told to cite POL-RD-10 and POL-NS-09, neither of which version 7 has -- so
# the pair is refused by name, in both directions, before a client is built.
V7_PROMPTS_DIR = PROJECT_ROOT / "prompts" / "v2"
V7_PROMPTS_VERSION = 7


def prompts_directory_for(policy_version: int) -> Path:
    """The prompts directory a policy version is run with."""
    return V7_PROMPTS_DIR if policy_version >= V7_PROMPTS_VERSION else PROMPTS_DIR


def mismatched_prompts_directory(
    policy_version: int, prompts_dir: Path
) -> Optional[str]:
    """Why this policy version and this prompts directory do not go together.

    ``None`` when they do. The message names both directories and the version,
    because the point of the refusal is that a reader can see which of the two
    moved.
    """
    wanted = prompts_directory_for(policy_version)
    named = Path(prompts_dir)
    try:
        same = named.resolve() == wanted.resolve()
    except OSError:  # pragma: no cover - a path that cannot be resolved
        same = named == wanted
    if same:
        return None
    return (
        "policy version {0} is run with {1}, and this invocation names {2}: a "
        "prompt set states the clause ids its policy carries, and prompts/v1 is "
        "written for versions 1 to 6 while prompts/v2 is written for version 7 "
        "and later".format(policy_version, wanted, named)
    )


def policy_version_argument(text: str) -> int:
    """``--policy-version`` as an integer, refused below 1 while it is read.

    Handed to ``argparse`` as the argument's ``type``, so a version below the
    lowest one is refused while the command line is being parsed -- before a
    client is built and before any destination is named. Version 0 is not a
    version this repository has ever had: version 1 is the three policy files
    exactly as committed, and version N applies the amendments ``0001``..``N-1``
    from ``policy/amendments/``.

    ``argparse.ArgumentTypeError`` rather than a ``ValueError`` because argparse
    prints that exception's message verbatim, and the message has to name the
    lowest version rather than the name of this function.
    """
    try:
        version = int(text)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            "--policy-version is an integer, and {0!r} is not".format(text)
        )
    if version < policy_versions.BASE_VERSION:
        raise argparse.ArgumentTypeError(
            "the lowest policy version is {0}, and {1} was asked for".format(
                policy_versions.BASE_VERSION, version
            )
        )
    return version


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.run_benchmark",
        description=(
            "Run cases against one model, cache every result under runs/, and "
            "grade the set. The model is the one recorded in tribunal/model.py "
            "unless --model names another."
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "the model id; when omitted the runtime model recorded in "
            "tribunal/model.py is used, and naming one here overrides it"
        ),
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="tabulate the runs already cached under runs/; makes no model call",
    )
    parser.add_argument(
        "--cases",
        default=None,
        help="comma-separated case numbers; default is every case in the answer key",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-run cases that are already cached",
    )
    parser.add_argument(
        "--token-budget",
        type=int,
        default=None,
        help="stop issuing new cases once the run has spent this many tokens",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help="cases to run at once; 1 (the default) is the deterministic order",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=llm.DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help=(
            "per-request read timeout for the client this run builds "
            "(default {0:g}, the client's own default; lower it deliberately for "
            "a quick probe)".format(llm.DEFAULT_TIMEOUT_SECONDS)
        ),
    )
    parser.add_argument(
        "--case-deadline",
        type=float,
        default=pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
        metavar="SECONDS",
        help=(
            "total time one case may consume, all three agent calls and any "
            "retry included (default {0:g}, the pipeline's own default; a case "
            "that exceeds it is recorded as a DEADLINE failure and the run "
            "continues)".format(pipeline.DEFAULT_CASE_DEADLINE_SECONDS)
        ),
    )
    parser.add_argument(
        "--judge-votes",
        type=int,
        default=pipeline.DEFAULT_JUDGE_VOTES,
        metavar="K",
        help=(
            "how many times to ask each case's judge on the same inputs, with the "
            "majority deciding (default {0}, the pipeline's own default). K = 1 is "
            "the single-draft behaviour every run before the vote used. Every "
            "draft is a call, so every draft is billed".format(
                pipeline.DEFAULT_JUDGE_VOTES
            )
        ),
    )
    parser.add_argument(
        "--replay-advocates",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help=(
            "reuse the rider and driver advocate outputs recorded in RUN_DIR's "
            "transcripts and call only the judge. Every case is checked first -- "
            "the brief this code builds, each advocate's rendered system prompt, "
            "the model and both recorded answers -- and a case the source cannot "
            "supply is recorded as a REPLAY failure with no call made. The tokens "
            "this run is billed are the judge's alone; the borrowed calls' own "
            "tokens are reported and never added to them. Replaying into a "
            "directory that already holds the results needs --force, because a "
            "cached case is reused rather than replayed"
        ),
    )
    parser.add_argument(
        "--replay-check",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help=(
            "report, case by case, whether --replay-advocates RUN_DIR would "
            "accept it and why not. Reads only: no model is called and nothing "
            "is written"
        ),
    )
    parser.add_argument(
        "--verify-drafts",
        action="store_true",
        help=(
            "after each case's drafts pass the code checks, ask a verifier once "
            "per case whether the brief supports every factual statement the "
            "drafts state; only a material contradiction makes a draft abstain. "
            "Off by default, needs a judge vote of at least 2, and every verifier "
            "call is billed"
        ),
    )
    parser.add_argument(
        "--verify-recorded-drafts",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help=(
            "reuse RUN_DIR's recorded judge drafts and call only the verifier, so "
            "that on and off are compared on the same drafts. A case whose "
            "recorded drafts were produced under a different brief or judge prompt "
            "is refused. Results go to runs/verify-recorded-drafts/<model>/, never "
            "into the headline run directory"
        ),
    )
    parser.add_argument(
        "--external",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "arbitrate one converted external case from PATH, writing it under "
            "runs/external/<name>/ and never into a model's run directory. The case "
            "has no answer-key entry, so the produced ruling is printed beside the "
            "organisers' stated expectation and no score is made"
        ),
    )
    parser.add_argument(
        "--ablate",
        choices=list(brief.ABLATIONS),
        default=None,
        metavar="NAME",
        help=(
            "build every case's brief with one thing removed, so the run measures "
            "the pipeline without it: {0}. Off by default. Results go to "
            "runs/ablation/<name>/<model>/, never into runs/<model>/ where the "
            "submission's figure lives, and the ablation is recorded in every "
            "artifact the run writes".format(", ".join(brief.ABLATIONS))
        ),
    )
    parser.add_argument(
        "--precedents",
        action="store_true",
        help=(
            "show the judge up to three earlier human closures from "
            "{0}, chosen because they share clauses with the case. Off by "
            "default. Results go to runs/precedents/<model>/, never into "
            "runs/<model>/ where the submission's figure lives, and the figures "
            "are not comparable to it: the library is built by people who have "
            "seen these sets".format(PRECEDENTS_STORE)
        ),
    )
    parser.add_argument(
        "--policy-version",
        type=policy_version_argument,
        default=DEFAULT_POLICY_VERSION,
        metavar="N",
        help=(
            "brief every case against policy version N: version 1 is the three "
            "policy files exactly as committed, and version N adds the amendments "
            "0001..N-1 from policy/amendments/. Off by default (version 1). "
            "Results for N >= 2 go to runs/policy-v<N>/<model>/, never into "
            "runs/<model>/ where the submission's figure lives, and the version "
            "is recorded in every artifact the run writes"
        ),
    )
    parser.add_argument(
        "--amount-rule",
        choices=list(pipeline.AMOUNT_RULES),
        default=pipeline.DEFAULT_AMOUNT_RULE,
        metavar="RULE",
        help=(
            "which rule reads a draft's amount off the brief's money block: "
            "published (the default) accepts a published figure or the sum of two "
            "or three of them, and signed also accepts a signed combination of "
            "two or three with the leading term positive and the result above "
            "zero. Off by default -- signed is measured, not adopted. A run under "
            "a non-default rule goes to runs/amount-rule/<rule>/<model>/, never "
            "into runs/<model>/ where the submission's figure lives"
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
            "case's configuration and it moves no run directory. It can still "
            "send requests a sequential run would not: up to two driver requests "
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
            "flight -- and it is refused for a sealed set, whose single run is "
            "one measurement. The position-swapped draft is always waited for, "
            "because the fairness measurement reads it; a draft the panel did "
            "not wait for is recorded as not_awaited and does not count. No "
            "individual request body changes, so it is not part of a case's "
            "configuration and it moves no run directory. It is refused with "
            "--verify-drafts, because the verifier can take a vote away after "
            "the panel has stopped waiting, and it has no effect on a panel of "
            "fewer than four drafts, where three drafts cannot be returned "
            "without the fourth"
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
            "configuration and it moves no run directory. It is refused for "
            "every sealed set, whose single run is one measurement and is not "
            "re-taken"
        ),
    )
    parser.add_argument(
        "--advocate-effort",
        choices=list(pipeline.ADVOCATE_EFFORTS),
        default=pipeline.ADVOCATE_EFFORT_DEFAULT,
        metavar="EFFORT",
        help=(
            "which reasoning effort the two advocates' requests carry: default "
            "(the default) leaves every request exactly as it is today, and none "
            "makes the two advocate requests carry reasoning_effort \"none\" "
            "while the judge's drafts and the verifier are untouched. It is a "
            "switch that changes what a run measures, so results go to "
            "runs/advocate-effort-<effort>/<set>/[policy-v<N>/]<model>/, never "
            "into a run directory holding a default result, and it is refused "
            "for every sealed set, whose single run is one measurement and is "
            "not re-taken. It may be given with --policy-version, whose "
            "directory sits under the switch's root, and it is refused beside "
            "--ablate, --precedents, --amount-rule and a replay"
        ),
    )
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--prompts-dir", type=Path, default=PROMPTS_DIR)
    args = parser.parse_args(argv)

    # The version and the prompt set are one pair. Refused before every other
    # check, so an invocation that names the wrong one is told about that rather
    # than about a switch it also named -- but only for a version this repository
    # has, because a version that names nothing is the runner's own refusal and
    # its message has to be the one that names it.
    try:
        highest = policy_versions.highest_available_version()
    except policy_versions.AmendmentError:
        highest = args.policy_version
    if args.policy_version <= highest:
        mismatch = mismatched_prompts_directory(args.policy_version, args.prompts_dir)
        if mismatch is not None:
            parser.error(mismatch)

    if args.ablate is not None:
        # An ablation changes what every agent is given, so it cannot be
        # combined with a mode that reads a run recorded without it or that
        # arbitrates a case outside the corpus. Every one of those would look as
        # though the ablation had been applied when it had not, so each is
        # refused here, before anything is read or written.
        if args.precedents:
            parser.error(
                "--ablate and --precedents cannot both be given: each changes "
                "what the agents are given, and a run with both on measures "
                "neither"
            )
        for present, name, why in (
            (args.compare, "--compare", "reads cached runs produced without it"),
            (
                args.replay_advocates is not None,
                "--replay-advocates",
                "reuses a recorded run's advocates, which were given the brief "
                "without it",
            ),
            (args.replay_check is not None, "--replay-check", "reads a recorded run"),
            (
                args.verify_recorded_drafts is not None,
                "--verify-recorded-drafts",
                "reuses a recorded run's drafts",
            ),
            (
                args.external is not None,
                "--external",
                "arbitrates a converted case in full, outside the corpus",
            ),
        ):
            if present:
                parser.error(
                    "--ablate builds an ablated brief and takes no {0}, which "
                    "{1}".format(name, why)
                )

    if args.precedents:
        # The block changes what the judge is given, so the same refusals apply
        # for the same reasons: every mode below reads or produces a run whose
        # judge saw no block, and naming the switch beside them would look as
        # though it had been shown.
        for present, name, why in (
            (args.compare, "--compare", "reads cached runs produced without it"),
            (
                args.replay_advocates is not None,
                "--replay-advocates",
                "reuses a recorded run's advocates, whose judge saw no block",
            ),
            (args.replay_check is not None, "--replay-check", "reads a recorded run"),
            (
                args.verify_recorded_drafts is not None,
                "--verify-recorded-drafts",
                "reuses a recorded run's drafts",
            ),
            (
                args.external is not None,
                "--external",
                "arbitrates a converted case in full, outside the corpus",
            ),
        ):
            if present:
                parser.error(
                    "--precedents shows the judge earlier closures and takes no "
                    "{0}, which {1}".format(name, why)
                )

    if args.policy_version != DEFAULT_POLICY_VERSION:
        # A later policy version changes what every agent is given, so the same
        # refusals apply for the same reasons: each mode below reads or produces
        # a run briefed at version 1, and naming the version beside one would
        # look as though the briefs had been built from amended policy. This
        # block comes after the other two, so it is the one that catches a
        # version named beside --ablate as well as one alone.
        #
        # ``--precedents`` is deliberately **not** in that list: the precedents
        # block is the same whatever the policy version, so the two may be given
        # together and the run goes to ``runs/precedents/policy-v<N>/<model>/``.
        if args.ablate is not None:
            parser.error(
                "at most one of --ablate, --policy-version N>=2 and --amount-rule "
                "may be given per invocation: each changes what the run measures, "
                "and a run with two of them on measures neither"
            )
        for present, name, why in (
            (args.compare, "--compare", "reads cached runs produced at version 1"),
            (
                args.replay_advocates is not None,
                "--replay-advocates",
                "reuses a recorded run's advocates, which were given their own "
                "run's policy version's brief",
            ),
            (args.replay_check is not None, "--replay-check", "reads a recorded run"),
            (
                args.verify_recorded_drafts is not None,
                "--verify-recorded-drafts",
                "reuses a recorded run's drafts",
            ),
            (
                args.external is not None,
                "--external",
                "arbitrates a converted case in full, outside the corpus",
            ),
        ):
            if present:
                parser.error(
                    "--policy-version N>=2 briefs every case against the amended "
                    "policy and takes no {0}, which {1}".format(name, why)
                )

    if args.amount_rule != pipeline.DEFAULT_AMOUNT_RULE:
        # The amount rule is the fourth switch that changes what a run measures,
        # and it follows the rule the other three follow. It changes what a
        # draft's amount is held to rather than what an agent is given, so every
        # mode below reads or produces a run judged by the published rule, and
        # naming another rule beside one would look as though it had been
        # applied. This block comes last, so it is the one that catches a rule
        # named beside any of the other switches as well as one named alone.
        if (
            args.ablate is not None
            or args.precedents
            or args.policy_version != DEFAULT_POLICY_VERSION
        ):
            parser.error(
                "at most one of --ablate, --precedents, --policy-version N>=2 "
                "and --amount-rule may be given per invocation: each changes "
                "what the run measures, and a run with two of them on measures "
                "neither"
            )
        for present, name, why in (
            (
                args.compare,
                "--compare",
                "reads cached runs judged by the published rule",
            ),
            (
                args.replay_check is not None,
                "--replay-check",
                "reads a recorded run",
            ),
            (
                args.verify_recorded_drafts is not None,
                "--verify-recorded-drafts",
                "reuses a recorded run's drafts and holds them to the published "
                "rule",
            ),
            (
                args.external is not None,
                "--external",
                "arbitrates a converted case in full, outside the corpus",
            ),
        ):
            if present:
                parser.error(
                    "--amount-rule names the rule a draft's amount is read off "
                    "the brief's money block by and takes no {0}, which "
                    "{1}".format(name, why)
                )

    if args.advocate_effort != pipeline.ADVOCATE_EFFORT_DEFAULT:
        # The fifth switch that changes what a run measures, and it follows the
        # rule the other four follow: every mode below reads or produces a run
        # whose advocates reasoned as they always did, so naming the switch
        # beside one would look as though it had been applied. ``--policy-version``
        # is deliberately **not** in that list: the version's directory sits
        # under the switch's own root, so the two may be given together and the
        # run goes to ``runs/advocate-effort-<effort>/policy-v<N>/<model>/``.
        # This block comes after the other four, so it is the one that catches
        # the switch named beside any of them as well as one named alone.
        if (
            args.ablate is not None
            or args.precedents
            or args.amount_rule != pipeline.DEFAULT_AMOUNT_RULE
        ):
            parser.error(
                "at most one of --ablate, --precedents, --policy-version N>=2, "
                "--amount-rule and --advocate-effort may be given per "
                "invocation: each changes what the run measures, and a run with "
                "two of them on measures neither"
            )
        for present, name, why in (
            (
                args.compare,
                "--compare",
                "reads cached runs produced with the advocates reasoning",
            ),
            (
                args.replay_advocates is not None,
                "--replay-advocates",
                "reuses a recorded run's advocates and calls only the judge, so "
                "no advocate request is made for the switch to change",
            ),
            (args.replay_check is not None, "--replay-check", "reads a recorded run"),
            (
                args.verify_recorded_drafts is not None,
                "--verify-recorded-drafts",
                "reuses a recorded run's drafts",
            ),
            (
                args.external is not None,
                "--external",
                "arbitrates a converted case in full, outside the corpus",
            ),
        ):
            if present:
                parser.error(
                    "--advocate-effort names the reasoning effort the two "
                    "advocates' requests carry and takes no {0}, which "
                    "{1}".format(name, why)
                )

    if args.early_majority:
        # The switch's two conditions, refused here rather than left to the
        # runner, so a caller is told before a directory is created and before
        # any call. It is deliberately **not** one of the four switches that
        # change what a run measures -- it changes no request body and moves no
        # directory -- so it is not refused beside them, and it is refused beside
        # these two for reasons of its own.
        if not args.parallel_calls:
            parser.error(
                "--early-majority needs --parallel-calls: the rule stops waiting "
                "for a draft that is already in flight, and a sequential panel "
                "has none"
            )
        if args.verify_drafts:
            parser.error(
                "--early-majority cannot be used with --verify-drafts: the "
                "verifier runs over every valid draft and a contradiction can "
                "take a vote away, so a panel that published at three could "
                "publish a ruling the full panel would not have carried"
            )

    if args.compare:
        if args.model is not None:
            parser.error("--compare reads cached runs and takes no --model")
        if args.external is not None:
            parser.error("--compare reads cached runs and takes no --external")
        if args.replay_advocates is not None or args.replay_check is not None:
            parser.error("--compare reads cached runs and takes no replay arguments")
        if args.verify_drafts or args.verify_recorded_drafts is not None:
            parser.error("--compare reads cached runs and takes no verification argument")
        print(render_comparison(collect_comparison(args.runs_dir)))
        return 0

    # Which model to run is decided in one place, and this is the boundary that
    # reads it. A caller who names one still overrides it, so a probe or a
    # comparison run is unaffected.
    model_id = resolve_model(args.model)

    if args.verify_recorded_drafts is not None:
        # Its own mode, and it refuses the flags it cannot combine with rather
        # than ignoring them: every one of them would otherwise look applied.
        for present, name in (
            (args.replay_check is not None, "--replay-check"),
            (args.replay_advocates is not None, "--replay-advocates"),
            (args.external is not None, "--external"),
            (args.force, "--force"),
        ):
            if present:
                parser.error(
                    "--verify-recorded-drafts reuses a run's recorded drafts and "
                    "takes no {0}".format(name)
                )
        try:
            cases = parse_cases(args.cases) or sorted(grade.load_answer_key())
        except BenchmarkError as exc:
            parser.error(str(exc))
        # Imported here rather than at module load: the module reads this one,
        # and a top-level import would make the two circular.
        #
        # ``python -m eval.run_benchmark`` makes this module ``__main__``, so a
        # plain ``from eval import run_benchmark`` inside the imported module
        # would import a *second* copy of this file -- with its own
        # ``BenchmarkError``, which the ``except`` clauses below would then fail
        # to catch. Aliasing this module under its canonical name first keeps
        # one copy, so a refusal raised inside the measurement is reported as a
        # refusal rather than as a traceback.
        sys.modules.setdefault("eval.run_benchmark", sys.modules[__name__])
        from eval import verify_drafts

        try:
            report = verify_drafts.verify_recorded_run(
                args.verify_recorded_drafts,
                cases,
                model=model_id,
                runs_dir=args.runs_dir,
                prompts_dir=args.prompts_dir,
                timeout_seconds=args.timeout,
            )
        except llm.ModelNotProvisionedError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        except llm.MissingAPIKeyError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        except BenchmarkError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        print(verify_drafts.render_report(report))
        # Non-zero when any case was refused or any draft was contradicted, so a
        # caller can gate on the finding without reading the text.
        return 0 if report.ok else 1

    if args.replay_check is not None:
        if args.external is not None:
            parser.error("--replay-check reads a run and takes no --external")
        if args.verify_drafts or args.verify_recorded_drafts is not None:
            parser.error("--replay-check reads a run and takes no verification argument")
        try:
            cases = parse_cases(args.cases) or sorted(grade.load_answer_key())
        except BenchmarkError as exc:
            parser.error(str(exc))
        try:
            check = check_replay(
                args.replay_check,
                cases,
                model=model_id,
                prompts_dir=args.prompts_dir,
                policy_version=args.policy_version,
            )
        except BenchmarkError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        print(render_replay_check(check))
        # Non-zero when anything was refused, so a caller can gate a paid replay
        # on this without reading the text. A partial acceptance is a finding,
        # not a success: those cases would be run in full, not replayed.
        return 0 if not check.refused else 1

    if args.external is not None:
        if args.replay_advocates is not None:
            parser.error(
                "--external arbitrates a converted case in full and takes no "
                "--replay-advocates: an external case is not one of the recorded "
                "corpus cases a replay reads from"
            )
        if args.cases is not None:
            parser.error("--external arbitrates one named case and takes no --cases")
        try:
            outcome, _run_dir = run_external_case(
                args.external,
                model_id,
                runs_dir=args.runs_dir,
                prompts_dir=args.prompts_dir,
                timeout_seconds=args.timeout,
                case_deadline_seconds=args.case_deadline,
                judge_votes=args.judge_votes,
                verify_drafts=args.verify_drafts,
                token_budget=args.token_budget,
            )
        except llm.ModelNotProvisionedError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        except llm.MissingAPIKeyError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        except loader.LoaderError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        except sealed_roots.SealedDestinationError as exc:
            # ``--runs-dir`` names the root an external case is written under,
            # so it can be a sealed root. ``assert_external_run_directory``
            # refuses that with ``SealedDestinationError``, and it is caught
            # here so the command reports a refusal rather than a traceback.
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        except BenchmarkError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        # Non-zero when the case produced no ruling, for the same reason the
        # corpus runner does: the caller should see it without reading the text.
        return 0 if outcome.ok else 1

    try:
        cases = parse_cases(args.cases)
    except BenchmarkError as exc:
        parser.error(str(exc))
    if not cases:
        cases = sorted(grade.load_answer_key())

    try:
        summary = run_benchmark(
            model_id,
            cases,
            runs_dir=args.runs_dir,
            prompts_dir=args.prompts_dir,
            force=args.force,
            token_budget=args.token_budget,
            concurrency=args.concurrency,
            timeout_seconds=args.timeout,
            case_deadline_seconds=args.case_deadline,
            replay_dir=args.replay_advocates,
            judge_votes=args.judge_votes,
            verify_drafts=args.verify_drafts,
            # The three switches that change what an agent is given. The first
            # two were parsed and refused in combination here but never reached
            # the runner on this command line, so ``--ablate`` and
            # ``--precedents`` ran an unswitched set and wrote it into the
            # headline run directory -- the opposite of what their help text and
            # ``runs/README.md`` say. They are named here beside the third, so
            # the flags this command line accepts are the flags it honours.
            ablation=args.ablate,
            precedents=(PRECEDENTS_STORE if args.precedents else None),
            policy_version=args.policy_version,
            # The fourth switch, named here for the same reason the first three
            # are: a flag this command line accepts is a flag it honours, and a
            # parsed-but-dropped switch would run the published rule while its
            # own help text said otherwise.
            amount_rule=args.amount_rule,
            # Not one of the four: it changes what a run measures in no respect,
            # so it is not refused beside them and it moves no directory. It is
            # named here for the same reason they are, though -- a switch this
            # command line accepts has to reach the pipeline.
            parallel_calls=args.parallel_calls,
            # And the early-majority switch, which reaches the pipeline on
            # exactly the same rule: accepted here, honoured there, and refused
            # above where it cannot be.
            early_majority=args.early_majority,
            # And the record-integrity gate, on the same rule once more: a switch
            # this command line accepts is a switch it honours.
            integrity_gate=args.integrity_gate,
            # And the advocate-effort switch, on the same rule again: accepted
            # here, honoured in the pipeline, and refused above where it cannot
            # be.
            advocate_effort=args.advocate_effort,
        )
    except llm.ModelNotProvisionedError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1
    except llm.MissingAPIKeyError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1
    except BenchmarkError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1

    print_summary(summary)
    # Non-zero when the run stopped early (budget or interrupt) and when it
    # finished the set but some case produced no ruling. Both mean the number in
    # the report does not cover everything that was asked for, and a caller in a
    # shell should be able to see that without reading the report.
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
