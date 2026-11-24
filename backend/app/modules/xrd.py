from __future__ import annotations

from typing import Any
import numpy as np
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


def process_xrd(
    files: list[tuple[str, bytes]],
    *,
    smooth_enabled: bool = True,
    smooth_window: int = 7,
    smooth_polyorder: int = 3,
    baseline_method: str = "asls",
    baseline_lam: float = 1e5,
    baseline_p: float = 0.01,
    poly_degree: int = 3,
    snip_window: int = 25,
    display_mode: str = "overlay",
    stack_offset_pct: float = 25.0,
    prominence_pct: float = 8.0,
    min_distance_deg: float = 1.5,
    max_peaks: int = 12,
    wavelength_angstrom: float = 1.5406,
    k_factor: float = 0.89,
    instrumental_fwhm_deg: float = 0.0,
    instrumental_method: str = "gaussian",
    skip_rows: int | None = None,
    ground_truth: dict[str, Any] | None = None,
) -> ModuleProcessResponse:
    """Process powder XRD patterns: smoothing, baseline, peak table, Pseudo-Voigt fit, stack/waterfall, and Scherrer size."""
    if not files:
        raise ValueError("No files supplied to XRD module.")

    parsed = [parse_tabular_bytes(fn, content, skip_rows=skip_rows) for fn, content in files]
    series_out: list[SeriesData] = []

    primary_x: np.ndarray | None = None
    primary_net: np.ndarray | None = None
    primary_bg: np.ndarray | None = None
    primary_raw: np.ndarray | None = None

    # Compute maximum net span for stacked offset scaling
    processed_patterns: list[tuple[str, np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
    max_span = 1.0
    for pt in parsed:
        x = pt.data[:, 0]
        y_raw = pt.data[:, 1]
        order = np.argsort(x)
        x = x[order]
        y_raw = y_raw[order]
        y_sm = _apply_savgol(y_raw, smooth_window, smooth_polyorder) if smooth_enabled else y_raw.copy()
        bg = compute_baseline(
            x, y_sm,
            method=baseline_method,
            lam=baseline_lam,
            p=baseline_p,
            poly_degree=poly_degree,
            snip_window=snip_window,
        )
        y_net = y_sm - bg
        max_span = max(max_span, float(np.max(y_net) - np.min(y_net)))
        processed_patterns.append((pt.filename, x, y_raw, bg, y_net))

    mode_low = display_mode.lower()
    for idx, (fname, x, y_raw, bg, y_net) in enumerate(processed_patterns):
        offset = idx * (float(stack_offset_pct) / 100.0) * max_span if mode_low == "stacked" else 0.0
        if idx == 0:
            primary_x, primary_raw, primary_bg, primary_net = x, y_raw, bg, y_net
            if mode_low == "overlay":
                series_out.append(SeriesData(name=f"{fname} (Raw)", x=x.tolist(), y=y_raw.tolist(), kind="raw"))
                if baseline_method.lower() != "none":
                    series_out.append(SeriesData(name=f"{fname} (Baseline)", x=x.tolist(), y=bg.tolist(), kind="baseline", line_style="dashed"))
        series_out.append(
            SeriesData(
                name=fname if len(processed_patterns) > 1 else f"{fname} (Net)",
                x=x.tolist(),
                y=(y_net + offset).tolist(),
                z=[float(idx)] * len(x) if mode_low == "waterfall_3d" else None,
                kind="processed",
            )
        )

    assert primary_x is not None and primary_net is not None
    y_span = float(np.max(primary_net) - np.min(primary_net)) or 1.0
    dx = float(np.median(np.diff(primary_x))) if len(primary_x) > 1 else 0.05
    min_dist_pts = max(2, int(round(float(min_distance_deg) / max(dx, 1e-6))))
    prom = (float(prominence_pct) / 100.0) * y_span

    peak_idx, _ = find_peaks(primary_net, prominence=prom, distance=min_dist_pts)
    if len(peak_idx) == 0:
        peak_idx = np.asarray([int(np.argmax(primary_net))], dtype=int)
    # Sort strongest first up to max_peaks, then order by 2theta
    peak_idx = peak_idx[np.argsort(primary_net[peak_idx])[::-1][:max_peaks]]
    peak_idx = np.sort(peak_idx)

    # Multi-peak Pseudo-Voigt joint fit across primary net pattern
    n_pk = len(peak_idx)
    p0: list[float] = []
    lb: list[float] = []
    ub: list[float] = []
    for pi in peak_idx:
        c0 = float(primary_x[pi])
        h0 = max(float(primary_net[pi]), 1.0)
        w0 = 0.35
        a0 = h0 * w0 * 1.15
        p0.extend([a0, c0, w0, 0.25])
        lb.extend([1e-3, c0 - 1.5, 0.04, 0.0])
        ub.extend([max(h0 * 25.0, 100.0), c0 + 1.5, 6.0, 1.0])

    def multi_pv(xv: np.ndarray, *params: float) -> np.ndarray:
        acc = np.zeros_like(xv, dtype=float)
        for j in range(n_pk):
            a, c, w, eta = params[4 * j : 4 * j + 4]
            acc += pseudo_voigt(xv, a, c, w, eta)
        return acc

    # Fit Pseudo-Voigt on unsmoothed raw baseline-corrected data so smoothing never artificially broadens FWHM
    assert primary_raw is not None and primary_bg is not None
    primary_unsmoothed_net = primary_raw - primary_bg
    popt, perr, r2, rmse, chi2, resid = nlls_fit_with_errors(
        multi_pv, primary_x, primary_unsmoothed_net, p0=p0, bounds=(lb, ub)
    )
    y_fit = multi_pv(primary_x, *popt)
    if mode_low == "overlay":
        series_out.append(SeriesData(name="Multi-Peak Pseudo-Voigt Fit", x=primary_x.tolist(), y=y_fit.tolist(), kind="fit"))

    lambda_nm = float(wavelength_angstrom) / 10.0
    max_int = max(float(np.max(primary_net)), 1e-12)
    table_columns = [
        "Peak #",
        "2θ (°)",
        "2θ ±SE",
        "d-spacing (Å)",
        "I/I0 (%)",
        "FWHM (°)",
        "FWHM ±SE",
        "D_Scherrer (nm)",
        "D ±SE (nm)",
    ]
    table_rows: list[dict[str, Any]] = []
    fit_params: list[FitParameter] = [
        FitParameter(name="k_factor", label="Scherrer K (经验默认值)", value=float(k_factor), std_error=0.0, is_empirical_default_input=True),
        FitParameter(name="wavelength_angstrom", label="X-ray λ (经验默认值)", value=float(wavelength_angstrom), std_error=0.0, unit="Å", is_empirical_default_input=True),
        FitParameter(name="instrumental_fwhm_deg", label="Instrument β_inst (经验默认值)", value=float(instrumental_fwhm_deg), std_error=0.0, unit="°", is_empirical_default_input=True),
    ]
    annotations: list[PlotAnnotation] = []
    d_values: list[float] = []

    for j in range(n_pk):
        a, c, w, eta = popt[4 * j : 4 * j + 4]
        a_se, c_se, w_se, _ = perr[4 * j : 4 * j + 4]
        theta_rad = float(np.radians(c / 2.0))
        sin_t = max(float(np.sin(theta_rad)), 1e-8)
        cos_t = max(float(np.cos(theta_rad)), 1e-8)
        d_ang = float(wavelength_angstrom) / (2.0 * sin_t)

        # Instrumental broadening subtraction
        if instrumental_method.lower() == "linear":
            beta_corr_deg = max(float(w) - float(instrumental_fwhm_deg), 1e-4)
            beta_corr_se_deg = float(w_se)
        else:
            diff_sq = float(w) ** 2 - float(instrumental_fwhm_deg) ** 2
            beta_corr_deg = float(np.sqrt(max(diff_sq, 1e-6)))
            beta_corr_se_deg = float(w * w_se / max(beta_corr_deg, 1e-6))

        beta_corr_rad = float(np.radians(beta_corr_deg))
        d_nm = (float(k_factor) * lambda_nm) / (beta_corr_rad * cos_t)
        d_nm_se = d_nm * (beta_corr_se_deg / max(beta_corr_deg, 1e-6))
        d_values.append(d_nm)

        nearest_i = int(np.argmin(np.abs(primary_x - c)))
        rel_i = float(primary_net[nearest_i]) / max_int * 100.0

        table_rows.append({
            "Peak #": j + 1,
            "2θ (°)": round(float(c), 4),
            "2θ ±SE": round(float(c_se), 4),
            "d-spacing (Å)": round(d_ang, 4),
            "I/I0 (%)": round(rel_i, 1),
            "FWHM (°)": round(float(w), 4),
            "FWHM ±SE": round(float(w_se), 4),
            "D_Scherrer (nm)": round(float(d_nm), 2),
            "D ±SE (nm)": round(float(d_nm_se), 2),
        })

        fit_params.extend([
            FitParameter(name=f"peak_{j+1}_2theta", label=f"Peak {j+1} 2θ", value=float(c), std_error=float(c_se), unit="°"),
            FitParameter(name=f"peak_{j+1}_fwhm", label=f"Peak {j+1} FWHM", value=float(w), std_error=float(w_se), unit="°"),
            FitParameter(name=f"peak_{j+1}_D", label=f"Peak {j+1} D_Scherrer", value=float(d_nm), std_error=float(d_nm_se), unit="nm"),
        ])

        if mode_low != "waterfall_3d":
            annotations.append(
                PlotAnnotation(
                    x=float(c),
                    y=float(primary_net[nearest_i]),
                    text=f"{c:.2f}° ({d_nm:.1f} nm)",
                    ax_offset=(0.0, 14.0),
                )
            )

    mean_d = float(np.mean(d_values)) if d_values else 0.0
    fit_report = FitReport(
        model_name="Multi-Peak Pseudo-Voigt + Scherrer",
        equation="D = K·λ / (β_corr · cosθ)",
        r_squared=r2,
        rmse=rmse,
        reduced_chi_sq=chi2,
        parameters=fit_params,
        residual=ResidualData(
            x=primary_x.tolist(),
            y=resid.tolist(),
            x_label="2θ / (°)",
            y_label="Residual (Counts)",
            rmse=rmse,
        ),
        summary_metrics={
            "n_peaks": n_pk,
            "mean_crystallite_size_nm": round(mean_d, 3),
            "r_squared": r2,
            "rmse": rmse,
        },
    )

    gt_comp: dict[str, Any] | None = None
    if ground_truth:
        true_peaks = ground_truth.get("peaks_2theta", [])
        detected_peaks = [r["2θ (°)"] for r in table_rows]
        max_pk_err = max((min(abs(d - tp) for d in detected_peaks) for tp in true_peaks), default=0.0) if (true_peaks and detected_peaks) else 999.0
        d_true = float(ground_truth.get("crystallite_size_nm", 0.0))
        d_rel_err = abs(mean_d - d_true) / d_true if d_true > 0 else 0.0
        gt_comp = {
            "passed": bool(max_pk_err < 0.05 and d_rel_err < 0.05),
            "max_peak_pos_error_deg": round(float(max_pk_err), 4),
            "crystallite_size_true_nm": d_true,
            "crystallite_size_measured_nm": round(mean_d, 3),
            "crystallite_size_rel_error_pct": round(d_rel_err * 100.0, 3),
        }

    return ModuleProcessResponse(
        module="xrd",
        sub_type=mode_low,
        title="Powder XRD Analysis & Scherrer Crystallite Size",
        x_label="2θ / (°)",
        y_label="Intensity / (counts)",
        plot_mode="waterfall_3d" if mode_low == "waterfall_3d" else "2d",
        series=series_out,
        annotations=annotations,
        fit_report=fit_report,
        table_columns=table_columns,
        table_rows=table_rows,
        provenance=[
            ProvenanceStep(
                step="xrd_processing",
                parameters={
                    "smooth_enabled": smooth_enabled,
                    "smooth_window": smooth_window,
                    "smooth_polyorder": smooth_polyorder,
                    "baseline_method": baseline_method,
                    "baseline_lam": baseline_lam,
                    "baseline_p": baseline_p,
                    "display_mode": display_mode,
                    "prominence_pct": prominence_pct,
                    "min_distance_deg": min_distance_deg,
                    "wavelength_angstrom": wavelength_angstrom,
                    "k_factor": k_factor,
                    "instrumental_fwhm_deg": instrumental_fwhm_deg,
                    "instrumental_method": instrumental_method,
                },
                empirical_defaults=["wavelength_angstrom", "k_factor", "instrumental_fwhm_deg"],
            )
        ],
        ground_truth_comparison=gt_comp,
    )
