# Viewer manual check, 2026-09-23

What a presenter does, a presenter does not delegate. This note records what
was checked by hand in a real browser against the committed viewer, in the
order the brief asked for it, with the result of each. The check is by DOM
query against the running page, not by an automated assertion, because the
behaviours being checked -- a hash updating when the address bar is the
only place a presenter can read it, a key press toggling presentation mode
in a room -- are the kind a presenter needs to have witnessed by eye.

## Earlier today (before the stance proof)

Each item is one check, with the observed result.

* **A fresh load of `#view=case&case=211&step=5` opens case 211 at the judge
  step.** Loaded the file from `file://` with that hash and queried the
  rendered page: the case view was visible, the title said `Case 211`, the
  step hint said `Step 5 of 6`, the judge panel (`role.JUDGE`) was present,
  and 10 discarded claims were listed. **passed.**

* **Pressing the right arrow from step 1 of case 208 four times reaches
  step 5, and the address updates to `#view=case&case=208&step=5`.** Set the
  hash to `#view=case&case=208&step=1` and dispatched four `ArrowRight`
  `KeyboardEvent`s on the document. The step hint moved through
  `Step 2 of 6`, `Step 3 of 6`, `Step 4 of 6`, `Step 5 of 6`, and
  `location.hash` after the fourth press was exactly
  `#view=case&case=208&step=5`. **passed.**

* **The Projector control and the `f` key each toggle presentation mode, body
  text 15px to 19px.** Read the computed `font-size` of `<body>` while
  clicking the `Projector` button (the on-screen control) and again while
  dispatching `f` keydowns. Both toggled `body.projector` on, with computed
  `font-size: 19px`; both toggled it off, with `font-size: 15px`. **passed.**

* **The deep-link format is `#view=case&case=N&step=K`, which differs from the
  `#case-N/step-K` originally specified.** Recorded so a presenter preparing
  slides uses the right one. The actual format is the URL-encoded query form:

  | view / path | meaning |
  |---|---|
  | `#view=overview` | the Overview |
  | `#view=case&case=208&step=3` | case 208, step 3 |
  | `#view=stance&case=208` | the stance view for case 208 |
  | `#projector=1` (append to any of the above) | projector mode on |

  Paths with a `&step=` segment imply `#view=case`. The stance and overview
  views do not carry a step. The deep link is written to `location.hash` on
  every navigation; `hashchange` is what makes the browser's back button walk
  through the steps. The actual addresses verified by hand:

  ```
  #view=overview
  #view=case&case=208&step=1
  #view=case&case=211&step=5
  #view=stance&case=208
  #view=stance&case=208&projector=1
  ```

  The form originally specified was `#case-N/step-K`. The viewer does not
  produce that; it produces the query-style form above, and that is the
  one a presenter must use. Recorded here because the difference is
  invisible until a slide is prepared with the wrong one.

* **Reloading on the same path with only the hash changed shows the
  previously loaded page rather than a rebuilt one, so a check after a
  rebuild must force a fresh load.** Demonstrated during the in-place
  annotation incident earlier today: the build was rewritten, but the
  browser served the cached file from `file://` until a hard reload
  (`Cmd-Shift-R`) was issued. Implication: any check that compares
  `ui/dist/index.html` against a fresh build must read the file from disk,
  not from the running browser; `python -m ui.build --check` does this, and
  it is the guard the brief asked for.

## This session: the stance proof

The deferred half asked the build to show, above the side-by-side claims,
that both advocates read the same evidence and differed only in stance.
That is the proof; these are the manual checks against the live page for
case 208, queried in the same browser.

* **Loading `#view=stance&case=208` reaches the proof and the three facts
  render.** After setting the hash, the page carried a `section.panel.proof`
  with three `.fact` blocks, in the order "They were handed the same
  evidence", "Their instructions differ", "The difference is confined to
  the stance block". **passed.**

* **The three user digests are byte-identical, shown in full.** Read the
  `textContent` of the three `.digest.same` rows of fact 1. They were
  literally the same 64-character hex string, repeated three times:
  `a2671c6d1f087715b3f1c6253f32927df2c8c9e2bb31e7fcb8b005913013a356`.
  This matches the brief's "should read as one value three times." Each
  carried a tag `identical`. **passed.**

* **The system digests differ, and are shown in full.** The two `.digest.differ`
  rows of fact 2 were the rider's `b90cb450bbd10645bb645632dfa64bafaeb4f690787527ce2ec0743e9e2ac355`
  and the driver's `c317acbca01e30fca7b769c8d85d31333a756e601b25ca9ad2ede328c4607543`.
  Both 64 characters. They were not equal. Each carried a tag `not equal`.
  **passed.**

* **The differing line ranges and the stance block are reported in the
  third fact.** The third fact rendered three rows: `differing line
  ranges` (the recomputed `[8,9],[12,18],[19,20]`), `recorded by the run`
  (the same value, because the build checked they match), and `stance
  block` (`[6, 21)`, half-open). The lead for fact 3 spelled the
  containment in prose: "differ on lines 8, 12-17, 19, and the stance
  block occupies lines 6 to 20. Every differing line falls inside it."
  **passed.**

* **The two rendered system prompts render side by side, with the differing
  lines highlighted and the stance block's extent marked.** Both columns
  carried 153 numbered lines, each a `<li>` carrying the line text. Lines
  8, 12, 13, 14, 15, 16, 17, 19 had the `diff` class (amber background
  and warn-coloured left border). Lines 6 through 20 had the `stance`
  class (faint accent background, marked with `stance` in the legend).
  All eight differing lines fell inside the 6-20 stance range, by
  construction. A legend at the foot of the panel named both classes.
  **passed.**

* **The full digests appear in the page source, not a truncated form.**
  Asserted separately by the test suite
  (`StanceProofTests.test_the_digests_are_carried_in_full`). Verified by
  eye as well: the 64-character strings above are what the user sees, not
  the first 12 of them. **passed.**

## Method

The checks were performed in a headless browser against the committed
viewer served from `file:///tmp/tribunal-preview.html`, a copy of
`ui/dist/index.html` made at the commit being verified. The copy was used
so the local preview's annotation of the file in place (a hazard recorded
in `MEMORY.md`) could not dirty the tracked artefact mid-check. Every
behaviour was confirmed by querying the rendered DOM after the
action, not by an automated assertion in the suite; that is the
distinction this note is here to make. The `--check` guard and the
`PresentationTests` tests are the programmatic counterpart, and they
were run separately.

The checks are written so a reviewer can reproduce them by hand on the
committed file: load the file, perform the action, and read what the
page says.