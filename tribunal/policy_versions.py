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

**A separate base.** Not every version is version 1 plus amendments. Version 3
is Ji Guofang's platform-aligned policy, added on 2026-10-08 as a second base of
its own: its three files live under ``policy/v3/``. ``SEPARATE_BASE_VERSIONS``
names those versions, and the functions around it say which directory a version
reads (:func:`base_directory`), whether a version **is** one of them
(:func:`is_a_separate_base`), which base a version belongs to
(:func:`separate_base_of`) and the highest version the repository can brief at
(:func:`highest_available_version`). ``current_version`` stays what it always
was -- the version of the **amendment sequence** on base 1, which is what the
next amendment there would compute -- so a separate base does not move it.

**Amendments on a separate base.** A separate base carries its own amendment
sequence, under exactly the rules the base-1 sequence obeys: one clause per file,
``NNNN-<slug>.json`` numbered from ``0001``, the clause's id the next free number
for its prefix, and add-only. They live at ``policy/v3/amendments/``, and the
numbering is the one the sheet that added it fixes: **version 3 is the base
alone, and version 3 + k applies the base-3 amendments ``0001`` to k**. So
``POL-NS-11``, the first clause added on base 3, makes **version 4**. The base-1
sequence is untouched by this: its amendments still apply to base 1 only, so
versions 1 and 2 are exactly what they were.

That gives every version one owner. Base 1 owns versions 1 and 2, and its
sequence can never grow past ``0001`` -- amendment ``0002`` there would compute
version 3, which base 3 owns -- so :func:`refuse_a_taken_version` refuses it.
Base 3 owns 3 and up. An amendment is refused when the version it would compute
belongs to a **different** base, and allowed when it belongs to its own, which is
what lets base 3's own first amendment compute version 4.
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

# Versions that are **their own base** rather than version 1 plus amendments.
# Each entry maps the version number to the directory under ``policy/`` whose
# three files it is. Version 3 is Ji Guofang's platform-aligned policy, added on
# 2026-10-08: a second base, kept beside the version-1 files, with **no
# amendment applied to it** -- the clause amendment ``0001`` adds to version 1 is
# already part of version 3's own text.
#
# The version numbers here are reserved. An amendment that computed one of them
# would be a second policy under one number, so :func:`refuse_a_taken_version`
# refuses one, and it is why ``policy/amendments/`` can never reach 0002.
SEPARATE_BASE_VERSIONS = {3: "v3"}

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

# One more field an amendment **on a separate base** may carry: a ``note`` saying
# how the clause was approved where it did not come through a ``policy_gaps``
# report. ``POL-NS-11`` is the case it was widened for: the key owner approved it
# directly after the 2026-10-08 development run, on cases 1734 and 2734, so its
# ``report_file`` and ``report_sha256`` are null and the note says why.
#
# It is **not** allowed on base 1. There the exact key set is the mechanism by
# which "an amendment adds one clause and can never edit one" is true rather than
# intended, and the amendment ``0001`` on that base has no note. The check is
# per base rather than global so that widening one base's schema cannot widen the
# other's.
AMENDMENT_NOTE_FIELD = "note"
AMENDMENT_NOTE_BASES = frozenset({3})


class AmendmentError(Exception):
    """An amendment, or a set of them, that this code will not apply."""


# --------------------------------------------------------------------------
# The set of amendments on disk
# --------------------------------------------------------------------------
def amendments_dir(root: Optional[Any] = None) -> Path:
    """The directory the **base-1** amendments live in, under ``root`` or the repository.

    This stays the one place the base-1 path is computed, so the tests that
    redirect this single function still redirect every base-1 read of it.
    """
    base = Path(root) if root is not None else POLICY_DIR
    return base / AMENDMENTS_DIRNAME


def amendments_dir_for(base_version: int, root: Optional[Any] = None) -> Path:
    """The amendments directory of **one base**.

    Base 1's is the one :func:`amendments_dir` computes, so a caller that
    redirects that function redirects base 1 everywhere. A separate base keeps
    its own amendments beside its own three files, which is
    ``policy/v3/amendments/`` for base 3 -- the same layout ``policy/amendments/``
    has for base 1, one directory down.
    """
    if base_version == BASE_VERSION:
        return amendments_dir(root)
    return base_directory(base_version, root) / AMENDMENTS_DIRNAME


def amendment_files(
    root: Optional[Any] = None, base_version: int = BASE_VERSION
) -> List[Path]:
    """Every amendment file **on one base**, in numeric order.

    A file that is not named ``NNNN-<slug>.json`` is refused rather than
    skipped, and so are a number used twice and a sequence with a hole in it.
    "Version N applies ``0001`` through ``N-1``" only means something if the
    numbers below N are exactly the ones on disk: a hole would make the current
    version name amendments that do not exist. A separate base's sequence is
    checked by the same rules, because it is the same kind of sequence.
    """
    directory = amendments_dir_for(base_version, root)
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
    """The version the amendment sequence is at: 1 plus the amendments on disk.

    This is the version of the **amendment sequence** on base 1, and it is what
    the next amendment there would compute. It is not the highest version the
    repository can brief at: a separate base carries its own sequence, so it is
    not counted here. Use :func:`highest_available_version` for that, or
    :func:`version_on_base` for one base.
    """
    return BASE_VERSION + len(amendment_files(root))


def amendments_on(base_version: int, root: Optional[Any] = None) -> int:
    """How many amendments one base carries.

    The number an amendment approved next would take is this plus one, which is
    what :func:`apply_amendments` and ``policy_gaps approve`` both need.
    """
    return len(amendment_files(root, base_version=base_version))


def version_on_base(base_version: int, root: Optional[Any] = None) -> int:
    """The highest version one base reaches: the base plus its own amendments.

    Base 1 gives :func:`current_version`. Base 3 gives 3 plus the amendments under
    ``policy/v3/amendments/``, so the base alone is version 3 and the first
    amendment on it makes version 4.
    """
    return base_version + amendments_on(base_version, root)


# --------------------------------------------------------------------------
# Separate bases
# --------------------------------------------------------------------------
def is_a_separate_base(version: Any) -> bool:
    """Whether ``version`` **is** a separate base rather than version 1 plus amendments.

    A version built from a separate base by one of that base's own amendments is
    not itself a base: version 4 is base 3 with its first amendment applied. Use
    :func:`separate_base_of` for "which base does this version belong to".
    """
    return version in SEPARATE_BASE_VERSIONS


def separate_base_of(version: Any) -> Optional[int]:
    """The separate base ``version`` belongs to, or ``None`` for the base-1 sequence.

    Every version at or above a separate base's own number belongs to that base:
    version 3 is the base alone and version 4 is the base with its amendment
    ``0001`` applied, so both read ``policy/v3/``. With more than one base the
    highest one at or below the version wins, which keeps a later base's versions
    its own.
    """
    candidates = [base for base in SEPARATE_BASE_VERSIONS if version >= base]
    return max(candidates) if candidates else None


def owner_of_version(version: int) -> int:
    """The base that owns a policy version: a separate base, or base 1.

    Every version has exactly one owner, which is what makes
    :func:`refuse_a_taken_version` a question with an answer: versions 1 and 2 are
    base 1's, and 3 and up are base 3's.
    """
    base = separate_base_of(version)
    return BASE_VERSION if base is None else base


def base_directory(version: int, root: Optional[Any] = None) -> Path:
    """The directory a version's three files are read from.

    Version 1, and every version built from it by amendment, reads ``policy/``
    itself. A separate base reads its own subdirectory of it -- and so does a
    version built from that base by one of its own amendments, because the files
    are the base's own. ``root`` overrides ``policy/`` for a caller that points
    the whole thing elsewhere, exactly as it does for the amendments directory.
    """
    base = Path(root) if root is not None else POLICY_DIR
    owner = separate_base_of(version)
    subdirectory = SEPARATE_BASE_VERSIONS.get(owner) if owner is not None else None
    return base if subdirectory is None else base / subdirectory


def highest_available_version(root: Optional[Any] = None) -> int:
    """The highest policy version this repository can brief at.

    The amendment sequence on base 1 gives :func:`current_version`; every separate
    base gives its own sequence, and they are independent. The highest of them is
    what a command line may ask for, so with one amendment on base 3 the answer is
    4 -- version 3 plus that amendment -- even though base 1's own sequence is
    still at 2.
    """
    tops = [current_version(root)]
    tops.extend(
        version_on_base(base, root) for base in sorted(SEPARATE_BASE_VERSIONS)
    )
    return max(tops)


def refuse_a_taken_version(version: int, base_version: int = BASE_VERSION) -> None:
    """Refuse a version number that belongs to a **different** base.

    An amendment that computed such a number would be a second policy under one
    number: ``load_policies`` would read the other base's own files for that
    version, and the amendment's clause would reach no brief at all. So amendment
    ``0002`` on base 1 is refused -- it would compute version 3, which base 3 owns
    -- while amendment ``0001`` on base 3 is allowed, because version 4 is that
    base's own next version. It refuses in both directions, so base 3 cannot
    compute base 1's versions either. The check lives here rather than at a call
    site so every caller is refused the same way, and the message names the
    directory the owning base is kept at.
    """
    owner = owner_of_version(version)
    if owner == base_version:
        return
    where = (
        "policy/{0}/".format(SEPARATE_BASE_VERSIONS[owner])
        if owner in SEPARATE_BASE_VERSIONS
        else "policy/"
    )
    if version > base_version:
        detail = (
            "amendment {0:04d} on base {1} would compute it, a second policy "
            "under the same number".format(version - base_version, base_version)
        )
    else:
        detail = (
            "an amendment on base {0} computes versions above {0}, and {1} is "
            "below it".format(base_version, version)
        )
    raise AmendmentError(
        "policy version {0} belongs to policy base {1}, kept at {2}, not to base "
        "{3}: {4}".format(version, owner, where, base_version, detail)
    )


# --------------------------------------------------------------------------
# One amendment
# --------------------------------------------------------------------------
def load_amendment(path: Any, base_version: int = BASE_VERSION) -> Dict[str, Any]:
    """One amendment file on ``base_version``, read and checked. Raises ``AmendmentError``.

    The checks here are the ones that make "adds one clause" true rather than
    merely intended: the exact key set at the top level and again inside the
    clause, an id of the right shape and of a known prefix, and a clause
    category that agrees with the file it is going to join.

    ``base_version`` decides one thing and one thing only: whether a ``note``
    field is allowed beside the provenance set. A separate base's amendments may
    carry one, because a clause there can be approved by hand rather than through
    a ``policy_gaps`` report -- ``POL-NS-11`` is such a clause. Base 1's may not,
    because there the exact key set is the mechanism that leaves nowhere to write
    an edit. The clause's own eight fields are the same on both.

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
    # ``note`` is **allowed** on a base that takes one and never required: the
    # provenance set is what every amendment must carry, and a note is an extra
    # sentence a hand-approved clause may add.
    required = set(AMENDMENT_FIELDS) | {"clause"}
    allowed = set(AMENDMENT_FIELDS) | {"clause"}
    if base_version in AMENDMENT_NOTE_BASES:
        allowed.add(AMENDMENT_NOTE_FIELD)
    missing = sorted(required - set(document))
    extra = sorted(set(document) - allowed)
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
    """``policies`` with the amendments of ``version``'s own base applied.

    On base 1 that is amendments ``0001`` through ``version - 1``; on a separate
    base it is that base's ``0001`` through ``version - base``, so base 3's
    version 4 applies base 3's ``0001``.

    ``files`` maps each policy's key in ``policies`` to the filename it was read
    from, so the prefix of a clause id can find the policy it belongs to without
    this module knowing the loader's own layout. A clause whose policy is not in
    ``policies`` is skipped: it belongs to a file this brief does not carry.

    ``version`` is decomposed by its **own base**: base 1's versions apply the
    amendments under ``policy/amendments/``, and a separate base's versions apply
    the amendments under that base's own directory. Version 3 is base 3 alone and
    has no amendment to apply, so it is refused here -- the loader returns its
    files before reaching this function. Version 4 applies base 3's ``0001``.

    The input is not modified. Each target file's ``version`` string gains
    ``+amendment.<highest number it received>``, so a brief says which
    amendments produced it.
    """
    if not isinstance(version, int) or isinstance(version, bool):
        raise AmendmentError(
            "a policy version is an integer, and {0!r} is not".format(version)
        )
    owner = separate_base_of(version)
    base = BASE_VERSION if owner is None else owner
    if owner is not None and version == owner:
        # A separate base is its own policy and has no amendment of its own: its
        # text already carries what amendment 0001 adds to version 1, so there is
        # nothing for this function to apply and reading an amendments directory
        # for it would be reading the wrong policy's provenance.
        raise AmendmentError(
            "policy version {0} is a separate policy base, kept at policy/{1}/, "
            "and amendments are never applied to it".format(
                version, SEPARATE_BASE_VERSIONS[owner]
            )
        )
    available = amendment_files(root, base_version=base)
    if version < base:
        raise AmendmentError(
            "the lowest policy version is {0}, and {1} was asked for".format(
                base, version
            )
        )
    if version > base + len(available):
        raise AmendmentError(
            "there is no policy version {0}; this repository is at version {1}, "
            "so {2} amendment{3} can be applied".format(
                version,
                base + len(available),
                len(available),
                "s" if len(available) != 1 else "",
            )
        )

    applied = {key: _copy_policy(policy) for key, policy in policies.items()}
    by_file = {name: key for key, name in files.items()}
    highest: Dict[str, int] = {}

    for number, path in enumerate(available[: version - base], start=1):
        amendment = load_amendment(path, base_version=base)
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
