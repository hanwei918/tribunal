"""The observable record of agent-to-agent communication.

This is a hard deliverable for the track, not a debugging aid: it is the record
of what each agent was told and what it answered.

One entry per call, in order. An entry carries the agent's role, the system
prompt's sha256, the user message's sha256, the raw response text, the parsed
value when there was one, the top-level JSON shape the body arrived in, the
usage figures, the duration, the attempt count and the timestamp.

**The shape is recorded, not left to be inferred.** The pipeline accepts an
advocate's claims either inside an object under ``claims`` or as a bare array, so
which of the two a model chose is a measurement about that model. It is recorded
per attempt rather than per case, because a model can switch shape between the
first attempt and the retry — one shipped run shows exactly that.

**Digests, not bodies, for the prompts.** The brief is large and already on disk,
and a transcript that inlines it three times is unreadable. The response text is
kept in full, because that is the part a reader needs to see.

A transcript contains no API key. The key travels only in the `Authorization`
header, and nothing here copies headers into the record; a test asserts this
with the same canary technique `test_llm.py` uses.

Serialisation uses the settings this package already applies everywhere:
``ensure_ascii=False``, ``sort_keys=True``, ``separators=(",", ":")``, via
``money.dumps_canonical`` so that any ``Decimal`` in a parsed value is written
as a JSON number carrying its own literal.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from . import money

# The roles, named once so the record and the tests cannot drift apart.
ROLE_RIDER_ADVOCATE = "RIDER_ADVOCATE"
ROLE_DRIVER_ADVOCATE = "DRIVER_ADVOCATE"
ROLE_JUDGE = "JUDGE"
# The draft verifier. It is a role of its own and not a judge call: it is asked
# once per case, over every valid draft at once, and it decides no part of the
# ruling. Keeping it apart is what lets its tokens be counted separately from
# the judge's and lets a reader of the transcript tell the two questions apart.
ROLE_VERIFIER = "VERIFIER"


def sha256_text(text: str) -> str:
    """The SHA-256 hex digest of ``text`` as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _default_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TranscriptEntry:
    """One call, as it happened."""

    role: str
    model: str
    system_sha256: str
    user_sha256: str
    response_text: str
    parsed: Optional[Any]
    parse_outcome: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cached_tokens: int
    duration_seconds: float
    attempts: int
    status: int
    timestamp: str
    note: Optional[str] = None
    shape: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        """The entry as a plain dict, for serialisation."""
        return {
            "role": self.role,
            "model": self.model,
            "system_sha256": self.system_sha256,
            "user_sha256": self.user_sha256,
            "response_text": self.response_text,
            "parsed": self.parsed,
            "parse_outcome": self.parse_outcome,
            "shape": self.shape,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cached_tokens": self.cached_tokens,
            "duration_seconds": self.duration_seconds,
            "attempts": self.attempts,
            "status": self.status,
            "timestamp": self.timestamp,
            "note": self.note,
        }


class Transcript:
    """An ordered list of :class:`TranscriptEntry`, serialisable deterministically.

    ``now`` is injectable so a test can pin the timestamp and prove that the
    same transcript serialises to the same bytes.
    """

    def __init__(self, now: Optional[Callable[[], str]] = None) -> None:
        self._entries: List[TranscriptEntry] = []
        self._now = now if now is not None else _default_timestamp

    def add(
        self,
        *,
        role: str,
        model: str,
        system_prompt: str,
        user_message: str,
        response_text: str,
        parsed: Optional[Any],
        parse_outcome: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        reasoning_tokens: int = 0,
        cached_tokens: int = 0,
        duration_seconds: float = 0.0,
        attempts: int = 1,
        status: int = 0,
        note: Optional[str] = None,
        shape: Optional[str] = None,
    ) -> TranscriptEntry:
        """Append one entry, digesting the prompts rather than storing them."""
        entry = TranscriptEntry(
            role=role,
            model=model,
            system_sha256=sha256_text(system_prompt),
            user_sha256=sha256_text(user_message),
            response_text=response_text,
            parsed=parsed,
            parse_outcome=parse_outcome,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            cached_tokens=cached_tokens,
            duration_seconds=duration_seconds,
            attempts=attempts,
            status=status,
            timestamp=self._now(),
            note=note,
            shape=shape,
        )
        self._entries.append(entry)
        return entry

    def record(
        self,
        *,
        role: str,
        system_prompt: str,
        user_message: str,
        result: Any,
        note=None,
        shape=None,
    ):
        """Append one entry straight from an :class:`tribunal.llm.LLMResult`."""
        return self.add(
            role=role,
            model=result.model,
            system_prompt=system_prompt,
            user_message=user_message,
            response_text=result.text,
            parsed=result.json_body,
            parse_outcome=result.parse_outcome,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            reasoning_tokens=result.reasoning_tokens,
            cached_tokens=result.cached_tokens,
            duration_seconds=result.duration_seconds,
            attempts=result.attempts,
            status=result.status,
            note=note,
            shape=shape,
        )

    @property
    def entries(self) -> List[TranscriptEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def add_recorded(self, entry: Mapping[str, Any], *, note: str) -> TranscriptEntry:
        """Append an entry copied from another transcript, carrying a new note.

        Every other field is carried across as it stands -- the digests, the
        timestamp, the usage figures and the response -- because the entry is
        the record of a call that really happened, and re-deriving any of it
        here would be inventing evidence rather than copying it. ``note`` is the
        one field replaced, and it is replaced rather than added beside because
        the note is where an entry says what this run did; an original note is
        not lost, since it travels inside the new one.

        Raises ``ValueError`` when the mapping is not an entry, so a caller that
        skipped its own checks hears about it here rather than producing a
        transcript with a hole in it.
        """
        missing = [
            name
            for name in (
                "role",
                "model",
                "system_sha256",
                "user_sha256",
                "response_text",
                "parse_outcome",
            )
            if not isinstance(entry.get(name), str) or not entry.get(name)
        ]
        if missing:
            raise ValueError(
                "a recorded entry cannot be copied: {0} is missing or is not a "
                "non-empty string".format(", ".join(missing))
            )

        original_note = entry.get("note")
        carried_note = note
        if isinstance(original_note, str) and original_note:
            carried_note = "{0} (the source run's own note: {1})".format(
                note, original_note
            )

        copied = TranscriptEntry(
            role=entry["role"],
            model=entry["model"],
            system_sha256=entry["system_sha256"],
            user_sha256=entry["user_sha256"],
            response_text=entry["response_text"],
            parsed=entry.get("parsed"),
            parse_outcome=entry["parse_outcome"],
            prompt_tokens=int(entry.get("prompt_tokens") or 0),
            completion_tokens=int(entry.get("completion_tokens") or 0),
            reasoning_tokens=int(entry.get("reasoning_tokens") or 0),
            cached_tokens=int(entry.get("cached_tokens") or 0),
            duration_seconds=float(entry.get("duration_seconds") or 0.0),
            attempts=int(entry.get("attempts") or 1),
            status=int(entry.get("status") or 0),
            timestamp=str(entry.get("timestamp") or ""),
            note=carried_note,
            shape=entry.get("shape"),
        )
        self._entries.append(copied)
        return copied

    def totals(self, entries: Optional[Sequence[TranscriptEntry]] = None) -> Dict[str, Any]:
        """The token and wall-clock totals across the entries given.

        ``entries`` defaults to every entry on the transcript. It is passed when
        a transcript holds entries this run did not make: a replayed advocate
        call belongs to the run that made it, and its usage was billed there.
        Summing the whole transcript in that case would report a bill this run
        never paid.
        """
        chosen = self._entries if entries is None else list(entries)
        return {
            "calls": len(chosen),
            "prompt_tokens": sum(e.prompt_tokens for e in chosen),
            "completion_tokens": sum(e.completion_tokens for e in chosen),
            "reasoning_tokens": sum(e.reasoning_tokens for e in chosen),
            "cached_tokens": sum(e.cached_tokens for e in chosen),
            "duration_seconds": sum(e.duration_seconds for e in chosen),
        }

    def as_dict(self) -> Dict[str, Any]:
        return {"entries": [entry.as_dict() for entry in self._entries]}

    def to_json(self) -> str:
        """The canonical JSON for this transcript."""
        return money.dumps_canonical(self.as_dict())

    def sha256(self) -> str:
        """The SHA-256 of the canonical JSON."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
