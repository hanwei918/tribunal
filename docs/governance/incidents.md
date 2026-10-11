# Incidents

This page records what went wrong while this system was built, how each incident
was found, what was done about it, and the file that records it. It is written
from the repository, not from memory: every entry names the note or the
directory that carries the record, and a reader can check each one.

Nothing here is reconstructed. Where a thing was lost, the record says it was
lost; where an attempt was ruled not to count, the record says who ruled and on
what ground.

## 2026-09-27 — iCloud split the event log

**What happened.** The owner turned on iCloud "Desktop & Documents" between
about 19:28 and 19:53. macOS moved the Desktop into iCloud Drive and left
`~/Desktop` resolving to the iCloud copy, while two runs were in flight — a
corpus run and a second-set (`codex`) run. Nothing in the repository changed;
what changed is which file a path resolved to.

`tribunal/events.py` does not hold the log open: `EventLog.record` reopens
`events.jsonl` **by path** on every append, which is what lets the log survive a
crash and is also what made this possible. A path that starts resolving to a
different file part-way through a run splits the log with no error at all. The
case **results** were not affected: `_write_text_atomic` writes each one through
a sibling `.part` file and renames it, so a result is written whole or not at
all.

**How it was found.** `python3 -m eval.events --verify` over every run
directory. One live log broke: `runs/codex/deepseek-deepseek-flash/events.jsonl`
covers `seq 0..454` and the chain first breaks at line 343 (`seq 348`), whose
`prev` names a line the file does not contain. The missing range is
**`seq 342..347`**, six lines; line 342 (`seq 341`, a `referee_decision`) hashes
correctly, and the next line claims a predecessor that is not `seq 341`'s hash.
Both lines belong to the same invocation, so the six lines were written while the
path resolved to the other copy and no later write repaired the hole.

**What was done.** The files written outside the repository were collected,
**exactly as found and not merged into the live logs**, under
`runs/_icloud-incident-2026-09-27/`, in three groups named for where each was
found (`from-desktop-subfolder/`, `from-tribunal-run/`, `from-icloud-root/`).
Merging them would put a second, contradictory line at sequence numbers the live
logs already use. The six lost lines are recorded as lost rather than
reconstructed, and four missing sequence numbers of a second probe
(`seq 79..82`) are recorded the same way. The nine tracked files under `runs/`
that carry one Han character (`U+7684`, from the macOS path the machine
recorded) were **left unedited**, because rewriting a recorded run so a scan
comes back clean would be editing the evidence.

**The file that records it.**
`docs/notes/2026-09-27-the-replays-the-icloud-move-and-the-probe.md`, with the
recovered files under `runs/_icloud-incident-2026-09-27/` and the directory's
description in `runs/README.md`.

## 2026-10-03 — the interrupted sealed attempt at 14:14

**What happened.** A probe started the `wild-v2` sealed run for real on
2026-10-03 at **14:14**, partly called cases 701 and 702, and was stopped at
**14:17:31**. Its `events.jsonl` was deleted.

**How it was found.** The attempt is recorded in the sealed-protocol note,
including the facts, the deletion and the fact that it ended with no terminal
event.

**What was done.** The owner ruled **before the run** that the attempt does not
count under the sealed protocol, because it ended with no terminal event. The
`wild-v2` set was run once afterwards, on 2026-10-04, from a commit whose
`tribunal/`, `prompts/` and `policy/` trees equal those at
`freeze-2026-10-03`; that single run is the figure the submission reports, and
the interrupted attempt is not a run in any table.

**The file that records it.**
`docs/notes/2026-10-03-the-sealed-protocol-made-executable.md`, under *The
partial run of 14:14, and the owner's decision*; restated in
`README.md`'s *About the second sealed set's provenance*.

## 2026-10-09 — `sealed-v1` opened before the freeze

**What happened.** Before the 2026-10-09 freeze, the policy owner's AI assistant
opened `sealed-v1`'s cases and key. By the policy owner's account, no policy
changed because of it. One sealed case's key and one derived fact (case 311)
reached the development side at **23:11**, after the frozen trees were committed
at **22:42** (`9ca7313`).

**How it was found.** It is disclosed in `README.md` under *Limitations and
disclosures*, from the policy owner's account. The set's own README says "run
once, k=3" and does not define `k`; the run is made once with judge votes 4, and
the agreement among the four votes is reported as k-consistency.

**What was done.** The disclosure is recorded rather than resolved. The
`sealed-v1` import itself opens no case content and no answer value: the import
note prints structure, counts and digests only, and states that no case content
and no answer value is printed, quoted or summarised anywhere in the repository
until the sealed run is committed. The set is registered at policy version 6, and
it **has since been run** — once, by the owner, on 2026-10-10, from the commit
`feb7174`, whose `tribunal/`, `prompts/` and `policy/` trees equal those at
`freeze-2026-10-09`. The run is read in
`docs/notes/2026-10-10-the-third-sealed-run.md`, and the one record the
re-derivation moved is case 311
(`docs/notes/2026-10-10-sealed-v1-key-at-version-6.md`).

**The files that record it.** `README.md` (*Limitations and disclosures*);
`docs/notes/2026-10-09-sealed-v1-imported.md`;
`docs/notes/2026-10-09-the-third-freeze.md`.

## The three base-3 amendments, approved without a gap report

**What happened.** The three amendments on the base-3 policy — `POL-NS-11`
(policy version 4), `POL-RD-14` (version 5) and `POL-NS-12` (version 6) — were
approved directly, without the `POL-GEN-07(5)` policy-gap report. Each
amendment's own `note` says so and records why its `report_file` and
`report_sha256` are null.

**How it was found.** The amendment files carry the statement in their own
`note` field, and `README.md` discloses it under *Limitations and disclosures*.

**What was done.** No report is backfilled. The disclosure is recorded as it
stands: the gap procedure was not run for these three, and the amendments are in
force regardless. A later policy change is expected to go through the procedure.

**The files that record it.** `policy/v3/amendments/0001-pol-ns-11.json`,
`0002-pol-rd-14.json` and `0003-pol-ns-12.json` (their `note` fields);
`README.md` (*Limitations and disclosures*, *Amendments without a gap report*);
`docs/notes/2026-10-09-policy-version-4.md`.

## How to report an incident

**Who to tell.** The repository owner. The owner is the one person who can rule
an attempt does not count, disclose a boundary crossing, or open a sealed root;
the disclosures above are all recorded from the owner's account, and each says
so.

**What to record.** The date and time, what happened, how it was found, and what
was done — the same five fields each entry on this page carries. Record it in a
dated note under `docs/notes/`, name the files the finding rests on, and commit
the evidence as it was found rather than merged into a live record. Where
something is not done, say so in those words: a page that says "not done" is
worth more than a page that quietly omits it.

**A policy change is never an edit of an existing clause.** The only thing in
this repository that can add to the policy is the policy-gap loop,
`eval.policy_gaps`, and it can do so only through a person: a draft under
`policy/proposals/` changes no run until someone runs `approve`, which is the
only writer of an amendments directory. An amendment **adds** one clause; it can
never edit or remove one, because the key set of the clause object is exact and
there is nowhere to write a changed field. A change to the policy therefore
means running the procedure and drafting a new amendment — never editing a
clause that is already in force. This is stated in `eval/policy_gaps.py` and in
`WORKBUDDY-SCOPE.md` (*Policy-gap loop*, *What a draft may not do*), and the
three disclosures above are exactly the case where the procedure was not run:
they are recorded, not backfilled.
