# The seven-case rerun

**2026-09-25.** The seven cases whose briefs gained `erp_gantry_proximity` were
rerun in full at commit `848acef`, during peak hours, on the owner's balance.
The run directories below are committed exactly as produced in a separate
run-record commit. No model call was made for this note.

## Commands and results

```
python3 -m eval.run_benchmark --cases 103,106,114,115 --force
python3 -m eval.development_sets --set codex --cases 9111,9113,9114 --force
```

| set | case | ruling | amount_sgd | driver_compensation_sgd | result |
|---|---:|---|---:|---:|---|
| corpus | 103 | `PARTIAL_REFUND` | 4.00 | `null` | match |
| corpus | 106 | `PARTIAL_REFUND` | 10.75 | `null` | match |
| corpus | 114 | `PARTIAL_REFUND` | 13.70 | `null` | match |
| corpus | 115 | `PARTIAL_REFUND` | 2.00 | `null` | match |
| codex | 9111 | `PARTIAL_REFUND` | 9.15 | `null` | amount miss; referral now matches |
| codex | 9113 | `PARTIAL_REFUND` | 9.05 | `null` | match |
| codex | 9114 | `FULL_REFUND` | 3.20 | `null` | match |

The corpus invocation is **4/4**. In the codex invocation, **9113 and 9114
match**. `9111` still misses on amount, producing `9.15` against `10.15`,
while its referral now matches.

## Cost

`billed` is prompt tokens plus completion tokens. Reasoning tokens are a
breakdown of completion and are not added.

| set | case | prompt | completion | of which reasoning | billed |
|---|---:|---:|---:|---:|---:|
| corpus | 103 | 46,994 | 34,013 | 30,976 | 81,007 |
| corpus | 106 | 47,054 | 31,801 | 27,316 | 78,855 |
| corpus | 114 | 47,931 | 68,260 | 63,843 | 116,191 |
| corpus | 115 | 48,044 | 29,722 | 25,685 | 77,766 |
| **corpus total** | | **190,023** | **163,796** | **147,820** | **353,819** |
| codex | 9111 | 46,471 | 80,424 | 76,750 | 126,895 |
| codex | 9113 | 48,961 | 77,723 | 72,096 | 126,684 |
| codex | 9114 | 45,345 | 36,835 | 32,923 | 82,180 |
| **codex total** | | **140,777** | **194,982** | **181,769** | **335,759** |
| **seven-case total** | | **330,800** | **358,778** | **329,589** | **689,578** |

The run records show these seven cases were produced at `848acef`, with no
failures and no cached cases in either invocation.

## The remaining 9111 gap

The judge wrote of the Pioneer Road line:

> "lies on the optimal route and is properly chargeable"

This is a gap in the policy text, not a slip by the judge. POL-RD-02 allows the
optimal route's ERP in the recomputed fare, while POL-RD-09(4) refunds a line
the trace never passes, and neither says which governs an on-route line the
trace never passes. The referee work must preserve this as a policy ambiguity
rather than treating the sentence as a model error.

The key is not changed after seeing a result. The recorded `9111` amount
remains `9.15` against the frozen `10.15` expectation.
