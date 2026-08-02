"""Progressive-web-app assets, so every scaffolded demo installs to a phone.

A demo you can only reach by pasting a URL into a browser is a demo you don't
open. Adding it to a home screen costs three files — a manifest, a service
worker, and icons — and turns it into something that opens like an app.

Two details are easy to get wrong and are handled here once, rather than in
each stack:

*Scope.* A service worker can only control URLs at or below the path it was
served from. These demos run at "/" on Fly but under "/<name>" behind the local
Tailscale proxy, so the worker is written to derive every URL from
``self.registration.scope`` rather than hard-coding a prefix. The same file
works under either.

*Caching.* Demo data changes constantly, so the worker never caches ``/api/``
and treats page loads as network-first. The cached shell is an offline
fallback, not a performance trick — a stale demo that looks live is worse than
one that plainly failed.

Icons are generated rather than shipped: a monogram of the app's first letter
on a colour derived from its name, so a row of installed demos is
distinguishable at a glance. PNG is written with zlib and struct so this stays
a dependency-free scaffolder.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

#: Icon background colours, picked per app from a hash of its name. Chosen to
#: stay legible under a white monogram and to look deliberate side by side.
_HUES: tuple[tuple[int, int, int], ...] = (
    (0x2F, 0x6F, 0xED),  # blue
    (0x0B, 0x80, 0x43),  # green
    (0x8E, 0x24, 0xAA),  # purple
    (0xD5, 0x00, 0x00),  # red
    (0xEF, 0x6C, 0x00),  # orange
    (0x00, 0x96, 0x88),  # teal
    (0xAD, 0x14, 0x57),  # magenta
    (0x45, 0x51, 0xB5),  # indigo
)

#: A 5x7 bitmap font — enough for the one character a monogram needs. Bundled
#: rather than rasterised from a system font, which a scaffolder cannot assume.
_GLYPHS: dict[str, tuple[str, ...]] = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
}

_FALLBACK_GLYPH = _GLYPHS["O"]


def accent(name: str) -> tuple[int, int, int]:
    """A stable colour for this app. Same name in, same colour out."""
    digest = zlib.crc32(name.encode("utf-8"))
    return _HUES[digest % len(_HUES)]


def hex_accent(name: str) -> str:
    red, green, blue = accent(name)
    return f"#{red:02x}{green:02x}{blue:02x}"


def _glyph(name: str) -> tuple[str, ...]:
    for char in name.upper():
        if char in _GLYPHS:
            return _GLYPHS[char]
    return _FALLBACK_GLYPH


def _png(width: int, height: int, rgba_rows: list[bytearray]) -> bytes:
    """Minimal RGBA PNG. One filter byte per scanline, filter type 0 (none)."""

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">2I5B", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(row) for row in rgba_rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def icon_bytes(name: str, size: int, *, maskable: bool = False) -> bytes:
    """A monogram icon: the app's first letter, white on its accent colour.

    ``maskable`` leaves the safe-zone padding Android needs when it crops the
    icon to whatever shape the launcher uses; the plain variant fills the tile.
    """
    red, green, blue = accent(name)
    rows = [bytearray(size * 4) for _ in range(size)]

    # A rounded square, or a full bleed for the maskable variant — Android
    # applies its own mask to that one, and a rounded icon inside a rounded
    # mask reads as a mistake.
    radius = 0 if maskable else int(size * 0.22)
    for y in range(size):
        row = rows[y]
        for x in range(size):
            if radius:
                # Only the corners need testing; the rest of the tile is solid.
                cx = radius - x if x < radius else x - (size - radius - 1) if x >= size - radius else 0
                cy = radius - y if y < radius else y - (size - radius - 1) if y >= size - radius else 0
                if cx > 0 and cy > 0 and cx * cx + cy * cy > radius * radius:
                    continue  # outside the rounded corner: leave transparent
            offset = x * 4
            row[offset : offset + 4] = bytes((red, green, blue, 255))

    glyph = _glyph(name)
    # The maskable icon's safe zone is the middle 80%, so its glyph is smaller.
    scale = max(1, int(size * (0.075 if maskable else 0.095)))
    glyph_width, glyph_height = 5 * scale, 7 * scale
    left = (size - glyph_width) // 2
    top = (size - glyph_height) // 2

    for gy, line in enumerate(glyph):
        for gx, bit in enumerate(line):
            if bit != "1":
                continue
            for y in range(top + gy * scale, top + (gy + 1) * scale):
                row = rows[y]
                start = (left + gx * scale) * 4
                row[start : start + 4 * scale] = b"\xff\xff\xff\xff" * scale

    return _png(size, size, rows)


#: Service worker. Base-path agnostic — see this module's docstring.
SERVICE_WORKER = """\
// Service worker for the installable app shell.
//
// Every URL below is derived from this worker's own registration scope rather
// than hard-coded, because the app is served at "/" on Fly and under a
// Tailscale-stripped "/<name>" prefix locally. Whatever prefix the browser
// registered this worker under is the prefix these URLs use too.
//
// Caching is deliberately conservative: demo data changes constantly and must
// never look stale.
//   - "/api/"      -> network only, never cached.
//   - navigations  -> network first; the cached shell is an offline fallback.
//   - other assets -> cache first, refreshed in the background.

const CACHE_NAME = "app-shell-v1";
const SCOPE_URL = new URL(self.registration.scope);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.add(SCOPE_URL.href))
      // Best effort: a failed precache (first install while offline) must not
      // block installation.
      .catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
      )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return; // never intercept mutating requests

  if (new URL(request.url).pathname.includes("/api/")) {
    event.respondWith(fetch(request));
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match(SCOPE_URL.href).then((r) => r || Response.error())
      )
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response.ok) {
            caches.open(CACHE_NAME).then((cache) => cache.put(request, response.clone()));
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
"""


def head_tags(asset_prefix: str = "") -> str:
    """The ``<head>`` markup that makes a page installable.

    ``asset_prefix`` is prepended to each asset URL for stacks served under a
    path prefix at build time; stacks that resolve URLs at request time pass
    an empty prefix and template the links themselves.
    """
    return (
        f'<link rel="manifest" href="{asset_prefix}/manifest.webmanifest">\n'
        f'<link rel="apple-touch-icon" href="{asset_prefix}/icon-192.png">\n'
        '<meta name="mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
    )


def manifest_json(
    name: str,
    *,
    scope: str = "/",
    assets: str | None = None,
    theme: str | None = None,
) -> str:
    """A web app manifest for ``name`` served under ``scope``.

    ``scope`` must end in "/" and match the path the app is served from, or the
    browser refuses to install it. ``assets`` is where the icons live if that
    differs from the scope — a FastAPI app serves them from ``/static/`` while
    still being scoped at its root.
    """
    if not scope.endswith("/"):
        scope += "/"
    assets = scope if assets is None else assets.rstrip("/") + "/"
    colour = theme or hex_accent(name)
    icons = ",\n".join(
        f"""    {{
      "src": "{assets}icon-{size}.png",
      "sizes": "{size}x{size}",
      "type": "image/png",
      "purpose": "{purpose}"
    }}"""
        for size, purpose in ((192, "any"), (512, "any"))
    )
    icons += f""",
    {{
      "src": "{assets}icon-512-maskable.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }}"""
    return f"""{{
  "name": "{name}",
  "short_name": "{name}",
  "start_url": "{scope}",
  "scope": "{scope}",
  "display": "standalone",
  "background_color": "{colour}",
  "theme_color": "{colour}",
  "icons": [
{icons}
  ]
}}
"""


def write_icons(directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "icon-192.png").write_bytes(icon_bytes(name, 192))
    (directory / "icon-512.png").write_bytes(icon_bytes(name, 512))
    (directory / "icon-512-maskable.png").write_bytes(icon_bytes(name, 512, maskable=True))


def write_next_app_assets(app_root: Path, name: str) -> None:
    """Install the assets using Next.js App Router file conventions.

    Next generates the ``<link rel="manifest">``, ``<link rel="icon">`` and
    ``<link rel="apple-touch-icon">`` tags itself for these exact filenames, so
    nothing here has to patch the generated ``layout.tsx`` — a regex edit on
    somebody else's scaffold output is the kind of thing that breaks silently
    on their next release.

    No service worker: a manifest plus icons is enough for the install prompt,
    and registering one from the App Router needs a client component that this
    has no business injecting.
    """
    src_app = app_root / "src" / "app"
    src_app.mkdir(parents=True, exist_ok=True)
    (src_app / "manifest.webmanifest").write_text(manifest_json(name), encoding="utf-8")
    (src_app / "apple-icon.png").write_bytes(icon_bytes(name, 192))
    write_icons(app_root / "public", name)


def write_assets(
    directory: Path,
    name: str,
    *,
    scope: str = "/",
    assets: str | None = None,
    theme: str | None = None,
    service_worker: bool = True,
) -> None:
    """Write the manifest, service worker and icons into ``directory``."""
    write_icons(directory, name)
    (directory / "manifest.webmanifest").write_text(
        manifest_json(name, scope=scope, assets=assets, theme=theme), encoding="utf-8"
    )
    if service_worker:
        (directory / "sw.js").write_text(SERVICE_WORKER, encoding="utf-8")
