"""
Tests for SwiftRoute._check_js_version() -- warns when a connecting
browser tab's JS handshake reports a different (or no) version than the
currently-installed swift-sim package, which almost always means a
stale browser cache surviving a pip upgrade.
"""

import json

import pytest

from swift.SwiftRoute import _check_js_version


@pytest.fixture(autouse=True)
def installed_version(monkeypatch):
    monkeypatch.setattr("swift.SwiftRoute._installed_version", lambda pkg: "2.0.0")


def test_matching_version_prints_nothing(capsys):
    _check_js_version(json.dumps({"event": "connected", "js_version": "2.0.0"}))

    assert capsys.readouterr().out == ""


def test_mismatched_version_warns_with_both_versions(capsys):
    _check_js_version(json.dumps({"event": "connected", "js_version": "1.9.0"}))

    out = capsys.readouterr().out
    assert "1.9.0" in out
    assert "2.0.0" in out
    assert "stale" in out


def test_pre_version_reporting_handshake_warns_as_very_old(capsys):
    # A JS build from before this feature existed just sends the bare
    # string "Connected" -- not valid JSON at all.
    _check_js_version("Connected")

    out = capsys.readouterr().out
    assert "very old" in out
    assert "2.0.0" in out


def test_json_handshake_missing_js_version_key_also_warns_as_very_old(capsys):
    _check_js_version(json.dumps({"event": "connected"}))

    out = capsys.readouterr().out
    assert "very old" in out


def test_dev_install_with_no_dist_info_prints_nothing(capsys, monkeypatch):
    from importlib.metadata import PackageNotFoundError

    def raise_not_found(pkg):
        raise PackageNotFoundError(pkg)

    monkeypatch.setattr("swift.SwiftRoute._installed_version", raise_not_found)

    _check_js_version("Connected")

    assert capsys.readouterr().out == ""
