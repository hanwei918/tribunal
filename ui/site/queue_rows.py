"""The Chinese queue table, built from the queue's own rows and a fixed vocabulary.

``cases.zh.html`` shows the same 151 disputes as the English ``cases.html``, and
until part 53b its table body was a copy of the English rows: every category, the
filing party, the status chip and the outcome were English on a Chinese page.
``ui/site/build.py`` now builds the English body from ``ui.v2.build``'s own row
function and the Chinese one from the same cases through this module, so the two
tables cannot come to disagree about a case and no English vocabulary can come
back into the Chinese one.

**What is translated, and what is not.** Only words are: the category, the filing
party, the four status chip labels, the outcome's ruling words, the trigger
phrases and the two sentences a cell carries under its chip. A figure, a case
number, a ruling code, a clause id and every ``data-`` attribute are the run's
own and are written unchanged, so a row sorts, links and reads its confidence
exactly as its English twin does.

The vocabulary is fixed here rather than derived, and ``tests/test_site.py``
holds every Chinese row to the same case id, amount, confidence, time and status
class as its English row, and holds the English words out of it.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.v2 import build as v2  # noqa: E402


def words(text: Any) -> str:
    """One row's own text, with the characters left as they are.

    ``ui.v2.build``'s ``_text`` writes every non-ASCII character as a numeric
    entity, because the queue's own pages are ASCII only. A Chinese page is not,
    and its table should read as the page around it does, so a vocabulary word is
    written in its own characters; only the four characters that would change the
    markup are escaped, exactly as the ASCII rows escape them.
    """
    if text is None:
        return ""
    return html.escape(str(text), quote=False)


def attribute(value: Any) -> str:
    """One attribute value, escaped the way ``ui.v2.build`` escapes its own."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def chip(kind: str, text: str, title: Any = None) -> str:
    """One status chip, in the shape and with the colour class the queue uses.

    ``ui.v2.build``'s own ``_chip`` writes the words through ``_text``, which
    would put a Chinese label on the page as numeric entities; this is the same
    markup with the characters left alone.
    """
    extra = ' title="{0}"'.format(attribute(title)) if title else ""
    return '<span class="chip {0}"{1}>{2}</span>'.format(
        attribute(kind), extra, words(text)
    )

# The category, as the Chinese pages name the two the track defines. ``\u7ed5\u8def`` is
# the phrase the try-it page's own case chips use for a route deviation and
# ``\u672a\u5230\u573a`` the one they use for a no-show charge.
ZH_CATEGORY: Mapping[str, str] = {
    "ROUTE_DEVIATION": "\u7ed5\u8def",
    "NO_SHOW_CHARGE": "\u672a\u5230\u573a",
}

# Who filed the dispute, as the table's own header names the column.
ZH_FILED_BY: Mapping[str, str] = {
    "RIDER": "\u4e58\u5ba2",
    "DRIVER": "\u53f8\u673a",
}

# The four short status labels, keyed by the lane ``ui.v2.build`` assigns.
ZH_CHIP: Mapping[str, str] = {
    "decided": "\u5df2\u81ea\u52a8\u5224\u51b3",
    "held": "\u5df2\u5224\uff0c\u7b49\u4eba\u653e\u6b3e",
    "reviewer": "\u5df2\u8f6c\u4eba\u5de5",
    "none": "\u65e0\u72b6\u6001\u8bb0\u5f55",
}

# The ruling values, as the outcome column words them.
ZH_RULING: Mapping[str, str] = {
    "FULL_REFUND": "\u5168\u989d\u9000\u6b3e",
    "PARTIAL_REFUND": "\u90e8\u5206\u9000\u6b3e",
    "NO_ACTION": "\u7ef4\u6301\u539f\u72b6",
    "DRIVER_COMPENSATION": "\u8d39\u7528\u7ef4\u6301\uff0c\u53f8\u673a\u83b7\u8865\u507f",
    "ESCALATE": "\u8f6c\u4eba\u5de5",
}

# The reviewer triggers. ``NO_MAJORITY`` names the panel size, so it is built by
# :func:`trigger_words` rather than typed here.
ZH_TRIGGER: Mapping[str, str] = {
    v2.TRIGGER_SCOPE: "\u5b89\u5168\u6216\u6295\u8bc9\u6807\u8bb0",
    v2.TRIGGER_NO_VALID_DRAFTS: "\u6ca1\u6709\u4e00\u4efd\u6cd5\u5b98\u8349\u7a3f\u901a\u8fc7\u4ee3\u7801\u68c0\u67e5",
    v2.TRIGGER_JUDGE: "\u6cd5\u5b98\u4f9d\u653f\u7b56\u8f6c\u4eba\u5de5",
}

ZH_NO_MAJORITY = "{0} \u4efd\u8349\u7a3f\u6ca1\u6709\u8fbe\u6210\u4e00\u81f4"

# What a case sent to a reviewer says where a decided case carries its ruling.
ZH_SENT_TO_A_REVIEWER = "\u8f6c\u4eba\u5de5"

# The ``data-label`` a cell carries for the mobile card view, matching the
# Chinese header row the page itself writes.
ZH_LABEL: Mapping[str, str] = {
    "case": "\u6848\u4ef6",
    "category": "\u7c7b\u522b",
    "filed_by": "\u63d0\u4ea4\u65b9",
    "amount": "\u4e89\u8bae\u91d1\u989d",
    "status": "\u72b6\u6001",
    "outcome": "\u7ed3\u679c",
    "confidence": "\u7f6e\u4fe1\u5ea6",
    "time": "\u7528\u65f6",
}

# The confidence cell of a decided case whose ruling carries no figure: the
# English table says ``none``, and a Chinese table says so in Chinese.
ZH_NO_CONFIDENCE = "\u65e0"


def trigger_words(trigger: str, votes: int) -> str:
    """The Chinese words one reviewer trigger is shown under."""
    if trigger == v2.TRIGGER_NO_MAJORITY:
        return ZH_NO_MAJORITY.format(votes)
    return ZH_TRIGGER.get(trigger, trigger)


def held_reason(case: "v2.CaseData") -> str:
    """Why a decided case's money is held for release, in one Chinese sentence.

    The clause id and both figures are the policy's own and are written
    unchanged; only the sentence around them is Chinese.
    """
    return "{0} \u8d85\u8fc7 POL-GEN-05 \u7684 {1} \u6267\u884c\u95e8\u69db".format(
        v2._money(v2.monetary_effect(case.ruling), case.policy.currency),
        v2._money(case.policy.execution_threshold, case.policy.currency),
    )


def status_chip(case: "v2.CaseData") -> str:
    """The short status chip, with the lane's colour class unchanged."""
    if case.trigger is not None:
        return chip("bad", ZH_CHIP["reviewer"])
    if v2._money_is_held(case):
        return chip("warn", ZH_CHIP["held"])
    if case.ruling.get("ruling") in (
        v2.FULL_REFUND,
        v2.PARTIAL_REFUND,
        v2.NO_ACTION,
        v2.pipeline_module.DRIVER_COMPENSATION,
    ):
        return chip("ok", ZH_CHIP["decided"])
    return chip("grey", ZH_CHIP["none"])


def status_cell(case: "v2.CaseData") -> str:
    """The status cell: the short chip, and its detail under it.

    The same shape the English row draws -- the chip alone, then the reason in
    the same small wrapping note -- so the two tables are the same table.
    """
    if case.trigger is not None:
        cell = chip("bad", ZH_CHIP["reviewer"])
        note = trigger_words(str(case.trigger), case.votes)
    else:
        cell = status_chip(case)
        note = held_reason(case) if v2._money_is_held(case) else ""
    if note:
        cell += '<span class="held-why">{0}</span>'.format(words(note))
    return cell


def outcome_text(case: "v2.CaseData") -> str:
    """The outcome column in Chinese, with every figure unchanged.

    The same four shapes the English column draws, including a refund that also
    pays the driver: that row names both amounts rather than only the refund.
    """
    ruling = case.ruling
    value = str(ruling.get("ruling"))
    currency = case.policy.currency
    if value == v2.ESCALATE and case.trigger is not None:
        return "{0} - {1}".format(
            ZH_SENT_TO_A_REVIEWER, trigger_words(str(case.trigger), case.votes)
        )
    amount = v2._decimal(ruling.get("amount_sgd"))
    driver = v2._decimal(ruling.get("driver_compensation_sgd"))
    words = ZH_RULING.get(value, value)
    if value == v2.pipeline_module.DRIVER_COMPENSATION and driver is not None:
        return "{0} - \u53f8\u673a\u83b7 {1}".format(words, v2._money(driver, currency))
    if value in v2.REFUND_RULINGS and amount is not None:
        if driver is not None:
            return "{0} - {1}\uff1b\u53f8\u673a\u83b7 {2}".format(
                words, v2._money(amount, currency), v2._money(driver, currency)
            )
        return "{0} - {1}".format(words, v2._money(amount, currency))
    return words


def row(case: "v2.CaseData") -> str:
    """One Chinese queue row, the shape of the English one and its own words.

    The cell order, the ``data-column`` names, the sort keys, the ``data-``
    attributes and the row's own class are exactly the English row's; only the
    text a reader reads is translated.
    """
    dispute = case.case.get("dispute") or {}
    currency = case.policy.currency
    confidence = case.ruling.get("confidence")
    if case.trigger is not None:
        confidence_text = "-"
    else:
        confidence_text = (
            ZH_NO_CONFIDENCE if confidence is None else str(confidence)
        )
    amount_sort = v2._decimal(dispute.get("amount_contested_sgd"))
    time_sort = v2._decimal(case.document.get("wall_seconds"))
    filed_by = dispute.get("filed_by")
    held = held_reason(case) if v2._money_is_held(case) else ""
    cells = (
        (
            "case",
            '<a href="{0}">{1}</a>'.format(attribute(case.link), words(case.case_no)),
            str(case.case_no),
            ZH_LABEL["case"],
            "",
        ),
        (
            "category",
            words(ZH_CATEGORY.get(case.category, case.category)),
            case.category,
            ZH_LABEL["category"],
            "",
        ),
        (
            "filed_by",
            words(ZH_FILED_BY.get(str(filed_by), str(filed_by))),
            str(filed_by),
            ZH_LABEL["filed_by"],
            "",
        ),
        (
            "amount",
            words(v2._money(dispute.get("amount_contested_sgd"), currency)),
            str(amount_sort if amount_sort is not None else 0),
            ZH_LABEL["amount"],
            "",
        ),
        ("status", status_cell(case), case.outcome_kind, ZH_LABEL["status"], held),
        (
            "outcome",
            words(outcome_text(case)),
            str(case.ruling.get("ruling")),
            ZH_LABEL["outcome"],
            "",
        ),
        (
            "confidence",
            words(confidence_text),
            confidence_text,
            ZH_LABEL["confidence"],
            "",
        ),
        (
            "time",
            words(v2._seconds(case.document.get("wall_seconds"))),
            str(time_sort if time_sort is not None else 0),
            ZH_LABEL["time"],
            "",
        ),
    )
    row_class = "reviewer" if case.trigger is not None else "auto"
    cells_html = "".join(
        '<td data-column="{0}" data-sort="{1}" data-label="{2}"{3}>{4}</td>'.format(
            attribute(name),
            attribute(sort),
            attribute(label),
            ' title="{0}"'.format(attribute(tip)) if tip else "",
            value,
        )
        for name, value, sort, label, tip in cells
    )
    return '<tr class="{0}" data-outcome="{1}" data-set="{2}">{3}</tr>'.format(
        row_class, case.outcome_kind, attribute(case.label), cells_html
    )


def rows(cases: Sequence["v2.CaseData"]) -> str:
    """Every Chinese row, in the order the queue lists them."""
    return "".join(row(case) for case in cases)
