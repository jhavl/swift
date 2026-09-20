"""
Enforces that swift's tests never touch roboticstoolbox (RTB).

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

import sys

sys.modules["roboticstoolbox"] = None  # type: ignore[assignment]
