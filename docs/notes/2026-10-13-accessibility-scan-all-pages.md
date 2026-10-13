# The accessibility scan of every built page, and the narrow window (2026-10-13)

**2026-10-13.** The owner scanned every page under `ui/dist/` with
**axe-core 4.8.2**, in the light and the dark theme, and measured every page's
width in a **375 px** window. This covers what the scan of 2026-10-12
([three pages in two themes](2026-10-12-accessibility-scan.md)) left out: the
other 148 case pages, the replay pages and the narrow layout. It was run against
a local server on `ui/dist/`, not the deployed site.

## How it was run

As on 2026-10-12: axe-core 4.8.2 loaded from cdnjs into the page under test,
never into the site, so the scan changes no published byte; `axe.run` with
violations only; each page loaded in its own frame of **1440 x 900**, in the
light theme and then the dark one, and each frame's theme read back from the
page (all 153 queue and case frames reported the dark scheme in the dark pass).

**The control.** A case page with two faults planted in it -- an image with no
`alt` and a paragraph of light grey on white -- was reported by the same scan
(`image-alt`, `color-contrast`). The scan can fail; a clean result is not a scan
that cannot see.

## What was scanned

181 pages, each in both themes:

- the queue, `404.html` and all **151** case pages (153);
- the product site's **22** pages, English and Chinese, including the short
  pages that forward to another (`architecture`, `docs` and `why`, in each
  language);
- the **6** replay pages under `ui/dist/replay/`.

## The result

**Queue, 404 and case pages: 0 violations in all 306 scans** (the pages as
they stand at commit `fe1625d`; part 57 changed none of them).

**Product site and replay pages: 0 violations once each page had finished
loading.** Two findings appeared only while a page was still loading, and both
cleared when the same page was scanned a few seconds later:

- the three forwarding pages were scanned while the page they forward to was
  still fading its sections in, so axe measured half-transparent text; scanned
  after the fade, 0;
- on the try page, scanned the moment it loaded, axe reported the complaint
  box as unlabelled in both languages (on the Chinese page the label was still
  empty at that moment; on the English page it already read "The rider's
  complaint", and why axe reported it there was not found). Scanned again after
  the page had loaded its case, both languages were clean. A reader who
  arrives in that first moment may meet a box without a label.

## The 375 px window

Each page was loaded in a 375 px frame and its width compared with the
window's.

- **Before part 58: 25 pages were wider than the screen.** 24 case pages,
  where the status chip ("Sent to a reviewer - the judge escalated under the
  policy - 149.5 s") did not wrap and ran up to 460 px; and the About page in
  both languages, whose three figures stayed in three 114 px columns while
  "3,200+" needed more.
- **Part 58** let the case page's chip wrap at 560 px or less (the queue's
  chips are unchanged) and stacked the About figures into one column there.
- **After part 58: 0 of 181 pages are wider than the screen** (commit
  `78eb172`).
- One narrow-screen fault that is not an overflow: the chat table's time
  column broke a clock such as `11:18:29` across two lines, because the cell
  used the monospace style that allows a break anywhere. Part 59 keeps a clock
  on one line.

## What it does not cover

- **Screen-reader testing by a person.** No screen reader was run and no
  person read a page with one.
- **A keyboard walk-through of every page.** The tables' scrolling regions
  carry `tabindex` (checked on 2026-10-12); no one tabbed through all 181
  pages.
- **Widths other than 375 px and 1440 px.**
- **The deployed site.** The pages scanned are the ones `ui/dist/` holds; the
  deployed copy is checked against them by hash when it is uploaded.

**axe finds only what a rule can detect.** A clean scan says that the
automated rules shipped with axe-core 4.8.2 found nothing to report; it does
not say a page is easy to use.
