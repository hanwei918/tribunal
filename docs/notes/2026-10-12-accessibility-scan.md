# The accessibility scan of the live site: three pages in two themes, no violations

Update 2026-10-13: every built page, both themes and a 375 px window -- see 2026-10-13-accessibility-scan-all-pages.md

**2026-10-12.** The owner ran an **axe-core 4.8.2** scan of the deployed site
after part 51d was deployed, from commit `c17b821`. The scan is the evidence
behind the sentence the queue page's safeguards card and the project description
both carry: the site has light and dark themes, its tables sort and scroll from
the keyboard, and every stated text contrast is at least 4.5:1.

## How it was run

axe-core 4.8.2 was loaded into Chromium **from cdnjs**, into the page under test
rather than into the site: nothing under `ui/dist/` carries a script from
anywhere but itself, and the scan changes no published byte. `axe.run` was
called with `violations` only, at a window of **1440 x 900**.

## What was scanned

Three addresses, each in the **light** and the **dark** theme -- **six scans**:

- `/` -- the queue
- `/case-00107.html` -- the impaired-evidence case, whose GPS trace is carried
  at weight 0.30
- `/case-00208.html` -- the no-show case the landing page sends a reader to

## The result

**0 violations in all six scans.** No rule in the axe-core 4.8.2 set fired on
any of the three pages, in either theme.

## Two faults an earlier scan reported, and why neither was the site's

An earlier scan in the same session reported a **contrast fault on the header**
and **missing `tabindex` on two tables**. Both came from the tool, not from the
site, and both were diagnosed rather than assumed:

- The **browser pane was hidden**, so the page had been laid out in a **0 px
  window**; axe measures contrast against the box it finds, and a 0 px window is
  not the layout a reader gets.
- The **tab held a cached pre-part-47 page**, so the tables it measured were the
  ones that predate the scrolling wrappers' `tabindex`.

Rescanned at 1440 px with a cache-busting query, both cleared. The six scans
above are that rescan.

## What it does not cover

- **Other case pages.** Three addresses were scanned; the site has 151 case
  pages, and the other 148 were not.
- **The replay pages** under `ui/dist/replay/`, which are a second site built by
  another builder.
- **A 375 px window.** The narrow layout was not scanned at any width; the six
  scans are one desktop window in two themes.
- **Screen-reader testing by a person.** No screen reader was run and no person
  read a page with one.

**axe finds only what a rule can detect.** A clean scan is not a statement that
a page is usable, only that the automated rules that ship with axe-core 4.8.2
found nothing to report.
