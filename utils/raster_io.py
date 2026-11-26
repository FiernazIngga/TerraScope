"""Raster loading, normalization, and zonal statistics helpers."""

from pathlib import Path
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize

BASE_DIR = Path(__file__).resolve().parent.parent
RASTER_DIR = BASE_DIR / "data" / "raster"
BOUNDARY_FILE = BASE_DIR / "data" / "boundaries" / "diy_kabupaten_kota.geojson"

_REGION_MASK_CACHE = {}


def load_raster_bands(filename: str) -> tuple[dict[str, np.ndarray], dict]:
    """Load all bands of a GeoTIFF in data/raster as float32 arrays with NaN nodata."""
    path = RASTER_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"File raster tidak ditemukan: {path}. "
            "Jalankan utils/prepare_raster.py terlebih dahulu."
        )

    with rasterio.open(path) as src:
        profile = src.profile.copy()
        nodata = src.nodata
        bands = {}
        for idx in range(1, src.count + 1):
            name = src.descriptions[idx - 1] or f"band_{idx}"
            arr = src.read(idx).astype(np.float32)
            invalid = ~np.isfinite(arr)
            if nodata is not None and not np.isnan(nodata):
                invalid |= arr == np.float32(nodata)
            arr[invalid] = np.nan
            bands[name] = arr

    return bands, profile


def min_max_normalize(
    arr: np.ndarray,
    low: float | None = None,
    high: float | None = None,
    invert: bool = False,
) -> np.ndarray:
    """Normalize array to [0, 1], preserving NaNs and optionally inverting."""
    valid = np.isfinite(arr)
    if not np.any(valid):
        return np.full_like(arr, np.nan, dtype=np.float32)

    lo = float(np.nanpercentile(arr, 2)) if low is None else float(low)
    hi = float(np.nanpercentile(arr, 98)) if high is None else float(high)
    span = hi - lo
    if span <= 1e-9:
        out = np.zeros_like(arr, dtype=np.float32)
        out[~valid] = np.nan
        return out

    norm = np.clip((arr - lo) / span, 0.0, 1.0).astype(np.float32)
    if invert:
        norm = 1.0 - norm
    norm[~valid] = np.nan
    return norm


def _get_region_masks(profile: dict) -> tuple[np.ndarray, dict[int, str]]:
    """Rasterize DIY kabupaten/kota polygons aligned to profile, cached by grid."""
    key = (
        str(profile["crs"]),
        int(profile["height"]),
        int(profile["width"]),
        tuple(profile["transform"])[:6],
    )
    if key in _REGION_MASK_CACHE:
        return _REGION_MASK_CACHE[key]

    gdf = gpd.read_file(BOUNDARY_FILE).to_crs(profile["crs"])
    gdf = gdf.sort_values("WADMKK").reset_index(drop=True)

    id_to_name = {idx + 1: str(row["WADMKK"]) for idx, row in gdf.iterrows()}
    shapes = [(geom, idx + 1) for idx, geom in enumerate(gdf.geometry)]

    region_grid = rasterize(
        shapes=shapes,
        out_shape=(profile["height"], profile["width"]),
        transform=profile["transform"],
        fill=0,
        dtype=np.uint8,
    )
    _REGION_MASK_CACHE[key] = (region_grid, id_to_name)
    return region_grid, id_to_name


def compute_zonal_stats(
    risk_grid: np.ndarray,
    profile: dict,
    class_labels: dict[int, str],
) -> dict:
    """Compute area (km^2 and %) per risk class across DIY and each kabupaten/kota."""
    pixel_area_km2 = abs(profile["transform"].a * profile["transform"].e) / 1_000_000.0
    region_grid, id_to_name = _get_region_masks(profile)

    def summarize(mask_bool: np.ndarray) -> dict:
        vals = risk_grid[mask_bool & (risk_grid > 0)]
        total_px = int(vals.size)
        total_km2 = round(total_px * pixel_area_km2, 2)
        classes = {}
        for cls_id, label in class_labels.items():
            cnt = int(np.sum(vals == cls_id))
            area = round(cnt * pixel_area_km2, 2)
            pct = round((cnt / total_px * 100.0) if total_px > 0 else 0.0, 1)
            classes[cls_id] = {"label": label, "area_km2": area, "pct": pct}
        return {"total_km2": total_km2, "classes": classes}

    overall = summarize(region_grid > 0)
    by_region = {}
    for reg_id, reg_name in id_to_name.items():
        by_region[reg_name] = summarize(region_grid == reg_id)

    return {"overall": overall, "by_region": by_region}
