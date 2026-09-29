# Policy amendments

One file per amendment, named `NNNN-<slug>.json`, with `NNNN` four digits and
numbered from `0001`. The files are applied in numeric order, and the policy
version a run measures is **1 plus the number of files in this directory**:
version N applies amendments `0001` through `N-1`.

This directory ships **empty**. The policy as committed is version 1.

## What an amendment may do

It adds **exactly one clause** to one of the three policy files. It never edits
a clause and never removes one. That is not caution about version control: the
brief parses the prose of several existing clauses, so an amendment that rewrote
one would change the meaning of a brief built from it without changing the
clause's id, and every recorded `brief_sha256` that rests on that clause would
be measuring something nobody approved.

The id decides which file the clause joins, and must be the **next free number
for its prefix**:

| Prefix | File | Category | Read for |
|---|---|---|---|
| `POL-GEN-` | `policy/general.json` | `GENERAL` | every case |
| `POL-NS-` | `policy/no_show.json` | `NO_SHOW_CHARGE` | `NO_SHOW_CHARGE` cases |
| `POL-RD-` | `policy/route_deviation.json` | `ROUTE_DEVIATION` | `ROUTE_DEVIATION` cases |

The clause's own `category` must agree with the file its prefix names.

Any other prefix is refused, and so is an id whose number is already taken or is
not the next one. When an amendment is applied, the target file's `version`
string gains the suffix `+amendment.<the highest NNNN applied to that file>`, so
a brief says which amendments produced it.

## The file

```json
{
  "base_version": 1,
  "proposal_file": "policy/proposals/0001-<slug>.json",
  "proposal_sha256": "<sha256 of that file>",
  "report_file": "runs/policy-gaps/report.json",
  "report_sha256": "<sha256 of that file>",
  "cluster_id": "C1",
  "cases": [101, 102, 103],
  "approved_by": "<name>",
  "approved_at": "<ISO 8601>",
  "clause": {
    "id": "POL-RD-13",
    "title": "...",
    "category": "ROUTE_DEVIATION",
    "rule": "...",
    "requires": ["..."],
    "licenses": ["..."],
    "favours": "RIDER",
    "notes": "..."
  }
}
```

`clause` carries the same eight fields every other clause carries. The fields
beside it are provenance: which proposal was approved, which report produced it,
which cluster of cases prompted it, and who approved it and when. They are there
so an amendment can be traced back to the evidence that asked for it.

## Who writes here

**Only a human, through `approve`.** Nothing else writes to this directory: not
a run, not the drafter, and not any test. A draft is a proposal, and a proposal
is a file under `policy/proposals/` until a person approves it.
