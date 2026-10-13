Version-7 runs, made by the owner's side outside WorkBuddy's sandbox, 2026-10-13/14.
Every run: model deepseek/deepseek-flash, judge votes 4, verifier off, timeout 900 s,
concurrency 2, --parallel-calls, --prompts-dir prompts/v2, policy version 7, each in a clean
git worktree detached at the commit named, with the repository's .env copied in (never printed).
Console logs contain no key string (checked: 0 matches for "sk-").

dev-v7-attempt-1/   2026-10-13 23:45:02 - 2026-10-14 00:48:48, commit ebcb753 (part 76)
  python3 -m eval.development_sets --set dev-v7 --parallel-calls --concurrency 2 --timeout 900 --prompts-dir prompts/v2
  40 cases: 35 match, 5 miss (5006, 5016, 5020, 5062, 5063).
  All five: a DRIVER-filed dispute where the platform had already refunded the rider and
  recovered the amount from the driver (fare_adjusted) or reversed the no-show fee
  (fee_reversed). Facts and money right; the ruling word wrong. POL-GEN-03 makes the ruling
  party-relative: the driver's claim fails and the present state stands -> NO_ACTION. The
  system ruled PARTIAL_REFUND / FULL_REFUND of the same amount (5006, 5016, 5062) or split
  2-2 and escalated (5020, 5063). Fixed by part 79 (filing frame + one prompts/v2 paragraph).

ryde-v7-attempt-1/  2026-10-14 00:5x - 00:55:30, commit 3fd5ef8 (part 79)
  python3 -m eval.development_sets --set ryde-v7 --parallel-calls --concurrency 2 --timeout 900 --prompts-dir prompts/v2
  902 MISS: every fact of Ryde's answer found (4.30 km, PIE vehicle fire and congestion justify,
  rider not informed, POL-RD-24 row (b), 4.30 x 0.80 = 3.44) but ESCALATE at confidence 0.75 <
  POL-RD-25's 0.80. The 0.75 was the fare record's weight: the converter had marked Ryde's
  fare breakdown PARTIAL_RECORD because it does not itemise base/time/platform lines; version 7
  needs only the per-km rate and the excess figures, which it states. Fixed by part 79b
  (converter: complete for what version 7 needs; GPS impairments kept).
  903 MISS: ESCALATE at 0.6 against the 0.95 bar the rider's fraud flag sets (POL-GEN-22);
  the arrival rests on eight GPS fixes 2-4 minutes apart. Not changed.

dev-v7-attempt-2-stopped/  2026-10-14 00:5x, commit 3fd5ef8; stopped by the owner's side after
  6 cases (4 match, 2 miss: 5001, 5003). Part 79's filing frame gave every rider filer the
  no-show sentence citing POL-NS-22; a route-deviation brief loads no POL-NS clause, so drafts
  that followed it were voided (DRAFT_CLAUSE_UNRESOLVED) and the panel lacked a majority.
  Fixed by part 79c (category-aware frame; referral paragraph per category; a guard test that
  every clause id outside `policies` resolves in the brief's own policies).

ryde-v7/            2026-10-14 01:3x - 01:43:20, commit 8157af8 (part 79c)
  902 MATCH: PARTIAL_REFUND 3.44, confidence 0.85 -- Ryde's stated answer.
  903 MISS: ESCALATE, the panel split 2-2 between DRIVER_COMPENSATION 5.00 (Ryde's stated
  answer: the fee upheld) and ESCALATE (the 0.95 bar the rider's fraud flag sets is not reached
  on eight sparse GPS fixes). 3 of 4 must agree; they did not. Reported as a known divergence.

dev-v7/             2026-10-14 01:31:44 - 02:31:47, commit 8157af8 (part 79c)
  40 cases: 40 match.
  This is development data the team tuned against (three attempts, two fixes between them).

Freeze: annotated tag freeze-2026-10-14 -> 8157af8, pushed 2026-10-14 02:3x.
  "Freeze 5: tribunal/, prompts/ and policy/ at policy version 7 (Ryde Dispute Resolution
  Policy v2.1) final; sealed-v4 runs once from here"

sealed-v4/          2026-10-14 02:32:37 - 03:14:51, commit 8157af8 = tag freeze-2026-10-14,
  in a clean worktree detached at the tag (tree clean, prompts 22632cd34844, key a416780445f5)
  TRIBUNAL_SEALED_RUN=sealed-v4 python3 -m eval.development_sets --set sealed-v4 --parallel-calls --concurrency 2 --timeout 900 --prompts-dir prompts/v2
  Run once. 30 completed, 0 cached, 0 failed. Nobody on the development side read its answers
  before this run.
  Four-field exact 30/30 (ruling 30/30, amount_sgd 30/30, driver_compensation_sgd 30/30,
  referrals 30/30); route deviation 15/15, no-show 15/15. Wilson 95% 88.6%-100%.
  Escalation 9 produced, 9 expected, 9 true positives: precision 9/9, recall 9/9.
  Wall clock median 139.8 s, p90 262.5 s. Model cost at the repository's prices
  (eval/v6_runs.py) median 0.0398 USD per case, 1.40 USD for the set.
  Tokens 4,657,643 (2,719,854 in, 1,937,789 out).

  One line in this log (and in every version-7 console log above) is a checker error, not a
  property of the run: "cached 30 of 30 results this code cannot vouch for / prompts moved".
  The post-run currency check compares each case's recorded prompt digests with prompts/v1
  (run_benchmark.PROMPTS_DIR) instead of the prompts directory the run used (prompts/v2,
  which every version-7 run must use). Re-checked against prompts/v2 with
  eval.development_sets.currency_for: stale_brief 0, stale_prompts 0, unknown 0 -- all 30
  current. The same wrong default is in the report's "Currency" line
  ("sealed-v4 current 0, ... stale_prompts 30").

  Provenance: written by Claude (Opus 5.5) in a fresh claude.ai chat with no project folder
  or repository access, from the owner's prompt, Ryde's v2.1, the version-7 policy files, the
  public contract, a format checker and the organisers' public sample case. The same model
  helped the team write the version-7 policy files and is the team's development assistant;
  the key was not reviewed by a person. 30/30 says the system applies the version-7 files as
  that author reads them; it is not an independent benchmark, and 30 cases is a small sample.
