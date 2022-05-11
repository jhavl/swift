/**
 * \file phys.h
 * \author Jesse Haviland
 * \brief Definitions for c file
 *
 */

#ifndef _phys_h_
#define _phys_h_

#include <math.h>
#include <numpy/arrayobject.h>
#include "linalg.h"

#ifdef __cplusplus
extern "C"
{
#endif /* __cplusplus */

    double _norm(npy_float64 *v);
    void _eye3(npy_float64 *data);
    void skew(Vector3 v, MapMatrix3dc sk);
    void _skew(npy_float64 *v, npy_float64 *sk);
    void _dot9(double mult, npy_float64 *arr, npy_float64 *ret);
    void _add9_inplace(npy_float64 *add, npy_float64 *ret);
    void _mult3(npy_float64 *A, npy_float64 *B, npy_float64 *C);
    void _cross(npy_float64 *a, npy_float64 *b, npy_float64 *c);
    void _r2q(npy_float64 *r, npy_float64 *q);
    void _copy4(npy_float64 *A, npy_float64 *B);

    static PyObject *step_v(PyObject *self, PyObject *args);
    static PyObject *step_shape(PyObject *self, PyObject *args);

#ifdef __cplusplus
} /* extern "C" */
#endif /* __cplusplus */

#endif