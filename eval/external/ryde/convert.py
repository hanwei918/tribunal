"""Convert the organisers' sample case (DISP-002) into this system's case format.

What this reads, and what it refuses to read
--------------------------------------------
``eval/external/ryde/DISP-002.md`` is the sample the organisers gave every team.
It is **answer-bearing**: a title states the expected ruling, and an
"Evidence Summary" argues for one side. Only the fenced JSON block inside it is
case material.

So the block is located by *parsing* the Markdown -- a line scanner over the
fences, not a regular expression over the whole document -- and the parse is
required to find exactly one fenced JSON block. That block, and nothing else,
is the converter's input: :func:`conversion_input` is the only function that
reads the document, and it returns the block text alone. A reader can check that
by looking at what the rest of this module is able to see, which is one string.

The title and the Evidence Summary reach nothing. They are not parsed, not
searched, and not available to any function here.

Why the converter lives under ``eval/``
---------------------------------------
It has to read answer-bearing material, and ``tests/test_answer_isolation.py``
forbids any module under ``tribunal/`` from naming a path under ``eval/``. A
converter in the package would be a path from the runtime code to the answer.
So it sits beside the source it reads. It writes to ``data/external/`` and never
the other way; nothing here writes into ``eval/``.

What it will not invent
-----------------------
The source is thinner than this corpus. Where it is silent, the converted case
carries ``null`` rather than a plausible value, and every such place is recorded
in the mapping record written beside the case. Four in particular:

* the GPS fixes carry **no** ``accuracy_m``. None is added. Under POL-NS-02 a
  fix without reported accuracy is evidence of neither presence nor absence, so
  these fixes do not establish arrival. That is the intended consequence.
* there is **no** rider GPS track, so ``rider_track`` is empty.
* there is **no** statement from the driver as counterparty, so the field is
  ``null``.
* the source states **no** pickup zone class. ``STANDARD`` is used as an
  explicitly stated assumption, never inferred from the place name, and the
  mapping records which figures depend on it.

What it will not drop in silence
--------------------------------
Every item in the block is either carried into the converted case or recorded in
the mapping record with the reason it is not. That is a contract, not an
intention: :func:`source_items` names every item in the block,
:func:`unrecorded_items` reports the ones no mapping entry names, and
:func:`write_outputs` **refuses to write a mapping that fails it** rather than
emitting a record with a hole in it.

Two of those records are about evidence rather than bookkeeping, and are worth
naming here.

* The source's ``driver_arrived`` event says the arrival marker was
  auto-confirmed from a GPS measurement within ten metres of the pickup point.
  That text is carried into the trip record's admissibility notes, verbatim and
  labelled for what it is: a platform **distance** claim, not a reported
  horizontal accuracy. So it is not written to ``accuracy_m`` on any fix, it
  does not make any fix qualifying under POL-NS-02, and it is not a GPS fix of
  its own.
* It also means the arrival marker and the trace are the **same measurement**.
  Under POL-GEN-02's independence rule the two are one carrier rather than two,
  and the notes say so, because a reader comparing the marker with the trace
  would otherwise take them for corroborating each other.

Run with ``python eval/external/ryde/convert.py``. It is idempotent: the same
source produces the same bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------------
# This file sits at <root>/eval/external/ryde/convert.py, so the project root is
# three directories up. It goes on the path because the converter needs
# ``tribunal.prepass`` for the corpus's weight arithmetic -- the one package
# import here, made at call time rather than at module scope.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SOURCE_PATH = PROJECT_ROOT / "eval" / "external" / "ryde" / "DISP-002.md"
EXPECTED_PATH = PROJECT_ROOT / "eval" / "external" / "ryde" / "expected.json"

# The policy version the conversion is written for. Version 1 is the case the
# recorded run read, and it stays byte-identical: nothing below changes for it.
# Version 3 adds the sample's own platform parameters and its app-event log,
# which is what POL-NS-01(c) and POL-GEN-02(2) read. Version 7 is Ryde's own
# Dispute Resolution Policy v2.1: the two samples are converted into the set the
# version-7 policy can be run against -- DISP-002 as case 903, and DISP-001, the
# route-deviation sample, as case 902 by the converter at the foot of this file.
DEFAULT_POLICY_VERSION = 1
PLATFORM_POLICY_VERSION = 3
V7_POLICY_VERSION = 7
POLICY_VERSIONS = (DEFAULT_POLICY_VERSION, PLATFORM_POLICY_VERSION, V7_POLICY_VERSION)

# One output directory per version. The version-1 directory holds the case the
# recorded run read and is never rewritten; the version-3 case is written beside
# it, under a directory of its own, with its own mapping; and version 7 writes
# the two cases of the `ryde-v7` set, with their mappings and the set's index.
OUTPUT_DIR = PROJECT_ROOT / "data" / "external" / "ryde"
OUTPUT_DIR_FOR_VERSION = {
    DEFAULT_POLICY_VERSION: OUTPUT_DIR,
    PLATFORM_POLICY_VERSION: PROJECT_ROOT / "data" / "external" / "ryde-v3",
    V7_POLICY_VERSION: PROJECT_ROOT / "data" / "external" / "ryde-v7",
}
CASE_NAME = "case-00901.json"
MAPPING_NAME = "mapping.json"
CASE_PATH = OUTPUT_DIR / CASE_NAME
MAPPING_PATH = OUTPUT_DIR / MAPPING_NAME

# The case number. The corpus occupies 101-115 and 201-214; a converted case is
# drawn from outside both ranges so it can never be mistaken for a corpus case.
CASE_NO = 901

# The number each version's conversion of DISP-002 carries. Versions 1 and 3
# both converted the one sample and both number it 901; version 7 converts two
# samples into one set, so DISP-002 is 903 and DISP-001 -- the route-deviation
# sample, whose converter is the `DISP-001` section below -- is 902.
CASE_NO_FOR_VERSION = {
    DEFAULT_POLICY_VERSION: CASE_NO,
    PLATFORM_POLICY_VERSION: CASE_NO,
    V7_POLICY_VERSION: 903,
}
ROUTE_DEVIATION_CASE_NO = 902

# The suffix every artifact id of that case carries. It is the case number, so
# the ids of one converted case name that case and no other.
ROUTE_DEVIATION_SUFFIX = "{0:05d}".format(ROUTE_DEVIATION_CASE_NO)

# The two counters the route-deviation sample states and the no-show sample does
# not. They are carried, because the corpus's driver profile has a field for
# each; the version-1 and version-3 conversions of DISP-002 null them, and their
# own source is silent on both.
DRIVER_COUNTERS_STATED = {
    "cancellation_rate": 0.03,
}

# The contract's version string. All 29 corpus cases carry it.
SCHEMA_VERSION = "1.2.0"

# The corpus's assessor label, so a reader can tell the converted case's
# admissibility blocks were produced the same way as the corpus's.
ASSESSOR_VERSION = "prepass-1.0.0"

# The category. The source calls this a "no_show_charge"; this system's
# vocabulary for that is NO_SHOW_CHARGE, which is what selects policy/no_show.json.
CATEGORY = "NO_SHOW_CHARGE"

# The zone class the source does not state. Recorded as an assumption, not
# inferred: this repository's prompts forbid world knowledge about places.
ASSUMED_ZONE_CLASS = "STANDARD"

# The vehicle tier the source does not state. The source names a Honda HR-V,
# which is a tier name nowhere in this corpus; RYDE_X is this corpus's base tier.
ASSUMED_VEHICLE_TIER = "RYDE_X"

# Every top-level key the source's fenced block is required to carry. A block
# with a different key set is not the document this converter was written for,
# and is refused rather than partly read.
SOURCE_KEYS = (
    "dispute_ticket",
    "rider_profile",
    "driver_profile",
    "trip_data",
    "gps_telemetry",
    "chat_logs",
    "app_events",
    "cancellation_policy",
)


class ConversionError(Exception):
    """The source is not the shape this converter can read."""


# --------------------------------------------------------------------------
# Parsing the Markdown: fences, structurally
# --------------------------------------------------------------------------
def fenced_blocks(markdown: str) -> List[Dict[str, Any]]:
    """Every fenced code block in a Markdown document.

    A line scanner over the fence markers, not a regular expression over the
    document. A regex for ```json ... ``` would match the *text* of a fence
    wherever it appeared, including inside prose about fences; walking the lines
    and tracking whether a fence is open is what makes this a parse.
    """
    blocks: List[Dict[str, Any]] = []
    opener: Optional[Tuple[int, str]] = None
    body: List[str] = []

    for number, line in enumerate(markdown.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if opener is None:
                opener = (number, stripped[3:].strip())
                body = []
            else:
                blocks.append(
                    {
                        "language": opener[1],
                        "open_line": opener[0],
                        "close_line": number,
                        "lines": body,
                    }
                )
                opener = None
                body = []
            continue
        if opener is not None:
            body.append(line)

    if opener is not None:
        raise ConversionError(
            "unclosed code fence opened at line {0}".format(opener[0])
        )
    return blocks


def conversion_input(markdown: str) -> str:
    """Exactly the fenced JSON block, and nothing else.

    This is the whole of the converter's input. The document's title and its
    Evidence Summary are never returned, never parsed and never seen by any
    other function here, so no argument for one side and no expected ruling can
    reach the converted case.

    Raises unless the document holds exactly one fenced JSON block, so a
    document that grew a second block fails loudly rather than having one of
    them chosen for it.
    """
    json_blocks = [block for block in fenced_blocks(markdown) if block["language"] == "json"]
    if len(json_blocks) != 1:
        raise ConversionError(
            "expected exactly one fenced json block, found {0}".format(len(json_blocks))
        )
    return "\n".join(json_blocks[0]["lines"])


def parse_source(block_text: str) -> Dict[str, Any]:
    """Parse the fenced block and require the key set it is supposed to have."""
    try:
        parsed = json.loads(block_text)
    except json.JSONDecodeError as exc:
        raise ConversionError("the fenced block is not valid JSON: {0}".format(exc)) from exc
    if not isinstance(parsed, dict):
        raise ConversionError("the fenced block is not a JSON object")
    missing = [key for key in SOURCE_KEYS if key not in parsed]
    if missing:
        raise ConversionError(
            "the fenced block is missing keys: {0}".format(", ".join(missing))
        )
    return parsed


# --------------------------------------------------------------------------
# The decision log
# --------------------------------------------------------------------------
class Decisions:
    """Every field of the converted case, and how it got its value.

    ``copied`` is used where the source states the value and the converted case
    carries it; ``judged`` is used where the conversion had to choose. The two
    are kept apart because the point of the mapping record is that a reader can
    see the choices and not only their results.
    """

    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def copied(self, target: str, source: str, value: Any, reason: str = "") -> Any:
        self.entries.append(
            {
                "target": target,
                "kind": "copied",
                "source": source,
                "value": _plain(value),
                "reason": reason or "the source states this value and the converted case carries it",
            }
        )
        return value

    def judged(self, target: str, value: Any, reason: str, source: Any = None) -> Any:
        self.entries.append(
            {
                "target": target,
                "kind": "judged",
                "source": source,
                "value": _plain(value),
                "reason": reason,
            }
        )
        return value


def _plain(value: Any) -> Any:
    """A value as the mapping record should show it."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    return value


# --------------------------------------------------------------------------
# Coverage: every source item is carried, or recorded as dropped
# --------------------------------------------------------------------------
def source_items(source: Dict[str, Any]) -> List[str]:
    """Every item in the source block, named the way the mapping names it.

    Scalars inside ``gps_telemetry`` and ``chat_logs`` are named once with a
    wildcard selector, because the conversion carries every element of those
    arrays through one code path: covering the key covers each element.

    ``app_events`` is different, and that is the point of this function. The
    conversion reads *named* events, so an event nobody read would hide behind a
    wildcard. Each event is therefore named individually, by its own
    ``event_type``.
    """
    items: List[str] = []

    def walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, "{0}.{1}".format(prefix, key) if prefix else key)
        else:
            items.append(prefix)

    for key, value in source.items():
        if key in ("gps_telemetry", "chat_logs"):
            for element in value:
                walk(element, key + "[*]")
        elif key == "app_events":
            for element in value:
                walk(element, "app_events[{0}]".format(element["event_type"]))
        else:
            walk(value, key)
    return sorted(set(items))


def named_items(mapping: Dict[str, Any]) -> List[str]:
    """Every source path the mapping record names.

    One entry may name several paths in its ``source``, separated by commas,
    which is how a value drawn from two places is recorded.
    """
    named: List[str] = []
    for entry in mapping["fields"]:
        source = entry.get("source")
        if isinstance(source, str):
            named.extend(part.strip() for part in source.split(","))
    return sorted(set(named))


def unrecorded_items(source: Dict[str, Any], mapping: Dict[str, Any]) -> List[str]:
    """Source items that are neither carried nor recorded as dropped."""
    named = set(named_items(mapping))
    return [item for item in source_items(source) if item not in named]


# What became of each app event the source records. The events the conversion
# reads are carried somewhere in the converted case; the rest have no field in
# either payload schema that can hold them and are dropped with the reason.
# An event type absent from this table is refused rather than dropped, so a
# source that grew an event cannot lose it quietly.
_APP_EVENT_DISPOSITION = {
    "booking_confirmed": (
        "Carried: its timestamp is EV-TRIP-{suffix}.payload.requested_at."
    ),
    "driver_assigned": (
        "Carried: its timestamp is EV-TRIP-{suffix}.payload.accepted_at."
    ),
    "driver_en_route": (
        "Read, not carried: EV-TRIP-{suffix}.payload.time_to_arrival_min is measured "
        "from its timestamp, and no field holds the event itself."
    ),
    "driver_arrived": (
        "Carried: its timestamp is EV-TRIP-{suffix}.payload.arrived_at, and its details "
        "are carried into EV-TRIP-{suffix}'s admissibility notes."
    ),
    "rider_notified": (
        "Dropped: no field in either payload schema holds a notification, and no limb "
        "of POL-NS-01 to POL-NS-09 reads one. It records the platform's act, not the "
        "rider's."
    ),
    "wait_timer_started": (
        "Dropped: no field holds a timer. The free-wait period it starts is the "
        "source platform's own rule rather than this system's, and POL-NS-01(c) "
        "measures the dwell from a GPS fix instead."
    ),
    "driver_called_rider": (
        "Carried: EV-TRIP-{suffix}.payload.in_app_calls[0] holds the call it records, "
        "with its time, initiator and duration."
    ),
    "wait_timer_expired": (
        "Dropped, for the same reason as wait_timer_started: no field holds a timer."
    ),
    "cancellation_fee_applied": (
        "Carried: its timestamp is EV-FARE-{suffix}.payload.charged_at and its amount is "
        "EV-FARE-{suffix}.payload.cancellation_fee."
    ),
    "driver_released": (
        "Dropped as an event: EV-TRIP-{suffix}.payload.status and cancelled_by carry the "
        "fact it records, and no field holds a release."
    ),
}


# What became of each app event the source records, at policy version 3. Every
# one is now carried in ``EV-TRIP-{suffix}.payload.events[]`` as well as wherever
# the version-1 conversion already put it, so no event is dropped any more. The
# table is kept separate from the version-1 one rather than rewritten, so that
# the version-1 mapping record still says what the version-1 conversion did.
_APP_EVENT_DISPOSITION_V3 = {
    kind: (
        "Carried in EV-TRIP-{suffix}.payload.events[] with its own event_type, "
        "timestamp and details. " + version_one
    )
    for kind, version_one in _APP_EVENT_DISPOSITION.items()
}


def _audit(
    decisions: Decisions, source: Dict[str, Any],
    policy_version: int = DEFAULT_POLICY_VERSION, suffix: str = "00901",
) -> None:
    """Record every source item the conversion reads and does not carry.

    A drop is a decision, so it goes on the record with its reason rather than
    disappearing. The events are recorded one at a time because the conversion
    reads them one at a time; a wildcard entry would hide an event nobody read.

    From policy version 3 three of the version-1 drops become copies: the
    scheduled time is carried as ``payload.scheduled_at``, the source's own
    cancellation-policy fields are carried in the ``platform_policy`` block, and
    the events are carried as ``payload.events[]``. Those entries are therefore
    not written for version 3 -- an entry saying a field was dropped, beside a
    field that carries it, would be a record that contradicts the case.
    """
    version_three = policy_version >= PLATFORM_POLICY_VERSION

    if not version_three:
        decisions.judged(
            "trip_data.scheduled_time", None,
            "Dropped: no field in this corpus's trip-record payload holds a scheduled "
            "pickup time, and no limb of POL-NS-01 to POL-NS-09 reads one. The source's "
            "08:45 schedule is quoted in policy_divergences, where the question it raises "
            "- whether a waiting clock runs from arrival or from the scheduled time - is "
            "recorded and left open rather than resolved here.",
            source="trip_data.scheduled_time",
        )

        for field, reason in (
            ("free_wait_time_min",
             "the source platform's own free-wait period, not this system's"),
            ("cancellation_fee_after_wait",
             "the source's own fee figure; the amount itself is carried on "
             "EV-FARE-{suffix}, and policy_divergences records that it does not "
             "reconcile with fee_schedule"),
            ("no_show_threshold_min",
             "the source's own threshold; this system's dwell minimum is read from "
             "fee_schedule at arbitration time, as policy_divergences records"),
            ("fee_goes_to",
             "the source's own instruction about where the fee goes; this system "
             "compensates the driver under POL-NS-07 at its own rate"),
        ):
            decisions.judged(
                "cancellation_policy." + field, None,
                "Dropped: {0}. No field of the converted case holds a source policy "
                "figure.".format(reason.format(suffix=suffix)),
                source="cancellation_policy." + field,
            )

    decisions.judged(
        "chat_logs[*].type", None,
        "Read, not carried: the type is what separates the log's messages from its "
        "call and from the platform's own entry, and each is carried where it belongs "
        "- the call as EV-TRIP-{suffix}.payload.in_app_calls[0], the rest as messages "
        "on EV-CHAT-{suffix}. Neither payload schema has a field for the type "
        "itself.".format(suffix=suffix),
        source="chat_logs[*].type",
    )
    decisions.judged(
        "rider_profile.fraud_flag_details", None,
        "Read, not carried: the text ('flagged_for_frequent_late_cancellations') is "
        "what identifies the rider's flag counter as belonging to the no-show family, "
        "which is why the counter is carried as prior_no_show_flags. This corpus's "
        "profile schema has no field for the detail text.",
        source="rider_profile.fraud_flag_details",
    )
    decisions.judged(
        "driver_profile.name", None,
        "Dropped: this corpus's profile schema has no field for a name, and no clause "
        "reads one. The same decision is recorded for the rider's name.",
        source="driver_profile.name",
    )
    decisions.judged(
        "driver_profile.dispute_history.rejected", None,
        "Dropped: this corpus's profile schema has no counterpart field. "
        "total_disputes and upheld_against carry the rest of the driver's history.",
        source="driver_profile.dispute_history.rejected",
    )

    dispositions = (
        _APP_EVENT_DISPOSITION_V3 if version_three else _APP_EVENT_DISPOSITION
    )
    for event in source["app_events"]:
        kind = event["event_type"]
        disposition = dispositions.get(kind)
        if disposition is None:
            raise ConversionError(
                "the source records an app event this converter has no disposition "
                "for, and it will not be dropped in silence: {0!r}".format(kind)
            )
        decisions.judged(
            "app_events[{0}]".format(kind), None,
            "This event is accounted for here, field by field. "
            + disposition.format(suffix=suffix),
            source=", ".join(
                "app_events[{0}].{1}".format(kind, field)
                for field in ("timestamp", "event_type", "details")
            ),
        )


# --------------------------------------------------------------------------
# Admissibility
# --------------------------------------------------------------------------
def admissibility(
    codes: List[str], notes: str, assessed_at: str
) -> Dict[str, Any]:
    """One admissibility block, with the weight derived from the codes.

    The weight is not written down here. It comes from
    ``prepass.weight_for``, the same function the corpus's own arithmetic was
    derived from, so a converted artifact cannot carry a weight the corpus's
    rule would not produce for the same codes.

    The import is deferred to call time on purpose: ``prepass`` lives under
    ``tribunal/``, and importing it at module scope would put a package import
    in a module that also names a path under ``eval/``.
    """
    from tribunal import prepass  # noqa: PLC0415 - see the docstring

    weight = prepass.weight_for(codes)
    if codes:
        status = "MISSING" if weight == 0.0 else "IMPAIRED"
    else:
        status = "COMPLETE"
    return {
        "status": status,
        "issues": list(codes),
        "weight_multiplier": weight,
        "notes": notes,
        "assessed_at": assessed_at,
        "assessor_version": ASSESSOR_VERSION,
    }


# --------------------------------------------------------------------------
# The version-7 fare rule
# --------------------------------------------------------------------------
# Ryde's fare records state the trip's totals and either a per-kilometre rate or
# an ``excess_distance_fare``, and itemise neither base, time nor platform-fee
# lines. Version 7 needs from them only the per-kilometre rate and the excess
# figures, and each record states what its own case needs, so at version 7 that
# gap is a difference of format rather than a gap in what v2.1 decides on. The
# two notes below are what each case's mapping records in place of the
# PARTIAL_RECORD the versions 1 and 3 conversions still read.
V7_FARE_ISSUE_NOTE = (
    "The record does not itemise base, time and platform-fee lines; version 7 "
    "needs only the per-kilometre rate and the excess figures, which it states "
    "(excess_distance_fare, and the rate in its notes), so it is not marked "
    "PARTIAL_RECORD at version 7."
)
V7_FEE_ISSUE_NOTE = (
    "The record itemises only the 5.00 cancellation fee; version 7 needs only "
    "that fee, and the record states it, so it is not marked PARTIAL_RECORD at "
    "version 7."
)


def _v7_fare_issue_codes() -> List[str]:
    """The issue codes a Ryde fare record carries at policy version 7: none.

    One rule for both samples, and the one place it lives. A fare record that
    states the trip's totals and either a per-kilometre rate or an
    ``excess_distance_fare`` is COMPLETE at version 7: the itemisation the source
    platform did not export is a difference of format, and v2.1 reads the rate
    and the excess figures, which the record states. So no code is minted and the
    artifact weighs what ``prepass.weight_for([])`` gives an empty set, 1.0,
    where versions 1 and 3 still read the same ledger as a PARTIAL_RECORD at
    0.75.

    A function rather than a constant so the rule has one name a reader -- and a
    test -- can point at: the version-7 fare tests remove it and show the two
    artifacts come back IMPAIRED.
    """
    return []


# --------------------------------------------------------------------------
# The conversion
# --------------------------------------------------------------------------
def convert(
    block_text: str, policy_version: int = DEFAULT_POLICY_VERSION
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build the converted case and its mapping record from the fenced block.

    ``policy_version`` selects what the conversion carries: version 1 is the case
    the recorded run read, and version 3 adds the sample's own platform
    parameters and its app-event log. An unknown version is refused rather than
    defaulted, so a typo cannot write the version-1 case under another name.
    """
    if policy_version not in POLICY_VERSIONS:
        raise ConversionError(
            "no conversion for policy version {0}; the versions are {1}".format(
                policy_version, ", ".join(str(item) for item in POLICY_VERSIONS)
            )
        )
    source = parse_source(block_text)
    decisions = Decisions()
    case_no = CASE_NO_FOR_VERSION[policy_version]
    directory = OUTPUT_DIR_FOR_VERSION[policy_version]
    # The suffix every minted artifact id carries. It is the case number, so the
    # ids of one converted case name that case and no other; versions 1 and 3
    # both convert DISP-002 as 901 and are byte-identical.
    suffix = "{0:05d}".format(case_no)

    ticket = source["dispute_ticket"]
    rider_profile = source["rider_profile"]
    driver_profile = source["driver_profile"]
    trip = source["trip_data"]
    fixes = source["gps_telemetry"]
    chats = source["chat_logs"]
    events = source["app_events"]
    policy = source["cancellation_policy"]

    trip_id = decisions.copied("trip_id", "dispute_ticket.trip_id", ticket["trip_id"])
    export_at = decisions.judged(
        "evidence[*].generated_at",
        ticket["filed_at"],
        "The source states no export time. The dispute's own filing time is used, "
        "because it is a real timestamp from the source and falls after every event "
        "the records describe, which is what an export time has to be.",
        source="dispute_ticket.filed_at",
    )
    assessed_at = decisions.judged(
        "evidence[*].admissibility.assessed_at",
        _plus_seconds(ticket["filed_at"], 5),
        "The admissibility pre-pass runs when the records are assembled. The corpus "
        "stamps its own blocks five seconds after generated_at, so the same offset is "
        "used rather than a second invented instant.",
    )

    artifacts = [
        _trip_record(
            decisions, trip, events, chats, ticket, export_at, assessed_at,
            policy, policy_version, suffix,
        ),
        _gps_trace(decisions, fixes, trip, trip_id, export_at, assessed_at, suffix),
        _chat_log(
            decisions, chats, trip_id, export_at, assessed_at, policy_version, suffix
        ),
        _fare(decisions, trip, export_at, assessed_at, policy_version, suffix),
        _rider(
            decisions, rider_profile, trip_id, export_at, assessed_at,
            policy_version, suffix,
        ),
        _driver(
            decisions, driver_profile, trip_id, export_at, assessed_at,
            policy_version, suffix,
        ),
        _advisory(decisions, trip_id, export_at, assessed_at, suffix),
    ]

    # Everything the conversion read and did not carry, recorded rather than
    # dropped in silence. It runs after the artifacts so the mapping reads as
    # the case first and the audit of what it left out second.
    _audit(decisions, source, policy_version, suffix)

    evidence_ids = [artifact["evidence_id"] for artifact in artifacts]

    dispute = {
        "dispute_id": decisions.copied(
            "dispute.dispute_id", "dispute_ticket.dispute_id", ticket["dispute_id"]
        ),
        "trip_id": trip_id,
        "case_no": decisions.judged(
            "dispute.case_no",
            case_no,
            "A converted case is numbered outside the corpus range (101-115, "
            "201-214) so it can never be mistaken for a corpus case.",
        ),
        "category": decisions.judged(
            "dispute.category",
            CATEGORY,
            "The source calls this dispute_type 'no_show_charge'. NO_SHOW_CHARGE is "
            "this system's token for that, and it is what selects policy/no_show.json.",
            source="dispute_ticket.dispute_type",
        ),
        "filed_by": decisions.judged(
            "dispute.filed_by",
            ticket["filed_by"].upper(),
            "Copied in substance and upper-cased: the source writes 'rider' and this "
            "corpus's vocabulary is RIDER.",
            source="dispute_ticket.filed_by",
        ),
        "filed_at": decisions.copied(
            "dispute.filed_at", "dispute_ticket.filed_at", ticket["filed_at"]
        ),
        "claim_text": decisions.copied(
            "dispute.claim_text", "dispute_ticket.description", ticket["description"]
        ),
        "amount_contested_sgd": decisions.judged(
            "dispute.amount_contested_sgd",
            float(trip["cancellation_fee"]),
            "The source has no 'amount contested' field. The cancellation fee is what "
            "the rider's claim asks to have reversed, and it is the figure the fare "
            "breakdown charges, so it is the figure contested.",
            source="trip_data.cancellation_fee",
        ),
        "counterparty_statement": decisions.judged(
            "dispute.counterparty_statement",
            None,
            "The source carries no statement from the driver. It is left null rather "
            "than substituted with an empty string or reconstructed from the chat log, "
            "which is a different artifact.",
        ),
        "channel": decisions.judged(
            "dispute.channel",
            "IN_APP_SUPPORT",
            "The source states no filing channel. IN_APP_SUPPORT is this corpus's value "
            "in 28 of 29 cases and the dispute is an in-app dispute; the field is "
            "presentation and no clause in either policy reads it.",
        ),
        "evidence_ids": decisions.judged(
            "dispute.evidence_ids",
            evidence_ids,
            "The ids are minted by this conversion. The corpus cites every artifact the "
            "case holds, so every minted artifact is cited.",
        ),
    }

    case = {
        "schema_version": decisions.copied(
            "schema_version", "the corpus contract", SCHEMA_VERSION,
            "data/PUBLIC-CONTRACT.md fixes the top-level value as \"1.2.0\" in all 29 "
            "corpus cases; a converted case is not a corpus case and may differ.",
        ),
        "case_no": case_no,
        "dispute": dispute,
        "evidence": artifacts,
    }

    mapping = {
        "source_document": "eval/external/ryde/DISP-002.md",
        "source_dispute_id": ticket["dispute_id"],
        "converted_case_no": case_no,
        "converted_case_file": "external/{0}/case-{1:05d}.json".format(
            directory.name, case_no
        ),
        "note": (
            "Every field of the converted case, with whether the conversion copied it "
            "or judged it, and why. The source's title and Evidence Summary are not "
            "listed anywhere here because nothing in them reached the conversion."
        ),
        "fields": decisions.entries,
        "policy_divergences": _divergences(trip, policy, policy_version),
        "assumptions": [
            {
                "assumption": "pickup zone class is STANDARD",
                "depends_on_it": [
                    "fee_schedule.zone_class_fee_sgd for STANDARD (4.00)",
                    "fee_schedule.minimum_dwell_sec for STANDARD (300 s)",
                    "fee_schedule.arrival_radius_m for STANDARD (50 m)",
                    "fee_schedule.rider_presence_radius_m for STANDARD (100 m)",
                    "the POL-NS-01 dwell comparison and the POL-NS-08(d) fee comparison",
                ],
                "reason": (
                    "The source gives a pickup place name and no zone class. Inferring "
                    "one from what the place is would be world knowledge about places, "
                    "which this repository's prompts forbid."
                ),
            },
            {
                "assumption": "vehicle tier is RYDE_X",
                "depends_on_it": [
                    "fee_schedule.vehicle_tier_fee_sgd for RYDE_X (4.00)",
                    "the POL-NS-08(d) fee comparison",
                ],
                "reason": (
                    "The source names a Honda HR-V, which is not a tier name in this "
                    "corpus. RYDE_X is this corpus's base tier; the choice is recorded "
                    "because the fee comparison turns on it."
                ),
            },
        ],
    }
    if policy_version >= PLATFORM_POLICY_VERSION:
        # Recorded on the version-3 mapping only. The version-1 mapping is the
        # record the recorded run was read against, and it stays byte-identical.
        mapping["policy_version"] = policy_version
    return case, mapping


def _plus_seconds(stamp: str, seconds: int) -> str:
    """An ISO-8601 stamp moved by whole seconds, keeping its offset text."""
    from datetime import datetime, timedelta

    parsed = datetime.fromisoformat(stamp)
    return (parsed + timedelta(seconds=seconds)).isoformat()


# --------------------------------------------------------------------------
# What policy version 3 adds to the trip record
# --------------------------------------------------------------------------
# The source's own platform parameters, in the contract's field names, plus the
# platform's app-event log. Version 1 carries neither, and nothing below runs for
# it: the version-1 case is the case the recorded run read and stays
# byte-identical.
PLATFORM_POLICY_SOURCE = "RECORD-PLATFORM"
SECONDS_PER_MINUTE = 60
PLATFORM_TELEMETRY_SOURCE = "PLATFORM_TELEMETRY"

# The channel a placed call is carried under in the chat log, and the channel a
# message is carried under. Both are this corpus's own field values, not v2.1's:
# POL-NS-23 reads a call from either ``trip_record.in_app_calls`` or a voice-call
# entry in the chat log, and ``tribunal.facts`` names the same token.
CALL_LOG_CHANNEL = "VOICE_CALL_LOG"
MESSAGE_CHANNEL = "IN_APP"

# The two source strings that carry material this repository drops elsewhere: the
# driver's name (as ``driver_profile.name`` is dropped) and the rider's payment
# method (as ``rider_profile.payment_method`` is). Both are removed from the
# event text, so the platform's own log can be carried without carrying them.
DROPPED_EVENT_FRAGMENTS = ("Lim Wei Ming, ", " (e-wallet)")


def _redacted(detail: str) -> str:
    """One event detail with the dropped fragments removed."""
    for fragment in DROPPED_EVENT_FRAGMENTS:
        detail = detail.replace(fragment, "")
    return detail


def _platform_policy_block(
    decisions: Decisions, policy: Dict[str, Any], arrival_details: str,
    suffix: str = "00901",
) -> Dict[str, Any]:
    """``trip_record.platform_policy``, the block policy version 3 adds.

    Three of the ten fields are the sample's own and are copied: the free wait
    and the no-show threshold, which the source states in minutes and the
    contract in seconds, and the fee. ``fee_goes_to`` is the source's instruction
    translated into the contract's token. The rest are judged, and each is
    recorded as judged: the two grace windows are the loaded policy's published
    defaults, written in so that the block is complete, and the arrival marker is
    read off the source's own arrival event, which says the arrival was
    auto-confirmed from a GPS measurement rather than a button press. The source
    is an opaque code, because the block reaches the model.
    """
    return {
        "grace_after_match_sec": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.platform_policy.grace_after_match_sec",
            180,
            "The source states no grace after matching. fee_schedule.defaults "
            "(Ryde's published 3 minutes) is written in so that the block is "
            "complete; POL-NS-10(a) reads it.",
        ),
        "advance_grace_before_scheduled_sec": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.platform_policy."
            "advance_grace_before_scheduled_sec",
            900,
            "The source states no advance grace for a scheduled trip. "
            "fee_schedule.defaults (Ryde's published 15 minutes) is written in, as "
            "above; POL-NS-10(b) reads it.",
        ),
        "free_wait_sec": decisions.copied(
            "evidence.EV-TRIP-" + suffix + ".payload.platform_policy.free_wait_sec",
            "cancellation_policy.free_wait_time_min",
            int(policy["free_wait_time_min"]) * SECONDS_PER_MINUTE,
            "The source states {0} minutes; carried as seconds, because "
            "POL-NS-01(c) reads a free waiting period in seconds and this is the "
            "period the sample's own wait timer runs.".format(
                policy["free_wait_time_min"]
            ),
        ),
        "no_show_threshold_sec": decisions.copied(
            "evidence.EV-TRIP-" + suffix + ".payload.platform_policy.no_show_threshold_sec",
            "cancellation_policy.no_show_threshold_min",
            int(policy["no_show_threshold_min"]) * SECONDS_PER_MINUTE,
            "The source states {0} minutes; POL-NS-01(c) requires the cancellation "
            "to fall at or after it where it is longer than free_wait_sec, and the "
            "sample's cancellation at 08:51:00 falls exactly on it.".format(
                policy["no_show_threshold_min"]
            ),
        ),
        "cancellation_fee_sgd": decisions.copied(
            "evidence.EV-TRIP-" + suffix + ".payload.platform_policy.cancellation_fee_sgd",
            "cancellation_policy.cancellation_fee_after_wait",
            policy["cancellation_fee_after_wait"],
            "The source states the fee; fee_schedule.resolution_rule now reads this "
            "field first, which resolves the version-1 divergence between the "
            "sample's figure and the schedule's.",
        ),
        "rider_gross_cancellation_fee_sgd": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.platform_policy."
            "rider_gross_cancellation_fee_sgd",
            None,
            "The source gives one figure only: no rider-side gross amount is "
            "stated, and none is derived. Null rather than the fee repeated.",
        ),
        "waiting_fee_sgd": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.platform_policy.waiting_fee_sgd",
            None,
            "The source states no waiting-time fee. POL-NS-10(d) reads this field, "
            "so a figure here would decide a limb on a value nobody recorded.",
        ),
        "fee_goes_to": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.platform_policy.fee_goes_to",
            "DRIVER",
            "The source writes 'driver_compensation'; DRIVER is this contract's "
            "token for the same instruction, and POL-NS-07 compensates the driver "
            "under it.",
            source="cancellation_policy.fee_goes_to",
        ),
        "arrival_marker": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.platform_policy.arrival_marker",
            "GPS_AUTO",
            "Read off the source's own arrival event, whose text is {0!r}: the "
            "marker was auto-confirmed from a GPS measurement rather than a driver "
            "button press, so GPS_AUTO is the marker this record carries.".format(
                arrival_details
            ),
            source="app_events[driver_arrived].details",
        ),
        "source": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.platform_policy.source",
            PLATFORM_POLICY_SOURCE,
            "An opaque code: the block came from the record itself. The "
            "human-readable provenance is in the mapping record and never in the "
            "case file, because the block reaches the model.",
        ),
    }


def _event_log(
    decisions: Decisions, events: List[Dict[str, Any]], by_type: Dict[str, Any],
    suffix: str = "00901",
) -> List[Dict[str, Any]]:
    """The source's app-event log, in the contract's ``events[]`` shape.

    Every event the source records is carried, in the source's own order, with
    its ``event_type``, its timestamp as ``at``, its detail and the evidence
    source ``PLATFORM_TELEMETRY``. Two details are redacted; both redactions are
    recorded separately below, because they are decisions about the text rather
    than about the event.
    """
    log = [
        {
            "event_type": event["event_type"],
            "at": event["timestamp"],
            "detail": _redacted(event["details"]),
            "source": PLATFORM_TELEMETRY_SOURCE,
        }
        for event in events
    ]
    decisions.judged(
        "evidence.EV-TRIP-" + suffix + ".payload.events[*]",
        log,
        "Copied: the source's platform event log, {0} events, each with its own "
        "event_type, timestamp and details and the evidence source "
        "PLATFORM_TELEMETRY. The version-1 conversion dropped it, which left the "
        "dwell carried by the GPS trace alone and capped confidence at the "
        "trace's 0.6 weight under POL-GEN-02(2); with the platform's own "
        "wait-timer events present the dwell has two independent carriers.".format(
            len(log)
        ),
        source=", ".join(
            "app_events[{0}]".format(event["event_type"]) for event in events
        ),
    )
    decisions.judged(
        "evidence.EV-TRIP-" + suffix + ".payload.events[driver_assigned].detail",
        _redacted(by_type["driver_assigned"]["details"]),
        "The driver's name is dropped from the event text, as driver_profile.name "
        "already is. The plate stays, as it does in the chat_log.",
        source="app_events[driver_assigned].details",
    )
    decisions.judged(
        "evidence.EV-TRIP-" + suffix + ".payload.events[cancellation_fee_applied].detail",
        _redacted(by_type["cancellation_fee_applied"]["details"]),
        "The rider's payment method is dropped from the event text, as "
        "rider_profile.payment_method already is.",
        source="app_events[cancellation_fee_applied].details",
    )
    return log


def _trip_record(
    decisions: Decisions, trip: Dict[str, Any], events: List[Dict[str, Any]],
    chats: List[Dict[str, Any]], ticket: Dict[str, Any], export_at: str,
    assessed_at: str, policy: Optional[Dict[str, Any]] = None,
    policy_version: int = DEFAULT_POLICY_VERSION, suffix: str = "00901",
) -> Dict[str, Any]:
    """TRIP_RECORD, assembled from trip_data and the app events.

    From policy version 3 the record also carries ``scheduled_at``, the
    ``platform_policy`` block and the platform's own ``events[]``. Version 1
    carries none of them, so the case the recorded run read is byte-identical.
    """
    by_type = {event["event_type"]: event for event in events}
    arrival_details = by_type["driver_arrived"]["details"]

    def at(event_type: str) -> Optional[str]:
        event = by_type.get(event_type)
        return event["timestamp"] if event else None

    requested_at = decisions.copied(
        "evidence.EV-TRIP-" + suffix + ".payload.requested_at",
        "app_events[booking_confirmed].timestamp", at("booking_confirmed"),
    )
    accepted_at = decisions.copied(
        "evidence.EV-TRIP-" + suffix + ".payload.accepted_at",
        "app_events[driver_assigned].timestamp", at("driver_assigned"),
    )
    arrived_at = decisions.copied(
        "evidence.EV-TRIP-" + suffix + ".payload.arrived_at",
        "trip_data.driver_arrival_time, app_events[driver_arrived].timestamp",
        trip["driver_arrival_time"],
        "Copied from the source's own arrival time. The driver_arrived event states "
        "the same instant, so both are named here rather than the second being left "
        "unrecorded.",
    )
    cancelled_at = decisions.copied(
        "evidence.EV-TRIP-" + suffix + ".payload.cancelled_at",
        "trip_data.cancellation_time", trip["cancellation_time"],
    )

    wait_min = decisions.judged(
        "evidence.EV-TRIP-" + suffix + ".payload.wait_time_min",
        round(_seconds_between(trip["driver_wait_start"], trip["cancellation_time"]) / 60.0, 1),
        "Computed from the source's own wait start (08:43) and cancellation (08:51), "
        "which is 480 s. The source states no wait figure.",
        source="trip_data.driver_wait_start, trip_data.cancellation_time",
    )
    to_arrival = decisions.judged(
        "evidence.EV-TRIP-" + suffix + ".payload.time_to_arrival_min",
        round(_seconds_between(at("driver_en_route"), trip["driver_arrival_time"]) / 60.0, 1),
        "Computed from the source's own en-route event (08:30:20) to arrival (08:43), "
        "which is 760 s. The source states no arrival-time figure.",
    )

    payload = {
        "trip_id": decisions.copied(
            "evidence.EV-TRIP-" + suffix + ".payload.trip_id", "trip_data.trip_id", trip["trip_id"]
        ),
        "rider_id": decisions.copied(
            "evidence.EV-TRIP-" + suffix + ".payload.rider_id",
            "trip_data.rider_id", trip["rider_id"],
            "Copied unchanged. The source's id form (R-7823) differs from this "
            "corpus's (RDR-02073); the value is carried as given rather than "
            "re-formatted, because the form is not this converter's to change.",
        ),
        "driver_id": decisions.copied(
            "evidence.EV-TRIP-" + suffix + ".payload.driver_id",
            "trip_data.driver_id", trip["driver_id"],
            "Copied unchanged, for the same reason as rider_id (source form D-2398).",
        ),
        "requested_at": requested_at,
        "accepted_at": accepted_at,
        "arrived_at": arrived_at,
        "started_at": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.started_at", None,
            "The trip never started: it was cancelled on a rider no-show. Null is what "
            "the corpus records for a trip that did not run.",
        ),
        "ended_at": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.ended_at", None,
            "The trip never ended because it never started.",
        ),
        "cancelled_at": cancelled_at,
        "status": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.status",
            "CANCELLED_BY_DRIVER",
            "The source's system message says 'Trip cancelled by driver'. "
            "CANCELLED_BY_DRIVER is this corpus's token for that.",
            source="chat_logs[system].content",
        ),
        "cancelled_by": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.cancelled_by",
            "DRIVER",
            "Same fact as status, in the corpus's separate field.",
            source="chat_logs[system].content",
        ),
        "cancellation_reason_code": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.cancellation_reason_code",
            "RIDER_NO_SHOW",
            "The source writes 'rider_no_show'; RIDER_NO_SHOW is this corpus's token. "
            "It is one of the three codes POL-NS-01(d) admits.",
            source="trip_data.cancellation_reason",
        ),
        "pickup": {
            "label": decisions.copied(
                "evidence.EV-TRIP-" + suffix + ".payload.pickup.label",
                "trip_data.pickup_location.name", trip["pickup_location"]["name"],
            ),
            "lat": decisions.copied(
                "evidence.EV-TRIP-" + suffix + ".payload.pickup.lat",
                "trip_data.pickup_location.lat", trip["pickup_location"]["lat"],
            ),
            "lng": decisions.copied(
                "evidence.EV-TRIP-" + suffix + ".payload.pickup.lng",
                "trip_data.pickup_location.lng", trip["pickup_location"]["lng"],
            ),
            "venue_id": decisions.judged(
                "evidence.EV-TRIP-" + suffix + ".payload.pickup.venue_id", None,
                "The source carries no venue identifier. Minting one would let "
                "POL-NS-03's venue_id corroboration test run on a value nobody "
                "recorded, which is the one thing that test must not do.",
            ),
        },
        "dropoff": {
            "label": decisions.copied(
                "evidence.EV-TRIP-" + suffix + ".payload.dropoff.label",
                "trip_data.dropoff_location.name", trip["dropoff_location"]["name"],
            ),
            "lat": decisions.copied(
                "evidence.EV-TRIP-" + suffix + ".payload.dropoff.lat",
                "trip_data.dropoff_location.lat", trip["dropoff_location"]["lat"],
            ),
            "lng": decisions.copied(
                "evidence.EV-TRIP-" + suffix + ".payload.dropoff.lng",
                "trip_data.dropoff_location.lng", trip["dropoff_location"]["lng"],
            ),
            "venue_id": decisions.judged(
                "evidence.EV-TRIP-" + suffix + ".payload.dropoff.venue_id", None,
                "The source carries no venue identifier, for the same reason as pickup.",
            ),
        },
        "vehicle_type": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.vehicle_type",
            ASSUMED_VEHICLE_TIER,
            "The source names a Honda HR-V, which is not a tier in this corpus. "
            "RYDE_X is the base tier; the fee comparison under POL-NS-08(d) depends "
            "on this choice and it is recorded as an assumption.",
            source="driver_profile.vehicle",
        ),
        "pickup_zone_class": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.pickup_zone_class",
            ASSUMED_ZONE_CLASS,
            "The source states no zone class. STANDARD is used as an explicitly stated "
            "assumption and not inferred from the place name, because inferring it "
            "would be world knowledge about places. The dwell minimum, the arrival "
            "radius and the zone fee all depend on it.",
        ),
        "chat_message_count": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.chat_message_count",
            len(chats),
            "The count of chat_logs entries the source supplies, which is what "
            "POL-NS-08(c) compares the chat artifact against.",
        ),
        "registered_pickup_points": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.registered_pickup_points", None,
            "The source does not say how many registered pickup points the location "
            "has. POL-NS-03(ii) reads this field, so a minted 1 or 2 would decide a "
            "limb on a value nobody recorded.",
        ),
        "in_app_calls": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.in_app_calls",
            [_call_record(decisions, chats, suffix)],
            "The source records one in-app call in chat_logs. POL-NS-04(b) reads this "
            "field, so the call the source does describe is carried rather than left "
            "out of the trip record.",
        ),
    }

    for field, reason in (
        ("optimal_distance_km", "no route was quoted in the source"),
        ("optimal_duration_min", "no route was quoted in the source"),
        ("optimal_route_source", "no routing engine is named in the source"),
        ("optimal_route_erp_sgd", "no ERP figure is given in the source"),
        ("actual_distance_km", "the trip was cancelled before it ran"),
        ("actual_duration_min", "the trip was cancelled before it ran"),
        ("deviation_pct", "a route-deviation figure has no meaning on a no-show"),
        ("amended_optimal_distance_km", "the pickup was never amended"),
        ("amended_optimal_duration_min", "the pickup was never amended"),
        ("solo_optimal_distance_km", "there is no co-rider data in the source"),
    ):
        payload[field] = decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload." + field, None,
            "Null rather than a plausible figure: {0}.".format(reason),
        )
    for field in ("pickup_amended_at", "dropoff_amended_at", "original_pickup", "original_dropoff"):
        payload[field] = decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload." + field, None,
            "Null: the source records no amendment to either end of the trip.",
        )

    if policy_version >= PLATFORM_POLICY_VERSION:
        # The three fields policy version 3 adds, in the order the contract's
        # trip record lists them. Nothing above changes for version 1.
        payload["scheduled_at"] = decisions.copied(
            "evidence.EV-TRIP-" + suffix + ".payload.scheduled_at",
            "trip_data.scheduled_time", trip["scheduled_time"],
            "The source states it; the version-1 conversion dropped it. POL-NS-10(b) "
            "reads it, and POL-NS-01(c) uses it to say where a scheduled trip's "
            "waiting clock starts.",
        )
        payload["platform_policy"] = _platform_policy_block(
            decisions, policy or {}, arrival_details, suffix
        )
        payload["events"] = _event_log(decisions, events, by_type, suffix)

    # The one deviation from the corpus's own shape that is worth stating in
    # full, because a reader comparing the two would otherwise have to find it.
    decisions.judged(
        "evidence.EV-TRIP-" + suffix + ".payload.optimal_distance_km, optimal_duration_min, "
        "optimal_route_source, optimal_route_erp_sgd",
        None,
        "These four are null here, and are null in NO corpus trip record: all 29 carry "
        "a quoted route. The deviation is deliberate and is NOT marked as an "
        "admissibility defect. No limb of POL-NS-01 to POL-NS-09 reads a route field on "
        "a no-show, because the trip was cancelled before it ran; the absence is a "
        "property of the source platform's export rather than of the record; and no "
        "issue code is minted for it, because the corpus's PARTIAL_RECORD was applied to "
        "a ledger missing its itemisation, not to a field the source platform does not "
        "export. Filling them with a plausible route would be inventing the quote.",
    )

    # The one app event whose text is case material rather than a duplicate of a
    # timestamp: the platform's own account of how the arrival marker was made.
    # Carried, and carried as what it is -- a distance claim, not an accuracy.
    decisions.judged(
        "evidence.EV-TRIP-" + suffix + ".admissibility.notes", None,
        "The source's driver_arrived details are carried into this artifact's "
        "admissibility notes, verbatim and labelled. The text is {0!r}. It is the "
        "platform's own DISTANCE claim and NOT a reported horizontal accuracy: it "
        "supplies no fix with a reported accuracy, it is not turned into a GPS fix of "
        "its own, and it makes no fix qualifying under POL-NS-02. Its consequence is "
        "recorded too, because it bears on independence: the arrival marker was "
        "produced from the same GPS measurement the trace is built from, so under "
        "POL-GEN-02 the marker and the trace are ONE carrier and not two.".format(
            arrival_details
        ),
        source="app_events[driver_arrived].details",
    )

    notes = (
        "The source's own trip record, causally ordered. Arrival marker 08:43:00 is "
        "the nearest GPS fix timestamp to the second, so the POL-NS-08(a) 90 s clock "
        "limb is not engaged. The source's own driver_arrived event reads {0!r}: the "
        "marker was auto-confirmed from a GPS measurement, so under POL-GEN-02 the "
        "marker and the trace are one carrier rather than two, and the ten-metre "
        "figure is the platform's distance claim rather than a reported horizontal "
        "accuracy, so no fix here is measurable under POL-NS-02 and none establishes "
        "arrival. pickup_zone_class and vehicle_type are stated assumptions, recorded "
        "in the mapping record; the source gives neither."
    ).format(arrival_details)
    return _artifact(
        decisions, "EV-TRIP-" + suffix, "TRIP_RECORD", "PLATFORM_TELEMETRY",
        trip["trip_id"], export_at, payload, [], notes, assessed_at,
    )


def _call_record(
    decisions: Decisions, chats: List[Dict[str, Any]], suffix: str = "00901"
) -> Dict[str, Any]:
    """The one in-app call the source describes, in the corpus's call shape."""
    call = next(entry for entry in chats if entry["type"] == "call")
    return {
        "call_id": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.in_app_calls[0].call_id",
            "CALL-" + suffix + "-001",
            "Minted. The source describes the call but gives it no identifier.",
        ),
        "initiated_at": decisions.copied(
            "evidence.EV-TRIP-" + suffix + ".payload.in_app_calls[0].initiated_at",
            "chat_logs[call].timestamp", call["timestamp"],
        ),
        "initiated_by": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.in_app_calls[0].initiated_by",
            "DRIVER",
            "The source says 'Outgoing call to rider' and the sender is the driver.",
            source="chat_logs[call].sender",
        ),
        "answered": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.in_app_calls[0].answered", False,
            "The source says the call was not answered.",
            source="chat_logs[call].content",
        ),
        "duration_sec": decisions.judged(
            "evidence.EV-TRIP-" + suffix + ".payload.in_app_calls[0].duration_sec",
            _rang_seconds(call["content"]),
            "Read out of the source's own description ('rang 22s, no response'), "
            "because the source states it only in prose and nowhere as a field.",
            source="chat_logs[call].content",
        ),
    }


def _channel_for(entry: Dict[str, Any], policy_version: int) -> str:
    """The channel one chat entry is carried under.

    ``VOICE_CALL_LOG`` is this corpus's own channel for a placed call, and the
    only entry it applies to is the one the source types ``call`` -- and only
    from policy version 7, where POL-NS-23 reads a call from the chat log as
    well as from ``trip_record.in_app_calls``.
    """
    if policy_version >= V7_POLICY_VERSION and entry.get("type") == "call":
        return CALL_LOG_CHANNEL
    return "IN_APP"


def _rang_seconds(content: str) -> Optional[int]:
    """The seconds in 'rang 22s', or None when the prose does not say."""
    import re

    match = re.search(r"rang\s+(\d+)\s*s", content)
    return int(match.group(1)) if match else None


def _gps_trace(
    decisions: Decisions, fixes: List[Dict[str, Any]], trip: Dict[str, Any],
    trip_id: str, export_at: str, assessed_at: str, suffix: str = "00901",
) -> Dict[str, Any]:
    """GPS_TRACE, with the accuracy the source does not have left absent."""
    timestamps = [fix["timestamp"] for fix in fixes]
    intervals = [
        _seconds_between(timestamps[index], timestamps[index + 1])
        for index in range(len(timestamps) - 1)
    ]
    median = statistics.median(intervals)
    # Both counts are derived here and read from these two lists everywhere the
    # note and the mapping state them. They were once typed into the prose, and
    # the typed figure was wrong: the note said three of the seven intervals
    # exceeded the limb while the payload's own list held five.
    over_limb = [interval for interval in intervals if interval > 120]
    in_window = [
        fix
        for fix in fixes
        if trip["driver_wait_start"] <= fix["timestamp"] <= trip["cancellation_time"]
    ]

    points = []
    for fix in fixes:
        point = {
            "lat": decisions.copied(
                "evidence.EV-GPS-" + suffix + ".payload.points[*].lat", "gps_telemetry[*].lat", fix["lat"]
            ),
            "lng": decisions.copied(
                "evidence.EV-GPS-" + suffix + ".payload.points[*].lng", "gps_telemetry[*].lng", fix["lng"]
            ),
            "ts": decisions.copied(
                "evidence.EV-GPS-" + suffix + ".payload.points[*].ts",
                "gps_telemetry[*].timestamp", fix["timestamp"],
            ),
            "speed_kph": decisions.copied(
                "evidence.EV-GPS-" + suffix + ".payload.points[*].speed_kph",
                "gps_telemetry[*].speed_kmh", fix["speed_kmh"],
            ),
        }
        # NOT added: accuracy_m. The source has no accuracy value for any fix, and
        # supplying one would be inventing the very field POL-NS-02 tests. Under
        # that clause a fix without reported accuracy is evidence of neither
        # presence nor absence, so none of these fixes establishes arrival. That
        # is the intended consequence, not a defect to repair.
        # NOT added: heading_deg. The source carries no heading; the corpus's point
        # schema has the field but this converter does not invent a value for it.
        decisions.judged(
            "evidence.EV-GPS-" + suffix + ".payload.points[*].status",
            None,
            "The source's per-fix 'status' (en_route / arrived / waiting / cancelled) "
            "has no counterpart in this corpus's point schema. It is dropped rather "
            "than carried as a ninth key, and the drop is recorded here. The "
            "information is not lost: speed_kph separates moving from stationary.",
            source="gps_telemetry[*].status",
        )
        points.append(point)

    payload = {
        "trip_id": trip_id,
        "points": points,
        "point_count": decisions.judged(
            "evidence.EV-GPS-" + suffix + ".payload.point_count", len(points),
            "The number of fixes the source supplies.",
        ),
        "first_fix_at": decisions.judged(
            "evidence.EV-GPS-" + suffix + ".payload.first_fix_at", timestamps[0],
            "The first fix timestamp the source supplies.",
        ),
        "last_fix_at": decisions.judged(
            "evidence.EV-GPS-" + suffix + ".payload.last_fix_at", timestamps[-1],
            "The last fix timestamp the source supplies.",
        ),
        "sample_interval_sec": decisions.judged(
            "evidence.EV-GPS-" + suffix + ".payload.sample_interval_sec", float(median),
            "Measured from the source's own timestamps: the intervals between "
            "consecutive fixes are {0} s, whose median is {1} s. The source states no "
            "nominal rate.".format(intervals, median),
        ),
        "expected_interval_sec": decisions.judged(
            "evidence.EV-GPS-" + suffix + ".payload.expected_interval_sec", None,
            "The source names no nominal sampling rate, so there is nothing to call "
            "expected. Setting one would make the measured interval look like a "
            "deviation from a standard the source never claimed.",
        ),
        "gaps": decisions.judged(
            "evidence.EV-GPS-" + suffix + ".payload.gaps",
            [
                {"from": timestamps[index], "to": timestamps[index + 1], "gap_sec": float(interval)}
                for index, interval in enumerate(intervals)
                if interval > 120
            ],
            "Intervals longer than POL-NS-08(b)'s own 120 s limb, measured from the "
            "source's timestamps: {0} of the {1} exceed it.".format(
                len(over_limb), len(intervals)
            ),
        ),
        "max_gap_sec": decisions.judged(
            "evidence.EV-GPS-" + suffix + ".payload.max_gap_sec", float(max(intervals)),
            "The longest interval measured from the source's timestamps.",
        ),
        "coverage_pct": decisions.judged(
            "evidence.EV-GPS-" + suffix + ".payload.coverage_pct", None,
            "Coverage is a ratio against an expected rate. The source names no rate, "
            "so a percentage would be computed against a denominator nobody supplied.",
        ),
        "trace_distance_km": decisions.judged(
            "evidence.EV-GPS-" + suffix + ".payload.trace_distance_km", None,
            "The source gives no distance, and summing eight fixes three minutes apart "
            "would understate the driven path by an unknown amount.",
        ),
        "rider_track": decisions.judged(
            "evidence.EV-GPS-" + suffix + ".payload.rider_track", [],
            "There is no rider GPS track in the source. An empty list is carried "
            "rather than points minted, because minting them would decide POL-NS-04(c) "
            "and the rider-presence test on evidence nobody recorded. The consequence "
            "is intended: POL-NS-04(c) is UNDECIDABLE on this trace, and POL-NS-08(b) "
            "is engaged because the trace omits a rider_track.",
        ),
    }
    notes = (
        "Sparse telemetry with no reported accuracy. The intervals between the "
        "source's own timestamps are {0} s, {1} of the {2} exceeding POL-NS-08(b)'s "
        "120 s gap limb, and the waiting window from arrival to cancellation holds "
        "{3} fixes, fewer than the six that limb requires. The trace is impaired for "
        "policy, not merely for admissibility, and POL-NS-08(b)'s rider_track limb is "
        "engaged too, because no rider track was supplied. No fix carries accuracy_m, "
        "so under POL-NS-02 every one of them is evidence of neither presence nor "
        "absence and none establishes arrival. The fixes are the driver's alone; the "
        "driver's own arrival marker still comes from trip_record.".format(
            intervals, len(over_limb), len(intervals), len(in_window)
        )
    )
    return _artifact(
        decisions, "EV-GPS-" + suffix, "GPS_TRACE", "DRIVER_DEVICE",
        trip_id, export_at, payload, ["LOW_SAMPLE_RATE", "PARTIAL_RECORD"],
        notes, assessed_at,
    )


def _chat_log(
    decisions: Decisions, chats: List[Dict[str, Any]], trip_id: str,
    export_at: str, assessed_at: str, policy_version: int = DEFAULT_POLICY_VERSION,
    suffix: str = "00901",
) -> Dict[str, Any]:
    """CHAT_LOG, with the six entries the source supplies.

    From policy version 7 the entry the source types ``call`` carries the
    channel ``VOICE_CALL_LOG`` rather than ``IN_APP``. POL-NS-23 reads a placed
    call from ``trip_record.in_app_calls`` **or** from a voice-call entry in the
    chat log, and it never counts such an entry as a message: with the call
    marked as a call, the driver's four messages and one call are counted as
    four and one, which is what the source's own evidence summary states. The
    entry stays in the log either way, so no message is dropped. Versions 1 and
    3 are byte-identical: they write ``IN_APP`` for every entry.
    """
    sender_map = {"driver": "DRIVER", "rider": "RIDER", "system": "SYSTEM"}
    # The channel entry's own text, chosen by version so that the version-1 and
    # version-3 mapping records are byte for byte the records they were.
    channel_reason = (
        "The source's chat log is the in-app log and carries no channel field. "
        "From policy version 7 the entry it types 'call' is carried as "
        "VOICE_CALL_LOG, because POL-NS-23 reads a placed call from there and never "
        "counts one as a message; versions 1 and 3 write IN_APP for every entry."
        if policy_version >= V7_POLICY_VERSION
        else "The source's chat log is the in-app log; it carries no channel field."
    )
    channel_source = "chat_logs[*].type" if policy_version >= V7_POLICY_VERSION else None
    messages = []
    for index, entry in enumerate(chats, start=1):
        sender = sender_map.get(entry["sender"])
        if sender is None:
            raise ConversionError("unknown chat sender {0!r}".format(entry["sender"]))
        messages.append(
            {
                "msg_id": decisions.judged(
                    "evidence.EV-CHAT-" + suffix + ".payload.messages[*].msg_id",
                    "MSG-" + suffix + "-{0:03d}".format(index),
                    "Minted consecutively. POL-NS-08(c) tests the chat for gaps in its "
                    "own msg_id sequence, so a minted sequence must be contiguous and "
                    "this one is.",
                ),
                "sender": decisions.judged(
                    "evidence.EV-CHAT-" + suffix + ".payload.messages[*].sender", sender,
                    "The source's lower-case sender, upper-cased to this corpus's "
                    "vocabulary.",
                    source="chat_logs[*].sender",
                ),
                "text": decisions.copied(
                    "evidence.EV-CHAT-" + suffix + ".payload.messages[*].text",
                    "chat_logs[*].content", entry["content"],
                ),
                "sent_at": decisions.copied(
                    "evidence.EV-CHAT-" + suffix + ".payload.messages[*].sent_at",
                    "chat_logs[*].timestamp", entry["timestamp"],
                ),
                "read_at": decisions.judged(
                    "evidence.EV-CHAT-" + suffix + ".payload.messages[*].read_at", None,
                    "The source carries no read receipt for any message. Null rather "
                    "than a copy of sent_at, which would assert a read that was never "
                    "recorded.",
                ),
                "delivered_at": decisions.judged(
                    "evidence.EV-CHAT-" + suffix + ".payload.messages[*].delivered_at", None,
                    "The source carries no delivery receipt, for the same reason.",
                ),
                "channel": decisions.judged(
                    "evidence.EV-CHAT-" + suffix + ".payload.messages[*].channel",
                    _channel_for(entry, policy_version),
                    channel_reason,
                    source=channel_source,
                ),
                "language": decisions.judged(
                    "evidence.EV-CHAT-" + suffix + ".payload.messages[*].language", "en",
                    "The source's messages are written in English. The field is "
                    "carried because POL-NS-08 and the language-ambiguity code read it.",
                ),
                "redacted": decisions.judged(
                    "evidence.EV-CHAT-" + suffix + ".payload.messages[*].redacted", False,
                    "Nothing in the source is marked as redacted, and no text is "
                    "withheld.",
                ),
                "waypoint_hint": decisions.judged(
                    "evidence.EV-CHAT-" + suffix + ".payload.messages[*].waypoint_hint", None,
                    "The source names no waypoint. POL-NS-03 reads this field, so "
                    "minting a hint would decide a fault allocation.",
                ),
            }
        )

    payload = {
        "trip_id": trip_id,
        "messages": messages,
        "message_count": decisions.judged(
            "evidence.EV-CHAT-" + suffix + ".payload.message_count", len(messages),
            "The number of chat_logs entries the source supplies, including the "
            "system entry, which is how the corpus counts them.",
        ),
        "first_message_at": decisions.judged(
            "evidence.EV-CHAT-" + suffix + ".payload.first_message_at", chats[0]["timestamp"],
            "The first chat_logs timestamp the source supplies.",
        ),
        "last_message_at": decisions.judged(
            "evidence.EV-CHAT-" + suffix + ".payload.last_message_at", chats[-1]["timestamp"],
            "The last chat_logs timestamp the source supplies.",
        ),
        "truncated": decisions.judged(
            "evidence.EV-CHAT-" + suffix + ".payload.truncated", False,
            "Nothing in the source indicates the log was cut short, and its msg_id "
            "sequence is contiguous by construction.",
        ),
    }
    notes = (
        "The source's own chat log, six entries, contiguous by construction. The "
        "largest interval between entries is 140 s, so no gap of more than 5 minutes "
        "spans the arrival marker and POL-NS-08(c) is not engaged. The in-app call is "
        "carried as a message here and as a call record on trip_record, which is where "
        "POL-NS-04(b) reads it."
    )
    return _artifact(
        decisions, "EV-CHAT-" + suffix, "CHAT_LOG", "PLATFORM_TELEMETRY",
        trip_id, export_at, payload, [], notes, assessed_at,
    )


def _fare(
    decisions: Decisions, trip: Dict[str, Any], export_at: str, assessed_at: str,
    policy_version: int = DEFAULT_POLICY_VERSION, suffix: str = "00901",
) -> Dict[str, Any]:
    """FARE_BREAKDOWN, carrying only the one line the source itemises.

    ``policy_version`` decides the admissibility note, and at version 7 the code
    set as well. The ledger carries one 5.00 line either way and itemises nothing
    else either way. At versions 1 and 3 the code set is ``PARTIAL_RECORD`` and
    its weight does not move; what moves between them is what the note says about
    the fee: at version 1 the 5.00 does not reconcile with ``fee_schedule`` and
    engages POL-NS-08(d) against 4.00, and at version 3 the fee in force is the
    record's own ``platform_policy.cancellation_fee_sgd``, 5.00, so the ledger
    reconciles and POL-NS-08(d) is not engaged. At version 7 the fee is the only
    figure v2.1 needs from the ledger and the record states it, so the record is
    not marked a PARTIAL_RECORD at all: see :func:`_v7_fare_issue_codes`. The
    version-1 note is left exactly as it was.
    """
    fee = float(trip["cancellation_fee"])
    payload = {
        "trip_id": decisions.copied(
            "evidence.EV-FARE-" + suffix + ".payload.trip_id", "trip_data.trip_id", trip["trip_id"]
        ),
        "currency": decisions.judged(
            "evidence.EV-FARE-" + suffix + ".payload.currency", "SGD",
            "The source's amounts are in Singapore dollars, which is also this "
            "corpus's currency and the policy's.",
        ),
        "fare_model": decisions.judged(
            "evidence.EV-FARE-" + suffix + ".payload.fare_model", "METERED",
            "The source states no fare model. METERED is used because the source "
            "quotes no upfront fare, and UPFRONT_QUOTE would assert a quote that does "
            "not exist here.",
        ),
        "cancellation_fee": decisions.copied(
            "evidence.EV-FARE-" + suffix + ".payload.cancellation_fee",
            "trip_data.cancellation_fee", fee,
        ),
        "total_charged": decisions.judged(
            "evidence.EV-FARE-" + suffix + ".payload.total_charged", fee,
            "The cancellation fee is the only amount the source charges, so it is the "
            "whole of what was charged.",
            source="trip_data.cancellation_fee",
        ),
        "payment_status": decisions.judged(
            "evidence.EV-FARE-" + suffix + ".payload.payment_status", "CHARGED",
            "The source says the fee was applied to the rider's e-wallet and the "
            "dispute is a request to reverse it, so the charge stands as CHARGED.",
            source="chat_logs[system].content",
        ),
        "refund_issued_sgd": decisions.judged(
            "evidence.EV-FARE-" + suffix + ".payload.refund_issued_sgd", 0.0,
            "No refund has been issued: the dispute is open and the rider is asking "
            "for one.",
            source="dispute_ticket.status",
        ),
        "charged_at": decisions.copied(
            "evidence.EV-FARE-" + suffix + ".payload.charged_at",
            "trip_data.cancellation_time", trip["cancellation_time"],
        ),
        "surge_multiplier": decisions.judged(
            "evidence.EV-FARE-" + suffix + ".payload.surge_multiplier", 1.0,
            "The source records no surge. 1.0 is no surge, and no amount in the source "
            "reflects one.",
        ),
        "rate_card_id": decisions.judged(
            "evidence.EV-FARE-" + suffix + ".payload.rate_card_id", None,
            "The source names no rate card. The corpus's ids encode a quarter and a "
            "tier; minting one would assert a rate card that was never issued.",
        ),
    }

    # The source itemises nothing else. Every other money line the corpus's fare
    # artifact carries is absent here, and is written as null or zero rather than
    # filled with a plausible figure.
    zero_fields = (
        "base_fare", "distance_fare", "time_fare", "surge_amount", "tolls_erp",
        "airport_surcharge", "platform_fee", "promo_discount", "waiting_time_fee",
    )
    for field in zero_fields:
        payload[field] = decisions.judged(
            "evidence.EV-FARE-" + suffix + ".payload." + field, 0.0,
            "Zero, not null: the source itemises no such line, and this trip ran no "
            "metered distance, so there is no amount for it to carry.",
        )
    null_fields = (
        "quoted_fare_sgd", "distance_charged_km", "time_charged_min",
        "per_km_rate_sgd", "per_min_rate_sgd",
    )
    for field in null_fields:
        payload[field] = decisions.judged(
            "evidence.EV-FARE-" + suffix + ".payload." + field, None,
            "Null: the trip never ran, so there is no distance, duration or rate to "
            "state. The source supplies none.",
        )
    payload["erp_gantries"] = decisions.judged(
        "evidence.EV-FARE-" + suffix + ".payload.erp_gantries", [],
        "The trip never ran, so it passed no gantries. The source names none.",
    )

    notes = (
        "The ledger carries one line: the 5.00 cancellation fee. It itemises nothing "
        "else, which is a PARTIAL_RECORD, and the 5.00 does not reconcile with this "
        "system's fee_schedule, so POL-NS-08(d) IS engaged: the greater of the STANDARD "
        "zone fee (4.00) and the RYDE_X tier fee (4.00) is 4.00. Both figures depend on "
        "the stated zone-class and vehicle-tier assumptions recorded in the mapping "
        "record. No issue code is minted for the POL-NS-08(d) mismatch, because no code "
        "in the corpus's vocabulary covers it and this conversion may not invent one; "
        "the engagement is stated here in prose instead."
    )
    codes = ["PARTIAL_RECORD"]
    codes_reason: Optional[str] = None
    if policy_version >= PLATFORM_POLICY_VERSION:
        # The version-3 reading, and the one place the two conversions of this
        # artifact differ. The fee in force is the record's own platform_policy
        # figure rather than the version-1 fee_schedule's, so the single line
        # reconciles and POL-NS-08(d) is not engaged. The weight is read from the
        # same pre-pass rule ``admissibility`` derives it from rather than typed
        # here, so the note cannot state a figure the block beside it does not.
        from tribunal import prepass  # noqa: PLC0415 - see admissibility()

        weight = prepass.weight_for(["PARTIAL_RECORD"])
        notes = (
            "The ledger carries one line: the 5.00 cancellation fee. It itemises "
            "nothing else, so this is still a PARTIAL_RECORD, at the weight this "
            "conversion's own pre-pass rule gives that code ({0}). The 5.00 equals the "
            "fee in force for this trip: fee_schedule.resolution_rule reads "
            "trip_record.platform_policy.cancellation_fee_sgd first, and the record "
            "states it as 5.00, so the single line reconciles with the fee and "
            "POL-NS-08(d) is NOT engaged. No issue code is minted for the "
            "reconciliation, because there is nothing to report: the one line and the "
            "fee in force are the same figure.".format(weight)
        )
    if policy_version >= V7_POLICY_VERSION:
        # The version-7 reading: the same ledger, read as a record that states
        # what v2.1 needs rather than as an itemisation that is missing. The code
        # set comes from the one rule, and the weight from the same pre-pass rule
        # the block beside it uses.
        weight = prepass.weight_for(_v7_fare_issue_codes())
        codes = _v7_fare_issue_codes()
        codes_reason = V7_FEE_ISSUE_NOTE
        notes = (
            "The ledger carries one line: the 5.00 cancellation fee. It itemises "
            "nothing else, but the fee is the only figure version 7 needs from it and "
            "the record states it, so no issue code is minted and the artifact is "
            "COMPLETE at version 7, at the weight this conversion's own pre-pass rule "
            "gives an empty code set ({0}). The 5.00 equals the fee in force for this "
            "trip: fee_schedule.resolution_rule reads "
            "trip_record.platform_policy.cancellation_fee_sgd first, and the record "
            "states it as 5.00, so the single line reconciles with the fee and "
            "POL-NS-08(d) is NOT engaged.".format(weight)
        )
    return _artifact(
        decisions, "EV-FARE-" + suffix, "FARE_BREAKDOWN", "PAYMENTS_LEDGER",
        trip["trip_id"], export_at, payload, codes, notes, assessed_at,
        codes_reason=codes_reason,
    )


def _rider(
    decisions: Decisions, profile: Dict[str, Any], trip_id: str, export_at: str,
    assessed_at: str, policy_version: int = DEFAULT_POLICY_VERSION,
    suffix: str = "00901",
) -> Dict[str, Any]:
    """RIDER_PROFILE, with this corpus's field set filled only where the source speaks.

    From policy version 7 the profile also carries the source's own
    ``fraud_flags`` counter under this corpus's name for it, because that is the
    field POL-GEN-22 reads: v2.1 raises the confidence a ruling needs to 0.95
    "where either party's profile carries fraud_flags of 1 or more", and the
    version-1 and version-3 conversions carried the counter as
    ``prior_no_show_flags`` instead, which no version-7 clause reads. Versions 1
    and 3 are byte-identical: the field is written only from version 7.
    """
    history = profile["dispute_history"]
    payload = {
        "party_id": decisions.copied(
            "evidence.EV-RPROF-" + suffix + ".payload.party_id", "rider_profile.rider_id",
            profile["rider_id"],
        ),
        "party_role": decisions.judged(
            "evidence.EV-RPROF-" + suffix + ".payload.party_role", "RIDER",
            "This is the rider's profile; the corpus's token is RIDER.",
        ),
        "snapshot_at": decisions.judged(
            "evidence.EV-RPROF-" + suffix + ".payload.snapshot_at", export_at,
            "The source gives no snapshot time. The case's export time is used, which "
            "is when these counters were read.",
        ),
        "account_age_days": decisions.copied(
            "evidence.EV-RPROF-" + suffix + ".payload.account_age_days",
            "rider_profile.account_age_days", profile["account_age_days"],
        ),
        "lifetime_trips": decisions.copied(
            "evidence.EV-RPROF-" + suffix + ".payload.lifetime_trips",
            "rider_profile.total_trips", profile["total_trips"],
            "The source calls this total_trips; lifetime_trips is this corpus's name for "
            "the same counter.",
        ),
        "rating": decisions.copied(
            "evidence.EV-RPROF-" + suffix + ".payload.rating", "rider_profile.avg_rating",
            profile["avg_rating"],
            "The source calls this avg_rating; rating is this corpus's name for it.",
        ),
        "prior_disputes_filed": decisions.copied(
            "evidence.EV-RPROF-" + suffix + ".payload.prior_disputes_filed",
            "rider_profile.dispute_history.total_disputes", history["total_disputes"],
        ),
        "prior_disputes_upheld": decisions.copied(
            "evidence.EV-RPROF-" + suffix + ".payload.prior_disputes_upheld",
            "rider_profile.dispute_history.upheld", history["upheld"],
        ),
        "prior_no_show_flags": decisions.judged(
            "evidence.EV-RPROF-" + suffix + ".payload.prior_no_show_flags",
            profile["fraud_flags"],
            "The source's fraud_flags counter is carried here, because its own detail "
            "text describes the flag as 'frequent late cancellations', which is the "
            "no-show family. POL-NS-09(d) explicitly does NOT read this field - it reads "
            "no_show_disputes_30d - so carrying it here decides no limb.",
            source="rider_profile.fraud_flags",
        ),
    }

    if policy_version >= V7_POLICY_VERSION:
        # POL-GEN-22's own field. The counter is the same one the version-1
        # conversion carried as prior_no_show_flags; version 7 states the field
        # name a version-7 clause reads, so it is carried here as well, and both
        # entries are on the record.
        payload["fraud_flags"] = decisions.copied(
            "evidence.EV-RPROF-" + suffix + ".payload.fraud_flags",
            "rider_profile.fraud_flags",
            profile["fraud_flags"],
            "The source's own fraud counter, under the name POL-GEN-22 reads it. "
            "The version-1 and version-3 conversions carried this counter as "
            "prior_no_show_flags, which no version-7 clause reads; from version 7 "
            "it is carried here as well, and POL-GEN-22 raises the confidence a "
            "ruling needs to 0.95 where either party's counter is 1 or more.",
        )

    # The source's dispute_history also carries a 'rejected' count, which this
    # corpus has no field for. It is dropped, and the drop is recorded.
    decisions.judged(
        "rider_profile.dispute_history.rejected", None,
        "The source's 'rejected' count has no counterpart in this corpus's profile "
        "schema. It is dropped rather than mapped onto a field that means something "
        "else. prior_disputes_filed and prior_disputes_upheld carry the rest of the "
        "history.",
        source="rider_profile.dispute_history.rejected",
    )
    decisions.judged(
        "rider_profile.name / payment_method", None,
        "The source carries the rider's name and payment method. This corpus's profile "
        "schema has no field for either, and the name is personal data that no clause "
        "reads, so neither is carried.",
        source="rider_profile.name, rider_profile.payment_method",
    )

    for field, reason in (
        ("cancellation_rate", "the source states no cancellation rate"),
        ("no_show_disputes_30d", "the source gives four disputes over an unstated window; a 30-day figure cannot be derived from it"),
        ("deviation_claims_60d", "a route-deviation counter has no meaning on a no-show"),
        ("deviation_claims_60d_substantiated", "a route-deviation counter has no meaning on a no-show"),
        ("disputes_with_counterparty_90d", "the source does not say how many of these disputes were with this same driver"),
    ):
        payload[field] = decisions.judged(
            "evidence.EV-RPROF-" + suffix + ".payload." + field, None,
            "Null rather than zero: {0}, and zero would assert there were none.".format(reason),
        )

    notes = (
        "The rider's own counters, complete for every field the source states. The "
        "corpus's schema has five fields the source does not speak to "
        "(cancellation_rate, no_show_disputes_30d, the two deviation counters, and "
        "disputes_with_counterparty_90d); each is null, and none is zero, because zero "
        "would assert a count nobody recorded. No issue code in the corpus's vocabulary "
        "covers a profile field the source is silent on, so none is minted."
    )
    return _artifact(
        decisions, "EV-RPROF-" + suffix, "RIDER_PROFILE", "PLATFORM_TELEMETRY",
        trip_id, export_at, payload, [], notes, assessed_at,
    )


def _driver(
    decisions: Decisions, profile: Dict[str, Any], trip_id: str, export_at: str,
    assessed_at: str, policy_version: int = DEFAULT_POLICY_VERSION,
    suffix: str = "00901", stated: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """DRIVER_PROFILE, on the same rule as the rider's.

    From policy version 7 it carries the source's own ``fraud_flags`` counter,
    as the rider's does and for the same reason: POL-GEN-22 reads either
    party's. Versions 1 and 3 are byte-identical.
    """
    history = profile["dispute_history"]
    payload = {
        "party_id": decisions.copied(
            "evidence.EV-DPROF-" + suffix + ".payload.party_id", "driver_profile.driver_id",
            profile["driver_id"],
        ),
        "party_role": decisions.judged(
            "evidence.EV-DPROF-" + suffix + ".payload.party_role", "DRIVER",
            "This is the driver's profile; the corpus's token is DRIVER.",
        ),
        "snapshot_at": decisions.judged(
            "evidence.EV-DPROF-" + suffix + ".payload.snapshot_at", export_at,
            "The source gives no snapshot time; the case's export time is used.",
        ),
        "account_age_days": decisions.copied(
            "evidence.EV-DPROF-" + suffix + ".payload.account_age_days",
            "driver_profile.account_age_days", profile["account_age_days"],
        ),
        "lifetime_trips": decisions.copied(
            "evidence.EV-DPROF-" + suffix + ".payload.lifetime_trips",
            "driver_profile.total_trips", profile["total_trips"],
            "The source calls this total_trips; lifetime_trips is this corpus's name.",
        ),
        "rating": decisions.copied(
            "evidence.EV-DPROF-" + suffix + ".payload.rating", "driver_profile.avg_rating",
            profile["avg_rating"],
            "The source calls this avg_rating; rating is this corpus's name.",
        ),
        "prior_disputes_filed": decisions.copied(
            "evidence.EV-DPROF-" + suffix + ".payload.prior_disputes_filed",
            "driver_profile.dispute_history.total_disputes", history["total_disputes"],
        ),
        "prior_disputes_upheld": decisions.copied(
            "evidence.EV-DPROF-" + suffix + ".payload.prior_disputes_upheld",
            "driver_profile.dispute_history.upheld_against", history["upheld_against"],
            "The source's upheld_against is the count of disputes decided against the "
            "driver, which is what prior_disputes_upheld records here.",
        ),
        "prior_no_show_flags": decisions.judged(
            "evidence.EV-DPROF-" + suffix + ".payload.prior_no_show_flags",
            profile["fraud_flags"],
            "The driver's fraud_flags counter is carried, as with the rider's. It is a "
            "lifetime counter and POL-NS-07 explicitly does not read it.",
            source="driver_profile.fraud_flags",
        ),
        "vehicle_type": decisions.judged(
            "evidence.EV-DPROF-" + suffix + ".payload.vehicle_type", ASSUMED_VEHICLE_TIER,
            "The source names a Honda HR-V, which is not a tier in this corpus; RYDE_X "
            "is the base tier. The assumption is stated in the mapping record and the "
            "POL-NS-08(d) fee comparison depends on it.",
            source="driver_profile.vehicle",
        ),
    }

    if policy_version >= V7_POLICY_VERSION:
        payload["fraud_flags"] = decisions.copied(
            "evidence.EV-DPROF-" + suffix + ".payload.fraud_flags",
            "driver_profile.fraud_flags",
            profile["fraud_flags"],
            "The source's own fraud counter, under the name POL-GEN-22 reads it, "
            "for the same reason as the rider's. It is zero here.",
        )

    decisions.judged(
        "driver_profile.vehicle", None,
        "The source's vehicle string ('Honda HR-V (SGP 4521 M)') carries a plate and a "
        "model. The corpus's schema has a tier, not a model; the tier is assumed and "
        "the string itself is dropped rather than carried into a field that means "
        "something else.",
        source="driver_profile.vehicle",
    )

    for field, reason in (
        ("cancellation_rate", "the source states no cancellation rate"),
        ("prior_deviation_flags", "the source states no deviation flags"),
        ("acceptance_rate", "the source states no acceptance rate"),
        ("active_region", "inferring a region from the pickup place name would be world knowledge about places, which this repository forbids"),
        ("deviation_flags_90d", "a route-deviation counter has no meaning on a no-show"),
        ("completed_trips_90d", "the source gives a lifetime trip count only"),
        ("no_show_terminations_30d", "the source states no 30-day termination count; POL-NS-07's anti-farming check therefore cannot be run on this case and is undecidable, not passed"),
        ("completed_trips_30d", "the source states no 30-day trip count"),
        ("disputes_with_counterparty_90d", "the source does not say how many disputes were with this same rider"),
    ):
        if stated is not None and field in stated:
            # This source states the field, so it is carried rather than nulled.
            # ``stated`` is empty for the version-1 and version-3 conversions of
            # DISP-002, whose own source is silent on these, so those two are
            # byte-identical.
            payload[field] = decisions.copied(
                "evidence.EV-DPROF-" + suffix + ".payload." + field,
                "driver_profile." + field, stated[field],
                "Carried: the source states this counter and this corpus's profile "
                "has the field for it. It is the source's own figure.",
            )
            continue
        payload[field] = decisions.judged(
            "evidence.EV-DPROF-" + suffix + ".payload." + field, None,
            "Null rather than zero: {0}, and zero would assert there were none.".format(reason),
        )

    notes = (
        "The driver's own counters, complete for every field the source states. Nine "
        "corpus fields the source does not speak to are null, not zero. "
        "no_show_terminations_30d being null makes POL-NS-07's anti-farming check "
        "undecidable on this case rather than passed, which is the honest state and is "
        "recorded in the mapping. No issue code is minted for the gaps, because no code "
        "in the corpus's vocabulary covers a field the source is silent on."
    )
    return _artifact(
        decisions, "EV-DPROF-" + suffix, "DRIVER_PROFILE", "PLATFORM_TELEMETRY",
        trip_id, export_at, payload, [], notes, assessed_at,
    )


def _advisory(
    decisions: Decisions, trip_id: str, export_at: str, assessed_at: str,
    suffix: str = "00901",
) -> Dict[str, Any]:
    """TRAFFIC_ADVISORY, absent, minted so that its absence can be cited.

    The source carries no advisory at all. This corpus's convention for "no
    advisory" is a MISSING artifact with a null payload, and it is the corpus's
    own documented practice: the note on all 25 such artifacts reads "Artifact
    absent. The identifier is minted anyway so that the absence itself can be
    cited by either advocate." So this mints an identifier and asserts absence.
    It asserts nothing that is not true, and it is the shape every case in this
    corpus has.
    """
    decisions.judged(
        "evidence.EV-ADVIS-" + suffix + "-01",
        "MISSING",
        "The source carries no traffic advisory. A MISSING artifact asserts absence, "
        "not presence, and is this corpus's convention: 25 of its 30 advisories are "
        "MISSING with a null payload. Minting it keeps the converted case in the same "
        "shape as every corpus case, and POL-NS-06(i) is explicitly unavailable against "
        "a MISSING advisory, which is the correct state here.",
    )
    return {
        "evidence_id": "EV-ADVIS-" + suffix + "-01",
        "evidence_type": "TRAFFIC_ADVISORY",
        "trip_id": trip_id,
        "source": "THIRD_PARTY_LTA",
        "generated_at": export_at,
        "schema_version": SCHEMA_VERSION,
        "admissibility": {
            "status": "MISSING",
            "issues": ["MISSING_ARTIFACT"],
            "weight_multiplier": 0.0,
            "notes": (
                "Artifact absent. The identifier is minted anyway so that the absence "
                "itself can be cited by either advocate."
            ),
            "assessed_at": assessed_at,
            "assessor_version": ASSESSOR_VERSION,
        },
        "payload": None,
    }


def _artifact(
    decisions: Decisions, evidence_id: str, evidence_type: str, source: str,
    trip_id: str, generated_at: str, payload: Dict[str, Any], codes: List[str],
    notes: str, assessed_at: str, codes_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """One evidence artifact in the contract's eight-key shape.

    ``codes_reason`` is how the mapping records the code set where the version-7
    conversion has something of its own to say about it: the two Ryde fare
    records, whose itemisation gap is a difference of format rather than an
    impairment at version 7. Every other artifact leaves it unset and gets the
    sentence it has always got.
    """
    decisions.judged(
        "evidence.{0}.admissibility.issues".format(evidence_id), codes,
        codes_reason
        or (
            "Codes chosen only from prepass.CODE_WEIGHTS, and the weight is "
            "computed by prepass.weight_for rather than written here."
        ),
    )
    return {
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "trip_id": trip_id,
        "source": source,
        "generated_at": generated_at,
        "schema_version": SCHEMA_VERSION,
        "admissibility": admissibility(codes, notes, assessed_at),
        "payload": payload,
    }


# What policy version 3 does about three of the divergences below, keyed by the
# opening words of the finding. The resolution is added to the entry rather than
# replacing it, so the mapping still says what the source and this system each
# said and, beside it, what changed.
DIVERGENCE_RESOLUTIONS = (
    (
        "The source's cancellation fee of SGD 5.00",
        "fee_schedule.resolution_rule reads trip_record.platform_policy."
        "cancellation_fee_sgd (5.00) first; POL-NS-08(d) is no longer engaged on "
        "the converted case.",
    ),
    (
        "The source's 8-minute no-show threshold",
        "POL-NS-01(c) reads platform_policy.free_wait_sec (300) and "
        "no_show_threshold_sec (480); the cancellation at 08:51:00 falls at the "
        "8-minute threshold measured from the 08:43 arrival.",
    ),
    (
        "Whether the waiting clock runs from arrival",
        "scheduled_at is now carried as trip_record.scheduled_at, and POL-NS-10(b) "
        "reads it. POL-NS-01(c) still runs the clock from the first qualifying "
        "in-geofence fix, and the platform's own wait_timer_started event "
        "(08:43:10) is a second, independent carrier of the same start.",
    ),
)


def _divergences(
    trip: Dict[str, Any], policy: Dict[str, Any],
    policy_version: int = DEFAULT_POLICY_VERSION,
) -> List[Dict[str, Any]]:
    """Where the source's policy and this system's policy disagree.

    Recorded, not resolved, at version 1: the case runs under this system's
    loaded policy unchanged, so each divergence is a fact about the conversion
    rather than something the converted case can express. From policy version 3
    the three the platform-policy block settles gain a ``resolution`` beside
    them; the rest stand as they were.
    """
    divergences = [
        {
            "finding": "The source's cancellation fee of SGD 5.00 matches no entry in fee_schedule.",
            "source_policy": "cancellation_fee_after_wait: 5.00",
            "this_system": (
                "fee_schedule.zone_class_fee_sgd for STANDARD is 4.00 and "
                "vehicle_tier_fee_sgd for RYDE_X is 4.00; the greater is 4.00. No "
                "combination of zone class and vehicle tier in the schedule produces "
                "5.00."
            ),
            "effect": (
                "The converted case carries the source's 5.00 unchanged, because "
                "changing it would be editing the evidence. POL-NS-08(d) is therefore "
                "engaged on the converted case."
            ),
            "depends_on_assumptions": ["pickup zone class is STANDARD", "vehicle tier is RYDE_X"],
        },
        {
            "finding": "The source's 8-minute no-show threshold has no counterpart in POL-NS.",
            "source_policy": "no_show_threshold_min: 8",
            "this_system": (
                "POL-NS-01(c) sets the dwell minimum from fee_schedule.minimum_dwell_sec: "
                "300 s (5 min) for STANDARD, LARGE_VENUE and TRANSPORT_HUB, 480 s (8 min) "
                "for AIRPORT. The source's flat 8 minutes is not this system's rule, and "
                "this system's figure varies by zone class where the source's does not."
            ),
            "effect": (
                "The converted case carries no threshold of its own: the threshold is "
                "read from the loaded policy at arbitration time, as it is for every "
                "case."
            ),
            "depends_on_assumptions": ["pickup zone class is STANDARD"],
        },
        {
            "finding": (
                "Whether the waiting clock runs from arrival or from the scheduled time "
                "is a question this system's policy does not address."
            ),
            "source_policy": (
                "scheduled_time 08:45, driver_arrival_time 08:43; the source's own app "
                "events start the free-wait timer at arrival (wait_timer_started at "
                "08:43:10), and the cancellation at 08:51:00 falls exactly on an "
                "8-minute threshold measured from arrival."
            ),
            "this_system": (
                "POL-NS-01(c) measures the dwell 'from the first qualifying in-geofence "
                "GPS fix and not from the arrived event'. That answers a different "
                "question from the one the source's timers answer: it fixes the start of "
                "the dwell, and is silent on whether a scheduled time could start "
                "anything."
            ),
            "effect": (
                "Recorded and NOT resolved. On this case the point does not bite, because "
                "no fix carries an accuracy value and POL-NS-02 therefore yields no "
                "qualifying in-geofence fix at all, so the dwell cannot be measured "
                "either way."
            ),
            "depends_on_assumptions": [],
        },
        {
            "finding": "The source's fee goes to driver_compensation without the platform share this system applies.",
            "source_policy": "fee_goes_to: driver_compensation",
            "this_system": (
                "POL-NS-07 compensates the driver at 80 percent of the fee, the residual "
                "20 percent being retained as the platform service fee."
            ),
            "effect": (
                "The converted case carries no compensation figure; POL-NS-07 computes "
                "it from the fee at arbitration time."
            ),
            "depends_on_assumptions": [],
        },
        {
            "finding": "The source's dispute vocabulary is not this system's.",
            "source_policy": (
                "dispute_id DISP-002, status 'open', dispute_type 'no_show_charge', "
                "cancellation_reason 'rider_no_show'"
            ),
            "this_system": (
                "This corpus's dispute ids are DSP-<case_no>, its reason code token is "
                "RIDER_NO_SHOW, and it has no 'status' key. The source's tokens are "
                "translated where this system has an equivalent and recorded where it "
                "does not."
            ),
            "effect": (
                "dispute_id is carried unchanged as DISP-002, so the converted case can "
                "be traced back to the organisers' document; status is dropped."
            ),
            "depends_on_assumptions": [],
        },
    ]

    if policy_version >= PLATFORM_POLICY_VERSION:
        for entry in divergences:
            for opening, resolution in DIVERGENCE_RESOLUTIONS:
                if entry["finding"].startswith(opening):
                    entry["resolution"] = resolution
    return divergences


def _seconds_between(start: str, end: str) -> float:
    """Whole seconds between two ISO-8601 stamps, as a float."""
    from datetime import datetime

    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


# --------------------------------------------------------------------------
# The expected outcome, kept apart
# --------------------------------------------------------------------------
def expected_outcome(source_text: str) -> Dict[str, Any]:
    """The organisers' stated expected outcome, recorded where it cannot leak.

    This is written to ``eval/external/ryde/expected.json``, never under
    ``data/``. It is **not** part of the frozen answer key at
    ``eval/answers/ground_truth.json`` and is never merged into it: that key is
    frozen, and the sample case is not one of the 29 cases it measures.

    The stated outcome is quoted from the source's title, which is why this
    function -- and only this function -- reads the document other than through
    :func:`conversion_input`. Its result never enters the case.
    """
    return {
        "source_document": "eval/external/ryde/DISP-002.md",
        "dispute_id": "DISP-002",
        "expected_outcome_as_stated": "Cancellation charge UPHELD",
        "stated_reasons": [
            "driver showed up",
            "waited the full free-wait + no-show window",
            "attempted contact",
            "rider has a pattern of late cancellations",
        ],
        "not_the_answer_key": (
            "This is the organisers' stated outcome for their own sample case. It is "
            "NOT part of eval/answers/ground_truth.json, it is not merged into that "
            "key, and it is not an input to any agent. The key is frozen and measures "
            "the 29-case corpus, which this case is not part of."
        ),
        "upheld_is_not_a_token_here": (
            "'UPHELD' is the source's word. This system's ruling vocabulary is "
            "POL-GEN-03's; the source's word is recorded as stated rather than "
            "translated into a token this system did not emit."
        ),
    }


# --------------------------------------------------------------------------
# DISP-001: the organisers' route-deviation sample, for policy version 7
# --------------------------------------------------------------------------
# ``tmp/ryde-v21/DISP-001.md`` is the second sample the organisers supplied: a
# route deviation in a format of its own -- ``gps_telemetry``, ``optimal_route``,
# ``traffic_conditions``, ``fare_breakdown`` and ``chat_logs`` at the top level.
# It is answer-bearing in a second way. Where DISP-002's expected ruling sits in
# the Markdown title, DISP-001's sits **inside** the JSON block, in
# ``case_metadata.expected_ruling`` and ``expected_refund_amount``, and four more
# of the block's keys carry the organisers' own analysis and their recommended
# ruling. Those five keys are named here and are never read: the conversion's
# input is the case material alone, and the mapping records that the other five
# were excluded rather than dropped in silence.
#
# The source is not committed. It is the organisers' material, it arrived in
# ``tmp/``, and ``tmp/`` is not in a clean clone -- so the two converted cases
# and their mappings travel and the document they came from does not. The set's
# README says so.
DISP001_SOURCE_PATH = PROJECT_ROOT / "tmp" / "ryde-v21" / "DISP-001.md"
DISP001_SOURCE_DOCUMENT = "tmp/ryde-v21/DISP-001.md"

# The keys the conversion reads, and the keys it never reads. Every key of the
# block must be one or the other: a block that grew a sixth case key fails here
# rather than having it ignored, which is the rule the version-1 key set follows.
DISP001_CASE_KEYS = (
    "dispute_ticket",
    "rider_profile",
    "driver_profile",
    "trip_data",
    "fare_breakdown",
    "gps_telemetry",
    "optimal_route",
    "chat_logs",
    "traffic_conditions",
)
DISP001_ANSWER_BEARING_KEYS = (
    "case_metadata",
    "chat_log_analysis",
    "traffic_analysis",
    "evidence_summary",
    "recommended_ruling",
)

# The per-kilometre rate the source states only in prose, in the fare
# breakdown's own ``notes``: "The distance fare is calculated at $0.80/km." The
# rate is read out of that sentence rather than typed here, so a note whose
# figure moved is a refusal instead of a rate nobody reviewed -- the rule
# ``ops.risk`` and ``tribunal.pipeline.confidence_floor`` both follow.
RATE_RE = re.compile(r"\$(\d+(?:\.\d+)?)\s*/\s*km")

# The category, and the two tokens the source's own vocabulary maps onto.
ROUTE_DEVIATION_CATEGORY = "ROUTE_DEVIATION"

# What the source's ``incident_type`` values are carried as. The corpus's
# advisory vocabulary is CLOSURE, ACCIDENT and KERB_RESTRICTION; the source
# writes ``vehicle_fire``, ``heavy_congestion`` and ``traffic_flow``. The type is
# carried upper-cased, exactly as the source states it, and the mapping records
# that the token is the source's rather than this corpus's: whether a vehicle
# fire is an "incident" for POL-RD-23 is a reading of v2.1's own sentence, and it
# is the policy owner's to settle rather than this converter's to decide.
#
# ``intersects_route`` is the one thing the conversion does judge, because the
# source says it in words: its traffic_analysis calls the PIE incidents the
# reason the driver could not use the recommended route ("A vehicle fire on PIE
# eastbound ... made the optimal route impassable"), and it calls the ECP report
# a report on the alternative the driver took. So the two PIE entries intersect
# the recommended route and the ECP flow report does not. Each of the three
# entries records which way it was read and why.
ADVISORY_INTERSECTS_ROUTE = {
    "TC-001": True,
    "TC-002": True,
    "TC-003": False,
}


def parse_route_deviation_source(block_text: str) -> Dict[str, Any]:
    """Parse the route-deviation block and hold its key set to the two tables.

    A block carrying a key that is neither case material nor one of the five
    answer-bearing keys is refused rather than partly read, so a source that grew
    a key cannot have it ignored.
    """
    try:
        parsed = json.loads(block_text)
    except json.JSONDecodeError as exc:
        raise ConversionError("the fenced block is not valid JSON: {0}".format(exc)) from exc
    if not isinstance(parsed, dict):
        raise ConversionError("the fenced block is not a JSON object")
    missing = [key for key in DISP001_CASE_KEYS if key not in parsed]
    if missing:
        raise ConversionError(
            "the route-deviation block is missing keys: {0}".format(", ".join(missing))
        )
    unknown = sorted(
        set(parsed) - set(DISP001_CASE_KEYS) - set(DISP001_ANSWER_BEARING_KEYS)
    )
    if unknown:
        raise ConversionError(
            "the route-deviation block carries keys this converter has no "
            "disposition for, and they will not be ignored in silence: {0}".format(
                ", ".join(unknown)
            )
        )
    return parsed


def route_deviation_source_items(source: Dict[str, Any]) -> List[str]:
    """Every item of the block's case material, named the way the mapping names it.

    Only the case-material keys are walked: the five answer-bearing keys are not
    case material, so they are excluded from the coverage check rather than
    recorded as dropped -- naming their contents would put the organisers'
    expected ruling on the mapping record. Every array is named with one
    wildcard selector, because the conversion carries every element of an array
    through one code path.
    """
    items: List[str] = []

    def walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, "{0}.{1}".format(prefix, key) if prefix else key)
        elif isinstance(node, list):
            for element in node:
                walk(element, prefix + "[*]")
        else:
            items.append(prefix)

    for key in DISP001_CASE_KEYS:
        walk(source[key], key)
    return sorted(set(items))


def _route_fare(
    decisions: Decisions, fare: Dict[str, Any], trip: Dict[str, Any],
    export_at: str, assessed_at: str,
) -> Dict[str, Any]:
    """FARE_BREAKDOWN, with the per-kilometre rate read out of the note.

    The one figure POL-RD-24 needs is ``per_km_rate_sgd``, and the source states
    it only in prose. It is read out of that sentence by :data:`RATE_RE` and the
    reading is recorded, so a note whose figure moved refuses rather than
    publishing a rate nobody wrote down.

    The artifact is COMPLETE: the source's ledger itemises no base, time or
    platform-fee line, but version 7 reads only the per-kilometre rate and the
    excess figures, and the record states both. See
    :func:`_v7_fare_issue_codes`.
    """
    notes = fare.get("notes")
    match = RATE_RE.search(notes or "")
    if match is None:
        raise ConversionError(
            "the fare breakdown's notes state no per-kilometre rate, so POL-RD-24's "
            "excess distance fare cannot be computed from the source: {0!r}".format(notes)
        )
    rate = decisions.judged(
        "evidence.EV-FARE-00902.payload.per_km_rate_sgd",
        float(match.group(1)),
        "Read out of the source's own note, which is where the rate is stated: "
        "{0!r}. The sentence is the source's; the figure is taken from it rather "
        "than typed here, so a note whose rate moved fails the conversion instead "
        "of publishing a rate nobody wrote down.".format(match.group(0)),
        source="fare_breakdown.notes",
    )

    payload: Dict[str, Any] = {
        "trip_id": decisions.copied(
            "evidence.EV-FARE-00902.payload.trip_id", "trip_data.trip_id",
            trip["trip_id"],
        ),
        "currency": decisions.judged(
            "evidence.EV-FARE-00902.payload.currency", "SGD",
            "The source's amounts are in Singapore dollars, which is this corpus's "
            "currency and v2.1's.",
        ),
        "fare_model": decisions.judged(
            "evidence.EV-FARE-00902.payload.fare_model", "METERED",
            "The source quotes an estimate and a metered actual fare; it names no "
            "upfront quote as binding, so METERED is the model rather than "
            "UPFRONT_QUOTE.",
            source="trip_data.estimated_fare, trip_data.actual_fare",
        ),
        "quoted_fare_sgd": decisions.copied(
            "evidence.EV-FARE-00902.payload.quoted_fare_sgd",
            "trip_data.estimated_fare, fare_breakdown.estimated.total",
            fare["estimated"]["total"],
            "The source states the estimate twice, in the trip record and in the "
            "breakdown, and the two agree. Both are named here rather than the "
            "second being left unrecorded.",
        ),
        "total_charged": decisions.copied(
            "evidence.EV-FARE-00902.payload.total_charged",
            "trip_data.actual_fare, fare_breakdown.actual.total",
            fare["actual"]["total"],
            "The source states the charged fare twice and the two agree; both are "
            "named, as above.",
        ),
        "distance_charged_km": decisions.copied(
            "evidence.EV-FARE-00902.payload.distance_charged_km",
            "trip_data.actual_distance_km", trip["actual_distance_km"],
            "The distance the fare was charged on, which is the actual distance the "
            "source records.",
        ),
        "time_charged_min": decisions.copied(
            "evidence.EV-FARE-00902.payload.time_charged_min",
            "trip_data.actual_duration_min", trip["actual_duration_min"],
        ),
        "per_km_rate_sgd": rate,
        "charged_at": decisions.copied(
            "evidence.EV-FARE-00902.payload.charged_at", "trip_data.end_time",
            trip["end_time"],
            "The charge is applied when the trip ends, which is the only instant "
            "the source gives for it.",
        ),
        "payment_status": decisions.judged(
            "evidence.EV-FARE-00902.payload.payment_status", "CHARGED",
            "The source says the fare was charged and the dispute asks for part of "
            "it back, so the charge stands as CHARGED.",
            source="dispute_ticket.description",
        ),
        "refund_issued_sgd": decisions.judged(
            "evidence.EV-FARE-00902.payload.refund_issued_sgd", 0.0,
            "No refund has been issued: the dispute is open and the rider is "
            "asking for one.",
            source="dispute_ticket.status",
        ),
    }

    decisions.judged(
        "fare_breakdown.delta.total", None,
        "The source's own delta is the difference between the estimate and the "
        "charge (6.50). It is read and not carried: this corpus's fare artifact "
        "holds the two totals, and the difference between them is arithmetic the "
        "reader can do. POL-RD-24 refunds the excess distance fare, which is not "
        "this figure.",
        source="fare_breakdown.delta.total",
    )
    decisions.judged(
        "fare_breakdown.excess_distance_fare, fare_breakdown.excess_tolls",
        None,
        "The source states the excess distance fare (3.44) and the excess tolls "
        "(2.22) itself. Neither is carried: the money block computes the excess "
        "distance fare from the two distances and the rate, under POL-RD-24, and "
        "carrying the source's own figure beside a computed one would be two "
        "answers to one question. The mapping records both readings.",
        source="fare_breakdown.excess_distance_fare, fare_breakdown.excess_tolls",
    )

    # Every other money line the corpus's fare artifact carries is absent here,
    # and is written as zero or null rather than filled with a plausible figure.
    for field in (
        "base_fare", "distance_fare", "time_fare", "surge_amount", "tolls_erp",
        "airport_surcharge", "platform_fee", "promo_discount", "waiting_time_fee",
        "cancellation_fee",
    ):
        payload[field] = decisions.judged(
            "evidence.EV-FARE-00902.payload." + field, 0.0,
            "Zero, not null: the source itemises no such line. It gives one "
            "aggregate charge and the excess distance fare, and no breakdown of "
            "the charge into lines.",
        )
    for field in (
        "per_min_rate_sgd", "rate_card_id", "surge_multiplier",
    ):
        payload[field] = decisions.judged(
            "evidence.EV-FARE-00902.payload." + field, None,
            "Null: the source states no per-minute rate, names no rate card and "
            "records no surge. A minted 1.0 surge multiplier would assert a "
            "multiplier nobody recorded.",
        )
    payload["erp_gantries"] = decisions.judged(
        "evidence.EV-FARE-00902.payload.erp_gantries", [],
        "The source names no gantry. Its note says the tolls rose by 2.22 'due to "
        "the additional ERP gantries', which is a statement about the excess rather "
        "than a list of gantries, so the list is empty rather than reconstructed.",
    )

    from tribunal import prepass  # noqa: PLC0415 - see admissibility()

    weight = prepass.weight_for(_v7_fare_issue_codes())
    notes = (
        "The ledger carries the aggregate the source charges (35.00) against the "
        "estimate it quoted (28.50) and the per-kilometre rate the distance fare "
        "was computed at (0.80, read out of the note). It itemises no base, time or "
        "platform-fee line, but version 7 needs only the per-kilometre rate and the "
        "excess figures, and the record states both: its note gives the rate as 0.80 "
        "per kilometre and fare_breakdown.excess_distance_fare states the excess "
        "distance fare. That is a difference of format rather than a gap in what "
        "v2.1 decides on, so the artifact is COMPLETE at version 7, at the weight "
        "this conversion's own pre-pass rule gives an empty code set ({0}). No issue "
        "code is minted for the itemisation, because there is nothing to report."
    ).format(weight)
    return _artifact(
        decisions, "EV-FARE-00902", "FARE_BREAKDOWN", "PAYMENTS_LEDGER",
        trip["trip_id"], export_at, payload, _v7_fare_issue_codes(), notes,
        assessed_at, codes_reason=V7_FARE_ISSUE_NOTE,
    )


def _route_advisories(
    decisions: Decisions, conditions: List[Dict[str, Any]], trip: Dict[str, Any],
    trip_id: str, export_at: str, assessed_at: str,
) -> List[Dict[str, Any]]:
    """One TRAFFIC_ADVISORY per ``traffic_conditions`` entry.

    POL-RD-23 reads three things off an advisory: whether it intersects the
    recommended route, whether its window overlaps the trip, and whether its type
    is one of the kinds the clause names. The first is judged here and recorded
    per entry -- see :data:`ADVISORY_INTERSECTS_ROUTE` -- and the other two are
    carried from the source: the window from the entry's own two timestamps
    compared with the trip's, and the type upper-cased as the source writes it.
    """
    built: List[Dict[str, Any]] = []
    start = trip["start_time"]
    end = trip["end_time"]
    for index, condition in enumerate(conditions, start=1):
        evidence_id = "EV-ADVIS-00902-{0:02d}".format(index)
        incident = condition["incident_id"]
        intersects = ADVISORY_INTERSECTS_ROUTE.get(incident)
        if intersects is None:
            raise ConversionError(
                "the source records a traffic condition this converter has no "
                "route reading for, and it will not be guessed: {0!r}".format(incident)
            )
        judged_intersects = decisions.judged(
            "evidence.{0}.payload.intersects_route".format(evidence_id),
            intersects,
            "Judged from the source's own traffic_analysis, which names the PIE "
            "incidents the reason the recommended route could not be used and the "
            "ECP entry a report on the alternative the driver took: {0} -> "
            "{1}.".format(incident, intersects),
            source="traffic_conditions[*].incident_id",
        )
        judged_overlaps = decisions.copied(
            "evidence.{0}.payload.overlaps_trip_window".format(evidence_id),
            "traffic_conditions[*].timestamp, traffic_conditions[*].clear_time",
            _overlaps(start, end, condition["timestamp"], condition["clear_time"]),
            "Computed by comparing the entry's own window with the trip's "
            "({0} to {1}). An entry with no clear time is treated as still "
            "active, so its window runs to the end of the trip.".format(start, end),
        )
        payload = {
            "advisory_id": decisions.copied(
                "evidence.{0}.payload.advisory_id".format(evidence_id),
                "traffic_conditions[*].incident_id", incident,
            ),
            "road_name": decisions.copied(
                "evidence.{0}.payload.road_name".format(evidence_id),
                "traffic_conditions[*].road", condition["road"],
            ),
            "type": decisions.judged(
                "evidence.{0}.payload.type".format(evidence_id),
                str(condition["incident_type"]).upper(),
                "The source's own incident_type, upper-cased. It is the source's "
                "token and not this corpus's vocabulary: the corpus writes CLOSURE, "
                "ACCIDENT or KERB_RESTRICTION, and POL-RD-23 names 'congestion, an "
                "incident or a closure'. Whether a vehicle fire is an incident for "
                "that clause is a reading of v2.1's sentence, and it is the policy "
                "owner's to settle -- the type travels as the source states it so "
                "the reading can be made from the record.",
                source="traffic_conditions[*].incident_type",
            ),
            "severity": decisions.copied(
                "evidence.{0}.payload.severity".format(evidence_id),
                "traffic_conditions[*].severity",
                str(condition["severity"]).upper(),
                "The source's own severity, upper-cased to this corpus's spelling.",
            ),
            "active_from": decisions.copied(
                "evidence.{0}.payload.active_from".format(evidence_id),
                "traffic_conditions[*].timestamp", condition["timestamp"],
            ),
            "active_to": decisions.copied(
                "evidence.{0}.payload.active_to".format(evidence_id),
                "traffic_conditions[*].clear_time", condition["clear_time"],
                "Null where the source states no clear time, which is what an "
                "open-ended incident is.",
            ),
            "description": decisions.copied(
                "evidence.{0}.payload.description".format(evidence_id),
                "traffic_conditions[*].description", condition["description"],
            ),
            "advisory_source": decisions.judged(
                "evidence.{0}.payload.advisory_source".format(evidence_id),
                "SOURCE_RECORD",
                "An opaque code: the advisory came from the record itself. The "
                "source names no feed, and minting a third party's name would "
                "assert one.",
            ),
            # The two readings POL-RD-23 makes. Both are recorded above, and both
            # are carried here: the decision log says how each was arrived at and
            # the payload is what the policy reads.
            "intersects_route": judged_intersects,
            "overlaps_trip_window": judged_overlaps,
        }
        decisions.judged(
            "traffic_conditions[*].direction, traffic_conditions[*].stretch",
            None,
            "Dropped: this corpus's advisory payload has no field for a direction "
            "or a stretch. The road name, the description and the window carry the "
            "same facts, and the entry's own identity is on the advisory_id.",
            source="traffic_conditions[*].direction, traffic_conditions[*].stretch",
        )
        decisions.judged(
            "evidence.{0}.payload.geometry".format(evidence_id), None,
            "Null: the source gives no geometry box for any of its traffic "
            "conditions. The corpus's advisories carry one; inventing a box would "
            "assert a stretch of road nobody mapped.",
        )
        built.append(
            _artifact(
                decisions, evidence_id, "TRAFFIC_ADVISORY", "THIRD_PARTY_LTA",
                trip_id, export_at, payload, [], (
                    "The source's own traffic condition, with its type and severity "
                    "upper-cased and its route reading judged from the source's "
                    "traffic_analysis. It carries no geometry, because the source "
                    "gives none."
                ), assessed_at,
            )
        )
    return built


def _overlaps(
    trip_start: str, trip_end: str, active_from: Any, active_to: Any
) -> bool:
    """Whether an advisory's window overlaps the trip's.

    An entry with no clear time is still active, so its window is open and
    overlaps any trip that starts after it does. The comparison is on instants
    and not on their text.
    """
    from datetime import datetime

    if not isinstance(active_from, str):
        return False
    start = datetime.fromisoformat(trip_start)
    end = datetime.fromisoformat(trip_end)
    opened = datetime.fromisoformat(active_from)
    if active_to is None:
        return opened <= end
    closed = datetime.fromisoformat(active_to)
    return opened <= end and closed >= start


def convert_route_deviation(block_text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build case 902 and its mapping record from the route-deviation block.

    The case is the organisers' sample converted for policy version 7: the
    distances POL-RD-22 subtracts, the rate POL-RD-24 multiplies by, one
    TRAFFIC_ADVISORY per traffic condition, the chat log POL-RD-21 indexes, and
    the two profiles POL-GEN-22 reads a fraud flag off.
    """
    source = parse_route_deviation_source(block_text)
    decisions = Decisions()

    ticket = source["dispute_ticket"]
    rider_profile = source["rider_profile"]
    driver_profile = source["driver_profile"]
    trip = source["trip_data"]
    fare = source["fare_breakdown"]
    route = source["optimal_route"]

    trip_id = decisions.copied("trip_id", "dispute_ticket.trip_id", ticket["trip_id"])
    export_at = decisions.judged(
        "evidence[*].generated_at", ticket["filed_at"],
        "The source states no export time. The dispute's own filing time is used, "
        "because it is a real timestamp from the source and falls after every event "
        "the records describe, which is what an export time has to be.",
        source="dispute_ticket.filed_at",
    )
    assessed_at = decisions.judged(
        "evidence[*].admissibility.assessed_at", _plus_seconds(ticket["filed_at"], 5),
        "The admissibility pre-pass runs when the records are assembled. The corpus "
        "stamps its own blocks five seconds after generated_at, so the same offset "
        "is used rather than a second invented instant.",
    )

    artifacts = [
        _route_trip_record(
            decisions, trip, route, ticket, source["chat_logs"], export_at, assessed_at
        ),
        _route_gps_trace(decisions, source["gps_telemetry"], trip, trip_id, export_at, assessed_at),
        _route_chat_log(decisions, source["chat_logs"], trip_id, export_at, assessed_at),
        _route_fare(decisions, fare, trip, export_at, assessed_at),
        _rider(
            decisions, rider_profile, trip_id, export_at, assessed_at,
            V7_POLICY_VERSION, ROUTE_DEVIATION_SUFFIX,
        ),
        _driver(
            decisions, driver_profile, trip_id, export_at, assessed_at,
            V7_POLICY_VERSION, ROUTE_DEVIATION_SUFFIX, DRIVER_COUNTERS_STATED,
        ),
    ]
    artifacts += _route_advisories(
        decisions, source["traffic_conditions"], trip, trip_id, export_at, assessed_at
    )

    evidence_ids = [artifact["evidence_id"] for artifact in artifacts]

    dispute = {
        "dispute_id": decisions.copied(
            "dispute.dispute_id", "dispute_ticket.dispute_id", ticket["dispute_id"]
        ),
        "trip_id": trip_id,
        "case_no": decisions.judged(
            "dispute.case_no", ROUTE_DEVIATION_CASE_NO,
            "A converted case is numbered outside the corpus range (101-115, "
            "201-214) so it can never be mistaken for a corpus case. 902 is this "
            "set's route-deviation case.",
        ),
        "category": decisions.judged(
            "dispute.category", ROUTE_DEVIATION_CATEGORY,
            "The source calls this dispute_type 'route_deviation'. ROUTE_DEVIATION is "
            "this system's token for that, and it is what selects "
            "policy/v7/route_deviation.json.",
            source="dispute_ticket.dispute_type",
        ),
        "filed_by": decisions.judged(
            "dispute.filed_by", ticket["filed_by"].upper(),
            "Copied in substance and upper-cased: the source writes 'rider' and this "
            "corpus's vocabulary is RIDER.",
            source="dispute_ticket.filed_by",
        ),
        "filed_at": decisions.copied(
            "dispute.filed_at", "dispute_ticket.filed_at", ticket["filed_at"]
        ),
        "claim_text": decisions.copied(
            "dispute.claim_text", "dispute_ticket.description", ticket["description"]
        ),
        "amount_contested_sgd": decisions.judged(
            "dispute.amount_contested_sgd", float(trip["excess_fare"]),
            "The source has no 'amount contested' field. The rider asks for the "
            "excess fare back -- 'The extra distance was 4.3 km and I was "
            "overcharged. I am requesting a refund of the excess fare' -- and the "
            "source's own excess_fare is 6.50, so that is the figure contested. "
            "POL-GEN-22 reads this value to pick the band.",
            source="trip_data.excess_fare",
        ),
        "counterparty_statement": decisions.judged(
            "dispute.counterparty_statement", None,
            "The source carries no statement from the driver. It is left null rather "
            "than substituted with an empty string or reconstructed from the chat "
            "log, which is a different artifact.",
        ),
        "channel": decisions.judged(
            "dispute.channel", "IN_APP_SUPPORT",
            "The source states no filing channel. IN_APP_SUPPORT is this corpus's "
            "value in 28 of 29 cases and the dispute is an in-app dispute; the field "
            "is presentation and no clause in either policy reads it.",
        ),
        "evidence_ids": decisions.judged(
            "dispute.evidence_ids", evidence_ids,
            "The ids are minted by this conversion. The corpus cites every artifact "
            "the case holds, so every minted artifact is cited.",
        ),
    }

    decisions.judged(
        "rider_profile.account_created_at, rider_profile.loyalty_tier, "
        "rider_profile.payment_provider, rider_profile.frequent_corridors[*], "
        "rider_profile.dispute_history.last_dispute_date",
        None,
        "Dropped: this corpus's rider-profile schema has no field for an account "
        "creation instant, a loyalty tier, a payment provider, a list of frequent "
        "corridors or the date of the last dispute. The counters that describe the "
        "same history -- prior_disputes_filed and prior_disputes_upheld -- are "
        "carried. The payment provider names a card, which is personal data no "
        "clause reads.",
        source="rider_profile.account_created_at, rider_profile.loyalty_tier, "
               "rider_profile.payment_provider, rider_profile.frequent_corridors[*], "
               "rider_profile.dispute_history.last_dispute_date",
    )
    decisions.judged(
        "driver_profile.name, driver_profile.account_created_at, "
        "driver_profile.completion_rate, driver_profile.license_class, "
        "driver_profile.vehicle_color, driver_profile.partner_since, "
        "driver_profile.recent_compliments[*], "
        "driver_profile.dispute_history.rejected, "
        "driver_profile.dispute_history.last_dispute_date",
        None,
        "Dropped: this corpus's driver-profile schema has no field for a name, an "
        "account creation instant, a licence class, a vehicle colour, a partner "
        "date, a list of compliments, a rejected-dispute count or a last-dispute "
        "date, and no field for a completion rate -- this corpus records a "
        "cancellation rate and not its complement. The name is personal data that "
        "no clause reads; the vehicle's tier is carried as vehicle_type; the "
        "cancellation rate the source states IS carried. prior_disputes_filed and "
        "prior_disputes_upheld carry the rest of the history.",
        source="driver_profile.name, driver_profile.account_created_at, "
               "driver_profile.completion_rate, driver_profile.license_class, "
               "driver_profile.vehicle_color, driver_profile.partner_since, "
               "driver_profile.recent_compliments[*], "
               "driver_profile.dispute_history.rejected, "
               "driver_profile.dispute_history.last_dispute_date",
    )
    decisions.judged(
        "dispute_ticket.filed_by_id, dispute_ticket.status, dispute_ticket.priority, "
        "dispute_ticket.assigned_to, dispute_ticket.evidence_provided[*]",
        None,
        "Dropped: the rider's id is already on the trip record as rider_id; the "
        "ticket's status and priority are the source platform's workflow fields and "
        "no clause reads one; assigned_to names the source's own auto-resolution "
        "route; and evidence_provided is a list of screenshot names the source "
        "platform offered, not artifacts this case carries. None of the five is "
        "carried.",
        source="dispute_ticket.filed_by_id, dispute_ticket.status, "
               "dispute_ticket.priority, dispute_ticket.assigned_to, "
               "dispute_ticket.evidence_provided[*]",
    )

    case = {
        "schema_version": decisions.copied(
            "schema_version", "the corpus contract", SCHEMA_VERSION,
            "data/PUBLIC-CONTRACT.md fixes the top-level value as \"1.2.0\" in all 29 "
            "corpus cases; a converted case is not a corpus case and may differ.",
        ),
        "case_no": ROUTE_DEVIATION_CASE_NO,
        "dispute": dispute,
        "evidence": artifacts,
    }

    mapping = {
        "source_document": DISP001_SOURCE_DOCUMENT,
        "source_dispute_id": ticket["dispute_id"],
        "converted_case_no": ROUTE_DEVIATION_CASE_NO,
        "converted_case_file": "external/{0}/case-{1:05d}.json".format(
            OUTPUT_DIR_FOR_VERSION[V7_POLICY_VERSION].name, ROUTE_DEVIATION_CASE_NO
        ),
        "policy_version": V7_POLICY_VERSION,
        "note": (
            "Every field of the converted case, with whether the conversion copied it "
            "or judged it, and why. The source's own expected ruling and its "
            "recommended ruling are not listed here because nothing in them reached "
            "the conversion; the five keys that carry them are named under "
            "answer_bearing_keys_excluded."
        ),
        "answer_bearing_keys_excluded": [
            {
                "key": key,
                "reason": (
                    "Answer-bearing: it carries the organisers' own expected ruling, "
                    "their analysis or their recommended ruling. It is never read, "
                    "never parsed and never listed in this record's fields, so no "
                    "expected outcome can reach the converted case."
                ),
            }
            for key in DISP001_ANSWER_BEARING_KEYS
        ],
        "fields": decisions.entries,
        "policy_divergences": _route_divergences(trip, fare),
        "assumptions": [
            {
                "assumption": "pickup zone class is STANDARD",
                "depends_on_it": [
                    "the v2.1 policy carries no zone-class table, so nothing in the "
                    "version-7 brief depends on it; the field is carried because the "
                    "corpus's trip-record schema has it",
                ],
                "reason": (
                    "The source gives a pickup place name and no zone class. "
                    "Inferring one from what the place is would be world knowledge "
                    "about places, which this repository's prompts forbid."
                ),
            },
            {
                "assumption": "vehicle tier is RYDE_X",
                "depends_on_it": [
                    "the trip record's vehicle_type, which no version-7 clause reads",
                ],
                "reason": (
                    "The source names a Toyota Vios, which is not a tier name in this "
                    "corpus. RYDE_X is this corpus's base tier."
                ),
            },
            {
                "assumption": (
                    "the two PIE traffic conditions intersect the recommended route "
                    "and the ECP flow report does not"
                ),
                "depends_on_it": [
                    "POL-RD-23's intersects_route limb on each advisory",
                ],
                "reason": (
                    "The source states it in words rather than as a field: its "
                    "traffic_analysis says the vehicle fire 'made the optimal route "
                    "impassable for much of the trip window' and calls the ECP entry "
                    "a report on the alternative the driver took. The reading is "
                    "recorded per advisory in the fields above."
                ),
            },
        ],
    }
    return case, mapping


def _route_trip_record(
    decisions: Decisions, trip: Dict[str, Any], route: Dict[str, Any],
    ticket: Dict[str, Any], chats: List[Dict[str, Any]], export_at: str,
    assessed_at: str,
) -> Dict[str, Any]:
    """TRIP_RECORD for the route deviation, with both recorded distances.

    POL-RD-22 subtracts ``optimal_distance_km`` from ``actual_distance_km``, and
    both are the source's own figures. The trace is not used to re-measure
    either, which is why the GPS payload carries no distance of its own.
    """
    payload = {
        "trip_id": decisions.copied(
            "evidence.EV-TRIP-00902.payload.trip_id", "trip_data.trip_id", trip["trip_id"]
        ),
        "rider_id": decisions.copied(
            "evidence.EV-TRIP-00902.payload.rider_id", "trip_data.rider_id",
            trip["rider_id"],
            "Copied unchanged. The source's id form (R-4521) differs from this "
            "corpus's (RDR-02073); the value is carried as given.",
        ),
        "driver_id": decisions.copied(
            "evidence.EV-TRIP-00902.payload.driver_id", "trip_data.driver_id",
            trip["driver_id"],
            "Copied unchanged, for the same reason as rider_id (source form D-1187).",
        ),
        "started_at": decisions.copied(
            "evidence.EV-TRIP-00902.payload.started_at", "trip_data.start_time",
            trip["start_time"],
        ),
        "ended_at": decisions.copied(
            "evidence.EV-TRIP-00902.payload.ended_at", "trip_data.end_time",
            trip["end_time"],
        ),
        "status": decisions.judged(
            "evidence.EV-TRIP-00902.payload.status", "COMPLETED",
            "The source describes a completed trip, from pickup to dropoff, and the "
            "dispute is about its fare.",
            source="trip_data.start_time, trip_data.end_time",
        ),
        "actual_distance_km": decisions.copied(
            "evidence.EV-TRIP-00902.payload.actual_distance_km",
            "trip_data.actual_distance_km", trip["actual_distance_km"],
            "POL-RD-22's own field, copied from the source's own distance.",
        ),
        "optimal_distance_km": decisions.copied(
            "evidence.EV-TRIP-00902.payload.optimal_distance_km",
            "trip_data.estimated_distance_km, optimal_route.estimated_distance_km",
            route["estimated_distance_km"],
            "The recommended route's distance. The source states it twice -- in the "
            "trip record as estimated_distance_km and in optimal_route -- and the "
            "two agree; both are named rather than the second left unrecorded.",
        ),
        "optimal_duration_min": decisions.copied(
            "evidence.EV-TRIP-00902.payload.optimal_duration_min",
            "trip_data.estimated_duration_min, optimal_route.estimated_duration_min",
            route["estimated_duration_min"],
            "The recommended route's duration, stated twice and agreeing, as above.",
        ),
        "actual_duration_min": decisions.copied(
            "evidence.EV-TRIP-00902.payload.actual_duration_min",
            "trip_data.actual_duration_min", trip["actual_duration_min"],
        ),
        "pickup": {
            "label": decisions.copied(
                "evidence.EV-TRIP-00902.payload.pickup.label",
                "trip_data.pickup_location.name", trip["pickup_location"]["name"],
            ),
            "lat": decisions.copied(
                "evidence.EV-TRIP-00902.payload.pickup.lat",
                "trip_data.pickup_location.lat", trip["pickup_location"]["lat"],
            ),
            "lng": decisions.copied(
                "evidence.EV-TRIP-00902.payload.pickup.lng",
                "trip_data.pickup_location.lng", trip["pickup_location"]["lng"],
            ),
            "venue_id": decisions.judged(
                "evidence.EV-TRIP-00902.payload.pickup.venue_id", None,
                "The source carries no venue identifier, and v2.1 has no clause that "
                "reads one. Minting one would assert a venue nobody recorded.",
            ),
        },
        "dropoff": {
            "label": decisions.copied(
                "evidence.EV-TRIP-00902.payload.dropoff.label",
                "trip_data.dropoff_location.name", trip["dropoff_location"]["name"],
            ),
            "lat": decisions.copied(
                "evidence.EV-TRIP-00902.payload.dropoff.lat",
                "trip_data.dropoff_location.lat", trip["dropoff_location"]["lat"],
            ),
            "lng": decisions.copied(
                "evidence.EV-TRIP-00902.payload.dropoff.lng",
                "trip_data.dropoff_location.lng", trip["dropoff_location"]["lng"],
            ),
            "venue_id": decisions.judged(
                "evidence.EV-TRIP-00902.payload.dropoff.venue_id", None,
                "The source carries no venue identifier, for the same reason as pickup.",
            ),
        },
        "vehicle_type": decisions.judged(
            "evidence.EV-TRIP-00902.payload.vehicle_type", ASSUMED_VEHICLE_TIER,
            "The source names a Toyota Vios, which is not a tier in this corpus. "
            "RYDE_X is the base tier and the choice is recorded as an assumption.",
            source="driver_profile.vehicle",
        ),
        "pickup_zone_class": decisions.judged(
            "evidence.EV-TRIP-00902.payload.pickup_zone_class", ASSUMED_ZONE_CLASS,
            "The source states no zone class. STANDARD is used as an explicitly "
            "stated assumption and not inferred from the place name. No version-7 "
            "clause reads it.",
        ),
        "chat_message_count": decisions.judged(
            "evidence.EV-TRIP-00902.payload.chat_message_count", len(chats),
            "The count of chat_logs entries the source supplies.",
        ),
        "in_app_calls": decisions.judged(
            "evidence.EV-TRIP-00902.payload.in_app_calls", [],
            "The source's chat log carries no call: all six entries are messages. "
            "An empty list rather than a minted call, because POL-RD-21 reads the "
            "messages and v2.1 has no clause that reads a call on a route deviation.",
        ),
        "deviation_pct": decisions.judged(
            "evidence.EV-TRIP-00902.payload.deviation_pct",
            round(
                (float(trip["actual_distance_km"]) - float(route["estimated_distance_km"]))
                / float(route["estimated_distance_km"])
                * 100.0,
                2,
            ),
            "Computed from the two recorded distances: (24.8 - 20.5) / 20.5. It is "
            "the corpus's own field and no version-7 clause reads it; POL-RD-22's "
            "reading is the difference in kilometres, which the brief publishes.",
            source="trip_data.actual_distance_km, trip_data.estimated_distance_km",
        ),
    }

    for field, reason in (
        ("requested_at", "the source states no booking time"),
        ("accepted_at", "the source states no assignment time"),
        ("arrived_at", "the source states no arrival event"),
        ("cancelled_at", "the trip ran to its dropoff and was not cancelled"),
        ("cancelled_by", "the trip was not cancelled"),
        ("cancellation_reason_code", "the trip was not cancelled"),
        ("optimal_route_source", "the source names no routing engine"),
        ("optimal_route_erp_sgd", "the source gives no ERP figure for the route"),
        ("amended_optimal_distance_km", "the pickup was never amended"),
        ("amended_optimal_duration_min", "the pickup was never amended"),
        ("solo_optimal_distance_km", "there is no co-rider data in the source"),
        ("registered_pickup_points", "the source does not say how many registered pickup points the location has"),
        ("pickup_amended_at", "the source records no amendment to either end of the trip"),
        ("dropoff_amended_at", "the source records no amendment to either end of the trip"),
        ("original_pickup", "the source records no amendment to either end of the trip"),
        ("original_dropoff", "the source records no amendment to either end of the trip"),
    ):
        payload[field] = decisions.judged(
            "evidence.EV-TRIP-00902.payload." + field, None,
            "Null rather than a plausible value: {0}.".format(reason),
        )

    decisions.judged(
        "trip_data.excess_distance_km, trip_data.excess_fare, trip_data.route_deviated, "
        "trip_data.estimated_fare, trip_data.actual_fare, trip_data.weather, "
        "trip_data.trip_type",
        None,
        "Read and not carried: excess_distance_km (4.3) and excess_fare (6.50) are "
        "the source's own restatements of the difference between the two distances "
        "and the two fares, and both are carried as the distances and the amounts "
        "themselves; route_deviated is a boolean the two distances already answer; "
        "the two fares are carried on the fare artifact; weather and trip_type are "
        "presentation fields no version-7 clause reads.",
        source="trip_data.excess_distance_km, trip_data.excess_fare, "
               "trip_data.route_deviated, trip_data.estimated_fare, "
               "trip_data.actual_fare, trip_data.weather, trip_data.trip_type",
    )
    decisions.judged(
        "optimal_route.route_name, optimal_route.total_waypoints, optimal_route.notes",
        None,
        "Read and not carried: the route name, its waypoint count and its note "
        "describe the recommended route. The distance and the duration are carried, "
        "which is what POL-RD-22 subtracts; the rest has no field in this corpus's "
        "trip record.",
        source="optimal_route.route_name, optimal_route.total_waypoints, "
               "optimal_route.notes",
    )
    decisions.judged(
        "optimal_route.waypoints[*].point, optimal_route.waypoints[*].lat, "
        "optimal_route.waypoints[*].lng, optimal_route.waypoints[*].location_desc",
        None,
        "Dropped: the recommended route's own waypoints. POL-RD-22 is explicit that "
        "the distance is the platform's recorded figure and that a trace is not used "
        "to re-measure it, so the route's geometry would be an alternative "
        "measurement the clause refuses. The route's distance is carried.",
        source="optimal_route.waypoints[*].point, optimal_route.waypoints[*].lat, "
               "optimal_route.waypoints[*].lng, optimal_route.waypoints[*].location_desc",
    )
    decisions.judged(
        "trip_data.pickup_location.address, trip_data.dropoff_location.address",
        None,
        "Dropped: this corpus's trip record holds a label and a position for each "
        "end of the trip, and no street address. Both addresses are in the source "
        "and neither is read by any clause of either policy.",
        source="trip_data.pickup_location.address, trip_data.dropoff_location.address",
    )
    decisions.judged(
        "gps_telemetry[*].location_desc",
        None,
        "Read and not carried: the place description beside each fix. This corpus's "
        "trace schema holds a position, a time and a speed, and the descriptions are "
        "the source's own prose about the places rather than a measurement.",
        source="gps_telemetry[*].location_desc",
    )

    notes = (
        "The source's own trip record, with both recorded distances: 24.8 km actual "
        "against 20.5 km on the recommended route, which is what POL-RD-22 "
        "subtracts. The trace is not used to re-measure either, because POL-RD-22 "
        "says so and a sparse trace understates a route's length. No fix carries a "
        "reported accuracy, so POL-NS-02's presence test is not this case's and no "
        "arrival is established from the trace. pickup_zone_class and vehicle_type "
        "are stated assumptions, recorded in the mapping record; the source gives "
        "neither."
    )
    return _artifact(
        decisions, "EV-TRIP-00902", "TRIP_RECORD", "PLATFORM_TELEMETRY",
        trip["trip_id"], export_at, payload, [], notes, assessed_at,
    )


def _route_gps_trace(
    decisions: Decisions, fixes: List[Dict[str, Any]], trip: Dict[str, Any],
    trip_id: str, export_at: str, assessed_at: str,
) -> Dict[str, Any]:
    """GPS_TRACE, with the accuracy the source does not have left absent.

    The trace shows which route was taken and when. It is not used to measure
    anything POL-RD-22 decides, and the block says so.
    """
    timestamps = [fix["timestamp"] for fix in fixes]
    intervals = [
        _seconds_between(timestamps[index], timestamps[index + 1])
        for index in range(len(timestamps) - 1)
    ]
    median = statistics.median(intervals)
    over_limb = [interval for interval in intervals if interval > 120]

    points = []
    for fix in fixes:
        points.append(
            {
                "lat": decisions.copied(
                    "evidence.EV-GPS-00902.payload.points[*].lat",
                    "gps_telemetry[*].lat", fix["lat"],
                ),
                "lng": decisions.copied(
                    "evidence.EV-GPS-00902.payload.points[*].lng",
                    "gps_telemetry[*].lng", fix["lng"],
                ),
                "ts": decisions.copied(
                    "evidence.EV-GPS-00902.payload.points[*].ts",
                    "gps_telemetry[*].timestamp", fix["timestamp"],
                ),
                "speed_kph": decisions.copied(
                    "evidence.EV-GPS-00902.payload.points[*].speed_kph",
                    "gps_telemetry[*].speed_kmh", fix["speed_kmh"],
                ),
            }
        )
    decisions.judged(
        "gps_telemetry[*].point", None,
        "Read and not carried: the source's own 1-based point number. The array's "
        "order carries it, and the corpus's point schema has no such field.",
        source="gps_telemetry[*].point",
    )

    payload = {
        "trip_id": trip_id,
        "points": points,
        "point_count": decisions.judged(
            "evidence.EV-GPS-00902.payload.point_count", len(points),
            "The number of fixes the source supplies.",
        ),
        "first_fix_at": decisions.judged(
            "evidence.EV-GPS-00902.payload.first_fix_at", timestamps[0],
            "The first fix timestamp the source supplies.",
        ),
        "last_fix_at": decisions.judged(
            "evidence.EV-GPS-00902.payload.last_fix_at", timestamps[-1],
            "The last fix timestamp the source supplies.",
        ),
        "sample_interval_sec": decisions.judged(
            "evidence.EV-GPS-00902.payload.sample_interval_sec", float(median),
            "Measured from the source's own timestamps: the intervals between "
            "consecutive fixes are {0} s, whose median is {1} s. The source states "
            "no nominal rate.".format(intervals, median),
        ),
        "expected_interval_sec": decisions.judged(
            "evidence.EV-GPS-00902.payload.expected_interval_sec", None,
            "The source names no nominal sampling rate, so there is nothing to call "
            "expected.",
        ),
        "gaps": decisions.judged(
            "evidence.EV-GPS-00902.payload.gaps",
            [
                {"from": timestamps[index], "to": timestamps[index + 1], "gap_sec": float(interval)}
                for index, interval in enumerate(intervals)
                if interval > 120
            ],
            "Intervals longer than the version-7 policy's own 120 s limb, measured "
            "from the source's timestamps: {0} of the {1} exceed it.".format(
                len(over_limb), len(intervals)
            ),
        ),
        "max_gap_sec": decisions.judged(
            "evidence.EV-GPS-00902.payload.max_gap_sec", float(max(intervals)),
            "The longest interval measured from the source's timestamps.",
        ),
        "coverage_pct": decisions.judged(
            "evidence.EV-GPS-00902.payload.coverage_pct", None,
            "Coverage is a ratio against an expected rate. The source names no rate, "
            "so a percentage would be computed against a denominator nobody supplied.",
        ),
        "trace_distance_km": decisions.judged(
            "evidence.EV-GPS-00902.payload.trace_distance_km", None,
            "The source gives no distance, and summing sixteen fixes minutes apart "
            "would understate the driven path by an unknown amount. POL-RD-22 is "
            "explicit that the recorded distances govern and the trace is not used to "
            "re-measure them.",
        ),
        "rider_track": decisions.judged(
            "evidence.EV-GPS-00902.payload.rider_track", [],
            "There is no rider GPS track in the source. An empty list rather than "
            "points minted.",
        ),
    }
    notes = (
        "Sparse telemetry with no reported accuracy, showing the route taken. The "
        "intervals between the source's own timestamps are {0} s, {1} of the {2} "
        "exceeding the version-7 policy's 120 s limb. No fix carries accuracy_m, so "
        "under POL-NS-02 every one of them is evidence of neither presence nor "
        "absence; no version-7 route-deviation clause reads the trace's geometry, "
        "because POL-RD-22 measures the deviation from the trip record's own two "
        "distances.".format(intervals, len(over_limb), len(intervals))
    )
    return _artifact(
        decisions, "EV-GPS-00902", "GPS_TRACE", "DRIVER_DEVICE",
        trip_id, export_at, payload, ["LOW_SAMPLE_RATE"], notes, assessed_at,
    )


def _route_chat_log(
    decisions: Decisions, chats: List[Dict[str, Any]], trip_id: str,
    export_at: str, assessed_at: str,
) -> Dict[str, Any]:
    """CHAT_LOG for the route deviation: six messages, and no call."""
    sender_map = {"driver": "DRIVER", "rider": "RIDER", "system": "SYSTEM"}
    messages = []
    for index, entry in enumerate(chats, start=1):
        sender = sender_map.get(entry["sender"])
        if sender is None:
            raise ConversionError("unknown chat sender {0!r}".format(entry["sender"]))
        messages.append(
            {
                "msg_id": decisions.judged(
                    "evidence.EV-CHAT-00902.payload.messages[*].msg_id",
                    "MSG-00902-{0:03d}".format(index),
                    "Minted consecutively, from the source's own message_id order.",
                ),
                "sender": decisions.judged(
                    "evidence.EV-CHAT-00902.payload.messages[*].sender", sender,
                    "The source's lower-case sender, upper-cased to this corpus's "
                    "vocabulary.",
                    source="chat_logs[*].sender",
                ),
                "text": decisions.copied(
                    "evidence.EV-CHAT-00902.payload.messages[*].text",
                    "chat_logs[*].message", entry["message"],
                ),
                "sent_at": decisions.copied(
                    "evidence.EV-CHAT-00902.payload.messages[*].sent_at",
                    "chat_logs[*].timestamp", entry["timestamp"],
                ),
                "read_at": decisions.judged(
                    "evidence.EV-CHAT-00902.payload.messages[*].read_at", None,
                    "The source carries no read receipt for any message. Null rather "
                    "than a copy of sent_at, which would assert a read.",
                ),
                "delivered_at": decisions.judged(
                    "evidence.EV-CHAT-00902.payload.messages[*].delivered_at", None,
                    "The source carries no delivery receipt, for the same reason.",
                ),
                "channel": decisions.judged(
                    "evidence.EV-CHAT-00902.payload.messages[*].channel",
                    MESSAGE_CHANNEL,
                    "The source's chat log is the in-app log and carries no channel "
                    "field. Every entry is a message; the source records no call on "
                    "this trip.",
                ),
                "language": decisions.judged(
                    "evidence.EV-CHAT-00902.payload.messages[*].language", "en",
                    "The source's messages are written in English.",
                ),
                "redacted": decisions.judged(
                    "evidence.EV-CHAT-00902.payload.messages[*].redacted", False,
                    "Nothing in the source is marked as redacted, and no text is "
                    "withheld.",
                ),
                "waypoint_hint": decisions.judged(
                    "evidence.EV-CHAT-00902.payload.messages[*].waypoint_hint", None,
                    "The source names no waypoint hint.",
                ),
            }
        )
    decisions.judged(
        "chat_logs[*].message_id, chat_logs[*].sender_name", None,
        "Read and not carried: the source's own message id (MSG-001 ...), which this "
        "conversion replaces with a contiguous minted sequence, and each sender's "
        "name, which this corpus's message schema has no field for and which no "
        "clause reads. The names are personal data and the messages travel as the "
        "source wrote them.",
        source="chat_logs[*].message_id, chat_logs[*].sender_name",
    )

    payload = {
        "trip_id": trip_id,
        "messages": messages,
        "message_count": decisions.judged(
            "evidence.EV-CHAT-00902.payload.message_count", len(messages),
            "The number of chat_logs entries the source supplies.",
        ),
        "first_message_at": decisions.judged(
            "evidence.EV-CHAT-00902.payload.first_message_at", chats[0]["timestamp"],
            "The first chat_logs timestamp the source supplies.",
        ),
        "last_message_at": decisions.judged(
            "evidence.EV-CHAT-00902.payload.last_message_at", chats[-1]["timestamp"],
            "The last chat_logs timestamp the source supplies.",
        ),
        "truncated": decisions.judged(
            "evidence.EV-CHAT-00902.payload.truncated", False,
            "Nothing in the source indicates the log was cut short.",
        ),
    }
    notes = (
        "The source's own chat log, six entries, contiguous by construction. The "
        "rider asks whether the route is the usual one at 13:24 and the driver does "
        "not explain it: POL-RD-21's reading of the messages sent while the trip ran "
        "is published in the brief, and the text stays here."
    )
    return _artifact(
        decisions, "EV-CHAT-00902", "CHAT_LOG", "PLATFORM_TELEMETRY",
        trip_id, export_at, payload, [], notes, assessed_at,
    )


def _route_divergences(trip: Dict[str, Any], fare: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Where the source's policy and v2.1 disagree, on the route-deviation sample.

    Recorded, not resolved: the case runs under the loaded policy unchanged, so
    each divergence is a fact about the conversion rather than something the
    converted case can express.
    """
    return [
        {
            "finding": "The source's Driver Policy 4.2 makes a failure to notify the rider render the driver liable for the excess fare.",
            "source_policy": (
                "traffic_analysis.policy_reference: 'Drivers must inform the rider of "
                "any route deviation ... Failure to notify renders the driver liable "
                "for excess fare charges attributable to the unnotified deviation.'"
            ),
            "this_system": (
                "POL-RD-24 states the remedy as a matrix: a traffic-justified reroute "
                "the rider was not informed of refunds the excess distance fare "
                "(row (b)), and one that is not traffic-justified refunds it in full "
                "(row (d)). The source's rule reaches the same figure for row (b)."
            ),
            "effect": (
                "The converted case carries no remedy. POL-RD-24 is read from the "
                "loaded policy at arbitration time, and the money block publishes the "
                "excess distance fare the clause computes."
            ),
            "depends_on_assumptions": [],
        },
        {
            "finding": "The source states the excess distance fare itself, and it does not equal the deviation times the rate it also states.",
            "source_policy": (
                "fare_breakdown.excess_distance_fare: 3.44, from a deviation the "
                "source gives as 4.3 km and a rate its note gives as $0.80/km, which "
                "multiply to 3.44."
            ),
            "this_system": (
                "POL-RD-24 computes the excess distance fare as the deviation "
                "distance times fare_breakdown.per_km_rate_sgd, to the cent. 4.30 x "
                "0.80 is 3.44, so the source's own figure and this system's "
                "arithmetic agree on this case."
            ),
            "effect": (
                "The converted case carries the rate and the two distances, and the "
                "money block computes the fare. The source's own figure is not "
                "carried beside it, because two answers to one question is one too "
                "many."
            ),
            "depends_on_assumptions": [],
        },
        {
            "finding": "The source's own dispute vocabulary is not this system's.",
            "source_policy": (
                "dispute_id DISP-001, status 'open', priority 'medium', "
                "dispute_type 'route_deviation', assigned_to "
                "'RydeResolve_Auto_Resolution'"
            ),
            "this_system": (
                "This corpus's dispute ids are DSP-<case_no>, its category token is "
                "ROUTE_DEVIATION, and it has no 'status', 'priority' or 'assigned_to' "
                "key."
            ),
            "effect": (
                "dispute_id is carried unchanged as DISP-001, so the converted case "
                "can be traced back to the organisers' document; the four workflow "
                "fields are dropped and the drops are recorded."
            ),
            "depends_on_assumptions": [],
        },
        {
            "finding": "The source names a traffic condition type this corpus's advisory vocabulary does not carry.",
            "source_policy": "traffic_conditions[*].incident_type: vehicle_fire, heavy_congestion, traffic_flow",
            "this_system": (
                "The corpus's advisories are typed CLOSURE, ACCIDENT or "
                "KERB_RESTRICTION, and POL-RD-23 names 'congestion, an incident or a "
                "closure'."
            ),
            "effect": (
                "Each type travels upper-cased exactly as the source states it, so "
                "the reading of whether it is a kind POL-RD-23 names can be made from "
                "the record rather than decided by the conversion."
            ),
            "depends_on_assumptions": [],
        },
    ]


def write_version_seven_outputs() -> Tuple[Path, ...]:
    """Convert both samples and write the ``ryde-v7`` set.

    The set is two cases, their two mappings and the set's own ``index.json``.
    The index records each case file's sha256, which
    :func:`tribunal.loader.load_external_set_case` holds the file to, so a case
    edited after it was written is refused rather than loaded.

    ``DISP-003``, the organisers' fare-dispute sample, is **not** converted. It
    is a v2.1 Section 3 dispute, which POL-GEN-24 routes to human review rather
    than adjudicating, and this corpus's schema carries two categories --
    ``ROUTE_DEVIATION`` and ``NO_SHOW_CHARGE``. There is no ``FARE_DISPUTE``
    category for a case to declare and no policy file for it to select, so the
    loader would refuse the case rather than convert it. The set's README says
    so.
    """
    directory = OUTPUT_DIR_FOR_VERSION[V7_POLICY_VERSION]
    directory.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    entries: List[Dict[str, Any]] = []

    sources = (
        (DISP001_SOURCE_PATH, DISP001_SOURCE_DOCUMENT, "route_deviation"),
        (SOURCE_PATH, "eval/external/ryde/DISP-002.md", "no_show_charge"),
    )
    for source_path, document, _kind in sources:
        markdown = source_path.read_text(encoding="utf-8")
        block = conversion_input(markdown)
        if source_path == DISP001_SOURCE_PATH:
            case, mapping = convert_route_deviation(block)
            missing = [
                item
                for item in route_deviation_source_items(
                    parse_route_deviation_source(block)
                )
                if item not in set(named_items(mapping))
            ]
        else:
            case, mapping = convert(block, V7_POLICY_VERSION)
            missing = unrecorded_items(parse_source(block), mapping)
        if missing:
            raise ConversionError(
                "the source carries {0} item(s) the conversion neither carried nor "
                "recorded: {1}".format(len(missing), ", ".join(missing))
            )
        case_path = directory / "case-{0:05d}.json".format(case["case_no"])
        mapping_path = directory / "mapping-{0:05d}.json".format(case["case_no"])
        case_path.write_text(
            json.dumps(case, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        mapping_path.write_text(
            json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        written += [case_path, mapping_path]
        entries.append(
            {
                "case_no": case["case_no"],
                "dispute_id": case["dispute"]["dispute_id"],
                "trip_id": case["dispute"]["trip_id"],
                "category": case["dispute"]["category"],
                "file": case_path.name,
                "sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
            }
        )

    index_path = directory / "index.json"
    index_path.write_text(
        json.dumps(sorted(entries, key=lambda entry: entry["case_no"]), indent=2) + "\n",
        encoding="utf-8",
    )
    written.append(index_path)
    return tuple(written)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def write_outputs(
    policy_version: int = DEFAULT_POLICY_VERSION,
) -> Tuple[Path, ...]:
    """Read the source, convert it, and write the output files.

    ``policy_version`` selects the directory and what the case carries. Version 1
    writes the three files it has always written, under ``data/external/ryde/``,
    and nothing about it changes. Version 3 writes the case and its mapping under
    ``data/external/ryde-v3/`` and leaves ``expected.json`` alone: the
    organisers' stated expectation belongs to the sample, not to a second reading
    of it. Version 7 writes the ``ryde-v7`` set -- both samples converted, their
    two mappings and the set's own ``index.json`` -- by
    :func:`write_version_seven_outputs`, and writes nothing under either of the
    other two directories.

    Refuses to write a mapping that drops a source item in silence. The check is
    made here as well as in the test suite because a mapping with a hole in it
    is wrong the moment it is written, not only when something reads it back.
    """
    if policy_version not in POLICY_VERSIONS:
        raise ConversionError(
            "no conversion for policy version {0}; the versions are {1}".format(
                policy_version, ", ".join(str(item) for item in POLICY_VERSIONS)
            )
        )
    if policy_version == V7_POLICY_VERSION:
        return write_version_seven_outputs()
    markdown = SOURCE_PATH.read_text(encoding="utf-8")
    block = conversion_input(markdown)
    case, mapping = convert(block, policy_version)

    missing = unrecorded_items(parse_source(block), mapping)
    if missing:
        raise ConversionError(
            "the source carries {0} item(s) the conversion neither carried nor "
            "recorded: {1}".format(len(missing), ", ".join(missing))
        )

    directory = OUTPUT_DIR_FOR_VERSION[policy_version]
    directory.mkdir(parents=True, exist_ok=True)
    case_path = directory / CASE_NAME
    mapping_path = directory / MAPPING_NAME
    case_path.write_text(
        json.dumps(case, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    mapping_path.write_text(
        json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if policy_version == DEFAULT_POLICY_VERSION:
        EXPECTED_PATH.write_text(
            json.dumps(expected_outcome(markdown), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return case_path, mapping_path, EXPECTED_PATH


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m eval.external.ryde.convert",
        description=(
            "Convert the organisers' sample cases into this repository's case shape. "
            "Version 1 writes data/external/ryde/ and is what the recorded run read; "
            "version 3 writes data/external/ryde-v3/ with the sample's own platform "
            "parameters and its app-event log; version 7 writes "
            "data/external/ryde-v7/, the two samples converted for Ryde's Dispute "
            "Resolution Policy v2.1."
        ),
    )
    parser.add_argument(
        "--policy-version",
        type=int,
        choices=list(POLICY_VERSIONS),
        default=DEFAULT_POLICY_VERSION,
        metavar="N",
        help="which conversion to write: 1 (the default), 3, or 7",
    )
    args = parser.parse_args(argv)
    for path in write_outputs(args.policy_version):
        print("wrote {0}".format(path.relative_to(PROJECT_ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
