# The sealed protocol, made executable — what a second invocation retries

**2026-10-03. This note makes no model call.** It records a rule that was
written down in `docs/notes/2026-10-03-the-second-freeze.md` before the sealed
run, and the code that makes the rule something a second invocation actually
follows. It is committed **before** the sealed run of `wild-v2`, so nothing in
it is decided after seeing a result.

## The two statements that could not both be followed

The second freeze note says two things about the retry:

- **"Transient failures are retried once, with the same command."** These are
  `TRANSPORT`, `TIMEOUT` and `DEADLINE`.
- **"A `SHAPE` failure is not retried."**

With the code as it stood on `freeze-2026-10-03`, re-running the same command
could not honour both. `load_cached` and `_persist` in `eval/run_benchmark.py`
keep a case file only for a **success**, and nothing on the run path read
`failure_kind`. So "re-running the same command" meant "re-attempt every case
that has no `case-<NNNNN>.json`", which includes every `SHAPE` failure. A second
invocation could not retry a `TRANSPORT` failure without also re-sampling a
`SHAPE` one, because the two are the same thing to the cache: no case file.

`wild-v1`'s second invocation did exactly that to **517** and **533**. Both had
died `SHAPE` — every judge draft was rejected, because each drafted the key's
amount as a *difference* the read-off rule does not accept — and both were
re-attempted, re-sampling the judge. That second invocation also overwrote
their first transcripts, so the record of what the first attempt actually did
was replaced rather than kept beside it. That is the deviation
`docs/notes/2026-09-30-the-sealed-run.md` records, and it is the reason the rule
had to be executable before `wild-v2` ran rather than merely intended.

## The rule, word for word

> The freeze note's intent stays the same: **a failure caused by the
> infrastructure is retried once; a failure in which the model answered is not
> retried, because retrying it only re-samples the model.**
>
> Code and an addendum note state it in these exact terms:
>
> - An **attempt** of a case is one invocation in which that case has at least
>   one `agent_call` event in the run's `events.jsonl`.
> - A case is **not retried** and is recorded as **no ruling** when its last
>   attempt ended in a `case_failed` event with `failure_kind` `SHAPE` **and**
>   every `agent_call` of that case in that invocation has `status` 200. This
>   covers every judge draft being rejected. It also covers an advocate whose
>   answer was unusable although the server answered 200.
> - A case is **retried once** when its last attempt ended in:
>   - `TRANSPORT`, `TIMEOUT`, `DEADLINE` or `INTERRUPTED`; or
>   - `SHAPE` with any `agent_call` status other than 200, meaning a server error
>     that exhausted the client's retries.
> - **No case gets a third attempt.** A case with two attempts and no result is
>   no ruling.
> - **An attempt that ended with no terminal event does not count.** That is an
>   invocation in which the case has `agent_call` events but neither a
>   `case_failed` nor a `ruling`, because the process was killed. Such an
>   attempt is printed, so the record shows it.
> - **A case with a result is never re-run.** This is unchanged.

The freeze note itself is left unchanged. It is the statement the owner runs
against, and rewriting it after the fact would be editing the thing the rule is
measured by.

## The one place the code had to go past the literal wording

The rule defines an attempt as an invocation with at least one `agent_call`
event. That is exact for a `SHAPE` failure, which reaches the runner with the
transcript entries its calls wrote. It is **not** exact for the four kinds that
are retried: a transport failure raises inside `LLMClient.complete` **before**
the transcript entry exists, so such an invocation records a `case_failed` and
**no** `agent_call` at all. Under the literal definition it would not be an
attempt, so the two-attempt cap could never bind on `TRANSPORT`, `TIMEOUT`,
`DEADLINE` or `INTERRUPTED`, and a case failing that way would be retried
forever.

The executable rule therefore counts an invocation as an attempt when it has an
`agent_call` event **or** a terminal event (`case_failed` or `ruling`) for the
case. Everything else follows the wording exactly: an invocation that only
began the case — because it found it cached, or because the run stopped before
reaching a call — has neither and is not an attempt; an invocation with
`agent_call` events and no terminal event is an attempt that does not count.
The refinement is stated in `eval/development_sets.py` beside the rule and is
covered by `tests/test_sealed_set_wild_v2.py`'s `SealedProtocolTests`.

## Where the rule lives

- **The code.** `eval/development_sets.py`:
  `cases_the_sealed_protocol_will_not_retry`, `_sealed_attempts` and
  `_sealed_verdict`. It reads the run's own `events.jsonl` with
  `tribunal.events.read_events`, read-only, and it applies **only** to a sealed
  set with `force` false — a sealed set is the only kind of run that is retried
  by re-running the same command. Nothing new is imported into `tribunal/`.
- **The tests.** `tests/test_sealed_set_wild_v2.py`'s `SealedProtocolTests`,
  over a scratch runs root and a scripted transport, calling the same invocation
  up to three times: a judge `SHAPE` case with all 200s and an advocate `SHAPE`
  case with all 200s are not called again; a `SHAPE` case with an exhausted 502
  is; a `TRANSPORT` case is retried once and then not at all; an attempt with no
  terminal event does not count; a case with a result is never called again.
- **What is printed.** Every case the rule does not run again, and every attempt
  it does not count, is printed on the invocation:

  ```
  not retried under the sealed protocol: <case_no> (SHAPE, every call answered 200)
  not retried under the sealed protocol: <case_no> (two attempts)
  attempt with no terminal event, so it does not count under the sealed protocol: <case_no>
  ```

## Committed before the run

This note, the code and the tests were committed together, **before** the sealed
run of `wild-v2` was made. The run is made once from a commit whose `tribunal/`,
`prompts/` and `policy/` trees equal those at `freeze-2026-10-03`; the events
that run writes record the commit it was made from. No choice recorded here was
made after seeing a result.
