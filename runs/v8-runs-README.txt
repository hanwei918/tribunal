Version-8 runs, made by the owner's side outside WorkBuddy's sandbox, 2026-10-14.
Every run: model deepseek/deepseek-flash, judge votes 4, verifier off, timeout 900 s,
concurrency 2, --parallel-calls, --prompts-dir prompts/v2, policy version 8, each in a clean
git worktree detached at the tag freeze-2026-10-14-v8 (af2b5ca), with the repository's .env
copied in for the run and removed afterwards (never printed). Console logs contain no key
string (checked: 0 matches).

Freeze: annotated tag freeze-2026-10-14-v8 -> af2b5ca, pushed 2026-10-14 11:30.
  "Freeze 6: tribunal/, prompts/ and policy/ at policy version 8 (Ryde Dispute Resolution
  Policy v2.1 with Ryde's answers of 2026-10-14) final; dev-v8 and ryde-v8 run from here"

ryde-v8/            2026-10-14 11:31:05 - 11:38:05, commit af2b5ca
  python3 -m eval.development_sets --set ryde-v8 --parallel-calls --concurrency 2 --timeout 900 --prompts-dir prompts/v2
  2 completed, 0 cached, 0 failed. Four-field exact 1/2 (ruling 1/2, amount_sgd 1/2,
  driver_compensation_sgd 1/2, referrals 2/2).
  902 MATCH: ESCALATE, by version 8's 2 km gate (POL-RD-25) before the judge was asked --
  what Ryde answered on 2026-10-14 (deviation 4.3 km).
  903 MISS: ESCALATE; the key is DRIVER_COMPENSATION 5.00. Drafts: ESCALATE, DRIVER_COMPENSATION
  5.00, ESCALATE, and one voided (DRAFT_CLAUSE_UNRESOLVED: it cited POL-NS-08, which does not
  exist in version 8). At most 2 of 3 valid drafts agreed; 3 were needed. The same divergence as
  at version 7: the rider's fraud flag sets the 0.95 bar (POL-GEN-22) and the arrival rests on
  eight GPS fixes two to four minutes apart.
  Wall clock median 256.2 s; model cost 0.126 USD for the two (repository prices).
  Currency: "all 2 results match the brief and the prompts this code builds".

dev-v8/             2026-10-14 11:31:05 - 12:26:26, commit af2b5ca
  python3 -m eval.development_sets --set dev-v8 --parallel-calls --concurrency 2 --timeout 900 --prompts-dir prompts/v2
  40 completed, 0 cached, 0 failed. Four-field exact 39/40 (ruling 39/40, amount_sgd 40/40,
  driver_compensation_sgd 40/40, referrals 40/40). Escalation 12/40: precision 1.0, recall
  0.923 (over 0, under 1).
  5010 and 5015 (the two keys version 8 changed, 2.3 km and 2.6 km) MATCH: ESCALATE by the
  2 km gate before the judge was asked.
  5017 MISS: NO_ACTION; the key is ESCALATE (INDETERMINATE). A driver-filed route deviation of
  1.2 km, justified by an LTA accident advisory; the driver says he told the rider verbally, the
  rider denies it, and there is no chat notice and no call recording. The key escalates because
  the notice can be established neither way; the judge read the unestablished notice as "not
  informed" (POL-RD-24 row (b), a refund the rider already has) and so ruled NO_ACTION on the
  driver's claim. Not a version-8 change: 1.2 km is under the 2 km limb, and no free wait is
  involved. 5017 matched in the version-7 dev run.
  Wall clock median 153.1 s, p90 299.4 s; model cost median 0.0390 USD per case, 1.823 USD for
  the set (repository prices).
  Tokens 6,132,227 (3,526,272 in, 2,605,955 out).
  Currency: "all 40 results match the brief and the prompts this code builds".
  This is development data: the dev-v7 cases with the version-8 key.

path replacements (part 83's regex, to be applied when these are committed):
  ryde-v8: 3 files, 6 replacements; dev-v8: 3 files, 6 replacements (run.json, invocations.json,
  console log in each); afterwards no file holds a temporary-folder path.
