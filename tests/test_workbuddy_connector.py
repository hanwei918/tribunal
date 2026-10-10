"""The WorkBuddy connector: a subprocess, its three tools, and its refusals.

The connector is an MCP server started over standard input and output, so this
module talks to it the way WorkBuddy does: it starts
``integrations/workbuddy/tribunal_mcp_server.py`` as a subprocess, writes one
JSON object per line, and reads the answers back off standard output. Nothing
is imported from the server, because the boundary being tested is the protocol
boundary and not a function call.

Four things are asserted, and each is asserted on the answer rather than on the
code that produced it:

* the protocol -- ``initialize`` names the server and the ``tools`` capability,
  ``tools/list`` names the three tools, and every line on standard output is one
  JSON object and nothing else;
* the answers -- case 901 of the organisers' sample is the
  ``DRIVER_COMPENSATION`` ruling of 4.00, and case 213 of the corpus is in the
  human-review lane;
* the refusals -- an unknown tool, an unknown method, a set that is not offered
  and a sealed set's case are each refused rather than answered;
* the imports -- the server's own import statements name no network module, and
  nothing outside the standard library and this repository's own packages.

**The server is read-only and the tests treat it that way.** It reads committed
run files, so no run directory is written, no fixture is created and no path
under ``runs/`` is touched. No model is called, no browser is launched and no
socket is opened by either side.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_ops_layer import is_standard_library  # noqa: E402

SERVER = (
    PROJECT_ROOT / "integrations" / "workbuddy" / "tribunal_mcp_server.py"
)

# The repository's own packages. Every other top-level import the server states
# must be the standard library.
REPOSITORY_PACKAGES = frozenset({"eval", "ops", "tribunal", "ui"})

# The modules a connector must never import: a socket, a web client, or the
# thing that opens a browser.
NETWORK_MODULES = frozenset(
    {
        "aiohttp",
        "ftplib",
        "http",
        "httpx",
        "requests",
        "smtplib",
        "socket",
        "ssl",
        "telnetlib",
        "urllib",
        "webbrowser",
        "xmlrpc",
    }
)

# The identifiers the exchange below uses, one per request, so a test names the
# request it is reading rather than counting lines.
INITIALIZE = 1
TOOLS_LIST = 2
CASE_901 = 3
QUEUE_CORPUS = 4
PACKET_213 = 5
UNKNOWN_TOOL = 6
BAD_SET = 7
SEALED_V1_CASE = 8
SEALED_WILD_V2_CASE = 9
UNKNOWN_METHOD = 10

REQUESTS: Tuple[Mapping[str, Any], ...] = (
    {"jsonrpc": "2.0", "id": INITIALIZE, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "id": TOOLS_LIST, "method": "tools/list", "params": {}},
    {
        "jsonrpc": "2.0",
        "id": CASE_901,
        "method": "tools/call",
        "params": {
            "name": "tribunal_case",
            "arguments": {"set": "ryde-v3", "case": 901},
        },
    },
    {
        "jsonrpc": "2.0",
        "id": QUEUE_CORPUS,
        "method": "tools/call",
        "params": {"name": "tribunal_queue", "arguments": {"set": "corpus"}},
    },
    {
        "jsonrpc": "2.0",
        "id": PACKET_213,
        "method": "tools/call",
        "params": {
            "name": "tribunal_packet",
            "arguments": {"set": "corpus", "case": 213},
        },
    },
    {
        "jsonrpc": "2.0",
        "id": UNKNOWN_TOOL,
        "method": "tools/call",
        "params": {"name": "tribunal_nonesuch", "arguments": {}},
    },
    {
        "jsonrpc": "2.0",
        "id": BAD_SET,
        "method": "tools/call",
        "params": {
            "name": "tribunal_case",
            "arguments": {"set": "no-such-set", "case": 1},
        },
    },
    {
        "jsonrpc": "2.0",
        "id": SEALED_V1_CASE,
        "method": "tools/call",
        "params": {
            "name": "tribunal_case",
            "arguments": {"set": "sealed-v1", "case": 301},
        },
    },
    {
        "jsonrpc": "2.0",
        "id": SEALED_WILD_V2_CASE,
        "method": "tools/call",
        "params": {
            "name": "tribunal_case",
            "arguments": {"set": "wild-v2", "case": 701},
        },
    },
    {
        "jsonrpc": "2.0",
        "id": UNKNOWN_METHOD,
        "method": "frobnicate",
        "params": {},
    },
)


def exchange(
    messages: Sequence[Mapping[str, Any]]
) -> Tuple[List[str], str, int]:
    """Send ``messages`` to a fresh server and read what it writes back.

    Returns the non-empty standard-output lines, standard error, and the exit
    code. Standard output is returned as lines rather than as parsed objects,
    so the test that every line is JSON is a reading of what the server
    actually wrote.
    """
    payload = "".join(json.dumps(message) + "\n" for message in messages)
    completed = subprocess.run(
        [sys.executable, str(SERVER)],
        cwd=str(PROJECT_ROOT),
        input=payload,
        capture_output=True,
        text=True,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    return lines, completed.stderr, completed.returncode


def imported_top_level_names(source: str) -> Set[str]:
    """Every top-level module name a module's own import statements name.

    Only the module's own statements are walked, which is the edge an import
    rule is about; a transitive walk would reach whatever ``ui.v2.build``
    reaches.
    """
    names: Set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def text_of(response: Mapping[str, Any]) -> str:
    """The text of a tool result."""
    return response["result"]["content"][0]["text"]


def human_lane_lines(text: str) -> List[str]:
    """The lines under ``human lane:``, stripped, with the heading dropped."""
    lines = text.splitlines()
    start = lines.index("human lane:")
    return [line.strip() for line in lines[start + 1:] if line.strip()]


def explanation_opening(text: str) -> str:
    """The judge's opening, between its heading and the case-page line."""
    marker = "judge's explanation (opening):\n"
    start = text.index(marker) + len(marker)
    end = text.index("\ncase page:", start)
    return text[start:end]


class TheConnectorTests(unittest.TestCase):
    """One server, one exchange, and every answer read by its own id."""

    @classmethod
    def setUpClass(cls):
        cls.lines, cls.stderr, cls.returncode = exchange(REQUESTS)
        cls.responses: List[Mapping[str, Any]] = []
        cls.unparsable: List[str] = []
        for line in cls.lines:
            try:
                cls.responses.append(json.loads(line))
            except ValueError:
                cls.unparsable.append(line)

    def by_id(self, identifier: int) -> Mapping[str, Any]:
        for response in self.responses:
            if response.get("id") == identifier:
                return response
        self.fail("no response carried id {0}".format(identifier))

    # -- the protocol -----------------------------------------------------
    def test_every_line_on_stdout_is_one_json_object(self):
        self.assertEqual(
            [], self.unparsable, "standard output carried something that is not JSON"
        )
        self.assertEqual(
            len(REQUESTS),
            len(self.lines),
            "one response per request was expected; stderr said: {0}".format(
                self.stderr.strip()
            ),
        )

    def test_the_server_exits_cleanly(self):
        self.assertEqual(0, self.returncode, self.stderr)

    def test_initialize_names_the_server_and_the_tools_capability(self):
        result = self.by_id(INITIALIZE)["result"]
        self.assertIn("tools", result["capabilities"])
        self.assertEqual("tribunal", result["serverInfo"]["name"])
        self.assertTrue(result["serverInfo"]["version"])
        self.assertTrue(result["protocolVersion"])

    def test_tools_list_names_the_three_tools(self):
        names = [tool["name"] for tool in self.by_id(TOOLS_LIST)["result"]["tools"]]
        self.assertEqual(
            ["tribunal_case", "tribunal_queue", "tribunal_packet"], names
        )

    def test_every_tool_declares_a_schema_and_offers_only_known_sets(self):
        tools = self.by_id(TOOLS_LIST)["result"]["tools"]
        for tool in tools:
            with self.subTest(tool=tool["name"]):
                self.assertEqual("object", tool["inputSchema"]["type"])
                self.assertTrue(tool["inputSchema"]["required"])
        case_tool = tools[0]
        offered = case_tool["inputSchema"]["properties"]["set"]["enum"]
        self.assertEqual(
            ["corpus", "dev-v2-ext", "dev-v2", "ryde-v3", "inject-v1", "pii-v1",
             "collusion-v1"],
            offered,
        )
        self.assertNotIn("sealed-v1", offered)

    # -- the answers ------------------------------------------------------
    def test_case_901_is_the_driver_compensation_ruling_of_four(self):
        response = self.by_id(CASE_901)
        self.assertFalse(response["result"]["isError"])
        text = text_of(response)
        self.assertIn("DRIVER_COMPENSATION", text)
        self.assertIn("4.00", text)
        self.assertIn("case page: ui/dist/case-00901.html", text)

    def test_the_judges_opening_is_at_least_a_hundred_and_twenty_characters(self):
        opening = explanation_opening(text_of(self.by_id(CASE_901)))
        self.assertGreaterEqual(len(" ".join(opening.split())), 120)

    def test_case_213_is_in_the_human_lane(self):
        text = text_of(self.by_id(QUEUE_CORPUS))
        self.assertIn("HUMAN_REVIEW", text)
        lane = human_lane_lines(text)
        self.assertTrue(lane, "the human lane was empty")
        named = [line for line in lane if line.startswith("213 ")]
        self.assertEqual(1, len(named), "213 is not listed in the human lane")
        self.assertIn("ESCALATE", named[0])

    def test_the_queue_counts_the_cases_it_lists(self):
        text = text_of(self.by_id(QUEUE_CORPUS))
        cases = int(re.search(r"^cases: ([0-9]+)$", text, re.M).group(1))
        listed = human_lane_lines(text)
        auto = int(re.search(r"^  AUTO ([0-9]+)$", text, re.M).group(1))
        human = int(re.search(r"^  HUMAN_REVIEW ([0-9]+)$", text, re.M).group(1))
        self.assertEqual(len(listed), human)
        self.assertLessEqual(auto + human, cases)

    def test_the_packet_names_case_213_and_carries_a_sha256(self):
        text = text_of(self.by_id(PACKET_213))
        self.assertIn("packet: case 213 of corpus", text)
        self.assertIn("ruling: ESCALATE", text)
        digest = re.search(r"^sha256: ([0-9a-f]{64})$", text, re.M)
        self.assertIsNotNone(digest, text)

    # -- the refusals -----------------------------------------------------
    def test_an_unknown_tool_answers_with_a_json_rpc_error(self):
        response = self.by_id(UNKNOWN_TOOL)
        self.assertIn("error", response)
        self.assertEqual(-32602, response["error"]["code"])
        self.assertIn("tribunal_nonesuch", response["error"]["message"])

    def test_an_unknown_method_answers_with_a_json_rpc_error(self):
        response = self.by_id(UNKNOWN_METHOD)
        self.assertIn("error", response)
        self.assertEqual(-32601, response["error"]["code"])
        self.assertIn("frobnicate", response["error"]["message"])

    def test_a_set_that_is_not_offered_is_refused(self):
        response = self.by_id(BAD_SET)
        self.assertTrue(response["result"]["isError"])
        self.assertIn("no set is offered", text_of(response))

    def test_a_sealed_sets_case_is_refused(self):
        for identifier in (SEALED_V1_CASE, SEALED_WILD_V2_CASE):
            with self.subTest(request=identifier):
                response = self.by_id(identifier)
                self.assertTrue(response["result"]["isError"])
                self.assertIn("sealed", text_of(response))

    # -- the imports ------------------------------------------------------
    def test_no_network_module_is_imported(self):
        names = imported_top_level_names(SERVER.read_text(encoding="utf-8"))
        self.assertEqual(set(), names & NETWORK_MODULES, "the server imports a network module")

    def test_every_import_is_the_standard_library_or_a_repository_package(self):
        names = imported_top_level_names(SERVER.read_text(encoding="utf-8"))
        for name in sorted(names):
            with self.subTest(imported=name):
                self.assertTrue(
                    name in REPOSITORY_PACKAGES or is_standard_library(name),
                    "{0} is neither the standard library nor a repository "
                    "package".format(name),
                )

    def test_the_import_walk_reaches_the_statements_it_claims_to(self):
        names = imported_top_level_names(SERVER.read_text(encoding="utf-8"))
        self.assertIn("json", names)
        self.assertIn("subprocess", names)
        self.assertIn("ui", names)

    def test_the_network_check_can_fail(self):
        """A control: the scan is capable of finding a network import."""
        found = imported_top_level_names("import socket\nfrom urllib import request\n")
        self.assertEqual({"socket", "urllib"}, found & NETWORK_MODULES)


if __name__ == "__main__":
    unittest.main()
