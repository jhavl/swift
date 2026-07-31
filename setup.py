from setuptools import setup, find_packages, Extension
from os import path
import os
import numpy


# Maintainer-only tooling in swift/public/ (npm vendoring scripts, not
# needed to serve the frontend) -- excluded so a locally-present
# node_modules/ (gitignored, ~25MB) never leaks into a build.
PACKAGE_DATA_EXCLUDE_DIRS = {"node_modules"}
PACKAGE_DATA_EXCLUDE_FILES = {"package.json", "package-lock.json"}

# package_data entries must be relative to the package's own source dir
# (src/swift/), not the repo root.
PACKAGE_SRC_DIR = os.path.join("src", "swift")


def package_files(directory):
    paths = []
    for pathhere, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in PACKAGE_DATA_EXCLUDE_DIRS]
        for filename in filenames:
            if filename in PACKAGE_DATA_EXCLUDE_FILES:
                continue
            paths.append(
                os.path.relpath(os.path.join(pathhere, filename), PACKAGE_SRC_DIR)
            )
    return paths


extra_folders = [
    "src/swift/public",
    "src/swift/cpp-extensions",
]

extra_files = []
for extra_folder in extra_folders:
    extra_files += package_files(extra_folder)

phys = Extension(
    "swift.phys",
    sources=["./src/swift/cpp-extensions/phys.cpp"],
    include_dirs=["./src/swift/cpp-extensions/", numpy.get_include()],
    define_macros=[("NPY_TARGET_VERSION", "NPY_2_0_API_VERSION")],
)

setup(
    package_data={"swift": extra_files},
    ext_modules=[phys],
)
