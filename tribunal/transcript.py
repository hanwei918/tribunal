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
from typing import Any, Callable, Dict, List, Optional

from . import money

# The roles, named once so the record and the tests cannot drift apart.
ROLE_RIDER_ADVOCATE = "RIDER_ADVOCATE"
ROLE_DRIVER_ADVOCATE = "DRIVER_ADVOCATE"
ROLE_JUDGE = "JUDGE"


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

    def totals(self) -> Dict[str, Any]:
        """The token and wall-clock totals across every entry."""
        return {
            "calls": len(self._entries),
            "prompt_tokens": sum(e.prompt_tokens for e in self._entries),
            "completion_tokens": sum(e.completion_tokens for e in self._entries),
            "reasoning_tokens": sum(e.reasoning_tokens for e in self._entries),
            "cached_tokens": sum(e.cached_tokens for e in self._entries),
            "duration_seconds": sum(e.duration_seconds for e in self._entries),
        }

    def as_dict(self) -> Dict[str, Any]:
        return {"entries": [entry.as_dict() for entry in self._entries]}

    def to_json(self) -> str:
        """The canonical JSON for this transcript."""
        return money.dumps_canonical(self.as_dict())

    def sha256(self) -> str:
        """The SHA-256 of the canonical JSON."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
