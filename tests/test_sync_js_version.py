"""
Tests for scripts/sync_js_version.py -- the release-build step that
patches comms.js's SWIFT_JS_VERSION constant to match pyproject.toml,
so the two can never silently drift.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from sync_js_version import sync_js_version  # noqa: E402


def _write_fixture(tmp_path, version, constant_value):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(f'[project]\nname = "swift-sim"\nversion = "{version}"\n')

    comms_js = tmp_path / "comms.js"
    comms_js.write_text(
        "/** some header comment */\n"
        f'export const SWIFT_JS_VERSION = "{constant_value}";\n'
        "\nexport class WebSocketTransport {}\n"
    )
    return pyproject, comms_js


def test_patches_a_mismatched_constant(tmp_path):
    pyproject, comms_js = _write_fixture(tmp_path, version="3.1.4", constant_value="0.0.0")

    result = sync_js_version(pyproject_path=pyproject, comms_js_path=comms_js)

    assert result == "3.1.4"
    assert 'export const SWIFT_JS_VERSION = "3.1.4";' in comms_js.read_text()


def test_is_a_no_op_when_already_in_sync(tmp_path):
    pyproject, comms_js = _write_fixture(tmp_path, version="2.0.0", constant_value="2.0.0")
    before = comms_js.read_text()

    sync_js_version(pyproject_path=pyproject, comms_js_path=comms_js)

    assert comms_js.read_text() == before


def test_preserves_everything_else_in_the_file(tmp_path):
    pyproject, comms_js = _write_fixture(tmp_path, version="1.2.3", constant_value="1.0.0")

    sync_js_version(pyproject_path=pyproject, comms_js_path=comms_js)

    content = comms_js.read_text()
    assert "/** some header comment */" in content
    assert "export class WebSocketTransport {}" in content


def test_raises_if_pyproject_has_no_version(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "swift-sim"\n')
    comms_js = tmp_path / "comms.js"
    comms_js.write_text('export const SWIFT_JS_VERSION = "0.0.0";\n')

    with pytest.raises(AssertionError, match="couldn't find a version"):
        sync_js_version(pyproject_path=pyproject, comms_js_path=comms_js)


def test_raises_if_comms_js_has_no_constant(tmp_path):
    pyproject, comms_js = _write_fixture(tmp_path, version="1.0.0", constant_value="1.0.0")
    comms_js.write_text("export class WebSocketTransport {}\n")

    with pytest.raises(AssertionError, match="expected exactly 1"):
        sync_js_version(pyproject_path=pyproject, comms_js_path=comms_js)


def test_the_real_repo_files_are_actually_in_sync():
    # Read-only check against the real files (never calls sync_js_version()
    # itself here -- that writes, and a test shouldn't mutate real repo
    # source as a side effect even when the write would be a no-op). This
    # is what would actually catch a forgotten manual bump in local dev,
    # before a release build's automatic patch ever runs.
    from sync_js_version import COMMS_JS, CONSTANT_PATTERN, PYPROJECT, VERSION_PATTERN

    version = VERSION_PATTERN.search(PYPROJECT.read_text()).group(1)
    constant_line = CONSTANT_PATTERN.search(COMMS_JS.read_text())

    assert constant_line is not None, f"no SWIFT_JS_VERSION constant found in {COMMS_JS}"
    assert constant_line.group() == f'export const SWIFT_JS_VERSION = "{version}";', (
        "comms.js's SWIFT_JS_VERSION doesn't match pyproject.toml's version -- "
        "run `python scripts/sync_js_version.py` and commit the result"
    )
