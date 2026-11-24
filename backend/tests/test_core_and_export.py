from __future__ import annotations

import io
import zipfile
import numpy as np
import openpyxl
from PIL import Image

from app.core.parser import parse_tabular_bytes
from app.core.detector import detect_file_type
from app.core.baseline import (
    asls_baseline,
    snip_baseline,
    poly_baseline,
    rubberband_baseline,
    shirley_baseline,
)
from app.core.fitting import (
    pseudo_voigt,
    linear_fit_with_errors,
    nlls_fit_with_errors,
)
from app.core.exporter import render_publication_figure, export_processed_data
from app.schemas.models import (
    FitParameter,
    FitReport,
    ModuleProcessResponse,
    ProvenanceStep,
    ResidualData,
    SeriesData,
)


def test_parse_csv_tsv_whitespace_comments_and_xlsx():
    csv_bytes = b"# comment line\nX,Y1,Y2\n1.0,2.0,3.0\n2.0,4.0,6.0\n"
    parsed_csv = parse_tabular_bytes("sample.csv", csv_bytes)
    assert parsed_csv.columns == ["X", "Y1", "Y2"]
    assert np.allclose(parsed_csv.data[:, 0], [1.0, 2.0])

    txt_bytes = b"Potential/V\tCurrent/mA\n-0.5\t0.12\n0.0\t1.45\n0.5\t-0.31\n"
    parsed_txt = parse_tabular_bytes("cv_scan.txt", txt_bytes)
    assert parsed_txt.columns == ["Potential/V", "Current/mA"]
    assert parsed_txt.data.shape == (3, 2)

    xy_bytes = b"10.0  100.0\n10.2  105.0\n10.4  110.0\n"
    parsed_xy = parse_tabular_bytes("pattern.xy", xy_bytes)
    assert parsed_xy.data.shape == (3, 2)
    assert len(parsed_xy.columns) == 2

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Wavenumber (cm^-1)", "Intensity"])
    ws.append([520.0, 1200.0])
    ws.append([1350.0, 800.0])
    buf = io.BytesIO()
    wb.save(buf)
    parsed_xlsx = parse_tabular_bytes("raman.xlsx", buf.getvalue())
    assert parsed_xlsx.columns == ["Wavenumber (cm^-1)", "Intensity"]
    assert np.allclose(parsed_xlsx.data[:, 0], [520.0, 1350.0])


def test_auto_detector_all_six_modules():
    # 1. Image -> Contact Angle
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    res_ca = detect_file_type("droplet_90deg.png", img_buf.getvalue())
    assert res_ca.module == "contact_angle"
    assert res_ca.is_image is True

    # 2. XRD
    xrd = b"2Theta (deg),Intensity (counts)\n15.0,120\n28.4,3500\n47.3,1900\n"
    assert detect_file_type("sample_xrd.csv", xrd).module == "xrd"

    # 3. XPS
    xps = b"Binding Energy (eV),Intensity (cps)\n292.0,400\n284.8,5200\n280.0,390\n"
    assert detect_file_type("C1s_region.csv", xps).module == "xps"

    # 4. Electrochem CV, GCD, EIS, Cycling
    cv = b"Potential (V),Current (A/g)\n-0.8,-1.2\n0.0,2.5\n0.8,3.1\n0.0,-2.0\n-0.8,-1.2\n"
    det_cv = detect_file_type("test.csv", cv)
    assert det_cv.module == "electrochem" and det_cv.sub_type == "cv"

    eis = b"Freq (Hz),Z' (Ohm),-Z'' (Ohm)\n100000,1.2,0.1\n100,12.5,8.4\n0.01,35.0,22.0\n"
    det_eis = detect_file_type("nyquist.csv", eis)
    assert det_eis.module == "electrochem" and det_eis.sub_type == "eis"

    gcd = b"Time (s),Potential (V)\n0.0,0.0\n10.0,0.5\n20.0,1.0\n30.0,0.5\n40.0,0.0\n"
    det_gcd = detect_file_type("galvanostatic.csv", gcd)
    assert det_gcd.module == "electrochem" and det_gcd.sub_type == "gcd"

    cyc = b"Cycle,Capacity (mAh/g),Coulombic Efficiency (%)\n1,180.2,94.5\n2,179.0,99.4\n"
    det_cyc = detect_file_type("stability.csv", cyc)
    assert det_cyc.module == "electrochem" and det_cyc.sub_type == "cycling"

    # 5. Spectroscopy UV-Vis, FTIR, Raman
    uv = b"Wavelength (nm),Absorbance\n250,1.8\n350,0.9\n500,0.05\n"
    det_uv = detect_file_type("tio2.csv", uv)
    assert det_uv.module == "spectroscopy" and det_uv.sub_type == "uvvis"

    ftir = b"Wavenumber (cm^-1),Transmittance (%)\n4000,95.0\n1710,32.0\n400,92.0\n"
    det_ftir = detect_file_type("polymer.csv", ftir)
    assert det_ftir.module == "spectroscopy" and det_ftir.sub_type == "ftir"

    raman = b"Raman Shift (cm^-1),Intensity\n200,150\n520.5,4200\n1582.0,3100\n"
    det_raman = detect_file_type("graphene.csv", raman)
    assert det_raman.module == "spectroscopy" and det_raman.sub_type == "raman"

    # 6. Universal XY fallback
    xy = b"Stress,Strain\n0.1,12.3\n0.2,24.1\n0.3,35.9\n"
    assert detect_file_type("generic_data.csv", xy).module == "xy"


def test_baselines_and_fitting_precision():
    x = np.linspace(10.0, 60.0, 400)
    bg_true = 120.0 + 1.5 * x - 0.02 * (x - 30.0) ** 2
    peak = pseudo_voigt(x, area=600.0, center=35.0, fwhm=2.0, eta=0.35)
    # Check normalized area of pseudo_voigt equals area parameter
    assert abs(np.trapezoid(peak, x) - 600.0) / 600.0 < 0.03

    y = bg_true + peak
    asls_bg = asls_baseline(y, lam=1e5, p=0.005, n_iter=10)
    snip_bg = snip_baseline(y, max_half_window=25)
    poly_bg = poly_baseline(x, y, degree=2, n_iter=10)
    rb_bg = rubberband_baseline(x, y)
    for b in (asls_bg, snip_bg, poly_bg, rb_bg):
        assert b.shape == y.shape
        assert np.median(np.abs(b - bg_true)) < 25.0

    # Shirley baseline with true secondary-electron step rising toward higher BE
    be = np.linspace(292.0, 280.0, 241)
    pv = pseudo_voigt(be, area=2000.0, center=284.8, fwhm=1.2, eta=0.25)
    # Integral from low BE (be[-1]=280) up to each BE gives step shape rising toward 292 eV
    order_asc = np.argsort(be)
    cum = np.cumsum(pv[order_asc])
    cum = cum / cum[-1]
    true_step = np.empty_like(pv)
    true_step[order_asc] = 100.0 + 300.0 * cum
    spec = true_step + pv
    sh = shirley_baseline(be, spec, tol=1e-6, max_iter=50)
    assert sh.shape == spec.shape
    assert sh[0] > sh[-1]  # step rises toward higher BE (index 0 = 292 eV)
    assert np.max(np.abs(sh - true_step)) < 25.0

    # Linear fit & NLLS fit with SE and residual
    xl = np.linspace(0, 10, 50)
    yl = 3.2 * xl - 0.7
    fit = linear_fit_with_errors(xl, yl)
    assert abs(fit["slope"] - 3.2) < 1e-8
    assert abs(fit["intercept"] + 0.7) < 1e-8
    assert fit["r_squared"] > 0.999999

    rng = np.random.default_rng(42)
    yn = pseudo_voigt(x, area=600.0, center=35.0, fwhm=2.0, eta=0.35) + rng.normal(0, 1.5, len(x))
    p_fit, p_se, r2, rmse, chi2, resid = nlls_fit_with_errors(
        lambda xv, a, c, w, e: pseudo_voigt(xv, a, c, w, e),
        x,
        yn,
        p0=[500.0, 34.7, 2.3, 0.5],
        bounds=([10.0, 25.0, 0.2, 0.0], [5000.0, 45.0, 10.0, 1.0]),
    )
    assert abs(p_fit[1] - 35.0) < 0.05
    assert abs(p_fit[2] - 2.0) < 0.08
    assert np.all(p_se > 0)
    assert r2 > 0.99
    assert resid.shape == x.shape


def test_exporter_three_journal_styles_pure_white_bg_and_data_formats():
    x = np.linspace(0, 10, 50)
    y = 2.0 * x + 1.0
    resp = ModuleProcessResponse(
        module="xy",
        title="线性拟合示例 / Linear Fit",
        x_label="Concentration / (mol/L)",
        y_label="Absorbance / (a.u.)",
        series=[
            SeriesData(name="Measured", x=x.tolist(), y=(y + 0.05).tolist(), kind="raw", show_markers=True),
            SeriesData(name="Linear Fit", x=x.tolist(), y=y.tolist(), kind="fit"),
        ],
        fit_report=FitReport(
            model_name="Linear",
            equation="y = k·x + b",
            r_squared=0.999,
            rmse=0.05,
            parameters=[
                FitParameter(name="k", label="Slope k", value=2.0, std_error=0.01, unit="L/mol"),
                FitParameter(name="b", label="Intercept b", value=1.0, std_error=0.02, unit="a.u."),
            ],
            residual=ResidualData(x=x.tolist(), y=np.full_like(x, 0.05).tolist(), x_label="Concentration", y_label="Residual", rmse=0.05),
        ),
        table_columns=["Parameter", "Value", "Std Error"],
        table_rows=[{"Parameter": "k", "Value": 2.0, "Std Error": 0.01}],
        provenance=[ProvenanceStep(step="linear_fit", parameters={"xmin": 0, "xmax": 10}, empirical_defaults=[])],
    )

    for style in ("nature", "adv_mater", "chinese_core"):
        png_bytes = render_publication_figure(resp, journal_style=style, fmt="png", dpi=300)
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        w, h = img.size
        assert w > 600 and h > 400
        for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            assert img.getpixel(corner) == (255, 255, 255), f"{style} corner {corner} not pure white!"

        svg_bytes = render_publication_figure(resp, journal_style=style, fmt="svg", dpi=300)
        assert b"<svg" in svg_bytes

        pdf_bytes = render_publication_figure(resp, journal_style=style, fmt="pdf", dpi=300)
        assert pdf_bytes.startswith(b"%PDF")

    csv_out = export_processed_data(resp, fmt="csv")
    assert b"Concentration" in csv_out

    xlsx_out = export_processed_data(resp, fmt="xlsx")
    with zipfile.ZipFile(io.BytesIO(xlsx_out)) as zf:
        assert "xl/workbook.xml" in zf.namelist()
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_out))
    assert "Curves" in wb.sheetnames
    assert "Fit_Parameters" in wb.sheetnames
    assert "Provenance" in wb.sheetnames
