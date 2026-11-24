from __future__ import annotations

import numpy as np
from app.modules.xy import process_xy
from app.synthetic.gen_xy import generate_xy_synthetic


def test_xy_synthetic_linear_fit_and_overlay():
    syn = generate_xy_synthetic()
    gt = syn["ground_truth"]
    files = [(f["filename"], f["content"]) for f in syn["files"]]

    resp = process_xy(
        files,
        x_col=0,
        y_col=1,
        normalize="none",
        y_offset_step=0.0,
        enable_linear_fit=True,
        fit_series_index=0,
        ground_truth=gt,
    )

    assert resp.module == "xy"
    assert len(resp.series) >= 3  # 2 data curves + 1 fit line
    assert resp.fit_report is not None
    params = {p.name: p for p in resp.fit_report.parameters}
    k = params["slope"]
    b = params["intercept"]

    assert abs(k.value - gt["slope"]) / abs(gt["slope"]) < 0.015
    assert abs(b.value - gt["intercept"]) / abs(gt["intercept"]) < 0.02
    assert k.std_error > 0 and b.std_error > 0
    assert resp.fit_report.r_squared > 0.99
    assert len(resp.fit_report.residual.x) == 80
    assert resp.ground_truth_comparison is not None
    assert resp.ground_truth_comparison["passed"] is True


def test_xy_normalization_offset_and_subrange():
    syn = generate_xy_synthetic()
    files = [(f["filename"], f["content"]) for f in syn["files"]]

    resp = process_xy(
        files,
        normalize="minmax",
        y_offset_step=1.2,
        enable_linear_fit=True,
        fit_xmin=2.0,
        fit_xmax=8.0,
        fit_series_index=0,
        x_label_override="Custom X",
        y_label_override="Custom Y",
    )
    assert resp.x_label == "Custom X"
    assert resp.y_label == "Custom Y"
    assert resp.fit_report is not None
    assert all(2.0 <= xv <= 8.0 for xv in resp.fit_report.residual.x)
    # Second series should be shifted upward by 1.2
    s1 = resp.series[1]
    assert np.min(s1.y) >= 1.19
