# What is synthetic, and how real data may differ

Every dispute this repository reports on is synthetic, semi-synthetic, or the
organisers' own sample. This file says which is which, who wrote each set, and
where Ryde's real traffic would differ from what was measured.

## Who wrote each set

The rows below are the record's own provenance table, condensed
([the full record](record.md), "Results", "Where the test sets came from").

| set | author and tool | role |
|---|---|---|
| the 29-case corpus | this team, with Claude Code: 29 case specifications expanded into evidence by a deterministic generator (`random.Random(42)`), before 2026-09-18; the generator is not in this repository | development |
| `dev-v2`, `dev-v2-ext` | Ji Guofang, the key owner, with her generator `eval/synth/make_dev_set.py` | development |
| `codex` | OpenAI Codex, drafted 2026-09-24, copied in by the owner | development |
| `wild` (v1) | the policy owner, Ji Guofang, with Claude | development and regression data |
| `wild-v2` | OpenAI Codex, for the owner | sealed |
| `sealed-v1` | Claude, created 2026-09-26 | sealed |
| the functional sets | the policy owner's archive | development |
| `sealed-v2` | the policy owner, with OpenAI Codex | sealed |

**The 29-case corpus's origin, in the record's own words.** Its row reads "this
team, with Claude Code: 29 case specifications expanded into evidence by a
deterministic generator (`random.Random(42)`)", dated "before 2026-09-18", with
the project material it was written against named as "the organisers' brief (the
dispute types); the corpus predates this repository", and its key recorded as
written "under policy version 1 and never edited". It is this team's own work; it
is not a set the organisers supplied.

**No test set came from outside the team.** Every one was written by a member of
the project, by a model the team directed, or by a collaborator the team
commissioned ([the full record](record.md), "Results").

## The one organisers' case

[`data/external/ryde/case-00901.json`](../data/external/ryde/case-00901.json) is
the organisers' sample case, converted from
[`eval/external/ryde/DISP-002.md`](../eval/external/ryde/DISP-002.md), and it is
the **only** case in this repository that came from them. It is deliberately
absent from [`data/index.json`](../data/index.json), so the 29-case corpus the
benchmark reports is unchanged by it, and it is not scored: the organisers'
stated expectation is printed beside the run's ruling and labelled a stated
expectation rather than a key
([the full record](record.md), "The organisers' sample case").

Every other dispute on the site and in the runs is this project's own writing.

## Where real data may differ

- **The mix of categories.** The corpus holds two of the brief's four scenarios:
  15 `ROUTE_DEVIATION` cases and 14 `NO_SHOW_CHARGE` cases
  ([`data/index.json`](../data/index.json);
  [`data/PUBLIC-CONTRACT.md`](../data/PUBLIC-CONTRACT.md) states the same two
  figures). Property damage needs image analysis the pipeline does not do, and a
  safety incident goes to a person, so real traffic would carry cases the system
  deliberately does not adjudicate.
- **The amounts.** The corpus's contested amounts run from 4.00 to 65.13 SGD over
  twelve distinct values ([`data/cases/`](../data/cases)). `POL-GEN-05`'s
  execution threshold is SGD 8.00, so a real mix with more disputes above that
  line would send a larger share of cases to a person for release.
- **Singlish and code-switching in chat.** Party text is written the way people
  write: case 203's claim reads "Driver cancel after 3 minutes only! I was coming
  down already, my block lift very slow. Then charge me $4. The app itself say
  must wait 5 minutes what."
  ([`data/cases/case-00203.json`](../data/cases/case-00203.json)), and the case's
  own note records that a message in it is code-switched and genuinely
  contestable. The threat rules in
  [`ops/chat_signals.py`](../ops/chat_signals.py) are written for English, and
  the site says so on the try-it page: a threat written in Chinese is not
  detected.
- **GPS quality.** Every scored set here uses about 10-second GPS fixes with a
  horizontal accuracy, while Ryde's sample carries 2 to 4 minute fixes and no
  accuracy field at all ([the full record](record.md), "The organisers' sample
  case", "Integrating with Ryde"). On Ryde-format data the GPS no-show tests
  cannot run: 901 was decided on the platform's own arrival and wait-timer events
  under `POL-NS-12`, and route deviation on Ryde-format data is untested.

## What is not measured

Real Ryde data. There is no live feed, no production queue and no deployment; the
runs are over committed case files, and the figures this repository reports are
figures about those files. [The full record](record.md), "Limitations and
disclosures" states the same in its own words, with the corpus's evidence notes —
which carry the case author's reasoning — among the disclosures.
