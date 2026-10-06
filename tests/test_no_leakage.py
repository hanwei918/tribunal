"""No case identifier reaches the prompts or the policy.

The judge can be shown three trees: the prompt templates in ``prompts/``, the
policy in ``policy/``, and the closures selected out of ``precedents/``. The
first two are shared by every case and are the two this module scans: anything
in either that names one particular case is a leak of that case's identity into
every call the system ever makes -- and the leak is permanent, because a prompt
or a policy file is not rebuilt per case.

``precedents/`` is the third tree and is deliberately **not** scanned, because
nothing it can hand the judge carries a case identifier. The block is built by
:func:`tribunal.precedents.block`, which receives no case id at all: it is
handed the entries already chosen for this case and writes each one's id, its
category, its clause ids and its ruling. The choosing happens one level up, in
:func:`tribunal.precedents.matches`, and it is a function of the category, the
clause ids a kept claim cites and the contested amount -- never of the case
number, and it **excludes** the case being judged rather than naming it.

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
