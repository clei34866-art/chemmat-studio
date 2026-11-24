from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.detector import detect_file_type
from app.core.exporter import export_processed_data, render_publication_figure
from app.modules.contact_angle import process_contact_angle
from app.modules.electrochem import process_electrochem
from app.modules.spectroscopy import process_spectroscopy
from app.modules.xps import process_xps
from app.modules.xrd import process_xrd
from app.modules.xy import process_xy
from app.schemas.models import DetectResponse, JournalStyle, ModuleName, ModuleProcessResponse
from app.synthetic.gen_contact_angle import generate_contact_angle_synthetic
from app.synthetic.gen_electrochem import generate_electrochem_synthetic
from app.synthetic.gen_spectroscopy import generate_spectroscopy_synthetic
from app.synthetic.gen_xps import generate_xps_synthetic
from app.synthetic.gen_xrd import generate_xrd_synthetic
from app.synthetic.gen_xy import generate_xy_synthetic

router = APIRouter(prefix="/api")


class FigureExportRequest(BaseModel):
    result: ModuleProcessResponse
    journal_style: JournalStyle = "nature"
    fmt: str = "png"
    dpi: int = 300


class DataExportRequest(BaseModel):
    result: ModuleProcessResponse
    fmt: str = "xlsx"


@router.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "ChemMat Studio API",
        "modules": ["xy", "xrd", "xps", "contact_angle", "electrochem", "spectroscopy"],
    }


@router.post("/detect", response_model=DetectResponse)
async def detect_uploaded_file(file: UploadFile = File(...)) -> DetectResponse:
    content = await file.read()
    try:
        return detect_file_type(file.filename or "unknown.csv", content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse or detect file: {exc}") from exc


@router.get("/synthetic/{module}")
def get_synthetic_dataset(
    module: ModuleName,
    sub_type: str | None = Query(default=None),
    angle_deg: float = Query(default=90.0),
) -> dict[str, Any]:
    try:
        if module == "xy":
            raw = generate_xy_synthetic()
        elif module == "xrd":
            raw = generate_xrd_synthetic()
        elif module == "xps":
            raw = generate_xps_synthetic()
        elif module == "contact_angle":
            raw = generate_contact_angle_synthetic(angle_deg=angle_deg)
        elif module == "electrochem":
            raw = generate_electrochem_synthetic(sub_type=sub_type or "eis")
        elif module == "spectroscopy":
            raw = generate_spectroscopy_synthetic(sub_type=sub_type or "uvvis")
        else:
            raise HTTPException(status_code=404, detail=f"Unknown module: {module}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    encoded_files = []
    for f in raw["files"]:
        fn = f["filename"]
        b64 = base64.b64encode(f["content"]).decode("ascii")
        mime = "image/png" if fn.lower().endswith(".png") else "text/csv"
        encoded_files.append({"filename": fn, "content_base64": b64, "mime_type": mime})

    return {
        "module": module,
        "files": encoded_files,
        "ground_truth": raw["ground_truth"],
        "default_params": raw["default_params"],
    }


@router.post("/process/{module}", response_model=ModuleProcessResponse)
async def process_module(
    module: ModuleName,
    files: list[UploadFile] = File(...),
    params_json: str = Form(default="{}"),
    ground_truth_json: str | None = Form(default=None),
) -> ModuleProcessResponse:
    try:
        params: dict[str, Any] = json.loads(params_json) if params_json else {}
        gt: dict[str, Any] | None = json.loads(ground_truth_json) if ground_truth_json else None
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON parameters: {exc}") from exc

    file_pairs: list[tuple[str, bytes]] = []
    for uf in files:
        file_pairs.append((uf.filename or "data.csv", await uf.read()))

    try:
        if module == "xy":
            allowed = {
                "x_col", "y_col", "normalize", "y_offset_step", "enable_linear_fit",
                "fit_xmin", "fit_xmax", "fit_series_index", "x_label_override",
                "y_label_override", "skip_rows", "delimiter",
            }
            return process_xy(file_pairs, **{k: v for k, v in params.items() if k in allowed}, ground_truth=gt)

        if module == "xrd":
            allowed = {
                "smooth_enabled", "smooth_window", "smooth_polyorder", "baseline_method",
                "baseline_lam", "baseline_p", "poly_degree", "snip_window", "display_mode",
                "stack_offset_pct", "prominence_pct", "min_distance_deg", "max_peaks",
                "wavelength_angstrom", "k_factor", "instrumental_fwhm_deg", "instrumental_method",
                "skip_rows",
            }
            return process_xrd(file_pairs, **{k: v for k, v in params.items() if k in allowed}, ground_truth=gt)

        if module == "xps":
            allowed = {
                "auto_charge_correct", "ref_be_ev", "manual_shift_ev", "charge_search_min",
                "charge_search_max", "bg_method", "bg_emin", "bg_emax", "shirley_tol",
                "shirley_max_iter", "n_peaks", "peak_specs", "fwhm_min", "fwhm_max",
                "eta_fixed", "rsf_entries", "skip_rows",
            }
            return process_xps(file_pairs, **{k: v for k, v in params.items() if k in allowed}, ground_truth=gt)

        if module == "contact_angle":
            allowed = {
                "threshold_mode", "manual_threshold", "blur_kernel", "auto_baseline",
                "baseline_y", "baseline_tilt_deg", "fit_model", "poly_order", "edge_band_px",
            }
            fn, content = file_pairs[0]
            return process_contact_angle(
                content,
                filename=fn,
                **{k: v for k, v in params.items() if k in allowed},
                ground_truth=gt,
            )

        if module == "electrochem":
            allowed = {
                "sub_type", "active_mass_mg", "current_ma", "scan_rate_mv_s",
                "potential_window_v", "cv_prominence_pct", "circuit_model",
                "initial_params", "bounds_override", "skip_rows",
            }
            return process_electrochem(file_pairs, **{k: v for k, v in params.items() if k in allowed}, ground_truth=gt)

        if module == "spectroscopy":
            allowed = {
                "sub_type", "smooth_enabled", "smooth_window", "smooth_polyorder",
                "baseline_method", "baseline_lam", "baseline_p", "poly_degree",
                "prominence_pct", "min_distance", "ftir_mode", "enable_tauc",
                "tauc_gamma", "path_length_cm", "kubelka_munk", "tauc_emin",
                "tauc_emax", "skip_rows",
            }
            return process_spectroscopy(file_pairs, **{k: v for k, v in params.items() if k in allowed}, ground_truth=gt)

        raise HTTPException(status_code=404, detail=f"Unknown module: {module}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/export/figure")
def export_figure_endpoint(req: FigureExportRequest) -> Response:
    fmt = req.fmt.lower()
    if fmt not in {"png", "svg", "pdf"}:
        raise HTTPException(status_code=400, detail=f"Unsupported figure format: {req.fmt}")
    media_map = {
        "png": "image/png",
        "svg": "image/svg+xml",
        "pdf": "application/pdf",
    }
    raw_bytes = render_publication_figure(req.result, journal_style=req.journal_style, fmt=fmt, dpi=req.dpi)
    filename = f"chemmat_{req.result.module}_{req.journal_style}.{fmt}"
    return Response(
        content=raw_bytes,
        media_type=media_map[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export/data")
def export_data_endpoint(req: DataExportRequest) -> Response:
    fmt = req.fmt.lower()
    if fmt not in {"csv", "xlsx", "json"}:
        raise HTTPException(status_code=400, detail=f"Unsupported data format: {req.fmt}")
    media_map = {
        "csv": "text/csv; charset=utf-8",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json",
    }
    raw_bytes = export_processed_data(req.result, fmt=fmt)
    filename = f"chemmat_{req.result.module}_processed.{fmt}"
    return Response(
        content=raw_bytes,
        media_type=media_map[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
