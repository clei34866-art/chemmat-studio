from __future__ import annotations

from typing import Any
import numpy as np

from app.core.fitting import linear_fit_with_errors
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


def _normalize_array(y: np.ndarray, mode: str) -> np.ndarray:
    m = mode.lower()
    if m == "max":
        denom = float(np.max(np.abs(y))) or 1.0
        return y / denom
    if m == "minmax":
        lo, hi = float(np.min(y)), float(np.max(y))
        span = (hi - lo) or 1.0
        return (y - lo) / span
    return y.copy()


def process_xy(
    files: list[tuple[str, bytes]],
    *,
    x_col: int = 0,
    y_col: int = 1,
    normalize: str = "none",
    y_offset_step: float = 0.0,
    enable_linear_fit: bool = True,
    fit_xmin: float | None = None,
    fit_xmax: float | None = None,
    fit_series_index: int = 0,
    x_label_override: str | None = None,
    y_label_override: str | None = None,
    skip_rows: int | None = None,
    delimiter: str | None = None,
    ground_truth: dict[str, Any] | None = None,
) -> ModuleProcessResponse:
    """Process one or more arbitrary XY files with overlay, normalization, offset, and linear regression."""
    if not files:
        raise ValueError("No files supplied to XY module.")

    parsed_list = [parse_tabular_bytes(fn, content, skip_rows=skip_rows, delimiter=delimiter) for fn, content in files]
    first = parsed_list[0]
    xc = max(0, min(int(x_col), first.data.shape[1] - 1))
    yc = max(0, min(int(y_col), first.data.shape[1] - 1))

    x_label = x_label_override.strip() if x_label_override else first.columns[xc]
    y_label = y_label_override.strip() if y_label_override else first.columns[yc]

    series_out: list[SeriesData] = []
    fit_target_x: np.ndarray | None = None
    fit_target_y: np.ndarray | None = None
    fit_target_name = ""

    target_idx = max(0, min(int(fit_series_index), len(parsed_list) - 1))

    for idx, pt in enumerate(parsed_list):
        c_x = max(0, min(int(x_col), pt.data.shape[1] - 1))
        c_y = max(0, min(int(y_col), pt.data.shape[1] - 1))
        x_arr = pt.data[:, c_x]
        y_arr = _normalize_array(pt.data[:, c_y], normalize) + idx * float(y_offset_step)

        if idx == target_idx:
            fit_target_x = x_arr
            fit_target_y = y_arr
            fit_target_name = pt.filename

        series_out.append(
            SeriesData(
                name=pt.filename,
                x=x_arr.tolist(),
                y=y_arr.tolist(),
                kind="raw" if (enable_linear_fit and idx == target_idx) else "processed",
                show_markers=enable_linear_fit and idx == target_idx and len(x_arr) <= 150,
            )
        )

    fit_report: FitReport | None = None
    annotations: list[PlotAnnotation] = []
    table_columns = ["Item", "Value", "Std Error (±1σ)", "Unit"]
    table_rows: list[dict[str, Any]] = []
    gt_comp: dict[str, Any] | None = None

    if enable_linear_fit and fit_target_x is not None and fit_target_y is not None:
        mask = np.ones(len(fit_target_x), dtype=bool)
        if fit_xmin is not None:
            mask &= fit_target_x >= float(fit_xmin)
        if fit_xmax is not None:
            mask &= fit_target_x <= float(fit_xmax)

        xf = fit_target_x[mask]
        yf = fit_target_y[mask]
        order = np.argsort(xf)
        xf = xf[order]
        yf = yf[order]

        res = linear_fit_with_errors(xf, yf)
        series_out.append(
            SeriesData(
                name=f"Linear Fit ({fit_target_name})",
                x=xf.tolist(),
                y=res["y_hat"].tolist(),
                kind="fit",
                line_style="solid",
            )
        )

        fit_report = FitReport(
            model_name="Linear Regression (OLS)",
            equation="y = k·x + b",
            r_squared=res["r_squared"],
            rmse=res["rmse"],
            reduced_chi_sq=res["reduced_chi_sq"],
            parameters=[
                FitParameter(name="slope", label="Slope (k)", value=res["slope"], std_error=res["slope_se"]),
                FitParameter(name="intercept", label="Intercept (b)", value=res["intercept"], std_error=res["intercept_se"]),
            ],
            residual=ResidualData(
                x=xf.tolist(),
                y=res["residual"].tolist(),
                x_label=x_label,
                y_label=f"Residual ({y_label})",
                rmse=res["rmse"],
            ),
            summary_metrics={
                "slope": res["slope"],
                "slope_se": res["slope_se"],
                "intercept": res["intercept"],
                "intercept_se": res["intercept_se"],
                "r_squared": res["r_squared"],
                "rmse": res["rmse"],
            },
        )

        table_rows = [
            {"Item": "Slope (k)", "Value": round(res["slope"], 6), "Std Error (±1σ)": round(res["slope_se"], 6), "Unit": "dy/dx"},
            {"Item": "Intercept (b)", "Value": round(res["intercept"], 6), "Std Error (±1σ)": round(res["intercept_se"], 6), "Unit": "y"},
            {"Item": "R²", "Value": round(res["r_squared"], 6), "Std Error (±1σ)": "-", "Unit": ""},
            {"Item": "RMSE", "Value": round(res["rmse"], 6), "Std Error (±1σ)": "-", "Unit": "y"},
        ]

        mid_i = len(xf) // 2
        annotations.append(
            PlotAnnotation(
                x=float(xf[mid_i]),
                y=float(res["y_hat"][mid_i]),
                text=f"y = {res['slope']:.4f}x + {res['intercept']:.4f} (R²={res['r_squared']:.4f})",
                ax_offset=(0.0, -24.0),
            )
        )

        if ground_truth and "slope" in ground_truth and "intercept" in ground_truth:
            s_true = float(ground_truth["slope"])
            i_true = float(ground_truth["intercept"])
            s_rel = abs(res["slope"] - s_true) / max(abs(s_true), 1e-12)
            i_rel = abs(res["intercept"] - i_true) / max(abs(i_true), 1e-12)
            gt_comp = {
                "passed": bool(s_rel < 0.02 and i_rel < 0.02),
                "slope_true": s_true,
                "slope_measured": round(res["slope"], 6),
                "slope_rel_error_pct": round(s_rel * 100.0, 4),
                "intercept_true": i_true,
                "intercept_measured": round(res["intercept"], 6),
                "intercept_rel_error_pct": round(i_rel * 100.0, 4),
            }

    return ModuleProcessResponse(
        module="xy",
        sub_type="general_xy",
        title="Universal XY Plot & Linear Fit",
        x_label=x_label,
        y_label=y_label,
        series=series_out,
        annotations=annotations,
        fit_report=fit_report,
        table_columns=table_columns,
        table_rows=table_rows,
        provenance=[
            ProvenanceStep(
                step="xy_processing",
                parameters={
                    "x_col": xc,
                    "y_col": yc,
                    "normalize": normalize,
                    "y_offset_step": y_offset_step,
                    "enable_linear_fit": enable_linear_fit,
                    "fit_xmin": fit_xmin,
                    "fit_xmax": fit_xmax,
                    "fit_series_index": target_idx,
                },
                empirical_defaults=[],
            )
        ],
        ground_truth_comparison=gt_comp,
    )
