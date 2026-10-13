# Catalogue development

Keep source pins, composition, provenance and minimal authored corrections here. Never commit fetched sources, copied rules prose, generated JSON or archives; publish generated files as verified release assets.

Keep saved-roster compatibility declarations, retained-build recipes and coverage exceptions here. The application owns their generic interpreters, compiler and domain semantics. Pin the compiler to a full Git commit in `compiler.json`; do not duplicate its implementation.

Corrections belong in `catalogue/patches/`. Verify their exact pinned source and provenance, materialize affected sources, and run the pinned compiler checks before publication. Preserve released rules identities and history.

Publication must verify both mirrors before advancing discovery pointers. Application builds retain exact release hashes; publication never changes production rules by itself.
