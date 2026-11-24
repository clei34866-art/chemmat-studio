from __future__ import annotations

from typing import Any
import numpy as np
from scipy.signal import find_peaks, savgol_filter

from app.core.baseline import compute_baseline
from app.core.fitting import linear_fit_with_errors, nlls_fit_with_errors, pseudo_voigt
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


def _apply_savgol(y: np.ndarray, window: int, polyorder: int) -> np.ndarray:
    n = len(y)
    if n < 5:
        return y.copy()
    w = max(5, int(window))
    if w % 2 == 0:
        w += 1
    w = min(w, n if n % 2 == 1 else n - 1)
    p = min(max(1, int(polyorder)), w - 1)
    return savgol_filter(y, window_length=w, polyorder=p)


def _auto_tauc_window(hv: np.ndarray, tauc_y: np.ndarray) -> tuple[float, float]:
    """Select the steepest, highest-linearity rising edge segment on a Tauc curve."""
    n = len(hv)
    y_max = float(np.max(tauc_y)) or 1.0
    # Candidate points in the main rising edge above noise floor
    cand_idx = np.where((tauc_y >= 0.12 * y_max) & (tauc_y <= 0.92 * y_max))[0]
    if len(cand_idx) < 8:
        return float(hv[max(0, n // 2)]), float(hv[-1])

    start_0 = int(cand_idx[0])
    end_0 = int(cand_idx[-1])
    win_len = max(8, min(28, (end_0 - start_0 + 1) // 2))
    best_score = -1.0
    best_range = (float(hv[start_0]), float(hv[end_0]))

    for s in range(start_0, max(start_0 + 1, end_0 - win_len + 2)):
        e = min(end_0, s + win_len)
        if e - s < 6:
            continue
        fit = linear_fit_with_errors(hv[s : e + 1], tauc_y[s : e + 1])
        if fit["slope"] <= 0:
            continue
        r2 = max(fit["r_squared"], 0.0)
        # Prefer regions with very high R^2 and strong positive slope
        score = (r2 ** 12) * fit["slope"]
        if score > best_score:
            best_score = score
            best_range = (float(hv[s]), float(hv[e]))

    return best_range


def process_spectroscopy(
    files: list[tuple[str, bytes]],
    *,
    sub_type: str = "uvvis",
    smooth_enabled: bool = True,
    smooth_window: int = 11,
    smooth_polyorder: int = 3,
    baseline_method: str = "asls",
    baseline_lam: float = 1e5,
    baseline_p: float = 0.01,
    poly_degree: int = 2,
    prominence_pct: float = 8.0,
    min_distance: float = 15.0,
    ftir_mode: str = "absorbance",
    enable_tauc: bool = True,
    tauc_gamma: float = 0.5,
    path_length_cm: float = 1.0,
    kubelka_munk: bool = False,
    tauc_emin: float | None = None,
    tauc_emax: float | None = None,
    skip_rows: int | None = None,
    ground_truth: dict[str, Any] | None = None,
) -> ModuleProcessResponse:
    """Process UV-Vis (with Tauc band-gap fit), FTIR (%T<->A), and Raman spectra."""
    if not files:
        raise ValueError("No files supplied to Spectroscopy module.")

    pt = parse_tabular_bytes(files[0][0], files[0][1], skip_rows=skip_rows)
    x_raw = pt.data[:, 0]
    y_raw = pt.data[:, 1]
    st = sub_type.lower()

    # Branch 1: UV-Vis Tauc Plot for Optical Band Gap Eg
    if st == "uvvis" and enable_tauc:
        hv = 1239.84198 / np.maximum(x_raw, 1.0)
        order = np.argsort(hv)
        hv = hv[order]
        y_ord = y_raw[order]

        if kubelka_munk:
            r_frac = y_ord / 100.0 if float(np.max(y_ord)) > 1.5 else y_ord
            r_frac = np.clip(r_frac, 1e-4, 0.9999)
            alpha = ((1.0 - r_frac) ** 2) / (2.0 * r_frac)
        else:
            alpha = 2.302585 * np.maximum(y_ord, 0.0) / max(float(path_length_cm), 1e-6)

        gamma = max(float(tauc_gamma), 0.1)
        tauc_y = np.power(np.maximum(alpha * hv, 0.0), 1.0 / gamma)

        if tauc_emin is not None and tauc_emax is not None and tauc_emax > tauc_emin:
            e_lo, e_hi = float(tauc_emin), float(tauc_emax)
        else:
            e_lo, e_hi = _auto_tauc_window(hv, tauc_y)

        mask = (hv >= e_lo) & (hv <= e_hi)
        if np.sum(mask) < 4:
            mask = np.arange(len(hv)) >= max(0, len(hv) - 15)
        hv_fit = hv[mask]
        ty_fit = tauc_y[mask]

        lin = linear_fit_with_errors(hv_fit, ty_fit)
        k = lin["slope"]
        k_se = lin["slope_se"]
        b = lin["intercept"]
        b_se = lin["intercept_se"]

        if abs(k) <= 1e-12:
            raise ValueError("Selected Tauc region has near-zero slope; cannot extrapolate Eg.")

        eg = -b / k
        eg_se = float(np.sqrt((b_se / k) ** 2 + (b * k_se / (k ** 2)) ** 2))

        # Extrapolation line from (Eg, 0) up to e_hi
        x_extrap = np.linspace(min(eg, float(hv_fit[0])), float(hv_fit[-1]), 60)
        y_extrap = k * x_extrap + b

        y_tauc_label = f"(α·hν)^(1/{gamma:g})"

        gt_comp = None
        if ground_truth and "band_gap_ev" in ground_truth:
            eg_true = float(ground_truth["band_gap_ev"])
            eg_err = abs(eg - eg_true)
            gt_comp = {
                "passed": bool(eg_err < 0.05),
                "Eg_true_eV": eg_true,
                "Eg_measured_eV": round(eg, 4),
                "Eg_abs_error_eV": round(eg_err, 4),
            }

        return ModuleProcessResponse(
            module="spectroscopy",
            sub_type="uvvis",
            title=f"UV-Vis Tauc Plot Band Gap Analysis (Eg = {eg:.3f} ± {eg_se:.3f} eV)",
            x_label="Photon Energy hν / (eV)",
            y_label=f"{y_tauc_label} / (a.u.)",
            series=[
                SeriesData(name=f"{pt.filename} (Tauc Curve)", x=hv.tolist(), y=tauc_y.tolist(), kind="processed"),
                SeriesData(name=f"Linear Extrapolation (Eg={eg:.3f} eV)", x=x_extrap.tolist(), y=y_extrap.tolist(), kind="fit", line_style="dashed"),
            ],
            annotations=[
                PlotAnnotation(x=float(eg), y=0.0, text=f"Eg = {eg:.3f} ± {eg_se:.3f} eV", ax_offset=(28.0, 24.0))
            ],
            fit_report=FitReport(
                model_name="Tauc Linear Edge Extrapolation",
                equation="(α·hν)^(1/γ) = k·(hν - Eg)",
                r_squared=lin["r_squared"],
                rmse=lin["rmse"],
                parameters=[
                    FitParameter(name="Eg_eV", label="Optical Band Gap Eg", value=eg, std_error=eg_se, unit="eV"),
                    FitParameter(name="slope", label="Linear Slope k", value=k, std_error=k_se),
                    FitParameter(name="tauc_gamma", label="Transition Exponent γ (经验默认值)", value=gamma, std_error=0.0, is_empirical_default_input=True),
                    FitParameter(name="path_length_cm", label="Optical Path Length (经验默认值)", value=float(path_length_cm), std_error=0.0, unit="cm", is_empirical_default_input=True),
                ],
                residual=ResidualData(
                    x=hv_fit.tolist(),
                    y=lin["residual"].tolist(),
                    x_label="Photon Energy hν / (eV)",
                    y_label="Tauc Fit Residual",
                    rmse=lin["rmse"],
                ),
                summary_metrics={"band_gap_ev": round(eg, 4), "band_gap_se_ev": round(eg_se, 4), "fit_window_ev": [round(e_lo, 3), round(e_hi, 3)]},
            ),
            table_columns=["Metric", "Value", "Std Error (±1σ)", "Unit"],
            table_rows=[
                {"Metric": "Band Gap Eg", "Value": round(eg, 4), "Std Error (±1σ)": round(eg_se, 4), "Unit": "eV"},
                {"Metric": "Fit Window", "Value": f"{e_lo:.2f} – {e_hi:.2f}", "Std Error (±1σ)": "-", "Unit": "eV"},
                {"Metric": "R² (Linear Region)", "Value": round(lin["r_squared"], 6), "Std Error (±1σ)": "-", "Unit": ""},
            ],
            provenance=[
                ProvenanceStep(
                    step="uvvis_tauc",
                    parameters={"tauc_gamma": gamma, "path_length_cm": path_length_cm, "kubelka_munk": kubelka_munk, "fit_emin": e_lo, "fit_emax": e_hi},
                    empirical_defaults=["tauc_gamma", "path_length_cm"],
                )
            ],
            ground_truth_comparison=gt_comp,
        )

    # Branch 2: Raman / FTIR / UV-Vis Absorption Peak & Baseline Processing
    order = np.argsort(x_raw)
    x_asc = x_raw[order]
    y_ord = y_raw[order]

    is_transmittance = st == "ftir" and (ftir_mode.lower() == "absorbance") and float(np.max(y_ord)) > 2.0
    if is_transmittance:
        y_sig = -np.log10(np.clip(y_ord / 100.0, 1e-4, 1.0))
        y_label = "Absorbance / (a.u.)"
    elif st == "ftir":
        y_sig = y_ord.copy()
        y_label = "Transmittance / (%)"
    elif st == "uvvis":
        y_sig = y_ord.copy()
        y_label = "Absorbance / (a.u.)"
    else:
        y_sig = y_ord.copy()
        y_label = "Raman Intensity / (counts)"

    y_sm = _apply_savgol(y_sig, smooth_window, smooth_polyorder) if smooth_enabled else y_sig.copy()
    bg = compute_baseline(x_asc, y_sm, method=baseline_method, lam=baseline_lam, p=baseline_p, poly_degree=poly_degree)
    y_net = y_sm - bg

    y_span = float(np.max(y_net) - np.min(y_net)) or 1.0
    dx = float(np.median(np.diff(x_asc))) if len(x_asc) > 1 else 2.0
    min_pts = max(2, int(round(float(min_distance) / max(dx, 1e-6))))
    prom = (float(prominence_pct) / 100.0) * y_span
    pk_idx, _ = find_peaks(y_net, prominence=prom, distance=min_pts)
    if len(pk_idx) == 0:
        pk_idx = np.asarray([int(np.argmax(y_net))], dtype=int)
    pk_idx = np.sort(pk_idx[np.argsort(y_net[pk_idx])[::-1][:10]])

    # Multi-peak Pseudo-Voigt fit for SE and residual plot
    n_pk = len(pk_idx)
    p0: list[float] = []
    lb: list[float] = []
    ub: list[float] = []
    w0 = max(dx * 6.0, 12.0 if st != "uvvis" else 8.0)
    for pi in pk_idx:
        c0 = float(x_asc[pi])
        h0 = max(float(y_net[pi]), 1e-3)
        p0.extend([h0 * w0 * 1.15, c0, w0, 0.25])
        lb.extend([1e-5, c0 - max(25.0, w0), max(dx * 2.0, 1.0), 0.0])
        ub.extend([h0 * w0 * 25.0, c0 + max(25.0, w0), max(w0 * 8.0, 200.0), 1.0])

    def multi_spec_pv(xv: np.ndarray, *params: float) -> np.ndarray:
        acc = np.zeros_like(xv, dtype=float)
        for j in range(n_pk):
            a, c, w, e = params[4 * j : 4 * j + 4]
            acc += pseudo_voigt(xv, a, c, w, e)
        return acc

    popt, perr, r2, rmse, chi2, resid = nlls_fit_with_errors(
        multi_spec_pv, x_asc, y_net, p0=p0, bounds=(lb, ub), max_nfev=3500
    )
    y_fit = multi_spec_pv(x_asc, *popt)

    disp = slice(None, None, -1) if st == "ftir" else slice(None)
    x_disp = x_asc[disp]
    x_label = "Wavenumber / (cm⁻¹)" if st == "ftir" else ("Raman Shift / (cm⁻¹)" if st == "raman" else "Wavelength / (nm)")
    # Avoid Unicode superscript minus warning in Matplotlib by using cm^-1 when needed or clean notation
    x_label = "Wavenumber / (cm^-1)" if st == "ftir" else ("Raman Shift / (cm^-1)" if st == "raman" else "Wavelength / (nm)")

    max_net = max(float(np.max(y_net)), 1e-12)
    table_rows: list[dict[str, Any]] = []
    fit_params: list[FitParameter] = []
    annotations: list[PlotAnnotation] = []
    for j in range(n_pk):
        a, c, w, _ = popt[4 * j : 4 * j + 4]
        _, c_se, w_se, _ = perr[4 * j : 4 * j + 4]
        ni = int(np.argmin(np.abs(x_asc - c)))
        rel_i = float(y_net[ni]) / max_net * 100.0
        table_rows.append({
            "Peak #": j + 1,
            "Position": round(float(c), 2),
            "Position ±SE": round(float(c_se), 3),
            "FWHM": round(float(w), 2),
            "FWHM ±SE": round(float(w_se), 3),
            "Rel Intensity (%)": round(rel_i, 1),
        })
        fit_params.extend([
            FitParameter(name=f"pk{j+1}_pos", label=f"Peak {j+1} Pos", value=float(c), std_error=float(c_se)),
            FitParameter(name=f"pk{j+1}_fwhm", label=f"Peak {j+1} FWHM", value=float(w), std_error=float(w_se)),
        ])
        annotations.append(PlotAnnotation(x=float(c), y=float(y_net[ni]), text=f"{c:.1f}", ax_offset=(0.0, 12.0)))

    gt_comp = None
    if ground_truth and "peaks_cm1" in ground_truth:
        true_pks = ground_truth["peaks_cm1"]
        det_pks = [r["Position"] for r in table_rows]
        max_err = max((min(abs(d - tp) for d in det_pks) for tp in true_pks), default=999.0)
        tol = 2.0 if st == "raman" else 4.0
        gt_comp = {
            "passed": bool(max_err < tol),
            "max_peak_error_cm1": round(float(max_err), 3),
            "tolerance_cm1": tol,
        }

    return ModuleProcessResponse(
        module="spectroscopy",
        sub_type=st,
        title=f"{st.upper()} Baseline Correction & Peak Analysis",
        x_label=x_label,
        y_label=y_label,
        invert_x=(st == "ftir"),
        series=[
            SeriesData(name="Processed Raw", x=x_disp.tolist(), y=y_sig[disp].tolist(), kind="raw"),
            SeriesData(name=f"Baseline ({baseline_method})", x=x_disp.tolist(), y=bg[disp].tolist(), kind="baseline", line_style="dashed"),
            SeriesData(name="Baseline Corrected", x=x_disp.tolist(), y=y_net[disp].tolist(), kind="processed"),
            SeriesData(name="Pseudo-Voigt Fit", x=x_disp.tolist(), y=y_fit[disp].tolist(), kind="fit"),
        ],
        annotations=annotations,
        fit_report=FitReport(
            model_name="Multi-Peak Pseudo-Voigt Spectrum Fit",
            equation="I(x) = Σ PV(x; A_i, x_i, FWHM_i, η_i)",
            r_squared=r2,
            rmse=rmse,
            reduced_chi_sq=chi2,
            parameters=fit_params,
            residual=ResidualData(x=x_disp.tolist(), y=resid[disp].tolist(), x_label=x_label, y_label="Residual", rmse=rmse),
            summary_metrics={"n_peaks": n_pk, "r_squared": r2, "rmse": rmse},
        ),
        table_columns=["Peak #", "Position", "Position ±SE", "FWHM", "FWHM ±SE", "Rel Intensity (%)"],
        table_rows=table_rows,
        provenance=[
            ProvenanceStep(
                step="spectroscopy_processing",
                parameters={
                    "sub_type": st,
                    "smooth_enabled": smooth_enabled,
                    "smooth_window": smooth_window,
                    "baseline_method": baseline_method,
                    "baseline_lam": baseline_lam,
                    "baseline_p": baseline_p,
                    "prominence_pct": prominence_pct,
                    "ftir_mode": ftir_mode,
                },
                empirical_defaults=[],
            )
        ],
        ground_truth_comparison=gt_comp,
    )
