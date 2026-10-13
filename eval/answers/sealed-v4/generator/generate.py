"""Build one Tribunal version-7 test set.

usage: python3 generate.py <specs_module> <out_dir> [--canary UUID]

  specs_module  the set's specs module (a module next to this file, e.g. the one shipped with this generator)
  out_dir       receives cases/ (case files, index.json, CANARY.txt, README.md)
                and answers/ground_truth.json

Standard library only. Case files are deterministic (fixed seed per case); the canary is
a fresh uuid4 unless one is passed, so a rebuild can keep the published canary.
"""
import importlib
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tribunal_engine as eng  # noqa: E402


def main(argv):
    canary = None
    if "--canary" in argv:
        i = argv.index("--canary")
        canary = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    mod = importlib.import_module(argv[0])
    out = argv[1]
    canary = canary or str(uuid.uuid4())
    key, index = eng.build_set(mod.SET, mod.SPECS, out, canary, mod.README)
    print("{0}: {1} case files, {2} answers written to {3}".format(mod.LABEL, len(index), len(key), out))


if __name__ == "__main__":
    main(sys.argv[1:])
