"""The four functional sets, and the checks over them that need no model call.

The four functional sets were imported on 2026-10-10, beside the policy
version-6 development data. Each exercises one functional property of the
system rather than its accuracy:

* **inject-v1** -- twelve cases in six invariance pairs. Cases 3107-3112 are the
  same trips as 3101-3106, drawn from the same random state, with one
  adversarial instruction added to party text. A case and its twin must reach
  the same four fields. The check is a *run*: it asks a model what it makes of
  the injected copy, so this module does not measure it and says so.
* **pii-v1** -- eight cases whose party text carries personal names, telephone
  numbers, e-mail addresses and vehicle plates, with place names that contain
  surnames as hard negatives. The check needs no model: the version-6 brief is
  built and every span the key names is looked for in it.
* **collusion-v1** -- eight cases read together as one case root, with a control
  or decoy beside every positive. The check needs no model: ``ops/risk.py`` is
  **run as a command** and its JSON is read, and the answer is held against the
  set's own key and its cross-case expectation.
* **chat-signals-v1** -- 32 labelled chat messages under ``eval/fixtures/``, not
  cases. The check is the label counts. No classifier exists yet: the fixture is
  the labelled set a classifier would be measured against, and nothing here
  classifies anything.

This module is under ``eval/``, so it may read ``eval/answers/``; nothing under
``tribunal/`` may, and nothing here is imported by it. It writes nothing: every
command is a reading, and ``--report`` prints to standard output.

**It imports no ``ops`` module.** The ops layer is a layer of its own and
``tests.test_ops_layer`` forbids the edge in either direction: nothing under
``tribunal/`` or ``eval/`` may import ``ops``, and ``ops`` may never open an
answer key. The collusion reading is therefore taken the way a person would take
it -- ``python3 -m ops.risk --case-root <root> --json`` is run as a subprocess
and its output is parsed -- rather than by importing the layer that produced it.

What "still present" means
--------------------------
``pii-v1``'s key lists, per case, the strings that must be masked before display
and the strings that must not be. A string the key says must be masked and that
the version-6 brief **still contains** is a leak: the mask did not reach it. The
version-6 mask implements ``POL-GEN-08(4)``'s vehicle registration marks only, so
today the plates are masked and the names, telephone numbers and e-mail addresses
are reported as found. Reporting is the whole of what this module does about
them: the gap is the policy's, not this reading's, and it is not fixed here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets  # noqa: E402
from tribunal import brief  # noqa: E402

# The three **case** sets this module reads, in the order the report prints them.
# The fourth functional set, ``inject-v1``, is registered beside them and is
# deliberately absent here: its check asks a model, so it is not a check this
# module can make.
FUNCTIONAL_SET_NAMES: Tuple[str, ...] = development_sets.FUNCTIONAL_SET_NAMES

# The chat fixture. It is not a case set and carries no cases: 32 messages with
# four labels each, under ``eval/fixtures/``.
CHAT_FIXTURE = PROJECT_ROOT / "eval" / "fixtures" / "chat-signals-v1.json"

# The policy version every brief here is built at. It is the version the three
# sets are registered for (base 3's latest), so it is the version their own runs
# would brief at -- a brief built at version 1 would answer a question nobody
# asked about these cases.
POLICY_VERSION = 6

# The span kinds the pii key uses, in the order the counts are printed. A kind
# absent from the key is printed as absent rather than dropped, so a new kind is
# visible the first time it appears.
SPAN_KINDS: Tuple[str, ...] = ("NAME", "PHONE", "EMAIL", "PLATE", "PLACE")

# The ops module the collusion reading is taken from, and the mode it is asked
# for. It is named as a command-line module rather than imported: see the module
# docstring.
RISK_MODULE = "ops.risk"

# The two comparison verdicts the collusion report counts.
MATCH = "match"
MISS = "miss"
EXTRA = "extra"


class FuncSetsError(Exception):
    """A reading this module cannot make."""


# --------------------------------------------------------------------------
# Reading the sets
# --------------------------------------------------------------------------
def answer_dir(name: str) -> Path:
    """One set's own answer directory, under ``eval/answers/``."""
    return development_sets.ANSWER_DIR / name


def case_root(name: str) -> Path:
    """One set's own case root, under ``data/external/``."""
    root = development_sets.named(name).case_root
    if root is None:
        raise FuncSetsError("{0} has no case root".format(name))
    return Path(root)


def read_json(path: Path) -> Any:
    """One UTF-8 JSON document. The keys are read, never written."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_case(name: str, case_no: int) -> Mapping[str, Any]:
    """One case, through the set's own index and its recorded digest."""
    return development_sets.named(name).load_case(case_no)


def case_numbers(name: str) -> Tuple[int, ...]:
    """Every case number of one set, in its index's order."""
    return tuple(development_sets.named(name).cases)


def brief_text(case: Mapping[str, Any], policy_version: int = POLICY_VERSION) -> str:
    """The canonical bytes of one case's brief, at the version this module reads.

    The same serialiser the pipeline hashes, so a string looked for here is
    looked for in the bytes the model would be handed and not in a second
    rendering of them.
    """
    return brief.brief_digest(
        brief.build_brief_for_case(case, policy_version=policy_version)
    )[0]


def key_of(name: str) -> Dict[int, Mapping[str, Any]]:
    """One set's ground-truth blocks, by case number."""
    return {
        record["case_no"]: record["ground_truth"]
        for record in read_json(answer_dir(name) / "ground_truth.json")
    }


# --------------------------------------------------------------------------
# pii-v1: what the version-6 brief does with each span
# --------------------------------------------------------------------------
def pii_rows() -> List[Mapping[str, Any]]:
    """The pii key's per-case rows, in file order.

    The key carries one further row that names no case -- a note about the
    organisers' sample and its converted case -- and it is kept apart from these
    rows rather than dropped, so the report can print it.
    """
    return [
        row
        for row in read_json(answer_dir("pii-v1") / "pii_spans.json")
        if "case_no" in row
    ]


def pii_notes() -> List[Mapping[str, Any]]:
    """The key's rows that name no case."""
    return [
        row
        for row in read_json(answer_dir("pii-v1") / "pii_spans.json")
        if "case_no" not in row
    ]


def pii_report() -> List[str]:
    """Every span of the pii key, against the version-6 brief of its own case."""
    lines: List[str] = [
        "For each case, every span the key says must be masked and whether the",
        "version-6 brief still contains it, then every span it says must not be",
        "masked and whether it survives. \"STILL PRESENT\" on a mask span is a",
        "leak: the mask did not reach it. Only PLATE is masked today; the other",
        "kinds are reported as found and are not fixed here.",
        "",
    ]
    masked = {kind: 0 for kind in SPAN_KINDS}
    leaked = {kind: 0 for kind in SPAN_KINDS}
    survives = {kind: 0 for kind in SPAN_KINDS}
    removed = {kind: 0 for kind in SPAN_KINDS}

    for row in pii_rows():
        case_no = row["case_no"]
        case = load_case("pii-v1", case_no)
        text = brief_text(case)
        lines.append(
            "  case {0}  ({1})".format(case_no, case["dispute"]["category"])
        )
        for span in row["mask"]:
            present = span["text"] in text
            masked[span["type"]] = masked.get(span["type"], 0) + 1
            if present:
                leaked[span["type"]] = leaked.get(span["type"], 0) + 1
            lines.append(
                "    mask   {0:<5} {1!r:<34} {2}".format(
                    span["type"],
                    span["text"],
                    "STILL PRESENT" if present else "masked",
                )
            )
        for span in row["do_not_mask"]:
            present = span["text"] in text
            survives[span["type"]] = survives.get(span["type"], 0) + 1
            if not present:
                removed[span["type"]] = removed.get(span["type"], 0) + 1
            lines.append(
                "    keep   {0:<5} {1!r:<34} {2}".format(
                    span["type"],
                    span["text"],
                    "survives" if present else "GONE",
                )
            )

    lines.append("")
    lines.append("  mask spans by kind:")
    for kind in SPAN_KINDS:
        if masked.get(kind):
            lines.append(
                "    {0:<6} {1} of {2} still present, {3} masked".format(
                    kind, leaked[kind], masked[kind], masked[kind] - leaked[kind]
                )
            )
    lines.append("  do-not-mask spans by kind:")
    for kind in SPAN_KINDS:
        if survives.get(kind):
            lines.append(
                "    {0:<6} {1} of {2} survive, {3} removed".format(
                    kind, survives[kind], survives[kind], removed[kind]
                )
            )

    total_masked = sum(masked.values())
    total_leaked = sum(leaked.values())
    lines.append("")
    lines.append(
        "  {0} mask spans over {1} cases; {2} still present, {3} masked.".format(
            total_masked, len(pii_rows()), total_leaked, total_masked - total_leaked
        )
    )
    lines.append(
        "  The mask implements POL-GEN-08(4)'s vehicle registration marks only,"
    )
    lines.append(
        "  so the {0} plate spans are masked and the {1} other spans are not.".format(
            masked.get("PLATE", 0), total_masked - masked.get("PLATE", 0)
        )
    )
    for note in pii_notes():
        lines.append("")
        lines.append("  note ({0}): {1}".format(note["external_reference"], note["note"]))
    return lines


# --------------------------------------------------------------------------
# collusion-v1: the risk layer against the key
# --------------------------------------------------------------------------
def expected_risk_tests(ground_truth: Mapping[str, Any]) -> Set[str]:
    """Which of the five policy tests the key says tripped.

    Read off the key's own two fields rather than its prose. The rule is: a test
    is expected to have tripped when the clause it belongs to is one the key's
    ruling rests on.

    * ``POL-NS-07`` is named on several no-show cases and is expected to trip
      only on the one that escalates -- on the others it is named because it was
      applied and did not trip.
    * ``POL-NS-09`` covers two limbs. Which one is the key's is stated by the
      profile field its rationale names: the pair counter for ``(c)``, the
      rider's trailing-30-day counter for ``(d)``.
    * ``POL-RD-06`` is expected to trip when it is named and the key's referrals
      send the driver to the clause's review limb.
    """
    clauses = set(ground_truth["governing_clauses"])
    ruling = ground_truth["expected_ruling"]
    rationale = ground_truth.get("rationale") or ""
    referrals = " ".join(ground_truth.get("expected_referrals") or [])

    expected: Set[str] = set()
    if ruling == "ESCALATE":
        if "POL-NS-07" in clauses:
            expected.add("POL-NS-07")
        if "POL-NS-09" in clauses:
            if "disputes_with_counterparty_90d" in rationale:
                expected.add("POL-NS-09(c)")
            if "no_show_disputes_30d" in rationale:
                expected.add("POL-NS-09(d)")
    elif "POL-RD-06" in clauses and "POL-RD-06" in referrals:
        expected.add("POL-RD-06")
    return expected


def collusion_expected_flags() -> Dict[int, List[int]]:
    """``cross_case.json``'s repeat_party expectation, by case number."""
    cross = read_json(answer_dir("collusion-v1") / "cross_case.json")
    return {
        row["case_no"]: sorted(flag["other_case"] for flag in row["flags"])
        for row in cross["expected_repeat_party"]
    }


def risk_reading(case_root: Path) -> Dict[int, Mapping[str, Any]]:
    """``ops/risk.py``'s reading of one case root, by case number.

    The module is **run**, not imported: ``eval/`` may not import ``ops`` (see
    the module docstring), so the reading is taken the way a person would take
    it. It is asked for its JSON mode, which is sorted and deterministic, and the
    interpreter is the one running this module, so the two halves cannot come
    from different Pythons.

    A non-zero exit is a refusal -- the root is not there, or a case cannot be
    read -- and is reported rather than parsed as an empty reading.
    """
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            RISK_MODULE,
            "--case-root",
            str(case_root),
            "--json",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise FuncSetsError(
            "{0} exited {1}: {2}".format(
                RISK_MODULE, completed.returncode, completed.stderr.strip()
            )
        )
    document = json.loads(completed.stdout)
    return {row["case_no"]: row for row in document["cases"]}


def collusion_report() -> List[str]:
    """The risk layer's flags over the root, against the key and cross_case.json."""
    root = case_root("collusion-v1")
    keys = key_of("collusion-v1")
    expected_flags = collusion_expected_flags()
    reading = risk_reading(root)

    lines: List[str] = [
        "ops/risk.py is run over the whole case root. Its repeat_party attention",
        "flag is held against eval/answers/collusion-v1/cross_case.json, and the",
        "five policy tests it reports are held against the key's risk clauses.",
        "The key's expectation is read from its own governing_clauses and",
        "expected_ruling (see expected_risk_tests).",
        "",
    ]

    flag_matches = flag_misses = flag_extras = 0
    risk_matches = risk_misses = risk_extras = 0
    for case_no in case_numbers("collusion-v1"):
        row = reading[case_no]
        tripped = sorted(
            signal["clause"] for signal in row["signals"] if signal["tripped"]
        )
        produced = sorted({flag["other_case_no"] for flag in row["attention"]})
        expected_repeat = expected_flags[case_no]
        expected_risk = sorted(expected_risk_tests(keys[case_no]))

        flag_matches += produced == expected_repeat
        flag_misses += len(set(expected_repeat) - set(produced))
        flag_extras += len(set(produced) - set(expected_repeat))
        risk_matches += tripped == expected_risk
        risk_misses += len(set(expected_risk) - set(tripped))
        risk_extras += len(set(tripped) - set(expected_risk))

        lines.append(
            "  case {0}  {1}  key ruling {2}".format(
                case_no, row["category"], keys[case_no]["expected_ruling"]
            )
        )
        lines.append(
            "    repeat_party  expected {0}  produced {1}  {2}".format(
                _numbers(expected_repeat),
                _numbers(produced),
                MATCH if produced == expected_repeat else "DIFFERS",
            )
        )
        lines.append(
            "    risk tests    expected {0}  tripped {1}  {2}".format(
                ", ".join(expected_risk) or "(none)",
                ", ".join(tripped) or "(none)",
                MATCH if tripped == expected_risk else "DIFFERS",
            )
        )

    lines.append("")
    lines.append(
        "  repeat_party: {0} of {1} cases match; {2} misses, {3} extras.".format(
            flag_matches, len(case_numbers("collusion-v1")), flag_misses, flag_extras
        )
    )
    lines.append(
        "  risk tests:   {0} of {1} cases match; {2} misses, {3} extras.".format(
            risk_matches, len(case_numbers("collusion-v1")), risk_misses, risk_extras
        )
    )
    lines.append("")
    lines.append(
        "  A risk test is a second reading of the profile counters for a reviewer"
    )
    lines.append(
        "  and never a policy finding: POL-GEN-01 forbids a profile from"
    )
    lines.append("  establishing a fact about the trip, so nothing here rules.")
    return lines


def _numbers(values: Sequence[int]) -> str:
    """A list of case numbers as the report spells it."""
    return "[" + ", ".join(str(value) for value in values) + "]"


# --------------------------------------------------------------------------
# chat-signals-v1: the fixture's counts per label
# --------------------------------------------------------------------------
CHAT_LABELS: Tuple[str, ...] = ("threat", "agreement", "disagreement")
SENTIMENTS: Tuple[str, ...] = ("NEG", "NEU", "POS")


def chat_report() -> List[str]:
    """The fixture's counts per label, recomputed and held against its own."""
    document = read_json(CHAT_FIXTURE)
    items = document["items"]
    declared = document["counts"]

    lines: List[str] = [
        "The fixture's counts per label. They are recomputed from the items and",
        "held against the counts the file itself states, so a drifted file is",
        "reported rather than copied.",
        "",
        "  set {0}, {1} messages".format(document["set"], len(items)),
        "",
    ]
    agrees = True
    for label in CHAT_LABELS:
        positive = sum(1 for item in items if item["labels"][label])
        negative = len(items) - positive
        agrees = agrees and declared[label] == {"positive": positive, "negative": negative}
        lines.append(
            "  {0:<13} positive {1:>3}   negative {2:>3}".format(
                label, positive, negative
            )
        )
    lines.append("")
    for sentiment in SENTIMENTS:
        count = sum(1 for item in items if item["labels"]["sentiment"] == sentiment)
        agrees = agrees and declared["sentiment"][sentiment] == count
        lines.append("  sentiment {0:<4} {1:>3}".format(sentiment, count))
    lines.append("")
    lines.append(
        "  the file's own counts agree with the recomputation: {0}".format(
            "yes" if agrees else "NO"
        )
    )
    lines.append("")
    lines.append("  No classifier exists yet: the fixture is the labelled set one")
    lines.append("  would be measured against, and nothing here classifies a")
    lines.append("  message. The label a threat carries is what routes a dispute to")
    lines.append("  the safety lane; no label enters a brief.")
    return lines


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
def report() -> str:
    """Every check this module makes, as text. Deterministic and ASCII."""
    lines: List[str] = [
        "The functional sets: the checks that need no model call",
        "=====================================================",
        "",
        "Policy version {0} throughout. Three case sets are read -- {1} --".format(
            POLICY_VERSION, ", ".join(FUNCTIONAL_SET_NAMES)
        ),
        "plus the chat fixture at eval/fixtures/chat-signals-v1.json.",
        "",
        "inject-v1 is the fourth functional set and is not measured here: its",
        "check is whether an injected copy of a case reaches its clean twin's",
        "four fields, which needs a model call and is not made.",
        "",
        "",
        "pii-v1: personal data in party text, and the version-6 brief",
        "-----------------------------------------------------------",
        "",
    ]
    lines.extend(pii_report())
    lines.extend(
        [
            "",
            "",
            "collusion-v1: the risk layer over the root, against the key",
            "-----------------------------------------------------------",
            "",
        ]
    )
    lines.extend(collusion_report())
    lines.extend(
        [
            "",
            "",
            "chat-signals-v1: the fixture's label counts",
            "-------------------------------------------",
            "",
        ]
    )
    lines.extend(chat_report())
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.func_sets",
        description=(
            "The checks over the functional sets that need no model call: the "
            "pii-v1 spans against the version-6 brief, the collusion-v1 risk "
            "flags against the key, and the chat-signals-v1 label counts. Reads "
            "and writes nothing."
        ),
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="print every check; the only thing this command does",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Print the checks. Nothing is written and no model is called."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.report:
        parser.error("nothing to do: pass --report (this module writes nothing)")
    sys.stdout.write(report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
