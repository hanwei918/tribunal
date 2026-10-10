# The counterparty-statement mask

`0001-mask-counterparty-statement.patch` changes `tribunal/brief.py`, which is inside the freeze tree. It is applied
**after** the sealed run, not before the freeze: the third sealed set had already had its single run from the trees frozen
at `freeze-2026-10-09`, and that run was made without this fix.

What it fixes: POL-GEN-08(4) requires vehicle registration marks to be masked before display. At policy version 6,
_masked_dispute masked dispute.counterparty_statement only when it was a string, but the dispute schema carries it as an
object {text, submitted_by, submitted_at}, so a mark in a counterparty statement reached the model unmasked. Found by
data/external/pii-v1/case-03202.json.

Effect on existing briefs: none. Every case under data/ was briefed at policy versions 1 and 6 before and after the patch
(716 briefs); the only digest that changes is pii-v1 case 3202 at version 6. No existing case carries a mark in its
counterparty statement.

Test: tests/test_mask_counterparty.py (fails without the patch, passes with it).
