from __future__ import annotations

from typing import Any
import numpy as np


def generate_electrochem_synthetic(sub_type: str = "eis") -> dict[str, Any]:
    """Generate deterministic CV, GCD, EIS (R(Q(RW))), or Cycling datasets with ground truth."""
    rng = np.random.default_rng(42)
    st = sub_type.lower()

    if st == "eis":
        freq = np.logspace(5, -1.3, 65)
        w = 2.0 * np.pi * freq
        rs, q, n, rct, aw = 4.5, 2.2e-4, 0.88, 32.0, 18.0
        zw = aw * (1.0 - 1j) / np.sqrt(w)
        z_faradaic = rct + zw
        zq_inv = q * ((1j * w) ** n)
        z = rs + 1.0 / (zq_inv + 1.0 / z_faradaic)
        z_re = np.real(z) * (1.0 + rng.normal(0.0, 0.004, len(freq)))
        z_neg_im = -np.imag(z) * (1.0 + rng.normal(0.0, 0.004, len(freq)))
        csv = "Freq (Hz),Z' (Ohm),-Z'' (Ohm)\n" + "\n".join(
            f"{f:.6g},{r:.6f},{ni:.6f}" for f, r, ni in zip(freq, z_re, z_neg_im)
        )
        return {
            "files": [{"filename": "eis_nyquist_randles.csv", "content": csv.encode("utf-8")}],
            "ground_truth": {"Rs": rs, "Q": q, "n": n, "Rct": rct, "Aw": aw},
            "default_params": {"sub_type": "eis", "circuit_model": "R(Q(RW))"},
        }

    if st == "cv":
        v_fwd = np.linspace(-0.2, 0.8, 200)
        v_rev = np.linspace(0.8, -0.2, 200)[1:]
        i_fwd = 0.45 + 0.35 * v_fwd + 3.2 * np.exp(-0.5 * ((v_fwd - 0.32) / 0.045) ** 2)
        i_rev = -0.45 - 0.25 * v_rev - 2.9 * np.exp(-0.5 * ((v_rev - 0.22) / 0.045) ** 2)
        v = np.concatenate([v_fwd, v_rev])
        i_ma = np.concatenate([i_fwd, i_rev]) + rng.normal(0.0, 0.02, len(v))
        csv = "Potential (V),Current (mA)\n" + "\n".join(f"{pv:.5f},{iv:.5f}" for pv, iv in zip(v, i_ma))
        return {
            "files": [{"filename": "cv_redox_50mVs.csv", "content": csv.encode("utf-8")}],
            "ground_truth": {"E_pa_V": 0.32, "E_pc_V": 0.22},
            "default_params": {"sub_type": "cv", "active_mass_mg": 1.0, "scan_rate_mv_s": 50.0},
        }

    if st == "gcd":
        # 1.0 mg, 1.0 mA, dV = 1.0 V, dt_discharge = 250.0 s => exact Cs = 250.0 F/g
        t_chg = np.linspace(0.0, 250.0, 126)
        v_chg = np.linspace(0.0, 1.0, 126)
        t_dis = np.linspace(250.0, 500.0, 126)[1:]
        v_dis = np.linspace(1.0, 0.0, 126)[1:]
        t = np.concatenate([t_chg, t_dis])
        v = np.concatenate([v_chg, v_dis]) + rng.normal(0.0, 0.001, len(t))
        csv = "Time (s),Potential (V)\n" + "\n".join(f"{tv:.4f},{vv:.5f}" for tv, vv in zip(t, v))
        return {
            "files": [{"filename": "gcd_1Ag.csv", "content": csv.encode("utf-8")}],
            "ground_truth": {"specific_capacitance_F_g": 250.0, "coulombic_efficiency_pct": 100.0},
            "default_params": {"sub_type": "gcd", "active_mass_mg": 1.0, "current_ma": 1.0},
        }

    if st == "cycling":
        cycles = np.arange(1, 101)
        cap = np.linspace(180.0, 162.0, 100) + rng.normal(0.0, 0.05, 100)
        cap[0] = 180.0
        cap[-1] = 162.0
        ce = np.full(100, 99.6)
        ce[0] = 92.5
        csv = "Cycle,Specific Capacity (mAh/g),Coulombic Efficiency (%)\n" + "\n".join(
            f"{c},{q:.4f},{e:.3f}" for c, q, e in zip(cycles, cap, ce)
        )
        return {
            "files": [{"filename": "long_cycling_100c.csv", "content": csv.encode("utf-8")}],
            "ground_truth": {"capacity_retention_pct": 90.0, "first_cycle_ce_pct": 92.5},
            "default_params": {"sub_type": "cycling"},
        }

    raise ValueError(f"Unsupported electrochem synthetic sub_type: {sub_type}")
