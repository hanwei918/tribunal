# The radius out of the brief docstring, and the scratch out of `runs/`

No model call was made.

## The failing test

Run outside the session's sandbox, the full suite failed exactly one test:

    tests.test_facts.GantryProximityTests.test_12_the_clauses_radius_is_not_in_either_module

That test reads `tribunal/facts.py` and `tribunal/brief.py` and asserts that the
string `250` appears in neither, because POL-RD-09(4) states its crossing radius
only in prose and every module in `tribunal/` must read such a value out of the
loaded clause rather than carry it as a literal.

Part B's `_gantry_match_radius` had quoted that prose in its docstring --
`treating any fix within 250 m of the gantry as a crossing` -- so the clause's
radius had become a literal in `brief.py`.

## The fix

The docstring now says the clause treats any fix within the clause's radius of
the gantry as a crossing. No code changed. `_gantry_match_radius` still reads the
radius out of the clause with the same regex, and `250` now appears in neither
module.

## Tests

- `python3 -m unittest tests.test_facts tests.test_brief -v` --
  `Ran 91 tests in 77.223s / OK`, with the radius test among the 91.
- `python3 -m ui.build --check` -- `ui/dist/index.html is identical to a fresh
  build (2381834 bytes)`.

## The scratch under `runs/`

Every untracked file left under `runs/` was removed: the `.patch`, `.py` and
`.log` scratch left by the earlier sessions. `git ls-files --others
--exclude-standard runs/` named every one of them; nothing tracked was touched,
and `git status` showed a clean tree afterwards.

## The buddy log

The four `wild-v1 as dev` rows (A2, A3, B and D) had been left short of two
cells -- they carried no screenshot cell and no commit cell, though the table has
seven columns. Each now carries `- (none taken)` and the hash of its own commit,
and this session has its own row.
