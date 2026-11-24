import type {
  DetectResponse,
  JournalStyle,
  ModuleName,
  ModuleProcessResponse,
  SyntheticDatasetResponse,
} from "./types";

export async function detectFile(file: File): Promise<DetectResponse> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/detect", { method: "POST", body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "文件自动识别失败");
  }
  return res.json();
}

export async function fetchSyntheticDataset(
  module: ModuleName,
  opts?: { sub_type?: string; angle_deg?: number }
): Promise<{
  files: File[];
  groundTruth: Record<string, unknown>;
  defaultParams: Record<string, unknown>;
}> {
  const qs = new URLSearchParams();
  if (opts?.sub_type) qs.set("sub_type", opts.sub_type);
  if (opts?.angle_deg !== undefined) qs.set("angle_deg", String(opts.angle_deg));
  const query = qs.toString() ? `?${qs.toString()}` : "";
  const res = await fetch(`/api/synthetic/${module}${query}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "合成数据生成失败");
  }
  const payload: SyntheticDatasetResponse = await res.json();
  const files = payload.files.map((item) => {
    const binStr = atob(item.content_base64);
    const bytes = new Uint8Array(binStr.length);
    for (let i = 0; i < binStr.length; i++) {
      bytes[i] = binStr.charCodeAt(i);
    }
    return new File([bytes], item.filename, { type: item.mime_type });
  });
  return {
    files,
    groundTruth: payload.ground_truth,
    defaultParams: payload.default_params,
  };
}

export async function processModuleData(
  module: ModuleName,
  files: File[],
  params: Record<string, unknown>,
  groundTruth?: Record<string, unknown> | null
): Promise<ModuleProcessResponse> {
  const fd = new FormData();
  for (const f of files) {
    fd.append("files", f);
  }
  fd.append("params_json", JSON.stringify(params));
  if (groundTruth) {
    fd.append("ground_truth_json", JSON.stringify(groundTruth));
  }
  const res = await fetch(`/api/process/${module}`, { method: "POST", body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "数据处理失败");
  }
  return res.json();
}

export async function downloadFigure(
  result: ModuleProcessResponse,
  journalStyle: JournalStyle,
  fmt: "png" | "svg" | "pdf",
  dpi: number
): Promise<void> {
  const res = await fetch("/api/export/figure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result, journal_style: journalStyle, fmt, dpi }),
  });
  if (!res.ok) {
    throw new Error("图表导出失败");
  }
  const blob = await res.blob();
  triggerBlobDownload(blob, `chemmat_${result.module}_${journalStyle}.${fmt}`);
}

export async function downloadData(
  result: ModuleProcessResponse,
  fmt: "csv" | "xlsx" | "json"
): Promise<void> {
  const res = await fetch("/api/export/data", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result, fmt }),
  });
  if (!res.ok) {
    throw new Error("数据导出失败");
  }
  const blob = await res.blob();
  triggerBlobDownload(blob, `chemmat_${result.module}_processed.${fmt}`);
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export interface ManualAngleResult {
  theta_left_deg: number;
  theta_right_deg: number;
  theta_mean_deg: number;
  contact_left: [number, number];
  contact_right: [number, number];
  circle_center?: [number, number];
  circle_radius?: number;
  image_width: number;
  image_height: number;
  annotated_image_base64: string;
}

export async function measureManualContactAngle(
  file: File,
  lines:
    | { baseline: number[]; tangent_left: number[]; tangent_right: number[] }
    | { baseline: number[]; arc_points: number[] }
): Promise<ManualAngleResult> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("lines_json", JSON.stringify(lines));
  const res = await fetch("/api/contact-angle/manual", { method: "POST", body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "手动测角失败");
  }
  return res.json();
}
