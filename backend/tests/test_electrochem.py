from __future__ import annotations

from app.modules.electrochem import process_electrochem
from app.synthetic.gen_electrochem import generate_electrochem_synthetic


def test_electrochem_eis_cnls_and_nyquist():
    syn = generate_electrochem_synthetic("eis")
    gt = syn["ground_truth"]
    files = [(f["filename"], f["content"]) for f in syn["files"]]

    resp = process_electrochem(files, sub_type="eis", circuit_model="R(Q(RW))", ground_truth=gt)
    assert resp.module == "electrochem"
    assert resp.sub_type == "eis"
    assert resp.equal_aspect is True
    assert resp.fit_report is not None
    assert resp.fit_report.residual.y_imag is not None
    params = {p.name: p for p in resp.fit_report.parameters}
    for k in ("Rs", "Q", "n", "Rct", "Aw"):
        assert abs(params[k].value - gt[k]) / gt[k] < 0.03
        assert params[k].std_error > 0
    assert resp.ground_truth_comparison["passed"] is True


def test_electrochem_cv_gcd_and_cycling():
    # CV
    syn_cv = generate_electrochem_synthetic("cv")
    resp_cv = process_electrochem([(syn_cv["files"][0]["filename"], syn_cv["files"][0]["content"])], sub_type="cv", ground_truth=syn_cv["ground_truth"])
    assert resp_cv.fit_report is not None
    m_cv = resp_cv.fit_report.summary_metrics
    assert abs(m_cv["E_pa_V"] - 0.32) < 0.015
    assert abs(m_cv["E_pc_V"] - 0.22) < 0.015

    # GCD
    syn_gcd = generate_electrochem_synthetic("gcd")
    resp_gcd = process_electrochem(
        [(syn_gcd["files"][0]["filename"], syn_gcd["files"][0]["content"])],
        sub_type="gcd",
        active_mass_mg=1.0,
        current_ma=1.0,
        ground_truth=syn_gcd["ground_truth"],
    )
    assert resp_gcd.fit_report is not None
    cs = resp_gcd.fit_report.summary_metrics["specific_capacitance_F_g"]
    assert abs(cs - 250.0) / 250.0 < 0.01

    # Cycling
    syn_cyc = generate_electrochem_synthetic("cycling")
    resp_cyc = process_electrochem(
        [(syn_cyc["files"][0]["filename"], syn_cyc["files"][0]["content"])],
        sub_type="cycling",
        ground_truth=syn_cyc["ground_truth"],
    )
    assert resp_cyc.plot_mode == "dual_y"
    assert resp_cyc.fit_report is not None
    ret = resp_cyc.fit_report.summary_metrics["capacity_retention_pct"]
    assert abs(ret - 90.0) < 0.5
