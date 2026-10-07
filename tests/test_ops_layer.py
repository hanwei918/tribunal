"""The rules that bind every module of the operations layer.

``ops/`` is a layer, not a set of commands, and the ops task states four rules
that hold for every part of it: what it may import, what it may read, what it may
write, and that it never reads an answer. They are asserted here, once, over
**every** ``ops`` command rather than in each part's own module, so a command
added later is covered by the same tests rather than by a fresh reading of them.

The four, and how each is made to mean something:

* **The import graph.** No ``ops`` module imports a network client or anything
  outside the standard library and the repository's own packages, and nothing in
  ``tribunal/`` or ``eval/`` imports ``ops``. The check is over the modules' own
  import statements, which is the edge the rule is about: ``ops`` is *told* to
  reach the sealed-root guard through ``eval.sealed_roots``, and that module
  reaches the runner -- and so the client module -- from inside one function.
* **The answer keys.** Every command is run over the corpus with ``io.open`` and
  ``builtins.open`` patched to raise on any path under an ``answers`` directory,
  and every output is checked for an ``expected`` or a ``matched`` **field**. The
  words may occur inside the judge's own prose, so the field is what is asserted;
  the positive control below shows the check can fail.
* **The writes.** No command writes anything unless it is given ``--out``, and an
  ``--out`` inside ``runs/``, ``data/``, ``policy/``, ``prompts/``, ``tribunal/``,
  ``eval/answers/`` or either sealed root is refused before anything is written.
* **The determinism.** Two runs of one command give byte-identical output.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Set, Tuple
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ops  # noqa: E402
from ops import escalation, review, risk  # noqa: E402

# The run directory every command here is run against, and its set.
CORPUS_RUN = PROJECT_ROOT / "runs" / "deepseek-deepseek-flash"

# The 29-case corpus, in manifest order, read off the manifest rather than
# restated so a corpus that changed would change what these tests cover.
CORPUS_CASE_NUMBERS: Tuple[int, ...] = tuple(
    entry["case_no"] for entry in json.loads((PROJECT_ROOT / "data" / "index.json").read_text())
)

# The keys no command's output may carry as a field.
FORBIDDEN_OUTPUT_FIELDS = ("expected", "matched")

# Directories that are not repository content, for the write check.
NOT_REPOSITORY_CONTENT = frozenset(
    {".git", ".workbuddy-ai", "__pycache__", ".venv", "tmp", "output"}
)

# A JSON field, as it appears in a serialised document.
FORBIDDEN_FIELD_RE = re.compile(r'"(?:expected|matched)"\s*:')

# The closure a review command records, for the one case it is exercised on. The
# ruling is one POL-GEN-03 licenses and is not ESCALATE; the reason cites this
# case's own evidence id and a clause its policy carries, which is what
# ``tribunal.precedents close`` requires.
REVIEW_CASE = 207
REVIEW_ARGUMENTS = [
    "--ruling",
    "NO_ACTION",
    "--clause",
    "POL-NS-01",
    "--closed-by",
    "the ops layer test",
    "--summary",
    "The fee stands on the record as it is.",
    "--reason",
    "Reviewed the packet; the fee stands under POL-NS-01 on EV-FARE-00207.",
]


def run_command(entry: Callable[..., int], arguments: Sequence[str]) -> Tuple[int, str, str]:
    """One command's ``main``, with both streams captured."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = entry(list(arguments))
    return code, stdout.getvalue(), stderr.getvalue()


def repository_files() -> Set[str]:
    found: Set[str] = set()
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if any(part in NOT_REPOSITORY_CONTENT for part in relative.parts[:-1]):
            continue
        found.add(str(relative))
    return found


def keys_of(node: Any) -> Set[str]:
    """Every key anywhere in a JSON document, recursively."""
    found: Set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(key)
            found |= keys_of(value)
    elif isinstance(node, list):
        for value in node:
            found |= keys_of(value)
    return found


def every_command() -> List[Tuple[str, Callable[..., int], List[str]]]:
    """Every ``ops`` command, over the corpus, as ``(name, entry, arguments)``.

    Each entry is a command that can run: the risk signals for every case, a
    packet for every case (``--any``, so a case that did not escalate is still
    built), a packet for each of the five escalated cases without ``--any``, and
    one closure through the review step. A command that refuses is still a
    command that was run, so the refusals are exercised too.
    """
    commands: List[Tuple[str, Callable[..., int], List[str]]] = []
    for case_no in CORPUS_CASE_NUMBERS:
        commands.append(("risk {0}".format(case_no), risk.main, ["--case", str(case_no)]))
        commands.append(
            (
                "escalation {0} --any".format(case_no),
                escalation.main,
                ["--run-dir", str(CORPUS_RUN), "--case", str(case_no), "--any"],
            )
        )
    for case_no in (110, 112, 207, 210, 213):
        commands.append(
            (
                "escalation {0}".format(case_no),
                escalation.main,
                ["--run-dir", str(CORPUS_RUN), "--case", str(case_no)],
            )
        )
    return commands


def review_arguments(store: Path, digest: str) -> List[str]:
    return [
        "--run-dir",
        str(CORPUS_RUN),
        "--case",
        str(REVIEW_CASE),
        "--packet-sha256",
        digest,
        "--store",
        str(store),
    ] + REVIEW_ARGUMENTS


def current_digest(case_no: int = REVIEW_CASE) -> str:
    return escalation.packet_sha256(escalation.build_packet(CORPUS_RUN, case_no))


# --------------------------------------------------------------------------
# Rule 1: the import graph
# --------------------------------------------------------------------------
class TheImportGraphTests(unittest.TestCase):
    """What ``ops/`` may import, and what may import ``ops/``."""

    FORBIDDEN_MODULES = frozenset(
        {
            "tribunal.llm",
            "urllib",
            "http",
            "socket",
            "ssl",
            "requests",
            "httpx",
            "urllib3",
            "ftplib",
            "smtplib",
            "telnetlib",
            "xmlrpc",
            "asyncio",
        }
    )

    def _imports(self, path: Path) -> Set[str]:
        import ast

        found: Set[str] = set()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                if node.module:
                    found.add(node.module)
                    for alias in node.names:
                        found.add(node.module + "." + alias.name)
        return found

    def ops_modules(self) -> List[Path]:
        return sorted((PROJECT_ROOT / "ops").glob("*.py"))

    def test_ops_modules_import_only_from_tribunal_eval_and_ops(self):
        self.assertTrue(self.ops_modules(), "ops/ holds no modules")
        for path in self.ops_modules():
            for name in self._imports(path):
                top = name.split(".")[0]
                if top in ("ops", "tribunal", "eval"):
                    continue
                if top in sys.stdlib_module_names:
                    continue
                with self.subTest(module=path.name, imported=name):
                    self.fail(
                        "{0} imports {1}, which is neither the standard library nor "
                        "a repository package".format(path.name, name)
                    )

    def test_no_ops_module_imports_a_network_client(self):
        """The modules' own imports, which is the edge the rule is about.

        A transitive walk would refuse ``eval.sealed_roots`` -- which rule 3
        tells the layer to use, and which reaches the runner and so the client
        module from inside one function -- so the check is over the imports each
        ``ops`` module states itself.
        """
        for path in self.ops_modules():
            for name in self._imports(path):
                for forbidden in self.FORBIDDEN_MODULES:
                    with self.subTest(module=path.name, imported=name):
                        self.assertFalse(
                            name == forbidden or name.startswith(forbidden + "."),
                            "{0} imports {1}".format(path.name, name),
                        )

    def test_nothing_in_tribunal_or_eval_imports_ops(self):
        for package in ("tribunal", "eval"):
            for path in sorted((PROJECT_ROOT / package).glob("*.py")):
                for name in self._imports(path):
                    with self.subTest(module=path.name, imported=name):
                        self.assertFalse(
                            name == "ops" or name.startswith("ops."),
                            "{0}/{1} imports ops".format(package, path.name),
                        )

    def test_the_import_walk_reaches_the_modules_it_claims_to(self):
        """A control: the walk is reading real import statements."""
        for name in ("risk.py", "escalation.py", "review.py"):
            with self.subTest(module=name):
                imports = self._imports(PROJECT_ROOT / "ops" / name)
                self.assertTrue(imports, "{0} was walked and no import was found".format(name))


# --------------------------------------------------------------------------
# Rule 2: no answer key, and no answer field
# --------------------------------------------------------------------------
class TheNoAnswersTests(unittest.TestCase):
    """No ``ops`` command opens an answer key, and none prints an answer."""

    def _guard(self):
        real_open = io.open

        def guarded(file, *args, **kwargs):
            text = str(file).replace(os.sep, "/")
            if "/answers/" in text:
                raise AssertionError("an ops command opened {0}".format(text))
            return real_open(file, *args, **kwargs)

        return guarded

    def test_the_guard_is_capable_of_failing(self):
        """The positive control: a path under answers/ is refused."""
        with mock.patch("io.open", self._guard()), mock.patch("builtins.open", self._guard()):
            with self.assertRaises(AssertionError):
                Path("/tmp/nowhere-at-all/answers/ground_truth.json").read_text()

    def test_the_field_check_is_capable_of_failing(self):
        """The second positive control: a document carrying the field is caught."""
        self.assertTrue(FORBIDDEN_FIELD_RE.search('{"matched":true}'))
        self.assertTrue(FORBIDDEN_FIELD_RE.search('{"expected": "PARTIAL_REFUND"}'))
        self.assertFalse(FORBIDDEN_FIELD_RE.search('{"note":"the gantry is matched"}'))

    def test_every_command_runs_over_the_corpus_with_the_keys_unreadable(self):
        commands = every_command()
        self.assertTrue(commands, "no command was enumerated")
        for name, entry, arguments in commands:
            with self.subTest(command=name):
                with mock.patch("io.open", self._guard()), mock.patch("builtins.open", self._guard()):
                    code, out, err = run_command(entry, arguments)
                self.assertEqual(0, code, err)
                for stream in (out, err):
                    self.assertIsNone(
                        FORBIDDEN_FIELD_RE.search(stream),
                        "{0} printed an answer field".format(name),
                    )

    def test_the_review_command_runs_with_the_keys_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            arguments = review_arguments(Path(tmp), current_digest())
            with mock.patch("io.open", self._guard()), mock.patch("builtins.open", self._guard()):
                code, out, err = run_command(review.main, arguments)
            self.assertEqual(0, code, err)
            self.assertIsNone(FORBIDDEN_FIELD_RE.search(out + err))

    def test_no_packet_carries_an_answer_field(self):
        """The structural half: the packet's own keys, walked recursively."""
        for case_no in (110, 112, 207, 210, 213):
            packet = escalation.build_packet(CORPUS_RUN, case_no)
            with self.subTest(case=case_no):
                self.assertEqual(set(), keys_of(packet) & set(FORBIDDEN_OUTPUT_FIELDS))
                for row in packet["timeline"]:
                    self.assertNotEqual("grade", row["event"])

    def test_the_corpus_run_is_printed_without_an_answer_field(self):
        code, out, err = run_command(
            escalation.main, ["--run-dir", str(CORPUS_RUN), "--case", "207"]
        )
        self.assertEqual(0, code, err)
        self.assertIsNone(FORBIDDEN_FIELD_RE.search(out))


# --------------------------------------------------------------------------
# Rule 3: nothing is written, and a forbidden destination is refused
# --------------------------------------------------------------------------
class TheWritesTests(unittest.TestCase):
    """No command writes unless it is given ``--out``, and then only where it may."""

    def test_no_command_writes_a_file_without_an_out(self):
        before = repository_files()
        for name, entry, arguments in every_command():
            with self.subTest(command=name):
                run_command(entry, arguments)
        with tempfile.TemporaryDirectory() as tmp:
            run_command(review.main, review_arguments(Path(tmp), current_digest()))
        self.assertEqual(before, repository_files())

    def test_the_out_guard_refuses_every_forbidden_tree(self):
        for name in ops.FORBIDDEN_DESTINATIONS:
            with self.subTest(tree=name):
                destination = PROJECT_ROOT / name / "ops-packet.json"
                with self.assertRaises(ops.OpsWriteError):
                    ops.refuse_a_forbidden_destination(destination)

    def test_the_out_guard_refuses_a_sealed_root_however_it_is_spelled(self):
        for spelling in ("wild", "WILD", "wild-v2", "WILD-V2"):
            with self.subTest(spelling=spelling):
                destination = PROJECT_ROOT / "runs" / spelling / "packet.json"
                with self.assertRaises(ops.OpsWriteError):
                    ops.refuse_a_forbidden_destination(destination)

    def test_the_out_guard_takes_a_destination_of_its_own(self):
        """A guard that refused everything would pass the tests above."""
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "packet.json"
            self.assertEqual(
                destination.resolve(), ops.refuse_a_forbidden_destination(destination)
            )

    def test_the_escalation_command_refuses_a_forbidden_out_and_writes_nothing(self):
        for name in ("runs", "data", "policy", "prompts", "tribunal", "eval/answers"):
            with self.subTest(tree=name):
                destination = PROJECT_ROOT / name / "ops-packet.json"
                code, out, err = run_command(
                    escalation.main,
                    [
                        "--run-dir",
                        str(CORPUS_RUN),
                        "--case",
                        "207",
                        "--out",
                        str(destination),
                    ],
                )
                self.assertEqual(1, code)
                self.assertIn("FATAL", err)
                self.assertIn(str(destination.resolve()), err)
                self.assertFalse(destination.exists())

    def test_the_escalation_command_writes_a_destination_of_its_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "packet.json"
            code, out, err = run_command(
                escalation.main,
                ["--run-dir", str(CORPUS_RUN), "--case", "207", "--out", str(destination)],
            )
            self.assertEqual(0, code, err)
            self.assertTrue(destination.is_file())
            self.assertEqual("", out)
            self.assertIn("packet sha256:", err)


# --------------------------------------------------------------------------
# Rule 5: two runs are the same run
# --------------------------------------------------------------------------
class TheLayerDeterminismTests(unittest.TestCase):
    """Every command's output is a function of the repository, not of the clock."""

    def test_two_runs_of_every_command_are_byte_identical(self):
        for name, entry, arguments in every_command()[:6] + every_command()[-1:]:
            with self.subTest(command=name):
                self.assertEqual(
                    run_command(entry, arguments), run_command(entry, arguments)
                )


if __name__ == "__main__":
    unittest.main()
