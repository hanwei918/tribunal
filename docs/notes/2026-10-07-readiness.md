# Readiness report

Computed by `python3 -m eval.readiness`. Every number below is computed from the repository, from the frozen answer keys, or from the speed run named here; nothing is typed in. No model call is made and no browser is launched.

## The measurement run

Named without a path, because an absolute path may not go into `docs/`:

- `invocation_id`: `20261006T124114.291705+0000-67572`
- `git_commit`: `b129824178b51b6d655bc0863f805cc75fe1f82b`
- `model`: `deepseek/deepseek-flash`
- `parallel_calls`: `True`
- `concurrency`: `2`
- `run_json_sha256`: `a7bd22f5dc66c25522717c9f33665d8e1b8be6395717069cab24270ebf959249`
- `cases`: 29
- `configuration`: `{"ablation": null, "judge_votes": 4, "policy_version": 2, "precedents": null, "verify_drafts": false}`
- priced at the **ordinary** tier: 2026-10-06 20:42 SGT is outside the peak windows on a Tuesday

## The five dimensions

### Quality -- PASS

**Quality.**

  The offline replay, per set, sequentially:
  corpus: 29 of 29 cases reproduced
  codex: 15 of 15 cases reproduced
  wild: 64 of 64 cases reproduced
  wild-v2: 20 of 20 cases reproduced

  The confidence floor, over the same four sets:
  504 recorded drafts rebuilt, 0 below the floor and still voting, 0 votes moved

  The speed run's four-field score: 29 of 29 cases exact.

### Speed -- PASS

**Speed.** From the speed run's own case files (29 cases):

  wall_seconds per case:  median 172.929   p90 300.143
  call_seconds per case:  median 373.093   p90 791.199
  the same run one call at a time would have taken its calls in the sum of those durations;
  the ratio of the two medians, wall over calls: 0.4635
  total_tokens per case:  median 198655   p90 305141
  cost per case at the prices given: median 0.053613   p90 0.116050

  Prices: input 0.15 USD/M, output 0.6 USD/M, cached input 0.003 USD/M.
  Priced at the ordinary tier (2026-10-06 20:42 SGT is outside the peak windows on a Tuesday).

  Compared with the sequential policy-v2/deepseek/deepseek-flash run over the 15 case numbers they share:
    its wall_seconds: median 276.767   p90 1049.933
    the speed run's on the same cases: median 150.408   p90 300.143
    the ratio of the medians, sequential over parallel: 1.8401

  For scale, and **not** as a baseline: the recorded wild-v2 run's mean wall_seconds is 429.638 over 20 cases of a different set at a different policy version.

### Reproducibility -- PASS

**Reproducibility.**

  PASS: ui.build --check, every page (exit 0)
  PASS: the two sealed-set manifest tests (exit 0)
  PASS: the offline replay (exit 0)
  PASS: the freeze gate, freeze-2026-10-03 against the working tree, over prompts and policy -- which may show policy/amendments/README.md and nothing else (exit 0)

### Human management -- PASS

**Human management.**

  52 case(s) across the committed runs ended in an ESCALATE. The votes that produced them, by outcome:
    34  carried
    11  escalated
    6  carried_not_unanimous
  and the reason codes they rest on, counted:
    8  DRAFT_AMOUNT_NOT_READ_OFF
    5  DRAFT_CLAUSE_UNRESOLVED
    1  six_pol_gen_03_fields
    1  the judge did not return a JSON object

  PASS: precedents close refuses a command with no --reason
  PASS: policy_gaps approve refuses a command with no --approved-by

### Logs -- FAIL

**Logs.**

  PASS: verify_chain over 13 committed run log(s) -- 1 known break(s): runs/codex/deepseek-deepseek-flash/events.jsonl at line 343: chain (prev does not name the previous line), known, documented in docs/notes/2026-09-27-the-replays-the-icloud-move-and-the-probe.md
  FAIL: 0 of 176 agent_call events in the speed run carry all four new fields (0%); the speed run was made at b129824178b51b6d655bc0863f805cc75fe1f82b, and the fields were added after it, so this criterion cannot be met by that run and is met by every run made since
  PASS: the timeline prints case 101 of the speed run (33 line(s))

## Result

- Quality: PASS
- Speed: PASS
- Reproducibility: PASS
- Human management: PASS
- Logs: FAIL

**At least one dimension fails.**
