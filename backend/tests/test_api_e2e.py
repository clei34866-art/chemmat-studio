from __future__ import annotations

import base64
import io
import json
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def test_health_and_all_six_modules_end_to_end():
    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["status"] == "ok"

    cases = [
        ("xy", {}, "xy"),
        ("xrd", {}, "xrd"),
        ("xps", {}, "xps"),
        ("contact_angle", {"angle_deg": 90.0}, "contact_angle"),
        ("electrochem", {"sub_type": "eis"}, "electrochem"),
        ("spectroscopy", {"sub_type": "uvvis"}, "spectroscopy"),
    ]

    for mod, query, expected_mod in cases:
        syn_resp = client.get(f"/api/synthetic/{mod}", params=query)
        assert syn_resp.status_code == 200
        syn = syn_resp.json()
        assert len(syn["files"]) >= 1

        # 1. Auto-detect first synthetic file
        first_f = syn["files"][0]
        raw_bytes = base64.b64decode(first_f["content_base64"])
        det_resp = client.post(
            "/api/detect",
            files={"file": (first_f["filename"], raw_bytes, first_f["mime_type"])},
        )
        assert det_resp.status_code == 200
        assert det_resp.json()["module"] == expected_mod

        # 2. Process module with synthetic ground truth
        upload_files = [
            ("files", (f["filename"], base64.b64decode(f["content_base64"]), f["mime_type"]))
            for f in syn["files"]
        ]
        proc_resp = client.post(
            f"/api/process/{mod}",
            files=upload_files,
            data={
                "params_json": json.dumps(syn["default_params"]),
                "ground_truth_json": json.dumps(syn["ground_truth"]),
            },
        )
        assert proc_resp.status_code == 200, proc_resp.text
        proc_json = proc_resp.json()
        assert proc_json["module"] == expected_mod
        assert proc_json["fit_report"] is not None
        assert proc_json["ground_truth_comparison"]["passed"] is True

        # 3. Export white-background PNG across journal styles + XLSX data
        for style in ("nature", "adv_mater", "chinese_core"):
            fig_resp = client.post(
                "/api/export/figure",
                json={"result": proc_json, "journal_style": style, "fmt": "png", "dpi": 300},
            )
            assert fig_resp.status_code == 200
            im = Image.open(io.BytesIO(fig_resp.content)).convert("RGB")
            w, h_px = im.size
            assert im.getpixel((0, 0)) == (255, 255, 255)
            assert im.getpixel((w - 1, h_px - 1)) == (255, 255, 255)

        xlsx_resp = client.post(
            "/api/export/data",
            json={"result": proc_json, "fmt": "xlsx"},
        )
        assert xlsx_resp.status_code == 200
        assert len(xlsx_resp.content) > 1000
