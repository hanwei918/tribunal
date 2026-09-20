"""Case loader for the Tribunal workspace.

This module implements the loader stage exactly as specified by
``data/PUBLIC-CONTRACT.md``. It uses the Python standard library only.

The four public entry points are:

``load_case(case_no)``
    Return one case dict with all four top-level keys retained, after checking
    that the requested case number, the manifest entry, the filename and the
    loaded file's own ``case_no`` all agree.

``load_policies(category)``
    Return the general policy plus the policy for ``category``, as whole files
    (metadata included), so the arithmetic constants reach the agents.

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
from pathlib import Path
from typing import Any, Dict, List, Tuple

# --------------------------------------------------------------------------
# Locations. ``tribunal/loader.py`` sits directly under the project root.
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CASES_DIR = DATA_DIR / "cases"
POLICY_DIR = PROJECT_ROOT / "policy"
INDEX_PATH = DATA_DIR / "index.json"

# The contract fixes the four top-level case keys; all four must be retained.
CASE_KEYS = ("schema_version", "case_no", "dispute", "evidence")

GENERAL_POLICY_FILE = "general.json"

# The only two supported dispute categories, and the policy each selects.
# The contract says to reject anything else rather than guess a policy.
CATEGORY_POLICY_FILES = {
    "ROUTE_DEVIATION": "route_deviation.json",
    "NO_SHOW_CHARGE": "no_show.json",
}

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
    """Read one UTF-8 JSON document, translating I/O problems to LoaderError."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
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
    """Resolve a manifest ``file`` value to a path under ``data/``.

    The contract states that ``file`` is relative to ``data/`` and always has
    the form ``cases/case-<case_no>.json`` with the case number zero-padded to
    five digits, so the filename can be checked against the case number.
    """
    relative = entry.get("file")
    if not isinstance(relative, str) or not relative:
        raise ManifestMismatchError(
            "manifest entry for case {0} has no 'file' string".format(case_no)
        )

    path = (DATA_DIR / relative).resolve()
    if not path.is_relative_to(DATA_DIR.resolve()):
        raise ManifestMismatchError(
            "manifest 'file' for case {0} escapes data/: {1!r}".format(case_no, relative)
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
    file's own ``case_no`` must all agree; any disagreement raises.
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


def load_policies(category: str) -> Dict[str, Any]:
    """Return the general policy plus the policy for ``category``.

    Both are returned as whole policy files, metadata included, so the
    arithmetic constants (for example ``fare_model`` and ``fee_schedule``)
    reach the agents. An unsupported category raises rather than defaulting.
    """
    filename = CATEGORY_POLICY_FILES.get(category)
    if filename is None:
        raise UnsupportedCategoryError(
            "unsupported dispute category {0!r}; supported categories: {1}".format(
                category, ", ".join(sorted(CATEGORY_POLICY_FILES))
            )
        )
    return {
        "general": _read_json(POLICY_DIR / GENERAL_POLICY_FILE),
        "category": _read_json(POLICY_DIR / filename),
    }


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
    """
    canonical = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return canonical, digest
