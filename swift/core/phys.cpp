/**
 * \file phys.c
 * \author Jesse Haviland
 *
 *
 */

#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION

#include <Python.h>
#include <numpy/arrayobject.h>
#include <math.h>
#include "phys.h"
#include "linalg.h"
#include <iostream>

static PyMethodDef physMethods[] = {
    {"step_v",
     (PyCFunction)step_v,
     METH_VARARGS,
     "Link"},
    {"step_shape",
     (PyCFunction)step_shape,
     METH_VARARGS,
     "Link"},
    {NULL, NULL, 0, NULL} /* Sentinel */
};

static struct PyModuleDef physmodule =
    {
        PyModuleDef_HEAD_INIT,
        "phys",
        "Fast Simulation",
        -1,
        physMethods};

PyMODINIT_FUNC PyInit_phys(void)
{
    import_array();
    return PyModule_Create(&physmodule);
}

extern "C"
{

    static PyObject *step_v(PyObject *self, PyObject *args)
    {
        int valid, n;
        double dt;
        PyArrayObject *py_q, *py_qd, *py_qlim;
        npy_float64 *q, *qd, *qlim;

        if (!PyArg_ParseTuple(
                args, "iidO!O!O!",
                &n,
                &valid,
                &dt,
                &PyArray_Type, &py_q,
                &PyArray_Type, &py_qd,
                &PyArray_Type, &py_qlim))
            return NULL;

        q = (npy_float64 *)PyArray_DATA(py_q);
        qd = (npy_float64 *)PyArray_DATA(py_qd);
        qlim = (npy_float64 *)PyArray_DATA(py_qlim);

        for (int i = 0; i < n; i++)
        {
            q[i] += qd[i] * dt;

            if (valid)
            {
                if (q[i] > qlim[1 * n + i])
                {
                    q[i] = qlim[1 * n + i];
                }
                else if (q[i] < qlim[0 * n + i])
                {
                    q[i] = qlim[0 * n + i];
                }
            }
        }

        Py_RETURN_NONE;
    }

    static PyObject *step_shape(PyObject *self, PyObject *args)
    {
        const double eps = 2.220446049250313e-16;
        double dt;
        PyArrayObject *py_v, *py_base, *py_sT, *py_sq;
        npy_float64 *v_np, *base_np, *sT_np, *sq_np, *R_np, *sk_np, *temp_np, *temp2_np, *dv_np;
        npy_float64 *n_np, *o_np, *a_np;
        double theta, n_norm, o_norm, a_norm;

        if (!PyArg_ParseTuple(
                args, "dO!O!O!O!",
                &dt,
                &PyArray_Type, &py_v,
                &PyArray_Type, &py_base,
                &PyArray_Type, &py_sT,
                &PyArray_Type, &py_sq))
            return NULL;

        base_np = (npy_float64 *)PyArray_DATA(py_base);
        sT_np = (npy_float64 *)PyArray_DATA(py_sT);

        R_np = (npy_float64 *)PyMem_RawCalloc(9, sizeof(npy_float64));
        sk_np = (npy_float64 *)PyMem_RawCalloc(9, sizeof(npy_float64));
        temp_np = (npy_float64 *)PyMem_RawCalloc(9, sizeof(npy_float64));
        temp2_np = (npy_float64 *)PyMem_RawCalloc(9, sizeof(npy_float64));

        v_np = (npy_float64 *)PyArray_DATA(py_v);
        dv_np = (npy_float64 *)PyMem_RawCalloc(6, sizeof(npy_float64));

        n_np = (npy_float64 *)PyMem_RawCalloc(3, sizeof(npy_float64));
        o_np = (npy_float64 *)PyMem_RawCalloc(3, sizeof(npy_float64));
        a_np = (npy_float64 *)PyMem_RawCalloc(3, sizeof(npy_float64));

        sq_np = (npy_float64 *)PyArray_DATA(py_sq);

        MapMatrix4dc base(base_np);
        MapMatrix4dc sT(sT_np);

        MapMatrix3dc R(R_np);
        MapMatrix3dc sk(sk_np);
        MapMatrix3dc temp(temp_np);
        MapMatrix3dc temp2(temp2_np);

        MapVector6 v(v_np);
        MapVector6 dv(dv_np);

        MapVector3 n(n_np);
        MapVector3 o(o_np);
        MapVector3 a(a_np);

        MapVector4 sq(sq_np);

        // R = Eigen::Matrix3d::Identity();
        _eye3(R_np);

        // Find the stepped velocity
        dv(0) = v(0) * dt;
        dv(1) = v(1) * dt;
        dv(2) = v(2) * dt;
        dv(3) = v(3) * dt;
        dv(4) = v(4) * dt;
        dv(5) = v(5) * dt;

        // theta = _norm(dv_np + 3);
        theta = dv.tail(3).norm();
        // std::cout << "theta: " << theta << std::endl;

        // Convert rotational vel to unit vector
        dv(3) = dv(3) / theta;
        dv(4) = dv(4) / theta;
        dv(5) = dv(5) / theta;

        // std::cout << "dv: " << dv << std::endl;

        if (theta > (10 * eps))
        {
            // std::cout << "HALLPPLPL " << std::endl;
            skew(dv.tail(3), sk);

            // std::cout << "sk: \n"
            //   << sk << std::endl;

            // temp = sin(theta) * sk
            // _dot9(sin(theta), sk_np, temp_np);
            temp = sk * sin(theta);

            // R = R + temp
            // _add9_inplace(temp_np, R_np);
            R = R + temp;

            // temp = (1.0 - np.cos(theta)) * sk
            // _dot9(1.0 - cos(theta), sk_np, temp_np);
            temp = sk * (1.0 - cos(theta));

            // temp2 = temp @ sk
            // _mult3(temp, sk, temp2);
            temp2 = temp * sk;

            // R = R + temp2
            // _add9_inplace(temp2_np, R_np);
            R = R + temp2;

            // std::cout << "R: \n"
            //   << R << std::endl;
        }

        // copy base.R into temp
        // temp = base.block<3, 3>(0, 0);
        temp(0, 0) = base(0, 0);
        temp(0, 1) = base(0, 1);
        temp(0, 2) = base(0, 2);
        temp(1, 0) = base(1, 0);
        temp(1, 1) = base(1, 1);
        temp(1, 2) = base(1, 2);
        temp(2, 0) = base(2, 0);
        temp(2, 1) = base(2, 1);
        temp(2, 2) = base(2, 2);

        // temp2 = R @ temp
        temp2 = R * temp;
        // std::cout << thetatemp2 << std::endl;
        // _mult3(R, temp, temp2);

        // copy temp2 into base.R
        // base.block<3, 3>(0, 0) = temp2;
        base(0, 0) = temp2(0, 0);
        base(0, 1) = temp2(0, 1);
        base(0, 2) = temp2(0, 2);
        base(1, 0) = temp2(1, 0);
        base(1, 1) = temp2(1, 1);
        base(1, 2) = temp2(1, 2);
        base(2, 0) = temp2(2, 0);
        base(2, 1) = temp2(2, 1);
        base(2, 2) = temp2(2, 2);

        // std::cout << "base: " << base << std::endl;

        // normalise rotation
        o(0) = base(0, 1);
        o(1) = base(1, 1);
        o(2) = base(2, 1);

        a(0) = base(0, 2);
        a(1) = base(1, 2);
        a(2) = base(2, 2);

        // _cross(o, a, n);
        n = o.cross(a);
        // std::cout << "n: " << n << std::endl;

        // _cross(a, n, o);
        o = a.cross(n);
        // std::cout << "o: " << o << std::endl;

        // n_norm = _norm(n_np);
        // o_norm = _norm(o_np);
        // a_norm = _norm(a_np);

        n_norm = n.norm();
        o_norm = o.norm();
        a_norm = a.norm();

        base(0, 0) = n(0) / n_norm;
        base(0, 1) = o(0) / o_norm;
        base(0, 2) = a(0) / a_norm;
        base(1, 0) = n(1) / n_norm;
        base(1, 1) = o(1) / o_norm;
        base(1, 2) = a(1) / a_norm;
        base(2, 0) = n(2) / n_norm;
        base(2, 1) = o(2) / o_norm;
        base(2, 2) = a(2) / a_norm;

        // std::cout << "base: \n"
        //   << base << std::endl;

        // Step translation
        base(0, 3) += dv(0);
        base(1, 3) += dv(1);
        base(2, 3) += dv(2);

        // base[3] = 0.0;
        // base[7] = 0.0;
        // base[11] = 0.0;

        // // Set other attributes
        // _copy4(base, sT);
        // sT = base;
        // _r2q(base, sq);

        free(R_np);
        free(sk_np);
        free(temp_np);
        free(temp2_np);
        free(dv_np);
        free(n_np);
        free(o_np);
        free(a_np);

        Py_RETURN_NONE;
    }

    double _norm(npy_float64 *v)
    {
        double n = v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
        return sqrt(n);
    }

    void _cross(npy_float64 *a, npy_float64 *b, npy_float64 *c)
    {
        c[0] = a[1] * b[2] - a[2] * b[1];
        c[1] = a[2] * b[0] - a[0] * b[2];
        c[2] = a[0] * b[1] - a[1] * b[0];
    }

    void _eye3(npy_float64 *data)
    {
        data[0] = 1;
        data[1] = 0;
        data[2] = 0;
        data[3] = 0;
        data[4] = 1;
        data[5] = 0;
        data[6] = 0;
        data[7] = 0;
        data[8] = 1;
    }

    // Multiply constant by 9 vector and store in different 9 vector
    void _dot9(double mult, npy_float64 *arr, npy_float64 *ret)
    {
        ret[0] = arr[0] * mult;
        ret[1] = arr[1] * mult;
        ret[2] = arr[2] * mult;
        ret[3] = arr[3] * mult;
        ret[4] = arr[4] * mult;
        ret[5] = arr[5] * mult;
        ret[6] = arr[6] * mult;
        ret[7] = arr[7] * mult;
        ret[8] = arr[8] * mult;
    }

    // Add 9 vector to 9 vector
    void _add9_inplace(npy_float64 *add, npy_float64 *ret)
    {
        ret[0] += add[0];
        ret[1] += add[1];
        ret[2] += add[2];
        ret[3] += add[3];
        ret[4] += add[4];
        ret[5] += add[5];
        ret[6] += add[6];
        ret[7] += add[7];
        ret[8] += add[8];
    }

    void _skew(npy_float64 *v, npy_float64 *sk)
    {
        sk[0] = 0;
        sk[1] = -v[2];
        sk[2] = v[1];

        sk[3] = v[2];
        sk[4] = 0;
        sk[5] = -v[0];

        sk[6] = -v[1];
        sk[7] = v[0];
        sk[8] = 0;
    }

    void skew(Vector3 v, MapMatrix3dc sk)
    {
        sk(0, 0) = 0;
        sk(0, 1) = -v(2);
        sk(0, 2) = v(1);

        sk(1, 0) = v(2);
        sk(1, 1) = 0;
        sk(1, 2) = -v(0);

        sk(2, 0) = -v(1);
        sk(2, 1) = v(0);
        sk(2, 2) = 0;
    }

    void _mult3(npy_float64 *A, npy_float64 *B, npy_float64 *C)
    {
        const int N = 3;
        int i, j, k;
        double num;

        for (i = 0; i < N; i++)
        {
            for (j = 0; j < N; j++)
            {
                num = 0;
                for (k = 0; k < N; k++)
                {
                    num += A[i * N + k] * B[k * N + j];
                }
                C[i * N + j] = num;
            }
        }
    }

    void _r2q(npy_float64 *r, npy_float64 *q)
    {
        double t12p, t13p, t23p;
        double t12m, t13m, t23m;
        double d1, d2, d3, d4;

        t12p = pow((r[0 * 4 + 1] + r[1 * 4 + 0]), 2);
        t13p = pow((r[0 * 4 + 2] + r[2 * 4 + 0]), 2);
        t23p = pow((r[1 * 4 + 2] + r[2 * 4 + 1]), 2);

        t12m = pow((r[0 * 4 + 1] - r[1 * 4 + 0]), 2);
        t13m = pow((r[0 * 4 + 2] - r[2 * 4 + 0]), 2);
        t23m = pow((r[1 * 4 + 2] - r[2 * 4 + 1]), 2);

        d1 = pow((r[0 * 4 + 0] + r[1 * 4 + 1] + r[2 * 4 + 2] + 1), 2);
        d2 = pow((r[0 * 4 + 0] - r[1 * 4 + 1] - r[2 * 4 + 2] + 1), 2);
        d3 = pow((-r[0 * 4 + 0] + r[1 * 4 + 1] - r[2 * 4 + 2] + 1), 2);
        d4 = pow((-r[0 * 4 + 0] - r[1 * 4 + 1] + r[2 * 4 + 2] + 1), 2);

        q[3] = sqrt(d1 + t23m + t13m + t12m) / 4.0;
        q[0] = sqrt(t23m + d2 + t12p + t13p) / 4.0;
        q[1] = sqrt(t13m + t12p + d3 + t23p) / 4.0;
        q[2] = sqrt(t12m + t13p + t23p + d4) / 4.0;

        // transfer sign from rotation element differences
        if (r[2 * 4 + 1] < r[1 * 4 + 2])
            q[0] = -q[0];
        if (r[0 * 4 + 2] < r[2 * 4 + 0])
            q[1] = -q[1];
        if (r[1 * 4 + 0] < r[0 * 4 + 1])
            q[2] = -q[2];
    }

    void _copy4(npy_float64 *A, npy_float64 *B)
    {
        // copy A into B
        B[0] = A[0];
        B[1] = A[1];
        B[2] = A[2];
        B[3] = A[3];
        B[4] = A[4];
        B[5] = A[5];
        B[6] = A[6];
        B[7] = A[7];
        B[8] = A[8];
        B[9] = A[9];
        B[10] = A[10];
        B[11] = A[11];
        B[12] = A[12];
        B[13] = A[13];
        B[14] = A[14];
        B[15] = A[15];
    }
} /* extern "C" */