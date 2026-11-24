from __future__ import annotations

from typing import Any
import numpy as np
from app.core.fitting import pseudo_voigt


def generate_xps_synthetic() -> dict[str, Any]:
    """Generate a synthetic C 1s XPS spectrum with charging shift, Shirley step, and 3 components."""
    rng = np.random.default_rng(42)
    be_true = np.linspace(293.0, 279.0, 281)  # descending 0.05 eV step

    peaks_spec = [
        {"label": "C-C/C-H", "center": 284.80, "fwhm": 1.15, "area": 5000.0, "eta": 0.25},
        {"label": "C-O", "center": 286.30, "fwhm": 1.25, "area": 2500.0, "eta": 0.25},
        {"label": "C=O", "center": 288.70, "fwhm": 1.35, "area": 1500.0, "eta": 0.25},
    ]

    net = np.zeros_like(be_true)
    for pk in peaks_spec:
        net += pseudo_voigt(be_true, area=pk["area"], center=pk["center"], fwhm=pk["fwhm"], eta=pk["eta"])

    # Exact Shirley step rising from low BE (150 cps) to high BE (420 cps)
    order_asc = np.argsort(be_true)
    dx = np.gradient(be_true[order_asc])
    cum = np.cumsum(net[order_asc] * dx)
    cum_norm = cum / (cum[-1] + 1e-12)
    bg = np.empty_like(net)
    bg[order_asc] = 150.0 + 270.0 * cum_norm

    spec = bg + net + rng.normal(0.0, 12.0, size=len(be_true))
    charge_shift_ev = 1.35
    be_raw = be_true - charge_shift_ev  # raw measured peak appears at 283.45 eV

    csv_text = "Binding Energy (eV),Intensity (cps)\n" + "\n".join(
        f"{b:.4f},{s:.3f}" for b, s in zip(be_raw, spec)
    )

    rsf_test_quant = {
        "elements": [
            {"name": "C 1s", "area": 9000.0, "rsf": 1.00},
            {"name": "O 1s", "area": 17580.0, "rsf": 2.93},
        ],
        "expected_pct": {"C 1s": 60.0, "O 1s": 40.0},
    }

    return {
        "files": [{"filename": "xps_C1s_shifted.csv", "content": csv_text.encode("utf-8")}],
        "ground_truth": {
            "charge_shift_ev": charge_shift_ev,
            "peaks_corrected": peaks_spec,
            "rsf_test_quant": rsf_test_quant,
        },
        "default_params": {
            "auto_charge_correct": True,
            "ref_be_ev": 284.8,
            "bg_method": "shirley",
            "n_peaks": 3,
            "rsf_entries": rsf_test_quant["elements"],
        },
    }
