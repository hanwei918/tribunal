"""Policy versions: the three policy files, plus the amendments approved on top.

The policy as committed is **version 1** -- ``policy/general.json``,
``policy/no_show.json`` and ``policy/route_deviation.json`` exactly as they are.
An **amendment** is one approved clause in its own file under
``policy/amendments/``, named ``NNNN-<slug>.json`` and numbered from ``0001``.
The current version is 1 plus the number of files in that directory, and
**version N applies amendments ``0001`` through ``N-1``**: version 1 is the
policy with nothing applied, version 2 is the policy with ``0001`` applied.

An amendment only ever **adds** a clause, and that is enforced rather than
asked for. The file carries exactly one ``clause`` and a fixed set of
provenance fields and no other key at all, so there is nowhere to express an
edit or a removal; and the clause's id must be the next free number for its
prefix, so an id that is already taken is refused. This matters because the
brief parses the prose of several existing clauses: an amendment that rewrote
one would change what a brief means while leaving every id where it was.

The prefix of the id decides which file the clause joins, and the clause's own
``category`` must agree with that file's. An amendment to a policy the brief in
hand does not carry is **skipped rather than refused** -- a no-show clause has
no business in a route-deviation brief, and one run briefs cases of both
categories.

The directory is a parameter with the repository's own path as its default, so
every test can point it at a temporary directory.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Where the approved amendments live, beside the three files they amend.
POLICY_DIR = PROJECT_ROOT / "policy"
AMENDMENTS_DIRNAME = "amendments"
README_FILE = "README.md"

# ``0001-<slug>.json``: four digits, then lower-case words joined by hyphens.
_AMENDMENT_FILE_RE = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.json$")

# Version 1 is the policy as committed, with nothing applied to it.
BASE_VERSION = 1

# What a file's ``version`` string gains once an amendment has reached it. The
# number it carries is the highest one that file received.
AMENDMENT_MARKER = "+amendment."
AMENDMENT_SUFFIX = AMENDMENT_MARKER + "{0:04d}"

# The clause id, and the file each prefix joins. Any other prefix is refused.
CLAUSE_ID_RE = re.compile(r"^POL-(NS|RD|GEN)-(\d{2})$")
PREFIX_FILES = {
    "GEN": "general.json",
    "NS": "no_show.json",
    "RD": "route_deviation.json",
}

# The category each prefix's file carries. Kept here rather than read off disk
# so that checking one amendment does not depend on the working tree, and a
# test pins it against the three real files so it cannot drift from them.
PREFIX_CATEGORY = {
    "GEN": "GENERAL",
    "NS": "NO_SHOW_CHARGE",
    "RD": "ROUTE_DEVIATION",
}

# The eight fields every clause carries, and no ninth.
CLAUSE_FIELDS = (
    "id",
    "title",
    "category",
    "rule",
    "requires",
    "licenses",
    "favours",
    "notes",
)

# What an amendment carries beside its clause: where it came from and who
# approved it. Nothing else may appear, which is what leaves no room for an
# edit or a removal to be written down.
AMENDMENT_FIELDS = (
    "base_version",
    "proposal_file",
    "proposal_sha256",
    "report_file",
    "report_sha256",
    "cluster_id",
    "cases",
    "approved_by",
    "approved_at",
)


class AmendmentError(Exception):
    """An amendment, or a set of them, that this code will not apply."""


# --------------------------------------------------------------------------
# The set of amendments on disk
# --------------------------------------------------------------------------
def amendments_dir(root: Optional[Any] = None) -> Path:
    """The directory the amendments live in, under ``root`` or the repository."""
    base = Path(root) if root is not None else POLICY_DIR
    return base / AMENDMENTS_DIRNAME


def amendment_files(root: Optional[Any] = None) -> List[Path]:
    """Every amendment file, in numeric order.

    A file that is not named ``NNNN-<slug>.json`` is refused rather than
    skipped, and so are a number used twice and a sequence with a hole in it.
    "Version N applies ``0001`` through ``N-1``" only means something if the
    numbers below N are exactly the ones on disk: a hole would make the current
    version name amendments that do not exist.
    """
    directory = amendments_dir(root)
    if not directory.is_dir():
        return []
    found: List[Tuple[int, Path]] = []
    for path in sorted(directory.iterdir()):
        if path.name == README_FILE:
            continue
        if path.is_dir():
            raise AmendmentError(
                "every file under {0} must be an amendment, and {1} is a "
                "directory".format(directory, path.name)
            )
        match = _AMENDMENT_FILE_RE.match(path.name)
        if match is None:
            raise AmendmentError(
                "an amendment file is named NNNN-<slug>.json, and {0!r} is "
                "not".format(path.name)
            )
        found.append((int(match.group(1)), path))

    numbers = [number for number, _path in found]
    repeated = sorted({number for number in numbers if numbers.count(number) > 1})
    if repeated:
        raise AmendmentError(
            "amendment number{0} {1} appear{0} more than once".format(
                "s" if len(repeated) > 1 else "",
                ", ".join("{0:04d}".format(number) for number in repeated),
            )
        )
    expected = list(range(1, len(found) + 1))
    if numbers != expected:
        raise AmendmentError(
            "the amendments must run 0001..{0:04d} with no holes; on disk they "
            "are {1}".format(
                len(found),
                ", ".join("{0:04d}".format(number) for number in numbers) or "none",
            )
        )
    return [path for _number, path in found]


def current_version(root: Optional[Any] = None) -> int:
    """The version this repository is at: 1 plus the amendments on disk."""
    return BASE_VERSION + len(amendment_files(root))


# --------------------------------------------------------------------------
# One amendment
# --------------------------------------------------------------------------
def load_amendment(path: Any) -> Dict[str, Any]:
    """One amendment file, read and checked. Raises ``AmendmentError``.

    The checks here are the ones that make "adds one clause" true rather than
    merely intended: the exact key set at the top level and again inside the
    clause, an id of the right shape and of a known prefix, and a clause
    category that agrees with the file it is going to join.

    Whether the number is the next free one is **not** decided here, because
    that depends on the amendments before it; :func:`apply_amendments` decides
    it against the clauses already in hand.
    """
    source = Path(path)
    try:
        # ``parse_float=Decimal``, the hook every other JSON read in this
        # repository uses for a document that may hold a money value. Read
        # without it, an amendment carrying an amount would be the one place a
        # policy number arrived as a binary float -- and the amendment's clause
        # is copied straight into the brief the agents are handed.
        document = json.loads(source.read_text(encoding="utf-8"), parse_float=Decimal)
    except FileNotFoundError:
        raise AmendmentError("there is no amendment file at {0}".format(source))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AmendmentError("{0} is not valid JSON: {1}".format(source, exc))

    if not isinstance(document, Mapping):
        raise AmendmentError(
            "{0} must hold one amendment object, and holds a {1}".format(
                source, type(document).__name__
            )
        )
    expected = set(AMENDMENT_FIELDS) | {"clause"}
    missing = sorted(expected - set(document))
    extra = sorted(set(document) - expected)
    if missing or extra:
        raise AmendmentError(
            "{0} carries the wrong fields: missing {1}, unexpected {2}. An "
            "amendment carries one clause and its provenance and nothing else, "
            "so there is nowhere to write an edit or a removal.".format(
                source, missing or "none", extra or "none"
            )
        )

    clause = document["clause"]
    if not isinstance(clause, Mapping):
        raise AmendmentError(
            "{0}'s clause must be an object, and is a {1}".format(
                source, type(clause).__name__
            )
        )
    clause_missing = sorted(set(CLAUSE_FIELDS) - set(clause))
    clause_extra = sorted(set(clause) - set(CLAUSE_FIELDS))
    if clause_missing or clause_extra:
        raise AmendmentError(
            "{0}'s clause carries the wrong fields: missing {1}, unexpected "
            "{2}. A clause carries {3}.".format(
                source,
                clause_missing or "none",
                clause_extra or "none",
                ", ".join(CLAUSE_FIELDS),
            )
        )

    clause_id = clause["id"]
    match = CLAUSE_ID_RE.match(clause_id) if isinstance(clause_id, str) else None
    if match is None:
        raise AmendmentError(
            "{0} adds a clause with id {1!r}; a policy clause id matches {2}, "
            "and any other prefix is refused".format(
                source, clause_id, CLAUSE_ID_RE.pattern
            )
        )

    prefix = match.group(1)
    target = PREFIX_FILES[prefix]
    declared = clause["category"]
    if declared != PREFIX_CATEGORY[prefix]:
        raise AmendmentError(
            "{0} adds {1} to {2}, whose category is {3!r}, and the clause "
            "declares {4!r}".format(
                source, clause_id, target, PREFIX_CATEGORY[prefix], declared
            )
        )
    return dict(document)


# --------------------------------------------------------------------------
# Applying them
# --------------------------------------------------------------------------
def apply_amendments(
    policies: Mapping[str, Any],
    version: int,
    *,
    files: Mapping[str, str],
    root: Optional[Any] = None,
) -> Dict[str, Any]:
    """``policies`` with amendments ``0001`` through ``version - 1`` applied.

    ``files`` maps each policy's key in ``policies`` to the filename it was read
    from, so the prefix of a clause id can find the policy it belongs to without
    this module knowing the loader's own layout. A clause whose policy is not in
    ``policies`` is skipped: it belongs to a file this brief does not carry.

    The input is not modified. Each target file's ``version`` string gains
    ``+amendment.<highest number it received>``, so a brief says which
    amendments produced it.
    """
    if not isinstance(version, int) or isinstance(version, bool):
        raise AmendmentError(
            "a policy version is an integer, and {0!r} is not".format(version)
        )
    available = amendment_files(root)
    if version < BASE_VERSION:
        raise AmendmentError(
            "the lowest policy version is {0}, and {1} was asked for".format(
                BASE_VERSION, version
            )
        )
    if version > BASE_VERSION + len(available):
        raise AmendmentError(
            "there is no policy version {0}; this repository is at version {1}, "
            "so {2} amendment{3} can be applied".format(
                version,
                BASE_VERSION + len(available),
                len(available),
                "s" if len(available) != 1 else "",
            )
        )

    applied = {key: _copy_policy(policy) for key, policy in policies.items()}
    by_file = {name: key for key, name in files.items()}
    highest: Dict[str, int] = {}

    for number, path in enumerate(available[: version - 1], start=1):
        amendment = load_amendment(path)
        clause = amendment["clause"]
        match = CLAUSE_ID_RE.match(clause["id"])
        prefix = match.group(1)
        target = PREFIX_FILES[prefix]
        key = by_file.get(target)
        if key is None:
            # An amendment to a policy this brief does not carry. The clause
            # belongs to the other category's file and is not part of this case.
            continue
        policy = applied[key]
        existing = _clause_numbers(policy, prefix)
        next_free = max(existing) + 1 if existing else 1
        if int(match.group(2)) != next_free:
            raise AmendmentError(
                "{0} adds {1}, and the next free {2} clause is POL-{2}-{3:02d}. "
                "An amendment adds the next clause and never edits or replaces "
                "one.".format(path.name, clause["id"], prefix, next_free)
            )
        policy["clauses"].append(dict(clause))
        highest[target] = max(highest.get(target, 0), number)

    for target, number in highest.items():
        policy = applied[by_file[target]]
        policy["version"] = _version_with_suffix(policy.get("version"), number)
    return applied


def _copy_policy(policy: Mapping[str, Any]) -> Dict[str, Any]:
    """A policy that can be appended to without touching the caller's."""
    copied = dict(policy)
    copied["clauses"] = [dict(clause) for clause in (policy.get("clauses") or ())]
    return copied


def _clause_numbers(policy: Mapping[str, Any], prefix: str) -> List[int]:
    """Every number already used by ``prefix`` in one policy file."""
    numbers: List[int] = []
    for clause in policy.get("clauses") or ():
        if not isinstance(clause, Mapping):
            continue
        clause_id = clause.get("id")
        match = CLAUSE_ID_RE.match(clause_id) if isinstance(clause_id, str) else None
        if match is not None and match.group(1) == prefix:
            numbers.append(int(match.group(2)))
    return numbers


def _version_with_suffix(version: Any, number: int) -> str:
    """``1.1.0`` and amendment 2 become ``1.1.0+amendment.0002``.

    Any suffix already there is replaced rather than appended to, so applying
    the same set twice cannot produce ``+amendment.0001+amendment.0001``.
    """
    base = str(version or "").split(AMENDMENT_MARKER)[0]
    return base + AMENDMENT_SUFFIX.format(number)
