"""Build the debate viewer: one self-contained HTML file, from the committed run.

What this is for
----------------
The track requires an observable record of inter-agent communication, and the
record that already exists is the transcript the pipeline writes for each case.
A transcript is the right evidence and the wrong thing to put on a projector:
it is JSON, it is 30 kB per case, and a reader has to know the pipeline to read
it. This module turns that record into two views a person can look at -- the
run's headline figures over all 29 cases, and one case stepped through in the
order the case was actually decided.

Why a replay rather than live calls
-----------------------------------
A case takes about three and a half minutes end to end, measured
(``runs/deepseek-deepseek-flash/run.json``: 29 cases in 5 985 s of wall clock).
Nobody watches that on stage, and a replay cannot fail in front of an audience.
So the viewer is built from the committed run and makes no network call at all.

The output
----------
``ui/dist/index.html`` -- one file, with every byte of data, CSS and JavaScript
inline. No framework, no CDN, no external request of any kind, so it opens from
``file://`` on a laptop with no internet on a projector at Demo Day, and serves
unchanged from GitHub Pages once the repository is public. The build is
deterministic: the same inputs produce the same bytes, and
``tests/test_ui_build.py`` requires the committed file to equal a fresh build,
because the lesson of this repository is that a stored artefact must not be
able to drift from the code that produces it without something going red.

What it reads, and what it refuses to invent
--------------------------------------------
* ``runs/deepseek-deepseek-flash/`` -- the headline run: per case a result file
  and a transcript, plus ``run.json`` and ``invocations.json`` for provenance.
* the brief for each case, **rebuilt** with :func:`tribunal.brief.build_brief`
  and serialised with :func:`tribunal.money.dumps_canonical`, then checked
  against the ``brief_sha256`` the result recorded. A digest that does not match
  means the brief this code builds is not the brief those agents were handed, so
  the case is **refused**: it is named, and it is not shown. The viewer must show
  the evidence the agents actually received, never a regenerated brief that
  merely resembles it. Policy text is identical across the cases of one category
  (asserted here, not assumed), so it is stored once per category rather than
  twenty-nine times -- the digest is still checked on the full brief first.
* ``eval/answers/ground_truth.json`` -- for the expected-versus-produced view,
  labelled in the viewer as the grading answer key. This module is a
  presentation layer *beside* ``eval/``; nothing under ``tribunal/`` gains any
  path to ``eval/``.
* ``tribunal/model.py`` -- the runtime model, read from the one module that
  decides it. The model id is deliberately not written down here: a second live
  value would be a second decision, and ``tests/test_model.py`` walks this
  directory to make sure there is not one.

The figures are computed, not typed
-----------------------------------
Every headline number comes from :func:`eval.grade.grade` over the same run, so
the viewer cannot print an accuracy the grader does not also print, and the test
that reads the numbers back out of the HTML recomputes them the same way. The
one figure the grader does not compute -- the total of discarded claims across
all judges -- is summed here from the run's own judge outputs, and the test
recomputes that too.

Money is carried as its own decimal literal
-------------------------------------------
The pipeline keeps every amount in :class:`decimal.Decimal`. Embedded in the
document as a JSON *number* a value like ``8.05`` would become the nearest
binary double on the way into the page, and the page would then be displaying a
different number from the one the agents were handed. Every ``Decimal`` is
therefore written as a string, so the viewer shows the literal the policy
produced.

Run it with ``python -m ui.build``; ``--check`` compares the committed file
against a fresh build and exits non-zero on any difference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import grade  # noqa: E402
from tribunal import brief as brief_module  # noqa: E402
from tribunal import llm  # noqa: E402
from tribunal import model as model_module  # noqa: E402
from tribunal import money  # noqa: E402
from tribunal import transcript as transcript_module  # noqa: E402

__all__ = [
    "BuildError",
    "RUN_DIR",
    "DIST_DIR",
    "OUTPUT_PATH",
    "DEFAULT_CASE",
    "cached_cases",
    "build_document",
    "render_html",
    "main",
]

# The headline run, by directory name. A run directory is named after the model
# id, and this is the one the runtime model decision rests on.
RUN_DIR = PROJECT_ROOT / "runs" / "deepseek-deepseek-flash"

# Where the built file lives. It is committed, so a judge can open it without
# running Python.
DIST_DIR = PROJECT_ROOT / "ui" / "dist"
OUTPUT_PATH = DIST_DIR / "index.html"

# The case the viewer opens on. 208 is the demonstration case: every artifact is
# COMPLETE, the miss is not a miss, and both advocates concede honestly.
DEFAULT_CASE = 208

# The path of a case result file, and nothing else in the run directory. The
# transcripts beside them match ``case-*.json`` too, so the suffix is anchored.
_CASE_FILE_RE = re.compile(r"^case-(\d{5})\.json$")

# The link a miss points at, relative to ``ui/dist/index.html``. The note records
# why case 211 is a contested reading rather than a defect.
_DECISION_NOTE_LINK = "../../" + model_module.DECISION_NOTE


class BuildError(Exception):
    """An input is not the shape the viewer can present."""


# --------------------------------------------------------------------------
# Reading the run
# --------------------------------------------------------------------------
def _read_json(path: Path) -> Any:
    """Parse a JSON file with ``parse_float=Decimal``, as the loader does.

    The hook matters for the same reason it matters in ``loader.py``: a money
    value written ``8.05`` must arrive as the decimal literal and not as the
    nearest binary approximation of it.
    """
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_float=Decimal)


def cached_cases(run_dir: Path = RUN_DIR) -> List[int]:
    """Every case number the run directory holds a result for, ascending.

    The transcript files sit beside the results and share their prefix, so the
    name is matched rather than the prefix alone.
    """
    numbers: List[int] = []
    for path in sorted(Path(run_dir).glob("case-*.json")):
        match = _CASE_FILE_RE.match(path.name)
        if match is not None:
            numbers.append(int(match.group(1)))
    return sorted(numbers)


def _brief_digest(built: Mapping[str, Any]) -> str:
    """The SHA-256 of the brief exactly as the pipeline serialised it.

    The same two steps :func:`tribunal.pipeline.run_case` takes, in the same
    order and with the same serialiser: ``money.dumps_canonical``, then SHA-256
    over those exact bytes. The serialiser is not interchangeable -- any other
    produces a different digest for the same brief, and every case would then be
    refused for the wrong reason.
    """
    canonical = money.dumps_canonical(built)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalise(node: Any) -> Any:
    """The document's own types: ``Decimal`` to its literal, everything else kept.

    A ``Decimal`` becomes a string, so the page shows the literal the policy
    produced rather than the nearest double to it. Floats are left alone: they
    are floats in the pipeline, they round-trip through JSON and back into a
    JavaScript number exactly, and rewriting them would be a claim about
    precision the derived facts do not make.
    """
    if isinstance(node, Decimal):
        return str(node)
    if isinstance(node, Mapping):
        return {str(key): _normalise(value) for key, value in node.items()}
    if isinstance(node, (list, tuple)):
        return [_normalise(value) for value in node]
    return node


# --------------------------------------------------------------------------
# The agents' side of one case
# --------------------------------------------------------------------------
def _agent_block(transcript: Optional[Mapping[str, Any]], role: str) -> Dict[str, Any]:
    """One agent's calls for one case, in order, with its answer parsed out.

    A role can have more than one entry: a response the prompt's shape contract
    rejects is retried, and one shipped run shows exactly that for the judge on
    cases 115 and 213. The retry is part of the record, so every call is carried
    and the viewer shows the ones that did not parse rather than quietly keeping
    only the answer that worked.

    The raw response text is carried only for a call that did **not** parse. For
    a call that did, the parsed value is the same information in a form the page
    can lay out, and keeping both would double the size of the file to say the
    same thing.
    """
    entries = []
    if isinstance(transcript, Mapping):
        for entry in transcript.get("entries", []) or []:
            if isinstance(entry, Mapping) and entry.get("role") == role:
                entries.append(entry)

    calls: List[Dict[str, Any]] = []
    parsed: Optional[Any] = None
    for entry in entries:
        outcome = entry.get("parse_outcome")
        calls.append(
            {
                "shape": entry.get("shape"),
                "parse_outcome": outcome,
                "attempts": entry.get("attempts"),
                "status": entry.get("status"),
                "duration_seconds": entry.get("duration_seconds"),
                "prompt_tokens": entry.get("prompt_tokens"),
                "completion_tokens": entry.get("completion_tokens"),
                "reasoning_tokens": entry.get("reasoning_tokens"),
                "cached_tokens": entry.get("cached_tokens"),
                "model": entry.get("model"),
                "timestamp": entry.get("timestamp"),
                "note": entry.get("note"),
                "response_text": (
                    entry.get("response_text")
                    if outcome != llm.PARSE_PARSED
                    else None
                ),
            }
        )
        if outcome == llm.PARSE_PARSED and isinstance(entry.get("parsed"), Mapping):
            # The last one that parsed is the answer that was used; an earlier
            # malformed attempt stays in ``calls`` as evidence of the retry.
            parsed = entry.get("parsed")

    return {
        "role": role,
        "calls": calls,
        # Normalised here rather than at each use: the transcript is read with
        # ``parse_float=Decimal`` for the same reason the loader is, so an
        # advocate's ``asserted_weight`` arrives as a Decimal and has to become
        # its literal before it can be embedded in the page.
        "parsed": _normalise(parsed),
        "call_count": len(entries),
        "retried": any(call["parse_outcome"] != llm.PARSE_PARSED for call in calls),
    }


def _claims_of(agent: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """The claims of an advocate block, normalised to a list of objects.

    The pipeline accepts an advocate's claims either inside an object under
    ``claims`` or as a bare array, and which of the two a model chose is
    recorded per call. Both shapes are presented; an advocate that answered in
    neither is presented as having produced no claims, which is what happened.
    """
    parsed = agent.get("parsed")
    if isinstance(parsed, Mapping):
        claims = parsed.get("claims")
    elif isinstance(parsed, list):
        claims = parsed
    else:
        claims = None
    if not isinstance(claims, list):
        return []
    return [claim for claim in claims if isinstance(claim, Mapping)]


# --------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------
def _policy_blocks(
    built_by_case: Mapping[int, Mapping[str, Any]],
    category_by_case: Mapping[int, str],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """The policy half of each brief, stored once per category.

    Policy text is identical across the cases of one category, so storing it
    once per category rather than twenty-nine times saves about a megabyte of
    the output for no loss of information. The saving is only sound if the
    blocks really are identical, so that is checked here and the build fails
    loudly rather than showing one case's policy under another case's name.

    The check is made on the block as the brief carries it, after the full
    brief's digest has already been verified against the run -- so a case is
    never admitted on the strength of a policy block that was not itself part of
    a verified brief.
    """
    blocks: Dict[str, Any] = {}
    digests: Dict[str, str] = {}
    for case_no in sorted(built_by_case):
        category = category_by_case[case_no]
        block = built_by_case[case_no]["policies"]
        canonical = money.dumps_canonical(block)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if category not in blocks:
            blocks[category] = _normalise(block)
            digests[category] = digest
            continue
        if digests[category] != digest:
            raise BuildError(
                "cases of category {0} were handed different policy blocks: case "
                "{1} does not match the block already stored for that category. "
                "Storing it once would show the wrong policy text.".format(
                    category, case_no
                )
            )
    return blocks, digests


def _expected_side(record: Mapping[str, Any]) -> Dict[str, Any]:
    """The answer key's own record for one case, in the shape the page wants.

    ``grade.expected_from_key`` is the public path to the four graded fields, so
    the expected side is built through it rather than by reading the raw keys
    here. ``difficulty``, ``governing_clauses`` and ``rationale`` are not part of
    the graded ruling and are not modelled by ``Ruling``, so they are taken from
    the same record directly. The viewer is a presentation layer beside
    ``eval/`` and this is the one place it reads the key's prose.
    """
    truth = record.get("ground_truth") or {}
    expected = grade.expected_from_key(record)
    return {
        "ruling": expected.ruling,
        "amount_sgd": grade.render_money(grade.money_or_none(expected.amount_sgd)),
        "driver_compensation_sgd": grade.render_money(
            grade.money_or_none(expected.driver_compensation_sgd)
        ),
        "referrals": [str(item) for item in expected.referrals],
        "difficulty": expected.difficulty,
        "governing_clauses": [str(item) for item in truth.get("governing_clauses", [])],
        "rationale": truth.get("rationale"),
    }


def _produced_side(score: grade.CaseScore) -> Dict[str, Any]:
    """The run's own ruling for one case, as the grader read it.

    Taken from the grader's parsed ruling rather than from the raw file, so the
    produced side the page shows is the same object the score was computed from.
    """
    produced = score.produced
    if produced is None:
        return {
            "ruling": None,
            "amount_sgd": "null",
            "driver_compensation_sgd": "null",
            "referrals": [],
            "confidence": None,
            "explanation": None,
        }
    return {
        "ruling": produced.ruling,
        "amount_sgd": grade.render_money(grade.money_or_none(produced.amount_sgd)),
        "driver_compensation_sgd": grade.render_money(
            grade.money_or_none(produced.driver_compensation_sgd)
        ),
        "referrals": [str(item) for item in produced.referrals],
        "confidence": _normalise(produced.confidence),
        "explanation": produced.explanation,
    }


def _grading_of(score: grade.CaseScore) -> Dict[str, Any]:
    """Field by field, what agreed and what did not, in the grader's own words."""
    return {
        "exact": score.exact,
        "failed_fields": list(score.failed_fields),
        "fields": [
            {
                "field": outcome.field,
                "correct": outcome.correct,
                "detail": outcome.detail,
            }
            for outcome in score.outcomes
        ],
    }


def _headline(
    report: grade.GradeReport,
    case_facts: Mapping[int, Mapping[str, Any]],
) -> Dict[str, Any]:
    """Every headline figure, computed from the run.

    Nothing here is typed in. The accuracy figures come from the grader over the
    same produced rulings the page shows, so the viewer and ``eval/grade.py``
    cannot disagree about what the run scored.

    ``case_facts`` is every case in the run, refused ones included, so the
    figures describe the run rather than the subset this build could verify. A
    refusal is a fact about the viewer; folding it into the run's accuracy would
    be a fact about the viewer pretending to be a fact about the model.

    The discarded-claim total is the one figure the grader does not compute -- it
    is a property of the judge outputs, not of the verdict -- so it is summed
    from the run's own judge results, and the test recomputes it the same way.
    """
    calibration = report.calibration
    total = report.total

    fields = {}
    for name in grade.GRADED_FIELDS:
        correct, denominator = report.field_tally(name)
        fields[name] = {
            "matched": correct,
            "total": denominator,
            # ``grade._percent`` is private, and it is used deliberately: it is
            # the grader's own rounding rule, and the viewer's whole claim about
            # these numbers is that it cannot disagree with the grader about
            # them. Re-deriving the rounding here would be a second rule.
            "display": "{0}/{1} = {2}".format(
                correct, denominator, grade.render_percent(grade._percent(correct, denominator))
            ),
        }

    discarded_per_case: Dict[str, int] = {}
    for case_no in sorted(case_facts):
        discarded = case_facts[case_no].get("discarded_claims") or []
        discarded_per_case[str(case_no)] = len(discarded)

    seconds = [
        float(case_facts[case_no]["wall_seconds"])
        for case_no in sorted(case_facts)
        if case_facts[case_no].get("wall_seconds") is not None
    ]
    tokens = [
        int(case_facts[case_no]["tokens"]["total_tokens"])
        for case_no in sorted(case_facts)
        if case_facts[case_no].get("tokens")
    ]

    return {
        "cases_graded": total,
        "exact": {
            "matched": report.exact_matches,
            "total": total,
            "display": "{0}/{1} = {2}".format(
                report.exact_matches,
                total,
                grade.render_percent(grade._percent(report.exact_matches, total)),
            ),
        },
        "two_field": {
            "matched": report.two_field_matches,
            "total": total,
            "note": (
                "Reported as a contrast only, never as the result. A ruling "
                "counts only when all four fields agree."
            ),
        },
        "fields": fields,
        "escalation": {
            "expected": len(calibration.expected_escalations),
            "produced": len(calibration.produced_escalations),
            "true_positives": list(calibration.true_positives),
            "precision": {
                "matched": len(calibration.true_positives),
                "total": len(calibration.true_positives) + len(calibration.false_positives),
                "display": grade.render_ratio(calibration.precision),
            },
            "recall": {
                "matched": len(calibration.true_positives),
                "total": len(calibration.true_positives) + len(calibration.false_negatives),
                "display": grade.render_ratio(calibration.recall),
            },
            "over_escalations": list(calibration.over_escalations),
            "under_escalations": list(calibration.under_escalations),
            "rate_percent": grade.render_percent(calibration.rate),
            "target_percent": grade.render_percent(calibration.target_rate),
            "off_target": calibration.rate_off_target,
            "indeterminate_ruled_confidently": list(
                calibration.indeterminate_ruled_confidently
            ),
        },
        "discarded_claims": {
            "total": sum(discarded_per_case.values()),
            "per_case": discarded_per_case,
        },
        "seconds": {
            "total": round(math.fsum(seconds), 1),
            "mean_per_case": round(math.fsum(seconds) / len(seconds), 1) if seconds else None,
            "cases": len(seconds),
        },
        "tokens": {
            "total": sum(tokens),
            "mean_per_case": round(sum(tokens) / len(tokens), 1) if tokens else None,
            "cases": len(tokens),
        },
    }


def _provenance(
    run: Mapping[str, Any],
    invocations: Sequence[Mapping[str, Any]],
    run_dir: Path,
) -> Dict[str, Any]:
    """Which run this page is showing, on the page and not in a footnote.

    Every path is relative to the project root. The run records absolute paths,
    and this repository is published before submission: an absolute path carries
    a username into the artifact, which is a small leak with no upside.
    """
    def relative(value: Any) -> Optional[str]:
        if not isinstance(value, str) or not value:
            return None
        try:
            return Path(value).resolve().relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            return value

    history = []
    for entry in invocations:
        if not isinstance(entry, Mapping):
            continue
        cases = entry.get("cases") or {}
        history.append(
            {
                "started_at": entry.get("started_at"),
                "ended_at": entry.get("ended_at"),
                "git_commit": entry.get("git_commit"),
                "model": entry.get("model"),
                "stop_reason": entry.get("stop_reason"),
                "completed": len(cases.get("completed") or []),
                "failed": len(cases.get("failed") or []),
                "requested": len(cases.get("requested") or []),
                "python_version": entry.get("python_version"),
                "tokens_spent": (entry.get("tokens") or {}).get("spent_this_invocation"),
            }
        )

    return {
        "run_directory": relative(str(run_dir)) or str(run_dir),
        "model": run.get("model"),
        "runtime_model": model_module.RUNTIME_MODEL,
        "model_provider": model_module.MODEL_PROVIDER,
        "model_region": model_module.MODEL_REGION,
        "git_commit": run.get("git_commit"),
        "working_tree_clean": run.get("working_tree_clean"),
        "prompts_directory": relative(run.get("prompts_dir")),
        "prompts_sha256": run.get("prompts_sha256"),
        "answer_key_sha256": grade.answer_key_sha256(),
        "python_version": run.get("python_version"),
        "started_at": run.get("started_at"),
        "ended_at": run.get("ended_at"),
        "case_deadline_seconds": run.get("case_deadline_seconds"),
        "timeout_seconds": run.get("timeout_seconds"),
        "token_budget": run.get("token_budget"),
        "tokens": run.get("tokens"),
        "invocation_count": len(history),
        "invocations": history,
    }


def build_document(
    run_dir: Path = RUN_DIR,
    brief_builder: Optional[Callable[[int], Mapping[str, Any]]] = None,
    key_path: Path = grade.ANSWER_KEY_PATH,
) -> Dict[str, Any]:
    """The whole data model of the viewer, as a plain dict.

    ``brief_builder`` is injectable so a test can hand in a brief that does not
    match the recorded digest and watch the case be refused rather than shown.
    The default is the real one, and there is no other way to change what is
    rebuilt.

    A case whose rebuilt brief does not match the digest its result recorded is
    refused: named, with both digests, and left out of the cases the viewer can
    open. The refusal is reported rather than swallowed, because a viewer that
    silently drops a case is indistinguishable from a run that never had one.
    """
    run_dir = Path(run_dir)
    builder = brief_module.build_brief if brief_builder is None else brief_builder

    run = _read_json(run_dir / "run.json")
    invocations = _read_json(run_dir / "invocations.json")
    if not isinstance(invocations, list):
        raise BuildError("invocations.json is not a list")

    key_records: Dict[int, Mapping[str, Any]] = {}
    for record in _read_json(key_path):
        key_records[int(record["case_no"])] = record

    numbers = cached_cases(run_dir)
    if not numbers:
        raise BuildError("no cached case results under {0}".format(run_dir))

    refused: List[Dict[str, Any]] = []
    built_by_case: Dict[int, Mapping[str, Any]] = {}
    raw_by_case: Dict[int, Mapping[str, Any]] = {}
    for case_no in numbers:
        result = _read_json(run_dir / ("case-%05d.json" % case_no))
        raw_by_case[case_no] = result
        recorded = result.get("brief_sha256")
        try:
            rebuilt = builder(case_no)
            rebuilt_digest = _brief_digest(rebuilt)
        except Exception as exc:  # noqa: BLE001 - an unbuildable brief is a refusal
            refused.append(
                {
                    "case_no": case_no,
                    "recorded_brief_sha256": recorded,
                    "rebuilt_brief_sha256": None,
                    "reason": "the brief could not be rebuilt: {0}: {1}".format(
                        type(exc).__name__, exc
                    ),
                }
            )
            continue
        if rebuilt_digest != recorded:
            refused.append(
                {
                    "case_no": case_no,
                    "recorded_brief_sha256": recorded,
                    "rebuilt_brief_sha256": rebuilt_digest,
                    "reason": (
                        "the brief this code builds is not the brief those agents "
                        "were handed, so the evidence on the page would be a "
                        "regenerated brief that merely resembles it."
                    ),
                }
            )
            continue
        built_by_case[case_no] = rebuilt

    if not built_by_case:
        raise BuildError(
            "every cached case was refused; the run and this code do not agree "
            "about what the agents were handed"
        )

    category_by_case = {
        case_no: built_by_case[case_no]["case"]["dispute"]["category"]
        for case_no in sorted(built_by_case)
    }
    policies, policy_digests = _policy_blocks(built_by_case, category_by_case)

    # The headline figures are computed over the whole run, not over the subset
    # the viewer can show: they are a measurement of the run, and a refusal is a
    # fact about the viewer. The refusal is reported beside them rather than
    # folded into them.
    produced = {case_no: raw_by_case[case_no]["ruling"] for case_no in numbers
                if "ruling" in raw_by_case[case_no]}
    report = grade.grade(produced)
    scores = {score.case_no: score for score in report.cases}

    # What the headline figures need per case, taken from the run's own result
    # files for every case the run holds -- refused ones included, so the
    # figures describe the run and not the subset this build could verify.
    case_facts = {
        case_no: {
            "discarded_claims": (
                (raw_by_case[case_no].get("ruling") or {}).get("discarded_claims") or []
            ),
            "wall_seconds": raw_by_case[case_no].get("wall_seconds"),
            "tokens": raw_by_case[case_no].get("tokens"),
        }
        for case_no in numbers
    }

    cases: List[Dict[str, Any]] = []
    for case_no in sorted(built_by_case):
        built = built_by_case[case_no]
        result = raw_by_case[case_no]
        transcript = _read_json(run_dir / ("case-%05d.transcript.json" % case_no))
        judge = _agent_block(transcript, transcript_module.ROLE_JUDGE)
        judge_output = result.get("ruling") or {}
        score = scores[case_no]
        expected = _expected_side(key_records[case_no])

        cases.append(
            {
                "case_no": case_no,
                "category": category_by_case[case_no],
                "difficulty": expected["difficulty"],
                "brief_sha256": result.get("brief_sha256"),
                "brief_rebuilt_sha256": _brief_digest(built),
                "dispute": _normalise(built["case"]["dispute"]),
                "evidence": _normalise(built["case"]["evidence"]),
                "advocates": {
                    transcript_module.ROLE_RIDER_ADVOCATE: _advocate_payload(
                        _agent_block(transcript, transcript_module.ROLE_RIDER_ADVOCATE)
                    ),
                    transcript_module.ROLE_DRIVER_ADVOCATE: _advocate_payload(
                        _agent_block(transcript, transcript_module.ROLE_DRIVER_ADVOCATE)
                    ),
                },
                "judge": {
                    "agent": judge,
                    "discarded_claims": _normalise(
                        judge_output.get("discarded_claims") or []
                    ),
                    "verdict": _produced_side(score),
                    "referrals": [
                        str(item)
                        for item in ((judge_output.get("ruling") or {}).get("referrals") or [])
                    ],
                },
                "expected": expected,
                "grading": _grading_of(score),
                "recorded_matched": result.get("matched"),
                "tokens": _normalise(result.get("tokens")),
                "wall_seconds": result.get("wall_seconds"),
                "call_seconds": result.get("call_seconds"),
                "recorded_at": result.get("recorded_at"),
                "git_commit": result.get("git_commit"),
                "python_version": result.get("python_version"),
                "model": result.get("model"),
            }
        )

    document = {
        "schema_version": 1,
        "generator": "ui/build.py",
        "default_case": DEFAULT_CASE if any(c["case_no"] == DEFAULT_CASE for c in cases) else (
            cases[0]["case_no"] if cases else None
        ),
        "decision_note": model_module.DECISION_NOTE,
        "decision_note_link": _DECISION_NOTE_LINK,
        "provenance": _provenance(run, invocations, run_dir),
        "headline": _headline(report, case_facts),
        "policies": policies,
        "policy_sha256": policy_digests,
        "cases": cases,
        "refused_cases": refused,
    }
    # One normalisation at the end rather than one at each use. A Decimal can
    # arrive from the brief, from a transcript's parsed value, or from a run file
    # read with ``parse_float=Decimal``, and a single pass makes it impossible to
    # miss one and ship a page whose data block will not parse.
    return _normalise(document)


def _advocate_payload(agent: Mapping[str, Any]) -> Dict[str, Any]:
    """An advocate block with its claims lifted out of whatever shape it chose."""
    payload = dict(agent)
    payload["claims"] = _claims_of(agent)
    return payload


# --------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------
_CSS = """
:root {
  --bg: #0e1116;
  --panel: #161c23;
  --panel-2: #1c242d;
  --line: #2b3641;
  --text: #e8eef5;
  --muted: #9dabb9;
  --accent: #79c0ff;
  --rider: #f0a35e;
  --driver: #62d2a2;
  --judge: #b9a2ff;
  --ok: #4ac26b;
  --warn: #d8a72a;
  --bad: #ff6b6b;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  padding-bottom: 74px;
}
a { color: var(--accent); }
h1, h2, h3, h4 { margin: 0 0 8px 0; line-height: 1.25; }
h1 { font-size: 20px; letter-spacing: 0.01em; }
h2 { font-size: 22px; margin-top: 4px; }
h3 { font-size: 16px; color: var(--text); margin-top: 22px; }
h4 { font-size: 14px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
p { margin: 8px 0; }
code, .mono { font-family: var(--mono); font-size: 12.5px; }

header.top {
  position: sticky; top: 0; z-index: 20;
  background: rgba(14,17,22,0.94);
  border-bottom: 1px solid var(--line);
  padding: 10px 20px;
  display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
}
header.top .brand { font-weight: 600; font-size: 15px; }
header.top .spacer { flex: 1; }
nav.views { display: flex; gap: 6px; }
main { padding: 20px; max-width: 1180px; margin: 0 auto; }

button {
  font: inherit; color: var(--text); background: var(--panel-2);
  border: 1px solid var(--line); border-radius: 6px; padding: 5px 11px; cursor: pointer;
}
button:hover { border-color: var(--accent); }
button.on { background: var(--accent); color: #08121c; border-color: var(--accent); font-weight: 600; }
button:disabled { opacity: 0.4; cursor: default; }
button:disabled:hover { border-color: var(--line); }

.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin: 16px 0 6px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 13px 15px; }
.card .label { color: var(--muted); font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.07em; }
.card .value { font-size: 25px; font-weight: 650; margin-top: 5px; font-variant-numeric: tabular-nums; }
.card .sub { color: var(--muted); font-size: 12.5px; margin-top: 4px; }
.card.wide { grid-column: span 2; }

table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th, td { text-align: left; padding: 6px 9px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.05em; }
tbody tr:hover { background: #1a222b; }
tr.clickable { cursor: pointer; }
tr.miss td { background: rgba(255,107,107,0.09); }
tr.miss:hover td { background: rgba(255,107,107,0.16); }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
td.case-no { font-weight: 650; font-variant-numeric: tabular-nums; }

.badge { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: 11.5px;
  border: 1px solid var(--line); color: var(--muted); white-space: nowrap; }
.badge.ok { color: var(--ok); border-color: rgba(74,194,107,0.5); }
.badge.miss { color: var(--bad); border-color: rgba(255,107,107,0.5); }
.badge.rider { color: var(--rider); border-color: rgba(240,163,94,0.5); }
.badge.driver { color: var(--driver); border-color: rgba(98,210,162,0.5); }
.badge.judge { color: var(--judge); border-color: rgba(185,162,255,0.5); }
.badge.complete { color: var(--ok); border-color: rgba(74,194,107,0.5); }
.badge.impaired { color: var(--warn); border-color: rgba(216,167,42,0.6); background: rgba(216,167,42,0.10); }
.badge.missing { color: var(--bad); border-color: rgba(255,107,107,0.6); background: rgba(255,107,107,0.10); }

.case-picker { display: flex; flex-wrap: wrap; gap: 5px; margin: 12px 0 16px; }
.case-picker button { padding: 3px 9px; font-size: 12.5px; font-variant-numeric: tabular-nums; }
.case-picker button.miss { border-color: rgba(255,107,107,0.45); color: #ffc9c9; }

.case-head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 4px; }
.case-head .title { font-size: 19px; font-weight: 650; }

.stepper { display: flex; gap: 6px; flex-wrap: wrap; margin: 14px 0; align-items: center; }
.stepper .step { font-size: 12.5px; }
.stepper .nav { margin-left: auto; display: flex; gap: 6px; }

section.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: 16px 18px; margin-top: 14px; }
section.panel + section.panel { margin-top: 14px; }

blockquote { margin: 10px 0; padding: 10px 14px; border-left: 3px solid var(--line);
  background: var(--panel-2); border-radius: 0 8px 8px 0; color: var(--text); }
blockquote .who { display: block; color: var(--muted); font-size: 12px; margin-bottom: 5px; }

.kv { display: grid; grid-template-columns: max-content 1fr; gap: 3px 16px; margin: 8px 0; font-size: 13.5px; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; }

dl.tree { display: grid; grid-template-columns: max-content 1fr; gap: 2px 14px; margin: 4px 0 4px 0; }
dl.tree > dt { color: var(--muted); font-family: var(--mono); font-size: 12px; padding-top: 1px; }
dl.tree > dd { margin: 0; }
ul.vals { margin: 0; padding-left: 16px; }
.null { color: #7b8794; font-style: italic; }
.bool { color: var(--accent); font-family: var(--mono); font-size: 12.5px; }
.scalar { font-family: var(--mono); font-size: 12.5px; }
.src { color: var(--muted); font-family: var(--mono); font-size: 11px; margin-left: 7px;
  border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; }
.empty { color: var(--muted); }

.artifact { border: 1px solid var(--line); border-left-width: 4px; border-radius: 8px;
  padding: 12px 14px; margin: 10px 0; background: var(--panel-2); }
.artifact.COMPLETE { border-left-color: var(--ok); }
.artifact.IMPAIRED { border-left-color: var(--warn); }
.artifact.MISSING { border-left-color: var(--bad); background: rgba(255,107,107,0.05); }
.artifact.flash { animation: flash 1.9s ease-out 1; }
@keyframes flash { 0% { background: rgba(121,192,255,0.30); } 100% { background: var(--panel-2); } }
.artifact .head { display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap; }
.artifact .id { font-family: var(--mono); font-weight: 650; font-size: 13px; }
.artifact .notes { color: var(--muted); font-size: 13px; margin: 7px 0 0 0; }
.artifact .issues { margin-top: 6px; display: flex; gap: 5px; flex-wrap: wrap; }

details { margin-top: 9px; }
details > summary { cursor: pointer; color: var(--muted); font-size: 12.5px; }
details[open] > summary { margin-bottom: 6px; }

.chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; align-items: center; }
.chips .chips-label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; margin-right: 3px; }
.chip { font-family: var(--mono); font-size: 11.5px; padding: 1px 7px; border-radius: 999px;
  background: #223040; border: 1px solid #33465a; color: #bcd8f5; }
.chip:hover { border-color: var(--accent); }
.chip.evidence { background: #1f2d24; border-color: #33543f; color: #b6e8c4; }
.chip.clause { background: #2b2537; border-color: #453a5c; color: #d6c8ff; }
.chip.unknown { background: rgba(255,107,107,0.12); border-color: rgba(255,107,107,0.5); color: #ffc9c9; }
.chip.issue { background: rgba(216,167,42,0.14); border-color: rgba(216,167,42,0.5); color: #f2d68a; }

.claim { border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; margin: 10px 0; background: var(--panel-2); }
.claim .claim-head { display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap; color: var(--muted); font-size: 12px; }
.claim .claim-no { font-family: var(--mono); color: var(--text); font-weight: 650; }
.claim .text { margin: 8px 0 0 0; }
.claim.discarded { border-color: rgba(255,107,107,0.4); background: rgba(255,107,107,0.06); }

.role { border-top: 3px solid var(--line); padding-top: 12px; }
.role.RIDER_ADVOCATE { border-top-color: var(--rider); }
.role.DRIVER_ADVOCATE { border-top-color: var(--driver); }
.role.JUDGE { border-top-color: var(--judge); }

.callbar { color: var(--muted); font-size: 12px; font-family: var(--mono); margin-top: 6px; }
.callbar .warn { color: var(--warn); }
pre.raw { background: #10151b; border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px;
  overflow-x: auto; font-family: var(--mono); font-size: 12px; white-space: pre-wrap; word-break: break-word; max-height: 340px; }

footer.prov { position: fixed; left: 0; right: 0; bottom: 0; z-index: 30;
  background: rgba(18,23,29,0.97); border-top: 1px solid var(--line);
  padding: 7px 20px; font-size: 11.5px; color: var(--muted); font-family: var(--mono);
  display: flex; flex-wrap: wrap; gap: 4px 18px; }
footer.prov b { color: var(--text); font-weight: 600; }

.modal { position: fixed; inset: 0; z-index: 50; background: rgba(5,8,11,0.72);
  display: flex; align-items: flex-start; justify-content: center; padding: 48px 20px; }
.modal .box { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
  max-width: 820px; width: 100%; max-height: 78vh; overflow: auto; padding: 18px 20px; }
.modal .box .head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.modal .box .head .id { font-family: var(--mono); font-weight: 650; font-size: 15px; color: var(--judge); }
.modal .box .close { margin-left: auto; }
.modal .rule { margin-top: 12px; white-space: pre-wrap; }

.miss-note { margin-top: 10px; padding: 11px 14px; border: 1px solid rgba(255,107,107,0.4);
  border-radius: 8px; background: rgba(255,107,107,0.06); font-size: 13.5px; }
.warnbox { margin-top: 12px; padding: 11px 14px; border: 1px solid rgba(216,167,42,0.5);
  border-radius: 8px; background: rgba(216,167,42,0.07); font-size: 13.5px; }
.lead { color: var(--muted); max-width: 78ch; }
.hint { color: var(--muted); font-size: 12.5px; margin-top: 10px; }
"""

_JS = r"""
(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("tribunal-data").textContent);
  var BY_CASE = {};
  DATA.cases.forEach(function (c) { BY_CASE[c.case_no] = c; });

  // Every clause of every loaded policy, by id, built once. A clause id in a
  // claim may carry a limb -- POL-NS-06(i), POL-RD-06(c) -- so lookup strips the
  // limb and shows the clause the limb belongs to.
  var CLAUSES = {};
  Object.keys(DATA.policies).forEach(function (category) {
    var block = DATA.policies[category];
    ["general", "category"].forEach(function (which) {
      var policy = block[which] || {};
      (policy.clauses || []).forEach(function (clause) {
        if (!Object.prototype.hasOwnProperty.call(CLAUSES, clause.id)) {
          CLAUSES[clause.id] = {
            clause: clause,
            policy_id: policy.policy_id,
            category: category,
            which: which
          };
        }
      });
    });
  });

  var STEPS = [
    { id: "dispute",  label: "1. The dispute" },
    { id: "evidence", label: "2. The evidence" },
    { id: "rider",    label: "3. Rider advocate" },
    { id: "driver",   label: "4. Driver advocate" },
    { id: "judge",    label: "5. Judge" },
    { id: "key",      label: "6. Against the answer key" }
  ];

  var state = { view: "overview", caseNo: DATA.default_case, step: 0, highlight: null };

  // ---- DOM helpers -------------------------------------------------------
  function h(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        var value = attrs[key];
        if (value === null || value === undefined || value === false) { return; }
        if (key === "class") { node.className = value; }
        else if (key === "text") { node.textContent = String(value); }
        else if (key === "onclick") { node.addEventListener("click", value); }
        else if (key === "data") {
          Object.keys(value).forEach(function (name) {
            node.setAttribute("data-" + name, String(value[name]));
          });
        } else { node.setAttribute(key, value === true ? "" : String(value)); }
      });
    }
    add(node, children);
    return node;
  }
  function add(node, children) {
    if (children === null || children === undefined) { return; }
    if (Array.isArray(children)) {
      children.forEach(function (child) { add(node, child); });
      return;
    }
    if (children instanceof Node) { node.appendChild(children); return; }
    node.appendChild(document.createTextNode(String(children)));
  }
  function clear(node) { while (node.firstChild) { node.removeChild(node.firstChild); } }
  function byData(attr, value) {
    var all = document.querySelectorAll("[" + attr + "]");
    for (var i = 0; i < all.length; i += 1) {
      if (all[i].getAttribute(attr) === value) { return all[i]; }
    }
    return null;
  }
  function text(value) {
    if (value === null || value === undefined) { return "null"; }
    return String(value);
  }
  function paragraphs(value) {
    if (!value) { return h("p", { class: "null", text: "(none)" }); }
    return String(value).split(/\n\s*\n/).map(function (part) {
      return h("p", { text: part });
    });
  }
  function definitionList(pairs) {
    var dl = h("dl", { class: "kv" });
    pairs.forEach(function (pair) {
      if (pair[1] === null || pair[1] === undefined) { return; }
      dl.appendChild(h("dt", { text: pair[0] }));
      dl.appendChild(h("dd", null, pair[1]));
    });
    return dl;
  }

  // A value tree from the brief: objects become nested lists, arrays become
  // bullet lists, and a derived fact -- {value, evidence_id} -- carries the
  // artifact it was computed from, so a number on the page has a source.
  function renderValue(value) {
    if (value === null || value === undefined) { return h("span", { class: "null", text: "null" }); }
    if (Array.isArray(value)) {
      if (!value.length) { return h("span", { class: "empty", text: "[]" }); }
      return h("ul", { class: "vals" }, value.map(function (item) {
        return h("li", null, renderValue(item));
      }));
    }
    if (typeof value === "object") {
      var keys = Object.keys(value);
      if (keys.length === 2 && keys.indexOf("value") >= 0 && keys.indexOf("evidence_id") >= 0) {
        return h("span", null, [
          renderValue(value.value),
          h("span", { class: "src", text: value.evidence_id })
        ]);
      }
      var dl = h("dl", { class: "tree" });
      keys.forEach(function (key) {
        dl.appendChild(h("dt", { text: key }));
        dl.appendChild(h("dd", null, renderValue(value[key])));
      });
      return dl;
    }
    if (typeof value === "boolean") {
      return h("span", { class: "bool", text: value ? "true" : "false" });
    }
    return h("span", { class: "scalar", text: String(value) });
  }

  // ---- chips -------------------------------------------------------------
  function evidenceChip(caseDoc, evidenceId) {
    var known = (caseDoc.evidence || []).some(function (a) { return a.evidence_id === evidenceId; });
    if (!known) {
      return h("span", { class: "chip unknown", title: "not an artifact in this case's brief",
        text: evidenceId + " (not in this brief)" });
    }
    return h("button", { class: "chip evidence", data: { evidence: evidenceId },
      title: "open this artifact", text: evidenceId,
      onclick: function () { jumpToEvidence(evidenceId); } });
  }
  function clauseChip(clauseId) {
    var base = String(clauseId).replace(/\s*\([^)]*\)\s*$/, "");
    var known = Object.prototype.hasOwnProperty.call(CLAUSES, base);
    return h("button", {
      class: known ? "chip clause" : "chip unknown",
      title: known ? "show this clause's rule text" : "not a clause in the loaded policy",
      text: clauseId,
      onclick: function () { openClause(clauseId); }
    });
  }
  function chips(label, children) {
    return h("div", { class: "chips" }, [h("span", { class: "chips-label", text: label })].concat(children));
  }

  // ---- navigation --------------------------------------------------------
  function showView(name) {
    state.view = name;
    document.getElementById("view-overview").hidden = name !== "overview";
    document.getElementById("view-case").hidden = name !== "case";
    document.getElementById("nav-overview").classList.toggle("on", name === "overview");
    document.getElementById("nav-case").classList.toggle("on", name === "case");
    if (name === "case") { renderCase(); }
  }
  function openCase(caseNo) {
    state.caseNo = caseNo;
    state.step = 0;
    state.highlight = null;
    showView("case");
    window.scrollTo(0, 0);
  }
  function goToStep(index) {
    state.step = Math.max(0, Math.min(STEPS.length - 1, index));
    state.highlight = null;
    renderCase();
  }
  function jumpToEvidence(evidenceId) {
    state.step = 1;
    state.highlight = evidenceId;
    renderCase();
    var node = byData("data-artifact", evidenceId);
    if (node && node.scrollIntoView) { node.scrollIntoView({ block: "center" }); }
  }
  function openClause(rawId) {
    var base = String(rawId).replace(/\s*\([^)]*\)\s*$/, "");
    var entry = CLAUSES[base];
    var box = h("div", { class: "box" });
    box.appendChild(h("div", { class: "head" }, [
      h("span", { class: "id", text: rawId }),
      entry ? h("span", { class: "badge", text: entry.policy_id + " - " + entry.which }) : null,
      h("button", { class: "close", text: "close", onclick: closeModal })
    ]));
    if (!entry) {
      box.appendChild(h("p", { class: "miss-note", text:
        "No clause with this id is in the policy the brief carried. The claim cites a clause the agents were not given." }));
    } else {
      box.appendChild(h("h3", { text: entry.clause.title || entry.clause.id }));
      box.appendChild(h("p", { class: "hint", text: "rule text, as the agents received it" }));
      box.appendChild(h("div", { class: "rule", text: entry.clause.rule }));
    }
    var overlay = h("div", { class: "modal", id: "clause-modal", onclick: function (event) {
      if (event.target === overlay) { closeModal(); }
    } }, box);
    document.body.appendChild(overlay);
  }
  function closeModal() {
    var modal = document.getElementById("clause-modal");
    if (modal) { modal.parentNode.removeChild(modal); }
  }

  // ---- View 1: overview --------------------------------------------------
  function headlineCards() {
    var hl = DATA.headline;
    var esc = hl.escalation;
    var cards = h("div", { class: "cards" });

    cards.appendChild(h("div", { class: "card wide" }, [
      h("div", { class: "label", text: "Four-field exact match" }),
      h("div", { class: "value", text: hl.exact.display }),
      h("div", { class: "sub", text: "A ruling counts only when ruling, amount_sgd, driver_compensation_sgd and referrals all agree with the key." })
    ]));
    cards.appendChild(h("div", { class: "card" }, [
      h("div", { class: "label", text: "Discarded claims, all judges" }),
      h("div", { class: "value", text: String(hl.discarded_claims.total) }),
      h("div", { class: "sub", text: "Claims the judges threw out for a citation defect, across all " + hl.cases_graded + " cases." })
    ]));
    cards.appendChild(h("div", { class: "card" }, [
      h("div", { class: "label", text: "Mean seconds per case" }),
      h("div", { class: "value", text: text(hl.seconds.mean_per_case) + " s" }),
      h("div", { class: "sub", text: hl.seconds.total + " s over " + hl.seconds.cases + " cases." })
    ]));
    cards.appendChild(h("div", { class: "card" }, [
      h("div", { class: "label", text: "Mean tokens per case" }),
      h("div", { class: "value", text: text(hl.tokens.mean_per_case) }),
      h("div", { class: "sub", text: hl.tokens.total.toLocaleString() + " tokens over " + hl.tokens.cases + " cases." })
    ]));
    cards.appendChild(h("div", { class: "card" }, [
      h("div", { class: "label", text: "Escalation recall" }),
      h("div", { class: "value", text: esc.recall.display }),
      h("div", { class: "sub", text: esc.recall.matched + " of " + esc.recall.total + " cases the key escalates." })
    ]));
    cards.appendChild(h("div", { class: "card" }, [
      h("div", { class: "label", text: "Escalation precision" }),
      h("div", { class: "value", text: esc.precision.display }),
      h("div", { class: "sub", text: esc.precision.matched + " of " + esc.precision.total + " cases the run escalated." })
    ]));
    cards.appendChild(h("div", { class: "card" }, [
      h("div", { class: "label", text: "Over-escalations" }),
      h("div", { class: "value", text: String(esc.over_escalations.length) }),
      h("div", { class: "sub", text: esc.over_escalations.length ? "case " + esc.over_escalations.join(", ") : "none" })
    ]));
    cards.appendChild(h("div", { class: "card" }, [
      h("div", { class: "label", text: "Under-escalations" }),
      h("div", { class: "value", text: String(esc.under_escalations.length) }),
      h("div", { class: "sub", text: esc.under_escalations.length ? "case " + esc.under_escalations.join(", ") : "none" })
    ]));
    return cards;
  }

  function fieldTable() {
    var hl = DATA.headline;
    var body = h("tbody");
    ["ruling", "amount_sgd", "driver_compensation_sgd", "referrals"].forEach(function (name) {
      var cell = hl.fields[name];
      body.appendChild(h("tr", null, [
        h("td", null, h("code", { text: name })),
        h("td", { class: "num", text: cell.display })
      ]));
    });
    return h("table", null, [
      h("thead", null, h("tr", null, [h("th", { text: "Graded field" }), h("th", { text: "Agreed with the key" })])),
      body
    ]);
  }

  function caseGrid() {
    var body = h("tbody");
    DATA.cases.forEach(function (c) {
      var row = h("tr", {
        class: (c.grading.exact ? "clickable" : "clickable miss"),
        title: "open case " + c.case_no,
        onclick: function () { openCase(c.case_no); }
      });
      row.appendChild(h("td", { class: "case-no", text: String(c.case_no) }));
      row.appendChild(h("td", { text: c.category }));
      row.appendChild(h("td", { text: text(c.difficulty) }));
      row.appendChild(h("td", { text: text(c.judge.verdict.ruling) }));
      row.appendChild(h("td", { text: text(c.expected.ruling) }));
      row.appendChild(h("td", null, h("span", {
        class: c.grading.exact ? "badge ok" : "badge miss",
        text: c.grading.exact ? "match" : "MISS"
      })));
      body.appendChild(row);
    });
    return h("table", null, [
      h("thead", null, h("tr", null, [
        h("th", { text: "#" }), h("th", { text: "Category" }), h("th", { text: "Difficulty" }),
        h("th", { text: "Produced" }), h("th", { text: "Expected" }), h("th", { text: "Result" })
      ])),
      body
    ]);
  }

  function refusedBlock() {
    if (!DATA.refused_cases.length) { return null; }
    var box = h("div", { class: "warnbox" });
    box.appendChild(h("b", { text: "Cases refused by this build" }));
    box.appendChild(h("p", { text:
      "A case is refused when the brief this code builds does not match the digest the result recorded. " +
      "Its evidence would then be a regenerated brief that merely resembles what the agents received, so it is not shown." }));
    var list = h("ul");
    DATA.refused_cases.forEach(function (entry) {
      list.appendChild(h("li", null, [
        h("b", { text: "case " + entry.case_no + " - " }),
        entry.reason + " ",
        h("code", { text: "recorded " + text(entry.recorded_brief_sha256) + ", rebuilt " + text(entry.rebuilt_brief_sha256) })
      ]));
    });
    box.appendChild(list);
    return box;
  }

  function renderOverview() {
    var root = document.getElementById("view-overview");
    clear(root);
    root.appendChild(h("h2", { text: "The run, at a glance" }));
    root.appendChild(h("p", { class: "lead", text:
      "Every figure here is computed from the committed run " + DATA.provenance.run_directory +
      " and the same grading code that produces eval/grade.py's report. Nothing on this page is typed in." }));
    root.appendChild(headlineCards());
    root.appendChild(h("h3", { text: "Per-field accuracy" }));
    root.appendChild(h("p", { class: "lead", text:
      "The per-field figures are there so a reader can see which field a model actually fails on; they are not alternative scores." }));
    root.appendChild(fieldTable());
    root.appendChild(h("h3", { text: "Escalation" }));
    root.appendChild(escalationTable());
    root.appendChild(h("h3", { text: "All " + DATA.cases.length + " cases" }));
    root.appendChild(h("p", { class: "lead", text: "Click any row to open the case stepped through in order." }));
    root.appendChild(caseGrid());
    root.appendChild(missNote());
    var refused = refusedBlock();
    if (refused) { root.appendChild(refused); }
  }

  function escalationTable() {
    var esc = DATA.headline.escalation;
    return h("table", null, [
      h("thead", null, h("tr", null, [h("th", { text: "" }), h("th", { text: "" })])),
      h("tbody", null, [
        h("tr", null, [h("td", { text: "Expected escalations" }), h("td", { class: "num", text: String(esc.expected) })]),
        h("tr", null, [h("td", { text: "Produced escalations" }), h("td", { class: "num", text: String(esc.produced) })]),
        h("tr", null, [h("td", { text: "Escalation rate" }), h("td", { class: "num", text: esc.rate_percent })]),
        h("tr", null, [h("td", { text: "Corpus target" }), h("td", { class: "num", text: esc.target_percent + (esc.off_target ? " (off target)" : " (on target)") })]),
        h("tr", null, [h("td", { text: "INDETERMINATE cases ruled confidently" }), h("td", { class: "num",
          text: esc.indeterminate_ruled_confidently.length ? esc.indeterminate_ruled_confidently.join(", ") : "none" })])
      ])
    ]);
  }

  function missNote() {
    var misses = DATA.cases.filter(function (c) { return !c.grading.exact; });
    if (!misses.length) { return null; }
    var box = h("div", { class: "miss-note" });
    misses.forEach(function (c) {
      box.appendChild(h("div", null, [
        h("b", { text: "Case " + c.case_no + " is a miss, and it is shown as one. " }),
        "It failed on " + c.grading.failed_fields.join(", ") + ". ",
        h("a", { href: DATA.decision_note_link, text: DATA.decision_note }),
        " records why this is a contested reading rather than a defect, and why the answer key is not changed for it."
      ]));
    });
    return box;
  }

  // ---- View 2: one case, stepped through ---------------------------------
  function renderCase() {
    var root = document.getElementById("view-case");
    var caseDoc = BY_CASE[state.caseNo];
    clear(root);
    if (!caseDoc) { root.appendChild(h("p", { text: "no such case" })); return; }

    var picker = h("div", { class: "case-picker" });
    DATA.cases.forEach(function (c) {
      picker.appendChild(h("button", {
        class: (c.case_no === state.caseNo ? "on" : (c.grading.exact ? "" : "miss")),
        text: String(c.case_no),
        onclick: function () { openCase(c.case_no); }
      }));
    });
    root.appendChild(picker);

    root.appendChild(h("div", { class: "case-head" }, [
      h("span", { class: "title", text: "Case " + caseDoc.case_no }),
      h("span", { class: "badge", text: caseDoc.category }),
      h("span", { class: "badge", text: text(caseDoc.difficulty) }),
      h("span", {
        class: caseDoc.grading.exact ? "badge ok" : "badge miss",
        text: caseDoc.grading.exact ? "four-field match" : "MISS on " + caseDoc.grading.failed_fields.join(", ")
      }),
      h("span", { class: "badge", text: "brief " + String(caseDoc.brief_sha256).slice(0, 12) })
    ]));

    var stepper = h("div", { class: "stepper" });
    STEPS.forEach(function (step, index) {
      stepper.appendChild(h("button", {
        class: "step" + (index === state.step ? " on" : ""),
        text: step.label,
        onclick: function () { goToStep(index); }
      }));
    });
    stepper.appendChild(h("span", { class: "nav" }, [
      h("button", { text: "back", disabled: state.step === 0, onclick: function () { goToStep(state.step - 1); } }),
      h("button", { text: "next", disabled: state.step === STEPS.length - 1, onclick: function () { goToStep(state.step + 1); } })
    ]));
    root.appendChild(stepper);

    var body = h("div", { id: "step-body" });
    root.appendChild(body);
    var panel = h("section", { class: "panel" });
    var render = [renderDispute, renderEvidence, renderRider, renderDriver, renderJudge, renderKey][state.step];
    render(caseDoc, panel);
    body.appendChild(panel);
    root.appendChild(h("p", { class: "hint", text: "Step " + (state.step + 1) + " of " + STEPS.length +
      ". Clicking an evidence chip on a claim opens the artifact it cites; clicking a clause chip shows the clause's rule text." }));
  }

  function renderDispute(caseDoc, panel) {
    var dispute = caseDoc.dispute;
    panel.appendChild(h("h2", { text: "The dispute" }));
    panel.appendChild(definitionList([
      ["case", String(caseDoc.case_no)],
      ["dispute id", h("code", { text: text(dispute.dispute_id) })],
      ["trip id", h("code", { text: text(dispute.trip_id) })],
      ["category", text(dispute.category)],
      ["filed by", text(dispute.filed_by)],
      ["filed at", text(dispute.filed_at)],
      ["channel", text(dispute.channel)],
      ["amount contested", "SGD " + text(dispute.amount_contested_sgd)]
    ]));

    panel.appendChild(h("h4", { text: "The claim, as filed" }));
    panel.appendChild(h("blockquote", null, [
      h("span", { class: "who", text: "filed by " + text(dispute.filed_by) + " at " + text(dispute.filed_at) }),
      h("span", { text: text(dispute.claim_text) })
    ]));

    var counterparty = dispute.counterparty_statement;
    panel.appendChild(h("h4", { text: "The counterparty's statement" }));
    if (counterparty) {
      panel.appendChild(h("blockquote", null, [
        h("span", { class: "who", text: "submitted by " + text(counterparty.submitted_by) + " at " + text(counterparty.submitted_at) }),
        h("span", { text: text(counterparty.text) })
      ]));
    } else {
      panel.appendChild(h("p", { class: "null", text: "no counterparty statement on the record" }));
    }
    panel.appendChild(h("p", { class: "hint", text:
      "The amount contested is the figure the dispute names. The amount actually decided is on the judge step, and whether it agrees with the key is on step 6." }));
  }

  function renderEvidence(caseDoc, panel) {
    panel.appendChild(h("h2", { text: "The evidence" }));
    panel.appendChild(h("p", { class: "lead", text:
      "Every artifact the agents were handed, with the admissibility pre-pass's own assessment and the facts derived from it. " +
      "COMPLETE, IMPAIRED and MISSING are shown apart because the pre-pass is what this project adds to a plain reading of the file." }));
    caseDoc.evidence.forEach(function (artifact) {
      panel.appendChild(artifactBlock(artifact, caseDoc));
    });
  }

  function artifactBlock(artifact, caseDoc) {
    var admissibility = artifact.admissibility || {};
    var status = admissibility.status || "COMPLETE";
    var box = h("div", {
      class: "artifact " + status + (state.highlight === artifact.evidence_id ? " flash" : ""),
      data: { artifact: artifact.evidence_id }
    });
    box.appendChild(h("div", { class: "head" }, [
      h("span", { class: "id", text: artifact.evidence_id }),
      h("span", { class: "badge", text: artifact.evidence_type }),
      h("span", { class: "badge " + status.toLowerCase(), text: status }),
      h("span", { class: "badge", text: "weight " + text(admissibility.weight_multiplier) }),
      artifact.source ? h("span", { class: "badge", text: artifact.source }) : null
    ]));

    var issues = admissibility.issues || [];
    if (issues.length) {
      box.appendChild(chips("issue codes", issues.map(function (issue) {
        return h("span", { class: "chip issue", text: String(issue) });
      })));
    } else {
      box.appendChild(chips("issue codes", [h("span", { class: "empty", text: "none - admissible on its face" })]));
    }
    if (admissibility.notes) {
      box.appendChild(h("p", { class: "notes", text: admissibility.notes }));
    }
    box.appendChild(definitionList([
      ["trip", artifact.trip_id ? h("code", { text: artifact.trip_id }) : null],
      ["generated", text(artifact.generated_at)],
      ["assessed", text(admissibility.assessed_at)],
      ["assessor", text(admissibility.assessor_version)]
    ]));

    var payload = artifact.payload;
    if (payload === null || payload === undefined) {
      box.appendChild(h("p", { class: "notes", text:
        "This artifact carries no payload: the record itself is absent, and the absence is what the agents were handed." }));
      return box;
    }

    var derived = (typeof payload === "object" && !Array.isArray(payload)) ? payload.derived : null;
    var rest = payload;
    if (derived) {
      rest = {};
      Object.keys(payload).forEach(function (key) {
        if (key !== "derived") { rest[key] = payload[key]; }
      });
    }

    var payloadDetails = h("details", null, [
      h("summary", { text: "payload" }),
      renderValue(rest)
    ]);
    box.appendChild(payloadDetails);

    if (derived) {
      var derivedBox = h("div", null, [
        h("h4", { text: "derived facts" }),
        h("p", { class: "hint", text: "Each fact carries the artifact it was computed from." })
      ]);
      Object.keys(derived).forEach(function (group) {
        derivedBox.appendChild(h("h4", { text: group }));
        derivedBox.appendChild(renderValue(derived[group]));
      });
      box.appendChild(derivedBox);
    }
    return box;
  }

  function advocateSection(caseDoc, role, label, accent, panel) {
    var agent = caseDoc.advocates[role];
    var section = h("div", { class: "role " + role });
    section.appendChild(h("h2", { text: label }));
    section.appendChild(h("span", { class: "badge " + accent, text: role }));

    if (!agent.parsed) {
      section.appendChild(h("p", { class: "miss-note", text:
        "This agent produced no parsable answer for this case." }));
    }
    var claims = agent.claims || [];
    section.appendChild(h("p", { class: "lead", text:
      claims.length + (claims.length === 1 ? " claim" : " claims") +
      ". Every claim cites both an evidence id and a clause id; a chip you can click is a record you can open." }));

    claims.forEach(function (claim, index) {
      var box = h("div", { class: "claim" });
      box.appendChild(h("div", { class: "claim-head" }, [
        h("span", { class: "claim-no", text: "#" + (index + 1) }),
        claim.asserted_weight !== undefined ? h("span", { text: "asserted weight " + text(claim.asserted_weight) }) : null,
        claim.relies_on ? h("span", null, ["relies on ", h("code", { text: claim.relies_on })]) : null
      ]));
      box.appendChild(h("p", { class: "text", text: text(claim.text) }));
      var evidenceIds = claim.evidence_ids || [];
      var clauseIds = claim.clause_ids || [];
      box.appendChild(chips("evidence", evidenceIds.map(function (id) {
        return evidenceChip(caseDoc, id);
      })));
      box.appendChild(chips("clauses", clauseIds.map(clauseChip)));
      if (!evidenceIds.length || !clauseIds.length) {
        box.appendChild(h("p", { class: "miss-note", text:
          "This claim is missing a citation. No citation, no claim." }));
      }
      section.appendChild(box);
    });
    panel.appendChild(section);
    panel.appendChild(callBar(agent));
  }

  function callBar(agent) {
    var bar = h("div", { class: "callbar" });
    agent.calls.forEach(function (call, index) {
      var parts = [
        "call " + (index + 1) + ": " + text(call.parse_outcome),
        "shape=" + text(call.shape),
        "attempts=" + text(call.attempts),
        "prompt=" + text(call.prompt_tokens),
        "completion=" + text(call.completion_tokens),
        "reasoning=" + text(call.reasoning_tokens),
        "cached=" + text(call.cached_tokens),
        text(Math.round((call.duration_seconds || 0) * 10) / 10) + "s"
      ];
      var line = h("div", { class: call.parse_outcome === "PARSED" ? "" : "warn", text: parts.join("  ") });
      bar.appendChild(line);
      if (call.note) { bar.appendChild(h("div", { class: "warn", text: "note: " + call.note })); }
      if (call.response_text) {
        bar.appendChild(h("details", null, [
          h("summary", { text: "raw response that did not parse" }),
          h("pre", { class: "raw", text: call.response_text })
        ]));
      }
    });
    return bar;
  }

  function renderRider(caseDoc, panel) {
    advocateSection(caseDoc, "RIDER_ADVOCATE", "The rider's advocate", "rider", panel);
  }
  function renderDriver(caseDoc, panel) {
    advocateSection(caseDoc, "DRIVER_ADVOCATE", "The driver's advocate", "driver", panel);
  }

  function renderJudge(caseDoc, panel) {
    var judge = caseDoc.judge;
    var section = h("div", { class: "role JUDGE" });
    section.appendChild(h("h2", { text: "The judge" }));
    section.appendChild(h("span", { class: "badge judge", text: "JUDGE" }));

    var discarded = judge.discarded_claims || [];
    section.appendChild(h("h3", { text: "Discarded claims first" }));
    section.appendChild(h("p", { class: "lead", text:
      discarded.length
        ? "The judge threw out " + discarded.length + (discarded.length === 1 ? " claim" : " claims") +
          " before deciding. A discarded claim is a claim that cited an impaired artifact without disclosing the impairment, as POL-GEN-02(1) requires."
        : "The judge discarded no claims in this case: every claim it was given carried its citations correctly." }));
    discarded.forEach(function (entry, index) {
      var box = h("div", { class: "claim discarded" });
      box.appendChild(h("div", { class: "claim-head" }, [
        h("span", { class: "claim-no", text: "#" + (index + 1) }),
        h("span", { class: "badge " + (String(entry.side).toLowerCase() === "rider" ? "rider" : "driver"),
          text: "side: " + text(entry.side) })
      ]));
      box.appendChild(h("p", { class: "text", text: text(entry.claim) }));
      box.appendChild(h("p", { class: "notes", text: "reason: " + text(entry.reason) }));
      section.appendChild(box);
    });

    var verdict = judge.verdict;
    section.appendChild(h("h3", { text: "The ruling" }));
    section.appendChild(definitionList([
      ["ruling", h("span", { class: "badge judge", text: text(verdict.ruling) })],
      ["amount_sgd", text(verdict.amount_sgd)],
      ["driver_compensation_sgd", text(verdict.driver_compensation_sgd)],
      ["confidence", text(verdict.confidence)]
    ]));

    section.appendChild(h("h4", { text: "Referrals" }));
    if (judge.referrals && judge.referrals.length) {
      var list = h("ul");
      judge.referrals.forEach(function (item) {
        list.appendChild(h("li", null, [h("span", { text: String(item) }), " ", clauseChipsInText(String(item))]));
      });
      section.appendChild(list);
    } else {
      section.appendChild(h("p", { class: "null", text: "no referral: no clause on these facts sends the case to a human" }));
    }

    section.appendChild(h("h4", { text: "Explanation" }));
    section.appendChild(h("div", null, paragraphs(verdict.explanation)));

    panel.appendChild(section);
    panel.appendChild(callBar(judge.agent));
  }

  function clauseChipsInText(value) {
    var found = value.match(/POL-[A-Z]{2,4}-[0-9]{2}(?:\([A-Za-z0-9]{1,3}\))?/g);
    if (!found) { return null; }
    var seen = {};
    var unique = found.filter(function (id) {
      if (seen[id]) { return false; }
      seen[id] = true;
      return true;
    });
    return h("span", { class: "chips" }, unique.map(clauseChip));
  }

  function renderKey(caseDoc, panel) {
    panel.appendChild(h("h2", { text: "Against the answer key" }));
    panel.appendChild(h("p", { class: "lead", text:
      "The expected side is the grading answer key at eval/answers/ground_truth.json. It is the answer key, not an input: " +
      "no agent saw it, and nothing under tribunal/ can reach it. A case counts as a match only when all four fields agree." }));

    var body = h("tbody");
    caseDoc.grading.fields.forEach(function (outcome) {
      var expectedValue = null;
      var producedValue = null;
      if (outcome.field === "referrals") {
        expectedValue = referralList(caseDoc.expected.referrals);
        producedValue = referralList(caseDoc.judge.referrals);
      } else if (outcome.field === "ruling") {
        expectedValue = h("code", { text: text(caseDoc.expected.ruling) });
        producedValue = h("code", { text: text(caseDoc.judge.verdict.ruling) });
      } else {
        expectedValue = h("span", { class: "mono", text: text(caseDoc.expected[outcome.field]) });
        producedValue = h("span", { class: "mono", text: text(caseDoc.judge.verdict[outcome.field]) });
      }
      body.appendChild(h("tr", null, [
        h("td", null, h("code", { text: outcome.field })),
        h("td", null, expectedValue),
        h("td", null, producedValue),
        h("td", null, h("span", { class: outcome.correct ? "badge ok" : "badge miss",
          text: outcome.correct ? "match" : "MISS" })),
        h("td", { class: "hint", text: outcome.detail || "" })
      ]));
    });
    panel.appendChild(h("table", null, [
      h("thead", null, h("tr", null, [
        h("th", { text: "Field" }), h("th", { text: "Expected (answer key)" }),
        h("th", { text: "Produced (the run)" }), h("th", { text: "Result" }), h("th", { text: "Grader's detail" })
      ])),
      body
    ]));

    panel.appendChild(h("h4", { text: "Answer-key metadata" }));
    panel.appendChild(definitionList([
      ["difficulty", text(caseDoc.expected.difficulty)],
      ["governing clauses", (caseDoc.expected.governing_clauses || []).map(function (id) {
        return h("div", null, [clauseChip(id)]);
      })],
      ["recorded matched flag", text(caseDoc.recorded_matched)]
    ]));
    if (caseDoc.recorded_matched !== caseDoc.grading.exact) {
      panel.appendChild(h("div", { class: "warnbox", text:
        "The run recorded matched=" + text(caseDoc.recorded_matched) + " for this case but the grader now reads " +
        text(caseDoc.grading.exact) + ". The two disagree, and the grader is the one that is recomputed here." }));
    }
    if (caseDoc.expected.rationale) {
      panel.appendChild(h("h4", { text: "The key's rationale" }));
      panel.appendChild(h("div", null, paragraphs(caseDoc.expected.rationale)));
    }
    if (!caseDoc.grading.exact) {
      panel.appendChild(h("div", { class: "miss-note" }, [
        h("b", { text: "This case is a miss and is shown as one. " }),
        h("a", { href: DATA.decision_note_link, text: DATA.decision_note }),
        " records why the reading is contested and why the key is not changed for it."
      ]));
    }
  }

  function referralList(items) {
    if (!items || !items.length) { return h("span", { class: "null", text: "none" }); }
    return h("ul", { class: "vals" }, items.map(function (item) {
      return h("li", { text: String(item) });
    }));
  }

  // ---- provenance --------------------------------------------------------
  function renderProvenance() {
    var footer = document.getElementById("provenance");
    var p = DATA.provenance;
    var short = function (value, length) {
      if (!value) { return "n/a"; }
      return String(value).slice(0, length || 12);
    };
    var fields = [
      ["model", text(p.model) + (p.model === p.runtime_model ? "" : " (runtime model is " + p.runtime_model + ")")],
      ["git commit", short(p.git_commit)],
      ["prompts", short(p.prompts_sha256)],
      ["answer key", short(p.answer_key_sha256)],
      ["python", text(p.python_version)],
      ["run", text(p.started_at) + " to " + text(p.ended_at)],
      ["run dir", p.run_directory],
      ["invocations", String(p.invocation_count)]
    ];
    clear(footer);
    fields.forEach(function (pair) {
      footer.appendChild(h("span", null, [
        h("b", { text: pair[0] + ": " }),
        h("span", { text: pair[1] })
      ]));
    });
  }

  // ---- start -------------------------------------------------------------
  document.getElementById("nav-overview").addEventListener("click", function () { showView("overview"); });
  document.getElementById("nav-case").addEventListener("click", function () { showView("case"); });
  renderProvenance();
  renderOverview();
  showView("overview");
})();
"""

_BODY = """
<header class="top">
  <span class="brand">Tribunal - debate viewer</span>
  <nav class="views">
    <button id="nav-overview" class="on">Overview</button>
    <button id="nav-case">One case</button>
  </nav>
  <span class="spacer"></span>
  <span class="badge">replay of a committed run</span>
</header>
<main>
  <noscript>
    <p>This viewer renders itself from data embedded in this file, so it needs
    JavaScript enabled. It makes no network request of any kind.</p>
  </noscript>
  <section id="view-overview"></section>
  <section id="view-case" hidden></section>
</main>
<footer class="prov" id="provenance"></footer>
"""


def render_html(document: Mapping[str, Any]) -> str:
    """The whole page, as one string, from the document.

    Deterministic: the same document produces the same bytes, and nothing here
    reads the clock, the environment or the filesystem. ``sort_keys`` is on, so
    the embedded JSON does not depend on the order the document's keys happened
    to be built in, and ``allow_nan`` is off, because ``NaN`` is not JSON and a
    page that will not parse is worse than a build that refuses.

    ``<`` is escaped inside the embedded JSON. A ``</script>`` anywhere in the
    agents' own prose would otherwise end the data block early -- and the agents'
    prose is not ours to constrain.
    """
    data = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).replace("<", "\\u003c")

    return "".join(
        [
            "<!DOCTYPE html>\n",
            '<html lang="en">\n<head>\n<meta charset="utf-8">\n',
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n',
            "<title>Tribunal - debate viewer</title>\n",
            "<style>\n",
            _CSS.strip(),
            "\n</style>\n</head>\n<body>\n",
            _BODY.strip(),
            '\n<script id="tribunal-data" type="application/json">',
            data,
            "</script>\n<script>\n",
            _JS.strip(),
            "\n</script>\n</body>\n</html>\n",
        ]
    )


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def _report_refusals(document: Mapping[str, Any]) -> None:
    """Say on the terminal which cases were refused, and why."""
    refused = document.get("refused_cases") or []
    if not refused:
        return
    print("refused {0} case(s):".format(len(refused)))
    for entry in refused:
        print(
            "  case {0}: {1}\n    recorded {2}\n    rebuilt  {3}".format(
                entry["case_no"],
                entry["reason"],
                entry["recorded_brief_sha256"],
                entry["rebuilt_brief_sha256"],
            )
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir", default=str(RUN_DIR), help="the run to replay")
    parser.add_argument("--out", default=str(OUTPUT_PATH), help="where to write the page")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the file on disk with a fresh build and write nothing",
    )
    args = parser.parse_args(argv)

    document = build_document(run_dir=Path(args.run_dir))
    _report_refusals(document)
    page = render_html(document)

    out = Path(args.out)
    if args.check:
        if not out.is_file():
            print("{0} does not exist; run the build".format(out))
            return 1
        committed = out.read_text(encoding="utf-8")
        if committed != page:
            print(
                "{0} differs from a fresh build ({1} bytes on disk, {2} bytes "
                "rebuilt)".format(out, len(committed.encode("utf-8")), len(page.encode("utf-8")))
            )
            return 1
        print("{0} is identical to a fresh build ({1} bytes)".format(out, len(page.encode("utf-8"))))
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(
        "wrote {0}: {1} cases, {2} bytes".format(
            out, len(document["cases"]), len(page.encode("utf-8"))
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
