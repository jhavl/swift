"""
Smoke test for examples/ -- runs every example script as a subprocess
under SWIFT_HEADLESS=1 and checks it doesn't raise within a short window.

Most examples end in an intentionally endless env.hold()/env.run()/
while-True (interactive demos meant to keep a browser tab open), so
there's no "finished successfully" exit to wait for -- still running
when the timeout hits counts as a pass here, same as a clean voluntary
exit. Only an early non-zero return code (an uncaught exception) fails
the test. This only catches bugs that surface within TIMEOUT seconds of
start (import errors, bad API usage, missing assets, ...) -- not one
that would only appear deep into a long-running loop.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*.py"))
TIMEOUT = 6  # seconds given to clear setup and the first few steps


def _needs_rtb(path: Path) -> bool:
    text = path.read_text()
    return "import roboticstoolbox" in text or "from roboticstoolbox" in text


def _example_param(path: Path) -> pytest.param:
    marks = [pytest.mark.rtb] if _needs_rtb(path) else []
    return pytest.param(path, id=path.name, marks=marks)


@pytest.mark.parametrize("example", [_example_param(f) for f in EXAMPLE_FILES])
def test_example_runs_without_crashing(example: Path):
    run_env = os.environ.copy()
    run_env["SWIFT_HEADLESS"] = "1"

    try:
        result = subprocess.run(
            [sys.executable, str(example)],
            cwd=example.parent,
            env=run_env,
            timeout=TIMEOUT,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        # Still running at the timeout -- expected for examples ending in
        # hold()/run()/while True, which never exit on their own headless.
        return

    assert result.returncode == 0, (
        f"{example.name} exited with code {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
