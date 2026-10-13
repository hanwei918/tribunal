"""Build a "try it" scenario from a recorded case, and show what plain code makes of it.

This module is shared by the live-run server (``tryit/server.py``) and the
website, which runs it in the visitor's browser with Pyodide. Both therefore
build exactly the same case from the same edits, and the browser shows exactly
what the server would hand the pipeline.

A scenario is always one of four recorded cases with a few things changed. The
evidence a visitor cannot sensibly invent -- the GPS trace, the fare lines, the
profiles -- stays as recorded; what can be changed is what a person would say or
type, the platform's safety flag, and whether the GPS trace or the chat log is
missing. Nothing here calls a model.

Standard library only, like the rest of the repository.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent

# The four recorded cases a scenario can start from.
TEMPLATES: Dict[int, str] = {
    208: "data/cases/case-00208.json",            # no-show, both sides argue
    901: "data/external/ryde-v3/case-00901.json",  # the organisers' sample
    103: "data/cases/case-00103.json",            # route deviation, ERP gantries
    1779: "data/external/dev-v2/case-01779.json",  # a planted "policy update"
}

# The policy version every recorded version-6 run used.
POLICY_VERSION = 6

# What a visitor may send. Anything longer is refused, not cut.
MAX_STATEMENT_CHARS = 1500
MAX_MESSAGE_CHARS = 400
MAX_MESSAGES = 14
SENDERS = ("RIDER", "DRIVER")
REMOVABLE = ("GPS_TRACE", "CHAT_LOG")

# The dispute fields POL-GEN-08(1) gates on (tribunal/pipeline.py SCOPE_GATE_FLAGS).
# Copied rather than imported so the browser need not load the model client.
SCOPE_GATE_FLAGS = ("safety_flag", "complaint_flag")

REMOVED_NOTE = "Removed on the try-it page: this scenario has no such artifact."


class ScenarioError(ValueError):
    """The edits cannot be applied; the message says why, in plain words."""


def load_template(case_no: int) -> Dict[str, Any]:
    if case_no not in TEMPLATES:
        raise ScenarioError("unknown template {0!r}; choose one of {1}".format(case_no, sorted(TEMPLATES)))
    with open(ROOT / TEMPLATES[case_no], encoding="utf-8") as handle:
        return json.load(handle)


def _text(value: Any, limit: int, what: str) -> str:
    if not isinstance(value, str):
        raise ScenarioError("{0} must be text".format(what))
    value = value.replace("\r\n", "\n").strip()
    if len(value) > limit:
        raise ScenarioError("{0} is {1} characters; the limit is {2}".format(what, len(value), limit))
    return value


def normalise_edits(edits: Any) -> Dict[str, Any]:
    """Check a visitor's edits and return them in one canonical shape."""
    if not isinstance(edits, dict):
        raise ScenarioError("the scenario must be a JSON object")
    try:
        template = int(edits.get("template"))
    except (TypeError, ValueError):
        raise ScenarioError("choose a starting case")
    if template not in TEMPLATES:
        raise ScenarioError("unknown starting case {0}".format(template))
    out: Dict[str, Any] = {"template": template}
    if "claim_text" in edits:
        out["claim_text"] = _text(edits["claim_text"], MAX_STATEMENT_CHARS, "the complaint")
        if not out["claim_text"]:
            raise ScenarioError("the complaint cannot be empty")
    if "counterparty_text" in edits:
        out["counterparty_text"] = _text(edits["counterparty_text"], MAX_STATEMENT_CHARS, "the other side's statement")
    if "messages" in edits:
        messages = edits["messages"]
        if not isinstance(messages, list):
            raise ScenarioError("the chat must be a list of messages")
        if len(messages) > MAX_MESSAGES:
            raise ScenarioError("the chat has {0} messages; the limit is {1}".format(len(messages), MAX_MESSAGES))
        clean = []
        for index, message in enumerate(messages, 1):
            if not isinstance(message, dict):
                raise ScenarioError("chat message {0} is not an object".format(index))
            msg_id = message.get("msg_id")
            sender = message.get("sender")
            text = _text(message.get("text", ""), MAX_MESSAGE_CHARS, "chat message {0}".format(index))
            if msg_id is not None and not isinstance(msg_id, str):
                raise ScenarioError("chat message {0} has a bad id".format(index))
            if msg_id is None and sender not in SENDERS:
                raise ScenarioError("a new chat message must come from the rider or the driver")
            clean.append({"msg_id": msg_id, "sender": sender, "text": text})
        out["messages"] = clean
    if "safety_flag" in edits:
        if not isinstance(edits["safety_flag"], bool):
            raise ScenarioError("the safety flag is yes or no")
        out["safety_flag"] = edits["safety_flag"]
    if "missing" in edits:
        missing = edits["missing"]
        if not isinstance(missing, list) or any(m not in REMOVABLE for m in missing):
            raise ScenarioError("only the GPS trace or the chat log can be removed")
        out["missing"] = sorted(set(missing))
    return out


def _stamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def build_case(edits: Any) -> Dict[str, Any]:
    """The recorded case with the visitor's edits applied. The template is not modified."""
    edits = normalise_edits(edits)
    case = copy.deepcopy(load_template(edits["template"]))
    dispute = case["dispute"]
    if "claim_text" in edits:
        dispute["claim_text"] = edits["claim_text"]
    if "counterparty_text" in edits:
        text = edits["counterparty_text"]
        statement = dispute.get("counterparty_statement")
        if text:
            if not isinstance(statement, dict):
                # The filing party's opponent writes it, a day after the filing.
                other = "DRIVER" if dispute.get("filed_by") == "RIDER" else "RIDER"
                statement = {"submitted_by": other,
                             "submitted_at": _iso(_stamp(dispute["filed_at"]) + timedelta(hours=18))}
            statement = dict(statement, text=text)
            dispute["counterparty_statement"] = statement
        else:
            dispute.pop("counterparty_statement", None)
    if "safety_flag" in edits:
        dispute["safety_flag"] = edits["safety_flag"]
        dispute.setdefault("complaint_flag", False)

    by_type = {artifact["evidence_type"]: artifact for artifact in case["evidence"]}
    chat = by_type.get("CHAT_LOG")
    if "messages" in edits and chat is not None and isinstance(chat.get("payload"), dict):
        _apply_messages(case, chat, edits["messages"])

    for evidence_type in edits.get("missing", []):
        artifact = by_type.get(evidence_type)
        if artifact is None:
            continue
        artifact["payload"] = None
        artifact["admissibility"] = dict(
            artifact.get("admissibility") or {},
            status="MISSING",
            issues=["MISSING_ARTIFACT"],
            issue_details=[{"code": "MISSING_ARTIFACT", "severity": "BLOCKING", "detail": REMOVED_NOTE}],
            weight_multiplier=0.0,
            notes=REMOVED_NOTE,
        )
        if evidence_type == "CHAT_LOG":
            _set_message_count(case, 0)
    return case


def _apply_messages(case: Dict[str, Any], chat: Dict[str, Any], wanted: List[Dict[str, Any]]) -> None:
    """Edit, drop or append chat messages, keeping the recorded timing for the recorded ones.

    A recorded message keeps its sender, its times and its id; only its text can
    change, and an empty text drops it. System lines are the app's own and are
    always kept as recorded. A new message is placed 30 seconds after the
    message before it, delivered at once and read 15 seconds later.
    """
    payload = chat["payload"]
    recorded = {m["msg_id"]: m for m in payload.get("messages", [])}
    system = [m for m in payload.get("messages", []) if m.get("sender") == "SYSTEM"]
    seen = set()
    kept: List[Dict[str, Any]] = []
    for item in wanted:
        if item["msg_id"] is not None:
            original = recorded.get(item["msg_id"])
            if original is None or original.get("sender") == "SYSTEM":
                raise ScenarioError("chat message {0} is not one of this case's messages".format(item["msg_id"]))
            seen.add(item["msg_id"])
            if item["text"]:
                kept.append(dict(original, text=item["text"]))
        elif item["text"]:
            kept.append({"msg_id": None, "sender": item["sender"], "text": item["text"]})
    for msg_id, original in recorded.items():
        if original.get("sender") != "SYSTEM" and msg_id not in seen:
            kept.append(original)  # not mentioned: unchanged
    # Order: recorded messages by their own time, new ones after the message before them.
    timeline: List[Dict[str, Any]] = []
    for message in system + [m for m in kept if m["msg_id"] is not None]:
        timeline.append(message)
    timeline.sort(key=lambda m: m["sent_at"])
    new_ones = [m for m in kept if m["msg_id"] is None]
    last = _stamp(timeline[-1]["sent_at"]) if timeline else _stamp(case["dispute"]["filed_at"]) - timedelta(minutes=30)
    trip = str(case["dispute"]["case_no"]).zfill(5)
    for number, message in enumerate(new_ones, 1):
        last = last + timedelta(seconds=30)
        timeline.append({
            "msg_id": "MSG-{0}-T{1:02d}".format(trip, number),
            "sender": message["sender"],
            "text": message["text"],
            "sent_at": _iso(last),
            "read_at": _iso(last + timedelta(seconds=15)),
            "delivered_at": _iso(last),
            "channel": "IN_APP",
            "language": "en",
            "redacted": False,
            "waypoint_hint": None,
        })
    payload["messages"] = timeline
    _set_message_count(case, len(timeline))


def _set_message_count(case: Dict[str, Any], count: int) -> None:
    for artifact in case["evidence"]:
        if artifact["evidence_type"] == "TRIP_RECORD" and isinstance(artifact.get("payload"), dict):
            if "chat_message_count" in artifact["payload"]:
                artifact["payload"]["chat_message_count"] = count


# ---------------------------------------------------------------------------
# What plain code makes of a scenario, before any model is asked
# ---------------------------------------------------------------------------
def _flatten(node: Any, path: str, out: Dict[str, Any]) -> None:
    if isinstance(node, dict):
        if "value" in node and "evidence_id" in node:
            out[path] = {"value": _plain(node["value"]), "evidence_id": node["evidence_id"]}
            return
        for key, value in node.items():
            _flatten(value, path + "." + key if path else key, out)
    elif isinstance(node, list):
        for index, value in enumerate(node[:6]):
            _flatten(value, "{0}[{1}]".format(path, index), out)


def _plain(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _chat_signals():
    """``ops/chat_signals.py``, the queue's own threat detector.

    Imported through the ``ops`` package when it can be. The package's
    ``__init__`` also imports the evaluation harness, which the browser does not
    carry, so there the same file is loaded on its own -- it uses the standard
    library only.
    """
    try:
        from ops import chat_signals
        return chat_signals
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location("ops_chat_signals", ROOT / "ops" / "chat_signals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def code_view(case: Dict[str, Any]) -> Dict[str, Any]:
    """Everything the deterministic code works out, as plain JSON."""
    from tribunal import brief as brief_module
    chat_signals = _chat_signals()

    built = brief_module.build_brief_for_case(case, policy_version=POLICY_VERSION)
    _, digest = brief_module.brief_digest(built)
    briefed = built["case"]
    dispute = briefed["dispute"]
    original_dispute = case["dispute"]

    flags = [flag for flag in SCOPE_GATE_FLAGS if original_dispute.get(flag) is True]

    messages = []
    chat_payload = None
    for artifact in briefed["evidence"]:
        if artifact["evidence_type"] == "CHAT_LOG":
            chat_payload = artifact.get("payload")
    raw_chat = None
    for artifact in case["evidence"]:
        if artifact["evidence_type"] == "CHAT_LOG":
            raw_chat = artifact.get("payload")
    if isinstance(chat_payload, dict):
        raw_by_id = {m["msg_id"]: m for m in (raw_chat or {}).get("messages", [])}
        for message in chat_payload.get("messages", []):
            raw = raw_by_id.get(message["msg_id"], {})
            signal = chat_signals.detect(raw.get("text", message.get("text", "")))
            messages.append({
                "msg_id": message["msg_id"],
                "sender": message.get("sender"),
                "sent_at": message.get("sent_at"),
                "text": raw.get("text", message.get("text")),
                "masked": message.get("text"),
                "threat": bool(signal.get("threat")),
                "matched": list(signal.get("matched", [])),
            })

    evidence = []
    facts: Dict[str, Any] = {}
    for artifact in briefed["evidence"]:
        admissibility = artifact.get("admissibility") or {}
        evidence.append({
            "evidence_id": artifact["evidence_id"],
            "type": artifact["evidence_type"],
            "status": admissibility.get("status"),
            "weight": _plain(admissibility.get("weight_multiplier")),
            "issues": list(admissibility.get("issues") or []),
        })
        payload = artifact.get("payload")
        if isinstance(payload, dict) and isinstance(payload.get("derived"), dict):
            _flatten(payload["derived"], artifact["evidence_type"], facts)

    statement = original_dispute.get("counterparty_statement") or {}
    masked_statement = (dispute.get("counterparty_statement") or {})
    return {
        "case_no": case["case_no"] if "case_no" in case else original_dispute.get("case_no"),
        "category": original_dispute.get("category"),
        "filed_by": original_dispute.get("filed_by"),
        "amount_contested_sgd": _plain(original_dispute.get("amount_contested_sgd")),
        "claim_text": original_dispute.get("claim_text"),
        "claim_masked": dispute.get("claim_text"),
        "counterparty_text": statement.get("text", ""),
        "counterparty_masked": masked_statement.get("text", ""),
        "messages": messages,
        "threat_in_chat": any(m["threat"] for m in messages),
        "scope_gate": {"flags": flags, "to_person": bool(flags)},
        "evidence": evidence,
        "facts": facts,
        "brief_sha256": digest,
        "model_calls": 0 if flags else 6,
    }


def view_for(edits: Any) -> Dict[str, Any]:
    """The browser's single entry point: edits in, code view out (both JSON)."""
    if isinstance(edits, str):
        edits = json.loads(edits)
    return code_view(build_case(edits))


def template_summaries() -> List[Dict[str, Any]]:
    """What the page needs to show each starting case before any edit."""
    out = []
    for case_no in TEMPLATES:
        case = load_template(case_no)
        dispute = case["dispute"]
        chat = next((a for a in case["evidence"] if a["evidence_type"] == "CHAT_LOG"), None)
        out.append({
            "case_no": case_no,
            "category": dispute["category"],
            "filed_by": dispute.get("filed_by"),
            "claim_text": dispute["claim_text"],
            "counterparty_text": (dispute.get("counterparty_statement") or {}).get("text", ""),
            "safety_flag": dispute.get("safety_flag") is True,
            "messages": [
                {"msg_id": m["msg_id"], "sender": m["sender"], "text": m["text"], "sent_at": m["sent_at"]}
                for m in ((chat or {}).get("payload") or {}).get("messages", [])
            ],
        })
    return out
