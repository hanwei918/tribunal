"""The operations layer: what a support team runs around the pipeline.

``ops/`` reads the pipeline's inputs -- the public case files and the loaded
policy -- and the pipeline's recorded outputs, and it never feeds anything back
into a brief or a prompt. Nothing in ``tribunal/`` or ``eval/`` imports it, and
no module here imports ``tribunal.llm`` or any network client, so a run made
through this layer is the same run the pipeline would have made.

**The three rules the whole layer is held to.** They are stated once, here, so a
module added later is held to the same ones rather than to a fresh reading of
them:

* **It never reads an answer.** No module opens an answer key, a ``grade``
  event, or anything under an ``answers`` directory.
* **It writes nothing unless it is given ``--out``.** And an ``--out`` is
  refused inside ``runs/``, ``data/``, ``policy/``, ``prompts/``, ``tribunal/``,
  ``eval/answers/`` or either sealed root, through
  :func:`eval.sealed_roots.refuse_a_sealed_destination`.
* **Every threshold it applies is read from the loaded policy text.** A sentence
  that has moved or changed is refused rather than resolved against a number
  written in Python.

The write guard is the one piece of shared code the layer needs, and it is not
here yet: part 1's command reads and prints and has no ``--out`` at all, so
there is no destination for it to refuse. It arrives with the first command that
takes one.
"""
