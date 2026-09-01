"""PyInstaller entry point for the console build.

This exists mainly so the release workflow has something it can actually run.
The GUI executable is built --windowed, so a failure there surfaces as a dialog
box on a machine nobody is watching; a console build of the same bundled code
exits non-zero and can be smoke-tested in CI. If the `passgen` package fails to
get bundled, this build fails loudly and the release stops.
"""

from passgen.cli import main

main()
