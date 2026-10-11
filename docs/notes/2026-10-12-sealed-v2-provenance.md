# The fourth sealed set's provenance, said exactly (2026-10-12)

**Where this starts.** The current `main`, after part 48 (`b4c6d56`). This part
changes documents, the summary strings in `eval/development_sets.py`, and the
tests that pin what it changes. **No model call was made and no test was run
here** -- the owner runs every test outside the sandbox. Nothing under `runs/`,
`tribunal/`, `prompts/`, `policy/`, `data/` or `eval/answers/` was changed: the
sealed-v2 answer archive is read-only for this repository and was read only as
the digest table below records.

**What the owner decided on 2026-10-12.** The three statements the fourth sealed
set's own manifest and this repository's registration disagreed about -- who
made it, whether its review gate was met, and which freeze it was run from --
are stated once, exactly, in the places a reader meets them.

## 1. Who and what

`sealed-v2` was **made by the policy owner, Ji Guofang, with OpenAI Codex**. She
states the model was **GPT-6**. The tool's own manifest could not name the model,
so **the model name is her attestation and not a recorded fact**.

The manifest's `author` field is the one place the tool says what it was, and it
is quoted once here:

> OpenAI Codex (GPT-based assistant; exact underlying model name and version are
> not exposed in this session)

Its `model_identity_status` is `UNVERIFIED: exact underlying model name and
version are not exposed to this assistant; no model version has been guessed`,
and its second release gate asks the owner to "obtain exact model name and
version from a trustworthy session record before claiming the model-version
disclosure requirement is fulfilled". That gate is **not fulfilled**, and this
note does not treat GPT-6 as recorded.

**The short form, everywhere.** The README's provenance row, the description,
the judges' questions and `eval/development_sets.py`'s `SEALED_V2` summary now
read the same sentence:

> made by the policy owner with OpenAI Codex (model stated by her as GPT-6; not
> recorded by the tool)

The five earlier statements that read "made with GPT-6" were each read from the
file they came from and rewritten to that one sentence.

## 2. The review gate was not met, and the review is pending

The manifest's **first** release gate is:

> Ji Guofang must review and sign all 12 cases against original policy text
> before the sealed run.

**That did not happen.** The gate sits in the answer archive, at
`eval/answers/sealed-v2/`, and the development side does not open that
directory: the import extracted archive B straight into place with `unzip` and
never opened a file of it. So nothing on the development side read the gate
before the run, and the owner ran the set on **2026-10-11 at 16:12** without it
-- the run is recorded in `docs/notes/2026-10-11-the-fourth-sealed-run.md`. The
manifest's own `review_status` says the same thing in its own words:
`PENDING: designated reviewer has not yet supplied case-by-case sign-off`.

**The review is pending, not made after the run.** No `review-signoff.json`
exists in `eval/answers/sealed-v2/` at the time this note was written; the
directory holds `MANIFEST.json`, `REVIEW_GUIDE.md`, `review_checklist.json`,
`additional_audit_output.txt`, `check_set.py`, `check_set_output.txt` and
`ground_truth.json`, and nothing else. Had a sign-off been there, this note
would say the review was made **after** the run by someone who had seen the
result, which is not the same thing as the gate. It is not there, so the review
is pending.

## 3. The freeze point: two tags, one brief

The manifest's `protocol.run_from` names **`freeze-2026-10-09`**. The run was
made from **`freeze-2026-10-11`** -- commit `19c7e5a`, the commit the annotated
tag points at. The two tags are not the same tree:

    git diff --stat freeze-2026-10-09 freeze-2026-10-11 -- tribunal prompts policy

    tribunal/brief.py    |  77 +++--
    tribunal/events.py   |   6 +
    tribunal/llm.py      |  44 ++-
    tribunal/pipeline.py | 817 ++++++++++++++++++++++++++++++++++++++++++++++++++-
    4 files changed, 898 insertions(+), 46 deletions(-)

`prompts/` and `policy/` are identical at the two tags, and the four files that
differ are all under `tribunal/`.

**What is checked, and how.** For each of the 12 cases the brief is built twice
-- once with the `tribunal/` and `policy/` trees at each tag -- at **policy
version 6**, and the sha256 of the canonical bytes is compared with the digest
the run recorded. The two trees are materialised as two `git worktree`s, and the
12 case files are copied into each worktree so that each tag's own loader
resolves them (they are byte-identical to the archive's, and
`docs/notes/2026-10-11-sealed-v2-imported.md` records their digests).

**The exact commands.**

    git worktree add --detach /tmp/wt-1009 freeze-2026-10-09
    git worktree add --detach /tmp/wt-1011 freeze-2026-10-11
    for w in /tmp/wt-1009 /tmp/wt-1011; do
      mkdir -p "$w/data/external/sealed-v2"
      cp data/external/sealed-v2/case-*.json \
         data/external/sealed-v2/index.json "$w/data/external/sealed-v2/"
    done

The probe, written once to `/tmp/briefcheck.py`, builds each brief with the
worktree's own `tribunal.brief.build_brief_for_case` and prints
`tribunal.brief.brief_digest`'s sha256:

    import json, sys
    from pathlib import Path
    from tribunal import brief, loader

    out = {}
    for raw in sys.argv[1:]:
        case = loader.load_external_case(Path(raw))
        canonical, digest = brief.brief_digest(
            brief.build_brief_for_case(case, policy_version=6)
        )
        out[str(case["case_no"])] = digest
    print(json.dumps(out, sort_keys=True, indent=1))

    cd /tmp/wt-1009 && PYTHONPATH=/tmp/wt-1009 python3 /tmp/briefcheck.py \
        /tmp/wt-1009/data/external/sealed-v2/case-*.json > /tmp/briefs-1009.json
    cd /tmp/wt-1011 && PYTHONPATH=/tmp/wt-1011 python3 /tmp/briefcheck.py \
        /tmp/wt-1011/data/external/sealed-v2/case-*.json > /tmp/briefs-1011.json

and the two results are compared with each other and with the digest each of the
run's own case files records at `brief_sha256`:

    for n in 801 802 803 804 805 806 851 852 853 854 855 856; do
      python3 -c "import json;print(json.load(open('runs/sealed-v2/deepseek-deepseek-flash/case-%05d.json' % $n))['brief_sha256'])"
    done

**The result: all 12 are equal at both tags, and all 12 equal the digest the run
recorded.**

| case | brief sha256 (both tags, and the run's record) |
|---|---|
| 801 | `7a714819301b5e3965eb2acf50a3cd1000c6b6bf09ef04ca46cb3098316230fa` |
| 802 | `3c1077cf5519eccc18e2d1f852f57042f7d518fe8ee9b7e2f60582ccb799ace2` |
| 803 | `9d272670a7e186a1a2890bb6e81353443d75dc5dcd135ea237cf39ffd887bad8` |
| 804 | `18c05076029fc524f6350ef390a0eb662d43f04e9220e813be90301a015440a3` |
| 805 | `d57421e019da7cb37761f43ed122240a05600d7a19851cee6d080d92a37fd833` |
| 806 | `8844551714db3c2ecd1bbd569b35eb59203214f96b19653738434c7ee34323cc` |
| 851 | `31cb7a159e4fec06c840d719d5e7d5604fe532eaa29ed4dca73d7a0e060614da` |
| 852 | `f17383fd1e2493b62b0bfee9c4d877e3cbe896b6a45f8bb26d10a86855b45e19` |
| 853 | `d7bae30748a510ba37804c9f23b5c1f6406cbd2e52f618c24934b909c006bc8f` |
| 854 | `b80bc0e158f322864d3cc37e8cae3d0ec101cc5a27720cfb41bf284c8fe3aef3` |
| 855 | `859b4e6661ba3adfc40d4f2badba8437d1059a3677984665b5cafcbd4f8c20bd` |
| 856 | `91785a4b02278659686b9598203fb82af120f6fa1aca4071ef44179b86cf7e89` |

**So the difference between the two tags does not matter for these cases.** The
four files that differ are `tribunal/`'s, and none of their changes reaches the
brief of any of the 12: `prompts/` and `policy/` are identical at the two tags,
the cases carry their own `trip_record.platform_policy` block, and the 12 briefs
the tag `freeze-2026-10-09` builds are byte-identical to the 12 briefs the tag
`freeze-2026-10-11` builds -- which are the 12 briefs the run itself recorded.
The manifest's `run_from` names an earlier tag than the run was made from, and
the mismatch is immaterial rather than hidden: every case was decided on the
brief both tags build.

## Where it goes

- This note; the README's provenance row for `sealed-v2`; `description.md`;
  `qa.md`; and `eval/development_sets.py`'s `SEALED_V2` summary.
- No answer file was touched. `eval/answers/sealed-v2/` is read-only here, and
  the one file this part read from it is the manifest, for the `author` string
  quoted above and for the two release gates.
