# prompts/v1

## The files

| File | What it is |
|---|---|
| `advocate.system.md` | The system prompt for **both** advocates. One file, one `{{STANCE}}` placeholder, no side-specific text. |
| `stance.rider.md` | The block substituted into `{{STANCE}}` when the RIDER argues. |
| `stance.driver.md` | The block substituted into `{{STANCE}}` when the DRIVER argues. |
| `judge.system.md` | The system prompt for the impartial judge. |

## One advocate prompt, not two

There is exactly **one** advocate prompt. The rider advocate and the driver advocate are the same
file with `{{STANCE}}` substituted. Everything else — every rule, every field list, every output
requirement — is byte-identical between them. That is literally true: the template is not duplicated
into two files with small edits, and the two rendered prompts differ only inside the stance block.
`{{STANCE}}` appears exactly once in `advocate.system.md`.

## How they are combined

1. **Render the advocate prompt twice.** `advocate.system.md` with `{{STANCE}}` replaced by the
   contents of `stance.rider.md`; and again with the contents of `stance.driver.md`.
2. **Send both renders the same `brief`.** Build the brief once for the case and pass the identical
   object to both advocates. Both read the same evidence, the same derived facts and the same
   policies; only the stance differs.
3. **Collect both claim arrays.** Each advocate returns a JSON array of claim objects.
4. **Send the judge the two arrays and the same brief**, together with the full policy the brief
   carries.
5. **The judge returns the POL-GEN-03 ruling object.**

The two rendered advocate prompts must differ only inside the stance block. Any other difference is a
defect.
