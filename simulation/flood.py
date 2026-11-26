"""Flood hazard scenario simulation using elevation, slope, land cover, and rainfall."""

import numpy as np

from simulation.common import SimulationResult, build_result, weighted_composite
from utils.raster_io import load_raster_bands, min_max_normalize

# ESA WorldCover v200 class -> baseline surface runoff susceptibility [0, 1]
LANDCOVER_RUNOFF = {
    10: 0.20,  # Tree cover
    20: 0.35,  # Shrubland
    30: 0.45,  # Grassland
    40: 0.60,  # Cropland
    50: 0.90,  # Built-up
    60: 0.75,  # Bare / sparse vegetation
    70: 0.50,  # Snow and ice (fallback)
    80: 0.95,  # Permanent water bodies
    90: 0.95,  # Herbaceous wetland
    95: 0.80,  # Mangroves
    100: 0.40,  # Moss and lichen
}


def _map_landcover_runoff(landcover: np.ndarray, sensitivity: float) -> np.ndarray:
    """Map ESA WorldCover codes to runoff factor scaled by sensitivity."""
    valid = np.isfinite(landcover)
    runoff = np.full(landcover.shape, np.nan, dtype=np.float32)
    codes = np.zeros(landcover.shape, dtype=np.int32)
    codes[valid] = np.rint(landcover[valid]).astype(np.int32)

    mapped = np.full(landcover.shape, 0.50, dtype=np.float32)
    for code, factor in LANDCOVER_RUNOFF.items():
        mapped[codes == code] = factor

    runoff[valid] = np.clip(mapped[valid] * np.float32(sensitivity), 0.0, 1.0)
    return runoff


def run_flood_simulation(
    rainfall_increase_pct: float = 30.0,
    runoff_sensitivity: float = 1.0,
) -> SimulationResult:
    """Estimate flood susceptibility across DIY under elevated rainfall scenarios."""
    terrain_bands, profile = load_raster_bands("diy_terrain_30m.tif")
    lc_bands, _ = load_raster_bands("diy_landcover_30m.tif")
    rain_bands, _ = load_raster_bands("diy_rainfall_30m.tif")

    elevation = terrain_bands["elevation"]
    slope = terrain_bands["slope"]
    landcover = lc_bands["landcover"]
    effective_rain = rain_bands["rainfall_mm"] * np.float32(
        1.0 + max(0.0, rainfall_increase_pct) / 100.0
    )

    domain_mask = np.isfinite(elevation) & np.isfinite(slope)

    low_elev_risk = min_max_normalize(elevation, low=0.0, high=450.0, invert=True)
    flat_slope_risk = min_max_normalize(slope, low=0.0, high=18.0, invert=True)
    lc_runoff = _map_landcover_runoff(landcover, runoff_sensitivity)
    rain_risk = min_max_normalize(effective_rain, low=1200.0, high=3500.0, invert=False)

    score = weighted_composite(
        indicators=[
            (low_elev_risk, 0.35),
            (flat_slope_risk, 0.25),
            (lc_runoff, 0.20),
            (rain_risk, 0.20),
        ],
        domain_mask=domain_mask,
    )

    return build_result(
        scenario="flood",
        title="Simulasi Banjir",
        score_grid=score,
        profile=profile,
        params={
            "rainfall_increase_pct": rainfall_increase_pct,
            "runoff_sensitivity": runoff_sensitivity,
        },
        thresholds=(0.35, 0.52, 0.68),
    )
