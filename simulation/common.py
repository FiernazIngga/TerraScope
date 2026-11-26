"""Shared scoring, classification, and result structures for disaster simulations."""

from dataclasses import dataclass
import numpy as np

from utils.raster_io import compute_zonal_stats

RISK_LABELS = {
    1: "Rendah",
    2: "Sedang",
    3: "Tinggi",
    4: "Sangat Tinggi",
}


@dataclass
class SimulationResult:
    """Container for simulation hazard grids, metadata, and zonal area statistics."""

    scenario: str
    title: str
    risk_grid: np.ndarray
    score_grid: np.ndarray
    profile: dict
    params: dict
    stats: dict


def weighted_composite(
    indicators: list[tuple[np.ndarray, float]],
    domain_mask: np.ndarray,
) -> np.ndarray:
    """Compute per-pixel weighted average over valid indicators inside domain_mask."""
    first = indicators[0][0]
    acc = np.zeros_like(first, dtype=np.float32)
    weight_sum = np.zeros_like(first, dtype=np.float32)

    for arr, weight in indicators:
        valid = domain_mask & np.isfinite(arr)
        acc[valid] += arr[valid] * np.float32(weight)
        weight_sum[valid] += np.float32(weight)

    score = np.full_like(first, np.nan, dtype=np.float32)
    has_data = domain_mask & (weight_sum > 0)
    score[has_data] = np.clip(acc[has_data] / weight_sum[has_data], 0.0, 1.0)
    return score


def classify_risk(
    score_grid: np.ndarray,
    thresholds: tuple[float, float, float] = (0.32, 0.50, 0.68),
) -> np.ndarray:
    """Classify continuous [0, 1] hazard score into uint8 levels 1..4 (0 = NoData)."""
    risk = np.zeros(score_grid.shape, dtype=np.uint8)
    valid = np.isfinite(score_grid)
    t1, t2, t3 = thresholds

    risk[valid & (score_grid < t1)] = 1
    risk[valid & (score_grid >= t1) & (score_grid < t2)] = 2
    risk[valid & (score_grid >= t2) & (score_grid < t3)] = 3
    risk[valid & (score_grid >= t3)] = 4
    return risk


def build_result(
    scenario: str,
    title: str,
    score_grid: np.ndarray,
    profile: dict,
    params: dict,
    thresholds: tuple[float, float, float] = (0.32, 0.50, 0.68),
) -> SimulationResult:
    """Classify hazard scores and compute per-region area statistics."""
    risk_grid = classify_risk(score_grid, thresholds=thresholds)
    stats = compute_zonal_stats(risk_grid, profile, RISK_LABELS)
    return SimulationResult(
        scenario=scenario,
        title=title,
        risk_grid=risk_grid,
        score_grid=score_grid,
        profile=profile,
        params=params,
        stats=stats,
    )
