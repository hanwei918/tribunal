"""Read a run's event log: one case's history, or the whole chain's integrity.

Two commands, and they are read-only:

* ``python3 -m eval.events --run-dir <dir> --case 211`` prints a **timeline** of
  case 211: one row per event, in the order it happened, with the time, the role
  or the draft it was, the status the provider returned, what it cost in tokens,
  how long it took and how its answer parsed -- and the last two lines are the
  vote and the ruling the case ended in. The log is cumulative, so the history it
  prints can span several invocations -- a case re-run under ``--force`` has
  more history than one that was run once, and the printer shows all of it.
  ``--json`` prints the payloads instead, one per line.
* ``python3 -m eval.events --verify`` checks the hash chain from the first line
  to the last and reports the first line that does not agree with it, exiting
  non-zero when there is one.

Nothing here makes a model call, writes a file or touches a cache entry. The
log is the artifact; this module only reads it.

Which log
---------
``--path`` names a log directly. Otherwise ``--run-dir`` names a run directory
and ``--set`` picks the development set whose runs root the directory is under:
the corpus is ``runs/<model>/`` and a development set is
``runs/<set>/<model>/``. The default is the corpus run directory for the model
``tribunal/model.py`` records.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import events, money  # noqa: E402
from eval import run_benchmark  # noqa: E402


def default_log_path(
    model: Optional[str] = None, set_name: str = "corpus", runs_dir: Optional[Path] = None
) -> Path:
    """The event log of the run directory a caller named by convention.

    ``set_name`` is a development set name or ``corpus``. The corpus's run
    directory is ``runs/<model>/`` and a set's is ``runs/<set>/<model>/``,
    which is the same layout the runner writes to, so the path a reader guesses
    is the path the run used.
    """
    resolved = run_benchmark.resolve_model(model)
    base = run_benchmark.RUNS_DIR if runs_dir is None else Path(runs_dir)
    if set_name != "corpus":
        from eval import development_sets

        development_set = development_sets.named(set_name)
        base = development_set.runs_dir(base)
    return run_benchmark.run_directory(base, resolved) / events.EVENTS_FILE


def _print_case(path: Path, case_no: int, as_json: bool) -> int:
    found = events.events_for_case(path, case_no)
    if not found:
        print(
            "no events for case {0} in {1}".format(case_no, path),
            file=sys.stderr,
        )
        return 1
    if as_json:
        for event in found:
            # ``money.dumps_canonical`` rather than ``json.dumps``: an event
            # carries a ruling's amounts as ``Decimal``, which the standard
            # encoder refuses. It is also the serialiser the line itself was
            # written with, so what is printed is what was written.
            print(money.dumps_canonical(event))
        return 0
    print(events.timeline(path, case_no))
    return 0


def _verify(path: Path) -> int:
    if not Path(path).exists():
        print("no event log at {0}".format(path), file=sys.stderr)
        return 1
    total = len(events.read_lines(path))
    break_at = events.verify_chain(path)
    if break_at is None:
        print("{0} line(s) verified in {1}: the chain is intact".format(total, path))
        return 0
    print(
        "TAMPERED: the chain first breaks at {0} in {1}".format(
            break_at.describe(), path
        ),
        file=sys.stderr,
    )
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.events",
        description=(
            "Print one case's history from a run's append-only event log, or "
            "verify the log's hash chain. Reads only; makes no model call."
        ),
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--case", type=int, help="print this case's full history, in order")
    action.add_argument(
        "--verify",
        action="store_true",
        help="check the whole hash chain and report the first break; exits non-zero on one",
    )
    parser.add_argument("--path", type=Path, default=None, help="the log file itself")
    parser.add_argument("--run-dir", type=Path, default=None, help="a run directory holding events.jsonl")
    parser.add_argument("--model", default=None, help="the model id; defaults to tribunal/model.py")
    parser.add_argument(
        "--set",
        dest="set_name",
        default="corpus",
        help="which development set's runs root to look under; default is the corpus",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="the runs root, when it is not runs/",
    )
    parser.add_argument("--json", action="store_true", help="print each event's raw JSON")
    return parser


def resolve_path(args: argparse.Namespace) -> Path:
    if args.path is not None:
        return Path(args.path)
    if args.run_dir is not None:
        return Path(args.run_dir) / events.EVENTS_FILE
    return default_log_path(args.model, args.set_name, args.runs_dir)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    path = resolve_path(args)
    if args.verify:
        return _verify(path)
    return _print_case(path, args.case, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
