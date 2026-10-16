# The try-it service

A visitor's scenario, run through the real pipeline. It is a small
standard-library HTTP server in front of
`tribunal.pipeline.run_loaded_case`, run with the settings of the recorded
version-6 runs — four judge drafts, policy version 6, parallel calls. It adds
nothing to the arbitration: the scenario is built by `tryit/case.py`, the same
code the earlier try-it page ran in the browser, and the pipeline is called as the
benchmark calls it. Each run costs about 0.06 USD in model calls and takes two
to five minutes.

```
TOKENHUB_API_KEY=... python3 -m tryit.server --port 8787
```

## Endpoints

JSON in and out:

| Endpoint | What it answers |
|---|---|
| `GET /api/health` | is a live run available, and how many are left today |
| `POST /api/run` | `{"scenario": {...}}` -> `{"id": ..., "position": n}` |
| `GET /api/run/<id>` | progress while it runs, the result when it is done |

## Limits

All from the environment, so nobody edits code to change them:

| Variable | Meaning | Default |
|---|---|---|
| `TRY_ALLOW_ORIGINS` | comma-separated origins allowed to call it | `https://tribunal.edgeone.dev` |
| `TRY_DAILY_CAP` | live runs per UTC day, all visitors together | `60` |
| `TRY_PER_VISITOR` | live runs per visitor address per UTC day | `3` |
| `TRY_WORKERS` | cases run at the same time | `2` |
| `TRY_MODEL` | model id | `deepseek/deepseek-flash` |
| `TRY_STORE` | where each run's scenario, events and result are kept | `./tryit-runs` |
| `TRY_TRUST_PROXY` | `1` to read the visitor address from `X-Forwarded-For` | unset |

## Testing without a key

- `--recorded-test` answers each call from case 208's recorded run, by role,
  instead of calling a model, and `GET /api/health` says so with
  `"mode": "recorded-test"`. The answers are real recorded model output, but
  they were written for the unedited case, so a scenario run this way is a test
  of the plumbing and not a ruling on the scenario. No key, no cost.
- `--once SCENARIO_JSON` runs one scenario file — the kind the earlier try-it
  page let a visitor download — prints the result and exits. Add `--recorded-test` to it
  for a keyless end-to-end check:

```
python3 -m tryit.server --once scenario.json --recorded-test
```

## The published site does not call it

The site's try-it page is the policy owner's phone demo (part 111): it replays
recorded version-8 runs and calls neither a model nor this service. The earlier
try-it page built a visitor's scenario with `tryit/case.py` under Pyodide in the
browser and could call this service; its files, the Pyodide runtime and the
bundle it loaded left the site at part 116. The service is kept, unchanged, for
running a scenario from the command line; `tryit/build_bundle.py` still lists
the files that bundle carried.
