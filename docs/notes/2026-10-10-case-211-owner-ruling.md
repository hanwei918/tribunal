# Case 211: the key owner's ruling on the contested reading (2026-10-10)

`2026-10-10-what-went-wrong-at-version-6.md` records corpus case 211 as a contested reading of `POL-GEN-02(2)`, not a
policy change, and leaves it "for the key owner to rule on which reading holds". This is that ruling, by Ji Guofang as
policy and key owner. The key is not edited.

## The two readings

| | reading | outcome |
|---|---|---|
| A (the key) | the 168-second outage inside the waiting window leaves the driver's in-geofence presence across it unobserved; the chat lifts the confidence cap but cannot show where he stood | `PARTIAL_REFUND` 2.00 |
| B (three of four drafts at version 6) | `MSG-00211-004`, sent from inside the outage, bridges it, so the dwell is one continuous 500-second run | `DRIVER_COMPENSATION` 3.20 |

## The ruling: reading B is excluded; the key stands

1. **`POL-NS-01(c)` asks for a continuous in-geofence dwell "measured from the first qualifying in-geofence GPS fix".**
   Continuity inside the geofence is a fact about position. `MSG-00211-004` shows the driver still working the
   pickup; it says nothing about where he was, and the key says so in terms ("What the chat cannot show is where he
   was standing").
2. **`POL-NS-08` forbids the step reading B takes.** `EV-GPS-00211` is impaired for policy under limb (b) (a gap
   over 120 seconds inside the waiting window), and "a claim resting on an artifact impaired under (a) to (d) ... cannot
   alone support a ruling against the party it disfavours". `DRIVER_COMPENSATION` lets the fee stand against the
   rider, and its in-geofence continuity rests on the impaired trace alone.
3. **The texts are unchanged.** `POL-NS-01(c)`, `POL-NS-06`, `POL-NS-08` and `POL-GEN-02(2)` read the same at versions
   1 and 6 (the free wait resolves to 300 s either way), so the key written under version 1 still applies.

`ESCALATE` under `POL-NS-08`'s last sentence and `POL-NS-09(e)` is a stricter reading of the same facts and is not
excluded by this ruling; the frozen key's `PARTIAL_REFUND` 2.00 is within that sentence's "may not exceed
PARTIAL_REFUND", and the key is kept as written. The version-6 run's `DRIVER_COMPENSATION` 3.20 is a miss on this key.
