"""The product site, built from the repository's own sources.

``tools/site_import.py`` transcribed the policy owner's design into
``ui/site/src/`` and ``ui/site/static/``; this package builds the site from
them. ``ui/site/build.py`` is the builder and this module is only the package
marker, so ``python3 -m ui.site.build`` runs.
"""
