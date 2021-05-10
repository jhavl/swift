from setuptools import setup, find_packages, Extension
from os import path
import os

# fmt: off
import pip
pip.main(['install', 'numpy>=1.18.0'])
import numpy
# fmt: on

here = path.abspath(path.dirname(__file__))

req = [
    'numpy>=1.18.0',
    'spatialgeometry>=0.1.0',
    'websockets'
]

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


def package_files(directory):
    paths = []
    for (pathhere, _, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join('..', pathhere, filename))
    return paths


extra_folders = [
    'swift/out',
    'swift/core',
]

extra_files = []
for extra_folder in extra_folders:
    extra_files += package_files(extra_folder)

phys = Extension(
    'phys',
    sources=[
        './swift/core/phys.c'],
    include_dirs=[
        './swift/core/',
        numpy.get_include()
    ])

setup(
    name='swift-sim',

    version='0.9.6',

    description='A Python/Javascript Visualiser',

    long_description=long_description,

    long_description_content_type='text/markdown',

    url='https://github.com/jhavl/swift',

    author='Jesse Haviland',

    license='MIT',

    classifiers=[
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],

    python_requires='>=3.6',

    keywords='python robotics robotics-toolbox kinematics dynamics' \
             ' motion-planning trajectory-generation jacobian hessian' \
             ' control simulation robot-manipulator mobile-robot',

    packages=find_packages(exclude=["tests", "examples"]),

    package_data={'swift': extra_files},

    # include_package_data=True,

    ext_modules=[phys],

    install_requires=req
)
