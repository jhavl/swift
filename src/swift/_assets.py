"""
Which files a mesh needs, for notebooks where the browser cannot ask Python for
them (see :mod:`swift._comm`).

On the desktop the page fetches a mesh, and whatever the mesh refers to (the
material file and textures of an ``.obj``, the images of a ``.dae``) from Swift's
``/retrieve/`` route as it loads them. In a notebook nothing can be fetched, so
Python works out the files and sends them before the shape that uses them.
"""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlparse

# MTL statements that name an image file
_MTL_IMAGE = re.compile(
    r"^\s*(?:map_\w+|bump|disp|decal|refl)\s+(.*\S)\s*$", re.IGNORECASE | re.MULTILINE
)


def asset_key(path: str | os.PathLike[str]) -> str:
    """
    The name a file goes by in the browser: the path with forward slashes, no
    drive letter and no ``.`` or ``..`` parts.

    This is what ``assetKey()`` in ``assets.js`` makes of the URL a loader asks
    for, which is ``/retrieve`` and the path (see ``retrieveUrl`` in
    ``shapes.js``); the two must agree, for Windows paths too, so this is done
    by hand, step for step as there, and not with ``os.path``, whose
    ``normpath`` depends on the operating system Python is running on.

    :param path: a file path, as given to a mesh, with either kind of slash
    :returns: the key
    """
    posix = os.fspath(path).replace("\\", "/")
    posix = re.sub(r"^[A-Za-z]:", "", posix)
    parts: list[str] = []
    for part in posix.split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part not in (".", ""):
            parts.append(part)
    return "/" + "/".join(parts)


def _local(reference: str, base: Path, uri: bool) -> Path | None:
    """
    The file a reference inside a mesh file points to, if it is a local one.

    :param reference: the reference as written in the mesh file
    :param base: the directory of the mesh file, which a relative reference is
        relative to
    :param uri: whether the file format writes references as URIs, with
        percent-encoding and a ``file:`` scheme (Collada, glTF), or as plain
        file names (the material file of an ``.obj``)
    """
    reference = reference.strip()
    if not reference or reference.startswith("data:"):
        return None

    if re.match(r"^[A-Za-z]:[\\/]", reference):  # a Windows path, not a URI scheme
        name = reference
    elif not uri:
        name = reference
    else:
        parsed = urlparse(reference)
        if parsed.scheme not in ("", "file"):
            return None
        name = unquote(parsed.path)
        # file:///C:/dir/a.png has the path /C:/dir/a.png
        name = re.sub(r"^/([A-Za-z]:)", r"\1", name)

    path = Path(name)
    if path.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", name):
        return path
    return base / path


def _obj_files(path: Path) -> list[Path]:
    # public/js/shapes.js loads <name>.mtl for <name>.obj, whatever the obj says
    mtl = path.with_suffix(".mtl")
    if not mtl.is_file():
        return []
    files = [mtl]
    for name in _MTL_IMAGE.findall(mtl.read_text(errors="replace")):
        # the file name is the last word: options such as "-s 1 1 1" come before it
        texture = _local(name.split()[-1], mtl.parent, uri=False)
        if texture is not None:
            files.append(texture)
    return files


def _dae_files(path: Path) -> list[Path]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []  # the browser will report it, as on the desktop
    files = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "init_from":
            continue
        # Collada 1.4 has the path as the text, 1.5 inside a <ref>; some
        # init_from name an image by its id rather than a file, and are dropped below
        ref = next((e for e in element if e.tag.rsplit("}", 1)[-1] == "ref"), element)
        file = _local(ref.text or "", path.parent, uri=True)
        if file is not None:
            files.append(file)
    return files


def _gltf_files(path: Path) -> list[Path]:
    try:
        gltf = json.loads(path.read_text())
    except ValueError:
        return []
    files = []
    for entry in gltf.get("buffers", []) + gltf.get("images", []):
        file = _local(entry.get("uri", ""), path.parent, uri=True)
        if file is not None:
            files.append(file)
    return files


_DEPENDENCIES = {".obj": _obj_files, ".dae": _dae_files, ".gltf": _gltf_files}


def mesh_files(filename: str | os.PathLike[str]) -> list[Path]:
    """
    The files needed to load a mesh: the file itself, and those it refers to
    that exist (the others are reported by the browser when it fails to load
    them, as on the desktop).

    :param filename: the mesh file
    :returns: the mesh file first, then the others
    :raises FileNotFoundError: if the mesh file itself does not exist
    """
    path = Path(filename)
    if not path.is_file():
        raise FileNotFoundError(f"Mesh file not found: {str(filename)!r}")

    files = [path]
    for file in _DEPENDENCIES.get(path.suffix.lower(), lambda _p: [])(path):
        if file.is_file() and file not in files:
            files.append(file)
    return files
