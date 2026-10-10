"""The chat threat lane: a deterministic read of a chat message for a threat.

The handbook asks that a chat log be read for threats to a person's safety, and
that a dispute whose chat carries one be fast-tracked ahead of every other lane.
This module is that read. It is a **reader**: it takes one message's text and
says whether it carries a threat and which rules matched, and it changes nothing
in ``tribunal/``. ``ops/queue.py`` is the one caller, and the signal it reads
routes a dispute and never enters a brief or a prompt.

**The four rules the layer holds every module to, and how this one keeps them.**

* **No network.** It imports nothing but the standard library.
* **No answer key.** It opens no file at all: a message arrives as a string, and
  nothing here reads a case, a run or a key.
* **Sorted output.** ``matched`` is a sorted list of rule ids, and the JSON
  document the command prints sorts its keys, so two runs are byte-identical.
* **English.** Every rule, message and comment is English.

**The rule table.** Two kinds of rule, both listed in :data:`RULES`:

* **threat rules** -- explicit harm ("I will hurt/kill/find you"), intimidation
  by location or by third parties ("I know where you live", "my brothers know
  your car", "watch your back"), conditional menace ("see what happens when"),
  and doxxing ("post your photo/address");
* **exclusion rules** -- a complaint or a review ("report", "review", "dispute"),
  an idiom ("killing me" about traffic), and a safety warning ("careful, ...
  don't hurt").

A message is a threat when at least one threat rule matches **and** no exclusion
rule does. ``matched`` names every rule that matched, threat and exclusion alike,
so a reader can see why a message was cleared as well as why one was flagged.

**What is not built.** Agreement, disagreement and sentiment are not detected:
the fixture carries those labels and this module reads only the threat label.
Nothing here classifies a message for any other purpose.

**The command.** ``python3 -m ops.chat_signals`` reads message texts from
standard input -- a JSON array of strings (or of objects with a ``text`` key), or
one message per line -- and prints one verdict per message, in input order, as a
JSON document. ``eval/func_sets.py`` runs it this way over the 32-message fixture
at ``eval/fixtures/chat-signals-v1.json``; the fixture is under ``eval/``, which
``ops`` never opens, so the texts are handed to the command rather than read by
it.

**The score is a development figure.** The rules were written with that
32-message fixture visible, so the agreement ``eval/func_sets.py --report``
prints is measured on the data the rules were fitted to and is not a held-out
figure. The report says so in its own words.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple

# The two kinds of rule. A message is a threat when a ``THREAT`` rule matches and
# no ``EXCLUSION`` rule does.
THREAT = "threat"
EXCLUSION = "exclusion"

# The prefix every threat rule id carries, and the prefix every exclusion rule id
# carries, so a reader can tell the two kinds apart by the id alone.
THREAT_PREFIX = "THREAT-"
EXCLUSION_PREFIX = "EXCL-"


class Rule(NamedTuple):
    """One rule: an id, its kind, the pattern, and what it is for."""

    rule_id: str
    kind: str
    pattern: "re.Pattern[str]"
    description: str


# The rule table, in the order a reader meets it. Every pattern is matched with
# ``re.IGNORECASE`` and ``re.search``, so a rule matches anywhere in the message.
# The patterns are deliberately narrow: a rule names the words a person uses, not
# a word that merely looks like one.
RULES: Tuple[Rule, ...] = (
    Rule(
        "THREAT-HARM",
        THREAT,
        re.compile(
            r"\b(?:i will|i'll|i would|i'd|i am going to|i'm going to|im going to"
            r"|gonna|you better)\s+(?:hurt|kill|find|beat|break|smash|stab|shoot"
            r"|hunt|deal with)\b",
            re.IGNORECASE,
        ),
        "an explicit threat to hurt, kill or find a person",
    ),
    Rule(
        "THREAT-MENACE",
        THREAT,
        re.compile(r"\bsee what happens\b", re.IGNORECASE),
        "conditional menace: see what happens when ...",
    ),
    Rule(
        "THREAT-LOCATION",
        THREAT,
        re.compile(
            r"\bi know where you (?:live|stay|work|park)\b", re.IGNORECASE
        ),
        "intimidation by knowing where a person lives or works",
    ),
    Rule(
        "THREAT-WATCH",
        THREAT,
        re.compile(r"\bwatch your back\b", re.IGNORECASE),
        "intimidation by a warning to watch one's back",
    ),
    Rule(
        "THREAT-THIRD-PARTY",
        THREAT,
        re.compile(
            r"\b(?:my|the)\s+(?:brothers|boys|friends|people|guys|men)\s+know"
            r"\s+(?:your|where)\b",
            re.IGNORECASE,
        ),
        "intimidation by third parties who know a person or their car",
    ),
    Rule(
        "THREAT-DOXX",
        THREAT,
        re.compile(
            r"\b(?:post|publish|share|expose|leak)\s+(?:your|the)\s+"
            r"(?:photo|address|nric|ic|number|location|home)\b",
            re.IGNORECASE,
        ),
        "doxxing: to post a person's photo or address",
    ),
    Rule(
        "EXCL-COMPLAINT",
        EXCLUSION,
        re.compile(
            r"\b(?:report|review|dispute|complain|refund|feedback|rating)\b",
            re.IGNORECASE,
        ),
        "a complaint, a review or a dispute is not a safety threat",
    ),
    Rule(
        "EXCL-IDIOM",
        EXCLUSION,
        re.compile(
            r"\bkilling me\b|\bkill for\b|\bdying\b|\bto die for\b", re.IGNORECASE
        ),
        "an idiom about traffic, hunger or a dead battery is not a threat",
    ),
    Rule(
        "EXCL-SAFETY",
        EXCLUSION,
        re.compile(
            r"\bcareful\b[\s\S]*\b(?:dont|don't|do not)\s+hurt\b", re.IGNORECASE
        ),
        "a safety warning that tells someone not to hurt themselves",
    ),
)

# The rule ids by kind, so a caller can read the two sets without walking the
# table. Both are sorted tuples, so the two are deterministic.
THREAT_RULE_IDS: Tuple[str, ...] = tuple(
    sorted(rule.rule_id for rule in RULES if rule.kind == THREAT)
)
EXCLUSION_RULE_IDS: Tuple[str, ...] = tuple(
    sorted(rule.rule_id for rule in RULES if rule.kind == EXCLUSION)
)


def detect(message_text: Any) -> Dict[str, Any]:
    """Whether one message is a threat, and which rules matched.

    Returns ``{"threat": bool, "matched": [rule ids]}``. ``matched`` names every
    rule that matched -- threat and exclusion alike -- sorted, so a reader can
    see why a message was cleared as well as why one was flagged. A message is a
    threat when at least one threat rule matched and no exclusion rule did.

    A non-string is read as the empty string rather than refused: a caller that
    hands a ``null`` field wants "not a threat", not an exception.
    """
    text = "" if message_text is None else str(message_text)
    matched = sorted(rule.rule_id for rule in RULES if rule.pattern.search(text))
    threats = [rule_id for rule_id in matched if rule_id in THREAT_RULE_IDS]
    exclusions = [rule_id for rule_id in matched if rule_id in EXCLUSION_RULE_IDS]
    return {"threat": bool(threats) and not exclusions, "matched": matched}


def detect_all(message_texts: Sequence[Any]) -> List[Dict[str, Any]]:
    """One verdict per message, in input order, each carrying its ``index``."""
    return [
        {
            "index": index,
            "threat": verdict["threat"],
            "matched": verdict["matched"],
        }
        for index, verdict in enumerate(detect(text) for text in message_texts)
    ]


def read_texts(stream: Any) -> List[str]:
    """The message texts on one stream: a JSON array, or one message per line.

    A JSON array of strings, or of objects carrying a ``text`` key, is read as
    one; anything else is read as newline-delimited messages. A blank input is no
    messages rather than an error.
    """
    raw = stream.read()
    stripped = raw.strip()
    if not stripped:
        return []
    if stripped[0] in "[{":
        try:
            document = json.loads(stripped)
        except ValueError:
            document = None
        if isinstance(document, list):
            return [_text_of(item) for item in document]
        if isinstance(document, dict) and isinstance(document.get("messages"), list):
            return [_text_of(item) for item in document["messages"]]
    return [line for line in raw.splitlines() if line.strip()]


def _text_of(item: Any) -> str:
    """One item of a JSON array as a message text."""
    if isinstance(item, dict):
        return str(item.get("text", ""))
    return str(item)


def render(verdicts: Sequence[Dict[str, Any]]) -> str:
    """The verdicts as one JSON document: sorted keys, ASCII, one trailing line."""
    return json.dumps({"count": len(verdicts), "results": list(verdicts)}, sort_keys=True, indent=2) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ops.chat_signals",
        description=(
            "Read chat message texts and say whether each carries a threat. "
            "The texts come from standard input: a JSON array of strings (or of "
            "objects with a text key), or one message per line. Reads no file, "
            "makes no model call and writes nothing."
        ),
    )
    parser.add_argument(
        "--text",
        action="append",
        default=None,
        metavar="MESSAGE",
        help="one message text; repeat for more. With none, standard input is read.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Print one verdict per message, in input order."""
    args = _build_parser().parse_args(argv)
    texts = list(args.text) if args.text is not None else read_texts(sys.stdin)
    sys.stdout.write(render(detect_all(texts)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
