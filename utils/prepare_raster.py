"""Clip, align, and validate raw GeoTIFF rasters against the DIY boundary."""

from pathlib import Path
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.warp import Resampling, reproject

BASE_DIR = Path(__file__).resolve().parent.parent
BOUNDARY_FILE = BASE_DIR / "data" / "boundaries" / "diy_kabupaten_kota.geojson"
RAW_DIR = BASE_DIR / "data" / "raw"
RASTER_DIR = BASE_DIR / "data" / "raster"

TARGET_CRS = "EPSG:32749"
NODATA_VALUE = -9999.0


def _load_boundary_geometries():
    """Load DIY kabupaten/kota geometries reprojected to TARGET_CRS."""
    if not BOUNDARY_FILE.exists():
        raise FileNotFoundError(f"File batas wilayah tidak ditemukan: {BOUNDARY_FILE}")

    gdf = gpd.read_file(BOUNDARY_FILE)
    if gdf.crs is None:
        raise ValueError("Data batas wilayah tidak memiliki CRS.")

    return gdf.to_crs(TARGET_CRS).geometry.values


def _normalize_array(data: np.ndarray, src_nodata) -> np.ndarray:
    """Convert NaN and source nodata values to unified float32 NODATA_VALUE."""
    out = data.astype(np.float32, copy=True)
    invalid = ~np.isfinite(out)
    if src_nodata is not None and not np.isnan(src_nodata):
        invalid |= out == np.float32(src_nodata)
    out[invalid] = np.float32(NODATA_VALUE)
    return out


def _align_to_reference(
    data: np.ndarray,
    src_transform,
    src_crs,
    ref_profile: dict,
    resampling: Resampling,
) -> np.ndarray:
    """Reproject/resample a multi-band array to match ref_profile grid."""
    aligned = np.full(
        (data.shape[0], ref_profile["height"], ref_profile["width"]),
        np.float32(NODATA_VALUE),
        dtype=np.float32,
    )
    for idx in range(data.shape[0]):
        reproject(
            source=data[idx],
            destination=aligned[idx],
            src_transform=src_transform,
            src_crs=src_crs,
            src_nodata=NODATA_VALUE,
            dst_transform=ref_profile["transform"],
            dst_crs=ref_profile["crs"],
            dst_nodata=NODATA_VALUE,
            resampling=resampling,
        )
    return aligned


def prepare_rasters():
    """Clip raw GeoTIFF files to DIY boundaries and align their pixel grids."""
    raw_files = sorted(RAW_DIR.glob("*.tif"))
    if not raw_files:
        raise FileNotFoundError(f"Tidak ada file .tif ditemukan di {RAW_DIR}")

    geometries = _load_boundary_geometries()
    RASTER_DIR.mkdir(parents=True, exist_ok=True)

    ref_profile = None

    for raw_path in raw_files:
        out_path = RASTER_DIR / raw_path.name
        is_categorical = "landcover" in raw_path.stem.lower()
        resampling = Resampling.nearest if is_categorical else Resampling.bilinear

        with rasterio.open(raw_path) as src:
            if src.crs is None:
                raise ValueError(f"Raster tidak memiliki CRS: {raw_path.name}")

            # Clip to DIY boundary in source CRS (reproject geometry if needed)
            clip_geoms = geometries
            if str(src.crs) != TARGET_CRS:
                clip_geoms = (
                    gpd.GeoSeries(geometries, crs=TARGET_CRS)
                    .to_crs(src.crs)
                    .values
                )

            clipped, clip_transform = mask(
                src,
                clip_geoms,
                crop=True,
                filled=True,
                nodata=np.nan,
            )
            normalized = _normalize_array(clipped, src.nodata)
            descriptions = src.descriptions
            src_crs = src.crs

        if ref_profile is None and str(src_crs) == TARGET_CRS:
            ref_profile = {
                "driver": "GTiff",
                "dtype": "float32",
                "crs": TARGET_CRS,
                "transform": clip_transform,
                "width": normalized.shape[2],
                "height": normalized.shape[1],
                "nodata": NODATA_VALUE,
                "compress": "lzw",
                "tiled": True,
            }
            output_data = normalized
        else:
            if ref_profile is None:
                raise RuntimeError(
                    f"Raster pertama ({raw_path.name}) harus ber-CRS {TARGET_CRS}."
                )

            same_grid = (
                str(src_crs) == TARGET_CRS
                and normalized.shape[1] == ref_profile["height"]
                and normalized.shape[2] == ref_profile["width"]
                and clip_transform == ref_profile["transform"]
            )
            if same_grid:
                output_data = normalized
            else:
                output_data = _align_to_reference(
                    normalized,
                    clip_transform,
                    src_crs,
                    ref_profile,
                    resampling,
                )

        profile = {**ref_profile, "count": output_data.shape[0]}
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(output_data)
            for band_idx, desc in enumerate(descriptions, start=1):
                if desc:
                    dst.set_band_description(band_idx, desc)

        print(f"[OK] {out_path.name} -> shape={output_data.shape}, crs={TARGET_CRS}")
        for band_idx, desc in enumerate(descriptions, start=1):
            band = output_data[band_idx - 1]
            valid = band[band != NODATA_VALUE]
            label = desc or f"band_{band_idx}"
            print(
                f"     - {label}: valid={valid.size:,} px, "
                f"min={valid.min():.2f}, max={valid.max():.2f}"
            )


if __name__ == "__main__":
    prepare_rasters()
