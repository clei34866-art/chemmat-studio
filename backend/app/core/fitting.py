from __future__ import annotations

from typing import Callable
import numpy as np
from scipy.linalg import pinvh
from scipy.optimize import least_squares


def pseudo_voigt(
    x: np.ndarray,
    area: float,
    center: float,
    fwhm: float,
    eta: float = 0.3,
) -> np.ndarray:
    """Area-normalized Pseudo-Voigt profile where integral over (-inf, +inf) equals `area`."""
    x_arr = np.asarray(x, dtype=float)
    w = max(float(fwhm), 1e-6)
    mix = float(np.clip(eta, 0.0, 1.0))

    sigma = w / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    gaussian = (1.0 / (sigma * np.sqrt(2.0 * np.pi))) * np.exp(-0.5 * ((x_arr - center) / sigma) ** 2)

    gamma = 0.5 * w
    lorentzian = (1.0 / np.pi) * (gamma / ((x_arr - center) ** 2 + gamma ** 2))

    return float(area) * (mix * lorentzian + (1.0 - mix) * gaussian)


def compute_fit_statistics(y_obs: np.ndarray, y_hat: np.ndarray, n_params: int) -> tuple[float, float, float, np.ndarray]:
    resid = np.asarray(y_obs, dtype=float) - np.asarray(y_hat, dtype=float)
    n = len(resid)
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y_obs - np.mean(y_obs)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-18 else (1.0 if ss_res <= 1e-18 else 0.0)
    rmse = float(np.sqrt(ss_res / max(1, n)))
    dof = max(1, n - n_params)
    s2 = ss_res / dof
    return r2, rmse, s2, resid


def linear_fit_with_errors(x: np.ndarray, y: np.ndarray) -> dict:
    """Ordinary least squares linear fit y = slope * x + intercept with 1-sigma SE and residuals."""
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    n = len(x_arr)
    if n < 3:
        raise ValueError("Linear fit requires at least 3 data points.")

    x_mean = float(np.mean(x_arr))
    y_mean = float(np.mean(y_arr))
    dx = x_arr - x_mean
    sxx = float(np.sum(dx ** 2))
    if sxx <= 1e-18:
        raise ValueError("Cannot fit vertical line (all X values are identical).")

    slope = float(np.sum(dx * (y_arr - y_mean)) / sxx)
    intercept = float(y_mean - slope * x_mean)
    y_hat = slope * x_arr + intercept
    r2, rmse, s2, resid = compute_fit_statistics(y_arr, y_hat, n_params=2)

    slope_se = float(np.sqrt(s2 / sxx))
    intercept_se = float(np.sqrt(s2 * (1.0 / n + (x_mean ** 2) / sxx)))

    return {
        "slope": slope,
        "slope_se": slope_se,
        "intercept": intercept,
        "intercept_se": intercept_se,
        "r_squared": r2,
        "rmse": rmse,
        "reduced_chi_sq": s2,
        "y_hat": y_hat,
        "residual": resid,
    }


def nlls_fit_with_errors(
    model_fn: Callable[..., np.ndarray],
    x: np.ndarray,
    y: np.ndarray,
    p0: list[float] | np.ndarray,
    bounds: tuple[list[float] | np.ndarray, list[float] | np.ndarray] = (-np.inf, np.inf),
    max_nfev: int = 4000,
) -> tuple[np.ndarray, np.ndarray, float, float, float, np.ndarray]:
    """Bounded nonlinear least squares returning (popt, perr, r2, rmse, s2, residual = y_obs - y_fit)."""
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    p0_arr = np.asarray(p0, dtype=float)

    def fun(params: np.ndarray) -> np.ndarray:
        return model_fn(x_arr, *params) - y_arr

    res = least_squares(fun, p0_arr, bounds=bounds, method="trf", max_nfev=max_nfev)
    popt = res.x
    y_hat = model_fn(x_arr, *popt)
    r2, rmse, s2, resid = compute_fit_statistics(y_arr, y_hat, n_params=len(popt))

    jtj = res.jac.T @ res.jac
    try:
        cov = s2 * pinvh(jtj)
        perr = np.sqrt(np.maximum(np.diag(cov), 0.0))
    except Exception:
        perr = np.zeros_like(popt)

    return popt, perr, r2, rmse, s2, resid


def cnls_fit_with_errors(
    complex_model_fn: Callable[..., np.ndarray],
    freq: np.ndarray,
    z_real: np.ndarray,
    z_imag: np.ndarray,
    p0: list[float] | np.ndarray,
    bounds: tuple[list[float] | np.ndarray, list[float] | np.ndarray],
    max_nfev: int = 6000,
) -> tuple[np.ndarray, np.ndarray, float, float, float, np.ndarray, np.ndarray]:
    """Complex nonlinear least squares (CNLS) for EIS equivalent circuits.

    Notes: z_imag is signed imaginary impedance Z'' (typically negative for capacitive arcs).
    """
    f_arr = np.asarray(freq, dtype=float)
    zr_arr = np.asarray(z_real, dtype=float)
    zi_arr = np.asarray(z_imag, dtype=float)
    y_stacked = np.concatenate([zr_arr, zi_arr])
    scale = np.maximum(np.sqrt(zr_arr ** 2 + zi_arr ** 2), 1.0)
    w_stacked = np.concatenate([scale, scale])

    def fun(params: np.ndarray) -> np.ndarray:
        z_hat = complex_model_fn(f_arr, *params)
        diff = np.concatenate([np.real(z_hat) - zr_arr, np.imag(z_hat) - zi_arr])
        return diff / w_stacked

    res = least_squares(fun, np.asarray(p0, dtype=float), bounds=bounds, method="trf", max_nfev=max_nfev)
    popt = res.x
    z_hat = complex_model_fn(f_arr, *popt)
    resid_real = zr_arr - np.real(z_hat)
    resid_imag = zi_arr - np.imag(z_hat)
    y_hat_stacked = np.concatenate([np.real(z_hat), np.imag(z_hat)])

    r2, rmse, _, _ = compute_fit_statistics(y_stacked, y_hat_stacked, n_params=len(popt))

    # Weighted reduced chi-squared and covariance in weighted Jacobian space
    n_obs = len(y_stacked)
    s2_weighted = float(np.sum(res.fun ** 2)) / max(1, n_obs - len(popt))
    jtj = res.jac.T @ res.jac
    try:
        cov = s2_weighted * pinvh(jtj)
        perr = np.sqrt(np.maximum(np.diag(cov), 0.0))
    except Exception:
        perr = np.zeros_like(popt)

    return popt, perr, r2, rmse, s2_weighted, resid_real, resid_imag
