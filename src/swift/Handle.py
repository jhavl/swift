#!/usr/bin/env python
"""
Instance handles for objects added to a Swift scene.
"""
import warnings
from typing import Callable, Protocol, runtime_checkable

import numpy as np
from spatialmath import SE3


@runtime_checkable
class SwiftPart(Protocol):
    """Minimal contract for anything Swift can render each step."""

    def part_poses(self) -> list[SE3]: ...


class AssemblyHandle:
    """
    Per-instance simulation state for an assembly of parts added to a
    Swift scene -- an ``rtb.Robot`` (via ``Swift.add_robot``) or any bare
    ``fk(q) -> list[SE3]`` callable plus a parts list (via
    ``Swift.add_assembly``).

    Whatever model produced it stays a plain, shareable, pure-FK thing --
    this handle owns the live, per-simulation joint state (``q``, ``qd``,
    ``control_mode``) that ``Swift.step()`` reads and mutates each frame,
    so several handles can drive independent instances of the same model.

    .. deprecated:: 2.0

        For an ``rtb.Robot`` handle, driving it by mutating
        ``robot.q``/``robot.qd`` directly (without ever touching the
        handle) still works, but is deprecated -- set
        ``handle.q``/``handle.qd`` instead.
    """

    def __init__(
        self,
        pose_fn: Callable[[np.ndarray], list[SE3]],
        q0,
        robot=None,
        readonly: bool = False,
        name: str | None = None,
        callback=None,
    ):
        self._pose_fn = pose_fn
        self.q = np.array(q0, dtype=float)
        self.qd = np.zeros_like(self.q)
        # Robots default to velocity control (matches Robot.control_mode's
        # own default); a bare assembly has no qd-integration support
        # (no qlim/n to integrate against) so defaults to position control
        # -- driven via handle.q directly, or a callback.
        self._control_mode = robot.control_mode if robot is not None else "p"
        self.robot = robot
        self.readonly = readonly
        self.name = name
        self.callback = callback
        self.id: int | None = None
        self._warned = False

        if robot is not None:
            # Snapshot of the model's own state as of the last sync, used
            # to detect the deprecated direct-mutation style -- *not*
            # compared against self.q/self.qd, which are expected to
            # diverge from the model as soon as the handle is used the
            # new way.
            self._model_q = np.array(robot.q, dtype=float)
            self._model_qd = np.array(robot.qd, dtype=float)
            self._model_control_mode = robot.control_mode

    @property
    def control_mode(self) -> str:
        return self._control_mode

    @control_mode.setter
    def control_mode(self, cn: str):
        if cn not in ("p", "v", "a"):
            raise ValueError("control_mode must be one of 'p', 'v', or 'a'")
        self._control_mode = cn

    def part_poses(self) -> list[SE3]:
        """World pose of every rendered part, from this handle's ``q``."""
        return self._pose_fn(self.q)

    def _sync_legacy(self):
        """
        Backward-compat bridge for the deprecated robot.q/robot.qd
        direct-mutation style. Only applies to a handle wrapping an actual
        ``rtb.Robot`` (``Swift.add_robot``) -- a bare assembly has no
        model to diverge from.
        """
        if self.robot is None:
            return

        if (
            np.array_equal(self.robot._q, self._model_q)
            and np.array_equal(self.robot._qd, self._model_qd)
            and self.robot._control_mode == self._model_control_mode
        ):
            return

        if not self._warned:
            warnings.warn(
                "Driving a Swift robot by mutating robot.q/robot.qd "
                "directly is deprecated. Use the handle returned by "
                "env.add_robot(robot) instead: `handle = "
                "env.add_robot(robot); handle.q = ...`.",
                DeprecationWarning,
                stacklevel=3,
            )
            self._warned = True

        self.q = np.array(self.robot._q, dtype=float)
        self.qd = np.array(self.robot._qd, dtype=float)
        self._control_mode = self.robot._control_mode
        self._model_q = self.q.copy()
        self._model_qd = self.qd.copy()
        self._model_control_mode = self._control_mode

    def _push_legacy(self):
        """
        Mirror image of :meth:`_sync_legacy`. Once a handle has been
        confirmed to be in the deprecated direct-mutation style
        (``self._warned``), Swift's own internal updates to
        ``handle.q``/``handle.qd`` -- e.g. velocity-mode integration in
        ``Swift._step_assembly`` -- need to reach back into
        ``robot.q``/``robot.qd`` too, or a control loop that reads
        ``robot.q`` back after ``env.step()`` (the common pattern, e.g.
        RTB's own README p_servo example) sees a permanently stale value
        and never converges.

        Only ever touches the robot once ``_warned`` is set, so a handle
        never driven the legacy way -- the intended case, and the one
        where several handles may share one plain, stateless robot model
        -- never has its q/qd silently overwritten by this.
        """
        if self.robot is None or not self._warned:
            return

        self.robot._q = self.q.copy()
        self.robot._qd = self.qd.copy()
        self._model_q = self.q.copy()
        self._model_qd = self.qd.copy()
        self._model_control_mode = self._control_mode
