from __future__ import annotations

import base64
import io
from PIL import Image
from app.modules.contact_angle import process_contact_angle
from app.synthetic.gen_contact_angle import generate_contact_angle_synthetic


def test_contact_angle_90_60_120_accuracy():
    for angle_true in (90.0, 60.0, 120.0):
        syn = generate_contact_angle_synthetic(angle_deg=angle_true)
        gt = syn["ground_truth"]
        img_bytes = syn["files"][0]["content"]

        for model in ("circle", "ellipse", "polynomial"):
            resp = process_contact_angle(
                img_bytes,
                filename=syn["files"][0]["filename"],
                threshold_mode="otsu",
                blur_kernel=5,
                auto_baseline=True,
                fit_model=model,
                ground_truth=gt,
            )
            assert resp.module == "contact_angle"
            assert resp.plot_mode == "image"
            assert resp.annotated_image_base64 is not None
            raw_png = base64.b64decode(resp.annotated_image_base64)
            im = Image.open(io.BytesIO(raw_png))
            assert im.size[0] >= 300

            assert resp.fit_report is not None
            assert len(resp.fit_report.residual.x) >= 20
            params = {p.name: p for p in resp.fit_report.parameters}
            tl = params["theta_left"]
            tr = params["theta_right"]
            assert tl.std_error > 0 and tr.std_error > 0
            assert abs(tl.value - angle_true) <= 2.0, f"{model}@{angle_true}: theta_L={tl.value}"
            assert abs(tr.value - angle_true) <= 2.0, f"{model}@{angle_true}: theta_R={tr.value}"
            assert resp.ground_truth_comparison is not None
            assert resp.ground_truth_comparison["passed"] is True
