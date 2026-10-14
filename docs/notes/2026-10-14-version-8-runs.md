# The version-8 runs, and version 8 told as what the submission applies

**2026-10-14.** Ryde answered the team's three questions on 2026-10-14 at 10:49
SGT, and the owner adopted the answers the same day as **policy version 8**:
`policy/v8/` is version 7 edited at fifteen JSON paths, `prompts/v2/` still
pairs with it, and the readings the answers settle are written down in
[`2026-10-14-policy-v8.md`](2026-10-14-policy-v8.md).

Two runs were made for version 8, both by the owner outside this sandbox, at
`deepseek/deepseek-flash`, four judge votes, the draft verifier off, a
900-second timeout, concurrency 2, `--parallel-calls` and
`--prompts-dir prompts/v2`, each in a clean worktree detached at the tag
`freeze-2026-10-14-v8` (`af2b5ca`). **No model call was made in this
repository.** The owner's own `README.txt` is committed beside them as
`runs/v8-runs-README.txt`, each run's console log as `runs/<set>-console.log`,
and the same path replacement part 83 applied to the version-7 runs was applied
to these six files when they were committed
([`2026-10-14-local-paths.md`](2026-10-14-local-paths.md)).

## 1. `ryde-v8`, Ryde's two samples

Ryde's own two samples, keyed by **Ryde's stated outcomes as amended by Ryde's
answer of 2026-10-14**: **1 of 2** four-field exact (ruling 1/2, amount_sgd
1/2, driver_compensation_sgd 1/2, referrals 2/2), from the two cases run once
at version 8. Each sample is scored against the answer Ryde gave rather than
against a reading of the policy.

| case | sample | the key | what the system ruled | |
|---|---|---|---|---|
| 902 | DISP-001, route deviation 4.3 km | `ESCALATE` | `ESCALATE`, by version 8's 2 km gate (POL-RD-25) before the judge was asked | **match** |
| 903 | DISP-002, no-show | `DRIVER_COMPENSATION` 5.00, the fee upheld | `ESCALATE` -- two drafts escalated, one upheld the fee and one was voided for citing a clause version 8 does not have; three must agree | **miss** |

**902 is what Ryde answered.** Ryde's answer of 2026-10-14 is that v2.1 6.2's
2 km limb applies, so a route deviation of more than 2 km is escalated rather
than ruled; 902's deviation is 4.3 km, so version 8 escalates it at the gate,
before any draft is asked for, and that is the outcome Ryde stated. The
sample's own stated outcome -- `PARTIAL_REFUND` 3.44, which version 7 followed
-- is superseded by the answer, and the key records that.

**903 is reported as a known divergence, and it is the same one version 7
reported.** The key is `DRIVER_COMPENSATION` 5.00, the fee upheld. The console
and the case file record what the four drafts proposed: `ESCALATE`,
`DRIVER_COMPENSATION` 5.00, `ESCALATE`, and one draft voided with
`DRAFT_CLAUSE_UNRESOLVED` because it cited `POL-NS-08`, which does not exist in
version 8. At most 2 of the 3 valid drafts agreed and 3 were needed, so no
ruling was carried and the case escalated. The reason is the policy working as
written: the rider's profile carries a fraud flag, so POL-GEN-22 raises the bar
to 0.95, and the arrival rests on eight GPS fixes two to four minutes apart,
which cannot carry 0.95. Version 8's answers move no fact of this case, so this
is the same divergence as at version 7, and it is reported rather than fixed.

Correction, 2026-10-14 (evening): 903 escalates because Tribunal's version-8
policy requires a confidence of 0.95 when a party carries a fraud flag
(POL-GEN-22). That is Tribunal's reading of v2.1 6.3 (C15); v2.1 6.2 makes a
no-show ruling AI-final and Ryde's stated outcome upholds the fee, so the
question was put to Ryde on 2026-10-14.

Wall clock median 256.2 s over the two, and a model cost of 0.126 USD for the
two at the repository's prices (`eval/v6_runs.py`). Both cases' results match
the brief and the prompts this code builds.

Corrected 2026-10-14: the table first said the panel split 2-2, which was the
version-7 run.

## 2. `dev-v8`, development data

**39 of 40** four-field exact (ruling 39/40, amount_sgd 40/40,
driver_compensation_sgd 40/40, referrals 40/40), from the 40 cases run once at
version 8. Escalation 12 produced, precision 1.0 and recall 0.923 (over 0,
under 1).

**One case misses.** **5017**: the key is `ESCALATE` (INDETERMINATE) and the
system ruled `NO_ACTION`. A driver-filed route deviation of 1.2 km, justified
by an LTA accident advisory; the driver says he told the rider verbally, the
rider denies it, and there is no chat notice and no call recording. The key
escalates because the notice can be established neither way; the judge read the
unestablished notice as "not informed" (POL-RD-24 row (b), a refund the rider
already has) and so ruled `NO_ACTION` on the driver's claim. **It is not a
version-8 change**: 1.2 km is under the 2 km limb and no free wait is involved,
and 5017 matched in the version-7 dev run.

**5010 and 5015, the two cases whose keys version 8 changed** (2.3 km and
2.6 km), both match: each is escalated by the 2 km gate before the judge is
asked, which is what the version-8 key says. They are the only two entries of
the 40 that differ from the dev-v7 key.

**Say it plainly: this is development data.** It is the dev-v7 cases with the
version-8 key, the team tuned against it and reads it, and 39 of 40 here is not
a generalisation figure and is never pooled with a sealed set's.

Median time to a decision **153.1 s** a case, 90th percentile 299.4 s, and a
median model cost of **0.0390 USD** a case (1.823 USD for the set) at the
repository's prices (`eval/v6_runs.py`). Tokens 6,132,227 (3,526,272 in,
2,605,955 out).

## 3. Not run at version 8

`sealed-v4` is a **version-7 measurement** and was not re-run: it is 30 cases
run once at policy version 7, and under the version-8 rule exactly one of its
cases would change -- 6009, at a deviation of 2.4 km, which version 8's 2 km
gate escalates before the judge is asked -- so no part of it was re-keyed and
no part of it was run again
([`2026-10-14-policy-v8.md`](2026-10-14-policy-v8.md), "The sealed set").
