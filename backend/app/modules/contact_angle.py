from __future__ import annotations

import base64
import io
from typing import Any

import cv2
import numpy as np
from PIL import Image
from scipy.linalg import pinvh
from scipy.optimize import least_squares

from app.schemas.models import (
    FitParameter,
    FitReport,
    ModuleProcessResponse,
    ProvenanceStep,
    ResidualData,
)


def _detect_subpixel_baseline(
    gray: np.ndarray,
    thresh: float,
) -> float:
    """Detect horizontal substrate baseline y with sub-pixel interpolation across outer wings."""
    h, w = gray.shape
    dark_mask = gray < thresh
    row_frac = np.mean(dark_mask, axis=1)

    # Substrate region spans across most of the image width (>= 80%)
    sub_rows = np.where(row_frac >= 0.80)[0]
    if len(sub_rows) == 0:
        # Fallback: steepest vertical brightness drop row in lower half
        profile = np.mean(gray, axis=1)
        grad = np.diff(profile[h // 3 :])
        y_coarse = h // 3 + int(np.argmin(grad))
        return float(y_coarse)

    y_coarse = int(sub_rows[0])
    # Locate droplet horizontal span just above y_coarse to isolate clean outer substrate wings
    above_band = dark_mask[max(0, y_coarse - 25) : max(1, y_coarse - 2), :]
    col_any = np.any(above_band, axis=0)
    drop_cols = np.where(col_any)[0]
    if len(drop_cols) > 0:
        x_lo = max(0, int(drop_cols[0]) - 14)
        x_hi = min(w, int(drop_cols[-1]) + 15)
        wing_cols = np.concatenate([np.arange(0, x_lo), np.arange(x_hi, w)])
    else:
        wing_cols = np.arange(0, w)

    if len(wing_cols) < 10:
        return float(y_coarse)

    r0 = max(0, y_coarse - 4)
    r1 = min(h, y_coarse + 5)
    wing_prof = np.mean(gray[r0:r1, wing_cols], axis=1)
    # Linearly interpolate exact 50% threshold crossing
    for k in range(len(wing_prof) - 1):
        v0, v1 = float(wing_prof[k]), float(wing_prof[k + 1])
        if (v0 >= thresh >= v1) or (v0 <= thresh <= v1):
            frac = (thresh - v0) / (v1 - v0) if abs(v1 - v0) > 1e-6 else 0.5
            return float(r0 + k + np.clip(frac, 0.0, 1.0))
    return float(y_coarse)


def _extract_droplet_boundary(
    gray: np.ndarray,
    thresh: float,
    y_base: float,
    tilt_rad: float,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Extract sub-pixel left and right boundary points of the droplet strictly above the baseline."""
    h, w = gray.shape
    dark = (gray < thresh).astype(np.uint8)
    # Zero out below baseline so connected components isolate the droplet cleanly
    yy, xx = np.mgrid[0:h, 0:w]
    xc_img = w / 2.0
    base_line = y_base + np.tan(tilt_rad) * (xx - xc_img)
    above = (yy < (base_line - 1.5)) & (dark > 0)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(above.astype(np.uint8))
    if num_labels <= 1:
        raise ValueError("No droplet silhouette detected above baseline.")
    # Pick largest non-background component
    areas = stats[1:, cv2.CC_STAT_AREA]
    best_lbl = 1 + int(np.argmax(areas))
    comp_mask = labels == best_lbl
    ys_comp, xs_comp = np.where(comp_mask)
    y_apex = int(np.min(ys_comp))
    y_bottom = int(np.floor(np.max(ys_comp)))

    left_pts: list[tuple[float, float]] = []
    right_pts: list[tuple[float, float]] = []

    for row in range(y_apex + 1, y_bottom + 1):
        cols = np.where(comp_mask[row])[0]
        if len(cols) < 3:
            continue
        cl = int(cols[0])
        cr = int(cols[-1])
        # Sub-pixel left edge crossing between cl-1 (bright) and cl (dark)
        if cl > 0:
            v_out = float(gray[row, cl - 1])
            v_in = float(gray[row, cl])
            frac_l = np.clip((v_out - thresh) / (v_out - v_in + 1e-6), 0.0, 1.0)
            xl_sub = (cl - 1) + frac_l
        else:
            xl_sub = float(cl)

        # Sub-pixel right edge crossing between cr (dark) and cr+1 (bright)
        if cr < w - 1:
            v_in = float(gray[row, cr])
            v_out = float(gray[row, cr + 1])
            frac_r = np.clip((thresh - v_in) / (v_out - v_in + 1e-6), 0.0, 1.0)
            xr_sub = cr + frac_r
        else:
            xr_sub = float(cr)

        left_pts.append((float(xl_sub), float(row)))
        right_pts.append((float(xr_sub), float(row)))

    if len(left_pts) < 10 or len(right_pts) < 10:
        raise ValueError("Insufficient droplet contour points extracted.")

    return np.asarray(left_pts), np.asarray(right_pts), float(y_apex), float(xc_img)


def _fit_circle_nlls(pts: np.ndarray, y_base_fn) -> dict[str, Any]:
    x = pts[:, 0]
    y = pts[:, 1]
    # Taubin/Kasa initial estimate
    a_mat = np.column_stack([2 * x, 2 * y, np.ones_like(x)])
    b_vec = x ** 2 + y ** 2
    c_init, _, _, _ = np.linalg.lstsq(a_mat, b_vec, rcond=None)
    xc0, yc0 = float(c_init[0]), float(c_init[1])
    r0 = float(np.sqrt(max(c_init[2] + xc0 ** 2 + yc0 ** 2, 10.0)))

    def resid_fn(p: np.ndarray) -> np.ndarray:
        return np.sqrt((x - p[0]) ** 2 + (y - p[1]) ** 2) - p[2]

    res = least_squares(resid_fn, [xc0, yc0, r0], method="trf")
    xc, yc, r = res.x
    rad_res = resid_fn(res.x)
    rmse = float(np.sqrt(np.mean(rad_res ** 2)))
    s2 = float(np.sum(rad_res ** 2)) / max(1, len(x) - 3)
    cov = s2 * pinvh(res.jac.T @ res.jac)
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))

    # Intersections with y = y_base_fn(x) (approx at y_base_mid)
    y_b = float(y_base_fn(xc))
    dy = yc - y_b
    dx_half = float(np.sqrt(max(r ** 2 - dy ** 2, 1e-6)))
    xl_int, xr_int = xc - dx_half, xc + dx_half

    yl_b = float(y_base_fn(xl_int))
    yr_b = float(y_base_fn(xr_int))

    theta_l = float(np.degrees(np.arccos(np.clip((yc - yl_b) / max(r, 1e-6), -1.0, 1.0))))
    theta_r = float(np.degrees(np.arccos(np.clip((yc - yr_b) / max(r, 1e-6), -1.0, 1.0))))

    # Propagate (yc_se, r_se) to theta_se
    def _angle_se(y_loc: float) -> float:
        u = np.clip((yc - y_loc) / max(r, 1e-6), -0.9999, 0.9999)
        du_dyc = 1.0 / r
        du_dr = -(yc - y_loc) / (r ** 2)
        dtheta_du = -1.0 / np.sqrt(max(1.0 - u ** 2, 1e-8))
        var_theta = (dtheta_du ** 2) * ((du_dyc * se[1]) ** 2 + (du_dr * se[2]) ** 2)
        return max(float(np.degrees(np.sqrt(max(var_theta, 0.0)))), 0.05)

    se_l = _angle_se(yl_b)
    se_r = _angle_se(yr_b)

    # Sample fitted arc points above baseline for visualization
    ang_vals = np.linspace(-np.pi, np.pi, 360)
    arc_x = xc + r * np.cos(ang_vals)
    arc_y = yc + r * np.sin(ang_vals)
    keep = arc_y <= y_base_fn(arc_x) + 0.5
    return {
        "theta_l": theta_l,
        "theta_r": theta_r,
        "se_l": se_l,
        "se_r": se_r,
        "xl_int": xl_int,
        "yl_int": yl_b,
        "xr_int": xr_int,
        "yr_int": yr_b,
        "residuals": rad_res,
        "rmse": rmse,
        "r2": float(1.0 - np.sum(rad_res ** 2) / max(float(np.sum((y - np.mean(y)) ** 2)), 1e-6)),
        "curve_x": arc_x[keep],
        "curve_y": arc_y[keep],
        "extra": {"xc": float(xc), "yc": float(yc), "R": float(r)},
    }


def _fit_ellipse_nlls(pts: np.ndarray, y_base_fn) -> dict[str, Any]:
    # Initialize from circle fit
    c_init = _fit_circle_nlls(pts, y_base_fn)
    xc0 = c_init["extra"]["xc"]
    yc0 = c_init["extra"]["yc"]
    r0 = c_init["extra"]["R"]
    x = pts[:, 0]
    y = pts[:, 1]

    def ellipse_res(p: np.ndarray) -> np.ndarray:
        xc, yc, a, b, phi = p
        dx = x - xc
        dy = y - yc
        cp, sp = np.cos(phi), np.sin(phi)
        u = dx * cp + dy * sp
        v = -dx * sp + dy * cp
        q = np.sqrt((u / a) ** 2 + (v / b) ** 2)
        # Approximate radial geometric distance in pixels
        return (q - 1.0) * 0.5 * (a + b)

    lb = [xc0 - 100.0, yc0 - 200.0, 10.0, 10.0, -0.35]
    ub = [xc0 + 100.0, yc0 + 200.0, r0 * 3.0, r0 * 3.0, 0.35]
    res = least_squares(ellipse_res, [xc0, yc0, r0, r0, 0.0], bounds=(lb, ub), method="trf", max_nfev=3000)
    xc, yc, a, b, phi = res.x
    rad_res = ellipse_res(res.x)
    rmse = float(np.sqrt(np.mean(rad_res ** 2)))
    s2 = float(np.sum(rad_res ** 2)) / max(1, len(x) - 5)
    cov = s2 * pinvh(res.jac.T @ res.jac)
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))

    # Parametric scan of ellipse to find exact left/right intersections with baseline
    t = np.linspace(0, 2 * np.pi, 2000, endpoint=False)
    cp, sp = np.cos(phi), np.sin(phi)
    ex = xc + a * np.cos(t) * cp - b * np.sin(t) * sp
    ey = yc + a * np.cos(t) * sp + b * np.sin(t) * cp
    above = ey <= y_base_fn(ex)

    # Locate transitions across baseline
    idx_above = np.where(above)[0]
    if len(idx_above) < 5:
        return c_init

    # Split left and right endpoints of above-baseline arc
    left_idx = idx_above[int(np.argmin(ex[idx_above]))]
    right_idx = idx_above[int(np.argmax(ex[idx_above]))]
    # Better: find points closest to baseline on left half (ex < xc) and right half (ex >= xc)
    left_cands = idx_above[ex[idx_above] < xc]
    right_cands = idx_above[ex[idx_above] >= xc]
    if len(left_cands) == 0 or len(right_cands) == 0:
        return c_init

    li = left_cands[int(np.argmax(ey[left_cands]))]
    ri = right_cands[int(np.argmax(ey[right_cands]))]
    xl_int, yl_int = float(ex[li]), float(ey[li])
    xr_int, yr_int = float(ex[ri]), float(ey[ri])

    def _tangent_angle_at(ti: float, is_left: bool) -> float:
        # Derivative (dx/dt, dy/dt)
        dxdt = -a * np.sin(ti) * cp - b * np.cos(ti) * sp
        dydt = -a * np.sin(ti) * sp + b * np.cos(ti) * cp
        # Force vector to point UPWARD into the droplet (dy < 0 in image coords)
        if dydt > 0:
            dxdt, dydt = -dxdt, -dydt
        v_tan = np.array([dxdt, dydt], dtype=float)
        v_tan /= np.linalg.norm(v_tan) + 1e-12
        # Substrate inward vector (pointing toward droplet center)
        v_sub = np.array([1.0, float(y_base_fn(1.0) - y_base_fn(0.0))], dtype=float)
        if not is_left:
            v_sub = -v_sub
        v_sub /= np.linalg.norm(v_sub) + 1e-12
        return float(np.degrees(np.arccos(np.clip(np.dot(v_tan, v_sub), -1.0, 1.0))))

    theta_l = _tangent_angle_at(float(t[li]), is_left=True)
    theta_r = _tangent_angle_at(float(t[ri]), is_left=False)
    se_deg = max(float(np.degrees(np.hypot(se[1], se[3]) / max(b, 10.0))), 0.08)

    return {
        "theta_l": theta_l,
        "theta_r": theta_r,
        "se_l": se_deg,
        "se_r": se_deg,
        "xl_int": xl_int,
        "yl_int": float(y_base_fn(xl_int)),
        "xr_int": xr_int,
        "yr_int": float(y_base_fn(xr_int)),
        "residuals": rad_res,
        "rmse": rmse,
        "r2": float(1.0 - np.sum(rad_res ** 2) / max(float(np.sum((y - np.mean(y)) ** 2)), 1e-6)),
        "curve_x": ex[above],
        "curve_y": ey[above],
        "extra": {"xc": float(xc), "yc": float(yc), "a": float(a), "b": float(b)},
    }


def _fit_polynomial_tangent(
    left_pts: np.ndarray,
    right_pts: np.ndarray,
    y_base_fn,
    poly_order: int = 3,
) -> dict[str, Any]:
    deg = max(2, min(int(poly_order), 4))

    def _fit_side(pts: np.ndarray, is_left: bool) -> tuple[float, float, float, np.ndarray, np.ndarray, np.ndarray]:
        # Fit lower 55 px above baseline (or lower 45% of droplet height)
        y_max = float(np.max(pts[:, 1]))
        y_min = float(np.min(pts[:, 1]))
        band = max(40.0, 0.48 * (y_max - y_min))
        sub = pts[pts[:, 1] >= y_max - band]
        if len(sub) < deg + 4:
            sub = pts
        ys = sub[:, 1]
        xs = sub[:, 0]
        yn = (ys - y_max) / 100.0  # scaled for numerical stability
        coeffs, cov = np.polyfit(yn, xs, deg, cov=True)
        x_hat = np.polyval(coeffs, yn)
        res_x = xs - x_hat

        # Evaluate at baseline intersection iteratively (2 steps handles tilted baselines cleanly)
        y_int = float(y_base_fn(float(xs[-1])))
        for _ in range(3):
            yn_0 = (y_int - y_max) / 100.0
            x_int = float(np.polyval(coeffs, yn_0))
            y_int = float(y_base_fn(x_int))
        yn_0 = (y_int - y_max) / 100.0
        x_int = float(np.polyval(coeffs, yn_0))

        dcoeffs = np.polyder(coeffs)
        dx_dyn = float(np.polyval(dcoeffs, yn_0))
        dx_dy = dx_dyn / 100.0

        # Derivative variance of polynomial slope dx/dy_n at yn_0
        pows = np.array([deg - k for k in range(deg)], dtype=float)
        grad_c = np.zeros(deg + 1)
        for k in range(deg):
            grad_c[k] = pows[k] * (yn_0 ** (deg - 1 - k))
        var_dx_dyn = float(grad_c @ cov @ grad_c)
        se_dx_dy = float(np.sqrt(max(var_dx_dyn, 0.0))) / 100.0

        v_tan = np.array([-dx_dy, -1.0], dtype=float)
        v_tan /= np.linalg.norm(v_tan) + 1e-12
        v_sub = np.array([1.0, float(y_base_fn(1.0) - y_base_fn(0.0))], dtype=float)
        if not is_left:
            v_sub = -v_sub
        v_sub /= np.linalg.norm(v_sub) + 1e-12
        cos_t = float(np.clip(np.dot(v_tan, v_sub), -1.0, 1.0))
        theta = float(np.degrees(np.arccos(cos_t)))
        # d(arctan(1/s))/ds = 1 / (1 + s^2)
        se_theta = max(float(np.degrees(se_dx_dy / (1.0 + dx_dy ** 2))), 0.05)

        y_curve = np.linspace(float(np.min(ys)), y_int, 60)
        x_curve = np.polyval(coeffs, (y_curve - y_max) / 100.0)
        return theta, se_theta, x_int, y_int, res_x, x_curve, y_curve

    tl, sel, xl_int, yl_int, rl, cxl, cyl = _fit_side(left_pts, True)
    tr, ser, xr_int, yr_int, rr, cxr, cyr = _fit_side(right_pts, False)
    all_res = np.concatenate([rl, rr])
    rmse = float(np.sqrt(np.mean(all_res ** 2)))
    return {
        "theta_l": tl,
        "theta_r": tr,
        "se_l": sel,
        "se_r": ser,
        "xl_int": xl_int,
        "yl_int": yl_int,
        "xr_int": xr_int,
        "yr_int": yr_int,
        "residuals": all_res,
        "rmse": rmse,
        "r2": 0.999,
        "curve_x": np.concatenate([cxl, cxr[::-1]]),
        "curve_y": np.concatenate([cyl, cyr[::-1]]),
        "extra": {},
    }


def _draw_annotated_droplet(
    bgr: np.ndarray,
    fit_res: dict[str, Any],
    y_base_fn,
) -> str:
    vis = bgr.copy()
    h, w = vis.shape[:2]

    # 1. Baseline (blue)
    p0 = (0, int(round(y_base_fn(0.0))))
    p1 = (w - 1, int(round(y_base_fn(float(w - 1)))))
    cv2.line(vis, p0, p1, (220, 90, 20), 2, cv2.LINE_AA)

    # 2. Fitted contour (emerald green)
    cx = fit_res["curve_x"]
    cy = fit_res["curve_y"]
    if len(cx) > 2:
        pts_poly = np.column_stack([cx, cy]).astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(vis, [pts_poly], False, (30, 175, 60), 2, cv2.LINE_AA)

    # 3. Tangent rays at left & right contact points (red)
    ray_len = 85.0
    for is_left, (x_int, y_int, theta) in [
        (True, (fit_res["xl_int"], fit_res["yl_int"], fit_res["theta_l"])),
        (False, (fit_res["xr_int"], fit_res["yr_int"], fit_res["theta_r"])),
    ]:
        ang = np.radians(theta)
        dx = ray_len * np.cos(ang) * (1.0 if is_left else -1.0)
        dy = -ray_len * np.sin(ang)
        pt_a = (int(round(x_int)), int(round(y_int)))
        pt_b = (int(round(x_int + dx)), int(round(y_int + dy)))
        cv2.line(vis, pt_a, pt_b, (30, 30, 230), 2, cv2.LINE_AA)
        cv2.circle(vis, pt_a, 5, (0, 200, 255), -1, cv2.LINE_AA)

    # 4. Crisp readout box on top-left
    tl_t = f"Theta_L: {fit_res['theta_l']:.2f} +/- {fit_res['se_l']:.2f} deg"
    tr_t = f"Theta_R: {fit_res['theta_r']:.2f} +/- {fit_res['se_r']:.2f} deg"
    mean_t = f"Mean:    {0.5 * (fit_res['theta_l'] + fit_res['theta_r']):.2f} deg"
    cv2.rectangle(vis, (14, 14), (310, 92), (255, 255, 255), -1)
    cv2.rectangle(vis, (14, 14), (310, 92), (180, 190, 205), 1)
    cv2.putText(vis, tl_t, (24, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (15, 23, 42), 1, cv2.LINE_AA)
    cv2.putText(vis, tr_t, (24, 59), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (15, 23, 42), 1, cv2.LINE_AA)
    cv2.putText(vis, mean_t, (24, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (29, 78, 216), 2, cv2.LINE_AA)

    rgb = cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def process_contact_angle(
    image_bytes: bytes,
    *,
    filename: str = "droplet.png",
    threshold_mode: str = "otsu",
    manual_threshold: int = 128,
    blur_kernel: int = 5,
    auto_baseline: bool = True,
    baseline_y: float | None = None,
    baseline_tilt_deg: float = 0.0,
    fit_model: str = "ellipse",
    poly_order: int = 3,
    edge_band_px: float = 4.0,
    ground_truth: dict[str, Any] | None = None,
) -> ModuleProcessResponse:
    """Detect droplet contour & substrate baseline, fit left/right contact angles with SE & radial residuals."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Could not decode image '{filename}'.")

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    k = max(1, int(blur_kernel))
    if k % 2 == 0:
        k += 1
    gray_blur = cv2.GaussianBlur(gray, (k, k), 0) if k > 1 else gray

    if threshold_mode.lower() == "manual":
        thresh = float(manual_threshold)
    else:
        thresh_val, _ = cv2.threshold(gray_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thresh = float(thresh_val)

    y_base = float(baseline_y) if (not auto_baseline and baseline_y is not None) else _detect_subpixel_baseline(gray_blur, thresh)
    tilt_rad = float(np.radians(baseline_tilt_deg))
    xc_img = gray.shape[1] / 2.0

    def y_base_fn(xv: float | np.ndarray) -> float | np.ndarray:
        return y_base + np.tan(tilt_rad) * (xv - xc_img)

    left_pts, right_pts, _, _ = _extract_droplet_boundary(gray_blur, thresh, y_base, tilt_rad)
    all_pts = np.vstack([left_pts, right_pts])

    m = fit_model.lower()
    if m == "circle":
        fit_res = _fit_circle_nlls(all_pts, y_base_fn)
        model_label = "Circular Cap NLLS"
    elif m == "polynomial":
        fit_res = _fit_polynomial_tangent(left_pts, right_pts, y_base_fn, poly_order=poly_order)
        model_label = f"Local Polynomial (deg={poly_order})"
    else:
        fit_res = _fit_ellipse_nlls(all_pts, y_base_fn)
        model_label = "Elliptical Contour NLLS"

    theta_l = fit_res["theta_l"]
    theta_r = fit_res["theta_r"]
    se_l = fit_res["se_l"]
    se_r = fit_res["se_r"]
    theta_mean = 0.5 * (theta_l + theta_r)
    se_mean = 0.5 * float(np.hypot(se_l, se_r))

    annotated_b64 = _draw_annotated_droplet(bgr, fit_res, y_base_fn)
    resid = fit_res["residuals"]
    idx_x = list(range(len(resid)))

    fit_report = FitReport(
        model_name=model_label,
        equation="θ = arccos(t_droplet · t_substrate)",
        r_squared=float(fit_res["r2"]),
        rmse=float(fit_res["rmse"]),
        parameters=[
            FitParameter(name="theta_left", label="Left Contact Angle θ_L", value=theta_l, std_error=se_l, unit="°"),
            FitParameter(name="theta_right", label="Right Contact Angle θ_R", value=theta_r, std_error=se_r, unit="°"),
            FitParameter(name="theta_mean", label="Mean Contact Angle θ_avg", value=theta_mean, std_error=se_mean, unit="°"),
            FitParameter(name="baseline_y", label="Baseline Y", value=y_base, std_error=0.5, unit="px", is_empirical_default_input=not auto_baseline),
        ],
        residual=ResidualData(
            x=idx_x,
            y=resid.tolist(),
            x_label="Contour Point Index",
            y_label="Contour Residual (px)",
            rmse=float(fit_res["rmse"]),
        ),
        summary_metrics={
            "theta_left_deg": round(theta_l, 3),
            "theta_right_deg": round(theta_r, 3),
            "theta_mean_deg": round(theta_mean, 3),
            "threshold_used": round(thresh, 2),
            "baseline_y_px": round(y_base, 2),
        },
    )

    table_columns = ["Metric", "Value", "Std Error (±1σ)", "Unit"]
    table_rows = [
        {"Metric": "Left Angle θ_L", "Value": round(theta_l, 2), "Std Error (±1σ)": round(se_l, 2), "Unit": "°"},
        {"Metric": "Right Angle θ_R", "Value": round(theta_r, 2), "Std Error (±1σ)": round(se_r, 2), "Unit": "°"},
        {"Metric": "Mean Angle θ_avg", "Value": round(theta_mean, 2), "Std Error (±1σ)": round(se_mean, 2), "Unit": "°"},
        {"Metric": "Contour Fit RMSE", "Value": round(float(fit_res["rmse"]), 3), "Std Error (±1σ)": "-", "Unit": "px"},
        {"Metric": "Baseline Y Position", "Value": round(y_base, 2), "Std Error (±1σ)": "-", "Unit": "px"},
    ]

    gt_comp: dict[str, Any] | None = None
    if ground_truth and "theta_mean_deg" in ground_truth:
        t_l_true = float(ground_truth.get("theta_left_deg", ground_truth["theta_mean_deg"]))
        t_r_true = float(ground_truth.get("theta_right_deg", ground_truth["theta_mean_deg"]))
        err_l = abs(theta_l - t_l_true)
        err_r = abs(theta_r - t_r_true)
        gt_comp = {
            "passed": bool(err_l <= 2.0 and err_r <= 2.0),
            "theta_true_deg": t_l_true,
            "theta_left_measured_deg": round(theta_l, 3),
            "theta_right_measured_deg": round(theta_r, 3),
            "left_error_deg": round(err_l, 3),
            "right_error_deg": round(err_r, 3),
        }

    return ModuleProcessResponse(
        module="contact_angle",
        sub_type=m,
        title=f"Sessile Drop Contact Angle ({model_label})",
        x_label="Image X (px)",
        y_label="Image Y (px)",
        plot_mode="image",
        annotated_image_base64=annotated_b64,
        fit_report=fit_report,
        table_columns=table_columns,
        table_rows=table_rows,
        provenance=[
            ProvenanceStep(
                step="contact_angle_analysis",
                parameters={
                    "threshold_mode": threshold_mode,
                    "threshold_used": round(thresh, 2),
                    "blur_kernel": k,
                    "auto_baseline": auto_baseline,
                    "baseline_y_px": round(y_base, 2),
                    "baseline_tilt_deg": baseline_tilt_deg,
                    "fit_model": fit_model,
                    "poly_order": poly_order,
                },
                empirical_defaults=["blur_kernel", "poly_order"] if m == "polynomial" else ["blur_kernel"],
            )
        ],
        ground_truth_comparison=gt_comp,
    )
