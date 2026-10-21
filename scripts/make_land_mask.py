# ruff: noqa: E501
"""Make the globe's land mask from Natural Earth 110m land data (Phase F2).

Downloads ne_110m_land.geojson once (Natural Earth, public domain), rasterises it with an
even-odd scanline fill into an equirectangular grayscale PNG (255 = land, 0 = sea) and writes
only the mask and a README to dashboard/public/globe/. The source download stays in a
temporary folder and is not committed. Standard library only.

    python scripts/make_land_mask.py [--width 1024]
"""

from __future__ import annotations

import argparse
import datetime
import json
import struct
import sys
import tempfile
import urllib.request
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "dashboard" / "public" / "globe"
URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_110m_land.geojson"
)
SOURCE_PAGE = "https://www.naturalearthdata.com/downloads/110m-physical-vectors/110m-land/"


def polygons(geojson: dict) -> list[list[list[tuple[float, float]]]]:
    """Every polygon as a list of rings (outer ring first), each ring a list of (lon, lat)."""
    result = []
    for feature in geojson["features"]:
        geometry = feature["geometry"]
        if geometry["type"] == "Polygon":
            parts = [geometry["coordinates"]]
        elif geometry["type"] == "MultiPolygon":
            parts = geometry["coordinates"]
        else:
            continue
        for rings in parts:
            result.append([[(float(p[0]), float(p[1])) for p in ring] for ring in rings])
    return result


def rasterise(polys: list, width: int, height: int) -> list[bytearray]:
    """Even-odd scanline fill; the pixel centre decides. Row 0 is the north pole."""
    rows = [bytearray(width) for _ in range(height)]
    for rings in polys:
        edges = []
        for ring in rings:
            for (x0, y0), (x1, y1) in zip(ring, ring[1:], strict=False):
                if y0 != y1:
                    edges.append((x0, y0, x1, y1))
        if not edges:
            continue
        lat_max = max(max(e[1], e[3]) for e in edges)
        lat_min = min(min(e[1], e[3]) for e in edges)
        for row in range(height):
            lat = 90.0 - (row + 0.5) * 180.0 / height
            if lat > lat_max or lat < lat_min:
                continue
            crossings = []
            for x0, y0, x1, y1 in edges:
                if (y0 <= lat < y1) or (y1 <= lat < y0):
                    crossings.append(x0 + (lat - y0) * (x1 - x0) / (y1 - y0))
            crossings.sort()
            for a, b in zip(crossings[0::2], crossings[1::2], strict=False):
                start = max(0, int((a + 180.0) * width / 360.0 + 0.5))
                stop = min(width, int((b + 180.0) * width / 360.0 + 0.5))
                for col in range(start, stop):
                    rows[row][col] = 255
    return rows


def png_bytes(rows: list[bytearray]) -> bytes:
    """A grayscale 8-bit PNG, written with zlib (no imaging package needed)."""
    height, width = len(rows), len(rows[0])

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--width", type=int, default=1024)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="pg_ne_") as tmp:
        source = Path(tmp) / "ne_110m_land.geojson"
        with urllib.request.urlopen(URL, timeout=60) as response:  # noqa: S310
            source.write_bytes(response.read())
        geojson = json.loads(source.read_text(encoding="utf-8"))
    width, height = args.width, args.width // 2
    rows = rasterise(polygons(geojson), width, height)
    land = sum(1 for row in rows for v in row if v) / (width * height)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mask = OUT_DIR / "land-mask.png"
    mask.write_bytes(png_bytes(rows))
    fetched = datetime.date.today().isoformat()
    readme = f"""# globe

- What lives here: `land-mask.png`, an equirectangular land mask ({width}x{height}, grayscale, 255 = land, 0 = sea) used to place the dots of the night globe.
- Origin: Natural Earth 110m land (`ne_110m_land`), made by `scripts/make_land_mask.py`.
- Source page: {SOURCE_PAGE}
- Downloaded from: {URL}
- Date fetched: {fetched}
- Licence: public domain (Natural Earth terms of use: no permission needed, attribution appreciated).
- Only the mask is committed; the source download is not. The mask covers {land * 100:.1f}% of the pixels.
- The globe is a stylised picture, not a map: do not read borders or coastlines from it.
"""
    (OUT_DIR / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    print(f"wrote {mask} ({mask.stat().st_size:,} bytes); land {land * 100:.1f}%", file=sys.stderr)


if __name__ == "__main__":
    main()
