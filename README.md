# Tribunal

2026 Tencent Cloud AI Singapore Hackathon / Digital Native / Ryde / Newbee.

Official WorkBuddy project root: `/Users/hanweizhou/Desktop/Tribunal`.
Execution start: 2026-09-18; feature-freeze target: 10-10; submission deadline: 10-16 (the exact time is per the submission platform).

## What is here

**The arbitration system.** `tribunal/` is the pipeline. A case is loaded from
`data/cases/` against the manifest at `data/index.json`, a brief is built from the
public case content and the loaded policy in `policy/`, two advocates argue from that
one brief under opposite stances, and a judge rules. `prompts/v1/` holds the prompts
and `eval/` runs the benchmark and grades it against the frozen key at
`eval/answers/`.

**The debate viewer.** `ui/dist/index.html` is one self-contained page, built by
`ui/build.py` from the committed run in `runs/deepseek-deepseek-flash/`. Open it
directly: it needs no server and makes no network request of any kind, so it works
from `file://` on a machine with no internet. It carries the run's headline figures
over all 29 cases, one case stepped through in the order it was decided, and the
stance proof — that both advocates were handed byte-identical evidence and differed
only in their instructions. Rebuild it with `python -m ui.build`; the committed file
is required by test to equal a fresh build.

**The organisers' sample case.** `eval/external/ryde/DISP-002.md` is the sample
supplied to every team. It is answer-bearing, so it is not agent input.
`eval/external/ryde/convert.py` converts it into this system's case format at
`data/external/ryde/case-00901.json`, recording every decision the conversion made —
copied or judged, with reasons — in `data/external/ryde/mapping.json`. It is
deliberately absent from `data/index.json`, so the 29-case corpus the benchmark
reports is unchanged. Arbitrate it with

    python -m eval.run_benchmark --external data/external/ryde/case-00901.json

It runs into `runs/external/ryde/` and never into a model's run directory. It is not
scored: there is no answer-key entry for it, so the produced ruling is printed beside
the organisers' stated expectation, labelled as a stated expectation rather than a
verified answer.

**Reading the record.** `runs/deepseek-deepseek-flash/` holds the run the submission
reports — per case a result and a transcript, plus `run.json` and `invocations.json`.
The figures themselves live in the viewer and in `eval/grade.py`, which computes them;
they are deliberately not copied here, because a number written down twice is a number
that can disagree with itself. `docs/notes/` holds the decisions behind the numbers and
`docs/buddy-log/` records the WorkBuddy sessions.

Run the tests with `python -m unittest discover -s tests -v`.

