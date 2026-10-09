"""The version-6 development runs, checked for provenance and read for their figures.

The owner made the final development runs at policy version 6, once, outside this
workspace, from a clean checkout of the commit tagged ``freeze-2026-10-09``. This
module commits nothing and calls nothing: it is the read-only reader of what that
work produced. Every figure it prints is computed from the committed runs under
``runs/`` and the committed keys under ``eval/answers/``, so a reader can
reproduce it from the repository alone.

Two commands, and they answer two different questions.

``--check`` answers *is this the record the freeze names*. For each of the five
runs it reads every case file and every event and asks whether they record the
freeze commit, whether the run recorded a clean tree, whether each case's
``configuration`` is the run's own (policy version 6, judge votes 4, verifier
off), whether the run's ``parallel_calls`` agrees with its own invocation event,
and whether the number of cases is the set's registered size. Anything that does
not agree is **listed by name** rather than summarised.

``--report`` answers *what did they score, cost and take*. Per set: the
four-field exact match and each field separately, the escalation block, the cases
that produced no ruling and the cases that differ from the key with both sides'
four fields side by side, and a Wilson 95% interval for every rate. Then the
precedent measurement over the fifteen route-deviation corpus cases, the
organisers' sample case, and the cost and wall-clock of every set at the owner's
prices.

**No model call is made and no browser is launched.** The module reads files and
prints; it writes nothing.

The sealed-v1 set is deliberately absent. Its single run waits for the key
owner's version-6 key, and nothing under ``eval/answers/sealed-v1/``,
``data/external/sealed-v1/`` or ``eval/external/sealed-v1/`` is opened here.

Run from the project root with::

    python3 -m eval.v6_runs --check
    python3 -m eval.v6_runs --report
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = PROJECT_ROOT / "runs"
ANSWER_DIR = PROJECT_ROOT / "eval" / "answers"

# The freeze every one of the five runs was made from. The tag is on this commit
# and every case file and every event names it.
FREEZE_TAG = "freeze-2026-10-09"
FREEZE_COMMIT = "9ca7313b945f2a8360251394bac2e05352eaf729"

# The model every run was made on, as its run directory is named. The run's own
# ``run.json`` records the model id; this is the directory component, so the
# module can name a path without naming the model id as a live value.
MODEL_SLUG = "deepseek-deepseek-flash"

# The committed manifest, and the directory the console logs were copied into.
MANIFEST_PATH = RUNS_DIR / "policy-v6-manifest.json"
CONSOLE_DIR = RUNS_DIR / "policy-v6-console"
CONSOLE_LOGS: Tuple[str, ...] = (
    "final.log",
    "corpus.log",
    "precedents.log",
    "dev-v2-ext.log",
    "dev-v2-1779.log",
    "ryde-v3.log",
)

# Every root the manifest lists a file under. The five run directories and the
# console logs; the test walks these and refuses a file the manifest omits.
MANIFEST_ROOTS: Tuple[Path, ...] = (
    RUNS_DIR / "policy-v6",
    RUNS_DIR / "precedents" / "policy-v6",
    RUNS_DIR / "dev-v2-ext" / "policy-v6",
    RUNS_DIR / "dev-v2" / "policy-v6",
    RUNS_DIR / "ryde-v3" / "policy-v6",
    CONSOLE_DIR,
)

# The configuration every run was made with. The version is part of what the run
# is, so a case that recorded another is a case the check lists.
POLICY_VERSION = 6
JUDGE_VOTES = 4

# The owner's prices, USD per million tokens, off-peak. Input and output are the
# two billed kinds; a cached prompt token is a cheaper input token and is not
# added a second time.
PRICE_INPUT = Decimal("0.15")
PRICE_CACHED_INPUT = Decimal("0.003")
PRICE_OUTPUT = Decimal("0.6")
MILLION = Decimal(1000000)

# The corpus key was written under policy version 1; the corpus run was made at
# version 6. The sentence is printed beside the corpus figures and is not a
# comment on the figures themselves.
CORPUS_KEY_NOTE = (
    "the key eval/answers/ground_truth.json was written under policy version 1, "
    "and this corpus run was made at policy version 6"
)

# The organisers' own sentence about their sample case. It is quoted rather than
# paraphrased, because it is the whole of why 901 is not scored.
STATED_EXPECTATION_SENTENCE = (
    "this run is not scored against it: the organisers' word is not one of "
    "POL-GEN-03's rulings"
)

# The fifteen route-deviation corpus cases: the corpus's 101-115.
ROUTE_DEVIATION_CASES: Tuple[int, ...] = tuple(range(101, 116))

# The holdout cases the key owner's amendments were drafted from, as the sheet
# names them. They are printed beside the dev-v2-ext split.
AMENDMENT_SOURCE_CASES: Tuple[int, ...] = (2734, 2758, 2832)

PRECEDENT_STORE = PROJECT_ROOT / "precedents" / "precedents.jsonl"
PRECEDENT_ID_RE = re.compile(r"^P-\d{4}$")

CASE_FILE_RE = re.compile(r"^case-(\d{5})\.json$")
WILSON_Z = 1.959963984540054


# --------------------------------------------------------------------------
# The five runs
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class V6Run:
    """One run of the version-6 batch: where it lives, what it covers, its key."""

    name: str
    run_dir: Path
    cases: Tuple[int, ...]
    key_path: Optional[Path]
    registered_size: int
    summary: str


RUNS: Tuple[V6Run, ...] = (
    V6Run(
        name="corpus",
        run_dir=RUNS_DIR / "policy-v6" / MODEL_SLUG,
        cases=tuple(range(101, 116)) + tuple(range(201, 215)),
        key_path=ANSWER_DIR / "ground_truth.json",
        registered_size=29,
        summary="the 29-case corpus, run at policy version 6",
    ),
    V6Run(
        name="dev-v2-ext",
        run_dir=RUNS_DIR / "dev-v2-ext" / "policy-v6" / MODEL_SLUG,
        cases=tuple(range(2701, 2761)) + tuple(range(2801, 2861)),
        key_path=ANSWER_DIR / "dev-v2-ext" / "ground_truth.json",
        registered_size=120,
        summary="dev-v2-ext, 120 cases, run at policy version 6",
    ),
    V6Run(
        name="dev-v2",
        run_dir=RUNS_DIR / "dev-v2" / "policy-v6" / MODEL_SLUG,
        cases=(1779,),
        key_path=ANSWER_DIR / "dev-v2" / "ground_truth.json",
        registered_size=1,
        summary="dev-v2 case 1779 alone, the prompt-injection case",
    ),
    V6Run(
        name="ryde-v3",
        run_dir=RUNS_DIR / "ryde-v3" / "policy-v6" / MODEL_SLUG,
        cases=(901,),
        key_path=None,
        registered_size=1,
        summary="the organisers' sample, case 901, run at policy version 6",
    ),
)

PRECEDENTS_RUN = V6Run(
    name="precedents",
    run_dir=RUNS_DIR / "precedents" / "policy-v6" / MODEL_SLUG,
    cases=ROUTE_DEVIATION_CASES,
    key_path=ANSWER_DIR / "ground_truth.json",
    registered_size=15,
    summary="the corpus's 15 route-deviation cases with --precedents on",
)


def run_by_name(name: str) -> V6Run:
    for run in RUNS:
        if run.name == name:
            return run
    raise KeyError(name)


# --------------------------------------------------------------------------
# Reading the record
# --------------------------------------------------------------------------
def read_json(path: Path) -> Any:
    """One committed file, with every JSON number carrying a point a ``Decimal``.

    The same hook the loader and the grader use, so a money value arrives as the
    literal that was written rather than as the nearest binary approximation.
    """
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_float=Decimal)


def case_files(run_dir: Path) -> Dict[int, Path]:
    """Every case file under a run directory, by case number.

    ``os.walk`` rather than a glob: this module must not list the policy
    directory, and a walk names every file it visits. A transcript is not a case
    file and is skipped by name.
    """
    found: Dict[int, Path] = {}
    for dirpath, _dirnames, filenames in os.walk(run_dir):
        for name in sorted(filenames):
            match = CASE_FILE_RE.match(name)
            if match is None:
                continue
            found[int(match.group(1))] = Path(dirpath) / name
    return found


def case_path(run_dir: Path, case_no: int) -> Path:
    return Path(run_dir) / "case-{0:05d}.json".format(case_no)


def event_lines(run_dir: Path) -> List[Dict[str, Any]]:
    """Every event of a run's log, parsed. An absent log is no events."""
    path = Path(run_dir) / "events.jsonl"
    if not path.is_file():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        out.append(json.loads(line, parse_float=Decimal))
    return out


def documents(run_dir: Path, cases: Sequence[int]) -> Dict[int, Dict[str, Any]]:
    """Every case's document, by number, for the cases a run covers."""
    out: Dict[int, Dict[str, Any]] = {}
    for case_no in cases:
        path = case_path(run_dir, case_no)
        if path.is_file():
            out[case_no] = read_json(path)
    return out


def load_manifest(path: Path = MANIFEST_PATH) -> Any:
    """The committed manifest, parsed."""
    return read_json(path)


def manifest_problems(
    manifest: Mapping[str, Any],
    roots: Optional[Sequence[Path]] = None,
    base: Path = PROJECT_ROOT,
) -> List[str]:
    """Every way a manifest and the files under its roots disagree.

    An empty list means the manifest describes the tree exactly: every listed
    file is present with the size and sha256 it records, no path is listed twice,
    and no file under a root is missing from the list. A non-empty list is the
    finding, and each entry names the file and what disagreed, so a reader is
    never left to compare two digests by eye.
    """
    base = Path(base)
    entries = manifest.get("files") if isinstance(manifest, Mapping) else None
    if not isinstance(entries, list):
        return ["the manifest carries no files list"]
    problems: List[str] = []
    listed: Dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        path = entry.get("path") if isinstance(entry, Mapping) else None
        if not isinstance(path, str):
            problems.append("a manifest entry carries no path: {0!r}".format(entry))
            continue
        if path in listed:
            problems.append("{0} is listed twice".format(path))
            continue
        listed[path] = entry
    for path, entry in sorted(listed.items()):
        file_path = base / path
        if not file_path.is_file():
            problems.append("{0} is listed but is not on disk".format(path))
            continue
        data = file_path.read_bytes()
        if entry.get("size") != len(data):
            problems.append(
                "{0} is {1} bytes, the manifest says {2}".format(
                    path, len(data), entry.get("size")
                )
            )
        digest = hashlib.sha256(data).hexdigest()
        if entry.get("sha256") != digest:
            problems.append(
                "{0} hashes to {1}, the manifest says {2}".format(
                    path, digest, entry.get("sha256")
                )
            )
    resolved_roots = MANIFEST_ROOTS if roots is None else tuple(roots)
    on_disk: List[str] = []
    for root in resolved_roots:
        for dirpath, _dirnames, filenames in os.walk(base / root):
            for name in filenames:
                on_disk.append(str((Path(dirpath) / name).relative_to(base)))
    for path in sorted(on_disk):
        if path not in listed:
            problems.append("{0} is on disk but not in the manifest".format(path))
    return problems


# --------------------------------------------------------------------------
# The provenance check
# --------------------------------------------------------------------------
def _configuration_line(configuration: Any) -> str:
    if not isinstance(configuration, Mapping):
        return "absent"
    return (
        "policy version {0}, judge votes {1}, verifier {2}, ablation {3}, "
        "precedents {4}".format(
            configuration.get("policy_version"),
            configuration.get("judge_votes"),
            "off" if configuration.get("verify_drafts") in (False, None) else "on",
            "none" if configuration.get("ablation") is None else configuration.get("ablation"),
            "none" if configuration.get("precedents") is None else configuration.get("precedents"),
        )
    )


def _configuration_is_the_run(
    configuration: Any,
) -> bool:
    if not isinstance(configuration, Mapping):
        return False
    return (
        configuration.get("policy_version") == POLICY_VERSION
        and configuration.get("judge_votes") == JUDGE_VOTES
        and configuration.get("verify_drafts") in (False, None)
        and configuration.get("ablation") is None
        and configuration.get("precedents") is None
    )


def check_run(run: V6Run) -> Tuple[bool, List[str]]:
    """The provenance of one run. Returns whether it passed and the lines to print."""
    ok = True
    lines: List[str] = []
    files = case_files(run.run_dir)
    lines.append("{0}  {1}".format(run.name, _relative(run.run_dir)))

    count = len(files)
    size_ok = count == run.registered_size
    ok = ok and size_ok
    lines.append(
        "  cases            {0} of a registered {1}{2}".format(
            count, run.registered_size, "" if size_ok else "  <-- DOES NOT MATCH"
        )
    )

    run_document = read_json(run.run_dir / "run.json")
    run_commit = run_document.get("git_commit")
    clean = run_document.get("working_tree_clean")
    commit_ok = run_commit == FREEZE_COMMIT
    ok = ok and commit_ok
    lines.append(
        "  run.json commit  {0}{1}".format(
            run_commit, "" if commit_ok else "  <-- NOT THE FREEZE COMMIT"
        )
    )
    tree_ok = clean is True
    ok = ok and tree_ok
    lines.append(
        "  working tree     {0}{1}".format(
            "clean" if tree_ok else repr(clean), "" if tree_ok else "  <-- NOT CLEAN"
        )
    )

    config_ok = _configuration_is_the_run(run_document.get("configuration"))
    ok = ok and config_ok
    lines.append(
        "  configuration    {0}{1}".format(
            _configuration_line(run_document.get("configuration")),
            "" if config_ok else "  <-- NOT THE FREEZE CONFIGURATION",
        )
    )

    # The run's own ``parallel_calls``, checked against the event that recorded
    # it: a run-level field nobody cross-checks is a field that can drift.
    events = event_lines(run.run_dir)
    parallel = run_document.get("parallel_calls")
    invocation = next(
        (event for event in events if event.get("event") == "invocation_start"), None
    )
    parallel_ok = invocation is not None and invocation.get("parallel_calls") == parallel
    ok = ok and parallel_ok
    lines.append(
        "  parallel calls   {0}{1}".format(
            parallel, "" if parallel_ok else "  <-- DISAGREES WITH THE INVOCATION EVENT"
        )
    )

    # Every case file's commit, and every case's configuration.
    bad_cases: List[int] = []
    bad_config: List[int] = []
    for case_no, path in sorted(files.items()):
        document = read_json(path)
        if document.get("git_commit") != FREEZE_COMMIT:
            bad_cases.append(case_no)
        if not _configuration_is_the_run(document.get("configuration")):
            bad_config.append(case_no)
    ok = ok and not bad_cases and not bad_config
    lines.append(
        "  case commits     {0} of {1} record the freeze commit{2}".format(
            count - len(bad_cases),
            count,
            "" if not bad_cases else "  <-- " + _named(bad_cases),
        )
    )
    lines.append(
        "  case configuration  {0} of {1} are the freeze configuration{2}".format(
            count - len(bad_config),
            count,
            "" if not bad_config else "  <-- " + _named(bad_config),
        )
    )

    # Every event's commit.
    bad_events = [
        (event.get("seq"), event.get("case"))
        for event in events
        if event.get("commit") != FREEZE_COMMIT
    ]
    ok = ok and not bad_events
    lines.append(
        "  event commits    {0} of {1} record the freeze commit{2}".format(
            len(events) - len(bad_events),
            len(events),
            ""
            if not bad_events
            else "  <-- "
            + ", ".join(
                "seq {0} (case {1})".format(seq, case) for seq, case in bad_events
            ),
        )
    )
    return ok, lines


def check() -> Tuple[bool, List[str]]:
    lines = [
        "Version 6 provenance check",
        "freeze tag {0}, commit {1}".format(FREEZE_TAG, FREEZE_COMMIT),
        "",
    ]
    ok = True
    for run in RUNS:
        run_ok, run_lines = check_run(run)
        ok = ok and run_ok
        lines.extend(run_lines)
        lines.append("")
    lines.append("check: {0}".format("PASS" if ok else "FAIL"))
    return ok, lines


# --------------------------------------------------------------------------
# Wilson 95% intervals
# --------------------------------------------------------------------------
def wilson(k: int, n: int) -> Optional[Tuple[float, float]]:
    """The Wilson score interval for ``k`` of ``n``, at 95%, or ``None`` for none."""
    if n == 0:
        return None
    p = k / n
    z2 = WILSON_Z * WILSON_Z
    denominator = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    margin = WILSON_Z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    low = max(0.0, (centre - margin) / denominator)
    high = min(1.0, (centre + margin) / denominator)
    return low, high


def wilson_text(k: int, n: int) -> str:
    interval = wilson(k, n)
    if interval is None:
        return "n/a"
    return "[{0:.1f}%, {1:.1f}%]".format(interval[0] * 100.0, interval[1] * 100.0)


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------
def _relative(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _plural(count: int, noun: str) -> str:
    """``1 case``, ``2 cases`` -- a count that reads as a count."""
    return "{0} {1}".format(count, noun if count == 1 else noun + "s")


def _named(cases: Sequence[int]) -> str:
    """``a``, ``a and b``, ``a, b and c`` -- a list that reads as a list."""
    items = [str(case_no) for case_no in cases]
    if not items:
        return "none"
    if len(items) == 1:
        return items[0]
    return "{0} and {1}".format(", ".join(items[:-1]), items[-1])


def _money(value: Any) -> str:
    from eval import grade

    return grade.render_money(grade.money_or_none(value))


def _referrals(referrals: Any) -> str:
    from eval import grade

    keys = grade.referral_keys_of(referrals)
    if not keys:
        return "(none)"
    return ", ".join(key.render() for key in keys)


def _ruling_side(ruling: Any) -> str:
    if ruling is None:
        return "no ruling  amount -  driver -  referrals -"
    return "ruling {0}  amount {1}  driver {2}  referrals {3}".format(
        ruling.ruling,
        _money(ruling.amount_sgd),
        _money(ruling.driver_compensation_sgd),
        _referrals(ruling.referrals),
    )


def _rate_text(k: int, n: int) -> str:
    from eval import grade

    return "{0}/{1} = {2}".format(k, n, grade.render_percent(grade._percent(k, n)))


def _ratio_text(k: int, n: int) -> str:
    from eval import grade

    return grade.render_ratio(grade._ratio(k, n))


def _median(values: Sequence[Any]) -> Optional[Decimal]:
    ordered = sorted(Decimal(str(value)) for value in values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _percentile(values: Sequence[Any], fraction: Decimal) -> Optional[Decimal]:
    """The nearest-rank percentile, the rule ``eval/readiness.py`` uses."""
    ordered = sorted(Decimal(str(value)) for value in values)
    if not ordered:
        return None
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def _count(value: Optional[Decimal]) -> str:
    if value is None:
        return "-"
    if value == value.to_integral_value():
        return str(int(value))
    return "{0:.1f}".format(value)


def _seconds(value: Optional[Decimal]) -> str:
    if value is None:
        return "-"
    return "{0:.1f}".format(value)


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
def _grade_run(run: V6Run, docs: Dict[int, Dict[str, Any]], key: Mapping[int, Any]):
    from eval import grade

    produced = {case_no: document.get("ruling") for case_no, document in docs.items()}
    subset = {case_no: key[case_no] for case_no in docs if case_no in key}
    return grade.grade(produced, subset, corpus=subset)


def _set_figures(
    run: V6Run, docs: Dict[int, Dict[str, Any]], key: Mapping[int, Any]
) -> List[str]:
    from eval import grade

    lines: List[str] = []
    report = _grade_run(run, docs, key)
    total = report.total
    exact = report.exact_matches

    lines.append(
        "  four-field exact  {0}   Wilson 95% {1}".format(
            _rate_text(exact, total), wilson_text(exact, total)
        )
    )
    for field in grade.GRADED_FIELDS:
        matched, field_total = report.field_tally(field)
        lines.append(
            "    {0:<24}{1}   Wilson 95% {2}".format(
                field,
                _rate_text(matched, field_total),
                wilson_text(matched, field_total),
            )
        )

    calibration = report.calibration
    produced_escalations = len(calibration.produced_escalations)
    target = (
        "  (target {0})".format(grade.render_percent(calibration.target_rate))
        if run.name == "corpus"
        else ""
    )
    lines.append(
        "  escalation  {0}   Wilson 95% {1}{2}".format(
            _rate_text(produced_escalations, total),
            wilson_text(produced_escalations, total),
            target,
        )
    )
    lines.append(
        "    true positives     {0}  {1}".format(
            len(calibration.true_positives), _named(calibration.true_positives)
        )
    )
    lines.append(
        "    false positives    {0}  {1}".format(
            len(calibration.false_positives), _named(calibration.false_positives)
        )
    )
    lines.append(
        "    false negatives    {0}  {1}".format(
            len(calibration.false_negatives), _named(calibration.false_negatives)
        )
    )
    lines.append(
        "    precision          {0}   Wilson 95% {1}".format(
            _ratio_text(len(calibration.true_positives), len(calibration.true_positives) + len(calibration.false_positives)),
            wilson_text(len(calibration.true_positives), len(calibration.true_positives) + len(calibration.false_positives)),
        )
    )
    lines.append(
        "    recall             {0}   Wilson 95% {1}".format(
            _ratio_text(len(calibration.true_positives), len(calibration.true_positives) + len(calibration.false_negatives)),
            wilson_text(len(calibration.true_positives), len(calibration.true_positives) + len(calibration.false_negatives)),
        )
    )
    lines.append(
        "    over-escalations   {0}  {1}".format(
            len(calibration.over_escalations), _named(calibration.over_escalations)
        )
    )
    lines.append(
        "    under-escalations  {0}  {1}".format(
            len(calibration.under_escalations), _named(calibration.under_escalations)
        )
    )

    no_ruling = [score.case_no for score in report.cases if score.produced is None]
    lines.append("  cases with no ruling: {0}".format(_named(no_ruling)))

    differing = [score for score in report.cases if not score.exact]
    lines.append(
        "  cases that differ from the key: {0}".format(
            _named([score.case_no for score in differing])
        )
    )
    for score in differing:
        lines.append("    {0}  key  {1}".format(score.case_no, _ruling_side(score.expected)))
        lines.append("    {0}  run  {1}".format(score.case_no, _ruling_side(score.produced)))
    return lines


def _split_figures(run: V6Run, docs: Dict[int, Dict[str, Any]], key: Mapping[int, Any]) -> List[str]:
    split_path = PROJECT_ROOT / "data" / "external" / "dev-v2-ext" / "split.json"
    split = read_json(split_path)
    lines = [
        "  split  data/external/dev-v2-ext/split.json partitions the {0}-case "
        "dev-v2 + dev-v2-ext pair; this set covers {1} of them: calibration {2}, "
        "holdout {3}".format(
            len(split["covers"]),
            len(docs),
            sum(1 for case_no in split["calibration"] if case_no in docs),
            sum(1 for case_no in split["holdout"] if case_no in docs),
        )
    ]
    for label in ("calibration", "holdout"):
        members = [case_no for case_no in split[label] if case_no in docs]
        part = {case_no: docs[case_no] for case_no in members}
        report = _grade_run(run, part, key)
        lines.append(
            "    {0:<12}{1} of this set   four-field exact {2}   Wilson 95% {3}".format(
                label,
                len(members),
                _rate_text(report.exact_matches, report.total),
                wilson_text(report.exact_matches, report.total),
            )
        )
    holdout = set(split["holdout"])
    in_holdout = [case_no for case_no in AMENDMENT_SOURCE_CASES if case_no in holdout]
    lines.append(
        "  the key owner's amendments were drafted from the holdout cases {0}".format(
            _named(AMENDMENT_SOURCE_CASES)
        )
    )
    lines.append(
        "    all three are holdout members of this set: {0}".format(
            "yes" if len(in_holdout) == len(AMENDMENT_SOURCE_CASES) else "no"
        )
    )
    return lines


def _cost_and_time(run: V6Run, docs: Dict[int, Dict[str, Any]]) -> List[str]:
    prompt = [document.get("tokens", {}).get("prompt_tokens", 0) for document in docs.values()]
    cached = [document.get("tokens", {}).get("cached_tokens", 0) for document in docs.values()]
    completion = [
        document.get("tokens", {}).get("completion_tokens", 0) for document in docs.values()
    ]
    walls = [document.get("wall_seconds") for document in docs.values()]

    total_prompt = sum(prompt)
    total_cached = sum(cached)
    total_completion = sum(completion)
    cost = (
        Decimal(total_prompt - total_cached) * PRICE_INPUT
        + Decimal(total_cached) * PRICE_CACHED_INPUT
        + Decimal(total_completion) * PRICE_OUTPUT
    ) / MILLION

    lines = ["{0}  ({1})".format(run.name, _plural(len(docs), "case"))]
    lines.append(
        "  tokens total     prompt {0:,}   cached prompt {1:,}   completion {2:,}   "
        "billed {3:,}".format(
            total_prompt, total_cached, total_completion, total_prompt + total_completion
        )
    )
    lines.append(
        "  tokens median    prompt {0}   cached prompt {1}   completion {2}   "
        "billed {3}".format(
            _count(_median(prompt)),
            _count(_median(cached)),
            _count(_median(completion)),
            _count(_median([p + c for p, c in zip(prompt, completion)])),
        )
    )
    lines.append("  cost             {0:.4f} USD".format(cost))
    lines.append(
        "  wall clock       median {0}s   p90 {1}s".format(
            _seconds(_median(walls)), _seconds(_percentile(walls, Decimal("0.9")))
        )
    )
    return lines


def _precedent_ids() -> List[str]:
    ids: List[str] = []
    for line in PRECEDENT_STORE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line, parse_float=Decimal)
        precedent_id = entry.get("precedent_id")
        if isinstance(precedent_id, str) and PRECEDENT_ID_RE.match(precedent_id):
            ids.append(precedent_id)
    return sorted(ids)


def _cites_a_precedent(explanation: Any, precedent_ids: Sequence[str]) -> bool:
    if not isinstance(explanation, str):
        return False
    for precedent_id in precedent_ids:
        if re.search(
            r"(?<![A-Za-z0-9-])" + re.escape(precedent_id) + r"(?![0-9])", explanation
        ):
            return True
    return False


def _precedent_measurement(
    corpus_docs: Dict[int, Dict[str, Any]],
    precedent_docs: Dict[int, Dict[str, Any]],
    key: Mapping[int, Any],
) -> List[str]:
    from eval import grade

    lines: List[str] = []
    subset = {case_no: key[case_no] for case_no in ROUTE_DEVIATION_CASES}
    with_report = _grade_run(PRECEDENTS_RUN, precedent_docs, key)
    without_report = grade.grade(
        {case_no: corpus_docs[case_no].get("ruling") for case_no in ROUTE_DEVIATION_CASES},
        subset,
        corpus=subset,
    )
    lines.append(
        "  with precedents     four-field exact {0}   Wilson 95% {1}".format(
            _rate_text(with_report.exact_matches, with_report.total),
            wilson_text(with_report.exact_matches, with_report.total),
        )
    )
    lines.append(
        "  without precedents  four-field exact {0}   Wilson 95% {1}".format(
            _rate_text(without_report.exact_matches, without_report.total),
            wilson_text(without_report.exact_matches, without_report.total),
        )
    )

    def word(document: Mapping[str, Any]) -> Any:
        inner = (document.get("ruling") or {}).get("ruling")
        return inner.get("ruling") if isinstance(inner, Mapping) else None

    changed = [
        case_no
        for case_no in ROUTE_DEVIATION_CASES
        if word(precedent_docs[case_no]) != word(corpus_docs[case_no])
    ]
    lines.append("  cases whose ruling changed: {0}".format(_named(changed)))
    for case_no in changed:
        lines.append(
            "    {0}  without {1}  ->  with {2}".format(
                case_no, word(corpus_docs[case_no]), word(precedent_docs[case_no])
            )
        )

    precedent_ids = _precedent_ids()
    citing = [
        case_no
        for case_no in ROUTE_DEVIATION_CASES
        if _cites_a_precedent(
            ((precedent_docs[case_no].get("ruling") or {}).get("ruling") or {}).get("explanation"),
            precedent_ids,
        )
    ]
    lines.append(
        "  rulings that cite a precedent: {0} of {1}  {2}".format(
            len(citing), len(ROUTE_DEVIATION_CASES), _named(citing)
        )
    )
    return lines


def _sample_case(run: V6Run, docs: Dict[int, Dict[str, Any]]) -> List[str]:
    document = docs[901]
    ruling = (document.get("ruling") or {}).get("ruling") or {}
    expected = read_json(PROJECT_ROOT / "eval" / "external" / "ryde" / "expected.json")
    lines = [
        "  ruling                 {0}".format(ruling.get("ruling")),
        "  amount_sgd             {0}".format(_money(ruling.get("amount_sgd"))),
        "  driver_compensation    {0}".format(
            _money(ruling.get("driver_compensation_sgd"))
        ),
        "  confidence             {0}".format(ruling.get("confidence")),
        "  vote agreement         {0}".format(document.get("vote_agreement")),
        "  the organisers' stated expectation: {0}".format(
            expected.get("expected_outcome_as_stated")
        ),
        "  {0}".format(STATED_EXPECTATION_SENTENCE),
    ]
    return lines


def report() -> str:
    lines: List[str] = [
        "Version 6 development runs -- report",
        "read from the committed runs under runs/ and the committed keys; no model call",
        "freeze tag {0}, commit {1}".format(FREEZE_TAG, FREEZE_COMMIT),
        "",
        "== Per set ==",
        "",
    ]

    corpus_key = None
    docs_by_name: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for run in RUNS:
        docs = documents(run.run_dir, run.cases)
        docs_by_name[run.name] = docs
        if run.key_path is not None:
            key = _key_for(run)
        else:
            key = {}
        if run.name == "corpus":
            corpus_key = key
        lines.append("-- {0}: {1}".format(run.name, run.summary))
        lines.append("   run {0}".format(_relative(run.run_dir)))
        if run.key_path is not None:
            lines.append("   key {0}".format(_relative(run.key_path)))
        else:
            lines.append("   key none: the organisers' sample is not scored")
        if run.name == "corpus":
            lines.append("   {0}".format(CORPUS_KEY_NOTE))
        lines.extend(_set_figures(run, docs, key))
        if run.name == "dev-v2-ext":
            lines.extend(_split_figures(run, docs, key))
        lines.append("")

    # The precedent measurement.
    lines.append("== The precedent measurement, over the corpus's 15 route-deviation cases ==")
    lines.append("   with precedents  {0}".format(_relative(PRECEDENTS_RUN.run_dir)))
    lines.append("   without          {0}".format(_relative(run_by_name("corpus").run_dir)))
    precedent_docs = documents(PRECEDENTS_RUN.run_dir, PRECEDENTS_RUN.cases)
    # Kept beside the four runs' own documents so the cost section below reads
    # every run through one lookup, the precedents run included. It is a
    # measurement of its own -- the corpus's fifteen route-deviation cases with
    # ``--precedents`` on -- and it is billed like any other run.
    docs_by_name[PRECEDENTS_RUN.name] = precedent_docs
    lines.extend(
        _precedent_measurement(
            docs_by_name["corpus"], precedent_docs, corpus_key
        )
    )
    lines.append("")

    # 901.
    lines.append("== The organisers' sample case (901) ==")
    lines.append("   run {0}".format(_relative(run_by_name("ryde-v3").run_dir)))
    lines.extend(_sample_case(run_by_name("ryde-v3"), docs_by_name["ryde-v3"]))
    lines.append("")

    # Cost and time.
    #
    # Five runs, not four: the precedents run is one of the five the freeze
    # names, and a cost section that left it out would be a figure a reader
    # could not reconcile with the manifest. It covers fifteen cases the corpus
    # run already covers, so the five totals are not disjoint and are never
    # summed -- each is the cost of one run, and that is all it is.
    lines.append("== Cost and time ==")
    lines.append(
        "   prices (USD per million tokens, off-peak): input {0}, cached input {1}, "
        "output {2}".format(PRICE_INPUT, PRICE_CACHED_INPUT, PRICE_OUTPUT)
    )
    lines.append("")
    for run in RUNS + (PRECEDENTS_RUN,):
        lines.extend(_cost_and_time(run, docs_by_name[run.name]))
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def _key_for(run: V6Run) -> Dict[int, Any]:
    from eval import grade

    return grade.load_answer_key(run.key_path)


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m eval.v6_runs",
        description=(
            "Check the provenance of the version-6 development runs, or print "
            "their figures. Read-only; no model call is made."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--check",
        action="store_true",
        help="verify every case file and event against the freeze commit",
    )
    group.add_argument(
        "--report",
        action="store_true",
        help="print the figures, computed from the committed runs and keys",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.check:
        ok, lines = check()
        print("\n".join(lines))
        return 0 if ok else 1
    sys.stdout.write(report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
