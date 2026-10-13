<p align="center">
  <img src="ui/assets/cover-1280.jpg" alt="Tribunal poster: a robot judge between a rider and a driver" width="760">
</p>

<h1 align="center">Tribunal</h1>

<p align="center">
  <a href="https://tribunal.edgeone.dev/"><img src="https://img.shields.io/badge/live%20demo-tribunal.edgeone.dev-6d28d9" alt="Live demo"></a>
  <a href="https://tribunal.edgeone.dev/try.html"><img src="https://img.shields.io/badge/try%20it-in%20your%20browser-6d28d9" alt="Try it"></a>
  <img src="https://img.shields.io/badge/python-3.9%20%7C%203.13-blue" alt="Python 3.9 and 3.13 (both tested)">
  <img src="https://img.shields.io/badge/dependencies-none-brightgreen" alt="No dependencies">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT licence"></a>
</p>

<p align="center"><sub>Poster made with Miora (Tencent); the people in it are generated, not real people.</sub></p>

**Tribunal settles ride-hail disputes in under three minutes at the median, and stops when it isn't sure.**
Two AI lawyers argue the rider's and the driver's side from the same evidence pack.
Plain code throws out any point that does not cite real evidence and a real rule.
An AI judge rules four times, once with the two sides swapped, and three must agree.
When the judge is unsure or the rulings split, nobody guesses: the money is frozen
and a person decides.

Built for the 2026 Tencent Cloud AI Singapore Hackathon (Digital Native track, the
Ryde challenge) by team Newbee, with WorkBuddy.

**Start here.**

- **Live demo:** <https://tribunal.edgeone.dev/> — the queue at `/queue.html`, case 208 at `/case-00208.html`, the organisers' sample case 901 at `/case-00901.html`.
- **Submission texts:** [`docs/submission/`](docs/submission/) · **Architecture:** [`docs/architecture.md`](docs/architecture.md)
- **How it was built:** [`docs/submission/how-we-built-it.md`](docs/submission/how-we-built-it.md)
- **What it does not do:** [Limitations and disclosures](docs/record.md#limitations-and-disclosures)

## The product site

The front page is the **product site** the policy owner, Ji Guofang, designed outside WorkBuddy: 22 pages, each in English (`*.html`) and Chinese (`*.zh.html`), with her images and a try-it page that runs this repository's own Python in the browser.
The queue is at `/queue.html`, and the live try-it service stays **off**: `try-config.js` leaves its address empty, so the page's in-browser checks run and no live run is offered.
Her design, her page text and her front-end code are hers, imported unchanged and built here by `ui/site/build.py`; the try-it service `tryit/` is hers too.

## In numbers

151 disputes at policy version 6 (the corpus, `dev-v2-ext`, case 1779 and the
organisers' case 901), read off the committed runs by
`python3 -m eval.business_value --report`. No figure below needs a key to recompute.

| | Tribunal | Today |
|---|---|---|
| Time to a decision | **160.4 s** median, 286.9 s at the 90th percentile | 24–72 hours per dispute (the Ryde brief) |
| Model cost per case | **0.0579 USD** median | — |
| Decided with no person needed | **112 of 151** (74.2%) | every case |
| Sent to a person | 26 with no ruling, 13 ruled but above SGD 8 so a person releases the money | — |

## What makes it different

| | |
|---|---|
| **Two sides, one judge** | A rider's AI lawyer and a driver's AI lawyer read byte-identical evidence. Their instructions differ only in whose side they are on, and the code checks that before any call. |
| **No proof, no point** | A deterministic referee drops any claim that cites no evidence id or no clause id, or cites one that does not exist. It never picks a winner. |
| **Never one shot** | The judge drafts four rulings, one with the parties' positions swapped. The swapped ruling matched the others on all four graded fields in 136 of 141 cases. |
| **Money by code** | Distances, waiting time, fares, surge and promo lines are computed in `Decimal` and handed to the agents. A draft whose amount does not match a figure code allows is refused. |
| **Knows its limits** | Below a confidence of 0.70, or when the drafts split, no ruling is issued. Safety-flagged disputes never reach a model. Either side may appeal once within 30 days, and `auto_rulings_enabled` switches automatic rulings off. |
| **Hard to fool** | Six attacks planted in party text (a forged system message, a fake clause, base64, zero-width characters): 5 rulings unchanged, 1 sent to a person, none flipped. |
| **On the record** | Every call and check goes into a hash-chained event log. An offline test replays 128 recorded cases with no model call and checks each request against the recording. |
| **An operations layer** | A queue with service targets, an escalation packet for the reviewer, an evidence window, appeals, fraud signals, and a read-only WorkBuddy connector. |

<p align="center"><img src="docs/architecture.svg" alt="Tribunal architecture" width="760"></p>

## Quick start

Python 3.9 and 3.13 (both tested) and nothing else: `requirements.txt` declares no dependency.

```bash
git clone <this repository> && cd tribunal
python3 -m tools.verify                   # every check below, in one command
python3 -m eval.v6_runs --report          # every development figure, from the committed runs
python3 -m eval.business_value --report   # the numbers above
python3 -m unittest discover -s tests     # the full suite
```

None of these makes a model call or needs a key. Clone rather than download a zip:
27 tests read the git history and skip without it. On Linux, the tests that rebuild
case 111's brief also skip, because glibc and macOS libm differ in the last digit of
one distance ([why](docs/record.md#limitations-and-disclosures)).

To arbitrate a case for real you need a Tencent Cloud TokenHub key:

```bash
export TOKENHUB_API_KEY=...
python3 -m eval.run_benchmark --cases 101 --policy-version 6 --runs-dir /tmp/tribunal-runs
```

## Commands

| Command | What it does |
|---|---|
| `python3 -m eval.v6_runs --report` | Agreement, escalation precision and recall, cost and time for every version-6 run |
| `python3 -m eval.fairness --report` | Errors by side, position-swap agreement, calibration |
| `python3 -m eval.sealed_report --set sealed-v2` | One test set's result against its own key |
| `python3 -m ops.queue --run-dir runs/policy-v6/deepseek-deepseek-flash` | The queue: lane, reason, due time for every case |
| `python3 -m ops.escalation --run-dir <run> --case N --format md` | The packet a human reviewer is handed |
| `python3 -m ops.risk --case N` | The fraud and bad-faith signals for one case |
| `python3 -m tribunal.precedents list` | The precedent library |
| `python3 -m tryit.server --recorded-test` | The try-it service, answering from a recording (no key) |

## Results

Agreement with each set's own key, on sets written apart from the code and run once
on frozen code. They are never pooled. None came from outside the team, and what
each author had seen is part of the result:

| Set | Agreement | Wilson 95% | Who wrote it, and what was seen early |
|---|---|---|---|
| `wild-v2` (20 cases) | 18/20 | [69.9%, 97.2%] | OpenAI Codex for the policy owner; nobody on the development side opened it |
| `sealed-v1` (24 cases) | 21/24 (20/24 under the key as imported) | [69.0%, 95.7%] | Claude; the policy owner's AI assistant opened the cases and key before the freeze, and case 311's key changed before the run |
| `sealed-v2` (12 cases) | 12/12 | [75.8%, 100.0%] | The policy owner with OpenAI Codex, after seeing development results. Reviewed case by case after the run (2026-10-13) and adopted by the policy owner as her sign-off; the review was made with her AI assistant (Claude), which knew the 12/12 result. All 12 answers were found consistent with the version-6 policy, and none was changed. The pre-run sign-off the manifest asked for was not made |

Development data, reported as such: `dev-v2-ext` 115/120 and the 29-case corpus
26/29 at version 6. The full tables, every figure's recompute command, and each
set's provenance are in [the full record](docs/record.md#results).

## Documentation

| Document | What's covered |
|---|---|
| [The full record](docs/record.md) | Every result table and its command, test-set provenance, limitations, concurrency, how to run everything |
| [Why a debate](docs/why-debate.md) | The five mechanisms, and the paper the design comes from |
| [Design choices](docs/design-choices.md) | The two places the build departs from the brief, and what each buys and costs |
| [Scale and cost](docs/scale.md) | What one model account can carry, and what a month would cost |
| [Integration](docs/integration.md) | The input contract, the ruling's fields, routing, the queue, the packet, appeals |
| [Data](docs/data.md) | Who wrote each set, the one organisers' case, and how real data may differ |
| [Architecture](docs/architecture.md) | The four C4 views, box by box, with the file behind each box |
| [Submission texts](docs/submission/) | Blurb, description, judges' questions, how we built it |
| [Demo script](docs/submission/demo-script.md) | A three-minute live demo, step by step |
| [Governance](docs/governance/) | Threat model, privacy, incidents |
| [Policy sources](docs/policy-sources.md) | Where each policy clause comes from |
| [Dated notes](docs/notes/) | One note per change or run, written when it happened |
| [WorkBuddy log](docs/buddy-log/README.md) | One row per WorkBuddy session, with screenshots |
| [WorkBuddy connector](integrations/workbuddy/) | A read-only MCP server over the committed records |
| [Try-it service](tryit/README.md) | The website's live-run service, its limits and how to run it |
| [Changelog](CHANGELOG.md) | Every change since `freeze-2026-10-11`, one line per part, and the command that shows the frozen tree has not moved |

## Team and licence

Team Newbee: Zhou Hanwei, Ji Guofang, Yan Lin. Built with WorkBuddy; the
[buddy log](docs/buddy-log/README.md) records every session.

MIT — see [LICENSE](LICENSE). Case 901 is the organisers' sample and remains their
material; third-party material is listed in [the full record](docs/record.md#third-party-material).
