from __future__ import annotations

from typing import Any
import numpy as np
from scipy.optimize import least_squares
from scipy.signal import find_peaks, savgol_filter

from app.core.baseline import compute_baseline
from app.core.fitting import nlls_fit_with_errors, pseudo_voigt
from app.core.parser import parse_tabular_bytes
from app.schemas.models import (
    FitParameter,
    FitReport,
    ModuleProcessResponse,
    PlotAnnotation,
    ProvenanceStep,
    ResidualData,
    SeriesData,
)


def _auto_seed_peaks(x_asc: np.ndarray, y_net: np.ndarray, n_peaks: int) -> list[tuple[float, float, float]]:
    """Greedy residual peak seeding that reliably resolves overlapping shoulder peaks without hardcoded BE values."""
    y_pos = np.maximum(y_net, 0.0)
    span = float(np.max(y_pos)) or 1.0
    dx = float(np.median(np.diff(x_asc))) if len(x_asc) > 1 else 0.05
    min_dist = max(2, int(round(0.65 / max(dx, 1e-6))))

    y_sm = savgol_filter(y_pos, min(7, len(y_pos) if len(y_pos) % 2 == 1 else len(y_pos) - 1), 2) if len(y_pos) >= 7 else y_pos
    pk_idx, _ = find_peaks(y_sm, prominence=0.04 * span, distance=min_dist)
    if len(pk_idx) == 0:
        pk_idx = np.asarray([int(np.argmax(y_sm))], dtype=int)

    # Sort strongest first, keep up to n_peaks
    pk_idx = pk_idx[np.argsort(y_sm[pk_idx])[::-1][:n_peaks]]
    seeds: list[tuple[float, float, float]] = []
    for idx in pk_idx:
        c = float(x_asc[idx])
        h = max(float(y_pos[idx]), 1.0)
        w = 1.2
        seeds.append((h * w * 1.15, c, w))

    # Iteratively fit current seeds and pick strongest residual shoulder until len(seeds) == n_peaks
    while len(seeds) < n_peaks:
        k = len(seeds)
        p0: list[float] = []
        lb: list[float] = []
        ub: list[float] = []
        for a0, c0, w0 in seeds:
            p0.extend([a0, c0, w0])
            lb.extend([1.0, float(x_asc[0]) + 0.3, 0.45])
            ub.extend([span * 25.0, float(x_asc[-1]) - 0.3, 3.2])

        def _partial(xv: np.ndarray, params: np.ndarray) -> np.ndarray:
            acc = np.zeros_like(xv)
            for j in range(k):
                acc += pseudo_voigt(xv, params[3 * j], params[3 * j + 1], params[3 * j + 2], 0.25)
            return acc - y_net

        res = least_squares(lambda pr: _partial(x_asc, pr), p0, bounds=(lb, ub), max_nfev=600)
        resid = -_partial(x_asc, res.x)
        resid_sm = savgol_filter(resid, min(9, len(resid) if len(resid) % 2 == 1 else len(resid) - 1), 2) if len(resid) >= 9 else resid

        existing_centers = [res.x[3 * j + 1] for j in range(k)]
        # Mask regions too close to already fitted centers
        cand = resid_sm.copy()
        for ec in existing_centers:
            cand[np.abs(x_asc - ec) < 0.7] = -np.inf
        best_i = int(np.argmax(cand))
        if not np.isfinite(cand[best_i]):
            cand = resid_sm.copy()
            for ec in existing_centers:
                cand[np.abs(x_asc - ec) < 0.35] = -np.inf
            best_i = int(np.argmax(cand))
        new_c = float(x_asc[best_i])
        new_h = max(float(resid_sm[best_i]), 0.05 * span)
        seeds = [(res.x[3 * j], res.x[3 * j + 1], res.x[3 * j + 2]) for j in range(k)]
        seeds.append((new_h * 1.2 * 1.15, new_c, 1.2))

    seeds.sort(key=lambda t: t[1])
    return seeds


def process_xps(
    files: list[tuple[str, bytes]],
    *,
    auto_charge_correct: bool = True,
    ref_be_ev: float = 284.8,
    manual_shift_ev: float = 0.0,
    charge_search_min: float = 280.0,
    charge_search_max: float = 290.0,
    bg_method: str = "shirley",
    bg_emin: float | None = None,
    bg_emax: float | None = None,
    shirley_tol: float = 1e-6,
    shirley_max_iter: int = 50,
    n_peaks: int = 3,
    peak_specs: list[dict[str, Any]] | None = None,
    fwhm_min: float = 0.4,
    fwhm_max: float = 3.5,
    eta_fixed: float | None = None,
    rsf_entries: list[dict[str, Any]] | None = None,
    skip_rows: int | None = None,
    ground_truth: dict[str, Any] | None = None,
) -> ModuleProcessResponse:
    """Process XPS narrow scan: charge calibration, Shirley background, Pseudo-Voigt deconvolution, and editable RSF %."""
    if not files:
        raise ValueError("No files supplied to XPS module.")

    pt = parse_tabular_bytes(files[0][0], files[0][1], skip_rows=skip_rows)
    be_raw = pt.data[:, 0]
    y_raw = pt.data[:, 1]

    # Sort ascending internally for clean numerical integration and peak fitting
    order = np.argsort(be_raw)
    be_raw = be_raw[order]
    y_raw = y_raw[order]

    if auto_charge_correct:
        win = (be_raw >= float(charge_search_min)) & (be_raw <= float(charge_search_max))
        if np.any(win):
            sub_x = be_raw[win]
            sub_y = y_raw[win]
        else:
            sub_x = be_raw
            sub_y = y_raw
        apparent_peak = float(sub_x[int(np.argmax(sub_y))])
        charge_shift = float(ref_be_ev) - apparent_peak
    else:
        charge_shift = float(manual_shift_ev)

    be = be_raw + charge_shift

    # Optional energy ROI window for background & fitting
    mask = np.ones(len(be), dtype=bool)
    if bg_emin is not None:
        mask &= be >= float(bg_emin)
    if bg_emax is not None:
        mask &= be <= float(bg_emax)
    be_roi = be[mask]
    y_roi = y_raw[mask]
    if len(be_roi) < 10:
        be_roi, y_roi = be, y_raw

    bg = compute_baseline(
        be_roi,
        y_roi,
        method=bg_method if bg_method.lower() in {"shirley", "poly", "asls", "rubberband", "none"} else "shirley",
        shirley_tol=shirley_tol,
        shirley_max_iter=shirley_max_iter,
    )
    y_net = y_roi - bg

    if peak_specs and len(peak_specs) > 0:
        n_pk = len(peak_specs)
        seeds: list[tuple[float, float, float, float]] = []
        y_max_net = max(float(np.max(y_net)), 10.0)
        for spec in peak_specs:
            c0 = float(spec.get("center", np.mean(be_roi)))
            w0 = float(spec.get("fwhm", 1.2))
            idx_c = int(np.argmin(np.abs(be_roi - c0)))
            a0 = float(spec.get("area", max(float(y_net[idx_c]), 0.2 * y_max_net) * w0 * 1.1))
            e0 = float(spec.get("eta", 0.25 if eta_fixed is None else eta_fixed))
            seeds.append((a0, c0, w0, e0))
    else:
        n_pk = max(1, int(n_peaks))
        auto_s = _auto_seed_peaks(be_roi, y_net, n_pk)
        seeds = [(a0, c0, w0, 0.25 if eta_fixed is None else float(eta_fixed)) for a0, c0, w0 in auto_s]

    p0: list[float] = []
    lb: list[float] = []
    ub: list[float] = []
    y_span = max(float(np.max(y_net) - np.min(y_net)), 10.0)
    e_lo = float(be_roi[0])
    e_hi = float(be_roi[-1])

    for a0, c0, w0, e0 in seeds:
        c_clamped = float(np.clip(c0, e_lo + 0.1, e_hi - 0.1))
        w_clamped = float(np.clip(w0, fwhm_min, fwhm_max))
        if eta_fixed is not None:
            p0.extend([max(a0, 1.0), c_clamped, w_clamped])
            lb.extend([0.1, e_lo, float(fwhm_min)])
            ub.extend([y_span * 40.0, e_hi, float(fwhm_max)])
        else:
            p0.extend([max(a0, 1.0), c_clamped, w_clamped, float(np.clip(e0, 0.0, 1.0))])
            lb.extend([0.1, e_lo, float(fwhm_min), 0.0])
            ub.extend([y_span * 40.0, e_hi, float(fwhm_max), 1.0])

    stride = 3 if eta_fixed is not None else 4

    def multi_xps_pv(xv: np.ndarray, *params: float) -> np.ndarray:
        acc = np.zeros_like(xv, dtype=float)
        for j in range(n_pk):
            if stride == 3:
                a, c, w = params[3 * j : 3 * j + 3]
                eta = float(eta_fixed)
            else:
                a, c, w, eta = params[4 * j : 4 * j + 4]
            acc += pseudo_voigt(xv, a, c, w, eta)
        return acc

    popt, perr, r2, rmse, chi2, resid = nlls_fit_with_errors(
        multi_xps_pv, be_roi, y_net, p0=p0, bounds=(lb, ub), max_nfev=6000
    )
    y_fit_net = multi_xps_pv(be_roi, *popt)
    y_fit_total = bg + y_fit_net

    # Display in descending BE order (XPS standard convention)
    desc = np.argsort(be_roi)[::-1]
    be_disp = be_roi[desc]
    y_raw_disp = y_roi[desc]
    bg_disp = bg[desc]
    y_fit_disp = y_fit_total[desc]
    resid_disp = resid[desc]

    series_out: list[SeriesData] = [
        SeriesData(name="Raw Spectrum", x=be_disp.tolist(), y=y_raw_disp.tolist(), kind="raw", show_markers=True),
        SeriesData(name=f"{bg_method.capitalize()} Background", x=be_disp.tolist(), y=bg_disp.tolist(), kind="baseline", line_style="dashed"),
        SeriesData(name="Total Fit Envelope", x=be_disp.tolist(), y=y_fit_disp.tolist(), kind="fit"),
    ]

    # Collect fitted peak info sorted by ascending BE
    comps: list[dict[str, Any]] = []
    for j in range(n_pk):
        if stride == 3:
            a, c, w = popt[3 * j : 3 * j + 3]
            a_se, c_se, w_se = perr[3 * j : 3 * j + 3]
            eta_val, eta_se = float(eta_fixed), 0.0
        else:
            a, c, w, eta_val = popt[4 * j : 4 * j + 4]
            a_se, c_se, w_se, eta_se = perr[4 * j : 4 * j + 4]
        label = peak_specs[j].get("label", f"Peak {j+1}") if (peak_specs and j < len(peak_specs)) else f"Peak {j+1}"
        comps.append({
            "label": label,
            "area": float(a),
            "area_se": float(a_se),
            "center": float(c),
            "center_se": float(c_se),
            "fwhm": float(w),
            "fwhm_se": float(w_se),
            "eta": float(eta_val),
            "eta_se": float(eta_se),
        })
    comps.sort(key=lambda d: d["center"])

    total_area = sum(c["area"] for c in comps) or 1.0
    fit_params: list[FitParameter] = [
        FitParameter(
            name="ref_be_ev",
            label="C 1s Reference BE (经验默认值)",
            value=float(ref_be_ev),
            std_error=0.0,
            unit="eV",
            is_empirical_default_input=True,
        ),
        FitParameter(
            name="charge_shift_ev",
            label="Applied Charge Shift ΔE",
            value=float(charge_shift),
            std_error=0.0,
            unit="eV",
        ),
    ]
    annotations: list[PlotAnnotation] = []
    table_columns = ["Section", "Name", "BE (eV)", "BE ±SE", "FWHM (eV)", "FWHM ±SE", "Area", "Area ±SE", "Ratio / At.%"]
    table_rows: list[dict[str, Any]] = []

    for idx, c in enumerate(comps):
        comp_y = bg + pseudo_voigt(be_roi, c["area"], c["center"], c["fwhm"], c["eta"])
        series_out.append(
            SeriesData(
                name=f"{c['label']} ({c['center']:.2f} eV)",
                x=be_disp.tolist(),
                y=comp_y[desc].tolist(),
                kind="component",
                line_style="dashed",
            )
        )
        pct = 100.0 * c["area"] / total_area
        table_rows.append({
            "Section": "Peak",
            "Name": c["label"],
            "BE (eV)": round(c["center"], 3),
            "BE ±SE": round(c["center_se"], 4),
            "FWHM (eV)": round(c["fwhm"], 3),
            "FWHM ±SE": round(c["fwhm_se"], 4),
            "Area": round(c["area"], 1),
            "Area ±SE": round(c["area_se"], 1),
            "Ratio / At.%": f"{pct:.2f}%",
        })
        fit_params.extend([
            FitParameter(name=f"pk{idx+1}_center", label=f"{c['label']} BE", value=c["center"], std_error=c["center_se"], unit="eV"),
            FitParameter(name=f"pk{idx+1}_fwhm", label=f"{c['label']} FWHM", value=c["fwhm"], std_error=c["fwhm_se"], unit="eV"),
            FitParameter(name=f"pk{idx+1}_area", label=f"{c['label']} Area", value=c["area"], std_error=c["area_se"], unit="cps·eV"),
        ])
        nearest_i = int(np.argmin(np.abs(be_disp - c["center"])))
        annotations.append(
            PlotAnnotation(
                x=float(c["center"]),
                y=float(y_fit_disp[nearest_i]),
                text=f"{c['label']}\n{c['center']:.2f} eV",
                ax_offset=(0.0, 14.0),
            )
        )

    # Atomic percentage quantification using user-editable RSF entries (zero fabricated RSFs!)
    if not rsf_entries:
        quant_entries = [{"name": pt.filename, "area": total_area, "rsf": 1.0}]
    else:
        quant_entries = rsf_entries

    norm_areas = []
    for entry in quant_entries:
        a_val = float(entry.get("area", total_area))
        rsf_val = max(float(entry.get("rsf", 1.0)), 1e-6)
        norm_areas.append((str(entry.get("name", "Region")), a_val, rsf_val, a_val / rsf_val))
    denom_norm = sum(item[3] for item in norm_areas) or 1.0
    atomic_pcts: dict[str, float] = {}
    for el_name, a_val, rsf_val, n_val in norm_areas:
        at_pct = 100.0 * n_val / denom_norm
        atomic_pcts[el_name] = round(at_pct, 3)
        table_rows.append({
            "Section": "Quant (RSF可编辑)",
            "Name": el_name,
            "BE (eV)": "-",
            "BE ±SE": "-",
            "FWHM (eV)": f"RSF={rsf_val:.3f}",
            "FWHM ±SE": "-",
            "Area": round(a_val, 1),
            "Area ±SE": "-",
            "Ratio / At.%": f"{at_pct:.2f} at.%",
        })

    fit_report = FitReport(
        model_name="XPS Multi-Peak Pseudo-Voigt + Shirley",
        equation="I(E) = BG_Shirley(E) + Σ PV(E; A_i, E_i, FWHM_i, η_i)",
        r_squared=r2,
        rmse=rmse,
        reduced_chi_sq=chi2,
        parameters=fit_params,
        residual=ResidualData(
            x=be_disp.tolist(),
            y=resid_disp.tolist(),
            x_label="Binding Energy / (eV)",
            y_label="Residual (cps)",
            rmse=rmse,
        ),
        summary_metrics={
            "charge_shift_ev": round(float(charge_shift), 4),
            "total_area": round(float(total_area), 2),
            "atomic_percentages": atomic_pcts,
            "r_squared": r2,
            "rmse": rmse,
        },
    )

    gt_comp: dict[str, Any] | None = None
    if ground_truth:
        shift_true = float(ground_truth.get("charge_shift_ev", 0.0))
        shift_err = abs(charge_shift - shift_true)
        gt_pks = sorted(ground_truth.get("peaks_corrected", []), key=lambda p: p["center"])
        max_be_err = 0.0
        max_fwhm_rel = 0.0
        if len(gt_pks) == len(comps):
            for est, exp in zip(comps, gt_pks):
                max_be_err = max(max_be_err, abs(est["center"] - exp["center"]))
                max_fwhm_rel = max(max_fwhm_rel, abs(est["fwhm"] - exp["fwhm"]) / exp["fwhm"])
        quant_err = 0.0
        if "rsf_test_quant" in ground_truth:
            exp_pct = ground_truth["rsf_test_quant"]["expected_pct"]
            for k, v in exp_pct.items():
                if k in atomic_pcts:
                    quant_err = max(quant_err, abs(atomic_pcts[k] - v))
        gt_comp = {
            "passed": bool(shift_err < 0.05 and max_be_err < 0.08 and max_fwhm_rel < 0.05 and quant_err < 2.0),
            "charge_shift_error_ev": round(float(shift_err), 4),
            "max_peak_center_error_ev": round(float(max_be_err), 4),
            "max_fwhm_rel_error_pct": round(float(max_fwhm_rel * 100.0), 3),
            "max_atomic_pct_error": round(float(quant_err), 3),
        }

    return ModuleProcessResponse(
        module="xps",
        sub_type="narrow_scan",
        title="XPS Charge Correction, Shirley Background & Peak Deconvolution",
        x_label="Binding Energy / (eV)",
        y_label="Intensity / (cps)",
        invert_x=True,
        series=series_out,
        annotations=annotations,
        fit_report=fit_report,
        table_columns=table_columns,
        table_rows=table_rows,
        provenance=[
            ProvenanceStep(
                step="xps_processing",
                parameters={
                    "auto_charge_correct": auto_charge_correct,
                    "ref_be_ev": ref_be_ev,
                    "applied_charge_shift_ev": round(float(charge_shift), 4),
                    "bg_method": bg_method,
                    "shirley_tol": shirley_tol,
                    "shirley_max_iter": shirley_max_iter,
                    "n_peaks": n_pk,
                    "fwhm_min": fwhm_min,
                    "fwhm_max": fwhm_max,
                    "eta_fixed": eta_fixed,
                    "rsf_entries": quant_entries,
                },
                empirical_defaults=["ref_be_ev", "rsf_entries (默认初始 RSF=1.00，须按仪器标定修改)"],
            )
        ],
        ground_truth_comparison=gt_comp,
    )
