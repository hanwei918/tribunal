"""Transport layer for the TokenHub Chat Completions endpoint.

This module is the *transport only*. It does not build prompts, does not run a
pipeline, and knows nothing about disputes, advocates or rulings. It sends a
system message and a user message to a model and accounts for what came back.

Standard library only. ``urllib.request`` is the client; no dependency is added
to ``requirements.txt``.

No magic values
---------------
Endpoint, model id, temperature, seed, reasoning effort, timeout and the whole
retry policy are constructor arguments on :class:`LLMClient`. ``model`` has **no
default** and is required, because which model this system runs on is a decision
that has not been made yet and belongs in one explicit place in the caller
rather than buried as a default here. The other arguments take the measured
values recorded in ``docs/notes/2026-09-21-tokenhub-api-facts.md`` as documented
defaults. This mirrors the rule that policy numbers are injected rather than
written as literals.

Why the timeout is 600 seconds
------------------------------
Measured on the real case 208 brief, which is the largest prompt this project
sends: advocate calls took 38.7 s and 68.9 s on ``hy3``, and 199.9 s and 221.6 s
on ``hy4-preview``. The judge call carries that same brief plus both claim
arrays, so it is larger than either advocate call. Under a 120-second default
``hy4-preview`` would time out on substantially every call, and the default did
cost a case: case 109 on ``hy3`` died at 120.1 s with ``TimeoutError: The read
operation timed out``.

The two errors are not symmetric. A timeout that is too long costs waiting. A
timeout that is too short costs the tokens already spent generating a response
that is then discarded — the provider produced it whether or not the client
stayed to read it. So the default belongs well above the slowest measured call
rather than close to it, and it stays a constructor argument for a caller who
wants to shorten it deliberately for a quick probe.

Every figure above is a measurement, recorded with how it was taken in
``docs/notes/2026-09-21-tokenhub-api-facts.md``.

Secret hygiene
--------------
The API key is read from ``TOKENHUB_API_KEY``, falling back to the
repository-root ``.env`` (which is git-ignored). It is never written to a log, a
``repr``, an exception message or a call record. Call records carry a SHA-256
digest of the request body instead, so a run stays auditable without copying
evidence text — or a credential — into a second place.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

# --------------------------------------------------------------------------
# Measured facts, as defaults. Each is a documented measurement, not a guess;
# see docs/notes/2026-09-21-tokenhub-api-facts.md for how each was established.
# --------------------------------------------------------------------------
DEFAULT_ENDPOINT = "https://tokenhub-intl.tencentcloudmaas.com/v1/chat/completions"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_SEED = 42

# Reasoning is left ON by default, because the case 208 measurement recorded in
# docs/notes/2026-09-21-tokenhub-api-facts.md showed the reasoning budget is
# where the answer quality comes from: with reasoning on, "hy4-preview" spent
# 16,772 and 19,363 reasoning tokens, produced 10 and 15 claims, and on both
# sides identified the POL-GEN-01 lifetime-counter substitution trap and refused
# it. Switching reasoning off is a deliberate cost or latency choice a caller
# makes, not the state a caller should land in by accident.
#
# None means the key is omitted from the request entirely and the model applies
# its own default. The explicit string "none" still suppresses reasoning.
DEFAULT_REASONING_EFFORT: Optional[str] = None

# 600 s, not 120 s. Measured on the real case 208 brief: hy3 advocate calls took
# 38.7 s and 68.9 s, hy4-preview 199.9 s and 221.6 s, and the judge call is
# larger than either because it carries both claim arrays as well. A timeout
# that is too long costs waiting; one that is too short costs the tokens already
# spent generating a response that is then discarded, and the provider produced
# it either way. The default therefore sits well above the slowest measured
# call. See the module docstring, and the measurements with their method in
# docs/notes/2026-09-21-tokenhub-api-facts.md.
DEFAULT_TIMEOUT_SECONDS = 600.0
DEFAULT_REQUESTS_PER_MINUTE = 60
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BACKOFF_SECONDS = 1.0
DEFAULT_BACKOFF_FACTOR = 2.0

# 1200 s, and derived rather than chosen. ``timeout_seconds`` bounds ONE
# attempt and ``max_attempts`` multiplies it, so before this limit existed the
# worst case for a single call was 4 x 600 s plus backoff -- about 40 minutes,
# for one call. Measured on 2026-09-22: a real run wrote its last case at 07:25
# and was still alive at 09:13, 1 h 48 m with no output, while a direct probe of
# the endpoint answered HTTP 200 in 0.95 s. Nothing was wrong with the provider;
# the limits simply did not multiply to anything bounded.
#
# Two full attempts is the floor, not a round number: the 605.8-second TIMEOUT
# failure recorded that day shows a real attempt does run into the per-attempt
# timeout, and a retry after one such attempt is exactly what ``max_attempts``
# exists for. 2 x 600 s = 1200 s bounds one call at 20 minutes instead of 40,
# while still letting a single slow call -- the slowest completed call measured
# is 305.7 s -- finish with room to spare. See
# docs/notes/2026-09-22-bounded-call-and-case-deadlines.md.
DEFAULT_TOTAL_DEADLINE_SECONDS = 1200.0

# The credential. The name of the variable is fixed by the workspace; the value
# is never held anywhere but on the client instance.
API_KEY_ENV_VAR = "TOKENHUB_API_KEY"
DEFAULT_ENV_FILE = ".env"

# Where a model is provisioned, named in the exception a wrong model id raises.
DEFAULT_PROVISIONING_HINT = (
    "the TokenHub console, Service invocation panel, where the model is provisioned"
)

# Statuses worth another attempt, and the one that must never be retried.
RETRY_STATUSES = (429, 500, 502, 503, 504)
NOT_PROVISIONED_STATUS = 402
NOT_PROVISIONED_CODE = "401006"

SECONDS_PER_MINUTE = 60

# The three parse outcomes a result can carry.
PARSE_NOT_REQUESTED = "NOT_REQUESTED"
PARSE_PARSED = "PARSED"
PARSE_MALFORMED = "MALFORMED"

JSON_OBJECT_FORMAT: Dict[str, str] = {"type": "json_object"}


class LLMError(Exception):
    """Base class for every failure this module raises."""


class MissingAPIKeyError(LLMError):
    """No credential was found in the environment or in the .env file."""


class ModelNotProvisionedError(LLMError):
    """The model is not provisioned for this account. Retrying cannot help."""


class TransportError(LLMError):
    """The request never produced an HTTP response."""


class DeadlineExceededError(LLMError):
    """The client's own total deadline for one call ran out before an attempt.

    Distinct from a timeout on purpose, and the distinction is what makes the
    failure actionable. A timeout says one request waited too long, and the
    answer is a longer timeout or a faster model. This says the client had
    already spent its whole budget for this call and refused to begin an attempt
    it had no time to finish, so the answer is a shorter per-attempt timeout, a
    smaller request, or a different model — waiting longer would only move the
    same wall.
    """

    def __init__(self, message: str, *, elapsed_seconds: float, attempts: int) -> None:
        super().__init__(message)
        self.elapsed_seconds = elapsed_seconds
        self.attempts = attempts


@dataclass(frozen=True)
class HttpResult:
    """What a transport hands back: a status and a body. No headers needed."""

    status: int
    body: bytes


@dataclass(frozen=True)
class LLMResult:
    """Everything one call produced, so a caller can account for every token.

    ``text`` is the assistant's answer — the ``choices[0].message.content``
    string. When the whole response envelope is not parseable, ``text`` is the
    raw body instead, so nothing is ever thrown away.

    ``json_body`` is that answer parsed as JSON, and it is populated only when a
    ``json_object`` format was requested. ``envelope`` is the parsed response
    envelope itself, kept for auditing (it carries ``finish_reason``, the echoed
    model id, and the ``usage`` block).

    ``parse_outcome`` distinguishes the ways a call can fail to give an answer.
    ``NOT_REQUESTED`` means no JSON was asked for. ``MALFORMED`` means the model
    answered with a 200 whose answer is not parseable — the model did not
    refuse, it produced something broken. ``parse_error`` carries the reason.
    """

    text: str
    json_body: Optional[Any]
    envelope: Optional[Any]
    parse_outcome: str
    parse_error: Optional[str]
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cached_tokens: int
    status: int
    duration_seconds: float
    model: str
    attempts: int
    request_sha256: str

    @property
    def answered(self) -> bool:
        """True when the model returned a usable parsed answer."""
        return self.parse_outcome == PARSE_PARSED


def _urllib_transport(
    url: str, headers: Dict[str, str], body: bytes, timeout: float
) -> HttpResult:
    """The default transport: one POST over ``urllib.request``.

    An HTTP error status is returned as an :class:`HttpResult` rather than
    raised, so the retry logic sees every status through one path. A failure to
    reach the endpoint at all raises :class:`TransportError`; the message names
    the reason and never the headers, which is where the credential lives.
    """
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResult(status=int(response.status), body=response.read())
    except urllib.error.HTTPError as exc:
        return HttpResult(status=int(exc.code), body=exc.read())
    except urllib.error.URLError as exc:
        raise TransportError("could not reach the endpoint: {0}".format(exc.reason)) from exc


def load_api_key(
    env_file: Optional[Path] = None, environ: Optional[Mapping[str, str]] = None
) -> Optional[str]:
    """Return the API key from the environment, else from ``.env``, else None.

    The value is returned, never printed. ``environ`` is injectable so a test
    can drive both branches without touching the real environment.
    """
    source = os.environ if environ is None else environ
    key = source.get(API_KEY_ENV_VAR)
    if key and key.strip():
        return key.strip()

    path = DEFAULT_ENV_FILE if env_file is None else env_file
    env_path = Path(path)
    if not env_path.is_absolute():
        env_path = Path(__file__).resolve().parents[1] / env_path
    if not env_path.is_file():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == API_KEY_ENV_VAR:
            value = value.strip().strip('"').strip("'")
            return value or None
    return None


def _error_code(body: bytes) -> Optional[str]:
    """The ``error.code`` from a JSON error body, or None. Never raises."""
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if isinstance(parsed, dict):
        error = parsed.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            if code is not None:
                return str(code)
    return None


def _assistant_content(envelope: Any) -> str:
    """The assistant's answer string from a response envelope, or ``""``.

    Defensive on purpose: an unexpected shape returns an empty answer rather
    than raising, so a strange envelope is reported as a parse outcome instead
    of escaping as an exception.
    """
    if not isinstance(envelope, dict):
        return ""
    choices = envelope.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _usage(envelope: Any) -> Dict[str, Any]:
    """The usage block from a response envelope, or ``{}``."""
    if isinstance(envelope, dict):
        usage = envelope.get("usage")
        if isinstance(usage, dict):
            return usage
    return {}


class LLMClient:
    """One model, one endpoint, one accounting path.

    Inject ``transport`` to drive the client without a network, and ``sleep`` /
    ``clock`` to exercise the rate limiter and the backoff without waiting.
    """

    def __init__(
        self,
        model: str,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        temperature: Optional[float] = DEFAULT_TEMPERATURE,
        seed: Optional[int] = DEFAULT_SEED,
        reasoning_effort: Optional[str] = DEFAULT_REASONING_EFFORT,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        total_deadline_seconds: float = DEFAULT_TOTAL_DEADLINE_SECONDS,
        requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        api_key: Optional[str] = None,
        transport: Optional[Callable[[str, Dict[str, str], bytes, float], HttpResult]] = None,
        record_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        env_file: Optional[Path] = None,
        provisioning_hint: str = DEFAULT_PROVISIONING_HINT,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not model:
            raise LLMError("model is required and has no default; name the model explicitly")
        if requests_per_minute <= 0:
            raise LLMError("requests_per_minute must be positive")
        if max_attempts < 1:
            raise LLMError("max_attempts must be at least 1")
        if total_deadline_seconds < timeout_seconds:
            # Refused rather than clamped. The deadline is checked before an
            # attempt begins and an attempt needs a whole ``timeout_seconds`` of
            # remaining budget, so a deadline below one attempt is a client that
            # can never make a call at all -- and clamping it to the timeout
            # would silently turn every call into a single-attempt one.
            raise LLMError(
                "total_deadline_seconds must be at least timeout_seconds, got {0} < {1}".format(
                    total_deadline_seconds, timeout_seconds
                )
            )

        self._model = model
        self._endpoint = endpoint
        self._temperature = temperature
        self._seed = seed
        self._reasoning_effort = reasoning_effort
        self._timeout_seconds = timeout_seconds
        self._total_deadline_seconds = total_deadline_seconds
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._backoff_factor = backoff_factor
        self._minimum_interval = SECONDS_PER_MINUTE / requests_per_minute
        self._provisioning_hint = provisioning_hint

        self._api_key = api_key if api_key is not None else load_api_key(env_file)
        self._transport = transport if transport is not None else _urllib_transport
        self._record_sink = record_sink
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: Optional[float] = None
        # The request interval belongs to the client, not to a caller, so the
        # limiter is shared state the moment a caller uses this client from more
        # than one thread. One lock, guarding the read-modify-write below.
        self._rate_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Never let the credential escape through a repr.
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            "LLMClient(model={0!r}, endpoint={1!r}, temperature={2!r}, seed={3!r}, "
            "reasoning_effort={4!r}, timeout_seconds={5!r}, total_deadline_seconds={6!r}, "
            "requests_per_minute={7!r}, max_attempts={8!r}, backoff_seconds={9!r}, "
            "backoff_factor={10!r}, api_key=<redacted>)"
        ).format(
            self._model,
            self._endpoint,
            self._temperature,
            self._seed,
            self._reasoning_effort,
            self._timeout_seconds,
            self._total_deadline_seconds,
            SECONDS_PER_MINUTE / self._minimum_interval,
            self._max_attempts,
            self._backoff_seconds,
            self._backoff_factor,
        )

    __str__ = __repr__

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        if not self._api_key:
            raise MissingAPIKeyError(
                "{0} is not set and no value was found in the .env file".format(API_KEY_ENV_VAR)
            )
        return {
            "Authorization": "Bearer {0}".format(self._api_key),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request_body(
        self, system: str, user: str, response_format: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """The request body, with every optional key omitted when it is None.

        ``temperature``, ``seed`` and ``reasoning_effort`` are each left out of
        the body entirely when they are ``None``, so a caller can ask for the
        provider's own behaviour on any of the three rather than being pinned to
        a value. Omitting ``reasoning_effort`` leaves reasoning ON; passing the
        explicit string ``"none"`` suppresses it.
        """
        body: Dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self._temperature is not None:
            body["temperature"] = self._temperature
        if self._seed is not None:
            body["seed"] = self._seed
        if self._reasoning_effort is not None:
            body["reasoning_effort"] = self._reasoning_effort
        if response_format is not None:
            body["response_format"] = response_format
        return body

    def _respect_rate_limit(self) -> None:
        """Hold the caller to the published requests-per-minute limit.

        The check and the update are one critical section. The interval being
        enforced is the gap between consecutive requests *from this client*, so
        two threads calling :meth:`complete` at the same time must together stay
        inside the published limit; an unguarded read-modify-write of
        ``_last_request_at`` would let both of them see a stale timestamp and
        release together.

        Sleeping while holding the lock is deliberate. The property is the
        interval between requests, so a second caller arriving mid-wait must
        wait out its own interval rather than start alongside the first — which
        is exactly what serialising the wait produces. Nothing slow happens
        here: the transport call itself is outside the lock.
        """
        if self._minimum_interval <= 0:
            return
        with self._rate_lock:
            if self._last_request_at is not None:
                elapsed = self._clock() - self._last_request_at
                remaining = self._minimum_interval - elapsed
                if remaining > 0:
                    self._sleep(remaining)
            self._last_request_at = self._clock()

    def _post(self, body: bytes) -> Tuple[int, bytes, int]:
        """POST once, retrying only what is worth retrying.

        Two limits are enforced here and they are deliberately not the same
        limit. ``timeout_seconds`` bounds **one attempt**;
        ``total_deadline_seconds`` bounds **the call**, every attempt and all
        backoff included. Before the second one existed the first one was the
        only bound, and four attempts of it is about 40 minutes for a single
        call.

        The deadline is checked *before* each attempt rather than after the last
        one, because an attempt needs a whole ``timeout_seconds`` of remaining
        budget. Beginning one that cannot finish would run past the deadline and
        reach the caller as a ``TimeoutError`` — the same event as a request that
        waited too long, which it is not. Refusing the attempt is what keeps
        :class:`DeadlineExceededError` and a timeout tellable apart.
        """
        delay = self._backoff_seconds
        status, payload, attempts = 0, b"", 0
        started_at = self._clock()
        deadline_at = started_at + self._total_deadline_seconds

        for attempt in range(1, self._max_attempts + 1):
            remaining = deadline_at - self._clock()
            if remaining < self._timeout_seconds:
                elapsed = self._clock() - started_at
                raise DeadlineExceededError(
                    "stopped after {0:.1f} s of a {1:g} s deadline with {2:.1f} s left: "
                    "{3} of {4} attempts were made, and the next one needs {5:g} s".format(
                        elapsed,
                        self._total_deadline_seconds,
                        remaining,
                        attempt - 1,
                        self._max_attempts,
                        self._timeout_seconds,
                    ),
                    elapsed_seconds=elapsed,
                    attempts=attempt - 1,
                )
            attempts = attempt
            self._respect_rate_limit()
            outcome = self._transport(self._endpoint, self._headers(), body, self._timeout_seconds)
            status, payload = outcome.status, outcome.body

            if status == NOT_PROVISIONED_STATUS or _error_code(payload) == NOT_PROVISIONED_CODE:
                raise ModelNotProvisionedError(
                    "model {0!r} is not provisioned for this account (HTTP {1}, code {2}); "
                    "enable it at {3}. Retrying cannot help.".format(
                        self._model, status, NOT_PROVISIONED_CODE, self._provisioning_hint
                    )
                )

            if status in RETRY_STATUSES and attempt < self._max_attempts:
                self._sleep(delay)
                delay *= self._backoff_factor
                continue

            return status, payload, attempts

        return status, payload, attempts

    def _record(self, result: LLMResult) -> None:
        if self._record_sink is None:
            return
        self._record_sink(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": self._model,
                "request_sha256": result.request_sha256,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "reasoning_tokens": result.reasoning_tokens,
                "cached_tokens": result.cached_tokens,
                "status": result.status,
                "duration_seconds": result.duration_seconds,
                "attempts": result.attempts,
                "parse_outcome": result.parse_outcome,
            }
        )

    @staticmethod
    def _extract(body: bytes, response_format: Optional[Dict[str, Any]]):
        """Return ``(text, json_body, envelope, outcome, error)``. Never raises.

        The envelope is always parsed, because the usage block lives inside it
        and a caller has to be able to account for tokens on a plain call too.
        The answer itself is parsed as JSON only when a ``json_object`` format
        was asked for.

        Model output is parsed with ``parse_float=Decimal``, matching the rule
        the loader applies to the corpus: a JSON number written with a decimal
        point is a Decimal, never a binary float.
        """
        try:
            raw = body.decode("utf-8")
        except UnicodeDecodeError as exc:
            return "", None, None, PARSE_MALFORMED, "response body is not valid UTF-8: {0}".format(exc)

        try:
            envelope = json.loads(raw, parse_float=Decimal)
        except ValueError as exc:
            # The whole body is unusable. Keep it as the text: it is evidence.
            return (
                raw,
                None,
                None,
                PARSE_MALFORMED,
                "response envelope is not JSON: {0}: {1}".format(type(exc).__name__, exc),
            )

        answer = _assistant_content(envelope)
        if response_format is None:
            return answer, None, envelope, PARSE_NOT_REQUESTED, None

        try:
            return answer, json.loads(answer, parse_float=Decimal), envelope, PARSE_PARSED, None
        except ValueError as exc:
            return answer, None, envelope, PARSE_MALFORMED, "{0}: {1}".format(type(exc).__name__, exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def complete(
        self,
        system: str,
        user: str,
        *,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResult:
        """Send one request and return everything it produced.

        Raises :class:`MissingAPIKeyError` when there is no credential and
        :class:`ModelNotProvisionedError` when the model is not provisioned.
        A 200 whose body is not parseable does **not** raise: the result carries
        ``parse_outcome == PARSE_MALFORMED``, ``parse_error`` and the raw text,
        so the caller can decide whether to retry.
        """
        request_body = self._request_body(system, user, response_format)
        encoded = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()

        started_at = self._clock()
        status, payload, attempts = self._post(encoded)
        duration = self._clock() - started_at

        text, json_body, envelope, parse_outcome, parse_error = self._extract(
            payload, response_format
        )
        usage = _usage(envelope)

        def _count(name: str) -> int:
            value = usage.get(name)
            return int(value) if isinstance(value, int) else 0

        def _nested(outer: str, inner: str) -> int:
            container = usage.get(outer)
            if isinstance(container, dict):
                value = container.get(inner)
                return int(value) if isinstance(value, int) else 0
            return 0

        result = LLMResult(
            text=text,
            json_body=json_body,
            envelope=envelope,
            parse_outcome=parse_outcome,
            parse_error=parse_error,
            prompt_tokens=_count("prompt_tokens"),
            completion_tokens=_count("completion_tokens"),
            reasoning_tokens=_nested("completion_tokens_details", "reasoning_tokens"),
            cached_tokens=_nested("prompt_tokens_details", "cached_tokens"),
            status=status,
            duration_seconds=duration,
            model=self._model,
            attempts=attempts,
            request_sha256=digest,
        )
        self._record(result)
        return result
