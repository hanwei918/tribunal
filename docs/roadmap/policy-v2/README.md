# Ji Guofang's platform-aligned policy: drafted 2026-10-07, added as version 3 on 2026-10-08

**Drafted, added as policy version 3, not the default, and not yet measured.**
The draft this folder holds is now part of the runtime as `policy/v3/` — a
second, separate policy base beside the version-1 files in `policy/`, which are
still what `BASE_VERSION = 1` names. Two things are still true of it: **no figure
anywhere in this repository was produced under this draft**, and **no run exists
at version 3**. The owner will make the development runs, and only if version 3
does no worse on them does the default move. Until then
`tribunal/policy_versions.py` still fixes `BASE_VERSION = 1`, the default policy
version is still 1, and every recorded run was made at version 1 or at version 2.

This folder is kept as the archive exactly as it was received, byte for byte. It
is the roadmap document: `policy/v3/` is what the runtime reads, and nothing
reads `docs/roadmap/`.

## Who drafted it, and when

Ji Guofang drafted it on 2026-10-07 against published platform rules — Ryde's own
help centre, the Singapore peers (Grab, Gojek, ComfortDelGro Zig), Uber, and the
standards named in its own sources table. It arrived as the archive
`tribunal-policy-v2.zip`, sha256
`78488e85363e8289a9aecf93e93d929205094433069922b8a2eec135b5c33aed`, and every
file kept here is byte for byte the file that archive holds.

**Why it is version 3 and not her "base version 2".** The version number is
`BASE_VERSION` plus the number of amendments, and that is 1 + 1 = 2. Version 2
already names version 1 plus amendment `0001`, and the sealed `wild-v2` run, the
`policy-v2` run and every `policy_version: 2` record were made under it. Her
bundle sets `BASE_VERSION = 2` and empties `amendments/`, which also computes 2:
two different policies under one number. So `BASE_VERSION` stays 1, nothing under
`policy/*.json` or `policy/amendments/` changes, and her policy is added as a
**new, separate base, version 3**, under `policy/v3/`.

## What it changes

`policy/POLICY-V2-CHANGES.md` is the draft's own account and is kept in full. In
short:

- All three base files become version 3.0.0 in `policy/v3/`, and amendment `0001`
  (`POL-RD-13`) is folded into `route_deviation.json` as a clause of the base, so
  no amendment applies to version 3 at all.
- **A `sources` key per clause**, carrying the provenance that `notes` may not:
  `notes` is what the model reads, `sources` is for people. `tribunal/brief.py`
  drops every `sources` key when the policies are injected, or Ryde's wording,
  the organisers' sample and a sealed-set author would reach the advocates and
  the judge.
- `general.json`: new `execution_threshold_sgd` and a top-level `sources` key,
  and five new clauses — `POL-GEN-04` appeal, `POL-GEN-05` automatic execution
  threshold, `POL-GEN-06` human review, `POL-GEN-07` residual principles, and
  `POL-GEN-08` scope of automated adjudication, disclosure and the right to a
  human.
- `no_show.json`: a `fee_schedule.defaults` block carrying the published Ryde
  parameters, a `resolution_rule` that reads `trip_record.platform_policy` first,
  the whole version-1 pre-pass weight table moved into an `integrity` block, and
  a new `POL-NS-10` (grace after match, scheduled trips, waiting-time fee, one
  fee per trip).
- `route_deviation.json`: `POL-RD-13` folded in from the amendment, and
  `sources` on several clauses.

The clause counts move from 3 / 9 / 12 to 8 / 10 / 13, and
`docs/PUBLIC-CONTRACT-additions.md` is the draft's additive revision of
`data/PUBLIC-CONTRACT.md` for the fields it needs.

## What making it the default would take

None of this has been done, and it is the owner's, not this repository's:

- **a development run at version 3** — the corpus, `codex`, `wild` and `wild-v2`
  as development data, and case 901 from `data/external/ryde-v3/`, into
  `runs/policy-v3/`;
- **a comparison, case by case, with the recorded runs.** Each disagreement with
  a key is decided by Ji Guofang as policy owner, with a written reason, and a key
  is never edited in place;
- **the default moves to version 3 only if it does no worse** on the development
  sets. Then **a freeze tag**, and then **one sealed run**.

Because version 3 is a separate base and versions 1 and 2 build the briefs they
built before, none of this needs a re-registration of the sealed sets, and none
of it needs a full rerun of the recorded briefs: the version-1 and version-2
briefs are byte-identical to the ones already recorded.

## What is not here, and why

- **`eval/backfill_platform_policy.py` is left out.** It rewrites case files in
  all four sets — 27 case files of the held-out set and 8 of the second sealed
  set among them — so it must not be in this repository **even as a document**.
  What it did is described in the draft's own notes, which are kept, and the one
  thing version 3 needed from it — the parameters a version-1 no-show case was
  authored under — is now derived in `tribunal/brief.py` at build time, from the
  version-1 fee table, without touching a single case file.
- **`policy/history/v1/` is left out.** It holds the version-1 bytes and
  amendment `0001` as the archive shipped them. Each was compared with `cmp`
  against the file this repository already carries, and all four are
  byte-identical: `general.json`, `no_show.json`, `route_deviation.json` and
  `0001-pol-rd-13.json`. Nothing is lost by leaving them out, and a second copy
  of a live file is a copy that can drift.
- **Nothing from the archive goes anywhere outside this folder and
  `policy/v3/`.** `data/`, `eval/` and `tribunal/` read nothing from this folder,
  and `tests/test_roadmap_policy_v2.py` asserts that nothing under `tribunal/`,
  `eval/` or `ops/` reads `docs/roadmap/`.

## One caution about the draft's own text

`docs/README-policy-sources.md` is kept exactly as the draft wrote it, and it
describes version 2 **as if it were in force** — "Rulings cite only the clauses
in `policy/`", the sources table, and the closing sentence that says the base
folded amendment 0001 into the base text. It is the draft's own text and is kept
as such. It is a description of the policy as a document; it is not a statement
that this repository runs on it. The policy in force here is version 1 plus
amendment `0001`, and version 3 is available beside it.

## The files, and their digests

Every file below is byte for byte the file the archive holds, and every one of
them still carries the version the draft wrote (`2.0.0` in the three policy
files). The digest is checked by `tests/test_roadmap_policy_v2.py`, so a file
that moves is a failing test rather than a stale claim.

| file | sha256 |
|---|---|
| `case901/case-00901.json` | `93f89fc967dbaaabf6b79b2c2c7c9287434e6077ea80125687ec2d6b517fefba` |
| `case901/mapping-v2-additions.json` | `ad64442d615032dc08e7d9168b5f6e71814f1bf2075347963b8ddffb88edea07` |
| `docs/PUBLIC-CONTRACT-additions.md` | `9289c23d56b2baa4a78d0df7735c287c3421f1419a4e48f3761f48f2c3735fc5` |
| `docs/README-policy-sources.md` | `324f5364a3c4df172f09940c8986ddc9967cfeb0dc327b8c56b05df2339506c9` |
| `policy/POLICY-V2-CHANGES.md` | `376f968fc3c057d922d38c47765db478091d593341d7bef156df94e5edf86bce` |
| `policy/amendments/README.md` | `c38c48a015130f13f7ef3c8337cb7ab977230381a8672d65d388ee21621d9d31` |
| `policy/general.json` | `30dfa2fb0519dd42f921cbea7648a6a7913b83926c3a5a18784f46bdebab9473` |
| `policy/no_show.json` | `8733277745cf5fffe7edd18333824a77ba56ae49481adf1176c3a9d8908041a2` |
| `policy/route_deviation.json` | `6484b4b9f858c3c6f5d07684fd859d579d8babe0334952369baef0eca6b6f67a` |

The archive also carried `eval/backfill_platform_policy.py` and the four
`policy/history/v1/` files; both are left out, for the reasons above.
