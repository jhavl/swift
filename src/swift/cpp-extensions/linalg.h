/**
 * \file linalg.h
 * \author Jesse Haviland
 *
 */
/* linalg.h */

#ifndef _LINALG_H_
#define _LINALG_H_

#include <Eigen/Dense>

#ifdef __cplusplus
extern "C"
{
#endif /* __cplusplus */

#define Matrix3dc Eigen::Matrix3d
#define Matrix3dr Eigen::Matrix<double, 3, 3, Eigen::RowMajor>

#define MapMatrix3dc Eigen::Map<Matrix3dc>
#define MapMatrix3dr Eigen::Map<Matrix3dr>

#define Matrix4dc Eigen::Matrix4d
#define Matrix4dr Eigen::Matrix<double, 4, 4, Eigen::RowMajor>

#define MapMatrix4dc Eigen::Map<Matrix4dc>
#define MapMatrix4dr Eigen::Map<Matrix4dr>

#define Vector3 Eigen::Vector3d
#define MapVector3 Eigen::Map<Vector3>

#define Vector4 Eigen::Vector4d
#define MapVector4 Eigen::Map<Vector4>

#define Vector6 Eigen::Matrix<double, 6, 1>
#define MapVector6 Eigen::Map<Vector6>

#ifdef __cplusplus
} /* extern "C" */
#endif /* __cplusplus */

#endif