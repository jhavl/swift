"""
Enforces that swift's tests never touch roboticstoolbox (RTB), and holds the
fixtures shared by the integration tests.

The dependency between the projects is strictly one way -- RTB depends on
swift, never the reverse -- so nothing in swift's source or tests may import
RTB. Putting ``None`` in ``sys.modules`` makes any ``import roboticstoolbox``
raise ``ImportError`` for the whole test session, *even on a machine that has
RTB installed* (a developer's environment usually does, since RTB is the main
consumer). Without this, an accidental RTB import would pass locally and only
fail in CI, or worse never fail at all.

Limits: this guarantees swift can be exercised without RTB, not that it
works *with* it. The real Robot/swift pairing is tested by RTB's own CI --
see tests/fake_robot.py for the stand-in used here and why.
"""

import os
import shutil
import sys
import threading
from pathlib import Path
from queue import Queue

import pytest

sys.modules["roboticstoolbox"] = None  # type: ignore[assignment]

PUBLIC = Path(__file__).resolve().parents[1] / "src" / "swift" / "public"


@pytest.fixture
def require_node():
    """
    For tests that drive the real JS frontend code with Node. Skips locally
    where Node or the npm dependencies are missing, but fails under CI (``CI``
    is set by GitHub Actions) so a broken workflow can't become a silent pass.
    """
    if shutil.which("node") is None:
        problem = "node is not on PATH"
    elif not (PUBLIC / "node_modules" / "three").is_dir():
        problem = "`npm ci` has not been run in src/swift/public"
    else:
        return
    if os.environ.get("CI"):
        pytest.fail(problem)
    pytest.skip(problem)


@pytest.fixture
def server_port():
    """The port of a real ``SwiftServer`` serving the installed ``public/``."""
    from swift.SwiftRoute import SwiftServer

    outq, inq = Queue(), Queue()
    t = threading.Thread(
        target=SwiftServer, args=(outq, inq, 0, lambda: True), daemon=True
    )
    t.start()
    port, instance = inq.get(timeout=5)
    yield port
    instance.stop()
    t.join(timeout=3)
