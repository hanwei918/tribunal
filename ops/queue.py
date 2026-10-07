"""The queue: which dispute is looked at first, and against which target.

The stretch goal is a "SLA & Routing Manager" that "prioritizes disputes by
urgency and value", with high-priority disputes -- safety-related ones -- fast
tracked. This is that router, and it is a **reader**: it takes the disputes a run
holds and says what lane each one belongs in, in what order they should be
worked and how long each has. It changes nothing in ``tribunal/``: the pipeline
does not consult it, and a dispute it routes to a human is a dispute the pipeline
has already finished with.

**Three lanes.**

* ``SAFETY_FAST_TRACK`` -- a category the pipeline does not adjudicate **and**
  that is safety-related, such as ``SAFETY_INCIDENT``. It never enters the
  pipeline, so there is no ruling to route on and the lane is decided by the
  category alone.
* ``HUMAN_REVIEW`` -- any of three things: the ruling is ``ESCALATE``; the
  category is out of scope (``PROPERTY_DAMAGE`` needs image analysis the pipeline
  does not do); or the kill switch is off.
* ``AUTO`` -- the pipeline ruled, or has ruled, and did not escalate.

**The kill switch.** ``auto_rulings_enabled`` false in ``ops/config.json`` moves
every dispute the pipeline would have ruled on into ``HUMAN_REVIEW`` with the
reason ``AUTO_PAUSED``. It is the router declining to hand the dispute on, and it
is recorded here and nowhere else: nothing in ``tribunal/`` reads this file, so
pausing the queue cannot change a request or a ruling.

**The order.** Four tiers: the safety lane; then ``HUMAN_REVIEW`` with a tripped
part-1 test; then the rest of ``HUMAN_REVIEW``; then ``AUTO``. Within a tier, the
earliest SLA due time first, then the larger contested amount, then the case
number. A tripped risk signal **orders** a human review, and it does not by
itself move an ``AUTO`` case out of its lane: the five tests are the judge's own
tests, applied through the policy, and a signal is a second reading for a person
rather than a reason to reroute a case the pipeline decided.

**The SLA.** A due time is ``filed_at`` plus the lane's target -- the safety
lane's ``safety_hours``, human review's ``human_review_hours``, the auto lane's
``auto_ruling_minutes`` -- and with ``--now`` the queue says what is left or says
``BREACHED``. The config's ``end_to_end_hours`` is the queue's commitment from
filing to resolution and is printed as such; no due time is computed from it,
because the policy does not state one and this module will not invent a second
deadline. The numbers themselves are the team's own, not Ryde's, and
``ops/config.json`` says so in its own ``note``.

**No threshold here comes from the policy, and that is not a gap.** The queue
applies no policy number of its own: the only policy figures that reach a lane
are part 1's five tests, and ``ops.risk`` reads those out of the loaded policy
and refuses a sentence that has moved. What this module reads instead is
``ops/config.json``, and it refuses a config that does not state a target rather
than defaulting to one -- the same rule, applied to the file the team owns.

**Determinism.** No wall clock is read unless ``--now`` is given; without it the
status column says so rather than guessing. The output is sorted by the queue's
own order, and two runs of one command are byte-identical.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from ops import OpsError, development_set_for, read_json_document, risk
from tribunal import loader

# The config this module reads when it is not given one. It sits beside the
# module, so the numbers a queue is run against travel with the code that
# applies them.
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

# The three lanes.
LANE_SAFETY = "SAFETY_FAST_TRACK"
LANE_HUMAN = "HUMAN_REVIEW"
LANE_AUTO = "AUTO"
LANES = (LANE_SAFETY, LANE_HUMAN, LANE_AUTO)

# The four tiers, in the order the queue is worked. Named so a reader of the
# output and a reader of this file are talking about the same thing.
TIER_SAFETY = 1
TIER_HUMAN_RISK = 2
TIER_HUMAN = 3
TIER_AUTO = 4

# Why a case is in the lane it is in. ``RISK_TRIPPED`` is not a lane reason: it
# is recorded because a reviewer reading the queue should see it, and it is what
# puts a human review in the second tier.
REASON_SAFETY = "SAFETY"
REASON_ESCALATED = "ESCALATE"
REASON_OUT_OF_SCOPE = "OUT_OF_SCOPE"
REASON_AUTO_PAUSED = "AUTO_PAUSED"
REASON_RULED = "RULED"
REASON_RISK_TRIPPED = "RISK_TRIPPED"

# The ruling value the pipeline uses to hand a case to a human. Named here
# rather than read from the policy, because it is a *value* of the ruling
# vocabulary and not a policy number.
ESCALATE = "ESCALATE"

# The safety categories. A category is fast-tracked when it is one of these AND
# the pipeline does not adjudicate it: the first half is the team's list, and
# the second is read off the loader's own map, so a safety category the pipeline
# later learns to rule on stops being fast-tracked rather than silently skipping
# the pipeline. The list is a list and not a name prefix, because a name is not
# a guarantee of anything.
SAFETY_CATEGORIES: Tuple[str, ...] = ("SAFETY_INCIDENT",)

# The four targets the config states, and the lane each one is the target of.
SLA_KEYS = (
    "auto_ruling_minutes",
    "human_review_hours",
    "safety_hours",
    "end_to_end_hours",
)

# What a config key must be for this module to route on it.
CONFIG_BOOL_KEY = "auto_rulings_enabled"
CONFIG_SLA_KEY = "sla"
CONFIG_NOTE_KEY = "note"


class QueueError(OpsError):
    """A queue could not be built: a run, a case or a config could not be read."""


# --------------------------------------------------------------------------
# The config
# --------------------------------------------------------------------------
class Slas(NamedTuple):
    """The targets one config states, in the units the config states them in."""

    auto_ruling_minutes: Decimal
    human_review_hours: Decimal
    safety_hours: Decimal
    end_to_end_hours: Decimal

    def target_for(self, lane: str) -> timedelta:
        """How long the lane has, from filing."""
        if lane == LANE_SAFETY:
            return timedelta(hours=float(self.safety_hours))
        if lane == LANE_HUMAN:
            return timedelta(hours=float(self.human_review_hours))
        if lane == LANE_AUTO:
            return timedelta(minutes=float(self.auto_ruling_minutes))
        raise QueueError("no lane named {0!r}".format(lane))

    def end_to_end(self) -> timedelta:
        return timedelta(hours=float(self.end_to_end_hours))


class Config(NamedTuple):
    """One loaded config: the kill switch, the targets, and the note."""

    auto_rulings_enabled: bool
    sla: Slas
    note: Optional[str]


def load_config(path: Optional[Path] = None) -> Config:
    """Read a config, refusing one that does not state what the queue needs.

    Every value is required. A missing key is a refusal rather than a default,
    for the reason a moved policy sentence is a refusal in ``ops.risk``: a
    target nobody wrote down is a target nobody chose, and a queue that invented
    one would be reporting against a figure the team never agreed.
    """
    document = read_json_document(
        CONFIG_PATH if path is None else Path(path), QueueError
    )
    if not isinstance(document, Mapping):
        raise QueueError("the config must be a JSON object")

    enabled = document.get(CONFIG_BOOL_KEY)
    if not isinstance(enabled, bool):
        raise QueueError(
            "the config must state {0} as true or false".format(CONFIG_BOOL_KEY)
        )

    sla_block = document.get(CONFIG_SLA_KEY)
    if not isinstance(sla_block, Mapping):
        raise QueueError("the config must state {0} as an object".format(CONFIG_SLA_KEY))

    values: Dict[str, Decimal] = {}
    for key in SLA_KEYS:
        raw = sla_block.get(key)
        if raw is None or isinstance(raw, bool):
            raise QueueError(
                "the config states no {0}.{1}".format(CONFIG_SLA_KEY, key)
            )
        try:
            value = Decimal(str(raw))
        except Exception as exc:
            raise QueueError(
                "the config's {0}.{1} is not a number: {2!r}".format(
                    CONFIG_SLA_KEY, key, raw
                )
            ) from exc
        if value <= 0:
            raise QueueError(
                "the config's {0}.{1} is {2}; a target must be greater than "
                "zero".format(CONFIG_SLA_KEY, key, value)
            )
        values[key] = value

    note = document.get(CONFIG_NOTE_KEY)
    return Config(
        auto_rulings_enabled=enabled,
        sla=Slas(**values),
        note=note if isinstance(note, str) else None,
    )


# --------------------------------------------------------------------------
# The disputes
# --------------------------------------------------------------------------
class Dispute(NamedTuple):
    """One dispute, as far as the queue is concerned.

    Everything a lane, a tier and a due time are computed from, and nothing
    else: no claim text, no evidence, no explanation. The queue routes cases; it
    does not decide them.
    """

    case_no: int
    category: str
    filed_at: str
    amount_contested_sgd: Optional[Decimal]
    ruling: Optional[str]
    wall_seconds: Optional[Decimal]
    risk_tripped: bool


class Entry(NamedTuple):
    """One dispute's place in the queue."""

    tier: int
    case_no: int
    category: str
    lane: str
    reasons: Tuple[str, ...]
    amount: Optional[Decimal]
    filed_at: str
    due_at: datetime
    status: str
    wall_seconds: Optional[Decimal]


def lane_for(dispute: Dispute, config: Config) -> Tuple[str, Tuple[str, ...]]:
    """Which lane a dispute is in, and why.

    The in-scope categories are the loader's own category-to-policy map, so a
    category the pipeline learns to adjudicate becomes routable without this
    module being edited.
    """
    if dispute.category not in loader.CATEGORY_POLICY_FILES:
        if dispute.category in SAFETY_CATEGORIES:
            return LANE_SAFETY, (REASON_SAFETY,)
        return LANE_HUMAN, (REASON_OUT_OF_SCOPE,)
    if dispute.ruling == ESCALATE:
        return LANE_HUMAN, (REASON_ESCALATED,)
    if not config.auto_rulings_enabled:
        # The kill switch is the reason this case is not AUTO, so it is the
        # reason recorded. A case already going to a human is not re-reasoned.
        return LANE_HUMAN, (REASON_AUTO_PAUSED,)
    return LANE_AUTO, (REASON_RULED,)


def tier_for(lane: str, risk_tripped: bool) -> int:
    """Where a case sits in the order, within its lane."""
    if lane == LANE_SAFETY:
        return TIER_SAFETY
    if lane == LANE_HUMAN:
        return TIER_HUMAN_RISK if risk_tripped else TIER_HUMAN
    return TIER_AUTO


def _parse_instant(text: Any, where: str) -> datetime:
    if not isinstance(text, str):
        raise QueueError("{0} is not an ISO 8601 instant: {1!r}".format(where, text))
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise QueueError(
            "{0} is not an ISO 8601 instant: {1!r}".format(where, text)
        ) from exc


def _duration(delta: timedelta) -> str:
    """A duration as days, hours and minutes, with trailing zeros dropped."""
    total = int(delta.total_seconds())
    if total == 0:
        return "0m"
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    parts = [(hours, "h"), (minutes, "m")]
    if days:
        parts.insert(0, (days, "d"))
    while len(parts) > 1 and parts[-1][0] == 0:
        parts.pop()
    while len(parts) > 1 and parts[0][0] == 0:
        parts.pop(0)
    return " ".join("{0}{1}".format(value, unit) for value, unit in parts)


def status_for(due_at: datetime, now: Optional[datetime]) -> str:
    """The time left, or ``BREACHED``, or a dash when no instant was given.

    ``now`` is the only wall clock this module ever sees. Without it the status
    is not computed at all, because a queue that answered "what is left" from
    the machine's clock would give a different answer every time it was read.
    """
    if now is None:
        return "-"
    remaining = due_at - now
    if remaining.total_seconds() < 0:
        return "BREACHED"
    return "{0} remaining".format(_duration(remaining))


def build_queue(
    disputes: Sequence[Dispute], config: Config, now: Optional[datetime] = None
) -> List[Entry]:
    """The queue, in the order it is worked.

    The sort is the rule the task states and it is a total order: tier, then the
    earliest due time, then the larger contested amount, then the case number.
    A case with no contested amount sorts as if it were zero, which is the only
    value that means "nothing was asked for".
    """
    entries: List[Entry] = []
    for dispute in disputes:
        lane, reasons = lane_for(dispute, config)
        if dispute.risk_tripped:
            reasons = reasons + (REASON_RISK_TRIPPED,)
        due_at = _parse_instant(dispute.filed_at, "filed_at") + config.sla.target_for(lane)
        entries.append(
            Entry(
                tier=tier_for(lane, dispute.risk_tripped),
                case_no=dispute.case_no,
                category=dispute.category,
                lane=lane,
                reasons=reasons,
                amount=dispute.amount_contested_sgd,
                filed_at=dispute.filed_at,
                due_at=due_at,
                status=status_for(due_at, now),
                wall_seconds=dispute.wall_seconds,
            )
        )
    return sorted(
        entries,
        key=lambda entry: (
            entry.tier,
            entry.due_at,
            -_as_decimal(entry.amount),
            entry.case_no,
        ),
    )


def _as_decimal(value: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        return Decimal(0)
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(0)


def measured_auto_sla(
    entries: Sequence[Entry], config: Config
) -> Tuple[int, int]:
    """``(met, of)`` for the auto lane: how many met the target, out of how many.

    Measured and reported as a count of cases rather than as a rate, because a
    rate is a claim and a count is a reading. A case whose run recorded no
    ``wall_seconds`` did not meet the target, and it is still counted in the
    denominator: it is one of the auto cases and its time is not known.
    """
    limit = config.sla.auto_ruling_minutes * 60
    auto = [entry for entry in entries if entry.lane == LANE_AUTO]
    met = [entry for entry in auto if _at_most(entry.wall_seconds, limit)]
    return len(met), len(auto)


def _at_most(value: Any, limit: Decimal) -> bool:
    """Whether a recorded number is at or under a limit.

    A ``wall_seconds`` read out of a run is a ``Decimal``, because every
    document this layer reads is parsed with ``parse_float=Decimal``; a fixture
    may hand it a float, so the comparison goes through the same conversion
    either way rather than testing the type and answering ``False``.
    """
    if value is None or isinstance(value, bool):
        return False
    try:
        return Decimal(str(value)) <= limit
    except Exception:
        return False


# --------------------------------------------------------------------------
# Reading a run
# --------------------------------------------------------------------------
def _risk_tripped(case: Mapping[str, Any], document: Mapping[str, Any], development_set) -> bool:
    """Whether any of part 1's five tests trips for this case.

    A category the pipeline does not adjudicate has no signals to read, because
    the tests are clauses of the policy that category has none of. The policy
    version is the one the run recorded for the case, as the closure rules use
    it: a case briefed at version 2 is read at version 2.
    """
    category = case["dispute"]["category"]
    if category not in loader.CATEGORY_POLICY_FILES:
        return False
    configuration = document.get("configuration")
    version = configuration.get("policy_version") if isinstance(configuration, Mapping) else None
    policies = loader.load_policies(category, version or development_set.policy_version)
    return any(signal.tripped for signal in risk.signals_for(case, policies))


def disputes_from_run(run_dir: Path) -> List[Dispute]:
    """Every case a run directory holds, as a dispute the queue can route."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise QueueError("no run directory at {0}".format(run_dir))
    development_set = development_set_for(run_dir)

    found: List[Dispute] = []
    for path in sorted(run_dir.glob("case-*.json")):
        if path.name.endswith(".transcript.json"):
            continue
        document = read_json_document(path, QueueError)
        if not isinstance(document, Mapping):
            raise QueueError("the case file at {0} is not a JSON object".format(path))
        case_no = document.get("case_no")
        ruling_block = document.get("ruling")
        inner = ruling_block.get("ruling") if isinstance(ruling_block, Mapping) else None
        if not isinstance(inner, Mapping):
            raise QueueError(
                "the case file at {0} records no ruling, so the queue cannot route "
                "it".format(path)
            )
        case = development_set.load_case(case_no)
        dispute = case["dispute"]
        found.append(
            Dispute(
                case_no=case_no,
                category=dispute["category"],
                filed_at=dispute["filed_at"],
                amount_contested_sgd=dispute.get("amount_contested_sgd"),
                ruling=inner.get("ruling"),
                wall_seconds=document.get("wall_seconds"),
                risk_tripped=_risk_tripped(case, document, development_set),
            )
        )
    return found


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
# The columns, in the order the task names them.
COLUMNS: Tuple[Tuple[str, int], ...] = (
    ("tier", 4),
    ("case", 5),
    ("category", 16),
    ("lane", 17),
    ("reasons", 26),
    ("amount", 7),
    ("filed_at", 25),
    ("due_at", 25),
    ("status", 0),
)


def _row(values: Sequence[str]) -> str:
    cells = []
    for (name, width), value in zip(COLUMNS, values):
        cells.append(value if width == 0 else "{0:<{1}}".format(value, width))
    return "  ".join(cells).rstrip()


def render(
    entries: Sequence[Entry], config: Config, run_dir: Path, disputes: Sequence[Dispute]
) -> str:
    """The queue as text: a header, one row per case, and the measured SLA."""
    met, of = measured_auto_sla(entries, config)
    lines: List[str] = [
        "queue: {0} case(s) from {1}".format(len(entries), run_dir),
        "auto rulings: {0}".format("enabled" if config.auto_rulings_enabled else "paused"),
        "end-to-end target: {0} from filing to resolution".format(
            _duration(config.sla.end_to_end())
        ),
        "",
        _row([name for name, _width in COLUMNS]),
    ]
    for entry in entries:
        lines.append(
            _row(
                [
                    str(entry.tier),
                    str(entry.case_no),
                    entry.category,
                    entry.lane,
                    "+".join(entry.reasons),
                    "-" if entry.amount is None else str(entry.amount),
                    entry.filed_at,
                    entry.due_at.isoformat(),
                    entry.status,
                ]
            )
        )
    lines += [
        "",
        "measured auto-ruling SLA: {0} of {1} AUTO case(s) met the {2}-minute "
        "target on wall_seconds".format(
            met, of, config.sla.auto_ruling_minutes
        ),
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    """Print the queue for one run: tier, lane, due time and status per case."""
    parser = argparse.ArgumentParser(
        prog="python -m ops.queue",
        description=(
            "Route the disputes of one run into the safety, human-review and "
            "auto lanes, order them by tier and due time, and report the "
            "measured auto-ruling SLA. Reads only; makes no model call and "
            "writes nothing."
        ),
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="the run directory")
    parser.add_argument(
        "--now",
        default=None,
        help=(
            "an ISO 8601 instant with a UTC offset, e.g. 2026-08-01T12:00:00+08:00; "
            "the only wall clock this command reads"
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="the config to read; defaults to ops/config.json",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        disputes = disputes_from_run(args.run_dir)
        now = None
        if args.now is not None:
            now = _parse_instant(args.now, "--now")
            if now.tzinfo is None:
                raise QueueError(
                    "--now must carry a UTC offset, so it names an instant rather "
                    "than a wall time: {0!r}".format(args.now)
                )
        entries = build_queue(disputes, config, now)
    except QueueError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1

    sys.stdout.write(render(entries, config, args.run_dir, disputes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
