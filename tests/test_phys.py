"""
Tests for the physics step functions.

The Python fallbacks (_step_v_py, _step_shape_py) are always tested.
When the compiled C extension is available, each test is also run against
it and the results are compared to the Python output.
"""

import numpy as np
import pytest
from numpy.testing import assert_allclose
import spatialmath.base as smb

from swift.Swift import _step_v_py, _step_shape_py

try:
    from swift.phys import step_v as _step_v_c, step_shape as _step_shape_c

    HAS_EXT = True
except ImportError:
    HAS_EXT = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identity_base():
    """Return a 4x4 identity SE(3) in Fortran (column-major) order.

    spatialgeometry stores _SceneNode__T in F-order, and the C extension uses
    column-major Eigen maps, so tests must use the same layout.
    """
    return np.asfortranarray(np.eye(4, dtype=np.float64))


def _zero_v():
    return np.zeros(6, dtype=np.float64)


def _zero_wT():
    return np.eye(4, dtype=np.float64)


def _zero_wq():
    return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)


def _pose_from_base(base):
    """Return renderer-facing pose: translation and quaternion [x, y, z, w]."""
    t = base[:3, 3].copy()
    q = smb.r2q(base[:3, :3], order="xyzs")
    return t, q


def _assert_same_rotation(q_actual, q_expected, atol=1e-10):
    """Quaternions q and -q represent the same rotation."""
    dot = float(np.dot(q_actual, q_expected))
    assert abs(dot) == pytest.approx(1.0, abs=atol)


# ---------------------------------------------------------------------------
# step_v tests
# ---------------------------------------------------------------------------


class TestStepV:
    def _call_py(self, n, valid, dt, q, qd, qlim):
        _step_v_py(n, valid, dt, q, qd, qlim)

    def _call_c(self, n, valid, dt, q, qd, qlim):
        _step_v_c(n, valid, dt, q, qd, qlim)

    def _make_inputs(self, n=3):
        q = np.array([0.0, 0.5, -0.5], dtype=np.float64)[:n]
        qd = np.array([1.0, -2.0, 0.5], dtype=np.float64)[:n]
        # qlim shape (2, n): row 0 = lower, row 1 = upper
        qlim = np.array([[-1.0] * n, [1.0] * n], dtype=np.float64)
        return q, qd, qlim

    def test_basic_integration(self):
        q, qd, qlim = self._make_inputs()
        dt = 0.1
        expected = q + qd * dt
        self._call_py(3, 0, dt, q, qd, qlim)
        assert_allclose(q, expected)

    def test_clamp_upper(self):
        q = np.array([0.9], dtype=np.float64)
        qd = np.array([5.0], dtype=np.float64)
        qlim = np.array([[-1.0], [1.0]], dtype=np.float64)
        self._call_py(1, 1, 0.1, q, qd, qlim)
        assert q[0] == pytest.approx(1.0)

    def test_clamp_lower(self):
        q = np.array([-0.9], dtype=np.float64)
        qd = np.array([-5.0], dtype=np.float64)
        qlim = np.array([[-1.0], [1.0]], dtype=np.float64)
        self._call_py(1, 1, 0.1, q, qd, qlim)
        assert q[0] == pytest.approx(-1.0)

    def test_no_clamp_when_valid_false(self):
        q = np.array([0.9], dtype=np.float64)
        qd = np.array([5.0], dtype=np.float64)
        qlim = np.array([[-1.0], [1.0]], dtype=np.float64)
        self._call_py(1, 0, 0.1, q, qd, qlim)
        assert q[0] == pytest.approx(1.4)

    def test_zero_dt(self):
        q, qd, qlim = self._make_inputs()
        original = q.copy()
        self._call_py(3, 1, 0.0, q, qd, qlim)
        assert_allclose(q, original)

    def test_modifies_in_place(self):
        q, qd, qlim = self._make_inputs()
        q_ref = q  # same object
        self._call_py(3, 0, 0.1, q, qd, qlim)
        assert q_ref is q

    @pytest.mark.skipif(not HAS_EXT, reason="C extension not available")
    def test_matches_c_extension(self):
        q_py, qd, qlim = self._make_inputs()
        q_c = q_py.copy()
        dt = 0.05
        self._call_py(3, 1, dt, q_py, qd, qlim)
        self._call_c(3, 1, dt, q_c, qd.copy(), qlim)
        assert_allclose(q_py, q_c, rtol=1e-12)


# ---------------------------------------------------------------------------
# step_shape tests
# ---------------------------------------------------------------------------


class TestStepShape:
    def _call_py(self, dt, v, base):
        _step_shape_py(dt, v, base, _zero_wT(), _zero_wq())

    def _call_c(self, dt, v, base):
        _step_shape_c(dt, v, base, _zero_wT(), _zero_wq())

    def test_zero_velocity_no_change(self):
        base = _identity_base()
        original = base.copy()
        self._call_py(0.1, _zero_v(), base)
        assert_allclose(base, original, atol=1e-12)

    def test_pure_translation(self):
        base = _identity_base()
        v = np.array([1.0, 2.0, 3.0, 0.0, 0.0, 0.0], dtype=np.float64)
        dt = 0.5
        self._call_py(dt, v, base)
        assert_allclose(base[:3, 3], [0.5, 1.0, 1.5], atol=1e-12)
        # Rotation should be unchanged
        assert_allclose(base[:3, :3], np.eye(3), atol=1e-12)

    def test_pure_rotation_z_quarter_turn(self):
        """90-degree rotation about Z should swap X/Y columns."""
        base = _identity_base()
        # omega_z = pi/2, dt = 1 → theta = pi/2
        v = np.array([0.0, 0.0, 0.0, 0.0, 0.0, np.pi / 2], dtype=np.float64)
        self._call_py(1.0, v, base)
        expected_R = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=np.float64)
        assert_allclose(base[:3, :3], expected_R, atol=1e-12)

    def test_pure_rotation_x_half_turn(self):
        """180-degree rotation about X."""
        base = _identity_base()
        v = np.array([0.0, 0.0, 0.0, np.pi, 0.0, 0.0], dtype=np.float64)
        self._call_py(1.0, v, base)
        expected_R = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float64)
        assert_allclose(base[:3, :3], expected_R, atol=1e-12)

    def test_rotation_matrix_stays_orthonormal(self):
        """After integration the rotation block must remain SO(3)."""
        base = _identity_base()
        v = np.array([0.1, -0.2, 0.3, 0.4, -0.5, 0.6], dtype=np.float64)
        for _ in range(50):
            self._call_py(0.05, v, base)
        R = base[:3, :3]
        assert_allclose(R @ R.T, np.eye(3), atol=1e-10)
        assert_allclose(np.linalg.det(R), 1.0, atol=1e-10)

    def test_combined_translation_and_rotation(self):
        base = _identity_base()
        v = np.array([1.0, 0.0, 0.0, 0.0, 0.0, np.pi / 2], dtype=np.float64)
        self._call_py(1.0, v, base)
        assert_allclose(base[:3, 3], [1.0, 0.0, 0.0], atol=1e-12)
        expected_R = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=np.float64)
        assert_allclose(base[:3, :3], expected_R, atol=1e-12)

    def test_modifies_base_in_place(self):
        base = _identity_base()
        base_ref = base
        v = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
        self._call_py(0.1, v, base)
        assert base_ref is base

    def test_homogeneous_row_unchanged(self):
        """Bottom row of base must always remain [0, 0, 0, 1]."""
        base = _identity_base()
        v = np.array([0.3, -0.1, 0.5, 0.2, 0.4, -0.3], dtype=np.float64)
        for _ in range(20):
            self._call_py(0.1, v, base)
        assert_allclose(base[3], [0.0, 0.0, 0.0, 1.0], atol=1e-14)

    @pytest.mark.skipif(not HAS_EXT, reason="C extension not available")
    def test_matches_c_extension_translation(self):
        v = np.array([0.5, -0.3, 0.1, 0.0, 0.0, 0.0], dtype=np.float64)
        base_py = _identity_base()
        base_c = _identity_base()
        self._call_py(0.1, v, base_py)
        self._call_c(0.1, v.copy(), base_c)
        t_py, q_py = _pose_from_base(base_py)
        t_c, q_c = _pose_from_base(base_c)
        assert_allclose(t_py, t_c, atol=1e-12)
        _assert_same_rotation(q_py, q_c)

    @pytest.mark.skipif(not HAS_EXT, reason="C extension not available")
    def test_matches_c_extension_rotation(self):
        v = np.array([0.0, 0.0, 0.0, 0.1, 0.2, 0.3], dtype=np.float64)
        base_py = _identity_base()
        base_c = _identity_base()
        self._call_py(0.1, v, base_py)
        self._call_c(0.1, v.copy(), base_c)
        t_py, q_py = _pose_from_base(base_py)
        t_c, q_c = _pose_from_base(base_c)
        assert_allclose(t_py, t_c, atol=1e-12)
        _assert_same_rotation(q_py, q_c)

    @pytest.mark.skipif(not HAS_EXT, reason="C extension not available")
    def test_matches_c_extension_combined_many_steps(self):
        """Run 100 steps and verify accumulated error is negligible."""
        v = np.array([0.05, -0.03, 0.01, 0.1, -0.2, 0.15], dtype=np.float64)
        base_py = _identity_base()
        base_c = _identity_base()
        for _ in range(100):
            self._call_py(0.02, v, base_py)
            self._call_c(0.02, v.copy(), base_c)
        t_py, q_py = _pose_from_base(base_py)
        t_c, q_c = _pose_from_base(base_c)
        assert_allclose(t_py, t_c, atol=1e-10)
        _assert_same_rotation(q_py, q_c, atol=1e-8)
