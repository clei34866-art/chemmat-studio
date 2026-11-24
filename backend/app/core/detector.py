from __future__ import annotations

import io
import numpy as np
from PIL import Image

from app.core.parser import is_image_file, parse_tabular_bytes
from app.schemas.models import DetectResponse


def detect_file_type(filename: str, content: bytes) -> DetectResponse:
    """Automatically infer the analytical module and sub-type from filename, headers, and values."""
    name_low = filename.lower()

    if is_image_file(filename, content):
        try:
            with Image.open(io.BytesIO(content)) as im:
                w, h = im.size
            reason = f"检测到图像文件 ({w}×{h} px)，自动判别为接触角液滴图像分析模块。"
        except Exception:
            reason = "检测到图像文件扩展名，自动判别为接触角模块。"
        return DetectResponse(
            module="contact_angle",
            sub_type="droplet_image",
            confidence=0.98,
            reason=reason,
            is_image=True,
            columns=["Image (RGB)"],
            preview_rows=[],
            suggested_params={"fit_model": "ellipse"},
        )

    parsed = parse_tabular_bytes(filename, content)
    cols_low = [c.lower() for c in parsed.columns]
    col_joined = " | ".join(cols_low)
    x = parsed.data[:, 0]
    y = parsed.data[:, 1]
    x_min, x_max = float(np.nanmin(x)), float(np.nanmax(x))
    y_min, y_max = float(np.nanmin(y)), float(np.nanmax(y))

    # 1. EIS (Electrochemical Impedance Spectroscopy)
    if (
        any(k in col_joined for k in ("z'", "z''", "z_re", "z_im", "zreal", "zimag", "nyquist", "impedance"))
        or ("eis" in name_low or "nyquist" in name_low)
    ):
        return DetectResponse(
            module="electrochem",
            sub_type="eis",
            confidence=0.96,
            reason=f"表头或文件名包含阻抗特征 ({', '.join(parsed.columns[:3])})，自动识别为电化学 EIS 模块。",
            columns=parsed.columns,
            preview_rows=parsed.preview_rows,
            suggested_params={"sub_type": "eis"},
        )

    # 2. XPS
    if (
        any(k in col_joined for k in ("binding energy", "be (", "be/", "kinetic energy", "cps", "counts/s"))
        or any(k in name_low for k in ("xps", "c1s", "o1s", "n1s", "s2p", "fe2p", "ti2p", "survey"))
        or (len(x) > 10 and x[0] > x[-1] and 50.0 <= x_max <= 1500.0 and "wavenumber" not in col_joined and "raman" not in col_joined)
    ):
        return DetectResponse(
            module="xps",
            sub_type="narrow_scan",
            confidence=0.95,
            reason=f"结合能特征或 XPS 轨道命名 ({parsed.columns[0]}, 范围 {x_min:.1f}–{x_max:.1f} eV)，识别为 XPS 模块。",
            columns=parsed.columns,
            preview_rows=parsed.preview_rows,
            suggested_params={"ref_be_ev": 284.8},
        )

    # 3. XRD
    if (
        any(k in col_joined for k in ("2theta", "2-theta", "two_theta", "2θ", "theta"))
        or "xrd" in name_low
        or filename.lower().endswith(".xy")
    ):
        return DetectResponse(
            module="xrd",
            sub_type="powder_xrd",
            confidence=0.95,
            reason=f"检测到衍射角 2θ 特征 ({parsed.columns[0]}, 范围 {x_min:.1f}°–{x_max:.1f}°)，识别为 XRD 模块。",
            columns=parsed.columns,
            preview_rows=parsed.preview_rows,
            suggested_params={"wavelength_angstrom": 1.5406, "k_factor": 0.89},
        )

    # 4. Spectroscopy: Raman / FTIR / UV-Vis
    if any(k in col_joined for k in ("raman", "shift")) or "raman" in name_low:
        return DetectResponse(
            module="spectroscopy",
            sub_type="raman",
            confidence=0.95,
            reason=f"表头或文件名包含 Raman 特征 ({parsed.columns[0]})，识别为光谱-拉曼 (Raman) 子模块。",
            columns=parsed.columns,
            preview_rows=parsed.preview_rows,
            suggested_params={"sub_type": "raman"},
        )

    if (
        any(k in col_joined for k in ("wavenumber", "transmittance", "%t", "cm-1", "cm^-1"))
        or "ftir" in name_low
        or "ir_" in name_low
    ):
        sub = "ftir"
        if "raman" in name_low:
            sub = "raman"
        return DetectResponse(
            module="spectroscopy",
            sub_type=sub,
            confidence=0.92,
            reason=f"波数/透射率特征 ({parsed.columns[0]}, 范围 {x_min:.0f}–{x_max:.0f})，识别为光谱-{sub.upper()} 子模块。",
            columns=parsed.columns,
            preview_rows=parsed.preview_rows,
            suggested_params={"sub_type": sub},
        )

    if (
        any(k in col_joined for k in ("wavelength", "absorbance", "uv-vis", "uvvis", "reflectance", "nm"))
        or any(k in name_low for k in ("uvvis", "uv-vis", "uv_vis", "tauc", "abs"))
    ):
        return DetectResponse(
            module="spectroscopy",
            sub_type="uvvis",
            confidence=0.94,
            reason=f"波长/吸光度特征 ({parsed.columns[0]}, 范围 {x_min:.0f}–{x_max:.0f} nm)，识别为光谱-UV-Vis 子模块。",
            columns=parsed.columns,
            preview_rows=parsed.preview_rows,
            suggested_params={"sub_type": "uvvis"},
        )

    # 5. Electrochemistry: Cycling, CV, GCD
    if (
        any(k in col_joined for k in ("cycle", "coulombic", "efficiency", "retention"))
        or "cycling" in name_low
        or "cycle" in name_low
    ):
        return DetectResponse(
            module="electrochem",
            sub_type="cycling",
            confidence=0.93,
            reason=f"包含循环圈数与容量/库仑效率特征 ({', '.join(parsed.columns[:3])})，识别为电化学-长循环子模块。",
            columns=parsed.columns,
            preview_rows=parsed.preview_rows,
            suggested_params={"sub_type": "cycling"},
        )

    if (
        any(k in col_joined for k in ("potential", "voltage", "ewe", "v vs"))
        and any(k in col_joined for k in ("current", "i (", "ma", "a/g"))
    ) or "cv" in name_low:
        return DetectResponse(
            module="electrochem",
            sub_type="cv",
            confidence=0.92,
            reason=f"检测到电位-电流特征 ({parsed.columns[0]} vs {parsed.columns[1]})，识别为电化学-CV 子模块。",
            columns=parsed.columns,
            preview_rows=parsed.preview_rows,
            suggested_params={"sub_type": "cv"},
        )

    if (
        (any(k in col_joined for k in ("time", "t (s)", "t/s")) and any(k in col_joined for k in ("potential", "voltage", "v)")))
        or any(k in name_low for k in ("gcd", "charge", "discharge"))
    ):
        return DetectResponse(
            module="electrochem",
            sub_type="gcd",
            confidence=0.92,
            reason=f"检测到时间-电位充放电曲线特征 ({parsed.columns[0]} vs {parsed.columns[1]})，识别为电化学-GCD 子模块。",
            columns=parsed.columns,
            preview_rows=parsed.preview_rows,
            suggested_params={"sub_type": "gcd"},
        )

    # 6. Numeric range heuristic fallback before XY
    if len(x) >= 20 and 4.0 <= x_min <= 30.0 and 40.0 <= x_max <= 100.0 and y_min >= 0 and np.all(np.diff(x) > 0):
        return DetectResponse(
            module="xrd",
            sub_type="powder_xrd",
            confidence=0.72,
            reason=f"X 轴单调递增且位于 {x_min:.1f}–{x_max:.1f} 区间（非负强度），推测为 XRD 图谱（可手动切换）。",
            columns=parsed.columns,
            preview_rows=parsed.preview_rows,
            suggested_params={"wavelength_angstrom": 1.5406, "k_factor": 0.89},
        )

    # 7. Universal XY fallback
    return DetectResponse(
        module="xy",
        sub_type="general_xy",
        confidence=0.68,
        reason=f"通用两列或多列数值表 ({', '.join(parsed.columns[:4])})，已加载至万能 XY 模块（可手动切换其它模块）。",
        columns=parsed.columns,
        preview_rows=parsed.preview_rows,
        suggested_params={"x_col": 0, "y_col": 1},
    )
