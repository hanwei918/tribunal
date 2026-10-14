# What one account can carry, and what it costs

**This document describes policy version 8**: Ryde's own Dispute Resolution
Policy v2.1 with Ryde's answers of 2026-10-14. The per-case and monthly figures
below are the **version-6** runs' and say so; the section "At version 8" states
the version-8 ones beside them.

Every figure here is either read from a committed run or computed from one, and
each one says which. Nothing in this file is measured on a live deployment.

## The ceiling per model account

A case is billed a median of 226,125 tokens, 58,364 of them cached prompt
(`python3 -m eval.v6_runs --report`, the corpus's own median line). The provider
publishes two limits per model, 1,000,000 tokens a minute and 60 requests a
minute, and the token limit binds first.

- If cached tokens count against the token limit, 1,000,000 / 226,125 is about
  **4.4 cases a minute**.
- If they do not, the billable figure is 167,761 and 1,000,000 / 167,761 is
  about **6 cases a minute**.
- The request limit does not bind: six model calls a case at 60 requests a minute
  is **10 cases a minute**, which is above both.

The endpoint note records that cached tokens are reported and does not record
which way they count against the limit, so which of the two figures applies is
not known ([the endpoint note](notes/2026-09-21-tokenhub-api-facts.md)). This is
arithmetic over published limits and a recorded median, **computed, not
measured**; the same figures are stated in
[the description](submission/description.md), "Throughput".

## At version 8

The ceiling above is the **version-6** runs'. At version 8 the `dev-v8` run -- 40
cases of development data the team tuned against -- records a median of 153.1 s a
case and a median model cost of 0.0390 USD a case, 1.823 USD over the 40
(`python3 -m eval.v8_report --report`). Read beside the version-6 figures above,
the clock is about the same and the cost is about a third lower, and neither
column is pooled with the other.

## Scaling out

The ceiling above is **per model account**, so the way past it is more accounts
or a higher quota rather than a different pipeline. Each account carries its own
limits and its own key, and nothing in this repository assumes one.

One runner process already works more than one case at a time:
`--concurrency N` on `eval.run_benchmark` and `eval.development_sets` runs N
cases in a pool, and the version-6 development runs used `--concurrency 3`
([the full record](record.md), "Concurrency" and "Running it"). `--parallel-calls`
is a different switch and is about the calls inside one case, not the cases.

## What a month costs, at assumed volumes

The table below is arithmetic, not a measurement: three **assumed volumes**, 30
days, at the two per-case figures the committed runs give — the median 0.0579 USD
and the mean 0.0684 USD, the mean being the version-6 runs' total cost over their
151 cases (`python3 -m eval.business_value --report` and
`python3 -m eval.v6_runs --report`).

| assumed volume | cases a month | at the median, 0.0579 USD | at the mean, 0.0684 USD |
|---|---|---|---|
| assumed volume: 100 disputes a day | 3,000 | 173.70 USD | 205.16 USD |
| assumed volume: 1,000 disputes a day | 30,000 | 1,737.00 USD | 2,051.62 USD |
| assumed volume: 10,000 disputes a day | 300,000 | 17,370.00 USD | 20,516.23 USD |

The two columns differ because the cost per case is skewed: the mean is about a
fifth above the median, so the wider the volume the more the choice of figure
matters. Neither column includes a person's time, an evidence window, or an
appeal.

## 1,000 cases in figures

1,000 disputes, at the two figures the committed runs give:

- **Machine time.** At the 160.4 s median (`python3 -m eval.business_value
  --report`) 1,000 cases are about **44.6 hours** of machine time if they are run
  one at a time. They are not: `--concurrency` overlaps them, so 44.6 hours is an
  upper bound on one account rather than the time anyone waits.
- **Model cost.** At the 0.0579 USD median, 1,000 cases are about **58 USD**.

The brief's own baseline is that a human review takes **24 to 72 hours per
dispute** ([`ops/config.json`](../ops/config.json) records that figure as Ryde's,
and [the full record](record.md), "Business value" states it). That is how long a
rider waits for an answer. It is **not** a staff-hours figure, so it is not subtracted from the
machine time above and the two are not compared as a saving.
