from __future__ import annotations

from typing import Any
import numpy as np
from app.core.fitting import pseudo_voigt


def _make_xrd_pattern(
    two_theta: np.ndarray,
    peaks: list[float],
    areas: list[float],
    d_true_nm: float,
    k_factor: float,
    wavelength_angstrom: float,
    inst_fwhm_deg: float,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    lambda_nm = wavelength_angstrom / 10.0
    bg = 180.0 + 260.0 * np.exp(-0.06 * (two_theta - 15.0)) + 0.6 * two_theta
    y = bg.copy()
    for p2t, area in zip(peaks, areas):
        theta_rad = np.radians(p2t / 2.0)
        beta_size_rad = (k_factor * lambda_nm) / (d_true_nm * np.cos(theta_rad))
        beta_size_deg = float(np.degrees(beta_size_rad))
        beta_obs_deg = float(np.sqrt(beta_size_deg ** 2 + inst_fwhm_deg ** 2))
        y += pseudo_voigt(two_theta, area=area, center=p2t, fwhm=beta_obs_deg, eta=0.25)
    y += rng.normal(0.0, 6.0, size=len(two_theta))
    return np.maximum(y, 0.0)


def generate_xrd_synthetic() -> dict[str, Any]:
    """Generate synthetic powder XRD patterns with known 2theta peaks and Scherrer crystallite size."""
    two_theta = np.linspace(15.0, 70.0, 1101)
    peaks = [28.44, 47.30, 56.12]
    areas = [2200.0, 1450.0, 1050.0]
    k_factor = 0.89
    wavelength = 1.5406
    inst_fwhm = 0.08
    d_true = 22.0

    y1 = _make_xrd_pattern(two_theta, peaks, areas, d_true, k_factor, wavelength, inst_fwhm, seed=42)
    y2 = _make_xrd_pattern(two_theta, peaks, [a * 0.9 for a in areas], 12.0, k_factor, wavelength, inst_fwhm, seed=99)

    csv1 = "2Theta (deg),Intensity (counts)\n" + "\n".join(f"{t:.4f},{v:.3f}" for t, v in zip(two_theta, y1))
    csv2 = "2Theta (deg),Intensity (counts)\n" + "\n".join(f"{t:.4f},{v:.3f}" for t, v in zip(two_theta, y2))

    return {
        "files": [
            {"filename": "xrd_sample_22nm.csv", "content": csv1.encode("utf-8")},
            {"filename": "xrd_sample_12nm.csv", "content": csv2.encode("utf-8")},
        ],
        "ground_truth": {
            "peaks_2theta": peaks,
            "crystallite_size_nm": d_true,
            "k_factor": k_factor,
            "wavelength_angstrom": wavelength,
            "instrumental_fwhm_deg": inst_fwhm,
        },
        "default_params": {
            "smooth_enabled": True,
            "smooth_window": 11,
            "smooth_polyorder": 3,
            "baseline_method": "asls",
            "baseline_lam": 1e5,
            "baseline_p": 0.01,
            "display_mode": "overlay",
            "prominence_pct": 8.0,
            "min_distance_deg": 1.5,
            "wavelength_angstrom": wavelength,
            "k_factor": k_factor,
            "instrumental_fwhm_deg": inst_fwhm,
            "instrumental_method": "gaussian",
        },
    }
