"""
A stand-in for roboticstoolbox's ``Robot``, so swift's tests need no RTB.

**Why this exists.** The dependency between the two projects is strictly one
way: RTB depends on swift (its ``Swift`` backend), never the reverse. Swift's
own source and tests therefore must not import roboticstoolbox. But
``Swift.add_robot()`` and :class:`~swift.Handle.AssemblyHandle` are written
against RTB's ``Robot`` *interface* -- ``fkine_geometry()``, ``_to_dict()``,
``q``/``qd``/``qlim``/``control_mode``, ``links`` and a few private
attributes. These tests used ``rtb.models.Panda()`` purely as a convenient
object providing that interface; ``FakeRobot`` provides the same interface
without the dependency, so swift's own robot-handling logic (handle state,
the deprecated ``robot.q``/``robot.qd`` bridge, ``show()``/``repr()``, the
socket message shapes) stays tested.

**What this does NOT test -- read before relying on it:**

* It is a *hand-written copy* of the interface swift uses, so it can drift:
  if RTB renames or changes semantics of one of these members, these tests
  keep passing while the real integration breaks. Nothing in swift's CI can
  catch that, by design.
* The real ``Robot``/swift pairing is covered on the other side of the
  dependency: RTB's own CI installs swift (``swift-sim`` is in its ``swift``
  and ``dev`` extras) and runs its Swift-backend tests against the real
  thing (tests/test_BaseRobot.py, test_backend_capabilities.py,
  test_demo.py in robotics-toolbox-python). A break in the interface swift
  relies on should surface there, in the project that owns it.
* The kinematics are a made-up planar chain -- enough for poses to change
  with ``q``, with no claim to match any real robot's geometry.

Keep this minimal: add a member only when swift's source starts using it,
and see ``Swift.add_robot``'s docstring for the list swift relies on.
"""

from types import SimpleNamespace

import numpy as np
from numpy.typing import NDArray
from spatialmath import SE3


class FakeRobot:
    """
    A small serial-chain stand-in providing the ``Robot`` interface swift uses.

    :param n: number of joints (and links)
    :param name: robot name, shown by ``Swift.show()``
    """

    def __init__(self, n: int = 3, name: str = "fake") -> None:
        self.name = name
        self._n = n

        # Named links with one geometry item each, plus two one-link
        # "grippers" -- the same shape of structure the real Panda has, so
        # tests can count parts the way they did with it.
        self.links = [
            SimpleNamespace(name=f"link{i}", geometry=[object()], collision=[])
            for i in range(n)
        ]
        self.grippers = [
            SimpleNamespace(
                links=[
                    SimpleNamespace(
                        name=f"finger{i}", geometry=[object()], collision=[]
                    )
                ]
            )
            for i in range(2)
        ]

        self.qz: NDArray = np.zeros(n)
        self.qr: NDArray = np.linspace(0.2, 0.6, n)

        self._q: NDArray = np.zeros(n)
        self._qd: NDArray = np.zeros(n)
        self._control_mode = "v"  # RTB's default, which Handle mirrors
        self._valid_qlim = True
        self._qlim: NDArray = np.vstack([np.full(n, -10.0), np.full(n, 10.0)])

    @property
    def n(self) -> int:
        return self._n

    @property
    def q(self) -> NDArray:
        return self._q

    @q.setter
    def q(self, q: NDArray) -> None:
        self._q = np.array(q, dtype=float)

    @property
    def qd(self) -> NDArray:
        return self._qd

    @qd.setter
    def qd(self, qd: NDArray) -> None:
        self._qd = np.array(qd, dtype=float)

    @property
    def control_mode(self) -> str:
        return self._control_mode

    @property
    def qlim(self) -> NDArray:
        return self._qlim

    @property
    def n_parts(self) -> int:
        """Total rendered parts: every link's geometry, then the grippers'."""
        parts = sum(len(link.geometry) for link in self.links)
        for gripper in self.grippers:
            parts += sum(len(link.geometry) for link in gripper.links)
        return parts

    def _update_link_tf(self) -> None:
        pass

    def update(self) -> None:
        pass

    def _to_dict(self, robot_alpha: float = 1.0, collision_alpha: float = 0.0) -> list:
        # Contents are opaque to swift's Python side (it only sends the list
        # to the browser and waits for that many parts to mount).
        return [{"stype": "fake", "alpha": robot_alpha} for _ in range(self.n_parts)]

    def fkine_geometry(
        self, q: NDArray, robot_alpha: float = 1.0, collision_alpha: float = 0.0
    ) -> list[SE3]:
        """One pose per rendered part; each link's pose depends on all earlier joints."""
        T = SE3()
        poses = []
        for qi in np.asarray(q, dtype=float):
            T = T * SE3.Rz(qi) * SE3.Tx(0.3)
            poses.append(T)
        # Gripper parts ride on the last link.
        poses.extend(poses[-1] for _ in range(self.n_parts - len(poses)))
        return poses
