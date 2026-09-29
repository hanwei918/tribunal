"""Case loader for the Tribunal workspace.

This module implements the loader stage exactly as specified by
``data/PUBLIC-CONTRACT.md``. It uses the Python standard library only.

The four public entry points are:

``load_case(case_no)``
    Return one case dict with all four top-level keys retained, after checking
    that the requested case number, the manifest entry, the filename and the
    loaded file's own ``case_no`` all agree.

``load_policies(category, policy_version=1)``
    Return the general policy plus the policy for ``category``, as whole files
    (metadata included), so the arithmetic constants reach the agents. A version
    above 1 applies the approved amendments numbered below it; version 1 is the
    three files as committed and is returned untouched.

``build_bundle(case_no)``
    Return the runtime bundle: the selected public case content plus the
    selected policies, and nothing else.

``bundle_digest(bundle)``
    Return ``(canonical_json_str, sha256_hex)`` for the bundle. The hex string
    is the value published as ``bundle_sha256``.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import money, policy_versions

# --------------------------------------------------------------------------
# Locations. ``tribunal/loader.py`` sits directly under the project root.
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CASES_DIR = DATA_DIR / "cases"
POLICY_DIR = PROJECT_ROOT / "policy"
INDEX_PATH = DATA_DIR / "index.json"

# Converted external cases, under their own root and never in the manifest. See
# ``data/PUBLIC-CONTRACT.md``; the corpus is 29 cases and stays 29.
EXTERNAL_DIR = DATA_DIR / "external"

# The filename a case file must carry, for the number it declares. Applied to
# external cases as well as to corpus cases.
_CASE_FILENAME_RE = re.compile(r"^case-(\d{5})$")

# The contract fixes the four top-level case keys; all four must be retained.
CASE_KEYS = ("schema_version", "case_no", "dispute", "evidence")

GENERAL_POLICY_FILE = "general.json"

# The only two supported dispute categories, and the policy each selects.
# The contract says to reject anything else rather than guess a policy.
CATEGORY_POLICY_FILES = {
    "ROUTE_DEVIATION": "route_deviation.json",
    "NO_SHOW_CHARGE": "no_show.json",
}

# Manifest fields that also appear inside the case file's `dispute` object. The
# contract requires the manifest entry and the case file to agree on all of
# them, not only on `case_no`.
MANIFEST_DISPUTE_FIELDS = ("dispute_id", "trip_id", "category")

# Evaluation-only keys that must never appear anywhere inside a runtime bundle.
FORBIDDEN_KEYS = (
    "ground_truth",
    "expected_ruling",
    "expected_amount_sgd",
    "expected_driver_compensation_sgd",
    "expected_referrals",
)


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
class LoaderError(Exception):
    """Base class for every loader failure."""


class CaseNotFoundError(LoaderError):
    """The requested case number is not present in the manifest."""


class ManifestMismatchError(LoaderError):
    """The requested case number, manifest entry, filename and loaded
    ``case_no`` do not all agree."""


class CaseShapeError(LoaderError):
    """A case file does not have the shape the contract requires."""


class UnsupportedCategoryError(LoaderError):
    """The dispute category has no policy mapping."""


class ForbiddenKeyError(LoaderError):
    """A runtime bundle contains an evaluation-only key."""


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------
def _read_json(path: Path) -> Any:
    """Read one UTF-8 JSON document, translating I/O problems to LoaderError.

    ``parse_float=Decimal`` fixes the money representation at the parse
    boundary, where the literal is still available. ``WORKBUDDY-HANDOFF.md``
    says money uses ``Decimal``; without this hook ``json.load`` would hand back
    the nearest binary float — ``fare_breakdown.total_charged`` for case 208
    arrives as the float ``8.0`` — and the literal as written would be lost.

    ``Decimal(str_token)`` is called with the raw token, so ``8.0`` becomes
    ``Decimal("8.0")`` exactly. Integers are untouched: ``parse_int`` is not
    overridden, so ``case_no`` stays an ``int``.
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle, parse_float=Decimal)
    except FileNotFoundError as exc:
        raise LoaderError("file not found: {0}".format(path)) from exc
    except json.JSONDecodeError as exc:
        raise LoaderError("invalid JSON in {0}: {1}".format(path, exc)) from exc


def _load_index() -> List[Dict[str, Any]]:
    """Return ``data/index.json``. The contract fixes it as a JSON array."""
    entries = _read_json(INDEX_PATH)
    if not isinstance(entries, list):
        raise LoaderError("data/index.json must be a JSON array")
    return entries


def _manifest_entry(case_no: int) -> Dict[str, Any]:
    """Return the single manifest entry for ``case_no``."""
    if isinstance(case_no, bool) or not isinstance(case_no, int):
        raise CaseNotFoundError("case_no must be an integer, got {0!r}".format(case_no))

    matches = [entry for entry in _load_index() if entry.get("case_no") == case_no]
    if not matches:
        raise CaseNotFoundError("case {0} is not listed in data/index.json".format(case_no))
    if len(matches) > 1:
        raise ManifestMismatchError(
            "case {0} appears {1} times in data/index.json".format(case_no, len(matches))
        )
    return matches[0]


def _case_path(entry: Dict[str, Any], case_no: int) -> Path:
    """Resolve a manifest ``file`` value to a real path under ``data/cases/``.

    The contract states that ``file`` is relative to ``data/`` and always has
    the form ``cases/case-<case_no>.json`` with the case number zero-padded to
    five digits, so the filename can be checked against the case number.

    The resolved path is constrained to ``data/cases/`` specifically, not
    merely to ``data/``. A manifest entry must never be able to reach
    ``data/answers/``, ``data/PUBLIC-CONTRACT.md`` or anything else under
    ``data/``. ``resolve()`` is applied first, so ``..`` segments and symlinks
    are followed before the containment test and cannot be used to escape.
    """
    relative = entry.get("file")
    if not isinstance(relative, str) or not relative:
        raise ManifestMismatchError(
            "manifest entry for case {0} has no 'file' string".format(case_no)
        )

    path = (DATA_DIR / relative).resolve()
    cases_root = CASES_DIR.resolve()
    if not path.is_relative_to(cases_root):
        raise ManifestMismatchError(
            "manifest 'file' for case {0} resolves outside data/cases/: {1!r}".format(
                case_no, relative
            )
        )

    expected_stem = "case-{0:05d}".format(case_no)
    if path.stem != expected_stem:
        raise ManifestMismatchError(
            "manifest 'file' for case {0} is {1!r}; expected filename {2!r}".format(
                case_no, path.name, expected_stem + ".json"
            )
        )
    return path


def _check_case_shape(case: Any, case_no: int) -> Dict[str, Any]:
    """Verify the loaded document is a case with all four top-level keys."""
    if not isinstance(case, dict):
        raise CaseShapeError("case {0} is not a JSON object".format(case_no))

    missing = [key for key in CASE_KEYS if key not in case]
    if missing:
        raise CaseShapeError(
            "case {0} is missing top-level keys: {1}".format(case_no, ", ".join(missing))
        )

    if case["case_no"] != case_no:
        raise ManifestMismatchError(
            "requested case {0} but the loaded file declares case_no {1!r}".format(
                case_no, case["case_no"]
            )
        )
    if not isinstance(case["dispute"], dict):
        raise CaseShapeError("case {0}: dispute must be an object".format(case_no))
    if not isinstance(case["evidence"], list):
        raise CaseShapeError("case {0}: evidence must be an array".format(case_no))
    return case


def _check_manifest_agreement(
    entry: Dict[str, Any], case: Dict[str, Any], case_no: int
) -> None:
    """Every manifest field that also lives inside the case file must agree.

    ``case_no`` is checked by ``_check_case_shape``. The manifest carries three
    further fields that also appear inside the case file — ``dispute_id``,
    ``trip_id`` and ``category`` — and a manifest that has drifted from its
    case file is exactly the kind of silent corruption the cross-check exists
    to catch. Any disagreement raises, naming the field, the manifest value and
    the file value.
    """
    dispute = case["dispute"]
    for field in MANIFEST_DISPUTE_FIELDS:
        manifest_value = entry.get(field)
        file_value = dispute.get(field)
        if manifest_value != file_value:
            raise ManifestMismatchError(
                "manifest '{0}' for case {1} is {2!r} but the case file's "
                "dispute.{0} is {3!r}".format(field, case_no, manifest_value, file_value)
            )


def _assert_no_forbidden_keys(node: Any, where: str = "bundle") -> None:
    """Recursively reject evaluation-only keys anywhere inside ``node``."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN_KEYS:
                raise ForbiddenKeyError("forbidden key {0!r} at {1}".format(key, where))
            _assert_no_forbidden_keys(value, "{0}.{1}".format(where, key))
    elif isinstance(node, list):
        for position, value in enumerate(node):
            _assert_no_forbidden_keys(value, "{0}[{1}]".format(where, position))


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def load_case(case_no: int) -> Dict[str, Any]:
    """Load one public case, checking every identity the contract names.

    The requested ``case_no``, the manifest entry, the filename and the loaded
    file's own ``case_no`` must all agree, and so must every manifest field that
    also appears inside the case file — ``dispute_id``, ``trip_id`` and
    ``category``. Any disagreement raises.
    """
    entry = _manifest_entry(case_no)
    if entry.get("case_no") != case_no:
        raise ManifestMismatchError(
            "manifest entry for case {0} declares case_no {1!r}".format(
                case_no, entry.get("case_no")
            )
        )

    path = _case_path(entry, case_no)
    case = _check_case_shape(_read_json(path), case_no)
    _check_manifest_agreement(entry, case, case_no)

    # Artifacts are keyed by evidence_id, never by evidence_type: evidence_type
    # repeats inside a case, evidence_id does not. This also rejects duplicates.
    index_artifacts(case)
    return case


def index_artifacts(case: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return ``{evidence_id: artifact}`` for one loaded case.

    Keying by ``evidence_type`` would silently drop artifacts, because an
    ``evidence_type`` value may repeat within a single case.
    """
    index: Dict[str, Dict[str, Any]] = {}
    for artifact in case.get("evidence", []):
        if not isinstance(artifact, dict):
            raise CaseShapeError("case {0}: evidence entry is not an object".format(case.get("case_no")))
        evidence_id = artifact.get("evidence_id")
        if not evidence_id:
            raise CaseShapeError("case {0}: evidence entry without evidence_id".format(case.get("case_no")))
        if evidence_id in index:
            raise CaseShapeError(
                "case {0}: duplicate evidence_id {1!r}".format(case.get("case_no"), evidence_id)
            )
        index[evidence_id] = artifact
    return index


def missing_payload_ids(case: Dict[str, Any]) -> List[str]:
    """Ids of artifacts whose payload is missing.

    ``payload`` is always present as a key, so a missing payload is a *value*
    test (``is None``) and never a key-presence test.
    """
    return [
        artifact["evidence_id"]
        for artifact in case.get("evidence", [])
        if artifact.get("payload") is None
    ]


def issue_details_of(artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return ``admissibility.issue_details``, or ``[]`` when it is absent.

    ``issue_details`` is optional: it is present on 45 artifacts and absent
    from 159, so it must never be subscripted without checking.
    """
    admissibility = artifact.get("admissibility") or {}
    details = admissibility.get("issue_details")
    return details if isinstance(details, list) else []


def load_policies(
    category: str, policy_version: int = policy_versions.BASE_VERSION
) -> Dict[str, Any]:
    """Return the general policy plus the policy for ``category``.

    Both are returned as whole policy files, metadata included, so the
    arithmetic constants (for example ``fare_model`` and ``fee_schedule``)
    reach the agents. An unsupported category raises rather than defaulting.

    ``policy_version`` is the version to build: version 1 is the three files
    exactly as committed, and a higher version applies the approved amendments
    numbered below it. Version 1 returns the files as they were read, without a
    copy, and does not read ``policy/amendments/`` at all -- so a plain run
    builds the bytes it always built, and a broken amendment cannot stop the
    version-1 measurement.
    """
    filename = CATEGORY_POLICY_FILES.get(category)
    if filename is None:
        raise UnsupportedCategoryError(
            "unsupported dispute category {0!r}; supported categories: {1}".format(
                category, ", ".join(sorted(CATEGORY_POLICY_FILES))
            )
        )
    policies = {
        "general": _read_json(POLICY_DIR / GENERAL_POLICY_FILE),
        "category": _read_json(POLICY_DIR / filename),
    }
    if policy_version == policy_versions.BASE_VERSION:
        return policies
    return policy_versions.apply_amendments(
        policies,
        policy_version,
        files={"general": GENERAL_POLICY_FILE, "category": filename},
    )


def build_bundle(case_no: int) -> Dict[str, Any]:
    """Return the runtime bundle for one case.

    The bundle holds the selected public case content and the selected
    policies and nothing else: no manifest, no contract, no file paths, no
    loader diagnostics and no development document. Evaluation-only keys are
    rejected recursively before the bundle is returned.
    """
    case = load_case(case_no)
    policies = load_policies(case["dispute"].get("category"))

    bundle = {"case": case, "policies": policies}
    _assert_no_forbidden_keys(bundle)
    return bundle


def bundle_digest(bundle: Dict[str, Any]) -> Tuple[str, str]:
    """Return ``(canonical_json_str, sha256_hex)`` for ``bundle``.

    Serialisation is fixed by the contract: UTF-8 JSON with
    ``ensure_ascii=False``, ``sort_keys=True`` and ``separators=(",", ":")``.
    The hex digest of exactly those bytes is the ``bundle_sha256`` value.

    The work is done by ``money.dumps_canonical``, because a bundle now carries
    ``Decimal`` amounts and plain ``json.dumps`` cannot write those. Decimals
    are emitted as JSON numbers carrying their own literal, so the canonical
    bytes are unchanged from before the Decimal change.
    """
    canonical = money.dumps_canonical(bundle)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return canonical, digest


def load_external_case(path: Any) -> Dict[str, Any]:
    """Load one converted external case from an explicit path.

    External cases are converted from material the organisers supplied and live
    under ``data/external/``. They are deliberately **not** in
    ``data/index.json``: the manifest indexes the 29-case corpus the benchmark
    measures, and adding a converted case to it would change that corpus. So
    the case is named by its path, and every constraint that does not depend on
    a manifest entry is enforced here instead:

    * the resolved path must stay inside ``data/external/``, so ``..`` segments
      and symlinks are followed and cannot walk out of the root — the same
      containment rule ``_case_path`` applies to ``data/cases/``;
    * the filename must be ``case-<case_no>.json`` for the number the file
      itself declares, so a case cannot be loaded under another case's name;
    * the same four top-level keys, the same shape checks and the same
      duplicate-``evidence_id`` rejection that :func:`load_case` applies.

    What is **not** checked is the manifest cross-check, because there is no
    manifest entry to check against. That is the whole of the difference.
    """
    resolved = Path(path).resolve()
    external_root = EXTERNAL_DIR.resolve()
    if not resolved.is_relative_to(external_root):
        raise ManifestMismatchError(
            "external case path resolves outside data/external/: {0!r}".format(str(resolved))
        )
    if not resolved.is_file():
        raise LoaderError("file not found: {0}".format(resolved))

    match = _CASE_FILENAME_RE.match(resolved.stem)
    if match is None:
        raise ManifestMismatchError(
            "external case filename {0!r} is not case-<five digits>.json".format(resolved.name)
        )
    case_no = int(match.group(1))

    case = _check_case_shape(_read_json(resolved), case_no)
    index_artifacts(case)
    return case


# --------------------------------------------------------------------------
# A whole set of external cases, named by number
# --------------------------------------------------------------------------
# A set is a directory under ``data/external/`` carrying its own ``index.json``
# and its case files. It is not the corpus manifest and is never merged into it.
EXTERNAL_INDEX_FILE = "index.json"

# An external set's index may record the digest of each case file. The corpus
# manifest does not carry this field; where it is present it is checked, because
# an index that states a digest and is not held to it is a comment.
INDEX_DIGEST_FIELD = "sha256"


def external_set_directory(set_dir: Any) -> Path:
    """Resolve one external set's directory, constrained to ``data/external/``.

    The containment rule is :func:`load_external_case`'s, applied one level up:
    ``..`` segments and symlinks are followed before the test, so a set cannot
    be pointed at the corpus, at ``policy/`` or anywhere else outside the
    external root. ``data/external/`` itself is refused, because a set is a
    named directory under it and the root holds no index of its own.
    """
    resolved = Path(set_dir).resolve()
    external_root = EXTERNAL_DIR.resolve()
    if not resolved.is_relative_to(external_root) or resolved == external_root:
        raise ManifestMismatchError(
            "external set directory resolves outside data/external/: {0!r}".format(str(resolved))
        )
    if not resolved.is_dir():
        raise LoaderError("external set directory not found: {0}".format(resolved))
    return resolved


def load_external_index(set_dir: Any) -> List[Dict[str, Any]]:
    """Return one external set's ``index.json``, which must be an array."""
    entries = _read_json(external_set_directory(set_dir) / EXTERNAL_INDEX_FILE)
    if not isinstance(entries, list):
        raise LoaderError(
            "{0} must be a JSON array".format(
                external_set_directory(set_dir) / EXTERNAL_INDEX_FILE
            )
        )
    return entries


def _external_case_path(set_root: Path, entry: Dict[str, Any], case_no: int) -> Path:
    """Resolve one set entry's ``file`` to a real path inside the set.

    The same two constraints ``_case_path`` applies to the corpus, with the set
    directory as the root instead of ``data/cases/``: the resolved path must
    stay inside the set, and the filename must be ``case-<case_no>.json`` for
    the number the entry declares. A manifest that names a path outside its own
    directory, or a case under another case's name, is refused rather than
    followed.
    """
    relative = entry.get("file")
    if not isinstance(relative, str) or not relative:
        raise ManifestMismatchError(
            "set entry for case {0} has no 'file' string".format(case_no)
        )

    path = (set_root / relative).resolve()
    if not path.is_relative_to(set_root):
        raise ManifestMismatchError(
            "set entry 'file' for case {0} resolves outside the set directory: {1!r}".format(
                case_no, relative
            )
        )

    expected_stem = "case-{0:05d}".format(case_no)
    if path.stem != expected_stem:
        raise ManifestMismatchError(
            "set entry 'file' for case {0} is {1!r}; expected filename {2!r}".format(
                case_no, path.name, expected_stem + ".json"
            )
        )
    return path


def _check_recorded_digest(entry: Dict[str, Any], path: Path, case_no: int) -> None:
    """Hold an entry to the digest it records, where it records one.

    Over the file's bytes and not over a re-serialisation of it: the entry makes
    a claim about the file, so the file is what the claim is checked against.
    The field is optional, because the corpus manifest does not carry it; an
    index without one is silent rather than wrong, and is not refused.
    """
    recorded = entry.get(INDEX_DIGEST_FIELD)
    if not isinstance(recorded, str) or not recorded:
        return
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != recorded:
        raise ManifestMismatchError(
            "set entry for case {0} records {1} {2!r} but the file's is {3!r}".format(
                case_no, INDEX_DIGEST_FIELD, recorded, actual
            )
        )


def load_external_set_case(set_dir: Any, case_no: int) -> Dict[str, Any]:
    """Load one case of an external set, named by number, from the set's index.

    The set's own ``index.json`` stands in for the corpus manifest, and every
    check :func:`load_case` makes that does not depend on ``data/index.json`` is
    made here: the number appears exactly once, the entry's ``file`` resolves
    inside the set and is named for that number, the loaded document has the
    four top-level keys and declares the number that was asked for, the
    duplicate-``evidence_id`` rejection applies, and the three manifest fields
    that also live inside the case file -- ``dispute_id``, ``trip_id`` and
    ``category`` -- must agree.

    Where the entry records a ``sha256`` the file's bytes are held to it. That
    check has no counterpart in :func:`load_case`, because the corpus manifest
    records no digests; it is enforced here because the set's index does record
    them.

    This is what lets a whole external set be run by the same runner as the
    corpus: the runner loads cases by number, and this is that load for a set
    that is deliberately absent from ``data/index.json``. Adding the set to the
    manifest instead would change the 29-case corpus the submission reports.
    """
    root = external_set_directory(set_dir)

    matches = [entry for entry in load_external_index(root) if entry.get("case_no") == case_no]
    if not matches:
        raise CaseNotFoundError(
            "case {0} is not listed in {1}".format(case_no, root / EXTERNAL_INDEX_FILE)
        )
    if len(matches) > 1:
        raise ManifestMismatchError(
            "case {0} appears {1} times in {2}".format(
                case_no, len(matches), root / EXTERNAL_INDEX_FILE
            )
        )
    entry = matches[0]

    path = _external_case_path(root, entry, case_no)
    if not path.is_file():
        raise LoaderError("file not found: {0}".format(path))
    _check_recorded_digest(entry, path, case_no)

    case = _check_case_shape(_read_json(path), case_no)
    _check_manifest_agreement(entry, case, case_no)
    index_artifacts(case)
    return case
