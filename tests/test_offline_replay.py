"""The offline replay: the same requests, the same record, given the same answers.

The claim this module exists to check is narrow and load-bearing: **no individual
request body this system sends to a model changed** when the calls were made
concurrent. Concurrency decides *when* a call is made; it must not decide *what*
is asked or *how* the answer is written down. It does not follow that the two
modes send the same *set* of requests -- parallel mode can spend up to two driver
requests after the rider fails, and the remaining draft requests after a draft
raises -- and this module is a statement about the bodies, not about the set.

The proof is a replay. The four sets' main recorded runs (128 cases) hold, per
case, the transcript of every call it made: the digests of the two prompts, the
raw answer, the usage figures and the timestamp. This module loads those files
and serves each recorded ``response_text`` back through a transport, in a
synthetic envelope carrying the recorded usage numbers, so a full arbitration
can be run again with **no model call at all**. Each case is then run twice --
once sequentially, once with ``parallel_calls`` on -- and both runs are held
against the recording.

**The coverage, stated exactly.** The transport keys every one of the **784**
requests the four sets' recordings hold by ``(sha256(system), sha256(user),
temperature, seed)``, so all 784 are checked on those four fields. A full-body
digest exists for **148** of them, because each run's ``calls.json`` is rewritten
by every invocation and holds only the last one; those 148 are pinned by
:meth:`OfflineReplayTests.test_every_recorded_request_is_reproduced`. The
verifier is **never** replayed: every committed run was made with the verifier
off, so no recording holds a verifier call. And the arms that are not replayed at
all are the ablation, the ``policy-v2`` run, ``hy3``, ``hy4-preview``,
``deepseek-v4.1-flash`` (case 105), ``rerun-2026-09-29/external/ryde`` (case 901),
``external``, and the ``_icloud-incident-2026-09-27`` archive.

What each assertion buys:

* the transport keys every request by ``(sha256(system), sha256(user),
  temperature, seed)``, so a request whose prompts differ by one byte finds no
  recording and the run stops. That is the "no individual request body changed"
  check;
* the request-body digests the transport computes must include every digest in
  the run's committed ``calls.json``, so the replay is tied to the record the
  committed run actually wrote;
* every transcript entry must equal the recorded entry, field for field, with
  only the clock and the replay note normalised;
* the ruling, the vote, the referee's ledger and the brief digest must equal
  what the recording holds;
* the parallel run's event log must be byte-identical to the sequential run's.

The runs are driven through :func:`tribunal.pipeline.run_case` with a pinned
``now`` and a clock pinned at zero, so nothing here depends on the wall clock
and the whole module takes a few seconds.

Run from the project root with::

    python -m unittest tests.test_offline_replay -v
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets  # noqa: E402
from tests import portability  # noqa: E402
from tribunal import events, llm, money, pipeline, transcript  # noqa: E402

# A key that is unmistakable if it ever turns up where it should not. No request
# leaves this process: the transport answers every one of them from a recording.
FAKE_KEY = "tok-live-FAKEKEY-0123456789abcdef-DO-NOT-LEAK"

PINNED_NOW = "2026-10-06T00:00:00+00:00"
RUNS_DIR = PROJECT_ROOT / "runs"

# The model every recorded run was made on. A run directory is
# ``runs/<subdir>/<model>/``, so this is needed to find the files at all -- which
# is why it is a constant here and why a test checks it against what each
# ``run.json`` says rather than reading it out of one.
MODEL = "deepseek/deepseek-flash"

# The four sets whose recorded runs are replayed, in the order the report prints
# them. ``wild`` is the held-out set: its 64 cases include the two that produced
# no ruling, and those two must still fail in the same place.
SET_NAMES = ("corpus", "codex", "wild", "wild-v2")

# Every recorded run was made with four judge drafts. The constant is not taken
# on trust: ``test_every_recorded_run_is_the_one_this_module_replays`` reads it
# back out of each run's own transcripts.
JUDGE_VOTES = 4

# The two per-call fields a replay cannot reproduce, and must not try to.
# ``timestamp`` is when a call finished and ``duration_seconds`` is how long it
# took: this module answers from a file, so both are the replay's own and
# neither is a claim about the run being checked. The note is normalised too --
# see :data:`REPLAY_NOTE_PREFIX`.
CLOCK_FIELDS = ("timestamp", "duration_seconds")

# What a copied entry says in place of its own note. A run that replayed its
# advocates wrote this into the advocate entries, so those entries no longer
# record whether the original answer was usable; the replay's own run is a full
# run and writes ``None`` there. Normalising the two together is the only honest
# comparison, and it is why the note is in this list rather than compared as it
# stands. An entry that is *not* a replay note -- an unusable answer's own note,
# for instance -- is still compared exactly.
REPLAY_NOTE_PREFIX = "replayed from "


# --------------------------------------------------------------------------
# Reading a recording
# --------------------------------------------------------------------------
def read_json(path: Path):
    """One recorded file, with every JSON number carrying a point a ``Decimal``.

    The recordings were written by the canonical serialiser, which writes a
    ``Decimal`` as a JSON number literal. Reading them with the default float
    parser would turn ``4.00`` into a binary float and the comparison against
    this run's own ``Decimal`` would fail on a value that never changed.
    """
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)


def as_recorded(value):
    """A value re-read the way a recording is read: JSON numbers as ``Decimal``.

    A value this run computed in memory can hold a ``float`` where the same
    value, read back from a recording, holds a ``Decimal`` -- the vote's
    ``agreement`` is one, because the pipeline divides two integers. Both are
    the same number written the same way, so serialising through the canonical
    form and reading it back with ``parse_float=Decimal`` puts the two sides in
    one representation and makes the comparison about the value rather than
    about which of the two types happened to carry it.
    """
    return json.loads(money.dumps_canonical(value), parse_float=Decimal)


def _number(value):
    """A request's numeric setting, comparable across ``Decimal`` and ``float``.

    A draft's temperature read from a recording is ``Decimal("0.7")``; the same
    value inside a request body is the float ``0.7``, and the two are not equal.
    Both are put through their own shortest decimal text, which is the same text
    for the same number.
    """
    if value is None:
        return None
    return Decimal(str(value))


def envelope(entry):
    """The recorded answer, wrapped in the envelope a provider would send.

    The usage numbers are the recorded ones rather than invented, so the tokens
    the replay accounts for are the tokens the recorded run was billed for. The
    status is the recorded status, which for every entry in every committed run
    is a 200.
    """
    payload = {
        "choices": [{"message": {"content": entry["response_text"]}}],
        "usage": {
            "prompt_tokens": entry["prompt_tokens"],
            "completion_tokens": entry["completion_tokens"],
            "completion_tokens_details": {"reasoning_tokens": entry["reasoning_tokens"]},
            "prompt_tokens_details": {"cached_tokens": entry["cached_tokens"]},
        },
    }
    return llm.HttpResult(
        status=entry.get("status") or 200,
        body=json.dumps(payload).encode("utf-8"),
    )


def transcript_path(run_dir: Path, case_no: int) -> Path:
    return Path(run_dir) / "case-{0:05d}.transcript.json".format(case_no)


def recordings_for(document):
    """``(key, entry)`` for every recorded entry, in the order it was recorded.

    The key is what the transport matches a request against: the digests of the
    two prompts, and the two per-call settings. The settings are the client's
    own -- ``0.0`` and ``42`` -- for every entry a draft does not own, and are
    read off the draft for every entry it does. A draft's entries are the ones
    it occupies, which is one entry for a usable draft and two for one whose
    first answer was unusable.
    """
    entries = document["entries"]
    per_entry = {}
    vote = document.get("vote")
    if vote:
        for draft in vote["drafts"]:
            for index in draft["entries"]:
                per_entry[index] = (draft["temperature"], draft["seed"])
    for index, entry in enumerate(entries):
        temperature, seed = per_entry.get(index, (0.0, 42))
        yield (
            entry["system_sha256"],
            entry["user_sha256"],
            _number(temperature),
            _number(seed),
        ), entry


class RecordedTransport:
    """Answers each request from the recording that belongs to it.

    Nothing is answered by arrival order, because there is no arrival order: two
    calls in flight together arrive in whichever order the operating system
    chooses. A request is matched by what it asks -- the two prompt digests and
    the two settings -- and a key asked more than once is answered from a FIFO,
    which is what a shape retry needs.

    ``digests`` is every full request body this transport was handed, hashed the
    way the client hashes one. ``leftover`` is what a caller checks to prove no
    recorded answer went unused. ``bodies`` is each body minus its messages,
    beside the key it was answered from, the role the recording gives that call,
    and the position the pipeline published on this thread for it -- read off
    ``pipeline.CALL_CONTEXT``, so a test knows which case, role, draft and
    attempt made the request rather than inferring them from the body it is
    checking.

    Every counter and every collection here is touched from whichever worker
    thread is completing a request -- with the calls in flight together that is
    not one thread -- so all of them are read and written under one lock. The
    lock is held for the bookkeeping and for one queue pop and nothing else, so
    it does not serialise the answer a caller gets.
    """

    def __init__(self, recordings) -> None:
        self.lock = threading.Lock()
        self.threads = set()
        self.bodies = []
        self.queues = {}
        self.recorded = 0
        for key, entry in recordings:
            self.queues.setdefault(key, []).append(entry)
            self.recorded += 1
        self.digests = set()
        self.served = 0
        self.unmatched = []

    def __call__(self, url, headers, body, timeout):
        request = json.loads(body.decode("utf-8"))
        with self.lock:
            self.threads.add(threading.get_ident())
            self.digests.add(hashlib.sha256(body).hexdigest())
        key = (
            transcript.sha256_text(request["messages"][0]["content"]),
            transcript.sha256_text(request["messages"][1]["content"]),
            _number(request.get("temperature")),
            _number(request.get("seed")),
        )
        with self.lock:
            queue = self.queues.get(key)
            if not queue:
                self.unmatched.append(key)
                raise AssertionError(
                    "no recorded answer for a request keyed {0!r}: the replay is "
                    "asking something the recorded run never asked".format(key)
                )
            entry = queue.pop(0)
            self.served += 1
            # The body minus its messages, beside the recording it was answered
            # from, the key it was matched by, and the position the pipeline
            # published on this thread. What the request said about itself is a
            # fact about the replay; the key is what the recording says that
            # call was, and the position is what the run says it was. Kept
            # together so all three can be compared.
            self.bodies.append(
                {
                    "call": pipeline.CALL_CONTEXT.get(),
                    "body": {
                        name: value
                        for name, value in request.items()
                        if name != "messages"
                    },
                    "key": key,
                    "role": entry.get("role"),
                }
            )
        return envelope(entry)

    def leftover(self) -> int:
        with self.lock:
            return sum(len(queue) for queue in self.queues.values())


# --------------------------------------------------------------------------
# Comparing a replayed run with its recording
# --------------------------------------------------------------------------
def comparable(entry):
    """One entry with the clock and the replay note normalised.

    Everything else is kept exactly as it stands. ``shape``, ``parse_outcome``,
    ``parsed``, the usage figures, ``attempts``, ``status`` and the two digests
    are all fields a wrong implementation would move, and none of them is
    normalised.
    """
    written = dict(entry)
    for name in CLOCK_FIELDS:
        written.pop(name, None)
    note = written.get("note")
    if isinstance(note, str) and note.startswith(REPLAY_NOTE_PREFIX):
        written["note"] = None
    return written


def entry_differences(recorded, produced):
    """Which fields of one entry differ, named."""
    left = comparable(recorded)
    right = comparable(produced)
    return sorted(
        name
        for name in set(left) | set(right)
        if left.get(name) != right.get(name)
    )


def transcript_differences(recorded_entries, produced_entries):
    """Every difference between a recording and a replay, one line each.

    An empty list means the two records are the same call for call, field for
    field. The index and the recorded role are named so a failure says which
    call moved rather than only that something did.
    """
    differences = []
    if len(recorded_entries) != len(produced_entries):
        differences.append(
            "entry count: recorded {0}, replayed {1}".format(
                len(recorded_entries), len(produced_entries)
            )
        )
    for index, (recorded, produced) in enumerate(zip(recorded_entries, produced_entries)):
        for name in entry_differences(recorded, produced):
            differences.append(
                "entry {0} ({1}): {2} differs".format(
                    index, recorded.get("role"), name
                )
            )
    return differences


# --------------------------------------------------------------------------
# Running a set twice
# --------------------------------------------------------------------------
class Replayed:
    """One set, replayed once in one mode, with everything the tests compare."""

    def __init__(self, development_set, model, parallel, results, transport, documents):
        self.development_set = development_set
        self.model = model
        self.parallel = parallel
        self.results = results
        self.transport = transport
        self.documents = documents

    @property
    def name(self):
        return self.development_set.name

    @property
    def mode(self):
        return "parallel" if self.parallel else "sequential"


def replay_set(development_set, model, *, parallel, events_path=None, cases=None):
    """Run cases of one set against their recordings, in one mode.

    ``now`` is pinned and the clock is pinned at zero, so a call takes no time
    and every timestamp is the same one: the two modes then differ in nothing
    that a comparison could see, which is the point. The recordings are read
    once, before any case runs, and the transport refuses any request they do
    not cover.

    ``cases`` defaults to the whole set, less case 111 on a platform whose libm
    cannot rebuild its brief (``tests/portability.py`` says which and why). A
    control that needs one case passes one, so a guard can be shown to fire
    without replaying a hundred cases.
    """
    run_dir = development_set.run_dir(model, RUNS_DIR)
    if cases is None:
        cases = list(development_set.cases)
        if (
            portability.the_case_111_platform_difference()
            and portability.CASE_111 in cases
        ):
            # Case 111's brief cannot be rebuilt here, so its recorded prompts
            # cannot be reproduced: it is left out rather than replayed against a
            # digest this machine cannot make, and the count below says so.
            cases = [case_no for case_no in cases if case_no != portability.CASE_111]
    else:
        cases = list(cases)
    documents = {}
    recordings = []
    for case_no in cases:
        document = read_json(transcript_path(run_dir, case_no))
        documents[case_no] = document
        recordings.extend(recordings_for(document))

    transport = RecordedTransport(recordings)
    client = llm.LLMClient(
        model=model,
        api_key=FAKE_KEY,
        transport=transport,
        sleep=lambda seconds: None,
        clock=lambda: 0.0,
    )
    log = None
    if events_path is not None:
        log = events.EventLog(
            Path(events_path), invocation_id="offline-replay", now=lambda: PINNED_NOW
        )

    results = {}
    for case_no in cases:
        results[case_no] = pipeline.run_case(
            case_no,
            client,
            case_loader=development_set.load_case,
            judge_votes=JUDGE_VOTES,
            policy_version=development_set.policy_version,
            now=lambda: PINNED_NOW,
            clock=lambda: 0.0,
            events_log=log,
            parallel_calls=parallel,
        )
    return Replayed(development_set, model, parallel, results, transport, documents)


def recorded_run_json(development_set):
    """The set's own ``run.json``."""
    return read_json(development_set.run_dir(MODEL, RUNS_DIR) / "run.json")


class OfflineReplayTests(unittest.TestCase):
    """Both modes, over all four recorded sets, held against the recordings."""

    @classmethod
    def setUpClass(cls):
        cls.temporary = Path(tempfile.mkdtemp(prefix="tribunal-offline-replay-"))
        cls.replayed = {}
        cls.models = {}
        for name in SET_NAMES:
            development_set = development_sets.BY_NAME[name]
            cls.models[name] = MODEL
            for parallel in (False, True):
                mode = "parallel" if parallel else "sequential"
                cls.replayed[(name, parallel)] = replay_set(
                    development_set,
                    cls.models[name],
                    parallel=parallel,
                    events_path=cls.temporary / "{0}-{1}.jsonl".format(name, mode),
                )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temporary, ignore_errors=True)

    def each(self, name):
        """The two modes of one set, in a fixed order."""
        return [self.replayed[(name, False)], self.replayed[(name, True)]]

    # -- the rig ----------------------------------------------------------
    def test_every_recorded_run_is_the_one_this_module_replays(self):
        """The model and the vote count are read back, not assumed.

        ``JUDGE_VOTES`` is a module constant, and a constant that has drifted
        from the recordings would make every replay below a measurement of a
        different run. Both are checked against the files instead.
        """
        for name in SET_NAMES:
            with self.subTest(set=name):
                self.assertEqual(
                    MODEL, recorded_run_json(development_sets.BY_NAME[name])["model"]
                )
                for case_no, document in self.replayed[(name, False)].documents.items():
                    with self.subTest(set=name, case=case_no):
                        self.assertEqual(JUDGE_VOTES, document["vote"]["votes"])
                        self.assertEqual(
                            self.models[name], document["entries"][0]["model"]
                        )

    # -- no byte of any request changed -----------------------------------
    def test_every_recorded_request_is_reproduced(self):
        """The replay's request bodies cover every digest the run recorded.

        This is the claim in the user's own words. Each committed run's
        ``calls.json`` holds the sha256 of the full request body of every call
        that invocation made; the transport hashes every body it is handed, the
        same way. If one byte of one request had moved, its digest would be
        different and would not be found here.
        """
        for name in SET_NAMES:
            run_dir = development_sets.BY_NAME[name].run_dir(self.models[name], RUNS_DIR)
            recorded = {
                record["request_sha256"]
                for record in read_json(run_dir / "calls.json")["calls"]
            }
            self.assertTrue(recorded, "{0}: calls.json holds no calls".format(name))
            for replayed in self.each(name):
                with self.subTest(set=name, mode=replayed.mode):
                    missing = recorded - replayed.transport.digests
                    self.assertEqual(
                        set(),
                        missing,
                        "the {0} run did not reproduce {1} recorded request(s)".format(
                            replayed.mode, len(missing)
                        ),
                    )

    def test_the_parallel_replay_really_overlaps(self):
        """A parallel run of one case has both advocates in flight at once.

        The whole point of comparing the two modes is that the calls overlap, and
        a "parallel" run that made every call on one thread would be a comparison
        of the sequential path with itself. The transport records the thread each
        request was made on, so the overlap is measured rather than assumed. One
        case is enough: the advocate pool is two workers wide and both advocates
        are submitted together, so the first case of the corpus shows it.
        """
        development_set = development_sets.BY_NAME["corpus"]
        for case_no in development_set.cases:
            replayed = replay_set(
                development_set, MODEL, parallel=True, cases=(case_no,)
            )
            if len(replayed.transport.threads) > 1:
                return
        self.fail("the parallel replay never called the transport on two worker threads")

    def test_request_body_settings_match_each_role_and_draft_kind(self):
        """Every request's non-message body is the settings the run made it with.

        A request body carries the model, the temperature, the seed and the
        response format beside the two messages, and nothing else. The position
        each request was made at is read off ``pipeline.CALL_CONTEXT`` -- the
        case, the role, the draft and the attempt the pipeline published on that
        thread -- so what a request *is* comes from the run rather than from the
        body being checked. The settings are then asserted by name: the client's
        own ``0.0`` and ``42`` for both advocates and for the position-swapped
        draft, and ``0.7`` with the draft's own recorded seed for a sampled one.

        Run over **both modes**. A setting that moved in one mode only is still a
        request that changed, and this is the half of "no individual request body
        changed" that the prompt digests cannot see.

        **The coverage, stated exactly.** Only 148 of the 784 recorded bodies
        have a digest in their run's ``calls.json`` (142 distinct), because that
        file holds only the run's **last** invocation while the transcript holds
        every invocation that ever wrote into the directory. The prompts of the
        earlier invocations are still checked, by the entry comparison; their
        settings are checked here, which reads the bodies themselves and does not
        depend on a digest. The argument that closes the rest of the gap is that
        ``tribunal/llm.py`` is unchanged and the worker hands ``client.complete``
        the same arguments it always did, so the body is built by the same code
        from the same inputs.
        """
        zero, default_seed = Decimal("0.0"), Decimal("42")
        for name in SET_NAMES:
            for parallel in (False, True):
                replayed = self.replayed[(name, parallel)]
                with self.subTest(set=name, mode=replayed.mode):
                    self.assertTrue(
                        replayed.transport.bodies,
                        "{0}: the replay made no request".format(name),
                    )
                    temperatures = {}
                    for record in replayed.transport.bodies:
                        call = record["call"]
                        body = record["body"]
                        self.assertIsNotNone(
                            call, "a request carried no position on its thread"
                        )
                        case_no, role, draft, attempt = call
                        self.assertIn(case_no, replayed.results)
                        self.assertEqual(
                            {"model", "temperature", "seed", "response_format"},
                            set(body),
                            "a request body carries more than the four settings",
                        )
                        self.assertEqual(MODEL, body["model"])
                        self.assertEqual(
                            {"type": "json_object"}, body["response_format"]
                        )
                        if role in (
                            transcript.ROLE_RIDER_ADVOCATE,
                            transcript.ROLE_DRIVER_ADVOCATE,
                        ):
                            self.assertEqual(0, draft)
                            kind = None
                            expected = (zero, default_seed)
                        else:
                            self.assertEqual(transcript.ROLE_JUDGE, role)
                            if draft == JUDGE_VOTES:
                                kind = "position_swapped"
                                expected = (zero, default_seed)
                            else:
                                kind = "sampled"
                                expected = (
                                    _number(pipeline.JUDGE_VOTE_TEMPERATURE),
                                    _number(pipeline.JUDGE_VOTE_SEEDS[draft - 1]),
                                )
                        self.assertEqual(
                            expected,
                            (_number(body["temperature"]), _number(body["seed"])),
                            "{0} sent settings the run does not make".format(call),
                        )
                        temperatures.setdefault((role, kind), set()).add(
                            _number(body["temperature"])
                        )
                    for group, values in temperatures.items():
                        self.assertEqual(
                            1,
                            len(values),
                            "{0} sent more than one temperature: {1}".format(
                                group, values
                            ),
                        )

    def test_no_request_goes_unanswered_and_no_recording_is_left_unused(self):
        """The transport is a closed system, and it has to balance.

        A request with no recording raises, so a run that completed at all
        answered every request it made. What is left to check is the other
        direction: an answer recorded and never used would mean the replay asked
        fewer questions than the run did.
        """
        for name in SET_NAMES:
            for replayed in self.each(name):
                with self.subTest(set=name, mode=replayed.mode):
                    self.assertEqual(
                        0, replayed.transport.leftover(), "a recorded answer went unused"
                    )
                    self.assertEqual(
                        replayed.transport.recorded, replayed.transport.served
                    )
                    self.assertEqual([], replayed.transport.unmatched)

    # -- the record -------------------------------------------------------
    def test_every_transcript_entry_matches_the_recording(self):
        for name in SET_NAMES:
            for replayed in self.each(name):
                for case_no, result in replayed.results.items():
                    with self.subTest(set=name, mode=replayed.mode, case=case_no):
                        differences = transcript_differences(
                            replayed.documents[case_no]["entries"],
                            [entry.as_dict() for entry in result.transcript.entries],
                        )
                        self.assertEqual([], differences)

    def test_the_ruling_the_vote_and_the_referee_match_the_recording(self):
        """What the run concluded, not only what it was told.

        Both sides go through :func:`as_recorded` first. The recordings were
        read with ``parse_float=Decimal``, so a number the recording holds with
        a point comes back as a ``Decimal`` while the same number computed here
        -- the vote's ``agreement`` is the one that bites -- is a ``float``.
        Writing both through the canonical form puts them in one representation
        and makes the comparison about the value, which is what the recording
        is evidence about.
        """
        for name in SET_NAMES:
            run_dir = development_sets.BY_NAME[name].run_dir(self.models[name], RUNS_DIR)
            for replayed in self.each(name):
                for case_no, result in replayed.results.items():
                    recorded = replayed.documents[case_no]
                    with self.subTest(set=name, mode=replayed.mode, case=case_no):
                        self.assertEqual(
                            as_recorded(recorded["vote"]),
                            as_recorded(result.judge_vote),
                        )
                        self.assertEqual(
                            as_recorded(recorded["referee"]),
                            as_recorded(result.referee),
                        )
                    case_file = run_dir / "case-{0:05d}.json".format(case_no)
                    if not case_file.exists():
                        # A case that produced no ruling has no result file; its
                        # vote is compared above, which is the record of why.
                        continue
                    recorded_case = read_json(case_file)
                    with self.subTest(set=name, mode=replayed.mode, case=case_no):
                        self.assertEqual(
                            as_recorded(recorded_case["ruling"]),
                            as_recorded(result.ruling),
                        )
                        self.assertEqual(
                            as_recorded(recorded_case["referee"]),
                            as_recorded(result.referee),
                        )
                        self.assertEqual(
                            as_recorded(recorded_case["ruling_findings"]),
                            as_recorded(result.ruling_findings),
                        )

    def test_the_brief_digest_matches_the_recording(self):
        portability.require_the_same_libm()
        for name in SET_NAMES:
            run_dir = development_sets.BY_NAME[name].run_dir(self.models[name], RUNS_DIR)
            for replayed in self.each(name):
                for case_no, result in replayed.results.items():
                    case_file = run_dir / "case-{0:05d}.json".format(case_no)
                    if not case_file.exists():
                        continue
                    with self.subTest(set=name, mode=replayed.mode, case=case_no):
                        self.assertEqual(
                            read_json(case_file)["brief_sha256"], result.brief_sha256
                        )

    def test_the_cases_with_no_ruling_still_fail_at_the_judge(self):
        """The two held-out cases the record says produced nothing.

        Replaying them must not quietly produce a ruling. Both failed because
        every draft was rejected by the draft check, and the same answers must
        produce the same failure in both modes.
        """
        for replayed in self.each("wild"):
            for case_no in (517, 533):
                with self.subTest(mode=replayed.mode, case=case_no):
                    result = replayed.results[case_no]
                    self.assertFalse(result.ok)
                    self.assertEqual(transcript.ROLE_JUDGE, result.failed_agent)
                    self.assertIsNone(result.ruling)
                    self.assertEqual(
                        as_recorded(replayed.documents[case_no]["vote"]),
                        as_recorded(result.judge_vote),
                    )
                    self.assertEqual(0, result.judge_vote["valid"])

    # -- the event log ----------------------------------------------------
    def test_the_parallel_events_equal_the_sequential_events(self):
        """The log is a deliverable too, and concurrency must not reorder it.

        The two runs of a set are identical in every request and every answer,
        and their clocks are pinned, so the two files must be the same bytes.
        A line whose order moved with the network would show up here.
        """
        for name in SET_NAMES:
            with self.subTest(set=name):
                sequential = (self.temporary / "{0}-sequential.jsonl".format(name)).read_bytes()
                parallel = (self.temporary / "{0}-parallel.jsonl".format(name)).read_bytes()
                self.assertTrue(sequential, "the sequential log is empty")
                self.assertEqual(sequential, parallel)

    def test_the_two_modes_reach_the_same_answers(self):
        """A guard on everything above: the two modes are the same measurement."""
        for name in SET_NAMES:
            sequential, parallel = self.each(name)
            with self.subTest(set=name):
                self.assertEqual(
                    {case_no: result.ok for case_no, result in sequential.results.items()},
                    {case_no: result.ok for case_no, result in parallel.results.items()},
                )
                for case_no in sequential.results:
                    self.assertEqual(
                        sequential.results[case_no].ruling,
                        parallel.results[case_no].ruling,
                    )


# --------------------------------------------------------------------------
# Negative controls
# --------------------------------------------------------------------------
class NegativeControlTests(unittest.TestCase):
    """Each check is shown to fire on a record that is wrong in one way.

    A comparison nobody has seen fail is not evidence of anything. Each control
    below takes one real case and one real recording, changes exactly one thing
    -- the thing the control names -- and asserts that the check the replay
    relies on reports it. The three are the three ways a wrong implementation
    could still send a request that looks right:

    * the advocates written in the order they finished rather than in the
      case's own order;
    * two drafts' seeds exchanged;
    * the judge's sampling temperature moved off ``0.7``.

    Completion order is caught by entries and event bytes; seed swaps by
    entries and vote; temperature changes by the transport's keying.
    """

    CASE = 101

    @classmethod
    def setUpClass(cls):
        cls.development_set = development_sets.BY_NAME["corpus"]
        cls.model = MODEL
        run_dir = cls.development_set.run_dir(cls.model, RUNS_DIR)
        cls.document = read_json(transcript_path(run_dir, cls.CASE))

    def replay(self, *, parallel=False, events_path=None):
        return replay_set(
            self.development_set,
            self.model,
            parallel=parallel,
            events_path=events_path,
            cases=(self.CASE,),
        )

    def test_the_replay_catches_advocates_written_in_completion_order(self):
        """The driver's entry written first must be reported, not accepted.

        The mistake is driven through the **parallel** path, with the write order
        patched so the driver's entry is written before the rider's -- which is
        what a run that wrote each answer as it came back would do. Two of the
        replay's checks have to fire: the entry comparison, which names the field
        that moved, and the byte comparison of the two runs' event logs, which is
        the log's own order. A control that only fed the comparison a
        hand-reordered list would prove the comparison works and nothing about
        the run.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            replayed = self.replay(parallel=True, events_path=path)
            produced = [
                entry.as_dict() for entry in replayed.results[self.CASE].transcript.entries
            ]
            self.assertEqual([], transcript_differences(self.document["entries"], produced))
            in_order_bytes = path.read_bytes()

            original = pipeline._write_agent_call
            held = []

            def reverse_write(call, **kwargs):
                if call.role == transcript.ROLE_RIDER_ADVOCATE:
                    held.append((call, kwargs))
                    return call.value, None
                result = original(call, **kwargs)
                if call.role == transcript.ROLE_DRIVER_ADVOCATE:
                    for waiting_call, waiting_kwargs in held:
                        original(waiting_call, **waiting_kwargs)
                    held.clear()
                return result

            reordered_path = Path(directory) / "reordered.jsonl"
            with mock.patch.object(
                pipeline, "_write_agent_call", side_effect=reverse_write
            ):
                reordered = self.replay(parallel=True, events_path=reordered_path)

            self.assertTrue(
                transcript_differences(
                    self.document["entries"],
                    [
                        entry.as_dict()
                        for entry in reordered.results[self.CASE].transcript.entries
                    ],
                ),
                "a swapped write order was not reported by the entry comparison",
            )
            self.assertNotEqual(
                in_order_bytes,
                reordered_path.read_bytes(),
                "a swapped write order did not move the event log's bytes",
            )

    def test_the_replay_catches_the_drafts_seeds_swapped(self):
        """Swapped seeds are caught by entry and vote comparison, not transport keying."""
        with mock.patch.object(
            pipeline, "JUDGE_VOTE_SEEDS", (202, 101, 303, 404, 505, 606)
        ):
            replayed = self.replay()

        recorded = self.document["vote"]["drafts"]
        produced = replayed.results[self.CASE].judge_vote["drafts"]

        self.assertTrue(transcript_differences(self.document["entries"], [
            entry.as_dict() for entry in replayed.results[self.CASE].transcript.entries
        ]), "a swapped seed did not change transcript entries")
        self.assertNotEqual(as_recorded(recorded), as_recorded(produced), "a swapped seed was not reported")
        self.assertEqual(202, produced[0]["seed"])
        self.assertEqual(101, recorded[0]["seed"])

    def test_the_replay_catches_a_judge_temperature_that_moved(self):
        """A temperature off the recorded one is a different request."""
        with mock.patch.object(pipeline, "JUDGE_VOTE_TEMPERATURE", 0.71):
            with self.assertRaises(AssertionError) as caught:
                self.replay()

        self.assertIn("no recorded answer for a request", str(caught.exception))

    def test_a_recorded_decimal_and_a_request_float_are_the_same_number(self):
        """Why the key normalises the settings instead of comparing them.

        The recordings are read with ``parse_float=Decimal``, so a sampled
        draft's temperature comes back as ``Decimal("0.7")``; the same setting
        inside a request body is the float ``0.7``. The two are not equal in
        Python, so a key that compared them as they stand would find no
        recording for any sampled draft at all -- every case would fail, which
        would be a failure about the type rather than about the run.
        """
        self.assertNotEqual(0.7, Decimal("0.7"))
        self.assertEqual(Decimal("0.7"), _number(0.7))
        self.assertEqual(_number(0.7), _number(Decimal("0.7")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
