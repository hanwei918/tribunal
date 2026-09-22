# TokenHub API facts — 2026-09-21

Everything the transport layer (`tribunal/llm.py`) is built on, with how each item was established,
so a later reader can tell a measurement from an assumption.

## How to read this

| Mark | Means |
|---|---|
| **MEASURED** | Established by a direct HTTP call to the live endpoint on 2026-09-21. |
| **VERIFIED** | Established by inspecting this repository. |
| **ASSUMED** | Not measured. Stated so it can be checked, not relied on. |

**The HTTP measurements were made outside this session and reported in the task brief.** No network
call was made while writing the adapter or its tests; the adapter is exercised entirely through an
injected transport. Nothing below marked MEASURED was re-run here, and no measurement was invented.

## Endpoint and protocol

| Item | Value | How |
|---|---|---|
| Endpoint | `https://tokenhub-intl.tencentcloudmaas.com/v1/chat/completions` | **MEASURED** |
| Protocol | Chat Completions — the first of three integration formats on the TokenHub console's Service invocation panel | **MEASURED** |
| The other two formats | Responses, and a vendor-specific format | **MEASURED** (observed on the panel). Neither is used by this project. |
| Auth header | `Authorization: Bearer <key>` | **MEASURED** |

## Credential

| Item | Value | How |
|---|---|---|
| Variable name | `TOKENHUB_API_KEY` | **MEASURED** / **VERIFIED** (present in this workspace's `.env`) |
| Source | the repository-root `.env` | **VERIFIED** — `.env` exists here and defines `TOKENHUB_API_KEY` |
| Git-ignored | yes | **VERIFIED** — `git check-ignore .env` reports `.gitignore:5:.env` |
| In the ambient environment | no | **VERIFIED** — the variable is not exported in the shell, so the client must read `.env` itself |

## Models

| Model id | State | Free quota | How |
|---|---|---|---|
| `hy3` | provisioned, HTTP 200 | 1,000,000 tokens, 100 % remaining, expiring 2027-09-21 | **MEASURED** |
| `hy4-preview` | provisioned, HTTP 200 | same | **MEASURED** |
| `deepseek/deepseek-flash` | provisioned, HTTP 200 | same | **MEASURED** |
| any unprovisioned model | HTTP 402, body `{"error":{"code":"401006", ...}}` | — | **MEASURED** |

Rate limit: **TPM 1,000,000 / RPM 60, per model** — **MEASURED**.

## Observed behaviours

| Behaviour | Detail | How |
|---|---|---|
| `response_format: {"type": "json_object"}` | accepted by all three models; produces bare JSON with **no markdown fence and no surrounding prose** | **MEASURED** |
| `reasoning_effort: "none"` | suppresses reasoning tokens on all three models | **MEASURED** |
| — its size | an identical request fell from **409 completion tokens to 16** | **MEASURED** |
| `enable_thinking` | silently ignored | **MEASURED** |
| `enable_enhancement` | silently ignored | **MEASURED** |
| `usage.completion_tokens_details.reasoning_tokens` | present | **MEASURED** |
| `usage.prompt_tokens_details.cached_tokens` | present | **MEASURED** |
| Determinism at `temperature: 0`, `seed: 42` | **a property of the model, not the endpoint** — see below | **MEASURED** |
| Prefix caching | **did not engage** — see below | **MEASURED** |

The two ignored parameters are the reason the adapter never sends them; a test asserts they are
absent from the request body.

## Determinism is per model — the finding that shapes the adapter

At `temperature: 0` with `seed: 42`, on three consecutive identical calls:

| Model | Result |
|---|---|
| `hy4-preview` | three **byte-identical** completions |
| `deepseek/deepseek-flash` | three **byte-identical** completions |
| `hy3` | the three completions **differed** |

One of the `hy3` completions was malformed JSON carrying inconsistent quote escaping. Recorded
verbatim:

```
{"ruling\":\"ALLOW"
```

**This is why a 200 can fail to parse, and therefore why `LLMResult` carries an explicit parse
outcome instead of letting a `json.JSONDecodeError` escape from inside the transport.** A malformed
body is an *expected condition*, not an impossible one. The raw text is kept on the result either
way, because a malformed body is evidence about the model and must not be thrown away. That exact
sample is the fixture used by the malformed-JSON tests.

A consequence worth stating plainly: **`seed` is not a determinism guarantee on this provider.**
Any later decision that depends on reproducible model output must pin the model, not just the seed.

## Prefix caching: tested, and it did not engage

Two requests sharing an **identical 15,600-token system prefix** both reported `cached_tokens: 0`.

**This must be re-tested before any prompt is restructured to exploit prefix caching.** The field
exists in the response, so the mechanism is present in the protocol; it simply did not fire on this
attempt. Restructuring the advocate or judge prompts to hoist a shared prefix — for example moving
the whole brief into the system message — would cost tokens and re-order the prompt for a saving
that has not been demonstrated. Treat the caching saving as **zero** until a measurement shows
otherwise.

## What the adapter does with each fact

| Fact | Where it lands |
|---|---|
| endpoint | `LLMClient(endpoint=...)`, default `DEFAULT_ENDPOINT` |
| model id | `LLMClient(model=...)` — **no default**, so the choice is made explicitly by the caller |
| temperature, seed, reasoning effort | constructor arguments. `temperature` defaults to `0.0` and `seed` to `42`; `reasoning_effort` defaults to **`None`**, which omits the key so reasoning stays on. Any of the three may be passed `None` to leave it to the provider. |
| rate limit | `requests_per_minute=60`; the client holds a minimum interval of `60 / requests_per_minute` seconds between HTTP requests |
| 402 / `401006` | never retried; raises `ModelNotProvisionedError` naming the console page, so a wrong model id fails in under a second |
| 429 and 5xx | retried with exponential backoff, bounded by `max_attempts` |
| usage fields | surfaced on `LLMResult` as `prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `cached_tokens` |
| malformed 200 | `parse_outcome = MALFORMED`, `parse_error` set, raw text preserved |
| per-call latency | `timeout_seconds`, default `600.0` (`DEFAULT_TIMEOUT_SECONDS`) — see the timeout section below; a read timeout escapes as a bare `TimeoutError` and is classified as such by the runner |
| the key | read from the environment or `.env`; never written to a log, a `repr`, an exception or a call record |

## Not measured

- **The exact console URL** for enabling a model. The exception names the page descriptively
  ("the TokenHub console, Service invocation panel, where the model is provisioned") and the string
  is a constructor argument, so a precise URL can be substituted once it is known. **ASSUMED** as a
  description, not a link.
- **The behaviour above the rate limit.** The 429 path is implemented and tested against a scripted
  response; a real 429 was not provoked, because provoking one would mean deliberately exceeding a
  published limit. **ASSUMED** that the endpoint answers 429 rather than dropping the connection.
- **Whether `cached_tokens` ever becomes non-zero** for any other prompt shape. See above.
- **Cost.** The free quota is measured; no paid rate was established, and no paid call was made.

## Case 208 advocate measurement — the evidence behind the reasoning default

**MEASURED** on 2026-09-21: six runs of the v1 advocate prompt over the real case 208 brief, one per
model per side, with reasoning left on.

| Model | Side | Wall clock | Prompt tokens | Completion tokens | Reasoning tokens | Claims | POL-GEN-01 lifetime-counter trap |
|---|---|---|---|---|---|---|---|
| `hy3` | rider | 55.2 s | 14,396 | 6,418 | 5,732 | 6 | not engaged |
| `hy3` | driver | 44.8 s | 14,410 | 5,269 | 4,025 | 7 | not engaged |
| `hy4-preview` | rider | 199.9 s | 14,409 | 18,420 | 16,772 | 10 | **identified and refused** |
| `hy4-preview` | driver | 221.6 s | 14,423 | 22,183 | 19,363 | 15 | **identified and refused** |
| `deepseek/deepseek-flash` | rider | 162.0 s | 14,584 | 37,579 | 36,487 | 5 | **identified and refused** |
| `deepseek/deepseek-flash` | driver | 41.4 s | 14,600 | 10,867 | 8,759 | 14 | not engaged |

### What this establishes

The reasoning budget is where the answer quality comes from. The two `hy4-preview` runs spent
16,772 and 19,363 reasoning tokens, produced 10 and 15 claims — the most thorough output of the six
— and on both sides identified the POL-GEN-01 lifetime-counter substitution trap and refused it.
That is why `reasoning_effort` defaults to `None`: the key is omitted, reasoning stays on, and
switching it off is a deliberate cost or latency choice rather than the state a caller lands in by
accident.

### Citation discipline held on all three models

**Across all six runs, every clause id was well-formed and no evidence id was invented.** The
citation contract — a clause id matching `^POL-[A-Z]{2,4}-\d{2}$`, and an evidence id that exists in
the case — was satisfied by all three models on both sides. That is a measured result, not an
expectation.

### "Trap not engaged" is not the same as handling it correctly

A run marked **not engaged** never raised the lifetime-counter issue at all. That is **not** a
statement that it handled the trap properly: it means the question never came up, so the run tells
us nothing about whether the model would have got it right. Only **identified and refused** is
positive evidence. On this measurement two models engaged it on both sides, one engaged it on the
rider side only, and one never engaged it.

### No model has been frozen

**No model has been frozen yet, and this single case is not a sufficient basis to freeze one.** Six
runs over one case cannot separate a model's behaviour from that case's particularities, and the
spread above — 5 to 15 claims, 41 s to 222 s — is exactly the variation a larger sample would need
to characterise. The transport therefore requires `model` with no default, so the choice stays
visible and undecided rather than being settled by an implementation detail.

## Per-call durations and the request timeout — the evidence behind the 600-second default

### The measurements

**MEASURED**, all on the real case 208 brief, which is the largest prompt this project sends. These
are the numbers the default timeout is derived from; the default is not a taste.

| Measurement | Model | Call | Wall clock | How |
|---|---|---|---|---|
| second run | `hy3` | advocate, one side | **38.7 s** | **MEASURED** 2026-09-21, reported in the task brief |
| second run | `hy3` | advocate, other side | **68.9 s** | **MEASURED** 2026-09-21, reported in the task brief |
| first run | `hy4-preview` | advocate, rider | **199.9 s** | **MEASURED** 2026-09-21, table above |
| first run | `hy4-preview` | advocate, driver | **221.6 s** | **MEASURED** 2026-09-21, table above |

The two `hy3` figures are a **second measurement of the same calls**, not a correction of the first.
The earlier table records `hy3` at 55.2 s and 44.8 s for the same two calls. Recorded side by side
rather than merged, because the spread is the useful fact: the same model on the same brief and the
same prompt ranged from **38.7 s to 68.9 s**, so a single figure would understate the tail.

The judge call is **not** in the table and is **larger than any of them**: it carries the same brief
plus both advocates' claim arrays.

### What it cost, before the default was fixed

**MEASURED**: case 109 on `hy3` failed with `TimeoutError: The read operation timed out` at
**120.1 s**, against the then-default of 120 s. Recorded in `runs/hy3/run.json` as
`{"case_no": 109, "failed_agent": null, "reason": "TimeoutError: The read operation timed out"}`.

`failed_agent` is `null` because the timeout happened inside a client call, so no agent had been
identified yet — the failure is not attributable to a side.

At that default, `hy4-preview` would time out on **substantially every call**: both measured
advocate calls exceed 120 s, and the judge call is larger still.

### Why the default is 600 s

**The two errors are not symmetric.** A timeout that is too long costs *waiting*. A timeout that is
too short costs *the tokens already spent generating a response that is then discarded* — the
provider produced the response whether or not the client stayed to read it, and it is billed either
way. Paying for an answer and throwing it away is strictly worse than waiting for it.

So the default sits **well above** the slowest measured call rather than close to it. 600 s is
roughly 2.7× the slowest advocate call measured (221.6 s) and leaves room for the judge call, which
is larger than any advocate call. It is a constructor argument, not a constant, so a caller can
shorten it deliberately; `eval/run_benchmark.py` exposes it as `--timeout`, defaulting to the
client's own default so the two cannot drift.

**VERIFIED**: a read timeout escapes `response.read()` as a bare `TimeoutError`, *not* wrapped in
`urllib.error.URLError`, so `_urllib_transport` never converts it. A *connect* timeout does arrive
as a `TransportError` wrapping a `URLError` whose reason is a timeout — and that is deliberately
left classified as a transport failure rather than a timeout, because a connect timeout means
nothing was generated, nothing was wasted, and "wait longer" would be the wrong advice. The
distinction stays visible because the reason string still contains "timed out".

**One version trap, measured.** `socket.timeout` is not `TimeoutError` on every interpreter:

| Interpreter | `socket.timeout is TimeoutError` |
|---|---|
| 3.9.6 (system) | **`False`** — two separate `OSError` subclasses |
| 3.13.12 | `True` — `socket.timeout` is an alias |

Both measured directly. A read timeout from `urlopen` is the *socket* one, so classifying on
`TimeoutError` alone would let a real timeout fall through to the transport kind on 3.9. The
classifier checks both, and a test pins each.

