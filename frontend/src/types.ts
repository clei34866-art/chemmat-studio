export type ModuleName =
  | "xy"
  | "xrd"
  | "xps"
  | "contact_angle"
  | "electrochem"
  | "spectroscopy";

export type JournalStyle = "nature" | "adv_mater" | "chinese_core";

export interface SeriesData {
  name: string;
  x: number[];
  y: number[];
  z?: number[] | null;
  y2?: number[] | null;
  kind: "raw" | "processed" | "baseline" | "fit" | "component" | "reference";
  line_style: "solid" | "dashed" | "dotted";
  show_markers: boolean;
  yaxis: "y" | "y2";
}

export interface ResidualData {
  x: number[];
  y: number[];
  y_imag?: number[] | null;
  x_label: string;
  y_label: string;
  rmse: number;
}

export interface FitParameter {
  name: string;
  label: string;
  value: number;
  std_error: number;
  unit: string;
  is_empirical_default_input: boolean;
}

export interface FitReport {
  model_name: string;
  equation: string;
  r_squared: number;
  rmse: number;
  reduced_chi_sq?: number | null;
  parameters: FitParameter[];
  residual: ResidualData;
  summary_metrics: Record<string, unknown>;
}

export interface PlotAnnotation {
  x: number;
  y: number;
  text: string;
  ax_offset: [number, number];
}

export interface ProvenanceStep {
  step: string;
  parameters: Record<string, unknown>;
  empirical_defaults: string[];
}

export interface ModuleProcessResponse {
  module: ModuleName;
  sub_type?: string | null;
  title: string;
  x_label: string;
  y_label: string;
  y2_label?: string | null;
  invert_x: boolean;
  equal_aspect: boolean;
  plot_mode: "2d" | "dual_y" | "waterfall_3d" | "image";
  series: SeriesData[];
  annotations: PlotAnnotation[];
  annotated_image_base64?: string | null;
  fit_report?: FitReport | null;
  table_columns: string[];
  table_rows: Record<string, unknown>[];
  provenance: ProvenanceStep[];
  ground_truth_comparison?: Record<string, unknown> | null;
  warnings: string[];
}

export interface DetectResponse {
  module: ModuleName;
  sub_type?: string | null;
  confidence: number;
  reason: string;
  is_image: boolean;
  columns: string[];
  preview_rows: unknown[][];
  suggested_params: Record<string, unknown>;
}

export interface UploadedEntry {
  id: string;
  file: File;
}

export interface SyntheticDatasetResponse {
  module: ModuleName;
  files: { filename: string; content_base64: string; mime_type: string }[];
  ground_truth: Record<string, unknown>;
  default_params: Record<string, unknown>;
}
