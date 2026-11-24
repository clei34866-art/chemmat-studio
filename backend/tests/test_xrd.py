from __future__ import annotations

from app.modules.xrd import process_xrd
from app.synthetic.gen_xrd import generate_xrd_synthetic


def test_xrd_synthetic_peaks_and_scherrer_precision():
    syn = generate_xrd_synthetic()
    gt = syn["ground_truth"]
    files = [(f["filename"], f["content"]) for f in syn["files"]]

    resp = process_xrd(
        files,
        smooth_enabled=True,
        smooth_window=11,
        smooth_polyorder=3,
        baseline_method="asls",
        baseline_lam=1e5,
        baseline_p=0.01,
        display_mode="overlay",
        prominence_pct=8.0,
        min_distance_deg=2.0,
        wavelength_angstrom=gt["wavelength_angstrom"],
        k_factor=gt["k_factor"],
        instrumental_fwhm_deg=gt["instrumental_fwhm_deg"],
        instrumental_method="gaussian",
        ground_truth=gt,
    )

    assert resp.module == "xrd"
    assert resp.fit_report is not None
    assert len(resp.fit_report.residual.x) > 100
    assert len(resp.table_rows) >= 3

    detected_2theta = [row["2θ (°)"] for row in resp.table_rows]
    for true_pk in gt["peaks_2theta"]:
        nearest = min(detected_2theta, key=lambda x: abs(x - true_pk))
        assert abs(nearest - true_pk) < 0.05

    # Check Scherrer crystallite size on main peaks within 5% of 22.0 nm
    sizes = [row["D_Scherrer (nm)"] for row in resp.table_rows if row["D_Scherrer (nm)"] is not None]
    assert len(sizes) >= 3
    mean_d = sum(sizes[:3]) / 3.0
    assert abs(mean_d - gt["crystallite_size_nm"]) / gt["crystallite_size_nm"] < 0.05
    assert any(p.is_empirical_default_input for p in resp.fit_report.parameters)
    assert resp.ground_truth_comparison is not None
    assert resp.ground_truth_comparison["passed"] is True


def test_xrd_stacked_and_waterfall_modes():
    syn = generate_xrd_synthetic()
    files = [(f["filename"], f["content"]) for f in syn["files"]]

    resp_stacked = process_xrd(files, display_mode="stacked", stack_offset_pct=30.0)
    assert resp_stacked.plot_mode == "2d"
    assert len(resp_stacked.series) >= 2

    resp_wf = process_xrd(files, display_mode="waterfall_3d")
    assert resp_wf.plot_mode == "waterfall_3d"
    assert all(s.z is not None for s in resp_wf.series)
