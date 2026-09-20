"""Tribunal - application package.

The only implemented stage so far is the case loader. Its public surface is
re-exported here so callers can use ``from tribunal import load_case``.

Everything in this module is specified by ``data/PUBLIC-CONTRACT.md``.
"""

from .loader import (
    CASE_KEYS,
    CATEGORY_POLICY_FILES,
    FORBIDDEN_KEYS,
    CaseNotFoundError,
    CaseShapeError,
    ForbiddenKeyError,
    LoaderError,
    ManifestMismatchError,
    UnsupportedCategoryError,
    build_bundle,
    bundle_digest,
    index_artifacts,
    issue_details_of,
    load_case,
    load_policies,
    missing_payload_ids,
)

__all__ = [
    "CASE_KEYS",
    "CATEGORY_POLICY_FILES",
    "FORBIDDEN_KEYS",
    "CaseNotFoundError",
    "CaseShapeError",
    "ForbiddenKeyError",
    "LoaderError",
    "ManifestMismatchError",
    "UnsupportedCategoryError",
    "build_bundle",
    "bundle_digest",
    "index_artifacts",
    "issue_details_of",
    "load_case",
    "load_policies",
    "missing_payload_ids",
]
