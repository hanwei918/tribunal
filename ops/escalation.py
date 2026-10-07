"""The escalation packet: what a human reviewer is handed, and nothing else.

The policy says what the packet holds. ``POL-RD-10`` names "the full case
summary, both advocate briefs and the admissibility report"; ``POL-NS-09`` names
"a case summary comprising both advocate briefs, the admissibility pre-pass
report, every clause ID relied on and the Judge's draft reasoning", and says the
Judge "states the escalation trigger and the specific open question the reviewer
must settle". This module builds exactly that, from a run directory, and it adds
three things a reviewer needs and neither clause forbids: the risk signals part 1
computes, the fare lines the money was charged on, and the timeline of the case's
calls.

**The judge's explanation is carried verbatim.** It is where the open question is
stated, so paraphrasing it would replace the question the reviewer has to settle
with this module's reading of it.

**What is never carried, and never read.** The run's event log holds a ``grade``
event per case, carrying the answer key's ``expected`` ruling and whether the
recorded ruling ``matched`` it. Those events are filtered out of the timeline by
name, and no answer key is opened anywhere in this module. The words may still
occur inside the judge's own prose -- "matched" is an ordinary English word in an
explanation about an ERP gantry -- so the rule this module is held to is that no
``expected`` and no ``matched`` **field** reaches a packet, which is the rule
that matters: a field is an answer, and a word in a sentence is a sentence.

**Where the case comes from.** The run directory says which set it belongs to,
through ``eval.development_sets``' own registration, and that set's loader reads
the case: the corpus through its manifest, a second set through its own index.
The case is the pipeline's input, not its output -- the packet is built from the
same public case the brief was built from, so nothing here can be circular.

**The digest.** :func:`packet_sha256` is the SHA-256 of the packet's canonical
JSON, and it is what ``ops.review`` requires before it will record a decision.
It is taken over the JSON rendering whichever ``--format`` is asked for, because
the packet is the JSON document and the Markdown is one rendering of it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from eval import development_sets
from ops import OpsError, OpsWriteError, refuse_a_forbidden_destination, risk
from tribunal import events, loader, money, precedents

# The ruling value a packet is built for.
ESCALATE = "ESCALATE"

# The packet's own schema version, so a reader can tell a later packet from this
# one without guessing from the fields.
PACKET_VERSION = 1

# The formats the command renders.
FORMATS = ("json", "md")

# The two sides, and the transcript role each advocate's claims arrive under.
SIDES: Tuple[Tuple[str, str], ...] = (("RIDER", "RIDER_ADVOCATE"), ("DRIVER", "DRIVER_ADVOCATE"))

# An abstention reason is recorded as ``CODE: detail``. The code is what a reader
# counts; the detail is what they read. A string that is not of that shape is
# kept whole as the code, because a reason that cannot be split is still a
# reason and losing it would be worse than reporting it unsplit.
ABSTENTION_RE = re.compile(r"^([A-Z][A-Z0-9_]*): (.*)$", re.S)

# The artifact whose payload the fare lines are read from.
FARE_EVIDENCE_TYPE = "FARE_BREAKDOWN"

# The referee verdict a claim the referee kept carries.
KEPT = "KEPT"


class EscalationError(OpsError):
    """A packet could not be built, or a destination was refused."""


# --------------------------------------------------------------------------
# Reading the run
# --------------------------------------------------------------------------
def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)
    except FileNotFoundError as exc:
        raise EscalationError("no file at {0}".format(path)) from exc
    except OSError as exc:
        raise EscalationError("{0} cannot be read: {1}".format(path, exc)) from exc
    except ValueError as exc:
        raise EscalationError("invalid JSON in {0}: {1}".format(path, exc)) from exc


def development_set_for(run_dir: Path):
    """Which set a run directory belongs to, read off its path.

    The rule is the registry's own: the path component that follows the last
    ``runs`` segment names a set when it is one of the registered runs
    subdirectories, and everything else is the corpus -- whose run directory is
    ``runs/<model>/`` and carries no component of its own. The registry is read
    rather than restated, so a set added there is one this command can build a
    packet for without being edited.
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


def _case_root(development_set) -> Path:
    """Where a set's cases live, which is where a repeat party would be found."""
    if development_set.case_root is None:
        return Path(loader.CASES_DIR)
    return Path(development_set.case_root)


def _transcript_path(run_dir: Path, document: Mapping[str, Any], case_no: int) -> Path:
    """The case's transcript, by the name the run recorded for it."""
    recorded = document.get("transcript_file")
    if isinstance(recorded, str) and recorded:
        return Path(run_dir) / recorded
    return precedents.transcript_file_for(run_dir, case_no)


# --------------------------------------------------------------------------
# The pieces
# --------------------------------------------------------------------------
def _mentions(text: Any) -> List[str]:
    """Every clause id a piece of prose cites, in the order it cites them."""
    if not isinstance(text, str):
        return []
    return precedents.CLAUSE_MENTION_RE.findall(text)


def _base_clause_ids(clause_ids: Sequence[Any]) -> List[str]:
    """Clause ids with their limbs dropped, sorted and unique.

    A limb (``POL-NS-09(d)``) is a way of citing a clause; the clause the policy
    carries is ``POL-NS-09``, and that is what a reviewer looks up. Anything
    that is not a clause id at all is left as it was written rather than
    silently dropped, so a malformed citation is visible instead of absent.
    """
    found = set()
    for clause_id in clause_ids:
        base = precedents.base_clause_id(clause_id)
        found.add(base if base is not None else str(clause_id))
    return sorted(found)


def _abstention_parts(abstention: Any) -> Tuple[Optional[str], Optional[str]]:
    """An abstention as ``(code, detail)``, either of which may be absent."""
    if not isinstance(abstention, str) or not abstention:
        return None, None
    match = ABSTENTION_RE.match(abstention)
    if match is None:
        return abstention, None
    return match.group(1), match.group(2)


def _parsed_ruling(transcript: Mapping[str, Any], entry_index: Any) -> Optional[Mapping[str, Any]]:
    """The ruling a transcript entry parsed to, or ``None``."""
    entries = transcript.get("entries")
    if not isinstance(entries, list) or not isinstance(entry_index, int):
        return None
    if entry_index < 0 or entry_index >= len(entries):
        return None
    entry = entries[entry_index]
    parsed = entry.get("parsed") if isinstance(entry, Mapping) else None
    ruling = parsed.get("ruling") if isinstance(parsed, Mapping) else None
    return ruling if isinstance(ruling, Mapping) else None


def _draft_ruling(transcript: Mapping[str, Any], draft: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """The last ruling a draft parsed to, so a retried draft is read as it stood."""
    for index in reversed(list(draft.get("entries") or [])):
        ruling = _parsed_ruling(transcript, index)
        if ruling is not None:
            return ruling
    return None


def _advocate_claims(transcript: Mapping[str, Any], role: str) -> List[Mapping[str, Any]]:
    """One advocate's claims, as it parsed them."""
    for entry in transcript.get("entries") or []:
        if not isinstance(entry, Mapping) or entry.get("role") != role:
            continue
        parsed = entry.get("parsed")
        claims = parsed.get("claims") if isinstance(parsed, Mapping) else None
        if isinstance(claims, list):
            return [claim for claim in claims if isinstance(claim, Mapping)]
    return []


def _timeline(run_dir: Path, case_no: int) -> List[Dict[str, Any]]:
    """The case's calls and their outcomes, from the run's event log.

    Every event the log records for the case, in the order it happened, with the
    six things a reader following a case needs: when it happened, what it was,
    which agent or which draft it was, the status the provider returned, what it
    cost in tokens, how long it took and how its answer parsed.

    The ``grade`` event is left out **by name**. It is the one event that carries
    the answer key's expectation and whether the ruling agreed with it, and a
    packet is something a person reads before deciding, so it must not hold the
    answer.
    """
    log = Path(run_dir) / events.EVENTS_FILE
    rows: List[Dict[str, Any]] = []
    for event in events.events_for_case(log, case_no):
        if event.get("event") == events.EVENT_GRADE:
            continue
        who = event.get("role")
        if who is None and event.get("draft") is not None:
            who = "draft {0}".format(event["draft"])
        rows.append(
            {
                "ts": event.get("ts"),
                "event": event.get("event"),
                "role_or_draft": who,
                "status": event.get("status"),
                "tokens": event.get("total_tokens"),
                "seconds": event.get("seconds"),
                "parse_outcome": event.get("parse_outcome"),
            }
        )
    return rows


def _risk_section(case: Mapping[str, Any], policies: Mapping[str, Any], case_root: Path) -> Dict[str, Any]:
    """Part 1's signals, as the packet carries them.

    The signals go to the reviewer and to the queue and never to the judge: they
    are the same five policy tests the judge applies through the policy, read
    again here so that the person who has to settle the case sees which of them
    tripped without having to re-derive them.
    """
    assessment = risk.assess(case, policies, case_root)
    return {
        "signals": [
            {
                "clause": signal.clause,
                "category": signal.category,
                "side": signal.side,
                "fields": {path: value for path, value in signal.fields},
                "threshold": signal.threshold,
                "tripped": signal.tripped,
                "notes": list(signal.notes),
            }
            for signal in assessment.signals
        ],
        "tripped": sorted(signal.clause for signal in assessment.signals if signal.tripped),
        "attention_flags": [
            {
                "flag": risk.REPEAT_PARTY_FLAG,
                "label": risk.REPEAT_PARTY_LABEL,
                "party_role": flag.party_role,
                "party_id": flag.party_id,
                "other_case_no": flag.other_case_no,
                "other_filed_at": flag.other_filed_at,
                "days_apart": flag.days_apart,
            }
            for flag in assessment.attention
        ],
    }


def _fare_lines(case: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """The fare breakdown's lines, as the money was charged on them.

    Every key of the payload, in key order, so two builds are the same build.
    The gantries are a list rather than a figure and travel as one.
    """
    for artifact in case.get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        if artifact.get("evidence_type") != FARE_EVIDENCE_TYPE:
            continue
        payload = artifact.get("payload")
        if not isinstance(payload, Mapping):
            continue
        return [
            {
                "line": key,
                "value": list(payload[key]) if isinstance(payload[key], list) else payload[key],
            }
            for key in sorted(payload)
        ]
    return []


# --------------------------------------------------------------------------
# The packet
# --------------------------------------------------------------------------
def build_packet(
    run_dir: Path, case_no: int, *, any_ruling: bool = False
) -> Dict[str, Any]:
    """The escalation packet for one case of one run.

    Raises :class:`EscalationError` when the case's ruling is not ``ESCALATE``
    and ``any_ruling`` was not asked for, when the run directory holds no result
    for the case, or when the case itself cannot be loaded.
    """
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise EscalationError("no run directory at {0}".format(run_dir))

    case_file = precedents.case_file_for(run_dir, case_no)
    document = _read_json(case_file)
    if not isinstance(document, Mapping):
        raise EscalationError("the case file at {0} is not a JSON object".format(case_file))
    if document.get("case_no") != case_no:
        raise EscalationError(
            "the case file at {0} declares case_no {1!r}".format(
                case_file, document.get("case_no")
            )
        )

    ruling_block = document.get("ruling")
    inner = ruling_block.get("ruling") if isinstance(ruling_block, Mapping) else None
    if not isinstance(inner, Mapping):
        raise EscalationError(
            "the case file at {0} records no ruling to build a packet from".format(case_file)
        )
    ruling_value = inner.get("ruling")
    if ruling_value != ESCALATE and not any_ruling:
        raise EscalationError(
            "case {0} of {1} is {2}, not {3}; a packet is built for an escalated "
            "case, and --any builds one for any case".format(
                case_no, run_dir, ruling_value, ESCALATE
            )
        )

    transcript = _read_json(_transcript_path(run_dir, document, case_no))
    if not isinstance(transcript, Mapping):
        raise EscalationError("the transcript for case {0} is not a JSON object".format(case_no))

    development_set = development_set_for(run_dir)
    try:
        case = development_set.load_case(case_no)
    except loader.LoaderError as exc:
        raise EscalationError(
            "case {0} of the {1} set cannot be loaded: {2}".format(
                case_no, development_set.name, exc
            )
        ) from exc
    case_root = _case_root(development_set)

    configuration = document.get("configuration")
    if not isinstance(configuration, Mapping):
        configuration = {}
    policy_version = configuration.get("policy_version") or development_set.policy_version
    category = case["dispute"]["category"]
    try:
        policies = loader.load_policies(category, policy_version)
    except loader.LoaderError as exc:
        raise EscalationError(
            "the policy for case {0} cannot be loaded: {1}".format(case_no, exc)
        ) from exc

    vote = transcript.get("vote")
    vote = vote if isinstance(vote, Mapping) else {}
    ledger = [
        entry
        for entry in (transcript.get("referee") or {}).get("ledger") or []
        if isinstance(entry, Mapping)
    ]

    # -- 1. The case --------------------------------------------------------
    dispute = case["dispute"]
    packet_case = {
        "case_no": case["case_no"],
        "dispute_id": dispute.get("dispute_id"),
        "category": dispute.get("category"),
        "filed_by": dispute.get("filed_by"),
        "filed_at": dispute.get("filed_at"),
        "channel": dispute.get("channel"),
        "amount_contested_sgd": dispute.get("amount_contested_sgd"),
        "claim_text": dispute.get("claim_text"),
        "counterparty_statement": dispute.get("counterparty_statement"),
    }

    # -- 4. The drafts ------------------------------------------------------
    source_drafts = sorted(
        (draft for draft in vote.get("drafts") or [] if isinstance(draft, Mapping)),
        key=lambda draft: draft.get("draft") or 0,
    )
    drafts: List[Dict[str, Any]] = []
    for draft in source_drafts:
        code, detail = _abstention_parts(draft.get("abstention"))
        parsed = _draft_ruling(transcript, draft)
        drafts.append(
            {
                "draft": draft.get("draft"),
                "proposal": draft.get("proposal"),
                "confidence": parsed.get("confidence") if parsed is not None else None,
                "valid": bool(draft.get("valid")),
                "abstention_code": code,
                "abstention_detail": detail,
                "kind": draft.get("kind"),
                "seed": draft.get("seed"),
                "temperature": draft.get("temperature"),
            }
        )

    # -- 5. Both advocate briefs -------------------------------------------
    briefs: Dict[str, List[Dict[str, Any]]] = {}
    for side, role in SIDES:
        by_text: Dict[Any, Mapping[str, Any]] = {}
        for entry in ledger:
            if entry.get("side") == side:
                by_text.setdefault(entry.get("claim"), entry)
        claims: List[Dict[str, Any]] = []
        for claim in _advocate_claims(transcript, role):
            verdict = by_text.get(claim.get("text"))
            claims.append(
                {
                    "text": claim.get("text"),
                    "evidence_ids": list(claim.get("evidence_ids") or []),
                    "clause_ids": list(claim.get("clause_ids") or []),
                    "verdict": (
                        None
                        if verdict is None
                        else {
                            "status": verdict.get("status"),
                            "reason_code": verdict.get("reason_code"),
                            "detail": verdict.get("detail"),
                        }
                    ),
                }
            )
        briefs[side] = claims

    # -- 6. The admissibility report ---------------------------------------
    admissibility: List[Dict[str, Any]] = []
    for artifact in case.get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        admitted = artifact.get("admissibility")
        admitted = admitted if isinstance(admitted, Mapping) else {}
        admissibility.append(
            {
                "evidence_id": artifact.get("evidence_id"),
                "evidence_type": artifact.get("evidence_type"),
                "source": artifact.get("source"),
                "status": admitted.get("status"),
                "issues": list(admitted.get("issues") or []),
                "weight_multiplier": admitted.get("weight_multiplier"),
                "notes": admitted.get("notes"),
            }
        )

    # -- 7. Every clause id relied on --------------------------------------
    relied: List[Any] = []
    for side, _role in SIDES:
        for claim in briefs[side]:
            verdict = claim["verdict"]
            if verdict is not None and verdict.get("status") == KEPT:
                relied.extend(claim["clause_ids"])
    for draft in source_drafts:
        if not draft.get("valid"):
            continue
        parsed = _draft_ruling(transcript, draft)
        if parsed is None:
            continue
        relied.extend(_mentions(parsed.get("explanation")))
        for referral in parsed.get("referrals") or []:
            relied.extend(_mentions(referral))
    relied.extend(_mentions(inner.get("explanation")))

    # -- 2. The trigger -----------------------------------------------------
    trigger = {
        "outcome": vote.get("outcome"),
        "threshold": vote.get("threshold"),
        "valid": vote.get("valid"),
        "votes": vote.get("votes"),
        "agreement": vote.get("agreement"),
        "unanimous": vote.get("unanimous"),
        "abstentions": [
            {"draft": draft["draft"], "code": draft["abstention_code"]} for draft in drafts
        ],
        "explanation_clause_ids": sorted(set(_mentions(inner.get("explanation")))),
    }

    return {
        "packet_version": PACKET_VERSION,
        "set": development_set.name,
        "case_no": case_no,
        "policy_version": policy_version,
        "case": packet_case,
        "trigger": trigger,
        "explanation": inner.get("explanation"),
        "drafts": drafts,
        "briefs": briefs,
        "admissibility": admissibility,
        "clause_ids": _base_clause_ids(relied),
        "ruling": {
            "ruling": inner.get("ruling"),
            "amount_sgd": inner.get("amount_sgd"),
            "driver_compensation_sgd": inner.get("driver_compensation_sgd"),
            "confidence": inner.get("confidence"),
            "referrals": list(inner.get("referrals") or []),
        },
        "risk": _risk_section(case, policies, case_root),
        "fare_lines": _fare_lines(case),
        "timeline": _timeline(run_dir, case_no),
    }


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def render_json(packet: Mapping[str, Any]) -> str:
    """The packet as its canonical JSON, which is what the digest is taken over."""
    return money.dumps_canonical(dict(packet))


def packet_sha256(packet: Mapping[str, Any]) -> str:
    """The SHA-256 of the packet's canonical JSON."""
    return hashlib.sha256(render_json(packet).encode("utf-8")).hexdigest()


def _cell(value: Any) -> str:
    """One table cell: a value with its newlines and pipes flattened."""
    if value is None:
        return "-"
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return text if text else "-"


def render_md(packet: Mapping[str, Any]) -> str:
    """The packet as Markdown, for a person to read."""
    case = packet["case"]
    lines: List[str] = [
        "# Escalation packet -- case {0} ({1}, {2})".format(
            packet["case_no"], packet["set"], case["category"]
        ),
        "",
        "packet sha256: {0}".format(packet_sha256(packet)),
        "policy version: {0}".format(packet["policy_version"]),
        "",
        "## 1. The case",
        "",
        "| field | value |",
        "|---|---|",
    ]
    for field in (
        "case_no",
        "dispute_id",
        "category",
        "filed_by",
        "filed_at",
        "channel",
        "amount_contested_sgd",
    ):
        lines.append("| {0} | {1} |".format(field, _cell(case.get(field))))
    lines += ["", "### The claim, verbatim", "", case.get("claim_text") or "-"]
    statement = case.get("counterparty_statement") or {}
    lines += [
        "",
        "### The counterparty statement, verbatim",
        "",
        statement.get("text") or "-",
        "",
        "submitted by {0} at {1}".format(
            statement.get("submitted_by"), statement.get("submitted_at")
        ),
        "",
        "## 2. The trigger",
        "",
    ]
    trigger = packet["trigger"]
    for field in ("outcome", "threshold", "valid", "votes", "agreement", "unanimous"):
        lines.append("- {0}: {1}".format(field, _cell(trigger.get(field))))
    lines.append(
        "- abstentions: {0}".format(
            ", ".join(
                "draft {0} {1}".format(item["draft"], item["code"] or "none")
                for item in trigger["abstentions"]
            )
            or "none"
        )
    )
    lines.append(
        "- clause ids the explanation cites: {0}".format(
            ", ".join(trigger["explanation_clause_ids"]) or "none"
        )
    )
    lines += ["", "## 3. The judge's explanation, verbatim", "", packet.get("explanation") or "-"]

    lines += ["", "## 4. The drafts", "", "| draft | ruling | amount | driver | confidence | valid | abstention | kind | seed | temperature |"]
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for draft in packet["drafts"]:
        proposal = draft.get("proposal") or {}
        lines.append(
            "| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} | {9} |".format(
                _cell(draft["draft"]),
                _cell(proposal.get("ruling")),
                _cell(proposal.get("amount_sgd")),
                _cell(proposal.get("driver_compensation_sgd")),
                _cell(draft["confidence"]),
                "valid" if draft["valid"] else "abstained",
                _cell(draft["abstention_code"]),
                _cell(draft["kind"]),
                _cell(draft["seed"]),
                _cell(draft["temperature"]),
            )
        )

    lines += ["", "## 5. Both advocate briefs", ""]
    for side, _role in SIDES:
        lines += ["### {0}".format(side), ""]
        for index, claim in enumerate(packet["briefs"][side], start=1):
            verdict = claim.get("verdict") or {}
            if verdict.get("status") == KEPT:
                outcome = "KEPT -- {0}".format(verdict.get("detail"))
            elif verdict:
                outcome = "{0} ({1}) -- {2}".format(
                    verdict.get("status"), verdict.get("reason_code"), verdict.get("detail")
                )
            else:
                outcome = "no referee verdict recorded"
            lines += [
                "{0}. {1}".format(index, claim.get("text") or "-"),
                "",
                "   evidence: {0}".format(", ".join(claim["evidence_ids"]) or "none"),
                "   clauses: {0}".format(", ".join(claim["clause_ids"]) or "none"),
                "   verdict: {0}".format(outcome),
                "",
            ]

    lines += ["", "## 6. The admissibility report", "", "| artifact | type | source | status | weight | issues | notes |"]
    lines.append("|---|---|---|---|---|---|---|")
    for artifact in packet["admissibility"]:
        lines.append(
            "| {0} | {1} | {2} | {3} | {4} | {5} | {6} |".format(
                _cell(artifact["evidence_id"]),
                _cell(artifact["evidence_type"]),
                _cell(artifact["source"]),
                _cell(artifact["status"]),
                _cell(artifact["weight_multiplier"]),
                _cell(", ".join(artifact["issues"])),
                _cell(artifact["notes"]),
            )
        )

    lines += [
        "",
        "## 7. Every clause id relied on",
        "",
        ", ".join(packet["clause_ids"]) or "none",
        "",
        "## 8. Referrals and directives",
        "",
    ]
    for referral in packet["ruling"]["referrals"] or ["none"]:
        lines.append("- {0}".format(referral))

    lines += ["", "## 9. Risk signals", ""]
    for signal in packet["risk"]["signals"]:
        lines.append(
            "- {0} ({1}) side {2} tripped={3}".format(
                signal["clause"], signal["category"], signal["side"],
                "true" if signal["tripped"] else "false",
            )
        )
        lines.append(
            "  - fields: {0}".format(
                ", ".join(
                    "{0}={1}".format(name, value)
                    for name, value in sorted(signal["fields"].items())
                )
            )
        )
        lines.append("  - threshold: {0}".format(signal["threshold"]))
        for note in signal["notes"]:
            lines.append("  - note: {0}".format(note))
    flags = packet["risk"]["attention_flags"]
    lines.append(
        "- {0}: {1}".format(
            risk.REPEAT_PARTY_FLAG,
            "; ".join(
                "{0} {1} also in case {2}".format(flag["party_role"], flag["party_id"], flag["other_case_no"])
                for flag in flags
            )
            or "none",
        )
    )

    lines += ["", "## 10. The fare lines", "", "| line | value |", "|---|---|"]
    for line in packet["fare_lines"]:
        lines.append("| {0} | {1} |".format(_cell(line["line"]), _cell(line["value"])))

    lines += ["", "## 11. The timeline", "", "| time | event | role or draft | status | tokens | seconds | parse |"]
    lines.append("|---|---|---|---|---|---|---|")
    for row in packet["timeline"]:
        lines.append(
            "| {0} | {1} | {2} | {3} | {4} | {5} | {6} |".format(
                _cell(row["ts"]),
                _cell(row["event"]),
                _cell(row["role_or_draft"]),
                _cell(row["status"]),
                _cell(row["tokens"]),
                _cell(row["seconds"]),
                _cell(row["parse_outcome"]),
            )
        )
    return "\n".join(lines) + "\n"


def render(packet: Mapping[str, Any], fmt: str) -> str:
    """One packet in the format asked for."""
    if fmt == "json":
        return render_json(packet) + "\n"
    if fmt == "md":
        return render_md(packet)
    raise EscalationError(
        "unknown format {0!r}; the formats are {1}".format(fmt, ", ".join(FORMATS))
    )


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    """Build one escalation packet and print it, or write it with ``--out``."""
    parser = argparse.ArgumentParser(
        prog="python -m ops.escalation",
        description=(
            "Build the escalation packet for one case of one run: the case, the "
            "trigger, the judge's explanation, the drafts, both advocate briefs, "
            "the admissibility report, every clause id relied on, the referrals, "
            "part 1's risk signals, the fare lines and the timeline. Makes no "
            "model call and reads no answer key."
        ),
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="the run directory")
    parser.add_argument("--case", type=int, required=True, help="the case number")
    parser.add_argument("--format", choices=FORMATS, default="json", help="json or md")
    parser.add_argument("--out", type=Path, default=None, help="write the packet here")
    parser.add_argument(
        "--any",
        action="store_true",
        help="build a packet for a case that did not escalate",
    )
    args = parser.parse_args(argv)

    try:
        packet = build_packet(args.run_dir, args.case, any_ruling=args.any)
    except EscalationError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1

    # The destination is the caller's to name, so it is refused before anything
    # is written. The rule is the layer's, in :mod:`ops`.
    if args.out is not None:
        try:
            out = refuse_a_forbidden_destination(args.out)
        except OpsWriteError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(packet, args.format), encoding="utf-8")
        print("wrote {0}".format(out), file=sys.stderr)
    else:
        sys.stdout.write(render(packet, args.format))

    # The digest is what ops.review requires before it will record a decision,
    # so it is printed whichever rendering was asked for: it is taken over the
    # packet's JSON, which is the document a reviewer read.
    print("packet sha256: {0}".format(packet_sha256(packet)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
