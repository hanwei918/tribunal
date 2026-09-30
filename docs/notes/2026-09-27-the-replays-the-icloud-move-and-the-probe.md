# The replays, the iCloud move, and the model probe

**2026-09-27, evening.** The whole corpus and the whole second development set were
re-run through the judge, a system event moved the working directory out from under
two runs that were in flight, one replay was refused and had to be re-run in full,
and a second model was probed on one case.

**No model call was made by this record, and no prompt was changed.** Every figure
below is read out of the files the runs left behind. The prompt digest is
`83a7431029da37e216d82b75f91349c610e02a314ed9cff22c4a5e4fa59a9ac0` — call it
`83a74310` — for every run recorded here and for the repository as it stands, so
nothing in this note measures a prompt change.

The prompt is **not** frozen. It may still change, until **6 October 2026**, and
only in response to a failure seen across **both** development sets, with every
change regression-run on all of them; it is frozen after that date, and a fresh
sealed set — drafted blind and run exactly once after the 10 October freeze — is
the only figure the submission reports as generalisation. See
`docs/notes/2026-09-25-the-standing-rule-change.md`. Nothing below is that figure.

---

## 0. The state at the end, and how it was checked

Everything in this section is computed, not copied: `eval.grade` over each run
directory, `runner.brief_staleness` over each set with the set's own loader, and
`eval.events --verify` over every event log.

| | corpus | second set (`codex`) | combined |
|---|---|---|---|
| cases present | 29 | 15 | 44 |
| four-field exact match | **29/29** | **14/15** | **43/44** |
| `ruling` | 29/29 | 15/15 | 44/44 |
| `amount_sgd` | 29/29 | 14/15 | 43/44 |
| `driver_compensation_sgd` | 29/29 | 15/15 | 44/44 |
| `referrals` | 29/29 | 15/15 | 44/44 |
| stale (brief) | 0 | 0 | 0 |
| stale (prompts) | 0 | 0 | 0 |
| unknown | 0 | 0 | 0 |

The single miss is **9111**, and it is entirely in `amount_sgd`; the other three
fields are right. That is the recorded policy gap of the second development set,
not something this evening introduced — see
`docs/notes/2026-09-25-the-second-development-set.md`.

**The vote.** The judge is asked `K = 4` times on the same inputs and the majority
decides. Across the 44 results, **41 are unanimous** (`vote_agreement` 1.0) and
**three sit at 0.75** — **107**, **211** and **9113**. All three carried
(`K//2+1 = 3` of 4 is the quorum and the threshold) and all three are correct
against their keys. Re-derived independently from the `vote` events in the event
logs, not from the result files:

```
non-unanimous votes: {107: 0.75, 211: 0.75, 9113: 0.75}
unanimous: 41
```

**Twenty-eight of the 29 corpus results are replays.** Only **207** is a full run:
every other corpus case had its advocates replayed out of an earlier transcript and
only the judge called. The second set is replays all the way through — all fifteen,
including 9115 — for the same reason, and the advocate outputs came from
`runs/codex/deepseek-deepseek-flash`.

Every one of the 44 results records `prompts_sha256 83a74310…`, and every brief
rebuilds to the `brief_sha256` the result stored. So the whole set is current on
both staleness channels, and the figure above is one measurement of one prompt.

### What moved, against the previous commit

Diffing every `case-*.json` at `b25b743` — the commit the evening started from —
against the working tree, on the four fields the vote compares — `ruling`,
`amount_sgd`, `driver_compensation_sgd` and the sorted referral **clause
references** — exactly **two** cases moved, and both moved the same way:

| case | key | at `b25b743` | now | grade |
|---|---|---|---|---|
| corpus **211** | `PARTIAL_REFUND`, 2.00 | `ESCALATE`, null, null | `PARTIAL_REFUND`, 2.00 | miss → **match** |
| second set **9111** | `PARTIAL_REFUND`, 10.15 | `ESCALATE`, null, null | `PARTIAL_REFUND`, 9.15, plus `POL-RD-09(4)` | miss → **miss**, different field |

Both left escalation for a money ruling. 211's new ruling and amount are the key's
exactly, which is where the corpus's 28/29 became 29/29. 9111 now gets the ruling
right and the amount wrong — 9.15 against the key's 10.15, a difference of exactly
1.00 — so the second set stays at 14/15 and its single miss simply changes field
from `ruling` to `amount_sgd`. The v4.1 probe's three 9111 drafts, made by a
different model on the same case, all proposed `PARTIAL_REFUND` at `amount_sgd
9.15` too (§4), so the figure is not one model's accident.

No other case's ruling, money or referral clause reference moved, on either set.
The referral **prose** is free text and was rewritten on eight further cases — 105,
115, 201, 207, 9104, 9108, 9113 and 9114 — which is exactly the kind of change the
vote does not compare and the grader does not score.

**One caveat about `report.md`.** `runs/<model>/report.md` is the **last
invocation's** report, not the directory's. Tonight the corpus invocation ended
with 207 alone and the codex invocation with 9115 alone, so both committed reports
now headline `Cases graded | 1` and `1/1`. The 29/29 and 14/15 above are the whole
directory graded, which is what `python -m eval.grade` does and what the figures in
this note mean. The committed reports are the record of what the run that produced
them printed and are not regenerated.

---

## 1. The runs, in order

All five corpus invocations and all three codex invocations of the evening ran at
`83a74310`, on the owner's balance, with four judge drafts. Times below are local
(UTC+8); the files store UTC, and the two agree.

| # | local | where from | set | cases | how | outcome |
|---|---|---|---|---|---|---|
| 1 | 19:10:28 → 19:27:34 | sandboxed session | corpus | 101–214 requested | judge-only replay | 101–106 completed, then **fatal** on 107 and 108 |
| 2 | 19:33:52 → 19:52:58 | sandboxed session | codex | 9101–9115 requested | judge-only replay | 9101–9112 completed, then **fatal** on 9113 and 9114 |
| 3 | 20:03:41 → 20:17:34 | owner's terminal | corpus | 107, 108 | judge-only replay | both completed |
| 4 | 20:03:48 → 20:12:57 | owner's terminal | codex | 9113, 9114 | judge-only replay | both completed |
| 5 | 20:48:02 → 21:27:30 | `~/Projects/Tribunal` | corpus | 109–214 | judge-only replay, `--concurrency 2` | 17 completed, **207 refused**, stopped mid-flight |
| 6 | 21:35:57 → 22:02:57 | owner's terminal | corpus | 211, 213, 214 | judge-only replay | all three completed |
| 7 | 22:02:57 → 22:07:20 | owner's terminal | corpus | 207 | **full run** | completed |
| 8 | 22:07:20 → 22:11:43 | owner's terminal | codex | 9115 | judge-only replay | completed |

The owner's own account of the evening was 19:10, "about 20:05", 20:52, and "about
21:35". The files give 19:10:28, 20:03:41/20:03:48, 20:48:02, and then a tail of
three invocations at 21:35:57, 22:02:57 and 22:07:20. The recollection and the
record agree on the shape and on the stopping point — the 20:48 invocation's last
event is at **21:27:30**, which is the folder move at about 21:28 — and differ by a
few minutes on the two middle times. The record is what is written down here.

Two of the end times in the table are the **live log's** last line, which is not
always where the invocation ended. Invocation 1's last line *in the live log* is at
19:27:34; its fatal end, and the case it was working on when it died, are in the
iCloud fragment at **19:28:04**, and its final metadata write is stamped
**19:33:51**. Invocation 2's last live line is at 19:52:58 and its fatal end is in a
fragment. Invocations 3, 4 and 6–8 are complete in the live logs.

### What the first two invocations actually died of

Both were killed by the same thing, and it is not a model error. The last line of
each invocation's log is an `invocation_end` whose `detail` is a `LoaderError`:

```
LoaderError: file not found: /Users/hanweizhou/Desktop/Tribunal/policy/general.json
```

That line survives only in a fragment (§2). The live `invocations.json` entry for
each of these two invocations is an intermediate snapshot that still says
`completed`, because `write_metadata` runs after every accepted case and the fatal
error came after the last one.

The corpus invocation's `invocation_end` reports `cases_seen 6` — 101 to 106 done —
and its fragment's `invocations.json` lists **`failed [107, 108]`**. The codex
invocation reports `cases_seen 12` — 9101 to 9112 — and lists **`failed [9113,
9114]`**. In both cases the two cases the invocation was on when it died are the two
it names.

That is not the same as those cases having no result, and it is not the same as
nothing being spent. The fragment's log shows both 107 and 108 reaching a `ruling`
— 108 a `NO_ACTION` at a unanimous 4/4, 107 an `ESCALATE` on a 2/2 split — and the
current `case-00107.json` and `case-00108.json` are **not** the 19:10 run's: their
judge calls are stamped 12:06–12:17 UTC, which is the 20:03 replay, and 107's vote
there is 0.75 against the 19:10 run's 0.5. A result written by a run that then died
is a result the next run overwrote. And all four fragments record `of_which_failed
0`, so the invocation records count **no tokens** against the cases they list as
failed, although the logs show judge calls being made for them — those calls are
recorded nowhere.

That is the first half of §2.

### The 20:48 invocation

Run from `~/Projects/Tribunal`, which is where the repository sat between about
20:47 and about 21:25. It requested 109–214 with `--concurrency 2`, and its
`cases.completed` list is in finish order, which is the order two workers happened
to land:

```
[110, 109, 111, 113, 112, 115, 114, 201, 203, 202, 204, 205, 206, 208, 209, 210, 212]
```

Seventeen cases. `cases.failed` is `[207]`, and 207's failure is a **refusal**, not
a model failure — §3. 211 and 213 were in flight when the folder was moved back at
about 21:25 and the run stopped at 21:27:30; the invocation's own record says
`stop_reason "completed"`, because the interrupt drained what was in flight and
then had nothing left to do. Their results were produced later, by invocation 6.

Its `run_dir` is written down as `/Users/hanweizhou/projects/Tribunal/…` — lower
case, and a different parent — which is what that path was called at the time. It
is the only run record in the repository that names a directory outside
`/Users/hanweizhou/Desktop/`.

---

## 2. The iCloud move

Between about **19:28 and 19:53** the owner turned on iCloud **"Desktop &
Documents"**. macOS moved the Desktop into iCloud Drive and left `~/Desktop`
resolving to the iCloud copy. Two runs were in flight — invocation 1 (corpus) and
invocation 2 (codex) — and one more (the first deepseek-v4.1-flash probe, §4) had
started at 19:10.

Nothing about the repository changed. What changed is which file a path resolved
to.

### The mechanism, and why only the log was hurt

`tribunal/events.py` does not hold the log open. `EventLog.__init__` calls
`_tail()`, which does a fresh `read_lines(self.path)`, and `record` opens the file
again **by path** on every single append:

```python
with open(self.path, "a", encoding="utf-8") as handle:
    handle.write(line + "\n")
    handle.flush()
    os.fsync(handle.fileno())
```

That is deliberate — it is what makes the log survive a crash — and it is also the
one property that made this incident possible. If the path starts resolving to a
different file part-way through a run, the log splits **with no error at all**.
Two processes appending to what had been one file each read their own tail, each
hand out the same `seq` numbers, and the two copies diverge from that point. The
fork is silent: every line is well-formed, every hash is internally correct, and
only `--verify` can see it.

The case **results** are safe for a different reason. `_write_text_atomic` writes
each one through a sibling `.part` file and then renames it:

```python
temporary = path.parent / (path.name + ".part")
temporary.write_text(text, encoding="utf-8")
temporary.replace(path)
```

A case result is therefore written whole or not at all; it can never be found
truncated. The worst a path flip can do to a result is put it in the *other* copy
of the directory, which shows up as a **missing** result rather than a corrupt one.
No result is missing — the directory holds exactly 29 and 15 — and every one of
them parses, grades, and is current on both channels. The `case-*.json` and
`case-*.transcript.json` files are the only inputs `eval.grade` reads, so none of
the figures in §0 ever depended on the event log.

The damage is confined to the one file that is appended to by path:
`events.jsonl`, plus the invocation bookkeeping that the sandboxed invocations
wrote outside the repository.

### The 14 files, as found

Fourteen files were written outside the repository, under the iCloud path. They
are collected, **exactly as found and not merged into the live logs**, under
`runs/_icloud-incident-2026-09-27/`, in three groups named for where each file was
found:

| group | run-level files | holds |
|---|---|---|
| `from-desktop-subfolder/` | 6 | codex `…83887` seq 368–384; v4.1 `…83013` seq 83–89 |
| `from-tribunal-run/` | 6 | corpus `…76652` seq 214–221; v4.1 `…76654` seq 33–37 |
| `from-icloud-root/` | 1 | corpus `…76652` seq 209–213 |

Plus one `.DS_Store` under `from-tribunal-run/`, which `.gitignore` clears. Fourteen
files in all: **five** `events.jsonl`, **four** `invocations.json`, **four**
`run.json`, one `.DS_Store`.

They are committed as evidence, not as history. Merging them would put a second,
contradictory line at sequence numbers the live logs already use.

### The chain breaks, exactly

`python3 -m eval.events --verify` on every live run directory:

```
runs/deepseek-deepseek-flash/events.jsonl
  953 line(s) verified in runs/deepseek-deepseek-flash/events.jsonl: the chain is intact

runs/codex/deepseek-deepseek-flash/events.jsonl
  TAMPERED: the chain first breaks at line 343: chain (prev does not name the previous line)

runs/deepseek-v4.1-flash/events.jsonl
  79 line(s) verified in runs/deepseek-v4.1-flash/events.jsonl: the chain is intact

runs/codex/deepseek-v4.1-flash/events.jsonl
  27 line(s) verified in runs/codex/deepseek-v4.1-flash/events.jsonl: the chain is intact
```

and on each of the five fragments:

```
runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/codex/deepseek-deepseek-flash/events.jsonl
  TAMPERED: the chain first breaks at line 1: chain (prev does not name the previous line)
runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/deepseek-v4.1-flash/events.jsonl
  TAMPERED: the chain first breaks at line 1: chain (prev does not name the previous line)
runs/_icloud-incident-2026-09-27/from-icloud-root/runs/deepseek-deepseek-flash/events.jsonl
  TAMPERED: the chain first breaks at line 1: chain (prev does not name the previous line)
runs/_icloud-incident-2026-09-27/from-tribunal-run/runs/deepseek-deepseek-flash/events.jsonl
  TAMPERED: the chain first breaks at line 1: chain (prev does not name the previous line)
runs/_icloud-incident-2026-09-27/from-tribunal-run/runs/deepseek-v4.1-flash/events.jsonl
  TAMPERED: the chain first breaks at line 1: chain (prev does not name the previous line)
```

Three of the four live logs verify clean; one breaks; the five fragments all break
at their first line. Each case is diagnosed below.

#### `runs/codex/deepseek-deepseek-flash/events.jsonl` — one real hole

449 lines covering `seq 0..454`, and the missing range is **`seq 342..347`**, six
lines. Line 342 (`seq 341`) is a `referee_decision` for invocation `…83887`, and
its hash recomputes correctly:

```
seq 341  hash 64303d424dbbe01acf43c70b7c1cd4728738861e2e538c9f802ef5757754b7f3
```

Line 343 (`seq 348`) is an `agent_call`, and it claims a predecessor the file does
not contain:

```
seq 348  prev 8907c6306d6ed7254ed88efbb534dfa8c17a8afc4f0b0787a7a3abf333406b5e
```

`8907c630…` is not `64303d42…`, so the chain stops there. **Both lines belong to
the same invocation** `…83887` — the 19:33 codex run — so the six lines were
written by that run and are simply not in this file. They were appended while the
path resolved to the other copy of the directory, and no later write repaired the
hole, because the next invocation to append read the tail it found and continued
from there.

**Cause:** the by-path reopen, plus a mid-run path flip. The six lines are in
neither this file nor any collected fragment; they are lost, and this note says so
rather than reconstructing them.

#### The three clean logs, and what they are missing

A clean `--verify` means the chain is unbroken **as written**. It does not mean
every line a run produced is present.

- **`runs/deepseek-deepseek-flash/events.jsonl`** — 953 lines, `seq 0..952`, no
  gaps, five invocations contiguous. It is clean because the 20:03 invocation read
  the tail at `seq 208` and continued at 209, which is exactly where the iCloud
  branch had also continued. The two branches therefore collide at `seq 209..213`
  instead of leaving a hole — see the divergence table below. What this log does
  **not** contain is any `invocation_end` for the 19:10 invocation `…76652` or for
  the 20:48 invocation `…8358`. It has three, for `…89474`, `…25564` and `…37205`.
- **`runs/deepseek-v4.1-flash/events.jsonl`** — 79 lines, `seq 0..78`, clean, and
  it holds **two** invocations: `…76654` at `seq 0..32` and `…83013` at `seq
  33..78`. The first probe's `invocation_end` is not here; the second's is in a
  fragment at `seq 83..89`, so `seq 79..82` are in no collected file.
- **`runs/codex/deepseek-v4.1-flash/events.jsonl`** — 27 lines, `seq 0..26`,
  clean, and it stops mid-case (§4).

#### The five fragments

Each fragment begins at a `seq` far above 0, so its first line's `prev` names a
line the fragment does not contain — hence "breaks at line 1" for all five. That
is not damage; it is what a tail looks like. What matters is whether a fragment
**continues** a live chain or **collides** with it, and the `prev` field answers
that exactly:

| fragment | invocation | seq | first line's `prev` | names the live log's… |
|---|---|---|---|---|
| `from-icloud-root/…/deepseek-deepseek-flash` | `…76652` | 209–213 | `3f74d479…` | `seq 208` hash — **continues** |
| `from-tribunal-run/…/deepseek-deepseek-flash` | `…76652` | 214–221 | `8ae1cc18…` | the fragment above's `seq 213` hash — **continues** |
| `from-desktop-subfolder/…/codex/…` | `…83887` | 368–384 | `25b21d2c…` | `seq 367` hash — **continues** |
| `from-desktop-subfolder/…/deepseek-v4.1-flash` | `…83013` | 83–89 | `56cb3e58…` | **nothing** — the live log ends at `seq 78` |
| `from-tribunal-run/…/deepseek-v4.1-flash` | `…76654` | 33–37 | `50feb651…` | **nothing** — the live log's `seq 32` is the previous line |

The first three are **branches of a chain the live logs already carry** — the two
corpus fragments together are `seq 209..221` of invocation `…76652`, and the codex
fragment is `seq 368..384` of invocation `…83887`. Their last lines are not the
live logs' lines at the same `seq`, and that difference is the fork, recorded in
bytes:

| `seq` | live log holds | fragment holds |
|---|---|---|
| 209 | `invocation_start` of `…89474` | `agent_call` of `…76652`, case 108 |
| 221 | `referee_decision` of `…89474`, hash `2af6415b…` | `ruling` of `…76652`, hash `38cfaa82…` |
| 368 | `invocation_start` of `…89520` | `agent_call` of `…83887` |
| 384 | `referee_decision` of `…89520` | `ruling` of `…83887` |

The last two fragments are **not** branches of anything the live logs hold: the
v4.1 probe's own tail simply went to the other copy, and `seq 79..82` of that
invocation are missing everywhere.

The fragments are also the **only surviving record of the fatal ends**. Each
carries the `invocation_end` that names the move:

| fragment | invocation | `stop_reason` | `cases_seen` | `detail` |
|---|---|---|---|---|
| `from-desktop-subfolder/…/codex` | `…83887` | fatal error | 12 | `LoaderError: file not found: …/Desktop - HANWEI U+7684 MacBook Pro/Tribunal/policy/general.json` |
| `from-desktop-subfolder/…/v4.1` | `…83013` | fatal error | 1 | same iCloud path |
| `from-icloud-root/…/corpus` | `…76652` | fatal error | 6 | `LoaderError: file not found: /Users/hanweizhou/Desktop/Tribunal/policy/general.json` |
| `from-tribunal-run/…/v4.1` | `…76654` | fatal error | 0 | `LoaderError: file not found: /Users/hanweizhou/Desktop/Tribunal/policy/general.json` |

Note the two directions. The fragments found **inside the iCloud tree** report the
**Desktop** path as the one that was not found, and the fragments found **under the
Desktop subfolder** report the **iCloud** path. The move ran both ways inside the
window, and the logs record both.

#### The one Chinese character, and the nine run files that keep it (2026-09-30)

The path above was recorded by the machine with one Han character inside it,
`U+7684`, which sits in the folder name between `HANWEI` and `MacBook`. **This
note now writes it as `U+7684`**, so the note itself carries no Chinese.

The same character is inside **nine tracked files under `runs/`**, where it is
part of the path the machine recorded. Those files are records produced by a run,
and they are **left unedited**: rewriting a recorded run so a scan comes back
clean would be editing the evidence. The nine, found by scanning every tracked
file for a code point in the CJK ranges and counting the code points found:

| file | code points |
|---|---|
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/codex/deepseek-deepseek-flash/events.jsonl` | 1 |
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/codex/deepseek-deepseek-flash/invocations.json` | 5 |
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/codex/deepseek-deepseek-flash/run.json` | 5 |
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/deepseek-v4.1-flash/events.jsonl` | 1 |
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/deepseek-v4.1-flash/invocations.json` | 4 |
| `runs/_icloud-incident-2026-09-27/from-desktop-subfolder/runs/deepseek-v4.1-flash/run.json` | 4 |
| `runs/codex/deepseek-deepseek-flash/invocations.json` | 3 |
| `runs/deepseek-v4.1-flash/invocations.json` | 3 |
| `runs/deepseek-v4.1-flash/run.json` | 3 |

That is 29 code points in total, all of them this one character. No file outside
`runs/` holds a CJK character any more:
`tests/test_language.py` fails on one, and it is the check that keeps it that way.

#### The fragments also carry the true final `invocations.json`

This is the second thing the fragments are for. The live `invocations.json` entries
for the iCloud-era invocations are **intermediate snapshots**, not finals:
`write_metadata` runs after every accepted case with whatever `stop_reason` the
state holds, which is `STOP_COMPLETED` until something sets it otherwise. The
fatal error came after the last accepted case, so the live entry says `completed`
while the run in fact died.

| invocation | live `invocations.json` | fragment `invocations.json` |
|---|---|---|
| corpus `…76652` | `completed`, `failed []` | **fatal error**, `completed [101–106]`, `failed [107, 108]` |
| codex `…83887` | `completed`, `failed []` | **fatal error**, `completed [9101–9112]`, `failed [9113, 9114]` |
| v4.1 `…83013` | `completed`, `failed []` | **fatal error**, `completed [105]`, `failed [107]` |
| v4.1 `…76654` | *not present at all* | **fatal error**, `completed []`, `failed [211]` |

The last row is worth its own sentence: the first v4.1 probe **does not appear in
the live `invocations.json` at all**. Its invocation id exists only in the live
`events.jsonl` (as `seq 0..32`) and in the fragment. Its tokens are therefore
unrecorded in the live history — from its own log, five calls totalling about
**310,600** prompt-and-completion tokens, billed and counted nowhere.

### What this does not change

The per-case results were not affected, and the check is not an argument, it is a
list:

1. **A result is written whole or not at all.** `_write_text_atomic` (§ above), so
   no result can be truncated by an interrupt or a path flip.
2. **Every result is present.** 29 and 15 files, exactly the case sets, no
   shortfall — which is what a result that landed in the other copy would have
   shown as.
3. **Every result parses and grades.** `eval.grade` reads only `case-*.json`, and
   it produced 29/29 and 14/15 with no unreadable file.
4. **Every result is current on both channels.** 0 stale-brief, 0 stale-prompts,
   0 unknown, on both sets, with each set passed its own loader.
5. **Every result has its own history in the live log.** For all 44 cases the live
   event log carries a `ruling` event — 29 of 29 and 15 of 15, none missing — and
   the vote agreement re-derived from those events (41 unanimous; 107, 211, 9113
   at 0.75) is the same one the result files record.

None of the five depends on the damaged file being intact. The event log is the
audit trail; the case files are the result, and the results are whole.

---

## 3. 207's refused replay

Invocation 5 refused 207 before making any call for it. The refusal text was:

```
a recorded entry cannot be copied: response_text is missing
```

That message comes from `tribunal/transcript.py`, `add_recorded`, which refuses to
copy a recorded entry into a new transcript unless every one of `role`, `model`,
`system_sha256`, `user_sha256`, `response_text` and `parse_outcome` is present and
is a non-empty string.

### Which entry, and why

The source transcript is the one the 2026-09-26 full run wrote, last touched by
`bc92487` ("Record the full re-run exactly as produced") and unchanged by tonight.
It has seven entries, and the offending one is **index 1**:

| field | value |
|---|---|
| `role` | `DRIVER_ADVOCATE` |
| `attempts` | 1 |
| `status` | 200 |
| `parse_outcome` | `MALFORMED` |
| `shape` | `NoneType` |
| `note` | `response was not the shape the prompt asked for; retried once` |
| `response_text` | `""` — **empty string** |
| `prompt_tokens` / `completion_tokens` | 15653 / 5725 |
| `reasoning_tokens` / `cached_tokens` | 5725 / 5504 |
| `duration_seconds` | 26.30 |
| `timestamp` | `2026-09-26T15:15:34.079952+00:00` |

It is the **first of the driver advocate's two attempts**. Entry 2 is the retry,
which parsed — `PARSED`, 6268 characters. Entry 0 is the rider advocate, entries
3–6 are the judge's four drafts.

The empty string is not a recording bug. `_response_text` in `tribunal/llm.py`
returns `""` when `choices[0].message.content` is not a string, and a completion
that spent all of its 5725 completion tokens on reasoning and emitted no content
lands exactly there: 5725 reasoning tokens out of 5725 completion tokens, and no
text. `_call_agent` writes one transcript entry per attempt, so the empty attempt
is kept on the record rather than dropped — which is the point, because the retry
that followed only makes sense next to the failure that caused it.

### Was the refusal correct?

**Yes.** `add_recorded`'s contract is that a copied entry must be a complete
record, because the whole reason a transcript can be replayed from is that its
entries hold the text the pipeline consumed. An entry with `response_text ""` has
no text to replay, so copying it would put a hole in the new transcript at exactly
the position the next entry's `prev` bookkeeping assumes is filled. The
alternative — copy it and let the replay carry an empty advocate output — would
make the replay's judge see something the original judge never saw.

The refusal is also *specific*: it named the field, and it refused the case before
`run_dir.mkdir`, so nothing was written, no call was made and no token was billed
for 207 in that invocation. The cost of the refusal is one case re-run in full,
which is what invocation 7 did at 22:02:57 with `replay: null`. It matched.

This is the same rule that keeps a replay honest: **a replay is only as good as
the transcript it copies from**, and 207's committed transcript has an attempt with
no text in it.

---

## 4. The deepseek-v4.1-flash probe

A second model was probed on one case. It is recorded as a probe, not as a
comparison.

### What it produced

`runs/deepseek-v4.1-flash/` holds one result, case **105**, and it **matched**:

| | value |
|---|---|
| `wall_seconds` | 737.955 |
| `call_seconds` | 737.880 |
| `matched` | `true` |
| `vote_agreement` | 0.75 |
| `prompts_sha256` | `83a74310…` |
| `token_budget` | 450,000 |
| tokens | prompt 110,498 · completion 154,495 · reasoning 146,772 · cached 62,208 · **total 264,993** |

The probe ran as **two** invocations, both fatal:

- `…76654` at 19:10:28, requesting **211**. It got as far as the two advocates and
  **three** judge drafts before the `LoaderError` — and it has no entry in the live
  `invocations.json` at all (§2).
- `…83013` at 19:30:28, requesting **105 and 107**. 105 completed; 107 failed with
  the same `LoaderError`, in the iCloud path.

So the "211 and 107 failed with the same file-not-found" is right, and 211's
failure belongs to the earlier invocation, not to the one that produced 105.

### The "about three times the wall time" claim

The comparison the owner made was against **deepseek-flash on the same case**. Three
figures for 105 are available, and they are three different things, which matters
for reading them:

| run | wall (s) | call (s) | judge calls | tokens | vote |
|---|---|---|---|---|---|
| deepseek-v4.1-flash, full run, 19:30 | **737.955** | 737.880 | 4 | 264,993 | 0.75 |
| deepseek-flash, full run, 2026-09-26 (committed) | 971.053 | 970.988 | 5 (4 drafts, one retried) | 367,729 | 0.75 |
| deepseek-flash, judge-only replay, 19:10 (current) | 622.503 | 622.449 | 4 | 237,802 | 1.00 |

Against the corpus as a whole: median **252.2 s**, mean **292.9 s**, max
**1009.3 s** (case 211). So "about three times" holds against the **median** and
the mean — 738 s is 2.9× the median — and it does **not** hold against this case's
own deepseek-flash figures, where it is 0.76× of the committed full run and 1.19×
of the current replay. On this case v4.1 was **faster** than deepseek-flash's full
run and used **fewer** tokens: 737.9 s against 971.0 s, and 264,993 against
367,729.

**Do not sum a replay's transcript.** The current 105 transcript's six entries sum
to 749.45 s, but two of them — the rider advocate's 43.529 s and the driver
advocate's 83.472 s — are **copied from the 2026-09-26 transcript, timestamps
included**, because that is what a replay is. The 749.45 s therefore adds 127.0 s
of borrowed time to 622.4 s of this run's judge time, and `call_seconds` (622.449)
is the judge's four calls alone: 192.276 + 184.894 + 129.671 + 115.608. A figure
that mixes the two runs is not a call time, which is why every comparison here
names which run and which part of it is being measured.

The honest difference is the **distribution**, not the total. v4.1's four judge
drafts took 90.5 s, 88.1 s, 100.2 s and **349.3 s** — the fourth, the
position-swapped one, is 47 % of the whole case. deepseek-flash's four on the
committed full run took 172.7 s, 132.3 s, 146.3 s and 277.9 s, plus a 114.8 s retry
after the fourth came back `MALFORMED` (the same empty-response failure that later
made 207 un-replayable, §3). So v4.1's first three drafts are roughly **half**
deepseek-flash's, and its fourth is 1.26× — one long draft decides the case either
way. And reasoning is 146,772 of v4.1's 154,495 completion tokens (95.0 %), against
150,095 of 156,090 (96.2 %) for deepseek-flash's replay.

**One case cannot compare two models.** There is a single case here; the two runs
were made on different days; and the three figures above are two full runs and one
judge-only replay, so no two of them measure the same thing. The corpus alone
spreads from 252 s to 1009 s, which is wider than the difference being attributed
to the model.

**The runtime model stays `deepseek/deepseek-flash`.** `tribunal/model.py` is
unchanged; `RUNTIME_MODEL` is still `"deepseek/deepseek-flash"` and this probe
overrode it on the command line, which is exactly what `resolve_model` exists to
allow. Nothing in the repository was edited to run the probe.

**A proper comparison belongs on the roadmap.** Measuring two models needs more
than one case, the same cases run both ways with the same advocate inputs, and a
stated statistic; that is work for after the 10 October freeze, not a line in this
record.

### The codex probe

`runs/codex/deepseek-v4.1-flash/` holds whatever the probe left before it was
stopped: one `events.jsonl`, 27 lines, `seq 0..26`, chain intact, invocation
`…87915` at **19:57:19** local (11:57:19 UTC), `cases [9111, 9113]`.

It got through 9111's two advocates and **three** judge drafts — seeds 101, 202 and
303, all `valid=True`, all proposing `PARTIAL_REFUND` at `amount_sgd 9.15` — and
then stopped. There is no fourth draft, no `vote`, no `ruling`, and no
`invocation_end`. `git status` shows no `case-09111.json`, so **no result** was
produced for either case. The three drafts are recorded and billed; the case is
not.

### What the evening cost

Read from the invocation records, `consumed` being what this evening's calls were
billed and `borrowed` being the replayed advocate tokens billed to the earlier runs
they came from:

| set | local | consumed | borrowed | cases |
|---|---|---|---|---|
| corpus | 19:10:28 | 891,571 | 378,594 | 6 |
| corpus | 20:03:41 | 366,390 | 129,728 | 2 |
| corpus | 20:48:02 | 2,398,509 | 1,155,388 | 17 |
| corpus | 21:35:57 | 660,941 | 206,684 | 3 |
| corpus | 22:02:57 | 193,997 | 0 | 1 (full run) |
| codex | 19:33:51 | 1,402,055 | 784,222 | 12 |
| codex | 20:03:48 | 299,544 | 112,636 | 2 |
| codex | 22:07:20 | 145,568 | 55,306 | 1 |
| | **total** | **6,623,568** | **2,822,558** | 44 |

The two fatal entries at 13:03:35 and 13:03:36 local (05:03 UTC) consumed nothing —
they are the unprovisioned-model failure recorded in
`docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`. The v4.1 probe's
264,993 is separate from the 6,623,568, and the first v4.1 probe's ~310,600 is
recorded nowhere.

---

## 5. The viewer, and the one figure the submission may quote

`ui/dist/index.html` was rebuilt with `python -m ui.build`. It went from
**2,326,444** to **2,371,908** bytes — the page embeds every result, its transcript
and the run-level provenance, so re-running the whole corpus and both sets moves it
— and `python -m ui.build --check` reports:

```
/Users/hanweizhou/Desktop/Tribunal/ui/dist/index.html is identical to a fresh build (2371908 bytes)
```

The viewer rebuilds each brief and **refuses** a case whose digest moved rather than
drawing a regenerated brief. The built page's `refused_cases` is `[]`, so no case is
refused by name, and all 29 corpus cases are current under `83a74310`.

The viewer's own totals are computed from `eval.grade` and from the files, never
typed in, so the page and this note cannot disagree about a case.

**The only figure this run contributes to the submission is:**

> **29/29 on the development set, the cases the prompt was tuned on — not a
> generalisation figure.**

It is a development figure. The prompt was tuned on these 29 cases, and it is still
open until 6 October 2026. The generalisation figure is the sealed set's, drafted
blind and run exactly once after the 10 October freeze, and there is exactly one of
those. Nothing else in this note — not 14/15, not 43/44, not the vote counts, not
the v4.1 timings — belongs in the submission.

---

## 6. What this evening did not establish

- It did not change the prompt. The digest is `83a74310…` throughout.
- It did not change the runtime model.
- It did not produce a generalisation figure, and none of its figures is one.
- It did not repair the six lost lines (`seq 342..347` of the codex log) or the
  four missing v4.1 sequence numbers (`seq 79..82`). They are lost and recorded as
  lost.
- It did not merge the incident fragments into the live logs, and it should not:
  they contradict them at the same `seq`.
- It did not measure v4.1 against deepseek-flash in any way that supports a
  conclusion about either model. One case is not a comparison.
- It did not show that a mid-run directory move can corrupt a case result. It
  showed the opposite: results are written whole by rename, and the one file that
  is appended to by path is the one that broke.
