from setuptools import setup, find_packages, Extension
from os import path
import os
import numpy


def package_files(directory):
    paths = []
    for (pathhere, _, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join("..", pathhere, filename))
    return paths


extra_folders = [
    "swift/out",
    "swift/core",
]

extra_files = []
for extra_folder in extra_folders:
    extra_files += package_files(extra_folder)

phys = Extension(
    "swift.phys",
    sources=["./swift/core/phys.cpp"],
    include_dirs=["./swift/core/", numpy.get_include()],
)

setup(
    package_data={"swift": extra_files},
    ext_modules=[phys],
)
