# Replaying the advocates

**A mode that reads a case's two advocate outputs out of an earlier run's transcript and calls only
the judge. It exists so that a change to one agent's prompt can be measured through that agent alone
instead of through all three, and so that a comparison meant to measure one change does not acquire
two agents' sampling variance on the way. No model call was made while building it: the check below
is read-only.**

| | |
|---|---|
| Source run | `runs/deepseek-deepseek-flash/` |
| Source commit | `493beeaf94953943116a25cb74353b3dd2279499` |
| Source model | `deepseek/deepseek-flash` |
| Source prompts digest | `b131e63f046aecc68471631df8c04f9e0fde88d3383775028f8da058474bc3d3` |
| Prompts digest now | `eece65ee58ab78de1ace84079e63c8a4de3bb63e3f4b2adc12b7a2a3d8bd6397` |
| What the source's advocates cost it | 1,732,682 of its 2,804,061 billed tokens — 61.8 % |
| Dry check against the source | 29 of 29 corpus cases accepted, 0 refused |
| Suite | 835 tests, OK (skipped=3) |

The prompt file that moved is `prompts/v1/judge.system.md`, twice, on 2026-09-24
(`docs/notes/2026-09-24-meeting-a-limb-and-the-dropped-record.md` and
`docs/notes/2026-09-24-the-limb-procedure-revised.md`). The advocate system prompts and every corpus
brief are byte-identical to what the source run recorded, which is what makes a replay possible at all
and what the acceptance check below establishes case by case rather than assumes.

---

# Why replay rather than re-run

The judge prompt changed; the advocates' did not. Re-running the advocates would regenerate inputs the
judge already has, at 61.8 % of the run's bill — measured, not estimated: the two advocate entries in
the 29 committed transcripts sum to 1,732,682 billed tokens against the judge's 1,071,379. It would
also put two agents' sampling variance into a comparison whose whole point is to isolate one change, so
a difference between the two runs could not be attributed to the prompt that moved.

**Replay is not a way round the identity checks.** It is a way of asking the judge the same question
with the same inputs, and it refuses to answer at all when it cannot establish that the inputs are the
same.

# What a replay refuses

A case is refused — recorded as a failure with its reason, **no model call, no cache entry, no
transcript** — unless every one of these holds:

| Condition | Why it is checked |
|---|---|
| The brief this repository builds now hashes to the `brief_sha256` the source result recorded | Otherwise the judge would be asked about facts the source's advocates never saw |
| Each advocate's system prompt, as rendered now, hashes to what the source recorded for that role | Otherwise the recorded output answers a question this build no longer asks |
| The model is the same | A different model's advocates are not this run's inputs |
| The recorded answer parsed | An unusable answer is not an answer to replay |

A run that did not record a prompt digest is **refused**, not assumed to match: "no recorded digest" is
`unknown`, the same rule the staleness report applies, and it must never read as `current`.

Two further properties are code rather than intention. The judge's user message is built by **the same
function a full run uses** (`_judge_user_message`), not by a second copy of it, and the two brief-identity
checks that guard a full run are repeated on the replay path — so a replay cannot hand the judge
different bytes than a full run would, and a test compares the two request bodies to say so. And
`check_replay` runs for every requested case **before** `run_dir.mkdir`, so a replay into the directory
it reads from reads and verifies every source entry before it writes any; the previous results stay
retrievable from git history in any case, and a test drives that order with a mock.

# The two figures, kept apart

The borrowed advocates' usage is **reported and charged to nothing in this run**. It travels in the
per-case cache entry (`replay.tokens`) and in `run.json`, where it is named
`tokens.billed_to_another_run` and sits apart from `spent_this_invocation` and
`consumed_this_invocation`; the result's own `tokens` are the judge's alone. The runner's ledgers are
now four — charged, failed, reused, replayed — and only the first three are this invocation's.

Wherever the figures appear, the record says whose they are:

- **The report** marks the headline figure `**(advocates replayed)**`, adds an `Advocates` row naming
  the source, adds an `advocates` column to the per-case table only when there is a replay to report,
  and renders a section that names each source and the borrowed cost.
- **The summary** prints the replay block before the figures, counts the refusals, and prints "plus N
  billed to the run the advocates came from… no figure above includes" beside them.
- **The viewer** adds a lead paragraph to the overview, a badge and a note to each replayed case, and a
  footer field that answers either way — "replayed from …; only the judge was called" or "called by
  this run" — because a reader looking for the answer must find one whether the answer is yes or no.

# What is recorded as provenance

Per case, and per run: the source run directory, its git commit, and the source transcript's sha256 —
**the digest of the file's bytes as they stand**, computed rather than trusted. The source run's own
recorded `transcript_sha256` is compared against it and a mismatch refuses the case, so a transcript
edited after it was written cannot be replayed. The brief digest, the model, the number of advocate
calls and the borrowed token split are recorded beside them.

# The dry check, in full

`python -m eval.run_benchmark --replay-check runs/deepseek-deepseek-flash` — reads only, writes nothing,
calls nothing. Run against the real headline run, whose prompts digest is `b131e63f…` against the
current `eece65ee…`, which is exactly the state replay exists for:

```
replay check  runs/deepseek-deepseek-flash
  source commit   493beeaf94953943116a25cb74353b3dd2279499
  source model    deepseek/deepseek-flash
  source prompts  b131e63f046aecc6

  case 101  accepted  2 advocate call(s), brief fd9b9761368a193a
  case 102  accepted  2 advocate call(s), brief 24bb68bce91c4916
  case 103  accepted  2 advocate call(s), brief 61eab1e081b05452
  case 104  accepted  2 advocate call(s), brief 079cb9a74922d8eb
  case 105  accepted  2 advocate call(s), brief f200111d32c9646f
  case 106  accepted  2 advocate call(s), brief 9a9f177030ec6f40
  case 107  accepted  2 advocate call(s), brief 538c6bf78353676a
  case 108  accepted  2 advocate call(s), brief 89a20c242d1c3051
  case 109  accepted  2 advocate call(s), brief 02c15cfbe0d9fbf3
  case 110  accepted  2 advocate call(s), brief ff551bd1677dc939
  case 111  accepted  2 advocate call(s), brief 2d55b98375ff2248
  case 112  accepted  2 advocate call(s), brief abe22f55516337fd
  case 113  accepted  2 advocate call(s), brief 7971592076111e2a
  case 114  accepted  2 advocate call(s), brief ad05a9bbd624be69
  case 115  accepted  2 advocate call(s), brief 89640828b9faeaea
  case 201  accepted  2 advocate call(s), brief 2c68f82ee7b58df9
  case 202  accepted  2 advocate call(s), brief 1b5fb62fb6b20499
  case 203  accepted  2 advocate call(s), brief 1edf234540f4e6ed
  case 204  accepted  2 advocate call(s), brief c74a3dbd373170d9
  case 205  accepted  2 advocate call(s), brief 76571f258be8efec
  case 206  accepted  2 advocate call(s), brief b5049a0ff4d13cd6
  case 207  accepted  2 advocate call(s), brief 57031ec4856c3b3e
  case 208  accepted  2 advocate call(s), brief a2671c6d1f087715
  case 209  accepted  2 advocate call(s), brief e1702e3ed6647eac
  case 210  accepted  2 advocate call(s), brief f9d9f153dab873d0
  case 211  accepted  2 advocate call(s), brief 614388d841cd7396
  case 212  accepted  2 advocate call(s), brief 6c4de3430c8a4668
  case 213  accepted  2 advocate call(s), brief 871f9010c925798d
  case 214  accepted  2 advocate call(s), brief fd64cd2b39200257

  29 accepted, 0 refused, of 29 asked about. No model was called and nothing was written.
```

Every case is accepted, which is the claim the two digest moves make: the briefs have not moved, the
advocate prompts have not moved, and the only thing that has is the judge's instructions. Two cases
(115 and 213) carry four transcript entries rather than three because their judge's first answer was
unusable and was retried; both still supply exactly two advocate calls, so the retry is a fact about
the judge and not about what is replayed.

# What is never replayed

**An external case.** Case 901's converted brief changed after its one run — it gained the source's own
account of how the arrival marker was made — so its `brief_sha256` no longer matches, and its run is
stale on both channels. It is re-run in full with `--external`, as before. `--replay-advocates` with
`--external` is refused by the CLI, and `run_one_case` raises if it is ever handed both.

**A comparison.** `--compare` takes no replay arguments. A table mixing a run that called its own
agents with one that borrowed another's is comparing two different measurements, and the refusal is
what stops the mixing being silent.

# What is tested

- **`tests/test_run_benchmark.py`, 25 new checks.** One call per replayed case and it is the judge's;
  the judge's user message byte-identical to what the full pipeline builds from the same claims; the
  advocate entries copied verbatim and marked as replayed; the cache entry and `run.json` naming the
  source, its commit, the transcript digest, the brief digest, the model and the advocate call count,
  with the result's tokens the judge's alone; the borrowed tokens reported and never charged; the
  report and the viewer saying the advocates were replayed and from where; a run that replayed nothing
  saying nothing. Refusals on a brief mismatch, an advocate prompt mismatch, an unrecorded prompt
  digest, a model mismatch, an unparsed recorded answer, an edited source transcript and a case the
  source never ran — each with a transport that **fails the test if the refused case is reached**, so
  "no call was made" is a property of the rig rather than a count that could be zero for the wrong
  reason. Plus: a refusal leaves no cache entry and no transcript; a missing source directory raises;
  every source is read before anything is written; a replay into its own directory reads the original
  entries; an external case is never replayed; the CLI refuses the two flags together, exits 0/1 from
  `--replay-check`, and takes no replay arguments with `--compare`.
- **`tests/test_ui_build.py`, 7 new checks.** The viewer's own statements about a replay, driven from a
  fixture run directory with the block written in the shape the runner produces. The page is a template
  plus data, so the two halves are asserted separately: the source path appears only in the data and
  the sentence that reads it only in the script, which is why a page that carried the fact and never
  rendered it fails one assertion and a page that rendered a sentence with nothing behind it fails the
  other. Plus the negative case — a run that called its own advocates must have a branch that answers
  no, not an absent field — a foreign source path named rather than published, and the source read from
  the case entries rather than from the invocation.
- **One pre-existing assertion was meant to fire.** The deliberate cache-shape guard in
  `test_the_cache_entry_carries_the_run_it_came_from` lists the entry's keys exactly; it went red on
  `+ 'replay'`, which is the guard doing its job, and `"replay"` was added with a comment saying why an
  absent key would be ambiguous rather than merely missing.

# What this does not establish

- **No model call has been made.** The mode is untested against the live provider. What is untested is
  the wiring, not the transport: the judge goes through the same `_call_agent`, the same guards and the
  same case deadline as a full run, and a test asserts the request bodies are the ones a full run
  builds.
- **The dry check does not predict the rulings.** It says the source can supply the advocates for all
  29 cases. Whether the re-run judge agrees with the answer key is the question the re-run is for, and
  the judge prompt changed on purpose — so a difference is the measurement, not a defect.
- **A replayed run is not a whole-pipeline measurement.** The figures describe the judge on fixed
  inputs. That is the point of the mode and it is stated wherever the figures are, including in the
  cache entry, so that no later reader can mistake one for the other.
