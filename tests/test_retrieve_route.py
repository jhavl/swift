"""
End-to-end test of the ``/retrieve/`` route: the path a browser would request
for a mesh, built by the real JS ``retrieveUrl()`` from the filename the real
spatialgeometry ``Mesh.to_dict()`` produces, served by the real
``SwiftServer`` over a real socket.

Everything else in tests/ drains Swift's queues through a fake browser, so a
path-handling bug at the Python/JS/OS boundary is invisible to it -- jhavl/
swift#152 (Windows backslashes) was only found by hand on Windows, and every
unit test involved passed on Linux. This runs on the CI matrix's Windows
runner too, so the boundary is exercised on the OS it broke on.

Needs Node and ``npm ci`` in src/swift/public (shapes.js imports three). Where
either is missing the tests skip locally, but fail under CI (``CI`` is set by
GitHub Actions), so a broken workflow can't turn this into a silent pass.
"""

import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import spatialgeometry as sg

PUBLIC = Path(__file__).resolve().parents[1] / "src" / "swift" / "public"

# Excluded from a plain `pytest` (see pyproject.toml); run with
# `pytest -m integration` after `npm ci` in src/swift/public. The
# require_node and server_port fixtures live in conftest.py.
pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("require_node")]


CONTENT = b"solid placeholder\nendsolid placeholder\n"


def js_retrieve_url(filename: str) -> str:
    """The URL path swift's frontend requests for ``filename`` (shapes.js)."""
    script = (
        "globalThis.window = { innerWidth: 0, innerHeight: 0 };"
        "const { retrieveUrl } = await import(process.argv[1]);"
        "process.stdout.write(retrieveUrl(process.argv[2]));"
    )
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            script,
            (PUBLIC / "js" / "shapes.js").as_uri(),
            filename,
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=PUBLIC,
    )
    return result.stdout


@pytest.fixture
def mesh_file():
    # Created under the working directory, not the system temp dir, and with
    # a space in its name (to exercise URI encoding on a real filesystem).
    # On Windows the frontend strips the drive letter and the server resolves
    # the remaining rooted path against the *current* drive, so a file on a
    # different drive than the working directory (GitHub's windows runners
    # keep the workspace on D: and the temp dir on C:) can never be found --
    # a known limitation of that scheme, not what this test is about.
    with tempfile.TemporaryDirectory(dir=Path.cwd(), prefix="my meshes ") as d:
        path = Path(d) / "arm link.stl"
        path.write_bytes(CONTENT)
        yield path


def fetch(port: int, url_path: str) -> bytes:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{url_path}", timeout=5) as r:
        assert r.status == 200
        return r.read()


def test_native_path_is_retrievable(server_port, mesh_file):
    # The filename exactly as the OS spells it: backslashes and a drive
    # letter on Windows, plain POSIX elsewhere.
    url_path = js_retrieve_url(str(mesh_file))
    assert fetch(server_port, url_path) == CONTENT


def test_path_as_serialized_by_spatialgeometry_is_retrievable(server_port, mesh_file):
    # The actual Python -> JS handoff: whatever Mesh.to_dict() emits (forward
    # slashes since spatialgeometry normalizes them, backslashes before).
    filename = sg.Mesh(str(mesh_file)).to_dict()["filename"]
    url_path = js_retrieve_url(filename)
    assert fetch(server_port, url_path) == CONTENT


def test_missing_file_is_404(server_port, mesh_file):
    # Guards the tests above: proves a 200 there means the file was found,
    # not that the route answers everything.
    url_path = js_retrieve_url(str(mesh_file.with_name("nonexistent.stl")))
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        fetch(server_port, url_path)
    assert excinfo.value.code == 404
