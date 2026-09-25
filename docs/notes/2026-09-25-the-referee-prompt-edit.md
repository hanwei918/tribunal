# The referee prompt edit

**2026-09-25.** The judge prompt now receives the mechanical referee's kept
claims, discard ledger and non-discarding flags. This is a prompt change only;
no model call was made for this audit.

## Digests

| | before | after |
|---|---|---|
| `prompts/v1/judge.system.md` | `8eee6472c31e62eef627dbbf500f8fd6d0af701cc6e93b615443a8cb08fd2443` | `2d8dff1212bade160fe4bf393c9f26e9a808261c4d400786bd0fb030a7e273bb` |
| `prompts/v1/` directory | `829ccc8fe999b809be7d9fbbaaa70694aa9377f9f42f753f678bae9f29bae512` | `324d5613275d27963b713b3adef9576007b97801794551a8d0719b52e5eebd80` |

`git diff --numstat -- prompts/v1/judge.system.md` is `33 19`.
The replaced Step 1 is 155 words; the new Step 1 is 288 words.

## Exact text replaced

```text
## Step 1 — the citation check

Apply this to **every** claim from **both** sides, before any claim is weighed. Each failure
**DISCARDS** the claim and records a reason:

- **(a)** every `evidence_id` in the claim resolves in this case's `evidence`.
- **(b)** every `clause_id` in the claim resolves in the loaded policy **and** is well-formed. A
  well-formed id matches `^POL-[A-Z]{2,4}-\d{2}$`. A sub-limb reference such as `POL-NS-09(d)` is
  malformed as an id and discards the claim.
- **(c)** a claim resting on an artifact whose `weight_multiplier` is below 1.0 discloses that
  impairment and names the issue codes (POL-GEN-02(1)). Silence discards the claim.
- **(d)** a claim citing a profile field outside the nine permitted (role, field) pairs, as a ground
  of decision, is rejected under POL-GEN-01.

The **number** of discarded claims, and the **reason for each**, is part of your output. It is not
an internal step and it is not summarised away.
```

## Exact text added

```text
## Step 1 — the referee's mechanical citation check

A deterministic code referee has already applied the mechanical checks to **every** claim from
**both** sides. The `claims` arrays in your input contain only the claims the referee kept. The
`referee_ledger` contains the discarded claims, each with the side, the claim text, a closed-set
reason code and a detail explaining the check that fired. The `referee_flags` contains non-discarding
flags, including a context-only profile field mentioned in claim text.

The referee's ledger is authoritative. You may **not reinstate** a discarded claim, cite it as a
surviving ground, or retype its entry in your own `discarded_claims`. The code assembles the final
`discarded_claims` by copying the referee's entries verbatim first.

The referee checks, in order, that:

- a claim has at least one `evidence_id`;
- a claim has at least one `clause_id`;
- every `evidence_id` resolves in this case's `evidence`;
- every clause id matches `^POL-[A-Z]{2,4}-\d{2}$` and resolves in the loaded policy;
- a claim resting on an artifact whose `weight_multiplier` is below 1.0 discloses that impairment
  and names the artifact's issue codes, as POL-GEN-02(1) requires;
- `relies_on` does not name a profile field that POL-GEN-01 makes context-only.

These are code checks, not matters for your judgment. A text mention of a context-only profile field
is only a `referee_flags` warning and is **not** a discard: a claim may correctly argue that the
field cannot be used. If you discard a further kept claim, it must be for a reason the referee
cannot check (for example, using a context-only profile field as a ground in the claim's reasoning),
and you must add the side, claim text, a clear reason code and detail. Such additions come after the
  referee's copied entries in the code-assembled `discarded_claims`.
```

## Staleness channels

The prompt edit moves the prompt channel only. For the 29-case corpus,
`stale_brief=()` and `stale_prompts=(101, 102, 103, 104, 105, 106, 107, 108,
109, 110, 111, 112, 113, 114, 115, 201, 202, 203, 204, 205, 206, 207, 208,
209, 210, 211, 212, 213, 214)`. For codex,
`stale_brief=()` and `stale_prompts=(9101, 9102, 9103, 9104, 9105, 9106,
9107, 9108, 9109, 9110, 9111, 9112, 9113, 9114, 9115)`. There are no unknowns.
