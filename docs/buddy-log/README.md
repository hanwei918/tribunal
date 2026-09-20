# WorkBuddy actual usage record

Fill in only sessions that have already happened; do not pre-fill success records. Check the account and sensitive information before making screenshots public.

| Date | Member | WorkBuddy task | Artifact | Verification | Screenshot | commit (if any) |
|---|---|---|---|---|---|---|
| 2026-09-20 | Zhou Hanwei | Preflight check of the workspace | `docs/notes/2026-09-20-preflight.md` | Reported the actual working directory, the top-level listing, Python 3.13.12, and that `requirements.txt` declares no dependencies | `2026-09-20-hanwei-01-preflight.png` | `1e7a2c5` |
| 2026-09-20 | Zhou Hanwei | Initialise the repository under version control | Git repository on `main`; initial commit `1e7a2c5` (52 files) | `git add -A --dry-run` confirmed no private balance path, no `.DS_Store`/`.venv`/`__pycache__`/`.env`/PDF, and all six `.gitkeep` files staged | `2026-09-20-hanwei-02-git-init.png` | `1e7a2c5` |
| 2026-09-20 | Zhou Hanwei | English documentation pass: rewrite six documents into English and add the standing language rule | `README.md`, `START-HERE.md`, `WORKBUDDY-HANDOFF.md`, `docs/notes/2026-09-18-bootstrap.md`, `docs/notes/CREDITS.md`, `docs/buddy-log/README.md`, `WORKBUDDY-SCOPE.md` | Scan of all 52 tracked files found 0 files containing Chinese characters; a positive control confirmed the pattern detects Chinese | - | `b21622a` |
| 2026-09-20 | Zhou Hanwei | Cleanup: ignore WorkBuddy local state, rename the buddy-log screenshots, and fill this table | `.gitignore`; `docs/buddy-log/2026-09-20-hanwei-01-preflight.png`; `docs/buddy-log/2026-09-20-hanwei-02-git-init.png`; `docs/buddy-log/README.md` | `git add -A --dry-run` and the pre-commit checks passed: `.workbuddy-ai/` was not staged, no private balance path was staged, no `.DS_Store` or PDF was staged, and no staged file contained Chinese characters | `2026-09-20-hanwei-03-cleanup.png` | `b21622a` |
| 2026-09-20 | Zhou Hanwei | Extend the public runtime contract by measuring the real corpus | `data/PUBLIC-CONTRACT.md` | Measured all 29 cases, 204 evidence artifacts and 24 clauses with Python and wrote every result into the contract; verified with `git diff` that the runtime bundle boundary and deterministic serialisation sections were unchanged, and that the file contains no Chinese characters | | - |

The sessions above are the first actual WorkBuddy session records. Repository preparation and manual rewriting were assisted by Codex; subsequent development is recorded by actual tool attribution.
