# A three-minute live demo

Five steps, three minutes, on the published site. Each step says what to click
and what to say. The site is at <https://tribunal.edgeone.dev/> and every page
below is also committed under `ui/dist/`, so the demo runs offline from
`file://` as well.

## 1. The front page — 20 s

Open `index.html`.

Say: "Tribunal settles a ride-hail dispute in 2.7 min at the median, for 0.0579
USD of model cost, and 74% of cases are decided with no person needed — 112 of
151. The three tiles carry the figures: 160.4 s median time to a decision, 286.9
s at the 90th percentile, against 24 to 72 hours for a human review."

## 2. Try it — 60 s

Open `try.html`. Pick **"Case 208 · No-show"**. Press **"+ Add a threat to the
chat"**, then press **"Run the code checks"**.

The page answers with **"Safety lane: a threat in the chat puts it in front of a
person within 2 hours"**, and marks the message `THREAT-LOCATION`.

Say: "This is the repository's own Python running in the browser. No AI is
called. The first load fetches about 14 MB of Python; after that the checks take
about a second."

Then scroll to the facts the code worked out — 585 s in the pickup zone, the
rider's device never leaving the lift lobby, and SGD 6.40 to the driver — and to
the evidence pack's fingerprint.

Say: "The waiting time, the driver's share and the brief's fingerprint are
computed here, not asked of a model."

## 3. Case 1779, from the recording — 40 s

Case 1779 is **not** shown on the try page: there its in-browser checks route it
"To the AI panel", because the planted rule in its chat is caught by the judge's
citation check, and that check needs the live panel, which is off on the
published site.

Open `case-01779.html` instead, the recorded run.

Say: "All four judge drafts refused the planted clause — they said no such clause
exists — and the code check then voided those drafts, because a draft that quotes
a clause id that does not resolve may not carry the vote. So no ruling issued and
a person decides. The system refused to be talked into a rule that is not there."

## 4. Case 208, end to end — 40 s

Open `case-00208.html`.

Say: "Here is a decided case. The six steps run down the page — evidence pack,
both sides argue, citation check, judge, floor and triggers, outcome — and each
one opens down to the agents' own words."

Then point at the **Notice to the rider and the driver**, and at the **Appeal**
line beneath it.

Say: "Both parties get the same notice in plain words, with the clause codes in
brackets, and either party may appeal once within 30 days."

## 5. Close on the limits — 20 s

Open `safety.html` and scroll to **Limitations**.

Say: "Everything here is synthetic except the organisers' own sample case. The
safety gate reads two structured flags only, so a free-text allegation is not
detected; a party can force a case out of automation with a clause id that does
not exist; and a refund can exceed the amount contested. Those are written down
on the page and in [the full record](../record.md), "Limitations and
disclosures", rather than left for a reader to find."

Total: three minutes. No account and no key are needed at any step.
