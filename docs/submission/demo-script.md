# A three-minute live demo

Five steps, three minutes, on the published site. Each step says what to open
and what to say. The site is at <https://tribunal.edgeone.dev/> and every page
below is also committed under `ui/dist/`, so it also runs locally with
`python3 -m http.server --directory ui/dist`.

Every page in this walk is a **version-8** page. The version-6 material is named
as such where it appears. The try-it page is not in the walk, because it runs
version 6, and the version-6 facts it works out in the browser include the
rider's phone 634-646 m from the pickup point.

## 1. The front page -- 20 s

Open `index.html`.

Say: "Tribunal applies Ryde's own Dispute Resolution Policy v2.1, with Ryde's
answers of 2026-10-14 -- policy version 8. Over the 40 cases of `dev-v8`, which
is development data, a decision takes a median of 153.1 s a case, at a median
model cost of 0.0390 USD a case: typically under three minutes, for about four
cents. The hidden test set was run at version 7 and agrees on all four graded
fields in 30/30 = 100.0%; it was written by the team's own development
assistant."

## 2. Ryde's DISP-001, case 902 -- 40 s

Open `v8-00902.html`.

Say: "Ryde's own route-deviation sample. The trip ran 24.8 km against 20.5 km
recommended -- 4.30 km over, and over the 2 km an AI may rule on, so version 8
sends it to a person before the judge is asked, exactly as Ryde answered on
2026-10-14. The code worked out the excess distance fare at SGD 3.44: 4.30 km
at the 0.80 per-km rate, with no surge."

## 3. A no-show the evidence settles, case 5051 -- 50 s

Open `v8-05051.html`.

Say: "Here the evidence settles it. The free wait is 300 s and the driver
cancelled 45 s past it, and the trace agrees.
Case 5051: 3 points for the rider, 8 for the driver.
Case 5051: 1 of 11 points thrown out by code before the judge saw them.
The four drafts agreed on all four graded fields at a confidence of 0.95, and
the fee stands: the driver paid SGD 5.00."

## 4. Ryde's DISP-002, case 903 -- 40 s

Open `v8-00903.html`.

Say: "Ryde's own no-show sample, and the one place we differ. The rider carries
a fraud flag, so Tribunal's version-8 policy asks for a confidence of 0.95 --
its reading C15 of v2.1 6.3. Eight sparse GPS fixes do not get there. Two drafts
escalated, one upheld the fee and one was voided for citing a clause version 8
does not have; three must agree. So a person decides, with the fee held. Ryde's
own outcome upholds the fee, and the question is with Ryde."

## 5. The results page -- 30 s

Open `results.html`.

Say: "The version-8 section first: `dev-v8` 39/40 and `dev-v7` 40/40
(development data); 28 of 40 ruled by the AI, the rest sent to a person; in 33
of 34 cases the draft written with the sides swapped agreed with the panel; and
Expected calibration error 0.097 over 139 drafts, at the version-8 bar of 0.80.
Then the version-7 section: `sealed-v4` agrees on all four graded fields in
30/30 = 100.0% on 30 hidden cases, Wilson 95% [88.6%, 100.0%], written by the
team's own development assistant and run once from `freeze-2026-10-14`."

## Three questions, one sentence each

- **Why is the sealed figure at version 7?** A sealed set is run once, and
  version 8 changes its key on one case, 6009, at a deviation of 2.4 km, which
  version 8's 2 km gate escalates before the judge is asked.
- **Why does 903 escalate?** Tribunal's reading C15 of v2.1 6.3, put to Ryde;
  Ryde's own outcome upholds the fee.
- **Why no fare disputes?** Scope: this prototype covers the two categories the
  brief asks for, route deviation and no-show, and leaves them out by its own
  choice.

Total: three minutes. No account and no key are needed at any step.
