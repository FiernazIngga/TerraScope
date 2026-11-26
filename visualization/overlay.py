"""Export raster layers and simulation grids to Web-Mercator RGBA PNGs for MapLibre."""

from pathlib import Path
import struct
import time
import zlib

import numpy as np
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform

from simulation.common import RISK_LABELS, SimulationResult
from utils.raster_io import load_raster_bands

BASE_DIR = Path(__file__).resolve().parent.parent
OVERLAY_DIR = BASE_DIR / "maps" / "overlays"
WEB_CRS = "EPSG:3857"

DROUGHT_COLORS = {
    1: (132, 204, 22, 170),   # Rendah
    2: (250, 204, 21, 185),   # Sedang
    3: (249, 115, 22, 200),   # Tinggi
    4: (220, 38, 38, 215),    # Sangat Tinggi
}

FLOOD_COLORS = {
    1: (56, 189, 248, 165),   # Rendah
    2: (59, 130, 246, 185),   # Sedang
    3: (29, 78, 216, 205),    # Tinggi
    4: (126, 34, 206, 220),   # Sangat Tinggi
}

ESA_WORLDCOVER_PALETTE = {
    10: ("Pohon / Hutan", (0, 100, 0, 195)),
    20: ("Semak Belukar", (255, 187, 34, 195)),
    30: ("Padang Rumput", (255, 255, 76, 195)),
    40: ("Lahan Pertanian", (240, 150, 255, 195)),
    50: ("Permukiman / Terbangun", (250, 0, 0, 195)),
    60: ("Lahan Terbuka", (180, 180, 180, 195)),
    80: ("Badan Air", (0, 100, 200, 205)),
    90: ("Lahan Basah", (0, 150, 160, 195)),
}

RAW_RASTER_LAYERS = {
    "ndvi": {
        "label": "NDVI (Kerapatan Vegetasi)",
        "file": "diy_drought_indices_30m.tif",
        "band": "NDVI",
        "range": (-0.1, 0.8),
        "stops": [(165, 42, 42), (250, 204, 21), (22, 163, 74)],
        "legend_labels": ("Rendah (-0.1)", "Sedang (0.35)", "Tinggi (0.8)"),
    },
    "ndmi": {
        "label": "NDMI (Kelembapan Vegetasi)",
        "file": "diy_drought_indices_30m.tif",
        "band": "NDMI",
        "range": (-0.3, 0.5),
        "stops": [(234, 88, 12), (253, 224, 71), (14, 165, 233)],
        "legend_labels": ("Kering (-0.3)", "Sedang (0.1)", "Lembap (0.5)"),
    },
    "lst": {
        "label": "LST (Suhu Permukaan °C)",
        "file": "diy_drought_indices_30m.tif",
        "band": "LST_C",
        "range": (22.0, 42.0),
        "stops": [(37, 99, 235), (250, 204, 21), (220, 38, 38)],
        "legend_labels": ("Sejuk (22 °C)", "Hangat (32 °C)", "Panas (42 °C)"),
    },
    "elevation": {
        "label": "Elevasi SRTM (mdpl)",
        "file": "diy_terrain_30m.tif",
        "band": "elevation",
        "range": (0.0, 1200.0),
        "stops": [(34, 197, 94), (250, 204, 21), (146, 64, 14)],
        "legend_labels": ("Dataran (0 m)", "Perbukitan (600 m)", "Tinggi (>1200 m)"),
    },
    "slope": {
        "label": "Kemiringan Lereng (°)",
        "file": "diy_terrain_30m.tif",
        "band": "slope",
        "range": (0.0, 35.0),
        "stops": [(34, 197, 94), (250, 204, 21), (220, 38, 38)],
        "legend_labels": ("Datar (0°)", "Miring (17°)", "Curam (>35°)"),
    },
    "landcover": {
        "label": "Tutupan Lahan (ESA WorldCover)",
        "file": "diy_landcover_30m.tif",
        "band": "landcover",
        "categorical": True,
    },
    "rainfall": {
        "label": "Curah Hujan Tahunan (CHIRPS)",
        "file": "diy_rainfall_30m.tif",
        "band": "rainfall_mm",
        "range": (1250.0, 2250.0),
        "stops": [(186, 230, 253), (59, 130, 246), (30, 58, 138)],
        "legend_labels": ("1250 mm", "1750 mm", "2250 mm"),
    },
}


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    """Create a PNG chunk with length, tag, data, and CRC32."""
    return (
        struct.pack("!I", len(data))
        + tag
        + data
        + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _write_rgba_png(rgba: np.ndarray, output_path: Path) -> None:
    """Write an (H, W, 4) uint8 array to an RGBA PNG file using stdlib zlib."""
    height, width, _ = rgba.shape
    raw_rows = np.hstack([
        np.zeros((height, 1), dtype=np.uint8),
        rgba.reshape(height, width * 4),
    ])
    compressed = zlib.compress(raw_rows.tobytes(), level=6)

    ihdr = struct.pack("!IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(png_bytes)


def _warp_to_web_mercator(
    arr: np.ndarray,
    profile: dict,
    resampling: Resampling,
    src_nodata: float,
    max_dim: int = 1400,
) -> tuple[np.ndarray, list[list[float]]]:
    """Reproject a 2D array to EPSG:3857 and compute WGS84 4-corner coordinates."""
    src_crs = profile["crs"]
    h, w = arr.shape
    left, bottom, right, top = (
        profile["transform"].c,
        profile["transform"].f + profile["transform"].e * h,
        profile["transform"].c + profile["transform"].a * w,
        profile["transform"].f,
    )

    dst_transform, dst_w, dst_h = calculate_default_transform(
        src_crs, WEB_CRS, w, h, left, bottom, right, top
    )
    scale = max(dst_w, dst_h) / float(max_dim)
    if scale > 1.0:
        dst_w = max(1, int(round(dst_w / scale)))
        dst_h = max(1, int(round(dst_h / scale)))
        dst_transform, dst_w, dst_h = calculate_default_transform(
            src_crs, WEB_CRS, w, h, left, bottom, right, top, dst_width=dst_w, dst_height=dst_h
        )

    warped = np.full((dst_h, dst_w), src_nodata, dtype=arr.dtype)
    reproject(
        source=arr,
        destination=warped,
        src_transform=profile["transform"],
        src_crs=src_crs,
        src_nodata=src_nodata,
        dst_transform=dst_transform,
        dst_crs=WEB_CRS,
        dst_nodata=src_nodata,
        resampling=resampling,
    )

    merc_left = dst_transform.c
    merc_top = dst_transform.f
    merc_right = dst_transform.c + dst_transform.a * dst_w
    merc_bottom = dst_transform.f + dst_transform.e * dst_h

    xs = [merc_left, merc_right, merc_right, merc_left]
    ys = [merc_top, merc_top, merc_bottom, merc_bottom]
    lons, lats = transform(WEB_CRS, "EPSG:4326", xs, ys)
    corners = [[float(lon), float(lat)] for lon, lat in zip(lons, lats)]
    return warped, corners


def _rgb_hex(rgba: tuple[int, int, int, int] | tuple[int, int, int]) -> str:
    return f"#{rgba[0]:02x}{rgba[1]:02x}{rgba[2]:02x}"


def _apply_discrete_palette(
    grid: np.ndarray, palette: dict[int, tuple[int, int, int, int]]
) -> np.ndarray:
    rgba = np.zeros((*grid.shape, 4), dtype=np.uint8)
    for cls_id, color in palette.items():
        rgba[grid == cls_id] = color
    return rgba


def _apply_ramp(
    grid: np.ndarray,
    vmin: float,
    vmax: float,
    stops: list[tuple[int, int, int]],
    alpha: int = 190,
) -> np.ndarray:
    rgba = np.zeros((*grid.shape, 4), dtype=np.uint8)
    valid = np.isfinite(grid)
    if not np.any(valid):
        return rgba

    t = np.clip((grid[valid] - vmin) / max(1e-9, vmax - vmin), 0.0, 1.0)
    c0, c1, c2 = [np.array(c, dtype=np.float32) for c in stops]

    colors = np.zeros((t.size, 3), dtype=np.float32)
    low_mask = t <= 0.5
    t_low = (t[low_mask] * 2.0)[:, None]
    t_high = ((t[~low_mask] - 0.5) * 2.0)[:, None]
    colors[low_mask] = c0 * (1.0 - t_low) + c1 * t_low
    colors[~low_mask] = c1 * (1.0 - t_high) + c2 * t_high

    rgba[valid, :3] = np.rint(colors).astype(np.uint8)
    rgba[valid, 3] = alpha
    return rgba


def export_simulation_overlay(result: SimulationResult) -> dict:
    """Render a SimulationResult risk grid to PNG and return MapLibre overlay config."""
    palette = DROUGHT_COLORS if result.scenario == "drought" else FLOOD_COLORS
    warped, corners = _warp_to_web_mercator(
        result.risk_grid,
        result.profile,
        resampling=Resampling.nearest,
        src_nodata=0,
    )
    rgba = _apply_discrete_palette(warped, palette)

    filename = f"{result.scenario}_overlay.png"
    out_path = OVERLAY_DIR / filename
    _write_rgba_png(rgba, out_path)

    legend_items = [
        {"label": RISK_LABELS[cls_id], "color": _rgb_hex(palette[cls_id])}
        for cls_id in (1, 2, 3, 4)
    ]

    return {
        "imageUrl": f"overlays/{filename}?v={int(time.time() * 1000)}",
        "coordinates": corners,
        "legend": {
            "title": f"Tingkat Risiko — {result.title}",
            "items": legend_items,
        },
    }


def export_raw_raster_overlay(layer_key: str) -> dict:
    """Render a raw raster band in data/raster/ to PNG for MapLibre inspection."""
    cfg = RAW_RASTER_LAYERS[layer_key]
    bands, profile = load_raster_bands(cfg["file"])
    arr = bands[cfg["band"]]

    if cfg.get("categorical"):
        warped, corners = _warp_to_web_mercator(
            np.where(np.isfinite(arr), np.rint(arr), 0).astype(np.int16),
            profile,
            resampling=Resampling.nearest,
            src_nodata=0,
        )
        palette = {code: info[1] for code, info in ESA_WORLDCOVER_PALETTE.items()}
        rgba = _apply_discrete_palette(warped, palette)
        present = set(np.unique(warped[warped > 0]).tolist())
        legend_items = [
            {"label": name, "color": _rgb_hex(color)}
            for code, (name, color) in ESA_WORLDCOVER_PALETTE.items()
            if code in present
        ]
    else:
        warped, corners = _warp_to_web_mercator(
            arr,
            profile,
            resampling=Resampling.bilinear,
            src_nodata=np.nan,
        )
        vmin, vmax = cfg["range"]
        rgba = _apply_ramp(warped, vmin, vmax, cfg["stops"])
        legend_items = [
            {"label": lbl, "color": _rgb_hex(color)}
            for lbl, color in zip(cfg["legend_labels"], cfg["stops"])
        ]

    filename = f"raster_{layer_key}.png"
    out_path = OVERLAY_DIR / filename
    _write_rgba_png(rgba, out_path)

    return {
        "imageUrl": f"overlays/{filename}?v={int(time.time() * 1000)}",
        "coordinates": corners,
        "legend": {
            "title": cfg["label"],
            "items": legend_items,
        },
    }
