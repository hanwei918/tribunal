"""Tests for policy versions.

A policy version is an integer. Version 1 is the three files in ``policy/``
exactly as committed, and it is what every run before this switch used, so
**version 1 is byte-identical** and the first thing this file proves is that:
version 1 rebuilds every one of the 44 recorded ``brief_sha256`` values exactly.

The rest is about the two things an amendment may not do, and both are enforced
rather than asked for. The top-level key set is exact, so an ``edits`` or a
``removes`` key has nowhere to go; and the clause's id must be the next free
number for its prefix, so an id already in use cannot be re-declared. That
matters because ``brief.py`` parses the prose of several existing clauses: an
amendment that rewrote one would change what a brief means while leaving every
id where it was.

Nothing here reaches a real model.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import re
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Mapping
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, run_benchmark as runner  # noqa: E402
from tests import portability  # noqa: E402
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import (  # noqa: E402
    brief,
    events,
    loader,
    money,
    policy_versions,
    precedents,
    referee,
)
from tribunal.model import resolve_model  # noqa: E402

# The id the rig runs its scripted transports under. It is deliberately not the
# headline model, so it must not be used to name a recorded run directory.
MODEL = rig.MODEL
PROMPTS_DIR = rig.PROMPTS_DIR
POLICY_DIR = PROJECT_ROOT / "policy"

# The model the headline runs were made under, read from the one place that
# declares it rather than repeated here.
HEADLINE_MODEL = resolve_model(None)

# The two recorded sets, whose briefs version 1 has to rebuild exactly. The
# corpus is run unlabelled into ``runs/<model>/`` and the second development set
# into ``runs/codex/<model>/``.
CORPUS_RUN_DIR = PROJECT_ROOT / "runs" / runner.model_slug(HEADLINE_MODEL)
CODEX_RUN_DIR = PROJECT_ROOT / "runs" / "codex" / runner.model_slug(HEADLINE_MODEL)
CASE_FILE_RE = re.compile(r"^case-\d{5}\.json$")

CORPUS_CASES = 29
CODEX_CASES = 15

# The next free clause number per prefix, as the three files stand. The numbers
# are pinned here rather than derived, so an amendment added to the repository
# moves this test rather than silently changing what "next free" means.
NEXT_FREE = {"GEN": 4, "NS": 10, "RD": 13}

CATEGORY = "ROUTE_DEVIATION"
PREFIX = "RD"


def amendment_document(clause_id, category="ROUTE_DEVIATION", **overrides):
    """One amendment, valid unless a test makes it otherwise."""
    document = {
        "base_version": 1,
        "proposal_file": "policy/proposals/0001-example.json",
        "proposal_sha256": "a" * 64,
        "report_file": "runs/policy-gaps/report.json",
        "report_sha256": "b" * 64,
        "cluster_id": "C1",
        "cases": [101],
        "approved_by": "Zhou Hanwei",
        "approved_at": "2026-09-29T00:00:00+00:00",
        "clause": {
            "id": clause_id,
            "title": "An added clause",
            "category": category,
            "rule": "A rule that says something.",
            "requires": [],
            "licenses": [],
            "favours": "RIDER",
            "notes": "Added by an amendment.",
        },
    }
    document.update(overrides)
    return document


def write_amendment(root, name, document, base_version=policy_versions.BASE_VERSION):
    directory = policy_versions.amendments_dir_for(base_version, root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def policies_for(category=CATEGORY):
    return loader.load_policies(category, policy_versions.BASE_VERSION)


def files_for(category=CATEGORY):
    return {
        "general": "general.json",
        "category": loader.CATEGORY_POLICY_FILES[category],
    }


def recorded_digests(run_dir, case_loader=None):
    """``{case_no: brief_sha256}`` as a recorded run directory holds it."""
    found = {}
    for path in sorted(Path(run_dir).iterdir()):
        if not CASE_FILE_RE.match(path.name):
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        found[document["case_no"]] = document.get("brief_sha256")
    return found


# --------------------------------------------------------------------------
# The vocabulary
# --------------------------------------------------------------------------
class PolicyVocabularyTests(unittest.TestCase):
    def test_the_repository_is_at_version_2_with_one_amendment(self):
        """The repository shipped at version 1 until 2026-10-01.

        The policy-gap loop's first full pass drafted POL-RD-13 for cluster C4
        and the owner approved it as amendment 0001, so the repository is at
        version 2 and ``amendment_files`` names that one file. Version 1 is
        still the three policy files exactly as committed, which is what
        ``BASE_VERSION`` says.
        """
        self.assertEqual(1, policy_versions.BASE_VERSION)
        self.assertEqual(2, policy_versions.current_version())
        self.assertEqual(
            ["0001-pol-rd-13.json"],
            [path.name for path in policy_versions.amendment_files()],
        )

    def test_the_prefix_maps_agree_with_each_other_and_with_the_id_pattern(self):
        self.assertEqual(
            set(policy_versions.PREFIX_FILES), set(policy_versions.PREFIX_CATEGORY)
        )
        for prefix in policy_versions.PREFIX_FILES:
            with self.subTest(prefix=prefix):
                self.assertIsNotNone(
                    policy_versions.CLAUSE_ID_RE.match("POL-{0}-01".format(prefix))
                )
        for prefix in ("XX", "GENX", "gen", "", "NS-"):
            with self.subTest(prefix=prefix):
                self.assertIsNone(
                    policy_versions.CLAUSE_ID_RE.match("POL-{0}-01".format(prefix))
                )

    def test_each_prefix_names_a_real_file_whose_category_it_declares(self):
        for prefix, filename in policy_versions.PREFIX_FILES.items():
            with self.subTest(prefix=prefix):
                document = json.loads(
                    (POLICY_DIR / filename).read_text(encoding="utf-8")
                )
                self.assertEqual(
                    policy_versions.PREFIX_CATEGORY[prefix], document["category"]
                )

    def test_the_next_free_number_for_each_prefix_is_where_the_files_stop(self):
        for prefix, expected in NEXT_FREE.items():
            with self.subTest(prefix=prefix):
                document = json.loads(
                    (
                        POLICY_DIR / policy_versions.PREFIX_FILES[prefix]
                    ).read_text(encoding="utf-8")
                )
                numbers = sorted(
                    int(clause["id"].rsplit("-", 1)[1]) for clause in document["clauses"]
                )
                self.assertEqual(expected, numbers[-1] + 1)

    def test_each_shipped_store_is_the_store_it_claims_to_be(self):
        # Rule 7 asks for **one** test over the three stores the repository
        # ships, so it is made here rather than split by whichever task added
        # which directory. Until 2026-10-01 all three shipped empty and this
        # asserted that. The policy-gap loop's first full pass then closed two
        # cases and approved one amendment, so each store now ships the thing
        # it is a store of, and the assertions are about that instead:
        #
        # * ``precedents/`` holds a hash-chained store, and the chain verifies
        #   -- an edited or reordered line is reported at that line;
        # * ``policy/amendments/`` holds the approved amendment, and its
        #   recorded ``proposal_sha256`` is the digest of the proposal file it
        #   names, so the amendment traces to the draft a person read;
        # * ``policy/proposals/`` holds that draft and its transcript.
        #
        # A store that shipped a *different* file, or an amendment whose
        # proposal had moved since approval, would pass the old emptiness check
        # for the wrong reason or not at all; neither passes these.
        precedents_dir = PROJECT_ROOT / "precedents"
        amendments_dir = POLICY_DIR / policy_versions.AMENDMENTS_DIRNAME
        proposals_dir = POLICY_DIR / "proposals"

        for directory in (precedents_dir, amendments_dir, proposals_dir):
            with self.subTest(directory=str(directory.relative_to(PROJECT_ROOT))):
                self.assertTrue(directory.is_dir())
                self.assertTrue((directory / policy_versions.README_FILE).is_file())

        # The precedent store is a chain, and the chain verifies.
        store = precedents.store_path(precedents_dir)
        self.assertTrue(store.is_file(), "the shipped precedent store is missing")
        self.assertIsNone(
            events.verify_chain(store),
            "the shipped precedent store's chain does not verify",
        )

        # Every amendment's recorded proposal digest matches its proposal file.
        amendments = policy_versions.amendment_files(POLICY_DIR)
        self.assertTrue(amendments, "the shipped amendment store is empty")
        for path in amendments:
            with self.subTest(amendment=path.name):
                amendment = policy_versions.load_amendment(path)
                proposal_file = PROJECT_ROOT / amendment["proposal_file"]
                self.assertTrue(
                    proposal_file.is_file(), "no proposal at {0}".format(proposal_file)
                )
                self.assertEqual(
                    hashlib.sha256(proposal_file.read_bytes()).hexdigest(),
                    amendment["proposal_sha256"],
                    "{0} records a digest its proposal no longer has".format(path.name),
                )


# --------------------------------------------------------------------------
# Version 1 is byte-identical
# --------------------------------------------------------------------------
class VersionOneIsUnchangedTests(unittest.TestCase):
    def test_version_1_returns_the_files_as_read(self):
        for category in sorted(loader.CATEGORY_POLICY_FILES):
            with self.subTest(category=category):
                self.assertEqual(
                    loader.load_policies(category),
                    loader.load_policies(category, policy_versions.BASE_VERSION),
                )

    def test_version_1_does_not_read_the_amendments_directory(self):
        # A broken amendment must not be able to stop the version-1 measurement,
        # so version 1 returns before the directory is looked at. The fixture is
        # a directory that cannot be listed, and version 1 still builds.
        with mock.patch.object(
            policy_versions,
            "amendment_files",
            side_effect=AssertionError("the amendments directory was read"),
        ):
            policies = loader.load_policies(CATEGORY, policy_versions.BASE_VERSION)
        self.assertIn("clauses", policies["category"])

    def test_version_1_rebuilds_every_recorded_brief_digest_exactly(self):
        portability.require_the_same_libm()
        corpus = recorded_digests(CORPUS_RUN_DIR)
        self.assertEqual(CORPUS_CASES, len(corpus))

        second_set = development_sets.named("codex")
        codex = recorded_digests(CODEX_RUN_DIR)
        self.assertEqual(CODEX_CASES, len(codex))

        for case_no, recorded in sorted(corpus.items()):
            with self.subTest(set_name="corpus", case_no=case_no):
                self.assertEqual(
                    recorded, runner.current_brief_sha256(case_no)
                )
        for case_no, recorded in sorted(codex.items()):
            with self.subTest(set_name="codex", case_no=case_no):
                self.assertEqual(
                    recorded,
                    runner.current_brief_sha256(
                        case_no, case_loader=second_set.load_case
                    ),
                )

    def test_the_whole_point_is_that_all_forty_four_agree(self):
        """The forty-four is a count of the repository's cases.

        The test this replaces asserted ``CORPUS_CASES + CODEX_CASES == 44``,
        which is a claim about arithmetic: 29 and 15 are written four lines
        above it and nothing in it reads the repository. Here the counts come
        off the two run directories, so a case that leaves either one moves the
        number; the two sets are asserted to name different cases, so the 44 is
        not 29 counted twice; and every one of them is asserted to have a
        digest for the test above to have compared.
        """
        corpus = recorded_digests(CORPUS_RUN_DIR)
        codex = recorded_digests(CODEX_RUN_DIR)
        self.assertEqual(CORPUS_CASES, len(corpus))
        self.assertEqual(CODEX_CASES, len(codex))
        self.assertEqual(44, len(corpus) + len(codex))
        self.assertEqual(set(), set(corpus) & set(codex))
        for set_name, digests in (("corpus", corpus), ("codex", codex)):
            for case_no, digest in sorted(digests.items()):
                with self.subTest(set_name=set_name, case_no=case_no):
                    self.assertIsInstance(digest, str)
                    self.assertEqual(64, len(digest))


# --------------------------------------------------------------------------
# Version 3, the separate base
# --------------------------------------------------------------------------
V3_DIR = POLICY_DIR / "v3"

# The version-1 bytes and amendment 0001, by digest, as they stand. Version 3 is
# added *beside* them and must not touch them: an edited version-1 file would
# move every recorded ``brief_sha256``, so the digests are pinned rather than
# assumed.
V1_FILE_DIGESTS = {
    "general.json": "12d64aa3de9878e3a99e5d9e39e4bdf251d4a82cd8f577993812278a57ea14bf",
    "no_show.json": "7e80df8f3084eb1ae8c4b8b3724096e36bb3491bb5ab154af5d626ff009daadf",
    "route_deviation.json": "628b503c0da63937f95a7e18e51bf1579972cdf590122d34150f4953d6e32b9d",
}
AMENDMENT_0001_DIGEST = "72ceb95957e72c4c10960ffd79ddf6a9c13ed1d97059b1bfb21f47fa4f3ae855"

# The three version-3 files, by digest. The bytes are the archive's with **one
# edit**: the top-level ``version`` string, ``2.0.0`` to ``3.0.0``.
V3_FILE_DIGESTS = {
    "general.json": "52248998cce5133abf8aa22428cf4eab089ad9cccbfa3c1cc9da76e670be9d2a",
    "no_show.json": "bef9c2bb217ea1f78266d600291a2b7b21e54825bfbbe67142f8d4054bc668bb",
    "route_deviation.json": "e49e72ce68cadb7af32ea20426d2693eb7e846767e82694bc2074f688fb5f7f8",
}

# The canonical digest of the loaded policy pair at each version, per category.
# Pinned so that "versions 1 and 2 build exactly what they built today" is a
# check over the *loaded documents* and not only over the files on disk.
#
# Version 4 is base 3 with the first amendment on that base, ``POL-NS-11``, which
# joins ``no_show.json`` -- so the no-show digest moves and the route-deviation
# one does not, because an amendment to a file a brief does not carry is skipped.
# Version 5 adds the second amendment, ``POL-RD-14``, which joins
# ``route_deviation.json`` -- so the route-deviation digest moves and the no-show
# one does not, and version 4's own pair is unchanged by it.
#
# Version 6 adds the third amendment, ``POL-NS-12``, which joins
# ``no_show.json`` -- so the no-show digest moves and the route-deviation one does
# not, and version 5's own pair is unchanged by it.
LOADED_POLICY_DIGESTS = {
    (1, "NO_SHOW_CHARGE"): "7b22d2d551be510a9fb7a95e817bfdc5c35913c85223c77a79582722573d151a",
    (1, "ROUTE_DEVIATION"): "c6e942b36b2de34c255fcc9259fa88f6b789d1e8267acb47882c75ca690fd82b",
    (2, "NO_SHOW_CHARGE"): "7b22d2d551be510a9fb7a95e817bfdc5c35913c85223c77a79582722573d151a",
    (2, "ROUTE_DEVIATION"): "07bfc0f1971febbf45741df6a5dfbfbba310183b76892bb7f44a27cf30df3535",
    (3, "NO_SHOW_CHARGE"): "d6d068a6a2cb781399bcb9f63dcb5e1ca12c52c1cd28483ecc45db1ec1cd8207",
    (3, "ROUTE_DEVIATION"): "fd6031f3382d126aee2e66353e9b8040f116acc296a08381742ceb67f4dc8eff",
    (4, "NO_SHOW_CHARGE"): "7ed85af25bfae34c03b46099989bcac197c1bebd8e02c7a8dc07ce0e8571c20e",
    (4, "ROUTE_DEVIATION"): "fd6031f3382d126aee2e66353e9b8040f116acc296a08381742ceb67f4dc8eff",
    (5, "NO_SHOW_CHARGE"): "7ed85af25bfae34c03b46099989bcac197c1bebd8e02c7a8dc07ce0e8571c20e",
    (5, "ROUTE_DEVIATION"): "377742d8ef9c0d0fc53da47ce687c8460dc4756f2c8282160265ee34fe6dec1c",
    (6, "NO_SHOW_CHARGE"): "1b5c4780690404e114b615a7a2d5d3a496b3ea5013e41f2fc976be3cbd1412b2",
    (6, "ROUTE_DEVIATION"): "377742d8ef9c0d0fc53da47ce687c8460dc4756f2c8282160265ee34fe6dec1c",
}

# The first amendment **on base 3**, by digest, and the proposal it was approved
# from. The proposal's digest is the one the amendment records, so the two pin
# each other: an edited proposal would leave the amendment naming a digest its
# proposal no longer has. The second amendment, ``POL-RD-14``, is pinned the same
# way and makes **version 5**; the third, ``POL-NS-12``, makes **version 6**.
V3_AMENDMENT_0001 = POLICY_DIR / "v3" / "amendments" / "0001-pol-ns-11.json"
V3_AMENDMENT_0001_DIGEST = (
    "0d24461e9a0fe3cc27a16dc78ffb7daa9cc36c05f8e233c0e272e2a168e8f6de"
)
V3_AMENDMENT_0001_PROPOSAL = POLICY_DIR / "v3" / "proposals" / "0001-pol-ns-11.json"
V3_AMENDMENT_0002 = POLICY_DIR / "v3" / "amendments" / "0002-pol-rd-14.json"
V3_AMENDMENT_0002_DIGEST = (
    "e254b5f837423e0ee7ee6beec7bb2661fc98e0442c694dc8cc9b4f81c9121703"
)
V3_AMENDMENT_0002_PROPOSAL = POLICY_DIR / "v3" / "proposals" / "0002-pol-rd-14.json"
V3_AMENDMENT_0003 = POLICY_DIR / "v3" / "amendments" / "0003-pol-ns-12.json"
V3_AMENDMENT_0003_DIGEST = (
    "9fa988960d049a67e9bdbdbbaa822cb246bb2bc0e806e1b865f730e25852d582"
)
V3_AMENDMENT_0003_PROPOSAL = POLICY_DIR / "v3" / "proposals" / "0003-pol-ns-12.json"
# The digest the amendment records, and the digest the file has.
V3_AMENDMENT_0003_PROPOSAL_DIGEST = (
    "79e597c05b69e6f213bed011df740b3819e4706899feacb76ac995cbcf61d97f"
)

# A version-4 route-deviation brief for a corpus case, pinned **from before**
# amendment 0002 existed. Version 4 is base 3 with 0001 only, and 0001 is a
# no-show clause, so this digest must not move when 0002 lands.
VERSION_FOUR_BRIEF_101 = (
    "1faec3653b2f07d0051a33f5be1e80d683144de59aafbcc93e867cd5961c6beb"
)

# The same brief at **version 5**, pinned from before amendment 0003 existed.
# Version 5 is base 3 with 0001 and 0002, and 0003 is a no-show clause, so this
# digest must not move when 0003 lands -- and the version-6 brief must differ
# from it, because 0003 adds a clause to the no-show policy the case is not in.
VERSION_FIVE_BRIEF_101 = (
    "81a63ee33f97a351cdcaa4eac863a1694b81ffca866e0c7d31711834272605ee"
)


def sources_keys(node: Any, path: str = "") -> List[str]:
    """Every **key** named ``sources`` in a parsed document, by path.

    A structural check, not a substring search: a clause's prose may contain the
    word "sources" -- one route-deviation clause's notes do -- and a search for
    the string would report a provenance key where there is only a sentence.
    """
    found: List[str] = []
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key == "sources":
                found.append("{0}/sources".format(path))
            found.extend(sources_keys(value, "{0}/{1}".format(path, key)))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            found.extend(sources_keys(value, "{0}[{1}]".format(path, index)))
    return found

# The draft's own clause counts, which the three version-3 files carry.
V3_CLAUSE_COUNTS = {"general.json": 8, "no_show.json": 10, "route_deviation.json": 13}


class VersionThreeTests(unittest.TestCase):
    """Version 3 is a separate base: its own directory, and no amendment."""

    def test_the_version_three_files_carry_version_three(self):
        for name, expected in sorted(V3_FILE_DIGESTS.items()):
            with self.subTest(file=name):
                path = V3_DIR / name
                self.assertTrue(path.is_file(), "policy/v3/{0} is missing".format(name))
                self.assertEqual(expected, hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(
                    "3.0.0", json.loads(path.read_text(encoding="utf-8"))["version"]
                )

    def test_the_version_one_bytes_and_amendment_are_untouched(self):
        for name, expected in sorted(V1_FILE_DIGESTS.items()):
            with self.subTest(file=name):
                self.assertEqual(
                    expected,
                    hashlib.sha256((POLICY_DIR / name).read_bytes()).hexdigest(),
                )
        amendment = (
            POLICY_DIR / policy_versions.AMENDMENTS_DIRNAME / "0001-pol-rd-13.json"
        )
        self.assertEqual(
            AMENDMENT_0001_DIGEST, hashlib.sha256(amendment.read_bytes()).hexdigest()
        )

    def test_version_three_loads_its_own_files(self):
        for category in sorted(loader.CATEGORY_POLICY_FILES):
            with self.subTest(category=category):
                loaded = loader.load_policies(category, 3)
                self.assertEqual("3.0.0", loaded["general"]["version"])
                self.assertEqual("3.0.0", loaded["category"]["version"])

    def test_version_three_does_not_read_the_amendments_directory(self):
        # A separate base has no amendment sequence, so a broken amendment must
        # not be able to stop a version-3 brief either.
        with mock.patch.object(
            policy_versions,
            "amendment_files",
            side_effect=AssertionError("the amendments directory was read"),
        ):
            policies = loader.load_policies(CATEGORY, 3)
        self.assertIn("clauses", policies["category"])

    def test_version_three_carries_the_drafts_clause_counts(self):
        for name, expected in sorted(V3_CLAUSE_COUNTS.items()):
            with self.subTest(file=name):
                document = json.loads((V3_DIR / name).read_text(encoding="utf-8"))
                self.assertEqual(expected, len(document["clauses"]))

    def test_the_loaded_documents_at_each_version_are_the_ones_pinned(self):
        """Versions 1 and 2 build exactly what they built; version 3 is new."""
        for (version, category), expected in sorted(LOADED_POLICY_DIGESTS.items()):
            with self.subTest(version=version, category=category):
                self.assertEqual(
                    expected,
                    money.canonical_sha256(loader.load_policies(category, version)),
                )

    def test_version_three_is_a_separate_base(self):
        self.assertTrue(policy_versions.is_a_separate_base(3))
        for version in (1, 2, 4):
            with self.subTest(version=version):
                self.assertFalse(policy_versions.is_a_separate_base(version))
        self.assertEqual(V3_DIR, policy_versions.base_directory(3))
        self.assertEqual(POLICY_DIR, policy_versions.base_directory(1))
        self.assertEqual(POLICY_DIR, policy_versions.base_directory(2))
        # Version 4 is base 3 with its own amendment applied, so it reads the
        # base's files: a version built *from* a base is not a base itself, and
        # ``separate_base_of`` is what says which base it belongs to.
        self.assertEqual(V3_DIR, policy_versions.base_directory(4))
        self.assertEqual(3, policy_versions.separate_base_of(4))
        self.assertIsNone(policy_versions.separate_base_of(2))

    def test_amendments_are_never_applied_to_version_three(self):
        with self.assertRaises(policy_versions.AmendmentError) as caught:
            policy_versions.apply_amendments(
                policies_for(), 3, files=files_for(), root=tempfile.mkdtemp()
            )
        self.assertIn("separate policy base", str(caught.exception))

    def test_the_highest_available_version_names_both_sequences(self):
        self.assertEqual(2, policy_versions.current_version())
        # Base 1's own sequence is still at 2 -- one amendment -- and base 3's is
        # at 6, because ``POL-NS-11``, ``POL-RD-14`` and ``POL-NS-12`` are its
        # three amendments. Base 7 is a separate base of its own with no
        # amendment yet, so it is at 7. The sequences are independent, so the
        # highest is 7 and ``current_version`` does not move.
        self.assertEqual(7, policy_versions.highest_available_version())
        self.assertEqual(6, policy_versions.version_on_base(3))
        self.assertEqual(2, policy_versions.version_on_base(1))
        # A scratch root with no amendments is at version 1, and each separate
        # base there is the base alone, so the highest there is 7 -- base 7's own
        # number: the sequences are independent, and none reads another's
        # directory.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(1, policy_versions.current_version(tmp))
            self.assertEqual(7, policy_versions.highest_available_version(tmp))
            self.assertEqual(3, policy_versions.version_on_base(3, tmp))

    def test_an_amendment_that_would_compute_a_separate_base_is_refused(self):
        for version in sorted(policy_versions.SEPARATE_BASE_VERSIONS):
            with self.subTest(version=version):
                with self.assertRaises(policy_versions.AmendmentError) as caught:
                    policy_versions.refuse_a_taken_version(version)
                # Each base is named by its own directory: version 3 is kept at
                # ``policy/v3/`` and version 7 at ``policy/v7/``.
                self.assertIn(
                    "policy/{0}/".format(
                        policy_versions.SEPARATE_BASE_VERSIONS[version]
                    ),
                    str(caught.exception),
                )
        # Every version base 3 owns is refused on base 1, not only the base
        # itself: amendment 0002 on base 1 would compute 3 and amendment 0003
        # would compute 4, and 4 and 5 are base 3's own amendment versions.
        for version in (3, 4, 5):
            with self.subTest(version=version, base=1):
                with self.assertRaises(policy_versions.AmendmentError) as caught:
                    policy_versions.refuse_a_taken_version(version)
                self.assertIn("policy/v3/", str(caught.exception))
        # A version that belongs to no separate base is not refused.
        policy_versions.refuse_a_taken_version(2)
        # And base 3's own versions are its own: the same call is allowed when the
        # amendment sits on base 3, which is what lets its 0001 compute 4 and its
        # 0002 compute 5.
        policy_versions.refuse_a_taken_version(4, 3)
        policy_versions.refuse_a_taken_version(5, 3)
        policy_versions.refuse_a_taken_version(3, 3)
        # A base may not compute another base's versions either.
        with self.assertRaises(policy_versions.AmendmentError):
            policy_versions.refuse_a_taken_version(2, 3)


# --------------------------------------------------------------------------
# Amendments on base 3, and version 4
# --------------------------------------------------------------------------
class BaseThreeAmendmentTests(unittest.TestCase):
    """A separate base carries its own amendment sequence, under the same rules.

    Version 3 is base 3 alone; version 3 + k applies the amendments under
    ``policy/v3/amendments/``. ``POL-NS-11`` is the first of them, so it makes
    **version 4** -- and base 1 is untouched, because an amendment on one base is
    never applied to another.
    """

    def test_the_three_amendments_on_base_three_are_installed(self):
        files = policy_versions.amendment_files(POLICY_DIR, base_version=3)
        self.assertEqual(
            [
                "0001-pol-ns-11.json",
                "0002-pol-rd-14.json",
                "0003-pol-ns-12.json",
            ],
            [path.name for path in files],
        )
        self.assertEqual(
            V3_AMENDMENT_0001_DIGEST,
            hashlib.sha256(V3_AMENDMENT_0001.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            V3_AMENDMENT_0002_DIGEST,
            hashlib.sha256(V3_AMENDMENT_0002.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            V3_AMENDMENT_0003_DIGEST,
            hashlib.sha256(V3_AMENDMENT_0003.read_bytes()).hexdigest(),
        )

    def test_the_amendment_records_the_digest_of_the_proposal_it_names(self):
        """The two pin each other: an edited proposal would break the record."""
        amendment = policy_versions.load_amendment(V3_AMENDMENT_0001, base_version=3)
        self.assertEqual(3, amendment["base_version"])
        self.assertEqual("POL-NS-11", amendment["clause"]["id"])
        self.assertEqual("NO_SHOW_CHARGE", amendment["clause"]["category"])
        self.assertEqual(
            "policy/v3/proposals/0001-pol-ns-11.json", amendment["proposal_file"]
        )
        self.assertEqual(
            hashlib.sha256(V3_AMENDMENT_0001_PROPOSAL.read_bytes()).hexdigest(),
            amendment["proposal_sha256"],
        )

    def test_the_note_is_allowed_on_base_three_and_refused_on_base_one(self):
        """The schema is widened for the base that needs it, and only there.

        ``POL-NS-11`` was approved by hand after the 2026-10-08 development run,
        so it carries a ``note`` and null report fields. Base 1's amendments may
        not carry one: there the exact key set is what leaves nowhere to write an
        edit.
        """
        amendment = policy_versions.load_amendment(V3_AMENDMENT_0001, base_version=3)
        self.assertIn(policy_versions.AMENDMENT_NOTE_FIELD, amendment)
        self.assertIsNone(amendment["report_file"])
        self.assertIsNone(amendment["report_sha256"])
        self.assertIsInstance(amendment["note"], str)
        self.assertIn("1734", amendment["note"])

        with self.assertRaises(policy_versions.AmendmentError) as caught:
            policy_versions.load_amendment(V3_AMENDMENT_0001)
        self.assertIn("unexpected", str(caught.exception))
        self.assertIn(policy_versions.AMENDMENT_NOTE_FIELD, str(caught.exception))

    def test_a_base_one_amendment_without_a_note_is_still_accepted_on_base_three(self):
        """A note is allowed, never required."""
        amendment = policy_versions.load_amendment(
            POLICY_DIR / "amendments" / "0001-pol-rd-13.json", base_version=3
        )
        self.assertEqual("POL-RD-13", amendment["clause"]["id"])

    def test_version_four_loads_with_eleven_no_show_clauses(self):
        loaded = loader.load_policies("NO_SHOW_CHARGE", 4)
        ids = [clause["id"] for clause in loaded["category"]["clauses"]]
        self.assertEqual(11, len(ids))
        self.assertIn("POL-NS-11", ids)
        self.assertEqual("3.0.0{0}0001".format(policy_versions.AMENDMENT_MARKER), loaded["category"]["version"])
        # Version 3 is the base alone and does not carry the amendment's clause.
        self.assertEqual(
            10, len(loader.load_policies("NO_SHOW_CHARGE", 3)["category"]["clauses"])
        )

    def test_the_amendment_moves_only_the_file_its_clause_joins(self):
        """A no-show clause leaves the route-deviation document exactly as it was."""
        self.assertEqual(
            6,
            policy_versions.version_on_base(3),
        )
        self.assertEqual(
            money.canonical_sha256(loader.load_policies("ROUTE_DEVIATION", 3)),
            money.canonical_sha256(loader.load_policies("ROUTE_DEVIATION", 4)),
        )
        self.assertNotEqual(
            money.canonical_sha256(loader.load_policies("NO_SHOW_CHARGE", 3)),
            money.canonical_sha256(loader.load_policies("NO_SHOW_CHARGE", 4)),
        )

    def test_version_five_loads_with_fourteen_route_deviation_clauses(self):
        """``POL-RD-14`` is the second amendment on base 3, so it makes version 5."""
        loaded = loader.load_policies("ROUTE_DEVIATION", 5)
        ids = [clause["id"] for clause in loaded["category"]["clauses"]]
        self.assertEqual(14, len(ids))
        self.assertIn("POL-RD-14", ids)
        self.assertEqual(
            "3.0.0{0}0002".format(policy_versions.AMENDMENT_MARKER),
            loaded["category"]["version"],
        )
        # The no-show file is untouched by a route-deviation clause, so its
        # version-5 digest equals version 4's and its suffix still names 0001.
        no_show = loader.load_policies("NO_SHOW_CHARGE", 5)
        self.assertEqual(
            11, len(no_show["category"]["clauses"])
        )
        self.assertEqual(
            "3.0.0{0}0001".format(policy_versions.AMENDMENT_MARKER),
            no_show["category"]["version"],
        )
        # Version 3 and 4 do not carry it: it is added at 5 and nowhere below.
        for version in (3, 4):
            with self.subTest(version=version):
                self.assertNotIn(
                    "POL-RD-14",
                    [
                        clause["id"]
                        for clause in loader.load_policies(
                            "ROUTE_DEVIATION", version
                        )["category"]["clauses"]
                    ],
                )

    def test_a_version_five_route_deviation_brief_carries_pol_rd_14_and_no_sources(self):
        case = loader.load_case(101)
        briefed = brief.build_brief_for_case(case, policy_version=5)
        ids = [clause["id"] for clause in briefed["policies"]["category"]["clauses"]]
        self.assertIn("POL-RD-14", ids)
        self.assertEqual([], sources_keys(briefed["policies"]))

    def test_the_version_four_brief_is_unchanged_by_the_second_amendment(self):
        """Version 4 is base 3 with 0001 only, and its brief digest is pinned."""
        case = loader.load_case(101)
        _canonical, digest = brief.brief_digest(
            brief.build_brief_for_case(case, policy_version=4)
        )
        self.assertEqual(VERSION_FOUR_BRIEF_101, digest)
        self.assertNotEqual(
            digest,
            brief.brief_digest(
                brief.build_brief_for_case(case, policy_version=5)
            )[1],
        )

    def test_a_version_four_brief_carries_pol_ns_11_and_no_sources(self):
        case = loader.load_external_set_case(loader.EXTERNAL_DIR / "dev-v2", 1734)
        briefed = brief.build_brief_for_case(case, policy_version=4)
        ids = [clause["id"] for clause in briefed["policies"]["category"]["clauses"]]
        self.assertIn("POL-NS-11", ids)
        self.assertEqual([], sources_keys(briefed["policies"]))

    def test_the_third_amendment_records_the_digest_of_the_proposal_it_names(self):
        """``POL-NS-12``, the third amendment on base 3, which makes version 6."""
        amendment = policy_versions.load_amendment(V3_AMENDMENT_0003, base_version=3)
        self.assertEqual(3, amendment["base_version"])
        self.assertEqual("POL-NS-12", amendment["clause"]["id"])
        self.assertEqual("NO_SHOW_CHARGE", amendment["clause"]["category"])
        self.assertEqual([901], amendment["cases"])
        self.assertIsNone(amendment["cluster_id"])
        self.assertIsNone(amendment["report_file"])
        self.assertIsNone(amendment["report_sha256"])
        self.assertEqual("Zhou Hanwei", amendment["approved_by"])
        self.assertEqual(
            "policy/v3/proposals/0003-pol-ns-12.json", amendment["proposal_file"]
        )
        self.assertEqual(
            V3_AMENDMENT_0003_PROPOSAL_DIGEST,
            hashlib.sha256(V3_AMENDMENT_0003_PROPOSAL.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            V3_AMENDMENT_0003_PROPOSAL_DIGEST, amendment["proposal_sha256"]
        )

    def test_version_six_loads_with_twelve_no_show_clauses(self):
        loaded = loader.load_policies("NO_SHOW_CHARGE", 6)
        ids = [clause["id"] for clause in loaded["category"]["clauses"]]
        self.assertEqual(12, len(ids))
        self.assertIn("POL-NS-12", ids)
        self.assertEqual(
            "3.0.0{0}0003".format(policy_versions.AMENDMENT_MARKER),
            loaded["category"]["version"],
        )
        # The route-deviation file is untouched by a no-show clause, so its
        # version-6 digest equals version 5's and its suffix still names 0002.
        route = loader.load_policies("ROUTE_DEVIATION", 6)
        self.assertEqual(
            14, len(route["category"]["clauses"])
        )
        self.assertEqual(
            "3.0.0{0}0002".format(policy_versions.AMENDMENT_MARKER),
            route["category"]["version"],
        )
        # Version 5 does not carry it: it is added at 6 and nowhere below.
        for version in (3, 4, 5):
            with self.subTest(version=version):
                self.assertNotIn(
                    "POL-NS-12",
                    [
                        clause["id"]
                        for clause in loader.load_policies(
                            "NO_SHOW_CHARGE", version
                        )["category"]["clauses"]
                    ],
                )

    def test_the_version_five_brief_is_unchanged_by_the_third_amendment(self):
        """Version 5 is base 3 with 0001 and 0002, and its brief digest is pinned."""
        case = loader.load_case(101)
        _canonical, digest = brief.brief_digest(
            brief.build_brief_for_case(case, policy_version=5)
        )
        self.assertEqual(VERSION_FIVE_BRIEF_101, digest)
        # 0003 is a no-show clause, so a route-deviation brief does not carry it
        # at any version: 101's version-6 brief is byte-identical to its
        # version-5 one, because the clause is skipped for the file it does not
        # join and 101 carries no registration mark for POL-GEN-08(4) to mask.
        self.assertEqual(
            digest,
            brief.brief_digest(
                brief.build_brief_for_case(case, policy_version=6)
            )[1],
        )
        # A no-show brief does carry it, so the two differ there.
        no_show = loader.load_case(201)
        self.assertNotEqual(
            brief.brief_digest(
                brief.build_brief_for_case(no_show, policy_version=5)
            )[1],
            brief.brief_digest(
                brief.build_brief_for_case(no_show, policy_version=6)
            )[1],
        )

    def test_a_third_amendment_that_rewrites_an_existing_clause_is_refused(self):
        """With two amendments already present, 0003 may still not edit a clause.

        The positive half of the refusal: the id must be the next free number, so
        a third amendment that re-declares an existing no-show clause is refused
        even though its number is the right one.
        """
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(
                tmp,
                "0001-first.json",
                amendment_document(
                    "POL-NS-11", category="NO_SHOW_CHARGE", base_version=3
                ),
                base_version=3,
            )
            write_amendment(
                tmp,
                "0002-second.json",
                amendment_document(
                    "POL-NS-12", category="NO_SHOW_CHARGE", base_version=3
                ),
                base_version=3,
            )
            write_amendment(
                tmp,
                "0003-rewrite.json",
                amendment_document(
                    "POL-NS-04", category="NO_SHOW_CHARGE", base_version=3
                ),
                base_version=3,
            )
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.apply_amendments(
                    loader.load_policies("NO_SHOW_CHARGE", 3),
                    6,
                    files={"general": "general.json", "category": "no_show.json"},
                    root=tmp,
                )
        self.assertIn("never edits or replaces", str(caught.exception))

    def test_a_second_amendment_numbered_0001_on_base_three_is_refused(self):
        """Two files numbered 0001 are the duplicate the numbering forbids."""
        with tempfile.TemporaryDirectory() as tmp:
            for name, clause_id in (
                ("0001-example.json", "POL-NS-11"),
                ("0001-second.json", "POL-NS-12"),
            ):
                write_amendment(
                    tmp,
                    name,
                    amendment_document(
                        clause_id, category="NO_SHOW_CHARGE", base_version=3
                    ),
                    base_version=3,
                )
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.amendment_files(tmp, base_version=3)
        self.assertIn("more than once", str(caught.exception))

    def test_an_amendment_that_rewrites_an_existing_clause_is_refused(self):
        """The id must be the next free number, so POL-NS-04 cannot be re-declared."""
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(
                tmp,
                "0001-rewrite.json",
                amendment_document(
                    "POL-NS-04", category="NO_SHOW_CHARGE", base_version=3
                ),
                base_version=3,
            )
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.apply_amendments(
                    loader.load_policies("NO_SHOW_CHARGE", 3),
                    4,
                    files={"general": "general.json", "category": "no_show.json"},
                    root=tmp,
                )
        self.assertIn("never edits or replaces", str(caught.exception))

    def test_a_next_free_clause_on_base_three_is_applied(self):
        """The positive half: the same fixture with the next free id is added."""
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(
                tmp,
                "0001-new.json",
                amendment_document(
                    "POL-NS-11", category="NO_SHOW_CHARGE", base_version=3
                ),
                base_version=3,
            )
            applied = policy_versions.apply_amendments(
                loader.load_policies("NO_SHOW_CHARGE", 3),
                4,
                files={"general": "general.json", "category": "no_show.json"},
                root=tmp,
            )
        ids = [clause["id"] for clause in applied["category"]["clauses"]]
        self.assertEqual(11, len(ids))
        self.assertIn("POL-NS-11", ids)

    def test_a_version_above_base_three_is_refused_with_base_three_in_the_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.apply_amendments(
                    loader.load_policies("NO_SHOW_CHARGE", 3),
                    6,
                    files={"general": "general.json", "category": "no_show.json"},
                    root=tmp,
                )
        self.assertIn("there is no policy version 6", str(caught.exception))
        self.assertIn("version 3", str(caught.exception))


# --------------------------------------------------------------------------
# What an amendment may not be
# --------------------------------------------------------------------------
class AmendmentRefusalTests(unittest.TestCase):
    def refusal(self, document, name="0001-example.json", root=None):
        with tempfile.TemporaryDirectory() as tmp:
            where = tmp if root is None else root
            path = write_amendment(where, name, document)
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.load_amendment(path)
        return str(caught.exception)

    def test_an_amendment_that_could_express_an_edit_is_refused(self):
        # There is no key an edit could be written in, which is the mechanism by
        # which "adds one clause" is true rather than intended.
        for extra in ({"edits": [{"id": "POL-RD-01"}]}, {"removes": ["POL-RD-02"]}):
            with self.subTest(extra=sorted(extra)):
                message = self.refusal(
                    amendment_document("POL-RD-13", **extra)
                )
                self.assertIn("unexpected", message)
                self.assertIn(sorted(extra)[0], message)

    def test_an_amendment_that_drops_a_provenance_field_is_refused(self):
        document = amendment_document("POL-RD-13")
        document.pop("approved_by")
        message = self.refusal(document)
        self.assertIn("missing", message)
        self.assertIn("approved_by", message)

    def test_a_clause_that_drops_one_of_its_eight_fields_is_refused(self):
        document = amendment_document("POL-RD-13")
        document["clause"].pop("notes")
        message = self.refusal(document)
        self.assertIn("missing", message)
        self.assertIn("notes", message)

    def test_a_clause_with_a_ninth_field_is_refused(self):
        document = amendment_document("POL-RD-13")
        document["clause"]["replaces"] = "POL-RD-01"
        message = self.refusal(document)
        self.assertIn("unexpected", message)
        self.assertIn("replaces", message)

    def test_an_unknown_prefix_is_refused(self):
        message = self.refusal(amendment_document("POL-XX-01"))
        self.assertIn("POL-XX-01", message)
        self.assertIn("prefix", message)

    def test_an_id_that_is_not_the_right_shape_is_refused(self):
        for clause_id in ("RD-13", "POL-RD-1", "POL-RD-131", "POL-RD-AA", ""):
            with self.subTest(clause_id=clause_id):
                message = self.refusal(amendment_document(clause_id))
                self.assertIn("prefix", message)

    def test_a_category_that_disagrees_with_the_prefix_is_refused(self):
        message = self.refusal(
            amendment_document("POL-RD-13", category="NO_SHOW_CHARGE")
        )
        self.assertIn("NO_SHOW_CHARGE", message)
        self.assertIn("ROUTE_DEVIATION", message)

    def test_an_amendment_that_is_not_an_object_is_refused(self):
        message = self.refusal(["POL-RD-13"])
        self.assertIn("one amendment object", message)

    def test_a_file_that_is_not_named_for_its_number_is_refused(self):
        for name in ("1-example.json", "0001_example.json", "0001-Example.json", "example.json"):
            with self.subTest(name=name):
                document = amendment_document("POL-RD-13")
                with tempfile.TemporaryDirectory() as tmp:
                    write_amendment(tmp, name, document)
                    with self.assertRaises(policy_versions.AmendmentError) as caught:
                        policy_versions.amendment_files(tmp)
                self.assertIn("NNNN-<slug>.json", str(caught.exception))

    def test_a_hole_in_the_sequence_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-one.json", amendment_document("POL-RD-13"))
            write_amendment(tmp, "0003-three.json", amendment_document("POL-RD-14"))
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.amendment_files(tmp)
        self.assertIn("no holes", str(caught.exception))

    def test_a_number_used_twice_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-one.json", amendment_document("POL-RD-13"))
            write_amendment(tmp, "0001-two.json", amendment_document("POL-RD-14"))
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.amendment_files(tmp)
        self.assertIn("more than once", str(caught.exception))

    def test_a_directory_under_the_amendments_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / policy_versions.AMENDMENTS_DIRNAME / "0001-dir").mkdir(
                parents=True
            )
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.amendment_files(tmp)
        self.assertIn("must be an amendment", str(caught.exception))

    def test_the_readme_is_not_an_amendment_and_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, policy_versions.README_FILE, {"anything": True})
            self.assertEqual([], policy_versions.amendment_files(tmp))


# --------------------------------------------------------------------------
# Applying them
# --------------------------------------------------------------------------
class ApplyingAmendmentsTests(unittest.TestCase):
    def test_an_amendment_is_appended_and_its_file_gains_the_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-example.json", amendment_document("POL-RD-13"))
            applied = policy_versions.apply_amendments(
                policies_for(), 2, files=files_for(), root=tmp
            )
        ids = [clause["id"] for clause in applied["category"]["clauses"]]
        self.assertIn("POL-RD-13", ids)
        self.assertEqual(
            "1.1.0{0}0001".format(policy_versions.AMENDMENT_MARKER),
            applied["category"]["version"],
        )
        # The general policy received nothing, so its version is untouched.
        self.assertEqual("1.0.1", applied["general"]["version"])

    def test_the_input_is_not_modified(self):
        before = policies_for()
        version_before = before["category"]["version"]
        count_before = len(before["category"]["clauses"])
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-example.json", amendment_document("POL-RD-13"))
            policy_versions.apply_amendments(before, 2, files=files_for(), root=tmp)
        self.assertEqual(version_before, before["category"]["version"])
        self.assertEqual(count_before, len(before["category"]["clauses"]))

    def test_a_colliding_id_is_refused(self):
        # POL-RD-01 is already there, so an amendment that declares it would be
        # rewriting an existing clause rather than adding one.
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-example.json", amendment_document("POL-RD-01"))
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.apply_amendments(
                    policies_for(), 2, files=files_for(), root=tmp
                )
        self.assertIn("next free", str(caught.exception))
        self.assertIn("never edits or replaces", str(caught.exception))

    def test_an_id_past_the_next_free_number_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-example.json", amendment_document("POL-RD-15"))
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.apply_amendments(
                    policies_for(), 2, files=files_for(), root=tmp
                )
        self.assertIn("next free", str(caught.exception))

    def test_two_amendments_must_be_ordered(self):
        # 0001 takes RD-13, so 0002 must take RD-14 and not RD-15.
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-one.json", amendment_document("POL-RD-13"))
            write_amendment(tmp, "0002-two.json", amendment_document("POL-RD-15"))
            with self.assertRaises(policy_versions.AmendmentError):
                policy_versions.apply_amendments(
                    policies_for(), 3, files=files_for(), root=tmp
                )

    def test_a_second_amendment_would_compute_a_separate_base_and_is_refused(self):
        """Two amendments on base 1 compute version 3, which a base already holds.

        Until 2026-10-08 this test applied two amendments in order and checked
        that the higher one was named. Version 3 is now a separate policy base of
        its own, so a second amendment would compute the same number as that
        base: the amendment sequence can hold at most one amendment, and the
        function that applies amendments refuses the second rather than
        producing a policy the loader would never read. The first amendment
        still applies, and still names ``0001``.
        """
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-one.json", amendment_document("POL-RD-13"))
            applied = policy_versions.apply_amendments(
                policies_for(), 2, files=files_for(), root=tmp
            )
            self.assertEqual("POL-RD-13", applied["category"]["clauses"][-1]["id"])
            self.assertTrue(applied["category"]["version"].endswith("0001"))

            write_amendment(tmp, "0002-two.json", amendment_document("POL-RD-14"))
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.apply_amendments(
                    policies_for(), 3, files=files_for(), root=tmp
                )
            self.assertIn("separate policy base", str(caught.exception))

    def test_an_amendment_to_a_policy_the_brief_does_not_carry_is_skipped(self):
        # A no-show clause has no business in a route-deviation brief, and one
        # run briefs cases of both categories.
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(
                tmp,
                "0001-example.json",
                amendment_document("POL-NS-10", category="NO_SHOW_CHARGE"),
            )
            applied = policy_versions.apply_amendments(
                policies_for(CATEGORY), 2, files=files_for(CATEGORY), root=tmp
            )
        self.assertEqual("1.1.0", applied["category"]["version"])

    def test_a_version_above_the_repository_is_refused(self):
        with self.assertRaises(policy_versions.AmendmentError) as caught:
            policy_versions.apply_amendments(
                policies_for(), 2, files=files_for(), root=tempfile.mkdtemp()
            )
        self.assertIn("there is no policy version 2", str(caught.exception))

    def test_a_version_below_one_is_refused(self):
        for version in (0, -1):
            with self.subTest(version=version):
                with self.assertRaises(policy_versions.AmendmentError) as caught:
                    policy_versions.apply_amendments(
                        policies_for(), version, files=files_for()
                    )
                self.assertIn("lowest policy version", str(caught.exception))

    def test_a_version_that_is_not_an_integer_is_refused(self):
        for version in ("2", 2.0, True, None):
            with self.subTest(version=version):
                with self.assertRaises(policy_versions.AmendmentError) as caught:
                    policy_versions.apply_amendments(
                        policies_for(), version, files=files_for()
                    )
                self.assertIn("is an integer", str(caught.exception))

    def test_applying_twice_does_not_stack_the_suffix(self):
        once = policy_versions._version_with_suffix("1.1.0", 1)
        self.assertEqual(
            "1.1.0{0}0001".format(policy_versions.AMENDMENT_MARKER), once
        )
        self.assertEqual(
            "1.1.0{0}0002".format(policy_versions.AMENDMENT_MARKER),
            policy_versions._version_with_suffix(once, 2),
        )

    def test_the_amendments_directory_may_be_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([], policy_versions.amendment_files(tmp))
            self.assertEqual(1, policy_versions.current_version(tmp))


# --------------------------------------------------------------------------
# Where a later version writes
# --------------------------------------------------------------------------
class PolicyVersionDestinationTests(unittest.TestCase):
    def test_a_later_version_has_a_directory_of_its_own(self):
        runs = Path("/tmp/runs")
        self.assertEqual(
            runs / "policy-v2" / runner.model_slug(MODEL),
            runner.policy_v_run_directory(runs, 2, MODEL),
        )
        self.assertEqual("policy-v3", runner.policy_v_directory_name(3))

    def test_a_later_version_cannot_land_in_the_headline_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            headline = runs / runner.model_slug(MODEL)
            with self.assertRaises(runner.BenchmarkError) as caught:
                runner.assert_policy_v_destination(headline, runs, 2, MODEL)
            self.assertIn("is the headline run directory", str(caught.exception))
            # The held-out set's run directory is a headline one too, so a
            # version-2 run must not be able to land there either.
            sealed = runs / runner.SEALED_SET_RUNS_SUBDIR / runner.model_slug(MODEL)
            with self.assertRaises(runner.BenchmarkError):
                runner.assert_policy_v_destination(sealed, runs, 2, MODEL)
            # A destination outside this version's root that is not a headline
            # directory is refused by the root check rather than by the
            # headline one.
            elsewhere = runs / "policy-v2" / ".." / ".." / "elsewhere"
            with self.assertRaises(runner.BenchmarkError) as root_caught:
                runner.assert_policy_v_destination(elsewhere, runs, 2, MODEL)
            self.assertIn("may only be written under", str(root_caught.exception))

    def test_one_version_cannot_land_in_another_versions_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            version2 = runner.policy_v_run_directory(runs, 2, MODEL)
            self.assertEqual(
                version2, runner.assert_policy_v_destination(version2, runs, 2, MODEL)
            )
            with self.assertRaises(runner.BenchmarkError):
                runner.assert_policy_v_destination(version2, runs, 3, MODEL)

    def test_a_dot_dot_name_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            escaped = runs / "policy-v2" / ".." / runner.model_slug(MODEL)
            with self.assertRaises(runner.BenchmarkError):
                runner.assert_policy_v_destination(escaped, runs, 2, MODEL)


# --------------------------------------------------------------------------
# Staleness at a version
# --------------------------------------------------------------------------
class StalenessAtAVersionTests(unittest.TestCase):
    def test_the_checker_asks_for_the_version_it_was_given(self):
        seen = []

        def fake(case_no, case_loader=None, ablate=None, policy_version=1):
            seen.append(policy_version)
            return "e" * 64

        with mock.patch.object(runner, "current_brief_sha256", side_effect=fake):
            checker = runner.BriefStaleness(policy_version=3)
            self.assertEqual("e" * 64, checker.current_digest(101))
        self.assertEqual([3], seen)

    def test_the_memo_is_keyed_by_case_and_version_together(self):
        calls = []

        def digest(case_no):
            calls.append(case_no)
            return "f" * 64

        checker = runner.BriefStaleness(digest=digest, policy_version=2)
        self.assertEqual("f" * 64, checker.current_digest(101))
        self.assertEqual("f" * 64, checker.current_digest(101))
        self.assertEqual([101], calls)
        self.assertEqual([(101, 2)], list(checker._current))

    def test_an_injected_digest_is_used_as_it_stands(self):
        # ``brief_digest_for`` closes the version over the callable it returns,
        # so a checker built with one must not re-bind a version on top of it.
        checker = runner.BriefStaleness(
            digest=lambda case_no: "g" * 64, policy_version=2
        )
        self.assertEqual("g" * 64, checker.current_digest(101))

    def test_brief_digest_for_still_returns_none_for_the_all_defaults_case(self):
        self.assertIsNone(runner.brief_digest_for())
        self.assertIsNotNone(runner.brief_digest_for(policy_version=2))


# --------------------------------------------------------------------------
# The command lines
# --------------------------------------------------------------------------
class RunBenchmarkCommandLineTests(unittest.TestCase):
    def refuse(self, arguments):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit):
                    runner.main(arguments)
        return errors.getvalue()

    def test_a_later_version_is_refused_with_every_replay_flag(self):
        for arguments in (
            ["--policy-version", "2", "--compare"],
            ["--policy-version", "2", "--replay-advocates", "runs/x"],
            ["--policy-version", "2", "--replay-check", "runs/x"],
            ["--policy-version", "2", "--verify-recorded-drafts", "runs/x"],
            ["--policy-version", "2", "--external", "data/external/ryde/case-901.json"],
        ):
            with self.subTest(arguments=arguments):
                message = self.refuse(arguments)
                self.assertIn("policy-version", message)
                self.assertIn(arguments[-2], message)

    def test_a_later_version_is_refused_beside_the_other_switches(self):
        # ``--precedents`` is no longer in this list: the precedents block is the
        # same whatever the policy version, so the two may be given together and
        # the run goes to ``runs/precedents/policy-vN/<model>/``.
        for arguments in (
            ["--policy-version", "2", "--ablate", "clause-notes"],
            ["--policy-version", "2", "--amount-rule", "signed"],
        ):
            with self.subTest(arguments=arguments):
                message = self.refuse(arguments)
                self.assertIn("at most one of", message)

    def test_version_1_is_not_a_switch_and_is_not_refused_with_them(self):
        # Version 1 is the default, so naming it changes nothing and must not
        # count as one of the switches that change what an agent is given. With
        # it named, ``--ablate`` and ``--compare`` are still refused for their
        # own reason and not for the mutual exclusion.
        message = self.refuse(
            ["--policy-version", "1", "--ablate", "clause-notes", "--compare"]
        )
        self.assertNotIn("at most one of", message)
        self.assertIn("--ablate", message)
        self.assertIn("--compare", message)

    def test_a_version_the_repository_does_not_have_is_refused_before_a_client(self):
        # The same shape as the development-set test below: the runs root is a
        # scratch one, so nothing here resolves a destination under the
        # repository's own runs/. The amendment sequence is at version 2 since
        # 2026-10-01, version 3 is a separate base since 2026-10-08, versions 4,
        # 5 and 6 are that base with its three amendments, and version 7 is a
        # second separate base since 2026-10-13, so the version the repository
        # does not have is 8.
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                runner,
                "_default_client_factory",
                side_effect=AssertionError("a client was built"),
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    with contextlib.redirect_stderr(io.StringIO()) as errors:
                        code = runner.main(
                            [
                                "--model", MODEL,
                                "--cases", "101",
                                "--policy-version", "8",
                                "--runs-dir", str(Path(tmp) / "runs"),
                            ]
                        )
        self.assertEqual(1, code)
        self.assertIn("there is no policy version 8", errors.getvalue())

    def test_version_1_is_accepted_and_writes_to_the_ordinary_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = rig.ScriptedTransport(
                rig.produced_from_key(rig.answer_key())
            )
            with mock.patch.object(
                runner,
                "_default_client_factory",
                return_value=rig.client_factory(MODEL, transport),
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = runner.main(
                        [
                            "--model", MODEL,
                            "--cases", "101",
                            "--policy-version", "1",
                            "--runs-dir", str(Path(tmp) / "runs"),
                        ]
                    )
            self.assertEqual(0, code)
            self.assertTrue(transport.calls() > 0)
            runs = Path(tmp) / "runs"
            self.assertTrue(
                (runs / runner.model_slug(MODEL) / "case-00101.json").is_file()
            )
            self.assertFalse((runs / "policy-v1").exists())


class DevelopmentSetsCommandLineTests(unittest.TestCase):
    def refuse(self, arguments):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()) as errors:
                    code = development_sets.main(arguments)
        return code, errors.getvalue()

    def test_a_later_version_is_refused_with_every_mode_that_reads_a_run(self):
        for arguments in (
            ["--policy-version", "2", "--report"],
            ["--policy-version", "2", "--replay-advocates", "runs/x"],
            ["--policy-version", "2", "--replay-check", "runs/x"],
            ["--policy-version", "2", "--verify-recorded-drafts", "runs/x"],
        ):
            with self.subTest(arguments=arguments):
                code, message = self.refuse(arguments)
                self.assertEqual(1, code)
                self.assertIn("--policy-version", message)
                self.assertIn(arguments[-2], message)

    def test_a_later_version_is_refused_beside_the_other_switches(self):
        # ``--precedents`` is no longer in this list, for the same reason it left
        # the runner's: the two may be given together.
        for arguments in (
            ["--policy-version", "2", "--ablate", "clause-notes"],
            ["--policy-version", "2", "--amount-rule", "signed"],
        ):
            with self.subTest(arguments=arguments):
                code, message = self.refuse(arguments)
                self.assertEqual(1, code)
                self.assertIn("at most one of", message)

    def test_an_unknown_version_is_reachable_and_says_so(self):
        # The flag is a plain integer, so a version that does not exist is not a
        # parser error: it is refused by the runner with a message naming the
        # version the repository is actually at. The amendment sequence is at
        # version 2 since 2026-10-01, version 3 is a separate base since
        # 2026-10-08, versions 4, 5 and 6 are that base with its three
        # amendments, and version 7 is a second separate base since 2026-10-13,
        # so the version that names nothing is 8. The runs root is a
        # scratch one, so the refusal is about the version and this test never
        # resolves a destination under the repository's own runs/.
        with tempfile.TemporaryDirectory() as tmp:
            code, message = self.refuse(
                [
                    "--set",
                    "codex",
                    "--policy-version",
                    "8",
                    "--cases",
                    "9101",
                    "--runs-dir",
                    str(Path(tmp) / "runs"),
                ]
            )
        self.assertEqual(1, code)
        self.assertIn("there is no policy version 8", message)


# --------------------------------------------------------------------------
# Nothing may glob the policy directory
# --------------------------------------------------------------------------
class NothingGlobsThePolicyDirectoryTests(unittest.TestCase):
    """``policy/`` gained two subdirectories, and a glob would now find them.

    ``policy/amendments/README.md`` and ``policy/proposals/README.md`` are not
    policy files. A module that listed ``policy/`` to find the three files would
    start reading them, so every read has to name its file.
    """

    GLOB_CALLS = re.compile(r"\.(glob|rglob|iterdir|listdir)\(")

    def source_files(self):
        for directory in ("tribunal", "eval", "ui", "tests"):
            for path in sorted((PROJECT_ROOT / directory).glob("*.py")):
                yield path

    def test_no_module_lists_the_policy_directory(self):
        offenders = []
        for path in self.source_files():
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if not self.GLOB_CALLS.search(line):
                    continue
                # ``POLICY_DIR / <subdirectory>`` is a listing of one of the two
                # subdirectories, which is what this file's own README check
                # does. The hazard is a listing of ``policy/`` itself, so that is
                # what is looked for.
                if "policy" in line.lower() and "POLICY_DIR / " not in line:
                    offenders.append(
                        "{0}:{1}: {2}".format(
                            path.relative_to(PROJECT_ROOT), number, line.strip()
                        )
                    )
        self.assertEqual([], offenders)

    def test_the_three_policy_files_are_read_by_name(self):
        # The positive half: the loader names all three, so there is nothing for
        # a listing to find.
        source = (PROJECT_ROOT / "tribunal" / "loader.py").read_text(encoding="utf-8")
        self.assertIn("GENERAL_POLICY_FILE", source)
        self.assertIn("CATEGORY_POLICY_FILES", source)
        for filename in policy_versions.PREFIX_FILES.values():
            with self.subTest(filename=filename):
                self.assertIn(filename, source)


# --------------------------------------------------------------------------
# A replay may not mix two policy versions
# --------------------------------------------------------------------------
CLAUSE_NOTES = "clause-notes"


def version_two_amendments(tmp):
    """One real amendment under ``<tmp>/amendments``, and the patch that finds it.

    ``loader.load_policies`` calls ``apply_amendments`` with no root, so the
    amendments directory is resolved from the repository -- which since
    2026-10-01 is at version 2 and holds amendment ``0001``. This points that
    one lookup at a temporary directory holding one valid amendment, which is
    what makes a *genuine* version-2 run possible against a fixture of this
    file's own rather than the repository's approved clause.
    """
    write_amendment(tmp, "0001-example.json", amendment_document("POL-RD-13"))
    directory = Path(tmp) / policy_versions.AMENDMENTS_DIRNAME
    return mock.patch.object(
        policy_versions, "amendments_dir", lambda root=None: directory
    )


def version_two_run(tmp, cases=(101,)):
    """A genuine version-2 run of ``cases`` under ``<tmp>/runs``.

    Returns ``(run directory, summary)``. Every case's brief is built from
    policy version 2, so the run's own artifacts record version 2 and its
    destination is ``runs/policy-v2/<model>/``.
    """
    transport = rig.ScriptedTransport(rig.produced_from_key(rig.answer_key()))
    with version_two_amendments(tmp):
        summary = runner.run_benchmark(
            MODEL,
            list(cases),
            runs_dir=Path(tmp) / "runs",
            prompts_dir=PROMPTS_DIR,
            client_factory=rig.client_factory(MODEL, transport),
            key=rig.answer_key(),
            git_runner=rig.git_runner(),
            progress=lambda text: None,
            judge_votes=1,
            policy_version=2,
        )
    landed = (
        Path(tmp)
        / "runs"
        / runner.policy_v_directory_name(2)
        / runner.model_slug(MODEL)
    )
    return landed, summary


class ReplayAcrossVersionsTests(unittest.TestCase):
    """A replay may not hand the judge one version's brief and record another.

    ``replay_verdict`` rebuilds each case's brief at the version the **source**
    run recorded and hands the judge that brief. The only refusal was about the
    version this run was *given*, so a plain run pointed at a version-2 source
    handed the judge a version-2 brief, wrote ``policy_version: 1`` into every
    artifact, and -- because a plain run's destination is ``runs/<model>/`` --
    put the result in the headline directory. The two halves of every case would
    then have been produced under different policy while the run said they had
    not.
    """

    def test_a_version_2_source_replayed_into_a_plain_run_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, summary = version_two_run(tmp)
            self.assertEqual([101], summary.completed_cases)
            self.assertTrue((source / "case-00101.json").is_file())
            self.assertEqual(
                2,
                runner.configuration_of(
                    runner.read_json(runner.case_cache_path(source, 101))
                )["policy_version"],
            )

            # ``LLMClient`` patched to raise, not the factory: the factory only
            # closes over the model, and what must not happen is a *client*.
            with mock.patch.object(
                runner.llm,
                "LLMClient",
                side_effect=AssertionError("a model was called"),
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    with contextlib.redirect_stderr(io.StringIO()) as errors:
                        code = runner.main(
                            [
                                "--model", MODEL,
                                "--cases", "101",
                                "--runs-dir", str(Path(tmp) / "runs"),
                                "--replay-advocates", str(source),
                            ]
                        )
            self.assertEqual(1, code)
            message = errors.getvalue()
            self.assertIn("policy version 2", message)
            self.assertIn("version 1", message)
            # Refused before anything was written: no headline directory, and no
            # model called -- the patch above would have raised.
            self.assertFalse((Path(tmp) / "runs" / runner.model_slug(MODEL)).exists())

    def test_the_check_refuses_it_without_a_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _summary = version_two_run(tmp)
            with self.assertRaises(runner.BenchmarkError) as caught:
                runner.check_replay(
                    source,
                    (101,),
                    model=MODEL,
                    prompts_dir=PROMPTS_DIR,
                    policy_version=policy_versions.BASE_VERSION,
                )
        self.assertIn("policy version 2", str(caught.exception))

    def test_a_check_with_no_version_of_its_own_is_left_alone(self):
        """The two read-only analyses pass no version, and must keep working.

        ``eval.baselines`` and ``eval.verify_drafts`` read a recorded run rather
        than producing one, so they have no version of their own to compare the
        source against -- and a version-2 source has to stay analysable by them.
        """
        with tempfile.TemporaryDirectory() as tmp:
            source, _summary = version_two_run(tmp)
            with version_two_amendments(tmp):
                check = runner.check_replay(
                    source, (101,), model=MODEL, prompts_dir=PROMPTS_DIR
                )
        self.assertEqual([101], check.accepted_cases)


# --------------------------------------------------------------------------
# The switches the command line accepts are the switches it honours
# --------------------------------------------------------------------------
class SwitchForwardingTests(unittest.TestCase):
    """Every switch the command line accepts has to reach the runner.

    ``--ablate`` and ``--precedents`` were parsed, refused in combination with
    the modes they cannot be combined with, and then never passed to
    :func:`run_benchmark` at all. ``--ablate clause-notes`` therefore ran an
    *unablated* set and wrote it into ``runs/<model>/`` -- the opposite of what
    the flag's own help text and ``runs/README.md`` say. The forwarding was
    fixed and nothing held it, so removing one keyword would put the defect back
    with the suite still green. The first test below is what holds it, at the
    boundary where the keyword would be lost; the second makes the same claim
    from the outside, in where the files land.
    """

    SWITCHES = (
        (["--ablate", CLAUSE_NOTES], "ablation", CLAUSE_NOTES),
        (["--precedents"], "precedents", runner.PRECEDENTS_STORE),
        (["--policy-version", "2"], "policy_version", 2),
    )

    def test_each_switch_reaches_the_runner(self):
        for switch, keyword, value in self.SWITCHES:
            with self.subTest(switch=switch):
                seen = {}

                def stub(model, cases, **kwargs):
                    seen.update(kwargs)
                    return mock.Mock(ok=True)

                with mock.patch.object(runner, "run_benchmark", side_effect=stub):
                    with mock.patch.object(runner, "print_summary"):
                        with contextlib.redirect_stdout(io.StringIO()):
                            runner.main(
                                ["--model", MODEL, "--cases", "101"] + switch
                            )
                self.assertIn(keyword, seen)
                self.assertEqual(value, seen[keyword])

    def test_each_switch_writes_under_the_directory_its_help_text_names(self):
        for switch, expected in (
            (["--ablate", CLAUSE_NOTES], ("ablation", CLAUSE_NOTES)),
            (["--precedents"], ("precedents",)),
            (["--policy-version", "2"], ("policy-v2",)),
        ):
            with self.subTest(switch=switch):
                with tempfile.TemporaryDirectory() as tmp:
                    runs = Path(tmp) / "runs"
                    transport = rig.ScriptedTransport(
                        rig.produced_from_key(rig.answer_key())
                    )
                    with version_two_amendments(tmp):
                        with mock.patch.object(
                            runner,
                            "_default_client_factory",
                            return_value=rig.client_factory(MODEL, transport),
                        ):
                            with contextlib.redirect_stdout(io.StringIO()):
                                code = runner.main(
                                    [
                                        "--model", MODEL,
                                        "--cases", "101",
                                        "--judge-votes", "1",
                                        "--runs-dir", str(runs),
                                    ] + switch
                                )
                    self.assertEqual(0, code)
                    landed = runs.joinpath(*expected, runner.model_slug(MODEL))
                    self.assertTrue((landed / "case-00101.json").is_file())
                    self.assertTrue((landed / runner.METADATA_FILE).is_file())
                    # And nothing at all in the headline directory.
                    self.assertFalse((runs / runner.model_slug(MODEL)).exists())


# --------------------------------------------------------------------------
# A closure of a case from a later-version run
# --------------------------------------------------------------------------
class ClosingAtARecordedVersionTests(unittest.TestCase):
    """``precedents close`` rebuilds the brief at the version the case records.

    ``close`` checks the rebuilt brief's digest against the one the case file
    records, and it rebuilt at version 1 unconditionally. A case from a run
    briefed at version 2 therefore rebuilt to a different digest and was
    refused -- so no case of a later-version run could be closed at all, which
    is the one thing the library exists to collect.
    """

    def test_a_case_of_a_version_two_run_can_be_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, summary = version_two_run(tmp, cases=(101,))
            self.assertEqual([101], summary.completed_cases)
            store = Path(tmp) / precedents.PRECEDENTS_DIRNAME
            # The patch is held open across the closure: ``close`` rebuilds the
            # brief, so it resolves the amendments directory the way the run
            # that wrote the case file did.
            with version_two_amendments(tmp):
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    code = precedents.main(
                        [
                            "--store", str(store),
                            "close",
                            "--run-dir", str(run_dir),
                            "--case", "101",
                            "--ruling", "PARTIAL_REFUND",
                            "--clause", "POL-RD-02",
                            "--reason",
                            "EV-TRIP-00101 supports the refund under POL-RD-02.",
                            "--closed-by", "A Reviewer",
                            "--summary", "A reviewer closed this case.",
                        ]
                    )
            self.assertEqual(0, code)
            self.assertIn("P-0001", out.getvalue())
            entries = precedents.read_entries(precedents.store_path(store))
            self.assertEqual(1, len(entries))
            self.assertEqual(2, entries[0]["policy_version"])


# --------------------------------------------------------------------------
# A policy version below the lowest one
# --------------------------------------------------------------------------
class PolicyVersionArgumentTests(unittest.TestCase):
    """A version below 1 is refused while the command line is read.

    The refusal used to come from the runner, after the value had been parsed
    and carried on the namespace: 0 or -1 was a namespace field like any other
    until something asked the policy for it. It is refused at parse time now, in
    both runners, so no client is built and no destination is named for a
    version that names nothing.
    """

    def test_the_validator_accepts_the_versions_the_repository_has(self):
        self.assertEqual(1, runner.policy_version_argument("1"))
        self.assertEqual(2, runner.policy_version_argument("2"))

    def test_the_validator_refuses_a_version_below_one(self):
        for text in ("0", "-1", "-99"):
            with self.subTest(text=text):
                with self.assertRaises(argparse.ArgumentTypeError) as caught:
                    runner.policy_version_argument(text)
                self.assertIn("lowest policy version is 1", str(caught.exception))

    def test_the_validator_refuses_something_that_is_not_an_integer(self):
        with self.assertRaises(argparse.ArgumentTypeError) as caught:
            runner.policy_version_argument("banana")
        self.assertIn("is an integer", str(caught.exception))

    def test_the_run_benchmark_command_line_refuses_it_before_a_client(self):
        # The runs root is a scratch directory rather than the repository's own.
        # The refusal happens while the line is read, so nothing is written
        # either way -- but a guard that is removed again must not leave residue
        # in ``runs/``, and the sabotage that proved this one left exactly that:
        # ``runs/policy-v0/hy4-preview/events.jsonl``, written before the mocked
        # client raised.
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                runner.llm,
                "LLMClient",
                side_effect=AssertionError("a model was called"),
            ):
                with contextlib.redirect_stderr(io.StringIO()) as errors:
                    with self.assertRaises(SystemExit) as caught:
                        runner.main(
                            [
                                "--model",
                                MODEL,
                                "--cases",
                                "101",
                                "--runs-dir",
                                tmp,
                                "--policy-version",
                                "0",
                            ]
                        )
        self.assertEqual(2, caught.exception.code)
        self.assertIn("lowest policy version is 1", errors.getvalue())

    def test_the_development_sets_command_line_refuses_it_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                runner.llm,
                "LLMClient",
                side_effect=AssertionError("a model was called"),
            ):
                with contextlib.redirect_stderr(io.StringIO()) as errors:
                    with self.assertRaises(SystemExit) as caught:
                        development_sets.main(
                            [
                                "--set",
                                "corpus",
                                "--cases",
                                "101",
                                "--runs-dir",
                                tmp,
                                "--policy-version",
                                "0",
                            ]
                        )
        self.assertEqual(2, caught.exception.code)
        self.assertIn("lowest policy version is 1", errors.getvalue())


# --------------------------------------------------------------------------
# A number in an amendment file
# --------------------------------------------------------------------------
class AmendmentNumberTests(unittest.TestCase):
    """A number in an amendment file arrives as a ``Decimal``.

    The amendment's clause is copied straight into the brief the agents are
    handed, so a float here would be the one place a policy number reached the
    brief as a binary float. Every field a clause carries is a string or a list
    of strings today, so there is no amount for the schema to hold; the read is
    pinned on a number inside ``requires``, which is the list a structured
    requirement would go in.
    """

    def test_a_number_in_an_amendment_is_read_as_a_decimal(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = amendment_document("POL-RD-13")
            document["clause"]["requires"] = [
                {"clause": "POL-RD-02", "threshold": 250.0}
            ]
            path = write_amendment(tmp, "0001-example.json", document)
            # The file itself carries a float: the point is how it is read.
            self.assertIn("250.0", path.read_text(encoding="utf-8"))
            loaded = policy_versions.load_amendment(path)
        value = loaded["clause"]["requires"][0]["threshold"]
        self.assertIsInstance(value, Decimal)
        self.assertNotIsInstance(value, float)
        self.assertEqual(Decimal("250.0"), value)


# --------------------------------------------------------------------------
# The switch off, and a version-2 run end to end
# --------------------------------------------------------------------------
class SwitchOffByteIdentityTests(unittest.TestCase):
    """With the version switch off, the brief is the brief it always was.

    ``policy_version`` defaults to 1 and every run before the switch used
    version 1, so a brief built without the argument and one built with it named
    have to be the same bytes -- and the same bytes the recorded runs digested.
    Compared as canonical JSON, because that is what ``brief_sha256`` is a
    digest of, over cases from both development sets.
    """

    def test_the_default_and_version_one_build_the_recorded_bytes(self):
        second_set = development_sets.named("codex")
        for set_name, run_dir, cases, load in (
            ("corpus", CORPUS_RUN_DIR, (101, 201, 214), loader.load_case),
            ("codex", CODEX_RUN_DIR, (9101, 9111), second_set.load_case),
        ):
            recorded = recorded_digests(run_dir)
            for case_no in cases:
                with self.subTest(set_name=set_name, case_no=case_no):
                    case = load(case_no)
                    default = brief.build_brief_for_case(case)
                    named = brief.build_brief_for_case(
                        case, policy_version=policy_versions.BASE_VERSION
                    )
                    self.assertEqual(
                        money.dumps_canonical(default), money.dumps_canonical(named)
                    )
                    self.assertEqual(recorded[case_no], brief.brief_digest(default)[1])
                    self.assertEqual(recorded[case_no], brief.brief_digest(named)[1])


class VersionTwoRunTests(unittest.TestCase):
    """One genuine version-2 run, end to end, on a scripted transport."""

    def test_the_added_clause_reaches_the_brief_the_run_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, summary = version_two_run(tmp, cases=(101,))
            self.assertEqual([101], summary.completed_cases)
            self.assertEqual(
                runner.policy_v_directory_name(2),
                run_dir.parent.name,
                "a version-2 run has a directory of its own",
            )
            document = runner.read_json(runner.case_cache_path(run_dir, 101))
            self.assertEqual(2, runner.configuration_of(document)["policy_version"])
            # The brief really is the amended one: the clause the amendment adds
            # resolves in the policy this case was briefed against, and the
            # digest the case file records is the digest of that brief.
            with version_two_amendments(tmp):
                brief_object = brief.build_brief_for_case(
                    loader.load_case(101), policy_version=2
                )
                rebuilt = brief.brief_digest(brief_object)[1]
            self.assertIn("POL-RD-13", referee.policy_clauses(brief_object))
            self.assertEqual(document["brief_sha256"], rebuilt)


if __name__ == "__main__":
    unittest.main()
