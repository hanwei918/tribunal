"""Build the debate viewer: one self-contained HTML file, from the committed run.

What this is for
----------------
The track requires an observable record of inter-agent communication, and the
record that already exists is the transcript the pipeline writes for each case.
A transcript is the right evidence and the wrong thing to put on a projector:
it is JSON, it is 30 kB per case, and a reader has to know the pipeline to read
it. This module turns that record into two views a person can look at -- the
run's headline figures over all 29 cases, and one case stepped through in the
order the case was actually decided.

Why a replay rather than live calls
-----------------------------------
A case takes about three and a half minutes end to end, measured
(``runs/deepseek-deepseek-flash/run.json``: 29 cases in 5 985 s of wall clock).
Nobody watches that on stage, and a replay cannot fail in front of an audience.
So the viewer is built from the committed run and makes no network call at all.

The output
----------
``ui/dist/index.html`` -- one file, with every byte of data, CSS and JavaScript
inline. No framework, no CDN, no external request of any kind, so it opens from
``file://`` on a laptop with no internet on a projector at Demo Day, and serves
unchanged from GitHub Pages once the repository is public. The build is
deterministic: the same inputs produce the same bytes, and
``tests/test_ui_build.py`` requires the committed file to equal a fresh build,
because the lesson of this repository is that a stored artefact must not be
able to drift from the code that produces it without something going red.

What it reads, and what it refuses to invent
--------------------------------------------
* ``runs/deepseek-deepseek-flash/`` -- the headline run: per case a result file
  and a transcript, plus ``run.json`` and ``invocations.json`` for provenance.
* the brief for each case, **rebuilt** with :func:`tribunal.brief.build_brief`
  and serialised with :func:`tribunal.money.dumps_canonical`, then checked
  against the ``brief_sha256`` the result recorded. A digest that does not match
  means the brief this code builds is not the brief those agents were handed, so
  the case is **refused**: it is named, and it is not shown. The viewer must show
  the evidence the agents actually received, never a regenerated brief that
  merely resembles it. Policy text is identical across the cases of one category
  (asserted here, not assumed), so it is stored once per category rather than
  twenty-nine times -- the digest is still checked on the full brief first.
* ``eval/answers/ground_truth.json`` -- for the expected-versus-produced view,
  labelled in the viewer as the grading answer key. This module is a
  presentation layer *beside* ``eval/``; nothing under ``tribunal/`` gains any
  path to ``eval/``.
* ``tribunal/model.py`` -- the runtime model, read from the one module that
  decides it. The model id is deliberately not written down here: a second live
  value would be a second decision, and ``tests/test_model.py`` walks this
  directory to make sure there is not one.

The figures are computed, not typed
-----------------------------------
Every headline number comes from :func:`eval.grade.grade` over the same run, so
the viewer cannot print an accuracy the grader does not also print, and the test
that reads the numbers back out of the HTML recomputes them the same way. The
one figure the grader does not compute -- the total of discarded claims across
all judges -- is summed here from the run's own judge outputs, and the test
recomputes that too.

The stance proof, which is the claim the viewer exists to show
--------------------------------------------------------------
The project's central claim is that both advocates read the same evidence and
differ only in stance. A side-by-side view of their claims is not that proof: it
shows what each side argued, not that they were handed the same bytes. The proof
is three facts the run already records, and the viewer shows all three for every
case:

* the two advocates' ``user_sha256`` are equal to each other **and** equal to
  the case's ``brief_sha256`` -- they were handed the same bytes;
* their ``system_sha256`` differ -- their instructions are not identical;
* the lines on which the two rendered system prompts differ all fall inside the
  stance block, which is what ``stance_differing_ranges`` records.

Nothing here is typed in. The prompts are rendered at build time with
:func:`tribunal.pipeline.render_advocate_prompts`, the differing line ranges are
recomputed from that render, and both are compared against what the run stored.
If the recomputed ranges disagree with the stored ones for any case, or if an
advocate's ``user_sha256`` is not the case's ``brief_sha256``, **the build stops
and names the case** -- a proof view that can display an unbacked claim is worse
than no proof view at all. The digests are shown in full, never truncated,
because a digest you cannot compare is not evidence of equality.

Money is carried as its own decimal literal
-------------------------------------------
The pipeline keeps every amount in :class:`decimal.Decimal`. Embedded in the
document as a JSON *number* a value like ``8.05`` would become the nearest
binary double on the way into the page, and the page would then be displaying a
different number from the one the agents were handed. Every ``Decimal`` is
therefore written as a string, so the viewer shows the literal the policy
produced.

Run it with ``python -m ui.build``; ``--check`` compares the committed file
against a fresh build and exits non-zero on any difference.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets  # noqa: E402
from eval import grade  # noqa: E402
from eval import run_benchmark  # noqa: E402
from eval import sealed_roots  # noqa: E402
from tribunal import brief as brief_module  # noqa: E402
from tribunal import llm  # noqa: E402
from tribunal import loader as loader_module  # noqa: E402
from tribunal import model as model_module  # noqa: E402
from tribunal import money  # noqa: E402
from tribunal import pipeline as pipeline_module  # noqa: E402
from tribunal import referee as referee_module  # noqa: E402
from tribunal import transcript as transcript_module  # noqa: E402

__all__ = [
    "BuildError",
    "ViewerPage",
    "RUN_DIR",
    "DIST_DIR",
    "OUTPUT_PATH",
    "INDEX_PATH",
    "DEFAULT_CASE",
    "cached_cases",
    "transcript_cases",
    "cases_the_run_left_evidence_for",
    "cases_whose_briefs_match",
    "run_has_moved_on",
    "pages",
    "build_document",
    "render_html",
    "render_index",
    "main",
]

# The headline run, by directory name. A run directory is named after the model
# id, and this is the one the runtime model decision rests on.
RUN_DIR = PROJECT_ROOT / "runs" / "deepseek-deepseek-flash"

# Where the built file lives. It is committed, so a judge can open it without
# running Python.
DIST_DIR = PROJECT_ROOT / "ui" / "dist"
OUTPUT_PATH = DIST_DIR / "index.html"

# The case the viewer opens on. 208 is the demonstration case: every artifact is
# COMPLETE, the miss is not a miss, and both advocates concede honestly.
DEFAULT_CASE = 208

# The path of a case result file, and nothing else in the run directory. The
# transcripts beside them match ``case-*.json`` too, so the suffix is anchored.
_CASE_FILE_RE = re.compile(r"^case-(\d{5})\.json$")

# The transcript beside it, anchored the same way and for the same reason.
_TRANSCRIPT_FILE_RE = re.compile(r"^case-(\d{5})\.transcript\.json$")

# The link a miss points at, relative to ``ui/dist/index.html``. The note records
# why case 211 is a contested reading rather than a defect. Kept as the corpus
# page's own link, so anything that read it keeps reading the same value; every
# other page recomputes it from its own depth.
_DECISION_NOTE_LINK = "../../" + model_module.DECISION_NOTE

# --------------------------------------------------------------------------
# The pages: one per run, plus the index beside them
# --------------------------------------------------------------------------
# The index is one directory down beside the non-corpus pages, so its own links
# resolve at the same depth as theirs.
INDEX_PATH = DIST_DIR / "runs" / "index.html"

# Where the organisers' sample case was re-run. **Not** ``runs/external/ryde``:
# that directory's brief predates the money facts and no longer rebuilds, so a
# page built from it would refuse the case. The 2026-09-29 re-run is the one
# whose brief this code rebuilds.
RYDE_RUN_DIR = PROJECT_ROOT / "runs" / "rerun-2026-09-29" / "external" / "ryde"
RYDE_EXPECTED_PATH = PROJECT_ROOT / "eval" / "external" / "ryde" / "expected.json"

# The tag each sealed set's single run was made from. The registration records
# the policy version and the fixed arguments; the tag is named here as its own
# value so a page can print it as one rather than as prose inside a caveat.
FREEZE_TAGS = {
    "wild": "freeze-2026-09-30",
    "wild-v2": "freeze-2026-10-03",
}

# The two notes that discuss a sealed set's misses, each named once. The first
# is about the held-out set's run as a whole, so it covers every miss of that
# set; the second names its two cases, so it is attached to those cases only.
THE_SEALED_RUN_NOTE = "docs/notes/2026-09-30-the-sealed-run.md"
THE_SECOND_SEALED_RUN_NOTE = "docs/notes/2026-10-04-the-second-sealed-run.md"


@dataclass(frozen=True)
class ViewerPage:
    """One page: a run to replay, the key to grade it with, and what it says.

    ``load_case`` is the set's own loader -- the manifest for the corpus, the
    set's index for a second set, an explicit path for the organisers' sample
    case. The brief builder is derived from it, so a page cannot brief a case
    with one loader and grade it against another's key.

    ``default_case`` is ``None`` for a page whose opening case is the first one
    that matched all four fields, which is a fact about the built document and
    not about the registration.
    """

    name: str
    run_dir: Path
    output_path: Path
    key_path: Optional[Path]
    policy_version: int
    load_case: Optional[Callable[[int], Mapping[str, Any]]]
    summary: str
    title: str
    brand: str
    badge: str
    # The report a reader can reproduce this page's figures with. It is per set
    # because the sets are not reported by one command: the corpus by
    # ``eval/grade.py``, each sealed set by ``eval/sealed_report.py --set``. A
    # page that named another set's command would send a reader to a figure that
    # is not the one on the page.
    report_tool: str
    caveat: Optional[str]
    freeze_tag: Optional[str]
    sealed: bool
    default_case: Optional[int]
    # A note written about one named case, and a note written about a whole
    # set's misses. The second is not a fallback for the first: the sealed set's
    # note is about that set's misses as a class, and it is the note the sheet
    # names for them. A miss with neither gets no link at all, which is the
    # point -- a link to a note about another case is a claim nobody made.
    miss_notes: Mapping[int, str] = field(default_factory=dict)
    miss_note_for_every_miss: Optional[str] = None
    stated_expectation_path: Optional[Path] = None

    @property
    def depth(self) -> int:
        """How many directories below ``ui/dist`` this page's file sits."""
        return len(self.output_path.relative_to(DIST_DIR).parts) - 1

    def link_to(self, repository_path: str) -> str:
        """A path from the project root, as a link written on this page."""
        return "../" * (self.depth + 2) + repository_path

    @property
    def has_key(self) -> bool:
        """Whether this page is graded against an answer key at all."""
        return self.key_path is not None

    @property
    def brief_builder(self) -> Callable[[int], Mapping[str, Any]]:
        """The brief this page's cases were handed, rebuilt from its own set.

        The version is the registration's, not the command line's: a set that
        fixes version 2 briefs every case at version 2, and there is no way to
        ask this page for version 1.
        """
        load_case = self.load_case
        version = self.policy_version
        return lambda case_no: brief_module.build_brief_for_case(
            load_case(case_no), policy_version=version
        )


def _ryde_case_loader(run_dir: Path) -> Callable[[int], Mapping[str, Any]]:
    """The organisers' sample case, loaded by the path its own run recorded.

    ``run.json`` names the converted case file, and the loader is
    ``loader.load_external_case``: the manifest cannot name a case it does not
    list, and this case is deliberately not in it. The path is read inside the
    loader rather than at import, because this module's own ``_read_json`` is
    defined below the registry.
    """

    def load_case(case_no: int) -> Mapping[str, Any]:
        recorded = _read_json(Path(run_dir) / "run.json").get("external_case_path")
        return loader_module.load_external_case(PROJECT_ROOT / str(recorded))

    return load_case


def _build_pages() -> Dict[str, ViewerPage]:
    """Every page, keyed by the name ``--set`` takes."""
    model = model_module.RUNTIME_MODEL
    corpus = development_sets.CORPUS
    codex = development_sets.SECOND_SET
    wild = development_sets.SEALED_SET
    wild_v2 = development_sets.WILD_V2
    pages = (
        ViewerPage(
            name="corpus",
            run_dir=RUN_DIR,
            output_path=OUTPUT_PATH,
            key_path=corpus.key_path,
            policy_version=corpus.policy_version,
            load_case=corpus.load_case,
            summary=corpus.summary,
            title="Tribunal - debate viewer",
            brand="Tribunal - debate viewer",
            badge="replay of a committed run",
            report_tool="eval/grade.py's report",
            caveat=None,
            freeze_tag=None,
            sealed=False,
            default_case=DEFAULT_CASE,
            # Only case 211 has a note written about it, and only the corpus's
            # own note is that note. Every other miss is a miss and is shown as
            # one, with no link and no claim that the reading is contested.
            miss_notes={211: model_module.DECISION_NOTE},
        ),
        ViewerPage(
            name="codex",
            run_dir=codex.run_dir(model),
            output_path=DIST_DIR / "codex" / "index.html",
            key_path=codex.key_path,
            policy_version=codex.policy_version,
            load_case=codex.load_case,
            summary=codex.summary,
            title="Tribunal - debate viewer - the second development set",
            brand="Tribunal - debate viewer - second development set",
            badge="replay of a committed development run",
            report_tool="the second development set's report, over its own key",
            caveat=None,
            freeze_tag=None,
            sealed=False,
            default_case=None,
        ),
        ViewerPage(
            name="wild",
            run_dir=wild.run_dir(model),
            output_path=DIST_DIR / "wild" / "index.html",
            key_path=wild.key_path,
            policy_version=wild.policy_version,
            load_case=wild.load_case,
            summary=wild.summary,
            title="Tribunal - debate viewer - the held-out set (wild-v1)",
            brand="Tribunal - debate viewer - the held-out set (wild-v1)",
            badge="replay of the held-out set's single run",
            report_tool="python3 -m eval.sealed_report --set wild",
            caveat=development_sets.SEALED_SET_SECTIONS[wild.name][1],
            freeze_tag=FREEZE_TAGS[wild.name],
            sealed=True,
            default_case=None,
            # The note about this set is about its misses as a class, so every
            # miss of the set links to it and no case of the set is named in
            # advance: which cases missed is a fact about the run.
            miss_note_for_every_miss=THE_SEALED_RUN_NOTE,
        ),
        ViewerPage(
            name="wild-v2",
            run_dir=wild_v2.run_dir(model),
            output_path=DIST_DIR / "wild-v2" / "index.html",
            key_path=wild_v2.key_path,
            policy_version=wild_v2.policy_version,
            load_case=wild_v2.load_case,
            summary=wild_v2.summary,
            title="Tribunal - debate viewer - the second sealed set (wild-v2)",
            brand="Tribunal - debate viewer - the second sealed set (wild-v2)",
            badge="replay of the second sealed set's single run",
            report_tool="python3 -m eval.sealed_report --set wild-v2",
            caveat=development_sets.SEALED_SET_SECTIONS[wild_v2.name][1],
            freeze_tag=FREEZE_TAGS[wild_v2.name],
            sealed=True,
            default_case=None,
            # Only these two cases of this set have a note written about them,
            # and it is one note about both. The other cases of the set are
            # misses if they are misses and nothing more.
            miss_notes={
                702: THE_SECOND_SEALED_RUN_NOTE,
                716: THE_SECOND_SEALED_RUN_NOTE,
            },
        ),
        ViewerPage(
            name="ryde-901",
            run_dir=RYDE_RUN_DIR,
            output_path=DIST_DIR / "ryde-901" / "index.html",
            # No key. The organisers' sample case has no entry in any answer
            # key, so it is shown beside their stated expectation and is not
            # graded on four fields at all.
            key_path=None,
            policy_version=1,
            load_case=_ryde_case_loader(RYDE_RUN_DIR),
            summary=(
                "the organisers' sample case, re-run under the current "
                "pipeline; it is not in any answer key and is not graded"
            ),
            title="Tribunal - debate viewer - the organisers' sample case",
            brand="Tribunal - debate viewer - the organisers' sample case",
            badge="replay of the organisers' sample case",
            # Unused on this page: it is not graded, so there is no report for a
            # reader to reproduce. It is named as nothing rather than as some
            # other set's command, so a mistake that printed it would print a
            # sentence with no claim in it.
            report_tool="no report: this case is not graded",
            caveat=None,
            freeze_tag=None,
            sealed=False,
            default_case=901,
            stated_expectation_path=RYDE_EXPECTED_PATH,
        ),
    )
    by_name = {page.name: page for page in pages}
    return by_name


def pages() -> Dict[str, ViewerPage]:
    """Every page the viewer builds, by name. Built fresh; nothing is cached."""
    return _build_pages()


class BuildError(Exception):
    """An input is not the shape the viewer can present."""


# --------------------------------------------------------------------------
# Reading the run
# --------------------------------------------------------------------------
def _read_json(path: Path) -> Any:
    """Parse a JSON file with ``parse_float=Decimal``, as the loader does.

    The hook matters for the same reason it matters in ``loader.py``: a money
    value written ``8.05`` must arrive as the decimal literal and not as the
    nearest binary approximation of it.
    """
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_float=Decimal)


def cached_cases(run_dir: Path = RUN_DIR) -> List[int]:
    """Every case number the run directory holds a result for, ascending.

    The transcript files sit beside the results and share their prefix, so the
    name is matched rather than the prefix alone.
    """
    numbers: List[int] = []
    for path in sorted(Path(run_dir).glob("case-*.json")):
        match = _CASE_FILE_RE.match(path.name)
        if match is not None:
            numbers.append(int(match.group(1)))
    return sorted(numbers)


def _brief_digest(built: Mapping[str, Any]) -> str:
    """The SHA-256 of the brief exactly as the pipeline serialised it.

    The same two steps :func:`tribunal.pipeline.run_case` takes, in the same
    order and with the same serialiser: ``money.dumps_canonical``, then SHA-256
    over those exact bytes. The serialiser is not interchangeable -- any other
    produces a different digest for the same brief, and every case would then be
    refused for the wrong reason.
    """
    canonical = money.dumps_canonical(built)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalise(node: Any) -> Any:
    """The document's own types: ``Decimal`` to its literal, everything else kept.

    A ``Decimal`` becomes a string, so the page shows the literal the policy
    produced rather than the nearest double to it. Floats are left alone: they
    are floats in the pipeline, they round-trip through JSON and back into a
    JavaScript number exactly, and rewriting them would be a claim about
    precision the derived facts do not make.
    """
    if isinstance(node, Decimal):
        return str(node)
    if isinstance(node, Mapping):
        return {str(key): _normalise(value) for key, value in node.items()}
    if isinstance(node, (list, tuple)):
        return [_normalise(value) for value in node]
    return node


# --------------------------------------------------------------------------
# The agents' side of one case
# --------------------------------------------------------------------------
def _agent_block(transcript: Optional[Mapping[str, Any]], role: str) -> Dict[str, Any]:
    """One agent's calls for one case, in order, with its answer parsed out.

    A role can have more than one entry: a response the prompt's shape contract
    rejects is retried, and one shipped run shows exactly that for the judge on
    cases 115 and 213. The retry is part of the record, so every call is carried
    and the viewer shows the ones that did not parse rather than quietly keeping
    only the answer that worked.

    The raw response text is carried only for a call that did **not** parse. For
    a call that did, the parsed value is the same information in a form the page
    can lay out, and keeping both would double the size of the file to say the
    same thing.
    """
    entries = []
    if isinstance(transcript, Mapping):
        for entry in transcript.get("entries", []) or []:
            if isinstance(entry, Mapping) and entry.get("role") == role:
                entries.append(entry)

    calls: List[Dict[str, Any]] = []
    parsed: Optional[Any] = None
    # The digests of the two prompts the answer that was used came from. They
    # are carried because they *are* the stance proof: two advocates handed the
    # same user prompt differed only in the system prompt they were given.
    system_digest: Optional[str] = None
    user_digest: Optional[str] = None
    for entry in entries:
        outcome = entry.get("parse_outcome")
        calls.append(
            {
                "shape": entry.get("shape"),
                "parse_outcome": outcome,
                "attempts": entry.get("attempts"),
                "status": entry.get("status"),
                "duration_seconds": entry.get("duration_seconds"),
                "prompt_tokens": entry.get("prompt_tokens"),
                "completion_tokens": entry.get("completion_tokens"),
                "reasoning_tokens": entry.get("reasoning_tokens"),
                "cached_tokens": entry.get("cached_tokens"),
                "model": entry.get("model"),
                "timestamp": entry.get("timestamp"),
                "note": entry.get("note"),
                "response_text": (
                    entry.get("response_text")
                    if outcome != llm.PARSE_PARSED
                    else None
                ),
            }
        )
        if outcome == llm.PARSE_PARSED and isinstance(entry.get("parsed"), Mapping):
            # The last one that parsed is the answer that was used; an earlier
            # malformed attempt stays in ``calls`` as evidence of the retry.
            parsed = entry.get("parsed")
            system_digest = entry.get("system_sha256")
            user_digest = entry.get("user_sha256")

    return {
        "role": role,
        # None when this role produced nothing that parsed, which the page has
        # to be able to say rather than silently printing "null" as evidence.
        "system_sha256": system_digest,
        "user_sha256": user_digest,
        "calls": calls,
        # Normalised here rather than at each use: the transcript is read with
        # ``parse_float=Decimal`` for the same reason the loader is, so an
        # advocate's ``asserted_weight`` arrives as a Decimal and has to become
        # its literal before it can be embedded in the page.
        "parsed": _normalise(parsed),
        "call_count": len(entries),
        "retried": any(call["parse_outcome"] != llm.PARSE_PARSED for call in calls),
    }


def _claims_of(agent: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """The claims of an advocate block, normalised to a list of objects.

    The pipeline accepts an advocate's claims either inside an object under
    ``claims`` or as a bare array, and which of the two a model chose is
    recorded per call. Both shapes are presented; an advocate that answered in
    neither is presented as having produced no claims, which is what happened.
    """
    parsed = agent.get("parsed")
    if isinstance(parsed, Mapping):
        claims = parsed.get("claims")
    elif isinstance(parsed, list):
        claims = parsed
    else:
        claims = None
    if not isinstance(claims, list):
        return []
    return [claim for claim in claims if isinstance(claim, Mapping)]


# --------------------------------------------------------------------------
# The stance proof
# --------------------------------------------------------------------------
def _rendered_advocate_prompts() -> Dict[str, Any]:
    """Both advocate system prompts, rendered now, and where they differ.

    Rendered from the prompt files with the pipeline's own renderer rather than
    carried as text: a proof that quotes a prompt is a proof about whatever was
    quoted, and the prompt files are the thing that can change under it.

    ``assert_stance_only`` performs the containment check as well as returning
    the ranges, so reaching the end of this function already means every
    differing line falls inside the stance block.
    """
    rider, driver, region = pipeline_module.render_advocate_prompts()
    ranges = pipeline_module.assert_stance_only(rider, driver, region)
    return {
        "rider_lines": rider.splitlines(),
        "driver_lines": driver.splitlines(),
        # Half-open, 0-indexed, as ``differing_line_ranges`` reports them.
        "stance_region": [int(region[0]), int(region[1])],
        "differing_ranges": [[int(lo), int(hi)] for lo, hi in ranges],
    }


def _stance_proof(
    case_no: int,
    brief_digest: str,
    rider: Mapping[str, Any],
    driver: Mapping[str, Any],
    stored_ranges: Any,
    computed_ranges: List[List[int]],
    recorded: bool = True,
) -> Dict[str, Any]:
    """The three facts of the stance proof for one case, checked not assumed.

    Every fact is recomputed here and compared against what the run recorded,
    and a disagreement raises :class:`BuildError` naming the case. That is the
    whole reason the proof belongs to the build and not to the view: a proof
    view able to display a claim this repository does not back is worse than no
    proof view, because it looks like evidence and is not.

    ``recorded`` is False for a case that wrote no result file at all -- the four
    judge drafts abstained and nothing was cached -- so there is no recorded
    ``stance_differing_ranges`` to compare against. Item 3 is then reported as
    **not recorded** rather than as a comparison with an empty list, which would
    read as a recorded finding that the two renders differ nowhere.
    """
    rider_user = rider.get("user_sha256")
    driver_user = driver.get("user_sha256")
    rider_system = rider.get("system_sha256")
    driver_system = driver.get("system_sha256")

    # 1. Same evidence: both advocates' user prompt is the verified brief.
    for role, digest in (
        (transcript_module.ROLE_RIDER_ADVOCATE, rider_user),
        (transcript_module.ROLE_DRIVER_ADVOCATE, driver_user),
    ):
        if digest is None:
            raise BuildError(
                "case {0}: the {1}'s user prompt digest is not in the "
                "transcript, so same-evidence cannot be shown for this "
                "case".format(case_no, role)
            )
        if digest != brief_digest:
            raise BuildError(
                "case {0}: the {1} was handed user prompt {2}, which is not the "
                "brief this build verified ({3}). What they were handed is not "
                "what the page would claim they were handed.".format(
                    case_no, role, digest, brief_digest
                )
            )
    if rider_user != driver_user:
        raise BuildError(
            "case {0}: the two advocates were handed different user prompts "
            "(rider {1}, driver {2}), so the same-evidence claim is false for "
            "this case".format(case_no, rider_user, driver_user)
        )

    # 2. Different instructions: their system prompts are not identical.
    for role, digest in (
        (transcript_module.ROLE_RIDER_ADVOCATE, rider_system),
        (transcript_module.ROLE_DRIVER_ADVOCATE, driver_system),
    ):
        if digest is None:
            raise BuildError(
                "case {0}: the {1}'s system prompt digest is not in the "
                "transcript, so the stance-only claim cannot be shown for this "
                "case".format(case_no, role)
            )
    if rider_system == driver_system:
        raise BuildError(
            "case {0}: the two advocates were handed the same system prompt "
            "({1}), so nothing but the evidence distinguishes them and the "
            "stance-only claim is untestable for this case".format(
                case_no, rider_system
            )
        )

    # 3. Stance only: the difference is where the run said it was.
    if not recorded:
        stored: Optional[List[List[int]]] = None
    else:
        stored = (
            []
            if stored_ranges is None
            else [[int(lo), int(hi)] for lo, hi in stored_ranges]
        )
        if stored != computed_ranges:
            raise BuildError(
                "case {0}: the run recorded differing ranges {1} but the prompts "
                "this build renders differ on {2}. The proof would be a claim this "
                "repository no longer backs.".format(case_no, stored, computed_ranges)
            )

    return {
        "brief_sha256": brief_digest,
        "rider": {"system_sha256": rider_system, "user_sha256": rider_user},
        "driver": {"system_sha256": driver_system, "user_sha256": driver_user},
        "differing_ranges": computed_ranges,
        # ``None`` when the run recorded none -- a case with no result file --
        # which the page renders as "not recorded" rather than as an empty list.
        "recorded_differing_ranges": stored,
    }


# --------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------
def _policy_blocks(
    built_by_case: Mapping[int, Mapping[str, Any]],
    category_by_case: Mapping[int, str],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """The policy half of each brief, stored once per category.

    Policy text is identical across the cases of one category, so storing it
    once per category rather than twenty-nine times saves about a megabyte of
    the output for no loss of information. The saving is only sound if the
    blocks really are identical, so that is checked here and the build fails
    loudly rather than showing one case's policy under another case's name.

    The check is made on the block as the brief carries it, after the full
    brief's digest has already been verified against the run -- so a case is
    never admitted on the strength of a policy block that was not itself part of
    a verified brief.
    """
    blocks: Dict[str, Any] = {}
    digests: Dict[str, str] = {}
    for case_no in sorted(built_by_case):
        category = category_by_case[case_no]
        block = built_by_case[case_no]["policies"]
        canonical = money.dumps_canonical(block)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if category not in blocks:
            blocks[category] = _normalise(block)
            digests[category] = digest
            continue
        if digests[category] != digest:
            raise BuildError(
                "cases of category {0} were handed different policy blocks: case "
                "{1} does not match the block already stored for that category. "
                "Storing it once would show the wrong policy text.".format(
                    category, case_no
                )
            )
    return blocks, digests


def _expected_side(record: Mapping[str, Any]) -> Dict[str, Any]:
    """The answer key's own record for one case, in the shape the page wants.

    ``grade.expected_from_key`` is the public path to the four graded fields, so
    the expected side is built through it rather than by reading the raw keys
    here. ``difficulty``, ``governing_clauses`` and ``rationale`` are not part of
    the graded ruling and are not modelled by ``Ruling``, so they are taken from
    the same record directly. The viewer is a presentation layer beside
    ``eval/`` and this is the one place it reads the key's prose.
    """
    truth = record.get("ground_truth") or {}
    expected = grade.expected_from_key(record)
    return {
        "ruling": expected.ruling,
        "amount_sgd": grade.render_money(grade.money_or_none(expected.amount_sgd)),
        "driver_compensation_sgd": grade.render_money(
            grade.money_or_none(expected.driver_compensation_sgd)
        ),
        "referrals": [str(item) for item in expected.referrals],
        "difficulty": expected.difficulty,
        "governing_clauses": [str(item) for item in truth.get("governing_clauses", [])],
        "rationale": truth.get("rationale"),
    }


def _produced_side(
    score: Optional[grade.CaseScore],
    ruling: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """The run's own ruling for one case.

    Taken from the grader's parsed ruling where there is one, so the produced
    side the page shows is the same object the score was computed from.

    A page that is not graded against a key has no score at all, and the produced
    side is then read straight from the run's own ruling record. The run did
    produce a ruling and the page has to show it: there is no key here for it to
    agree or disagree with, and printing four nulls would hide a result the run
    actually reached.

    The fallback is used only where there is no score. A graded page whose ruling
    the grader could not parse keeps the grader's reading of it, because that is
    the reading the score was computed from.
    """
    if score is None and ruling is not None:
        return {
            "ruling": ruling.get("ruling"),
            "amount_sgd": grade.render_money(
                grade.money_or_none(ruling.get("amount_sgd"))
            ),
            "driver_compensation_sgd": grade.render_money(
                grade.money_or_none(ruling.get("driver_compensation_sgd"))
            ),
            "referrals": [str(item) for item in (ruling.get("referrals") or [])],
            "confidence": _normalise(ruling.get("confidence")),
            "explanation": ruling.get("explanation"),
        }
    produced = None if score is None else score.produced
    if produced is None:
        return {
            "ruling": None,
            "amount_sgd": "null",
            "driver_compensation_sgd": "null",
            "referrals": [],
            "confidence": None,
            "explanation": None,
        }
    return {
        "ruling": produced.ruling,
        "amount_sgd": grade.render_money(grade.money_or_none(produced.amount_sgd)),
        "driver_compensation_sgd": grade.render_money(
            grade.money_or_none(produced.driver_compensation_sgd)
        ),
        "referrals": [str(item) for item in produced.referrals],
        "confidence": _normalise(produced.confidence),
        "explanation": produced.explanation,
    }


def _grading_of(score: Optional[grade.CaseScore]) -> Optional[Dict[str, Any]]:
    """Field by field, what agreed and what did not, in the grader's own words.

    ``None`` when the page is not graded against a key: there is no four-field
    grading to report, and an empty one would read as a case that failed every
    field rather than as a case that was never scored.
    """
    if score is None:
        return None
    return {
        "exact": score.exact,
        "failed_fields": list(score.failed_fields),
        "fields": [
            {
                "field": outcome.field,
                "correct": outcome.correct,
                "detail": outcome.detail,
            }
            for outcome in score.outcomes
        ],
    }


def _tally(correct: int, total: int) -> str:
    """A count as ``n/of``, or ``n/a`` where there is nothing to divide by."""
    return "{0}/{1}".format(correct, total) if total else "n/a"


def _headline(
    report_produced: Optional[grade.GradeReport],
    report_all: Optional[grade.GradeReport],
    case_facts: Mapping[int, Mapping[str, Any]],
    failed_tokens: int = 0,
    failed_cases: int = 0,
    known_dirs: Sequence[Path] = (),
) -> Dict[str, Any]:
    """Every headline figure, computed from the run.

    Nothing here is typed in. The accuracy figures come from the grader over the
    same produced rulings the page shows, so the viewer and ``eval/grade.py``
    cannot disagree about what the run scored.

    **Two bases, and both are printed.** ``report_produced`` grades the cases
    that produced a ruling; ``report_all`` grades every case of the key, with a
    case that produced no ruling counted as a miss. The second is what the run
    did on its set and is the honest one to quote, and it is the one the single
    ``exact`` figure uses -- a figure that quietly drops the cases a run could
    not answer is the figure that flatters it. ``exact_bases`` carries both,
    labelled, which is what ``python3 -m eval.sealed_report`` prints.

    ``case_facts`` is every case in the run, refused ones included, so the
    figures describe the run rather than the subset this build could verify. A
    refusal is a fact about the viewer; folding it into the run's accuracy would
    be a fact about the viewer pretending to be a fact about the model.

    The discarded-claim total is the one figure the grader does not compute -- it
    is a property of the judge outputs, not of the verdict -- so it is summed
    from the run's own judge results, and the test recomputes it the same way.

    ``failed_tokens`` and ``failed_cases`` are the tokens spent on the cases
    that produced no ruling. They have no case file to be counted from, so they
    are added here from ``run.json``'s own failure total: a token total that
    left them out would report less than the run spent.
    """
    discarded_per_case: Dict[str, int] = {}
    for case_no in sorted(case_facts):
        discarded = case_facts[case_no].get("discarded_claims") or []
        discarded_per_case[str(case_no)] = len(discarded)

    seconds = [
        float(case_facts[case_no]["wall_seconds"])
        for case_no in sorted(case_facts)
        if case_facts[case_no].get("wall_seconds") is not None
    ]
    tokens = [
        int(case_facts[case_no]["tokens"]["total_tokens"])
        for case_no in sorted(case_facts)
        if case_facts[case_no].get("tokens")
    ]
    token_total = sum(tokens) + int(failed_tokens)
    token_cases = len(tokens) + int(failed_cases)

    def basis(report: grade.GradeReport, label: str) -> Dict[str, Any]:
        return {
            "label": label,
            "matched": report.exact_matches,
            "total": report.total,
            "display": _tally(report.exact_matches, report.total),
        }

    if report_all is None:
        exact: Optional[Dict[str, Any]] = None
        exact_bases: List[Dict[str, Any]] = []
        fields: Dict[str, Any] = {}
        two_field: Optional[Dict[str, Any]] = None
        escalation: Optional[Dict[str, Any]] = None
        cases_graded: Optional[int] = None
    else:
        fields = {}
        for name in grade.GRADED_FIELDS:
            correct, denominator = report_all.field_tally(name)
            fields[name] = {
                "matched": correct,
                "total": denominator,
                # ``grade._percent`` is private, and it is used deliberately: it
                # is the grader's own rounding rule, and the viewer's whole claim
                # about these numbers is that it cannot disagree with the grader
                # about them. Re-deriving the rounding here would be a second
                # rule.
                "display": "{0}/{1} = {2}".format(
                    correct,
                    denominator,
                    grade.render_percent(grade._percent(correct, denominator)),
                ),
            }
        # The same ``full`` rule ``eval/grade.py`` uses to decide whether the
        # corpus target may be printed beside a rate. ``TARGET_ESCALATION_RATE``
        # is a property of the 29-case corpus, so it is shown on the corpus's own
        # page and nowhere else.
        corpus_target = report_all.grades_full_corpus and (
            tuple(sorted(report_all.corpus_cases)) == grade.corpus_case_numbers()
        )
        calibration = report_all.calibration
        exact = basis(
            report_all,
            "over the {0} cases in the set, a case with no ruling counted as a "
            "miss".format(report_all.total),
        )
        # Both bases, always, and neither offered as the one to quote. Over the
        # cases that produced a ruling is what the system did where it answered;
        # over every case in the set is what it did on the set. A set whose
        # cases all produced a ruling prints the same figure twice, and that is
        # the honest reading of it: the two bases coincide, and the page says so
        # rather than choosing one for the reader.
        exact_bases = [exact]
        if report_produced is not None:
            exact_bases.insert(
                0,
                basis(
                    report_produced,
                    "over the {0} cases that produced a ruling".format(
                        report_produced.total
                    ),
                ),
            )
        cases_graded = report_all.total
        two_field = {
            "matched": report_all.two_field_matches,
            "total": report_all.total,
            "note": (
                "Reported as a contrast only, never as the result. A ruling "
                "counts only when all four fields agree."
            ),
        }
        escalation = {
            "expected": len(calibration.expected_escalations),
            "produced": len(calibration.produced_escalations),
            "true_positives": list(calibration.true_positives),
            "precision": {
                "matched": len(calibration.true_positives),
                "total": len(calibration.true_positives) + len(calibration.false_positives),
                "display": grade.render_ratio(calibration.precision),
            },
            "recall": {
                "matched": len(calibration.true_positives),
                "total": len(calibration.true_positives) + len(calibration.false_negatives),
                "display": grade.render_ratio(calibration.recall),
            },
            "over_escalations": list(calibration.over_escalations),
            "under_escalations": list(calibration.under_escalations),
            "rate_percent": grade.render_percent(calibration.rate),
            "target_percent": grade.render_percent(calibration.target_rate),
            "off_target": calibration.rate_off_target,
            # Whether the corpus target may be printed beside the rate at all.
            # False for every set that is not the 29-case corpus, which is what
            # stops a sealed set's rate being shown beside a target it is not
            # answerable to.
            "corpus_target": bool(corpus_target),
            "indeterminate_ruled_confidently": list(
                calibration.indeterminate_ruled_confidently
            ),
        }

    return {
        "cases_graded": cases_graded,
        # Present only when the advocates were replayed, and ``None`` otherwise.
        # It sits beside the figure it qualifies rather than in the footer: a
        # reader who reads only the cards must still learn that the number is the
        # judge's and not the pipeline's, and a reader of a run that replayed
        # nothing must not be shown a field that reads like a finding.
        "replay": (
            {
                "cases": len(report_all.replay.cases),
                "total": report_all.total,
                "sources": [
                    _source_directory(source, known_dirs) or "an unrecorded source"
                    for source in report_all.replay.sources
                ],
                "tokens": report_all.replay.tokens,
            }
            if report_all is not None and report_all.replay.any
            else None
        ),
        "exact": exact,
        "exact_bases": exact_bases,
        "two_field": two_field,
        "fields": fields,
        "escalation": escalation,
        "discarded_claims": {
            "total": sum(discarded_per_case.values()),
            "per_case": discarded_per_case,
        },
        "seconds": {
            "total": round(math.fsum(seconds), 1),
            "mean_per_case": round(math.fsum(seconds) / len(seconds), 1) if seconds else None,
            "cases": len(seconds),
        },
        "tokens": {
            "total": token_total,
            "mean_per_case": round(token_total / token_cases, 1) if token_cases else None,
            "cases": token_cases,
            "failed_cases": int(failed_cases),
            "failed_total": int(failed_tokens),
        },
    }


def _repository_relative(
    value: Any, known_dirs: Sequence[Path] = ()
) -> Optional[str]:
    """A path from the run, as this repository expresses it, or ``None``.

    The run records absolute paths from the machine that produced it. Only the
    part that is a fact about *this* repository may reach the page. A path from
    another checkout is a stranger's filesystem layout, and publishing it would
    both leak it and make the built page depend on where the build ran -- which
    is the one thing a committed artefact must not do, because it then cannot be
    reproduced from the code by anybody else.

    So: a path under the project root is relativised directly; a path that is
    not, but whose trailing components name a directory this repository has, is
    reported as this repository names it; anything else is dropped rather than
    published.

    ``known_dirs`` adds the directories this particular page is about -- a
    second set's own run directory, which the run's recorded paths may name from
    another checkout just as the corpus's are named. The corpus's run directory
    and the prompts directory are always recognised.

    This is not a nicety. The committed run was made in one checkout, and in
    that checkout its recorded prompts path sat under the project root and was
    relativised. In every other checkout it did not, and the absolute path was
    published instead -- so the committed page differed from a fresh build
    everywhere except the single directory it was built in, and a judge cloning
    the repository would have seen the artefact-versus-build test go red.
    """
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        pass
    known_roots = (RUN_DIR, pipeline_module.PROMPTS_DIR) + tuple(known_dirs)
    for known in known_roots:
        try:
            tail = Path(known).resolve().relative_to(PROJECT_ROOT).parts
        except ValueError:
            continue
        if len(path.parts) >= len(tail) and path.parts[-len(tail) :] == tail:
            return "/".join(tail)
    return None


def _replay_facts(raw_by_case: Mapping[int, Mapping[str, Any]]) -> grade.ReplayFacts:
    """The replay provenance the run's own case entries record.

    Read from the per-case entries rather than from ``run.json``, because
    ``run.json`` describes the last invocation and the entries describe the
    results -- which is the question the figures on this page are asking. A
    directory can hold results from more than one invocation, and only the
    entries say which of them reused another run's advocates.

    ``checked`` is True because every entry was read, so "nothing was replayed"
    is a finding rather than an absence.
    """
    cases: List[int] = []
    sources: List[str] = []
    tokens = 0
    for case_no in sorted(raw_by_case):
        record = raw_by_case[case_no].get("replay")
        if not isinstance(record, Mapping):
            continue
        cases.append(case_no)
        source = record.get("run_dir")
        if isinstance(source, str) and source and source not in sources:
            sources.append(source)
        tokens += int((record.get("tokens") or {}).get("total_tokens") or 0)
    return grade.ReplayFacts(
        checked=True,
        sources=tuple(sources),
        cases=tuple(cases),
        tokens=tokens,
    )


def _case_replay(
    record: Any, known_dirs: Sequence[Path] = ()
) -> Optional[Dict[str, Any]]:
    """One case's replay provenance, as the page shows it.

    ``None`` when this run called that case's advocates itself, so the case view
    can say which of the two happened rather than printing an empty block. The
    source path is relativised like every other path on this page: the page is
    committed, and a path from another checkout would both leak it and make the
    built artefact depend on where the build ran.
    """
    if not isinstance(record, Mapping):
        return None
    return {
        "run_directory": _source_directory(record.get("run_dir"), known_dirs),
        "git_commit": record.get("git_commit"),
        "advocate_calls": record.get("advocate_calls"),
        "tokens": record.get("tokens"),
    }


def _run_replay(
    record: Any,
    raw_by_case: Mapping[int, Mapping[str, Any]],
    known_dirs: Sequence[Path] = (),
) -> Optional[Dict[str, Any]]:
    """The run's own replay provenance, as the page's footer shows it.

    ``None`` when ``run.json`` records no replay, which is what a run that
    called every agent itself writes. The footer then says so in words rather
    than printing an empty field: a reader looking for the answer to "did this
    run ask its own agents" has to be able to find one either way.

    ``git_commit`` is the commit the source directory recorded, and a replay
    into that same directory makes it the commit of the run that *copied* the
    advocates rather than the one that made them. ``advocate_commits`` names the
    run that made them, read per case from the entries for the same reason
    ``replay_sources`` is: the entries describe the results, and ``run.json``
    describes the last invocation. Without it the footer's one commit would read
    as the advocates' provenance, which is the run that copied them.
    """
    if not isinstance(record, Mapping):
        return None
    made: List[str] = []
    for case_no in sorted(raw_by_case):
        case_replay = raw_by_case[case_no].get("replay")
        if not isinstance(case_replay, Mapping):
            continue
        commit = case_replay.get("git_commit")
        if isinstance(commit, str) and commit and commit not in made:
            made.append(commit)
    return {
        "run_directory": _source_directory(record.get("run_dir"), known_dirs),
        "git_commit": record.get("git_commit"),
        "advocate_commits": made,
        "model": record.get("model"),
        "replayed_cases": len(record.get("replayed_cases") or []),
        "refused_cases": len(record.get("refused_cases") or []),
        "tokens": (record.get("tokens") or {}).get("total_tokens"),
    }


def _source_directory(
    value: Any, known_dirs: Sequence[Path] = ()
) -> Optional[str]:
    """A replay source, as this repository can express it.

    Relativised when it is inside the checkout, named as such when it is not,
    and ``None`` when there is no path at all. The middle case matters: dropping
    a foreign path would leave the page saying the advocates were replayed
    without saying from where, which is half the fact.
    """
    relative = _repository_relative(value, known_dirs)
    if relative is not None:
        return relative
    if isinstance(value, str) and value:
        return "a run outside this repository"
    return None


def _invocation_cases(entry: Mapping[str, Any]) -> Dict[str, Any]:
    """One invocation's case counts, from whichever shape it recorded.

    The corpus and the second sets write ``cases`` as an object with
    ``completed``, ``failed`` and ``requested`` lists. The organisers' sample
    case writes it as a bare list of case numbers, which is what it has to say:
    one converted case, run on its own. Reading the object's keys off that list
    is an ``AttributeError``, which is how a page for that run used to die
    before it printed anything.

    For the bare list, the count of cases is the count asked for and neither of
    the other two is claimed -- the record does not carry the split, and
    inventing one would be a figure the run never wrote.
    """
    cases = entry.get("cases")
    if isinstance(cases, Mapping):
        return {
            "completed": len(cases.get("completed") or []),
            "failed": len(cases.get("failed") or []),
            "requested": len(cases.get("requested") or []),
        }
    if isinstance(cases, list):
        return {"completed": None, "failed": None, "requested": len(cases)}
    return {"completed": None, "failed": None, "requested": None}


def _provenance(
    run: Mapping[str, Any],
    invocations: Sequence[Mapping[str, Any]],
    run_dir: Path,
    raw_by_case: Mapping[int, Mapping[str, Any]],
    key_path: Optional[Path] = grade.ANSWER_KEY_PATH,
    known_dirs: Sequence[Path] = (),
) -> Dict[str, Any]:
    """Which run this page is showing, on the page and not in a footnote.

    ``raw_by_case`` is passed through to the footer's replay block, which reads
    the commit that made the advocates from the entries rather than from
    ``run.json``: a replay into the directory it reads from makes the two
    different, and the footer is the one place on the page that names a commit.

    ``key_path`` is the key **this page** was graded against, so a second set's
    footer shows its own key's digest rather than the corpus key's, and a page
    with no key at all -- the organisers' sample case -- shows none.

    Every path is relative to the project root, because the run records absolute
    paths and this repository is published before submission: an absolute path
    carries a username into the artifact, which is a small leak with no upside.
    ``_repository_relative`` is what makes that hold in every checkout rather
    than only in the one the run happened to be made in.
    """
    relative = lambda value: _repository_relative(value, known_dirs)  # noqa: E731

    history = []
    for entry in invocations:
        if not isinstance(entry, Mapping):
            continue
        counts = _invocation_cases(entry)
        history.append(
            {
                "started_at": entry.get("started_at"),
                "ended_at": entry.get("ended_at"),
                "git_commit": entry.get("git_commit"),
                "model": entry.get("model"),
                "stop_reason": entry.get("stop_reason"),
                "completed": counts["completed"],
                "failed": counts["failed"],
                "requested": counts["requested"],
                "python_version": entry.get("python_version"),
                "tokens_spent": (entry.get("tokens") or {}).get("spent_this_invocation"),
            }
        )

    return {
        # No ``or str(run_dir)`` fallback. That would publish an absolute path
        # whenever relativisation failed, which is the same leak in the same
        # field. The run directory is always inside the repository, so the
        # fallback was unreachable -- which is exactly why it would have gone
        # unnoticed until the day it was not.
        "run_directory": relative(str(run_dir)),
        "model": run.get("model"),
        "runtime_model": model_module.RUNTIME_MODEL,
        "model_provider": model_module.MODEL_PROVIDER,
        "model_region": model_module.MODEL_REGION,
        "git_commit": run.get("git_commit"),
        "working_tree_clean": run.get("working_tree_clean"),
        "prompts_directory": relative(run.get("prompts_dir")),
        "prompts_sha256": run.get("prompts_sha256"),
        "answer_key_sha256": (
            grade.answer_key_sha256(key_path) if key_path is not None else None
        ),
        "python_version": run.get("python_version"),
        "started_at": run.get("started_at"),
        "ended_at": run.get("ended_at"),
        "case_deadline_seconds": run.get("case_deadline_seconds"),
        "timeout_seconds": run.get("timeout_seconds"),
        "token_budget": run.get("token_budget"),
        "tokens": run.get("tokens"),
        "invocation_count": len(history),
        "invocations": history,
        # Present only when the run's advocates were replayed, and ``None``
        # otherwise, so "this run called every agent itself" is a fact the page
        # states rather than one a reader infers from an absent field. The footer
        # renders the negative case in words for that reason.
        "replay": _run_replay(run.get("replay"), raw_by_case, known_dirs),
    }


def transcript_cases(run_dir: Path = RUN_DIR) -> List[int]:
    """Every case number the run directory holds a transcript for, ascending.

    A case the judge could not rule on writes a transcript and no result: the
    four drafts abstained, so there is nothing to cache. The transcript is then
    the only evidence the case was run at all, and a page that listed the
    directory by its result files would drop it silently.
    """
    numbers: List[int] = []
    for path in sorted(Path(run_dir).glob("case-*.transcript.json")):
        match = _TRANSCRIPT_FILE_RE.match(path.name)
        if match is not None:
            numbers.append(int(match.group(1)))
    return sorted(numbers)


def cases_the_run_left_evidence_for(
    run_dir: Path = RUN_DIR, key_cases: Sequence[int] = ()
) -> List[int]:
    """The cases a page must account for, ascending.

    Three sources, unioned. Two of them are on disk: the cases with a result
    file, and the cases with only a transcript -- a case the judge could not
    rule on writes a transcript and no result, so its transcript is the only
    evidence it was run at all. The third is the answer key's own case list,
    which is the set the figures are computed over; a case the key names that
    left neither a result nor a transcript is a case the run never reached, and
    it is counted as a miss in the headline's all-cases basis rather than drawn,
    because there is nothing about it to show.
    """
    run_dir = Path(run_dir)
    on_disk = set(cached_cases(run_dir)) | set(transcript_cases(run_dir))
    return sorted(on_disk | (set(key_cases) & on_disk))


def _recorded_brief_digest(run_dir: Path, case_no: int) -> Optional[str]:
    """The brief digest a case's own record holds, or ``None``.

    A case with a result file records it there. A case the run left only a
    transcript for records it on the two advocates' transcript entries instead,
    and that is the same bytes: both advocates are handed the brief, so the
    digest on their entry is the brief they were handed. Reading it there is
    what lets such a case be admitted rather than refused for having no result.
    """
    result_path = Path(run_dir) / ("case-%05d.json" % case_no)
    if result_path.is_file():
        return _read_json(result_path).get("brief_sha256")
    transcript_path = Path(run_dir) / ("case-%05d.transcript.json" % case_no)
    if not transcript_path.is_file():
        return None
    record = _read_json(transcript_path)
    for entry in record.get("entries", []) or []:
        if not isinstance(entry, Mapping):
            continue
        if entry.get("role") == transcript_module.ROLE_RIDER_ADVOCATE:
            return entry.get("user_sha256")
    return None


def _rebuild_cached_cases(
    run_dir: Path,
    builder: Callable[[int], Mapping[str, Any]],
    numbers: Sequence[int],
) -> Tuple[
    Dict[int, Mapping[str, Any]], Dict[int, Mapping[str, Any]], List[Dict[str, Any]]
]:
    """Rebuild each cached case's brief, and say which ones the run agrees with.

    The one place the comparison is made. :func:`build_document` turns the answer
    into a page and raises when nothing is left to draw; :func:`run_has_moved_on`
    reads the same answer without building anything, so the two cannot disagree
    about a case.

    A case is refused when its rebuilt digest is not the digest its result
    recorded, and also when the brief cannot be rebuilt at all: "cannot build it"
    is not "it matches", which is the rule the runner applies to the same
    question. A case with no result file at all -- one whose judge drafts all
    abstained -- is checked against the digest its advocates' transcript entries
    recorded instead, which is the same brief by a different route.
    """
    refused: List[Dict[str, Any]] = []
    built_by_case: Dict[int, Mapping[str, Any]] = {}
    raw_by_case: Dict[int, Mapping[str, Any]] = {}
    for case_no in numbers:
        result_path = Path(run_dir) / ("case-%05d.json" % case_no)
        if result_path.is_file():
            raw_by_case[case_no] = _read_json(result_path)
        recorded = _recorded_brief_digest(run_dir, case_no)
        try:
            rebuilt = builder(case_no)
            rebuilt_digest = _brief_digest(rebuilt)
        except Exception as exc:  # noqa: BLE001 - an unbuildable brief is a refusal
            refused.append(
                {
                    "case_no": case_no,
                    "recorded_brief_sha256": recorded,
                    "rebuilt_brief_sha256": None,
                    "reason": "the brief could not be rebuilt: {0}: {1}".format(
                        type(exc).__name__, exc
                    ),
                }
            )
            continue
        if rebuilt_digest != recorded:
            refused.append(
                {
                    "case_no": case_no,
                    "recorded_brief_sha256": recorded,
                    "rebuilt_brief_sha256": rebuilt_digest,
                    "reason": (
                        "the brief this code builds is not the brief those agents "
                        "were handed, so the evidence on the page would be a "
                        "regenerated brief that merely resembles it."
                    ),
                }
            )
            continue
        built_by_case[case_no] = rebuilt
    return built_by_case, raw_by_case, refused


def cases_whose_briefs_match(
    run_dir: Optional[Path] = None, page: Optional[ViewerPage] = None
) -> List[int]:
    """The cached cases whose rebuilt brief is the brief their result recorded.

    Asked without building a page, and answered by the same comparison
    :func:`build_document` makes, so a caller reading this list and the build
    acting on it are reading one answer. The page decides which set's loader and
    which policy version the brief is rebuilt at; the corpus's is the default.
    """
    page = pages()["corpus"] if page is None else page
    run_dir = Path(page.run_dir if run_dir is None else run_dir)
    built_by_case, _, _ = _rebuild_cached_cases(
        run_dir, page.brief_builder, cached_cases(run_dir)
    )
    return sorted(built_by_case)


def run_has_moved_on(
    run_dir: Optional[Path] = None, page: Optional[ViewerPage] = None
) -> bool:
    """Whether **every** cached case's brief has moved on from this code.

    True only when the run holds at least one cached case and this code agrees
    with none of them -- the state in which the viewer refuses the whole run and
    :func:`build_document` raises, because a page drawn from it would show
    regenerated briefs that merely resemble the ones those agents were handed.
    One matching case makes it False: the page can be built, and that case can be
    shown.

    It is a question about the run rather than about the viewer, and it answers
    itself from the run's own result files, so a run made by this code reads
    False with nothing reset by hand.
    """
    page = pages()["corpus"] if page is None else page
    run_dir = Path(page.run_dir if run_dir is None else run_dir)
    if not cached_cases(run_dir):
        return False
    return not cases_whose_briefs_match(run_dir, page)


def _policy_version_mismatches(
    raw_by_case: Mapping[int, Mapping[str, Any]], page: ViewerPage
) -> List[str]:
    """Every case whose own record disagrees with the page's policy version.

    Read from the case file's ``configuration``, which the runner writes for a
    run made at a fixed version and omits for one made at the command line's
    default. Where it is recorded it is checked, and a disagreement stops the
    build: a page that briefed a case at version 1 while the run recorded
    version 2 would show evidence the agents were never handed. This is the
    check that makes briefing ``wild-v2`` at version 1 impossible rather than
    merely unlikely -- at version 1 twelve of its twenty cases are silently
    refused and the page still builds, which is the failure this exists to stop.
    """
    problems: List[str] = []
    for case_no in sorted(raw_by_case):
        configuration = raw_by_case[case_no].get("configuration")
        if not isinstance(configuration, Mapping):
            continue
        recorded = configuration.get("policy_version")
        if recorded is None:
            continue
        if int(recorded) != int(page.policy_version):
            problems.append(
                "case {0}: the run recorded policy version {1}, but this page "
                "briefs every case of {2} at version {3}".format(
                    case_no, recorded, page.name, page.policy_version
                )
            )
    return problems


def _stated_expectation(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    """The organisers' stated outcome for their own sample case, or ``None``.

    Read as it stands and labelled on the page as what it is: not part of any
    answer key, not merged into one, and not an input to any agent. It is shown
    beside the produced ruling and is never a grade.
    """
    if path is None or not Path(path).is_file():
        return None
    record = _read_json(path)
    return {
        "source_document": record.get("source_document"),
        "dispute_id": record.get("dispute_id"),
        "expected_outcome_as_stated": record.get("expected_outcome_as_stated"),
        "stated_reasons": [str(item) for item in record.get("stated_reasons", []) or []],
        "not_the_answer_key": record.get("not_the_answer_key"),
        "upheld_is_not_a_token_here": record.get("upheld_is_not_a_token_here"),
    }


def build_document(
    run_dir: Optional[Path] = None,
    brief_builder: Optional[Callable[[int], Mapping[str, Any]]] = None,
    key_path: Optional[Path] = None,
    page: Optional[ViewerPage] = None,
) -> Dict[str, Any]:
    """The whole data model of one page, as a plain dict.

    ``page`` names the set this page is about: its run directory, its loader,
    its policy version and its key. It defaults to the corpus, so a caller that
    names nothing gets the page the submission reports.

    ``brief_builder`` is injectable so a test can hand in a brief that does not
    match the recorded digest and watch the case be refused rather than shown.
    The default is the page's own -- ``build_brief_for_case`` over that set's
    loader at that set's policy version -- and there is no other way to change
    what is rebuilt. ``key_path`` is the same kind of override for the key; a
    page with no key at all (the organisers' sample case) passes ``None`` and is
    not graded.

    A case whose rebuilt brief does not match the digest its result recorded is
    refused: named, with both digests, and left out of the cases the viewer can
    open. The refusal is reported rather than swallowed, because a viewer that
    silently drops a case is indistinguishable from a run that never had one.
    """
    page = pages()["corpus"] if page is None else page
    run_dir = Path(page.run_dir if run_dir is None else run_dir)
    builder = page.brief_builder if brief_builder is None else brief_builder
    key_path = page.key_path if key_path is None else key_path
    known_dirs = (page.run_dir,)

    run = _read_json(run_dir / "run.json")
    invocations = _read_json(run_dir / "invocations.json")
    if not isinstance(invocations, list):
        raise BuildError("invocations.json is not a list")

    key_records: Dict[int, Mapping[str, Any]] = {}
    key: Optional[Dict[int, grade.Ruling]] = None
    if key_path is not None:
        for record in _read_json(key_path):
            key_records[int(record["case_no"])] = record
        key = grade.load_answer_key(key_path)

    numbers = cases_the_run_left_evidence_for(run_dir, key_records)
    if not numbers:
        raise BuildError("no cached case results under {0}".format(run_dir))

    built_by_case, raw_by_case, refused = _rebuild_cached_cases(
        run_dir, builder, numbers
    )

    mismatches = _policy_version_mismatches(raw_by_case, page)
    if mismatches:
        raise BuildError(
            "the run's own case records disagree with the policy version this "
            "page briefs at (version {0}):\n  {1}".format(
                page.policy_version, "\n  ".join(mismatches)
            )
        )

    if not built_by_case:
        raise BuildError(
            "every cached case was refused; the run and this code do not agree "
            "about what the agents were handed"
        )

    category_by_case = {
        case_no: built_by_case[case_no]["case"]["dispute"]["category"]
        for case_no in sorted(built_by_case)
    }
    policies, policy_digests = _policy_blocks(built_by_case, category_by_case)

    # The headline figures are computed over the whole run, not over the subset
    # the viewer can show: they are a measurement of the run, and a refusal is a
    # fact about the viewer. The refusal is reported beside them rather than
    # folded into them.
    produced = {
        case_no: raw_by_case[case_no]["ruling"]
        for case_no in sorted(raw_by_case)
        if "ruling" in raw_by_case[case_no]
    }
    # The replay facts travel into the report so the headline figures and the
    # page's own statement about them come from one place. A page that said the
    # advocates were replayed while the report it is graded by did not would be
    # two answers to one question.
    replay_facts = _replay_facts(raw_by_case)
    if key is None:
        report_produced: Optional[grade.GradeReport] = None
        report_all: Optional[grade.GradeReport] = None
        scores: Dict[int, grade.CaseScore] = {}
    else:
        report_all = grade.grade(produced, key, corpus=key, replay=replay_facts)
        report_produced = grade.grade(
            produced,
            {case_no: key[case_no] for case_no in produced if case_no in key},
            corpus=key,
            replay=replay_facts,
        )
        scores = {score.case_no: score for score in report_all.cases}

    # What the headline figures need per case, taken from the run's own result
    # files for every case the run holds -- refused ones included, so the
    # figures describe the run and not the subset this build could verify. A
    # case with no result file (its judge drafts all abstained) contributes no
    # facts here; its tokens are added from ``run.json``'s failure total below.
    case_facts = {
        case_no: {
            "discarded_claims": (
                ((raw_by_case.get(case_no) or {}).get("ruling") or {}).get(
                    "discarded_claims"
                )
                or []
            ),
            "wall_seconds": (raw_by_case.get(case_no) or {}).get("wall_seconds"),
            "tokens": (raw_by_case.get(case_no) or {}).get("tokens"),
        }
        for case_no in numbers
    }

    failures = {
        int(entry["case_no"]): entry
        for entry in (run.get("failures") or [])
        if isinstance(entry, Mapping) and "case_no" in entry
    }
    failed_tokens = int(((run.get("tokens") or {}).get("failed") or {}).get("total_tokens") or 0)
    failed_cases = len(failures)

    # The stance proof's shared half is rendered once, before any case: the
    # advocate template is the same for every case, so the two renders and the
    # ranges where they differ belong to the document, while each case carries
    # the digests proving *its* agents were the ones handed them. Verifying
    # against every case below is what stops the shared block from being a
    # claim about a template nobody checked against this run.
    stance_prompts = _rendered_advocate_prompts()
    computed_ranges = stance_prompts["differing_ranges"]

    cases: List[Dict[str, Any]] = []
    no_ruling: List[Dict[str, Any]] = []
    for case_no in sorted(built_by_case):
        built = built_by_case[case_no]
        result = raw_by_case.get(case_no)
        transcript = _read_json(run_dir / ("case-%05d.transcript.json" % case_no))
        rider_agent = _agent_block(transcript, transcript_module.ROLE_RIDER_ADVOCATE)
        driver_agent = _agent_block(transcript, transcript_module.ROLE_DRIVER_ADVOCATE)
        judge = _agent_block(transcript, transcript_module.ROLE_JUDGE)
        referee_result = referee_module.referee(
            built,
            _claims_of(rider_agent),
            _claims_of(driver_agent),
        )
        judge_output = (result or {}).get("ruling") or {}
        score = scores.get(case_no)
        expected = _expected_side(key_records[case_no]) if key_records else None
        # The digest the run recorded, or -- for a case that wrote no result --
        # the one its advocates' transcript entries hold, which is the same
        # brief by the other route the run records it on.
        brief_digest = (result or {}).get("brief_sha256") or _recorded_brief_digest(
            run_dir, case_no
        )
        recorded_ranges = (result or {}).get("stance_differing_ranges")
        # A case with no result file never recorded where the two renders
        # differ, so item 3 of the proof is reported as not recorded rather than
        # compared against an empty list, which would read as a recorded "no
        # difference" and is the opposite of what the run left.
        ranges_recorded = result is not None and "stance_differing_ranges" in result

        if result is None or "ruling" not in result:
            failure = failures.get(case_no) or {}
            no_ruling.append(
                {
                    "case_no": case_no,
                    "failure_kind": failure.get("failure_kind"),
                    "failed_agent": failure.get("failed_agent"),
                    "detail": failure.get("reason"),
                }
            )

        cases.append(
            {
                "case_no": case_no,
                "category": category_by_case[case_no],
                "difficulty": (expected or {}).get("difficulty"),
                "brief_sha256": brief_digest,
                "brief_rebuilt_sha256": _brief_digest(built),
                "has_ruling": result is not None and "ruling" in result,
                "dispute": _normalise(built["case"]["dispute"]),
                "evidence": _normalise(built["case"]["evidence"]),
                "advocates": {
                    transcript_module.ROLE_RIDER_ADVOCATE: _advocate_payload(rider_agent),
                    transcript_module.ROLE_DRIVER_ADVOCATE: _advocate_payload(
                        driver_agent
                    ),
                },
                "stance_proof": _stance_proof(
                    case_no,
                    brief_digest,
                    rider_agent,
                    driver_agent,
                    recorded_ranges,
                    computed_ranges,
                    recorded=ranges_recorded,
                ),
                "referee": _normalise(referee_result.as_dict()),
                "judge": {
                    "agent": judge,
                    "discarded_claims": _normalise(
                        judge_output.get("discarded_claims") or []
                    ),
                    "verdict": _produced_side(score, judge_output.get("ruling")),
                    "referrals": [
                        str(item)
                        for item in ((judge_output.get("ruling") or {}).get("referrals") or [])
                    ],
                },
                "expected": expected,
                "grading": _grading_of(score),
                # The judge's vote, read out of this case's own transcript. It is
                # how the ruling above was reached, so it travels beside the
                # judge rather than being recomputed from the ruling -- which
                # could not recover it, since a 2-of-4 split and a unanimous
                # panel can produce the same ruling.
                "vote": _vote_payload(transcript.get("vote")),
                # The precedents the judge was shown, read from the case's own
                # top-level field rather than from the vote's payload: the runner
                # writes it on the case file, and an empty list means the switch
                # was on and nothing matched. A case decided with the switch off
                # carries no key at all, and the two are different findings.
                "precedents_shown": (result or {}).get("precedents_shown"),
                "recorded_matched": (result or {}).get("matched"),
                # ``None`` when this run asked this case's advocates itself, so
                # the case view can say which of the two happened rather than
                # leaving a reader to infer it from a missing field.
                "replay": _case_replay((result or {}).get("replay"), known_dirs),
                "tokens": _normalise((result or {}).get("tokens")),
                "wall_seconds": (result or {}).get("wall_seconds"),
                "call_seconds": (result or {}).get("call_seconds"),
                "recorded_at": (result or {}).get("recorded_at"),
                "git_commit": (result or {}).get("git_commit"),
                "python_version": (result or {}).get("python_version"),
                "model": (result or {}).get("model"),
            }
        )

    document = {
        "schema_version": 1,
        "generator": "ui/build.py",
        "set": _set_block(page, len(cases), key_path),
        "default_case": _default_case(page, cases),
        "decision_note": model_module.DECISION_NOTE,
        "decision_note_link": page.link_to(model_module.DECISION_NOTE),
        # Only a case a note was written about gets a link, and only that case's
        # note. A miss with no note is a miss and is shown as one: it is not
        # called contested, and it does not link to a note about another case.
        "miss_notes": _miss_notes(page, cases),
        "provenance": _provenance(
            run, invocations, run_dir, raw_by_case, key_path, known_dirs
        ),
        "headline": _headline(
            report_produced,
            report_all,
            case_facts,
            failed_tokens,
            failed_cases,
            known_dirs,
        ),
        "policies": policies,
        "policy_sha256": policy_digests,
        "stance_prompts": stance_prompts,
        "cases": cases,
        # Cases the run asked and could not rule on. They are graded as misses
        # in the headline above, and named here with the run's own failure kind
        # and detail, because a figure that counts them and a page that never
        # mentions them is a page a reader cannot audit.
        "no_ruling_cases": no_ruling,
        "refused_cases": refused,
        "stated_expectation": _stated_expectation(page.stated_expectation_path),
    }
    # One normalisation at the end rather than one at each use. A Decimal can
    # arrive from the brief, from a transcript's parsed value, or from a run file
    # read with ``parse_float=Decimal``, and a single pass makes it impossible to
    # miss one and ship a page whose data block will not parse.
    return _normalise(document)


def _set_block(
    page: ViewerPage, case_count: int, key_path: Optional[Path]
) -> Dict[str, Any]:
    """What the page says about the set it is showing.

    The name, what the set is, and -- for a sealed set -- the tag its single run
    was made from and the caveat ``eval/development_sets.py`` already carries.
    No caveat text is written here: the registration owns those words, and a
    second copy would be a second place for them to drift.
    """
    return {
        "name": page.name,
        "summary": page.summary,
        "title": page.title,
        "brand": page.brand,
        "badge": page.badge,
        "report_tool": page.report_tool,
        "caveat": page.caveat,
        "freeze_tag": page.freeze_tag,
        "sealed": page.sealed,
        "policy_version": page.policy_version,
        "case_count": case_count,
        "has_key": page.has_key,
        "key_path": (
            _repository_relative(str(key_path)) if key_path is not None else None
        ),
        # The corpus page is the one at ``ui/dist/index.html``; every other page
        # and the index itself sit one directory down.
        "runs_index_link": "../" * page.depth + "runs/index.html",
    }


def _default_case(page: ViewerPage, cases: Sequence[Mapping[str, Any]]) -> Optional[int]:
    """The case the page opens on.

    The registration's own choice where it names one -- the corpus's
    demonstration case, the organisers' sample case -- and otherwise the first
    case that matched all four fields, which is a fact about the built document
    and not about the registration.
    """
    if not cases:
        return None
    if page.default_case is not None:
        for case in cases:
            if case["case_no"] == page.default_case:
                return page.default_case
    for case in cases:
        if (case.get("grading") or {}).get("exact"):
            return case["case_no"]
    return cases[0]["case_no"]


def _miss_notes(
    page: ViewerPage, cases: Sequence[Mapping[str, Any]]
) -> Dict[str, Dict[str, str]]:
    """The note written about each miss, and only about that miss.

    A note reaches a case by one of two routes: it is written about that case by
    number, or the set names one note for every miss it has. Both are the
    registration's own statement, and neither is inferred here.

    A miss with no note gets nothing at all. The sentence the page writes about
    it says it is a miss; it does not call the reading contested and it does not
    link a note written about a different case, because that would be a claim
    this repository does not make.
    """
    notes: Dict[str, Dict[str, str]] = {}
    for case in cases:
        grading = case.get("grading")
        if grading is None or grading.get("exact"):
            continue
        case_no = int(case["case_no"])
        note = page.miss_notes.get(case_no, page.miss_note_for_every_miss)
        if note is not None:
            notes[str(case_no)] = {"note": note, "link": page.link_to(note)}
    return notes


def _advocate_payload(agent: Mapping[str, Any]) -> Dict[str, Any]:
    """An advocate block with its claims lifted out of whatever shape it chose."""
    payload = dict(agent)
    payload["claims"] = _claims_of(agent)
    return payload


def _vote_payload(raw: Any) -> Optional[Dict[str, Any]]:
    """The judge's vote as the run recorded it, ready for the page.

    ``None`` when the run recorded no vote at all -- a single-draft run. The page
    then says so rather than drawing a panel of nothing.

    Every value here is the run's own: the drafts, their kinds, seeds and
    temperatures, and their proposals are copied out of the transcript's ``vote``
    block unchanged. The only thing derived is each draft's ``verdict``, and it
    is derived from the run's own two fields and nothing else -- a draft that
    produced no usable ruling abstained, one the run marked as agreeing agreed,
    and one that produced a usable ruling the run did not mark dissented. The
    count of agreeing drafts is derived the same way, so a reader can see the
    majority the run reported rather than recomputing a rounded fraction.
    """
    if not isinstance(raw, Mapping):
        return None
    drafts: List[Dict[str, Any]] = []
    for draft in raw.get("drafts") or []:
        if not isinstance(draft, Mapping):
            continue
        if not draft.get("valid"):
            verdict = "abstained"
        elif draft.get("agrees"):
            verdict = "agreed"
        else:
            verdict = "dissented"
        drafts.append(
            {
                "draft": draft.get("draft"),
                "kind": draft.get("kind"),
                "seed": draft.get("seed"),
                "temperature": draft.get("temperature"),
                "verdict": verdict,
                "abstention": draft.get("abstention"),
                "proposal": draft.get("proposal"),
            }
        )
    payload: Dict[str, Any] = {
        "votes": raw.get("votes"),
        "threshold": raw.get("threshold"),
        "valid": raw.get("valid"),
        "agreement": raw.get("agreement"),
        "agreeing": sum(1 for draft in drafts if draft["verdict"] == "agreed"),
        "outcome": raw.get("outcome"),
        "unanimous": raw.get("unanimous"),
        "drafts": drafts,
    }
    if raw.get("verification") is not None:
        # The verifier's findings ride on the vote's own record, and they are
        # carried here only when the run recorded them: a case decided with the
        # verifier off must not gain a key claiming the verifier read it. The
        # page draws its verifier panel exactly when this key is present, which
        # is why the key is added rather than always written as null.
        payload["verification"] = raw["verification"]
    return payload


# --------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------
_CSS = """
:root {
  --bg: #0e1116;
  --panel: #161c23;
  --panel-2: #1c242d;
  --line: #2b3641;
  --text: #e8eef5;
  --muted: #9dabb9;
  --accent: #79c0ff;
  --rider: #f0a35e;
  --driver: #62d2a2;
  --judge: #b9a2ff;
  --ok: #4ac26b;
  --warn: #d8a72a;
  --bad: #ff6b6b;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  padding-bottom: 74px;
}
a { color: var(--accent); }
h1, h2, h3, h4 { margin: 0 0 8px 0; line-height: 1.25; }
h1 { font-size: 20px; letter-spacing: 0.01em; }
h2 { font-size: 22px; margin-top: 4px; }
h3 { font-size: 16px; color: var(--text); margin-top: 22px; }
h4 { font-size: 14px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
p { margin: 8px 0; }
code, .mono { font-family: var(--mono); font-size: 12.5px; }

header.top {
  position: sticky; top: 0; z-index: 20;
  background: rgba(14,17,22,0.94);
  border-bottom: 1px solid var(--line);
  padding: 10px 20px;
  display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
}
header.top .brand { font-weight: 600; font-size: 15px; }
header.top .spacer { flex: 1; }
header.top .runs-link { font-size: 13px; color: var(--accent); text-decoration: none; }
header.top .runs-link:hover { text-decoration: underline; }
nav.views { display: flex; gap: 6px; }
main { padding: 20px; max-width: 1180px; margin: 0 auto; }

button {
  font: inherit; color: var(--text); background: var(--panel-2);
  border: 1px solid var(--line); border-radius: 6px; padding: 5px 11px; cursor: pointer;
}
button:hover { border-color: var(--accent); }
button.on { background: var(--accent); color: #08121c; border-color: var(--accent); font-weight: 600; }
button:disabled { opacity: 0.4; cursor: default; }
button:disabled:hover { border-color: var(--line); }

.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin: 16px 0 6px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 13px 15px; }
.card .label { color: var(--muted); font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.07em; }
.card .value { font-size: 25px; font-weight: 650; margin-top: 5px; font-variant-numeric: tabular-nums; }
.card .sub { color: var(--muted); font-size: 12.5px; margin-top: 4px; }
.card.wide { grid-column: span 2; }

table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th, td { text-align: left; padding: 6px 9px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.05em; }
tbody tr:hover { background: #1a222b; }
tr.clickable { cursor: pointer; }
tr.miss td { background: rgba(255,107,107,0.09); }
tr.miss:hover td { background: rgba(255,107,107,0.16); }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
td.case-no { font-weight: 650; font-variant-numeric: tabular-nums; }

.badge { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: 11.5px;
  border: 1px solid var(--line); color: var(--muted); white-space: nowrap; }
.badge.ok { color: var(--ok); border-color: rgba(74,194,107,0.5); }
.badge.miss { color: var(--bad); border-color: rgba(255,107,107,0.5); }
.badge.rider { color: var(--rider); border-color: rgba(240,163,94,0.5); }
.badge.driver { color: var(--driver); border-color: rgba(98,210,162,0.5); }
.badge.judge { color: var(--judge); border-color: rgba(185,162,255,0.5); }
.badge.complete { color: var(--ok); border-color: rgba(74,194,107,0.5); }
.badge.impaired { color: var(--warn); border-color: rgba(216,167,42,0.6); background: rgba(216,167,42,0.10); }
.badge.missing { color: var(--bad); border-color: rgba(255,107,107,0.6); background: rgba(255,107,107,0.10); }

.case-picker { display: flex; flex-wrap: wrap; gap: 5px; margin: 12px 0 16px; }
.case-picker button { padding: 3px 9px; font-size: 12.5px; font-variant-numeric: tabular-nums; }
.case-picker button.miss { border-color: rgba(255,107,107,0.45); color: #ffc9c9; }

.case-head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 4px; }
.case-head .title { font-size: 19px; font-weight: 650; }

.stepper { display: flex; gap: 6px; flex-wrap: wrap; margin: 14px 0; align-items: center; }
.stepper .step { font-size: 12.5px; }
.stepper .nav { margin-left: auto; display: flex; gap: 6px; }

section.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: 16px 18px; margin-top: 14px; }
section.panel + section.panel { margin-top: 14px; }

blockquote { margin: 10px 0; padding: 10px 14px; border-left: 3px solid var(--line);
  background: var(--panel-2); border-radius: 0 8px 8px 0; color: var(--text); }
blockquote .who { display: block; color: var(--muted); font-size: 12px; margin-bottom: 5px; }

.kv { display: grid; grid-template-columns: max-content 1fr; gap: 3px 16px; margin: 8px 0; font-size: 13.5px; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; }

dl.tree { display: grid; grid-template-columns: max-content 1fr; gap: 2px 14px; margin: 4px 0 4px 0; }
dl.tree > dt { color: var(--muted); font-family: var(--mono); font-size: 12px; padding-top: 1px; }
dl.tree > dd { margin: 0; }
ul.vals { margin: 0; padding-left: 16px; }
.null { color: #7b8794; font-style: italic; }
.bool { color: var(--accent); font-family: var(--mono); font-size: 12.5px; }
.scalar { font-family: var(--mono); font-size: 12.5px; }
.src { color: var(--muted); font-family: var(--mono); font-size: 11px; margin-left: 7px;
  border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; }
.empty { color: var(--muted); }

.artifact { border: 1px solid var(--line); border-left-width: 4px; border-radius: 8px;
  padding: 12px 14px; margin: 10px 0; background: var(--panel-2); }
.artifact.COMPLETE { border-left-color: var(--ok); }
.artifact.IMPAIRED { border-left-color: var(--warn); }
.artifact.MISSING { border-left-color: var(--bad); background: rgba(255,107,107,0.05); }
.artifact.flash { animation: flash 1.9s ease-out 1; }
@keyframes flash { 0% { background: rgba(121,192,255,0.30); } 100% { background: var(--panel-2); } }
.artifact .head { display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap; }
.artifact .id { font-family: var(--mono); font-weight: 650; font-size: 13px; }
.artifact .notes { color: var(--muted); font-size: 13px; margin: 7px 0 0 0; }
.artifact .issues { margin-top: 6px; display: flex; gap: 5px; flex-wrap: wrap; }

details { margin-top: 9px; }
details > summary { cursor: pointer; color: var(--muted); font-size: 12.5px; }
details[open] > summary { margin-bottom: 6px; }

.chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; align-items: center; }
.chips .chips-label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; margin-right: 3px; }
.chip { font-family: var(--mono); font-size: 11.5px; padding: 1px 7px; border-radius: 999px;
  background: #223040; border: 1px solid #33465a; color: #bcd8f5; }
.chip:hover { border-color: var(--accent); }
.chip.evidence { background: #1f2d24; border-color: #33543f; color: #b6e8c4; }
.chip.clause { background: #2b2537; border-color: #453a5c; color: #d6c8ff; }
.chip.unknown { background: rgba(255,107,107,0.12); border-color: rgba(255,107,107,0.5); color: #ffc9c9; }
.chip.issue { background: rgba(216,167,42,0.14); border-color: rgba(216,167,42,0.5); color: #f2d68a; }

.claim { border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; margin: 10px 0; background: var(--panel-2); }
.claim .claim-head { display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap; color: var(--muted); font-size: 12px; }
.claim .claim-no { font-family: var(--mono); color: var(--text); font-weight: 650; }
.claim .text { margin: 8px 0 0 0; }
.claim.discarded { border-color: rgba(255,107,107,0.4); background: rgba(255,107,107,0.06); }

.role { border-top: 3px solid var(--line); padding-top: 12px; }
.role.RIDER_ADVOCATE { border-top-color: var(--rider); }
.role.DRIVER_ADVOCATE { border-top-color: var(--driver); }
.role.JUDGE { border-top-color: var(--judge); }

.callbar { color: var(--muted); font-size: 12px; font-family: var(--mono); margin-top: 6px; }
.callbar .warn { color: var(--warn); }
pre.raw { background: #10151b; border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px;
  overflow-x: auto; font-family: var(--mono); font-size: 12px; white-space: pre-wrap; word-break: break-word; max-height: 340px; }

footer.prov { position: fixed; left: 0; right: 0; bottom: 0; z-index: 30;
  background: rgba(18,23,29,0.97); border-top: 1px solid var(--line);
  padding: 7px 20px; font-size: 11.5px; color: var(--muted); font-family: var(--mono);
  display: flex; flex-wrap: wrap; gap: 4px 18px; }
footer.prov b { color: var(--text); font-weight: 600; }

.modal { position: fixed; inset: 0; z-index: 50; background: rgba(5,8,11,0.72);
  display: flex; align-items: flex-start; justify-content: center; padding: 48px 20px; }
.modal .box { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
  max-width: 820px; width: 100%; max-height: 78vh; overflow: auto; padding: 18px 20px; }
.modal .box .head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.modal .box .head .id { font-family: var(--mono); font-weight: 650; font-size: 15px; color: var(--judge); }
.modal .box .close { margin-left: auto; }
.modal .rule { margin-top: 12px; white-space: pre-wrap; }

.miss-note { margin-top: 10px; padding: 11px 14px; border: 1px solid rgba(255,107,107,0.4);
  border-radius: 8px; background: rgba(255,107,107,0.06); font-size: 13.5px; }
.warnbox { margin-top: 12px; padding: 11px 14px; border: 1px solid rgba(216,167,42,0.5);
  border-radius: 8px; background: rgba(216,167,42,0.07); font-size: 13.5px; }
.lead { color: var(--muted); max-width: 78ch; }
.hint { color: var(--muted); font-size: 12.5px; margin-top: 10px; }

/* ---- the judge's vote ------------------------------------------------- */
/* A ruling one draft reached and a ruling four drafts agreed on look the same
   in the result object; this panel is what tells them apart. */
.vote-result { border: 1px solid var(--line); border-left-width: 4px; border-radius: 8px;
  padding: 11px 14px; margin: 10px 0; background: var(--panel-2); }
/* The class is the outcome string the run recorded, spelled out here once so
   the colour cannot drift away from the word. */
.vote-result.carried { border-left-color: var(--ok); }
.vote-result.carried_not_unanimous { border-left-color: var(--warn); }
.vote-result.escalated { border-left-color: var(--bad); }
.vote-result .headline { display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap; }
.vote-result .headline .what { font-weight: 600; }
.draft { border: 1px solid var(--line); border-left-width: 4px; border-radius: 8px;
  padding: 10px 13px; margin: 9px 0; background: var(--panel-2); }
.draft.agreed { border-left-color: var(--ok); }
.draft.dissented { border-left-color: var(--warn); }
.draft.abstained { border-left-color: #5d6b78; background: rgba(157,171,185,0.05); }
.draft .draft-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;
  color: var(--muted); font-size: 12px; }
.draft .draft-no { font-family: var(--mono); color: var(--text); font-weight: 650; }
.draft .notes { color: var(--muted); font-size: 12.5px; margin: 6px 0 0 0; }
.badge.sampled { color: var(--accent); border-color: rgba(121,192,255,0.5); }
.badge.swapped { color: var(--judge); border-color: rgba(185,162,255,0.5); }
.badge.agreed { color: var(--ok); border-color: rgba(74,194,107,0.5); }
.badge.dissented { color: var(--warn); border-color: rgba(216,167,42,0.6); background: rgba(216,167,42,0.10); }
.badge.abstained { color: var(--muted); }
.badge.contested { color: var(--warn); border-color: rgba(216,167,42,0.6); }
/* The verifier's findings and the precedents the judge was shown. Both panels
   are drawn only when the run recorded them, so a case decided with either
   switch off shows neither and carries no empty heading. */
.verifier-panel, .precedents-panel { margin-top: 18px; }
.draft.verification { background: var(--panel); }
.draft .verdicts { margin: 8px 0 0 0; padding-left: 18px; }
.draft .verdicts li { margin: 5px 0; }
.draft .verdicts li .src { margin-left: 8px; }
.badge.material { color: var(--bad); border-color: rgba(255,107,107,0.5); }
.badge.not_material { color: var(--muted); }
.vote-filter { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 10px 0; }
.vote-filter .count { color: var(--muted); font-size: 12.5px; }
td.vote-cell { white-space: nowrap; }
td.vote-cell .who { color: var(--muted); font-size: 12px; margin-left: 6px; }
tr.contested { background: rgba(216,167,42,0.06); }
tr.contested:hover { background: rgba(216,167,42,0.12); }

/* ---- stance view: the two advocates against the same record ------------ */
.stance-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 12px; }
@media (max-width: 940px) { .stance-grid { grid-template-columns: 1fr; } }
.stance-col { background: var(--panel); border: 1px solid var(--line); border-top-width: 3px;
  border-radius: 10px; padding: 14px 16px; }
.stance-col.RIDER_ADVOCATE { border-top-color: var(--rider); }
.stance-col.DRIVER_ADVOCATE { border-top-color: var(--driver); }
.stance-col > h3 { margin-top: 0; display: flex; align-items: baseline; gap: 8px; }
.stance-col > h3 .count { color: var(--muted); font-size: 13px; font-weight: 400; }
.record-row { display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap;
  border: 1px solid var(--line); border-left-width: 4px; border-radius: 8px;
  padding: 9px 12px; margin: 8px 0; background: var(--panel-2); }
.record-row.both { border-left-color: var(--accent); }
.record-row.one { border-left-color: var(--warn); }
.record-row .id { font-family: var(--mono); font-weight: 650; font-size: 13px; }
.record-row .sides { color: var(--muted); font-size: 12.5px; margin-top: 5px; flex-basis: 100%; }

/* ---- deep link -------------------------------------------------------- */
.linkbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
.linkbar input { flex: 1 1 320px; min-width: 220px; font-family: var(--mono); font-size: 12px;
  color: var(--text); background: var(--panel-2); border: 1px solid var(--line);
  border-radius: 6px; padding: 5px 9px; }
.linkbar .what { color: var(--muted); font-size: 12.5px; }

/* ---- keyboard help ---------------------------------------------------- */
dl.keys { display: grid; grid-template-columns: max-content 1fr; gap: 6px 14px; margin-top: 12px; }
dl.keys > dt { margin: 0; }
dl.keys > dd { margin: 0; color: var(--muted); }
kbd { font-family: var(--mono); font-size: 11.5px; background: var(--panel-2);
  border: 1px solid var(--line); border-bottom-width: 2px; border-radius: 5px;
  padding: 1px 6px; color: var(--text); white-space: nowrap; }

/* ---- the stance proof ------------------------------------------------- */
.proof { border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px;
  background: var(--panel); margin-top: 12px; }
.proof > h3 { margin-top: 0; }
.fact { border-left: 3px solid var(--ok); padding: 2px 0 2px 12px; margin: 12px 0; }
.fact .what { font-weight: 600; }
.fact .why { color: var(--muted); font-size: 12.5px; margin-top: 3px; max-width: 84ch; }
dl.digests { display: grid; grid-template-columns: max-content 1fr; gap: 5px 12px;
  margin: 9px 0 0 0; }
dl.digests > dt { color: var(--muted); font-size: 12px; white-space: nowrap; }
dl.digests > dd { margin: 0; }
/* The digest is shown whole. A digest you can only see part of is not
   evidence of equality, it is an assertion that there is equality. */
.digest { font-family: var(--mono); font-size: 11.5px; word-break: break-all;
  padding: 2px 7px; border-radius: 4px; border: 1px solid var(--line);
  background: var(--panel-2); color: var(--text); }
.digest.same { border-color: rgba(74,194,107,0.55); background: rgba(74,194,107,0.10); }
.digest.differ { border-color: rgba(240,163,94,0.55); background: rgba(240,163,94,0.09); }
.tag { display: inline-block; margin-left: 8px; font-size: 11px; padding: 0 6px;
  border-radius: 999px; border: 1px solid var(--line); color: var(--muted); white-space: nowrap; }
.tag.ok { color: var(--ok); border-color: rgba(74,194,107,0.5); }

.prompt-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
@media (max-width: 940px) { .prompt-grid { grid-template-columns: 1fr; } }
.prompt-col { border: 1px solid var(--line); border-radius: 8px; overflow: hidden;
  background: var(--panel-2); }
.prompt-col > h4 { margin: 0; padding: 7px 10px; border-bottom: 1px solid var(--line);
  background: var(--panel); text-transform: none; letter-spacing: 0; font-size: 13px; }
.plines { margin: 0; padding: 0; list-style: none; font-family: var(--mono);
  font-size: 11px; max-height: 480px; overflow: auto; }
.plines li { display: flex; gap: 8px; padding: 1px 8px 1px 5px; white-space: pre-wrap;
  word-break: break-word; border-left: 3px solid transparent; }
.plines li .n { color: #5d6b78; min-width: 28px; text-align: right; flex: none; }
.plines li.stance { background: rgba(121,192,255,0.05); border-left-color: rgba(121,192,255,0.35); }
.plines li.stance .n { color: var(--muted); }
.plines li.diff { background: rgba(216,167,42,0.15); border-left-color: var(--warn); }
.plines li.diff .t { color: #ffe6b0; }
.marker { display: flex; gap: 14px; flex-wrap: wrap; color: var(--muted);
  font-size: 12px; margin-top: 10px; }
.marker span { display: inline-flex; align-items: center; gap: 6px; }
.swatch { display: inline-block; width: 11px; height: 11px; border-radius: 2px;
  border: 1px solid var(--line); }
.swatch.stance { background: rgba(121,192,255,0.05); border-color: rgba(121,192,255,0.55); }
.swatch.diff { background: rgba(216,167,42,0.15); border-color: var(--warn); }

/* ---- projector -------------------------------------------------------- */
/* A room is not a laptop: everything scales, and the contrast goes up so a
   pale projector does not swallow the muted text. */
body.projector {
  --text: #f5f9fd;
  --muted: #c2cfdc;
  --line: #3d4a57;
  font-size: 19px; line-height: 1.62;
}
body.projector main { max-width: 1560px; padding: 24px; }
body.projector h1 { font-size: 27px; }
body.projector h2 { font-size: 31px; }
body.projector h3 { font-size: 22px; margin-top: 26px; }
body.projector h4 { font-size: 17px; }
body.projector p, body.projector .lead { max-width: 92ch; }
body.projector .card .value { font-size: 35px; }
body.projector .card .label { font-size: 13px; }
body.projector .card .sub { font-size: 15px; }
body.projector table { font-size: 17px; }
body.projector th, body.projector td { padding: 10px 14px; }
body.projector th { font-size: 13px; }
body.projector code, body.projector .mono, body.projector .scalar, body.projector .bool,
body.projector pre.raw { font-size: 15px; }
body.projector .chip { font-size: 14px; padding: 2px 9px; }
body.projector .badge { font-size: 13.5px; padding: 2px 9px; }
body.projector button { padding: 8px 15px; }
body.projector .stepper .step { font-size: 16px; }
body.projector .case-picker button { font-size: 15px; padding: 5px 11px; }
body.projector .artifact, body.projector .claim, body.projector .record-row { padding: 16px 18px; }
body.projector .artifact .id { font-size: 16px; }
body.projector footer.prov { font-size: 14px; padding: 11px 24px; gap: 6px 22px; }
body.projector .stance-grid { gap: 18px; }
body.projector .modal .box { max-width: 980px; }
/* A digest in 11px mono is unreadable from the back of a room, and the
   stance proof is precisely the thing a room is meant to be able to check. */
body.projector .digest { font-size: 14px; padding: 3px 10px; }
body.projector dl.digests > dt { font-size: 14px; }
body.projector .tag { font-size: 13px; }
body.projector .fact .why { font-size: 15px; max-width: 92ch; }
body.projector .plines { font-size: 14px; max-height: none; }
body.projector .plines li { padding: 2px 10px 2px 7px; }
body.projector .plines li .n { min-width: 34px; }
body.projector .prompt-col > h4 { font-size: 16px; padding: 9px 12px; }
body.projector .marker { font-size: 14px; }
"""

_JS = r"""
(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("tribunal-data").textContent);
  var BY_CASE = {};
  DATA.cases.forEach(function (c) { BY_CASE[c.case_no] = c; });

  // Every clause of every loaded policy, by id, built once. A clause id in a
  // claim may carry a limb -- POL-NS-06(i), POL-RD-06(c) -- so lookup strips the
  // limb and shows the clause the limb belongs to.
  var CLAUSES = {};
  Object.keys(DATA.policies).forEach(function (category) {
    var block = DATA.policies[category];
    ["general", "category"].forEach(function (which) {
      var policy = block[which] || {};
      (policy.clauses || []).forEach(function (clause) {
        if (!Object.prototype.hasOwnProperty.call(CLAUSES, clause.id)) {
          CLAUSES[clause.id] = {
            clause: clause,
            policy_id: policy.policy_id,
            category: category,
            which: which
          };
        }
      });
    });
  });

  // Whether this page is graded against an answer key at all. The organisers'
  // sample case is not: it has no entry in any key, so its last step shows
  // their stated expectation instead of a comparison with a key that does not
  // cover it.
  var HAS_KEY = !!(DATA.set && DATA.set.has_key);

  var STEPS = [
    { id: "dispute",  label: "1. The dispute" },
    { id: "evidence", label: "2. The evidence" },
    { id: "rider",    label: "3. Rider advocate" },
    { id: "driver",   label: "4. Driver advocate" },
    { id: "judge",    label: "5. Judge" },
    { id: "key",      label: HAS_KEY ? "6. Against the answer key" : "6. The stated expectation" }
  ];

  var state = {
    view: "overview",
    caseNo: DATA.default_case,
    step: 0,
    highlight: null,
    projector: false,
    help: false,
    // The vote filter is a reading aid, not part of the run, so it stays out
    // of the hash: a shared link opens the same run, and whoever follows it
    // decides for themselves whether to narrow the grid.
    contestedOnly: false
  };

  // ---- deep links ------------------------------------------------------
  // The address bar is the only place a link can live in a page opened from
  // file:// with no server behind it, so the whole view state is written
  // there. It reads back on load and on hashchange, which is what lets the
  // browser's own back button walk through a case at Demo Day.
  function parseHash(hash) {
    var out = {};
    String(hash || "").replace(/^#/, "").split("&").forEach(function (pair) {
      if (!pair) { return; }
      var bits = pair.split("=");
      out[decodeURIComponent(bits[0])] = decodeURIComponent(bits.slice(1).join("="));
    });
    return out;
  }
  function formatHash() {
    var parts = ["view=" + state.view];
    if (state.view !== "overview") {
      parts.push("case=" + state.caseNo);
      if (state.view === "case") { parts.push("step=" + (state.step + 1)); }
    }
    if (state.projector) { parts.push("projector=1"); }
    return "#" + parts.join("&");
  }
  function hashState(hash) {
    var parts = parseHash(hash);
    var caseNo = parseInt(parts["case"], 10);
    var step = parseInt(parts["step"], 10);
    var view = parts["view"];
    return {
      caseNo: Object.prototype.hasOwnProperty.call(BY_CASE, caseNo) ? caseNo : state.caseNo,
      view: (view === "case" || view === "stance") ? view : "overview",
      step: isNaN(step) ? 0 : Math.max(0, Math.min(STEPS.length - 1, step - 1)),
      projector: parts["projector"] === "1"
    };
  }
  function sameHashState(a, b) {
    return a.caseNo === b.caseNo && a.view === b.view && a.step === b.step &&
      a.projector === b.projector;
  }
  function applyHashState(next) {
    state.caseNo = next.caseNo;
    state.view = next.view;
    state.step = next.step;
    state.projector = next.projector;
    state.highlight = null;
  }

  // ---- DOM helpers -------------------------------------------------------
  function h(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        var value = attrs[key];
        if (value === null || value === undefined || value === false) { return; }
        if (key === "class") { node.className = value; }
        else if (key === "text") { node.textContent = String(value); }
        else if (key === "onclick") { node.addEventListener("click", value); }
        else if (key === "data") {
          Object.keys(value).forEach(function (name) {
            node.setAttribute("data-" + name, String(value[name]));
          });
        } else { node.setAttribute(key, value === true ? "" : String(value)); }
      });
    }
    add(node, children);
    return node;
  }
  function add(node, children) {
    if (children === null || children === undefined) { return; }
    if (Array.isArray(children)) {
      children.forEach(function (child) { add(node, child); });
      return;
    }
    if (children instanceof Node) { node.appendChild(children); return; }
    node.appendChild(document.createTextNode(String(children)));
  }
  // ``appendChild`` throws when it is handed anything that is not a node, and a
  // section that has nothing to draw answers with null rather than an empty box.
  // Every append of such a function's result goes through here, so a null child
  // is skipped instead of thrown on.
  function appendNode(node, child) {
    if (!(child instanceof Node)) { return; }
    node.appendChild(child);
  }
  function clear(node) { while (node.firstChild) { node.removeChild(node.firstChild); } }
  function byData(attr, value) {
    var all = document.querySelectorAll("[" + attr + "]");
    for (var i = 0; i < all.length; i += 1) {
      if (all[i].getAttribute(attr) === value) { return all[i]; }
    }
    return null;
  }
  function text(value) {
    if (value === null || value === undefined) { return "null"; }
    return String(value);
  }
  function paragraphs(value) {
    if (!value) { return h("p", { class: "null", text: "(none)" }); }
    return String(value).split(/\n\s*\n/).map(function (part) {
      return h("p", { text: part });
    });
  }
  function definitionList(pairs) {
    var dl = h("dl", { class: "kv" });
    pairs.forEach(function (pair) {
      if (pair[1] === null || pair[1] === undefined) { return; }
      dl.appendChild(h("dt", { text: pair[0] }));
      dl.appendChild(h("dd", null, pair[1]));
    });
    return dl;
  }

  // A value tree from the brief: objects become nested lists, arrays become
  // bullet lists, and a derived fact -- {value, evidence_id} -- carries the
  // artifact it was computed from, so a number on the page has a source.
  function renderValue(value) {
    if (value === null || value === undefined) { return h("span", { class: "null", text: "null" }); }
    if (Array.isArray(value)) {
      if (!value.length) { return h("span", { class: "empty", text: "[]" }); }
      return h("ul", { class: "vals" }, value.map(function (item) {
        return h("li", null, renderValue(item));
      }));
    }
    if (typeof value === "object") {
      var keys = Object.keys(value);
      if (keys.length === 2 && keys.indexOf("value") >= 0 && keys.indexOf("evidence_id") >= 0) {
        return h("span", null, [
          renderValue(value.value),
          h("span", { class: "src", text: value.evidence_id })
        ]);
      }
      var dl = h("dl", { class: "tree" });
      keys.forEach(function (key) {
        dl.appendChild(h("dt", { text: key }));
        dl.appendChild(h("dd", null, renderValue(value[key])));
      });
      return dl;
    }
    if (typeof value === "boolean") {
      return h("span", { class: "bool", text: value ? "true" : "false" });
    }
    return h("span", { class: "scalar", text: String(value) });
  }

  // ---- chips -------------------------------------------------------------
  function evidenceChip(caseDoc, evidenceId) {
    var known = (caseDoc.evidence || []).some(function (a) { return a.evidence_id === evidenceId; });
    if (!known) {
      return h("span", { class: "chip unknown", title: "not an artifact in this case's brief",
        text: evidenceId + " (not in this brief)" });
    }
    return h("button", { class: "chip evidence", data: { evidence: evidenceId },
      title: "open this artifact", text: evidenceId,
      onclick: function () { jumpToEvidence(evidenceId); } });
  }
  function clauseChip(clauseId) {
    var base = String(clauseId).replace(/\s*\([^)]*\)\s*$/, "");
    var known = Object.prototype.hasOwnProperty.call(CLAUSES, base);
    return h("button", {
      class: known ? "chip clause" : "chip unknown",
      title: known ? "show this clause's rule text" : "not a clause in the loaded policy",
      text: clauseId,
      onclick: function () { openClause(clauseId); }
    });
  }
  function chips(label, children) {
    return h("div", { class: "chips" }, [h("span", { class: "chips-label", text: label })].concat(children));
  }

  // ---- navigation --------------------------------------------------------
  // One function owns every rendering of the state, so a clicked row, a key
  // press and a pasted link all end up in exactly the same place and cannot
  // disagree about what is on screen.
  function refresh() {
    state.step = Math.max(0, Math.min(STEPS.length - 1, state.step));
    document.body.classList.toggle("projector", state.projector);
    document.getElementById("view-overview").hidden = state.view !== "overview";
    document.getElementById("view-case").hidden = state.view !== "case";
    document.getElementById("view-stance").hidden = state.view !== "stance";
    ["overview", "case", "stance"].forEach(function (name) {
      document.getElementById("nav-" + name).classList.toggle("on", state.view === name);
    });
    document.getElementById("toggle-projector").classList.toggle("on", state.projector);
    if (state.view === "case") { renderCase(); }
    if (state.view === "stance") { renderStance(); }
    syncLinkBar();
    syncHash();
  }
  function syncHash() {
    var next = formatHash();
    if (window.location.hash === next) { return; }
    // Writing the hash fires hashchange. That handler re-reads the hash and
    // stops when it already agrees with the state, rather than trusting a flag
    // that a slow event loop could leave set at the wrong moment.
    window.location.hash = next;
  }
  function syncLinkBar() {
    var input = document.getElementById("link-input");
    if (input) { input.value = formatHash(); }
  }
  function showView(name) {
    state.view = name;
    refresh();
  }
  function openCase(caseNo) {
    state.caseNo = caseNo;
    state.step = 0;
    state.highlight = null;
    state.view = "case";
    refresh();
    window.scrollTo(0, 0);
  }
  function openStance(caseNo) {
    if (caseNo !== undefined && caseNo !== null) { state.caseNo = caseNo; }
    state.highlight = null;
    state.view = "stance";
    refresh();
    window.scrollTo(0, 0);
  }
  function goToStep(index) {
    state.step = Math.max(0, Math.min(STEPS.length - 1, index));
    state.highlight = null;
    refresh();
  }
  // Next and previous case, in the order the run lists them, so a presenter
  // can walk the corpus without going back to the grid.
  function stepCase(delta) {
    var order = DATA.cases.map(function (c) { return c.case_no; });
    var at = order.indexOf(state.caseNo);
    if (at < 0) { return; }
    var next = order[Math.max(0, Math.min(order.length - 1, at + delta))];
    if (next === state.caseNo) { return; }
    state.caseNo = next;
    state.step = 0;
    state.highlight = null;
    refresh();
    window.scrollTo(0, 0);
  }
  function toggleProjector() {
    state.projector = !state.projector;
    refresh();
  }
  function jumpToEvidence(evidenceId) {
    state.step = 1;
    state.highlight = evidenceId;
    state.view = "case";
    refresh();
    var node = byData("data-artifact", evidenceId);
    if (node && node.scrollIntoView) { node.scrollIntoView({ block: "center" }); }
  }
  function openClause(rawId) {
    var base = String(rawId).replace(/\s*\([^)]*\)\s*$/, "");
    var entry = CLAUSES[base];
    var box = h("div", { class: "box" });
    box.appendChild(h("div", { class: "head" }, [
      h("span", { class: "id", text: rawId }),
      entry ? h("span", { class: "badge", text: entry.policy_id + " - " + entry.which }) : null,
      h("button", { class: "close", text: "close", onclick: closeModal })
    ]));
    if (!entry) {
      box.appendChild(h("p", { class: "miss-note", text:
        "No clause with this id is in the policy the brief carried. The claim cites a clause the agents were not given." }));
    } else {
      box.appendChild(h("h3", { text: entry.clause.title || entry.clause.id }));
      box.appendChild(h("p", { class: "hint", text: "rule text, as the agents received it" }));
      box.appendChild(h("div", { class: "rule", text: entry.clause.rule }));
    }
    var overlay = h("div", { class: "modal", id: "clause-modal", onclick: function (event) {
      if (event.target === overlay) { closeModal(); }
    } }, box);
    document.body.appendChild(overlay);
  }
  function closeModal() {
    var modal = document.getElementById("clause-modal");
    if (modal) { modal.parentNode.removeChild(modal); }
  }

  // ---- View 1: overview --------------------------------------------------
  function headlineCards() {
    var hl = DATA.headline;
    var esc = hl.escalation;
    var cards = h("div", { class: "cards" });

    // The four-field figure, on both bases where there are two. Over the cases
    // that produced a ruling is what the system did where it answered; over
    // every case in the set is what it did on the set. Both are printed and
    // neither is offered as the one to quote, because a figure that quietly
    // drops the cases a run could not answer is the figure that flatters it.
    var exactCard = h("div", { class: "card wide" }, [
      h("div", { class: "label", text: "Four-field exact match" })
    ]);
    if (hl.exact) {
      exactCard.appendChild(h("div", { class: "value", text: hl.exact.display }));
      (hl.exact_bases || []).forEach(function (basis) {
        exactCard.appendChild(h("div", { class: "sub", text: basis.display + " " + basis.label }));
      });
      exactCard.appendChild(h("div", { class: "sub", text:
        "A ruling counts only when ruling, amount_sgd, driver_compensation_sgd and referrals all agree with the key." }));
    } else {
      exactCard.appendChild(h("div", { class: "value", text: "not graded" }));
      exactCard.appendChild(h("div", { class: "sub", text:
        "This run is not graded against an answer key, so no accuracy is claimed for it." }));
    }
    cards.appendChild(exactCard);

    cards.appendChild(h("div", { class: "card" }, [
      h("div", { class: "label", text: "Discarded claims, all judges" }),
      h("div", { class: "value", text: String(hl.discarded_claims.total) }),
      h("div", { class: "sub", text: "Claims the judges threw out for a citation defect, across all " + DATA.cases.length + " cases." })
    ]));
    cards.appendChild(h("div", { class: "card" }, [
      h("div", { class: "label", text: "Mean seconds per case" }),
      h("div", { class: "value", text: text(hl.seconds.mean_per_case) + " s" }),
      h("div", { class: "sub", text: hl.seconds.total + " s over " + hl.seconds.cases + " cases." })
    ]));
    cards.appendChild(h("div", { class: "card" }, [
      h("div", { class: "label", text: "Mean tokens per case" }),
      h("div", { class: "value", text: text(hl.tokens.mean_per_case) }),
      h("div", { class: "sub", text: hl.tokens.total.toLocaleString() + " tokens over " + hl.tokens.cases + " cases" +
        (hl.tokens.failed_cases
          ? ", including " + hl.tokens.failed_total.toLocaleString() + " spent on the " + hl.tokens.failed_cases +
            " case(s) that produced no ruling."
          : ".") })
    ]));
    if (esc) {
      cards.appendChild(h("div", { class: "card" }, [
        h("div", { class: "label", text: "Escalation recall" }),
        h("div", { class: "value", text: esc.recall.display }),
        h("div", { class: "sub", text: esc.recall.matched + " of " + esc.recall.total + " cases the key escalates." })
      ]));
      cards.appendChild(h("div", { class: "card" }, [
        h("div", { class: "label", text: "Escalation precision" }),
        h("div", { class: "value", text: esc.precision.display }),
        h("div", { class: "sub", text: esc.precision.matched + " of " + esc.precision.total + " cases the run escalated." })
      ]));
      cards.appendChild(h("div", { class: "card" }, [
        h("div", { class: "label", text: "Over-escalations" }),
        h("div", { class: "value", text: String(esc.over_escalations.length) }),
        h("div", { class: "sub", text: esc.over_escalations.length ? "case " + esc.over_escalations.join(", ") : "none" })
      ]));
      cards.appendChild(h("div", { class: "card" }, [
        h("div", { class: "label", text: "Under-escalations" }),
        h("div", { class: "value", text: String(esc.under_escalations.length) }),
        h("div", { class: "sub", text: esc.under_escalations.length ? "case " + esc.under_escalations.join(", ") : "none" })
      ]));
    }
    return cards;
  }

  function fieldTable() {
    var hl = DATA.headline;
    var body = h("tbody");
    ["ruling", "amount_sgd", "driver_compensation_sgd", "referrals"].forEach(function (name) {
      var cell = hl.fields[name];
      body.appendChild(h("tr", null, [
        h("td", null, h("code", { text: name })),
        h("td", { class: "num", text: cell.display })
      ]));
    });
    return h("table", null, [
      h("thead", null, h("tr", null, [h("th", { text: "Graded field" }), h("th", { text: "Agreed with the key" })])),
      body
    ]);
  }

  function caseGridTable(rows) {
    var body = h("tbody");
    rows.forEach(function (c) {
      // Three states, not two. A case can be graded and agree, graded and miss,
      // or not graded at all -- the organisers' sample case is in no key, so
      // there is nothing for it to miss. It is drawn plainly rather than as a
      // miss, because calling it one would be a claim about a key it is not in.
      var graded = !!(c.grading && c.grading.exact);
      var row = h("tr", {
        class: "clickable" + (c.grading && !graded ? " miss" : "") +
          (isContested(c) ? " contested" : ""),
        title: "open case " + c.case_no,
        onclick: function () { openCase(c.case_no); }
      });
      row.appendChild(h("td", { class: "case-no", text: String(c.case_no) }));
      row.appendChild(h("td", { text: c.category }));
      row.appendChild(h("td", { text: text(c.difficulty) }));
      // A case the run could not rule on produced nothing. Its result cell says
      // so in words: a blank there reads as a ruling of null, and a null ruling
      // is a real token this system emits and a different thing entirely.
      row.appendChild(h("td", { class: c.has_ruling ? "" : "null",
        text: c.has_ruling ? text(c.judge.verdict.ruling) : "no ruling" }));
      row.appendChild(h("td", { class: c.expected ? "" : "null",
        text: c.expected ? text(c.expected.ruling) : "not graded" }));
      // The vote column is the run's own vote_agreement, shown beside the
      // result rather than instead of it: a case can be a four-field match and
      // still be one the drafts only just agreed on.
      row.appendChild(h("td", { class: "vote-cell" }, c.vote ? [
        h("span", { text: agreementLabel(c.vote.agreeing, c.vote.votes) }),
        c.vote.unanimous ? null : h("span", { class: "badge contested " + text(c.vote.outcome),
          text: outcomeLabel(c.vote.outcome) })
      ] : h("span", { class: "null", text: "no vote" })));
      row.appendChild(h("td", null, h("span", {
        class: graded ? "badge ok" : (c.grading ? "badge miss" : "badge"),
        text: graded ? "match" : (c.grading ? "MISS" : "not graded")
      })));
      body.appendChild(row);
    });
    return h("table", null, [
      h("thead", null, h("tr", null, [
        h("th", { text: "#" }), h("th", { text: "Category" }), h("th", { text: "Difficulty" }),
        h("th", { text: "Produced" }), h("th", { text: "Expected" }), h("th", { text: "Vote" }),
        h("th", { text: "Result" })
      ])),
      body
    ]);
  }

  // The whole grid, with a filter for the cases the drafts did not agree on.
  // The filter is view state and stays out of the hash: a link should open the
  // same run, and the filter is a reading aid on top of it.
  function caseGrid() {
    var holder = h("div", { class: "grid-holder" });
    var count = h("span", { class: "count" });
    function paint() {
      var contested = contestedCases();
      var rows = state.contestedOnly ? contested : DATA.cases;
      clear(holder);
      holder.appendChild(caseGridTable(rows));
      count.textContent = state.contestedOnly
        ? "showing the " + contested.length + " case" + (contested.length === 1 ? "" : "s") +
          " the drafts did not agree on, of " + DATA.cases.length
        : "showing all " + DATA.cases.length + " cases; " + contested.length +
          " of them were not unanimous";
    }
    var toggle = h("button", {
      text: "Contested only",
      onclick: function () {
        state.contestedOnly = !state.contestedOnly;
        toggle.classList.toggle("on", state.contestedOnly);
        paint();
      }
    });
    toggle.classList.toggle("on", state.contestedOnly);
    paint();
    return h("div", { class: "grid-wrap" }, [
      h("div", { class: "vote-filter" }, [toggle, count]),
      holder
    ]);
  }

  function refusedBlock() {
    if (!DATA.refused_cases.length) { return null; }
    var box = h("div", { class: "warnbox" });
    box.appendChild(h("b", { text: "Cases refused by this build" }));
    box.appendChild(h("p", { text:
      "A case is refused when the brief this code builds does not match the digest the result recorded. " +
      "Its evidence would then be a regenerated brief that merely resembles what the agents received, so it is not shown." }));
    var list = h("ul");
    DATA.refused_cases.forEach(function (entry) {
      list.appendChild(h("li", null, [
        h("b", { text: "case " + entry.case_no + " - " }),
        entry.reason + " ",
        h("code", { text: "recorded " + text(entry.recorded_brief_sha256) + ", rebuilt " + text(entry.rebuilt_brief_sha256) })
      ]));
    });
    box.appendChild(list);
    return box;
  }

  // The set this page is about: its name, and -- for a sealed set -- the tag its
  // single run was made from and the caveat the registration already carries.
  // The caveat is not written here; it comes out of the data block, so this page
  // and eval/development_sets.py cannot drift apart about what the set is.
  function setBlock() {
    var s = DATA.set || {};
    var box = h("div", { class: "set-block" });
    box.appendChild(h("h2", { class: "set-name" }, [
      h("span", { text: s.name }),
      s.sealed ? h("span", { class: "badge", text: "sealed set, run once" }) : null,
      s.freeze_tag ? h("span", { class: "badge", text: s.freeze_tag }) : null
    ]));
    if (s.summary) { box.appendChild(h("p", { class: "lead", text: s.summary })); }
    if (s.caveat) { box.appendChild(h("p", { class: "lead caveat", text: s.caveat })); }
    return box;
  }

  // What the page is a figure of. A page with no key has no accuracy to report,
  // and saying so is the whole of what it may claim.
  function headlineLead() {
    if (!HAS_KEY) {
      return "This case is not graded: it is not in any answer key. Everything here is computed from the run " +
        DATA.provenance.run_directory + ", and the run's own ruling is shown beside the organisers' stated " +
        "expectation, which is not an answer.";
    }
    return "Every figure here is computed from the run " + DATA.provenance.run_directory +
      " and the same grading code that produces " + text(DATA.set.report_tool) +
      ". Nothing on this page is typed in.";
  }

  function renderOverview() {
    var root = document.getElementById("view-overview");
    clear(root);
    root.appendChild(setBlock());
    root.appendChild(h("h2", { text: "The run, at a glance" }));
    root.appendChild(h("p", { class: "lead", text: headlineLead() }));
    if (DATA.headline.replay) {
      root.appendChild(h("p", { class: "lead", text:
        "The advocates' outputs for " + DATA.headline.replay.cases + " of " + DATA.headline.replay.total +
        " cases were replayed from " + DATA.headline.replay.sources.join(", ") +
        " and not regenerated here: only the judge was called for those cases, so every figure on this page is the " +
        "judge's behaviour on fixed inputs rather than a measurement of the whole pipeline. Those calls cost " +
        DATA.headline.replay.tokens.toLocaleString() + " tokens, billed to the run that made them." }));
    }
    root.appendChild(headlineCards());
    if (HAS_KEY) {
      root.appendChild(h("h3", { text: "Per-field accuracy" }));
      root.appendChild(h("p", { class: "lead", text:
        "The per-field figures are there so a reader can see which field a model actually fails on; they are not alternative scores." }));
      root.appendChild(fieldTable());
      root.appendChild(h("h3", { text: "Escalation" }));
      root.appendChild(escalationTable());
    }
    root.appendChild(voteSummary());
    root.appendChild(h("h3", { text: "All " + DATA.cases.length + " cases" }));
    root.appendChild(h("p", { class: "lead", text: "Click any row to open the case stepped through in order." }));
    root.appendChild(caseGrid());
    appendNode(root, noRulingBlock());
    appendNode(root, missNote());
    var refused = refusedBlock();
    if (refused) { root.appendChild(refused); }
  }

  // The cases the run asked and could not rule on. They are counted as misses
  // in the figures above, and listed here with the run's own failure kind, so a
  // reader can audit the count rather than take it. It is a separate block from
  // the refused one: a refusal is this build declining to draw a case whose
  // brief it cannot verify, and a no-ruling case is the run's own result.
  function noRulingBlock() {
    var rows = DATA.no_ruling_cases || [];
    if (!rows.length) { return null; }
    var box = h("div", { class: "warnbox" });
    box.appendChild(h("b", { text: "Cases the run could not rule on" }));
    box.appendChild(h("p", { text:
      "These cases were asked and produced no ruling: every judge draft abstained, so no result was written for " +
      "them. They are counted as misses in the figures above -- a case that produced nothing is not a case that " +
      "agreed -- and each is listed here with the run's own failure kind, so the count can be audited." }));
    var list = h("ul");
    rows.forEach(function (entry) {
      list.appendChild(h("li", null, [
        h("b", { text: "case " + entry.case_no + " - " }),
        h("code", { text: text(entry.failure_kind) }),
        entry.failed_agent ? " (" + text(entry.failed_agent) + ")" : "",
        entry.detail ? h("div", { class: "hint", text: text(entry.detail) }) : null
      ]));
    });
    box.appendChild(list);
    return box;
  }

  function escalationTable() {
    var esc = DATA.headline.escalation;
    if (!esc) {
      return h("p", { class: "null", text: "No escalation figures: this run is not graded against a key." });
    }
    var rows = [
      h("tr", null, [h("td", { text: "Expected escalations" }), h("td", { class: "num", text: String(esc.expected) })]),
      h("tr", null, [h("td", { text: "Produced escalations" }), h("td", { class: "num", text: String(esc.produced) })]),
      h("tr", null, [h("td", { text: "Escalation rate" }), h("td", { class: "num", text: esc.rate_percent })])
    ];
    // The corpus target is a property of the 29-case corpus, and it is shown
    // only on the corpus's own page. A sealed set's rate printed beside it
    // would invite a comparison the set is not answerable to.
    if (esc.corpus_target) {
      rows.push(h("tr", null, [h("td", { text: "Corpus target" }), h("td", { class: "num",
        text: esc.target_percent + (esc.off_target ? " (off target)" : " (on target)") })]));
    }
    rows.push(h("tr", null, [h("td", { text: "INDETERMINATE cases ruled confidently" }), h("td", { class: "num",
      text: esc.indeterminate_ruled_confidently.length ? esc.indeterminate_ruled_confidently.join(", ") : "none" })]));
    return h("table", null, [
      h("thead", null, h("tr", null, [h("th", { text: "" }), h("th", { text: "" })])),
      h("tbody", null, rows)
    ]);
  }

  // What the page says about one miss. It is written once, and used by both the
  // overview's block and the last step of the case view, so the two cannot say
  // different things about the same case.
  //
  // The link is drawn only where a note about *this* case exists. Otherwise the
  // case is a miss and nothing more: calling it a contested reading, or pointing
  // at a note written about another case, would be a claim this repository does
  // not make.
  function missLine(caseDoc) {
    var note = (DATA.miss_notes || {})[String(caseDoc.case_no)];
    var line = h("div", null, [
      h("b", { text: "Case " + caseDoc.case_no + " is a miss, and it is shown as one. " }),
      "It failed on " + caseDoc.grading.failed_fields.join(", ") + ". "
    ]);
    if (note) {
      line.appendChild(h("a", { href: note.link, text: note.note }));
      line.appendChild(" records why this is a contested reading rather than a defect, and why the answer key is not changed for it.");
    } else {
      line.appendChild("No note is written about this case, so it is shown as a miss and is not called a contested reading.");
    }
    return line;
  }

  function missNote() {
    var misses = DATA.cases.filter(function (c) { return c.grading && !c.grading.exact; });
    if (!misses.length) { return null; }
    var box = h("div", { class: "miss-note" });
    misses.forEach(function (c) { box.appendChild(missLine(c)); });
    return box;
  }

  // ---- the judge's vote --------------------------------------------------
  // Four drafts can reach one ruling, or three can outvote a fourth, or the
  // drafts can split so evenly that nothing carries. The result object looks
  // the same in all three cases, so these functions are the only place on the
  // page that says which one happened -- and they say it from the run's own
  // vote record, never from a re-derivation of the vote.
  function isContested(c) { return !!(c.vote && c.vote.unanimous === false); }

  function contestedCases() { return DATA.cases.filter(isContested); }

  var VOTE_OUTCOME_LABEL = {
    carried: "carried unanimously",
    carried_not_unanimous: "carried, not unanimous",
    escalated: "no majority, escalated"
  };
  var VOTE_OUTCOME_TEXT = {
    carried: "Every draft proposed the same four graded fields, so the ruling is the one they agreed on.",
    carried_not_unanimous: "One proposal reached the threshold and the others did not, so the ruling is the " +
      "proposal that carried rather than the one a single draft preferred.",
    escalated: "No proposal reached the threshold. Because the judge's own drafts disagreed, the case is " +
      "escalated with no amount set, instead of the code choosing one of the proposals for it."
  };

  // ---- how a value is written --------------------------------------------
  // Money is shown with two decimals here, at the moment it reaches the page,
  // and nowhere else. The document keeps the literal the run recorded -- the
  // tests pin every money value in the data as a string -- so the one rounding
  // rule lives in one place and never touches the data. ``"null"`` is what the
  // grader writes for an amount that was never set, and a reader should see
  // ``none``. Anything that is not a number at all is shown as it came, because
  // inventing a figure for it would be worse than showing the one that is
  // there.
  function money(value) {
    if (value === null || value === undefined) { return "none"; }
    var raw = String(value);
    if (raw === "null") { return "none"; }
    if (raw.trim() === "" || !isFinite(Number(raw))) { return raw; }
    return Number(raw).toFixed(2);
  }

  // The run's own tokens stay as class names -- the stylesheet colours the vote
  // outcomes and the draft kinds by those names -- so these maps only say what
  // a reader is shown in place of the token.
  var DRAFT_KIND_LABEL = {
    sampled: "sampled",
    position_swapped: "position-swapped"
  };
  function draftKindLabel(kind) {
    return DRAFT_KIND_LABEL[kind] || text(kind);
  }
  function outcomeLabel(outcome) {
    return VOTE_OUTCOME_LABEL[outcome] || text(outcome);
  }
  function agreementLabel(agreeing, votes) {
    return agreeing + " of " + votes + (votes === 1 ? " draft agrees" : " drafts agree");
  }

  // An abstention is recorded as a reason code, and one of the codes carries
  // the statement the verifier rejected. The code is what the run wrote, so it
  // stays on the element as its title; the sentence in front of a reader says
  // what kind of thing the code means.
  function abstentionSentence(reason) {
    var raw = String(reason);
    var code = raw.split(":")[0].trim();
    if (code === "CONTRADICTED_BY_EVIDENCE") {
      return "abstained: the verifier found the evidence contradicts a statement this draft relied on.";
    }
    if (code === "no reason recorded") {
      return "abstained, and the run recorded no reason.";
    }
    if (code.indexOf("DRAFT_") === 0) {
      return "abstained: the draft did not pass the code checks a voting draft must pass.";
    }
    if (raw.indexOf(":") < 0) {
      return "abstained: the answer could not be read as a ruling.";
    }
    return "abstained: the run recorded a reason this page does not classify.";
  }

  // The whole four-field proposal, not just the ruling. On this run one case's
  // drafts all proposed ESCALATE and still disagreed, because they differed on
  // a referral -- a line that showed only the ruling would have called that
  // vote unanimous.
  function proposalLine(proposal) {
    var p = proposal || {};
    return text(p.ruling) + ", amount " + money(p.amount_sgd) +
      ", driver " + money(p.driver_compensation_sgd) +
      ", referrals " + ((p.referrals && p.referrals.length) ? p.referrals.join(" ") : "none");
  }

  function draftLine(draft) {
    return "draft " + draft.draft + " (" + draftKindLabel(draft.kind) + ", seed " + text(draft.seed) + ") " +
      text(draft.verdict) + ": " + proposalLine(draft.proposal);
  }

  function draftBox(draft) {
    var swapped = draft.kind === "position_swapped";
    var box = h("div", { class: "draft " + text(draft.verdict) });
    box.appendChild(h("div", { class: "draft-head" }, [
      h("span", { class: "draft-no", text: "Draft " + text(draft.draft) }),
      h("span", { class: "badge " + (swapped ? "swapped" : "sampled"),
        text: draftKindLabel(draft.kind) }),
      h("span", { class: "badge", text: "seed " + text(draft.seed) }),
      h("span", { class: "badge", text: "temperature " + text(draft.temperature) }),
      h("span", { class: "badge " + text(draft.verdict), text: text(draft.verdict) })
    ]));
    var proposal = draft.proposal || {};
    box.appendChild(definitionList([
      ["ruling", h("span", { class: "badge judge", text: text(proposal.ruling) })],
      ["amount_sgd", money(proposal.amount_sgd)],
      ["driver_compensation_sgd", money(proposal.driver_compensation_sgd)],
      ["referrals", (proposal.referrals && proposal.referrals.length)
        ? h("ul", null, proposal.referrals.map(function (item) {
            return h("li", null, [h("span", { text: String(item) }), " ", clauseChipsInText(String(item))]);
          }))
        : h("span", { class: "null", text: "none" })]
    ]));
    if (draft.abstention) {
      box.appendChild(h("p", { class: "notes", title: text(draft.abstention),
        text: abstentionSentence(draft.abstention) }));
    }
    return box;
  }

  function votePanel(caseDoc) {
    var vote = caseDoc.vote;
    var section = h("div", { class: "vote-panel" });
    section.appendChild(h("h3", { text: "How the judge's drafts voted" }));
    if (!vote) {
      section.appendChild(h("p", { class: "lead", text:
        "This case was decided by a single judge call. No vote was recorded for it, so there is nothing to show here." }));
      return section;
    }
    section.appendChild(h("p", { class: "lead", text:
      "The judge was asked the same question " + vote.votes + " times. A proposal becomes this case's ruling " +
      "only when at least " + vote.threshold + " of the " + vote.votes + " drafts propose the same four graded " +
      "fields together; the drafts are drawn differently, and the run records how, per draft, below." }));

    var result = h("div", { class: "vote-result " + text(vote.outcome) });
    result.appendChild(h("div", { class: "headline" }, [
      h("span", { class: "what", text: outcomeLabel(vote.outcome) }),
      h("span", { class: "badge", text: agreementLabel(vote.agreeing, vote.votes) }),
      h("span", { class: "badge", text: "vote_agreement " + text(vote.agreement) }),
      vote.unanimous ? h("span", { class: "badge ok", text: "unanimous" })
                     : h("span", { class: "badge contested", text: "not unanimous" })
    ]));
    result.appendChild(h("p", { class: "notes", text: VOTE_OUTCOME_TEXT[vote.outcome] || "" }));
    section.appendChild(result);

    section.appendChild(h("h4", { text: "The drafts" }));
    vote.drafts.forEach(function (draft) { section.appendChild(draftBox(draft)); });
    return section;
  }

  // The verifier's own findings, drawn only when the run recorded them. The
  // counts are grouped by the draft each statement was charged to, read off the
  // run's own ``draft`` field on every judged item: no verdict is recomputed
  // here, and a case decided with the verifier off carries no block at all, so
  // the panel is absent rather than empty.
  function verifierPanel(caseDoc) {
    var vote = caseDoc.vote;
    var verification = vote && vote.verification;
    if (!verification) { return null; }
    var counts = verification.counts || {};
    var box = h("div", { class: "verifier-panel" });
    box.appendChild(h("h3", { text: "The verifier" }));
    box.appendChild(h("p", { class: "lead", text: verification.usable
      ? "One verifier call read " + text(verification.statements) + " factual statement" +
        (verification.statements === 1 ? "" : "s") + " the drafts made and checked each against this case's " +
        "brief. A statement the brief contradicts is recorded below; one marked material could change a " +
        "conclusion, and it stops the draft that stated it."
      : "The verifier was called but its answer could not be used (" + text(verification.reason) +
        "), so no statement was judged and the vote below stands as the drafts left it." }));
    box.appendChild(definitionList([
      ["statements judged", text(verification.statements)],
      ["supported", text(counts.supported)],
      ["contradicted", text(counts.contradicted)],
      ["not in evidence", text(counts.not_in_evidence)],
      ["contradictions that matter", text(verification.material)],
      ["contradictions that do not", text(verification.not_material)]
    ]));
    if (verification.abstained && verification.abstained.length) {
      box.appendChild(h("p", { class: "notes", text:
        "Drafts a material contradiction stopped: " + verification.abstained.join(", ") + "." }));
    }
    var byDraft = {};
    (verification.judged || []).forEach(function (item) {
      var list = byDraft[item.draft] || (byDraft[item.draft] = []);
      list.push(item);
    });
    var numbers = Object.keys(byDraft).map(Number).sort(function (a, b) { return a - b; });
    if (!numbers.length) {
      box.appendChild(h("p", { class: "notes", text:
        "No draft stated a fact the verifier could check against the brief." }));
      return box;
    }
    numbers.forEach(function (number) {
      var items = byDraft[number];
      var tally = { supported: 0, contradicted: 0, not_in_evidence: 0 };
      items.forEach(function (item) {
        if (Object.prototype.hasOwnProperty.call(tally, item.verdict)) { tally[item.verdict] += 1; }
      });
      var draft = h("div", { class: "draft verification" });
      draft.appendChild(h("div", { class: "draft-head" }, [
        h("span", { class: "draft-no", text: "Draft " + number }),
        h("span", { class: "badge ok", text: tally.supported + " supported" }),
        h("span", { class: "badge miss", text: tally.contradicted + " contradicted" }),
        h("span", { class: "badge", text: tally.not_in_evidence + " not in evidence" })
      ]));
      var contradicted = items.filter(function (item) { return item.verdict === "contradicted"; });
      if (contradicted.length) {
        draft.appendChild(h("ul", { class: "verdicts" }, contradicted.map(function (item) {
          return h("li", null, [
            h("span", { class: "badge " + (item.material ? "material" : "not_material"),
              text: item.material ? "material" : "not material" }),
            h("span", { text: text(item.text) }),
            item.brief_value ? h("span", { class: "src", text: "brief holds " + text(item.brief_value) }) : null
          ]);
        })));
      }
      box.appendChild(draft);
    });
    return box;
  }

  // The precedents the judge was shown, read from the case's own top-level
  // field rather than from the vote's payload. An empty list means the switch
  // was on and nothing matched; a case with no key at all was decided without
  // the question being asked. Those are different findings, so the panel is
  // drawn for the first and not the second.
  function precedentsPanel(caseDoc) {
    var shown = caseDoc.precedents_shown;
    if (shown === null || shown === undefined) { return null; }
    var box = h("div", { class: "precedents-panel" });
    box.appendChild(h("h3", { text: "Precedents shown to the judge" }));
    box.appendChild(h("p", { class: "lead", text: shown.length
      ? "The precedents switch was on and " + shown.length + " earlier closure" +
        (shown.length === 1 ? "" : "s") + " from the library went to the judge with this case. They are not " +
        "evidence and not policy: the judge was told to rest every finding on this case's own evidence ids " +
        "and clause ids."
      : "The precedents switch was on and no entry in the library matched this case, so the judge was shown " +
        "no precedents. That is not the same as the switch being off." }));
    if (shown.length) {
      box.appendChild(chips("precedent ids", shown.map(function (id) {
        return h("span", { class: "chip", text: String(id) });
      })));
    }
    return box;
  }

  // The cases a reader most needs to find are the ones the judge's own drafts
  // did not agree on: their ruling came from a majority, or from a refusal to
  // pick, and nothing else on the overview would say so.
  function voteSummary() {
    var contested = contestedCases();
    var box = h("div", { class: "vote-summary" });
    box.appendChild(h("h3", { text: "Where the judge's drafts disagreed" }));
    if (!contested.length) {
      box.appendChild(h("p", { class: "lead", text:
        "Every case in this run was decided by a unanimous vote: all " + DATA.cases.length +
        " cases had every draft propose the same four graded fields." }));
      return box;
    }
    box.appendChild(h("p", { class: "lead", text:
      contested.length + " of " + DATA.cases.length + " cases were not unanimous. Every case's vote agreement " +
      "is a column in the grid below, and the grid can be narrowed to just these cases." }));
    var body = h("tbody");
    contested.forEach(function (c) {
      var dissenters = c.vote.drafts.filter(function (draft) { return draft.verdict !== "agreed"; });
      var row = h("tr", {
        class: "clickable",
        title: "open case " + c.case_no,
        onclick: function () { openCase(c.case_no); }
      });
      row.appendChild(h("td", { class: "case-no", text: String(c.case_no) }));
      row.appendChild(h("td", { text: c.category }));
      row.appendChild(h("td", { class: "vote-cell", text: agreementLabel(c.vote.agreeing, c.vote.votes) }));
      row.appendChild(h("td", null, h("span", { class: "badge contested " + text(c.vote.outcome),
        text: outcomeLabel(c.vote.outcome) })));
      row.appendChild(h("td", { text: dissenters.map(draftLine).join("; ") }));
      body.appendChild(row);
    });
    box.appendChild(h("table", null, [
      h("thead", null, h("tr", null, [
        h("th", { text: "#" }), h("th", { text: "Category" }), h("th", { text: "Agreed" }),
        h("th", { text: "Vote outcome" }), h("th", { text: "The drafts that did not agree" })
      ])),
      body
    ]));
    return box;
  }

  // ---- View 2: one case, stepped through ---------------------------------
  // The four-field badge, in one place so the case view and the stance view
  // cannot disagree about the same case. Three states again: no key at all, a
  // case the run produced no ruling for, and a graded case that matched or did
  // not. The middle one is not a miss on four fields -- there are no four
  // fields, because there is no ruling to compare.
  function gradingBadge(caseDoc) {
    if (!caseDoc.grading) {
      return h("span", { class: "badge", text: "not graded" });
    }
    if (!caseDoc.has_ruling) {
      return h("span", { class: "badge miss", text: "no ruling produced" });
    }
    return h("span", {
      class: caseDoc.grading.exact ? "badge ok" : "badge miss",
      text: caseDoc.grading.exact
        ? "four-field match"
        : "MISS on " + caseDoc.grading.failed_fields.join(", ")
    });
  }

  function renderCase() {
    var root = document.getElementById("view-case");
    var caseDoc = BY_CASE[state.caseNo];
    clear(root);
    if (!caseDoc) { root.appendChild(h("p", { text: "no such case" })); return; }

    root.appendChild(casePicker());

    root.appendChild(h("div", { class: "case-head" }, [
      h("span", { class: "title", text: "Case " + caseDoc.case_no }),
      h("span", { class: "badge", text: caseDoc.category }),
      h("span", { class: "badge", text: text(caseDoc.difficulty) }),
      gradingBadge(caseDoc),
      h("span", { class: "badge", text: "brief " + String(caseDoc.brief_sha256).slice(0, 12) }),
      // Said per case, not only once for the run: a reader stepping through one
      // case has to know whether these advocate outputs were asked for here, and
      // a run can hold both kinds.
      caseDoc.replay ? h("span", { class: "badge", text: "advocates replayed" }) : null,
      caseDoc.replay ? h("span", { class: "badge", text: "from " + text(caseDoc.replay.run_directory) }) : null
    ]));

    var stepper = h("div", { class: "stepper" });
    STEPS.forEach(function (step, index) {
      stepper.appendChild(h("button", {
        class: "step" + (index === state.step ? " on" : ""),
        text: step.label,
        onclick: function () { goToStep(index); }
      }));
    });
    stepper.appendChild(h("span", { class: "nav" }, [
      h("button", { text: "back", disabled: state.step === 0, onclick: function () { goToStep(state.step - 1); } }),
      h("button", { text: "next", disabled: state.step === STEPS.length - 1, onclick: function () { goToStep(state.step + 1); } })
    ]));
    root.appendChild(stepper);

    var body = h("div", { id: "step-body" });
    root.appendChild(body);
    var panel = h("section", { class: "panel" });
    var render = [renderDispute, renderEvidence, renderRider, renderDriver, renderJudge, renderKey][state.step];
    render(caseDoc, panel);
    body.appendChild(panel);
    root.appendChild(h("p", { class: "hint", text: "Step " + (state.step + 1) + " of " + STEPS.length +
      ". Clicking an evidence chip on a claim opens the artifact it cites; clicking a clause chip shows the " +
      "clause's rule text. Left and right arrows move between steps, [ and ] between cases, and ? lists the keys." }));
  }

  function renderDispute(caseDoc, panel) {
    var dispute = caseDoc.dispute;
    panel.appendChild(h("h2", { text: "The dispute" }));
    panel.appendChild(definitionList([
      ["case", String(caseDoc.case_no)],
      ["dispute id", h("code", { text: text(dispute.dispute_id) })],
      ["trip id", h("code", { text: text(dispute.trip_id) })],
      ["category", text(dispute.category)],
      ["filed by", text(dispute.filed_by)],
      ["filed at", text(dispute.filed_at)],
      ["channel", text(dispute.channel)],
      ["amount contested", "SGD " + money(dispute.amount_contested_sgd)]
    ]));

    panel.appendChild(h("h4", { text: "The claim, as filed" }));
    panel.appendChild(h("blockquote", null, [
      h("span", { class: "who", text: "filed by " + text(dispute.filed_by) + " at " + text(dispute.filed_at) }),
      h("span", { text: text(dispute.claim_text) })
    ]));

    var counterparty = dispute.counterparty_statement;
    panel.appendChild(h("h4", { text: "The counterparty's statement" }));
    if (counterparty) {
      panel.appendChild(h("blockquote", null, [
        h("span", { class: "who", text: "submitted by " + text(counterparty.submitted_by) + " at " + text(counterparty.submitted_at) }),
        h("span", { text: text(counterparty.text) })
      ]));
    } else {
      panel.appendChild(h("p", { class: "null", text: "no counterparty statement on the record" }));
    }
    panel.appendChild(h("p", { class: "hint", text:
      "The amount contested is the figure the dispute names. The amount actually decided is on the judge step, and whether it agrees with the key is on step 6." }));
  }

  function renderEvidence(caseDoc, panel) {
    panel.appendChild(h("h2", { text: "The evidence" }));
    panel.appendChild(h("p", { class: "lead", text:
      "Every artifact the agents were handed, with the admissibility pre-pass's own assessment and the facts derived from it. " +
      "COMPLETE, IMPAIRED and MISSING are shown apart because the pre-pass is what this project adds to a plain reading of the file." }));
    caseDoc.evidence.forEach(function (artifact) {
      panel.appendChild(artifactBlock(artifact, caseDoc));
    });
  }

  function artifactBlock(artifact, caseDoc) {
    var admissibility = artifact.admissibility || {};
    var status = admissibility.status || "COMPLETE";
    var box = h("div", {
      class: "artifact " + status + (state.highlight === artifact.evidence_id ? " flash" : ""),
      data: { artifact: artifact.evidence_id }
    });
    box.appendChild(h("div", { class: "head" }, [
      h("span", { class: "id", text: artifact.evidence_id }),
      h("span", { class: "badge", text: artifact.evidence_type }),
      h("span", { class: "badge " + status.toLowerCase(), text: status }),
      h("span", { class: "badge", text: "weight " + text(admissibility.weight_multiplier) }),
      artifact.source ? h("span", { class: "badge", text: artifact.source }) : null
    ]));

    var issues = admissibility.issues || [];
    if (issues.length) {
      box.appendChild(chips("issue codes", issues.map(function (issue) {
        return h("span", { class: "chip issue", text: String(issue) });
      })));
    } else {
      box.appendChild(chips("issue codes", [h("span", { class: "empty", text: "none - admissible on its face" })]));
    }
    if (admissibility.notes) {
      box.appendChild(h("p", { class: "notes", text: admissibility.notes }));
    }
    box.appendChild(definitionList([
      ["trip", artifact.trip_id ? h("code", { text: artifact.trip_id }) : null],
      ["generated", text(artifact.generated_at)],
      ["assessed", text(admissibility.assessed_at)],
      ["assessor", text(admissibility.assessor_version)]
    ]));

    var payload = artifact.payload;
    if (payload === null || payload === undefined) {
      box.appendChild(h("p", { class: "notes", text:
        "This artifact carries no payload: the record itself is absent, and the absence is what the agents were handed." }));
      return box;
    }

    var derived = (typeof payload === "object" && !Array.isArray(payload)) ? payload.derived : null;
    var rest = payload;
    if (derived) {
      rest = {};
      Object.keys(payload).forEach(function (key) {
        if (key !== "derived") { rest[key] = payload[key]; }
      });
    }

    var payloadDetails = h("details", null, [
      h("summary", { text: "payload" }),
      renderValue(rest)
    ]);
    box.appendChild(payloadDetails);

    if (derived) {
      var derivedBox = h("div", null, [
        h("h4", { text: "derived facts" }),
        h("p", { class: "hint", text: "Each fact carries the artifact it was computed from." })
      ]);
      Object.keys(derived).forEach(function (group) {
        derivedBox.appendChild(h("h4", { text: group }));
        derivedBox.appendChild(renderValue(derived[group]));
      });
      box.appendChild(derivedBox);
    }
    return box;
  }

  function advocateSection(caseDoc, role, label, accent, panel) {
    var agent = caseDoc.advocates[role];
    var section = h("div", { class: "role " + role });
    section.appendChild(h("h2", { text: label }));
    section.appendChild(h("span", { class: "badge " + accent, text: role }));

    if (!agent.parsed) {
      section.appendChild(h("p", { class: "miss-note", text:
        "This agent produced no parsable answer for this case." }));
    }
    var claims = agent.claims || [];
    section.appendChild(h("p", { class: "lead", text:
      claims.length + (claims.length === 1 ? " claim" : " claims") +
      ". Every claim cites both an evidence id and a clause id; a chip you can click is a record you can open." }));

    claims.forEach(function (claim, index) {
      var box = h("div", { class: "claim" });
      box.appendChild(h("div", { class: "claim-head" }, [
        h("span", { class: "claim-no", text: "#" + (index + 1) }),
        claim.asserted_weight !== undefined ? h("span", { text: "asserted weight " + text(claim.asserted_weight) }) : null,
        claim.relies_on ? h("span", null, ["relies on ", h("code", { text: claim.relies_on })]) : null
      ]));
      box.appendChild(h("p", { class: "text", text: text(claim.text) }));
      var evidenceIds = claim.evidence_ids || [];
      var clauseIds = claim.clause_ids || [];
      box.appendChild(chips("evidence", evidenceIds.map(function (id) {
        return evidenceChip(caseDoc, id);
      })));
      box.appendChild(chips("clauses", clauseIds.map(clauseChip)));
      if (!evidenceIds.length || !clauseIds.length) {
        box.appendChild(h("p", { class: "miss-note", text:
          "This claim is missing a citation. No citation, no claim." }));
      }
      section.appendChild(box);
    });
    // Stated on the panel that carries the token figures, not only in the case
    // head: a reader looking at these calls has to know this run did not make
    // them, and the figures below were billed to the run that did.
    if (caseDoc.replay) {
      section.appendChild(h("p", { class: "miss-note", text:
        "These advocate outputs were replayed from " + text(caseDoc.replay.run_directory) +
        " and were not regenerated by this run: only the judge was called, so the token figures below were billed " +
        "to the run that made these calls and not to this one." }));
    }
    panel.appendChild(section);
    panel.appendChild(callBar(agent));
  }

  function callBar(agent) {
    var bar = h("div", { class: "callbar" });
    agent.calls.forEach(function (call, index) {
      var parts = [
        "call " + (index + 1) + ": " + text(call.parse_outcome),
        "shape=" + text(call.shape),
        "attempts=" + text(call.attempts),
        "prompt=" + text(call.prompt_tokens),
        "completion=" + text(call.completion_tokens),
        "reasoning=" + text(call.reasoning_tokens),
        "cached=" + text(call.cached_tokens),
        text(Math.round((call.duration_seconds || 0) * 10) / 10) + "s"
      ];
      var line = h("div", { class: call.parse_outcome === "PARSED" ? "" : "warn", text: parts.join("  ") });
      bar.appendChild(line);
      if (call.note) { bar.appendChild(h("div", { class: "warn", text: "note: " + call.note })); }
      if (call.response_text) {
        bar.appendChild(h("details", null, [
          h("summary", { text: "raw response that did not parse" }),
          h("pre", { class: "raw", text: call.response_text })
        ]));
      }
    });
    return bar;
  }

  function renderRider(caseDoc, panel) {
    advocateSection(caseDoc, "RIDER_ADVOCATE", "The rider's advocate", "rider", panel);
  }
  function renderDriver(caseDoc, panel) {
    advocateSection(caseDoc, "DRIVER_ADVOCATE", "The driver's advocate", "driver", panel);
  }

  function renderJudge(caseDoc, panel) {
    var judge = caseDoc.judge;
    var section = h("div", { class: "role JUDGE" });
    section.appendChild(h("h2", { text: "The judge" }));
    section.appendChild(h("span", { class: "badge judge", text: "JUDGE" }));

    var refereeLedger = (caseDoc.referee || {}).ledger || [];
    section.appendChild(h("h3", { text: "Referee ledger" }));
    section.appendChild(h("p", { class: "lead", text:
      refereeLedger.length
        ? "The code referee checked " + refereeLedger.length + " claims before the judge. Kept claims remain available to the judge; discarded claims are authoritative and cannot be reinstated."
        : "No referee ledger was recorded for this case." }));
    refereeLedger.forEach(function (entry, index) {
      var kept = entry.status === "KEPT";
      var box = h("div", { class: "claim " + (kept ? "" : "discarded") });
      box.appendChild(h("div", { class: "claim-head" }, [
        h("span", { class: "claim-no", text: "#" + (index + 1) }),
        h("span", { class: "badge " + (String(entry.side).toLowerCase() === "rider" ? "rider" : "driver"),
          text: "side: " + text(entry.side) }),
        h("span", { class: "badge " + (kept ? "complete" : "missing"),
          text: text(entry.status) })
      ]));
      box.appendChild(h("p", { class: "text", text: text(entry.claim) }));
      box.appendChild(h("p", { class: "notes", text:
        text(entry.reason_code) + ": " + text(entry.detail) }));
      if (entry.flags && entry.flags.length) {
        box.appendChild(h("p", { class: "notes", text: "flag: " + entry.flags.join("; ") }));
      }
      section.appendChild(box);
    });

    var discarded = judge.discarded_claims || [];
    section.appendChild(h("h3", { text: "Code-assembled discarded claims" }));
    section.appendChild(h("p", { class: "lead", text:
      discarded.length
        ? "The final list starts with the referee's entries copied verbatim, followed by any further judge additions."
        : "The code-assembled list is empty." }));
    discarded.forEach(function (entry, index) {
      var box = h("div", { class: "claim discarded" });
      box.appendChild(h("div", { class: "claim-head" }, [
        h("span", { class: "claim-no", text: "#" + (index + 1) }),
        h("span", { class: "badge " + (String(entry.side).toLowerCase() === "rider" ? "rider" : "driver"),
          text: "side: " + text(entry.side) })
      ]));
      box.appendChild(h("p", { class: "text", text: text(entry.claim) }));
      box.appendChild(h("p", { class: "notes", text:
        "reason: " + text(entry.reason_code || entry.reason) +
        (entry.detail ? ": " + text(entry.detail) : "") }));
      section.appendChild(box);
    });

    var verdict = judge.verdict;
    section.appendChild(h("h3", { text: "The ruling" }));
    section.appendChild(definitionList([
      ["ruling", h("span", { class: "badge judge", text: text(verdict.ruling) })],
      ["amount_sgd", money(verdict.amount_sgd)],
      ["driver_compensation_sgd", money(verdict.driver_compensation_sgd)],
      ["confidence", text(verdict.confidence)]
    ]));

    section.appendChild(h("h4", { text: "Referrals" }));
    if (judge.referrals && judge.referrals.length) {
      var list = h("ul");
      judge.referrals.forEach(function (item) {
        list.appendChild(h("li", null, [h("span", { text: String(item) }), " ", clauseChipsInText(String(item))]));
      });
      section.appendChild(list);
    } else {
      section.appendChild(h("p", { class: "null", text: "no referral: no clause on these facts sends the case to a human" }));
    }

    section.appendChild(h("h4", { text: "Explanation" }));
    section.appendChild(h("div", null, paragraphs(verdict.explanation)));

    // The ruling above is the vote's outcome; this is the vote itself. It is
    // shown per case rather than once for the run because the drafts are a
    // property of the case: some cases carry a unanimous vote, some do not.
    section.appendChild(votePanel(caseDoc));

    // Both of these are drawn only when the run recorded their data -- the
    // verifier's findings, and the precedents the judge was shown. Each returns
    // null when it has nothing, and appendNode appends only a real node, so a
    // run with either switch off shows neither heading rather than an empty
    // panel.
    appendNode(section, verifierPanel(caseDoc));
    appendNode(section, precedentsPanel(caseDoc));

    panel.appendChild(section);
    panel.appendChild(callBar(judge.agent));
  }

  function clauseChipsInText(value) {
    var found = value.match(/POL-[A-Z]{2,4}-[0-9]{2}(?:\([A-Za-z0-9]{1,3}\))?/g);
    if (!found) { return null; }
    var seen = {};
    var unique = found.filter(function (id) {
      if (seen[id]) { return false; }
      seen[id] = true;
      return true;
    });
    return h("span", { class: "chips" }, unique.map(clauseChip));
  }

  // The organisers' stated expectation for their own sample case, drawn as what
  // it is. It is not a key and it is not used as one: nothing here is compared
  // field by field, nothing is called a match or a miss against it, and the
  // page says both of those things above it rather than leaving a reader to
  // infer them from the absence of a Result column.
  function statedExpectation(caseDoc) {
    var stated = DATA.stated_expectation;
    if (!stated) {
      return h("p", { class: "null", text: "No stated expectation is recorded for this case." });
    }
    var box = h("div");
    box.appendChild(definitionList([
      ["source document", h("code", { text: text(stated.source_document) })],
      ["dispute id", h("code", { text: text(stated.dispute_id) })],
      ["stated outcome", h("b", { text: text(stated.expected_outcome_as_stated) })],
      ["the run's own ruling", h("code", { text: text(caseDoc.judge.verdict.ruling) })]
    ]));
    var reasons = stated.stated_reasons || [];
    if (reasons.length) {
      box.appendChild(h("h4", { text: "The reasons as stated" }));
      box.appendChild(h("ul", { class: "vals" }, reasons.map(function (reason) {
        return h("li", { text: text(reason) });
      })));
    }
    box.appendChild(h("p", { class: "hint", text: text(stated.not_the_answer_key) }));
    box.appendChild(h("p", { class: "hint", text: text(stated.upheld_is_not_a_token_here) }));
    return box;
  }

  function renderKey(caseDoc, panel) {
    // A page with no key is not graded at all, so this step shows what it has
    // instead of a grade. There is no four-field comparison to draw and none is
    // drawn: an empty table of four fields would read as four misses.
    if (!HAS_KEY) {
      panel.appendChild(h("h2", { text: "The organisers' stated expectation" }));
      panel.appendChild(h("p", { class: "lead", text:
        "This case is not in any answer key, so it is not graded and no accuracy is claimed for it. What the " +
        "organisers state about their own sample case is below, labelled as what it is: the organisers' stated " +
        "expectation, not an answer key." }));
      panel.appendChild(statedExpectation(caseDoc));
      return;
    }
    // A keyed page can still hold a case the key does not. Nothing is claimed
    // about such a case rather than a table of four fields being drawn against
    // no expected side, which would read as four misses.
    if (!caseDoc.grading) {
      panel.appendChild(h("h2", { text: "Against the answer key" }));
      panel.appendChild(h("p", { class: "null", text:
        "This case is not in the answer key this page grades against, so there is no expected side to compare it with." }));
      return;
    }
    panel.appendChild(h("h2", { text: "Against the answer key" }));
    panel.appendChild(h("p", { class: "lead", text:
      "The expected side is the grading answer key at " + text(DATA.set.key_path) + ". It is the answer key, not an " +
      "input: no agent saw it, and nothing under tribunal/ can reach it. A case counts as a match only when all four " +
      "fields agree." }));

    var body = h("tbody");
    caseDoc.grading.fields.forEach(function (outcome) {
      var expectedValue = null;
      var producedValue = null;
      if (outcome.field === "referrals") {
        expectedValue = referralList(caseDoc.expected.referrals);
        producedValue = referralList(caseDoc.judge.referrals);
      } else if (outcome.field === "ruling") {
        expectedValue = h("code", { text: text(caseDoc.expected.ruling) });
        producedValue = h("code", { text: text(caseDoc.judge.verdict.ruling) });
      } else {
        expectedValue = h("span", { class: "mono", text: money(caseDoc.expected[outcome.field]) });
        producedValue = h("span", { class: "mono", text: money(caseDoc.judge.verdict[outcome.field]) });
      }
      body.appendChild(h("tr", null, [
        h("td", null, h("code", { text: outcome.field })),
        h("td", null, expectedValue),
        h("td", null, producedValue),
        h("td", null, h("span", { class: outcome.correct ? "badge ok" : "badge miss",
          text: outcome.correct ? "match" : "MISS" })),
        h("td", { class: "hint", text: outcome.detail || "" })
      ]));
    });
    panel.appendChild(h("table", null, [
      h("thead", null, h("tr", null, [
        h("th", { text: "Field" }), h("th", { text: "Expected (answer key)" }),
        h("th", { text: "Produced (the run)" }), h("th", { text: "Result" }), h("th", { text: "Grader's detail" })
      ])),
      body
    ]));

    panel.appendChild(h("h4", { text: "Answer-key metadata" }));
    panel.appendChild(definitionList([
      ["difficulty", text(caseDoc.expected.difficulty)],
      ["governing clauses", (caseDoc.expected.governing_clauses || []).map(function (id) {
        return h("div", null, [clauseChip(id)]);
      })],
      ["recorded matched flag", text(caseDoc.recorded_matched)]
    ]));
    // Only where the run recorded a flag at all. A case that wrote no result
    // file recorded nothing, and "the run recorded matched=null" would be a
    // claim about a file that does not exist.
    if (caseDoc.has_ruling && caseDoc.recorded_matched !== caseDoc.grading.exact) {
      panel.appendChild(h("div", { class: "warnbox", text:
        "The run recorded matched=" + text(caseDoc.recorded_matched) + " for this case but the grader now reads " +
        text(caseDoc.grading.exact) + ". The two disagree, and the grader is the one that is recomputed here." }));
    }
    if (caseDoc.expected.rationale) {
      panel.appendChild(h("h4", { text: "The key's rationale" }));
      panel.appendChild(h("div", null, paragraphs(caseDoc.expected.rationale)));
    }
    if (!caseDoc.grading.exact) {
      panel.appendChild(h("div", { class: "miss-note" }, [missLine(caseDoc)]));
    }
  }

  function referralList(items) {
    if (!items || !items.length) { return h("span", { class: "null", text: "none" }); }
    return h("ul", { class: "vals" }, items.map(function (item) {
      return h("li", { text: String(item) });
    }));
  }

  // ---- View 3: the two advocates against the same record -----------------
  // The stance view is not about who won. It is about what each side chose to
  // build an argument on: which artifacts it reached for, which it left alone,
  // and what the judge then threw away.
  function casePicker() {
    var picker = h("div", { class: "case-picker" });
    DATA.cases.forEach(function (c) {
      // A picker button is marked as a miss only when the case was graded and
      // did not match. A page with no key has no misses, and marking every
      // button would say the run failed every case.
      var cls = c.case_no === state.caseNo ? "on" : (c.grading && !c.grading.exact ? "miss" : "");
      picker.appendChild(h("button", {
        class: cls,
        text: String(c.case_no),
        onclick: function () {
          if (state.view === "stance") { openStance(c.case_no); } else { openCase(c.case_no); }
        }
      }));
    });
    return picker;
  }

  function renderStance() {
    var root = document.getElementById("view-stance");
    var caseDoc = BY_CASE[state.caseNo];
    clear(root);
    if (!caseDoc) { root.appendChild(h("p", { text: "no such case" })); return; }

    root.appendChild(casePicker());
    root.appendChild(h("div", { class: "case-head" }, [
      h("span", { class: "title", text: "Case " + caseDoc.case_no + ", both sides at once" }),
      h("span", { class: "badge", text: caseDoc.category }),
      h("span", { class: "badge", text: text(caseDoc.difficulty) }),
      gradingBadge(caseDoc)
    ]));
    root.appendChild(h("p", { class: "lead", text:
      "Both advocates were handed the same brief and the same " + caseDoc.evidence.length +
      " artifacts. What follows is what each of them chose to stand on." }));

    // The proof comes first, above the side-by-side claims: the claims are what
    // each side argued, and the proof is why their disagreement is evidence of
    // anything at all.
    root.appendChild(stanceProof(caseDoc));

    var grid = h("div", { class: "stance-grid" });
    grid.appendChild(stanceColumn(caseDoc, "RIDER_ADVOCATE"));
    grid.appendChild(stanceColumn(caseDoc, "DRIVER_ADVOCATE"));
    root.appendChild(grid);

    root.appendChild(contestedRecord(caseDoc));
    root.appendChild(discardedBySide(caseDoc));
  }

  function stanceColumn(caseDoc, role) {
    var agent = caseDoc.advocates[role] || {};
    var claims = agent.claims || [];
    var isRider = role === "RIDER_ADVOCATE";
    var col = h("div", { class: "stance-col " + role });
    col.appendChild(h("h3", null, [
      h("span", { class: "badge " + (isRider ? "rider" : "driver"), text: role }),
      h("span", { class: "count", text: claims.length + (claims.length === 1 ? " claim" : " claims") })
    ]));
    if (!claims.length) {
      col.appendChild(h("p", { class: "empty", text:
        agent.parsed ? "this side made no claims" : "this agent produced no parsable answer" }));
      return col;
    }
    claims.forEach(function (claim, index) {
      var evidenceIds = claim.evidence_ids || [];
      var clauseIds = claim.clause_ids || [];
      var box = h("div", { class: "claim" });
      box.appendChild(h("div", { class: "claim-head" }, [
        h("span", { class: "claim-no", text: "#" + (index + 1) }),
        claim.asserted_weight !== undefined ? h("span", { text: "asserted weight " + text(claim.asserted_weight) }) : null,
        claim.relies_on ? h("span", null, ["relies on ", h("code", { text: claim.relies_on })]) : null
      ]));
      box.appendChild(h("p", { class: "text", text: text(claim.text) }));
      box.appendChild(chips("evidence", evidenceIds.map(function (id) { return evidenceChip(caseDoc, id); })));
      box.appendChild(chips("clauses", clauseIds.map(clauseChip)));
      if (!evidenceIds.length || !clauseIds.length) {
        box.appendChild(h("p", { class: "miss-note", text:
          "This claim is missing a citation. No citation, no claim." }));
      }
      col.appendChild(box);
    });
    return col;
  }

  // Which artifacts each side reached for. An artifact both sides cite is a
  // disagreement about what the same record means; an artifact only one side
  // cites is a choice about what to stand on.
  function contestedRecord(caseDoc) {
    var bySide = { RIDER_ADVOCATE: {}, DRIVER_ADVOCATE: {} };
    Object.keys(bySide).forEach(function (role) {
      var claims = (caseDoc.advocates[role] || {}).claims || [];
      claims.forEach(function (claim, index) {
        (claim.evidence_ids || []).forEach(function (id) {
          if (!bySide[role][id]) { bySide[role][id] = []; }
          bySide[role][id].push(index + 1);
        });
      });
    });
    var seen = {};
    Object.keys(bySide.RIDER_ADVOCATE).forEach(function (id) { seen[id] = true; });
    Object.keys(bySide.DRIVER_ADVOCATE).forEach(function (id) { seen[id] = true; });
    // Artifacts in the order the brief lists them, so what the reader sees
    // here matches step 2, with anything unrecognised appended rather than lost.
    var ordered = (caseDoc.evidence || [])
      .map(function (a) { return a.evidence_id; })
      .filter(function (id) { return Object.prototype.hasOwnProperty.call(seen, id); });
    Object.keys(seen).forEach(function (id) {
      if (ordered.indexOf(id) < 0) { ordered.push(id); }
    });

    var box = h("section", { class: "panel" });
    box.appendChild(h("h2", { text: "The record they argued over" }));
    box.appendChild(h("p", { class: "lead", text:
      "The badge on each row is the admissibility pre-pass's own verdict on that artifact, not " +
      "either advocate's opinion of it." }));
    if (!ordered.length) {
      box.appendChild(h("p", { class: "empty", text: "Neither advocate cited an artifact in this case." }));
      return box;
    }
    ordered.forEach(function (id) {
      var rider = bySide.RIDER_ADVOCATE[id] || [];
      var driver = bySide.DRIVER_ADVOCATE[id] || [];
      var both = rider.length > 0 && driver.length > 0;
      var artifact = null;
      (caseDoc.evidence || []).forEach(function (a) { if (a.evidence_id === id) { artifact = a; } });
      var status = (artifact && artifact.admissibility && artifact.admissibility.status) || "COMPLETE";
      var row = h("div", { class: "record-row " + (both ? "both" : "one") });
      row.appendChild(h("span", { class: "id", text: id }));
      row.appendChild(h("span", { class: "badge " + status.toLowerCase(), text: status }));
      if (artifact) { row.appendChild(h("span", { class: "badge", text: artifact.evidence_type })); }
      row.appendChild(h("span", { class: "badge", text:
        both ? "both sides" : (rider.length ? "rider only" : "driver only") }));
      row.appendChild(h("span", { class: "sides", text:
        "rider: " + (rider.length ? "claims " + rider.join(", ") : "not cited") +
        "   |   driver: " + (driver.length ? "claims " + driver.join(", ") : "not cited") }));
      box.appendChild(row);
    });
    return box;
  }

  function discardedBySide(caseDoc) {
    var discarded = caseDoc.judge.discarded_claims || [];
    var box = h("section", { class: "panel" });
    box.appendChild(h("h2", { text: "What the judge threw out, by side" }));
    if (!discarded.length) {
      box.appendChild(h("p", { class: "lead", text:
        "The judge discarded no claims in this case: every claim it was given carried its citations correctly." }));
      return box;
    }
    var grouped = { rider: [], driver: [], other: [] };
    discarded.forEach(function (entry) {
      var key = String(entry.side || "").toLowerCase();
      if (!Object.prototype.hasOwnProperty.call(grouped, key)) { key = "other"; }
      grouped[key].push(entry);
    });
    ["rider", "driver", "other"].forEach(function (key) {
      var items = grouped[key];
      box.appendChild(h("h3", null, [
        h("span", { class: "badge " + (key === "rider" ? "rider" : (key === "driver" ? "driver" : "")),
          text: key === "other" ? "side not recorded" : key }),
        h("span", { class: "count", text: items.length + (items.length === 1 ? " discarded" : " discarded") })
      ]));
      if (!items.length) {
        box.appendChild(h("p", { class: "empty", text: "nothing discarded from this side" }));
        return;
      }
      items.forEach(function (entry, index) {
        var claim = h("div", { class: "claim discarded" });
        claim.appendChild(h("div", { class: "claim-head" }, [
          h("span", { class: "claim-no", text: "#" + (index + 1) })
        ]));
        claim.appendChild(h("p", { class: "text", text: text(entry.claim) }));
        claim.appendChild(h("p", { class: "notes", text: "reason: " + text(entry.reason) }));
        box.appendChild(claim);
      });
    });
    return box;
  }

  // ---- the stance proof -------------------------------------------------
  // The claim this viewer exists to show is not that the two advocates argued
  // differently -- any two agents will. It is that they were handed the same
  // evidence and differed only in stance. Three facts, all read from the
  // transcript and the result, all recomputed by the build, which refuses to
  // publish a page on which any of them fails.
  function fact(what, why, rows) {
    var node = h("div", { class: "fact" });
    node.appendChild(h("div", { class: "what", text: what }));
    node.appendChild(h("p", { class: "why", text: why }));
    var dl = h("dl", { class: "digests" });
    rows.forEach(function (row) {
      dl.appendChild(h("dt", { text: row[0] }));
      dl.appendChild(h("dd", null, [
        h("code", { class: "digest " + row[2], text: text(row[1]) }),
        row[3] ? h("span", { class: "tag", text: row[3] }) : null
      ]));
    });
    node.appendChild(dl);
    return node;
  }

  function differingAsLines(ranges) {
    return ranges.map(function (pair) {
      return pair[1] - pair[0] === 1 ? String(pair[0]) : pair[0] + "-" + String(pair[1] - 1);
    }).join(", ");
  }

  function stanceProof(caseDoc) {
    var proof = caseDoc.stance_proof;
    var region = DATA.stance_prompts.stance_region;
    var box = h("section", { class: "panel proof" });
    box.appendChild(h("h2", { text: "The stance proof" }));
    box.appendChild(h("p", { class: "lead", text:
      "Both advocates read the same evidence and differ only in stance. These are the three facts " +
      "that back it. Every digest is shown whole, because a digest you can only partly see is an " +
      "assertion that two things are equal rather than evidence that they are." }));

    // 1. Same evidence. The same value is printed three times, which is the
    //    point: equality is the thing being shown, so it is shown three times.
    box.appendChild(fact(
      "1. They were handed the same evidence.",
      "The two advocates' user prompts are byte-identical to each other and to the brief this "
        + "build rebuilt from the repository and verified against the digest the run recorded. "
        + "One value, three times.",
      [
        ["rider advocate, user prompt", proof.rider.user_sha256, "same", "identical"],
        ["driver advocate, user prompt", proof.driver.user_sha256, "same", "identical"],
        ["the brief this build verified", proof.brief_sha256, "same", "identical"]
      ]
    ));

    // 2. Different instructions.
    box.appendChild(fact(
      "2. Their instructions differ.",
      "Their system prompts are not identical, so whatever they disagree about comes from the "
        + "stance each was given rather than from the record they read.",
      [
        ["rider advocate, system prompt", proof.rider.system_sha256, "differ", "not equal"],
        ["driver advocate, system prompt", proof.driver.system_sha256, "differ", "not equal"]
      ]
    ));

    // 3. The difference is confined to the stance block. A case that wrote no
    //    result file has nothing recorded for this, and the row says so: an
    //    empty list would read as a recorded finding that the two prompts do
    //    not differ, which is the opposite of what the run left behind.
    var recordedRanges = proof.recorded_differing_ranges;
    var why3 = "The two rendered system prompts differ on lines " + differingAsLines(proof.differing_ranges)
      + ", and the stance block occupies lines " + region[0] + " to " + (region[1] - 1)
      + ". Every differing line falls inside it, which is what this build recomputed before writing this page.";
    why3 += recordedRanges === null
      ? " This case wrote no result file, so the run recorded no differing ranges for it: the recomputed ranges " +
        "stand alone here, and the run's own record is shown as not recorded rather than as an empty list, which " +
        "would read as a recorded finding that the two prompts do not differ."
      : " It is also what the run recorded in stance_differing_ranges.";
    box.appendChild(fact(
      "3. The difference is confined to the stance block.",
      why3,
      [
        ["differing line ranges", JSON.stringify(proof.differing_ranges), "differ", "recomputed"],
        ["recorded by the run",
          recordedRanges === null ? "not recorded" : JSON.stringify(recordedRanges),
          recordedRanges === null ? "none" : "differ",
          recordedRanges === null ? "not recorded" : "matches"],
        ["stance block", "[" + region[0] + ", " + region[1] + ")", "same", "half-open"]
      ]
    ));

    box.appendChild(promptPair());
    return box;
  }

  function promptPair() {
    var sp = DATA.stance_prompts;
    var wrap = h("div");
    wrap.appendChild(h("h3", { text: "The two system prompts, as rendered" }));
    wrap.appendChild(h("p", { class: "lead", text:
      "Rendered at build time from the prompt files, not quoted into this page, so what is shown " +
      "is what the run was handed. The differing lines are highlighted and the stance block's " +
      "extent is marked. The template is the same for every case, so this pair is shared." }));
    var grid = h("div", { class: "prompt-grid" });
    grid.appendChild(promptColumn("RIDER_ADVOCATE", sp.rider_lines));
    grid.appendChild(promptColumn("DRIVER_ADVOCATE", sp.driver_lines));
    wrap.appendChild(grid);
    wrap.appendChild(h("div", { class: "marker" }, [
      h("span", null, [h("i", { class: "swatch diff" }), "a line where the two renders differ"]),
      h("span", null, [h("i", { class: "swatch stance" }), "inside the stance block"])
    ]));
    return wrap;
  }

  function promptColumn(role, lines) {
    var sp = DATA.stance_prompts;
    var region = sp.stance_region;
    var ranges = sp.differing_ranges;
    var col = h("div", { class: "prompt-col" });
    col.appendChild(h("h4", null, [
      h("span", {
        class: "badge " + (role === "RIDER_ADVOCATE" ? "rider" : "driver"),
        text: role
      }),
      " system prompt, " + lines.length + " lines"
    ]));
    var list = h("ol", { class: "plines" });
    lines.forEach(function (line, index) {
      var differs = ranges.some(function (pair) {
        return index >= pair[0] && index < pair[1];
      });
      var inStance = index >= region[0] && index < region[1];
      list.appendChild(h("li", {
        class: (differs ? "diff " : "") + (inStance ? "stance" : "")
      }, [
        h("span", { class: "n", text: String(index) }),
        h("span", { class: "t", text: line })
      ]));
    });
    col.appendChild(list);
    return col;
  }

  // ---- keyboard ----------------------------------------------------------
  var KEYS = [
    ["right  or  l", "next step"],
    ["left  or  h", "previous step"],
    ["1 to " + String(STEPS.length), "jump straight to a step"],
    ["[  /  ]", "previous / next case"],
    ["o", "overview"],
    ["c", "one case, stepped through"],
    ["s", "stance: both sides at once"],
    ["f", "projector: scale everything up"],
    ["?", "this list"],
    ["esc", "close a clause or this list"]
  ];
  function helpOpen() { return !!document.getElementById("keys-modal"); }
  function renderHelp() {
    if (helpOpen()) { return; }
    var box = h("div", { class: "box" });
    box.appendChild(h("div", { class: "head" }, [
      h("span", { class: "id", text: "Keyboard" }),
      h("button", { class: "close", text: "close", onclick: closeHelp })
    ]));
    var dl = h("dl", { class: "keys" });
    KEYS.forEach(function (pair) {
      dl.appendChild(h("dt", null, h("kbd", { text: pair[0] })));
      dl.appendChild(h("dd", { text: pair[1] }));
    });
    box.appendChild(dl);
    box.appendChild(h("p", { class: "hint", text:
      "The address bar always carries a link to exactly what is on screen, so one step can be sent to someone." }));
    var overlay = h("div", { class: "modal", id: "keys-modal", onclick: function (event) {
      if (event.target === overlay) { closeHelp(); }
    } }, box);
    document.body.appendChild(overlay);
  }
  function closeHelp() {
    var modal = document.getElementById("keys-modal");
    if (modal) { modal.parentNode.removeChild(modal); }
  }
  function modalOpen() { return helpOpen() || !!document.getElementById("clause-modal"); }

  function onKeyDown(event) {
    // A modal owns the keyboard while it is open: escape closes it and nothing
    // else reaches the view behind it.
    if (modalOpen()) {
      if (event.key === "Escape") { closeHelp(); closeModal(); event.preventDefault(); }
      return;
    }
    var tag = String((event.target && event.target.tagName) || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") { return; }
    if (event.metaKey || event.ctrlKey || event.altKey) { return; }

    var key = event.key;
    if (key === "ArrowRight" || key === "l") { goToStep(state.step + 1); }
    else if (key === "ArrowLeft" || key === "h") { goToStep(state.step - 1); }
    else if (key === "[") { stepCase(-1); }
    else if (key === "]") { stepCase(1); }
    else if (key >= "1" && key <= String(STEPS.length)) { goToStep(parseInt(key, 10) - 1); }
    else if (key === "o") { showView("overview"); }
    else if (key === "c") { openCase(state.caseNo); }
    else if (key === "s") { openStance(); }
    else if (key === "f") { toggleProjector(); }
    else if (key === "?" || key === "/") { renderHelp(); }
    else { return; }
    event.preventDefault();
  }

  // ---- provenance --------------------------------------------------------
  function renderProvenance() {
    var footer = document.getElementById("provenance");
    var p = DATA.provenance;
    var short = function (value, length) {
      if (!value) { return "n/a"; }
      return String(value).slice(0, length || 12);
    };
    var fields = [
      ["model", text(p.model) + (p.model === p.runtime_model ? "" : " (runtime model is " + p.runtime_model + ")")],
      ["git commit", short(p.git_commit)],
      ["prompts", short(p.prompts_sha256)],
      ["answer key", short(p.answer_key_sha256)],
      ["python", text(p.python_version)],
      ["run", text(p.started_at) + " to " + text(p.ended_at)],
      ["run dir", p.run_directory],
      // Said either way, and never left blank. "Did this run ask its own
      // advocates" is a question about the figures above, and a reader looking
      // for its answer must be able to find one whether the answer is yes or no.
      ["advocates", p.replay
        ? "replayed from " + text(p.replay.run_directory) + " at " + short(p.replay.git_commit) +
          // "in this invocation", because the count beside it is the last
          // invocation's and not the directory's: a run directory can hold
          // results from more than one, and the overview's own figure counts
          // every case on the page. Without the two words the page answers the
          // same question twice, with two different numbers and no way to tell
          // them apart.
          " for " + p.replay.replayed_cases + " case(s) in this invocation; only the judge was called" +
          // The commit named above is the source directory's, and for a replay
          // into that same directory it is the run that *copied* the advocates.
          // Naming the run that made them is what stops that one commit reading
          // as the advocates' own provenance.
          (p.replay.advocate_commits.length
            ? "; those advocates were made at " + p.replay.advocate_commits.map(function (commit) {
                return short(commit);
              }).join(", ")
            : "")
        : "called by this run"],
      ["invocations", String(p.invocation_count)]
    ];
    clear(footer);
    fields.forEach(function (pair) {
      footer.appendChild(h("span", null, [
        h("b", { text: pair[0] + ": " }),
        h("span", { text: pair[1] })
      ]));
    });
  }

  // ---- start -------------------------------------------------------------
  document.getElementById("nav-overview").addEventListener("click", function () { showView("overview"); });
  document.getElementById("nav-case").addEventListener("click", function () { showView("case"); });
  document.getElementById("nav-stance").addEventListener("click", function () { openStance(); });
  document.getElementById("toggle-projector").addEventListener("click", toggleProjector);
  document.getElementById("show-keys").addEventListener("click", renderHelp);
  document.addEventListener("keydown", onKeyDown);

  // The browser's own back button walks the steps: every navigation writes the
  // hash, and a hash this code did not write is applied exactly as asked.
  window.addEventListener("hashchange", function () {
    var next = hashState(window.location.hash);
    if (sameHashState(next, state)) { return; }
    applyHashState(next);
    refresh();
  });

  renderProvenance();
  renderOverview();

  // A link someone pasted wins over the default case. If the address bar
  // carries a view, that is the view being asked for.
  applyHashState(hashState(window.location.hash));
  refresh();
})();
"""

_BODY = """
<header class="top">
  <span class="brand">{brand}</span>
  <nav class="views">
    <button id="nav-overview" class="on">Overview</button>
    <button id="nav-case">One case</button>
    <button id="nav-stance">Stance</button>
  </nav>
  <a class="runs-link" href="{runs_index_link}">Runs</a>
  <span class="spacer"></span>
  <button id="toggle-projector" title="scale everything up for a projector">Projector</button>
  <button id="show-keys" title="keyboard shortcuts">?</button>
  <span class="badge">{badge}</span>
</header>
<main>
  <noscript>
    <p>This viewer renders itself from data embedded in this file, so it needs
    JavaScript enabled. It makes no network request of any kind.</p>
  </noscript>
  <div class="linkbar">
    <span class="what">A link to exactly this view, for the address bar or a slide:</span>
    <input id="link-input" readonly spellcheck="false" aria-label="link to this view">
  </div>
  <section id="view-overview"></section>
  <section id="view-case" hidden></section>
  <section id="view-stance" hidden></section>
</main>
<footer class="prov" id="provenance"></footer>
"""


def _body(set_block: Mapping[str, Any]) -> str:
    """The static half of one page, with the set's own words in it.

    Only three things here are the set's: the brand, the badge, and where the
    Runs link points. Everything else the page says about the set comes out of
    the data block, so the behavioural script is the same bytes on every page
    and the appendChild scan has one script to read rather than five.
    """
    return _BODY.format(
        brand=_escape_html(set_block.get("brand") or "Tribunal - debate viewer"),
        badge=_escape_html(set_block.get("badge") or "replay of a committed run"),
        runs_index_link=_escape_html(set_block.get("runs_index_link") or "runs/index.html"),
    )


def _escape_html(value: Any) -> str:
    """Text for an HTML context, escaped by the standard library."""
    return html.escape(str(value), quote=True)


def render_html(document: Mapping[str, Any]) -> str:
    """The whole page, as one string, from the document.

    Deterministic: the same document produces the same bytes, and nothing here
    reads the clock, the environment or the filesystem. ``sort_keys`` is on, so
    the embedded JSON does not depend on the order the document's keys happened
    to be built in, and ``allow_nan`` is off, because ``NaN`` is not JSON and a
    page that will not parse is worse than a build that refuses.

    ``<`` is escaped inside the embedded JSON. A ``</script>`` anywhere in the
    agents' own prose would otherwise end the data block early -- and the agents'
    prose is not ours to constrain.
    """
    set_block = document.get("set") or {}
    data = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).replace("<", "\\u003c")

    return "".join(
        [
            "<!DOCTYPE html>\n",
            '<html lang="en">\n<head>\n<meta charset="utf-8">\n',
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n',
            "<title>",
            _escape_html(set_block.get("title") or "Tribunal - debate viewer"),
            "</title>\n",
            "<style>\n",
            _CSS.strip(),
            "\n</style>\n</head>\n<body>\n",
            _body(set_block).strip(),
            '\n<script id="tribunal-data" type="application/json">',
            data,
            "</script>\n<script>\n",
            _JS.strip(),
            "\n</script>\n</body>\n</html>\n",
        ]
    )


# --------------------------------------------------------------------------
# The runs index
# --------------------------------------------------------------------------
# The order the index lists the pages in. The corpus first because it is the
# figure the submission reports; the two sealed sets together and after it,
# because they are the same kind of thing; the sample case last, because it is
# not graded.
_INDEX_ORDER = ("corpus", "codex", "wild", "wild-v2", "ryde-901")


def _page_link_from_index(name: str) -> str:
    """A link to one page, written on the index. The index is one level down."""
    relative = pages()[name].output_path.relative_to(DIST_DIR).as_posix()
    return "../" + relative


def _index_rows(documents: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """One row per built page, with the figures read out of its own document.

    Nothing here is typed in. The case count and the headline figure come from
    the document this build has just produced, so the index cannot print a
    figure the page it links to does not also print.
    """
    rows: List[Dict[str, Any]] = []
    for name in _INDEX_ORDER:
        document = documents.get(name)
        if document is None:
            continue
        set_block = document.get("set") or {}
        headline = document.get("headline") or {}
        exact = headline.get("exact")
        rows.append(
            {
                "name": name,
                "summary": set_block.get("summary"),
                "case_count": set_block.get("case_count"),
                "freeze_tag": set_block.get("freeze_tag"),
                "sealed": bool(set_block.get("sealed")),
                "graded": bool(set_block.get("has_key")),
                "figure": None if exact is None else exact.get("display"),
                "figure_label": (
                    None
                    if exact is None
                    else "four-field exact over the {0} cases of the set".format(
                        exact.get("total")
                    )
                ),
                "link": _page_link_from_index(name),
            }
        )
    return rows


def render_index(documents: Mapping[str, Mapping[str, Any]]) -> str:
    """The runs index: every page, its own figures, and a link to each.

    The sealed sets stand on rows of their own, with the tag their single run
    was made from. They are **never summed**, with each other or with anything
    else: one figure over 64 cases plus another over 20 is not a measurement of
    84 cases, and a total row here would say that it is.

    The figures are read out of the documents this build has just produced, so
    the index cannot disagree with any page it links to.
    """
    rows = _index_rows(documents)
    parts: List[str] = []
    for row in rows:
        badge = (
            '<span class="badge">' + _escape_html(row["freeze_tag"]) + "</span>"
            if row["freeze_tag"]
            else ""
        )
        figure = (
            _escape_html(row["figure"])
            if row["figure"] is not None
            else '<span class="null">not graded</span>'
        )
        note = (
            '<div class="sub">' + _escape_html(row["figure_label"]) + "</div>"
            if row["figure_label"]
            else ""
        )
        parts.append(
            "<tr>"
            '<td><a href="' + _escape_html(row["link"]) + '">'
            + _escape_html(row["name"])
            + "</a> " + badge + "</td>"
            "<td>" + _escape_html(row["summary"] or "") + "</td>"
            '<td class="num">' + _escape_html(row["case_count"]) + "</td>"
            '<td class="num">' + figure + note + "</td>"
            "</tr>"
        )
    return "".join(
        [
            "<!DOCTYPE html>\n",
            '<html lang="en">\n<head>\n<meta charset="utf-8">\n',
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n',
            "<title>Tribunal - the runs</title>\n",
            "<style>\n",
            _CSS.strip(),
            "\n</style>\n</head>\n<body>\n",
            '<header class="top">\n'
            '  <span class="brand">Tribunal - the runs</span>\n'
            "</header>\n",
            "<main>\n",
            "<h1>The runs</h1>\n",
            '<p class="lead">Every run the viewer draws, with the figure its own '
            "page reports. Each figure is computed from that run, and the two "
            "sealed sets are never added to each other or to anything else: one "
            "figure over 64 cases plus another over 20 is not a measurement of "
            "84 cases.</p>\n",
            '<div class="table-wrap">\n<table>\n',
            "<thead><tr><th>Set</th><th>What it is</th><th>Cases</th>"
            "<th>Headline figure</th></tr></thead>\n",
            "<tbody>\n",
            "\n".join(parts),
            "\n</tbody>\n</table>\n</div>\n",
            "</main>\n",
            "</body>\n</html>\n",
        ]
    )


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def _report_refusals(document: Mapping[str, Any]) -> None:
    """Say on the terminal which cases were refused, and why."""
    refused = document.get("refused_cases") or []
    if not refused:
        return
    print("refused {0} case(s):".format(len(refused)))
    for entry in refused:
        print(
            "  case {0}: {1}\n    recorded {2}\n    rebuilt  {3}".format(
                entry["case_no"],
                entry["reason"],
                entry["recorded_brief_sha256"],
                entry["rebuilt_brief_sha256"],
            )
        )


def _write_or_check(
    destination: Path, text: str, check: bool, what: str
) -> int:
    """Write one built file, or compare it with what is on disk. 0 on success."""
    if check:
        if not destination.is_file():
            print("{0} does not exist; run the build".format(destination))
            return 1
        committed = destination.read_text(encoding="utf-8")
        if committed != text:
            print(
                "{0} differs from a fresh build ({1} bytes on disk, {2} bytes "
                "rebuilt)".format(
                    destination,
                    len(committed.encode("utf-8")),
                    len(text.encode("utf-8")),
                )
            )
            return 1
        print(
            "{0} is identical to a fresh build ({1} bytes)".format(
                destination, len(text.encode("utf-8"))
            )
        )
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    print(
        "wrote {0}: {1}, {2} bytes".format(
            destination, what, len(text.encode("utf-8"))
        )
    )
    return 0


def _refuse_a_sealed_destination(destination: Path) -> bool:
    """Refuse a destination before anything is read or built. True when refused."""
    try:
        sealed_roots.refuse_a_sealed_destination(destination)
    except sealed_roots.SealedDestinationError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return True
    return False


def _build_one_page(
    page: ViewerPage,
    run_dir: Optional[str] = None,
    out: Optional[str] = None,
    check: bool = False,
) -> int:
    """Build one page, or check it. The page's own path unless ``out`` names one."""
    destination = Path(page.output_path if out is None else out)
    # The page's destination is the caller's to name, so it is refused before
    # the run is read and before anything is built. The rule is
    # :mod:`eval.sealed_roots`'s, so this command and every other one that
    # writes to a path a caller names refuse the same paths.
    if _refuse_a_sealed_destination(destination):
        return 1
    try:
        document = build_document(run_dir=run_dir, page=page)
    except BuildError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1
    _report_refusals(document)
    return _write_or_check(
        destination,
        render_html(document),
        check,
        "{0} cases".format(len(document["cases"])),
    )


def _build_every_page(check: bool = False) -> int:
    """Every page, plus the index beside them. Non-zero if anything failed."""
    status = 0
    documents: Dict[str, Dict[str, Any]] = {}
    for name in _INDEX_ORDER:
        page = pages()[name]
        if _refuse_a_sealed_destination(Path(page.output_path)):
            return 1
        try:
            document = build_document(page=page)
        except BuildError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        _report_refusals(document)
        documents[name] = document
        status |= _write_or_check(
            Path(page.output_path),
            render_html(document),
            check,
            "{0} cases".format(len(document["cases"])),
        )
    if _refuse_a_sealed_destination(INDEX_PATH):
        return 1
    status |= _write_or_check(
        INDEX_PATH, render_index(documents), check, "{0} pages".format(len(documents))
    )
    return 0 if status == 0 else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--set",
        dest="set_name",
        default=None,
        help=(
            "which page to build: {0}. With no --set, every page is built, plus "
            "the index beside them.".format(", ".join(sorted(pages())))
        ),
    )
    parser.add_argument(
        "--run-dir", default=None, help="the run to replay, overriding the set's own"
    )
    parser.add_argument(
        "--out", default=None, help="where to write the page, overriding the set's own"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the file on disk with a fresh build and write nothing",
    )
    args = parser.parse_args(argv)

    known = pages()
    if args.set_name is not None and args.set_name not in known:
        print(
            "FATAL: {0!r} is not a page; the pages are {1}".format(
                args.set_name, ", ".join(sorted(known))
            ),
            file=sys.stderr,
        )
        return 1
    if args.set_name is None:
        if args.run_dir is not None or args.out is not None:
            print(
                "FATAL: --run-dir and --out name one page's inputs; give --set "
                "as well, or neither",
                file=sys.stderr,
            )
            return 1
        return _build_every_page(check=args.check)
    return _build_one_page(
        known[args.set_name],
        run_dir=args.run_dir,
        out=args.out,
        check=args.check,
    )


if __name__ == "__main__":
    raise SystemExit(main())
