"""The runtime model, decided once and recorded in one place.

The decision
------------
This system runs on **``deepseek/deepseek-flash``**, served through Tencent Cloud
TokenHub in the Singapore region.

:class:`tribunal.llm.LLMClient` deliberately has **no default model**. Until the
choice was made, a default inside the transport would have been a decision
pretending to be a convenience, so ``model`` stayed a required constructor
argument. The choice is made now, and it is written down here rather than there:
this module is the one place a reader looks for "which model does this run on",
and the transport stays model-agnostic. Nothing else in the repository writes the
model id down as a default.

The entry points read it from here when no model is named on the command line —
both the pipeline's command line and the benchmark's — so a run that says nothing
about a model still runs on a named, recorded one, and a run that names one still
overrides it. That distinction is the point: the decision is load-bearing, and
overriding it is still one flag away.

The evidence
------------
The decision is measured rather than preferred. The deciding run produced 28 of
29 cases matching on all four graded fields, with every cached result current
under the brief and the prompts this code builds now, an escalation recall of 1.0
and one over-escalation on the corpus's one genuinely contested case. Its cost
was measured from the recorded token splits of that run, not estimated.

Every measurement, how it was taken, and the limits of each comparison are
recorded in ``docs/notes/2026-09-23-runtime-model-decision.md``, together with
the alternatives and why each was rejected. Read that note before changing the
value below; the reasons are there, and the honest ones include the ones that are
weaker than they look.
"""

from __future__ import annotations

from typing import Optional

# The one place the runtime model id is written down. A reader looking for
# "which model does this run on" should find the answer here and nowhere else.
RUNTIME_MODEL = "deepseek/deepseek-flash"

# Where it is served from, named rather than left to be inferred from the
# transport, so that a move to another provider or region is one visible change.
MODEL_PROVIDER = "Tencent Cloud TokenHub"
MODEL_REGION = "Singapore"

# The note that records why, with every measurement and the method behind it.
DECISION_NOTE = "docs/notes/2026-09-23-runtime-model-decision.md"


def resolve_model(model: Optional[str] = None) -> str:
    """The model to run: the caller's choice if given, else the runtime model.

    A caller who names a model gets it, so a probe, a comparison or a deliberate
    experiment is unaffected. A caller who names none gets the decided model
    rather than an error, which is what makes the decision load-bearing rather
    than decorative. A blank or whitespace-only name counts as none: it names no
    model, and running on it would mean running on nothing.
    """
    chosen = (model or "").strip()
    return chosen if chosen else RUNTIME_MODEL
