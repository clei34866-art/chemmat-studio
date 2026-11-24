from __future__ import annotations

from typing import Any
import numpy as np
from app.core.fitting import pseudo_voigt


def generate_spectroscopy_synthetic(sub_type: str = "uvvis") -> dict[str, Any]:
    """Generate synthetic UV-Vis (direct band gap Eg=3.20 eV), Raman, or FTIR datasets."""
    rng = np.random.default_rng(42)
    st = sub_type.lower()

    if st == "uvvis":
        lam = np.linspace(250.0, 700.0, 451)
        hv = 1239.84198 / lam
        eg_true = 3.20
        path_cm = 1.0

        # Direct allowed transition: (alpha * hv)^2 = C^2 * (hv - Eg) for hv > Eg
        c_const = 2.8
        alpha_hv = np.where(
            hv > eg_true,
            c_const * np.sqrt(np.maximum(hv - eg_true, 0.0)),
            0.03 * np.exp((hv - eg_true) / 0.09),
        )
        # Smooth tiny knee around Eg slightly while preserving linear segment above 3.32 eV
        alpha = alpha_hv / hv
        absorbance = alpha * path_cm / 2.302585 + rng.normal(0.0, 0.0015, len(lam))
        absorbance = np.maximum(absorbance, 0.0)
        csv = "Wavelength (nm),Absorbance (a.u.)\n" + "\n".join(
            f"{l:.2f},{a:.6f}" for l, a in zip(lam, absorbance)
        )
        return {
            "files": [{"filename": "uvvis_semiconductor_3p20eV.csv", "content": csv.encode("utf-8")}],
            "ground_truth": {"band_gap_ev": eg_true, "tauc_gamma": 0.5},
            "default_params": {
                "sub_type": "uvvis",
                "enable_tauc": True,
                "tauc_gamma": 0.5,
                "path_length_cm": path_cm,
                "kubelka_munk": False,
            },
        }

    if st == "raman":
        wn = np.linspace(200.0, 2000.0, 901)
        peaks = [520.5, 1350.0, 1582.0]
        bg = 420.0 + 0.35 * wn - 0.00012 * (wn - 800.0) ** 2
        y = bg.copy()
        for pk, area, w in zip(peaks, [38000.0, 52000.0, 64000.0], [16.0, 32.0, 26.0]):
            y += pseudo_voigt(wn, area=area, center=pk, fwhm=w, eta=0.3)
        y += rng.normal(0.0, 8.0, len(wn))
        csv = "Raman Shift (cm^-1),Intensity (counts)\n" + "\n".join(
            f"{x:.2f},{v:.3f}" for x, v in zip(wn, y)
        )
        return {
            "files": [{"filename": "raman_carbon_si.csv", "content": csv.encode("utf-8")}],
            "ground_truth": {"peaks_cm1": peaks},
            "default_params": {
                "sub_type": "raman",
                "baseline_method": "asls",
                "baseline_lam": 1e5,
                "baseline_p": 0.01,
                "prominence_pct": 8.0,
            },
        }

    if st == "ftir":
        wn = np.linspace(4000.0, 400.0, 901)
        peaks = [3420.0, 2925.0, 1715.0, 1105.0]
        abs_sig = 0.04 + 0.000015 * (4000.0 - wn)
        for pk, area, w in zip(peaks, [45.0, 22.0, 32.0, 28.0], [95.0, 40.0, 34.0, 45.0]):
            abs_sig += pseudo_voigt(wn, area=area, center=pk, fwhm=w, eta=0.25)
        transmittance = 100.0 * (10.0 ** (-abs_sig)) + rng.normal(0.0, 0.15, len(wn))
        transmittance = np.clip(transmittance, 1.0, 100.0)
        csv = "Wavenumber (cm^-1),Transmittance (%T)\n" + "\n".join(
            f"{x:.2f},{t:.4f}" for x, t in zip(wn, transmittance)
        )
        return {
            "files": [{"filename": "ftir_polymer.csv", "content": csv.encode("utf-8")}],
            "ground_truth": {"peaks_cm1": peaks},
            "default_params": {
                "sub_type": "ftir",
                "ftir_mode": "absorbance",
                "baseline_method": "asls",
                "prominence_pct": 8.0,
            },
        }

    raise ValueError(f"Unsupported spectroscopy synthetic sub_type: {sub_type}")
