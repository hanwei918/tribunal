# Policy version 8 (2026-10-14)

Version 8 is **version 7 plus Ryde's answers of 2026-10-14**. Version 7 is Ryde's
own Dispute Resolution Policy v2.1, kept byte for byte under `policy/v7/`; version
8 keeps the same three files and applies two of the four readings version 7 had
left open, so it is a later policy on the same base and not a second one.

The three questions were put to Ryde in the track group on 2026-10-13 and answered
on 2026-10-14 at 10:49 SGT:

1. **C1 -- 6.2's 2 km limb against DISP-001.** v2.1 6.2 makes a route-deviation
   ruling an AI ruling only where the confidence is 0.80 or more **and** the
   deviation is 2 km or less, else the case is escalated; DISP-001's deviation is
   4.3 km and its stated outcome is an AI partial refund of 3.44. Asked which
   wins, Ryde answered: **"Escalate."**
2. **C2 -- where the free wait starts for a scheduled trip the driver reached
   early.** Asked where the no-show free wait starts in that case, Ryde answered:
   **"From driver arrival."**
3. **C3 -- surge on the excess distance fare.** Asked whether surge is applied to
   the excess distance fare, Ryde answered: **"No - the excess distance fare
   refund is calculated at the base per-km rate, without surge."** Version 7
   already read it that way, so answer 3 confirms C3 and changes nothing.

Version 7 held C1's 2 km limb off and started the free wait at the scheduled time
when the driver arrived early. Version 8 applies answers 1 and 2, and records
answer 3 as confirming C3.

## The edits, and nothing else

Every file was copied byte for byte from `policy/v7/` and edited only at the JSON
paths below, keeping each file's formatting and key order.

`general.json`:

- `version` -> `"8.0.0"`; `last_reviewed` -> `"2026-10-14"`.

`route_deviation.json`:

- `version` -> `"8.0.0"`; `last_reviewed` -> `"2026-10-14"`.
- `thresholds.ai_ruling_max_deviation_applied` -> `true`.
- `thresholds.ai_ruling_max_deviation_note` -> "C1, settled by Ryde on
  2026-10-14: v2.1 6.2's 2 km limb applies; a route deviation over 2 km is
  escalated (DISP-001's 4.3 km included)."
- `POL-RD-25.rule` -> "The AI ruling on a route deviation stands only where
  POL-GEN-22 allows it, its confidence is 0.80 or more, and the deviation is
  2 km or less (v2.1 6.2); otherwise the case is escalated."
- `POL-RD-25.notes` -> "v2.1 6.2. The 2 km limb was confirmed by Ryde on
  2026-10-14 (C1): DISP-001's 4.3 km deviation is escalated, not ruled."
- `POL-RD-24.notes`: the sentence beginning "C3:" becomes "C3, confirmed by Ryde
  on 2026-10-14: the excess distance fare is at the base per-km rate, without
  surge (DISP-001: 4.3 x 0.80 = 3.44)." The rest of the note stays.

`no_show.json`:

- `version` -> `"8.0.0"`; `last_reviewed` -> `"2026-10-14"`.
- `thresholds.free_wait_starts` -> "trip_record.arrived_at (C2, settled by Ryde on
  2026-10-14)".
- a new key `thresholds.free_wait_starts_from` -> `"arrived_at"`, placed right
  after `free_wait_starts`.
- `POL-NS-21.rule` -> "The driver waits a free wait time of 5 minutes (300 s) from
  the driver's arrival at the pickup; after it, the driver may cancel the trip as
  a rider no-show."
- `POL-NS-21.notes` -> "v2.1's free wait, with its start settled by Ryde on
  2026-10-14 (C2): the clock runs from the driver's arrival, scheduled trip or
  not."

Fifteen JSON paths in all: two in `general.json`, six in `no_show.json` and seven
in `route_deviation.json`. Nothing else in any of the three files changed, and
`policy/v8/amendments/README.md` is `policy/v7/amendments/README.md` byte for
byte.

## Every other reading stands

Every other reading of `docs/notes/2026-10-13-policy-v7.md` is unchanged, and
those are C4 to C18: the dispute value is the amount the filer asks back (C4); the
rows of POL-RD-24's refund matrix and the label they carry (C5); the optional
`fraud_flags` counter and the 0.95 bar it raises (C6); the optional 30-day
no-show counter (C7); the fee on the record (C8); the ruling vocabulary (C9); what
"confidence" is (C10); a verbal notice with no recording (C11); rounding to the
cent (C12); the driver-no-show deadline on an on-demand trip (C13); which trip the
repeat counter counts (C14); the fraud flag on a no-show (C15); the arrival test
and the accuracy filter's reach (C16); which distance governs a deviation (C17);
and the kinds of traffic event a reroute needs, with the types each admits and the
normalisation rule (C18). C1, C2 and C3 are the three answers above; C3's reading
was already what version 7 said, so answer 3 changed no text of its own.

The question about what "partial" and "full" refund of the excess distance fare
each pay (C5) was **not** asked in this round, so it is untouched.
