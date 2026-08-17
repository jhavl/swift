"""
Tests for swift.__version__ -- installed via importlib.metadata off the
swift-sim distribution, so it always matches whatever was actually built,
with no separate constant to fall out of sync.
"""

import re
from pathlib import Path

import swift


def test_version_is_a_non_empty_string():
    assert isinstance(swift.__version__, str)
    assert swift.__version__


def test_version_matches_pyproject():
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(), re.MULTILINE)
    assert match, f"couldn't find a version in {pyproject}"
    assert swift.__version__ == match.group(1)
