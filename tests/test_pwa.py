"""PWA assets: generated icons, the manifest, and per-stack installation."""

from __future__ import annotations

import json
import struct
import zlib

import pytest

from demo_tools import pwa
from demo_tools._resources import STARTERS_DIR

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_header(data: bytes) -> tuple[int, int, int, int]:
    """(width, height, bit depth, colour type) straight out of the IHDR."""
    assert data[:8] == PNG_SIGNATURE
    width, height = struct.unpack(">II", data[16:24])
    return width, height, data[24], data[25]


def _png_pixels(data: bytes) -> tuple[int, int, list[bytes]]:
    width, height, _, _ = _png_header(data)
    idat = b""
    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        tag = data[offset + 4 : offset + 8]
        if tag == b"IDAT":
            idat += data[offset + 8 : offset + 8 + length]
        offset += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 4 + 1
    # Strip the per-scanline filter byte; the encoder always writes filter 0.
    rows = [raw[r * stride + 1 : (r + 1) * stride] for r in range(height)]
    assert all(raw[r * stride] == 0 for r in range(height))
    return width, height, rows


# --- icons ------------------------------------------------------------------


@pytest.mark.parametrize("size", [192, 512])
def test_icons_are_valid_rgba_pngs_of_the_requested_size(size):
    width, height, depth, colour_type = _png_header(pwa.icon_bytes("demo", size))
    assert (width, height) == (size, size)
    assert (depth, colour_type) == (8, 6)  # 8-bit RGBA


def test_icon_draws_the_first_letter_in_white_on_the_accent():
    data = pwa.icon_bytes("calshift", 192)
    _, _, rows = _png_pixels(data)
    red, green, blue = pwa.accent("calshift")

    colours = {tuple(row[x * 4 : x * 4 + 4]) for row in rows for x in range(192)}
    assert (255, 255, 255, 255) in colours, "monogram should be opaque white"
    assert (red, green, blue, 255) in colours, "tile should be the accent colour"
    # The centre of the tile is inside the glyph's bounding box, not the corner.
    assert (0, 0, 0, 0) in colours, "plain icon should have transparent corners"


def test_maskable_icon_fills_the_tile_so_the_launcher_can_crop_it():
    _, _, rows = _png_pixels(pwa.icon_bytes("calshift", 512, maskable=True))
    corners = [rows[0][:4], rows[0][-4:], rows[-1][:4], rows[-1][-4:]]
    assert all(tuple(c)[3] == 255 for c in corners), "maskable icon must not be rounded"


def test_glyph_falls_back_when_the_name_starts_with_punctuation():
    # Must not raise, and must still produce a real icon.
    _, _, depth, colour_type = _png_header(pwa.icon_bytes("_", 192))
    assert (depth, colour_type) == (8, 6)


def test_accent_is_stable_per_name_and_differs_between_names():
    assert pwa.accent("calshift") == pwa.accent("calshift")
    assert pwa.hex_accent("beeper-inbox") != pwa.hex_accent("poster-studio")
    assert pwa.hex_accent("demo").startswith("#")


# --- manifest ---------------------------------------------------------------


def test_manifest_is_valid_json_scoped_to_the_app_path():
    manifest = json.loads(pwa.manifest_json("calshift", scope="/calshift"))
    assert manifest["scope"] == "/calshift/"
    assert manifest["start_url"] == "/calshift/"
    assert manifest["display"] == "standalone"
    assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}
    assert any(icon["purpose"] == "maskable" for icon in manifest["icons"])


def test_manifest_icons_can_live_somewhere_other_than_the_scope():
    manifest = json.loads(pwa.manifest_json("x", scope="/x/", assets="/x/static"))
    assert manifest["scope"] == "/x/"
    assert all(icon["src"].startswith("/x/static/") for icon in manifest["icons"])


def test_service_worker_never_caches_api_calls():
    # A cached API response is how a demo ends up showing yesterday's data.
    assert '.includes("/api/")' in pwa.SERVICE_WORKER
    assert "registration.scope" in pwa.SERVICE_WORKER
    assert 'request.method !== "GET"' in pwa.SERVICE_WORKER


def test_write_assets_emits_every_file_a_browser_asks_for(tmp_path):
    pwa.write_assets(tmp_path, "demo", scope="/demo/")
    written = {p.name for p in tmp_path.iterdir()}
    assert written == {
        "manifest.webmanifest",
        "sw.js",
        "icon-192.png",
        "icon-512.png",
        "icon-512-maskable.png",
    }


def test_next_app_assets_use_the_file_conventions_next_understands(tmp_path):
    pwa.write_next_app_assets(tmp_path, "demo")
    # Next injects the link tags for exactly these names; nothing patches
    # layout.tsx.
    assert (tmp_path / "src" / "app" / "manifest.webmanifest").is_file()
    assert (tmp_path / "src" / "app" / "apple-icon.png").is_file()
    assert (tmp_path / "public" / "icon-512.png").is_file()


# --- the fastapi starter ----------------------------------------------------


def test_fastapi_starter_ships_an_installable_shell():
    static = STARTERS_DIR / "fastapi" / "static"
    index = (static / "index.html").read_text()
    assert 'rel="manifest"' in index
    assert 'rel="apple-touch-icon"' in index
    assert "serviceWorker" in index

    main = (STARTERS_DIR / "fastapi" / "main.py").read_text()
    # The worker must be served from the app root: one under /static/ could
    # never control the pages it exists to cache.
    assert '@app.get("/sw.js"' in main
    assert '@app.get("/manifest.webmanifest"' in main


def test_fastapi_scaffold_writes_root_path_aware_pwa_assets(tmp_path):
    from demo_tools.stacks import fastapi as fastapi_stack

    fastapi_stack.scaffold(tmp_path, "my-demo")
    static = tmp_path / "app" / "static"
    manifest = (static / "manifest.webmanifest").read_text()
    # The prefix differs between Fly ("") and the local Tailscale target
    # ("/my-demo"), so it stays a placeholder for main.py to substitute.
    assert "{{ROOT_PATH}}/" in manifest
    assert (static / "icon-192.png").is_file()
    assert (static / "sw.js").is_file()
