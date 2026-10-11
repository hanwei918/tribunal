# The WorkBuddy connector

A read-only MCP server that answers, from Tribunal's own committed records, the
questions a support agent working in WorkBuddy would ask: how was case 901
decided, what is waiting for a reviewer, what is in the escalation packet for
case 213.

WorkBuddy's connectors are MCP servers started over standard input and output.
`tribunal_mcp_server.py` is one: JSON-RPC 2.0, one JSON object per line. It is
Python standard library plus this repository's own modules, and it needs **no
key and no network** -- every answer is computed from files already committed
under `runs/`, from the public case files those runs were made from, from
`policy/`, and from the two operations commands the layer already ships
(`ops.queue` and `ops.escalation`, each run as a subprocess).

## Try it in one line

From the repository root:

```
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python3 integrations/workbuddy/tribunal_mcp_server.py
```

The answer is one line of JSON:

```json
{"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "tribunal", "version": "1.0.0"}}}
```

The startup line and any error go to standard error, so a pipe that reads
standard output sees protocol messages only. A whole conversation is a
sequence of lines on standard input:

```
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"tribunal_case","arguments":{"set":"ryde-v3","case":901}}}' \
  | python3 integrations/workbuddy/tribunal_mcp_server.py
```

## The `mcp.json` entry

A user adds one entry to their WorkBuddy MCP configuration. Replace
`/absolute/path/to/Tribunal` with the checkout's own path -- the entry below
carries a placeholder and no machine's path:

```json
{
  "mcpServers": {
    "tribunal": {
      "command": "python3",
      "args": ["/absolute/path/to/Tribunal/integrations/workbuddy/tribunal_mcp_server.py"]
    }
  }
}
```

Nothing else is needed. There is no API key to set and no environment variable
to name: the server reads committed files and never calls a model. After
editing the file, open the connector management page, use the custom connectors
entry at the top right, and trust the new server to enable it.

## The three tools

- **`tribunal_case`** -- `{"set": ..., "case": ...}`. The ruling in plain words,
  both amounts, the confidence, the reason code when the case went to a human,
  the opening of the judge's explanation, and the case page's path under
  `ui/dist/`.
- **`tribunal_queue`** -- `{"set": ...}`. The three lanes and how many cases
  each holds, and every case in the human-review lane with the reason it is
  there, read from `python3 -m ops.queue`.
- **`tribunal_packet`** -- `{"set": ..., "case": ...}`. An escalated case's
  escalation packet: its trigger, its ruling and money, how many drafts it
  holds, the clause ids relied on, and the packet's sha256, read from
  `python3 -m ops.escalation`.

## The sets it offers

The four committed version-6 runs -- `corpus`, `dev-v2-ext`, `dev-v2`,
`ryde-v3` -- and the three functional case sets -- `inject-v1`, `pii-v1`,
`collusion-v1`. That list is read from `eval.v6_runs.RUNS` and
`eval.func_sets.FUNCTIONAL_SET_NAMES` rather than typed into the server, so a
set added to either registry is offered without this file being edited.

## Seen in WorkBuddy

Four screenshots of a real WorkBuddy session on 2026-10-11 are committed under
`docs/buddy-log/`, one for each step:

- [`13-2026-10-11-connector-1-connector-enabled.png`](../../docs/buddy-log/13-2026-10-11-connector-1-connector-enabled.png)
  — the connector management window with `tribunal` enabled and its three tools
  listed: `tribunal_case`, `tribunal_queue` and `tribunal_packet`.
- [`13-2026-10-11-connector-2-tool-calls.png`](../../docs/buddy-log/13-2026-10-11-connector-2-tool-calls.png)
  — the owner's question and WorkBuddy calling `tribunal_case` and
  `tribunal_queue`.
- [`13-2026-10-11-connector-3-case-901.png`](../../docs/buddy-log/13-2026-10-11-connector-3-case-901.png)
  — the answer for case 901 of `ryde-v3`: `DRIVER_COMPENSATION`, SGD 4.00,
  confidence 0.9.
- [`13-2026-10-11-connector-4-corpus-queue.png`](../../docs/buddy-log/13-2026-10-11-connector-4-corpus-queue.png)
  — the answer for the `corpus` queue: 29 cases, 9 in `HUMAN_REVIEW`, 20 `AUTO`,
  0 `SAFETY_FAST_TRACK`, with the nine cases and their reason codes.

Every answer shown there matches the server's own output for the same calls.

## What it will not do

- **It never reads a sealed set.** `wild`, `wild-v2`, `sealed-v1` and `sealed-v2`
  are refused
  by name before any path is resolved, and nothing under `eval/answers/` is
  opened anywhere in the server.
- **It never answers about the answer key.** A run's own `matched` field and its
  `grade` event are read by nobody here and surfaced by nothing here.
- **It writes nothing.** No run directory, no page, no store: every tool is a
  reading, and the only processes it starts are the two `ops` commands, which
  write nothing either.
- **It makes no model call, opens no socket and launches no browser.**
