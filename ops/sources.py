"""One mocked source system per adapter, over an index built on a case root.

The stretch goal is an "Evidence Collection Agent" that "autonomously
orchestrates multi-modal data retrieval across all tools and APIs". This is the
honest version of it: **a deterministic index over the repository's own case
files, and six adapters that answer key lookups against it.** No model is
called, no network is reached, and nothing here decides what evidence exists --
the case file does, and the adapters can only hand back what is already in it.

**One index, six adapters.** :class:`SourceIndex` reads every case file under one
case root and keys the artifacts two ways: by ``trip_id`` and by ``party_id``.
An adapter is a name, the artifact types it holds, the ``source`` values it
answers for, and the key it is looked up by -- and its one public method is
:meth:`Adapter.fetch`, which returns the artifacts filed under one key.

**A party key is scoped to a trip.** A trip id is unique to one case; a party id
is not. The collusion set holds three disputes between the same rider and the
same driver, so a lookup keyed by party id **alone** would answer with all three
cases' profiles and a case would be handed another case's evidence. Every lookup
the collector makes therefore carries the trip it is being made for, and the
party answer is filtered to artifacts whose own ``trip_id`` is that trip. A
caller that names no trip still gets the party's artifacts over the whole root,
which is what the adapter's own description says it holds; it is the collector
that must never ask that way.

**No adapter ever returns a whole case file.** The index keeps artifacts, not
documents, and there is no method on it that hands a case back. What an adapter
returns is a tuple of artifacts, each the object the case file carries.

**A key that names nothing returns nothing.** An adapter answers with an empty
tuple rather than raising, because a source system that does not hold a record is
the ordinary case for an advisory feed; the collector is where an absent trip
record becomes an error, because without it the parties cannot be looked up.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from ops import OpsError, read_json_document

# The artifact types, in the order every case file files them in and the order
# the collector returns them in.
EVIDENCE_ORDER: Tuple[str, ...] = (
    "TRIP_RECORD",
    "GPS_TRACE",
    "CHAT_LOG",
    "FARE_BREAKDOWN",
    "RIDER_PROFILE",
    "DRIVER_PROFILE",
    "TRAFFIC_ADVISORY",
)

# The two keys an artifact can be filed under.
KEY_TRIP = "trip_id"
KEY_PARTY = "party_id"

# The key each adapter is looked up by.
PROFILE_EVIDENCE_TYPES = ("RIDER_PROFILE", "DRIVER_PROFILE")

# The file name every case file carries.
CASE_FILE_GLOB = "case-*.json"
TRANSCRIPT_SUFFIX = ".transcript.json"


class SourceError(OpsError):
    """An index could not be built, or a case root could not be read."""


class SourceIndex:
    """Every artifact under one case root, filed by trip id and by party id.

    Built once, by reading each case file and indexing its ``evidence`` array.
    The index holds artifacts and never a document: :meth:`artifacts` is the
    only way in, and it answers with the artifacts filed under one key.

    **A key is not unique across a root, and the index does not pretend it is.**
    Two artifacts of one case may share a trip id -- case 104 carries two traffic
    advisories on one trip -- so a key maps to a tuple. That is what a source
    system keyed by ``trip_id`` would answer with, and it is why the collector
    compares what it found with what the case lists rather than assuming one
    artifact per call.

    **A party key spans cases, so it is read with a trip.** A trip id belongs to
    one case; a party id does not, and three disputes of the collusion set are
    between the same rider and the same driver. :meth:`artifacts` therefore takes
    an optional ``trip_id`` that keeps a party answer to one trip's artifacts,
    which is the form the collector uses.
    """

    def __init__(self, case_root: Path) -> None:
        self.case_root = Path(case_root)
        if not self.case_root.is_dir():
            raise SourceError("no case root at {0}".format(self.case_root))
        self._by_trip: Dict[Tuple[str, str], List[Mapping[str, Any]]] = {}
        self._by_party: Dict[Tuple[str, str], List[Mapping[str, Any]]] = {}
        self._case_count = 0
        self._build()

    def _build(self) -> None:
        for path in sorted(self.case_root.rglob(CASE_FILE_GLOB)):
            if path.name.endswith(TRANSCRIPT_SUFFIX):
                continue
            document = read_json_document(path, SourceError)
            if not isinstance(document, Mapping):
                raise SourceError("the case file at {0} is not a JSON object".format(path))
            self._case_count += 1
            for artifact in document.get("evidence") or []:
                if not isinstance(artifact, Mapping):
                    continue
                trip_id = artifact.get("trip_id")
                evidence_type = artifact.get("evidence_type")
                if isinstance(trip_id, str) and isinstance(evidence_type, str):
                    self._by_trip.setdefault((trip_id, evidence_type), []).append(artifact)
                payload = artifact.get("payload")
                if isinstance(payload, Mapping):
                    party_id = payload.get("party_id")
                    if isinstance(party_id, str) and isinstance(evidence_type, str):
                        self._by_party.setdefault((party_id, evidence_type), []).append(artifact)

    @property
    def case_count(self) -> int:
        """How many case files the index was built from."""
        return self._case_count

    def artifacts(
        self,
        key: str,
        key_kind: str,
        evidence_types: Sequence[str],
        sources: Optional[Sequence[str]] = None,
        trip_id: Optional[str] = None,
    ) -> Tuple[Mapping[str, Any], ...]:
        """The artifacts filed under one key, of these types and sources.

        ``trip_id`` scopes a **party** lookup to one trip. A party id is not
        unique across a case root -- the collusion set holds three disputes
        between the same rider and the same driver -- so without it a party
        lookup answers with every case that party appears in, and the collector
        would hand one case another case's profiles. The collector always passes
        the trip the profiles are being fetched for; the parameter is optional
        because a caller that wants a party's artifacts over the whole root can
        still ask for them, which is what :class:`ProfileService` describes.

        A trip-keyed lookup ignores ``trip_id`` in the sense that it can never
        drop anything: every artifact in the trip table is filed under the trip
        it carries.

        Sorted by ``evidence_id`` within the answer, so two collections of the
        same case are the same collection.
        """
        table = self._by_trip if key_kind == KEY_TRIP else self._by_party
        allowed = None if sources is None else set(sources)
        found: List[Mapping[str, Any]] = []
        for evidence_type in evidence_types:
            for artifact in table.get((key, evidence_type), ()):
                if trip_id is not None and artifact.get("trip_id") != trip_id:
                    continue
                if allowed is not None and artifact.get("source") not in allowed:
                    continue
                found.append(artifact)
        return tuple(sorted(found, key=lambda artifact: str(artifact.get("evidence_id"))))


class Adapter:
    """One mocked source system: a name, what it holds, and the key it takes."""

    #: The service's name, as the retrieval log prints it.
    name = "Adapter"
    #: The artifact types it holds.
    evidence_types: Tuple[str, ...] = ()
    #: The ``source`` values it answers for, or ``None`` for any.
    sources: Optional[Tuple[str, ...]] = None
    #: Which key it is looked up by.
    key_kind = KEY_TRIP

    def __init__(self, index: SourceIndex) -> None:
        self.index = index

    def fetch(
        self, key: str, trip_id: Optional[str] = None
    ) -> Tuple[Mapping[str, Any], ...]:
        """The artifacts this service holds under one key.

        ``trip_id`` scopes a party-keyed lookup to one trip, which is what keeps
        two cases that share a party from answering for each other -- see
        :meth:`SourceIndex.artifacts`. A trip-keyed adapter can never lose an
        artifact to it, because its key already names the trip.
        """
        return self.index.artifacts(
            key, self.key_kind, self.evidence_types, self.sources, trip_id
        )

    def describe(self) -> Dict[str, Any]:
        """The adapter as data, for a caller that wants to enumerate them."""
        return {
            "name": self.name,
            "evidence_types": list(self.evidence_types),
            "sources": None if self.sources is None else list(self.sources),
            "key": self.key_kind,
        }


class TripService(Adapter):
    """Trip records, by trip id."""

    name = "TripService"
    evidence_types = ("TRIP_RECORD",)
    sources = ("PLATFORM_TELEMETRY",)


class TelemetryService(Adapter):
    """GPS traces, by trip id. The platform's own, or the driver's device."""

    name = "TelemetryService"
    evidence_types = ("GPS_TRACE",)
    sources = ("PLATFORM_TELEMETRY", "DRIVER_DEVICE")


class ChatService(Adapter):
    """Chat logs, by trip id."""

    name = "ChatService"
    evidence_types = ("CHAT_LOG",)


class PaymentsLedger(Adapter):
    """Fare breakdowns, by trip id.

    No source restriction: a fare breakdown may be the ledger's own or one the
    user submitted, and both are the fare breakdown for the trip.
    """

    name = "PaymentsLedger"
    evidence_types = ("FARE_BREAKDOWN",)


class ProfileService(Adapter):
    """The two party profiles, by party id.

    The party ids come from the trip record rather than from the dispute, which
    is why this is the one adapter the collector cannot call first.

    A party id is not unique across a case root, so the collector passes the trip
    it is fetching the profiles for and the answer is kept to that trip's
    artifacts. Without it, the collusion set's repeated pair would answer three
    times over and each of the three cases would be handed the other two's
    profiles.
    """

    name = "ProfileService"
    evidence_types = PROFILE_EVIDENCE_TYPES
    key_kind = KEY_PARTY


class AdvisoryFeed(Adapter):
    """Traffic advisories, by trip id. The authority's, or a user's."""

    name = "AdvisoryFeed"
    evidence_types = ("TRAFFIC_ADVISORY",)
    sources = ("THIRD_PARTY_LTA", "USER_SUBMITTED")


class SourceSystems(NamedTuple):
    """The six adapters over one index."""

    trip: TripService
    telemetry: TelemetryService
    chat: ChatService
    payments: PaymentsLedger
    profiles: ProfileService
    advisories: AdvisoryFeed

    @classmethod
    def over(cls, case_root: Path) -> "SourceSystems":
        """The six adapters over one case root."""
        index = SourceIndex(case_root)
        return cls(
            trip=TripService(index),
            telemetry=TelemetryService(index),
            chat=ChatService(index),
            payments=PaymentsLedger(index),
            profiles=ProfileService(index),
            advisories=AdvisoryFeed(index),
        )

    @property
    def index(self) -> SourceIndex:
        """The index every adapter here is backed by."""
        return self.trip.index

    def adapters(self) -> Tuple[Adapter, ...]:
        return (self.trip, self.telemetry, self.chat, self.payments, self.profiles, self.advisories)
