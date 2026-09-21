"""
End-to-end test of the JS asset check: the real ``integrity.js`` (run under
Node) hashes Swift's files fetched over HTTP from a real ``SwiftServer``, and
the real ``_check_js_assets`` compares that against the files on disk.

The unit tests on each side (public/js/integrity.test.js and
tests/test_js_asset_check.py) can only agree with themselves; this is what
proves the two ends compute the *same* hash for the same bytes -- through a
real socket, on the CI matrix's Windows runner too, where line endings or
path separators could otherwise make them silently disagree.

Needs Node and ``npm ci`` in src/swift/public; see the ``require_node``
fixture in conftest.py.
"""

import json
import subprocess
from pathlib import Path

import pytest

from swift.SwiftRoute import _check_js_assets

PUBLIC = Path(__file__).resolve().parents[1] / "src" / "swift" / "public"

# Excluded from a plain `pytest` (see pyproject.toml); run with
# `pytest -m integration`.
pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("require_node")]


def page_resource_urls() -> list[str]:
    """
    Paths a browser would report having loaded: Swift's page, stylesheet and
    modules (not the *.test.js files, which the page never loads), plus a
    vendored module and an icon that must be ignored.
    """
    paths = ["index.html", "style/index.css"]
    paths += sorted(
        p.relative_to(PUBLIC).as_posix()
        for p in (PUBLIC / "js").glob("*.js")
        if not p.name.endswith(".test.js")
    )
    paths += ["js/vendor/build/three.module.js", "icons/icons/dark/add.svg"]
    return paths


def js_asset_hashes(port: int) -> dict[str, str]:
    """What the browser-side code sends: integrity.js run against the server."""
    script = (
        "const { loadedAssetPaths, hashAssets } = await import(process.argv[1]);"
        "const base = `http://127.0.0.1:${process.argv[2]}/`;"
        "const urls = JSON.parse(process.argv[3]).map((p) => base + p);"
        "const paths = loadedAssetPaths(urls, base + '?12345');"
        "const hashes = await hashAssets(paths, (p) => fetch(base + p));"
        "process.stdout.write(JSON.stringify(hashes));"
    )
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            script,
            (PUBLIC / "js" / "integrity.js").as_uri(),
            str(port),
            json.dumps(page_resource_urls()),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=PUBLIC,
    )
    return json.loads(result.stdout)


def handshake(hashes) -> str:
    return json.dumps({"event": "connected", "js_hashes": hashes})


def test_hashes_computed_by_the_js_match_the_files_on_disk(server_port, capsys):
    hashes = js_asset_hashes(server_port)

    # Swift's own files are covered; vendored code and icons are not.
    assert "index.html" in hashes
    assert "style/index.css" in hashes
    assert "js/main.js" in hashes
    assert "js/integrity.js" in hashes
    assert not any(name.startswith(("js/vendor/", "icons/")) for name in hashes)
    assert all(isinstance(h, str) and len(h) == 64 for h in hashes.values())

    _check_js_assets(handshake(hashes))

    assert capsys.readouterr().out == ""


def test_a_stale_file_reported_by_the_js_is_named(server_port, capsys):
    hashes = js_asset_hashes(server_port)
    hashes["js/shapes.js"] = "0" * 64  # as if the tab held an older copy

    _check_js_assets(handshake(hashes))

    out = capsys.readouterr().out
    assert "js/shapes.js" in out
    assert "js/main.js" not in out
