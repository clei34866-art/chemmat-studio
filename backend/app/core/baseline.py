from __future__ import annotations

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.spatial import ConvexHull


def asls_baseline(y: np.ndarray, lam: float = 1e5, p: float = 0.01, n_iter: int = 15) -> np.ndarray:
    """Asymmetric Least Squares (AsLS) baseline estimation (Eilers & Boelens)."""
    y_arr = np.asarray(y, dtype=float)
    n = len(y_arr)
    if n < 4:
        return y_arr.copy()
    d = sparse.diags([1.0, -2.0, 1.0], [0, 1, 2], shape=(n - 2, n), format="csc")
    dtd = lam * (d.T @ d)
    w = np.ones(n, dtype=float)
    z = y_arr.copy()
    for _ in range(max(1, int(n_iter))):
        w_mat = sparse.diags(w, 0, shape=(n, n), format="csc")
        z = spsolve(w_mat + dtd, w * y_arr)
        w = p * (y_arr > z) + (1.0 - p) * (y_arr <= z)
    return z


def snip_baseline(y: np.ndarray, max_half_window: int = 25, decreasing: bool = True) -> np.ndarray:
    """Statistics-sensitive Non-linear Iterative Peak-clipping (SNIP) baseline."""
    y_arr = np.asarray(y, dtype=float)
    n = len(y_arr)
    if n < 5:
        return y_arr.copy()
    y_min = float(np.min(y_arr))
    shifted = np.maximum(y_arr - y_min, 0.0)
    v = np.log(np.log(np.sqrt(shifted + 1.0) + 1.0) + 1.0)

    w_max = min(max(1, int(max_half_window)), (n - 1) // 2)
    windows = range(w_max, 0, -1) if decreasing else range(1, w_max + 1)
    for w in windows:
        v_new = v.copy()
        v_new[w:-w] = np.minimum(v[w:-w], 0.5 * (v[:-2 * w] + v[2 * w:]))
        v = v_new

    inv = (np.exp(np.exp(v) - 1.0) - 1.0) ** 2 - 1.0
    return np.maximum(inv, 0.0) + y_min


def poly_baseline(x: np.ndarray, y: np.ndarray, degree: int = 2, n_iter: int = 15, n_sigma: float = 2.0) -> np.ndarray:
    """Iterative sigma-clipped polynomial baseline."""
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    n = len(y_arr)
    if n <= degree + 2:
        return np.polyval(np.polyfit(x_arr, y_arr, max(0, min(degree, n - 1))), x_arr)

    # Normalize x to [-1, 1] for numerical stability
    x_span = float(np.max(x_arr) - np.min(x_arr)) or 1.0
    xn = 2.0 * (x_arr - np.min(x_arr)) / x_span - 1.0
    mask = np.ones(n, dtype=bool)
    coeffs = np.zeros(degree + 1)
    for _ in range(max(1, int(n_iter))):
        if np.sum(mask) <= degree + 1:
            break
        coeffs = np.polyfit(xn[mask], y_arr[mask], degree)
        fit = np.polyval(coeffs, xn)
        resid = y_arr - fit
        neg = resid[resid <= 0]
        sigma = float(np.std(neg)) if len(neg) > 3 else float(np.std(resid))
        if sigma <= 1e-12:
            break
        new_mask = resid <= n_sigma * sigma
        if np.array_equal(new_mask, mask):
            break
        mask = new_mask
    return np.polyval(coeffs, xn)


def rubberband_baseline(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Lower convex-hull (rubberband) baseline independent of x direction."""
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    n = len(x_arr)
    if n < 3:
        return y_arr.copy()

    order = np.argsort(x_arr)
    xs = x_arr[order]
    ys = y_arr[order]

    # Try ConvexHull lower chain; fall back to monotone lower envelope if collinear
    try:
        pts = np.column_stack([xs, ys])
        hull = ConvexHull(pts)
        v = sorted(hull.vertices)
        # Keep only vertices between leftmost and rightmost forming lower envelope
        lower_idx: list[int] = []
        for idx in v:
            # Check if point lies on/below the chord connecting endpoints
            y_chord = ys[0] + (ys[-1] - ys[0]) * (xs[idx] - xs[0]) / (xs[-1] - xs[0] + 1e-18)
            if ys[idx] <= y_chord + 1e-9 or idx in (0, n - 1):
                lower_idx.append(idx)
        if len(lower_idx) < 2:
            lower_idx = [0, n - 1]
        bg_sorted = np.interp(xs, xs[lower_idx], ys[lower_idx])
    except Exception:
        bg_sorted = np.interp(xs, [xs[0], xs[-1]], [ys[0], ys[-1]])

    bg = np.empty_like(bg_sorted)
    bg[order] = bg_sorted
    return bg


def shirley_baseline(x: np.ndarray, y: np.ndarray, tol: float = 1e-6, max_iter: int = 50) -> np.ndarray:
    """Iterative Shirley integral background for XPS spectra.

    Works consistently whether x (binding energy) is stored high-to-low or low-to-high:
    the background steps up toward the high-BE (lower kinetic energy) side proportionally
    to the integrated peak intensity from the low-BE side.
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    n = len(x_arr)
    if n < 3:
        return y_arr.copy()

    # Sort ascending by binding energy so index 0 is low-BE and index -1 is high-BE
    order = np.argsort(x_arr)
    xs = x_arr[order]
    ys = y_arr[order]

    # Estimate stable endpoint levels using small edge windows
    edge_k = min(3, max(1, n // 30))
    i_low = float(np.mean(ys[:edge_k]))
    i_high = float(np.mean(ys[-edge_k:]))
    bg = np.linspace(i_low, i_high, n)

    if abs(i_high - i_low) < 1e-12 and float(np.max(ys) - min(i_low, i_high)) < 1e-12:
        out = np.empty_like(bg)
        out[order] = bg
        return out

    for _ in range(max(1, int(max_iter))):
        diff = np.maximum(ys - bg, 0.0)
        # Cumulative integral from high-BE down or low-BE up:
        # At energy E, background step above i_low equals (i_high - i_low) * (Area_from_low_to_E / Total_Area)
        dx = np.diff(xs)
        seg = 0.5 * (diff[:-1] + diff[1:]) * dx
        cum_low_to_high = np.concatenate(([0.0], np.cumsum(seg)))
        total_area = float(cum_low_to_high[-1])
        if total_area <= 1e-12:
            break
        bg_next = i_low + (i_high - i_low) * (cum_low_to_high / total_area)
        if np.max(np.abs(bg_next - bg)) < tol * max(1.0, abs(i_high - i_low)):
            bg = bg_next
            break
        bg = bg_next

    out = np.empty_like(bg)
    out[order] = bg
    return out


def compute_baseline(
    x: np.ndarray,
    y: np.ndarray,
    method: str = "asls",
    *,
    lam: float = 1e5,
    p: float = 0.01,
    n_iter: int = 15,
    snip_window: int = 25,
    poly_degree: int = 2,
    shirley_tol: float = 1e-6,
    shirley_max_iter: int = 50,
) -> np.ndarray:
    m = method.lower()
    if m == "none":
        return np.zeros_like(y, dtype=float)
    if m == "asls":
        return asls_baseline(y, lam=lam, p=p, n_iter=n_iter)
    if m == "snip":
        return snip_baseline(y, max_half_window=snip_window)
    if m in {"poly", "polynomial"}:
        return poly_baseline(x, y, degree=poly_degree, n_iter=n_iter)
    if m == "rubberband":
        return rubberband_baseline(x, y)
    if m == "shirley":
        return shirley_baseline(x, y, tol=shirley_tol, max_iter=shirley_max_iter)
    raise ValueError(f"Unknown baseline method: {method}")
