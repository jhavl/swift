"""
Tests for working out which files a mesh needs (swift/_assets.py) and sending
them over the comm bridge. The names files go by must agree with the browser's
(public/js/assets.js): both read tests/data/asset_keys.json.
"""

import json
from pathlib import Path

import pytest

from swift._assets import asset_key, mesh_files
from swift._comm import CommBridge
import swift._comm as comm

CASES = json.loads((Path(__file__).parent / "data" / "asset_keys.json").read_text())[
    "cases"
]


@pytest.mark.parametrize("case", CASES, ids=[c["path"] for c in CASES])
def test_asset_key_is_what_the_browser_works_out(case):
    assert asset_key(case["path"]) == case["key"]


def write(directory: Path, name: str, content: str | bytes = b"x") -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content)
    else:
        path.write_bytes(content)
    return path


def test_a_mesh_with_nothing_else_is_just_itself(tmp_path):
    stl = write(tmp_path, "arm.stl")
    assert mesh_files(stl) == [stl]


def test_a_missing_mesh_is_an_error_at_once(tmp_path):
    with pytest.raises(FileNotFoundError, match="arm.stl"):
        mesh_files(tmp_path / "arm.stl")


def test_an_obj_needs_its_mtl_and_the_textures_that_names(tmp_path):
    obj = write(tmp_path, "arm.obj")
    mtl = write(
        tmp_path,
        "arm.mtl",
        "newmtl a\nmap_Kd paint.png\nmap_Bump -bm 0.5 bumps/rough.png\nKd 1 1 1\n"
        "map_Ks missing.png\n",
    )
    paint = write(tmp_path, "paint.png")
    rough = write(tmp_path, "bumps/rough.png")

    assert mesh_files(obj) == [obj, mtl, paint, rough]


def test_an_obj_without_an_mtl_is_just_itself(tmp_path):
    obj = write(tmp_path, "arm.obj")
    assert mesh_files(obj) == [obj]


def test_a_texture_name_in_an_mtl_is_a_file_name_not_a_uri(tmp_path):
    obj = write(tmp_path, "arm.obj")
    write(tmp_path, "arm.mtl", "map_Kd 100%25.png\n")
    literal = write(tmp_path, "100%25.png")
    write(tmp_path, "100%.png")

    assert mesh_files(obj)[-1] == literal


def test_a_dae_needs_the_images_it_names(tmp_path):
    dae = write(
        tmp_path,
        "arm.dae",
        """<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
          <library_images>
            <image id="a"><init_from>tex/a b.png</init_from></image>
            <image id="b"><init_from>file:///{here}/tex/b.png</init_from></image>
            <image id="c"><init_from>http://example.com/c.png</init_from></image>
          </library_images>
          <newparam sid="s"><surface type="2D"><init_from>a</init_from></surface></newparam>
        </COLLADA>""".replace(
            "{here}", str(tmp_path).lstrip("/")
        ),
    )
    a = write(tmp_path, "tex/a b.png")
    b = write(tmp_path, "tex/b.png")
    write(tmp_path, "a")  # an image id that happens to be a file name too is harmless

    # the id "a" resolves to a file here, which is sent needlessly but does no harm
    assert mesh_files(dae)[:3] == [dae, a, b]


def test_a_dae_in_collada_1_5_names_images_in_a_ref(tmp_path):
    dae = write(
        tmp_path,
        "arm.dae",
        """<COLLADA xmlns="http://www.collada.org/2008/03/COLLADASchema" version="1.5.0">
          <image id="a"><init_from><ref>a.png</ref></init_from></image>
        </COLLADA>""",
    )
    a = write(tmp_path, "a.png")

    assert mesh_files(dae) == [dae, a]


def test_a_dae_that_does_not_parse_is_left_for_the_browser_to_report(tmp_path):
    dae = write(tmp_path, "arm.dae", "<COLLADA")
    assert mesh_files(dae) == [dae]


def test_a_gltf_needs_its_buffers_and_images(tmp_path):
    gltf = write(
        tmp_path,
        "arm.gltf",
        json.dumps(
            {
                "buffers": [
                    {"uri": "arm.bin"},
                    {"uri": "data:application/octet-stream;base64,AA=="},
                ],
                "images": [{"uri": "skin%20one.png"}],
            }
        ),
    )
    bin_ = write(tmp_path, "arm.bin")
    skin = write(tmp_path, "skin one.png")

    assert mesh_files(gltf) == [gltf, bin_, skin]


def test_windows_style_references_are_not_mistaken_for_uri_schemes(tmp_path):
    obj = write(tmp_path, "arm.obj")
    write(tmp_path, "arm.mtl", "map_Kd C:\\textures\\paint.png\n")

    # no such file here, so it is left out; what matters is that it is not an error
    assert len(mesh_files(obj)) == 2


def make_bridge():
    sent = []
    return CommBridge(lambda msg, buffers=None: sent.append((msg, buffers))), sent


def test_files_are_sent_as_numbered_messages_with_the_bytes_as_a_buffer(tmp_path):
    bridge, sent = make_bridge()
    stl = write(tmp_path, "arm.stl", b"abc")

    bridge.send_files(str(stl))

    ((msg, buffers),) = sent
    assert msg["func"] == "asset" and msg["seq"] == 1
    assert msg["data"] == {"path": asset_key(stl), "index": 0, "count": 1}
    assert buffers == [b"abc"]


def test_a_large_file_is_sent_in_pieces(tmp_path, monkeypatch):
    monkeypatch.setattr(comm, "_CHUNK", 4)
    bridge, sent = make_bridge()
    stl = write(tmp_path, "arm.stl", b"0123456789")

    bridge.send_files(str(stl))

    assert [m["data"]["index"] for m, _ in sent] == [0, 1, 2]
    assert all(m["data"]["count"] == 3 for m, _ in sent)
    assert b"".join(b[0] for _, b in sent) == b"0123456789"


def test_an_empty_file_is_sent_as_one_empty_piece(tmp_path):
    bridge, sent = make_bridge()
    stl = write(tmp_path, "arm.stl", b"")

    bridge.send_files(str(stl))

    ((msg, buffers),) = sent
    assert msg["data"]["count"] == 1
    assert buffers == [b""]  # the browser reads the first buffer of every piece


def test_a_file_already_sent_is_not_sent_again(tmp_path):
    bridge, sent = make_bridge()
    stl = write(tmp_path, "arm.stl")

    bridge.send_files(str(stl))
    bridge.send_files(str(stl))

    assert len(sent) == 1


def test_a_resend_carries_the_buffers_again(tmp_path):
    bridge, sent = make_bridge()
    stl = write(tmp_path, "arm.stl", b"abc")
    bridge.send_files(str(stl))
    sent.clear()

    bridge.receive({"reply": {"event": "sync", "have": 0}})

    ((msg, buffers),) = sent
    assert msg["func"] == "asset" and buffers == [b"abc"]


def test_a_missing_mesh_raises_before_anything_is_sent(tmp_path):
    bridge, sent = make_bridge()

    with pytest.raises(FileNotFoundError):
        bridge.send_files(str(tmp_path / "nope.stl"))

    assert sent == []
