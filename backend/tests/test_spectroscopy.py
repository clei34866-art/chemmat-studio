from __future__ import annotations

from app.modules.spectroscopy import process_spectroscopy
from app.synthetic.gen_spectroscopy import generate_spectroscopy_synthetic


def test_spectroscopy_uvvis_tauc_bandgap():
    syn = generate_spectroscopy_synthetic("uvvis")
    gt = syn["ground_truth"]
    files = [(f["filename"], f["content"]) for f in syn["files"]]

    resp = process_spectroscopy(
        files,
        sub_type="uvvis",
        enable_tauc=True,
        tauc_gamma=0.5,
        path_length_cm=1.0,
        ground_truth=gt,
    )
    assert resp.module == "spectroscopy"
    assert resp.sub_type == "uvvis"
    assert resp.fit_report is not None
    params = {p.name: p for p in resp.fit_report.parameters}
    eg = params["Eg_eV"]
    assert abs(eg.value - gt["band_gap_ev"]) < 0.05
    assert eg.std_error > 0
    assert len(resp.fit_report.residual.x) >= 10
    assert resp.ground_truth_comparison is not None
    assert resp.ground_truth_comparison["passed"] is True


def test_spectroscopy_raman_and_ftir_peaks():
    syn_r = generate_spectroscopy_synthetic("raman")
    resp_r = process_spectroscopy(
        [(syn_r["files"][0]["filename"], syn_r["files"][0]["content"])],
        sub_type="raman",
        baseline_method="asls",
        prominence_pct=8.0,
        ground_truth=syn_r["ground_truth"],
    )
    assert resp_r.fit_report is not None
    detected_r = [r["Position"] for r in resp_r.table_rows]
    for pk in syn_r["ground_truth"]["peaks_cm1"]:
        assert min(abs(d - pk) for d in detected_r) < 2.0

    syn_f = generate_spectroscopy_synthetic("ftir")
    resp_f = process_spectroscopy(
        [(syn_f["files"][0]["filename"], syn_f["files"][0]["content"])],
        sub_type="ftir",
        ftir_mode="absorbance",
        baseline_method="asls",
        prominence_pct=8.0,
        ground_truth=syn_f["ground_truth"],
    )
    assert resp_f.invert_x is True
    assert resp_f.fit_report is not None
    detected_f = [r["Position"] for r in resp_f.table_rows]
    for pk in syn_f["ground_truth"]["peaks_cm1"]:
        assert min(abs(d - pk) for d in detected_f) < 4.0
