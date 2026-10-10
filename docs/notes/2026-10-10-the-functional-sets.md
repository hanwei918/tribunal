# The functional sets

**2026-10-10.** Four functional sets were imported from the policy owner's
archive (the archive's sha256 starts `f1478c09b6ff894e`), each exercising one
functional property of the version-6 system rather than its accuracy. Three are
case sets -- `inject-v1`, `pii-v1` and `collusion-v1` -- registered as
development sets written for policy base 3, run by name into
`runs/<set>/policy-v6/<model>/` and never part of `--set all` or the combined
figure. The fourth is a fixture of labelled chat messages,
`eval/fixtures/chat-signals-v1.json`. The counterparty-statement masking gap
that pii-v1 case 3202 exposed is fixed in the same change; that fix is
`docs/notes/2026-10-10-the-counterparty-mask.md`.

Nothing here changes a case file, a policy, a prompt or a key. Every figure
below is printed by `python3 -m eval.func_sets --report`, which reads the sets
and writes nothing; no model was called to produce it.

## What each set measures

**inject-v1** measures robustness, not accuracy. It is six invariance pairs:
cases 3101-3106 are clean trips and 3107-3112 are the same trips drawn from the
same random state with one adversarial instruction added to party text -- a
direct instruction in a claim, a forged platform notice in a chat message, a
forged evidence id and a clause that does not exist, a base64-encoded
instruction, and false arithmetic with zero-width characters. A case and its
twin must reach the same four fields. The check is a run: it asks a model what
it makes of the injected copy, so it is not in this report.

**pii-v1** measures what the version-6 brief does with personal data in party
text. Eight cases carry names in Chinese, Malay and Indian naming conventions,
telephone numbers with and without `+65` and with and without spaces, two
e-mail addresses at RFC 2606 reserved domains, and vehicle plates, with place
names that contain surnames as hard negatives. The check needs no model: the
version-6 brief is built and every span the key names is looked for in it. The
mask implements `POL-GEN-08(4)`'s vehicle registration marks only, so the
report finds the plate spans masked and every name, telephone number and e-mail
address still present. The gap is reported as found and is not fixed here.

**collusion-v1** measures the operations layer's risk reading over a whole case
root rather than one case at a time. Eight cases are read together: 3301-3303
are three no-show disputes between the same rider and driver, twenty-five days
apart, and the third trips `POL-NS-09(c)`; 3304 trips the `POL-NS-07`
anti-farming check and 3305 is its control under the ratio; 3306 trips
`POL-NS-09(d)` and 3307 is the lifetime-counter decoy; 3308 is a
route-deviation case whose driver carries an established `POL-RD-06` pattern.
The check needs no model: `ops/risk.py`'s `repeat_party` attention flag is held
against the set's own `cross_case.json`, and the five policy tests it reports
are held against the risk clauses the key's own ruling rests on.

**chat-signals-v1** is not a case set. It is 32 labelled chat messages, each
carrying three boolean labels (threat, agreement, disagreement) and a sentiment
label, with hard negatives beside every positive -- a complaint threat that is
not a safety threat, sarcasm that is not agreement, a location correction that
is not a dispute. The check is the label counts, recomputed from the items and
held against the counts the file itself states. No classifier exists yet: the
fixture is the labelled set one would be measured against, and nothing here
classifies a message. The routing rule it is built for is that a message
labelled `threat` sends the dispute to the safety lane; no label enters a brief.

## The report

`python3 -m eval.func_sets --report`, read-only, as printed:

```
The functional sets: the checks that need no model call
=====================================================

Policy version 6 throughout. Three case sets are read -- inject-v1, pii-v1, collusion-v1 --
plus the chat fixture at eval/fixtures/chat-signals-v1.json.

inject-v1 is the fourth functional set and is not measured here: its
check is whether an injected copy of a case reaches its clean twin's
four fields, which needs a model call and is not made.


pii-v1: personal data in party text, and the version-6 brief
-----------------------------------------------------------

For each case, every span the key says must be masked and whether the
version-6 brief still contains it, then every span it says must not be
masked and whether it survives. "STILL PRESENT" on a mask span is a
leak: the mask did not reach it. Only PLATE is masked today; the other
kinds are reported as found and are not fixed here.

  case 3201  (NO_SHOW_CHARGE)
    mask   NAME  'Tan Mei Ling'                     STILL PRESENT
    mask   PHONE '9912 3456'                        STILL PRESENT
    mask   NAME  'Mei Ling'                         STILL PRESENT
    mask   PHONE '+65 9934 1207'                    STILL PRESENT
    keep   PLACE 'Tan Tock Seng Hospital'           survives
  case 3202  (NO_SHOW_CHARGE)
    mask   NAME  'Jonathan Lim'                     STILL PRESENT
    mask   PLATE 'SZZ 4821 K'                       masked
    mask   PLATE 'SZZ 4821 K'                       masked
  case 3203  (NO_SHOW_CHARGE)
    mask   EMAIL 'priya.raghavan@example.com'       STILL PRESENT
    mask   PHONE '99785521'                         STILL PRESENT
    mask   NAME  'Muhammad Hafiz bin Rahman'        STILL PRESENT
  case 3204  (NO_SHOW_CHARGE)
    mask   NAME  'Siti'                             STILL PRESENT
    keep   PLACE 'Lim Chu Kang Road'                survives
  case 3205  (ROUTE_DEVIATION)
    mask   NAME  'Daniel Koh'                       STILL PRESENT
    mask   PHONE '9921 8804'                        STILL PRESENT
    mask   PLATE 'SZY 7302 D'                       masked
  case 3206  (ROUTE_DEVIATION)
    mask   NAME  'Kumar s/o Ramasamy'               STILL PRESENT
  case 3207  (ROUTE_DEVIATION)
    mask   NAME  'Aisyah Binte Osman'               STILL PRESENT
    mask   PHONE '9967 0042'                        STILL PRESENT
    keep   PLACE 'Jurong Point'                     survives
  case 3208  (ROUTE_DEVIATION)
    mask   EMAIL 'w.chen@example.org'               STILL PRESENT
    keep   PLACE 'AYE Alexandra Rd'                 survives

  mask spans by kind:
    NAME   8 of 8 still present, 0 masked
    PHONE  5 of 5 still present, 0 masked
    EMAIL  2 of 2 still present, 0 masked
    PLATE  0 of 3 still present, 3 masked
  do-not-mask spans by kind:
    PLACE  4 of 4 survive, 0 removed

  18 mask spans over 8 cases; 15 still present, 3 masked.
  The mask implements POL-GEN-08(4)'s vehicle registration marks only,
  so the 3 plate spans are masked and the 15 other spans are not.

  note (eval/external/ryde/DISP-002.md): The organisers' sample as supplied carries two personal names and a plate; the converted case 901 carries only the plate. A new-dispute intake that reads the original must mask both names before any brief is built.


collusion-v1: the risk layer over the root, against the key
-----------------------------------------------------------

ops/risk.py is run over the whole case root. Its repeat_party attention
flag is held against eval/answers/collusion-v1/cross_case.json, and the
five policy tests it reports are held against the key's risk clauses.
The key's expectation is read from its own governing_clauses and
expected_ruling (see expected_risk_tests).

  case 3301  NO_SHOW_CHARGE  key ruling DRIVER_COMPENSATION
    repeat_party  expected [3302]  produced [3302]  match
    risk tests    expected (none)  tripped (none)  match
  case 3302  NO_SHOW_CHARGE  key ruling DRIVER_COMPENSATION
    repeat_party  expected [3301, 3303]  produced [3301, 3303]  match
    risk tests    expected (none)  tripped (none)  match
  case 3303  NO_SHOW_CHARGE  key ruling ESCALATE
    repeat_party  expected [3302]  produced [3302]  match
    risk tests    expected POL-NS-09(c)  tripped POL-NS-09(c)  match
  case 3304  NO_SHOW_CHARGE  key ruling ESCALATE
    repeat_party  expected []  produced []  match
    risk tests    expected POL-NS-07  tripped POL-NS-07  match
  case 3305  NO_SHOW_CHARGE  key ruling DRIVER_COMPENSATION
    repeat_party  expected []  produced []  match
    risk tests    expected (none)  tripped (none)  match
  case 3306  NO_SHOW_CHARGE  key ruling ESCALATE
    repeat_party  expected []  produced []  match
    risk tests    expected POL-NS-09(d)  tripped POL-NS-09(d)  match
  case 3307  NO_SHOW_CHARGE  key ruling DRIVER_COMPENSATION
    repeat_party  expected []  produced []  match
    risk tests    expected (none)  tripped (none)  match
  case 3308  ROUTE_DEVIATION  key ruling FULL_REFUND
    repeat_party  expected []  produced []  match
    risk tests    expected POL-RD-06  tripped POL-RD-06  match

  repeat_party: 8 of 8 cases match; 0 misses, 0 extras.
  risk tests:   8 of 8 cases match; 0 misses, 0 extras.

  A risk test is a second reading of the profile counters for a reviewer
  and never a policy finding: POL-GEN-01 forbids a profile from
  establishing a fact about the trip, so nothing here rules.


chat-signals-v1: the fixture's label counts
-------------------------------------------

The fixture's counts per label. They are recomputed from the items and
held against the counts the file itself states, so a drifted file is
reported rather than copied.

  set chat-signals-v1, 32 messages

  threat        positive   6   negative  26
  agreement     positive   6   negative  26
  disagreement  positive  12   negative  20

  sentiment NEG   14
  sentiment NEU   13
  sentiment POS    5

  the file's own counts agree with the recomputation: yes

  No classifier exists yet: the fixture is the labelled set one
  would be measured against, and nothing here classifies a
  message. The label a threat carries is what routes a dispute to
  the safety lane; no label enters a brief.
```

## What the report found

**pii-v1.** Eighteen spans are marked for masking and four for keeping. The
three plate spans are masked at version 6 -- two in case 3202's counterparty
statement and chat message, one in case 3205's claim -- and all fifteen other
spans are still present: eight names, five telephone numbers and two e-mail
addresses. All four hard negatives survive, so the mask is not over-reaching
either. The set's datasheet states thirteen strings to mask and five hard
negatives; the key file holds eighteen mask spans (two of them the same plate)
and four do-not-mask spans, and the report reads the key file. Masking the
names, numbers and addresses is `POL-GEN-08(4)`'s own wording and is not done
here.

**collusion-v1.** Both readings agree with the key on all eight cases: the
`repeat_party` flag matches `cross_case.json` on every case (0 misses, 0
extras), and the five policy tests match the risk clauses the key's ruling rests
on (0 misses, 0 extras). The three cases the key escalates are the three whose
risk test trips, and the decoys -- 3305 under the anti-farming ratio, 3307 on
the lifetime counter -- trip nothing, which is the property the set was built
to check.

**chat-signals-v1.** The recomputed counts equal the file's own: 6 of 32
messages carry a threat, 6 an agreement, 12 a disagreement, and the sentiment
split is 14 negative, 13 neutral and 5 positive. There is nothing to classify
against yet.

**inject-v1.** Not measured here. Its check asks a model, and no model was
called.
