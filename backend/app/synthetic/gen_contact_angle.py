from __future__ import annotations

import io
from typing import Any
import numpy as np
from PIL import Image


def generate_contact_angle_synthetic(angle_deg: float = 90.0) -> dict[str, Any]:
    """Render an anti-aliased synthetic sessile droplet PNG with exact geometric contact angle."""
    w, h = 640, 480
    ss = 4  # 4x supersampling for clean anti-aliased subpixel edges
    ws, hs = w * ss, h * ss

    y_base_s = 340.0 * ss
    xc_s = 320.0 * ss
    r_s = 135.0 * ss
    yc_s = y_base_s + r_s * np.cos(np.radians(angle_deg))

    yy, xx = np.mgrid[0:hs, 0:ws]
    canvas = np.full((hs, ws), 236.0, dtype=np.float32)

    # Dark flat substrate below y_base
    substrate_mask = yy >= y_base_s
    canvas[substrate_mask] = 28.0

    # Dark droplet circle clipped to y <= y_base
    droplet_mask = (((xx - xc_s) ** 2 + (yy - yc_s) ** 2) <= r_s ** 2) & (yy <= y_base_s)
    canvas[droplet_mask] = 34.0

    img_hi = Image.fromarray(canvas.astype(np.uint8), mode="L")
    img_aa = img_hi.resize((w, h), Image.Resampling.LANCZOS)

    rng = np.random.default_rng(42)
    arr = np.asarray(img_aa, dtype=np.float32) + rng.normal(0.0, 2.0, size=(h, w))
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    rgb = Image.fromarray(np.stack([arr, arr, arr], axis=-1), mode="RGB")

    buf = io.BytesIO()
    rgb.save(buf, format="PNG")

    return {
        "files": [{"filename": f"droplet_{angle_deg:.0f}deg.png", "content": buf.getvalue()}],
        "ground_truth": {
            "theta_left_deg": float(angle_deg),
            "theta_right_deg": float(angle_deg),
            "theta_mean_deg": float(angle_deg),
        },
        "default_params": {
            "threshold_mode": "otsu",
            "blur_kernel": 5,
            "auto_baseline": True,
            "baseline_tilt_deg": 0.0,
            "fit_model": "ellipse",
            "poly_order": 3,
        },
    }
