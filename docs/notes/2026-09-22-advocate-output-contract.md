# The advocate output contract — 2026-09-22

## Summary

`tribunal/pipeline.py` sent every agent `response_format: {"type": "json_object"}`, which constrains
the response to a top-level JSON **object**. `prompts/v1/advocate.system.md` asked the advocate for
"A JSON array of claim objects". The two requirements are incompatible, no model can satisfy both,
and the API-level constraint wins — so the pipeline's own validator rejected every advocate answer,
twice per case, and the case failed.

**Both runs under `runs/` are invalidated.** They were produced under this configuration. They are
kept because they are the evidence for this finding, not because any number in them is usable.

They are **untracked** — not deleted, and not committed either. The raw bodies that prove the finding
therefore live on the machine that produced them and not in this repository, which is a decision this
note records rather than hides. The per-attempt table below is the part of the evidence that travels
with the note, and the digests section lets a reader tell a future run from these without needing the
files.

## How it was found

**Not from the failure label.** Both `runs/*/run.json` files record the advocate failures as `SHAPE`
with the reason:

```
the advocate did not return a JSON array of claims
```

That sentence reads as a statement about the model, and it was read as one: the failures were
attributed to the advocate's output discipline. It was found by opening the transcripts and reading
the raw `response_text` the models had actually returned, which is where the wrapper shows up.

The label was accurate about what the validator saw and misleading about why. That distinction is
the whole finding.

## The evidence, attempt by attempt

**MEASURED** from the transcripts under `runs/`. "Uncited" counts claims missing an `evidence_ids`
or `clause_ids` entry.

| Transcript | # | Agent | Shape the model actually returned | Verdict then |
|---|---|---|---|---|
| `hy4-preview/case-00207` | 1 | RIDER | bare array, 9 claims | accepted |
| | 2 | DRIVER | `{"claims": [11 claims]}`, 0 uncited | **rejected** |
| | 3 | DRIVER | `{"claims": [10 claims]}`, 0 uncited | **rejected** |
| `hy3/case-00108` | 1 | RIDER | one claim object, keys `text`/`evidence_ids`/`clause_ids` | **rejected** |
| | 2 | RIDER | one claim object, 5 keys | **rejected** |
| `hy3/case-00109` | 1 | RIDER | the case JSON echoed back — keys `case_no`/`dispute`/`evidence`/`schema_version` | **rejected** |
| | 2 | RIDER | one claim object, 17 keys | **rejected** |
| `hy4-preview/case-00109` | 1 | RIDER | `{"claims": [6 claims]}`, 0 uncited | **rejected** |
| | 2 | RIDER | bare array, 4 claims | accepted |
| | 3 | DRIVER | bare array, 16 claims | accepted |
| | 4 | JUDGE | object with `ruling`/`discarded_claims` | accepted |

Seven rejected advocate attempts. **Twenty-seven fully cited claims — 11 + 10 + 6 — were discarded
for their wrapper alone, with no citation missing in any of them.**

The two `hy4-preview/case-00207` driver answers are the clearest case, because the same model on the
same case produced a bare array for the rider and an object for the driver. It was not one model
failing to follow instructions; it was one model guessing which of two contradictory instructions
would be enforced.

## What the contradiction does not explain

**One of the seven rejections is not attributable to it.** `hy3/case-00109` attempt 1 returned the
case JSON back — `case_no`, `dispute`, `evidence`, `schema_version` — which contains no claims in
either wrapper. No reading of the advocate prompt makes that a correct answer, so it is a separate
model failure that happened to be recorded under the same label.

Stated plainly because the tempting summary — "every advocate failure traces to this line" — is
false by one, and the difference matters: it means the advocate prompt has more than one thing wrong
with it, and the other one was not fixed here.

## Which runs it invalidates

Both, in full. Every number in them was produced by a pipeline whose advocate stage could not
succeed except by luck.

| Run | Commit | Prompt digest | Requested | Completed | Failed | Never attempted |
|---|---|---|---|---|---|---|
| `runs/hy3/` | `bf1c8dd` | `5c1f58a3…` | 8 | **0** | 108, 109 | 110, 112, 207, 209, 210, 213 |
| `runs/hy4-preview/` | `bf1c8dd` | `5c1f58a3…` | 3 | 109 | 207 | 210 |

`runs/hy3/` produced **no ruling at all** — both cases it reached failed at the advocate, and six of
its eight requested cases were never attempted. It carries no benchmark data to lose.

## The `hy4-preview` case 109 four-field match was obtained in spite of the configuration

`runs/hy4-preview/case-00109.json` records `matched: true` with `ruling_findings: []`, and the
report it fed was the one clean number this configuration produced.

**That match is not evidence that the configuration was sound, and it must not be cited as one.** It
came from the *second* attempt: the rider's first answer was an object and was rejected, the retry
happened to return a bare array and was accepted, and the run proceeded from there. The case
succeeded because a retry landed on the shape the validator accepted, not because the contract was
satisfiable.

Two consequences:

- **The retry is load-bearing, and it is the wrong thing to lean on.** A run whose success depends
  on a second attempt happening to produce a different wrapper is not reproducible, and the
  `matched` flag cannot distinguish it from a run that was never in trouble.
- **The judge on that case saw four rider claims, not six.** The rider's rejected first attempt
  carried 6 claims and the accepted retry carried 4. The judge never saw the other two, and
  `discarded_claims: []` records nothing about them. The ruling was therefore reached on an input
  the model had already been told was wrong — which is a second reason the match is not a
  measurement of anything.

## A second finding, recorded and not fixed here

**Both `run.json` files claim `"completed": true`. Neither run completed.** Neither directory
contains `calls.json` or `report.md`, both of which `run_benchmark` writes only *after* its case loop
finishes; and `runs/hy3/` has metadata for 8 requested cases but reached only 2.

The cause is in `eval/run_benchmark.py`: `state["stop_reason"]` is initialised to `STOP_COMPLETED`
and the metadata file is rewritten after every case, so a process killed mid-run leaves the last
written file saying `completed` — the value it started with rather than the value it earned. A clean
`KeyboardInterrupt` is handled and would have written `"interrupted"`; a SIGTERM, a closed terminal
or a sleeping machine is not.

**This is out of scope for the contract fix and was not repaired.** It is recorded because it changes
how these two files must be read: `"completed": true` in a `run.json` currently means "not known to
have stopped early", and the presence of `report.md` and `calls.json` is the only reliable evidence
that the loop ran to the end. It also means the failed cases' tokens are absent from the recorded
spend — `run_benchmark` charges only completed outcomes to the budget, and `runs/hy3/run.json`
records `spent_this_invocation: 0` for a run whose transcripts carry 83,412 billed tokens.

## The fix

`json_object` was kept. It is what guarantees bare JSON with no markdown fence and no surrounding
prose, measured across all three models on 2026-09-21, and that guarantee is worth more than the
convenience of a bare array. The contract was changed instead.

1. **`prompts/v1/advocate.system.md`** now states that the response is a JSON object with exactly
   one key, `claims`, whose value is the array of claim objects, and its worked example was updated
   to match. Every other rule in the file is unchanged and the stance block is untouched.
   `prompts/v1/README.md` was stating the same array contract in prose and was updated with it.
2. **The pipeline accepts both shapes.** `normalise_claims` takes an object carrying a `claims`
   array or a bare array, and normalises either to a list of claims. A model that returns the array
   directly has answered the question; rejecting it would be measuring the wrapper. Which shape
   arrived is recorded per attempt on the transcript entry as `shape`, so a model's choice between
   the two is countable — and per attempt rather than per case, because the case above shows a model
   changing shape between an attempt and its retry.
3. **The judge is unaffected.** It already returns an object with `ruling` and `discarded_claims`, so
   `json_object` was always correct for it and its prompt does not change.

## The guard against the class, not the instance

`tests/test_pipeline.py::PromptContractTests` checks that for every agent the shape the prompt asks
for is one the `response_format` the pipeline sends can produce. It is structural: the prompt's own
worked JSON example is extracted and parsed, and its top-level shape is compared against
`RESPONSE_FORMAT_SHAPES`, the table of shapes each format permits.

Three things it also pins:

- **The prompt's example is fed to the validator.** If the example the prompt tells the model to
  copy is one the validator refuses, the two have drifted and every obedient model fails.
- **`json_object` permits an object and nothing else.** A guard on the guard: if that table were
  widened, the checks above would stop meaning anything.
- **The example check catches the prompt that was actually shipped**, reconstructed as a fixture.
  Note what does *not* catch it: the validator accepts a bare array, because that is one of the two
  shapes a model may answer with. Tolerating the array in the validator does not make a prompt that
  asks for one consistent with a request that forces an object, and only the format check sees the
  difference.

There is one text check as well, and it is labelled as such in the file: a prompt whose request
forces an object must not contain the phrase "JSON array" anywhere. The thing under test there is
prose and there is no structural way to ask what a paragraph instructs a model to do, so it is kept
as narrow as it can be. It is a backstop; the example check is the guard.

## Digests

| | Value |
|---|---|
| `prompts/v1` digest the invalidated runs used | `5c1f58a3cb00a30bf74e34e236c3a6da94b210dc0b7fd2d212062cf52932993d` |
| `prompts/v1` digest after the fix | `faa3da27c5fbd75052ef7cea11f09de6282f63b522183bf1de49a2fcc892de0b` |
| commit the invalidated runs were made at | `bf1c8ddeadf17575394bf6d36b50c1e2835229ad` |
| answer key digest | `08a3eccfab7fa9d2e5cad923a7a5967f798131e85ca66e398b022e64e4116206` (unchanged) |

A reader comparing a future run against either file under `runs/` can see from the digest alone that
the prompts differ, which is the point of recording it.

## The stance guarantee still holds

`prompts/v1/advocate.system.md` was edited, so the stance-only-difference check was re-run. The two
rendered prompts differ in line ranges `[(8, 9), (12, 18), (19, 20)]`, all inside the stance block at
`[6, 21)`, and the text before and after the block is identical. The project's central claim is
unchanged.
