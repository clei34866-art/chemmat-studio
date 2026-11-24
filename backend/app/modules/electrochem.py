from __future__ import annotations

from typing import Any
import numpy as np
from scipy.signal import find_peaks

from app.core.fitting import cnls_fit_with_errors, linear_fit_with_errors, nlls_fit_with_errors, pseudo_voigt
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


def _circuit_eval(model_name: str, freq: np.ndarray, *params: float) -> np.ndarray:
    w = 2.0 * np.pi * freq
    jw = 1j * w
    m = model_name.strip()
    if m == "R(CR)":
        rs, cdl, rct = params
        return rs + 1.0 / (jw * cdl + 1.0 / rct)
    if m == "R(QR)":
        rs, q, n, rct = params
        return rs + 1.0 / (q * (jw ** n) + 1.0 / rct)
    if m == "R(Q(RW))":
        rs, q, n, rct, aw = params
        zw = aw * (1.0 - 1j) / np.sqrt(w)
        return rs + 1.0 / (q * (jw ** n) + 1.0 / (rct + zw))
    if m == "R(QR)(QR)":
        rs, q1, n1, r1, q2, n2, r2 = params
        return rs + 1.0 / (q1 * (jw ** n1) + 1.0 / r1) + 1.0 / (q2 * (jw ** n2) + 1.0 / r2)
    raise ValueError(f"Unsupported EIS circuit model: {model_name}")


def _process_eis(
    files: list[tuple[str, bytes]],
    *,
    circuit_model: str = "R(Q(RW))",
    initial_params: dict[str, float] | None = None,
    bounds_override: dict[str, list[float]] | None = None,
    skip_rows: int | None = None,
    ground_truth: dict[str, Any] | None = None,
) -> ModuleProcessResponse:
    pt = parse_tabular_bytes(files[0][0], files[0][1], skip_rows=skip_rows)
    freq = pt.data[:, 0]
    z_re = pt.data[:, 1]
    z_col2 = pt.data[:, 2]
    # Convention: input may store -Z'' (positive in capacitive quadrant) or signed Z''
    neg_imag_input = float(np.median(z_col2)) >= 0
    z_im = -z_col2 if neg_imag_input else z_col2
    z_neg_im = -z_im

    rs0 = max(float(np.min(z_re)), 0.05)
    # Estimate semicircle diameter from high/mid frequency portion
    n_pts = len(freq)
    high_mid = z_re[: max(5, (2 * n_pts) // 3)]
    rct0 = max(float(np.max(high_mid) - rs0), 5.0)
    # Find apex frequency of -Z'' inside semicircle region
    apex_i = int(np.argmax(z_neg_im[: max(5, (3 * n_pts) // 4)]))
    f_apex = max(float(freq[apex_i]), 1e-2)
    c0 = 1.0 / (2.0 * np.pi * f_apex * rct0)
    aw0 = max(float((z_re[-1] - z_re[max(0, n_pts - 5)]) * np.sqrt(2.0 * np.pi * freq[-1])), 1.0)

    specs: dict[str, list[tuple[str, float, float, float, str]]] = {
        "R(CR)": [
            ("Rs", rs0, 1e-3, 1e4, "Ω"),
            ("Cdl", c0, 1e-9, 1.0, "F"),
            ("Rct", rct0, 1e-2, 1e6, "Ω"),
        ],
        "R(QR)": [
            ("Rs", rs0, 1e-3, 1e4, "Ω"),
            ("Q", c0, 1e-9, 1.0, "S·s^n"),
            ("n", 0.85, 0.2, 1.0, ""),
            ("Rct", rct0, 1e-2, 1e6, "Ω"),
        ],
        "R(Q(RW))": [
            ("Rs", rs0, 1e-3, 1e4, "Ω"),
            ("Q", c0, 1e-9, 1.0, "S·s^n"),
            ("n", 0.85, 0.2, 1.0, ""),
            ("Rct", rct0, 1e-2, 1e6, "Ω"),
            ("Aw", aw0, 1e-3, 1e5, "Ω·s^-0.5"),
        ],
        "R(QR)(QR)": [
            ("Rs", rs0, 1e-3, 1e4, "Ω"),
            ("Q1", c0, 1e-9, 1.0, "S·s^n"),
            ("n1", 0.85, 0.2, 1.0, ""),
            ("R1", rct0 * 0.4, 1e-2, 1e6, "Ω"),
            ("Q2", c0 * 5.0, 1e-9, 1.0, "S·s^n"),
            ("n2", 0.85, 0.2, 1.0, ""),
            ("R2", rct0 * 0.6, 1e-2, 1e6, "Ω"),
        ],
    }
    if circuit_model not in specs:
        raise ValueError(f"Unsupported circuit_model: {circuit_model}")

    elem_defs = specs[circuit_model]
    p0: list[float] = []
    lb: list[float] = []
    ub: list[float] = []
    for name, d_val, lo, hi, _ in elem_defs:
        val = float(initial_params[name]) if (initial_params and name in initial_params) else float(d_val)
        if bounds_override and name in bounds_override and len(bounds_override[name]) == 2:
            lo, hi = float(bounds_override[name][0]), float(bounds_override[name][1])
        p0.append(float(np.clip(val, lo * 1.001, hi * 0.999)))
        lb.append(lo)
        ub.append(hi)

    popt, perr, r2, rmse, chi2, res_re, res_im = cnls_fit_with_errors(
        lambda f, *p: _circuit_eval(circuit_model, f, *p),
        freq, z_re, z_im, p0=p0, bounds=(lb, ub),
    )
    z_hat = _circuit_eval(circuit_model, freq, *popt)
    z_hat_re = np.real(z_hat)
    z_hat_neg_im = -np.imag(z_hat)

    log_f = np.log10(np.maximum(freq, 1e-12))
    fit_params: list[FitParameter] = []
    table_rows: list[dict[str, Any]] = []
    param_dict: dict[str, float] = {}
    for (name, _, _, _, unit), val, se in zip(elem_defs, popt, perr):
        param_dict[name] = float(val)
        fit_params.append(
            FitParameter(
                name=name,
                label=name,
                value=float(val),
                std_error=float(se),
                unit=unit,
                is_empirical_default_input=initial_params is not None,
            )
        )
        table_rows.append({
            "Element": name,
            "Value": float(f"{val:.6g}"),
            "Std Error (±1σ)": float(f"{se:.4g}"),
            "Rel Error (%)": round(100.0 * float(se) / max(abs(float(val)), 1e-12), 2),
            "Unit": unit,
        })

    gt_comp: dict[str, Any] | None = None
    if ground_truth:
        rel_errs = {}
        for name in param_dict:
            if name in ground_truth and ground_truth[name] != 0:
                rel_errs[name] = abs(param_dict[name] - float(ground_truth[name])) / abs(float(ground_truth[name]))
        max_rel = max(rel_errs.values(), default=0.0)
        gt_comp = {
            "passed": bool(max_rel < 0.03),
            "max_rel_error_pct": round(max_rel * 100.0, 3),
            "per_element_rel_error_pct": {k: round(v * 100.0, 3) for k, v in rel_errs.items()},
        }

    return ModuleProcessResponse(
        module="electrochem",
        sub_type="eis",
        title=f"EIS Nyquist Plot & Equivalent Circuit Fit [{circuit_model}]",
        x_label="Z' / (Ω)",
        y_label="-Z'' / (Ω)",
        equal_aspect=True,
        series=[
            SeriesData(name=f"{pt.filename} (Measured)", x=z_re.tolist(), y=z_neg_im.tolist(), kind="raw", show_markers=True),
            SeriesData(name=f"CNLS Fit [{circuit_model}]", x=z_hat_re.tolist(), y=z_hat_neg_im.tolist(), kind="fit"),
        ],
        fit_report=FitReport(
            model_name=f"CNLS Equivalent Circuit ({circuit_model})",
            equation=circuit_model,
            r_squared=r2,
            rmse=rmse,
            reduced_chi_sq=chi2,
            parameters=fit_params,
            residual=ResidualData(
                x=log_f.tolist(),
                y=res_re.tolist(),
                y_imag=(-res_im).tolist(),
                x_label="log10(Frequency / Hz)",
                y_label="Impedance Residual (Ω)",
                rmse=rmse,
            ),
            summary_metrics={**param_dict, "r_squared": r2, "rmse": rmse},
        ),
        table_columns=["Element", "Value", "Std Error (±1σ)", "Rel Error (%)", "Unit"],
        table_rows=table_rows,
        provenance=[
            ProvenanceStep(
                step="eis_cnls_fit",
                parameters={"circuit_model": circuit_model, "initial_params": initial_params or "auto-estimated"},
                empirical_defaults=["circuit_model", "initial_params"] if initial_params else ["circuit_model"],
            )
        ],
        ground_truth_comparison=gt_comp,
    )


def _process_cv(
    files: list[tuple[str, bytes]],
    *,
    active_mass_mg: float = 1.0,
    scan_rate_mv_s: float = 50.0,
    cv_prominence_pct: float = 10.0,
    skip_rows: int | None = None,
    ground_truth: dict[str, Any] | None = None,
) -> ModuleProcessResponse:
    series_out: list[SeriesData] = []
    annotations: list[PlotAnnotation] = []
    table_rows: list[dict[str, Any]] = []

    pt0 = parse_tabular_bytes(files[0][0], files[0][1], skip_rows=skip_rows)
    v0 = pt0.data[:, 0]
    i0 = pt0.data[:, 1]

    for fn, content in files:
        pt = parse_tabular_bytes(fn, content, skip_rows=skip_rows)
        series_out.append(SeriesData(name=fn, x=pt.data[:, 0].tolist(), y=pt.data[:, 1].tolist(), kind="processed"))

    # Separate forward anodic and reverse cathodic segments on primary scan
    span_i = float(np.max(i0) - np.min(i0)) or 1.0
    prom = (float(cv_prominence_pct) / 100.0) * span_i
    ox_idx, _ = find_peaks(i0, prominence=prom)
    red_idx, _ = find_peaks(-i0, prominence=prom)

    epa = float(v0[ox_idx[int(np.argmax(i0[ox_idx]))]]) if len(ox_idx) > 0 else float(v0[int(np.argmax(i0))])
    ipa = float(np.max(i0[ox_idx])) if len(ox_idx) > 0 else float(np.max(i0))
    epc = float(v0[red_idx[int(np.argmin(i0[red_idx]))]]) if len(red_idx) > 0 else float(v0[int(np.argmin(i0))])
    ipc = float(np.min(i0[red_idx])) if len(red_idx) > 0 else float(np.min(i0))

    # Local Pseudo-Voigt peak fit around oxidation peak for uncertainty & residual plot
    win = np.abs(v0 - epa) <= 0.25
    vx = v0[win]
    iy = i0[win]
    # Take forward half-scan around oxidation peak
    if len(vx) >= 6:
        dv = np.gradient(vx)
        fwd = dv >= 0
        if np.sum(fwd) >= 5:
            vx, iy = vx[fwd], iy[fwd]
    order = np.argsort(vx)
    vx, iy = vx[order], iy[order]
    base_off = float(np.min(iy))
    popt, perr, r2, rmse, chi2, resid = nlls_fit_with_errors(
        lambda x, a, c, w, eta, b: b + pseudo_voigt(x, a, c, w, eta),
        vx, iy,
        p0=[max((ipa - base_off) * 0.1, 0.05), epa, 0.09, 0.1, base_off],
        bounds=([1e-4, float(np.min(vx)), 0.01, 0.0, -1e4], [1e4, float(np.max(vx)), 1.0, 1.0, 1e4]),
    )
    epa_fit, epa_se = float(popt[1]), float(perr[1])
    y_fit = popt[4] + pseudo_voigt(vx, popt[0], popt[1], popt[2], popt[3])
    series_out.append(SeriesData(name="Oxidation Peak Fit", x=vx.tolist(), y=y_fit.tolist(), kind="fit"))

    # Loop integral capacitance: C = integral(|I| dV) / (2 * m * v * dV)
    loop_area = float(np.abs(np.trapezoid(i0, v0)))  # mA * V
    dv_win = max(float(np.max(v0) - np.min(v0)), 1e-6)
    mass_g = max(float(active_mass_mg) / 1000.0, 1e-9)
    scan_v_s = max(float(scan_rate_mv_s) / 1000.0, 1e-6)
    cs_cv = (loop_area / 1000.0) / (2.0 * mass_g * scan_v_s * dv_win)

    annotations.extend([
        PlotAnnotation(x=epa_fit, y=ipa, text=f"Epa={epa_fit:.3f} V", ax_offset=(0.0, 14.0)),
        PlotAnnotation(x=epc, y=ipc, text=f"Epc={epc:.3f} V", ax_offset=(0.0, -18.0)),
    ])
    table_rows = [
        {"Metric": "Anodic Peak E_pa", "Value": round(epa_fit, 4), "Std Error (±1σ)": round(epa_se, 4), "Unit": "V"},
        {"Metric": "Anodic Peak I_pa", "Value": round(ipa, 4), "Std Error (±1σ)": "-", "Unit": "mA"},
        {"Metric": "Cathodic Peak E_pc", "Value": round(epc, 4), "Std Error (±1σ)": "-", "Unit": "V"},
        {"Metric": "Cathodic Peak I_pc", "Value": round(ipc, 4), "Std Error (±1σ)": "-", "Unit": "mA"},
        {"Metric": "Peak Separation ΔE_p", "Value": round(abs(epa_fit - epc), 4), "Std Error (±1σ)": "-", "Unit": "V"},
        {"Metric": "Integral Capacitance C_s", "Value": round(cs_cv, 2), "Std Error (±1σ)": "-", "Unit": "F/g"},
    ]

    gt_comp = None
    if ground_truth:
        err_pa = abs(epa_fit - float(ground_truth.get("E_pa_V", epa_fit)))
        err_pc = abs(epc - float(ground_truth.get("E_pc_V", epc)))
        gt_comp = {
            "passed": bool(err_pa < 0.015 and err_pc < 0.015),
            "E_pa_error_V": round(err_pa, 4),
            "E_pc_error_V": round(err_pc, 4),
        }

    return ModuleProcessResponse(
        module="electrochem",
        sub_type="cv",
        title="Cyclic Voltammetry (CV) Redox & Capacitance Analysis",
        x_label="Potential / (V)",
        y_label="Current / (mA)",
        series=series_out,
        annotations=annotations,
        fit_report=FitReport(
            model_name="Oxidation Peak Pseudo-Voigt Fit",
            equation="I(E) = I0 + PV(E; A, E_pa, FWHM, η)",
            r_squared=r2,
            rmse=rmse,
            reduced_chi_sq=chi2,
            parameters=[
                FitParameter(name="E_pa", label="Anodic Peak E_pa", value=epa_fit, std_error=epa_se, unit="V"),
                FitParameter(name="active_mass_mg", label="Active Mass (经验默认值)", value=float(active_mass_mg), std_error=0.0, unit="mg", is_empirical_default_input=True),
                FitParameter(name="scan_rate_mv_s", label="Scan Rate (经验默认值)", value=float(scan_rate_mv_s), std_error=0.0, unit="mV/s", is_empirical_default_input=True),
            ],
            residual=ResidualData(x=vx.tolist(), y=resid.tolist(), x_label="Potential / (V)", y_label="Residual (mA)", rmse=rmse),
            summary_metrics={"E_pa_V": epa_fit, "E_pc_V": epc, "delta_Ep_V": abs(epa_fit - epc), "specific_capacitance_F_g": cs_cv},
        ),
        table_columns=["Metric", "Value", "Std Error (±1σ)", "Unit"],
        table_rows=table_rows,
        provenance=[
            ProvenanceStep(
                step="cv_analysis",
                parameters={"active_mass_mg": active_mass_mg, "scan_rate_mv_s": scan_rate_mv_s, "cv_prominence_pct": cv_prominence_pct},
                empirical_defaults=["active_mass_mg", "scan_rate_mv_s"],
            )
        ],
        ground_truth_comparison=gt_comp,
    )


def _process_gcd(
    files: list[tuple[str, bytes]],
    *,
    active_mass_mg: float = 1.0,
    current_ma: float = 1.0,
    potential_window_v: float | None = None,
    skip_rows: int | None = None,
    ground_truth: dict[str, Any] | None = None,
) -> ModuleProcessResponse:
    pt = parse_tabular_bytes(files[0][0], files[0][1], skip_rows=skip_rows)
    t = pt.data[:, 0]
    v = pt.data[:, 1]

    apex = int(np.argmax(v))
    t_chg, v_chg = t[: apex + 1], v[: apex + 1]
    t_dis, v_dis = t[apex:], v[apex:]
    if len(t_dis) < 3:
        raise ValueError("Could not identify discharge segment in GCD curve.")

    dt_chg = max(float(t_chg[-1] - t_chg[0]), 1e-6)
    dt_dis = max(float(t_dis[-1] - t_dis[0]), 1e-6)
    ir_drop = max(0.0, float(v_chg[-1] - v_dis[1])) if len(v_dis) > 1 else 0.0
    dv = float(potential_window_v) if potential_window_v else max(float(v_dis[0] - v_dis[-1]) - ir_drop, 1e-6)

    # Note: 1 mA * 1 s / (1 mg * 1 V) = 1 F/g
    cs = (float(current_ma) * dt_dis) / (max(float(active_mass_mg), 1e-9) * dv)
    qs = (float(current_ma) * dt_dis) / (3.6 * max(float(active_mass_mg), 1e-9))
    ce = 100.0 * dt_dis / dt_chg

    # Linear fit on discharge curve V(t) -> slope dV/dt with error & residual
    lin = linear_fit_with_errors(t_dis, v_dis)
    slope = lin["slope"]
    slope_se = lin["slope_se"]
    # Cs_slope = |I / (m * dV/dt)|
    cs_fit = float(current_ma) / (max(float(active_mass_mg), 1e-9) * max(abs(slope), 1e-9))
    cs_se = cs_fit * (slope_se / max(abs(slope), 1e-9))

    gt_comp = None
    if ground_truth and "specific_capacitance_F_g" in ground_truth:
        c_true = float(ground_truth["specific_capacitance_F_g"])
        rel_err = abs(cs - c_true) / c_true
        gt_comp = {
            "passed": bool(rel_err < 0.01),
            "Cs_true_F_g": c_true,
            "Cs_measured_F_g": round(cs, 3),
            "Cs_rel_error_pct": round(rel_err * 100.0, 4),
        }

    return ModuleProcessResponse(
        module="electrochem",
        sub_type="gcd",
        title="Galvanostatic Charge-Discharge (GCD) Capacitance Analysis",
        x_label="Time / (s)",
        y_label="Potential / (V)",
        series=[
            SeriesData(name=f"{pt.filename} (GCD)", x=t.tolist(), y=v.tolist(), kind="processed"),
            SeriesData(name="Discharge Linear Fit", x=t_dis.tolist(), y=lin["y_hat"].tolist(), kind="fit", line_style="dashed"),
        ],
        fit_report=FitReport(
            model_name="GCD Discharge Slope Regression",
            equation="C_s = I·Δt / (m·ΔV)",
            r_squared=lin["r_squared"],
            rmse=lin["rmse"],
            parameters=[
                FitParameter(name="Cs_endpoint", label="Specific Capacitance C_s", value=cs, std_error=cs_se, unit="F/g"),
                FitParameter(name="Qs", label="Specific Capacity Q_s", value=qs, std_error=qs * (cs_se / max(cs, 1e-9)), unit="mAh/g"),
                FitParameter(name="active_mass_mg", label="Active Mass (经验默认值)", value=float(active_mass_mg), std_error=0.0, unit="mg", is_empirical_default_input=True),
                FitParameter(name="current_ma", label="Current (经验默认值)", value=float(current_ma), std_error=0.0, unit="mA", is_empirical_default_input=True),
            ],
            residual=ResidualData(x=t_dis.tolist(), y=lin["residual"].tolist(), x_label="Time / (s)", y_label="Residual (V)", rmse=lin["rmse"]),
            summary_metrics={
                "specific_capacitance_F_g": round(cs, 3),
                "specific_capacity_mAh_g": round(qs, 4),
                "coulombic_efficiency_pct": round(ce, 2),
                "ir_drop_V": round(ir_drop, 4),
                "discharge_time_s": round(dt_dis, 3),
            },
        ),
        table_columns=["Metric", "Value", "Std Error (±1σ)", "Unit"],
        table_rows=[
            {"Metric": "Specific Capacitance C_s", "Value": round(cs, 2), "Std Error (±1σ)": round(cs_se, 2), "Unit": "F/g"},
            {"Metric": "Specific Capacity Q_s", "Value": round(qs, 3), "Std Error (±1σ)": round(qs * cs_se / max(cs, 1e-9), 3), "Unit": "mAh/g"},
            {"Metric": "Coulombic Efficiency", "Value": round(ce, 2), "Std Error (±1σ)": "-", "Unit": "%"},
            {"Metric": "Discharge Time Δt", "Value": round(dt_dis, 2), "Std Error (±1σ)": "-", "Unit": "s"},
            {"Metric": "IR Drop", "Value": round(ir_drop, 4), "Std Error (±1σ)": "-", "Unit": "V"},
        ],
        provenance=[
            ProvenanceStep(
                step="gcd_analysis",
                parameters={"active_mass_mg": active_mass_mg, "current_ma": current_ma, "potential_window_v": dv},
                empirical_defaults=["active_mass_mg", "current_ma"],
            )
        ],
        ground_truth_comparison=gt_comp,
    )


def _process_cycling(
    files: list[tuple[str, bytes]],
    *,
    skip_rows: int | None = None,
    ground_truth: dict[str, Any] | None = None,
) -> ModuleProcessResponse:
    pt = parse_tabular_bytes(files[0][0], files[0][1], skip_rows=skip_rows)
    cyc = pt.data[:, 0]
    cap = pt.data[:, 1]
    ce = pt.data[:, 2] if pt.data.shape[1] >= 3 else np.full_like(cap, 100.0)

    first_cap = float(cap[0])
    final_cap = float(cap[-1])
    retention = 100.0 * final_cap / max(first_cap, 1e-9)
    first_ce = float(ce[0])
    avg_ce = float(np.mean(ce[1:])) if len(ce) > 1 else first_ce

    lin = linear_fit_with_errors(cyc, cap)
    gt_comp = None
    if ground_truth and "capacity_retention_pct" in ground_truth:
        r_true = float(ground_truth["capacity_retention_pct"])
        err = abs(retention - r_true)
        gt_comp = {
            "passed": bool(err < 0.5),
            "retention_true_pct": r_true,
            "retention_measured_pct": round(retention, 3),
            "retention_abs_error_pct": round(err, 4),
        }

    return ModuleProcessResponse(
        module="electrochem",
        sub_type="cycling",
        title="Long-Term Cycling Stability & Coulombic Efficiency",
        x_label="Cycle Number",
        y_label="Specific Capacity / (mAh/g)",
        y2_label="Coulombic Efficiency / (%)",
        plot_mode="dual_y",
        series=[
            SeriesData(name="Discharge Capacity", x=cyc.tolist(), y=cap.tolist(), kind="processed", show_markers=True, yaxis="y"),
            SeriesData(name="Capacity Decay Trend", x=cyc.tolist(), y=lin["y_hat"].tolist(), kind="fit", line_style="dashed", yaxis="y"),
            SeriesData(name="Coulombic Efficiency", x=cyc.tolist(), y=ce.tolist(), kind="processed", show_markers=True, yaxis="y2"),
        ],
        fit_report=FitReport(
            model_name="Linear Capacity Fade Trend",
            equation="Q(n) = Q0 + slope · n",
            r_squared=lin["r_squared"],
            rmse=lin["rmse"],
            parameters=[
                FitParameter(name="fade_rate", label="Capacity Fade per Cycle", value=lin["slope"], std_error=lin["slope_se"], unit="mAh/(g·cycle)"),
                FitParameter(name="q0", label="Extrapolated Q0", value=lin["intercept"], std_error=lin["intercept_se"], unit="mAh/g"),
            ],
            residual=ResidualData(x=cyc.tolist(), y=lin["residual"].tolist(), x_label="Cycle Number", y_label="Residual (mAh/g)", rmse=lin["rmse"]),
            summary_metrics={
                "first_cycle_capacity": round(first_cap, 2),
                "final_cycle_capacity": round(final_cap, 2),
                "capacity_retention_pct": round(retention, 2),
                "first_cycle_ce_pct": round(first_ce, 2),
                "average_ce_pct": round(avg_ce, 2),
            },
        ),
        table_columns=["Metric", "Value", "Std Error (±1σ)", "Unit"],
        table_rows=[
            {"Metric": "Cycle-1 Capacity", "Value": round(first_cap, 2), "Std Error (±1σ)": "-", "Unit": "mAh/g"},
            {"Metric": "Final Capacity", "Value": round(final_cap, 2), "Std Error (±1σ)": "-", "Unit": "mAh/g"},
            {"Metric": "Capacity Retention", "Value": round(retention, 2), "Std Error (±1σ)": "-", "Unit": "%"},
            {"Metric": "Cycle-1 CE", "Value": round(first_ce, 2), "Std Error (±1σ)": "-", "Unit": "%"},
            {"Metric": "Avg Steady CE", "Value": round(avg_ce, 2), "Std Error (±1σ)": "-", "Unit": "%"},
            {"Metric": "Fade Slope", "Value": round(lin["slope"], 4), "Std Error (±1σ)": round(lin["slope_se"], 4), "Unit": "mAh/g/cyc"},
        ],
        provenance=[ProvenanceStep(step="cycling_analysis", parameters={"total_cycles": int(len(cyc))}, empirical_defaults=[])],
        ground_truth_comparison=gt_comp,
    )


def process_electrochem(
    files: list[tuple[str, bytes]],
    *,
    sub_type: str = "eis",
    active_mass_mg: float = 1.0,
    current_ma: float = 1.0,
    scan_rate_mv_s: float = 50.0,
    potential_window_v: float | None = None,
    cv_prominence_pct: float = 10.0,
    circuit_model: str = "R(Q(RW))",
    initial_params: dict[str, float] | None = None,
    bounds_override: dict[str, list[float]] | None = None,
    skip_rows: int | None = None,
    ground_truth: dict[str, Any] | None = None,
) -> ModuleProcessResponse:
    """Unified entry point for Electrochemistry sub-modules: CV, GCD, EIS, Cycling."""
    if not files:
        raise ValueError("No files supplied to Electrochemistry module.")
    st = sub_type.lower()
    if st == "eis":
        return _process_eis(
            files,
            circuit_model=circuit_model,
            initial_params=initial_params,
            bounds_override=bounds_override,
            skip_rows=skip_rows,
            ground_truth=ground_truth,
        )
    if st == "cv":
        return _process_cv(
            files,
            active_mass_mg=active_mass_mg,
            scan_rate_mv_s=scan_rate_mv_s,
            cv_prominence_pct=cv_prominence_pct,
            skip_rows=skip_rows,
            ground_truth=ground_truth,
        )
    if st == "gcd":
        return _process_gcd(
            files,
            active_mass_mg=active_mass_mg,
            current_ma=current_ma,
            potential_window_v=potential_window_v,
            skip_rows=skip_rows,
            ground_truth=ground_truth,
        )
    if st == "cycling":
        return _process_cycling(files, skip_rows=skip_rows, ground_truth=ground_truth)
    raise ValueError(f"Unsupported electrochemistry sub_type: {sub_type}")
