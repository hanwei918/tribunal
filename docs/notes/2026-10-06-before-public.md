# Before the repository goes public (2026-10-06)

The owner is about to make this repository public, and the four parts of the task
sheet dated 2026-10-06 prepare it for a reader who has never seen it. **No model
call was made in any part, and no browser was launched.** The repository's
visibility is the owner's to change and is not changed here.

Three decisions the owner took before the work started, recorded because each
one is visible in the repository afterwards:

- the git history stays as it is and is not rewritten;
- the licence is MIT;
- the Ryde sample stays, and the owner will ask the organisers whether it may be
  redistributed; if the answer is no it will be removed later.

Nothing under `tribunal/`, `prompts/`, `policy/` or `runs/` changes. The one
file under `runs/` that this task touches is `runs/README.md`, which is the
directory's own description rather than a recorded run file; the paths recorded
inside the run files stay exactly as the machine wrote them.

## A. The licence

`LICENSE` is new: the standard MIT text, with the copyright line the owner
specified, `Copyright (c) 2026 Zhou Hanwei, Ji Guofang and Yan Lin (team
Newbee)`.

The README gains a **Third-party material** section at its end. It names the
organisers' sample material — which the Tencent Cloud AI Agent Hackathon
Singapore 2026, Digital Native track (Ryde), gave to participants — and every
file derived from it, each by its exact path: `eval/external/ryde/DISP-002.md`,
`eval/external/ryde/expected.json`, `data/external/ryde/`, `runs/external/ryde/`
and `runs/rerun-2026-09-29/external/ryde/`. It says the files are included only
to show how this system handles that sample, and that they are not covered by
the MIT licence.

`tests/test_repository_hygiene.py` gains the one-line check that `LICENSE` is
there and starts with `MIT License`. It sits in that module rather than in a
module of its own because the module is already about what the repository
carries for a reader who is not its author.
