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


def test_manual_contact_angle_geometry():
    """User-placed lines at known angles must come back exact."""
    import cv2
    import numpy as np

    from app.modules.contact_angle import manual_contact_angle

    img = np.full((600, 800, 3), 255, np.uint8)
    ok, enc = cv2.imencode(".png", img)
    assert ok
    res = manual_contact_angle(
        enc.tobytes(),
        baseline=[0, 300, 800, 300],
        tangent_left=[300, 300, 350, 213.4],   # 60 deg interior
        tangent_right=[500, 300, 550, 213.4],  # 120 deg interior
    )
    assert abs(res["theta_left_deg"] - 60.0) < 0.1
    assert abs(res["theta_right_deg"] - 120.0) < 0.1
    assert abs(res["theta_mean_deg"] - 90.0) < 0.1
    assert res["annotated_image_base64"]


def test_manual_contact_angle_arc_geometry():
    """Three points on a known circle must reproduce its tangent angles."""
    import cv2
    import numpy as np

    from app.modules.contact_angle import manual_contact_angle_arc

    img = np.full((600, 800, 3), 255, np.uint8)
    ok, enc = cv2.imencode(".png", img)
    assert ok
    # Circle center (400, 330), R = 100; baseline y = 372
    # -> theta = 90 + asin(42 / 100) = 114.83 deg on both sides.
    res = manual_contact_angle_arc(
        enc.tobytes(),
        baseline=[0, 372, 800, 372],
        arc_points=[400, 230, 329.3, 259.3, 470.7, 259.3],
    )
    assert abs(res["theta_left_deg"] - 114.83) < 0.2
    assert abs(res["theta_right_deg"] - 114.83) < 0.2
    assert abs(res["circle_radius"] - 100.0) < 0.5
    assert res["annotated_image_base64"]


def test_manual_arc_three_point_flow():
    """User flow: fix left/right contact points, pull the arc through a
    third profile point. L/R/pull on circle (400,330) R=100, baseline
    through L-R at y=372 -> theta = 114.83 deg both sides."""
    import cv2
    import numpy as np

    from app.modules.contact_angle import manual_contact_angle_arc

    img = np.full((600, 800, 3), 255, np.uint8)
    ok, enc = cv2.imencode(".png", img)
    assert ok
    res = manual_contact_angle_arc(
        enc.tobytes(),
        baseline=[309.3, 372, 490.7, 372],
        arc_points=[309.3, 372, 490.7, 372, 400, 230],
    )
    assert abs(res["theta_left_deg"] - 114.83) < 0.2
    assert abs(res["theta_right_deg"] - 114.83) < 0.2
    assert abs(res["contact_left"][0] - 309.3) < 1.0
    assert abs(res["contact_right"][0] - 490.7) < 1.0
