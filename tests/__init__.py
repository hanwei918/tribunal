"""The suite, as one package.

``python3 -m unittest`` from the repository root finds **nothing** without this
file: ``tests/`` is then not a package, so discovery never walks into it and the
suite silently runs zero tests. It carries this docstring and nothing else --
every module here imports its neighbours as ``tests.test_x``, which is what
being a package is for.
"""
