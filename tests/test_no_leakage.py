"""No case identifier reaches the prompts or the policy.

The judge can be shown three trees: the prompt templates in ``prompts/``, the
policy in ``policy/``, and the closures selected out of ``precedents/``. The
first two are shared by every case and are the two this module scans: anything
in either that names one particular case is a leak of that case's identity into
every call the system ever makes -- and the leak is permanent, because a prompt
or a policy file is not rebuilt per case.

``precedents/`` is the third tree and is deliberately **not** scanned, because
nothing it can hand the judge carries a case identifier. The block is built by
:func:`tribunal.precedents.block`, and the guarantee is in what it **emits**:
each item carries only ``precedent_id``, ``category``, ``clause_ids`` and
``ruling``, and the block only a fixed ``note`` and those items. It *is* handed
entries that carry ``case_no`` and ``dispute_id`` -- those are the stored entries
-- so the guarantee is about the output, not about the input. The choosing
happens one level up, in :func:`tribunal.precedents.matches`, which uses
``case_no`` and ``dispute_id`` to **exclude** the case being judged rather than
to name it, and is otherwise a function of the category, the clause ids a kept
claim cites and the contested amount.

This module asserts that leak does not exist. It walks ``prompts/`` and
``policy/`` and looks for four kinds of identifier:

* a case file stem, ``case-NNNNN``;
* a ``dispute_id`` value, ``DSP-NNNNN``;
* a trip id, ``TRP-NNNNN``;
* an evidence id, ``EV-<KIND>-<digits>``.

The identifiers are **built, not typed**. A hand-written list would drift: a set
added later, a case added later, or an id scheme changed later would leave the
check quietly measuring yesterday's corpus. So the tokens come from the registry
itself -- :data:`eval.development_sets.BY_NAME`, every registered set, the
development ones and the sealed ones and the re-run one -- and from each set's
own index, its own answer key and its own cases. Every kind is derived from those
files rather than listed here, and a test asserts each kind came back non-empty,
so a harvest that silently stopped working fails rather than passing.

**Bare numbers do not count.** The policy legitimately carries fees, distances,
thresholds and day counts, and the corpus's own case numbers are five-digit
numbers that occur inside legitimate policy prose. Only a *prefixed* identifier
is looked for, which is why the patterns above carry their prefixes.

**What a failure says.** The file and the kind of token, and nothing else --
never the token, and never the text around it. This module's own output is
committed, and a failure that quoted the surrounding line would copy case
material into a place that has none. So no assertion compares ``Violation``
tuples, which unittest would print in full: every comparison goes through
:func:`report`, which is the whole of the message format, and a test pins it.

**The one violation that is known, and why it stays.** One real identifier does
appear under ``prompts/``: the advocate template's worked example cites
``EV-GPS-00208``, which is a genuine evidence id of corpus case 208. It is not a
mistake in this check; it is a mistake in the prompt, and it is a mistake the
repository has already made once and fixed once -- the verifier prompt's worked
example was rewritten to invented placeholder ids (``EV-DEMO-00042`` and
``EV-DEMO-00051``) for exactly this reason, and the note that records it says
none of those ids appears anywhere in the repository.

The advocate example is **not** fixed here, and the reason is the same one that
freezes the judge prompt's ``referee_ledger`` naming: the prompt is sent with
every request, so editing it changes every request, and the whole point of the
change this module ships beside is that no byte sent to a model moved. So the
violation is named and pinned instead of hidden: it is asserted to be the *only*
one, and it is asserted to be *still there*, so a new leak fails this module and
so does a fix that leaves the pin behind. Removing the pin is the first thing a
reader should do after the example is rewritten.

Run from the project root with::

    python3 -m unittest tests.test_no_leakage -v
"""

from __future__ import annotations

import collections
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets  # noqa: E402
from tribunal import brief, loader, money  # noqa: E402

# The two trees the agents are briefed from. Nothing else is scanned: the point
# is what a model is handed, and a model is handed these two and no more.
SCANNED_DIRECTORIES = ("prompts", "policy")

# One identifier kind, and the pattern that recognises it. Each pattern carries
# its prefix, so a bare number can never match: the policy's own "3.80" and the
# corpus's own "00208" are not identifiers of anything.
PATTERNS = {
    "case file stem": re.compile(r"case-\d{5}"),
    "dispute id": re.compile(r"DSP-\d{5}"),
    "trip id": re.compile(r"TRP-\d{5}"),
    "evidence id": re.compile(r"EV-[A-Z]+-\d+(?:-\d+)*"),
}

# One finding: where it was, what kind it was, and which token it was. The token
# is carried so the pin below can be exact; it is never printed -- see
# :func:`report`.
Violation = collections.namedtuple("Violation", "path kind token")

# The identifiers that are known to be there, and are not being fixed. See the
# module docstring: the advocate template's worked example cites a real evidence
# id, and the template cannot be edited without changing every request.
KNOWN_VIOLATIONS = (
    Violation("prompts/v1/advocate.system.md", "evidence id", "EV-GPS-00208"),
)


# --------------------------------------------------------------------------
# Building the identifiers
# --------------------------------------------------------------------------
def _strings(node):
    """Every string in a parsed JSON value, keys included."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _strings(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _strings(value)


def _harvest(texts, tokens):
    """Add every identifier in ``texts`` to ``tokens``, by kind."""
    for text in texts:
        for kind, pattern in PATTERNS.items():
            tokens[kind].update(pattern.findall(text))


def _index_path(development_set):
    """A set's own index: the manifest for the corpus, its own for a second set."""
    if development_set.case_root is None:
        return PROJECT_ROOT / "data" / "index.json"
    return Path(development_set.case_root) / "index.json"


def identifiers():
    """Every case identifier of every registered set, by kind.

    Four sources, and each is the set's own rather than a copy:

    * the **registry** -- every set in ``BY_NAME``, development, sealed and
      re-run, and its own ``cases`` tuple, which is where the case file stems
      come from;
    * each set's **index**, parsed and walked;
    * each set's **answer key**, parsed and walked -- the keys carry evidence ids
      in their explanations, which is one of the ways an id could travel;
    * each set's **cases**, loaded through the set's own loader, parsed and
      walked.
    """
    tokens = {kind: set() for kind in PATTERNS}
    for development_set in development_sets.BY_NAME.values():
        for case_no in development_set.cases:
            tokens["case file stem"].add("case-{0:05d}".format(case_no))
        _harvest(
            _strings(json.loads(_index_path(development_set).read_text(encoding="utf-8"))),
            tokens,
        )
        _harvest(
            _strings(json.loads(Path(development_set.key_path).read_text(encoding="utf-8"))),
            tokens,
        )
        for case_no in development_set.cases:
            _harvest(_strings(development_set.load_case(case_no)), tokens)
    return {kind: frozenset(values) for kind, values in tokens.items()}


# --------------------------------------------------------------------------
# Scanning
# --------------------------------------------------------------------------
def scan(root, tokens):
    """Every identifier of ``tokens`` that appears under ``root``'s two trees.

    The returned path is relative to ``root``, so the same function reads the
    repository and a fixture without either one's paths leaking into the other's
    message.
    """
    root = Path(root)
    found = []
    for directory in SCANNED_DIRECTORIES:
        for path in sorted((root / directory).rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for kind, values in tokens.items():
                for token in values:
                    if token in text:
                        found.append(
                            Violation(
                                str(path.relative_to(root)).replace("\\", "/"),
                                kind,
                                token,
                            )
                        )
    return sorted(found)


def report(violations):
    """One line per violation: the file and the kind of token, and nothing else.

    This is the whole of what a failure prints. The token is not printed and
    neither is the line it sat on: this module's output is committed, and the
    text around a leaked identifier is exactly the text that must not be copied
    anywhere.
    """
    return sorted("{0}: {1}".format(item.path, item.kind) for item in violations)


def _all_keys(node):
    """Every key in a parsed JSON value, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _all_keys(value)


# --------------------------------------------------------------------------
# A version-3 brief carries no provenance and names no other case
# --------------------------------------------------------------------------
# The two cases a version-3 brief is built for below: one of each category. 101
# is a route-deviation case and 201 a no-show case, and both are corpus cases,
# so neither belongs to a sealed set.
VERSION_THREE_BRIEF_CASES = (101, 201)

# What version 3's policies carry inside their ``sources`` keys, and what must
# therefore not reach a brief: Ryde's own help centre, the organisers' sample,
# and a sealed set's author. Matched case-insensitively, because a brief that
# said "Sealed" would leak exactly as much as one that said "sealed".
PROVENANCE_STRINGS = ("help.rydesharing", "DISP-002", "organiser", "sealed")

# The provenance keys ``brief.py`` drops. The draft's own notes call the
# top-level one ``policy_sources``; the file spells it ``sources``. Both are
# removed, so this list names both.
PROVENANCE_KEYS = ("sources", "policy_sources")


class VersionThreeBriefTests(unittest.TestCase):
    """What a version-3 brief must not carry.

    The policies at version 3 record their provenance in ``sources`` keys: on a
    clause, on ``fee_schedule`` and ``fare_model``, and once at the top level of
    ``general.json``. Those keys name Ryde's help centre, the organisers' sample
    and a sealed set, and every case-number mention in the draft's files sits
    inside one. ``notes`` is what the model reads and ``sources`` is for people,
    so ``brief.py`` drops every one of them before the policies are injected.

    This class builds real version-3 briefs and looks at what they hold, rather
    than trusting the filter's name. Every assertion is over a fixed string, a
    set of keys, or a count -- never over a case identifier, because this
    module's own output is committed and a failure must not copy one anywhere.
    """

    @classmethod
    def setUpClass(cls):
        cls.tokens = identifiers()
        cls.briefs = {
            case_no: brief.build_brief_for_case(
                loader.load_case(case_no), policy_version=3
            )
            for case_no in VERSION_THREE_BRIEF_CASES
        }
        cls.texts = {
            case_no: money.dumps_canonical(document)
            for case_no, document in cls.briefs.items()
        }

    def own_tokens(self, case_no):
        """Every identifier of the case itself, which its own brief may carry."""
        text = "\n".join(_strings(loader.load_case(case_no)))
        found = set()
        for pattern in PATTERNS.values():
            found.update(pattern.findall(text))
        return found

    # -- the control ------------------------------------------------------
    def test_the_policies_really_are_the_version_three_ones(self):
        """A brief that was not briefed at version 3 would pass vacuously."""
        for case_no, document in sorted(self.briefs.items()):
            with self.subTest(case_no=case_no):
                self.assertEqual("3.0.0", document["policies"]["general"]["version"])
                self.assertEqual("3.0.0", document["policies"]["category"]["version"])

    def test_the_raw_policies_do_carry_provenance(self):
        """The filter is doing work: the files it is handed carry the strings."""
        raw = loader.load_policies("NO_SHOW_CHARGE", 3)
        self.assertIn("sources", set(_all_keys(raw["category"])))
        self.assertTrue(
            any(
                needle.lower() in money.dumps_canonical(raw).lower()
                for needle in PROVENANCE_STRINGS
            ),
            "the version-3 files carry none of the provenance strings",
        )

    # -- the property -----------------------------------------------------
    def test_the_brief_carries_no_provenance_key_at_any_depth(self):
        for case_no, document in sorted(self.briefs.items()):
            with self.subTest(case_no=case_no):
                present = sorted(
                    set(_all_keys(document["policies"])) & set(PROVENANCE_KEYS)
                )
                self.assertEqual([], present, "a provenance key reached the brief")

    def test_the_brief_carries_no_provenance_string(self):
        for case_no, text in sorted(self.texts.items()):
            lowered = text.lower()
            for needle in PROVENANCE_STRINGS:
                with self.subTest(case_no=case_no, needle=needle):
                    self.assertNotIn(needle.lower(), lowered)

    def test_the_brief_names_no_other_case(self):
        """No case, dispute, trip or evidence id other than the case's own."""
        for case_no, text in sorted(self.texts.items()):
            own = self.own_tokens(case_no)
            foreign = sorted(
                {
                    kind
                    for kind, values in self.tokens.items()
                    for token in values
                    if token not in own and token in text
                }
            )
            with self.subTest(case_no=case_no):
                self.assertEqual(
                    [], foreign, "an identifier of another case reached the brief"
                )

    # -- the raw tree -----------------------------------------------------
    def test_the_scan_reaches_the_version_three_policy_directory(self):
        """``policy/`` is walked whole, so ``policy/v3/`` is covered too.

        The three version-3 files carry provenance, and a case identifier could
        reach them as easily as it could reach a version-1 clause. The walk is
        what covers them, so the coverage is pinned rather than assumed: a later
        change that narrowed the walk would fail here.
        """
        scanned = {
            str(path.relative_to(PROJECT_ROOT))
            for directory in SCANNED_DIRECTORIES
            for path in (PROJECT_ROOT / directory).rglob("*")
            if path.is_file()
        }
        for name in (
            "general.json",
            "no_show.json",
            "route_deviation.json",
            "CHANGES.md",
        ):
            with self.subTest(file=name):
                self.assertIn("policy/v3/{0}".format(name), scanned)


class NoLeakageTests(unittest.TestCase):
    """The two trees, the identifiers, and the one finding that is pinned."""

    @classmethod
    def setUpClass(cls):
        cls.tokens = identifiers()
        cls.violations = scan(PROJECT_ROOT, cls.tokens)

    # -- the rig ----------------------------------------------------------
    def test_every_identifier_kind_is_built_and_is_not_empty(self):
        """A kind that harvested nothing would make this module vacuous.

        Each of the four kinds is a different way for a case to be named, and
        each is built from the registry and the sets' own files. If a harvest
        stopped working -- a path moved, a key changed shape -- the kind would
        come back empty and the scan would pass by finding nothing to look for.
        """
        for kind in PATTERNS:
            with self.subTest(kind=kind):
                self.assertTrue(
                    self.tokens[kind],
                    "the {0} harvest is empty, so nothing is being looked for".format(kind),
                )

    def test_the_identifier_set_covers_every_registered_set(self):
        """Every set in the registry contributes, sealed sets included."""
        for name, development_set in development_sets.BY_NAME.items():
            with self.subTest(set=name):
                self.assertTrue(development_set.cases)
                for case_no in development_set.cases:
                    self.assertIn(
                        "case-{0:05d}".format(case_no), self.tokens["case file stem"]
                    )

    # -- the check --------------------------------------------------------
    def test_no_identifier_appears_under_the_prompts_or_the_policy(self):
        """The property, over everything but the one pinned finding."""
        extra = sorted(set(self.violations) - set(KNOWN_VIOLATIONS))
        self.assertEqual(
            [],
            report(extra),
            "an identifier of a case reached the prompts or the policy",
        )

    def test_the_one_known_violation_is_still_there(self):
        """The pin cannot rot into a permanent excuse for nothing.

        If the advocate template's example is ever rewritten to an invented id,
        this fails and says so, which is the signal to delete the pin rather
        than to leave it covering whatever comes next.
        """
        missing = sorted(set(KNOWN_VIOLATIONS) - set(self.violations))
        self.assertEqual(
            [],
            report(missing),
            "a pinned violation is gone; remove it from KNOWN_VIOLATIONS",
        )

    # -- the message ------------------------------------------------------
    def test_the_report_names_the_file_and_the_kind_and_never_the_text(self):
        """What a failure prints, pinned, because it is what gets committed."""
        example = [Violation("prompts/v1/advocate.system.md", "trip id", "TRP-00501")]
        self.assertEqual(["prompts/v1/advocate.system.md: trip id"], report(example))
        self.assertNotIn("TRP-00501", "\n".join(report(example)))

    # -- falsifiability ---------------------------------------------------
    def test_the_scan_is_red_on_a_dirty_fixture(self):
        """The check is shown to fire, on a fixture, on a copy of the real tree.

        The clean copy reports exactly the one pinned finding; one real
        identifier spliced into one file is then reported with that file and
        that kind. A guard nobody has seen fail is not evidence of anything.
        """
        with tempfile.TemporaryDirectory(prefix="tribunal-no-leakage-") as temporary:
            fixture = Path(temporary)
            for directory in SCANNED_DIRECTORIES:
                shutil.copytree(PROJECT_ROOT / directory, fixture / directory)

            clean = scan(fixture, self.tokens)
            self.assertEqual(report(KNOWN_VIOLATIONS), report(clean))

            target = fixture / "prompts" / "v1" / "advocate.system.md"
            target.write_text(
                target.read_text(encoding="utf-8") + "\n<!-- TRP-00501 -->\n",
                encoding="utf-8",
            )

            dirty = scan(fixture, self.tokens)
            spliced = Violation("prompts/v1/advocate.system.md", "trip id", "TRP-00501")
            # Compared through ``report`` and never as ``Violation`` tuples: a
            # failed comparison prints its arguments, and a tuple carries the
            # token. The first assertion is what says the splice was found; the
            # second is what says nothing else moved.
            self.assertEqual(
                ["prompts/v1/advocate.system.md: trip id"],
                report([item for item in dirty if item == spliced]),
            )
            self.assertEqual(
                report(sorted(KNOWN_VIOLATIONS) + [spliced]),
                report(dirty),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
