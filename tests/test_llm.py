"""Tests for ``tribunal.llm``.

No test here touches the network. The transport is injected, and so are the
clock and the sleep, so the rate limiter and the backoff are exercised in
virtual time rather than by waiting.

The one exception is :class:`NetworkTests`, which is skipped unless
``TRIBUNAL_LLM_NETWORK_TESTS=1`` is set, and skipped again if no credential is
available.

Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import llm  # noqa: E402

# A key that is unmistakable if it ever turns up where it should not.
FAKE_KEY = "tok-live-FAKEKEY-0123456789abcdef-DO-NOT-LEAK"
MODEL = "hy4-preview"
NETWORK_ENV_VAR = "TRIBUNAL_LLM_NETWORK_TESTS"

# The malformed completion recorded verbatim from "hy3" on 2026-09-21. It is
# the reason a 200 can fail to parse, and therefore the reason LLMResult
# carries a parse outcome instead of letting a JSONDecodeError escape.
MALFORMED_BODY = b'{"ruling\\":\\"ALLOW"'


class VirtualClock:
    """A clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeTransport:
    """A scripted transport: hands back queued results, records every call."""

    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "body": body, "timeout": timeout})
        if not self.responses:
            raise AssertionError("FakeTransport ran out of scripted responses")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def http(status: int, payload) -> llm.HttpResult:
    """An HttpResult, JSON-encoding a dict payload."""
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload).encode("utf-8")
    return llm.HttpResult(status=status, body=payload)


def usage_body(**usage) -> dict:
    return {"choices": [{"message": {"content": "{}"}}], "usage": usage}


def make_client(transport, **overrides):
    """A client wired to a fake transport and a virtual clock."""
    clock = VirtualClock()
    kwargs = dict(
        model=MODEL,
        api_key=FAKE_KEY,
        transport=transport,
        sleep=clock.sleep,
        clock=clock.clock,
    )
    kwargs.update(overrides)
    return llm.LLMClient(**kwargs), clock


class SuccessfulCallTests(unittest.TestCase):
    """Requirement 3 and 9: a successful JSON completion."""

    def test_a_successful_json_completion_accounts_for_every_token(self):
        payload = {
            "choices": [{"message": {"content": '{"ruling": "ALLOW"}'}}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 16,
                "completion_tokens_details": {"reasoning_tokens": 0},
                "prompt_tokens_details": {"cached_tokens": 0},
            },
        }
        transport = FakeTransport(http(200, payload))
        client, _ = make_client(transport)

        result = client.complete("sys", "user", response_format=llm.JSON_OBJECT_FORMAT)

        self.assertEqual(result.status, 200)
        self.assertEqual(result.parse_outcome, llm.PARSE_PARSED)
        self.assertIsNone(result.parse_error)
        self.assertEqual(result.json_body, {"ruling": "ALLOW"})
        self.assertTrue(result.answered)
        # text is the assistant's answer, and envelope is the parsed response
        self.assertEqual(result.text, '{"ruling": "ALLOW"}')
        self.assertIsInstance(result.envelope, dict)
        self.assertEqual(result.envelope["usage"]["prompt_tokens"], 120)
        self.assertEqual(result.prompt_tokens, 120)
        self.assertEqual(result.completion_tokens, 16)
        self.assertEqual(result.reasoning_tokens, 0)
        self.assertEqual(result.cached_tokens, 0)
        self.assertEqual(result.model, MODEL)
        self.assertEqual(result.attempts, 1)
        self.assertIsInstance(result.duration_seconds, float)
        self.assertGreaterEqual(result.duration_seconds, 0.0)
        self.assertEqual(len(result.request_sha256), 64)

    def test_the_request_carries_the_configured_parameters(self):
        transport = FakeTransport(http(200, usage_body()))
        client, _ = make_client(transport)

        client.complete("sys", "user", response_format=llm.JSON_OBJECT_FORMAT)

        sent = json.loads(transport.calls[0]["body"].decode("utf-8"))
        self.assertEqual(sent["model"], MODEL)
        self.assertEqual(sent["messages"][0], {"role": "system", "content": "sys"})
        self.assertEqual(sent["messages"][1], {"role": "user", "content": "user"})
        self.assertEqual(sent["temperature"], 0.0)
        self.assertEqual(sent["seed"], 42)
        # reasoning_effort is deliberately absent by default; see RequestBodyTests.
        self.assertNotIn("reasoning_effort", sent)
        self.assertEqual(sent["response_format"], {"type": "json_object"})
        # The ignored parameters must not be sent at all.
        self.assertNotIn("enable_thinking", sent)
        self.assertNotIn("enable_enhancement", sent)

    def test_no_response_format_means_the_answer_is_not_parsed_as_json(self):
        payload = {"choices": [{"message": {"content": "plain prose, not JSON"}}], "usage": {}}
        transport = FakeTransport(http(200, payload))
        client, _ = make_client(transport)

        result = client.complete("sys", "user")

        self.assertEqual(result.parse_outcome, llm.PARSE_NOT_REQUESTED)
        self.assertIsNone(result.json_body)
        self.assertIsNone(result.parse_error)
        self.assertEqual(result.text, "plain prose, not JSON")

    def test_a_200_whose_envelope_is_not_json_is_reported(self):
        transport = FakeTransport(llm.HttpResult(200, b"<html>gateway</html>"))
        client, _ = make_client(transport)

        result = client.complete("sys", "user", response_format=llm.JSON_OBJECT_FORMAT)

        self.assertEqual(result.parse_outcome, llm.PARSE_MALFORMED)
        self.assertIsNone(result.envelope)
        self.assertIsInstance(result.parse_error, str)
        self.assertIn("envelope", result.parse_error)
        self.assertEqual(result.text, "<html>gateway</html>")
        self.assertEqual(result.prompt_tokens, 0)

    def test_the_endpoint_and_timeout_are_constructor_arguments(self):
        transport = FakeTransport(http(200, usage_body()))
        client, _ = make_client(transport, endpoint="https://example.invalid/v1/chat", timeout_seconds=7.5)

        client.complete("sys", "user")

        self.assertEqual(transport.calls[0]["url"], "https://example.invalid/v1/chat")
        self.assertEqual(transport.calls[0]["timeout"], 7.5)


class MalformedResponseTests(unittest.TestCase):
    """Requirement 4 and 9: a 200 whose body is not parseable."""

    def test_a_200_with_malformed_json_is_reported_not_raised(self):
        transport = FakeTransport(llm.HttpResult(200, MALFORMED_BODY))
        client, _ = make_client(transport)

        result = client.complete("sys", "user", response_format=llm.JSON_OBJECT_FORMAT)

        self.assertEqual(result.status, 200)
        self.assertEqual(result.parse_outcome, llm.PARSE_MALFORMED)
        self.assertIsNone(result.json_body)
        self.assertFalse(result.answered)
        self.assertIsInstance(result.parse_error, str)
        self.assertTrue(result.parse_error)
        # The raw text is kept: a malformed body is evidence about the model.
        self.assertEqual(result.text, MALFORMED_BODY.decode("utf-8"))

    def test_a_valid_envelope_whose_answer_is_malformed_is_reported(self):
        """The realistic shape: the envelope parses, the answer inside it does not."""
        payload = {
            "choices": [{"finish_reason": "stop", "message": {"content": MALFORMED_BODY.decode("utf-8")}}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 7},
        }
        transport = FakeTransport(http(200, payload))
        client, _ = make_client(transport)

        result = client.complete("sys", "user", response_format=llm.JSON_OBJECT_FORMAT)

        self.assertEqual(result.parse_outcome, llm.PARSE_MALFORMED)
        self.assertIsNone(result.json_body)
        # the malformed answer is preserved verbatim as evidence
        self.assertEqual(result.text, MALFORMED_BODY.decode("utf-8"))
        # and the envelope still gave up its usage, so the tokens are accounted for
        self.assertIsInstance(result.envelope, dict)
        self.assertEqual(result.prompt_tokens, 9)
        self.assertEqual(result.completion_tokens, 7)

    def test_usage_is_extracted_even_when_no_json_format_was_requested(self):
        """A caller must be able to account for every token on a plain call."""
        payload = {
            "choices": [{"message": {"content": "plain prose"}}],
            "usage": {"prompt_tokens": 31, "completion_tokens": 12},
        }
        transport = FakeTransport(http(200, payload))
        client, _ = make_client(transport)

        result = client.complete("sys", "user")

        self.assertEqual(result.parse_outcome, llm.PARSE_NOT_REQUESTED)
        self.assertIsNone(result.json_body)
        self.assertEqual(result.text, "plain prose")
        self.assertEqual(result.prompt_tokens, 31)
        self.assertEqual(result.completion_tokens, 12)

    def test_a_200_with_a_non_utf8_body_is_reported_not_raised(self):
        transport = FakeTransport(llm.HttpResult(200, b"\xff\xfe\x00not utf-8"))
        client, _ = make_client(transport)

        result = client.complete("sys", "user", response_format=llm.JSON_OBJECT_FORMAT)

        self.assertEqual(result.parse_outcome, llm.PARSE_MALFORMED)
        self.assertIsInstance(result.parse_error, str)
        self.assertIn("UTF-8", result.parse_error)


class NotProvisionedTests(unittest.TestCase):
    """Requirement 6 and 9: a wrong model id must fail at once."""

    def test_a_402_raises_the_dedicated_exception_without_retrying(self):
        payload = {"error": {"code": "401006", "message": "model not provisioned"}}
        transport = FakeTransport(http(402, payload), http(200, usage_body()))
        client, clock = make_client(transport)

        with self.assertRaises(llm.ModelNotProvisionedError) as caught:
            client.complete("sys", "user")

        message = str(caught.exception)
        self.assertIn("not provisioned", message)
        self.assertIn("401006", message)
        self.assertIn(MODEL, message)
        self.assertIn("Service invocation panel", message)

        self.assertEqual(len(transport.calls), 1, "a 402 must not be retried")
        self.assertEqual(clock.sleeps, [], "a 402 must not back off")
        self.assertEqual(clock.now, 0.0, "a wrong model id must fail in under a second")

    def test_the_error_code_alone_is_enough_even_on_another_status(self):
        transport = FakeTransport(http(400, {"error": {"code": "401006"}}))
        client, _ = make_client(transport)

        with self.assertRaises(llm.ModelNotProvisionedError):
            client.complete("sys", "user")
        self.assertEqual(len(transport.calls), 1)


class RetryTests(unittest.TestCase):
    """Requirement 6 and 9: retry on 429 and 5xx, bounded, with backoff."""

    def test_a_429_is_retried_then_succeeds(self):
        transport = FakeTransport(
            http(429, {"error": {"code": "429001"}}),
            http(429, b""),
            http(200, usage_body(prompt_tokens=5)),
        )
        client, clock = make_client(transport)

        result = client.complete("sys", "user")

        self.assertEqual(result.status, 200)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(len(transport.calls), 3)
        # Backoff is 1.0 then 2.0. The rate limiter adds nothing here, because
        # the backoff sleeps already exceed the one-second request interval.
        self.assertEqual(clock.sleeps, [1.0, 2.0])

    def test_a_5xx_is_retried(self):
        transport = FakeTransport(http(503, b""), http(200, usage_body()))
        client, clock = make_client(transport)

        result = client.complete("sys", "user")

        self.assertEqual(result.status, 200)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(clock.sleeps, [1.0])

    def test_retries_are_bounded_and_the_last_status_is_returned(self):
        transport = FakeTransport(*[http(500, b"") for _ in range(10)])
        client, clock = make_client(transport, max_attempts=3)

        result = client.complete("sys", "user")

        self.assertEqual(result.status, 500)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(len(transport.calls), 3, "must stop at max_attempts")
        self.assertEqual(clock.sleeps, [1.0, 2.0], "no sleep after the final attempt")

    def test_a_transport_error_propagates(self):
        transport = FakeTransport(llm.TransportError("could not reach the endpoint"))
        client, _ = make_client(transport)

        with self.assertRaises(llm.TransportError):
            client.complete("sys", "user")


class RateLimitTests(unittest.TestCase):
    """Requirement 5 and 9: 87 calls must stay inside the published limit."""

    def test_87_calls_are_spaced_to_the_published_limit(self):
        transport = FakeTransport(*[http(200, usage_body()) for _ in range(87)])
        client, clock = make_client(transport, requests_per_minute=60)

        for _ in range(87):
            client.complete("sys", "user")

        self.assertEqual(len(transport.calls), 87)
        # 60 requests per minute is one request per second, so 87 requests span
        # 86 intervals. The first request is free; the other 86 each waited.
        self.assertEqual(clock.now, 86.0)
        self.assertEqual(len(clock.sleeps), 86)
        for slept in clock.sleeps:
            self.assertAlmostEqual(slept, 1.0, places=9)

    def test_the_interval_is_derived_from_the_argument(self):
        transport = FakeTransport(*[http(200, usage_body()) for _ in range(4)])
        client, clock = make_client(transport, requests_per_minute=120)

        for _ in range(4):
            client.complete("sys", "user")

        self.assertEqual(clock.now, 1.5)
        for slept in clock.sleeps:
            self.assertAlmostEqual(slept, 0.5, places=9)

    def test_no_wait_is_added_when_the_caller_is_already_slow_enough(self):
        clock = VirtualClock()

        def slow_transport(url, headers, body, timeout):
            clock.now += 10.0
            return http(200, usage_body())

        client = llm.LLMClient(
            model=MODEL, api_key=FAKE_KEY, transport=slow_transport,
            sleep=clock.sleep, clock=clock.clock,
        )
        client.complete("sys", "user")
        client.complete("sys", "user")

        self.assertEqual(clock.sleeps, [], "a slow caller must not be slowed further")


class CallRecordTests(unittest.TestCase):
    """Requirement 8: every call appends an auditable record."""

    def test_every_call_appends_one_record_with_a_request_digest(self):
        records = []
        transport = FakeTransport(
            http(200, usage_body(prompt_tokens=11, completion_tokens=2,
                                 completion_tokens_details={"reasoning_tokens": 0},
                                 prompt_tokens_details={"cached_tokens": 0})),
            http(200, usage_body(prompt_tokens=13, completion_tokens=4)),
        )
        client, _ = make_client(transport, record_sink=records.append)

        first = client.complete("sys", "one")
        client.complete("sys", "two")

        self.assertEqual(len(records), 2)
        record = records[0]
        self.assertEqual(record["model"], MODEL)
        self.assertEqual(record["request_sha256"], first.request_sha256)
        self.assertEqual(record["prompt_tokens"], 11)
        self.assertEqual(record["completion_tokens"], 2)
        self.assertIn("reasoning_tokens", record)
        self.assertIn("cached_tokens", record)
        self.assertIn("duration_seconds", record)
        self.assertIn("timestamp", record)
        self.assertEqual(record["status"], 200)

    def test_the_digest_is_of_the_request_body_and_differs_per_request(self):
        records = []
        transport = FakeTransport(http(200, usage_body()), http(200, usage_body()))
        client, _ = make_client(transport, record_sink=records.append)

        client.complete("sys", "one")
        client.complete("sys", "two")

        import hashlib

        for record, call in zip(records, transport.calls):
            self.assertEqual(
                record["request_sha256"],
                hashlib.sha256(call["body"]).hexdigest(),
            )
        self.assertNotEqual(records[0]["request_sha256"], records[1]["request_sha256"])

    def test_a_call_without_a_sink_is_fine(self):
        transport = FakeTransport(http(200, usage_body()))
        client, _ = make_client(transport)
        client.complete("sys", "user")


class SecretHygieneTests(unittest.TestCase):
    """Requirement 7 and 9: the key must never appear in a produced string."""

    def test_the_api_key_never_appears_in_any_produced_string(self):
        produced = []
        records = []

        def note(text) -> None:
            produced.append(str(text))

        def sink(record) -> None:
            records.append(record)
            note(json.dumps(record, default=str))

        def attempt(label, callable_):
            try:
                outcome = callable_()
            except Exception as exc:  # noqa: BLE001 - the point is to catch them all
                note(label + " str: " + str(exc))
                note(label + " repr: " + repr(exc))
                for argument in exc.args:
                    note(label + " arg: " + str(argument))
            else:
                note(label + " repr: " + repr(outcome))
                note(label + " str: " + str(outcome))

        captured_out, captured_err = io.StringIO(), io.StringIO()
        with redirect_stdout(captured_out), redirect_stderr(captured_err):
            # 1. the success path, and the client's own reprs
            good = make_client(
                FakeTransport(http(200, usage_body(prompt_tokens=1))), record_sink=sink
            )[0]
            note(repr(good))
            note(str(good))
            note(format(good))
            attempt("success", lambda: good.complete("sys", "user", response_format=llm.JSON_OBJECT_FORMAT))

            # 2. a 200 carrying malformed JSON
            malformed = make_client(FakeTransport(llm.HttpResult(200, MALFORMED_BODY)))[0]
            attempt("malformed", lambda: malformed.complete("sys", "user", response_format=llm.JSON_OBJECT_FORMAT))

            # 3. a 402
            not_provisioned = make_client(
                FakeTransport(http(402, {"error": {"code": "401006"}}))
            )[0]
            attempt("402", lambda: not_provisioned.complete("sys", "user"))

            # 4. an exhausted 429
            exhausted = make_client(FakeTransport(*[http(429, b"") for _ in range(4)]), max_attempts=2)[0]
            attempt("429", lambda: exhausted.complete("sys", "user"))

            # 5. a 5xx
            broken = make_client(FakeTransport(*[http(500, b"") for _ in range(4)]), max_attempts=2)[0]
            attempt("5xx", lambda: broken.complete("sys", "user"))

            # 6. a transport failure
            unreachable = make_client(FakeTransport(llm.TransportError("endpoint unreachable")))[0]
            attempt("transport", lambda: unreachable.complete("sys", "user"))

            # 7. no credential at all
            keyless = llm.LLMClient(
                model=MODEL, api_key="", transport=FakeTransport(),
                env_file=Path("/nonexistent/.env"),
            )
            note(repr(keyless))
            attempt("no key", lambda: keyless.complete("sys", "user"))

        note(captured_out.getvalue())
        note(captured_err.getvalue())

        leaked = sorted({text for text in produced if FAKE_KEY in text})
        self.assertEqual(leaked, [], "the API key leaked into {0} string(s)".format(len(leaked)))
        # The run really did exercise the paths it claims to.
        self.assertTrue(records, "expected at least one call record")
        self.assertTrue(any("not provisioned" in text for text in produced))
        self.assertTrue(any("endpoint unreachable" in text for text in produced))

    def test_the_repr_redacts_the_key_and_the_headers_still_carry_it(self):
        transport = FakeTransport(http(200, usage_body()))
        client, _ = make_client(transport)

        self.assertNotIn(FAKE_KEY, repr(client))
        self.assertIn("api_key=<redacted>", repr(client))

        client.complete("sys", "user")
        # The wire must carry the credential; that is the one place it belongs.
        self.assertEqual(transport.calls[0]["headers"]["Authorization"], "Bearer " + FAKE_KEY)


class CredentialLoadingTests(unittest.TestCase):
    """Requirement 2: the key comes from the environment or from .env."""

    def test_the_environment_wins_over_the_env_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("TOKENHUB_API_KEY=from-the-file\n", encoding="utf-8")

            self.assertEqual(llm.load_api_key(env_file, {"TOKENHUB_API_KEY": "from-the-env"}), "from-the-env")
            self.assertEqual(llm.load_api_key(env_file, {}), "from-the-file")
            self.assertEqual(llm.load_api_key(Path(directory) / "absent.env", {}), None)

    def test_quotes_and_comments_in_the_env_file_are_handled(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "# a comment\nOTHER=1\nTOKENHUB_API_KEY=\"quoted-value\"\n", encoding="utf-8"
            )
            self.assertEqual(llm.load_api_key(env_file, {}), "quoted-value")

    def test_the_repository_env_file_defines_the_variable(self):
        """The workspace ships a .env; if it is present it must define the name."""
        env_path = PROJECT_ROOT / ".env"
        if not env_path.is_file():
            self.skipTest("no .env in the workspace")
        self.assertIsNotNone(llm.load_api_key(env_path, {}))

    def test_a_missing_credential_raises_on_use_not_on_construction(self):
        client = llm.LLMClient(
            model=MODEL, api_key="", transport=FakeTransport(),
            env_file=Path("/nonexistent/.env"),
        )
        with self.assertRaises(llm.MissingAPIKeyError):
            client.complete("sys", "user")


class ConstructorContractTests(unittest.TestCase):
    """Requirement 2: model has no default; the rest are documented defaults."""

    def test_model_is_required(self):
        import inspect

        parameters = inspect.signature(llm.LLMClient.__init__).parameters
        self.assertIs(parameters["model"].default, inspect.Parameter.empty)

        with self.assertRaises(TypeError):
            llm.LLMClient()  # type: ignore[call-arg]

    def test_the_measured_values_are_the_defaults(self):
        import inspect

        parameters = inspect.signature(llm.LLMClient.__init__).parameters
        self.assertEqual(parameters["endpoint"].default, llm.DEFAULT_ENDPOINT)
        self.assertEqual(parameters["temperature"].default, 0.0)
        self.assertEqual(parameters["seed"].default, 42)
        # Reasoning is ON by default: the key is omitted so the model decides.
        self.assertIsNone(parameters["reasoning_effort"].default)
        self.assertEqual(parameters["requests_per_minute"].default, 60)
        self.assertEqual(parameters["endpoint"].default, "https://tokenhub-intl.tencentcloudmaas.com/v1/chat/completions")
        # 600 s, and it is a constructor argument rather than a constant so a
        # caller can shorten it deliberately. The number is derived from
        # measurement; TimeoutContractTests asserts the derivation.
        self.assertEqual(parameters["timeout_seconds"].default, 600.0)
        self.assertEqual(parameters["timeout_seconds"].default, llm.DEFAULT_TIMEOUT_SECONDS)

    def test_an_empty_model_is_refused(self):
        with self.assertRaises(llm.LLMError):
            llm.LLMClient(model="")


class TimeoutContractTests(unittest.TestCase):
    """The request timeout: what it is, why, and what a timeout looks like.

    The default is derived from measurement rather than taste, so these tests
    assert the derivation instead of restating the number. The two errors are
    not symmetric — a timeout that is too long costs *waiting*, one that is too
    short costs *the tokens already spent generating a response that is then
    discarded*, because the provider produced it whether or not the client
    stayed to read it. So the default has to sit well above the slowest call
    anyone has observed rather than close to it.
    """

    # The slowest single call measured on the real case 208 brief, which is the
    # largest prompt this project sends. Recorded with its method, alongside the
    # other per-call durations, in
    # docs/notes/2026-09-21-tokenhub-api-facts.md.
    SLOWEST_MEASURED_CALL_SECONDS = 221.6

    # The limit that actually lost a case: case 109 on hy3 died at 120.1 s.
    THE_LIMIT_THAT_LOST_A_CASE_SECONDS = 120.1

    def test_the_default_is_not_close_to_the_slowest_measured_call(self):
        self.assertGreaterEqual(
            llm.DEFAULT_TIMEOUT_SECONDS, 2 * self.SLOWEST_MEASURED_CALL_SECONDS
        )

    def test_the_default_clears_the_limit_that_cost_us_a_case(self):
        """120 s is a measured failure, not a hypothetical one."""
        self.assertGreater(
            llm.DEFAULT_TIMEOUT_SECONDS, self.THE_LIMIT_THAT_LOST_A_CASE_SECONDS
        )

    def test_the_timeout_is_passed_to_the_transport_unchanged(self):
        """The default reaches the socket, rather than being shadowed inside."""
        transport = FakeTransport(http(200, usage_body()))
        client, _ = make_client(transport)

        client.complete("sys", "user")

        self.assertEqual(transport.calls[0]["timeout"], llm.DEFAULT_TIMEOUT_SECONDS)

    def test_a_read_timeout_reaches_the_caller_as_a_timeout(self):
        """A read timeout is NOT converted, so the caller can classify it.

        This is the fact the runner's failure kinds rest on. A read timeout
        escapes ``response.read()`` as a bare ``TimeoutError`` rather than being
        wrapped in ``urllib.error.URLError``, so ``_urllib_transport`` never
        turns it into a ``TransportError`` and the distinction survives.
        """
        transport = FakeTransport(TimeoutError("The read operation timed out"))
        client, _ = make_client(transport, max_attempts=1)

        with self.assertRaises(TimeoutError):
            client.complete("sys", "user")

    def test_a_connect_timeout_arrives_as_a_transport_error(self):
        """A connect timeout is deliberately grouped as transport, not timeout.

        Nothing was generated, so nothing was wasted, and "wait longer" would be
        the wrong advice. The distinction stays visible because the reason still
        contains the word "timed out".
        """
        import urllib.error
        from unittest import mock

        connect_timeout = urllib.error.URLError(TimeoutError("timed out"))
        with mock.patch("urllib.request.urlopen", side_effect=connect_timeout):
            with self.assertRaises(llm.TransportError) as caught:
                llm._urllib_transport("https://example.invalid/v1", {}, b"{}", 1.0)

        self.assertIn("timed out", str(caught.exception))


class SlowTransport:
    """A transport that spends time and then answers.

    It advances the injected clock by the wall time the call "took" and returns
    the next scripted response. Advancing the clock here rather than sleeping
    keeps the test instant while leaving the client's arithmetic real: a real
    attempt spends wall time waiting, and that is what a deadline has to count.
    """

    def __init__(self, clock, per_call_seconds, *responses) -> None:
        self.clock = clock
        self.per_call_seconds = per_call_seconds
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "body": body, "timeout": timeout})
        self.clock.now += self.per_call_seconds
        if not self.responses:
            raise AssertionError("SlowTransport ran out of scripted responses")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


class CallDeadlineTests(unittest.TestCase):
    """The total deadline for one call, beside the per-attempt timeout.

    ``timeout_seconds`` bounds **one attempt** and ``max_attempts`` multiplies
    it, so before a second limit existed the worst case for a single call was
    four attempts of it plus backoff. Measured on 2026-09-22: a real run wrote
    its last case at 07:25 and was still alive at 09:13 with no output, while a
    direct probe of the endpoint answered HTTP 200 in 0.95 s. The provider was
    fine; the limits simply did not multiply to anything bounded.

    These tests drive the client through its injected transport and clock, so
    the deadline is reached in virtual time.
    """

    # Chosen so the arithmetic is legible: two attempts fit inside the deadline,
    # and the third never could.
    ATTEMPT_SECONDS = 600.0
    DEADLINE_SECONDS = 1200.0

    def client_with(self, per_call_seconds, *responses, **overrides):
        """A client whose transport spends ``per_call_seconds`` per attempt."""
        clock = VirtualClock()
        transport = SlowTransport(clock, per_call_seconds, *responses)
        kwargs = dict(
            timeout_seconds=self.ATTEMPT_SECONDS,
            total_deadline_seconds=self.DEADLINE_SECONDS,
            clock=clock.clock,
            sleep=clock.sleep,
        )
        kwargs.update(overrides)
        client, _ = make_client(transport, **kwargs)
        return client, transport, clock

    def test_no_attempt_starts_that_cannot_finish_inside_the_deadline(self):
        """The discriminating case: the deadline has NOT passed, yet it refuses.

        After a 700-second attempt the clock reads 700 of 1200, so an
        after-the-fact check would happily begin a second attempt and run to
        1400. A pre-attempt check refuses it, because a whole
        ``timeout_seconds`` no longer fits. That is the difference the
        requirement asks for, and this is the only arrangement where the two
        behave differently.
        """
        client, transport, _ = self.client_with(
            700.0, *[http(503, b"") for _ in range(4)]
        )

        with self.assertRaises(llm.DeadlineExceededError) as caught:
            client.complete("sys", "user")

        self.assertEqual(1, len(transport.calls), "no attempt may start that cannot finish")
        self.assertEqual(1, caught.exception.attempts)
        # The clock also carries the 1-second backoff slept after the attempt,
        # so the assertion is on the property that matters -- the deadline had
        # not yet passed when the refusal happened -- rather than on the figure.
        self.assertGreaterEqual(caught.exception.elapsed_seconds, 700.0)
        self.assertLess(caught.exception.elapsed_seconds, self.DEADLINE_SECONDS)

    def test_a_call_that_reaches_the_deadline_raises_the_deadline_failure(self):
        """Not the timeout kind: nothing waited too long, the budget ran out."""
        client, transport, _ = self.client_with(
            self.DEADLINE_SECONDS, *[http(503, b"") for _ in range(4)]
        )

        with self.assertRaises(llm.DeadlineExceededError) as caught:
            client.complete("sys", "user")

        self.assertIsInstance(caught.exception, llm.LLMError)
        self.assertNotIsInstance(caught.exception, TimeoutError)
        self.assertEqual(1, len(transport.calls), "the retries stop at the deadline")
        self.assertLess(len(transport.calls), llm.DEFAULT_MAX_ATTEMPTS)
        self.assertGreaterEqual(caught.exception.elapsed_seconds, self.DEADLINE_SECONDS)
        # The reason names the limit and the budget left, so a reader does not
        # have to open the code to learn what was hit.
        self.assertIn("deadline", str(caught.exception))

    def test_the_per_attempt_timeout_still_behaves_as_before(self):
        """Inside the deadline the retry logic is untouched."""
        client, transport, clock = self.client_with(
            0.0, http(503, b""), http(503, b""), http(200, usage_body())
        )

        result = client.complete("sys", "user")

        self.assertEqual(result.status, 200)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(len(transport.calls), 3)
        # The per-attempt timeout still reaches the socket unchanged, which is
        # what makes the two limits separable rather than one replacing the other.
        self.assertEqual(
            [self.ATTEMPT_SECONDS] * 3, [call["timeout"] for call in transport.calls]
        )
        self.assertEqual([1.0, 2.0], clock.sleeps, "backoff is unchanged")

    def test_a_deadline_below_one_attempt_is_refused_not_clamped(self):
        """Clamping would silently turn every call into a single-attempt one."""
        with self.assertRaises(llm.LLMError):
            make_client(FakeTransport(), timeout_seconds=600.0, total_deadline_seconds=599.0)

    def test_the_default_leaves_room_for_a_full_retry(self):
        """The derivation, asserted instead of the number restated.

        A retry after an attempt that ran into the per-attempt timeout is the
        one thing ``max_attempts`` exists for, so the default has to be at least
        two of them -- and a default below one attempt would be a client that
        cannot make a call at all.
        """
        self.assertGreaterEqual(llm.DEFAULT_TOTAL_DEADLINE_SECONDS, llm.DEFAULT_TIMEOUT_SECONDS)
        self.assertGreaterEqual(
            llm.DEFAULT_TOTAL_DEADLINE_SECONDS, 2 * llm.DEFAULT_TIMEOUT_SECONDS
        )
        # And it must be a bound rather than a restatement of the unbounded
        # worst case it was added to remove.
        unbounded = llm.DEFAULT_MAX_ATTEMPTS * llm.DEFAULT_TIMEOUT_SECONDS
        self.assertLess(llm.DEFAULT_TOTAL_DEADLINE_SECONDS, unbounded)

    def test_the_deadline_is_not_a_hidden_value(self):
        client, _, _ = self.client_with(0.0, http(200, usage_body()))
        self.assertIn("total_deadline_seconds=1200.0", repr(client))


class RequestBodyTests(unittest.TestCase):
    """Reasoning is ON by default, and any optional key can be left to the provider."""

    @staticmethod
    def sent_body(transport):
        return json.loads(transport.calls[0]["body"].decode("utf-8"))

    def test_the_default_body_omits_reasoning_effort_entirely(self):
        """Switching reasoning off must be a choice, never the default state."""
        transport = FakeTransport(http(200, usage_body()))
        client, _ = make_client(transport)

        client.complete("sys", "user")

        sent = self.sent_body(transport)
        self.assertNotIn("reasoning_effort", sent, "the default must leave reasoning on")
        # The other two measured defaults are still sent.
        self.assertEqual(sent["temperature"], 0.0)
        self.assertEqual(sent["seed"], 42)

    def test_passing_none_explicitly_still_suppresses_reasoning(self):
        transport = FakeTransport(http(200, usage_body()))
        client, _ = make_client(transport, reasoning_effort="none")

        client.complete("sys", "user")

        sent = self.sent_body(transport)
        self.assertIn("reasoning_effort", sent)
        self.assertEqual(sent["reasoning_effort"], "none")

    def test_temperature_and_seed_can_be_left_to_the_provider(self):
        """A caller who wants the provider's own sampling must be able to ask."""
        transport = FakeTransport(http(200, usage_body()))
        client, _ = make_client(transport, temperature=None, seed=None)

        client.complete("sys", "user")

        sent = self.sent_body(transport)
        self.assertNotIn("temperature", sent)
        self.assertNotIn("seed", sent)
        self.assertNotIn("reasoning_effort", sent)
        # The parts that identify the request are still there.
        self.assertEqual(sent["model"], MODEL)
        self.assertIn("messages", sent)

    def test_an_explicit_temperature_and_seed_are_still_sent(self):
        transport = FakeTransport(http(200, usage_body()))
        client, _ = make_client(transport, temperature=0.7, seed=7)

        client.complete("sys", "user")

        sent = self.sent_body(transport)
        self.assertEqual(sent["temperature"], 0.7)
        self.assertEqual(sent["seed"], 7)

    def test_the_repr_still_shows_what_is_configured(self):
        client, _ = make_client(FakeTransport(), reasoning_effort=None)
        self.assertIn("reasoning_effort=None", repr(client))
        client_none, _ = make_client(FakeTransport(), reasoning_effort="none")
        self.assertIn("reasoning_effort='none'", repr(client_none))


class PerCallSettingTests(unittest.TestCase):
    """One client, several calls, and the seed is a property of the call.

    The judge's vote asks the same question under several seeds, so one client
    has to be able to vary a setting per call without its own configuration
    being rewritten between them. The default has to leave the body alone,
    which is what keeps a single-draft run the request it always was.
    """

    def sent_body(self, transport):
        return json.loads(transport.calls[-1]["body"].decode("utf-8"))

    def test_a_call_that_names_neither_sends_the_clients_own_settings(self):
        transport = FakeTransport(http(200, usage_body()))
        client, _ = make_client(transport)

        client.complete("sys", "user")

        sent = self.sent_body(transport)
        self.assertEqual(sent["temperature"], llm.DEFAULT_TEMPERATURE)
        self.assertEqual(sent["seed"], llm.DEFAULT_SEED)

    def test_a_per_call_override_wins_without_rewriting_the_client(self):
        transport = FakeTransport(http(200, usage_body()), http(200, usage_body()))
        client, _ = make_client(transport)

        client.complete("sys", "user", temperature=0.7, seed=101)
        first = self.sent_body(transport)
        client.complete("sys", "user")
        second = self.sent_body(transport)

        self.assertEqual(first["temperature"], 0.7)
        self.assertEqual(first["seed"], 101)
        # The client's own settings survived the override untouched.
        self.assertEqual(second["temperature"], llm.DEFAULT_TEMPERATURE)
        self.assertEqual(second["seed"], llm.DEFAULT_SEED)

    def test_two_calls_under_two_seeds_are_two_different_requests(self):
        transport = FakeTransport(http(200, usage_body()), http(200, usage_body()))
        client, _ = make_client(transport)

        client.complete("sys", "user", seed=101)
        client.complete("sys", "user", seed=202)

        seeds = [json.loads(call["body"].decode("utf-8"))["seed"] for call in transport.calls]
        self.assertEqual([101, 202], seeds)

    def test_an_override_of_none_omits_the_key_entirely(self):
        transport = FakeTransport(http(200, usage_body()))
        client, _ = make_client(transport)

        client.complete("sys", "user", temperature=None, seed=None)

        sent = self.sent_body(transport)
        self.assertNotIn("temperature", sent)
        self.assertNotIn("seed", sent)


@unittest.skipUnless(
    os.environ.get(NETWORK_ENV_VAR) == "1",
    "set {0}=1 to run the live TokenHub call".format(NETWORK_ENV_VAR),
)
class NetworkTests(unittest.TestCase):
    """Requirement 10: one real call, skipped by default."""

    NETWORK_MODEL = "hy4-preview"

    def test_a_single_real_call_returns_parseable_json(self):
        if llm.load_api_key() is None:
            self.skipTest("TOKENHUB_API_KEY is not set and no .env value was found")

        client = llm.LLMClient(model=self.NETWORK_MODEL)
        result = client.complete(
            "You reply with JSON only.",
            'Reply with exactly {"ok": true} and nothing else.',
            response_format=llm.JSON_OBJECT_FORMAT,
        )

        self.assertEqual(result.status, 200)
        self.assertIsInstance(result.json_body, dict)
        self.assertEqual(result.parse_outcome, llm.PARSE_PARSED)
        self.assertGreater(result.prompt_tokens, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
