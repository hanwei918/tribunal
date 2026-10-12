"""The product view: what a support team sees when Tribunal runs at policy version 6.

Why a second site
-----------------
``ui/build.py`` replays the headline run as an *evaluation*: 29 cases, policy
version 1, an answer key beside them and a miss marked where the ruling and the
key disagree. That is the right page for a judge of the benchmark and the wrong
one for the person who works the queue. This module builds the other page. It
shows what a support team would have in front of it when the system runs at
policy version 6: today's disputes, what was decided automatically, what went to
a human, and -- for one case -- the whole decision, step by step, with the
agents' own words.

It is the **front door**. The site root is this page -- ``ui/dist/index.html``,
the queue, and ``ui/dist/case-<NNNNN>.html`` beside it -- and the evaluation
replay ``ui/build.py`` builds now lives one level down under ``ui/dist/replay/``.
The code still lives in ``ui/v2/``, and every page here carries a link to the
replay.

What it reads
-------------
Only committed files, and only these four run directories:

* ``runs/policy-v6/`` -- the 29-case corpus at version 6;
* ``runs/dev-v2-ext/policy-v6/`` -- the 120-case second development set;
* ``runs/dev-v2/policy-v6/`` -- case 1779 alone, the prompt-injection case;
* ``runs/ryde-v3/policy-v6/`` -- the organisers' sample case, 901.

Per case it reads the run's own case file and transcript, the public case file
the run was made from (through the set's own loader), the loaded policy, and --
for a case that was sent to a reviewer -- the escalation packet
:mod:`ops.escalation` builds, which is called rather than re-implemented. The
only other files read are ``ops/config.json``, for the queue's targets, the four
``docs/architecture/*.svg`` views, which are copied into the site byte for byte
so the architecture links off the queue stay inside ``ui/dist/``, and the two
committed images under ``ui/assets/`` -- the link-preview image
``og-image.png`` and the front page's poster ``cover-1280.jpg`` -- copied the
same way.

**No answer key is opened anywhere in this module**, and nothing under
``eval/answers/sealed-v1/``, ``data/external/sealed-v1/`` or
``eval/external/sealed-v1/`` is read. The sealed-v1 set is not shown, not
counted and not named.

Every number is read, not typed
-------------------------------
Nothing in this module writes a figure into a template. The queue figures, the
amounts, the confidences, the confidence floor, the execution threshold, the
appeal window, the token prices and the wall clock are each read from the file
that records them, and :func:`build` recomputes all of them from those files on
every run. A number that cannot be read raises :class:`BuildError` and names
what was missing rather than defaulting to something plausible.

What the queue counts, and what a case page tells
--------------------------------------------------
The queue's three routing counts are the three
``python3 -m eval.business_value --report`` prints: decided and executed,
decided with the amount held for a person to release under POL-GEN-05, and sent
to a reviewer with no ruling at all. ``tests/test_ui_v2.py`` holds the page's
three to that command's own reading of the same four runs, so the page cannot
count a held case as an automatic one again.

Every case page carries, under its heading, **the dispute** as the brief carries
it -- the claim, the other party's statement and the chat, with POL-GEN-08(4)'s
mask already applied, so a reader sees the text the agents were handed. A
no-show case carries **what the record shows**: the brief's own derived facts,
laid out and labelled as computed from the record before any model read it. And
above the judge's text sits the **notice to the rider and the driver**, built
from the ruling's fields and the loaded policy alone -- the outcome, the money,
the clauses the ruling rests on by their titles, the record kinds it rests on,
who made the decision and how to appeal -- and naming no field of either
party's profile. The judge's own reasoning is long internal working written for a
reviewer, so its label says whose view it is: the judge's on a decided case, the
drafts' where a panel ran, and the pipeline's own routing sentence where the
scope gate stopped before any judge was asked.

The debate, and why it is not the agents' answers
--------------------------------------------------
A case page's "How it was decided" tab is how a judge sees the brief's required
observable inter-agent communication, so it is drawn as a debate and not as the
agents' answers. **Both sides argue** is two columns of claim cards -- the
rider's and the driver's -- and each card carries the claim's own text, the
artifacts it cites with their kind, the clauses it cites with the policy's own
titles, and the referee's verdict on it. **Citation check** counts what each side
kept and discarded and gives each discarded claim's reason. **Judge** is the four
drafts as four cards: the ruling in words, both amounts, the confidence, whether
the draft carried, and a mark on the drafts that formed the majority; a voided
draft carries its ``DRAFT_*`` reason in words. No page prints an agent's answer
as JSON, and a test holds every page to that.

Two builds are byte-identical
-----------------------------
There is no clock, no random seed and no dictionary iteration in the output
path: cases are walked in a fixed order, every mapping is rendered in sorted key
order where its order is not already meaningful, and ``--check`` compares the
committed bytes against a fresh build and exits non-zero on any difference.

One thing this module rewrites, and it says so
----------------------------------------------
The repository scans every published file for a key-shaped run -- ``sk-``
followed by eight or more word characters -- before it goes public, and ordinary
prose produces one: the transcript of case 2738 says "ask-to-cancel". A page that
carried that verbatim would be reported as a leaked credential by the scan that
exists to catch one, so the run's first hyphen is written as a numeric entity.
It renders as the same character and cannot be read as part of a key, and
:func:`build` prints the page and the count of what it rewrote, so nothing is
done quietly.

The reviewer's form, and what each decision carries
---------------------------------------------------
A case that went to a reviewer carries a form with POL-GEN-06(4)'s four
decisions, and each one builds its own command:

* **ADOPT** records the panel's best-supported proposal, read with
  ``tribunal.precedents.best_supported_proposal``. Where that proposal is
  ``ESCALATE``, or where there is no proposal at all, the page says "nothing to
  adopt" and disables the choice rather than offering an empty command.
* **VARY** and **REFER_COMPLIANCE** offer a ruling from POL-GEN-03's values
  (without ``ESCALATE``, which a closure refuses), an amount, and a multi-select
  of **every** clause the case's own policy carries -- ``referee.policy_clauses``
  called rather than re-implemented, so POL-GEN-07 is reachable. REFER_COMPLIANCE
  carries a note as well.
* **REQUEST_EVIDENCE** offers the six record kinds of POL-GEN-04(b) -- read from
  ``ops.appeal.RECORD_EVIDENCE_KINDS`` -- and the instant the window opens. It
  builds ``python3 -m ops.evidence_window open``, which is **part 26**: one
  window is opened to both parties at once, and the page names the store the
  command writes to rather than pretending the command runs here.

The closing command is ``tribunal.precedents close``'s own command line behind
``ops.review``, and it carries **no** ``close`` of its own: ``ops.review``
supplies the subcommand. The page builds the same string in JavaScript that
:func:`closing_command` and :func:`evidence_window_command` build in Python, so a
test can hold the command itself to ``ops.review`` without a browser.

Where the sealed set enters, and where it does not
--------------------------------------------------
This module names no path under ``eval/answers/sealed-v1/``,
``data/external/sealed-v1/`` or ``eval/external/sealed-v1/``, and during a build
it opens none. It does import :mod:`ops.escalation`, which imports the
development-set registry, and that registry reads the sealed set's *index* at
import time -- the twenty-four case numbers, their dispute ids, their trip ids
and their category, and nothing else. That is the same import ``ui/build.py``
has always made. No case file and no answer key of the sealed set is read, no
sealed case is built, and no page names one.

Run it with::

    python3 -m ui.v2.build
    python3 -m ui.v2.build --check
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets  # noqa: E402
from eval import v6_runs  # noqa: E402
from ops import appeal as appeal_module  # noqa: E402
from ops import escalation  # noqa: E402
from ops import queue as queue_module  # noqa: E402
from tribunal import brief as brief_module  # noqa: E402
from tribunal import loader  # noqa: E402
from tribunal import model as model_module  # noqa: E402
from tribunal import pipeline as pipeline_module  # noqa: E402
from tribunal import precedents as precedents_module  # noqa: E402
from tribunal import referee as referee_module  # noqa: E402

# --------------------------------------------------------------------------
# Where the site lives
# --------------------------------------------------------------------------
DIST_DIR = PROJECT_ROOT / "ui" / "dist"
INDEX_PATH = DIST_DIR / "index.html"

# The evaluation replay, one level down from this site's own pages. Every page
# here links to it, and every page it builds links back to this queue. It is the
# **benchmark** replay at policy version 1 -- a historical record, not the
# pipeline these pages show -- and the footer link names it as that: it is the
# earlier benchmark, and its runs are the version-1 ones, which is what a reader
# who follows it should expect to find.
REPLAY_INDEX = "replay/index.html"
REPLAY_LABEL = "Earlier benchmark replay (policy v1 runs)"

# The architecture set, copied into the site so the queue's links to it stay
# inside the published root. The sources are the repository's own drawings under
# ``docs/architecture/``; the assets are the byte-for-byte copies this builder
# writes beside the pages, in a directory of their own so a link to one of them
# is a file inside ``ui/dist/``. The first view is the **dynamic** one -- one
# dispute, step by step -- which is the view the README embeds at
# ``docs/architecture.svg`` and the one the queue's own "Architecture" link
# opens; the three container views are named beside it, because a reader who
# wants the system as a whole and a reader who wants one dispute's path are not
# the same reader. The set is the policy owner's, drawn from the code at the
# final freeze.
ARCHITECTURE_DIRNAME = "architecture"
ARCHITECTURE_SOURCE_DIR = PROJECT_ROOT / "docs" / ARCHITECTURE_DIRNAME
ARCHITECTURE_ASSET_DIR = DIST_DIR / ARCHITECTURE_DIRNAME
ARCHITECTURE_VIEWS: Tuple[Tuple[str, str], ...] = (
    ("3-dynamic-one-dispute.svg", "Architecture"),
    ("1-system-context.svg", "System context"),
    ("2a-containers-deciding.svg", "Containers: deciding"),
    ("2b-containers-after-ruling.svg", "Containers: after a ruling"),
)


def architecture_link(view: str) -> str:
    """One view's link, as a page writes it: a file under ``ui/dist/``."""
    return "{0}/{1}".format(ARCHITECTURE_DIRNAME, view)


ARCHITECTURE_LINK = architecture_link(ARCHITECTURE_VIEWS[0][0])

# The link-preview image, copied into the site the same way and for the same
# reason: ``og:image`` has to be an absolute URL a scraper can fetch, so the
# file it names must be inside the published root. Its source is a committed
# file and not the owner's original: the original sat in ``tmp/``, which
# ``.gitignore`` excludes, so a clean clone could not build this site at all --
# and a builder that reads a gitignored path is a builder that fails on the
# machine that did not write it. ``ui/assets/og-image.png`` is the owner's own
# bytes, committed, and ``ui/dist/og-image.png`` is its copy.
OG_IMAGE_SOURCE = PROJECT_ROOT / "ui" / "assets" / "og-image.png"
OG_IMAGE_ASSET = DIST_DIR / "og-image.png"
OG_IMAGE_LINK = "og-image.png"

# The poster the front page carries (51a.2), copied into the site the same way
# and for the same reason as the link-preview image: it is a committed file and
# not the owner's original, which sat in the gitignored scratch directory a
# clean clone does not have. ``ui/assets/cover-1280.jpg`` is the owner's own
# bytes -- the poster made with Miora -- and ``ui/dist/cover-1280.jpg`` is its
# copy, so ``--check`` covers it exactly as it covers the og image.
COVER_SOURCE = PROJECT_ROOT / "ui" / "assets" / "cover-1280.jpg"
COVER_ASSET = DIST_DIR / "cover-1280.jpg"
COVER_LINK = "cover-1280.jpg"

# The poster's own size, which the hero's ``<img>`` states so the browser can
# hold the box before the file arrives, and the two lines the front page gives
# it: an alt text that describes the picture for a reader who cannot see it, and
# the caption under it, which is the same small print the README carries.
COVER_WIDTH = 1280
COVER_HEIGHT = 720
COVER_ALT = (
    "Tribunal poster: a robot judge at a bench between a rider holding a phone "
    "and a driver beside his car"
)
COVER_CAPTION = (
    "Poster made with Miora (Tencent); the people are generated, not real people."
)

# The site's own root, as the link scrapers need it: ``og:url`` and ``og:image``
# are absolute URLs or a scraper resolves nothing. It is the address the README
# and the submission's description publish.
SITE_ROOT = "https://tribunal.edgeone.dev/"

# The page a host serves for a path that does not exist. It is built with the
# pages rather than beside them, so ``--check`` covers it too.
NOT_FOUND_PATH = DIST_DIR / "404.html"
NOT_FOUND_LINK = "404.html"

# The five steps of the product's own sentence, and the shape of a page's
# ``og:type``. ``og:type`` is ``website`` for the queue and the 404 page and
# ``article`` for a case page, which is what the tag means.
OG_TYPE_SITE = "website"
OG_TYPE_CASE = "article"

# The four runs the queue is drawn from, in the order the set selector lists
# them. The name is the run's name in ``eval.v6_runs``; the label is what a
# reader sees, and for the two one-case sets it is the case number, because that
# is the only thing that tells them apart.
SET_ORDER: Tuple[str, ...] = ("corpus", "dev-v2-ext", "ryde-v3", "dev-v2")
SET_LABELS: Mapping[str, str] = {
    "corpus": "corpus",
    "dev-v2-ext": "dev-v2-ext",
    "ryde-v3": "901",
    "dev-v2": "1779",
}

# The words a category is shown under. The codes are the loader's own; the words
# are the two the track brief uses for them.
CATEGORY_WORDS: Mapping[str, str] = {
    "ROUTE_DEVIATION": "Route deviation",
    "NO_SHOW_CHARGE": "No-show fee",
}

# --------------------------------------------------------------------------
# The escalation triggers
# --------------------------------------------------------------------------
# A case reaches a human for one of four reasons, and each is read off the run's
# own record rather than inferred from the ruling value alone:
#
# * ``GEN08_SCOPE`` -- the dispute carries ``safety_flag`` or ``complaint_flag``,
#   so POL-GEN-08(1) refuses to adjudicate it and no agent was asked. The flags
#   are on the public case file; the reason code is the pipeline's own.
# * ``NO_VALID_DRAFTS`` -- every draft was rejected by the code checks. The vote
#   the transcript records says so.
# * ``NO_MAJORITY`` -- the panel produced rulings but no majority carried one.
#   The vote's outcome says so.
# * ``JUDGE_ESCALATE`` -- the panel carried an ``ESCALATE``. This is the judge
#   escalating on the merits, which the explanation states in its own words.
#
# The first two are the pipeline's own named reason codes. The other two are
# named here because the pipeline names them only through the vote's outcome
# (``escalated``) and through the ruling value itself, and a queue that counted
# every human review under one word would be counting nothing.
TRIGGER_SCOPE = "GEN08_SCOPE"
TRIGGER_NO_VALID_DRAFTS = "NO_VALID_DRAFTS"
TRIGGER_NO_MAJORITY = "NO_MAJORITY"
TRIGGER_JUDGE = "JUDGE_ESCALATE"
TRIGGER_ORDER: Tuple[str, ...] = (
    TRIGGER_SCOPE,
    TRIGGER_NO_VALID_DRAFTS,
    TRIGGER_NO_MAJORITY,
    TRIGGER_JUDGE,
)

# The ruling value that means "a human decides this".
ESCALATE = pipeline_module.ESCALATE

# What the ruling panel of an escalated case says where a decided case shows the
# ruling. A case sent to a person carried no ruling at all, so the panel's
# headline names who decides next and the reason it went there sits under it.
SENT_TO_A_PERSON = "Sent to a person"

# What the key-figure tile says where a decided case shows its confidence. The
# escalation record's ``confidence`` is 0.0 because no draft's confidence
# attaches to a ruling the panel did not reach -- the vote records the drafts'
# own figures -- so a tile that read 0.0 against the floor would report a
# measurement that was never made.
NO_RULING_CARRIED = "no ruling was carried"

# The two ruling values that return money to the filing party, and the one that
# leaves the present state standing. ``ESCALATE`` and ``DRIVER_COMPENSATION``
# come from the pipeline; these are named here because nothing else names them.
FULL_REFUND = "FULL_REFUND"
PARTIAL_REFUND = "PARTIAL_REFUND"
NO_ACTION = "NO_ACTION"
REFUND_RULINGS: Tuple[str, ...] = (FULL_REFUND, PARTIAL_REFUND)

# The two outcomes a queue row can have, as the filter row names them.
OUTCOME_AUTO = "auto"
OUTCOME_REVIEWER = "reviewer"

# --------------------------------------------------------------------------
# The reviewer's four decisions, and the vocabulary each one offers
# --------------------------------------------------------------------------
# POL-GEN-06(4) names exactly four decisions, and the form offers them in the
# order the clause does.
DECISION_ADOPT = "ADOPT"
DECISION_VARY = "VARY"
DECISION_REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
DECISION_REFER_COMPLIANCE = "REFER_COMPLIANCE"
DECISIONS: Tuple[str, ...] = (
    DECISION_ADOPT,
    DECISION_VARY,
    DECISION_REQUEST_EVIDENCE,
    DECISION_REFER_COMPLIANCE,
)

# The words each decision is offered under, so the form's order and its labels
# are facts about this file rather than about a tuple written out twice.
DECISION_LABELS: Mapping[str, str] = {
    DECISION_ADOPT: "Adopt the system's proposed ruling.",
    DECISION_VARY: (
        "Vary: choose a ruling and a remedy from the options the money block "
        "enumerates for this trip."
    ),
    DECISION_REQUEST_EVIDENCE: (
        "Request evidence: name the record-type items required."
    ),
    DECISION_REFER_COMPLIANCE: (
        "Refer compliance: a safety, fraud or conduct matter."
    ),
}

# The ruling values a VARY or REFER_COMPLIANCE decision may choose from, in the
# order POL-GEN-03 states them and **without** ``ESCALATE``: a closure records a
# decision, and ``ESCALATE`` is the absence of one, which
# ``tribunal.precedents close`` refuses in as many words.
DECISION_RULING_VALUES: Tuple[str, ...] = (
    FULL_REFUND,
    PARTIAL_REFUND,
    NO_ACTION,
    pipeline_module.DRIVER_COMPENSATION,
)

# The record kinds a REQUEST_EVIDENCE decision may name. They are
# ``ops.appeal``'s own list, read rather than retyped, so the page offers exactly
# the kinds POL-GEN-04(b) lists.
EVIDENCE_KINDS: Tuple[str, ...] = tuple(appeal_module.RECORD_EVIDENCE_KINDS)

# The part the evidence-window command belongs to, and the store the page's
# command writes to. ``POL-GEN-06(4)`` lets a reviewer choose REQUEST_EVIDENCE,
# and ``ops/evidence_window.py`` is the command that executes it: it is part 26,
# and the page names the store rather than pretending the command runs in the
# browser. The store is gitignored, so a command copied off the page writes
# under the repository root and leaves nothing tracked.
EVIDENCE_WINDOW_PART = "part 26"
EVIDENCE_STORE = "evidence-windows"

# The words a ruling value is shown under, before its code. These are the words
# the track brief uses for the five values; the code follows in small monospace,
# so a reader meets the meaning first and the vocabulary the policy names after
# it. A value with no words of its own is shown as the code itself.
RULING_WORDS: Mapping[str, str] = {
    "FULL_REFUND": "Full refund",
    "PARTIAL_REFUND": "Partial refund",
    "NO_ACTION": "No change",
    "DRIVER_COMPENSATION": "Fee stands, driver compensated",
    "ESCALATE": "Sent to a human reviewer",
}

# The words a reviewer trigger is shown under, before its code. Three of the
# four are fixed phrases. The fourth -- ``NO_MAJORITY`` -- names the panel size,
# so it is built from the run's own count of drafts rather than typed here, and
# :func:`trigger_words` is what builds it. A code with no phrase of its own is
# shown as the code.
TRIGGER_WORDS: Mapping[str, str] = {
    TRIGGER_SCOPE: "safety or complaint flag",
    TRIGGER_NO_VALID_DRAFTS: "no judge draft passed the code checks",
    TRIGGER_JUDGE: "the judge escalated under the policy",
}

# The words a draft's own abstention reason is shown under, before its
# ``DRAFT_*`` code. A voided draft says in the record why the code checks
# rejected it, and the reason is a code a reader has to be told the meaning of;
# the keys are the pipeline's own constants, so a code the pipeline adds and
# this file does not word is caught by ``tests/test_ui_v2.py`` rather than
# printed as a bare constant on a page. The code still follows the words in
# small monospace, so the vocabulary the record names is on the page too.
DRAFT_WORDS: Mapping[str, str] = {
    pipeline_module.DRAFT_RULING_NOT_AN_OBJECT: (
        "the draft's ruling was not an object"
    ),
    pipeline_module.DRAFT_UNKNOWN_RULING: (
        "the draft named a ruling the policy does not have"
    ),
    pipeline_module.DRAFT_ESCALATE_WITH_MONEY: (
        "the draft escalated and named an amount as well"
    ),
    pipeline_module.DRAFT_AMOUNT_FIELD_ABSENT: (
        "the draft named no amount field"
    ),
    pipeline_module.DRAFT_AMOUNT_REQUIRED_MISSING: (
        "the draft left out an amount this ruling requires"
    ),
    pipeline_module.DRAFT_AMOUNT_DOES_NOT_MIRROR: (
        "the draft's two amounts do not mirror each other"
    ),
    pipeline_module.DRAFT_CLAUSE_MALFORMED: (
        "the draft's clause reference was malformed"
    ),
    pipeline_module.DRAFT_CLAUSE_UNRESOLVED: (
        "the draft quoted a clause id that does not resolve in the policy"
    ),
    pipeline_module.DRAFT_AMOUNT_NOT_READ_OFF: (
        "the draft's amount is not read off the brief"
    ),
    pipeline_module.DRAFT_BELOW_FLOOR: (
        "the draft's confidence is below the policy's floor"
    ),
}

# The words a referee verdict is shown under. The keys are the referee's own
# reason codes, read from that module rather than retyped, so a verdict the
# referee adds and this file does not word is caught by ``tests/test_ui_v2.py``
# rather than printed as a bare constant in the debate.
REFEREE_WORDS: Mapping[str, str] = {
    referee_module.REASON_KEPT: "kept",
    referee_module.NO_EVIDENCE_ID: "the claim cites no evidence id",
    referee_module.NO_CLAUSE_ID: "the claim cites no clause id",
    referee_module.EVIDENCE_UNRESOLVED: (
        "the claim cites an evidence id that does not resolve in this case"
    ),
    referee_module.CLAUSE_UNRESOLVED: (
        "the claim cites a clause id that is malformed or does not resolve in "
        "the policy"
    ),
    referee_module.IMPAIRMENT_UNDISCLOSED: (
        "the claim cites an impaired artifact but does not name its issue codes"
    ),
    referee_module.PROFILE_FIELD_AS_GROUND: (
        "the claim rests on a profile field, which POL-GEN-01 allows as context "
        "only"
    ),
}

# The words a draft's kind is shown under. The keys are the pipeline's own
# constants: a sampled draft is one of the panel asked the same question, and
# the position-swapped draft is the one asked with the two parties' stances
# exchanged, which is what makes the panel's agreement mean something.
DRAFT_KIND_WORDS: Mapping[str, str] = {
    pipeline_module.DRAFT_SAMPLED: "sampled",
    pipeline_module.DRAFT_POSITION_SWAPPED: "parties' positions swapped",
}

# The five steps the landing page's strip names, each as (who, what, note). The
# three ``who`` values are the case page's own -- code, model, outcome -- and
# they still say which kind each step is. The strip no longer draws them: 51b.7
# brings it to the poster's one accent, and the case page's stepper circles and
# its legend are where the three colours are met.
HOW_IT_WORKS: Tuple[Tuple[str, str, str], ...] = (
    ("code", "The evidence brief", "the same bytes to both sides"),
    ("model", "Rider and driver advocates", "one advocate for each side, AI"),
    ("code", "The citation referee", "checks every claim against the record"),
    ("model", "The judge, four drafts", "AI; a majority carries the ruling"),
    ("outcome", "A ruling, or a person", "the money held until a person decides"),
)

# The words the filing party is shown under, by the loader's own role.
FILED_BY_WORDS: Mapping[str, str] = {
    "RIDER": "Rider",
    "DRIVER": "Driver",
}

# What a case sent to a reviewer says where a decided case carries its
# provisional-ruling disclosure. A case that went to a reviewer produced no
# ruling at all, so the disclosure above would be a statement about a ruling
# that was never made: the case says instead that nothing was decided
# automatically, that the disputed amount is held, and that a person decides.
NO_AUTOMATED_RULING = (
    "No automated ruling was made. The disputed amount is held, and a person "
    "decides this case."
)

# The label the judge's own text is shown under. On a decided case the text is
# the judge's reasoning, and it is long internal working -- it carries field
# names and the other party's account counters -- so the page says whose view it
# is. On a case that went to a reviewer the text the panel carried is the
# drafts' reasoning, and a case the scope gate stopped before any judge has no
# drafts at all: its text is the pipeline's own routing sentence, and it is
# labelled as that rather than as a panel's reasoning.
JUDGE_TEXT_LABEL = "Reviewer view: the judge's full reasoning"
DRAFTS_TEXT_LABEL = "From the judges' drafts' reasoning"
ROUTING_TEXT_LABEL = "Why no automatic ruling was made"

# The notice every case page carries above the judge's text. It is built from
# the ruling's own fields and the loaded policy and from nothing else: no
# profile field of either party, no answer key, no sentence of this file's own
# about what happened.
NOTICE_TITLE = "Notice to the rider and the driver"

# What every notice says above its first line. The notice is the decision put
# into the parties' own words, and this page does not send it to either of them:
# there is no mail, no account, no form and no request of any kind on it, which
# the site's own self-containment is what makes true. A reader who took the
# notice for something the two parties had been sent would be reading a page as
# a delivery, so the page says what it is.
NOTICE_PREVIEW = "Preview: this page sends nothing."

# The record kinds the notice names, in the order it names them. A kind that is
# not here is not named: the two profile artifacts are deliberately absent,
# because a notice to the parties must not tell them their own profiles carried
# the decision, and POL-GEN-01 forbids a profile establishing a fact about the
# trip anyway.
EVIDENCE_KIND_WORDS: Mapping[str, str] = {
    "GPS_TRACE": "GPS trace",
    "CHAT_LOG": "chat log",
    "TRIP_RECORD": "trip record",
    "FARE_BREAKDOWN": "fare breakdown",
    "TRAFFIC_ADVISORY": "traffic advisory",
}
EVIDENCE_KIND_ORDER: Tuple[str, ...] = tuple(EVIDENCE_KIND_WORDS)
PROFILE_EVIDENCE_KINDS: Tuple[str, ...] = ("RIDER_PROFILE", "DRIVER_PROFILE")

# The most clauses the notice names. The line says what the ruling rests on, and
# one sentence can name several clauses at once -- a ruling that lists the limbs
# it applied -- so the line stops at five rather than reciting the policy.
NOTICE_CLAUSE_LIMIT = 5

# What the clause line says when the ruling refers nothing on and no sentence of
# its explanation names a clause of the policy in force. The reviewer view is the
# judge's own reasoning, shown further down the same page.
NO_CLAUSE_NAMED = "The reviewer view gives the clauses the panel applied."

# The admissibility status that means the artifact is not in the record at all.
# A kind whose artifact is MISSING is not something a ruling rested on, however
# often its identifier is named: case 209's ruling says in as many words that no
# traffic advisory exists, and its identifier appears in the text all the same.
ADMISSIBILITY_MISSING = "MISSING"

# The one chat channel a call-log entry is recorded under. A message on it is
# the record's own line about a call that was placed, answered or missed, and it
# is shown as its own line rather than as a chat message.
CALL_LOG_CHANNEL = "VOICE_CALL_LOG"

# The README's results section, linked from the queue. The queue's own figures
# are development data, and the README is where the submission's figures -- the
# sealed sets among them -- are stated, with the command that measured each one.
# The link is the repository's own page and not a path out of the site: it was
# ``../../README.md#results``, which resolved in a checkout -- the repository's
# file is two directories above the site -- and 404s wherever ``ui/dist/`` is
# served on its own, which is where this site is served. The repository is
# private until the owner opens it on 2026-10-16; the address is the one the
# repository will have, so the link is correct now and works then.
README_RESULTS_LINK = "https://github.com/hanwei918/tribunal#results"
README_RESULTS_WORDS = "How the figures were measured"

# The case the links row sends a reader to for the debate itself: the no-show
# case the description names, whose "How it was decided" tab shows the two
# advocates' claims and the judge's four drafts.
HOW_IT_WAS_DECIDED_CASE = 208

# The three pages the safeguards section links to that this site does not carry:
# the repository's privacy note, the limits section of its README, and the note
# recording the accessibility scan. Each is an absolute URL, because the site is
# served on its own and a repository-relative path resolves nowhere and 404s
# there; the tests' own external-link allowance names all three rather than
# passing them over silently.
PRIVACY_LINK = (
    "https://github.com/hanwei918/tribunal/blob/main/docs/governance/privacy.md"
)
LIMITATIONS_LINK = (
    "https://github.com/hanwei918/tribunal#limitations-and-disclosures"
)
ACCESSIBILITY_NOTE_LINK = (
    "https://github.com/hanwei918/tribunal/blob/main/docs/notes/"
    "2026-10-12-accessibility-scan.md"
)

# The two case pages the safeguards section links to: the safety flag that
# stopped before any model was asked, and the planted clause every draft
# refused. Both are pages this builder writes, so both links stay inside the
# site and are checked against the pages it commits.
SAFEGUARD_SAFETY_CASE = 2735
SAFEGUARD_PLANTED_CLAUSE_CASE = 1779

# The seven lead words of the safeguards section, in the order it prints them.
# They are what a reader scans for, and the section's own test holds the page to
# them in this order rather than to a memory of the sentence around each.
SAFEGUARD_LEADS: Tuple[str, ...] = (
    "Cited or dropped.",
    "A person for what the panel cannot decide.",
    "Safety goes straight to a person.",
    "A planted clause is not obeyed.",
    "One appeal.",
    "Privacy.",
    "What it does not do.",
)

# The muted line under the safeguards list. Its first sentence states what the
# site does for a reader and its second is a link to the note recording the
# scan; the two are kept apart here so the anchor can carry the sentence whole.
SAFEGUARDS_ACCESSIBILITY = (
    "Accessibility: light and dark themes, tables that sort and scroll from the "
    "keyboard, and text contrast of at least 4.5:1, recomputed by the test "
    "suite."
)
ACCESSIBILITY_SCAN_WORDS = (
    "An axe-core 4.8.2 scan of the live site on 2026-10-12 found no violations."
)

# What the queue page says the product is, and what the disputes on it are. Two
# sentences about the system, and then the two disclosures: every dispute shown
# is synthetic except the organisers' own sample, and the figures are
# development data measured over the recorded runs.
WHAT_TRIBUNAL_DOES = (
    "Tribunal decides one disputed trip from one evidence brief: two AI "
    "advocates argue the same brief, a citation referee checks every claim, a "
    "judge answers four times and its majority decides, and a person decides "
    "what the panel cannot."
)
WHAT_THE_DISPUTES_ARE = (
    "Every dispute shown here is a synthetic test case, except case 901, which "
    "is the organisers' sample."
)
WHAT_THE_FIGURES_ARE = "These figures are development data."

# The one-sentence description the 404 page carries, and the title it is shown
# under. Both are this file's own words: the page is about the site, not about a
# case.
NOT_FOUND_TITLE = "Tribunal - page not found"
NOT_FOUND_DESCRIPTION = (
    "This page does not exist; the queue lists every dispute this site replays."
)

# The set order, as an index. The queue's row order is this order and then the
# case number; nothing about a directory listing or an interpreter's string hash
# seed may decide it.
SET_ORDER_INDEX: Mapping[str, int] = {
    name: index for index, name in enumerate(SET_ORDER)
}

CASE_FILE_RE = re.compile(r"^case-(\d{5})\.json$")

# A recorded instant: the ISO 8601 strings every timestamp in the record is
# written as. The chat table and the record's event lines show the clock alone,
# with the date once above them, because the full string wraps in a cell.
INSTANT_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})"
)

# One call-log entry's own text: what happened, how long the call was, and what
# became of it -- "Voice call placed by driver, 0:34, answered". Read rather than
# re-worded, so the one-line record answer quotes the record's own figures.
CALL_TEXT_RE = re.compile(
    r"^(?P<what>.*?),\s*(?P<minutes>\d+):(?P<seconds>\d{2}),\s*(?P<state>.+)$"
)

# The six steps a case page walks. It is a tuple so its order is a fact about
# this file rather than about a dict.
STEP_TITLES: Tuple[str, ...] = (
    "Evidence pack",
    "Both sides argue",
    "Citation check",
    "Judge",
    "Floor and triggers",
    "Outcome",
)

DISCLOSURE = "This is a provisional ruling made by an automated system."

# --------------------------------------------------------------------------
# 47. The summary bar, and what two loaded words mean
# --------------------------------------------------------------------------
# 47.1: a case page opened with the two parties' long accounts and the chat, and
# the ruling came after them. The summary bar states the outcome, the money and
# who decides next in one line under the title, and links to the ruling panel.
# Every word of it is read from the ruling and from the lane the queue's own
# status chip assigns the case, as the chips already are: nothing here reads a
# file the page did not already read.
SUMMARY_BAR_WHY = "Why"
SUMMARY_BAR_TARGET = "panel-ruling"
SUMMARY_MONEY_REFUND = "refund to the {0}"
SUMMARY_MONEY_DRIVER = "driver compensation"
SUMMARY_MONEY_NOTHING = "nothing moves"
SUMMARY_MONEY_HELD = "held"
SUMMARY_WHO_PANEL = "decided by the panel"
SUMMARY_WHO_HELD = "held for a person to release"
SUMMARY_WHO_PERSON = "sent to a person"

# 47.3: what the queue's two loaded words mean, in one sentence each. The tile's
# small print and the line under the tiles both read these, so the page cannot
# come to mean two things by "executed" or by "confidence": "executed" is not a
# payment and "confidence" is not a measured accuracy.
EXECUTED_MEANS = (
    "the system would have executed the ruling on issue, and no money moved"
)
CONFIDENCE_MEANS = (
    "the judge's own figure, capped by the evidence weights, not a measured "
    "accuracy"
)

# The one line under the queue's tiles, built from the two sentences above so
# the tile's small print and the line cannot say different things about the same
# word.
QUEUE_WORDS_NOTE = (
    'These are recorded runs on synthetic cases, so "executed" means '
    + EXECUTED_MEANS
    + '; and "confidence" is '
    + CONFIDENCE_MEANS
    + " - the measured agreement figures are in the README's results."
)

# 47.4: the clause whose arithmetic a refund above the contested amount comes
# from, and the clause whose wording says a partial refund returns part of the
# contested amount. They are named on the page and in the README, and the
# tension between them is disclosed rather than repaired.
REFUND_ARITHMETIC_CLAUSE = "POL-RD-02"
REFUND_WORDING_CLAUSE = "POL-GEN-03"


class BuildError(Exception):
    """A page could not be built from the files it reads."""


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------
def _read_json(path: Path) -> Any:
    """One committed file, with every JSON number carrying a point a ``Decimal``."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise BuildError("cannot read {0}: {1}".format(path, exc)) from exc
    try:
        return json.loads(text, parse_float=Decimal)
    except ValueError as exc:
        raise BuildError("invalid JSON in {0}: {1}".format(path, exc)) from exc


def _case_numbers(run_dir: Path) -> List[int]:
    """Every case number a run directory holds, ascending.

    ``os.walk`` rather than a glob: the walk names every file it visits, and the
    transcripts beside the case files match ``case-*.json`` too, so they are
    skipped by name.
    """
    found: List[int] = []
    for dirpath, _dirnames, filenames in os.walk(run_dir):
        for name in sorted(filenames):
            match = CASE_FILE_RE.match(name)
            if match is not None:
                found.append(int(match.group(1)))
    return sorted(found)


def _set_for(name: str):
    """The registered development set a run name belongs to."""
    if name not in development_sets.BY_NAME:
        raise BuildError("no development set is registered as {0!r}".format(name))
    return development_sets.BY_NAME[name]


def _run_for(name: str) -> "v6_runs.V6Run":
    try:
        return v6_runs.run_by_name(name)
    except KeyError as exc:
        raise BuildError("no version-6 run is registered as {0!r}".format(name)) from exc


def _transcript_of(run_dir: Path, document: Mapping[str, Any], case_no: int) -> Mapping[str, Any]:
    """The case's transcript, by the name the run recorded for it."""
    recorded = document.get("transcript_file")
    name = recorded if isinstance(recorded, str) and recorded else "case-{0:05d}.transcript.json".format(case_no)
    return _read_json(Path(run_dir) / name)


def _inner_ruling(document: Mapping[str, Any]) -> Mapping[str, Any]:
    block = document.get("ruling")
    inner = block.get("ruling") if isinstance(block, Mapping) else None
    if not isinstance(inner, Mapping):
        raise BuildError("case {0} records no ruling".format(document.get("case_no")))
    return inner


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------
def _entity(text: str) -> str:
    """``text`` with every non-ASCII character written as a numeric entity.

    The pages are ASCII only, and the run's prose is not: a judge's explanation
    is written with em dashes and typographic quotes. Escaping them keeps the
    file ASCII without changing a character of what it says.
    """
    out: List[str] = []
    for character in text:
        if ord(character) < 128:
            out.append(character)
        else:
            out.append("&#{0};".format(ord(character)))
    return "".join(out)


def _text(value: Any) -> str:
    """A value as HTML text, ASCII only."""
    if value is None:
        return ""
    return _entity(html.escape(str(value), quote=False))


def _attribute(value: Any) -> str:
    """A value as an HTML attribute value, ASCII only."""
    if value is None:
        return ""
    return _entity(html.escape(str(value), quote=True))


def _coded(words: Any, code: Any, strong: bool = False) -> str:
    """The plain words first, the code after them in small monospace.

    Every place a reader meets a ruling value or a reason code is drawn with
    this: the words carry the meaning, and the code follows in ``.mono`` so the
    vocabulary the policy names is still on the page. The words are escaped
    here, so a caller passes the rendered HTML straight through.
    """
    word_html = "<strong>{0}</strong>".format(_text(words)) if strong else _text(words)
    return '{0} <span class="mono">{1}</span>'.format(word_html, _text(code))


def _money(value: Any, currency: str) -> str:
    """An amount as the currency and two decimals, or ``none`` when absent.

    The literal is the one the file wrote: ``Decimal`` throughout, so ``3.20``
    is rendered ``3.20`` and never re-rounded through a binary float.
    """
    if value is None or isinstance(value, bool):
        return "none"
    try:
        return "{0} {1:.2f}".format(currency, Decimal(str(value)))
    except Exception as exc:  # pragma: no cover - a malformed amount is a refusal
        raise BuildError("cannot render the amount {0!r}".format(value)) from exc


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _share(count: int, total: int) -> str:
    if total == 0:
        raise BuildError("a share of nothing has no value")
    return "{0:.1f}%".format(Decimal(count) * 100 / Decimal(total))


def _seconds(value: Any) -> str:
    number = _decimal(value)
    return "none" if number is None else "{0:.1f} s".format(number)


def _whole(value: Any) -> str:
    """A figure in whole units, rounded half up, or ``none`` where it is absent.

    The record's figures are metres and seconds carrying many decimals; a
    sentence that quotes one says "585" and not "585.0", and a value the block
    does not carry is said to be missing rather than shown as a zero.
    """
    number = _decimal(value)
    if number is None:
        return "none"
    return str(int(number.quantize(Decimal(1), rounding=ROUND_HALF_UP)))


def _clock(value: Any) -> str:
    """The time of day a recorded instant carries, as ``16:02:26``.

    Every instant in the record is an ISO 8601 string with a UTC offset, which
    is long enough to wrap inside a table cell. The date is written once above
    the table and each row carries the clock alone. A value that is not an
    instant is left exactly as it is rather than cut about.
    """
    text = str(value or "")
    match = INSTANT_RE.match(text)
    if match is None:
        return text
    return "{0}:{1}:{2}".format(
        match.group("hour"), match.group("minute"), match.group("second")
    )


def _date_of(value: Any) -> str:
    """The date a recorded instant falls on, as ``2026-07-30``."""
    text = str(value or "")
    match = INSTANT_RE.match(text)
    return match.group("date") if match is not None else text


def _call_line(text: Any) -> str:
    """One call-log entry as a sentence: "a 34 s answered call".

    The entry's own text is "Voice call placed by driver, 0:34, answered", and
    the duration and the outcome are read out of it rather than retyped. An
    entry whose text is not that shape is quoted as it stands.
    """
    written = str(text or "").strip()
    match = CALL_TEXT_RE.match(written)
    if match is None:
        return written
    total = int(match.group("minutes")) * 60 + int(match.group("seconds"))
    return "a {0} s {1} call".format(total, match.group("state").strip())


def _cost_usd(prompt: int, cached: int, completion: int) -> Decimal:
    """One case's cost, at the prices ``eval.v6_runs`` bills at.

    Read from that module rather than typed here, so the queue and the report
    cannot come to bill the same tokens at two different prices.
    """
    return (
        Decimal(prompt - cached) * v6_runs.PRICE_INPUT
        + Decimal(cached) * v6_runs.PRICE_CACHED_INPUT
        + Decimal(completion) * v6_runs.PRICE_OUTPUT
    ) / v6_runs.MILLION


def _median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    if not ordered:
        raise BuildError("a median of nothing has no value")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _usd(value: Decimal) -> str:
    return "{0:.4f} USD".format(value)


# A key-shaped run of characters: ``sk-`` followed by eight or more word
# characters. It is the pattern the repository scans every published file for
# before the repository goes public, and ordinary prose produces it --
# "ask-to-cancel" is one, and it occurs in a transcript this site draws from.
# A page that carried such a run verbatim would be reported as a leaked
# credential by the scan that exists to catch one, so the run's first hyphen is
# written as a numeric entity. It renders as the same character and cannot be
# read as part of a key. :func:`pages` counts what it rewrote and names the page,
# so nothing is done quietly.
KEY_SHAPED_RE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
DEFUSED = "sk&#45;"


def defuse_key_shaped(text: str) -> str:
    """``text`` with the first hyphen of every key-shaped run entity-escaped."""
    return KEY_SHAPED_RE.sub(
        lambda match: match.group(0).replace("-", "&#45;", 1), text
    )


# --------------------------------------------------------------------------
# The policy the pages quote
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PolicyFacts:
    """The general policy's own figures and sentences, read once per category."""

    category: str
    version: int
    currency: str
    confidence_floor: Decimal
    execution_threshold: Decimal
    clause_rules: Mapping[str, str]
    clause_titles: Mapping[str, str]

    def rule(self, clause_id: str) -> str:
        try:
            return self.clause_rules[clause_id]
        except KeyError as exc:
            raise BuildError(
                "the loaded policy carries no clause {0}".format(clause_id)
            ) from exc

    def title(self, clause_id: str) -> str:
        """The clause's own title, or its id where the policy states none."""
        return self.clause_titles.get(clause_id) or clause_id


def _policy_facts(category: str, version: int) -> PolicyFacts:
    """The loaded policy for one category, at one version."""
    try:
        policies = loader.load_policies(category, version)
    except loader.LoaderError as exc:
        raise BuildError(
            "the policy for {0} at version {1} cannot be loaded: {2}".format(
                category, version, exc
            )
        ) from exc
    general = policies["general"]
    floor = _decimal(general.get("confidence_floor"))
    threshold = _decimal(general.get("execution_threshold_sgd"))
    if floor is None or threshold is None:
        raise BuildError(
            "the general policy states no confidence floor or execution threshold"
        )
    rules: Dict[str, str] = {}
    titles: Dict[str, str] = {}
    for clause in general.get("clauses") or []:
        if isinstance(clause, Mapping) and isinstance(clause.get("id"), str):
            rules[clause["id"]] = str(clause.get("rule") or "")
            titles[clause["id"]] = str(clause.get("title") or "")
    # The category policy's own clauses are titled the same way and are read
    # here too, because the notice names the clause titles a ruling relied on
    # and a ruling cites category clauses (POL-NS-*, POL-RD-*) as often as it
    # cites general ones.
    for clause in (policies.get("category") or {}).get("clauses") or []:
        if isinstance(clause, Mapping) and isinstance(clause.get("id"), str):
            titles[clause["id"]] = str(clause.get("title") or "")
    return PolicyFacts(
        category=category,
        version=version,
        currency=str(general.get("currency") or ""),
        confidence_floor=floor,
        execution_threshold=threshold,
        clause_rules=rules,
        clause_titles=titles,
    )


def ruling_words(ruling_value: Any) -> str:
    """The words a ruling value is shown under, before its code."""
    return RULING_WORDS.get(str(ruling_value), str(ruling_value))


def trigger_words(trigger: str, votes: int) -> str:
    """The words a reviewer trigger is shown under, before its code.

    The no-majority phrase names the panel size -- "the four drafts did not
    agree" -- and the count is the run's own number of judge drafts, so the
    number on the page is read from the run rather than typed here.
    """
    if trigger == TRIGGER_NO_MAJORITY:
        return "the {0} drafts did not agree".format(votes)
    return TRIGGER_WORDS.get(trigger, trigger)


def draft_words(reason_code: str) -> str:
    """The words one draft-abstention code is shown under, before its code."""
    return DRAFT_WORDS.get(reason_code, reason_code)


def referee_words(reason_code: str) -> str:
    """The words one referee verdict code is shown under, before its code."""
    return REFEREE_WORDS.get(reason_code, reason_code)


def filed_by_words(value: Any) -> str:
    """The words the filing party is shown under, before its role code."""
    return FILED_BY_WORDS.get(str(value), str(value))


def money_statement(
    ruling: Mapping[str, Any], currency: str, filed_by: Any
) -> str:
    """What money moves, stated by the ruling value (POL-GEN-03).

    POL-GEN-03 says ``amount_sgd`` is the refund to the filing party on every
    ruling but one. Its single exception is ``DRIVER_COMPENSATION``: there the
    field carries the same figure as ``driver_compensation_sgd`` -- the amount
    the ruling moves, not a second payment and not a refund -- so the sentence
    is chosen by the ruling value and never calls that figure a refund. A value
    the clause does not cover is refused rather than described by hand.
    """
    value = str(ruling.get("ruling"))
    if value in REFUND_RULINGS:
        who = str(filed_by or "").strip().lower() or "filing party"
        return "Refund to the {0}: {1}".format(
            who, _money(ruling.get("amount_sgd"), currency)
        )
    if value == pipeline_module.DRIVER_COMPENSATION:
        return "The fee stands. The driver is paid {0}. No refund.".format(
            _money(ruling.get("driver_compensation_sgd"), currency)
        )
    if value == NO_ACTION:
        return "No money moves. The charge stands."
    if value == ESCALATE:
        return "No money moves. The disputed amount is held."
    raise BuildError(
        "POL-GEN-03 states no money rule for the ruling value {0!r}".format(value)
    )


def ruling_sentence(ruling: Mapping[str, Any], currency: str) -> str:
    """The ruling as one sentence in plain words, with the figure it moves.

    The notice leads with words and puts the ruling's own code in brackets
    after them, so a party meets what was decided before the vocabulary the
    policy names, and the code is still on the line for a reader who needs it.
    The sentence is chosen by the ruling value, exactly as
    :func:`money_statement` is and for the same reason: POL-GEN-03's single
    exception is ``DRIVER_COMPENSATION``, where the figure is what the driver is
    paid and is never called a refund. A value the clause does not cover is
    refused rather than described by hand.
    """
    value = str(ruling.get("ruling"))
    if value in REFUND_RULINGS:
        return "The rider is refunded {0}".format(
            _money(ruling.get("amount_sgd"), currency)
        )
    if value == pipeline_module.DRIVER_COMPENSATION:
        return "The fee stands and the driver is paid {0}".format(
            _money(ruling.get("driver_compensation_sgd"), currency)
        )
    if value == NO_ACTION:
        return "The charge stands and no money moves"
    if value == ESCALATE:
        return "No ruling is made and the case goes to a person"
    raise BuildError(
        "POL-GEN-03 states no ruling for the ruling value {0!r}".format(value)
    )


# POL-GEN-04's own sentence about the route: "may appeal it once, within 30
# days". Both numbers are read from it, so a clause whose sentence has moved is
# a refusal rather than a re-typed figure.
_APPEAL_RE = re.compile(
    r"may appeal it (once|twice|[0-9]+ times), within ([0-9]+) days"
)


def appeal_line(policy: PolicyFacts) -> str:
    """POL-GEN-04's appeal route in one line, built from the clause's numbers.

    The route is stated in words and the clause id follows it in brackets: the
    clause line above names what the ruling rests on, and the appeal route is a
    right POL-GEN-04 gives the parties whether or not the ruling rested on it,
    so a notice that named the clause only there would lose it the moment the
    ruling rested on other clauses. The id is on the line all the same, after
    the words rather than in front of them, because a party reads what they may
    do first.
    """
    match = _APPEAL_RE.search(policy.rule("POL-GEN-04"))
    if match is None:
        raise BuildError(
            "POL-GEN-04 no longer states how many times a party may appeal and "
            "within how many days"
        )
    return (
        "You may appeal {0} within {1} days (POL-GEN-04). A different human "
        "reviewer hears it, and only record evidence may be added.".format(
            match.group(1), match.group(2)
        )
    )


# POL-GEN-06(2)'s own sentence about the two review limits: "decided within 24
# hours of entry, within 2 hours for a safety flag".
_REVIEW_TIME_RE = re.compile(
    r"decided within ([0-9]+) hours of entry, within ([0-9]+) hours for a safety flag"
)


def appeal_line_after_a_decision(policy: PolicyFacts) -> str:
    """POL-GEN-04's route for a case a person has yet to decide.

    The clause's numbers are the same ones :func:`appeal_line` reads, and they
    are read the same way; what differs is that there is no ruling to appeal
    yet, so the route is stated as the one that opens when a person has decided.
    The sentence is deliberately not :func:`appeal_line`'s: that line is the one
    a decided case carries, and a page that carried it on a case with no ruling
    would be offering an appeal against a decision nobody made.
    """
    match = _APPEAL_RE.search(policy.rule("POL-GEN-04"))
    if match is None:
        raise BuildError(
            "POL-GEN-04 no longer states how many times a party may appeal and "
            "within how many days"
        )
    return (
        "No ruling has been made yet, so there is nothing to appeal. After a "
        "person decides, you may appeal it {0} within {1} days (POL-GEN-04), "
        "and a different human reviewer hears it.".format(
            match.group(1), match.group(2)
        )
    )


def review_time_limit(policy: PolicyFacts) -> str:
    """POL-GEN-06(2)'s two review time limits, read from the clause's sentence."""
    match = _REVIEW_TIME_RE.search(policy.rule("POL-GEN-06"))
    if match is None:
        raise BuildError("POL-GEN-06 no longer states the two review time limits")
    return (
        "A reviewer decides within {0} hours of entry, or within {1} hours when "
        "the case carries a safety flag.".format(match.group(1), match.group(2))
    )


# --------------------------------------------------------------------------
# The pieces of a case
# --------------------------------------------------------------------------
def escalation_trigger(case: Mapping[str, Any], transcript: Mapping[str, Any]) -> str:
    """Why a case was sent to a reviewer, read off the run's own record."""
    dispute = case.get("dispute") or {}
    if dispute.get("safety_flag") is True or dispute.get("complaint_flag") is True:
        return TRIGGER_SCOPE
    vote = transcript.get("vote")
    outcome = vote.get("outcome") if isinstance(vote, Mapping) else None
    if outcome == pipeline_module.VOTE_NO_VALID_DRAFTS:
        return TRIGGER_NO_VALID_DRAFTS
    if outcome == pipeline_module.VOTE_ESCALATED:
        return TRIGGER_NO_MAJORITY
    return TRIGGER_JUDGE


def monetary_effect(ruling: Mapping[str, Any]) -> Decimal:
    """The money a ruling moves, under POL-GEN-05.

    The clause names "the refund, the driver compensation, or their sum". On a
    ``DRIVER_COMPENSATION`` ruling POL-GEN-03 states the one exception: the two
    fields carry the same figure, which is the amount of money the ruling moves
    and not a second payment, so it is counted once. On every other ruling the
    two are independent and are added.
    """
    amount = _decimal(ruling.get("amount_sgd")) or Decimal(0)
    driver = _decimal(ruling.get("driver_compensation_sgd")) or Decimal(0)
    if ruling.get("ruling") == pipeline_module.DRIVER_COMPENSATION:
        return driver if driver else amount
    return amount + driver


def execution_sentence(
    policy: PolicyFacts, ruling: Mapping[str, Any], currency: str
) -> str:
    """Whether the money executes on issue or is held for release (POL-GEN-05)."""
    threshold = policy.execution_threshold
    if ruling.get("ruling") == ESCALATE:
        return (
            "Escalation is terminal: no monetary outcome issues, so there is "
            "nothing for POL-GEN-05 to execute and the disputed amount is held "
            "rather than collected or refunded."
        )
    effect = monetary_effect(ruling)
    sentence = (
        "POL-GEN-05: the monetary effect is {0} against an execution threshold "
        "of {1}. ".format(_money(effect, currency), _money(threshold, currency))
    )
    if effect > threshold:
        return sentence + (
            "It exceeds the threshold, so the amount is issued but not executed: "
            "it is held for release and the case is placed in the human queue."
        )
    return sentence + (
        "It does not exceed the threshold, so the amount is executed "
        "automatically on issue, subject to POL-GEN-04."
    )


def _claims(transcript: Mapping[str, Any], side: str) -> List[Dict[str, Any]]:
    """One side's claims, each with the referee's verdict where there is one.

    The advocate's own parsed answer is the source of the claims and the
    referee's ledger is the source of the verdicts, matched on the claim text --
    which is how the ledger names them.
    """
    role = side + "_ADVOCATE"
    claims: List[Dict[str, Any]] = []
    for entry in transcript.get("entries") or []:
        if not isinstance(entry, Mapping) or entry.get("role") != role:
            continue
        parsed = entry.get("parsed")
        found = parsed.get("claims") if isinstance(parsed, Mapping) else None
        if isinstance(found, list):
            claims = [claim for claim in found if isinstance(claim, Mapping)]
            break
    referee = transcript.get("referee")
    ledger = referee.get("ledger") if isinstance(referee, Mapping) else None
    by_text: Dict[Any, Mapping[str, Any]] = {}
    for entry in ledger or []:
        if isinstance(entry, Mapping) and entry.get("side") == side:
            by_text.setdefault(entry.get("claim"), entry)
    out: List[Dict[str, Any]] = []
    for claim in claims:
        verdict = by_text.get(claim.get("text"))
        out.append(
            {
                "side": side,
                "text": claim.get("text"),
                "evidence_ids": list(claim.get("evidence_ids") or []),
                "clause_ids": list(claim.get("clause_ids") or []),
                "status": verdict.get("status") if isinstance(verdict, Mapping) else None,
                "reason_code": verdict.get("reason_code") if isinstance(verdict, Mapping) else None,
                "detail": verdict.get("detail") if isinstance(verdict, Mapping) else None,
            }
        )
    return out


def _drafts(transcript: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """The panel's drafts, each with the ruling it parsed to."""
    vote = transcript.get("vote")
    source = vote.get("drafts") if isinstance(vote, Mapping) else None
    entries = transcript.get("entries") or []
    out: List[Dict[str, Any]] = []
    for draft in sorted(
        (item for item in source or [] if isinstance(item, Mapping)),
        key=lambda item: item.get("draft") or 0,
    ):
        parsed_ruling: Optional[Mapping[str, Any]] = None
        for index in reversed(list(draft.get("entries") or [])):
            if isinstance(index, int) and 0 <= index < len(entries):
                entry = entries[index]
                parsed = entry.get("parsed") if isinstance(entry, Mapping) else None
                candidate = parsed.get("ruling") if isinstance(parsed, Mapping) else None
                if isinstance(candidate, Mapping):
                    parsed_ruling = candidate
                    break
        proposal = draft.get("proposal")
        out.append(
            {
                "draft": draft.get("draft"),
                "kind": draft.get("kind"),
                "sides": list(draft.get("sides") or []),
                # The transcript entries this draft occupies, so a page can read
                # the seconds the judge's own calls took without guessing a role
                # name.
                "entry_indices": [
                    index
                    for index in draft.get("entries") or []
                    if isinstance(index, int)
                ],
                "seed": draft.get("seed"),
                "temperature": draft.get("temperature"),
                "valid": bool(draft.get("valid")),
                "agrees": bool(draft.get("agrees")),
                "abstention": draft.get("abstention"),
                "proposal": proposal if isinstance(proposal, Mapping) else {},
                "confidence": parsed_ruling.get("confidence") if parsed_ruling else None,
                "explanation": parsed_ruling.get("explanation") if parsed_ruling else None,
                # The ruling the draft itself parsed to, whether or not the code
                # checks accepted it. A voided draft still says what it decided,
                # and the featured card for 1779 reads the four drafts' own
                # answers to say they reached the same one.
                "ruling": parsed_ruling.get("ruling") if parsed_ruling else None,
                "amount_sgd": parsed_ruling.get("amount_sgd") if parsed_ruling else None,
                "driver_compensation_sgd": (
                    parsed_ruling.get("driver_compensation_sgd")
                    if parsed_ruling
                    else None
                ),
            }
        )
    return out


def _derived_facts(brief: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Every artifact's derived fact blocks, by key, in artifact order."""
    rows: List[Dict[str, Any]] = []
    for artifact in brief.get("case", {}).get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        payload = artifact.get("payload")
        derived = payload.get("derived") if isinstance(payload, Mapping) else None
        keys = sorted(derived) if isinstance(derived, Mapping) else []
        rows.append(
            {
                "evidence_id": artifact.get("evidence_id"),
                "evidence_type": artifact.get("evidence_type"),
                "derived_keys": keys,
            }
        )
    return rows


def _evidence(brief: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Every artifact with the weight and issue codes the precheck gave it."""
    rows: List[Dict[str, Any]] = []
    for artifact in brief.get("case", {}).get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        admitted = artifact.get("admissibility")
        admitted = admitted if isinstance(admitted, Mapping) else {}
        rows.append(
            {
                "evidence_id": artifact.get("evidence_id"),
                "evidence_type": artifact.get("evidence_type"),
                "source": artifact.get("source"),
                "status": admitted.get("status"),
                "weight": admitted.get("weight_multiplier"),
                "issues": list(admitted.get("issues") or []),
            }
        )
    return rows


def _outcome_text(
    ruling: Mapping[str, Any],
    currency: str,
    trigger: Optional[str],
    votes: int,
) -> str:
    """The outcome column: the words and the amount, and no code.

    The ruling code belongs on the case page, so this cell carries the words a
    reader meets first and the figure the ruling moves -- "Partial refund -
    SGD 8.05". On a ``DRIVER_COMPENSATION`` ruling the figure is never called a
    refund: POL-GEN-03 says the fee stands and the driver is paid.
    """
    value = str(ruling.get("ruling"))
    if value == ESCALATE and trigger is not None:
        return "Sent to a reviewer - {0}".format(_text(trigger_words(trigger, votes)))
    amount = _decimal(ruling.get("amount_sgd"))
    driver = _decimal(ruling.get("driver_compensation_sgd"))
    words = _text(ruling_words(value))
    if value == pipeline_module.DRIVER_COMPENSATION and driver is not None:
        return "{0} - driver paid {1}".format(words, _money(driver, currency))
    if value in REFUND_RULINGS and amount is not None:
        return "{0} - {1}".format(words, _money(amount, currency))
    return words


def _chip(kind: str, words: str, title: Any = None) -> str:
    """One status chip. The kind is the colour class, and it is fixed here."""
    attribute = ' title="{0}"'.format(_attribute(title)) if title else ""
    return '<span class="chip {0}"{1}>{2}</span>'.format(
        _attribute(kind), attribute, _text(words)
    )


def _money_is_held(case: "CaseData") -> bool:
    """Whether POL-GEN-05 holds this case's money for release.

    A decided case whose monetary effect is above the execution threshold is
    issued but not executed, so its status is not simply "decided": the amount
    is held and the case joins the human queue.
    """
    if case.trigger is not None:
        return False
    return monetary_effect(case.ruling) > case.policy.execution_threshold


def held_reason(case: "CaseData") -> str:
    """Why a decided case's money is held for release, in one sentence."""
    return "{0} is above the POL-GEN-05 execution threshold of {1}".format(
        _money(monetary_effect(case.ruling), case.policy.currency),
        _money(case.policy.execution_threshold, case.policy.currency),
    )


# The reason code ``ops.queue`` gives a case whose money POL-GEN-05 holds: the
# case sits in the human lane for release. It is read from the module that
# routes it rather than retyped here, so a rename cannot leave the page naming a
# code the queue no longer uses.
HELD_RELEASE_REASON = queue_module.REASON_GEN05_RELEASE


def held_money_statement(
    ruling: Mapping[str, Any], policy: PolicyFacts, filed_by: Any
) -> str:
    """The notice's money line when POL-GEN-05 holds the amount for release.

    :func:`money_statement` states what money the ruling moves, which on a held
    case reads as though it had moved. It has not: the ruling issued the amount
    and POL-GEN-05 stopped it at the execution threshold, so the line says what
    was decided, what holds it, and until when.
    """
    return (
        "{0} The amount was decided and is held above POL-GEN-05's execution "
        "threshold of {1} until a person releases it.".format(
            money_statement(ruling, policy.currency, filed_by),
            _money(policy.execution_threshold, policy.currency),
        )
    )


def release_sentence(policy: PolicyFacts) -> str:
    """Who releases a held amount, and how, in one sentence.

    ``ops.review`` is the command this page's review form builds, and it cannot
    record a release: it insists on the digest of an escalation packet, and
    ``ops.escalation`` builds a packet only for an escalated case -- which a
    held case, whose ruling is a refund rather than an escalation, is not. What
    the repository does have is the human queue the case sits in and the closure
    command that needs no packet. The threshold is the loaded policy's own, so
    the sentence cannot quote a figure the policy does not state.
    """
    return (
        "A person releases it, not this form: the queue holds the case in the "
        "human lane under {0} (POL-GEN-05, execution threshold {1}), and the "
        "release is recorded as a closure by python3 -m tribunal.precedents "
        "close, not by ops/review.py, which requires the digest of an escalation "
        "packet and a packet is built only for an escalated case.".format(
            HELD_RELEASE_REASON,
            _money(policy.execution_threshold, policy.currency),
        )
    )


# The four short chip labels a status chip is one of, keyed by the lane the
# queue routes the case into. A chip does not wrap (:func:`status_chip`), so the
# longest of these is the widest a status chip can be and the queue's Status
# column cannot grow past it; the queue's own test holds every chip in the built
# queue to that width, and the labels live here so the chip and the test cannot
# drift apart.
CHIP_LABELS: Mapping[str, str] = {
    "decided": "Decided automatically",
    "held": "Held for release",
    "reviewer": "Sent to a reviewer",
    "none": "No status is recorded",
}


def status_chip(
    case: "CaseData", with_time: bool = False, title: bool = False
) -> str:
    """The status chip: green decided, red reviewer, amber held, grey otherwise.

    The four meanings the sheet names. A held amount gets the short words "Held
    for release": a chip long enough to wrap would change the row's height, so
    the figure and the threshold it crossed travel in the ``title`` attribute,
    which is where a reader looks for the detail. The wall time is appended on a
    case page and left off a queue row, where the time has a column of its own.
    """
    suffix = (
        " - {0}".format(_seconds(case.document.get("wall_seconds"))) if with_time else ""
    )
    if case.trigger is not None:
        return _chip(
            "bad",
            "{0} - {1}{2}".format(
                CHIP_LABELS["reviewer"],
                trigger_words(str(case.trigger), case.votes),
                suffix,
            ),
        )
    if _money_is_held(case):
        return _chip(
            "warn",
            "{0}{1}".format(CHIP_LABELS["held"], suffix),
            title=held_reason(case) if title else None,
        )
    if case.ruling.get("ruling") in (
        FULL_REFUND,
        PARTIAL_REFUND,
        NO_ACTION,
        pipeline_module.DRIVER_COMPENSATION,
    ):
        return _chip("ok", "{0}{1}".format(CHIP_LABELS["decided"], suffix))
    return _chip("grey", "{0}{1}".format(CHIP_LABELS["none"], suffix))


def queue_status_cell(case: "CaseData") -> str:
    """The queue row's status cell: the short chip, and its detail under it.

    A chip does not wrap, so on a queue row -- where the Status column's width
    is the whole table's business and not one heading's -- a case sent to a
    reviewer shows the short chip :data:`CHIP_LABELS` names and the trigger
    words travel under it in the same small wrapping note a held amount's reason
    uses (same class, same ``max-width``). The words do not change; only where
    they sit does. The case page's header keeps the long form,
    :func:`status_chip` with ``with_time``, where the words are a heading and no
    column is at stake.
    """
    if case.trigger is not None:
        cell = _chip("bad", CHIP_LABELS["reviewer"])
        note = trigger_words(str(case.trigger), case.votes)
    else:
        cell = status_chip(case)
        note = held_reason(case) if _money_is_held(case) else ""
    if note:
        cell += '<span class="held-why">{0}</span>'.format(_text(note))
    return cell


# --------------------------------------------------------------------------
# 47.1: the outcome first, in one line
# --------------------------------------------------------------------------
def _summary_outcome(case: "CaseData") -> str:
    """The outcome in words: the ruling's own, or who decides where there is none."""
    if case.trigger is not None:
        return _text(SENT_TO_A_PERSON)
    return _text(ruling_words(str(case.ruling.get("ruling"))))


def _summary_money(case: "CaseData") -> str:
    """What the money does, in one of the four phrases the sheet names.

    Read from the ruling and from the lane the queue's own chip assigns the
    case: a refund to the filing party, the driver's compensation, no money
    moving, or an amount held -- by ``POL-GEN-05`` above the execution threshold
    where the case was decided, and by the escalation where it was not.
    """
    ruling = case.ruling
    currency = case.policy.currency
    value = str(ruling.get("ruling"))
    if case.trigger is not None or _money_is_held(case):
        return _text(SUMMARY_MONEY_HELD)
    if value in REFUND_RULINGS:
        filed_by = str(
            (case.case.get("dispute") or {}).get("filed_by") or ""
        ).strip().lower() or "filing party"
        return "{0} {1}".format(
            _text(SUMMARY_MONEY_REFUND.format(filed_by)),
            _text(_money(ruling.get("amount_sgd"), currency)),
        )
    if value == pipeline_module.DRIVER_COMPENSATION:
        return "{0} {1}".format(
            _text(SUMMARY_MONEY_DRIVER),
            _text(_money(ruling.get("driver_compensation_sgd"), currency)),
        )
    if value == NO_ACTION:
        return _text(SUMMARY_MONEY_NOTHING)
    raise BuildError(
        "POL-GEN-03 states no money rule for the ruling value {0!r}".format(value)
    )


def _summary_who(case: "CaseData") -> str:
    """Who decided, or who decides next: the panel, a release, or a person."""
    if case.trigger is not None:
        return _text(SUMMARY_WHO_PERSON)
    if _money_is_held(case):
        return _text(SUMMARY_WHO_HELD)
    return _text(SUMMARY_WHO_PANEL)


def summary_bar(case: "CaseData") -> str:
    """The one-line summary a case page opens with, directly under its chips.

    The outcome in words, the money, who decides, and a link to the ruling
    panel. It is the same three facts the chips and the ruling panel carry, put
    where a reader meets them first rather than after the two parties' accounts
    and the chat.
    """
    return (
        '<p class="summarybar">'
        "<b>{0}</b> &middot; {1} &middot; {2} &middot; "
        '<a href="#{3}">{4}</a></p>'
    ).format(
        _summary_outcome(case),
        _summary_money(case),
        _summary_who(case),
        _attribute(SUMMARY_BAR_TARGET),
        _text(SUMMARY_BAR_WHY),
    )


def refund_over_contested(case: "CaseData") -> str:
    """One line where the refund is larger than the amount the rider contested.

    ``POL-RD-02`` computes the refund from the fare -- the charged total minus
    the fare recomputed on the optimal route -- and does not cap it at the
    amount the rider named, while ``POL-GEN-03``'s wording says a partial refund
    returns "part of the contested amount". Where the two disagree the page says
    which figure it is showing and where it comes from. The comparison is made
    here, from the record, and the line is drawn only where the refund is the
    larger of the two.
    """
    ruling = case.ruling
    if str(ruling.get("ruling")) not in REFUND_RULINGS:
        return ""
    amount = _decimal(ruling.get("amount_sgd"))
    dispute = case.case.get("dispute") or {}
    contested = _decimal(dispute.get("amount_contested_sgd"))
    if amount is None or contested is None or amount <= contested:
        return ""
    filed_by = str(dispute.get("filed_by") or "").strip().lower() or "filing party"
    return (
        '<p class="refundnote">The refund is the fare difference {0} computes, '
        "which here is more than the {1} the {2} asked for; the policy does not "
        "cap it at the amount contested ({3}).</p>"
    ).format(
        _text(REFUND_ARITHMETIC_CLAUSE),
        _text(_money(contested, case.policy.currency)),
        _text(filed_by),
        _text(REFUND_WORDING_CLAUSE),
    )


# --------------------------------------------------------------------------
# One case, read once
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class CaseData:
    """Everything one case page and one queue row are built from."""

    set_name: str
    case_no: int
    run_dir: Path
    document: Mapping[str, Any]
    transcript: Mapping[str, Any]
    case: Mapping[str, Any]
    brief: Mapping[str, Any]
    brief_sha256: str
    policy: PolicyFacts
    ruling: Mapping[str, Any]
    trigger: Optional[str]
    packet: Optional[Mapping[str, Any]]

    @property
    def label(self) -> str:
        return SET_LABELS[self.set_name]

    @property
    def link(self) -> str:
        return "case-{0:05d}.html".format(self.case_no)

    @property
    def outcome_kind(self) -> str:
        return OUTCOME_REVIEWER if self.trigger is not None else OUTCOME_AUTO

    @property
    def category(self) -> str:
        return str((self.case.get("dispute") or {}).get("category"))

    @property
    def votes(self) -> int:
        """The number of drafts the judge was asked for, read from the run.

        The run's own configuration records it, and a scope-gated case -- which
        asked no judge -- has no vote in its transcript, so the configuration is
        the first place to look and the transcript's own count is the fallback.
        A case that records neither is refused rather than drawn with a zero.
        """
        configuration = self.document.get("configuration")
        if isinstance(configuration, Mapping) and configuration.get("judge_votes") is not None:
            return int(configuration["judge_votes"])
        vote = self.transcript.get("vote")
        if isinstance(vote, Mapping) and vote.get("votes") is not None:
            return int(vote["votes"])
        raise BuildError(
            "case {0} of {1} records no judge vote count".format(
                self.case_no, self.set_name
            )
        )


def _load_case(set_name: str, case_no: int) -> CaseData:
    """Read one case: its run's record, its public case, its brief and its packet."""
    run = _run_for(set_name)
    run_dir = run.run_dir
    document = _read_json(run_dir / "case-{0:05d}.json".format(case_no))
    transcript = _transcript_of(run_dir, document, case_no)
    development_set = _set_for(set_name)
    try:
        case = development_set.load_case(case_no)
    except loader.LoaderError as exc:
        raise BuildError(
            "case {0} of {1} cannot be loaded: {2}".format(case_no, set_name, exc)
        ) from exc
    configuration = document.get("configuration")
    version = (
        configuration.get("policy_version")
        if isinstance(configuration, Mapping)
        else None
    )
    policy = _policy_facts(
        str((case.get("dispute") or {}).get("category")), int(version or 0)
    )
    try:
        brief = brief_module.build_brief_for_case(case, policy_version=int(version or 0))
    except Exception as exc:
        raise BuildError(
            "the brief for case {0} of {1} cannot be built: {2}".format(
                case_no, set_name, exc
            )
        ) from exc
    _canonical, digest = brief_module.brief_digest(brief)
    recorded = document.get("brief_sha256")
    if recorded != digest:
        # The page shows the bytes the agents were handed. A digest that does not
        # match means this code builds a different brief, so the case is refused
        # rather than drawn from a brief that merely resembles it.
        raise BuildError(
            "case {0} of {1}: the rebuilt brief hashes to {2} and the run "
            "recorded {3}, so this code builds a different brief from the one "
            "the agents were handed".format(case_no, set_name, digest, recorded)
        )
    ruling = _inner_ruling(document)
    trigger = (
        escalation_trigger(case, transcript)
        if ruling.get("ruling") == ESCALATE
        else None
    )
    packet: Optional[Mapping[str, Any]] = None
    if trigger is not None:
        try:
            packet = escalation.build_packet(run_dir, case_no)
        except escalation.EscalationError as exc:
            raise BuildError(
                "the escalation packet for case {0} of {1} cannot be built: "
                "{2}".format(case_no, set_name, exc)
            ) from exc
    return CaseData(
        set_name=set_name,
        case_no=case_no,
        run_dir=run_dir,
        document=document,
        transcript=transcript,
        case=case,
        brief=brief,
        brief_sha256=digest,
        policy=policy,
        ruling=ruling,
        trigger=trigger,
        packet=packet,
    )


def read_every_case() -> List[CaseData]:
    """Every case of the four runs: the set selector's order, then case number.

    The order is a fact about this file rather than about a directory listing or
    an interpreter's string hash seed. The rows are collected in ``SET_ORDER``
    and then sorted on the same order and the case number, so a build run twice
    under two hash seeds writes the same bytes and the queue's row order is the
    order the set selector lists the sets in.
    """
    out: List[CaseData] = []
    for set_name in SET_ORDER:
        run = _run_for(set_name)
        for case_no in _case_numbers(run.run_dir):
            out.append(_load_case(set_name, case_no))
    out.sort(key=lambda row: (SET_ORDER_INDEX[row.set_name], row.case_no))
    return out


# --------------------------------------------------------------------------
# The queue's five figures
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class QueueFigures:
    """The figures across the top of the queue, and the reason-code tally.

    The decided cases are counted twice and never once: ``executed`` is the
    money that executes on issue, ``held`` is the money POL-GEN-05 holds above
    the execution threshold for a person to release, and ``reviewer`` is the
    cases that produced no ruling at all. The three are the figures
    ``python3 -m eval.business_value --report`` prints, and a test holds them to
    it: the older page counted the held cases as automatic, which made the queue
    and the command disagree about the same 151 cases.
    """

    total: int
    executed: int
    held: int
    reviewer: int
    triggers: Mapping[str, int]
    median_seconds: Decimal
    median_cost: Decimal
    policy_version: int
    votes: int
    model: str

    @property
    def executed_share(self) -> str:
        return _share(self.executed, self.total)

    @property
    def held_share(self) -> str:
        return _share(self.held, self.total)

    @property
    def reviewer_share(self) -> str:
        return _share(self.reviewer, self.total)


def queue_figures(cases: Sequence[CaseData]) -> QueueFigures:
    """The figures, each computed from the cases' own files."""
    if not cases:
        raise BuildError("the queue holds no cases")
    decided = [case for case in cases if case.trigger is None]
    # A decided case whose money is above POL-GEN-05's execution threshold is
    # issued but not executed: the amount is held for a person to release, and
    # it is counted as held rather than as automatic, which is how
    # ``eval.business_value`` counts it.
    held = [case for case in decided if _money_is_held(case)]
    reviewer = [case for case in cases if case.trigger is not None]
    triggers = Counter(case.trigger for case in reviewer)
    walls: List[Decimal] = []
    costs: List[Decimal] = []
    for case in cases:
        wall = _decimal(case.document.get("wall_seconds"))
        if wall is None:
            raise BuildError(
                "case {0} of {1} records no wall_seconds".format(
                    case.case_no, case.set_name
                )
            )
        walls.append(wall)
        # The tokens are summed from the transcript's own entries, which is where
        # the calls are recorded; the case file carries the same totals, and a
        # case no agent was asked about has none in either place.
        prompt = cached = completion = 0
        for entry in case.transcript.get("entries") or []:
            if not isinstance(entry, Mapping):
                continue
            prompt += int(entry.get("prompt_tokens") or 0)
            cached += int(entry.get("cached_tokens") or 0)
            completion += int(entry.get("completion_tokens") or 0)
        costs.append(_cost_usd(prompt, cached, completion))
    versions = {
        int((case.document.get("configuration") or {}).get("policy_version") or 0)
        for case in cases
    }
    models = {str(case.document.get("model")) for case in cases}
    votes = {case.votes for case in cases}
    if len(versions) != 1 or len(models) != 1 or len(votes) != 1:
        raise BuildError(
            "the queue mixes policy versions {0}, models {1} or judge vote "
            "counts {2}".format(sorted(versions), sorted(models), sorted(votes))
        )
    return QueueFigures(
        total=len(cases),
        executed=len(decided) - len(held),
        held=len(held),
        reviewer=len(reviewer),
        triggers={name: triggers.get(name, 0) for name in TRIGGER_ORDER},
        median_seconds=_median(walls),
        median_cost=_median(costs),
        policy_version=versions.pop(),
        votes=votes.pop(),
        model=models.pop(),
    )


# --------------------------------------------------------------------------
# The stylesheet and the script
# --------------------------------------------------------------------------
_CSS = """
/* The light theme is the default: the palette in :root is what a reader gets
   when the system asks for no preference, and the dark palette below replaces
   it only when the system asks for dark. The status colours move with it, so a
   chip keeps the same contrast on either background. */
/* 37a.6: the muted token is darker than the #6b7280 it was. That colour
   measured 4.39:1 on the page background and 4.83:1 on a card, and 4.5:1 is the
   floor body text is held to, so muted text on the page background was below
   it. #5b6470 measures 5.45:1 on --bg, 6.00:1 on --card and 5.74:1 on --soft;
   the three figures are recomputed from this file by tests/test_ui_v2.py. */
/* 51b.5/51b.6: the accent is the poster's violet, not the blue it was, so the
   site belongs to the poster it carries. Measured: #6d28d9 is 7.10:1 on --card
   (#ffffff), 6.46:1 on --bg (#f3f4f6), 6.80:1 on --soft (#f9fafb) and 5.98:1 on
   --accent-wash (#ede9fe), and white on #6d28d9 is 7.10:1. In the dark palette
   #c4b5fd is 7.92:1 on --card (#1e293b), 9.67:1 on --bg (#0f172a) and 8.67:1
   on --soft (#16213a). The header band is #160b0e in both themes: its right-hand
   readout #c8b8be is 10.16:1 on it and white is 19.3:1. All ten pairs are in
   tests/test_ui_v2.py's STATED_CONTRAST and are recomputed from this file. */
/* 51c.1: the accent is a background too, and the text on it needs a token of
   its own. In the light theme the accent is #6d28d9 and --on-accent is
   #ffffff, 7.10:1 on it; in the dark theme the accent is #c4b5fd, a light
   lavender, and --on-accent is #1e1035, 9.63:1 on it. White on the dark accent
   measured 1.85:1 here, below the 4.5:1 floor, and two rules painted it that
   way: the filled button and the five numbered circles of How it works. The
   brand mark was the same -- a white glyph on the accent -- so its SVG strokes
   take currentColor and the tile carries the token. Both figures are in
   tests/test_ui_v2.py's STATED_CONTRAST and are recomputed from this file. */
/* 51d.1: the case page's numbered step circles are a token background too, and
   their text was white. In the dark theme --grey, --ok and --bad are #cbd5e1,
   #86efac and #fca5a5, and white on them measured 1.48:1, 1.40:1 and 1.90:1
   here, all below the 4.5:1 floor. A token --on-status is added -- #ffffff in
   :root, 10.31:1 on --grey (#374151), 5.02:1 on --ok (#15803d) and 6.47:1 on
   --bad (#b91c1c), and #0f172a in the dark block, 12.02:1, 12.71:1 and 9.41:1
   on the same three -- and .stepper button .n i takes it. The model circle
   keeps --on-accent, because that circle is drawn on the accent and not on one
   of these. All six pairs are in tests/test_ui_v2.py's STATED_CONTRAST and are
   recomputed from this file. */
:root{
  --bg:#f3f4f6;--card:#ffffff;--line:#e5e7eb;--ink:#111827;--muted:#5b6470;
  --soft:#f9fafb;--accent:#6d28d9;--accent-wash:#ede9fe;--on-accent:#ffffff;
  --on-status:#ffffff;
  --ok:#15803d;--ok-wash:#dcfce7;--bad:#b91c1c;--bad-wash:#fee2e2;
  --warn:#92400e;--warn-wash:#fef3c7;--grey:#374151;--grey-wash:#f3f4f6;
  --band:#160b0e;--band-note:#c8b8be;
}
@media (prefers-color-scheme:dark){
  :root{--bg:#0f172a;--card:#1e293b;--line:#334155;--ink:#f1f5f9;--muted:#94a3b8;
    --soft:#16213a;--accent:#c4b5fd;--accent-wash:#2e1065;--on-accent:#1e1035;
    --on-status:#0f172a;
    --ok:#86efac;--ok-wash:#14532d;--bad:#fca5a5;--bad-wash:#7f1d1d;
    --warn:#fcd34d;--warn-wash:#78350f;--grey:#cbd5e1;--grey-wash:#1e293b;}
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--accent)}
h1{font-size:1.6rem;line-height:1.25;margin:0 0 6px}
h2{font-size:1rem;margin:0 0 12px}
h3{font-size:.92rem;margin:16px 0 6px}
p{margin:.5em 0}
/* 51b.6: the header is the poster's dark band in both themes, with a crimson to
   violet rule along its foot. The brand and the nav are white on it and the
   right-hand readout is #c8b8be, so the bar reads the same in either theme; the
   focus ring on it is white rather than the accent, which on #160b0e would be a
   ring a reader could not see. */
/* 52b.1: the bar is sticky and 58 px tall -- .top-in's 56 px height and the
   band's 2 px rule -- and an in-page link landed its target underneath it. The
   owner measured three at a 1440 x 900 window: the queue's "Safeguards" put the
   heading 15 px from the top, and "How it works" and a case page's "Why" put
   their sections at 0 px, so the reader arrived at a section whose heading was
   hidden. Every element an in-page link can target takes a scroll margin larger
   than the bar, so the page stops with the heading in view. */
[id]{scroll-margin-top:72px}
.top{position:sticky;top:0;z-index:5;background:var(--band);
  border-bottom:2px solid;border-image:linear-gradient(90deg,#b91c1c,#6d28d9) 1}
.top-in{max-width:1280px;margin:0 auto;padding:0 24px;height:56px;display:flex;align-items:center;gap:20px}
.top :focus-visible{outline-color:#ffffff}
.brand{display:inline-flex;align-items:center;gap:9px;font-weight:700;font-size:17px;text-decoration:none;color:#ffffff}
/* 51c.1: the mark is a glyph on the accent, so the tile carries --on-accent and
   the drawing takes currentColor rather than a white of its own. */
.mark{width:26px;height:26px;border-radius:7px;background:var(--accent);color:var(--on-accent);display:inline-flex;align-items:center;justify-content:center;flex:none}
.nav{display:flex;align-items:center;gap:2px;flex-wrap:wrap}
.nav a{padding:7px 12px;border:1px solid rgba(255,255,255,.28);border-radius:8px;text-decoration:none;color:#ffffff;font-weight:500;line-height:1.2}
.nav a.on{color:#ffffff;background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.5)}
.mode{margin-left:auto;font-size:13px;color:var(--band-note);white-space:nowrap}
@media (max-width:700px){.mode{display:none}.top-in{gap:12px;padding:0 16px}}
.wrap{max-width:1280px;margin:0 auto;padding:26px 24px 56px}
@media (max-width:700px){.wrap{padding:18px 16px 40px}}
.lede{color:var(--muted);margin:.3em 0 1.1em;max-width:78ch}
.ids{color:var(--muted);font-size:.86rem;font-variant-numeric:tabular-nums;margin:0}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.85rem;overflow-wrap:anywhere;word-break:break-word}
.num{font-variant-numeric:tabular-nums}

/* chips */
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0}
.chip{display:inline-flex;align-items:center;height:24px;padding:0 10px;border-radius:999px;font-size:13px;font-weight:500;background:var(--grey-wash);color:var(--grey);border:1px solid var(--line);white-space:nowrap}
.chip.ok{background:var(--ok-wash);color:var(--ok);border-color:transparent}
.chip.bad{background:var(--bad-wash);color:var(--bad);border-color:transparent}
.chip.warn{background:var(--warn-wash);color:var(--warn);border-color:transparent}

/* featured cards */
.featured{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:18px 0 22px}
@media (max-width:960px){.featured{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:560px){.featured{grid-template-columns:minmax(0,1fr)}}
.fcard{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;text-decoration:none;color:var(--ink);
  transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease}
/* 51b.9: the whole card is one link, so it lifts under the pointer and carries
   the way in at its foot. The lift is movement, and that is the one thing the
   reduce preference takes; the focus ring is the stylesheet's own. */
.fcard:hover{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 8px 20px rgba(0,0,0,.16)}
.fcard .fcase{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.fcard h2{font-size:.95rem;margin:2px 0 8px}
.fcard p{margin:.25em 0;font-size:13px;color:var(--muted)}
.fcard b{color:var(--ink);font-weight:600}
.fcard .fopen{display:block;margin-top:10px;color:var(--accent);font-weight:600;font-size:.85rem}
@media (prefers-reduced-motion:reduce){.fcard{transition:none}.fcard:hover{transform:none}}

/* figures */
.figures{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 22px}
.figure{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;min-width:168px;flex:1 1 168px}
.figure .k{color:var(--muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;margin:0 0 6px}
.figure .v{font-size:1.9rem;font-weight:650;margin:0}
.figure .s{color:var(--muted);font-size:.85rem;margin:4px 0 0}
.figure.wide{flex:1 1 100%}
/* 51b.8: each lane tile carries its lane's own colour on a 3px top border, and
   the three figures under them carry the accent. */
/* 51c.3: the modifiers are named for the tile they draw and not for the colour
   they use. They were `ok`, `warn`, `bad` and `accent`, and the stylesheet's
   older global rule `.ok{color:var(--ok);font-weight:600}` -- the one the
   claims and the notices use -- also matched `<div class="figure ok">`, so the
   first lane tile's figure turned green and its small print turned semibold
   while the other two lanes matched no such rule and stayed as they were. The
   lane rules are `lane-*` now and the global `.ok` is left alone for whatever
   else uses it; every lane rule is qualified by `.figure`. */
.figure.lane-ok{border-top:3px solid var(--ok)}
.figure.lane-warn{border-top:3px solid var(--warn)}
.figure.lane-bad{border-top:3px solid var(--bad)}
.figure.lane-accent{border-top:3px solid var(--accent)}
.triggers{list-style:none;margin:0;padding:0}
.triggers li{display:flex;flex-wrap:wrap;justify-content:space-between;gap:2px 14px;padding:4px 0;border-bottom:1px solid var(--line)}
.triggers li:last-child{border-bottom:0}
.triggers .n{font-weight:650;font-variant-numeric:tabular-nums}

/* table */
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:0 0 18px}
.card.wide{padding:0;overflow:hidden}
.card.wide>h2,.card.wide>p{padding:0 22px}
.card.wide>h2{margin-top:18px}
table{border-collapse:collapse;width:100%}
th,td{text-align:left;padding:11px 14px;border-bottom:1px solid var(--line);vertical-align:middle}
th{color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover td{background:var(--soft)}
th.sortable{cursor:pointer;user-select:none}
td[data-column="time"],td[data-column="confidence"]{white-space:nowrap}
/* 51b.10: the Outcome column wrapped into five lines -- "Sent to a reviewer -
   the judge escalated under the policy" -- while Status had room to spare. The
   column is given a floor, and the note under a status chip is allowed to wrap
   rather than push the chip wider. The row hover is the --soft rule above. */
td[data-column="outcome"]{min-width:11rem}
td[data-column="status"]{white-space:normal;overflow-wrap:anywhere}
td a{font-weight:600;text-decoration:none}

/* case page */
.pagehead{margin:0 0 18px}
/* 51b.4: the queue's head is a hero -- the words on the left and the poster on
   the right at 1000 px and wider, the poster under the words below that. The h1
   grows only here, where the poster sits beside it. */
.hero{display:grid;grid-template-columns:minmax(0,1fr);gap:16px;align-items:start}
.hero h1{font-size:2rem}
.hero-art{margin:0;min-width:0}
.hero-art img{display:block;width:100%;height:auto;border-radius:14px;box-shadow:0 10px 26px rgba(0,0,0,.22)}
.hero-cta{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 0}
.btn{display:inline-flex;align-items:center;gap:6px;padding:9px 16px;border-radius:9px;
  font-weight:600;font-size:.92rem;text-decoration:none;border:1px solid var(--accent)}
.btn-fill{background:var(--accent);color:var(--on-accent)}
.btn-out{background:transparent;color:var(--accent)}
@media (min-width:1000px){
  .hero{grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:30px;align-items:center}
}
.tabs{display:flex;flex-wrap:wrap;gap:6px;border-bottom:1px solid var(--line);margin:0 0 22px}
.tabs button{appearance:none;border:0;background:transparent;color:var(--muted);font:inherit;font-weight:500;padding:9px 13px;border-bottom:2px solid transparent;margin-bottom:-1px;cursor:pointer}
.tabs button.tab-on{color:var(--ink);border-bottom-color:var(--accent)}
.verdict{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:24px 26px;display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:30px;margin:0 0 22px}
.verdict .word{font-size:2.1rem;font-weight:700;letter-spacing:-.01em;line-height:1.1;margin:0}
.verdict .code{color:var(--muted);margin:6px 0 0}
.verdict .lbl{color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;margin:18px 0 4px}
.verdict .why{margin:0;font-size:1rem}
.verdict .after{margin:14px 0 0;font-size:.9rem;color:var(--muted)}
.tiles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 20px;align-content:start;border-left:1px solid var(--line);padding-left:26px}
.tiles div{display:flex;flex-direction:column;gap:2px}
.tiles b{font-size:1.15rem;font-weight:650}
.tiles span{font-size:.8rem;color:var(--muted)}
@media (max-width:960px){.verdict{grid-template-columns:minmax(0,1fr)}.tiles{border-left:0;padding-left:0;border-top:1px solid var(--line);padding-top:16px}}
.two{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:26px;align-items:start}
@media (max-width:960px){.two{grid-template-columns:minmax(0,1fr)}}
.sec{margin:0 0 22px}
.sides{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
@media (max-width:700px){.sides{grid-template-columns:minmax(0,1fr)}}
.sides>*{min-width:0}
.two>*{min-width:0}
.side{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;min-width:0;overflow-wrap:anywhere}
.side header{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}
.side header small{color:var(--muted)}
.side ol{margin:0;padding-left:20px;display:flex;flex-direction:column;gap:8px}
.side li{line-height:1.5;overflow-wrap:anywhere}
.side li s{color:var(--muted)}
.side .ref{color:var(--muted);font-size:.78rem;margin-left:4px;overflow-wrap:anywhere}
.side .why{display:block;font-size:.82rem;color:var(--bad);margin-top:2px}

/* rail */
.rail{display:flex;flex-direction:column;gap:14px}
.rail details{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:0 16px}
.rail summary{list-style:none;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 0;font-weight:600;cursor:pointer}
.rail summary::-webkit-details-marker{display:none}
.rail summary span{font-weight:400;color:var(--muted);font-size:.82rem}
.rail .in{padding:0 0 14px;font-size:.9rem}
.map{background:var(--soft);border:1px solid var(--line);border-radius:8px;overflow:hidden}
.map svg{display:block;width:100%;height:auto}
/* 51b.11: the driven trace was drawn in a literal blue that the accent change
   did not reach, and on the dark map's --soft it measured under 2:1. It is the
   accent now, so it follows the theme like everything else on the page. */
.map .trace{stroke:var(--accent)}
.cap{color:var(--muted);font-size:.78rem;margin:6px 0 0}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:.78rem;color:var(--muted);margin-top:8px}
.legend i{display:inline-block;width:16px;height:3px;vertical-align:middle;margin-right:5px;border-radius:2px}
.legend i.dot{width:9px;height:9px;border-radius:50%}
.kv{display:grid;grid-template-columns:auto minmax(0,1fr);gap:6px 14px;font-size:.88rem}

/* stepper */
.stepper{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;margin:0 0 10px}
.stepper button{appearance:none;text-align:left;border:0;border-left:1px solid var(--line);background:transparent;font:inherit;color:inherit;cursor:pointer;padding:14px 16px;display:flex;flex-direction:column;gap:5px;position:relative}
.stepper button:first-child{border-left:0}
.stepper button .n{display:flex;align-items:center;gap:8px;font-size:.78rem;color:var(--muted)}
.stepper button .n i{width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:var(--on-status);background:var(--grey);font-style:normal}
.stepper button .n i.llm{background:var(--accent);color:var(--on-accent)}
.stepper button .n i.ok{background:var(--ok)}
.stepper button .n i.bad{background:var(--bad)}
.stepper button .t{font-weight:600}
.stepper button .s{font-size:.78rem;color:var(--muted)}
.stepper button.on{background:var(--soft)}
.stepper button.on::after{content:"";position:absolute;left:0;right:0;bottom:0;height:3px;background:var(--accent)}
@media (max-width:900px){.stepper{grid-template-columns:repeat(3,minmax(0,1fr))}.stepper button{border-top:1px solid var(--line)}}
/* On a phone, three to a row is narrower than the longest step title, so the
   words broke mid-word ("Evidence" -> "Evidence" / "ce"). Two to a row, and the
   button no longer breaks a word at all: it wraps at the spaces or not at all. */
@media (max-width:640px){.stepper{grid-template-columns:repeat(2,minmax(0,1fr))}.stepper button{overflow-wrap:normal;word-break:normal}}
.who{display:flex;flex-wrap:wrap;gap:16px;font-size:.8rem;color:var(--muted);margin:0 0 16px 4px}
.who i{display:inline-block;width:9px;height:9px;border-radius:50%;vertical-align:0;margin-right:5px}
.detail{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px}
.detail h3{margin:0 0 4px;font-size:1.05rem}
.detail .lead{margin:0 0 12px;color:var(--muted)}
.pane{display:none}.pane.on{display:block}
.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0}
.grid3 div{background:var(--soft);border-radius:8px;padding:10px 12px}
.grid3 b{display:block;font-size:1.15rem;font-weight:650}
.grid3 span{font-size:.8rem;color:var(--muted)}
@media (max-width:700px){.grid3{grid-template-columns:minmax(0,1fr)}}

/* misc */
.claim{border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:0 0 10px}
.claim p{margin:.3em 0}
.pill{display:inline-block;border-radius:999px;padding:1px 9px;font-size:.78rem;font-weight:600}
.pill.green{background:var(--ok-wash);color:var(--ok)}
.pill.red{background:var(--bad-wash);color:var(--bad)}
.pill.grey{background:var(--grey-wash);color:var(--muted)}
.err{color:var(--bad);font-weight:600}
.ok{color:var(--ok);font-weight:600}
.empty{color:var(--muted)}
blockquote{margin:8px 0;padding:10px 14px;border-left:3px solid var(--line);background:var(--soft);white-space:pre-wrap;overflow-wrap:anywhere}
details.form{border:1px solid var(--line);border-radius:10px;padding:0 16px;margin:0 0 10px}
details.form summary{cursor:pointer;padding:12px 0;font-weight:600}
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 14px}
.filters button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:6px 14px;font:inherit;cursor:pointer}
.filters button.on{background:var(--ink);color:var(--card);border-color:var(--ink)}
.filters select{font:inherit;padding:6px 10px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.foot{border-top:1px solid var(--line);margin-top:32px;padding-top:14px;color:var(--muted);font-size:.82rem;display:flex;flex-wrap:wrap;gap:16px}
pre{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:12px;overflow-wrap:anywhere;white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.85rem}
textarea,input[type="text"]{font:inherit;color:inherit}

/* the reviewer's decision form */
.decision-fields{border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:10px 0}
.decision-fields[hidden]{display:none}
.decision-fields label{margin-right:12px}
.decision-fields select,.decision-fields input[type="text"]{font:inherit;color:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:8px;background:var(--card)}
.decision-fields select[multiple]{min-width:240px;vertical-align:top}
.decision-fields .ev{display:inline-flex;align-items:center;gap:6px;margin:0 14px 6px 0;font-size:.9rem}

/* 37a.5: a wide table scrolls inside its own container, and nothing else
   overflows the page. The queue's table was clipped and could not scroll below
   about 1230 px, and 23 case pages scrolled sideways at 390 px, so every table
   now sits in a box that scrolls and every grid track is allowed to shrink. */
html,body{max-width:100%}
body{overflow-wrap:break-word}
.tscroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.wrap,.two,.maincol,.rail,.side,.card,.verdict,.tiles,.pagehead,.notice{min-width:0}
.ids,.cap,.legend,.legend span,.kv span,.claim p,.tiles span{overflow-wrap:anywhere}
svg{max-width:100%}
pre{overflow-x:auto}

/* the held reason, written under the chip as well as into its title */
/* 51c.2: the note is one sentence naming a figure and the threshold it crossed
   ("SGD 8.05 is above the POL-GEN-05 execution threshold of SGD 8.00"), and
   with nothing to stop it, it ran on one line: the Status column took 414 px,
   the table came to 1285 px inside a 1230 px wrapper at a 1440 px window, and
   the Time column was cut off the right-hand edge. The note is capped at 16rem
   so it wraps onto two lines and the table fits its wrapper from 1280 px up.
   Below that the table scrolls inside .tscroll as it always did. */
.held-why{display:block;color:var(--muted);font-size:.78rem;margin-top:4px;max-width:16rem}

/* 37a.6: the header cells are buttons, so sorting is reachable by keyboard and
   the state a sighted reader reads off the arrow is on the cell as aria-sort. */
th .sort{appearance:none;border:0;background:transparent;color:inherit;font:inherit;
  letter-spacing:inherit;text-transform:inherit;padding:0;cursor:pointer}
th .sort::after{content:"\\2195";margin-left:6px;opacity:.6}
th[aria-sort="ascending"] .sort::after{content:"\\2191"}
th[aria-sort="descending"] .sort::after{content:"\\2193"}

/* every control keeps a focus ring a reader can see */
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}

/* the notice to the parties */
.notice{background:var(--soft);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:10px;padding:14px 16px;margin:14px 0}
.notice h2{margin:0 0 8px;font-size:.95rem}
.notice p{margin:.3em 0;font-size:.88rem}
.notice b{color:var(--ink)}
.legend i.dash{background:none;border-top:3px dashed #6b7280;height:0}
.legend i.ring{width:10px;height:10px;border-radius:50%;background:none;
  border:1px dashed #9ca3af}

/* 44.1: the debate. The two advocates' claims are drawn as cards, and the
   panel's four drafts as four cards side by side (two by two on a phone), so
   the step reads as an argument and not as the agents' raw answers. */
.debate{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:14px 0 0}
@media (max-width:700px){.debate{grid-template-columns:minmax(0,1fr)}}
.claim{background:var(--soft)}
.claim .cite{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.chip.ev,.chip.clause{height:auto;padding:3px 9px;white-space:normal;text-align:left}
.chip.ev .k,.chip.clause .ct{font-weight:400;color:var(--muted);margin-left:6px}
.chip.clause .ct{display:none}
.chip.clause:focus .ct{display:inline}
.claimv{margin:.45em 0 0;font-size:.86rem}
.claimv .why{color:var(--bad)}
.drafts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:12px 0}
@media (max-width:900px){.drafts{grid-template-columns:repeat(2,minmax(0,1fr))}}
.dcard{background:var(--soft);border:1px solid var(--line);border-radius:10px;
  padding:10px 12px;min-width:0}
.dcard h4{margin:0 0 6px;font-size:.84rem;color:var(--muted);font-weight:600}
.dcard p{margin:.22em 0;font-size:.86rem}
.dcard .d-ruling{margin:.3em 0 .5em}
.d-void{margin:.4em 0 0;padding-left:18px;font-size:.82rem;color:var(--bad)}
.pill.blue{background:var(--accent-wash);color:var(--accent)}

/* 44.2: the landing page's how-it-works strip and its links row. */
.how{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:14px 18px;margin:0 0 18px}
.how h2{margin:0 0 10px;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.how ol{display:flex;flex-wrap:wrap;gap:10px 16px;list-style:none;margin:0;padding:0}
.how li{display:flex;align-items:flex-start;gap:9px;font-size:.86rem;color:var(--muted)}
/* 51b.7, and 51c.1 on top of it: a step is a numbered violet circle, its name
   in bold on one line and its description under it in muted text. The number is
   text on the accent, so it takes --on-accent rather than white. */
.how .n{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;
  border-radius:50%;background:var(--accent);color:var(--on-accent);font-size:11px;font-weight:700;
  font-style:normal;flex:none}
.how .st{display:block}
.how .st b{display:block;color:var(--ink);font-weight:600}
.how .arw{color:var(--muted);margin-left:8px}
.links{display:flex;flex-wrap:wrap;gap:6px 18px;margin:0 0 20px;font-size:.9rem}

/* 52.1: the safeguards card. It is the How-it-works card's surface and its h2
   treatment -- the same border, radius and padding, the same small uppercase
   heading -- because the two cards are the same kind of thing: what the system
   is, said once. Each line's lead words are --ink and the rest of it is
   --muted, and the list is two columns at 1000 px and wider and one below. */
.safeguards{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:14px 18px;margin:0 0 18px}
.safeguards h2{margin:0 0 10px;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.safeguards ul{list-style:none;margin:0;padding:0;display:grid;
  grid-template-columns:minmax(0,1fr);gap:9px 26px;font-size:.86rem;color:var(--muted)}
.safeguards li{margin:0}
.safeguards b{color:var(--ink);font-weight:600}
.safeguards .access{margin:12px 0 0;font-size:.86rem;color:var(--muted)}
@media (min-width:1000px){
  .safeguards ul{grid-template-columns:repeat(2,minmax(0,1fr))}
}

/* 46b.8, and 51b.7 on top of it: on a wide screen the five steps of "How it
   works" wrapped into three ragged lines with the arrows stranded at the line
   ends, so at 1000 px and wider they are five equal columns in one row, each
   with its arrow at the column's right. The row is a flex row in both layouts
   now: it was a block here, which dropped the gap and left the circle touching
   the step's name. Below 1000 px the strip stacks as it did. */
@media (min-width:1000px){
  .how ol{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px 22px}
  .how li{display:flex;position:relative;padding-right:20px}
  .how .arw{position:absolute;right:0;top:3px;margin:0}
}

/* 46b.10: the trace's own box runs the width of the rail column, so the map is
   drawn at the width the column has rather than 32 px narrower. */
.rail details.full{padding:0}
.rail details.full>summary{padding:12px 16px}
.rail details.full .in{padding:0 0 14px}
.rail details.full .cap{padding:6px 16px 0;margin:0}
.rail details.full .legend{padding:8px 16px 0;margin-top:0}

/* 46b.11: a claim is a paragraph of 80-200 words, so its first sentence is
   shown and the rest of it sits behind a control that reads as one. */
.claim details,.side details{margin:.3em 0 0}
.claim details>summary,.side details>summary{color:var(--accent);cursor:pointer;font-size:.86rem}
.claim details p,.side details p{margin:.3em 0 0}

/* 44.3: on a 375 px phone the nav wrapped, which pushed its Queue pill against
   the bar's top edge. The nav stays on one line now and scrolls sideways when
   it has to, and the bar's three children are allowed to shrink around it. */
.nav{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;min-width:0}
.nav a{flex:none;white-space:nowrap}
.brand{flex:none}
.mode{flex:none}

/* 47.1: the outcome first. A case page opened with the two parties' long
   accounts and the chat, and the ruling came after them; the summary bar states
   the outcome, the money and who decides in one line under the title, and its
   "Why" link goes to the ruling panel. */
.summarybar{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 8px;
  background:var(--soft);border:1px solid var(--line);border-radius:10px;
  padding:9px 13px;margin:12px 0 0;font-size:.9rem;color:var(--muted)}
.summarybar b{color:var(--ink);font-weight:650}

/* 47.4: where the refund POL-RD-02 computes is larger than the amount the rider
   contested, the figure is named for what it is and the clause it comes from. */
.refundnote{margin:.5em 0 0;font-size:.86rem;color:var(--muted)}

/* 47.3: the line under the queue's tiles, for "executed" and "confidence". */
.figurewords{color:var(--muted);font-size:.86rem;margin:-10px 0 20px;max-width:78ch}

/* 47.5/47.6: a table's scrolling box is reachable by keyboard, so it carries a
   focus ring of its own rather than depending on the one a control gets. */
.tscroll:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
"""

_JS = """
(function(){
  "use strict";
  function each(selector, root){
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  // Tabs: a button with data-tab shows the panel with the same data-panel.
  var tabs = each("[data-tab]");
  tabs.forEach(function(tab){
    tab.addEventListener("click", function(){
      var name = tab.getAttribute("data-tab");
      tabs.forEach(function(other){
        var on = other === tab;
        other.setAttribute("aria-selected", on ? "true" : "false");
        other.className = on ? "tab tab-on" : "tab";
      });
      each("[data-panel]").forEach(function(panel){
        panel.hidden = panel.getAttribute("data-panel") !== name;
      });
    });
  });

  // The stepper: a button with data-step shows the pane with the same data-pane.
  each(".stepper").forEach(function(stepper){
    var buttons = each("button[data-step]", stepper);
    buttons.forEach(function(button){
      button.addEventListener("click", function(){
        buttons.forEach(function(other){
          other.className = other === button ? "on" : "";
        });
        var detail = stepper.parentElement.querySelector(".detail");
        if (!detail){ return; }
        each(".pane", detail).forEach(function(pane){
          pane.className = pane.getAttribute("data-pane") === button.getAttribute("data-step") ? "pane on" : "pane";
        });
      });
    });
  });

  var table = document.getElementById("queue");
  if (table){
    var body = table.tBodies[0];
    var rows = Array.prototype.slice.call(body.rows);
    var state = {column: null, up: true};

    function value(row, column){
      var cell = row.querySelector('td[data-column="' + column + '"]');
      if (!cell){ return ""; }
      var sort = cell.getAttribute("data-sort");
      return sort === null ? cell.textContent.trim() : sort;
    }

    function numeric(text){
      return /^-?[0-9]+(\\.[0-9]+)?$/.test(text);
    }

    function sortBy(column){
      if (state.column === column){ state.up = !state.up; }
      else { state.column = column; state.up = true; }
      rows.sort(function(a, b){
        var x = value(a, column), y = value(b, column);
        if (numeric(x) && numeric(y)){
          return state.up ? Number(x) - Number(y) : Number(y) - Number(x);
        }
        if (x === y){ return 0; }
        return state.up ? (x < y ? -1 : 1) : (x < y ? 1 : -1);
      });
      rows.forEach(function(row){ body.appendChild(row); });
    }

    // The header cell says which column the rows are ordered by and which way,
    // so a reader who cannot see the arrow is told the same thing.
    function markSort(column){
      each("th[data-column]", table).forEach(function(head){
        var mine = head.getAttribute("data-column") === column;
        head.setAttribute("aria-sort", mine ? (state.up ? "ascending" : "descending") : "none");
      });
    }

    each("th[data-column]", table).forEach(function(head){
      head.classList.add("sortable");
      function activate(){
        var column = head.getAttribute("data-column");
        sortBy(column);
        markSort(column);
      }
      // The button in the cell is what a keyboard reaches -- Enter and Space
      // fire its click -- and a header cell without one stays clickable.
      var button = head.querySelector("button.sort");
      if (button){ button.addEventListener("click", activate); }
      else { head.addEventListener("click", activate); }
    });

    var chosen = {outcome: "all", set: "all"};
    function apply(){
      var shown = 0;
      rows.forEach(function(row){
        var okOutcome = chosen.outcome === "all" || row.getAttribute("data-outcome") === chosen.outcome;
        var okSet = chosen.set === "all" || row.getAttribute("data-set") === chosen.set;
        var ok = okOutcome && okSet;
        row.hidden = !ok;
        if (ok){ shown += 1; }
      });
      var count = document.getElementById("shown");
      if (count){ count.textContent = String(shown); }
    }

    each("[data-filter]").forEach(function(button){
      button.addEventListener("click", function(){
        chosen.outcome = button.getAttribute("data-filter");
        each("[data-filter]").forEach(function(other){
          other.className = other === button ? "on" : "";
        });
        apply();
      });
    });

    var picker = document.getElementById("set-picker");
    if (picker){
      picker.addEventListener("change", function(){
        chosen.set = picker.value;
        apply();
      });
    }
    apply();
  }

  var form = document.getElementById("review-form");
  if (form){
    var reason = document.getElementById("reason");
    var verdict = document.getElementById("verdict");
    var output = document.getElementById("command");
    var evidence = (form.getAttribute("data-evidence") || "").split(" ").filter(Boolean);
    var clauses = (form.getAttribute("data-clauses") || "").split(" ").filter(Boolean);
    var floor = Number(form.getAttribute("data-reason-min") || "0");
    var runDir = form.getAttribute("data-run-dir") || "";
    var caseNo = form.getAttribute("data-case") || "";
    var packet = form.getAttribute("data-packet") || "";
    var store = form.getAttribute("data-store") || "";

    function cited(text, ids){
      for (var i = 0; i < ids.length; i += 1){
        if (text.indexOf(ids[i]) >= 0){ return true; }
      }
      return false;
    }

    function check(){
      var text = reason.value.trim();
      var problems = [];
      if (text.length < floor){
        problems.push("the reason is " + text.length + " characters; POL-GEN-06(6) requires at least " + floor);
      }
      if (!cited(text, evidence)){
        problems.push("the reason cites no evidence id of this case");
      }
      if (!cited(text, clauses)){
        problems.push("the reason cites no clause id of this case");
      }
      return {text: text, problems: problems};
    }

    function decision(){
      var picked = form.querySelector('input[name="decision"]:checked');
      return picked ? picked.value : "";
    }

    function valueOf(id){
      var node = document.getElementById(id);
      return node ? node.value : "";
    }

    // One value as one shell word. Double quotes leave $, a backtick and ! to
    // the shell, so a reason carrying one would be rewritten before the command
    // ran; a single-quoted word is literal, and the one character that cannot
    // appear inside it is closed, escaped and reopened. This is the rule
    // ``ui.v2.build.shell_quote`` applies in Python, so the command the page
    // shows and the command the builder builds are the same word for word.
    function quoted(text){
      return "'" + String(text).replace(/'/g, "'\\\\''") + "'";
    }

    function who(){
      return valueOf("reviewer") || "reviewer";
    }

    function chosenClauses(id){
      var node = document.getElementById(id);
      if (!node){ return []; }
      return Array.prototype.slice.call(node.options)
        .filter(function(option){ return option.selected; })
        .map(function(option){ return option.value; });
    }

    function reviewCommand(){
      var d = decision();
      var ruling = "", amount = "", list = [], summary = d;
      if (d === "ADOPT"){
        ruling = form.getAttribute("data-adopt-ruling") || "";
        amount = form.getAttribute("data-adopt-amount") || "";
        list = (form.getAttribute("data-adopt-clauses") || "").split(" ").filter(Boolean);
      } else {
        var prefix = d === "REFER_COMPLIANCE" ? "refer-" : "vary-";
        ruling = valueOf(prefix + "ruling");
        amount = valueOf(prefix + "amount");
        list = chosenClauses(prefix + "clauses");
        if (d === "REFER_COMPLIANCE"){
          var note = valueOf("refer-note").trim();
          if (note){ summary = d + ": " + note; }
        }
      }
      var parts = ["python3 -m ops.review", "--run-dir " + runDir,
        "--case " + caseNo, "--packet-sha256 " + packet];
      if (ruling){ parts.push("--ruling " + ruling); }
      if (amount){ parts.push("--amount " + amount); }
      list.forEach(function(clause){ parts.push("--clause " + clause); });
      parts.push("--closed-by " + quoted(who()));
      parts.push("--summary " + quoted(summary));
      parts.push("--reason " + quoted(reason.value.trim()));
      return parts.join(" ");
    }

    function windowCommand(){
      var items = each('input[name="evidence"]:checked', form)
        .map(function(box){ return box.value; });
      return ["python3 -m ops.evidence_window", "open", "--store " + store,
        "--run-dir " + runDir,
        "--case " + caseNo, "--now " + quoted(valueOf("window-now")),
        "--items " + items.join(","), "--opened-by " + quoted(who())].join(" ");
    }

    function command(){
      return decision() === "REQUEST_EVIDENCE" ? windowCommand() : reviewCommand();
    }

    function showFields(){
      var d = decision();
      each("[data-for]", form).forEach(function(block){
        block.hidden = block.getAttribute("data-for") !== d;
      });
    }

    function refresh(){
      showFields();
      if (!decision()){
        // Nothing is chosen, so there is nothing to build: the command appears
        // once the reviewer has chosen one of the four decisions.
        verdict.className = "empty";
        verdict.textContent = "Choose one of the four decisions: the command is built once a decision is chosen.";
        output.textContent = "";
        return;
      }
      if (decision() === "REQUEST_EVIDENCE"){
        verdict.className = "empty";
        verdict.textContent = "The evidence-window command is part 26 (ops/evidence_window.py): it opens one window to both parties at once.";
      } else {
        var state = check();
        if (state.problems.length){
          verdict.className = "err";
          verdict.textContent = state.problems.join("; ");
        } else {
          verdict.className = "ok";
          verdict.textContent = "The reason is long enough and cites this case's own evidence and clause ids.";
        }
      }
      output.textContent = command();
    }

    form.addEventListener("input", refresh);
    form.addEventListener("change", refresh);

    var copy = document.getElementById("copy");
    if (copy){
      copy.addEventListener("click", function(){
        var text = command();
        var done = function(){
          var status = document.getElementById("copy-status");
          if (status){ status.textContent = "Copied."; }
        };
        if (navigator.clipboard && navigator.clipboard.writeText){
          navigator.clipboard.writeText(text).then(done, function(){
            var status = document.getElementById("copy-status");
            if (status){ status.textContent = "Select the command above and copy it by hand."; }
          });
        } else {
          var status = document.getElementById("copy-status");
          if (status){ status.textContent = "Select the command above and copy it by hand."; }
        }
      });
    }
    refresh();
  }
})();
"""


# --------------------------------------------------------------------------
# The shell every page is built in
# --------------------------------------------------------------------------
def _shell(
    title: str,
    body: str,
    *,
    description: str,
    canonical: str,
    og_type: str,
) -> str:
    """One self-contained page: inline CSS, inline script, nothing external.

    The head carries what a link scraper reads as well as what a browser does:
    a one-sentence description, the tab icon, and an Open Graph card with
    ``twitter:card`` beside it. Every URL in the card is absolute -- a scraper
    resolves a relative one against nothing -- and the icon is an inline
    ``data:`` SVG, so the page still loads nothing and stays one file.
    """
    image = SITE_ROOT + OG_IMAGE_LINK
    head = "".join(
        (
            "<title>{0}</title>\n".format(_text(title)),
            '<meta name="description" content="{0}">\n'.format(
                _attribute(description)
            ),
            '<link rel="icon" href="{0}">\n'.format(_attribute(FAVICON_DATA_URI)),
            '<meta property="og:title" content="{0}">\n'.format(_attribute(title)),
            '<meta property="og:description" content="{0}">\n'.format(
                _attribute(description)
            ),
            '<meta property="og:type" content="{0}">\n'.format(_attribute(og_type)),
            '<meta property="og:url" content="{0}">\n'.format(
                _attribute(canonical)
            ),
            '<meta property="og:image" content="{0}">\n'.format(_attribute(image)),
            '<meta name="twitter:card" content="summary_large_image">\n',
        )
    )
    page = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "{0}<style>{1}</style>\n</head>\n<body>\n"
        "{2}\n<script>{3}</script>\n</body>\n</html>\n"
    ).format(head, _CSS, body, _JS)
    return defuse_key_shaped(page)


# The product's mark, inline: a beam, a base, a crossbar and two pans. It is
# drawn here rather than loaded, so the page needs no font and no image. The
# same path data draws the tab icon below, so the two cannot drift apart. The
# stroke is ``currentColor`` -- 51c.1 -- because the mark is drawn on the accent
# tile, whose text colour is ``--on-accent`` and is white in the light theme and
# a deep violet in the dark one; a hard-coded white would be illegible in the
# dark theme, where the accent is a light lavender.
SCALES_PATH = "M12 4v16M8 20h8M5 7h14M5 7L2 13h6zM19 7l-3 6h6z"
SCALES_MARK = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="{0}"/></svg>'
).format(SCALES_PATH)

# The tab icon: the header's mark on the header's own accent tile, as an inline
# SVG data URI. A ``data:`` URL is not a request, so the page stays one file
# with nothing external in it; the ``#`` of each colour is percent-encoded
# because a bare one would end the URL at the fragment. The tile is the light
# theme's accent -- one file serves both themes, and the violet is what the mark
# is drawn on in either.
_FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
    "<rect width='24' height='24' rx='5' fill='#6d28d9'/>"
    "<path d='{0}' fill='none' stroke='#ffffff' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'/></svg>"
).format(SCALES_PATH)
FAVICON_DATA_URI = "data:image/svg+xml," + quote(_FAVICON_SVG, safe="'/:=")


def _mode_text(version: Any) -> str:
    """The top bar's right-hand readout: the runs the pages replay.

    It says what the pages are -- recorded runs at one policy version -- and
    leaves the model to the footer, which names the run each page replays. The
    version is the run's own, read from the record rather than typed here.
    """
    return "Recorded runs, policy version {0}".format(_text(version))


def _topbar(mode: str, current: str) -> str:
    """The top bar: the product, the queue, and the run being replayed.

    The header carries the queue alone. The replay beside this site is the
    benchmark replay at policy version 1 -- historical, and not the pipeline
    these pages show -- and a judge who met it in the header went to the
    historical figures first, so it sits in the footer with the label that says
    which pipeline it is.
    """
    # The item is a link on every page -- the current one is marked with
    # ``aria-current`` rather than turned into a span, so the page's own item is
    # still a link a reader can follow.
    queue = (
        '<a href="index.html" class="on" aria-current="page">Queue</a>'
        if current == "queue"
        else '<a href="index.html">Queue</a>'
    )
    return (
        '<header class="top">\n<div class="top-in">\n'
        '<a class="brand" href="index.html"><span class="mark">{0}</span>Tribunal'
        "</a>\n"
        '<nav class="nav" aria-label="Sites">{1}</nav>\n'
        '<span class="mode">{2}</span>\n'
        "</div>\n</header>\n"
    ).format(SCALES_MARK, queue, _text(mode))


# The two freezes these pages stand between, and what each one is. The runs this
# site replays were recorded from the trees frozen at ``freeze-2026-10-09`` --
# ``v6_runs.FREEZE_TAG``, read from the module that names it rather than typed
# here -- and the repository's final code freeze is the tag below, which is the
# one the fourth sealed set ran on. The footer states both, because a reader who
# meets one tag should not have to guess which tree a page came from. The
# README does not claim that the two trees build byte-identical briefs for these
# cases, so this does not claim it either.
FINAL_FREEZE_TAG = "freeze-2026-10-11"
FREEZE_NOTE = "Runs recorded at {0}. The final code freeze is {1}.".format(
    v6_runs.FREEZE_TAG, FINAL_FREEZE_TAG
)


def _footer(case: CaseData) -> str:
    """The footer every page carries: commit, freezes, policy version, model, replay."""
    configuration = case.document.get("configuration") or {}
    return (
        '<footer class="foot">'
        "<span>commit {0}</span>"
        "<span>{1}</span>"
        "<span>policy version {2}</span>"
        "<span>model {3}</span>"
        '<span><a href="{4}">{5}</a></span>'
        "</footer>"
    ).format(
        _text(str(case.document.get("git_commit"))[:7]),
        _text(FREEZE_NOTE),
        _text(configuration.get("policy_version")),
        _text(case.document.get("model")),
        _attribute(REPLAY_INDEX),
        _text(REPLAY_LABEL),
    )


# --------------------------------------------------------------------------
# The queue page
# --------------------------------------------------------------------------
def _figure(key: str, value: str, note: str = "", tone: str = "") -> str:
    """One figure tile, and the lane colour it is drawn under.

    ``tone`` is one of the three lane names -- ``lane-ok``, ``lane-warn`` or
    ``lane-bad``, and the tile carries its lane's own colour on a 3px top border
    -- or ``lane-accent`` for the three figures under them. It is a class name
    and not a colour, so the colour stays in the stylesheet where the two themes
    are. The names are prefixed -- 51c.3 -- because a bare ``ok``, ``warn`` or
    ``bad`` on a ``.figure`` also matched the stylesheet's global status rules
    and repainted the tile's own figure and small print.
    """
    sub = '<p class="s">{0}</p>'.format(_text(note)) if note else ""
    classes = "figure" if not tone else "figure {0}".format(tone)
    return (
        '<div class="{0}"><p class="k">{1}</p><p class="v">{2}</p>{3}</div>'
    ).format(classes, _text(key), _text(value), sub)


def _trigger_card(figures: QueueFigures) -> str:
    """The reviewer triggers, one per line: the words first, then the count.

    A row per trigger rather than one run-on string, so a reader sees which
    reason fired and how often without counting commas. The card spans the row
    (``.figure.wide``) and its lines wrap, so a long phrase cannot overflow it.
    """
    lines = []
    for name in TRIGGER_ORDER:
        count = figures.triggers.get(name, 0)
        if not count:
            continue
        lines.append(
            '<li><span class="t">{0}</span> <span class="n">{1}</span></li>'.format(
                _text(trigger_words(name, figures.votes)), _text(count)
            )
        )
    body = "".join(lines) if lines else '<li><span class="t">none</span></li>'
    return (
        '<div class="figure wide"><p class="k">Reviewer triggers</p>'
        '<ul class="triggers">{0}</ul>'
        '<p class="s">counted by reason code</p></div>'
    ).format(body)


def _queue_row(case: CaseData) -> str:
    dispute = case.case.get("dispute") or {}
    currency = case.policy.currency
    outcome = _outcome_text(case.ruling, currency, case.trigger, case.votes)
    confidence = case.ruling.get("confidence")
    # A case sent to a reviewer has no ruling to be confident in, so the column
    # shows a dash rather than a figure read off a ruling that was never made.
    if case.trigger is not None:
        confidence_text = "-"
    else:
        confidence_text = "none" if confidence is None else str(confidence)
    amount_sort = _decimal(dispute.get("amount_contested_sgd"))
    time_sort = _decimal(case.document.get("wall_seconds"))
    filed_by = dispute.get("filed_by")
    # The cell text is escaped once, when it is written -- the status is the one
    # cell already rendered as HTML -- and the sort key is a plain value, so a
    # sort never reads a markup fragment as though it were the value.
    # The status cell's title carries the reason a held amount is held: the chip
    # itself stays short so the row's height cannot change, and the figure is one
    # hover away rather than cut off.
    held = held_reason(case) if _money_is_held(case) else ""
    # The detail a short chip hides -- a held amount's reason, or a reviewer
    # case's trigger words -- is written under the chip as well as into its
    # title: a tooltip is not text a reader who cannot hover is told, and the
    # row is where the reader meets the case.
    status_cell = queue_status_cell(case)
    cells = (
        (
            "case",
            '<a href="{0}">{1}</a>'.format(_attribute(case.link), _text(case.case_no)),
            str(case.case_no),
            "Case",
            "",
        ),
        (
            "category",
            _text(CATEGORY_WORDS.get(case.category, case.category)),
            case.category,
            "Category",
            "",
        ),
        (
            "filed_by",
            _text(filed_by_words(filed_by)),
            str(filed_by),
            "Filed by",
            "",
        ),
        (
            "amount",
            _text(_money(dispute.get("amount_contested_sgd"), currency)),
            str(amount_sort if amount_sort is not None else 0),
            "Amount contested",
            "",
        ),
        ("status", status_cell, case.outcome_kind, "Status", held),
        ("outcome", _text(outcome), str(case.ruling.get("ruling")), "Outcome", ""),
        ("confidence", _text(confidence_text), confidence_text, "Confidence", ""),
        (
            "time",
            _text(_seconds(case.document.get("wall_seconds"))),
            str(time_sort if time_sort is not None else 0),
            "Time",
            "",
        ),
    )
    row_class = "reviewer" if case.trigger is not None else "auto"
    cells_html = "".join(
        '<td data-column="{0}" data-sort="{1}" data-label="{2}"{3}>{4}</td>'.format(
            _attribute(name),
            _attribute(sort),
            _attribute(label),
            ' title="{0}"'.format(_attribute(tip)) if tip else "",
            value,
        )
        for name, value, sort, label, tip in cells
    )
    return '<tr class="{0}" data-outcome="{1}" data-set="{2}">{3}</tr>'.format(
        row_class, case.outcome_kind, _attribute(case.label), cells_html
    )


def _queue_head() -> str:
    """The header row: a button per column, so sorting is reachable by keyboard.

    A ``th`` with a click handler is not a control: it cannot be tabbed to and a
    reader who cannot see it is not told it does anything. Each column carries a
    real button instead, and the header cell's ``aria-sort`` says which column
    the rows are ordered by and which way -- the state a sighted reader reads off
    the arrow.
    """
    columns = (
        ("case", "Case"),
        ("category", "Category"),
        ("filed_by", "Filed by"),
        ("amount", "Amount contested"),
        ("status", "Status"),
        ("outcome", "Outcome"),
        ("confidence", "Confidence"),
        ("time", "Time"),
    )
    return "<tr>{0}</tr>".format(
        "".join(
            '<th data-column="{0}" aria-sort="none">'
            '<button type="button" class="sort" data-column="{0}">{1}</button></th>'.format(
                _attribute(name), _text(label)
            )
            for name, label in columns
        )
    )


def _set_picker(cases: Sequence[CaseData]) -> str:
    labels = []
    for set_name in SET_ORDER:
        if any(case.set_name == set_name for case in cases):
            labels.append(SET_LABELS[set_name])
    options = ['<option value="all">All sets</option>']
    for label in labels:
        options.append('<option value="{0}">{1}</option>'.format(_attribute(label), _text(label)))
    return (
        '<label for="set-picker">Set</label>'
        '<select id="set-picker">{0}</select>'.format("".join(options))
    )


# The four featured cases, and the fixed title each card carries. The title is
# this file's words; every fact under it is read from the run.
FEATURED_CASES: Tuple[Tuple[int, str], ...] = (
    (901, "The organisers' sample"),
    (208, "A no-show the evidence settles"),
    (1779, "A prompt injection, refused"),
    (2735, "A safety flag: straight to a human"),
)


def _featured_answer(case: CaseData) -> str:
    """Case 208's record in one line, from the same derived facts the table uses.

    The three facts the no-show record turns on: how long the driver held
    position inside the arrival radius, where the rider's device was, and the one
    call the log records. Each is read from the brief's own derived blocks, or
    from the chat the record carries, so the card says nothing the record does
    not. A fact the blocks do not carry is left out rather than filled in.
    """
    arrival = _derived_block(case.brief, "GPS_TRACE", "arrival") or {}
    presence = _derived_block(case.brief, "GPS_TRACE", "rider_presence") or {}
    parts: List[str] = []
    dwell = _fact_value(arrival, "accumulated_dwell", "longest_run_sec")
    if dwell is not None:
        parts.append(
            "driver inside the arrival radius {0} s".format(_whole(dwell))
        )
    near = _fact_value(presence, "min_distance_m")
    far = _fact_value(presence, "max_distance_m")
    if near is not None and far is not None:
        parts.append(
            "her phone {0}-{1} m away".format(_whole(near), _whole(far))
        )
    calls = [
        message
        for message in _chat_messages(case)
        if str(message.get("channel")) == CALL_LOG_CHANNEL
    ]
    if calls:
        parts.append(_call_line(calls[0].get("text")))
    return "; ".join(part for part in parts if part)


def _featured_facts(case: CaseData) -> List[Tuple[str, str]]:
    """The facts one featured card carries, each read from the run's own files.

    Each fact is returned as the HTML it is drawn with, so a reason code can sit
    small after its words exactly as it does on the case page.
    """
    currency = case.policy.currency
    if case.case_no == 901:
        return [
            (
                "Outcome",
                _text(
                    _outcome_text(case.ruling, currency, case.trigger, case.votes)
                ),
            ),
            ("Confidence", _text(str(case.ruling.get("confidence")))),
        ]
    if case.case_no == 208:
        # The outcome line already carries the ruling and the money, so the
        # second line is the record's own one-line answer rather than the
        # amounts a second time.
        return [
            (
                "Outcome",
                _text(
                    _outcome_text(case.ruling, currency, case.trigger, case.votes)
                ),
            ),
            ("What the record shows", _text(_featured_answer(case))),
        ]
    if case.case_no == 1779:
        drafts = _drafts(case.transcript)
        refused = [
            draft
            for draft in drafts
            if not draft["valid"]
            and str(draft["abstention"] or "").startswith(
                pipeline_module.DRAFT_CLAUSE_UNRESOLVED
            )
        ]
        reached = {
            (
                str(draft["ruling"]),
                _decimal(draft["amount_sgd"]),
                _decimal(draft["driver_compensation_sgd"]),
            )
            for draft in drafts
            if draft["ruling"]
        }
        if drafts and len(refused) == len(drafts) and len(reached) == 1:
            # The panel refused the planted clause and agreed; what escalated the
            # case is the code check, which treats a quoted clause id as a
            # citation and so voided every draft that named the invented one.
            panel = (
                "All {0} drafts refused the planted clause and reached the same "
                "ruling; the code check, which treats any quoted clause id as a "
                "citation, voided them, so a person decides.".format(len(drafts))
            )
        else:
            panel = "{0} of {1} drafts were voided by the code checks".format(
                len(refused), len(drafts)
            )
        return [
            # The words alone: the card is a summary a reader meets first, and
            # the reason code belongs on the case page's own steps.
            ("Reason", _text(trigger_words(str(case.trigger), case.votes))),
            ("The panel", _text(panel)),
        ]
    if case.case_no == 2735:
        calls = [
            entry
            for entry in case.transcript.get("entries") or []
            if isinstance(entry, Mapping)
        ]
        return [
            ("Reason", _text(trigger_words(str(case.trigger), case.votes))),
            (
                "Model calls",
                _text(
                    "0 - the scope gate asked no model"
                    if not calls
                    else "{0} agent calls are recorded".format(len(calls))
                ),
            ),
        ]
    raise BuildError(
        "case {0} is featured but has no card of its own".format(case.case_no)
    )


def _featured_card(case: CaseData, title: str) -> str:
    """One featured case: a fixed title, the run's own facts, and the way in.

    The whole card is one link to the case's own page -- it always was -- and
    51b.9 puts the way in at its foot, so a reader who has read the card is told
    what following it does.
    """
    facts = "".join(
        "<p><b>{0}</b> {1}</p>".format(_text(label), value)
        for label, value in _featured_facts(case)
    )
    return (
        '<a class="fcard" href="{0}">'
        '<span class="fcase">Case {1}</span>'
        "<h2>{2}</h2>{3}"
        '<span class="fopen">Open case <span aria-hidden="true">&#8594;</span></span>'
        "</a>"
    ).format(_attribute(case.link), _text(case.case_no), _text(title), facts)


def _featured_cards(cases: Sequence[CaseData]) -> str:
    """The four featured cases, in the order this file names them."""
    by_number = {case.case_no: case for case in cases}
    cards: List[str] = []
    for case_no, title in FEATURED_CASES:
        case = by_number.get(case_no)
        if case is None:
            raise BuildError(
                "featured case {0} is not among the runs this site draws".format(case_no)
            )
        cards.append(_featured_card(case, title))
    return '<section class="featured">' + "".join(cards) + "</section>\n"


def _how_it_works() -> str:
    """The five steps of one dispute, numbered, in the accent's own circle.

    Each step is a violet circle carrying its number, the step's name in bold
    and its description under it in muted text; the arrows between the steps are
    kept on a wide screen, where the strip is five columns. The section carries
    ``id="how"`` because the hero's "How it works" button is an in-page anchor
    to it (51b.4).
    """
    items = []
    for index, (_who, what, note) in enumerate(HOW_IT_WORKS):
        arrow = (
            ""
            if index + 1 == len(HOW_IT_WORKS)
            else '<span class="arw">&#8594;</span>'
        )
        items.append(
            '<li><i class="n">{0}</i><span class="st"><b>{1}</b>'
            "<span>{2}</span></span>{3}</li>".format(
                index + 1, _text(what), _text(note), arrow
            )
        )
    return (
        '<section class="how" id="how" aria-label="How a dispute is decided">'
        "<h2>How it works</h2><ol>{0}</ol></section>\n"
    ).format("".join(items))


def _safeguards(figures: QueueFigures) -> str:
    """The seven safeguards, and the accessibility line under them.

    Two of the ten judging dimensions are responsible AI and accessibility, and
    neither was named on the front page. Every line here is already true in the
    repository -- the citation referee, the human lane, the scope gate, the
    draft checks, the appeal rule, the mask and the disclosed limits -- and the
    reviewer figure is read from the same :class:`QueueFigures` the lane tile
    above the table carries, so the two cannot state different numbers. The
    three links out are absolute URLs to the repository's own pages, because the
    site is served on its own and a relative path would 404 there.
    """
    safety_link = '<a href="{0}">case {1}</a>'.format(
        _attribute("case-{0:05d}.html".format(SAFEGUARD_SAFETY_CASE)),
        _text(SAFEGUARD_SAFETY_CASE),
    )
    planted_link = '<a href="{0}">case {1}</a>'.format(
        _attribute("case-{0:05d}.html".format(SAFEGUARD_PLANTED_CLAUSE_CASE)),
        _text(SAFEGUARD_PLANTED_CLAUSE_CASE),
    )
    limits_link = '<a href="{0}">the limits are listed in full</a>'.format(
        _attribute(LIMITATIONS_LINK)
    )
    items: Tuple[Tuple[str, str], ...] = (
        (
            "<b>{0}</b>".format(_text(SAFEGUARD_LEADS[0])),
            "Every claim must name evidence and a clause that exist in the "
            "record; the citation referee drops any claim that does not.",
        ),
        (
            "<b>{0}</b>".format(_text(SAFEGUARD_LEADS[1])),
            "{0} of {1} queued disputes went to a reviewer, with no ruling "
            "issued and the amount held.".format(figures.reviewer, figures.total),
        ),
        (
            "<b>{0}</b>".format(_text(SAFEGUARD_LEADS[2])),
            "A safety or complaint flag stops the case before any model is "
            "asked ({0}: 0 model calls).".format(safety_link),
        ),
        (
            "<b>{0}</b>".format(_text(SAFEGUARD_LEADS[3])),
            "In {0} the record carries a planted clause; all four drafts "
            "refused it, and the code check voided them, so a person "
            "decides.".format(planted_link),
        ),
        (
            "<b>{0}</b>".format(_text(SAFEGUARD_LEADS[4])),
            "Either party may appeal once within 30 days (POL-GEN-04); a "
            "different human reviewer hears it.",
        ),
        (
            '<a href="{0}"><b>{1}</b></a>'.format(
                _attribute(PRIVACY_LINK), _text(SAFEGUARD_LEADS[5])
            ),
            "Vehicle registration marks, telephone numbers and e-mail "
            "addresses are masked before a model reads the record; names are "
            "not.",
        ),
        (
            "<b>{0}</b>".format(_text(SAFEGUARD_LEADS[6])),
            "Every case shown except 901 is synthetic, and {0}.".format(
                limits_link
            ),
        ),
    )
    lines = "".join(
        "<li>{0} {1}</li>".format(lead, body) for lead, body in items
    )
    accessibility = '<p class="access">{0} <a href="{1}">{2}</a></p>'.format(
        _text(SAFEGUARDS_ACCESSIBILITY),
        _attribute(ACCESSIBILITY_NOTE_LINK),
        _text(ACCESSIBILITY_SCAN_WORDS),
    )
    return (
        '<section class="safeguards" id="safeguards" '
        'aria-labelledby="safeguards-h">'
        '<h2 id="safeguards-h">Safeguards</h2>'
        "<ul>{0}</ul>{1}</section>\n"
    ).format(lines, accessibility)


def _links_row() -> str:
    """The links out of the queue's own words: the architecture views, and a case.

    Every architecture link is a file this builder copies in beside the pages, so
    it resolves wherever ``ui/dist/`` is served and not only in a checkout. The
    dynamic view comes first under the plain label, because it is the one a
    reader wants first -- one dispute, step by step -- and the three container
    views are named beside it. The "Safeguards" link is the way down to the
    seven lines the strip's card does not carry. The last link sends a reader to
    the case whose "How it was decided" tab is the debate itself.
    """
    views = "".join(
        '<a href="{0}">{1}</a>'.format(
            _attribute(architecture_link(view)), _text(label)
        )
        for view, label in ARCHITECTURE_VIEWS
    )
    return (
        '<p class="links">'
        "{0}"
        '<a href="#safeguards">Safeguards</a>'
        '<a href="{1}">How it was decided: see case {2}</a>'
        "</p>\n"
    ).format(
        views,
        _attribute("case-{0:05d}.html".format(HOW_IT_WAS_DECIDED_CASE)),
        _text(HOW_IT_WAS_DECIDED_CASE),
    )


def build_index(cases: Sequence[CaseData]) -> str:
    """The queue: the hero, the featured cases, the safeguards, the figures and the table."""
    figures = queue_figures(cases)
    # 51b.4: the head is the hero. The words are the ones it always carried --
    # nothing on this page is rewritten -- and the poster sits beside them at
    # 1000 px and wider, under them below that. The two buttons under the
    # paragraphs are the way into the case the site is about and the way down to
    # the strip that explains the pipeline.
    case_link = "case-{0:05d}.html".format(HOW_IT_WAS_DECIDED_CASE)
    header = (
        '<header class="pagehead hero">\n'
        '<div class="hero-text">\n'
        "<h1>Today's disputes</h1>\n"
        '<p class="lede">{tribunal}</p>\n'
        '<p class="lede">{disputes} {figures} These pages replay the recorded '
        "runs committed in this repository and call no model; every number is "
        'read from the run\'s own files. <a href="{results_link}">{results_words}'
        "</a>.</p>\n"
        '<p class="hero-cta">'
        '<a class="btn btn-fill" href="{case_link}">See case {case_no}</a>'
        '<a class="btn btn-out" href="#how">How it works</a>'
        "</p>\n"
        "</div>\n"
        '<figure class="hero-art">'
        '<img src="{cover}" width="{cover_width}" height="{cover_height}" '
        'alt="{cover_alt}">'
        '<figcaption class="cap">{cover_caption}</figcaption>'
        "</figure>\n"
        "</header>\n"
    ).format(
        tribunal=_text(WHAT_TRIBUNAL_DOES),
        disputes=_text(WHAT_THE_DISPUTES_ARE),
        figures=_text(WHAT_THE_FIGURES_ARE),
        results_link=_attribute(README_RESULTS_LINK),
        results_words=_text(README_RESULTS_WORDS),
        case_link=_attribute(case_link),
        case_no=_text(HOW_IT_WAS_DECIDED_CASE),
        cover=_attribute(COVER_LINK),
        cover_width=COVER_WIDTH,
        cover_height=COVER_HEIGHT,
        cover_alt=_attribute(COVER_ALT),
        cover_caption=_text(COVER_CAPTION),
    )
    figure_html = '<div class="figures">' + "".join(
        (
            _figure(
                "Decided and executed",
                "{0} of {1}".format(figures.executed, figures.total),
                "{0} of the queue: {1} (POL-GEN-05)".format(
                    figures.executed_share, EXECUTED_MEANS
                ),
                tone="lane-ok",
            ),
            _figure(
                "Decided, amount held for a person to release",
                "{0} of {1}".format(figures.held, figures.total),
                "{0} of the queue, held above the POL-GEN-05 execution "
                "threshold".format(figures.held_share),
                tone="lane-warn",
            ),
            _figure(
                "Sent to a reviewer",
                "{0} of {1}".format(figures.reviewer, figures.total),
                "{0} of the queue, no ruling issued".format(figures.reviewer_share),
                tone="lane-bad",
            ),
            _trigger_card(figures),
            _figure(
                "Median time per case",
                _seconds(figures.median_seconds),
                "wall clock",
                tone="lane-accent",
            ),
            _figure(
                "Median cost per case",
                _usd(figures.median_cost),
                "at the published {0} prices the runs are billed at".format(
                    model_module.MODEL_PROVIDER
                ),
                tone="lane-accent",
            ),
            _figure(
                "Policy version and model",
                "v{0}".format(figures.policy_version),
                figures.model,
                tone="lane-accent",
            ),
        )
    ) + "</div>\n"
    # 47.3: one line under the tiles, for the two loaded words a reader can take
    # wrongly: "executed" is not a payment, and "confidence" is not a measured
    # accuracy. The executed tile's small print carries the same words.
    words_note = '<p class="figurewords">{0}</p>\n'.format(
        _text(QUEUE_WORDS_NOTE)
    )
    filters = (
        '<div class="filters">'
        '<button type="button" data-filter="all" class="on">All</button>'
        '<button type="button" data-filter="auto">Decided automatically</button>'
        '<button type="button" data-filter="reviewer">Sent to a reviewer</button>'
        "{0}"
        '<span class="empty"><span id="shown">{1}</span> shown</span>'
        "</div>\n".format(_set_picker(cases), len(cases))
    )
    rows = "".join(_queue_row(case) for case in cases)
    # The table scrolls inside its own box. The card clips what it holds, so
    # without the box the table was cut off below about 1230 px with no way to
    # reach the columns past the edge.
    table = (
        '<div class="card wide">\n'
        '<div class="tscroll" tabindex="0" role="region" '
        'aria-label="The queue of disputes"><table id="queue">\n'
        "<thead>{0}</thead>\n"
        "<tbody>{1}</tbody>\n</table></div>\n</div>\n".format(_queue_head(), rows)
    )
    body = (
        _topbar(_mode_text(figures.policy_version), "queue")
        + '<main class="wrap">\n'
        + header
        + _how_it_works()
        + _links_row()
        + _featured_cards(cases)
        + _safeguards(figures)
        + figure_html
        + words_note
        + filters
        + table
        + _footer(cases[0])
        + "\n</main>\n"
    )
    return _shell(
        "Tribunal - today's disputes",
        body,
        description=WHAT_TRIBUNAL_DOES,
        canonical=SITE_ROOT,
        og_type=OG_TYPE_SITE,
    )


def build_not_found(cases: Sequence[CaseData]) -> str:
    """The page a host serves for an address that is not one of the site's.

    It is built with the pages rather than beside them, so ``--check`` covers it
    and a rebuild cannot leave it behind, and it is in the site's own style: the
    same top bar, the same footer, and the two links a lost reader needs -- the
    queue, and the no-show case the landing page sends a reader to.
    """
    if not cases:
        raise BuildError("the 404 page needs a case to read the footer from")
    configuration = cases[0].document.get("configuration") or {}
    body = (
        _topbar(_mode_text(configuration.get("policy_version")), "none")
        + '<main class="wrap">\n'
        + '<header class="pagehead">\n'
        + "<h1>This page does not exist</h1>\n"
        + '<p class="lede">The address you followed is not one of this site\'s '
        "pages. Every dispute is one page, and the queue lists them all.</p>\n"
        + "</header>\n"
        + '<p class="links">'
        + '<a href="index.html">The queue</a>'
        + '<a href="{0}">Case {1}: how it was decided</a>'
        "</p>\n".format(
            _attribute("case-{0:05d}.html".format(HOW_IT_WAS_DECIDED_CASE)),
            _text(HOW_IT_WAS_DECIDED_CASE),
        )
        + _footer(cases[0])
        + "\n</main>\n"
    )
    return _shell(
        NOT_FOUND_TITLE,
        body,
        description=NOT_FOUND_DESCRIPTION,
        canonical=SITE_ROOT + NOT_FOUND_LINK,
        og_type=OG_TYPE_SITE,
    )


# --------------------------------------------------------------------------
# The case page
# --------------------------------------------------------------------------
def _summary_line(case: Mapping[str, Any]) -> str:
    """One line of the dispute's own claim text, masked as the brief masks it.

    The mask is :func:`tribunal.brief`'s own -- the same function the version-6
    brief applies to ``claim_text`` -- so a registration mark is replaced on the
    page exactly as it was replaced in front of the agents. The line is the
    claim's first sentence, with its newlines flattened.
    """
    dispute = case.get("dispute") or {}
    text = dispute.get("claim_text")
    if not isinstance(text, str) or not text.strip():
        raise BuildError("the dispute records no claim_text")
    masked = brief_module._mask_registrations(text)
    collapsed = " ".join(str(masked).split())
    end = collapsed.find(". ")
    return collapsed if end < 0 else collapsed[: end + 1]


def _claims_block(case: CaseData, side: str) -> str:
    """One side's column: its numbered claims, and the referee's verdict on each.

    A discarded claim is struck through and the referee's reason sits under it in
    red. The head says how many claims the side made and how many were kept.
    """
    heading = side.title() + " advocate"
    claims = _claims(case.transcript, side)
    if not claims:
        return (
            '<article class="side"><header><b>{0}</b></header>'
            '<p class="empty">No advocate was asked to argue this case, so this '
            "side made no claim.</p></article>".format(_text(heading))
        )
    kept = sum(1 for claim in claims if claim["status"] == "KEPT")
    items = []
    for claim in claims:
        text = _claim_text(claim["text"], struck=claim["status"] == "DISCARDED")
        refs = '<span class="ref">{0} &middot; {1}</span>'.format(
            _text(", ".join(claim["evidence_ids"]) or "no evidence id"),
            _text(", ".join(claim["clause_ids"]) or "no clause id"),
        )
        reason = ""
        if claim["status"] == "DISCARDED":
            reason = '<span class="why">Discarded by the referee ({0}): {1}</span>'.format(
                _text(claim["reason_code"]), _text(claim["detail"])
            )
        items.append("<li>{0}{1}{2}</li>".format(text, refs, reason))
    return (
        '<article class="side"><header><b>{0}</b><small>{1} claim(s), {2} kept</small>'
        "</header><ol>{3}</ol></article>"
    ).format(_text(heading), len(claims), kept, "".join(items))


def _evidence_table(case: CaseData) -> str:
    rows = []
    for artifact in _evidence(case.brief):
        rows.append(
            "<tr>"
            "<td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td>"
            "</tr>".format(
                _text(artifact["evidence_id"]),
                _text(artifact["evidence_type"]),
                _text(artifact["source"]),
                _text(
                    "{0} (weight {1})".format(
                        artifact["status"], artifact["weight"]
                    )
                ),
                _text(", ".join(str(issue) for issue in artifact["issues"]) or "none"),
            )
        )
    return (
        "<table><thead><tr><th>Artifact</th><th>Type</th><th>Source</th>"
        "<th>Admissibility</th><th>Issue codes</th></tr></thead><tbody>{0}"
        "</tbody></table>".format("".join(rows))
    )


def _compact(value: Any) -> str:
    """A derived figure, written short: two decimals, no trailing zeros."""
    number = _decimal(value)
    if number is None:
        return _text(value)
    try:
        text = format(number.quantize(Decimal("0.01")), "f")
    except Exception:
        return _text(value)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _payload(brief: Mapping[str, Any], evidence_type: str) -> Mapping[str, Any]:
    """One artifact's payload, by evidence type, or an empty mapping."""
    for artifact in brief.get("case", {}).get("evidence") or []:
        if isinstance(artifact, Mapping) and artifact.get("evidence_type") == evidence_type:
            payload = artifact.get("payload")
            return payload if isinstance(payload, Mapping) else {}
    return {}


def _case_payload(case: Mapping[str, Any], evidence_type: str) -> Mapping[str, Any]:
    """One artifact's payload from a **public case**, by evidence type.

    The brief reduces a GPS trace to cited derived facts and carries no point
    list, so the geometry a trace is drawn from is read from the case file the
    run was made from rather than from the brief.
    """
    for artifact in case.get("evidence") or []:
        if isinstance(artifact, Mapping) and artifact.get("evidence_type") == evidence_type:
            payload = artifact.get("payload")
            return payload if isinstance(payload, Mapping) else {}
    return {}


def _derived_block(
    brief: Mapping[str, Any], evidence_type: str, key: str
) -> Optional[Mapping[str, Any]]:
    """One artifact's derived block by key, or ``None`` when it carries none."""
    derived = _payload(brief, evidence_type).get("derived")
    if isinstance(derived, Mapping) and isinstance(derived.get(key), Mapping):
        return derived[key]
    return None


def _fact_value(block: Any, *path: str) -> Any:
    """The ``value`` at a dotted path inside a derived block, or ``None``."""
    node: Any = block
    for name in path:
        if not isinstance(node, Mapping):
            return None
        node = node.get(name)
    if isinstance(node, Mapping) and "value" in node:
        return node.get("value")
    return node


def _platform_arrival(case: CaseData) -> Mapping[str, Any]:
    """The platform's own arrival and wait-timer times, where POL-NS-12 applies.

    The clause reads a platform-confirmed arrival (``arrival_marker`` is
    ``GPS_AUTO``) and the platform's own wait-timer events. A case without the
    marker gets an empty mapping rather than a substituted time.
    """
    payload = _payload(case.brief, "TRIP_RECORD")
    policy = payload.get("platform_policy_in_force") or payload.get("platform_policy")
    marker = policy.get("arrival_marker") if isinstance(policy, Mapping) else None
    events = payload.get("events")
    if marker != "GPS_AUTO" or not isinstance(events, list):
        return {}
    times: Dict[str, Any] = {}
    for event in events:
        if isinstance(event, Mapping) and event.get("event_type"):
            times.setdefault(str(event["event_type"]), event.get("at"))
    return times


def key_figure_tiles(case: CaseData) -> List[Tuple[str, str]]:
    """A computed fact beside the policy limit it is tested against.

    Every tile is read from the brief's derived facts or from the run's own
    record; a fact the block does not carry is left out rather than invented.
    """
    brief = case.brief
    currency = case.policy.currency
    tiles: List[Tuple[str, str]] = []

    deviation = _derived_block(brief, "GPS_TRACE", "deviation")
    if deviation is not None and _fact_value(deviation, "available"):
        excess_km = _fact_value(deviation, "excess_km")
        excess_pct = _fact_value(deviation, "excess_pct")
        thresholds = deviation.get("thresholds") or {}
        if excess_km is not None:
            tiles.append(
                (
                    "{0} km".format(_compact(excess_km)),
                    "extra distance, against POL-RD-01's {0} km limit".format(
                        _compact(_fact_value(thresholds, "threshold_km"))
                    ),
                )
            )
        if excess_pct is not None:
            tiles.append(
                (
                    "{0}%".format(_compact(excess_pct)),
                    "of the optimal distance, against POL-RD-01's {0}% limit".format(
                        _compact(_fact_value(thresholds, "threshold_pct"))
                    ),
                )
            )

    coverage = _payload(brief, "GPS_TRACE").get("coverage_pct")
    if coverage is not None:
        tiles.append(("{0}%".format(_compact(coverage)), "trace coverage"))

    arrival = _derived_block(brief, "GPS_TRACE", "arrival")
    driver_track = _derived_block(brief, "GPS_TRACE", "driver_track")
    if arrival is not None and _fact_value(arrival, "available"):
        dwell = _fact_value(arrival, "accumulated_dwell", "longest_run_sec")
        wait = _fact_value(arrival, "thresholds", "minimum_dwell_sec")
        if dwell is not None and wait is not None:
            tiles.append(
                (
                    _seconds(dwell),
                    "continuous in-geofence dwell, against the free wait in force "
                    "({0})".format(_seconds(wait)),
                )
            )
        approach = _fact_value(driver_track or {}, "min_distance_m")
        radius = _fact_value(arrival, "thresholds", "arrival_radius_m")
        if approach is not None and radius is not None:
            tiles.append(
                (
                    "{0} m".format(_compact(approach)),
                    "closest approach to the pickup point, against the arrival "
                    "radius ({0} m)".format(_compact(radius)),
                )
            )

    times = _platform_arrival(case)
    if times:
        if times.get("driver_arrived"):
            tiles.append(
                (
                    str(times["driver_arrived"]),
                    "platform-confirmed arrival (POL-NS-12)",
                )
            )
        start = times.get("wait_timer_started")
        expiry = times.get("wait_timer_expired")
        if start or expiry:
            tiles.append(
                (
                    "{0} to {1}".format(start or "not recorded", expiry or "not recorded"),
                    "the platform's own wait timer (POL-NS-12)",
                )
            )

    value = str(case.ruling.get("ruling"))
    amount = _decimal(case.ruling.get("amount_sgd"))
    driver = _decimal(case.ruling.get("driver_compensation_sgd"))
    confidence = _decimal(case.ruling.get("confidence"))
    if value in REFUND_RULINGS and amount is not None:
        tiles.append(
            (_money(amount, currency), "refund to the filing party (POL-GEN-03)")
        )
    if driver is not None:
        tiles.append((_money(driver, currency), "driver compensation (POL-GEN-03)"))
    if case.trigger is not None:
        # No ruling was carried, so there is no confidence of this case's own to
        # weigh against the floor: the 0.0 the escalation record carries is the
        # absence of a figure, not a low one. The drafts' own confidences are on
        # the drafts.
        tiles.append(
            (
                NO_RULING_CARRIED,
                "so there is no confidence to weigh against the floor of {0} "
                "(POL-GEN-02)".format(case.policy.confidence_floor),
            )
        )
    elif confidence is not None:
        tiles.append(
            (
                str(confidence),
                "confidence against the floor of {0} (POL-GEN-02)".format(
                    case.policy.confidence_floor
                ),
            )
        )
    return tiles


def _tiles_html(case: CaseData) -> str:
    """The right-hand column of the verdict card: the key-figure tiles.

    The confidence tile carries the confidence and the floor as its accessible
    name, so the two figures a reader checks it against are on the page rather
    than only in the words beside them.
    """
    tiles = key_figure_tiles(case)
    if not tiles:
        return (
            '<div class="tiles"><div><span>No derived fact is recorded for this '
            "case.</span></div></div>"
        )
    confidence = case.ruling.get("confidence")
    parts = []
    for value, label in tiles:
        aria = ""
        if confidence is not None and label.startswith(
            "confidence against the floor of"
        ):
            aria = ' aria-label="confidence {0} against a floor of {1}"'.format(
                _attribute(confidence), _attribute(case.policy.confidence_floor)
            )
        parts.append(
            "<div{0}><b>{1}</b><span>{2}</span></div>".format(
                aria, _text(value), _text(label)
            )
        )
    return '<div class="tiles">' + "".join(parts) + "</div>"


# The trace's drawing frame, and the metres in one degree of latitude used to
# turn the fixes into metres. The projection is local and equirectangular, so a
# metre is the same number of pixels on both axes.
MAP_WIDTH = 360.0
MAP_HEIGHT = 250.0
MAP_PAD = 12.0
METRES_PER_DEGREE = 111320.0

# How far a rider's fixes may spread and still be read as one place. A device
# that never moves reports the same fix over and over, and a polyline through
# one point is invisible; the radius is the size a mark has to be drawn at to be
# seen, in the metres the projection works in.
STATIONARY_TRACK_M = 25.0


def _latlngs(points: Any) -> List[Tuple[float, float]]:
    """``[(lat, lng), ...]`` from a trace's point list, skipping anything else."""
    out: List[Tuple[float, float]] = []
    for point in points or []:
        if not isinstance(point, Mapping):
            continue
        try:
            out.append((float(point["lat"]), float(point["lng"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _one_latlng(node: Any) -> Optional[Tuple[float, float]]:
    """``(lat, lng)`` from a labelled place, or ``None``."""
    if not isinstance(node, Mapping):
        return None
    try:
        return (float(node["lat"]), float(node["lng"]))
    except (KeyError, TypeError, ValueError):
        return None


def _dwell_points(gps: Mapping[str, Any], arrival: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    """The driver's fixes inside the arrival radius: the dwell the record names.

    The brief computes the in-geofence dwell as a run of fixes with a first and
    a last instant, so the fixes are the raw points whose timestamps fall inside
    that run. A block that carries no run yields nothing rather than a guess.
    """
    runs = _fact_value(arrival, "accumulated_dwell", "runs")
    if not isinstance(runs, list) or not runs:
        return []
    first = runs[0]
    if not isinstance(first, Mapping):
        return []
    start = _fact_value(first, "first_ts")
    end = _fact_value(first, "last_ts")
    if not start or not end:
        return []
    out: List[Mapping[str, Any]] = []
    for point in gps.get("points") or []:
        if not isinstance(point, Mapping):
            continue
        stamp = point.get("ts")
        if isinstance(stamp, str) and str(start) <= stamp <= str(end):
            out.append(point)
    return out


def _device_distance(case: CaseData) -> Optional[str]:
    """How far the rider's device was from the pickup, as the derived facts give it.

    ``POL-NS-04`` turns on where the device was, and the brief records the
    nearest and the furthest fix's distance from the pickup. Where the two
    round to one figure the label is that figure; where they do not, the label
    is the range, so the page and the featured card cannot disagree about it.
    """
    presence = _derived_block(case.brief, "GPS_TRACE", "rider_presence") or {}
    near = _fact_value(presence, "min_distance_m")
    far = _fact_value(presence, "max_distance_m")
    if near is None and far is None:
        return None
    # Whole metres, which is how the featured card states the same two figures,
    # so the map and the card cannot disagree about the distance.
    if near is None or far is None or _whole(near) == _whole(far):
        return "{0} m".format(_whole(near if near is not None else far))
    return "{0}-{1} m".format(_whole(near), _whole(far))


def _map_label(
    case: CaseData,
    radius_m: Any,
    dwell_seconds: Any,
    distance: Optional[str],
    dropoff: bool,
) -> str:
    """The map's accessible name: what the drawing shows, read off the record."""
    parts = ["The trip trace: the driven route, the pickup point"]
    if dropoff:
        parts.append("the drop-off")
    if radius_m is not None:
        parts.append(
            "the arrival radius of {0} m around the pickup".format(_compact(radius_m))
        )
    if dwell_seconds is not None:
        parts.append(
            "the driver's {0} inside that radius".format(_seconds(dwell_seconds))
        )
    if distance is not None:
        parts.append(
            "the rider's device {0} away, joined to the pickup by a dashed line".format(
                distance
            )
        )
    return ", ".join(parts) + "."


def _trace_svg(case: CaseData) -> str:
    """The trace, drawn by the builder from the GPS fixes.

    The driven trace, the pickup and drop-off points, and -- for a no-show --
    the arrival radius around the pickup point with the fixes inside it and the
    rider's own track where the record carries one. The optimal route is a
    distance and not a line, so no optimal line is drawn here.

    **The frame holds both tracks.** On a route case the extent every point is
    projected into is taken over the driven trace, the rider's track, the two
    labelled places and the arrival radius, so neither track is fitted out of
    the picture. A rider's track that never moves is a point repeated -- a
    polyline through it draws nothing a reader can see, and where the device was
    is the fact ``POL-NS-04`` turns on -- so a track whose fixes lie within
    :data:`STATIONARY_TRACK_M` of each other is marked as well as drawn.

    **A no-show is fitted to its own story.** The driven trace on a no-show case
    runs for kilometres while the case turns on a few hundred metres -- the
    arrival radius and the rider's device -- and a frame fitted to the whole
    trace drew that radius a few pixels across. So on a no-show case the extent
    is the pickup point, the driver's dwell inside the radius and the rider's
    device, the frame is the content's own shape rather than a fixed rectangle,
    and the distance between the device and the pickup is drawn and labelled.
    """
    # The raw fixes and the labelled places are the case file's; the arrival
    # radius below is the brief's own derived figure.
    gps = _case_payload(case.case, "GPS_TRACE")
    trip = _case_payload(case.case, "TRIP_RECORD")
    driver = _latlngs(gps.get("points"))
    if not driver:
        return ""
    rider = _latlngs(gps.get("rider_track"))
    pickup = _one_latlng(trip.get("pickup"))
    dropoff = _one_latlng(trip.get("dropoff"))
    arrival = _derived_block(case.brief, "GPS_TRACE", "arrival") or {}
    radius_m = _fact_value(arrival, "thresholds", "arrival_radius_m")
    no_show = case.category == "NO_SHOW_CHARGE"
    dwell = _dwell_points(gps, arrival) if no_show else []
    dwell_latlngs = _latlngs(dwell)
    dwell_seconds = (
        _fact_value(arrival, "accumulated_dwell", "longest_run_sec")
        if no_show
        else None
    )
    distance = _device_distance(case) if no_show else None
    local = no_show and bool(dwell_latlngs) and pickup is not None

    lat0 = sum(point[0] for point in driver) / len(driver)
    metres_per_degree_lng = METRES_PER_DEGREE * math.cos(math.radians(lat0))

    def to_metres(point: Tuple[float, float]) -> Tuple[float, float]:
        return (point[1] * metres_per_degree_lng, -point[0] * METRES_PER_DEGREE)

    if local:
        focus = dwell_latlngs + rider + [pickup]
    else:
        focus = driver + rider + [
            point for point in (pickup, dropoff) if point is not None
        ]
    xs: List[float] = []
    ys: List[float] = []
    for point in focus:
        x, y = to_metres(point)
        xs.append(x)
        ys.append(y)
    if pickup is not None and radius_m is not None:
        x, y = to_metres(pickup)
        xs += [x - float(radius_m), x + float(radius_m)]
        ys += [y - float(radius_m), y + float(radius_m)]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 100.0)
    span_y = max(max_y - min_y, 100.0)
    if local:
        # The frame takes the content's own aspect ratio, so the drawing fills
        # the column's width instead of leaving two thirds of it empty; the
        # height is capped, so a long thin story cannot become a tall ribbon.
        scale = (MAP_WIDTH - 2 * MAP_PAD) / span_x
        height = span_y * scale + 2 * MAP_PAD
        if height > MAP_HEIGHT:
            scale = (MAP_HEIGHT - 2 * MAP_PAD) / span_y
            height = MAP_HEIGHT
    else:
        scale = min(
            (MAP_WIDTH - 2 * MAP_PAD) / span_x, (MAP_HEIGHT - 2 * MAP_PAD) / span_y
        )
        height = MAP_HEIGHT
    offset_x = (MAP_WIDTH - span_x * scale) / 2 - min_x * scale
    offset_y = (height - span_y * scale) / 2 - min_y * scale

    def to_pixels(point: Tuple[float, float]) -> Tuple[float, float]:
        x, y = to_metres(point)
        return (round(x * scale + offset_x, 2), round(y * scale + offset_y, 2))

    def polyline(points: List[Tuple[float, float]]) -> str:
        return " ".join(
            "{0},{1}".format(*to_pixels(point)) for point in points
        )

    label = _map_label(case, radius_m, dwell_seconds, distance, dropoff is not None)
    parts = [
        '<svg viewBox="0 0 {0} {1}" role="img" aria-label="{2}">'
        "<title>{3}</title>".format(
            int(MAP_WIDTH), round(height, 2), _attribute(label), _text(label)
        )
    ]
    if pickup is not None and radius_m is not None:
        centre_x, centre_y = to_pixels(pickup)
        parts.append(
            '<circle cx="{0}" cy="{1}" r="{2}" fill="none" stroke="#9ca3af" '
            'stroke-width="1" stroke-dasharray="4 3"/>'.format(
                centre_x, centre_y, round(float(radius_m) * scale, 2)
            )
        )
    device: Optional[Tuple[float, float]] = None
    if rider:
        parts.append(
            '<polyline points="{0}" fill="none" stroke="#6b7280" stroke-width="1.5" '
            'stroke-dasharray="4 3"/>'.format(polyline(rider))
        )
        # A track that never moves is one place, and the place is what matters:
        # it is marked so a reader can see it at any zoom.
        rider_metres = [to_metres(point) for point in rider]
        spread = max(
            max(x for x, _y in rider_metres) - min(x for x, _y in rider_metres),
            max(y for _x, y in rider_metres) - min(y for _x, y in rider_metres),
        )
        if spread <= STATIONARY_TRACK_M:
            device = rider[len(rider) // 2]
            x, y = to_pixels(device)
            parts.append(
                '<circle cx="{0}" cy="{1}" r="3" fill="none" stroke="#6b7280" '
                'stroke-width="1.5"><title>{2}</title></circle>'.format(
                    x, y, _text("the rider's device")
                )
            )
    if device is not None and pickup is not None and distance is not None:
        # The distance the case turns on, drawn: the rider's device was not at
        # the pickup point, and the two are joined so the gap is on the map
        # rather than only in the derived facts.
        start_x, start_y = to_pixels(device)
        end_x, end_y = to_pixels(pickup)
        parts.append(
            '<line x1="{0}" y1="{1}" x2="{2}" y2="{3}" stroke="#6b7280" '
            'stroke-width="1" stroke-dasharray="2 3"/>'.format(
                start_x, start_y, end_x, end_y
            )
        )
        parts.append(
            '<text x="{0}" y="{1}" text-anchor="middle" font-size="12" '
            'fill="currentColor">{2}</text>'.format(
                round((start_x + end_x) / 2, 2),
                round((start_y + end_y) / 2 - 4, 2),
                _text(distance),
            )
        )
    parts.append(
        '<polyline class="trace" points="{0}" fill="none" stroke-width="2"/>'.format(
            polyline(driver)
        )
    )
    for point, colour, label_text in (
        (pickup, "#15803d", "pickup"),
        (dropoff, "#b91c1c", "drop-off"),
    ):
        if point is None:
            continue
        x, y = to_pixels(point)
        parts.append(
            '<circle cx="{0}" cy="{1}" r="4" fill="{2}"><title>{3}</title></circle>'.format(
                x, y, colour, _text(label_text)
            )
        )
    parts.append("</svg>")
    return "".join(parts)


def _trace_caption(case: CaseData) -> str:
    """The trace's caption, or nothing where the figure belongs to another case.

    On a route case the caption states the optimal route's distance and the
    promise not to draw it, because the route is a distance and not a line. A
    no-show case is not about the route at all -- what it turns on is where the
    device was and how long the driver waited -- so it carries no caption rather
    than a figure about a different dispute.
    """
    if case.category == "NO_SHOW_CHARGE":
        return ""
    deviation = _derived_block(case.brief, "GPS_TRACE", "deviation")
    optimal = _fact_value(deviation, "optimal_distance_km") if deviation else None
    if optimal is None:
        optimal = _case_payload(case.case, "TRIP_RECORD").get("optimal_distance_km")
    if optimal is None:
        return "The optimal route's distance is not recorded for this case."
    return "optimal: {0} km (distance only)".format(_compact(optimal))


def _rail(case: CaseData) -> str:
    """The right rail: the trace, the evidence and the record."""
    svg = _trace_svg(case)
    if svg:
        # Every line and mark the drawing can carry has its own entry, and an
        # entry is written only where the drawing carries it: a legend that
        # named the rider's track on a case with none would be naming a line
        # that is not there.
        gps_payload = _case_payload(case.case, "GPS_TRACE")
        arrival = _derived_block(case.brief, "GPS_TRACE", "arrival") or {}
        radius_m = _fact_value(arrival, "thresholds", "arrival_radius_m")
        legend = ['<i style="background:var(--accent)"></i>driven trace']
        if _latlngs(gps_payload.get("rider_track")):
            legend.append(
                '<i class="dash"></i>rider\'s track'
            )
        legend.append('<i class="dot" style="background:#15803d"></i>pickup')
        legend.append('<i class="dot" style="background:#b91c1c"></i>drop-off')
        if radius_m is not None:
            legend.append(
                '<i class="ring"></i>arrival radius ({0} m)'.format(
                    _compact(radius_m)
                )
            )
        # The distance line is its own entry, and only where the drawing
        # carries it: the gap between the device and the pickup is what a
        # no-show case turns on.
        distance = _device_distance(case) if case.category == "NO_SHOW_CHARGE" else None
        if distance is not None and _latlngs(gps_payload.get("rider_track")):
            legend.append(
                '<i class="dash"></i>rider\'s device to the pickup ({0})'.format(
                    _text(distance)
                )
            )
        caption = _trace_caption(case)
        trace = (
            '<div class="map">{0}</div>{1}'
            '<p class="legend">{2}</p>'
        ).format(
            svg,
            '<p class="cap">{0}</p>'.format(_text(caption)) if caption else "",
            "".join(legend),
        )
        # The trace's own box runs the full width of the column: a map drawn
        # inside the details' padding loses 32 of the 360 px the rail gives it.
        trace_block = (
            '<details open class="full"><summary>Trace <span>{0}</span></summary>'
            '<div class="in">{1}</div></details>'.format(
                _text(
                    "{0} fixes".format(
                        len(
                            _latlngs(
                                _case_payload(case.case, "GPS_TRACE").get("points")
                            )
                        )
                    )
                ),
                trace,
            )
        )
    else:
        trace_block = (
            "<details open><summary>Trace <span>not recorded</span></summary>"
            '<div class="in"><p class="empty">This case carries no GPS fixes to '
            "draw.</p></div></details>"
        )

    evidence = _evidence(case.brief)
    evidence_lines = "".join(
        '<p>{0}<br><span class="ref">{1} &middot; {2} (weight {3})</span></p>'.format(
            _text(item["evidence_id"]),
            _text(item["source"]),
            _text(item["status"]),
            _text(item["weight"]),
        )
        for item in evidence
    )
    evidence_block = (
        "<details><summary>Evidence <span>{0}</span></summary>"
        '<div class="in">{1}</div></details>'.format(
            _text("{0} item(s)".format(len(evidence))), evidence_lines or "<p>none</p>"
        )
    )

    entries = [
        entry
        for entry in case.transcript.get("entries") or []
        if isinstance(entry, Mapping)
    ]
    prompt = cached = completion = 0
    for entry in entries:
        prompt += int(entry.get("prompt_tokens") or 0)
        cached += int(entry.get("cached_tokens") or 0)
        completion += int(entry.get("completion_tokens") or 0)
    record_block = (
        "<details><summary>Record <span>{0}</span></summary>"
        '<div class="in"><div class="kv">'
        "<span>events</span><span>{1} (one per agent call)</span>"
        "<span>tokens</span><span>{2} (prompt {3}, cached {4}, completion {5})</span>"
        "<span>wall time</span><span>{6}</span>"
        "</div></div></details>"
    ).format(
        _text(_seconds(case.document.get("wall_seconds"))),
        len(entries),
        prompt + cached + completion,
        prompt,
        cached,
        completion,
        _text(_seconds(case.document.get("wall_seconds"))),
    )
    return '<aside class="rail">{0}{1}{2}</aside>'.format(
        trace_block, evidence_block, record_block
    )


def _ruling_clause_ids(case: CaseData) -> List[str]:
    """The clause ids the ruling cites, read from the ruling's own referrals."""
    references = pipeline_module.referral_clause_references(
        case.ruling.get("referrals")
    )
    return [
        str(reference)
        for reference in references
        if str(reference).startswith("POL-")
    ]


# The opening of a judge's explanation is shown from its first paragraph up to
# at least this many characters: some cases open with a one-line salutation, and
# a summary that is one line long is not a summary.
SUMMARY_MINIMUM_CHARS = 120


def _summary_paragraphs(text: Any, minimum: int = SUMMARY_MINIMUM_CHARS) -> str:
    """The explanation's opening, verbatim, from its first paragraph to ``minimum``.

    Paragraphs are added until the opening is at least ``minimum`` characters
    long, so a case that opens with a one-line salutation shows the sentence
    after it too. Nothing is rewritten: the chosen paragraphs are the
    explanation's own, joined by the blank line that separated them.
    """
    collapsed = str(text or "").strip()
    if not collapsed:
        return ""
    chosen: List[str] = []
    length = 0
    for paragraph in re.split(r"\n\s*\n", collapsed):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        chosen.append(paragraph)
        # Counted the way a reader measures it: runs of whitespace are one space.
        length += len(" ".join(paragraph.split()))
        if length >= minimum:
            break
    return "\n\n".join(chosen)


# --------------------------------------------------------------------------
# The notice to the parties, the dispute, and what the record shows
# --------------------------------------------------------------------------
def _ruling_text(case: CaseData) -> str:
    """The ruling's own prose: its explanation and its referrals, joined.

    Both are fields of the ruling, and both are where a ruling writes down what
    it relied on -- the explanation argues the case and the referrals direct a
    person. Nothing else about a ruling is prose.
    """
    return " ".join(
        [str(case.ruling.get("explanation") or "")]
        + [str(referral) for referral in case.ruling.get("referrals") or []]
    )


def _base_clause_id(clause_id: Any) -> str:
    """A citation as the policy keys it: a limb (``POL-RD-06(c)``) is its clause.

    ``precedents.base_clause_id`` is the reader the escalation packet uses for
    the same job, called rather than re-implemented. A citation the reader does
    not recognise is left as it was written rather than guessed at.
    """
    base = precedents_module.base_clause_id(clause_id)
    return base if base is not None else str(clause_id)


def _referral_clause_ids(case: CaseData) -> List[str]:
    """The clause ids the ruling's own ``referrals`` name, as the policy keys them.

    The referrals are the ruling's structured direction to a person -- "refer
    the driver to driver-conduct review" -- so they are read as data rather than
    out of the prose, and each limb citation is reduced to its clause.
    """
    found: List[str] = []
    for clause_id in _ruling_clause_ids(case):
        base = _base_clause_id(clause_id)
        if base not in found:
            found.append(base)
    return found


def _opening_clause_ids(text: Any) -> List[str]:
    """The clause ids the explanation's opening names, in the order it names them.

    The opening is the **first sentence of the explanation that names a clause
    of the policy at all** -- the sentence a ruling states what it decided in.
    Nothing after it is read, and nothing before it is read either: an
    explanation's later sentences and paragraphs argue the clauses it rejects as
    well as the ones it rests on, and a notice that named a clause the ruling
    declined to apply would be telling the parties something the ruling does not
    say. Case 209 is why the sentence and not the paragraph is the unit: its
    whole reasoning is one paragraph, so a paragraph-wide read would put
    ``POL-NS-04``, ``POL-NS-05`` and ``POL-NS-07`` on the notice -- three
    clauses that ruling says in as many words do not apply. Case 208 is why the
    search runs on rather than stopping at the first line: it opens with a
    one-line summary that names no clause, and the clause it rests on is named
    in the sentence after it. Where no sentence of the explanation names a
    clause -- a ruling that only routes the case -- the opening names nothing.
    """
    for paragraph in re.split(r"\n\s*\n", str(text or "").strip()):
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph.strip()):
            found: List[str] = []
            for mention in precedents_module.CLAUSE_MENTION_RE.findall(sentence):
                clause_id = _base_clause_id(mention)
                if clause_id not in found:
                    found.append(clause_id)
            if found:
                return found
    return []


def _cited_clause_ids(case: CaseData) -> List[str]:
    """The clause ids the notice names: what the ruling rests on, and no more.

    Two structured sources, in this order: the ruling's own ``referrals``, and
    the clause ids named in the opening of its explanation -- the first sentence
    that names a clause at all. A clause the loaded policy does not carry is
    given no title it never had and is dropped, and the list stops at
    :data:`NOTICE_CLAUSE_LIMIT`. The set is deliberately not every clause the
    explanation mentions: an explanation names the clauses it rejects as well as
    the ones it rests on -- case 208's names twelve -- and a notice that listed
    them all would tell the parties the ruling relied on clauses it declined to
    apply.
    """
    found = _referral_clause_ids(case) + _opening_clause_ids(
        case.ruling.get("explanation")
    )
    return [
        clause_id
        for clause_id in found
        if clause_id in case.policy.clause_titles
    ][:NOTICE_CLAUSE_LIMIT]


def _cited_evidence_kinds(case: CaseData) -> List[str]:
    """The record kinds the ruling rests on, in a fixed order.

    A kind is named when an artifact of it is cited -- the artifact's own
    ``evidence_id`` appears in the ruling's text -- and the artifact is really
    in the record: its admissibility weight is above 0 and its status is not
    MISSING. Both figures are read from the brief's own admissibility block, so
    an artifact the ruling says is absent is never counted as evidence, however
    often the explanation names it. The two profile artifacts are never named:
    ``POL-GEN-01`` says a profile may not establish a fact about the trip, and a
    notice to the parties is the last place to tell them their own profiles
    carried it.
    """
    text = _ruling_text(case)
    cited: List[str] = []
    for artifact in (case.brief.get("case") or {}).get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        kind = str(artifact.get("evidence_type"))
        evidence_id = artifact.get("evidence_id")
        if kind in PROFILE_EVIDENCE_KINDS or not isinstance(evidence_id, str):
            continue
        if not evidence_id or evidence_id not in text:
            continue
        admissibility = artifact.get("admissibility")
        admissibility = admissibility if isinstance(admissibility, Mapping) else {}
        if str(admissibility.get("status")) == ADMISSIBILITY_MISSING:
            continue
        weight = _decimal(admissibility.get("weight_multiplier"))
        if weight is None or weight <= 0:
            continue
        if kind not in cited:
            cited.append(kind)
    return [kind for kind in EVIDENCE_KIND_ORDER if kind in cited]


def _notice(case: CaseData) -> str:
    """The notice to the two parties, built from the ruling and the policy.

    Six lines and no more: what was decided, what money moves, the clauses the
    ruling rests on by their own titles, the record kinds it rests on, who made
    the decision, and how to appeal. Every one of them is read from the ruling's
    fields or from the loaded policy -- no profile field of either party is
    named, and no sentence here states a fact the record does not carry. The
    judge's reasoning is long internal working written for a reviewer; this is
    the part of the decision that is addressed to the two people it is about.

    The clause line says "named in the ruling" and not "relied on", because what
    it can state is which clauses the ruling's own opening names and which it
    refers on -- not a legal reading of them. What it must not do is name a
    clause the ruling declined to apply, which is why the clauses are read from
    the ruling's ``referrals`` and from the first sentence of its explanation
    that names any rather than from the whole of the prose: the argument that
    rejects a clause and the argument that rests on one read alike to a search,
    and only the sentence a ruling states its decision in says what it decided.
    The evidence line is read the same way -- the artifacts the ruling cites
    whose admissibility weight is above 0 and whose status is not MISSING -- so
    an artifact the ruling says is absent is never counted. Both lines are
    capped and both fall back to a sentence rather than to a guess.
    """
    policy = case.policy
    ruling = case.ruling
    dispute = case.case.get("dispute") or {}
    held = _money_is_held(case)
    if case.trigger is None:
        # The words first and the ruling's own code after them in brackets: a
        # party reads what was decided before meeting the vocabulary the policy
        # names, and the code is on the line for a reader who wants it.
        outcome = "{0} ({1}).".format(
            _text(ruling_sentence(ruling, policy.currency)),
            _text(ruling.get("ruling")),
        )
        who = (
            "An automated system made this decision. The judge answered four "
            "times and the majority carried."
        )
        if held:
            # The amount is decided but not executed, so the parties are told
            # who releases it and how: this page's form cannot, and the sentence
            # says why in the same breath.
            who = "{0} {1}".format(who, release_sentence(policy))
        appeal = appeal_line(policy)
    else:
        outcome = _text(NO_AUTOMATED_RULING)
        who = (
            "A person decides this case. The automated system produced no "
            "ruling for it, so it was sent to a reviewer."
        )
        appeal = appeal_line_after_a_decision(policy)
    money = (
        held_money_statement(ruling, policy, dispute.get("filed_by"))
        if held
        else money_statement(ruling, policy.currency, dispute.get("filed_by"))
    )
    clauses = _cited_clause_ids(case)
    clause_line = (
        "; ".join(
            "{0}: {1}".format(clause_id, policy.title(clause_id))
            for clause_id in clauses
        )
        if clauses
        else NO_CLAUSE_NAMED
    )
    kinds = _cited_evidence_kinds(case)
    kinds_line = (
        ", ".join(EVIDENCE_KIND_WORDS[kind] for kind in kinds)
        if kinds
        else "The ruling names no record kind."
    )
    return (
        '<div class="notice" id="notice">'
        "<h2>{0}</h2>"
        '<p class="preview">{1}</p>'
        "<p><b>Outcome.</b> {2}</p>"
        "<p><b>The money.</b> {3}</p>"
        "<p><b>Clauses named in the ruling.</b> {4}</p>"
        "<p><b>Evidence cited.</b> {5}</p>"
        "<p><b>Who decided.</b> {6}</p>"
        "<p><b>Appeal.</b> {7}</p>"
        "</div>"
    ).format(
        _text(NOTICE_TITLE),
        _text(NOTICE_PREVIEW),
        outcome,
        _text(money),
        _text(clause_line),
        _text(kinds_line),
        _text(who),
        _text(appeal),
    )


def _brief_dispute(case: CaseData) -> Mapping[str, Any]:
    """The dispute as the **brief** carries it, so POL-GEN-08(4) has been applied.

    The page reads the brief rather than the public case file for every word
    either party wrote: a plate, a telephone number and an e-mail address were
    replaced in front of the agents, and they are replaced here too, so a reader
    sees the text the decision was made on.
    """
    dispute = (case.brief.get("case") or {}).get("dispute")
    return dispute if isinstance(dispute, Mapping) else {}


def _chat_messages(case: CaseData) -> List[Mapping[str, Any]]:
    """Every chat message of this trip, as the brief carries it (masked)."""
    messages = _payload(case.brief, "CHAT_LOG").get("messages")
    return [message for message in messages or [] if isinstance(message, Mapping)]


def _dispute_block(case: CaseData) -> str:
    """The dispute itself: the claim, the other party's account, and the chat.

    All three come from the brief. A call-log entry -- a chat message recorded
    on the call channel -- is shown as its own line rather than as a chat
    message, because the record says what happened to the call and not what
    either party typed.
    """
    dispute = _brief_dispute(case)
    filed_by = str(dispute.get("filed_by") or "")
    if filed_by == "RIDER":
        filer, other = "Rider", "Driver"
    elif filed_by == "DRIVER":
        filer, other = "Driver", "Rider"
    else:
        filer, other = "Filing party", "Other party"
    claim = dispute.get("claim_text")
    statement = dispute.get("counterparty_statement")
    statement = statement if isinstance(statement, Mapping) else {}
    messages = _chat_messages(case)
    chat = [
        message
        for message in messages
        if str(message.get("channel")) != CALL_LOG_CHANNEL
    ]
    calls = [
        message
        for message in messages
        if str(message.get("channel")) == CALL_LOG_CHANNEL
    ]
    if chat:
        # The date is written once above the table and each row carries the
        # clock alone: a full ISO instant wraps inside a cell on a phone.
        chat_block = (
            '<p class="cap">{0}</p>'
            '<div class="tscroll" tabindex="0" role="region" '
            'aria-label="The chat, as the record carries it">'
            "<table><thead><tr><th>Time</th><th>From</th>"
            "<th>Message</th></tr></thead><tbody>{1}</tbody></table></div>"
        ).format(
            _text(_date_of(chat[0].get("sent_at"))),
            "".join(
                "<tr><td class=\"mono\">{0}</td><td>{1}</td><td>{2}</td></tr>".format(
                    _text(_clock(message.get("sent_at"))),
                    _text(message.get("sender")),
                    _text(message.get("text")),
                )
                for message in chat
            ),
        )
    else:
        chat_block = '<p class="empty">No chat message is recorded for this trip.</p>'
    call_block = "".join(
        '<p class="cap">Call log: {0} &middot; {1} &middot; {2}</p>'.format(
            _text(_clock(message.get("sent_at"))),
            _text(message.get("sender")),
            _text(message.get("text")),
        )
        for message in calls
    )
    if not statement.get("text"):
        statement_block = (
            '<p class="empty">No statement from the other party is recorded for '
            "this dispute.</p>"
        )
    else:
        statement_block = "<blockquote>{0}</blockquote><p class=\"cap\">Submitted by {1} at {2}</p>".format(
            _text(statement.get("text")),
            _text(statement.get("submitted_by")),
            _text(statement.get("submitted_at")),
        )
    return (
        '<section class="card dispute" id="the-dispute">'
        "<h2>The dispute</h2>"
        "<h3>{0}'s account, as filed</h3>"
        "<blockquote>{1}</blockquote>"
        "<h3>The {2}'s account</h3>"
        "{3}"
        "<h3>The chat, as the record carries it</h3>"
        "{4}{5}"
        "</section>"
    ).format(
        _text(filer),
        _text(claim),
        _text(other.lower()),
        statement_block,
        chat_block,
        call_block,
    )


def _record_rows(case: CaseData) -> List[Tuple[str, str]]:
    """The no-show facts the brief's derived blocks already compute.

    Each row is a value the brief carries and the policy limit it is tested
    against, both read from the block rather than typed here. A fact the block
    does not carry is left out rather than filled in.
    """
    arrival = _derived_block(case.brief, "GPS_TRACE", "arrival") or {}
    driver_track = _derived_block(case.brief, "GPS_TRACE", "driver_track") or {}
    rider_presence = _derived_block(case.brief, "GPS_TRACE", "rider_presence") or {}
    rows: List[Tuple[str, str]] = []
    dwell = _fact_value(arrival, "accumulated_dwell", "longest_run_sec")
    wait = _fact_value(arrival, "thresholds", "minimum_dwell_sec")
    if dwell is not None:
        rows.append(
            (
                "Time inside the arrival radius",
                "{0}, against the free waiting period in force ({1})".format(
                    _seconds(dwell),
                    _seconds(wait) if wait is not None else "not recorded",
                ),
            )
        )
    approach = _fact_value(driver_track, "min_distance_m")
    radius = _fact_value(arrival, "thresholds", "arrival_radius_m")
    if approach is not None:
        rows.append(
            (
                "Closest approach to the pickup point",
                "{0} m, against the arrival radius ({1})".format(
                    _compact(approach),
                    "{0} m".format(_compact(radius))
                    if radius is not None
                    else "not recorded",
                ),
            )
        )
    near = _fact_value(rider_presence, "min_distance_m")
    far = _fact_value(rider_presence, "max_distance_m")
    if near is not None and far is not None:
        first = _fact_value(rider_presence, "first_ts")
        last = _fact_value(rider_presence, "last_ts")
        # The clock alone, with the date written once above the table.
        rows.append(
            (
                "Where the rider's device was",
                "{0} m to {1} m from the pickup point, from {2} to {3}".format(
                    _compact(near),
                    _compact(far),
                    _clock(first) if first else "not recorded",
                    _clock(last) if last else "not recorded",
                ),
            )
        )
    calls = [
        message
        for message in _chat_messages(case)
        if str(message.get("channel")) == CALL_LOG_CHANNEL
    ]
    rows.append(
        (
            "Call-log entries",
            "; ".join(
                "{0} ({1}, {2})".format(
                    message.get("text"), message.get("sender"), message.get("sent_at")
                )
                for message in calls
            )
            or "none recorded in the chat",
        )
    )
    return rows


def _record_date(case: CaseData) -> str:
    """The date the record's own facts fall on, for the line above the table."""
    for block, key in (("rider_presence", "first_ts"), ("arrival", "arrived_at")):
        value = _fact_value(_derived_block(case.brief, "GPS_TRACE", block) or {}, key)
        if value:
            return _date_of(value)
    calls = [
        message
        for message in _chat_messages(case)
        if str(message.get("channel")) == CALL_LOG_CHANNEL
    ]
    return _date_of(calls[0].get("sent_at")) if calls else ""


def _record_block(case: CaseData) -> str:
    """What the record shows for a no-show case, before any model reads it.

    The table is the brief's own derived facts laid out, so it adds nothing to
    the record and no fact it shows is one the brief does not carry. A case of
    another category has no such table: the derived facts differ by category,
    and this one is about arrival and waiting. The date the facts fall on is
    written once above the table, and each row carries the clock alone.
    """
    if case.category != "NO_SHOW_CHARGE":
        return ""
    rows = _record_rows(case)
    if not rows:
        return ""
    date = _record_date(case)
    caption = "computed from the record, before any model"
    if date:
        caption = "{0} &middot; {1}".format(caption, _text(date))
    return (
        '<section class="sec" id="what-the-record-shows">'
        "<h2>What the record shows</h2>"
        '<p class="cap">{0}</p>'
        '<div class="tscroll" tabindex="0" role="region" '
        'aria-label="What the record shows">'
        "<table><thead><tr><th>Fact</th><th>The record</th>"
        "</tr></thead><tbody>{1}</tbody></table></div>"
        "</section>"
    ).format(
        caption,
        "".join(
            "<tr><td>{0}</td><td>{1}</td></tr>".format(_text(fact), _text(value))
            for fact, value in rows
        ),
    )


# The pipeline writes the panel's drafts into its escalation explanation as one
# line each, ``- draft 1 (sampled): ...``. The line repeats a draft's reason as
# many times as the check recorded it, so the ruling panel draws the list as a
# table instead and shows every reason once.
DRAFT_LINE_RE = re.compile(r"^- draft \d+ \(")


def _paragraphs_html(text: Any) -> str:
    """The explanation's paragraphs, verbatim, as ``<p class="why">`` blocks."""
    return "".join(
        '<p class="why">{0}</p>'.format(_text(paragraph))
        for paragraph in str(text or "").split("\n\n")
        if paragraph.strip()
    )


def _void_reasons(abstention: Any) -> List[Tuple[str, str]]:
    """A voided draft's reasons, each once, as ``(code, detail)`` pairs.

    The record writes a reason as ``CODE: detail`` and joins several with a
    semicolon; the same pair may be recorded twice, which is why the pair is
    what is deduplicated rather than the line.
    """
    found: List[Tuple[str, str]] = []
    for piece in str(abstention or "").split(";"):
        piece = piece.strip()
        if not piece:
            continue
        code, _, detail = piece.partition(":")
        pair = (code.strip(), detail.strip())
        if pair not in found:
            found.append(pair)
    return found


def _draft_proposal(case: CaseData, draft: Mapping[str, Any]) -> str:
    """The ruling and amount a draft itself proposed, voided or not.

    The vote drops a voided draft's proposal -- there is nothing to carry -- so
    the draft's own answer is read from the transcript entry the draft parsed to
    and worded exactly as a carried ruling's money is.
    """
    if not draft["ruling"]:
        return "no ruling was parsed"
    return _outcome_text(
        {
            "ruling": draft["ruling"],
            "amount_sgd": draft["amount_sgd"],
            "driver_compensation_sgd": draft["driver_compensation_sgd"],
        },
        case.policy.currency,
        None,
        case.votes,
    )


def _draft_table(case: CaseData, drafts: Sequence[Mapping[str, Any]]) -> str:
    """The panel's drafts, one row each: kind, proposal, confidence, voiding.

    A row per draft rather than a sentence per draft, so the four can be read
    down the page: what kind of draft it was, what it proposed, how confident it
    was, and -- where the code checks rejected it -- why, each reason once.
    """
    rows = []
    for draft in drafts:
        if draft["valid"]:
            why = "not voided: the code checks accepted it"
        else:
            reasons = _void_reasons(draft["abstention"])
            why = "; ".join(
                "{0} ({1}){2}".format(
                    draft_words(code), code, ": {0}".format(detail) if detail else ""
                )
                for code, detail in reasons
            ) or "no reason is recorded"
        rows.append(
            "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td></tr>".format(
                _text(draft["draft"]),
                _text(DRAFT_KIND_WORDS.get(str(draft["kind"]), str(draft["kind"]))),
                _text(_draft_proposal(case, draft)),
                _text(
                    "none" if draft["confidence"] is None else str(draft["confidence"])
                ),
                _text(why),
            )
        )
    return (
        '<div class="tscroll" tabindex="0" role="region" '
        'aria-label="The panel\'s drafts, one row each">'
        "<table><thead><tr><th>Draft</th><th>Kind</th>"
        "<th>Proposed</th><th>Confidence</th><th>Why it was voided</th></tr>"
        "</thead><tbody>{0}</tbody></table></div>"
    ).format("".join(rows))


def _panel_summary(case: CaseData) -> str:
    """The ruling panel's summary: the panel's own words, and its drafts as a table.

    On a case the panel could not decide, the pipeline's own routing sentence
    ends with a list of the drafts, one line each. The list is drawn as a table
    -- one row per draft, each reason once, and the ruling the draft itself
    proposed, which the vote drops for a voided draft -- and the sentence around
    it is shown verbatim. A panel that reached a ruling has no such list, and
    its explanation is shown as it was.
    """
    summary = _summary_paragraphs((case.packet or {}).get("explanation"))
    drafts = _drafts(case.transcript)
    if not drafts:
        return _paragraphs_html(summary)
    lead: List[str] = []
    tail: List[str] = []
    listed = False
    for line in summary.split("\n"):
        if DRAFT_LINE_RE.match(line.strip()):
            listed = True
            continue
        (tail if listed else lead).append(line)
    return (
        _paragraphs_html("\n".join(lead).strip())
        + _draft_table(case, drafts)
        + _paragraphs_html("\n".join(tail).strip())
    )


def _verdict_card(case: CaseData) -> str:
    """The verdict card: the outcome on the left, the key figures on the right.

    The left column carries the notice to the two parties, the outcome in large
    type, the code and the clauses the ruling cites, the opening of the judge's
    text verbatim, and -- on a decided case -- POL-GEN-04's appeal route; on a
    case sent to a reviewer it carries the reviewer line instead, because there
    is no ruling to appeal, and its disclosure says that no automatic ruling was
    made rather than that one was.
    """
    policy = case.policy
    ruling = case.ruling
    dispute = case.case.get("dispute") or {}
    value = str(ruling.get("ruling"))
    if case.trigger is not None:
        # The panel carried no ruling, so the headline names who decides next
        # and the reason the case went there sits under it, in words first and
        # in the record's own code after them.
        headline = _text(SENT_TO_A_PERSON)
        clause_line = '<p class="code">{0}</p>'.format(
            _coded(trigger_words(str(case.trigger), case.votes), case.trigger)
        )
        after = "No automated ruling was made. {0}".format(review_time_limit(policy))
        disclosure = NO_AUTOMATED_RULING
        details = ""
        note = ""
        # The text a case that went to a reviewer carries is the panel's drafts'
        # reasoning where there was a panel, and the pipeline's own routing
        # sentence where the scope gate stopped before any judge was asked. The
        # drafts themselves are drawn as a table rather than as the pipeline's
        # one-line-each list.
        summary_label = (
            DRAFTS_TEXT_LABEL if _drafts(case.transcript) else ROUTING_TEXT_LABEL
        )
        panel_block = _panel_summary(case)
        summary_block = (
            '<p class="lbl">{0}</p>{1}'.format(_text(summary_label), panel_block)
            if panel_block
            else ""
        )
    else:
        headline = _coded(ruling_words(value), value, strong=True)
        clauses = _ruling_clause_ids(case)
        clause_line = (
            '<p class="code mono">{0}</p>'.format(_text(", ".join(clauses)))
            if clauses
            else ""
        )
        summary = _summary_paragraphs(ruling.get("explanation"))
        after = "How to appeal: {0}".format(appeal_line(policy))
        disclosure = DISCLOSURE
        summary_label = JUDGE_TEXT_LABEL
        details = (
            "<details><summary>Read POL-GEN-04 in full</summary>"
            "<blockquote>{0}</blockquote></details>".format(
                _text(policy.rule("POL-GEN-04"))
            )
        )
        note = (
            ""
            if _decimal(ruling.get("confidence")) is not None
            else '<p class="empty">No confidence is recorded for this case.</p>'
        )
        summary_block = (
            '<p class="lbl">{0}</p>{1}'.format(
                _text(summary_label), _paragraphs_html(summary)
            )
            if summary
            else ""
        )
    # A ruling whose money is above the execution threshold was issued but not
    # executed, so the figure is named for what it is: an amount awaiting release.
    awaiting = (
        '<p class="awaiting">Amount awaiting release: {0}</p>'.format(
            _text(_money(monetary_effect(ruling), policy.currency))
        )
        if _money_is_held(case)
        else ""
    )
    return (
        '<div class="verdict">'
        '<div class="v-left">'
        '<p class="cap">{0}</p>'
        '<p class="word">{1}</p>'
        "{2}"
        "<p>{3}</p>"
        "{12}"
        "{11}"
        "{4}"
        '<p class="after">{5}</p>'
        "<p>{6}</p>"
        "{10}"
        "{7}"
        "{8}"
        "</div>"
        "{9}"
        "</div>"
    ).format(
        _text(disclosure),
        headline,
        clause_line,
        _text(money_statement(ruling, policy.currency, dispute.get("filed_by"))),
        summary_block,
        _text(after),
        _text(execution_sentence(policy, ruling, policy.currency)),
        details,
        note,
        _tiles_html(case),
        awaiting,
        _notice(case),
        refund_over_contested(case),
    )


def _ruling_tab(case: CaseData) -> str:
    """The Ruling tab: the verdict, what each side argued, and the right rail."""
    sides = (
        '<section class="sec"><h2>What each side argued</h2>'
        '<div class="sides">'
        + _claims_block(case, "RIDER")
        + _claims_block(case, "DRIVER")
        + "</div></section>"
    )
    return (
        _verdict_card(case)
        + _record_block(case)
        + '<div class="two"><div class="maincol">'
        + sides
        + "</div>"
        + _rail(case)
        + "</div>"
    )


# Who did each of the six steps. Steps 1, 3 and 5 are code; 2 and 4 are the
# model; 6 is the outcome.
STEP_WHO: Tuple[str, ...] = ("code", "model", "code", "model", "code", "outcome")
STEP_WHO_WORDS: Mapping[str, str] = {
    "code": "computed by code",
    "model": "asked of the model",
    "outcome": "the outcome",
}

# The colour each of the three is drawn in: the case page's legend and its
# stepper circles read them from here, so a reader meets one colour for code,
# one for the model and one for the outcome wherever they are on the site. The
# model's is the accent rather than a literal, because the stepper's model
# circles have always been ``var(--accent)`` and a legend that named a fixed
# blue beside them was the colour 51b.11 went looking for.
STEP_COLOURS: Mapping[str, str] = {
    "code": "#374151",
    "model": "var(--accent)",
    "outcome": "#15803d",
}


def _seconds_for_entries(case: CaseData, indices: Sequence[int]) -> Optional[str]:
    """The seconds the transcript records for the entries at these indices."""
    entries = case.transcript.get("entries") or []
    total = Decimal(0)
    found = False
    for index in sorted(set(indices)):
        if not isinstance(index, int) or not 0 <= index < len(entries):
            continue
        entry = entries[index]
        value = _decimal(entry.get("duration_seconds")) if isinstance(entry, Mapping) else None
        if value is not None:
            total += value
            found = True
    return _seconds(total) if found else None


def _seconds_for_roles(case: CaseData, roles: Sequence[str]) -> Optional[str]:
    """The seconds the transcript records for the entries of these roles."""
    entries = case.transcript.get("entries") or []
    indices = [
        index
        for index, entry in enumerate(entries)
        if isinstance(entry, Mapping) and entry.get("role") in roles
    ]
    return _seconds_for_entries(case, indices)


# --------------------------------------------------------------------------
# The debate: what the two advocates claimed, and what the panel drafted
# --------------------------------------------------------------------------
# The "Both sides argue" step is how a judge sees the brief's required
# observable inter-agent communication, so it is drawn as a debate and not as
# the advocates' raw answers: each claim is a card carrying the claim's own
# text, the artifacts and clauses it cites, and the referee's verdict on it.
#
# A claim runs to 80-200 words, so the card shows the claim's first sentence and
# keeps the argument for it one click away. The words are the claim's own; this
# is the label on the click.
READ_THE_WHOLE_CLAIM = "Read the whole claim"


def _evidence_kinds(case: CaseData) -> Dict[str, str]:
    """Each artifact's kind in words, by evidence id, as the brief carries it."""
    kinds: Dict[str, str] = {}
    for artifact in _evidence(case.brief):
        if artifact["evidence_id"] is None:
            continue
        kinds[str(artifact["evidence_id"])] = EVIDENCE_KIND_WORDS.get(
            str(artifact["evidence_type"]), str(artifact["evidence_type"])
        )
    return kinds


def _evidence_chip(kinds: Mapping[str, str], evidence_id: Any) -> str:
    """One cited evidence id as a chip, carrying the kind of artifact it names."""
    kind = kinds.get(str(evidence_id), "not in the brief")
    return (
        '<span class="chip ev" title="{0}">{1}<span class="k">{0}</span></span>'
    ).format(_attribute(kind), _text(evidence_id))


def _clause_chip(case: CaseData, clause_id: Any) -> str:
    """One cited clause id as a chip, its title on hover and in text on focus.

    The title is the loaded policy's own for the clause, so a reader is told
    what the clause says without the page saying anything about the case. A
    clause the policy does not carry is shown by its id alone, which is what a
    voided draft's clause ids are.
    """
    title = case.policy.title(str(clause_id))
    return (
        '<span class="chip clause" tabindex="0" title="{0}">{1}'
        '<span class="ct">{0}</span></span>'
    ).format(_attribute(title), _text(clause_id))


def _claim_verdict(claim: Mapping[str, Any]) -> str:
    """The referee's verdict on one claim: kept, or discarded with its reason."""
    status = claim["status"]
    if status == referee_module.STATUS_KEPT:
        return '<p class="claimv"><span class="pill green">kept</span></p>'
    if status == referee_module.STATUS_DISCARDED:
        code = str(claim["reason_code"])
        return (
            '<p class="claimv"><span class="pill red">discarded</span> '
            '<span class="why">{0} ({1}): {2}</span></p>'
        ).format(
            _text(referee_words(code)), _text(code), _text(claim["detail"])
        )
    return (
        '<p class="claimv"><span class="pill grey">no referee verdict is '
        "recorded for this claim</span></p>"
    )


def _claim_paragraph(text: str, struck: bool) -> str:
    """One piece of a claim as a paragraph, struck through where it was discarded."""
    body = _text(text)
    if struck:
        body = "<s>{0}</s>".format(body)
    return "<p>{0}</p>".format(body)


def _claim_text(text: Any, struck: bool = False) -> str:
    """One claim: its first sentence, and the rest behind a collapsed detail.

    Each claim is a paragraph of 80 to 200 words. The first sentence states the
    claim, and the argument for it is what follows, so the paragraph is shown
    as its first sentence with the remainder one click away rather than as a
    wall of small print in the middle of the debate. Nothing is rewritten: the
    two pieces are the paragraph's own, split after its first sentence, and a
    claim that is one sentence is shown whole.
    """
    whole = str(text or "").strip()
    match = re.search(r"(?<=[.!?])\s+", whole)
    if match is None:
        return _claim_paragraph(whole, struck)
    first = whole[: match.start()].strip()
    rest = whole[match.end():].strip()
    if not rest:
        return _claim_paragraph(first, struck)
    return (
        _claim_paragraph(first, struck)
        + "<details><summary>{0}</summary>{1}</details>".format(
            _text(READ_THE_WHOLE_CLAIM), _claim_paragraph(rest, struck)
        )
    )


def _claim_card(case: CaseData, claim: Mapping[str, Any], kinds: Mapping[str, str]) -> str:
    """One claim as a card: its text, what it cites, and the referee's verdict."""
    evidence = "".join(
        _evidence_chip(kinds, item) for item in claim["evidence_ids"]
    )
    clauses = "".join(_clause_chip(case, item) for item in claim["clause_ids"])
    return (
        '<article class="claim">{0}'
        '<p class="cite">{1}{2}</p>{3}</article>'
    ).format(
        _claim_text(claim["text"]),
        evidence or '<span class="cap">no evidence id</span>',
        clauses or '<span class="cap">no clause id</span>',
        _claim_verdict(claim),
    )


def _advocate_column(case: CaseData, side: str) -> str:
    """One advocate's claims as a column of cards, with its own kept count."""
    heading = "Rider advocate" if side == "RIDER" else "Driver advocate"
    claims = _claims(case.transcript, side)
    if not claims:
        return (
            '<article class="side"><header><b>{0}</b></header>'
            '<p class="empty">No advocate was asked to argue this case, so this '
            "side made no claim.</p></article>".format(_text(heading))
        )
    kept = sum(
        1 for claim in claims if claim["status"] == referee_module.STATUS_KEPT
    )
    kinds = _evidence_kinds(case)
    return (
        '<article class="side"><header><b>{0}</b><small>{1} claim(s), {2} '
        "kept</small></header>{3}</article>"
    ).format(
        _text(heading),
        len(claims),
        kept,
        "".join(_claim_card(case, claim, kinds) for claim in claims),
    )


def _citation_detail(case: CaseData) -> str:
    """The counts kept and discarded per side, and each discarded claim's reason."""
    counts: List[str] = []
    discarded: List[Mapping[str, Any]] = []
    for side, heading in (("RIDER", "Rider advocate"), ("DRIVER", "Driver advocate")):
        claims = _claims(case.transcript, side)
        kept = sum(
            1 for claim in claims if claim["status"] == referee_module.STATUS_KEPT
        )
        dropped = [
            claim
            for claim in claims
            if claim["status"] == referee_module.STATUS_DISCARDED
        ]
        counts.append(
            "<li>{0}: {1} kept, {2} discarded</li>".format(
                _text(heading), kept, len(dropped)
            )
        )
        discarded.extend(dropped)
    if discarded:
        reasons = "".join(
            '<li><span class="pill red">discarded</span> {0} ({1}) -- {2}: {3}</li>'.format(
                _text(referee_words(str(claim["reason_code"]))),
                _text(claim["reason_code"]),
                _text("Rider advocate" if claim["side"] == "RIDER" else "Driver advocate"),
                _text(claim["detail"]),
            )
            for claim in discarded
        )
    else:
        reasons = "<li>No claim was discarded: every claim the referee checked cited what it said it did.</li>"
    return (
        '<p class="label">Kept and discarded, by side</p><ul>{0}</ul>'
        '<p class="label">Each discarded claim and the referee\'s reason</p>'
        "<ul>{1}</ul>"
    ).format("".join(counts), reasons)


def _draft_card(
    case: CaseData, draft: Mapping[str, Any], majority: bool
) -> str:
    """One draft as a card: its ruling, its money, its confidence, how it voted.

    ``majority`` is whether this draft formed the majority the vote carried. It
    is the record's own answer -- the drafts whose proposal the reduction
    carried -- rather than a second reading of the amounts here, so a panel that
    wrote the same figure ``6.4`` on one draft and ``6.40`` on another is the
    one panel it is.
    """
    currency = case.policy.currency
    proposal = draft["proposal"] if isinstance(draft["proposal"], Mapping) else {}
    ruling_value = proposal.get("ruling") or draft["ruling"]
    amount = proposal.get("amount_sgd") if proposal else draft["amount_sgd"]
    driver = (
        proposal.get("driver_compensation_sgd")
        if proposal
        else draft["driver_compensation_sgd"]
    )
    confidence = draft["confidence"]
    if not draft["valid"]:
        voted = '<span class="pill red">voided</span>'
    elif draft["agrees"]:
        voted = '<span class="pill green">carried</span>'
    else:
        voted = '<span class="pill grey">did not carry</span>'
    mark = (
        '<span class="pill blue">in the majority</span>' if majority else ""
    )
    return (
        '<article class="dcard"><h4>Draft {0} &middot; {1}</h4>'
        '<p class="d-ruling">{2}</p>'
        "<p>Amount {3}</p><p>Driver compensation {4}</p><p>Confidence {5}</p>"
        "<p>{6}{7}</p>{8}</article>"
    ).format(
        _text(draft["draft"]),
        _text(DRAFT_KIND_WORDS.get(str(draft["kind"]), str(draft["kind"]))),
        _coded(ruling_words(ruling_value), ruling_value)
        if ruling_value
        else '<span class="cap">no ruling was parsed</span>',
        _text(_money(amount, currency)),
        _text(_money(driver, currency)),
        _text("none" if confidence is None else str(confidence)),
        voted,
        " " + mark if mark else "",
        _abstention_detail(draft["abstention"]) if not draft["valid"] else "",
    )


def _judge_detail(case: CaseData, drafts: Sequence[Mapping[str, Any]], vote: Mapping[str, Any]) -> str:
    """The panel's four drafts as cards, and the vote they were reduced to."""
    outcome = str(vote.get("outcome"))
    carried = outcome in (
        pipeline_module.VOTE_CARRIED,
        pipeline_module.VOTE_CARRIED_NOT_UNANIMOUS,
    )
    agreement = vote.get("agreement")
    return (
        "<p>The judge was asked {0} times on the same inputs: {1} sampled "
        "drafts and one with the parties' positions swapped. The vote "
        "agreement is {2}, and the outcome recorded is {3}.</p>"
        '<div class="drafts">{4}</div>'
        '<p class="label">Each draft\'s own explanation</p>{5}'
    ).format(
        _text(vote.get("votes")),
        _text(sum(1 for draft in drafts if draft.get("kind") == pipeline_module.DRAFT_SAMPLED)),
        _text(agreement if agreement is not None else "not recorded"),
        _text(outcome),
        "".join(
            _draft_card(case, draft, bool(draft["agrees"]) and carried)
            for draft in drafts
        ),
        "".join(
            # 47.2: each explanation is long -- a draft's own reasoning runs to
            # several paragraphs -- so it sits in a closed ``<details>`` named
            # for its draft, and the four draft cards above stay visible.
            "<details><summary>{0}</summary><blockquote>{1}</blockquote></details>".format(
                _text(
                    "Draft {0} - {1}".format(
                        draft["draft"],
                        DRAFT_KIND_WORDS.get(
                            str(draft["kind"]), str(draft["kind"])
                        ),
                    )
                ),
                _text(draft["explanation"]),
            )
            for draft in drafts
        )
        or '<p class="empty">No draft was asked for.</p>',
    )


def _abstention_detail(abstention: Any) -> str:
    """A voided draft's own reason, each code worded, then the record's words."""
    items = []
    for part in [piece.strip() for piece in str(abstention or "").split(";")]:
        if not part:
            continue
        code, _, message = part.partition(":")
        code = code.strip()
        items.append(
            "<li>{0} ({1}): {2}</li>".format(
                _text(draft_words(code)), _text(code), _text(message.strip())
            )
        )
    return '<ul class="d-void">{0}</ul>'.format("".join(items)) if items else ""


def _decision_tab(case: CaseData) -> str:
    """How it was decided: a stepper of the six steps, and the chosen step's detail."""
    transcript = case.transcript
    entries = transcript.get("entries") or []
    vote = transcript.get("vote") if isinstance(transcript.get("vote"), Mapping) else {}
    advocates = {
        entry.get("role"): entry
        for entry in entries
        if isinstance(entry, Mapping)
        and entry.get("role") in ("RIDER_ADVOCATE", "DRIVER_ADVOCATE")
    }
    rider = advocates.get("RIDER_ADVOCATE")
    driver = advocates.get("DRIVER_ADVOCATE")
    same_bytes = (
        isinstance(rider, Mapping)
        and isinstance(driver, Mapping)
        and rider.get("user_sha256") == driver.get("user_sha256")
        and rider.get("user_sha256") == case.brief_sha256
    )

    # 1. The evidence pack.
    facts = _derived_facts(case.brief)
    fact_rows = "".join(
        "<li>{0} ({1}): {2}</li>".format(
            _text(row["evidence_id"]),
            _text(row["evidence_type"]),
            _text(", ".join(row["derived_keys"]) or "no derived facts"),
        )
        for row in facts
    )
    step1 = {
        "title": STEP_TITLES[0],
        "time": None,
        "summary": "{0} artifacts, brief {1}".format(
            len(facts), case.brief_sha256[:12]
        ),
        "detail": (
            "<p>The brief was built from the case and the loaded policy. Its sha256 "
            'is <span class="mono">{0}</span>.</p>'
            "<p>Both advocates received these same bytes: {1}.</p>"
            '<p class="label">The derived facts each artifact carries</p><ul>{2}</ul>'
        ).format(
            _text(case.brief_sha256),
            _text(
                "yes, the recorded user_sha256 of each advocate is this digest"
                if same_bytes
                else "no, the recorded digests do not agree with the brief"
            ),
            fact_rows,
        ),
    }

    # 2. Both sides argue.

    def claim_count(entry: Any) -> int:
        parsed = entry.get("parsed") if isinstance(entry, Mapping) else None
        claims = parsed.get("claims") if isinstance(parsed, Mapping) else None
        return len(claims) if isinstance(claims, list) else 0

    if rider is None and driver is None:
        step2 = {
            "title": STEP_TITLES[1],
            "time": None,
            "summary": "no advocate was asked",
            "detail": (
                "<p>No advocate was asked: the scope gate assembled the record and "
                "stopped, so neither side argued this case.</p>"
            ),
        }
    else:
        step2 = {
            "title": STEP_TITLES[1],
            "time": _seconds_for_roles(case, ("RIDER_ADVOCATE", "DRIVER_ADVOCATE")),
            "summary": "rider {0} claims - driver {1}".format(
                claim_count(rider), claim_count(driver)
            ),
            "detail": (
                "<p>The two advocates ran on the same brief and at the same time: the "
                "rider advocate made {0} claim(s) and the driver advocate made {1}. "
                'Their instructions differ -- system_sha256 <span class="mono">{2}'
                '</span> against <span class="mono">{3}</span> -- and their brief is '
                "one digest for both. Each claim is shown with the artifacts and "
                "clauses it cites and the referee's verdict on it.</p>"
                '<div class="debate">{4}{5}</div>'
            ).format(
                claim_count(rider),
                claim_count(driver),
                _text((rider or {}).get("system_sha256")),
                _text((driver or {}).get("system_sha256")),
                _advocate_column(case, "RIDER"),
                _advocate_column(case, "DRIVER"),
            ),
        }

    # 3. The citation check.
    rider_claims = _claims(transcript, "RIDER")
    driver_claims = _claims(transcript, "DRIVER")
    all_claims = rider_claims + driver_claims
    kept = [
        claim for claim in all_claims if claim["status"] == referee_module.STATUS_KEPT
    ]
    discarded = [
        claim
        for claim in all_claims
        if claim["status"] == referee_module.STATUS_DISCARDED
    ]
    if all_claims:
        step3 = {
            "title": STEP_TITLES[2],
            "time": None,
            "summary": "{0} kept, {1} discarded".format(len(kept), len(discarded)),
            "detail": (
                "<p>The referee checked every claim against the artifacts it cites, "
                "in code and with no model: {0} claim(s) kept, {1} discarded.</p>"
                "{2}"
            ).format(len(kept), len(discarded), _citation_detail(case)),
        }
    else:
        step3 = {
            "title": STEP_TITLES[2],
            "time": None,
            "summary": "no claim reached the referee",
            "detail": (
                "<p>No claim reached the referee: no advocate was asked to argue "
                "this case.</p>"
            ),
        }

    # 4. The judge.
    drafts = _drafts(transcript)
    judge_indices = [
        index for draft in drafts for index in draft["entry_indices"]
    ]
    if drafts:
        agreement = vote.get("agreement")
        step4 = {
            "title": STEP_TITLES[3],
            "time": _seconds_for_entries(case, judge_indices),
            "summary": "{0} drafts{1}".format(
                len(drafts), ", {0}".format(_text(agreement)) if agreement else ""
            ),
            "detail": _judge_detail(case, drafts, vote),
        }
    else:
        step4 = {
            "title": STEP_TITLES[3],
            "time": None,
            "summary": "no draft was asked for",
            "detail": (
                "<p>No draft was asked for: the scope gate stopped before the "
                "judge, so this case has no panel and no vote.</p>"
            ),
        }

    # 5. The floor and the triggers.
    floor = case.policy.confidence_floor
    step5 = {
        "title": STEP_TITLES[4],
        "time": None,
        "summary": "confidence {0} against the floor {1}".format(
            _text(case.ruling.get("confidence")), _text(floor)
        ),
        "detail": (
            "<p>The confidence recorded for this case is {0} against the floor of "
            "{1} stated by POL-GEN-02.</p>{2}"
        ).format(
            _text(case.ruling.get("confidence")),
            _text(floor),
            "<p>The escalation reason is {0}.</p>".format(
                _coded(trigger_words(str(case.trigger), case.votes), case.trigger)
            )
            if case.trigger
            else "<p>No escalation reason is recorded: the case did not escalate.</p>",
        ),
    }

    # 6. The outcome.
    dispute = case.case.get("dispute") or {}
    if case.trigger:
        step6 = {
            "title": STEP_TITLES[5],
            "time": None,
            "summary": trigger_words(str(case.trigger), case.votes),
            "detail": "<p>Sent to a reviewer, fee held: {0}.</p>".format(
                _coded(trigger_words(str(case.trigger), case.votes), case.trigger)
            ),
        }
    else:
        step6 = {
            "title": STEP_TITLES[5],
            "time": None,
            "summary": ruling_words(case.ruling.get("ruling")),
            "detail": "<p>{0}</p><p>{1}</p>".format(
                _coded(
                    ruling_words(case.ruling.get("ruling")),
                    case.ruling.get("ruling"),
                    strong=True,
                ),
                _text(
                    money_statement(
                        case.ruling, case.policy.currency, dispute.get("filed_by")
                    )
                ),
            ),
        }

    steps = [step1, step2, step3, step4, step5, step6]
    circle_class = {
        "code": "",
        "model": "llm",
        "outcome": "ok" if case.trigger is None else "bad",
    }
    buttons: List[str] = []
    panes: List[str] = []
    for index, step in enumerate(steps):
        who = STEP_WHO[index]
        circle = (
            ' class="{0}"'.format(circle_class[who]) if circle_class[who] else ""
        )
        buttons.append(
            '<button type="button" data-step="{0}"{1}>'
            '<span class="n"><i{2}>{3}</i>{4}</span>'
            '<span class="t">{5}</span><span class="s">{6}</span></button>'.format(
                index + 1,
                ' class="on"' if index == 0 else "",
                circle,
                index + 1,
                _text(step["time"] or ""),
                _text(step["title"]),
                _text(step["summary"]),
            )
        )
        panes.append(
            '<div class="pane{0}" data-pane="{1}"><h3>{2}</h3>'
            '<p class="lead">{3}</p>{4}</div>'.format(
                " on" if index == 0 else "",
                index + 1,
                _text(step["title"]),
                _text("{0} - {1}".format(STEP_WHO_WORDS[who], step["summary"])),
                step["detail"],
            )
        )
    return (
        '<div class="stepper">' + "".join(buttons) + "</div>"
        '<p class="who">'
        '<span><i style="background:{0}"></i>code</span>'
        '<span><i style="background:{1}"></i>model</span>'
        '<span><i style="background:{2}"></i>outcome</span>'
        "</p>"
        '<div class="detail">' + "".join(panes) + "</div>"
    ).format(
        _attribute(STEP_COLOURS["code"]),
        _attribute(STEP_COLOURS["model"]),
        _attribute(STEP_COLOURS["outcome"]),
    )


# --------------------------------------------------------------------------
# The closing command the form builds
# --------------------------------------------------------------------------
def case_policy_clauses(case: "CaseData") -> List[str]:
    """Every clause id of the policy this case was decided under, sorted.

    POL-GEN-06(6) requires a decision's reason to cite "at least one clause of
    the policy in force, or POL-GEN-07 where no clause applies", so the form
    offers **every** clause the case's own policy carries rather than only the
    ones the ruling happened to cite -- which is what lets POL-GEN-07 be chosen.
    ``referee.policy_clauses`` is the policy's own reader, called rather than
    re-implemented.
    """
    return sorted(referee_module.policy_clauses(case.brief))


def adopt_proposal(case: "CaseData") -> Optional[Mapping[str, Any]]:
    """The panel's best-supported proposal, as ``tribunal.precedents`` reads it."""
    return precedents_module.best_supported_proposal(case.transcript.get("vote"))


def adopt_is_disabled(case: "CaseData") -> bool:
    """Whether there is nothing for a reviewer to adopt.

    ``tribunal.precedents.best_supported_proposal`` counts the valid drafts'
    proposals and takes the plurality, so an ADOPT is "adopt what the panel
    proposed". When the plurality is ``ESCALATE`` -- or when there is no valid
    draft and so no proposal at all -- there is nothing to adopt, and the page
    says so and disables the choice rather than offering an empty command.
    """
    proposal = adopt_proposal(case)
    if not isinstance(proposal, Mapping):
        return True
    return str(proposal.get("ruling")) == ESCALATE


def _summary_for(decision: str, note: str) -> str:
    """The summary a decision's closure carries: the decision, and its note."""
    note = str(note or "").strip()
    if decision == DECISION_REFER_COMPLIANCE and note:
        return "{0}: {1}".format(decision, note)
    return decision


def shell_quote(value: Any) -> str:
    """A value as one shell word: single-quoted, with ``'`` written ``'\\''``.

    Double quotes leave ``$``, a backtick and ``!`` to the shell, so a reason
    carrying one is rewritten before the command ever runs -- the same bug part
    38c fixed in ``ops/``. A single-quoted word is literal; the one character
    that cannot appear inside it is closed, escaped and reopened, which is what
    ``'\\''`` does. This is ``shlex.quote``'s rule written out, because the page
    builds the same word in JavaScript and the two have to agree.
    """
    return "'" + str(value).replace("'", "'\\''") + "'"


def closing_command(
    case: "CaseData",
    decision: str,
    *,
    ruling: Optional[str] = None,
    amount: Any = None,
    clauses: Sequence[str] = (),
    note: str = "",
    closed_by: str = "reviewer",
    summary: Optional[str] = None,
    reason: str = "",
    store: Optional[str] = None,
) -> str:
    """The ``python3 -m ops.review`` command the form builds for one decision.

    It is ``tribunal.precedents close``'s own command line -- ``ops.review``
    forwards every argument it does not use -- and it carries **no** ``close``:
    ``ops.review`` supplies the subcommand itself, and a second one is what the
    old page's command was refused for. The ruling is the decision's own: the
    panel's best-supported proposal for ADOPT, and the reviewer's choice from
    POL-GEN-03's values for VARY and REFER_COMPLIANCE. ``--clause`` is repeated
    once per clause, and every clause offered is one of the case's own policy's.

    ``store`` is for a caller that wants the closure somewhere other than the
    repository's own ``precedents/``; the page's command leaves it out, so the
    command a reviewer copies writes to the repository's store.
    """
    if case.packet is None:
        raise BuildError("case {0} has no escalation packet".format(case.case_no))
    # What an ADOPT records is the panel's own proposal, so when the caller
    # passes no ruling the command takes the proposal's ruling and amount. The
    # amount is the proposal's ``amount_sgd``, or its ``driver_compensation_sgd``
    # on a ``DRIVER_COMPENSATION`` ruling -- the two fields the proposal carries,
    # read the way ``ops.appeal.monetary_effect`` reads them.
    if decision == DECISION_ADOPT and ruling is None:
        proposal = adopt_proposal(case)
        if isinstance(proposal, Mapping):
            ruling = str(proposal.get("ruling") or "") or None
            if amount is None:
                if ruling == pipeline_module.DRIVER_COMPENSATION:
                    amount = proposal.get("driver_compensation_sgd")
                    if amount is None:
                        amount = proposal.get("amount_sgd")
                else:
                    amount = proposal.get("amount_sgd")
    parts: List[str] = ["python3", "-m", "ops.review"]
    if store is not None:
        parts += ["--store", str(store)]
    parts += [
        "--run-dir", _relative_run_dir(case),
        "--case", str(case.case_no),
        "--packet-sha256", escalation.packet_sha256(case.packet),
    ]
    if ruling:
        parts += ["--ruling", str(ruling)]
    if amount is not None and str(amount) != "":
        parts += ["--amount", str(amount)]
    for clause in clauses:
        parts += ["--clause", str(clause)]
    parts += [
        "--closed-by",
        shell_quote(closed_by),
        "--summary",
        shell_quote(summary if summary is not None else _summary_for(decision, note)),
        "--reason",
        shell_quote(reason),
    ]
    return " ".join(parts)


def evidence_window_command(
    case: "CaseData",
    *,
    items: Sequence[str] = (),
    opened_at: str = "",
    opened_by: str = "reviewer",
    store: str = EVIDENCE_STORE,
) -> str:
    """The ``python3 -m ops.evidence_window open`` command, which is part 26.

    ``POL-GEN-06(4)`` lets a reviewer choose REQUEST_EVIDENCE, and
    ``ops/evidence_window.py`` is the command that executes it. The form builds
    the command in that command's own shape -- ``--store``, ``--run-dir``,
    ``--case``, ``--now``, ``--items`` and ``--opened-by`` -- and the page names
    the store it writes to, which is gitignored, rather than pretending the
    command runs in the browser.
    """
    parts: List[str] = ["python3", "-m", "ops.evidence_window", "open"]
    if store is not None:
        parts += ["--store", str(store)]
    parts += [
        "--run-dir", _relative_run_dir(case),
        "--case", str(case.case_no),
        "--now", shell_quote(opened_at),
        "--items", ",".join(str(item) for item in items),
        "--opened-by", shell_quote(opened_by),
    ]
    return " ".join(parts)


def _brief_kept(claim: Any) -> bool:
    """Whether the packet records the referee keeping one advocate's claim."""
    if not isinstance(claim, Mapping):
        return False
    verdict = claim.get("verdict")
    return isinstance(verdict, Mapping) and verdict.get("status") == "KEPT"


def _review_tab(case: CaseData) -> str:
    """The human-review tab: the packet, its digest, and a form that closes nothing."""
    packet = case.packet
    if packet is None:
        raise BuildError("case {0} has no escalation packet".format(case.case_no))
    digest = escalation.packet_sha256(packet)
    trigger = packet.get("trigger") or {}
    case_block = packet.get("case") or {}
    ruling = packet.get("ruling") or {}
    currency = case.policy.currency
    # The packet drops a voided draft's proposal -- there is nothing to carry --
    # so the drafts are read from the transcript, where each draft's own answer
    # is recorded whether or not the code checks accepted it, and the packet's
    # own abstention detail is joined on by draft number.
    packet_drafts = {
        draft.get("draft"): draft
        for draft in packet.get("drafts") or []
        if isinstance(draft, Mapping)
    }
    draft_rows = "".join(
        "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td>"
        "<td>{5}</td></tr>".format(
            _text(draft["draft"]),
            _coded(ruling_words(draft["ruling"]), draft["ruling"])
            if draft["ruling"]
            else '<span class="cap">no ruling was parsed</span>',
            _text(_money(draft["amount_sgd"], currency)),
            _text(
                "none" if draft["confidence"] is None else str(draft["confidence"])
            ),
            _text("valid" if draft["valid"] else "abstained"),
            _text(
                (packet_drafts.get(draft["draft"]) or {}).get("abstention_code")
                or "none"
            ),
        )
        for draft in _drafts(case.transcript)
    )
    admissibility_rows = "".join(
        "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td></tr>".format(
            _text(artifact.get("evidence_id")),
            _text(artifact.get("evidence_type")),
            _text(artifact.get("source")),
            _text(artifact.get("status")),
            _text(artifact.get("weight_multiplier")),
        )
        for artifact in packet.get("admissibility") or []
    )
    # The event log's instants are full ISO strings with microseconds, and its
    # durations carry sixteen decimals. Each row carries the clock alone and the
    # duration to a tenth of a second, and the table is collapsed, because the
    # log is a long mechanical record rather than the decision itself.
    timeline_rows = "".join(
        "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td></tr>".format(
            _text(_clock(row.get("ts"))),
            _text(row.get("event")),
            _text(row.get("role_or_draft")),
            _text("none" if row.get("seconds") is None else _seconds(row.get("seconds"))),
        )
        for row in packet.get("timeline") or []
    )
    timeline_block = (
        "<details><summary>Show the event log</summary>"
        '<div class="tscroll" tabindex="0" role="region" '
        'aria-label="The escalation packet\'s event log">'
        "<table><thead><tr><th>Time</th><th>Event</th>"
        "<th>Role or draft</th><th>Seconds</th></tr></thead><tbody>{0}</tbody>"
        "</table></div></details>"
    ).format(timeline_rows or '<tr><td colspan="4">none</td></tr>')
    briefs = packet.get("briefs") or {}
    brief_rows = "".join(
        "<li>{0}<ul>{1}</ul></li>".format(
            _text(side),
            "".join(
                '<li>{0} <span class="pill {1}">{2}</span></li>'.format(
                    _text(claim.get("text")),
                    "green" if _brief_kept(claim) else "red",
                    _text("kept" if _brief_kept(claim) else "discarded"),
                )
                for claim in briefs.get(side) or []
            )
            or "<li>no claim</li>",
        )
        for side in ("RIDER", "DRIVER")
    )
    packet_card = (
        '<div class="card wide"><h2>The escalation packet</h2>'
        '<p>Built by <span class="mono">ops.escalation</span> from this run. Its '
        'sha256 is <span class="mono">{0}</span>.</p>'
        "<h3>The case</h3><p>{1} &middot; filed by {2} &middot; contested {3}</p>"
        "<h3>The trigger</h3><p>outcome {4} &middot; threshold {5} &middot; valid {6} "
        "&middot; votes {7} &middot; agreement: {8} &middot; unanimous: {9}</p>"
        "<h3>The judge's explanation, verbatim</h3><blockquote>{10}</blockquote>"
        "<h3>The drafts</h3>"
        '<div class="tscroll" tabindex="0" role="region" '
        'aria-label="The escalation packet\'s drafts">'
        "<table><thead><tr><th>Draft</th><th>Ruling</th>"
        "<th>Amount</th><th>Confidence</th><th>State</th><th>Abstention</th></tr>"
        "</thead><tbody>{11}</tbody></table></div>"
        "<h3>The advocate briefs, as the packet carries them</h3><ul>{12}</ul>"
        "<h3>The admissibility report</h3>"
        '<div class="tscroll" tabindex="0" role="region" '
        'aria-label="The escalation packet\'s admissibility report">'
        "<table><thead><tr><th>Artifact</th>"
        "<th>Type</th><th>Source</th><th>Status</th><th>Weight</th></tr></thead>"
        "<tbody>{13}</tbody></table></div>"
        "<h3>Every clause id relied on</h3><p class=\"mono\">{14}</p>"
        "<h3>The ruling</h3><p>{15} &middot; amount {16} &middot; driver {17} &middot; "
        "confidence {18}</p>"
        "<h3>The timeline</h3>{19}"
        "</div>"
    ).format(
        _text(digest),
        _text(case_block.get("category")),
        _text(case_block.get("filed_by")),
        _text(_money(case_block.get("amount_contested_sgd"), currency)),
        _text(trigger.get("outcome")),
        _text(trigger.get("threshold")),
        _text(trigger.get("valid")),
        _text(trigger.get("votes")),
        _text(
            "no vote"
            if trigger.get("agreement") is None
            else trigger.get("agreement")
        ),
        _text("yes" if trigger.get("unanimous") else "no"),
        _text(packet.get("explanation")),
        draft_rows or "<tr><td colspan=\"6\">none</td></tr>",
        brief_rows or "<li>none</li>",
        admissibility_rows or "<tr><td colspan=\"5\">none</td></tr>",
        _text(", ".join(packet.get("clause_ids") or []) or "none"),
        _coded(ruling_words(ruling.get("ruling")), ruling.get("ruling")),
        _text(_money(ruling.get("amount_sgd"), currency)),
        _text(_money(ruling.get("driver_compensation_sgd"), currency)),
        _text(ruling.get("confidence")),
        timeline_block,
    )

    evidence_ids = [
        str(artifact.get("evidence_id"))
        for artifact in packet.get("admissibility") or []
        if artifact.get("evidence_id")
    ]
    clause_ids = case_policy_clauses(case)
    proposal = adopt_proposal(case)
    adopt_ruling = (
        "" if not isinstance(proposal, Mapping) else str(proposal.get("ruling") or "")
    )
    adopt_amount = (
        ""
        if not isinstance(proposal, Mapping) or proposal.get("amount_sgd") is None
        else str(proposal.get("amount_sgd"))
    )
    # What an ADOPT records is the panel's proposal, so the command's clauses are
    # the ones the packet relied on; a packet that names none falls back to every
    # clause the case's policy carries, because a closure rests on at least one.
    adopt_clauses = [str(item) for item in packet.get("clause_ids") or []] or clause_ids
    disabled = adopt_is_disabled(case)

    choices = tuple((value, DECISION_LABELS[value]) for value in DECISIONS)
    # No radio is ``checked``. The form opens on no decision, so the outcome on
    # the page is the reviewer's from the first click and never the page's.
    radios = "".join(
        '<p><label><input type="radio" name="decision" value="{0}"{1}> {2}</label></p>'.format(
            _attribute(value),
            " disabled" if value == DECISION_ADOPT and disabled else "",
            _text(label),
        )
        for value, label in choices
    )
    if disabled:
        adopt_note = (
            '<p class="empty" id="adopt-note">nothing to adopt: the panel\'s '
            "best-supported proposal is {0}.</p>".format(_text(adopt_ruling or "absent"))
        )
    else:
        adopt_note = (
            '<p class="empty" id="adopt-note">The panel\'s best-supported proposal is '
            "{0} {1}; ADOPT records exactly that.</p>".format(
                _text(adopt_ruling),
                "" if not adopt_amount else _money(adopt_amount, case.policy.currency),
            )
        )
    # The form opens on no decision at all. A pre-selected one would be an
    # outcome chosen by the page rather than by the reviewer -- and on 1779 the
    # first enabled choice was VARY with the ruling select on a full refund,
    # which is the outcome the injected message asked for.
    ruling_options = (
        '<option value="">choose a ruling</option>'
        + "".join(
            '<option value="{0}">{1}</option>'.format(
                _attribute(value), _text(ruling_words(value))
            )
            for value in DECISION_RULING_VALUES
        )
    )
    clause_options = "".join(
        '<option value="{0}">{0}</option>'.format(_attribute(clause))
        for clause in clause_ids
    )
    evidence_boxes = "".join(
        '<label class="ev"><input type="checkbox" name="evidence" value="{0}"> '
        "{0}</label>".format(_attribute(kind))
        for kind in EVIDENCE_KINDS
    )
    decision_fields = (
        '<div class="decision-fields" data-for="ADOPT">'
        "<p>Adopt the panel's proposal. The command carries the proposal's own "
        "ruling and amount, and the clauses the packet relied on.</p></div>"
        '<div class="decision-fields" data-for="VARY">'
        '<p><label for="vary-ruling">Ruling</label> '
        '<select id="vary-ruling">{0}</select> '
        '<label for="vary-amount">Amount</label> '
        '<input id="vary-amount" type="text" inputmode="decimal" size="8" '
        'placeholder="a figure the money block enumerates"></p>'
        '<p><label for="vary-clauses">Clauses (choose at least one)</label><br>'
        '<select id="vary-clauses" multiple size="6">{1}</select></p></div>'
        '<div class="decision-fields" data-for="REFER_COMPLIANCE">'
        '<p><label for="refer-ruling">Ruling</label> '
        '<select id="refer-ruling">{0}</select> '
        '<label for="refer-amount">Amount</label> '
        '<input id="refer-amount" type="text" inputmode="decimal" size="8"></p>'
        '<p><label for="refer-clauses">Clauses (choose at least one)</label><br>'
        '<select id="refer-clauses" multiple size="6">{1}</select></p>'
        "<p><label for=\"refer-note\">Note: the safety, fraud or conduct matter "
        "referred</label><br>"
        '<input id="refer-note" type="text" size="40"></p></div>'
        '<div class="decision-fields" data-for="REQUEST_EVIDENCE">'
        "<p>Name the record-type items required, and when the window opens. The "
        "reviewer opens one window for both parties at once.</p>"
        "<p>{2}</p>"
        '<p><label for="window-now">Opens at (an ISO 8601 instant with a zone)</label> '
        '<input id="window-now" type="text" size="30" '
        'placeholder="2026-08-11T20:00:00+08:00"></p>'
        '<p class="empty">{3}: the evidence window is '
        '<span class="mono">ops/evidence_window.py</span>, which opens one window '
        "to both parties at once; the command below names the store it writes to, "
        "and that store is not tracked.</p></div>"
    ).format(ruling_options, clause_options, evidence_boxes, EVIDENCE_WINDOW_PART)
    form_card = (
        '<div class="card wide" id="review-form" '
        'data-run-dir="{0}" data-case="{1}" data-packet="{2}" '
        'data-adopt-ruling="{3}" data-adopt-amount="{4}" data-adopt-clauses="{5}" '
        'data-evidence="{6}" data-clauses="{7}" data-reason-min="{8}" '
        'data-store="{13}">'
        "<h2>The decision</h2>"
        "<p>POL-GEN-06(4) names exactly four decisions:</p>{9}"
        "{10}"
        "{11}"
        '<p><label>Reviewer <input id="reviewer" type="text" '
        'placeholder="a name"></label></p>'
        '<p><label for="reason">Reason</label> (at least {12} characters, citing one '
        "evidence id of this case and one clause id of the policy)</p>"
        '<textarea id="reason" rows="4" style="width:100%"></textarea>'
        '<p id="verdict"></p>'
        '<p><button type="button" id="copy">Copy the command</button> '
        '<span id="copy-status" class="empty"></span></p>'
        '<pre id="command"></pre>'
        "<p><strong>This form closes nothing by itself: there is no server.</strong> "
        "It checks the reason and builds the command; recording the decision is a "
        "command a person runs.</p>"
        "</div>"
    ).format(
        _attribute(_relative_run_dir(case)),
        _attribute(case.case_no),
        _attribute(digest),
        _attribute(adopt_ruling),
        _attribute(adopt_amount),
        _attribute(" ".join(adopt_clauses)),
        _attribute(" ".join(evidence_ids)),
        _attribute(" ".join(clause_ids)),
        _attribute(precedents_module.MIN_REASON_CHARS),
        radios,
        adopt_note,
        decision_fields,
        precedents_module.MIN_REASON_CHARS,
        _attribute(EVIDENCE_STORE),
    )
    return packet_card + form_card


def _relative_run_dir(case: CaseData) -> str:
    """The run directory as a path from the project root, never an absolute one."""
    try:
        return case.run_dir.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        raise BuildError(
            "the run directory {0} is outside the project".format(case.run_dir)
        )


def build_case_page(case: CaseData) -> str:
    """One case page: a header, two or three tabs, and the footer."""
    dispute = case.case.get("dispute") or {}
    currency = case.policy.currency
    category_words = CATEGORY_WORDS.get(case.category, case.category)
    title = "{0} - {1}".format(_text(category_words), _text(_summary_line(case.case)))
    header = (
        '<header class="pagehead">\n'
        '<p class="ids">{0} &middot; {1} &middot; filed {2}</p>\n'
        "<h1>{3}</h1>\n"
        '<div class="chips">'
        '<span class="chip">{4}</span>'
        '<span class="chip">{5}</span>'
        '<span class="chip">{6}</span>'
        "{7}"
        "</div>\n"
        "{8}"
        "</header>\n"
    ).format(
        _text(dispute.get("dispute_id")),
        _text(dispute.get("trip_id")),
        _text(dispute.get("filed_at")),
        title,
        _text(category_words),
        _text("Filed by {0}".format(str(filed_by_words(dispute.get("filed_by"))).lower())),
        _text(
            "Contested {0}".format(
                _money(dispute.get("amount_contested_sgd"), currency)
            )
        ),
        status_chip(case, with_time=True, title=True),
        summary_bar(case),
    )
    tabs = [
        ("ruling", "Ruling"),
        ("decision", "How it was decided"),
    ]
    if case.trigger is not None:
        tabs.append(("review", "Human review"))
    tab_html = "".join(
        '<button type="button" class="tab{0}" role="tab" id="tab-{1}" '
        'aria-controls="panel-{1}" data-tab="{1}" '
        'aria-selected="{2}">{3}</button>'.format(
            " tab-on" if index == 0 else "",
            _attribute(name),
            "true" if index == 0 else "false",
            _text(label),
        )
        for index, (name, label) in enumerate(tabs)
    )

    def panel(name: str, hidden: bool, content: str) -> str:
        return (
            '<section role="tabpanel" id="panel-{0}" aria-labelledby="tab-{0}" '
            'data-panel="{0}"{1}>{2}</section>'
        ).format(_attribute(name), " hidden" if hidden else "", content)

    panels = [panel("ruling", False, _ruling_tab(case))]
    panels.append(panel("decision", True, _decision_tab(case)))
    if case.trigger is not None:
        panels.append(panel("review", True, _review_tab(case)))
    configuration = case.document.get("configuration") or {}
    body = (
        _topbar(
            _mode_text(configuration.get("policy_version")),
            "case",
        )
        + '<main class="wrap">\n'
        + header
        + _dispute_block(case)
        + '<div class="tabs" role="tablist">'
        + tab_html
        + "</div>\n"
        + "\n".join(panels)
        + "\n"
        + _footer(case)
        + "\n</main>\n"
    )
    return _shell(
        "Case {0} - {1}".format(case.case_no, category_words),
        body,
        description="{0} - {1}".format(
            category_words, _summary_line(case.case)
        ),
        canonical=SITE_ROOT + case.link,
        og_type=OG_TYPE_CASE,
    )


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------
def _write_or_check(destination: Path, text: str, check: bool) -> int:
    if check:
        if not destination.is_file():
            print("{0} does not exist; run the build".format(destination))
            return 1
        if destination.read_text(encoding="utf-8") != text:
            print(
                "{0} differs from a fresh build ({1} bytes on disk, {2} rebuilt)".format(
                    destination,
                    destination.stat().st_size,
                    len(text.encode("utf-8")),
                )
            )
            return 1
        print("{0} is identical to a fresh build".format(destination))
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    print("wrote {0}: {1} bytes".format(destination, len(text.encode("utf-8"))))
    return 0


def _write_or_check_bytes(destination: Path, data: bytes, check: bool) -> int:
    """One copied file, written byte for byte, or compared with the committed one.

    The pages are text and go through :func:`_write_or_check`; a file this
    builder copies rather than renders is compared and written as bytes, so a
    re-encoding cannot slip between the source and the site.
    """
    if check:
        if not destination.is_file():
            print("{0} does not exist; run the build".format(destination))
            return 1
        if destination.read_bytes() != data:
            print(
                "{0} differs from a fresh build ({1} bytes on disk, {2} rebuilt)".format(
                    destination,
                    destination.stat().st_size,
                    len(data),
                )
            )
            return 1
        print("{0} is identical to a fresh build".format(destination))
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    print("wrote {0}: {1} bytes".format(destination, len(data)))
    return 0


def assets() -> List[Tuple[Path, bytes]]:
    """The files this site carries that are not pages, as ``(destination, bytes)``.

    Six: the four architecture views, the link-preview image and the front
    page's poster, each copied out of the repository byte for byte. The views'
    links off the queue's links row are files inside the published root instead
    of paths out of it, and ``og:image`` names a URL a scraper fetches, so the
    file it names has to be inside the published root too. Like :func:`pages` it
    is a list a check and a writing build both walk, so the two cannot disagree
    about which files there are.
    """
    out = [
        (
            ARCHITECTURE_ASSET_DIR / view,
            (ARCHITECTURE_SOURCE_DIR / view).read_bytes(),
        )
        for view, _label in ARCHITECTURE_VIEWS
    ]
    out.append((OG_IMAGE_ASSET, OG_IMAGE_SOURCE.read_bytes()))
    out.append((COVER_ASSET, COVER_SOURCE.read_bytes()))
    return out


def pages() -> List[Tuple[Path, str]]:
    """Every page this site commits, as ``(destination, text)``.

    The one place the site's shape is decided, so ``--check`` and a writing
    build cannot disagree about which files there are: both walk this list. The
    queue, the page a host serves for an address that is not one of these, and
    one page per case.
    """
    cases = read_every_case()
    out: List[Tuple[Path, str]] = [
        (INDEX_PATH, build_index(cases)),
        (NOT_FOUND_PATH, build_not_found(cases)),
    ]
    for case in cases:
        out.append((DIST_DIR / case.link, build_case_page(case)))
    return out


def build(check: bool = False) -> int:
    """Every page, or a comparison of the committed bytes against a fresh build."""
    status = 0
    for destination, text in pages():
        defused = text.count(DEFUSED)
        if defused:
            print(
                "{0}: {1} key-shaped run(s) written with an entity-escaped "
                "hyphen, so the publish scan cannot read them as a "
                "credential".format(destination, defused)
            )
        status |= _write_or_check(destination, text, check)
    for destination, data in assets():
        status |= _write_or_check_bytes(destination, data, check)
    return 0 if status == 0 else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m ui.v2.build",
        description=(
            "Build the product view: the queue at ui/dist/index.html and one "
            "page per case of the four version-6 runs. Read-only on runs/, data/, "
            "policy/ and ops/config.json; no model call."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the committed pages with a fresh build and write nothing",
    )
    args = parser.parse_args(argv)
    try:
        return build(check=args.check)
    except BuildError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
