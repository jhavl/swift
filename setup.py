from setuptools import setup, find_packages, Extension
from os import path
import os

here = path.abspath(path.dirname(__file__))

req = [
    'numpy',
    'websockets'
]

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# # Get the release/version string
# with open(path.join(here, 'RELEASE'), encoding='utf-8') as f:
#     release = f.read()


def package_files(directory):
    paths = []
    for (pathhere, _, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join('..', pathhere, filename))
    return paths


extra_files = package_files('swift/public')

setup(
    name='swift',

    version='0.1.0',

    description='A Python/Javascript Visualiser',

    long_description=long_description,

    long_description_content_type='text/markdown',

    url='https://github.com/jhavl/swift',

    author='Jesse Haviland',

    license='MIT',

    python_requires='>=3.6',

    keywords='robotics vision arm kinematics ros',

    packages=find_packages(exclude=["tests", "examples"]),

    package_data={'swift': extra_files},

    include_package_data=True,

    install_requires=req
)
