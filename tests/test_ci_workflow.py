"""The CI workflow: what it runs, and what it must not carry.

The suite is the repository's own claim about itself, and until this part nothing
ran it on a machine that was not the author's. ``.github/workflows/tests.yml`` runs
it on four runners -- two operating systems by two interpreters -- and this module
holds the workflow to what the part promised, reading the YAML as **text**: no YAML
library, so a workflow that parsed would make the suite depend on one it does not
have.

What it holds:

* the file is committed;
* the matrix names both operating systems and both Python versions;
* the checkout fetches the whole history (``fetch-depth: 0``), because the history
  tests read ``git check-ignore`` and the sealed run's manifest;
* it runs the suite (``unittest discover -s tests``) and ``tools.verify --quick``;
* it reaches no credential: no ``secrets.`` reference and none of the variables a
  workflow would use to name a key. No step calls a model.

No model call, no network, and nothing here reads a run.
"""

from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "tests.yml"

# The two runners and the two interpreters the matrix names, as they are written.
# Ubuntu is named by release since part 121: `ubuntu-latest` became 26.04, which
# has no Python 3.9.
OPERATING_SYSTEMS = ("ubuntu-24.04", "macos-latest")
PYTHON_VERSIONS = ('"3.9"', '"3.13"')

# The names a workflow would use to reach a credential. The workflow runs no
# model, so none of them may appear.
FORBIDDEN = ("secrets.", "TOKENHUB", "API_KEY", "OPENAI", "DEEPSEEK")


def workflow() -> str:
    """The workflow, read as text, so a failure names the file it read."""
    return WORKFLOW.read_text(encoding="utf-8")


class TheCiWorkflowTests(unittest.TestCase):
    """One workflow, four runners, and no credential."""

    def test_the_workflow_is_committed(self):
        self.assertTrue(
            WORKFLOW.is_file(),
            ".github/workflows/tests.yml is not committed",
        )

    def test_it_names_both_operating_systems(self):
        text = workflow()
        for name in OPERATING_SYSTEMS:
            with self.subTest(os=name):
                self.assertIn(
                    name,
                    text,
                    ".github/workflows/tests.yml does not name {0}".format(name),
                )

    def test_it_names_both_python_versions(self):
        text = workflow()
        for version in PYTHON_VERSIONS:
            with self.subTest(python=version):
                self.assertIn(
                    version,
                    text,
                    ".github/workflows/tests.yml does not name Python {0}".format(
                        version
                    ),
                )

    def test_it_fetches_the_whole_history(self):
        """The history tests read the tags and the log, so a shallow clone fails."""
        self.assertIn(
            "fetch-depth: 0",
            workflow(),
            ".github/workflows/tests.yml does not fetch the whole history",
        )

    def test_it_runs_the_suite_and_the_quick_verify(self):
        text = workflow()
        self.assertIn(
            "unittest discover -s tests",
            text,
            ".github/workflows/tests.yml does not run the test suite",
        )
        self.assertIn(
            "tools.verify --quick",
            text,
            ".github/workflows/tests.yml does not run tools.verify --quick",
        )

    def test_it_reaches_no_credential(self):
        text = workflow()
        for name in FORBIDDEN:
            with self.subTest(name=name):
                self.assertNotIn(
                    name,
                    text,
                    ".github/workflows/tests.yml names {0!r}, a credential "
                    "variable".format(name),
                )


if __name__ == "__main__":
    unittest.main()
