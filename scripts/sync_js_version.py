#!/usr/bin/env python
"""
Patches comms.js's SWIFT_JS_VERSION constant to match pyproject.toml's
version, in place. Run before packaging (see .github/workflows/
cibuildwheel.yml) so every built wheel/sdist ships with a JS version
string that's always correct for that exact release, with no manual
sync step to forget.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
COMMS_JS = REPO_ROOT / "src" / "swift" / "public" / "js" / "comms.js"

VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
CONSTANT_PATTERN = re.compile(r'export const SWIFT_JS_VERSION = "[^"]*";')


def sync_js_version(pyproject_path: Path = PYPROJECT, comms_js_path: Path = COMMS_JS) -> str:
    """
    :param pyproject_path: defaults to this repo's own pyproject.toml --
        overridable so tests can point at a throwaway fixture instead
    :param comms_js_path: defaults to this repo's own comms.js -- same
        reason
    :returns: the version string comms_js_path was set to
    :raises AssertionError: pyproject_path's version, or comms_js_path's
        constant, couldn't be found -- fail loudly rather than silently
        shipping a stale/wrong version
    """
    match = VERSION_PATTERN.search(pyproject_path.read_text())
    assert match, f"couldn't find a version in {pyproject_path}"
    version = match.group(1)

    content = comms_js_path.read_text()
    new_content, count = CONSTANT_PATTERN.subn(f'export const SWIFT_JS_VERSION = "{version}";', content)
    assert count == 1, f"expected exactly 1 SWIFT_JS_VERSION constant in {comms_js_path}, found {count}"

    comms_js_path.write_text(new_content)
    return version


if __name__ == "__main__":
    print(f"SWIFT_JS_VERSION set to {sync_js_version()}")
