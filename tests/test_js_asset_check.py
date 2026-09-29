"""
Tests for SwiftRoute._check_js_assets() -- warns when a connecting browser
tab's handshake reports hashes of Swift's JavaScript that differ from the
files on disk (a stale cached copy, or a file edited mid-session), naming the
files that differ.

The JS side that produces these hashes is tested in
public/js/integrity.test.js, and the two are run against each other over a
real server in tests/test_js_asset_check_integration.py.
"""

import hashlib
import json

import pytest

from swift.SwiftRoute import _check_js_assets


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def root(tmp_path):
    (tmp_path / "js").mkdir()
    (tmp_path / "js" / "main.js").write_bytes(b"main v1")
    (tmp_path / "js" / "shapes.js").write_bytes(b"shapes v1")
    (tmp_path / "index.html").write_bytes(b"<html></html>")
    return tmp_path


def handshake(hashes) -> str:
    return json.dumps({"event": "connected", "js_hashes": hashes})


def test_matching_hashes_print_nothing(root, capsys):
    _check_js_assets(
        handshake(
            {
                "index.html": sha256(b"<html></html>"),
                "js/main.js": sha256(b"main v1"),
                "js/shapes.js": sha256(b"shapes v1"),
            }
        ),
        root,
    )

    assert capsys.readouterr().out == ""


def test_a_differing_file_is_named_and_the_others_are_not(root, capsys):
    _check_js_assets(
        handshake(
            {
                "js/main.js": sha256(b"main v1"),
                "js/shapes.js": sha256(b"an older shapes"),
            }
        ),
        root,
    )

    out = capsys.readouterr().out
    assert "js/shapes.js" in out
    assert "js/main.js" not in out
    assert "stale" in out


def test_every_differing_file_is_named(root, capsys):
    _check_js_assets(
        handshake({"js/main.js": sha256(b"x"), "js/shapes.js": sha256(b"y")}), root
    )

    out = capsys.readouterr().out
    assert "js/main.js" in out and "js/shapes.js" in out


def test_edited_on_disk_after_the_tab_loaded_is_caught(root, capsys):
    # The case a version string could never see: same release, different
    # content.
    loaded = sha256((root / "js" / "main.js").read_bytes())
    (root / "js" / "main.js").write_bytes(b"main v2, edited mid-session")

    _check_js_assets(handshake({"js/main.js": loaded}), root)

    assert "js/main.js" in capsys.readouterr().out


def test_a_file_the_server_does_not_have_is_reported(root, capsys):
    _check_js_assets(handshake({"js/removed.js": sha256(b"old")}), root)

    out = capsys.readouterr().out
    assert "js/removed.js" in out
    assert "not found" in out


def test_a_null_hash_for_one_file_means_could_not_check(root, capsys):
    _check_js_assets(handshake({"js/main.js": None}), root)

    assert capsys.readouterr().out == ""


def test_null_js_hashes_means_the_browser_could_not_hash(root, capsys):
    # crypto.subtle only exists in secure contexts (https / localhost).
    _check_js_assets(handshake(None), root)

    assert capsys.readouterr().out == ""


def test_paths_outside_the_served_directory_are_never_read(root, tmp_path_factory, capsys):
    outside = tmp_path_factory.mktemp("outside") / "secret.txt"
    outside.write_bytes(b"secret")

    _check_js_assets(
        handshake({"../" + outside.parent.name + "/secret.txt": sha256(b"different")}),
        root,
    )

    assert capsys.readouterr().out == ""


def test_handshake_without_hashes_warns_as_old_js(root, capsys):
    _check_js_assets(json.dumps({"event": "connected"}), root)

    assert "old, cached copy" in capsys.readouterr().out


def test_previous_version_string_handshake_warns_as_old_js(root, capsys):
    # 2.0.0 / 2.0.1 sent js_version instead of hashes.
    _check_js_assets(json.dumps({"event": "connected", "js_version": "2.0.1"}), root)

    assert "old, cached copy" in capsys.readouterr().out


def test_bare_connected_string_warns_as_old_js(root, capsys):
    # The very first JS builds sent the plain string "Connected", not JSON.
    _check_js_assets("Connected", root)

    assert "old, cached copy" in capsys.readouterr().out


def test_works_without_an_installed_dist_info(root, capsys, monkeypatch):
    # Content comparison needs no package metadata, so an editable/dev
    # checkout is checked like any other install (the old version check had
    # to skip these).
    def not_consulted(pkg):
        raise AssertionError("package metadata should not be consulted")

    monkeypatch.setattr("importlib.metadata.version", not_consulted)

    _check_js_assets(handshake({"js/main.js": sha256(b"an older main")}), root)

    assert "js/main.js" in capsys.readouterr().out
