"""Drought scenario simulation using NDVI, NDMI, LST, and rainfall deficit."""

import numpy as np

from simulation.common import SimulationResult, build_result, weighted_composite
from utils.raster_io import load_raster_bands, min_max_normalize


def run_drought_simulation(
    rainfall_reduction_pct: float = 20.0,
    temp_increase_c: float = 1.5,
) -> SimulationResult:
    """Estimate drought hazard levels across DIY under rainfall/temperature stress."""
    drought_bands, profile = load_raster_bands("diy_drought_indices_30m.tif")
    rain_bands, _ = load_raster_bands("diy_rainfall_30m.tif")

    ndvi = drought_bands["NDVI"]
    ndmi = drought_bands["NDMI"]
    lst_c = drought_bands["LST_C"] + np.float32(temp_increase_c)
    effective_rain = rain_bands["rainfall_mm"] * np.float32(
        max(0.0, 1.0 - rainfall_reduction_pct / 100.0)
    )

    # Use NDMI (100% valid across DIY polygon) + any valid indicator as domain mask
    domain_mask = (
        np.isfinite(ndmi)
        | np.isfinite(ndvi)
        | np.isfinite(lst_c)
        | np.isfinite(effective_rain)
    )

    veg_stress = min_max_normalize(ndvi, low=0.05, high=0.78, invert=True)
    moisture_deficit = min_max_normalize(ndmi, low=-0.25, high=0.45, invert=True)
    thermal_stress = min_max_normalize(lst_c, low=23.0, high=44.0, invert=False)
    rain_deficit = min_max_normalize(effective_rain, low=800.0, high=2300.0, invert=True)

    score = weighted_composite(
        indicators=[
            (veg_stress, 0.30),
            (moisture_deficit, 0.30),
            (thermal_stress, 0.25),
            (rain_deficit, 0.15),
        ],
        domain_mask=domain_mask,
    )

    return build_result(
        scenario="drought",
        title="Simulasi Kekeringan",
        score_grid=score,
        profile=profile,
        params={
            "rainfall_reduction_pct": rainfall_reduction_pct,
            "temp_increase_c": temp_increase_c,
        },
        thresholds=(0.35, 0.50, 0.65),
    )
