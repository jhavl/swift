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
static PyObject *step_v(PyObject *self, PyObject *args);

static PyMethodDef physMethods[] = {
    {"step_v",
     (PyCFunction)step_v,
     METH_VARARGS,
     "Link"},
    {NULL, NULL, 0, NULL} /* Sentinel */
};

static struct PyModuleDef physmodule =
    {
        PyModuleDef_HEAD_INIT,
        "phys",
        "Fast Kinematics",
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
