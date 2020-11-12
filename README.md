[![PyPI version](https://badge.fury.io/py/swift-sim.svg)](https://badge.fury.io/py/swift-sim)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/swift-sim)](https://img.shields.io/pypi/pyversions/swift-sim)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![QUT Centre for Robotics Open Source](https://github.com/qcr/qcr.github.io/raw/master/misc/badge.svg)](https://qcr.github.io)

# Swift

Swift is a lightweight browser based simulator built on top of the [Robotics Toolbox for Python](https://github.com/petercorke/robotics-toolbox-python). This simulator provides robotics-specific functionality for rapid prototyping of algorithms, research, and education. Built using Python and Javascript, Swift is corss-platform (Linux, MacOS, and Windows) while also leveraging the ubiquity and support of these languages.

Through the [Robotics Toolbox for Python](https://github.com/petercorke/robotics-toolbox-python), Swift can visualise over 30 supplied robot models from well-known contemporary robots from Franka-Emika, Kinova, Universal Robotics, Rethink as well as classical robots such as the Puma 560 and the Stanford arm. Swift is under development and will support mobile robots in the future.

Swift provides:

  * visualisation of mesh objects (collada and stl files) and also primitive shapes;
  * robot visualisation and simulation;
  * recording and saving a video of the simulation;
  * source code which can be read for learning and teaching;


## Installing
### Using pip

It is highly recommended to control Swift through the [Robotics Toolbox for Python](https://github.com/petercorke/robotics-toolbox-python). By installing the toolbox through PyPI, swift is installed as a dependancy

```shell script
pip3 install roboticstoolbox-python
```

Otherwise, Swift alone can be install by

```shell script
pip3 install swift-sim
```

### From GitHub

To install the bleeding-edge version from GitHub

```shell script
git clone https://github.com/jhavl/swift.git
cd swift
pip3 install -e .
```

