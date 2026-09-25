"""Deterministic mechanical citation referee.

The referee is deliberately narrower than the judge. It checks only the facts
that code can check from the loaded brief: citation presence and resolution,
impairment disclosure, and profile fields that the general policy makes
context-only. It never decides the merits of a claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from . import money

SIDE_RIDER = "RIDER"
SIDE_DRIVER = "DRIVER"
STATUS_KEPT = "KEPT"
STATUS_DISCARDED = "DISCARDED"
REASON_KEPT = "KEPT"
NO_EVIDENCE_ID = "NO_EVIDENCE_ID"
NO_CLAUSE_ID = "NO_CLAUSE_ID"
EVIDENCE_UNRESOLVED = "EVIDENCE_UNRESOLVED"
CLAUSE_UNRESOLVED = "CLAUSE_UNRESOLVED"
IMPAIRMENT_UNDISCLOSED = "IMPAIRMENT_UNDISCLOSED"
PROFILE_FIELD_AS_GROUND = "PROFILE_FIELD_AS_GROUND"

REASON_CODES = (
    REASON_KEPT,
    NO_EVIDENCE_ID,
    NO_CLAUSE_ID,
    EVIDENCE_UNRESOLVED,
    CLAUSE_UNRESOLVED,
    IMPAIRMENT_UNDISCLOSED,
    PROFILE_FIELD_AS_GROUND,
)
CLAUSE_ID_RE = re.compile(r"^POL-[A-Z]{2,4}-\d{2}$")
_CONTEXT_FIELDS_RE = re.compile(
    r"Every other field on either profile\s*-\s*(.*?)\s*-\s*is CONTEXT ONLY\.",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class RefereeResult:
    """The complete, deterministic ledger and the inputs for the judge."""

    ledger: Tuple[Dict[str, Any], ...]
    kept_claims: Dict[str, Tuple[Mapping[str, Any], ...]]
    discards: Tuple[Dict[str, Any], ...]
    flags: Tuple[Dict[str, Any], ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ledger": [dict(entry) for entry in self.ledger],
            "discards": [dict(entry) for entry in self.discards],
            "flags": [dict(entry) for entry in self.flags],
        }


def _policy_clauses(brief: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    policies = brief.get("policies")
    if not isinstance(policies, Mapping):
        return {}
    clauses: Dict[str, Mapping[str, Any]] = {}
    for policy in policies.values():
        if not isinstance(policy, Mapping):
            continue
        for clause in policy.get("clauses", []) or []:
            if isinstance(clause, Mapping) and isinstance(clause.get("id"), str):
                clauses[clause["id"]] = clause
    return clauses


def _general_clause(brief: Mapping[str, Any], clause_id: str) -> Mapping[str, Any]:
    policies = brief.get("policies")
    if not isinstance(policies, Mapping):
        return {}
    general = policies.get("general")
    if not isinstance(general, Mapping):
        return {}
    for clause in general.get("clauses", []) or []:
        if isinstance(clause, Mapping) and clause.get("id") == clause_id:
            return clause
    return {}


def context_only_profile_fields(brief: Mapping[str, Any]) -> Tuple[str, ...]:
    """Read POL-GEN-01's context-only field list from its rule text.

    The list is intentionally not duplicated in this module. A policy edit that
    changes the list therefore changes the referee's behaviour from the loaded
    text, and the tests can assert that the parser still agrees with the clause.
    """
    clause = _general_clause(brief, "POL-GEN-01")
    rule = clause.get("rule") if isinstance(clause, Mapping) else None
    if not isinstance(rule, str):
        raise ValueError("POL-GEN-01 is missing or has no rule text")
    match = _CONTEXT_FIELDS_RE.search(rule)
    if match is None:
        raise ValueError("POL-GEN-01 does not state its context-only profile fields")
    fields = tuple(item.strip() for item in match.group(1).split(",") if item.strip())
    if not fields:
        raise ValueError("POL-GEN-01 states no context-only profile fields")
    return fields


def _profile_field_mentions(value: Any, fields: Sequence[str]) -> Tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    found: List[str] = []
    for field in fields:
        if re.search(r"(?:rider_profile|driver_profile)\." + re.escape(field) + r"\b", value):
            found.append(field)
        elif re.search(r"(?:^|[., /])" + re.escape(field) + r"(?:$|[., /])", value):
            found.append(field)
    return tuple(found)


def _as_decimal(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _evidence_index(brief: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    case = brief.get("case")
    evidence = case.get("evidence", []) if isinstance(case, Mapping) else []
    return {
        artifact.get("evidence_id"): artifact
        for artifact in evidence
        if isinstance(artifact, Mapping) and isinstance(artifact.get("evidence_id"), str)
    }


def _issue_codes(artifact: Mapping[str, Any]) -> Tuple[str, ...]:
    admissibility = artifact.get("admissibility")
    if not isinstance(admissibility, Mapping):
        return ()
    codes = [item for item in admissibility.get("issues", []) or [] if isinstance(item, str)]
    if codes:
        return tuple(codes)
    details = admissibility.get("issue_details", []) or []
    return tuple(
        item.get("code")
        for item in details
        if isinstance(item, Mapping) and isinstance(item.get("code"), str)
    )


def _claim_text(claim: Mapping[str, Any]) -> str:
    text = claim.get("text")
    return text if isinstance(text, str) else ""


def _entry(
    side: str,
    claim: Mapping[str, Any],
    status: str,
    reason_code: str,
    detail: str,
    flags: Sequence[str] = (),
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "side": side,
        "claim": _claim_text(claim),
        "status": status,
        "reason_code": reason_code,
        "detail": detail,
    }
    if flags:
        result["flags"] = list(flags)
    return result


def _check_claim(
    brief: Mapping[str, Any],
    side: str,
    claim: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
    clauses: Mapping[str, Mapping[str, Any]],
    context_fields: Sequence[str],
) -> Tuple[Dict[str, Any], bool]:
    evidence_ids = claim.get("evidence_ids")
    if evidence_ids is None and claim.get("evidence_id") is not None:
        evidence_ids = [claim.get("evidence_id")]
    if not isinstance(evidence_ids, list) or not evidence_ids:
        return (
            _entry(
                side,
                claim,
                STATUS_DISCARDED,
                NO_EVIDENCE_ID,
                "the claim has no evidence_ids",
            ),
            False,
        )

    clause_ids = claim.get("clause_ids")
    if clause_ids is None and claim.get("clause_id") is not None:
        clause_ids = [claim.get("clause_id")]
    if not isinstance(clause_ids, list) or not clause_ids:
        return (
            _entry(
                side,
                claim,
                STATUS_DISCARDED,
                NO_CLAUSE_ID,
                "the claim has no clause_ids",
            ),
            False,
        )

    unresolved_evidence = [item for item in evidence_ids if item not in evidence]
    if unresolved_evidence:
        return (
            _entry(
                side,
                claim,
                STATUS_DISCARDED,
                EVIDENCE_UNRESOLVED,
                "evidence_ids do not resolve in this case: {0}".format(
                    ", ".join(str(item) for item in unresolved_evidence)
                ),
            ),
            False,
        )

    malformed_or_unresolved = [
        item
        for item in clause_ids
        if not isinstance(item, str) or CLAUSE_ID_RE.fullmatch(item) is None or item not in clauses
    ]
    if malformed_or_unresolved:
        return (
            _entry(
                side,
                claim,
                STATUS_DISCARDED,
                CLAUSE_UNRESOLVED,
                "clause_ids are malformed or do not resolve in the loaded policy: {0}".format(
                    ", ".join(str(item) for item in malformed_or_unresolved)
                ),
            ),
            False,
        )

    text_lower = _claim_text(claim).lower()
    for evidence_id in evidence_ids:
        artifact = evidence[evidence_id]
        admissibility = artifact.get("admissibility")
        weight = admissibility.get("weight_multiplier") if isinstance(admissibility, Mapping) else None
        decimal_weight = _as_decimal(weight)
        if decimal_weight is not None and decimal_weight < Decimal("1"):
            codes = _issue_codes(artifact)
            disclosed_codes = [code for code in codes if code.lower() in text_lower]
            if codes and not disclosed_codes:
                return (
                    _entry(
                        side,
                        claim,
                        STATUS_DISCARDED,
                        IMPAIRMENT_UNDISCLOSED,
                        "the claim cites impaired artifact {0} at weight_multiplier {1} but does not "
                        "name its issue code(s): {2}".format(
                            evidence_id,
                            weight,
                            ", ".join(codes),
                        ),
                    ),
                    False,
                )

    relied_fields = _profile_field_mentions(claim.get("relies_on"), context_fields)
    if relied_fields:
        return (
            _entry(
                side,
                claim,
                STATUS_DISCARDED,
                PROFILE_FIELD_AS_GROUND,
                "relies_on names context-only profile field(s): {0}; POL-GEN-01 permits "
                "profile context but not a ground of decision".format(
                    ", ".join(relied_fields)
                ),
            ),
            False,
        )

    mentioned_fields = _profile_field_mentions(_claim_text(claim), context_fields)
    flags = tuple(
        "context-only profile field mentioned in claim text: {0}".format(field)
        for field in mentioned_fields
    )
    return (
        _entry(
            side,
            claim,
            STATUS_KEPT,
            REASON_KEPT,
            "all mechanical referee checks passed",
            flags=flags,
        ),
        True,
    )


def run(
    brief: Mapping[str, Any],
    rider_claims: Sequence[Mapping[str, Any]],
    driver_claims: Sequence[Mapping[str, Any]],
) -> RefereeResult:
    """Run the mechanical checks in a fixed order over both claim arrays."""
    evidence = _evidence_index(brief)
    clauses = _policy_clauses(brief)
    context_fields = context_only_profile_fields(brief)
    ledger: List[Dict[str, Any]] = []
    discards: List[Dict[str, Any]] = []
    flags: List[Dict[str, Any]] = []
    kept: Dict[str, Tuple[Mapping[str, Any], ...]] = {}

    for side, claims in ((SIDE_RIDER, rider_claims), (SIDE_DRIVER, driver_claims)):
        kept_for_side: List[Mapping[str, Any]] = []
        for claim in claims:
            if not isinstance(claim, Mapping):
                claim = {}
            entry, is_kept = _check_claim(
                brief, side, claim, evidence, clauses, context_fields
            )
            ledger.append(entry)
            if is_kept:
                kept_for_side.append(claim)
                if entry.get("flags"):
                    flags.append(
                        {
                            "side": side,
                            "claim": entry["claim"],
                            "flags": list(entry["flags"]),
                        }
                    )
            else:
                discards.append(
                    {
                        "side": entry["side"],
                        "claim": entry["claim"],
                        "reason_code": entry["reason_code"],
                        "detail": entry["detail"],
                    }
                )
        kept[side] = tuple(kept_for_side)

    return RefereeResult(
        ledger=tuple(ledger),
        kept_claims=kept,
        discards=tuple(discards),
        flags=tuple(flags),
    )


def referee(
    brief: Mapping[str, Any],
    rider_claims: Sequence[Mapping[str, Any]],
    driver_claims: Sequence[Mapping[str, Any]],
) -> RefereeResult:
    """Named entry point used by the pipeline and no-model audits."""
    return run(brief, rider_claims, driver_claims)
