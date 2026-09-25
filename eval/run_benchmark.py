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
from tribunal import brief, llm, loader, money, pipeline
from tribunal.model import resolve_model

__all__ = [
    "BenchmarkError",
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
    "failure_kind_for",
    "failure_reason_for",
    "billed_tokens",
    "model_slug",
    "run_directory",
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
# than silently misread.
CACHE_SCHEMA_VERSION = 1

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
    case_loader: Optional[Callable[[int], Mapping[str, Any]]] = None,
) -> ReplayCheck:
    """Ask, per case, whether a recorded run can supply this run's advocates.

    Reads only. No model is called and nothing is written, which is what makes
    this the question a caller can ask before it spends anything -- and what
    makes :func:`run_benchmark` able to ask it once, for every requested case,
    before the first file is written. A replay into the source run's own
    directory therefore reads everything it needs before it overwrites anything.

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
    case_no: int, case_loader: Optional[Callable[[int], Mapping[str, Any]]] = None
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

    ``None`` when the brief cannot be built at all: a case file that has since
    moved, a policy that no longer parses. That is "cannot tell", and it is not
    "matches".
    """
    load = loader.load_case if case_loader is None else case_loader
    try:
        return brief.brief_digest(brief.build_brief_for_case(load(case_no)))[1]
    except Exception:  # noqa: BLE001 - a brief that cannot be built is not a match
        return None


def brief_digest_for(
    case_loader: Optional[Callable[[int], Mapping[str, Any]]] = None,
) -> Optional[Callable[[int], Optional[str]]]:
    """The current-brief digest function for one set's cases.

    ``None`` means the corpus loader, which is what :class:`BriefStaleness`
    already defaults to. A development set needs its own: the manifest cannot
    load a case it does not list, so every one of the set's cached results would
    read as a brief that cannot be rebuilt, and the set would report itself as a
    mixed set -- not one measurement -- when in fact every brief matches.
    """
    if case_loader is None:
        return None
    return lambda case_no: current_brief_sha256(case_no, case_loader=case_loader)


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

    Two recorded digests answer it, not one. ``brief_sha256`` is the digest of
    the exact bytes the agents were handed, so a moved brief means the facts
    changed. ``prompts_sha256`` is the digest of the prompt directory, so a moved
    prompt means the instructions changed. Either one takes the result out of
    this code's measurements, and they are kept apart because they call for
    different responses.

    Both are memoised: the brief digest per case, because rebuilding a brief is a
    file read per case, and the prompts digest once for the whole directory,
    however many cases are asked about.
    """

    def __init__(
        self,
        digest: Optional[Callable[[int], Optional[str]]] = None,
        prompts_digest: Optional[Callable[[], Optional[str]]] = None,
    ) -> None:
        self._digest = current_brief_sha256 if digest is None else digest
        self._prompts_digest = (
            current_prompts_sha256 if prompts_digest is None else prompts_digest
        )
        self._current: Dict[int, Optional[str]] = {}
        self._current_prompts: Optional[str] = None

    def current_digest(self, case_no: int) -> Optional[str]:
        if case_no not in self._current:
            self._current[case_no] = self._digest(case_no)
        return self._current[case_no]

    def current_prompts_digest(self) -> Optional[str]:
        if self._current_prompts is None:
            self._current_prompts = self._prompts_digest()
        return self._current_prompts

    def brief_moved(self, case_no: int, document: Mapping[str, Any]) -> bool:
        """Whether the brief digest was recorded and no longer matches."""
        if not isinstance(document, Mapping):
            return False
        recorded = document.get("brief_sha256")
        if not isinstance(recorded, str) or not recorded:
            return False
        current = self.current_digest(case_no)
        return current is not None and recorded != current

    def prompts_moved(self, document: Mapping[str, Any]) -> bool:
        """Whether the prompts digest was recorded and no longer matches."""
        if not isinstance(document, Mapping):
            return False
        recorded = document.get("prompts_sha256")
        if not isinstance(recorded, str) or not recorded:
            return False
        current = self.current_prompts_digest()
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

    def prompts_unchecked(self, document: Mapping[str, Any]) -> bool:
        """Whether the prompt half of the check could not be made for this entry.

        Either the entry records no prompts digest -- it was written before one
        was kept, so the file cannot say which prompts produced it -- or the
        prompt directory cannot be read now. Both are "cannot tell", and neither
        is a match.
        """
        if not isinstance(document, Mapping):
            return True
        recorded = document.get("prompts_sha256")
        if not isinstance(recorded, str) or not recorded:
            return True
        return self.current_prompts_digest() is None

    def moved_for(self, case_no: int, document: Mapping[str, Any]) -> Tuple[str, ...]:
        """Which recorded digests moved, named, in a fixed order.

        Empty when nothing recorded has moved. Both may be present: a result
        produced by an older brief under older prompts is stale for both reasons.
        """
        moved: List[str] = []
        if self.brief_moved(case_no, document):
            moved.append(grade.MOVED_BRIEF)
        if self.prompts_moved(document):
            moved.append(grade.MOVED_PROMPTS)
        return tuple(moved)

    def status_of(self, case_no: int, document: Mapping[str, Any]) -> str:
        """``current``, ``stale`` or ``unknown`` for one cache entry.

        A moved digest is a finding, whichever channel it is in, and a finding
        beats not being able to tell. Only when nothing recorded has moved does
        the question become whether every channel could actually be checked -- an
        entry that never recorded a prompts digest is not an entry whose prompts
        are known to match.
        """
        if self.moved_for(case_no, document):
            return grade.STALENESS_STALE
        if self.brief_unchecked(case_no, document) or self.prompts_unchecked(document):
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

    The two channels are collected separately as well as as a union, so a report
    can say which of the two moved rather than only that something did.
    """
    checker = BriefStaleness() if checker is None else checker
    stale: List[int] = []
    unknown: List[int] = []
    stale_brief: List[int] = []
    stale_prompts: List[int] = []
    unchecked_prompts: List[int] = []
    for case_no in cases:
        document = load_cached(run_dir, case_no)
        if document is None:
            continue
        if checker.prompts_unchecked(document):
            unchecked_prompts.append(case_no)
        status = checker.status_of(case_no, document)
        if status == grade.STALENESS_STALE:
            stale.append(case_no)
            moved = checker.moved_for(case_no, document)
            if grade.MOVED_BRIEF in moved:
                stale_brief.append(case_no)
            if grade.MOVED_PROMPTS in moved:
                stale_prompts.append(case_no)
        elif status == grade.STALENESS_UNKNOWN:
            unknown.append(case_no)
    return grade.Staleness(
        True,
        tuple(sorted(stale)),
        tuple(sorted(unknown)),
        tuple(sorted(stale_brief)),
        tuple(sorted(stale_prompts)),
        tuple(sorted(unchecked_prompts)),
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

    ``replay`` is a :class:`tribunal.pipeline.Replayable`, which only
    :func:`check_replay` produces and which carries the proof that the source
    run's brief, prompts, model and recorded answers all agree with this code.
    When it is given, the advocates are not called and only the judge is, through
    :func:`tribunal.pipeline.replay_case`.
    """
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

    started = time.monotonic()
    try:
        if replay is not None:
            result = pipeline.replay_case(
                client,
                replay=replay,
                case_deadline_seconds=case_deadline_seconds,
            )
        elif loaded_case is None:
            result = pipeline.run_case(
                case_no,
                client,
                prompts_dir=prompts_dir,
                case_deadline_seconds=case_deadline_seconds,
                case_loader=case_loader,
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
            )
    except (llm.MissingAPIKeyError, llm.ModelNotProvisionedError):
        raise
    except Exception as exc:  # noqa: BLE001 - any transport or parse failure is a case failure
        kind = failure_kind_for(exc)
        detail = "{0}: {1}".format(type(exc).__name__, exc)
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
    document = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "case_no": case_no,
        "model": result.model,
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


# Which digest moved, as a reader needs to hear it. Two phrases rather than one
# word, because they send the reader to different files: a moved brief means
# re-read the case, a moved prompt means re-read what the agents were told.
_STALE_PHRASES = (
    (grade.MOVED_BRIEF, "the brief has moved"),
    (grade.MOVED_PROMPTS, "the prompts have moved"),
)


def _describe_moved(moved: Sequence[str]) -> str:
    """``the brief has moved``, ``the prompts have moved``, or both, joined.

    When nothing was named -- an older cache entry, or a caller that supplied
    only a status -- the fallback says what is known and no more, rather than
    picking one of the two and being wrong half the time.
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


def run_benchmark(
    model: str,
    cases: Sequence[int],
    *,
    runs_dir: Path = RUNS_DIR,
    prompts_dir: Path = PROMPTS_DIR,
    force: bool = False,
    token_budget: Optional[int] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout_seconds: float = llm.DEFAULT_TIMEOUT_SECONDS,
    case_deadline_seconds: float = pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
    replay_dir: Optional[Path] = None,
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

    # De-duplicated but order-preserving: the requested order is the order the
    # progress lines and the report use, and a case named twice is one case.
    requested = list(dict.fromkeys(cases))
    if not requested:
        raise BenchmarkError("no cases were selected")

    resolved_key: Mapping[int, grade.Ruling] = (
        grade.load_answer_key() if key is None else dict(key)
    )
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
            case_loader=case_loader,
        )

    run_dir = run_directory(runs_dir, model)
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

    # A shared sink, because the client is shared across every case and, above
    # concurrency 1, across threads. The client calls this from whichever thread
    # is completing a request, so it is the one piece of the runner's state that
    # needs a lock.
    records: List[Dict[str, Any]] = []
    records_lock = threading.Lock()

    def sink(record: Dict[str, Any]) -> None:
        with records_lock:
            records.append(record)

    positions = {case_no: index + 1 for index, case_no in enumerate(requested)}
    total = len(requested)

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
    # the run is in progress.
    checker = BriefStaleness(brief_digest_for(case_loader))
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
        reused = reused + outcome.tokens
        state["replayed"] = state["replayed"] + outcome.replayed_tokens
        progress(format_progress(outcome, positions[case_no], total))

    def write_metadata(stop_reason: str) -> None:
        document = _metadata_document(
            model=model,
            run_dir=run_dir,
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

    if pending:
        # Built lazily, and only when there is work to do: a re-run whose cases
        # are all cached has no reason to need a credential.
        client = build_client(sink)

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
        except BaseException:
            state["stop_reason"] = STOP_FATAL
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

    write_json(run_dir / CALLS_FILE, {"calls": records})
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
    report = grade_run(run_dir, resolved_key, covered, checker)
    report_title = "Benchmark report — {0}".format(model)
    if label is not None:
        report_title = "Benchmark report — {0} — development set {1}".format(
            model, label
        )
    (run_dir / REPORT_FILE).write_text(
        grade.render_report(report, report_title, key_path=key_path),
        encoding="utf-8",
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
def grade_run(
    run_dir: Path,
    key: Optional[Mapping[int, grade.Ruling]] = None,
    cases: Optional[Sequence[int]] = None,
    checker: Optional[BriefStaleness] = None,
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
    replayed_cases: List[int] = []
    replay_sources: List[str] = []
    replay_tokens = 0
    for case_no in covered:
        document = load_cached(run_dir, case_no)
        if document is None:
            continue
        produced[case_no] = document.get("ruling")
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

    # One checker across every row: the current brief for a case is the same
    # question whichever run directory is asking it, and rebuilding it once per
    # directory would be the same answer computed twice.
    checker = BriefStaleness()
    return [
        _row_from_run(directory, shared, resolved_key, checker) for directory in directories
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


def print_summary(summary: RunSummary) -> None:
    """A short block a person reads at the end of a run."""
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
    """
    resolved = Path(run_dir).resolve()
    external_root = (Path(runs_dir) / EXTERNAL_RUNS_SUBDIR).resolve()
    if not resolved.is_relative_to(external_root):
        raise BenchmarkError(
            "an external case may only be written under runs/{0}/, and this one "
            "would go to {1}".format(EXTERNAL_RUNS_SUBDIR, resolved)
        )
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
    )
    _persist(run_dir, outcome, document, transcript_json)

    metadata = dict(run_provenance)
    # _record_invocation keys its history on started_at, so the invocation's own
    # start is carried under that name; recorded_at means the same instant here.
    metadata.setdefault("started_at", metadata.get("recorded_at"))
    metadata.update(
        {
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
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--prompts-dir", type=Path, default=PROMPTS_DIR)
    args = parser.parse_args(argv)

    if args.compare:
        if args.model is not None:
            parser.error("--compare reads cached runs and takes no --model")
        if args.external is not None:
            parser.error("--compare reads cached runs and takes no --external")
        if args.replay_advocates is not None or args.replay_check is not None:
            parser.error("--compare reads cached runs and takes no replay arguments")
        print(render_comparison(collect_comparison(args.runs_dir)))
        return 0

    # Which model to run is decided in one place, and this is the boundary that
    # reads it. A caller who names one still overrides it, so a probe or a
    # comparison run is unaffected.
    model_id = resolve_model(args.model)

    if args.replay_check is not None:
        if args.external is not None:
            parser.error("--replay-check reads a run and takes no --external")
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
