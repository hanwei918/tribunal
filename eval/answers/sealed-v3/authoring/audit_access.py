"""Audit what files the workflow subagents touched. Prints only agent labels and offending path tokens.

usage: python3 tools/audit_access.py <workflow_transcript_dir> <workspace>
"""
import collections, glob, json, os, re, sys

D, W = sys.argv[1], sys.argv[2]
labels = {}
for line in open(os.path.join(D, "journal.jsonl")):
    o = json.loads(line)
    if o.get("type") == "started":
        labels[o["agentId"]] = o["label"]

HOME = "/Users/hanweizhou"
OUTSIDE = re.compile(r"(?<![A-Za-z0-9_.>-])(~/[^\s\"']*|\$HOME[^\s\"']*|/Users/[^\s\"']*|/private/tmp/[^\s\"']*|/tmp/[^\s\"']*|/var/folders/[^\s\"']*)|(Desktop[^\s\"']*)")
READER_BAD = re.compile(r"(out/answers|ground_truth|build/|blueprint|plan\.json|plan_notes|critique|revisions|review/round0|compare-|fixlog|reading-\d{4}-[ab])")


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


findings = collections.defaultdict(set)
calls = collections.Counter()
for f in sorted(glob.glob(os.path.join(D, "agent-*.jsonl"))):
    aid = os.path.basename(f)[len("agent-"):-len(".jsonl")]
    label = labels.get(aid, "?" + aid)
    reader = label.startswith("read ")
    m = re.match(r"read (\d{4})([ab]) r(\d)", label)
    for line in open(f):
        o = json.loads(line)
        if o.get("type") != "assistant":
            continue
        for blk in o["message"].get("content", []):
            if not isinstance(blk, dict) or blk.get("type") != "tool_use":
                continue
            calls[label] += 1
            for s in strings(blk.get("input", {})):
                t = s.replace(W, "<W>").replace(W.replace(" ", "\\ "), "<W>")
                for a, b in OUTSIDE.findall(t):
                    tok = a or b
                    findings[label].add(("outside-ws", tok[:400]))
                if reader:
                    own = "reading-%s-%s" % (m.group(1), m.group(2)) if m else None
                    for tok in READER_BAD.findall(s):
                        if own and tok == own:
                            continue
                        findings[label].add(("reader-forbidden", tok))
                    if blk.get("name") in ("Glob", "Grep", "LS") or re.search(r"(^|[;&|]\s*)(ls|find|tree)\b", s):
                        findings[label].add(("reader-listing", blk.get("name")))

print("agents:", len(calls), "| tool calls:", sum(calls.values()))
print("agents with findings:", len(findings))
for label in sorted(findings):
    for kind, tok in sorted(findings[label]):
        print("  %-28s %-17s %s" % (label, kind, tok))
