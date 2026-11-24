from __future__ import annotations

from app.modules.xps import process_xps
from app.synthetic.gen_xps import generate_xps_synthetic


def test_xps_synthetic_charge_shirley_deconv_and_rsf():
    syn = generate_xps_synthetic()
    gt = syn["ground_truth"]
    files = [(f["filename"], f["content"]) for f in syn["files"]]

    resp = process_xps(
        files,
        auto_charge_correct=True,
        ref_be_ev=284.8,
        bg_method="shirley",
        n_peaks=3,
        rsf_entries=gt["rsf_test_quant"]["elements"],
        ground_truth=gt,
    )

    assert resp.module == "xps"
    assert resp.invert_x is True
    assert resp.fit_report is not None
    assert resp.fit_report.r_squared > 0.99
    assert len(resp.fit_report.residual.x) > 100

    shift_val = resp.fit_report.summary_metrics["charge_shift_ev"]
    assert abs(shift_val - gt["charge_shift_ev"]) < 0.05

    # Compare sorted peak centers and FWHMs against ground truth
    peak_rows = [r for r in resp.table_rows if r.get("Section", "Peak") == "Peak"]
    assert len(peak_rows) == 3
    peak_rows_sorted = sorted(peak_rows, key=lambda r: r["BE (eV)"])
    gt_sorted = sorted(gt["peaks_corrected"], key=lambda p: p["center"])

    for est, exp in zip(peak_rows_sorted, gt_sorted):
        assert abs(est["BE (eV)"] - exp["center"]) < 0.08
        assert abs(est["FWHM (eV)"] - exp["fwhm"]) / exp["fwhm"] < 0.05
        assert est["BE ±SE"] > 0 and est["FWHM ±SE"] > 0 and est["Area ±SE"] > 0

    # Atomic percentage quantification using supplied RSF entries
    quant = resp.fit_report.summary_metrics["atomic_percentages"]
    assert abs(quant["C 1s"] - 60.0) < 2.0
    assert abs(quant["O 1s"] - 40.0) < 2.0
    assert resp.ground_truth_comparison is not None
    assert resp.ground_truth_comparison["passed"] is True
