from setuptools import setup, find_packages
from os import path
import os

here = path.abspath(path.dirname(__file__))

req = [
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
    name='swift-sim',

    version='0.6.1',

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

    include_package_data=True,

    install_requires=req
)
