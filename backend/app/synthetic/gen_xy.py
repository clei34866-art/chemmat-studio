from __future__ import annotations

from typing import Any
import numpy as np


def generate_xy_synthetic() -> dict[str, Any]:
    """Generate deterministic linear calibration & control CSV datasets with known truth."""
    rng = np.random.default_rng(42)
    x = np.linspace(0.0, 10.0, 80)

    slope_true = 2.45
    intercept_true = -1.20
    noise_std = 0.04
    y1 = slope_true * x + intercept_true + rng.normal(0.0, noise_std, size=len(x))

    y2 = 1.85 * x + 0.50 + rng.normal(0.0, 0.05, size=len(x))

    csv1 = "Concentration (mmol/L),Response Signal (a.u.)\n" + "\n".join(
        f"{xv:.6f},{yv:.6f}" for xv, yv in zip(x, y1)
    )
    csv2 = "Concentration (mmol/L),Control Signal (a.u.)\n" + "\n".join(
        f"{xv:.6f},{yv:.6f}" for xv, yv in zip(x, y2)
    )

    return {
        "files": [
            {"filename": "xy_calibration.csv", "content": csv1.encode("utf-8")},
            {"filename": "xy_control.csv", "content": csv2.encode("utf-8")},
        ],
        "ground_truth": {
            "slope": slope_true,
            "intercept": intercept_true,
            "noise_std": noise_std,
        },
        "default_params": {
            "x_col": 0,
            "y_col": 1,
            "normalize": "none",
            "y_offset_step": 0.0,
            "enable_linear_fit": True,
            "fit_series_index": 0,
        },
    }
