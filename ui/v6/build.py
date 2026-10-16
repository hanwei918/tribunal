"""The 151 version-6 case pages, in English and Chinese, in the site's own design.

Until this module the version-6 case pages were the product view's own pages
(``ui/v2/build.py``): English only, and drawn in the queue's older look, so a
reader who clicked into a case from the Chinese site landed on an English page
in another design. This module writes ``ui/dist/case-<NNNNN>.html`` and
``ui/dist/case-<NNNNN>.zh.html`` for every case of the four version-6 runs, in
the shell every other page of the site uses (``ui.v8.build.page``), from the same
records the product view reads (``ui.v2.build.read_every_case``).

The product view's own page for each case is kept, unchanged, at
``ui/dist/review-<NNNNN>.html``: it carries the step-by-step decision and, for a
case sent to a person, the escalation packet and the review form. Every page
written here links to it.

What is translated, and what is not
-----------------------------------
The page's own words are written in both languages here. What the parties wrote,
the chat, the advocates' points and the judge's reasoning are the record's own
and stay in English on the Chinese page, which says so where they appear. Every
figure, clause id and evidence id is read from the record and written unchanged.

Usage::

    python3 -m ui.v6.build            # write the 302 pages
    python3 -m ui.v6.build --check    # compare them with a fresh build
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.v2 import build as v2  # noqa: E402
from ui.v8 import build as v8  # noqa: E402

EN = "en"
ZH = "zh"
LANGUAGES = (EN, ZH)
DIST_DIR = v2.DIST_DIR

# The four cases the try-it page lets a reader change.
TRY_CASES = (103, 208, 901, 1779)
# The organisers' own sample.
ORGANISER_CASES = (901,)


class BuildError(Exception):
    """A page that cannot be built from the record."""


def esc(value: Any) -> str:
    return "" if value is None else html.escape(str(value), quote=True)


def dec(value: Any) -> Optional[Decimal]:
    return v2._decimal(value)


def money(value: Any) -> str:
    """``SGD 6.40``: the record's amount, two decimals, never re-rounded."""
    number = dec(value)
    if number is None:
        raise BuildError("an amount the page needs is not recorded")
    return "SGD {0:.2f}".format(number)


def plain(value: Any) -> str:
    """``6.40``: the amount without the currency, for the Chinese sentences."""
    number = dec(value)
    if number is None:
        raise BuildError("an amount the page needs is not recorded")
    return "{0:.2f}".format(number)


def whole(value: Any) -> str:
    number = dec(value)
    if number is None:
        return "-"
    return str(int(number.quantize(Decimal(1), rounding=ROUND_HALF_UP)))


def tenth(value: Any) -> str:
    number = dec(value)
    return "-" if number is None else "{0:.1f}".format(number)


def km(value: Any) -> str:
    number = dec(value)
    return "-" if number is None else "{0:.2f}".format(number)


def minsec(seconds: Any, language: str) -> str:
    total = int(dec(seconds).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    m, s = divmod(total, 60)
    if language == ZH:
        return "{0} \u5206 {1} \u79d2".format(m, s) if m else "{0} \u79d2".format(s)
    return "{0} min {1} s".format(m, s) if m else "{0} s".format(s)


def t(language: str, en: str, zh: str) -> str:
    return zh if language == ZH else en


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------
CATEGORY = {
    "ROUTE_DEVIATION": ("Route deviation", "\u7ed5\u8def"),
    "NO_SHOW_CHARGE": ("No-show fee", "\u672a\u5230\u573a\u8d39"),
}
PARTY = {"RIDER": ("rider", "\u4e58\u5ba2"), "DRIVER": ("driver", "\u53f8\u673a"), "SYSTEM": ("system", "\u7cfb\u7edf")}
EVIDENCE = {
    "TRIP_RECORD": ("Trip record", "\u884c\u7a0b\u8bb0\u5f55"),
    "GPS_TRACE": ("GPS trace", "GPS \u8f68\u8ff9"),
    "CHAT_LOG": ("Chat log", "\u804a\u5929\u8bb0\u5f55"),
    "FARE_BREAKDOWN": ("Fare breakdown", "\u8d39\u7528\u660e\u7ec6"),
    "RIDER_PROFILE": ("Rider profile", "\u4e58\u5ba2\u6863\u6848"),
    "DRIVER_PROFILE": ("Driver profile", "\u53f8\u673a\u6863\u6848"),
    "TRAFFIC_ADVISORY": ("Traffic advisory", "\u4ea4\u901a\u901a\u544a"),
}
ADMISSIBILITY = {
    "COMPLETE": ("complete", "\u5b8c\u6574", "ok"),
    "IMPAIRED": ("impaired", "\u53d7\u635f", "warn"),
    "MISSING": ("missing", "\u7f3a\u5931", "bad"),
}
ZONE = {
    "STANDARD": ("standard", "\u666e\u901a"),
    "LARGE_VENUE": ("large venue", "\u5927\u578b\u573a\u6240"),
    "TRANSPORT_HUB": ("transport hub", "\u4ea4\u901a\u67a2\u7ebd"),
    "AIRPORT": ("airport", "\u673a\u573a"),
}
RULING = {
    "FULL_REFUND": ("Full refund", "\u5168\u989d\u9000\u6b3e"),
    "PARTIAL_REFUND": ("Partial refund", "\u90e8\u5206\u9000\u6b3e"),
    "NO_ACTION": ("No change", "\u7ef4\u6301\u539f\u72b6"),
    "DRIVER_COMPENSATION": ("Fee stands, driver paid", "\u8d39\u7528\u6210\u7acb\uff0c\u53f8\u673a\u83b7\u8865\u507f"),
    "ESCALATE": ("Sent to a person", "\u8f6c\u4eba\u5de5"),
}
TRIGGER = {
    v2.TRIGGER_SCOPE: (
        "The dispute carries a safety flag, so no AI was asked to rule (POL-GEN-08).",
        "\u8fd9\u8d77\u4e89\u8bae\u5e26\u5b89\u5168\u6807\u8bb0\uff0c\u6309 POL-GEN-08 \u4e0d\u8ba9 AI \u5224\u3002",
    ),
    v2.TRIGGER_NO_VALID_DRAFTS: (
        "None of the judge's drafts passed the code checks, so there was nothing to carry.",
        "\u6cd5\u5b98\u7684\u8349\u7a3f\u6ca1\u6709\u4e00\u4efd\u901a\u8fc7\u4ee3\u7801\u68c0\u67e5\uff0c\u6ca1\u6709\u53ef\u4ee5\u91c7\u7528\u7684\u5224\u51b3\u3002",
    ),
    v2.TRIGGER_JUDGE: (
        "The judge sent it to a person, as the policy directs.",
        "\u6cd5\u5b98\u6309\u653f\u7b56\u89c4\u5b9a\uff0c\u628a\u5b83\u4ea4\u7ed9\u4e86\u4eba\u3002",
    ),
}
VERDICT = {
    "KEPT": ("kept", "\u4fdd\u7559", "ok"),
    "DISCARDED": ("thrown out", "\u5254\u9664", "bad"),
}
REASON = {
    "IMPAIRMENT_UNDISCLOSED": (
        "cites impaired evidence without saying so",
        "\u5f15\u7528\u4e86\u53d7\u635f\u8bc1\u636e\u5374\u6ca1\u8bf4\u660e",
    ),
    "PROFILE_FIELD_AS_GROUND": (
        "uses a profile field as a ground",
        "\u628a\u6863\u6848\u5b57\u6bb5\u5f53\u4f5c\u7406\u7531",
    ),
    "NO_EVIDENCE_ID": ("names no evidence", "\u6ca1\u6709\u6307\u660e\u8bc1\u636e"),
}


def category_words(case: "v2.CaseData", language: str) -> str:
    en, zh = CATEGORY.get(case.category, (case.category, case.category))
    return t(language, en, zh)


def party(value: Any, language: str) -> str:
    en, zh = PARTY.get(str(value), (str(value).lower(), str(value)))
    return t(language, en, zh)


def link(case_no: int, language: str) -> str:
    return "case-{0:05d}{1}.html".format(case_no, ".zh" if language == ZH else "")


def review_link(case_no: int) -> str:
    return v2.review_link_for(case_no)


# --------------------------------------------------------------------------
# Facts read from the record
# --------------------------------------------------------------------------
def votes_carried(case: "v2.CaseData") -> Tuple[int, int]:
    """(drafts that agreed with the carried ruling, drafts asked)."""
    drafts = v2._drafts(case.transcript)
    asked = len(drafts)
    agreed = sum(1 for d in drafts if d["valid"] and d["agrees"])
    return agreed, asked


def deviation(case: "v2.CaseData") -> Mapping[str, Any]:
    return v2._derived_block(case.brief, "GPS_TRACE", "deviation") or {}


def arrival(case: "v2.CaseData") -> Mapping[str, Any]:
    return v2._derived_block(case.brief, "GPS_TRACE", "arrival") or {}


def fare(case: "v2.CaseData") -> Mapping[str, Any]:
    return v2._derived_block(case.brief, "FARE_BREAKDOWN", "money") or {}


def headline(case: "v2.CaseData", language: str) -> str:
    """The page's title: the one fact the case turns on, read from the record."""
    if case.trigger == v2.TRIGGER_SCOPE:
        return t(language, "A safety flag: straight to a person", "\u5e26\u5b89\u5168\u6807\u8bb0\uff0c\u76f4\u63a5\u4ea4\u7ed9\u4eba")
    if case.category == "ROUTE_DEVIATION":
        block = deviation(case)
        excess = v2._fact_value(block, "excess_km")
        status = v2._fact_value(block, "status")
        if block.get("available") and excess is not None:
            if status == "no deviation":
                return t(
                    language,
                    "Only {0} km over the best route".format(km(excess)),
                    "\u53ea\u6bd4\u6700\u4f73\u8def\u7ebf\u591a {0} \u516c\u91cc".format(km(excess)),
                )
            return t(
                language,
                "{0} km longer than the best route".format(km(excess)),
                "\u6bd4\u6700\u4f73\u8def\u7ebf\u591a\u5f00\u4e86 {0} \u516c\u91cc".format(km(excess)),
            )
        return t(language, "The route record is incomplete", "\u8def\u7ebf\u8bb0\u5f55\u4e0d\u5b8c\u6574")
    block = arrival(case)
    if block.get("available"):
        dwell = v2._fact_value(block, "accumulated_dwell", "longest_run_sec")
        fixes = dec(v2._fact_value(block, "driver_fix_count")) or Decimal(0)
        radius = dec(v2._fact_value(block, "thresholds", "arrival_radius_m"))
        track = v2._derived_block(case.brief, "GPS_TRACE", "driver_track") or {}
        nearest = dec(v2._fact_value(track, "min_distance_m"))
        sparse = fixes < 20 or any(
            "LOW_SAMPLE_RATE" in row["issues"]
            for row in v2._evidence(case.brief)
            if row["evidence_type"] == "GPS_TRACE"
        )
        if sparse:
            return t(
                language,
                "The GPS trace is too sparse to show the wait",
                "GPS \u8bb0\u5f55\u592a\u7a00\uff0c\u770b\u4e0d\u51fa\u53f8\u673a\u7b49\u4e86\u591a\u4e45",
            )
        if dwell is not None and dec(dwell) and dec(dwell) > 0:
            return t(
                language,
                "The driver waited {0} at the pickup".format(minsec(dwell, EN)),
                "\u53f8\u673a\u5728\u63a5\u5ba2\u70b9\u7b49\u4e86 {0}".format(minsec(dwell, ZH)),
            )
        if nearest is not None and radius is not None and nearest > radius:
            return t(
                language,
                "The driver never got inside the pickup zone",
                "\u53f8\u673a\u59cb\u7ec8\u6ca1\u8fdb\u63a5\u5ba2\u5708",
            )
        return t(
            language,
            "No GPS fix shows the driver waiting at the pickup",
            "GPS \u4e0a\u770b\u4e0d\u5230\u53f8\u673a\u5728\u63a5\u5ba2\u70b9\u7b49\u5019",
        )
    return t(language, "The arrival record is incomplete", "\u5230\u8fbe\u8bb0\u5f55\u4e0d\u5b8c\u6574")


def outcome(case: "v2.CaseData", language: str) -> str:
    """One sentence: what was decided and what moves."""
    ruling = case.ruling
    value = str(ruling.get("ruling"))
    amount = ruling.get("amount_sgd")
    driver = ruling.get("driver_compensation_sgd")
    if case.trigger is not None:
        first = t(
            language,
            "No AI ruling: a person decides, and the money is held until then.",
            "AI \u6ca1\u6709\u5224\uff0c\u4ea4\u7ed9\u4eba\u51b3\u5b9a\uff1b\u5728\u6b64\u4e4b\u524d\u94b1\u5148\u51bb\u7ed3\u3002",
        )
        if case.trigger == v2.TRIGGER_NO_MAJORITY:
            why = t(
                language,
                "The {0} drafts did not agree.".format(case.votes),
                "{0} \u4efd\u8349\u7a3f\u6ca1\u6709\u8fbe\u6210\u4e00\u81f4\u3002".format(case.votes),
            )
        else:
            en, zh = TRIGGER[case.trigger]
            why = t(language, en, zh)
        return first + (" " if language == EN else "") + why
    if value == "DRIVER_COMPENSATION":
        text = t(
            language,
            "The fee stands; the driver is paid {0}.".format(money(driver)),
            "\u8d39\u7528\u6210\u7acb\uff0c\u53f8\u673a\u83b7\u5f97 {0} \u65b0\u5143\u3002".format(plain(driver)),
        )
    elif value == "FULL_REFUND":
        text = t(
            language,
            "Full refund of {0}.".format(money(amount)),
            "\u5168\u989d\u9000\u56de {0} \u65b0\u5143\u3002".format(plain(amount)),
        )
    elif value == "PARTIAL_REFUND":
        text = t(
            language,
            "{0} refunded.".format(money(amount)),
            "\u9000\u56de {0} \u65b0\u5143\u3002".format(plain(amount)),
        )
    elif value == "NO_ACTION":
        text = t(
            language,
            "No change: the record does not support the complaint.",
            "\u7ef4\u6301\u539f\u72b6\uff1a\u8bb0\u5f55\u4e0d\u652f\u6301\u8fd9\u6b21\u6295\u8bc9\u3002",
        )
    else:
        raise BuildError("case {0}: an unknown ruling {1}".format(case.case_no, value))
    if value in ("FULL_REFUND", "PARTIAL_REFUND") and driver is not None:
        text += t(
            language,
            " The driver is paid {0}.".format(money(driver)),
            "\u53f8\u673a\u53e6\u83b7 {0} \u65b0\u5143\u3002".format(plain(driver)),
        )
    if v2._money_is_held(case):
        text += t(
            language,
            " Over the {0} threshold, so a person releases it.".format(
                money(case.policy.execution_threshold)
            ),
            "\u91d1\u989d\u8d85\u8fc7 {0} \u65b0\u5143\u7684\u6267\u884c\u95e8\u69db\uff0c\u7531\u4eba\u786e\u8ba4\u540e\u653e\u6b3e\u3002".format(
                plain(case.policy.execution_threshold)
            ),
        )
    return text


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------
STYLE = (
    "<style>"
    ".say{margin:0;font-size:15.5px;line-height:1.6}"
    ".evl{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px}"
    ".evl li{font:12px/1.2 var(--mono);padding:7px 9px}"
    ".evl li.ok{background:var(--ok-wash);color:var(--ok)}"
    ".evl li.warn{background:var(--warn-wash);color:var(--warn)}"
    ".evl li.bad{background:var(--bad-wash);color:var(--bad)}"
    ".chatv{list-style:none;margin:8px 0;padding:0;display:flex;flex-direction:column;gap:8px;font-size:14.5px;line-height:1.5}"
    ".chatv li{padding:10px 12px;background:var(--paper);border-left:3px solid var(--line)}"
    ".chatv li.d{border-left-color:var(--accent)}"
    ".chatv li.s{border-left-color:var(--muted);color:var(--muted)}"
    ".chatv .when{font:12px var(--mono);color:var(--muted);margin-right:8px}"
    ".fx{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:6px 16px;margin:0;font-size:14.5px}"
    ".fx dt{color:var(--band-2)}"
    ".fx dd{margin:0;font-family:var(--mono)}"
    ".drafts.plain{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px;font-size:15px}"
    ".drafts.plain li.no{opacity:.65}"
    ".pts{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:12px}"
    ".pts li{padding:12px 14px;background:var(--paper);border-left:3px solid var(--ok)}"
    ".pts li.out{border-left-color:var(--bad)}"
    ".pts .v{display:inline-block;font:11px/1 var(--mono);letter-spacing:.06em;padding:5px 7px;margin-bottom:6px}"
    ".pts .v.ok{background:var(--ok-wash);color:var(--ok)}"
    ".pts .v.bad{background:var(--bad-wash);color:var(--bad)}"
    ".pts .ids{font:12px/1.5 var(--mono);color:var(--muted);margin:6px 0 0}"
    ".casenav{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:28px}"
    ".note{font-size:14px;color:var(--muted)}"
    "@media (max-width:620px){.fx{grid-template-columns:minmax(0,1fr)}.fx dd{margin-bottom:6px}}"
    "</style>"
)

ICON = (
    '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v16M8 20h8M5 7h14M5 7L2 13h6zM19 7l-3 6h6z"/></svg>'
)


def heading(title: str, sub: str = "") -> str:
    return (
        '<div class="sh" data-rise>{0}<h2 class="display">{1}</h2>{2}</div>'.format(
            '<span class="ico">{0}</span><br>'.format(ICON) if ICON else "",
            esc(title),
            "<p>{0}</p>".format(esc(sub)) if sub else "",
        )
    )


def accordion(title: str, inner: str, lang_en: bool = False) -> str:
    return (
        '<div class="acc" style="margin-top:24px"><div class="acc-item">'
        '<button type="button" class="acc-btn" aria-expanded="false"><span>{0}</span>'
        '<span class="pm" aria-hidden="true"></span></button>'
        '<div class="acc-panel"><div><div class="in"{1}>{2}</div></div></div>'
        "</div></div>"
    ).format(esc(title), ' lang="en"' if lang_en else "", inner)


def refund_note(case: "v2.CaseData", language: str) -> str:
    """The one line ``ui.v2.build.refund_over_contested`` draws, in this page's words.

    POL-RD-02 computes a refund from the fare and does not cap it at the amount
    the rider named, while POL-GEN-03's wording says a partial refund returns
    part of the contested amount; where the refund is the larger, the page says so.
    """
    if not v2.refund_over_contested(case):
        return ""
    dispute = case.case.get("dispute") or {}
    contested = dispute.get("amount_contested_sgd")
    filer = str(dispute.get("filed_by") or "")
    return t(
        language,
        "The refund is the fare difference POL-RD-02 computes, which here is more than the {0} the {1} asked for; the policy does not cap it at the amount contested (POL-GEN-03).".format(
            money(contested), party(filer, EN)
        ),
        "\u9000\u6b3e\u662f\u6309 POL-RD-02 \u7528\u8f66\u8d39\u5dee\u989d\u7b97\u51fa\u7684\uff0c\u8fd9\u91cc\u6bd4{1}\u63d0\u51fa\u7684 {0} \u65b0\u5143\u8fd8\u591a\uff1b\u653f\u7b56\u6ca1\u6709\u628a\u9000\u6b3e\u9650\u5236\u5728\u4e89\u8bae\u91d1\u989d\u4ee5\u5185\uff08POL-GEN-03\uff09\u3002".format(
            plain(contested), party(filer, ZH)
        ),
    )


def hero(case: "v2.CaseData", language: str) -> str:
    dispute = case.case.get("dispute") or {}
    kicker = " \u00b7 ".join(
        [
            category_words(case, language),
            t(
                language,
                "filed by the {0}".format(party(dispute.get("filed_by"), EN)),
                "{0}\u6295\u8bc9".format(party(dispute.get("filed_by"), ZH)),
            ),
            money(dispute.get("amount_contested_sgd")),
            t(language, "policy version 6", "\u7b2c 6 \u7248\u653f\u7b56"),
        ]
    )
    crumb = '<p class="crumb"><a href="{0}">{1}</a> / <a href="{2}#all">{3}</a> / {4}</p>'.format(
        t(language, "index.html", "index.zh.html"),
        t(language, "Home", "\u9996\u9875"),
        t(language, "cases.html", "cases.zh.html"),
        t(language, "Cases", "\u6848\u4f8b"),
        esc(t(language, "Case {0}", "\u6848\u4ef6 {0}").format(case.case_no)),
    )
    disclosure = ""
    over = refund_note(case, language)
    if over:
        disclosure += '<p class="note" style="color:var(--band-2)">{0}</p>'.format(esc(over))
    if case.trigger is None:
        disclosure += '<p class="note" style="color:var(--band-2)">{0}</p>'.format(
            esc(
                t(
                    language,
                    "A provisional ruling made by an automated system. Either side may ask for a person instead.",
                    "\u8fd9\u662f\u81ea\u52a8\u7cfb\u7edf\u4f5c\u51fa\u7684\u521d\u6b65\u88c1\u51b3\u3002\u4efb\u4f55\u4e00\u65b9\u90fd\u53ef\u4ee5\u8981\u6c42\u6539\u7531\u4eba\u6765\u5904\u7406\u3002",
                )
            )
        )
    return (
        '<section class="band phero"><div class="wrap"><div class="phero-grid"><div>'
        "{0}"
        '<p class="kicker" style="color:var(--band-2)">{1}</p>'
        '<h1 class="display" style="font-size:clamp(38px,5.6vw,72px)">{2}</h1>'
        '<p class="lede">{3}</p>{4}'
        "</div>"
        '<div class="art"><img src="assets/step-check.webp" alt="" loading="lazy" decoding="async"></div>'
        "</div></div></section>"
    ).format(crumb, esc(kicker), esc(headline(case, language)), esc(outcome(case, language)), disclosure)


def figures(case: "v2.CaseData", language: str) -> str:
    evidence = v2._evidence(case.brief)
    rider = v2._claims(case.transcript, "RIDER")
    driver = v2._claims(case.transcript, "DRIVER")
    points = rider + driver
    kept = sum(1 for p in points if p["status"] == "KEPT")
    agreed, asked = votes_carried(case)
    confidence = case.ruling.get("confidence")
    wall = case.document.get("wall_seconds")
    cards: List[Tuple[str, str]] = [
        (str(len(evidence)), t(language, "pieces of evidence", "\u9879\u8bc1\u636e")),
    ]
    if points:
        cards.append(
            (
                "{0} vs {1}".format(len(rider), len(driver)),
                t(language, "points made (rider vs driver)", "\u6761\u8bba\u70b9\uff08\u4e58\u5ba2 vs \u53f8\u673a\uff09"),
            )
        )
        cards.append(
            (
                "{0}/{1}".format(kept, len(points)),
                t(language, "points kept by the code checks", "\u6761\u8bba\u70b9\u901a\u8fc7\u4ee3\u7801\u68c0\u67e5"),
            )
        )
    else:
        cards.append(("-", t(language, "points made: the lawyers were not asked", "\u6761\u8bba\u70b9\uff1a\u6ca1\u6709\u8be2\u95ee\u5f8b\u5e08")))
        cards.append(("0", t(language, "model calls", "\u6b21\u6a21\u578b\u8c03\u7528")))
    if asked:
        cards.append(
            (str(asked), t(language, "rulings drafted, one with the sides swapped", "\u4efd\u5224\u51b3\u8349\u7a3f\uff0c\u5176\u4e2d\u4e00\u4efd\u53cc\u65b9\u5bf9\u8c03"))
        )
    else:
        cards.append(("0", t(language, "rulings drafted: the judge was not asked", "\u4efd\u5224\u51b3\u8349\u7a3f\uff1a\u6ca1\u6709\u8be2\u95ee\u6cd5\u5b98")))
    if case.trigger is None:
        cards.append(
            (
                "{0}/{1}".format(agreed, asked),
                t(
                    language,
                    "agreed; confidence {0}".format(confidence),
                    "\u4efd\u4e00\u81f4\uff1b\u7f6e\u4fe1\u5ea6 {0}".format(confidence),
                ),
            )
        )
        value = str(case.ruling.get("ruling"))
        if value == "DRIVER_COMPENSATION":
            big = money(case.ruling.get("driver_compensation_sgd"))
            words = t(language, "to the driver, in {0} s", "\u4ed8\u7ed9\u53f8\u673a\uff0c\u7528\u65f6 {0} \u79d2")
        elif value in ("FULL_REFUND", "PARTIAL_REFUND"):
            big = money(case.ruling.get("amount_sgd"))
            words = t(language, "back to the rider, in {0} s", "\u9000\u7ed9\u4e58\u5ba2\uff0c\u7528\u65f6 {0} \u79d2")
        else:
            big = "SGD 0.00"
            words = t(language, "moves, in {0} s", "\u4e0d\u52a8\u94b1\uff0c\u7528\u65f6 {0} \u79d2")
        cards.append((big, words.format(tenth(wall))))
    else:
        if asked:
            cards.append(
                (
                    "{0}/{1}".format(
                        sum(1 for d in v2._drafts(case.transcript) if d["valid"]), asked
                    ),
                    t(language, "drafts passed the code checks", "\u4efd\u8349\u7a3f\u901a\u8fc7\u4ee3\u7801\u68c0\u67e5"),
                )
            )
        else:
            cards.append(("-", t(language, "no vote was taken", "\u6ca1\u6709\u6295\u7968")))
        cards.append(
            (
                t(language, "To a person", "\u8f6c\u4eba\u5de5"),
                t(language, "after {0} s", "\u7528\u65f6 {0} \u79d2").format(tenth(wall)),
            )
        )
    items = "".join(
        '<li data-rise><span class="n">{0:02d}</span><span class="big">{1}</span><p>{2}</p></li>'.format(
            index + 1, esc(big), esc(words)
        )
        for index, (big, words) in enumerate(cards)
    )
    return (
        '<section class="paper"><div class="wrap">{0}<ol class="flow f6">{1}</ol></div></section>'
    ).format(heading(t(language, "The case in six figures.", "\u516d\u4e2a\u6570\u5b57\u770b\u8fd9\u4e2a\u6848\u5b50\u3002")), items)


def sides(case: "v2.CaseData", language: str) -> str:
    dispute = v2._brief_dispute(case)
    filed_by = str(dispute.get("filed_by") or "")
    other = "DRIVER" if filed_by == "RIDER" else "RIDER"
    statement = dispute.get("counterparty_statement")
    statement = statement if isinstance(statement, Mapping) else {}
    original = t(language, "", "\uff08\u82f1\u6587\u539f\u6587\uff09")
    cards = [
        '<div class="card"><span class="kicker">{0}</span><p class="say" lang="en">{1}</p></div>'.format(
            esc(
                t(
                    language,
                    "The {0}'s complaint".format(party(filed_by, EN)),
                    "{0}\u7684\u6295\u8bc9{1}".format(party(filed_by, ZH), original),
                )
            ),
            esc(dispute.get("claim_text")),
        ),
        '<div class="card"><span class="kicker">{0}</span><p class="say"{1}>{2}</p></div>'.format(
            esc(
                t(
                    language,
                    "The {0}'s account".format(party(other, EN)),
                    "{0}\u7684\u8bf4\u6cd5{1}".format(party(other, ZH), original if statement.get("text") else ""),
                )
            ),
            ' lang="en"' if statement.get("text") else "",
            esc(
                statement.get("text")
                or t(language, "No statement is recorded.", "\u8bb0\u5f55\u91cc\u6ca1\u6709\u5bf9\u65b9\u7684\u8bf4\u6cd5\u3002")
            ),
        ),
    ]
    messages = v2._chat_messages(case)
    lines = []
    for message in messages:
        sender = str(message.get("sender"))
        kind = {"DRIVER": "d", "SYSTEM": "s"}.get(sender, "r")
        lines.append(
            '<li class="{0}"><span class="when">{1}</span><b>{2}</b> {3}</li>'.format(
                kind,
                esc(v2._clock(message.get("sent_at"))),
                esc(party(sender, language)),
                esc(message.get("text")),
            )
        )
    chat = (
        '<ul class="chatv" lang="en">{0}</ul>'.format("".join(lines))
        if lines
        else "<p>{0}</p>".format(esc(t(language, "No chat message is recorded.", "\u6ca1\u6709\u804a\u5929\u8bb0\u5f55\u3002")))
    )
    return (
        '<section class="paper" style="padding-top:0"><div class="wrap">{0}'
        '<div class="cards c2">{1}</div>{2}</div></section>'
    ).format(
        heading(
            t(language, "What each side said.", "\u53cc\u65b9\u600e\u4e48\u8bf4\u3002"),
            t(language, "In their own words, as filed.", "\u63d0\u4ea4\u65f6\u7684\u539f\u8bdd\u3002"),
        ),
        "".join(cards),
        accordion(
            t(language, "The in-app chat ({0})", "\u5e94\u7528\u5185\u804a\u5929\uff08{0} \u6761\uff09").format(len(messages)),
            chat,
        ),
    )


def facts(case: "v2.CaseData", language: str) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    if case.category == "ROUTE_DEVIATION":
        block = deviation(case)
        money_block = fare(case)
        if block.get("available"):
            rows.append((t(language, "Distance driven", "\u5b9e\u9645\u91cc\u7a0b"), "{0} km".format(km(v2._fact_value(block, "trace_distance_km")))))
            rows.append((t(language, "Best route", "\u6700\u4f73\u8def\u7ebf"), "{0} km".format(km(v2._fact_value(block, "optimal_distance_km")))))
            pct = dec(v2._fact_value(block, "excess_pct"))
            rows.append(
                (
                    t(language, "Extra distance", "\u591a\u51fa\u7684\u91cc\u7a0b"),
                    "{0} km ({1}%)".format(
                        km(v2._fact_value(block, "excess_km")),
                        "-" if pct is None else "{0:.1f}".format(pct),
                    ),
                )
            )
        charged = v2._fact_value(money_block, "charged_total")
        if charged is not None:
            rows.append((t(language, "Fare charged", "\u5b9e\u6536\u8f66\u8d39"), money(charged)))
        recomputed = v2._fact_value(money_block, "recomputed_fare")
        if recomputed is not None:
            rows.append((t(language, "Fare on the best route", "\u6309\u6700\u4f73\u8def\u7ebf\u91cd\u7b97"), money(recomputed)))
        payable = v2._fact_value(money_block, "refund", "payable")
        if payable is not None:
            rows.append((t(language, "Refund the rule gives", "\u89c4\u5219\u7b97\u51fa\u7684\u9000\u6b3e"), money(payable)))
        return rows
    block = arrival(case)
    money_block = fare(case)
    if block.get("available"):
        dwell = v2._fact_value(block, "accumulated_dwell", "longest_run_sec")
        if dwell is not None:
            rows.append((t(language, "Driver's wait inside the pickup zone", "\u53f8\u673a\u5728\u63a5\u5ba2\u5708\u5185\u7b49\u5019"), "{0} s".format(whole(dwell))))
        wait = v2._fact_value(block, "thresholds", "minimum_dwell_sec")
        if wait is not None:
            rows.append((t(language, "Free waiting time", "\u514d\u8d39\u7b49\u5f85\u65f6\u95f4"), "{0} s".format(whole(wait))))
        zone = v2._fact_value(block, "pickup_zone_class")
        if zone is not None:
            en, zh = ZONE.get(str(zone), (str(zone), str(zone)))
            rows.append((t(language, "Pickup point", "\u4e0a\u8f66\u70b9\u7c7b\u578b"), t(language, en, zh)))
    presence = v2._derived_block(case.brief, "GPS_TRACE", "rider_presence") or {}
    nearest = v2._fact_value(presence, "min_distance_m")
    if presence.get("available") and nearest is not None:
        rows.append((t(language, "Rider's phone, nearest to the pickup", "\u4e58\u5ba2\u624b\u673a\u79bb\u4e0a\u8f66\u70b9\u6700\u8fd1"), "{0} m".format(whole(nearest))))
    for key, en, zh in (
        ("fee_charged", "Fee charged", "\u5df2\u6536\u8d39\u7528"),
        ("schedule_fee", "Fee the rule allows", "\u89c4\u5219\u5141\u8bb8\u7684\u8d39\u7528"),
        ("driver_compensation", "Driver's share if the fee stands", "\u8d39\u7528\u6210\u7acb\u65f6\u53f8\u673a\u6240\u5f97"),
    ):
        value = v2._fact_value(money_block, key)
        if value is not None:
            rows.append((t(language, en, zh), money(value)))
    return rows


def code_section(case: "v2.CaseData", language: str) -> str:
    evidence = []
    for row in v2._evidence(case.brief):
        en, zh = EVIDENCE.get(str(row["evidence_type"]), (str(row["evidence_type"]), str(row["evidence_type"])))
        s_en, s_zh, kind = ADMISSIBILITY.get(str(row["status"]), (str(row["status"]).lower(), str(row["status"]), "warn"))
        evidence.append(
            '<li class="{0}">{1} \u00b7 {2} \u00b7 {3}</li>'.format(
                kind, esc(t(language, en, zh)), esc(t(language, s_en, s_zh)), esc(row["weight"])
            )
        )
    rows = facts(case, language)
    dl = "".join("<dt>{0}</dt><dd>{1}</dd>".format(esc(k), esc(v)) for k, v in rows)
    return (
        '<section class="band"><div class="wrap">{0}<div class="egrid">'
        '<div class="rcard"><span class="kicker">{1}</span><ul class="evl">{2}</ul></div>'
        '<div class="rcard"><span class="kicker">{3}</span><dl class="fx">{4}</dl></div>'
        "</div></div></section>"
    ).format(
        heading(
            t(language, "What the code found.", "\u4ee3\u7801\u67e5\u5230\u4e86\u4ec0\u4e48\u3002"),
            t(
                language,
                "Worked out before any AI reads the case. Impaired or missing evidence weighs less, or nothing.",
                "\u5728 AI \u8bfb\u6848\u5b50\u4e4b\u524d\u5c31\u7b97\u597d\u3002\u53d7\u635f\u6216\u7f3a\u5931\u7684\u8bc1\u636e\u6743\u91cd\u964d\u4f4e\uff0c\u751a\u81f3\u4e3a\u96f6\u3002",
            ),
        ),
        esc(t(language, "Evidence, and the weight each carries", "\u8bc1\u636e\u548c\u5404\u81ea\u7684\u6743\u91cd")),
        "".join(evidence),
        esc(t(language, "Facts and money", "\u4e8b\u5b9e\u548c\u91d1\u989d")),
        dl or "<dt>-</dt><dd>-</dd>",
    )


def points_section(case: "v2.CaseData", language: str) -> str:
    blocks = []
    for side in ("RIDER", "DRIVER"):
        claims = v2._claims(case.transcript, side)
        items = []
        for claim in claims:
            status = str(claim["status"])
            v_en, v_zh, kind = VERDICT.get(status, (status.lower(), status, "bad"))
            reason = ""
            if status != "KEPT" and claim.get("reason_code"):
                r_en, r_zh = REASON.get(str(claim["reason_code"]), (str(claim["reason_code"]), str(claim["reason_code"])))
                reason = " - " + t(language, r_en, r_zh)
            ids = ", ".join(list(claim["evidence_ids"]) + list(claim["clause_ids"]))
            items.append(
                '<li class="{0}"><span class="v {1}">{2}{3}</span><p class="say" lang="en">{4}</p>{5}</li>'.format(
                    "" if status == "KEPT" else "out",
                    kind,
                    esc(t(language, v_en, v_zh)),
                    esc(reason),
                    esc(claim["text"]),
                    '<p class="ids">{0}</p>'.format(esc(ids)) if ids else "",
                )
            )
        title = t(
            language,
            "The {0}'s AI lawyer: {1} points",
            "{0}\u7684 AI \u5f8b\u5e08\uff1a{1} \u6761\u8bba\u70b9",
        ).format(party(side, language), len(claims))
        body = '<ul class="pts">{0}</ul>'.format("".join(items)) if items else "<p>{0}</p>".format(
            esc(t(language, "No point was made: the lawyers were not asked.", "\u6ca1\u6709\u8bba\u70b9\uff1a\u8fd9\u4e2a\u6848\u5b50\u6ca1\u6709\u8be2\u95ee\u5f8b\u5e08\u3002"))
        )
        blocks.append(accordion(title, body))
    return (
        '<section class="paper"><div class="wrap">{0}{1}</div></section>'
    ).format(
        heading(
            t(language, "What the two AI lawyers argued.", "\u4e24\u4f4d AI \u5f8b\u5e08\u600e\u4e48\u5435\u3002"),
            t(
                language,
                "Each point names its evidence and its rule; a point the code cannot match to both is thrown out before the judge sees it.",
                "\u6bcf\u6761\u8bba\u70b9\u90fd\u8981\u5199\u660e\u8bc1\u636e\u548c\u89c4\u5219\uff1b\u4ee3\u7801\u5bf9\u4e0d\u4e0a\u7684\uff0c\u5728\u6cd5\u5b98\u770b\u5230\u4e4b\u524d\u5c31\u5254\u9664\u3002",
            ),
        ),
        "".join(blocks),
    )


CLAUSE_RE = re.compile(r"POL-[A-Z]+-\d+")


def decision_section(case: "v2.CaseData", language: str) -> str:
    drafts = v2._drafts(case.transcript)
    lines = []
    for draft in drafts:
        swapped = draft["kind"] == "position_swapped"
        label = t(language, "Draft {0}", "\u7b2c {0} \u4efd").format(draft["draft"])
        if swapped:
            label += t(language, " (sides swapped)", "\uff08\u53cc\u65b9\u5bf9\u8c03\uff09")
        if not draft["valid"]:
            body = t(language, "set aside by the code checks", "\u672a\u901a\u8fc7\u4ee3\u7801\u68c0\u67e5\uff0c\u4f5c\u5e9f")
            cls = "no"
        else:
            value = str(draft["ruling"])
            en, zh = RULING.get(value, (value, value))
            body = t(language, en, zh)
            figure = draft["driver_compensation_sgd"] if value == "DRIVER_COMPENSATION" else draft["amount_sgd"]
            if figure is not None and value != "ESCALATE":
                body += " \u00b7 " + money(figure)
            cls = ""
        lines.append('<li class="{0}">{1} \u2014 {2}</li>'.format(cls, esc(label), esc(body)))
    explanation = str(case.ruling.get("explanation") or "")
    clauses = sorted(set(CLAUSE_RE.findall(explanation)))
    if drafts:
        left = '<div class="card"><ol class="drafts plain">{0}</ol></div>'.format("".join(lines))
    else:
        left = '<div class="card"><p>{0}</p></div>'.format(
            esc(t(language, "The judge was not asked.", "\u6ca1\u6709\u8be2\u95ee\u6cd5\u5b98\u3002"))
        )
    right = '<div class="card"><span class="kicker">{0}</span><p>{1}</p></div>'.format(
        esc(t(language, "Rules the reasoning cites", "\u7406\u7531\u4e2d\u5f15\u7528\u7684\u6761\u6b3e")),
        esc(", ".join(clauses) or t(language, "none", "\u65e0")),
    )
    paragraphs = "".join("<p>{0}</p>".format(esc(p)) for p in explanation.split("\n") if p.strip())
    if case.trigger is not None:
        sub = t(
            language,
            "Three of the four drafts must agree. Here no ruling was carried.",
            "\u56db\u4efd\u8349\u7a3f\u81f3\u5c11\u4e09\u4efd\u4e00\u81f4\u624d\u7b97\u6570\u3002\u8fd9\u4e2a\u6848\u5b50\u6ca1\u6709\u5f62\u6210\u5224\u51b3\u3002",
        )
        label = t(language, "Why it went to a person (in English)", "\u4e3a\u4ec0\u4e48\u4ea4\u7ed9\u4eba\uff08\u82f1\u6587\u539f\u6587\uff09")
    else:
        sub = t(
            language,
            "The judge rules four times, once with the two sides swapped, to check it favours no one.",
            "\u6cd5\u5b98\u5224\u56db\u6b21\uff0c\u5176\u4e2d\u4e00\u6b21\u628a\u53cc\u65b9\u4f4d\u7f6e\u5bf9\u8c03\uff0c\u68c0\u67e5\u6709\u6ca1\u6709\u504f\u5fc3\u3002",
        )
        label = t(language, "The judge's full reasoning (in English)", "\u6cd5\u5b98\u7684\u5b8c\u6574\u7406\u7531\uff08\u82f1\u6587\u539f\u6587\uff09")
    return (
        '<section class="paper" style="padding-top:0"><div class="wrap">{0}<div class="egrid">{1}{2}</div>{3}</div></section>'
    ).format(
        heading(t(language, "How it was decided.", "\u600e\u4e48\u5224\u7684\u3002"), sub),
        left,
        right,
        accordion(label, paragraphs, lang_en=True),
    )


def notice_section(case: "v2.CaseData", language: str) -> str:
    value = str(case.ruling.get("ruling"))
    amount = case.ruling.get("amount_sgd")
    driver = case.ruling.get("driver_compensation_sgd")
    if case.trigger is not None:
        rider = driver_words = t(
            language,
            "No decision yet. A person will decide, and the money stays held until then.",
            "\u8fd8\u6ca1\u6709\u7ed3\u679c\u3002\u7531\u4eba\u6765\u51b3\u5b9a\uff0c\u5728\u6b64\u4e4b\u524d\u94b1\u5148\u51bb\u7ed3\u3002",
        )
    elif value == "DRIVER_COMPENSATION":
        rider = t(language, "The fee stands; no refund.", "\u8fd9\u7b14\u8d39\u7528\u6210\u7acb\uff0c\u4e0d\u9000\u6b3e\u3002")
        driver_words = t(language, "You are paid {0}.".format(money(driver)), "\u4f60\u4f1a\u62ff\u5230 {0} \u65b0\u5143\u3002".format(plain(driver)))
    elif value in ("FULL_REFUND", "PARTIAL_REFUND"):
        rider = t(language, "You get {0} back.".format(money(amount)), "\u4f60\u4f1a\u62ff\u56de {0} \u65b0\u5143\u3002".format(plain(amount)))
        driver_words = (
            t(language, "You are paid {0}.".format(money(driver)), "\u4f60\u4f1a\u62ff\u5230 {0} \u65b0\u5143\u3002".format(plain(driver)))
            if driver is not None
            else t(language, "The rider gets {0} back.".format(money(amount)), "\u4e58\u5ba2\u62ff\u56de {0} \u65b0\u5143\u3002".format(plain(amount)))
        )
    else:
        rider = t(language, "No change: the record does not support the complaint.", "\u7ef4\u6301\u539f\u72b6\uff1a\u8bb0\u5f55\u4e0d\u652f\u6301\u8fd9\u6b21\u6295\u8bc9\u3002")
        driver_words = t(language, "No change.", "\u7ef4\u6301\u539f\u72b6\uff0c\u6ca1\u6709\u53d8\u52a8\u3002")
    if v2._money_is_held(case):
        held = t(
            language,
            " A person releases the money first, because it is over {0}.".format(money(case.policy.execution_threshold)),
            "\u91d1\u989d\u8d85\u8fc7 {0} \u65b0\u5143\uff0c\u5148\u7531\u4eba\u786e\u8ba4\u518d\u653e\u6b3e\u3002".format(plain(case.policy.execution_threshold)),
        )
        rider += held
        driver_words += held
    appeal = t(
        language,
        "Under the team's version-6 policy (POL-GEN-04) either side may appeal once within 30 days, to a reviewer who has not seen the case. Ryde's v2.1, used from version 7, has no appeal clause.",
        "\u6309\u56e2\u961f\u7b2c 6 \u7248\u653f\u7b56\uff08POL-GEN-04\uff09\uff0c\u4efb\u4f55\u4e00\u65b9\u53ef\u5728 30 \u5929\u5185\u7533\u8bc9\u4e00\u6b21\uff0c\u7531\u6ca1\u770b\u8fc7\u8fd9\u5355\u7684\u5ba1\u6838\u5458\u5904\u7406\u3002\u4ece\u7b2c 7 \u7248\u8d77\u91c7\u7528\u7684 Ryde v2.1 \u6ca1\u6709\u7533\u8bc9\u6761\u6b3e\u3002",
    )
    cards = (
        '<div class="card"><span class="kicker">{0}</span><p>{1}</p></div>'
        '<div class="card"><span class="kicker">{2}</span><p>{3}</p></div>'
    ).format(
        esc(t(language, "To the rider", "\u7ed9\u4e58\u5ba2")),
        esc(rider),
        esc(t(language, "To the driver", "\u7ed9\u53f8\u673a")),
        esc(driver_words),
    )
    return (
        '<section class="paper"><div class="wrap">{0}<div class="cards c2">{1}</div>'
        '<p class="note" style="margin-top:20px">{2}</p></div></section>'
    ).format(
        heading(
            t(language, "What each side is told.", "\u53cc\u65b9\u4f1a\u6536\u5230\u4ec0\u4e48\u3002"),
            t(language, "A preview: nothing is sent and no money moves.", "\u53ea\u662f\u9884\u89c8\uff0c\u4e0d\u4f1a\u771f\u7684\u53d1\u9001\uff0c\u4e5f\u4e0d\u4f1a\u52a8\u94b1\u3002"),
        ),
        cards,
        esc(appeal),
    )


def review_section(case: "v2.CaseData", language: str) -> str:
    if case.trigger is not None:
        body = t(
            language,
            "The reviewer gets one packet: the evidence and its weights, both lawyers' points, every draft and the judge's words. The review form is on the reviewer's page.",
            "\u5ba1\u6838\u5458\u62ff\u5230\u4e00\u4e2a\u5ba1\u6838\u5305\uff1a\u8bc1\u636e\u548c\u6743\u91cd\u3001\u53cc\u65b9\u5f8b\u5e08\u7684\u8bba\u70b9\u3001\u6bcf\u4e00\u4efd\u8349\u7a3f\u548c\u6cd5\u5b98\u7684\u539f\u8bdd\u3002\u5ba1\u6838\u8868\u5355\u5728\u5ba1\u6838\u5458\u89c6\u56fe\u91cc\u3002",
        )
        title = t(language, "For the person who decides.", "\u4ea4\u7ed9\u51b3\u5b9a\u7684\u4eba\u3002")
    else:
        body = t(
            language,
            "The reviewer's page shows every step of this decision in the record's own words.",
            "\u5ba1\u6838\u5458\u89c6\u56fe\u6309\u8bb0\u5f55\u539f\u6587\u5c55\u793a\u8fd9\u6b21\u5224\u51b3\u7684\u6bcf\u4e00\u6b65\u3002",
        )
        title = t(language, "The full record.", "\u5b8c\u6574\u8bb0\u5f55\u3002")
    return (
        '<section class="paper" style="padding-top:0"><div class="wrap">{0}'
        '<p><a class="btn" href="{1}">{2} -&gt;</a></p></div></section>'
    ).format(
        heading(title, body),
        esc(review_link(case.case_no)),
        esc(t(language, "Open the reviewer's page (English)", "\u6253\u5f00\u5ba1\u6838\u5458\u89c6\u56fe\uff08\u82f1\u6587\uff09")),
    )


def nav(case: "v2.CaseData", cases: Sequence["v2.CaseData"], index: int, language: str) -> str:
    prev_link = next_link = ""
    if index > 0:
        prev_case = cases[index - 1]
        prev_link = '<a class="ul" href="{0}">&lt;- {1}</a>'.format(
            link(prev_case.case_no, language), esc(t(language, "Case {0}", "\u6848\u4ef6 {0}").format(prev_case.case_no))
        )
    if index + 1 < len(cases):
        next_case = cases[index + 1]
        next_link = '<a class="ul" href="{0}">{1} -&gt;</a>'.format(
            link(next_case.case_no, language), esc(t(language, "Case {0}", "\u6848\u4ef6 {0}").format(next_case.case_no))
        )
    middle = '<a class="ul" href="{0}#all">{1}</a>'.format(
        t(language, "cases.html", "cases.zh.html"),
        esc(t(language, "All {0} disputes", "\u5168\u90e8 {0} \u4e2a\u4e89\u8bae").format(len(cases))),
    )
    extra = ""
    if case.case_no in TRY_CASES:
        extra = '<p style="margin-top:20px"><a class="ul" href="{0}">{1} -&gt;</a></p>'.format(
            t(language, "try.html", "try.zh.html"),
            esc(t(language, "Change this case on the try-it page", "\u5728\u201c\u8bd5\u4e00\u8bd5\u201d\u91cc\u6539\u8fd9\u4e2a\u6848\u5b50")),
        )
    recorded = str(case.document.get("recorded_at") or "")[:10]
    if case.case_no in ORGANISER_CASES:
        source = t(
            language,
            "The organisers' sample case, recorded on {0} at policy version 6 (the team's own policy).",
            "\u4e3b\u529e\u65b9\u7684\u6837\u4f8b\u6848\u4ef6\uff0c{0} \u6309\u7b2c 6 \u7248\uff08\u56e2\u961f\u81ea\u5df1\u7684\u653f\u7b56\uff09\u5f55\u5236\u3002",
        )
    else:
        source = t(
            language,
            "A test case, recorded on {0} at policy version 6 (the team's own policy).",
            "\u6d4b\u8bd5\u6848\u4ef6\uff0c{0} \u6309\u7b2c 6 \u7248\uff08\u56e2\u961f\u81ea\u5df1\u7684\u653f\u7b56\uff09\u5f55\u5236\u3002",
        )
    return (
        '<section class="paper" style="padding-top:0"><div class="wrap">'
        '<div class="casenav">{0}{1}{2}</div>{3}<p class="note" style="margin-top:20px">{4}</p>'
        "</div></section>"
    ).format(
        prev_link or "<span></span>", middle, next_link or "<span></span>", extra, esc(source.format(recorded))
    )


def case_main(case, cases, index, language) -> str:
    return "".join(
        [
            STYLE,
            hero(case, language),
            figures(case, language),
            sides(case, language),
            code_section(case, language),
            points_section(case, language),
            decision_section(case, language),
            notice_section(case, language),
            review_section(case, language),
            nav(case, cases, index, language),
        ]
    )


def case_page(case, cases, index, language) -> str:
    title = "{0} - {1} - Tribunal Agent".format(
        t(language, "Case {0}", "\u6848\u4ef6 {0}").format(case.case_no), headline(case, language)
    )
    description = "{0}: {1}".format(category_words(case, language), outcome(case, language))
    return v8.page(
        language,
        title=title,
        description=description,
        main=case_main(case, cases, index, language),
        en_href=link(case.case_no, EN),
        zh_href=link(case.case_no, ZH),
    )


def written_paths() -> frozenset:
    """Every path this builder writes, relative to ``ui/dist/``, built from nothing.

    The case numbers are the four runs' own, read off their directories, so a
    test can hold the builders apart without building a page.
    """
    names = []
    for set_name in v2.SET_ORDER:
        for case_no in v2._case_numbers(v2._run_for(set_name).run_dir):
            for language in LANGUAGES:
                names.append(link(case_no, language))
    return frozenset(names)


def pages() -> List[Tuple[Path, str]]:
    cases = v2.read_every_case()
    out: List[Tuple[Path, str]] = []
    for index, case in enumerate(cases):
        for language in LANGUAGES:
            out.append((DIST_DIR / link(case.case_no, language), case_page(case, cases, index, language)))
    return out


def build(check: bool = False) -> int:
    status = 0
    for destination, text in pages():
        status |= v2._write_or_check(destination, text, check)
    return 0 if status == 0 else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m ui.v6.build",
        description="Write the 151 version-6 case pages in English and Chinese.",
    )
    parser.add_argument("--check", action="store_true", help="compare with a fresh build; write nothing")
    args = parser.parse_args(argv)
    try:
        return build(check=args.check)
    except (BuildError, v2.BuildError) as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
