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

// forward defines
double _norm(npy_float64 *v);
void _eye3(npy_float64 *data);
void _skew(npy_float64 *v, npy_float64 *sk);
void _dot9(double mult, npy_float64 *arr, npy_float64 *ret);
void _add9_inplace(npy_float64 *add, npy_float64 *ret);
void _mult3(npy_float64 *A, npy_float64 *B, npy_float64 *C);
void _cross(npy_float64 *a,npy_float64 *b, npy_float64 *c);
void _r2q(npy_float64 *r, npy_float64 *q);
void _copy4(npy_float64 *A, npy_float64 *B);

static PyObject *step_v(PyObject *self, PyObject *args);
static PyObject *step_shape(PyObject *self, PyObject *args);

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
    npy_float64 *v, *base, *sT, *sq, *R, *sk, *temp, *temp2, *dv;
    npy_float64 *n, *o, *a;
    double theta, n_norm, o_norm, a_norm;

    if (!PyArg_ParseTuple(
            args, "dO!O!O!O!",
            &dt,
            &PyArray_Type, &py_v,
            &PyArray_Type, &py_base,
            &PyArray_Type, &py_sT,
            &PyArray_Type, &py_sq))
        return NULL;

    v = (npy_float64 *)PyArray_DATA(py_v);
    base = (npy_float64 *)PyArray_DATA(py_base);
    sT = (npy_float64 *)PyArray_DATA(py_sT);
    sq = (npy_float64 *)PyArray_DATA(py_sq);
    R = (npy_float64 *)PyMem_RawCalloc(9, sizeof(npy_float64));
    sk = (npy_float64 *)PyMem_RawCalloc(9, sizeof(npy_float64));
    temp = (npy_float64 *)PyMem_RawCalloc(9, sizeof(npy_float64));
    temp2 = (npy_float64 *)PyMem_RawCalloc(9, sizeof(npy_float64));
    dv = (npy_float64 *)PyMem_RawCalloc(6, sizeof(npy_float64));
    n = (npy_float64 *)PyMem_RawCalloc(3, sizeof(npy_float64));
    o = (npy_float64 *)PyMem_RawCalloc(3, sizeof(npy_float64));
    a = (npy_float64 *)PyMem_RawCalloc(3, sizeof(npy_float64));

    _eye3(R);

    // Find the stepped velocity
    dv[0] = v[0] * dt;
    dv[1] = v[1] * dt;
    dv[2] = v[2] * dt;
    dv[3] = v[3] * dt;
    dv[4] = v[4] * dt;
    dv[5] = v[5] * dt;

    theta = _norm(dv + 3);

    // Convert rotational vel to unit vector
    dv[3] /= theta;
    dv[4] /= theta;
    dv[5] /= theta;

    if (theta > (10 * eps))
    {
        _skew(dv + 3, sk);

        // temp = sin(theta) * sk
        _dot9(sin(theta), sk, temp);

        // R = R + temp
        _add9_inplace(temp, R);

        // temp = (1.0 - np.cos(theta)) * sk
        _dot9(1.0 - cos(theta), sk, temp);

        // temp2 = temp @ sk
        _mult3(temp, sk, temp2);

        // R = R + temp2
        _add9_inplace(temp2, R);
    }

    // copy base.R into temp
    temp[0] = base[0];
    temp[1] = base[1];
    temp[2] = base[2];
    temp[3] = base[4];
    temp[4] = base[5];
    temp[5] = base[6];
    temp[6] = base[8];
    temp[7] = base[9];
    temp[8] = base[10];

    // temp2 = R @ temp
    _mult3(R, temp, temp2);
    
    // copy temp2 into base.R
    base[0] = temp2[0];
    base[1] = temp2[1];
    base[2] = temp2[2];
    base[4] = temp2[3];
    base[5] = temp2[4];
    base[6] = temp2[5];
    base[8] = temp2[6];
    base[9] = temp2[7];
    base[10] = temp2[8];

    // normalise rotation
    o[0] = base[0 * 4 + 1];
    o[1] = base[1 * 4 + 1];
    o[2] = base[2 * 4 + 1];

    a[0] = base[0 * 4 + 2];
    a[1] = base[1 * 4 + 2];
    a[2] = base[2 * 4 + 2];

    _cross(o, a, n);
    _cross(a, n, o);

    n_norm = _norm(n);
    o_norm = _norm(o);
    a_norm = _norm(a);

    base[0] = n[0] / n_norm;
    base[1] = o[0] / o_norm;
    base[2] = a[0] / a_norm;
    base[4] = n[1] / n_norm;
    base[5] = o[1] / o_norm;
    base[6] = a[1] / a_norm;
    base[8] = n[2] / n_norm;
    base[9] = o[2] / o_norm;
    base[10] = a[2] / a_norm;

    // Step translation
    base[3] += dv[0];
    base[7] += dv[1];
    base[11] += dv[2];

    // Set other attributes
    _copy4(base, sT);
    _r2q(base, sq);

    free(R);
    free(sk);
    free(temp);
    free(temp2);
    free(dv);
    free(n);
    free(o);
    free(a);

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
