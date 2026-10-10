"""A read-only WorkBuddy connector over Tribunal's committed records.

What it is
----------
WorkBuddy's connectors are MCP servers started over standard input and output.
This is one: a JSON-RPC 2.0 server, one JSON object per line, that answers the
questions a support agent working in WorkBuddy would ask about the Tribunal
record -- "how was case 901 decided?", "what is waiting for a reviewer?", "what
is in the escalation packet for case 213?".

It is **read-only**. Every answer is computed from files already committed to
this repository: the version-6 runs under ``runs/``, the three functional
sets' runs, the public case files those runs were made from, the loaded policy,
and the two operations commands the layer already ships (``ops.queue`` and
``ops.escalation``, each run as a subprocess). It opens no answer key: nothing
under ``eval/answers/`` is read, and the sealed sets -- ``wild``, ``wild-v2``
and ``sealed-v1`` -- are refused by name and never read at all.

The run's own ``matched`` field and its ``grade`` event are the run's verdict
against the answer key. They are read by nobody here and surfaced by nothing
here: a connector a support agent talks to answers about the case, not about
whether the case agreed with a key.

It makes no model call, opens no socket and launches no browser.

The sets offered
----------------
The four committed version-6 runs and the three functional case sets. That list
is built from ``eval.v6_runs.RUNS`` and ``eval.func_sets.FUNCTIONAL_SET_NAMES``
rather than typed here, so a set added to either registry is offered without
this file being edited, and a set the registries call sealed is refused before
any path is resolved.

The reading
-----------
The case is read the way the product view reads one. The reading functions are
``ui/v2/build.py``'s own -- its JSON reader, its transcript lookup, its ruling
unwrapper, its policy loader and its trigger reading -- so the connector
answers from the same reading the queue page is drawn from, and the rebuild of
the brief is held to the digest the run recorded exactly as the page holds it.
Its ``_load_case`` is not called: that resolves the run through
``eval.v6_runs``, which knows the four version-6 runs and not the functional
sets, and this connector offers both.

The protocol
------------
One JSON object per line on standard input; one JSON object per line on
standard output. ``initialize`` answers with ``serverInfo`` and the ``tools``
capability, ``tools/list`` names the three tools, and ``tools/call`` runs one.
An unknown method answers with a JSON-RPC error. A notification -- a request
with no ``id`` -- is never answered, as the protocol requires. Standard error
is for logs; standard output carries protocol messages and nothing else.

Run it with::

    printf '%s\\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
        | python3 integrations/workbuddy/tribunal_mcp_server.py
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets  # noqa: E402
from eval import func_sets  # noqa: E402
from eval import v6_runs  # noqa: E402
from tribunal import brief as brief_module  # noqa: E402
from ui.v2 import build as view  # noqa: E402

# --------------------------------------------------------------------------
# The protocol's own constants
# --------------------------------------------------------------------------
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "tribunal"
SERVER_VERSION = "1.0.0"

# The JSON-RPC 2.0 error codes this server uses.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# --------------------------------------------------------------------------
# The sets, and the vocabulary of the queue
# --------------------------------------------------------------------------
# The four version-6 runs, by the name ``eval.v6_runs`` registers them.
V6_RUN_NAMES = frozenset(run.name for run in v6_runs.RUNS)

# The sets this connector offers: the committed version-6 runs in the order
# their registry lists them, then the three functional case sets in theirs.
# The list is read from the registries, not typed, so it cannot come to offer
# a set that does not exist or to omit one that does.
OFFERED_SETS: Tuple[str, ...] = tuple(
    run.name for run in v6_runs.RUNS
) + tuple(func_sets.FUNCTIONAL_SET_NAMES)

# The sets the registries call sealed. A request naming one is refused by name,
# before any run directory is resolved, so no sealed case is ever opened.
SEALED_SET_NAMES = frozenset(
    development_set.name for development_set in development_sets.SEALED_SETS
)

# The three lanes the operations layer routes into, in its own order, and the
# one this connector lists case by case. They are the values ``ops.queue``
# prints in its lane column; they are named here so the counts read in a fixed
# order even when a lane holds no case.
LANES: Tuple[str, ...] = ("SAFETY_FAST_TRACK", "HUMAN_REVIEW", "AUTO")
HUMAN_LANE = "HUMAN_REVIEW"

# The eleven columns ``ops.queue`` prints, in its own order. The parser reads
# the command's table by these names rather than by position, so a column added
# to the command is a refusal here rather than a silent misreading.
QUEUE_COLUMNS: Tuple[str, ...] = (
    "tier",
    "case",
    "category",
    "lane",
    "reasons",
    "amount",
    "filed_at",
    "due_at",
    "status",
    "review_due_at",
    "review_status",
)

# The interpreter the two operations commands are run with. It is the
# interpreter running this server, so the reading and the answer cannot come
# from two different Pythons -- the rule ``eval/func_sets.py`` follows for the
# commands it runs.
PYTHON = sys.executable or "python3"

QUEUE_MODULE = "ops.queue"
ESCALATION_MODULE = "ops.escalation"

# ``ops.queue`` pads every column and joins them with two spaces, and no cell
# value carries two consecutive spaces, so a run of two or more spaces is the
# column boundary.
COLUMN_SEPARATOR = re.compile(r" {2,}")

# The line ``ops.escalation`` prints on standard error carrying the packet's
# digest.
SHA256_LINE = re.compile(r"^packet sha256: ([0-9a-f]{64})$")


class ProtocolError(Exception):
    """A request the JSON-RPC layer itself refuses."""


class ToolRefusal(Exception):
    """A tool call the connector answers with an error result."""


# --------------------------------------------------------------------------
# The sets, and one case
# --------------------------------------------------------------------------
def run_directory(set_name: str) -> Path:
    """Where a set's committed run lives."""
    if set_name in V6_RUN_NAMES:
        return v6_runs.run_by_name(set_name).run_dir
    return func_sets.run_directory(set_name)


def case_numbers(set_name: str) -> Tuple[int, ...]:
    """Every case number a set holds, from the set's own registration."""
    if set_name in V6_RUN_NAMES:
        return tuple(v6_runs.run_by_name(set_name).cases)
    return tuple(development_sets.named(set_name).cases)


@dataclass(frozen=True)
class CaseRecord:
    """One case, read once, with everything the answers are built from."""

    set_name: str
    case_no: int
    run_dir: Path
    case: Mapping[str, Any]
    document: Mapping[str, Any]
    transcript: Mapping[str, Any]
    policy: view.PolicyFacts
    ruling: Mapping[str, Any]
    trigger: Optional[str]

    @property
    def category(self) -> str:
        return str((self.case.get("dispute") or {}).get("category"))

    @property
    def filed_by(self) -> Any:
        return (self.case.get("dispute") or {}).get("filed_by")

    @property
    def votes(self) -> int:
        """The number of drafts the judge was asked for, read from the run."""
        configuration = self.document.get("configuration")
        if (
            isinstance(configuration, Mapping)
            and configuration.get("judge_votes") is not None
        ):
            return int(configuration["judge_votes"])
        vote = self.transcript.get("vote")
        if isinstance(vote, Mapping) and vote.get("votes") is not None:
            return int(vote["votes"])
        return 0


def read_case(set_name: str, case_no: int) -> CaseRecord:
    """Read one case, through the product view's own reading functions.

    The brief is rebuilt and held to the digest the run recorded, exactly as
    ``ui/v2/build.py`` holds it: a digest that does not match means this code
    builds a different brief from the one the agents were handed, and the case
    is refused rather than answered from a brief that merely resembles it.
    """
    run_dir = run_directory(set_name)
    document = view._read_json(run_dir / "case-{0:05d}.json".format(case_no))
    transcript = view._transcript_of(run_dir, document, case_no)
    case = development_sets.named(set_name).load_case(case_no)

    configuration = document.get("configuration")
    version = (
        configuration.get("policy_version")
        if isinstance(configuration, Mapping)
        else None
    )
    category = str((case.get("dispute") or {}).get("category"))
    policy = view._policy_facts(category, int(version or 0))

    brief = brief_module.build_brief_for_case(case, policy_version=int(version or 0))
    _canonical, digest = brief_module.brief_digest(brief)
    recorded = document.get("brief_sha256")
    if recorded != digest:
        raise ToolRefusal(
            "case {0} of {1}: the rebuilt brief hashes to {2} and the run "
            "recorded {3}, so this code builds a different brief from the one "
            "the agents were handed".format(case_no, set_name, digest, recorded)
        )

    ruling = view._inner_ruling(document)
    trigger = (
        view.escalation_trigger(case, transcript)
        if ruling.get("ruling") == view.ESCALATE
        else None
    )
    return CaseRecord(
        set_name=set_name,
        case_no=case_no,
        run_dir=run_dir,
        case=case,
        document=document,
        transcript=transcript,
        policy=policy,
        ruling=ruling,
        trigger=trigger,
    )


# --------------------------------------------------------------------------
# Running an operations command
# --------------------------------------------------------------------------
def run_command(name: str, arguments: Sequence[str]) -> "subprocess.CompletedProcess[str]":
    """Run one operations command from the repository root and refuse a failure.

    The commands are run rather than imported: this module must not put an
    ``ops`` import edge into the evaluated system, and ``ops`` is a layer of
    its own. A non-zero exit is a refusal, reported with the command's own
    message rather than parsed as an empty reading.
    """
    completed = subprocess.run(
        [PYTHON, *arguments],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip() or (completed.stdout or "").strip()
        raise ToolRefusal(
            "{0} exited {1}: {2}".format(name, completed.returncode, detail)
        )
    return completed


# --------------------------------------------------------------------------
# tribunal_case
# --------------------------------------------------------------------------
def _plain(value: Any) -> str:
    """A recorded value as text, with an absent one named rather than blank."""
    return "none" if value is None else str(value)


def _relative(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def case_page(case_no: int) -> str:
    """The case page's path under ``ui/dist/``, and whether it was built."""
    path = view.DIST_DIR / "case-{0:05d}.html".format(case_no)
    shown = _relative(path)
    if path.is_file():
        return shown
    return "{0} (not built: ui/dist covers the four version-6 runs)".format(shown)


def case_text(record: CaseRecord) -> str:
    """One case's answer: the ruling, the money, the confidence, the opening."""
    ruling = record.ruling
    value = str(ruling.get("ruling"))
    currency = record.policy.currency
    filed_by = record.filed_by
    lines: List[str] = [
        "case {0} of {1} ({2}), filed by {3}".format(
            record.case_no,
            record.set_name,
            record.category,
            view.filed_by_words(filed_by) if filed_by else "unknown",
        ),
        "ruling: {0} ({1})".format(value, view.ruling_words(value)),
        "amount_sgd: {0}".format(view._money(ruling.get("amount_sgd"), currency)),
        "driver_compensation_sgd: {0}".format(
            view._money(ruling.get("driver_compensation_sgd"), currency)
        ),
        "confidence: {0}".format(_plain(ruling.get("confidence"))),
        "money: {0}".format(view.money_statement(ruling, currency, filed_by)),
    ]
    if record.trigger is not None:
        lines.append(
            "reason: {0} ({1})".format(
                record.trigger, view.trigger_words(record.trigger, record.votes)
            )
        )
    lines.append("judge's explanation (opening):")
    summary = view._summary_paragraphs(ruling.get("explanation"))
    lines.append(summary or "(the run records no explanation)")
    lines.append("case page: {0}".format(case_page(record.case_no)))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# tribunal_queue
# --------------------------------------------------------------------------
def _columns(line: str) -> List[str]:
    return [cell.strip() for cell in COLUMN_SEPARATOR.split(line.strip())]


def parse_queue(text: str) -> List[Dict[str, str]]:
    """``ops.queue``'s table, one dict per case, in the order the queue prints.

    The header row is located by its own column names, so a table this parser
    does not recognise is a refusal rather than a misreading.
    """
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if tuple(_columns(line)) == QUEUE_COLUMNS:
            start = index
            break
    if start is None:
        raise ToolRefusal("ops.queue printed no table this connector recognises")
    rows: List[Dict[str, str]] = []
    for line in lines[start + 1:]:
        if not line.strip():
            break
        cells = _columns(line)
        if len(cells) != len(QUEUE_COLUMNS) or not cells[0].isdigit():
            break
        rows.append(dict(zip(QUEUE_COLUMNS, cells)))
    return rows


def queue_text(set_name: str) -> str:
    """One set's lanes, their counts, and the cases in the human lane."""
    run_dir = run_directory(set_name)
    completed = run_command(
        QUEUE_MODULE, ("-m", QUEUE_MODULE, "--run-dir", str(run_dir))
    )
    rows = parse_queue(completed.stdout)
    if not rows:
        raise ToolRefusal("ops.queue printed no case for {0}".format(set_name))
    counts = {lane: sum(1 for row in rows if row["lane"] == lane) for lane in LANES}
    lines: List[str] = [
        "set: {0}".format(set_name),
        "run: {0}".format(_relative(run_dir)),
        "cases: {0}".format(len(rows)),
        "lanes:",
    ]
    for lane in LANES:
        lines.append("  {0} {1}".format(lane, counts.get(lane, 0)))
    human = [row for row in rows if row["lane"] == HUMAN_LANE]
    lines.append("human lane:")
    if not human:
        lines.append("  (none)")
    for row in human:
        lines.append("  {0} {1} {2}".format(row["case"], row["lane"], row["reasons"]))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# tribunal_packet
# --------------------------------------------------------------------------
def packet_sha256(stdout: str, stderr: str) -> str:
    """The packet's digest, as the command prints it.

    ``ops.escalation`` prints the digest on standard error. Where it does not,
    the digest is taken over the canonical JSON the command printed, which is
    the document the digest is defined over.
    """
    for line in (stderr or "").splitlines():
        match = SHA256_LINE.match(line.strip())
        if match is not None:
            return match.group(1)
    return hashlib.sha256(stdout.rstrip("\n").encode("utf-8")).hexdigest()


def packet_text(set_name: str, case_no: int) -> str:
    """One escalation packet's summary and its digest."""
    run_dir = run_directory(set_name)
    completed = run_command(
        ESCALATION_MODULE,
        (
            "-m",
            ESCALATION_MODULE,
            "--run-dir",
            str(run_dir),
            "--case",
            str(case_no),
            "--format",
            "json",
        ),
    )
    try:
        packet = json.loads(completed.stdout)
    except ValueError as exc:
        raise ToolRefusal(
            "ops.escalation printed no JSON packet: {0}".format(exc)
        ) from exc
    if not isinstance(packet, Mapping):
        raise ToolRefusal("ops.escalation printed a packet that is not an object")
    case = packet.get("case") or {}
    trigger = packet.get("trigger") or {}
    ruling = packet.get("ruling") or {}
    lines: List[str] = [
        "packet: case {0} of {1} ({2}), policy version {3}".format(
            case_no,
            packet.get("set"),
            case.get("category"),
            packet.get("policy_version"),
        ),
        "trigger: outcome={0} threshold={1} valid={2} votes={3} agreement={4}".format(
            _plain(trigger.get("outcome")),
            _plain(trigger.get("threshold")),
            _plain(trigger.get("valid")),
            _plain(trigger.get("votes")),
            _plain(trigger.get("agreement")),
        ),
        "ruling: {0}".format(_plain(ruling.get("ruling"))),
        "amount_sgd: {0}".format(_plain(ruling.get("amount_sgd"))),
        "driver_compensation_sgd: {0}".format(
            _plain(ruling.get("driver_compensation_sgd"))
        ),
        "confidence: {0}".format(_plain(ruling.get("confidence"))),
        "drafts: {0}".format(len(packet.get("drafts") or [])),
        "clause ids relied on: {0}".format(
            ", ".join(packet.get("clause_ids") or []) or "none"
        ),
        "sha256: {0}".format(packet_sha256(completed.stdout, completed.stderr)),
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# The tools
# --------------------------------------------------------------------------
def _required_set(arguments: Mapping[str, Any]) -> str:
    """The set a request names, refused unless it is one this connector offers."""
    set_name = arguments.get("set")
    if not isinstance(set_name, str):
        raise ToolRefusal(
            "a set name is required; the sets are: {0}".format(", ".join(OFFERED_SETS))
        )
    if set_name not in OFFERED_SETS:
        if set_name in SEALED_SET_NAMES:
            raise ToolRefusal(
                "the {0} set is sealed: it is not offered and its cases are "
                "never read".format(set_name)
            )
        raise ToolRefusal(
            "no set is offered as {0!r}; the sets are: {1}".format(
                set_name, ", ".join(OFFERED_SETS)
            )
        )
    return set_name


def _required_case(arguments: Mapping[str, Any]) -> int:
    """The case number a request names, refused unless it is an integer."""
    case_no = arguments.get("case")
    if isinstance(case_no, bool) or not isinstance(case_no, int):
        raise ToolRefusal(
            "a case number is required, as an integer; got {0!r}".format(case_no)
        )
    return case_no


def _require_case_in_set(set_name: str, case_no: int) -> None:
    """Refuse a case the named set does not hold."""
    numbers = case_numbers(set_name)
    if case_no in numbers:
        return
    if not numbers:
        raise ToolRefusal("{0} holds no case".format(set_name))
    raise ToolRefusal(
        "case {0} is not in {1}; that set holds {2} cases, {3} to {4}".format(
            case_no, set_name, len(numbers), min(numbers), max(numbers)
        )
    )


def tool_case(arguments: Mapping[str, Any]) -> str:
    set_name = _required_set(arguments)
    case_no = _required_case(arguments)
    _require_case_in_set(set_name, case_no)
    try:
        record = read_case(set_name, case_no)
    except ToolRefusal:
        raise
    except Exception as exc:
        raise ToolRefusal(
            "case {0} of {1} cannot be read: {2}".format(case_no, set_name, exc)
        ) from exc
    return case_text(record)


def tool_queue(arguments: Mapping[str, Any]) -> str:
    set_name = _required_set(arguments)
    return queue_text(set_name)


def tool_packet(arguments: Mapping[str, Any]) -> str:
    set_name = _required_set(arguments)
    case_no = _required_case(arguments)
    _require_case_in_set(set_name, case_no)
    return packet_text(set_name, case_no)


TOOL_HANDLERS: Mapping[str, Callable[[Mapping[str, Any]], str]] = {
    "tribunal_case": tool_case,
    "tribunal_queue": tool_queue,
    "tribunal_packet": tool_packet,
}

TOOLS: Tuple[Mapping[str, Any], ...] = (
    {
        "name": "tribunal_case",
        "description": (
            "How one Tribunal case was decided: the ruling in plain words, the "
            "amounts, the confidence, the reason code when the case went to a "
            "human, the opening of the judge's explanation, and the case page's "
            "path under ui/dist/. Read-only; reads committed records only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "set": {
                    "type": "string",
                    "enum": list(OFFERED_SETS),
                    "description": "the set the case belongs to",
                },
                "case": {
                    "type": "integer",
                    "description": "the case number, as an integer",
                },
            },
            "required": ["set", "case"],
        },
    },
    {
        "name": "tribunal_queue",
        "description": (
            "One Tribunal set's queue: the three lanes and how many cases each "
            "holds, and every case in the human-review lane with the reason it "
            "is there. Read-only; runs python3 -m ops.queue and reads its table."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "set": {
                    "type": "string",
                    "enum": list(OFFERED_SETS),
                    "description": "the set whose queue is asked for",
                }
            },
            "required": ["set"],
        },
    },
    {
        "name": "tribunal_packet",
        "description": (
            "One escalated Tribunal case's escalation packet: its trigger, its "
            "ruling and money, how many drafts it holds, the clause ids relied "
            "on, and the packet's sha256. Read-only; runs "
            "python3 -m ops.escalation and reads what it prints."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "set": {
                    "type": "string",
                    "enum": list(OFFERED_SETS),
                    "description": "the set the case belongs to",
                },
                "case": {
                    "type": "integer",
                    "description": "the case number, as an integer",
                },
            },
            "required": ["set", "case"],
        },
    },
)


# --------------------------------------------------------------------------
# The JSON-RPC layer
# --------------------------------------------------------------------------
def _result(identifier: Any, result: Mapping[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": identifier, "result": dict(result)}


def _error(identifier: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}


def initialize_result() -> Dict[str, Any]:
    """What ``initialize`` answers: the server's name, version and tools."""
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
    }


def call_tool(params: Any) -> Dict[str, Any]:
    """One ``tools/call``: the named tool, run, as an MCP result.

    A malformed request is a :class:`ProtocolError`, which the layer turns into
    a JSON-RPC error. A tool that runs and refuses its input answers with an
    error result, so a caller can tell "I do not know that tool" from "that
    tool declined this case".
    """
    if not isinstance(params, Mapping):
        raise ProtocolError("tools/call needs an object with a name and arguments")
    name = params.get("name")
    if not isinstance(name, str):
        raise ProtocolError("tools/call needs a tool name")
    arguments = params.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, Mapping):
        raise ProtocolError("tools/call arguments must be an object")
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise ProtocolError(
            "unknown tool {0!r}; the tools are: {1}".format(
                name, ", ".join(TOOL_HANDLERS)
            )
        )
    try:
        text = handler(arguments)
    except ToolRefusal as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    return {"content": [{"type": "text", "text": text}], "isError": False}


def handle(message: Any) -> Optional[Dict[str, Any]]:
    """One request in, one response out, or ``None`` for a notification."""
    if not isinstance(message, Mapping):
        return _error(None, INVALID_REQUEST, "a request must be a JSON object")
    identifier = message.get("id")
    if message.get("jsonrpc") != "2.0":
        return _error(identifier, INVALID_REQUEST, 'the "jsonrpc" member must be "2.0"')
    method = message.get("method")
    if not isinstance(method, str):
        return _error(identifier, INVALID_REQUEST, 'the "method" member must be a string')
    if "id" not in message:
        # A notification is never answered, whatever method it names.
        return None
    if method == "initialize":
        return _result(identifier, initialize_result())
    if method == "tools/list":
        return _result(identifier, {"tools": [dict(tool) for tool in TOOLS]})
    if method == "tools/call":
        try:
            return _result(identifier, call_tool(message.get("params")))
        except ProtocolError as exc:
            return _error(identifier, INVALID_PARAMS, str(exc))
    return _error(identifier, METHOD_NOT_FOUND, "unknown method {0!r}".format(method))


def _log(message: str) -> None:
    sys.stderr.write("tribunal-mcp: {0}\n".format(message))
    sys.stderr.flush()


def _write(response: Mapping[str, Any]) -> None:
    """One protocol message on standard output, and nothing else is ever written."""
    sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Read one JSON object per line from standard input and answer each."""
    _log("ready; {0} sets offered".format(len(OFFERED_SETS)))
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError as exc:
            _write(_error(None, PARSE_ERROR, "invalid JSON: {0}".format(exc)))
            continue
        try:
            response = handle(message)
        except Exception as exc:  # a server must not die on one request
            _log("unhandled error: {0!r}".format(exc))
            response = _error(
                message.get("id") if isinstance(message, Mapping) else None,
                INTERNAL_ERROR,
                "the connector failed: {0}".format(exc),
            )
        if response is not None:
            _write(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
