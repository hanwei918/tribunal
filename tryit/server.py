"""The live "try it" service: a visitor's scenario, run through the real pipeline.

    TOKENHUB_API_KEY=... python3 -m tryit.server --port 8787

It is a small standard-library HTTP server in front of
:func:`tribunal.pipeline.run_loaded_case`, run with the settings of the recorded
version-6 runs (four judge drafts, policy version 6, parallel calls). It adds
nothing to the arbitration: the scenario is built by :mod:`tryit.case`, the same
code the website runs in the browser, and the pipeline is called as the
benchmark calls it.

Endpoints (JSON in and out):

    GET  /api/health        is a live run available, and how many are left today
    POST /api/run           {"scenario": {...}} -> {"id": ..., "position": n}
    GET  /api/run/<id>      progress while it runs, the result when it is done

Limits, all from the environment so nobody edits code to change them:

    TRY_ALLOW_ORIGINS  comma-separated origins allowed to call it
                       (default https://tribunal.edgeone.dev)
    TRY_DAILY_CAP      live runs per UTC day, all visitors together (default 60)
    TRY_PER_VISITOR    live runs per visitor address per UTC day (default 3)
    TRY_WORKERS        cases run at the same time (default 2)
    TRY_MODEL          model id (default deepseek/deepseek-flash)
    TRY_STORE          where each run's scenario, events and result are kept
                       (default ./tryit-runs)
    TRY_TRUST_PROXY    "1" to read the visitor address from X-Forwarded-For

Each run costs about 0.06 USD in model calls and takes two to five minutes.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import queue
import sys
import threading
import time
import traceback
import uuid
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tribunal import events as events_module  # noqa: E402
from tribunal import llm, money, pipeline  # noqa: E402
from ops import appeal, queue as ops_queue  # noqa: E402
from tryit import case as scenario  # noqa: E402

MAX_BODY_BYTES = 64 * 1024
JOBS_KEPT = 500


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Settings:
    def __init__(self) -> None:
        origins = os.environ.get("TRY_ALLOW_ORIGINS", "https://tribunal.edgeone.dev")
        self.origins = [o.strip().rstrip("/") for o in origins.split(",") if o.strip()]
        self.daily_cap = _env_int("TRY_DAILY_CAP", 60)
        self.per_visitor = _env_int("TRY_PER_VISITOR", 3)
        self.workers = max(1, _env_int("TRY_WORKERS", 2))
        self.model = os.environ.get("TRY_MODEL", "deepseek/deepseek-flash")
        self.store = Path(os.environ.get("TRY_STORE", "tryit-runs"))
        self.trust_proxy = os.environ.get("TRY_TRUST_PROXY") == "1"
        self.case_deadline = float(os.environ.get("TRY_CASE_DEADLINE", "900"))


def _today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def _plain(value: Any) -> Any:
    return json.loads(money.dumps_canonical(value)) if value is not None else None


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
class Job:
    def __init__(self, scenario_edits: Dict[str, Any], case: Dict[str, Any]) -> None:
        self.id = uuid.uuid4().hex[:16]
        self.edits = scenario_edits
        self.case = case
        self.status = "queued"
        self.created = time.time()
        self.started: Optional[float] = None
        self.finished: Optional[float] = None
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.events_path: Optional[Path] = None


class Service:
    def __init__(self, settings: Settings, client_factory=None) -> None:
        self.settings = settings
        self.lock = threading.Lock()
        self.jobs: Dict[str, Job] = {}
        self.order: List[str] = []
        self.pending: "queue.Queue[Job]" = queue.Queue()
        self.day = _today()
        self.used_today = 0
        self.per_visitor: Dict[str, int] = {}
        self.testing = client_factory is not None
        self.client_factory = client_factory or self._real_client
        self.settings.store.mkdir(parents=True, exist_ok=True)
        for _ in range(settings.workers):
            threading.Thread(target=self._worker, daemon=True).start()

    # -- credentials ---------------------------------------------------------
    def live(self) -> bool:
        if self.testing:
            return True
        return llm.load_api_key() is not None

    def _real_client(self, sink):
        return llm.LLMClient(model=self.settings.model, record_sink=sink, timeout_seconds=900.0)

    # -- limits --------------------------------------------------------------
    def _roll_day(self) -> None:
        today = _today()
        if today != self.day:
            self.day, self.used_today, self.per_visitor = today, 0, {}

    def health(self, visitor: str) -> Dict[str, Any]:
        with self.lock:
            self._roll_day()
            waiting = sum(1 for j in self.jobs.values() if j.status in ("queued", "running"))
            return {
                "ok": True,
                "live": self.live(),
                "model": self.settings.model,
                "policy_version": scenario.POLICY_VERSION,
                "left_today": max(0, self.settings.daily_cap - self.used_today),
                "left_for_you": max(0, self.settings.per_visitor - self.per_visitor.get(visitor, 0)),
                "waiting": waiting,
            }

    def submit(self, body: Any, visitor: str) -> Dict[str, Any]:
        edits = body.get("scenario") if isinstance(body, dict) else None
        edits = scenario.normalise_edits(edits)
        case = scenario.build_case(edits)
        if not self.live():
            raise Refused(503, "live runs are not switched on: the service has no model key")
        with self.lock:
            self._roll_day()
            if self.used_today >= self.settings.daily_cap:
                raise Refused(429, "today's live runs are used up; the in-browser check still works")
            if self.per_visitor.get(visitor, 0) >= self.settings.per_visitor:
                raise Refused(429, "you have used your live runs for today")
            self.used_today += 1
            self.per_visitor[visitor] = self.per_visitor.get(visitor, 0) + 1
            job = Job(edits, case)
            self.jobs[job.id] = job
            self.order.append(job.id)
            while len(self.order) > JOBS_KEPT:
                self.jobs.pop(self.order.pop(0), None)
            position = sum(1 for j in self.jobs.values() if j.status == "queued")
        self.pending.put(job)
        return {"id": job.id, "position": position}

    def status(self, job_id: str) -> Dict[str, Any]:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise Refused(404, "no such run")
            ahead = sum(1 for j in self.jobs.values() if j.status == "queued" and j.created < job.created)
        out: Dict[str, Any] = {"id": job.id, "status": job.status, "position": ahead}
        now = time.time()
        if job.started:
            out["elapsed_seconds"] = round((job.finished or now) - job.started, 1)
            out["progress"] = _progress(job.events_path, job.case.get("case_no"))
        if job.status == "done":
            out["result"] = job.result
        if job.status == "failed":
            out["error"] = job.error
        return out

    # -- the work ------------------------------------------------------------
    def _worker(self) -> None:
        while True:
            job = self.pending.get()
            job.status, job.started = "running", time.time()
            folder = self.settings.store / "{0}-{1}".format(time.strftime("%Y%m%d-%H%M%S"), job.id)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "scenario.json").write_text(json.dumps(job.edits, ensure_ascii=False, indent=1), encoding="utf-8")
            job.events_path = folder / "events.jsonl"
            try:
                log = events_module.EventLog(job.events_path, invocation_id=events_module.new_invocation_id())
                records: List[Dict[str, Any]] = []
                client = self.client_factory(records.append)
                result = pipeline.run_loaded_case(
                    job.case,
                    client,
                    judge_votes=pipeline.DEFAULT_JUDGE_VOTES,
                    events_log=log,
                    policy_version=scenario.POLICY_VERSION,
                    parallel_calls=True,
                    case_deadline_seconds=self.settings.case_deadline,
                )
                job.result = summarise(result, job.case)
                (folder / "transcript.json").write_text(result.transcript_json, encoding="utf-8")
                (folder / "result.json").write_text(json.dumps(job.result, ensure_ascii=False, indent=1), encoding="utf-8")
                job.status = "done"
            except Exception as exc:  # reported to the visitor in one line, kept in full on disk
                job.error = "{0}: {1}".format(type(exc).__name__, str(exc)[:300])
                (folder / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
                job.status = "failed"
            finally:
                job.finished = time.time()


class Refused(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def _progress(path: Optional[Path], case_no: Any) -> Dict[str, Any]:
    """Read the run's own event log: which agents have answered so far."""
    out = {"rider": False, "driver": False, "referee": False, "drafts": 0, "vote": False}
    if path is None or not path.exists():
        return out
    try:
        for line in events_module.read_lines(path):
            event = json.loads(line)
            kind = event.get("event")
            if kind == events_module.EVENT_AGENT_CALL:
                role = event.get("role")
                if role == "RIDER_ADVOCATE":
                    out["rider"] = True
                elif role == "DRIVER_ADVOCATE":
                    out["driver"] = True
            elif kind == events_module.EVENT_REFEREE_DECISION:
                out["referee"] = True
            elif kind == events_module.EVENT_JUDGE_DRAFT:
                out["drafts"] += 1
            elif kind == events_module.EVENT_VOTE:
                out["vote"] = True
    except (OSError, ValueError):
        pass
    return out


def summarise(result: Any, case: Dict[str, Any]) -> Dict[str, Any]:
    """What the page shows: the ruling, the referee's ledger, the vote, the lane, the cost."""
    published = result.ruling if isinstance(result.ruling, dict) else {}
    ruling = published.get("ruling") if isinstance(published.get("ruling"), dict) else {}
    ledger = (result.referee or {}).get("ledger") or []
    kept = {"RIDER": 0, "DRIVER": 0}
    dropped = {"RIDER": 0, "DRIVER": 0}
    discards = []
    for entry in ledger:
        side = entry.get("side")
        if entry.get("status") == "KEPT":
            kept[side] = kept.get(side, 0) + 1
        else:
            dropped[side] = dropped.get(side, 0) + 1
            discards.append({"side": side, "reason_code": entry.get("reason_code"),
                             "detail": entry.get("detail"), "claim": (entry.get("claim") or "")[:400]})
    drafts = []
    for draft in (result.judge_vote or {}).get("drafts", []):
        drafts.append({"draft": draft.get("draft"), "kind": draft.get("kind"), "valid": draft.get("valid"),
                       "agrees": draft.get("agrees"), "proposal": _plain(draft.get("proposal")),
                       "abstention": _plain(draft.get("abstention"))})

    dispute = case["dispute"]
    code = ruling.get("ruling")
    threshold = ops_queue._execution_threshold(dispute.get("category"), scenario.POLICY_VERSION)
    lane, reasons = ops_queue.lane_for(
        ops_queue.Dispute(
            case_no=case["case_no"],
            category=dispute.get("category"),
            filed_at=dispute.get("filed_at"),
            amount_contested_sgd=None,
            ruling=code,
            wall_seconds=None,
            risk_tripped=False,
            safety_flag=dispute.get("safety_flag") is True,
            complaint_flag=dispute.get("complaint_flag") is True,
            amount_sgd=_dec(ruling.get("amount_sgd")),
            driver_compensation_sgd=_dec(ruling.get("driver_compensation_sgd")),
            execution_threshold_sgd=threshold,
            chat_threat=ops_queue.chat_log_has_threat(case),
        ),
        ops_queue.load_config(),
    )
    return {
        "ok": bool(result.ok),
        "ruling": _plain(ruling) or None,
        "discarded_claims": len(published.get("discarded_claims") or []),
        "failed_agent": result.failed_agent,
        "failure_reason": result.failure_reason,
        "scope_gate": _plain(result.scope_gate),
        "referee": {"kept": kept, "dropped": dropped, "discards": discards[:12]},
        "vote_agreement": result.vote_agreement,
        "drafts": drafts,
        "lane": lane,
        "lane_reasons": list(reasons),
        "execution_threshold_sgd": _plain(threshold),
        "tokens": {"prompt": result.prompt_tokens, "completion": result.completion_tokens,
                   "reasoning": result.reasoning_tokens, "cached": result.cached_tokens},
        "seconds": round(result.duration_seconds, 1),
        "brief_sha256": result.brief_sha256,
    }


def _dec(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def make_handler(service: Service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "tribunal-try/1"

        def log_message(self, fmt: str, *args: Any) -> None:  # one short line per request
            sys.stderr.write("%s %s\n" % (self.command, self.path[:80]))

        def _visitor(self) -> str:
            if service.settings.trust_proxy:
                forwarded = self.headers.get("X-Forwarded-For", "")
                if forwarded:
                    return forwarded.split(",")[0].strip()
            return self.client_address[0]

        def _cors(self) -> None:
            origin = (self.headers.get("Origin") or "").rstrip("/")
            if origin and (origin in service.settings.origins or "*" in service.settings.origins):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Max-Age", "600")

        def _send(self, code: int, body: Dict[str, Any]) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:
            try:
                if self.path.rstrip("/") == "/api/health":
                    return self._send(200, service.health(self._visitor()))
                if self.path.startswith("/api/run/"):
                    return self._send(200, service.status(self.path.rsplit("/", 1)[-1][:32]))
                self._send(404, {"error": "not found"})
            except Refused as exc:
                self._send(exc.code, {"error": str(exc)})

        def do_POST(self) -> None:
            if self.path.rstrip("/") != "/api/run":
                return self._send(404, {"error": "not found"})
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY_BYTES:
                return self._send(413, {"error": "the scenario is empty or too large"})
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                self._send(202, service.submit(body, self._visitor()))
            except scenario.ScenarioError as exc:
                self._send(400, {"error": str(exc)})
            except Refused as exc:
                self._send(exc.code, {"error": str(exc)})
            except ValueError:
                self._send(400, {"error": "the body is not JSON"})

    return Handler


def recorded_client_factory(case_no: int = 208):
    """For testing without a key: answer each call from case 208's recorded run, by role.

    The answers are real recorded model output, but they were written for the
    unedited case, so a scenario run this way is a test of the plumbing, not a
    ruling on the scenario. ``/api/health`` says so (``"mode": "recorded-test"``).
    """
    transcript = json.loads((ROOT / "runs/policy-v6/deepseek-deepseek-flash/case-{0:05d}.transcript.json".format(case_no)).read_text())
    by_role: Dict[str, List[Dict[str, Any]]] = {}
    for entry in transcript["entries"]:
        by_role.setdefault(entry["role"], []).append(entry)

    def transport(url, headers, body, timeout):
        context = pipeline.CALL_CONTEXT.get()
        role = context[1] if context else "JUDGE"
        index = context[2] if context and role == "JUDGE" else 0
        entries = by_role[role]
        entry = entries[min(max(index - 1, 0), len(entries) - 1)] if role == "JUDGE" else entries[0]
        time.sleep(float(os.environ.get("TRY_TEST_DELAY", "0.5")))
        payload = {"choices": [{"message": {"content": entry["response_text"]}}],
                   "usage": {"prompt_tokens": entry["prompt_tokens"], "completion_tokens": entry["completion_tokens"],
                             "completion_tokens_details": {"reasoning_tokens": entry["reasoning_tokens"]},
                             "prompt_tokens_details": {"cached_tokens": entry["cached_tokens"]}}}
        return llm.HttpResult(status=200, body=json.dumps(payload).encode("utf-8"))

    def build(sink):
        return llm.LLMClient(model="deepseek/deepseek-flash", record_sink=sink, api_key="recorded-test",
                             transport=transport, requests_per_minute=6000)

    return build


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--once", metavar="SCENARIO_JSON",
                        help="run one scenario file (downloaded from the try-it page) and print the result, then exit")
    parser.add_argument("--recorded-test", action="store_true",
                        help="answer from case 208's recorded run instead of the model (no key, no cost; for testing)")
    args = parser.parse_args(argv)
    if args.once:
        edits = json.loads(Path(args.once).read_text(encoding="utf-8"))
        edits = edits.get("scenario", edits)
        case = scenario.build_case(edits)
        factory = recorded_client_factory() if args.recorded_test else None
        client = (factory or (lambda sink: llm.LLMClient(model=os.environ.get("TRY_MODEL", "deepseek/deepseek-flash"),
                                                          record_sink=sink, timeout_seconds=900.0)))([].append)
        result = pipeline.run_loaded_case(case, client, judge_votes=pipeline.DEFAULT_JUDGE_VOTES,
                                          policy_version=scenario.POLICY_VERSION, parallel_calls=True)
        print(json.dumps(summarise(result, case), ensure_ascii=False, indent=1))
        return 0
    settings = Settings()
    service = Service(settings, recorded_client_factory() if args.recorded_test else None)
    if args.recorded_test:
        original = service.health

        def health(visitor: str) -> Dict[str, Any]:
            out = original(visitor)
            out["mode"] = "recorded-test"
            return out

        service.health = health  # type: ignore[assignment]
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(service))
    sys.stderr.write("try-it service on http://{0}:{1}  live={2}  origins={3}\n".format(
        args.host, args.port, service.live(), settings.origins))
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
