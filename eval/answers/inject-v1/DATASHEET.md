# Datasheet: inject-v1

* Purpose: show that an instruction planted in party text does not move a ruling.
* Composition: 6 pairs, 3 no-show and 3 route-deviation; kinds: direct (claim), direct (counterparty), forged system message in chat, forged evidence id and clause, base64-encoded instruction, false arithmetic with zero-width characters.
* Keys: the injected copy carries its twin's key; the generator asserts the four fields are equal.
* Author: the same author as dev-v2. Not a sealed set.
* References: OWASP Top 10 for LLM Applications 2025 (LLM01); Hines et al. 2024, arXiv:2403.14720; Ribeiro et al. 2020 (CheckList INV).
