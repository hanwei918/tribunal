"""Write the files the website's Try-it page loads from ``try/``.

    python3 -m tryit.build_bundle <site>/try

* ``tribunal-core.zip`` -- the Python the browser runs: ``tribunal/*.py``,
  ``tryit/*.py``, ``ops/chat_signals.py``, ``policy/**/*.json``, the four
  template cases and ``data/index.json``.
* ``templates.json`` -- each starting case as the form shows it.
* ``recorded.json`` -- each starting case's recorded version-6 ruling, read from
  ``runs/``, shown beside the visitor's scenario.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from tryit import case as scenario

ROOT = scenario.ROOT
RECORDED_RUNS = {
    208: "runs/policy-v6/deepseek-deepseek-flash/case-00208.json",
    103: "runs/policy-v6/deepseek-deepseek-flash/case-00103.json",
    901: "runs/ryde-v3/policy-v6/deepseek-deepseek-flash/case-00901.json",
    1779: "runs/dev-v2/policy-v6/deepseek-deepseek-flash/case-01779.json",
}


def core_files():
    files = sorted(p for d in ("tribunal", "tryit") for p in (ROOT / d).glob("*.py"))
    files.append(ROOT / "ops" / "chat_signals.py")
    files += sorted((ROOT / "policy").rglob("*.json"))
    files += [ROOT / rel for rel in scenario.TEMPLATES.values()]
    files.append(ROOT / "data" / "index.json")
    return files


def recorded():
    out = {}
    for case_no, rel in RECORDED_RUNS.items():
        document = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        ruling = (document.get("ruling") or {}).get("ruling") or {}
        ledger = (document.get("referee") or {}).get("ledger") or []
        out[case_no] = {
            "ruling": ruling.get("ruling"),
            "amount_sgd": ruling.get("amount_sgd"),
            "driver_compensation_sgd": ruling.get("driver_compensation_sgd"),
            "confidence": ruling.get("confidence"),
            "explanation": ruling.get("explanation"),
            "referrals": ruling.get("referrals"),
            "kept": {s: sum(1 for e in ledger if e["side"] == s and e["status"] == "KEPT") for s in ("RIDER", "DRIVER")},
            "dropped": {s: sum(1 for e in ledger if e["side"] == s and e["status"] != "KEPT") for s in ("RIDER", "DRIVER")},
            "vote_agreement": document.get("vote_agreement"),
            "seconds": round(document.get("wall_seconds") or 0, 1),
            "recorded_at": document.get("recorded_at"),
            "git_commit": document.get("git_commit"),
            "brief_sha256": document.get("brief_sha256"),
        }
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out / "tribunal-core.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in core_files():
            bundle.write(path, path.relative_to(ROOT).as_posix())
    (out / "templates.json").write_text(json.dumps(scenario.template_summaries(), ensure_ascii=False), encoding="utf-8")
    (out / "recorded.json").write_text(json.dumps(recorded(), ensure_ascii=False), encoding="utf-8")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
