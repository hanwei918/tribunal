# The freeze moved to this commit

> **Correction, 2026-09-30, later the same day.** "The sealed set" in this note
> means `wild-v1`, now called **the held-out set (`wild-v1`)**: 64 cases derived
> from real complaints, prepared by their author as a development set, which
> nobody who changed the system opened before the freeze tagged
> `freeze-2026-09-30` and which was run once from that tag. Every sentence below
> is kept as written; nothing in this note changes.

**2026-09-30.** The sealed set is run once, and the rule that dates it says
"after the 10 October freeze" (`docs/notes/2026-09-25-the-standing-rule-change.md`,
*The rule that is*). This note **moves that freeze to this commit** and records
the freeze before the set enters the repository. The sealed set itself is
imported in a later commit, under the tag this note creates.

Nothing in this note changes a ruling, a prompt, a policy or a case file. It
records a date and a set of digests.

## The rule change, and why

- **The rule that was.** A fresh sealed set, drafted without access to this
  repository and seen beforehand by nobody who works on the prompt, is run
  exactly once after the 10 October freeze; that single run is the only figure
  the submission reports as generalisation.
- **The rule that is.** The freeze is **now**, at the tag `freeze-2026-09-30`.
  The sealed set is run once from this commit, and that run is the
  generalisation figure.
- **The reason.** No pending change would alter a ruling. Everything still
  outstanding before submission touches documents, the viewer, or switches that
  stay off: notes, `runs/README.md`, the viewer's panels, and the `--precedents`,
  `--ablate`, `--policy-version` and `--verify-drafts` switches, all of which are
  off in the configuration below. Moving the date forward does not make the
  figure less honest; leaving the system able to change under a run that has
  already been taken is what would.
- **The precedent.** The change is recorded in its own dated note **before the
  set is in the repository**, exactly as the 2026-09-25 rule change was recorded
  in `docs/notes/2026-09-25-the-standing-rule-change.md` rather than folded into
  the note it amended. The 2026-09-25 note is not rewritten and neither is any
  other: each records the rule in force on its own date.

> **Correction, 2026-09-30, later the same day.** "The sealed set" in this
> section means `wild-v1`, now called **the held-out set (`wild-v1`)**. The
> section is kept as written.

## What is frozen

The `tribunal/`, `prompts/` and `policy/` trees at the tag `freeze-2026-09-30`.

| file | sha256 |
|---|---|
| `prompts/v1/judge.system.md` | `73961ae5d750c8e4ecbb9feb1ab456ae6e3994c6c4600ccdd008d2bcf3db86a9` |
| `prompts/v1/advocate.system.md` | `15cd5aadb90794f86c8f214afd42e4f9b616a2112ff583e6beb4693bbe352570` |
| `prompts/v1/stance.driver.md` | `7e0cb843437408155e75ac41fbcbebbfb3650dc742d6828465cc2d718610cb22` |
| `prompts/v1/stance.rider.md` | `4b626f29ededa14526d766286565dafdf22933763db322bec6a024a8a20444d6` |
| `policy/general.json` | `12d64aa3de9878e3a99e5d9e39e4bdf251d4a82cd8f577993812278a57ea14bf` |
| `policy/no_show.json` | `7e80df8f3084eb1ae8c4b8b3724096e36bb3491bb5ab154af5d626ff009daadf` |
| `policy/route_deviation.json` | `628b503c0da63937f95a7e18e51bf1579972cdf590122d34150f4953d6e32b9d` |

`prompts/v1/` also holds `README.md`, `policy_drafter.system.md` and
`verifier.system.md`; those three are not part of the frozen judge path (the
drafter belongs to the policy-gap loop and the verifier is off), and the tag
freezes the whole tree regardless.

**The owner makes the sealed run only if this holds:**

    git diff --quiet freeze-2026-09-30 -- tribunal prompts policy

A non-empty diff means the code that would be measured is not the code that was
frozen, and the run is not the frozen run. The run's own `run.json` records its
commit and whether the working tree was clean, so the check is made twice — once
by hand before the run and once by the record the run leaves behind.

> **Correction, 2026-09-30, later the same day.** "The sealed run" is the single
> run of `wild-v1`, now called **the held-out set (`wild-v1`)**. The paragraph
> above is kept as written.

## The configuration

| switch | value |
|---|---|
| model | `deepseek/deepseek-flash` |
| judge votes | 4 |
| verifier (`--verify-drafts`) | off |
| precedents (`--precedents`) | off |
| ablation (`--ablate`) | none |
| policy version | 1 |
| `--timeout` | 900 |
| `--concurrency` | 2 |
| case deadline | the default, `pipeline.DEFAULT_CASE_DEADLINE_SECONDS` = 2400 s |

The judge is asked four times per case — three sampled drafts and one
position-swapped — and the four graded fields are voted together at a quorum of
three. Every one of the switches that would change what the agents are given is
off, so the run measures the pipeline and the brief as committed.

## The protocol

- **The run is one command.** A case that fails is retried **with the same
  command** until every case has a result. A failure here means `TRANSPORT`,
  `TIMEOUT`, `DEADLINE` or `SHAPE`.
- **A case that has a result is never re-run**, and `--force` is refused for
  this set **in code** rather than by convention (added with the set's import).
- **The results are committed exactly as produced and graded once.**
- **The key is never changed after the run.** A disagreement with the key is
  recorded, not corrected. `eval/answers/wild/ground_truth.json` is frozen from
  the moment it is imported, under the standing rule in `START-HERE.md`.
- **The run reports**: the four-field exact score and each field alone;
  escalation precision and recall; and the score per category.
- **This is the submission's only generalisation figure.** It is reported beside
  the development figures — the 29-case corpus and the fifteen-case second set —
  and is **never summed with them**. One figure over 64 cases plus another over
  44 is not a measurement of 108 cases.

## A known defect, left as it is

`prompts/v1/judge.system.md` calls the referee's output `referee_ledger` and
`referee_flags`, while the message it is answering carries `referee.ledger` and
`referee.flags` (recorded in `docs/notes/2026-09-28-provenance-currency-and-three-defects.md`).

**The development figures were produced under this wording, and it is not
changed.** Correcting it now would mean the sealed run measured a prompt no
development run has ever measured, which is the one thing the freeze exists to
prevent. The defect is recorded here so that it is a known property of the
frozen system rather than a discovery made afterwards.

> **Correction, 2026-09-30, later the same day.** "The sealed run" is the single
> run of `wild-v1`, now called **the held-out set (`wild-v1`)**. The paragraph
> above is kept as written.

## The provenance the set's author stated

As she stated it on 2026-09-29 and 2026-09-30:

- She did not read this repository's case files.
- Her generator is not derived from this repository's.
- The answers are in a separate file and give all four graded fields.
- The archive's `eval/wild/MANIFEST.json` says:
  - 64 cases were derived from real complaints;
  - `gen/validate.py` passes;
  - `gen/semcheck.py` independently re-derives 61 of the 64 rulings, and the
    three differences — **502, 515 and 520** — are explained there.

These are the author's statements, recorded as stated. This repository has not
verified them and cannot: verifying the generator would mean reading it against
its cases, which is the reading the sealed set exists to keep out of the
development process.

> **Correction, 2026-09-30, later the same day.** "The sealed set" in this
> paragraph means `wild-v1`, now called **the held-out set (`wild-v1`)**. The
> paragraph above is kept as written.

## What the owner's structure-only check found

Reading **no case content and no answer** — structure and counts only:

- The archive's sha256 is
  `73440528584f78149f5e977b02dd17183070d2686a72ccfc6061337e6c1b6e65`.
- There are **64** case files, numbered **501 to 627**: **37
  `ROUTE_DEVIATION`** and **27 `NO_SHOW_CHARGE`**. (64 cases over a 127-wide
  number range, so the numbering is not contiguous and the count is not the
  range.)
- The cases use schema **1.2.0**, carry **7 artifacts** each, and put
  `accuracy_m` on every GPS point.
- There is **no answer field in any case file**.
- `brief.build_brief_for_case` builds all 64.
- `en/` holds **84** English source seeds, of which **62** were used. `en/` is
  answer-bearing and is not imported.

## What this note does not do

It does not import the set. The import — the file map, the digests of every
imported file, the `wild` registration in `eval/development_sets.py`, and the
guards — follows in a later commit, after this note is committed and the tag is
pushed. Until the sealed run is committed, no case content and no answer value
is printed, quoted or summarised anywhere in this repository.

> **Correction, 2026-09-30, later the same day.** "The sealed run" is the single
> run of `wild-v1`, now called **the held-out set (`wild-v1`)**. The paragraph
> above is kept as written.

---

## The import, recorded (added after the tag)

**2026-09-30, after `freeze-2026-09-30` was pushed.** The section above says what
this note did not do at the moment it was committed. This one records what was
done afterwards, in the commits that follow it under that tag. It is the record
the last paragraph above promised.

**Still no case content and no answer value.** Structure, counts and digests
only, until the sealed run is committed.

> **Correction, 2026-09-30, later the same day.** "The sealed run" is the single
> run of `wild-v1`, now called **the held-out set (`wild-v1`)**. The paragraph
> above is kept as written.

### Where the files went

Mirroring the second development set's layout exactly:

| archive path | repository path | files |
|---|---|---|
| `data/wild/cases/case-*.json` | `data/external/wild/case-*.json` (flat) | 64 |
| `data/wild/index.json` | `data/external/wild/index.json` | 1 |
| `eval/wild/ground_truth.json` | `eval/answers/wild/ground_truth.json` | 1 |
| `README.md` | `eval/external/wild/README.md` | 1 |
| `eval/wild/MANIFEST.json` | `eval/external/wild/MANIFEST.json` | 1 |
| `eval/wild/seed_map.json` | `eval/external/wild/seed_map.json` | 1 |
| `eval/wild/eval_index.json` | `eval/external/wild/eval_index.json` | 1 |
| `eval/wild/summary.csv` | `eval/external/wild/summary.csv` | 1 |
| `gen/` | `eval/external/wild/gen/` | 9 |
| `en/` | **not imported** | 3 left behind |

**80 files imported.** `data/external/wild/` holds 65 of them — the 64 cases and
the index — `eval/answers/wild/` holds one, and `eval/external/wild/` holds
fourteen.

The three destinations sit on two sides of the boundary `WORKBUDDY-SCOPE.md`
draws. `data/external/wild/` is agent-visible and answer-free, under the contract
`data/cases/` and `data/external/codex/` are under. `eval/answers/wild/` and
`eval/external/wild/` are answer-bearing: nothing under `tribunal/` may read
either, and the second holds the set's own generator, its manifest and its
author's README.

### The set's own README calls this set a development set, not the sealed set

**This conflicts with the premise of this task, and it is recorded rather than
resolved.** `eval/external/wild/README.md` — the archive's own `README.md`,
copied byte for byte — says, in its own words, that the **sealed set is a
different set of 24 cases**, and that the 64 cases in this archive are a
**development and regression set**. It says the sealed set is the one run once
after the freeze, while *this* set is for development: it can be run repeatedly,
its answers can be read, and its prompts can be tuned on the cases it misses. It
says the same thing twice more — in a section heading, and in a reporting note
about a case type "the sealed set does not have".

Three things follow, and each is stated rather than acted on:

- **The import is what the task specifies.** Part 2's table names this archive
  and these destinations, and the task calls the result the sealed set. Nothing
  was changed on the strength of the README: the files are where the task puts
  them, and the `wild` registration describes the set the way the task asks it
  to.
- **The README's statement is not reconciled here.** It may be that the README
  is stale — written when the plan had a 24-case sealed set, and not revised
  when a 64-case set was delivered for that role — or it may be that this
  archive is not the set the task means. This repository cannot tell those two
  apart, and guessing would be worse than recording.
- **The generalisation claim depends on which it is.** If this is the set the
  README describes, then it is a set its author expected to be read and iterated
  on, and a single run over it is not the generalisation figure this note and
  `eval/development_sets.py` call it. The owner should settle this before the
  run, and before any figure from it is reported as generalisation.

The README is answer-bearing at case level: it names cases and the outcome the
policy gives for them. Nothing from it is quoted or summarised here.

> **Correction, 2026-09-30, later the same day.** Two things in this section have
> since changed, and the section above is kept as written.
>
> - **The name.** The task that produced this note called this archive "the sealed
>   set". The repository now calls it **the held-out set (`wild-v1`)**: 64 cases
>   derived from real complaints, prepared by their author as a development set,
>   which nobody who changed the system opened before the freeze tagged
>   `freeze-2026-09-30` and which was run once from that tag. "The sealed set" in
>   the section above therefore means `wild-v1` wherever the task's own naming is
>   being reported, and the author's **24-case** set wherever her README is being
>   reported. The distinction the section draws — her README names a different,
>   24-case set as the sealed one — stands either way, and the conflict is still
>   the owner's to settle.
> - **The language.** `eval/external/wild/README.md` has since been **translated
>   into English**, so it is no longer the eleventh tracked file that holds
>   Chinese. The translation says on its first line that it is a translation, and
>   the sha256 of the author's original bytes —
>   `8761344077eb9ef2a238c047a18b71b0f6b8f1855d1baeb63ab0ba89e1c9befb` — is
>   recorded in `docs/notes/2026-09-30-the-names-and-the-chinese-text.md`. The
>   original is recoverable byte for byte from `3cb059a`, which is why the
>   section's argument that "a translation is not that evidence" is preserved by
>   keeping the original in the repository's history rather than by keeping it in
>   the working tree.

### The digest of every imported file

All 80 files, as committed. Each hashes to the archive's own value except the
two in the next section.

| repository path | sha256 |
|---|---|
| `data/external/wild/case-00501.json` | `857ffea3d9d24db9a4d1b91b316f81ad8d9e2edc17bf3cc7f148de0523794d91` |
| `data/external/wild/case-00502.json` | `54d47988a9d30f57f0834f04172c7f979560733051d4137837d92f4635687f6f` |
| `data/external/wild/case-00503.json` | `e62333a616b99eebc08181d09b076218436841262500425e87488ce115952117` |
| `data/external/wild/case-00504.json` | `3f565abf8b3671715017b590fe7ea009071978af5fb406e0004f3c2dac1dba55` |
| `data/external/wild/case-00505.json` | `5083dbbf792462845c4cf493853812dd6c50d4484d19bccbbda7e0e3c0bf92cb` |
| `data/external/wild/case-00506.json` | `c347d0107edbbf749ab606c0731a7141e4d756fbfb3854c8bb3bb11d22fb53c3` |
| `data/external/wild/case-00507.json` | `57cadeadf905e5b8cd9c9f5596b00a38e32b97daeb8403947a8ef88903c1e6aa` |
| `data/external/wild/case-00508.json` | `b0a1c809fa99f8b33cc391346a38fc8058b9e08c6d61963c0e442e786c34700d` |
| `data/external/wild/case-00509.json` | `d8e882c6b4cb920cb38d380787309b38657d6404162a3f650b598c253b17d90f` |
| `data/external/wild/case-00510.json` | `97dd0de60843ee16c3c35f0785456e48110e480a0817492ee75001a17791f2a6` |
| `data/external/wild/case-00511.json` | `fc41363374fbae2214a0d361db9e7546a2633d479ae50693fc15f2c177c61ea2` |
| `data/external/wild/case-00512.json` | `983c63687788e7f227788e47802b14a5c41baa429bc9fd855dcdece5cb1c049b` |
| `data/external/wild/case-00513.json` | `f1d8877356c94b8ed4acb827c387cbccb93cee610f1c23ad779811bbf29b978c` |
| `data/external/wild/case-00514.json` | `5b0b058cca4063e0fc023dd8eeb522c44cdac806f30cb2b6d0322e6a756c6f4c` |
| `data/external/wild/case-00515.json` | `568ab2c5bf5be2ff08229467d4fe809156e829bbb1ff0faaf1916a818fda2177` |
| `data/external/wild/case-00516.json` | `2384069dc94112e2dd1eecce6604f951f9f028543caa34f0505871af43f8bad9` |
| `data/external/wild/case-00517.json` | `4804604c32607251be7b917383f3e3061197debd35ee4e301a66fd44274ad75b` |
| `data/external/wild/case-00518.json` | `4e431399dddc023fb67f806bb9cc0858d3184a3cf97bdc430d18af13c58ff5ca` |
| `data/external/wild/case-00519.json` | `b31896048fc6574468669356ce06973b9e0409e464d472e44c85c7d03f0f1180` |
| `data/external/wild/case-00520.json` | `f5f614c64b7a4515ffc90f7d14621f3a1ddfd6b330140b645666f9533fea7285` |
| `data/external/wild/case-00521.json` | `d8b7a781d98c3ab6f06181b198b608efa9db83f87059be5e2b374df95302e525` |
| `data/external/wild/case-00522.json` | `0020d2489e0f5c872b3502d916d98012d01c3d318321209264d9e991d202b713` |
| `data/external/wild/case-00523.json` | `85a7a26bc033e89b8842e6efe6e1a2996da22fa869bdc3b653cbf660ffa338b2` |
| `data/external/wild/case-00524.json` | `d2d72ea2afc0d600f4f7fe7653681043f3dd923ef6f3697b70ccce84587e705f` |
| `data/external/wild/case-00525.json` | `2d25a163536d53f067d62225d1be6c317a13a5209c24a7211380e2826f17cacc` |
| `data/external/wild/case-00526.json` | `5c6ec5650491d6d686034424688239e1032f01032a39cfce4313d83c0fe2e702` |
| `data/external/wild/case-00527.json` | `376806f34161081322a2e7076926b79b3839270e758591667c86243631fc1c24` |
| `data/external/wild/case-00528.json` | `98af894692677b9c1f3382d0a1f0ff55af50157e0727d18a7c6b12669a8633f9` |
| `data/external/wild/case-00529.json` | `5ce2cbad66ae2e7c871c1f1a601bd6b30e478049374daa8be0bf2971c74d841b` |
| `data/external/wild/case-00530.json` | `6a7970d9374186104bcbb81bad02c93c5f9caf3011bd40702e309ed24c628947` |
| `data/external/wild/case-00531.json` | `112c4e5e123fea9b3c8558f4d3bd06a4f95d24c4b96c66840b5351d3d8f59531` |
| `data/external/wild/case-00532.json` | `66f3ae4d661b068058b5ad09d706713cfe2416e6db850c4f11462d64166e99b0` |
| `data/external/wild/case-00533.json` | `96448cfe36ea8e30862a1c9bdcf4b7bd683fa2dbda59bc00bf49dd95ed7175d8` |
| `data/external/wild/case-00534.json` | `0bf615290ee893f9884892ba382bfdecb1236783ff4465ffc40f539316ad934c` |
| `data/external/wild/case-00535.json` | `32f26914a3c4a93ec7d757d805418b3afa2c50b1c6b7baf115dd44659f544c75` |
| `data/external/wild/case-00536.json` | `2305d29801ac9e62d12db37a4a9f6ee5ec573ca50cc4c74cabed4ea4042efe58` |
| `data/external/wild/case-00537.json` | `2df7ddcb9c6cf64c9917dd6dea2db2a0a153730ee41c5f1b0d87259cc4886d26` |
| `data/external/wild/case-00601.json` | `a1d1a44faa4ce47b5ac86b08dc65e85d3424cf76271c18cb23e0e6a72b28d9b8` |
| `data/external/wild/case-00602.json` | `acd4acadd928294ca3fa6b6d0839feee3a613c54fd73b83caf13727da675f80b` |
| `data/external/wild/case-00603.json` | `519d6bc397d7a532ebddfa2c6e56ef21f869548433cbf8417bbca13c9fc1de99` |
| `data/external/wild/case-00604.json` | `536a982f56135a08624566710411cac2f8cd0c94b224ddf4a5e28d64bead6203` |
| `data/external/wild/case-00605.json` | `e1812f66191995096c2dfd926989f212f8c9dde09502a59d7247750238f616a7` |
| `data/external/wild/case-00606.json` | `ed646bce191851d23783b3ca7813d9d80897c6f8b5caa5796cd58b318eb48e1a` |
| `data/external/wild/case-00607.json` | `312494991ce6a0f1d0373b869cd8779d5ae7e618c3888bbaa173b2869fbe32d3` |
| `data/external/wild/case-00608.json` | `889861f27106935e7264ac9c1f9060ae1bd9d00adf2f024bb8bcc7762877c606` |
| `data/external/wild/case-00609.json` | `632eab557476243d32b25d2147d2c962c15e1dcf731be97104a7a1c4325bac41` |
| `data/external/wild/case-00610.json` | `a33d1c1a7c694b802cb533d81cd934ff3616571731ece4008f4af7c8acec988a` |
| `data/external/wild/case-00611.json` | `7c3f2e47af17f584dcc8637030f13dd54584bdf86abc0e1972edc0b09295cdc8` |
| `data/external/wild/case-00612.json` | `84cad2eb86ddfb94bd49701dc7bc32f1c63ba0c8a38bfc634f5d0cbaef2c25dd` |
| `data/external/wild/case-00613.json` | `f6b5138e1f2fd21425d42e41d2f05d369a92b6702b78d13e98a258bc6b243726` |
| `data/external/wild/case-00614.json` | `9ae8bc3270fecc7a90847d66a9672303bbc915326a20c4f816e1b1745f309632` |
| `data/external/wild/case-00615.json` | `b76cbd10baadc0c13febbabc81f151158cf0dbd38334baf22a79575046189a70` |
| `data/external/wild/case-00616.json` | `8df7815323351df493ca6e722a25d4e3ef2ca57f003f27091307f4817a719b95` |
| `data/external/wild/case-00617.json` | `6833a49d51a4e69b545f3b495ce51022124ace73613d517a1d1ea26d701626b9` |
| `data/external/wild/case-00618.json` | `f565aec9f4a0e93c71bd7b08c0a7dfc77a4afb44d822114bd0f2fec2cf656c8e` |
| `data/external/wild/case-00619.json` | `559b3cb6b161dce85ca4f2cd8b3d0c0b310c3e4b468a0e4f368a20a1e86da428` |
| `data/external/wild/case-00620.json` | `06e030ca06552c0d1ff48f47f09a613d34a25fd2ebee9d38c844ccbd7fac5ec7` |
| `data/external/wild/case-00621.json` | `7b83fe3e35333badad80e1471b6c4ba5219b37b849d9556089835ca44655b631` |
| `data/external/wild/case-00622.json` | `1488c8b7007ae8ad0fed5934f820fbae5e8cd1fffe1862135fea677c02c94bd3` |
| `data/external/wild/case-00623.json` | `cd3deb8e50329447ed33332dd6846dcae625ea67d0a2ee93672c232bdd2b8d23` |
| `data/external/wild/case-00624.json` | `681b28a5f3f3e3066fa8f91e7a4305a18faf2783f503cbdc7a28a28d44b7585d` |
| `data/external/wild/case-00625.json` | `54cb0ed67bd640c16cafb94bc36e85b16ee915d794e977e4555b1deb0333fac2` |
| `data/external/wild/case-00626.json` | `d4790ac1df54a1aa0783c903bc7892abd9198cc910d65528e6b84d39074ec26b` |
| `data/external/wild/case-00627.json` | `7725c67ad632d07708d89c92f0ff32644d68c229a53133f5f10db4b7272192f7` |
| `data/external/wild/index.json` | `852fa3f93265c0005ea05e07125c5cedc77dbd6b23b40d27659411c75a64b246` |
| `eval/answers/wild/ground_truth.json` | `1bbe020c68325f92f92e43a1ec3093e6e297d3fff9703d7dbb29e20d5722b234` |
| `eval/external/wild/README.md` | `8761344077eb9ef2a238c047a18b71b0f6b8f1855d1baeb63ab0ba89e1c9befb` |
| `eval/external/wild/MANIFEST.json` | `58dda6674b9db876472483cf905bf7afff97f7d8a0e36f72376c98ba9a187394` |
| `eval/external/wild/seed_map.json` | `4ca2486545933a36551d83b23452cff1356a2156d101c540d72397348b891393` |
| `eval/external/wild/eval_index.json` | `034f5e57e2a8469d3591a0c2ed98015a69c8248ea3b02cad46e190cf1a7f7031` |
| `eval/external/wild/summary.csv` | `118091ec9d60ce29317125be82c45cbfb25d90aedf3265288c4aafbc64817657` |
| `eval/external/wild/gen/build.py` | `5d7c99d5097aa72dbeff66b258bd8f2942946625d1b99fe1b13692c939943617` |
| `eval/external/wild/gen/core.py` | `0793379e73091aba1093bd1b034744fa569e632cad0feaedfb06d0a4af0d8ae4` |
| `eval/external/wild/gen/places.py` | `ab0eab77710364a50315be0229ab946abc11b3903cd0d0082724de838b89dc77` |
| `eval/external/wild/gen/semcheck.py` | `a7129f1b96b1571627391e5c31fd35cfffc227512eae1d9ac88c609abb3d32f3` |
| `eval/external/wild/gen/specs_bill.py` | `0be3f1eb78ea1d28bebc37633b080082fe8691d00b390042eadb7bf07884cd02` |
| `eval/external/wild/gen/specs_ns.py` | `9dac8c7c60413e8fbcbf300167dfb9fcb02c4f71818632749353764a29666360` |
| `eval/external/wild/gen/specs_rd.py` | `1379145acdd867cc4be0ba059ccabdb63c301910aca2fc21601c25bf4b4e2cce` |
| `eval/external/wild/gen/validate.py` | `e0c0bd0a62a5e8f0ffe967f4229a559589ea45fadf22a12057f94cdc34dd0982` |
| `eval/external/wild/gen/wild.py` | `ddb25683e4c1ce5ac4c037ef980415ce52373b93c20f1aee21819f72ae88ccc5` |

### The two files that are not byte-identical to the archive

The rule is to copy bytes exactly and re-serialise nothing. Two files could not
be copied as they were, and both are the archive's own content re-serialised
rather than changed. Neither alters a case, a ruling or an answer.

- **`data/external/wild/index.json`.** Every entry of the archive's index carries
  `"file": "cases/case-00501.json"`. The cases are imported flat, as the second
  development set's are, so that path resolves to nothing and
  `loader.load_external_set_case` refuses every case of the set. The `file` field
  of all 64 entries is rewritten to `case-<NNNNN>.json`; every other field of
  every entry is unchanged.
  - archive `8c41144f419e48eb1243d0ed5b4f60967eb0eb952f7fb90b9432e2ad6fda136c`
  - committed `852fa3f93265c0005ea05e07125c5cedc77dbd6b23b40d27659411c75a64b246`
  - This is the same correction the second development set's index needed, made
    in a commit of its own (`2b20acd`).
- **`eval/answers/wild/ground_truth.json`.** The archive's key is a JSON
  **object** keyed by case number. `eval.grade.load_answer_key` requires a JSON
  **array** of records each carrying a `ground_truth` object, so the archive's
  file raises `GradeError` on the grader that has to read it — and the structure
  check this task asks for cannot be met without a change. It is re-wrapped into
  `[{case_no, dispute_id, ground_truth}, ...]`, each `ground_truth` object
  carried across unchanged: no number literal is dropped, rounded or invented,
  and all 64 records carry all four graded fields.
  - archive `d8037d23e5aab93ba90e8cc28644ec2fb48a6661c1c43979dc12589f86e3ffde`
  - committed `1bbe020c68325f92f92e43a1ec3093e6e297d3fff9703d7dbb29e20d5722b234`

The other 78 imported files are byte-for-byte the archive's, checked by hashing
both sides.

### The two digests the archive's MANIFEST states

`eval/external/wild/MANIFEST.json` states two digests of its own content. **Both
reproduce exactly, and by an obvious method:**

| MANIFEST field | value | the method | reproduces |
|---|---|---|---|
| `case_set_sha256` | `77bc2dbb603393a4eea252136a0936623854cc42a05b445ab34466a019188bea` | sha256 over the 64 case files' bytes concatenated in file-name order, `case-00501.json` first and `case-00627.json` last | yes |
| `answer_key_sha256` | `d8037d23e5aab93ba90e8cc28644ec2fb48a6661c1c43979dc12589f86e3ffde` | sha256 over the bytes of the archive's own `eval/wild/ground_truth.json` | yes |

The second is the digest of the key **as the archive holds it**, so it does not
match the committed key, which is the re-wrapped one at `1bbe020c…` recorded
above. That is expected rather than a discrepancy: a digest of a file cannot
survive that file being re-serialised, which is why every run records the digest
of the key it actually read.

The MANIFEST's other fields are the set's name, its case count, and counts of
categories, rulings and difficulty levels. Those are counts, and they are not
repeated here.

### `en/` is not imported

The three files under `en/` are not imported. These digests are all that is
recorded about them in this section:

| archive path | sha256 |
|---|---|
| `en/CASES.md` | `e19b2e85e0cb84f1c4bdb7923285aa47a18d619d21483225293e1f40b433bf44` |
| `en/cases.jsonl` | `957b0a2029707481520c94a4cf77c72d18dcd53ecb4c89f02264ef657dcabd8c` |
| `en/index.csv` | `65e2b60135b2c1b18f1ba0508c63b579791137c4c4a858b277b3f9d5e7b21ad4` |

### The one conflict with the standing language rule

The archive's `README.md` is written in **Chinese** — 992 Han characters
(U+4E00–U+9FFF) and 36 CJK punctuation marks, 1028 code points outside ASCII in
5809 bytes — and it is imported byte for byte to `eval/external/wild/README.md`,
as this task requires. That conflicts with the standing rule in
`WORKBUDDY-SCOPE.md` (*Language rule (standing)*): "No Chinese characters in any
tracked text file."

It is imported anyway, and the conflict is recorded rather than resolved:

- this task's rule for handling the files is "copy bytes exactly and
  re-serialise nothing", and translating the author's own README would be both a
  re-serialisation and a replacement of her words with someone else's;
- the README is the evidence for the provenance statements above and for the
  conflict recorded before it, and a translation is not that evidence;
- it is not agent input, and nothing under `tribunal/` reads it.

It is therefore the eleventh tracked file that holds CJK. The other ten are one
note and nine recorded run files that quote paths containing them, listed by the
scan recorded in `docs/notes/2026-09-27-the-replays-the-icloud-move-and-the-probe.md`.
No other imported file holds a character outside ASCII.

### The registration, and the guards around the single run

The set is registered in `eval/development_sets.py` as `wild`, apart from
`DEVELOPMENT_SETS`:

- `SEALED_SET` carries `sealed=True`, and `SEALED_SETS` and `ALL_SETS` are built
  from it. `--set all` reads `DEVELOPMENT_SETS` and so never runs it, and
  `--report` prints it in a section of its own, never inside the combined
  figure. Its runs go to `runs/wild/<model-slug>/`, and it is graded against
  `eval/answers/wild/ground_truth.json` through its own loader.
- `run_benchmark.headline_run_directories` is the one place the reported run
  directories are named, and it now includes `runs/wild/<model-slug>/`. The
  ablation, precedents, policy-version, baselines, policy-gap and
  recorded-drafts destinations all refuse it, because all six read that one
  function rather than keeping a list each.
- `assert_not_sealed` refuses `--force`, `--replay-advocates`, `--replay-check`
  and `--verify-recorded-drafts` for this set, and for no other. `--force` is
  refused inside `run_set`, so a case that has a result cannot be re-run; the
  other three are refused while the command line is read.
- `tests/test_sealed_set.py` holds the registration, the report, the four switch
  refusals and the six headline-directory refusals — each shown on a dirty
  fixture first, with the fixture compared byte for byte afterwards — plus the
  structure checks: all 64 cases load through the set's own loader, all 64
  briefs build, and the key loads through `eval.grade.load_answer_key` with 64
  records each carrying all four graded fields. Counts and keys only, never a
  value.
- `tests/test_answer_isolation.py` gains a sealed-set section beside the corpus
  and second-set ones: no answer field in any of the 64 case files, no brief
  carrying an answer-key field name, no module under `tribunal/` naming either
  `eval/answers/wild` or `eval/external/wild`, and a falsifiability check that
  goes red on a spliced case.

### The command the owner will run

    python3 -m eval.development_sets --set wild --concurrency 2 --timeout 900

The flags are this task's and they are the ones this command line takes: `--set
wild` is accepted, and `--concurrency` and `--timeout` are both arguments of it.
A case that fails is retried with the same command, as the protocol above says.
`--force` cannot be added to it: it is refused for this set in code.
