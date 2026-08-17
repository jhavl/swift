from importlib.metadata import PackageNotFoundError, version

from swift.SwiftRoute import SwiftServer, SwiftSocket, start_servers
from swift.SwiftElement import (
    SwiftElement,
    Slider,
    Select,
    Checkbox,
    Radio,
    Button,
    Label,
)
from swift.Swift import Swift
from swift.Handle import AssemblyHandle
from swift.Light import (
    Light,
    AmbientLight,
    HemisphereLight,
    DirectionalLight,
    PointLight,
    SpotLight,
)

try:
    __version__ = version("swift-sim")
except PackageNotFoundError:
    # running from a source checkout without an installed/editable
    # swift-sim distribution -- e.g. importing straight from src/
    __version__ = "unknown"

__all__ = [
    "__version__",
    "Swift",
    "SwiftServer",
    "SwiftSocket",
    "start_servers",
    "SwiftElement",
    "Slider",
    "Select",
    "Checkbox",
    "Radio",
    "Button",
    "Label",
    "AssemblyHandle",
    "Light",
    "AmbientLight",
    "HemisphereLight",
    "DirectionalLight",
    "PointLight",
    "SpotLight",
]
