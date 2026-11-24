from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

ModuleName = Literal[
    "xy",
    "xrd",
    "xps",
    "contact_angle",
    "electrochem",
    "spectroscopy",
]

JournalStyle = Literal["nature", "adv_mater", "chinese_core"]


class SeriesData(BaseModel):
    name: str
    x: list[float]
    y: list[float]
    z: list[float] | None = None
    y2: list[float] | None = None
    kind: Literal["raw", "processed", "baseline", "fit", "component", "reference"] = "processed"
    line_style: Literal["solid", "dashed", "dotted"] = "solid"
    show_markers: bool = False
    yaxis: Literal["y", "y2"] = "y"


class ResidualData(BaseModel):
    x: list[float]
    y: list[float]
    y_imag: list[float] | None = None
    x_label: str = "X"
    y_label: str = "Residual"
    rmse: float = 0.0


class FitParameter(BaseModel):
    name: str
    label: str
    value: float
    std_error: float
    unit: str = ""
    is_empirical_default_input: bool = False


class FitReport(BaseModel):
    model_name: str
    equation: str
    r_squared: float
    rmse: float
    reduced_chi_sq: float | None = None
    parameters: list[FitParameter] = Field(default_factory=list)
    residual: ResidualData
    summary_metrics: dict[str, Any] = Field(default_factory=dict)


class PlotAnnotation(BaseModel):
    x: float
    y: float
    text: str
    ax_offset: tuple[float, float] = (0.0, 14.0)


class ProvenanceStep(BaseModel):
    step: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    empirical_defaults: list[str] = Field(default_factory=list)


class ModuleProcessResponse(BaseModel):
    module: ModuleName
    sub_type: str | None = None
    title: str
    x_label: str
    y_label: str
    y2_label: str | None = None
    invert_x: bool = False
    equal_aspect: bool = False
    plot_mode: Literal["2d", "dual_y", "waterfall_3d", "image"] = "2d"
    series: list[SeriesData] = Field(default_factory=list)
    annotations: list[PlotAnnotation] = Field(default_factory=list)
    annotated_image_base64: str | None = None
    fit_report: FitReport | None = None
    table_columns: list[str] = Field(default_factory=list)
    table_rows: list[dict[str, Any]] = Field(default_factory=list)
    provenance: list[ProvenanceStep] = Field(default_factory=list)
    ground_truth_comparison: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class DetectResponse(BaseModel):
    module: ModuleName
    sub_type: str | None = None
    confidence: float
    reason: str
    is_image: bool = False
    columns: list[str] = Field(default_factory=list)
    preview_rows: list[list[Any]] = Field(default_factory=list)
    suggested_params: dict[str, Any] = Field(default_factory=dict)
