import React from "react";
import { Play, Plus, SlidersHorizontal, Trash2 } from "lucide-react";
import type { ModuleName } from "../types";
import { EmpiricalBadge } from "./EmpiricalBadge";

interface ParameterInspectorProps {
  module: ModuleName;
  params: Record<string, unknown>;
  columns: string[];
  onChange: (next: Record<string, unknown>) => void;
  onApply: () => void;
  onSubTypeQuickLoad?: (subType: string) => void;
  onContactAnglePreset?: (angleDeg: number) => void;
  disabled: boolean;
}

const FieldLabel: React.FC<{ label: string; empirical?: boolean }> = ({
  label,
  empirical = false,
}) => (
  <div className="mb-1 flex items-center justify-between gap-1">
    <span className="text-xs font-medium text-[#334155]">{label}</span>
    {empirical && <EmpiricalBadge />}
  </div>
);

export const ParameterInspector: React.FC<ParameterInspectorProps> = ({
  module,
  params,
  columns,
  onChange,
  onApply,
  onSubTypeQuickLoad,
  onContactAnglePreset,
  disabled,
}) => {
  const set = (key: string, val: unknown) => onChange({ ...params, [key]: val });
  const num = (key: string, fallback: number) =>
    params[key] !== undefined && params[key] !== null ? Number(params[key]) : fallback;
  const str = (key: string, fallback: string) =>
    params[key] !== undefined && params[key] !== null ? String(params[key]) : fallback;
  const bool = (key: string, fallback: boolean) =>
    params[key] !== undefined && params[key] !== null ? Boolean(params[key]) : fallback;

  const rsfEntries: { name: string; area: number; rsf: number }[] = Array.isArray(params.rsf_entries)
    ? (params.rsf_entries as { name: string; area: number; rsf: number }[])
    : [{ name: "Region 1", area: 9000, rsf: 1.0 }];

  return (
    <aside className="flex w-[348px] shrink-0 flex-col border-l border-[#E2E8F0] bg-[#FFFFFF]">
      <div className="flex items-center justify-between border-b border-[#E2E8F0] px-3.5 py-2.5">
        <div className="flex items-center gap-1.5">
          <SlidersHorizontal className="h-4 w-4 text-[#1D4ED8]" />
          <span className="text-xs font-semibold uppercase tracking-wide text-[#0F172A]">
            全透明参数面板
          </span>
        </div>
        <span className="text-[10px] text-[#64748B]">零黑箱 · 全部可改</span>
      </div>

      <div className="flex-1 space-y-3.5 overflow-y-auto p-3.5 text-xs">
        {module === "xy" && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <FieldLabel label="X 轴列索引" />
                <select
                  value={num("x_col", 0)}
                  onChange={(e) => set("x_col", Number(e.target.value))}
                  className="w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                >
                  {(columns.length > 0 ? columns : ["Col 0", "Col 1"]).map((c, idx) => (
                    <option key={idx} value={idx}>
                      [{idx}] {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <FieldLabel label="Y 轴列索引" />
                <select
                  value={num("y_col", 1)}
                  onChange={(e) => set("y_col", Number(e.target.value))}
                  className="w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                >
                  {(columns.length > 0 ? columns : ["Col 0", "Col 1"]).map((c, idx) => (
                    <option key={idx} value={idx}>
                      [{idx}] {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <FieldLabel label="归一化方式" />
                <select
                  value={str("normalize", "none")}
                  onChange={(e) => set("normalize", e.target.value)}
                  className="w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                >
                  <option value="none">不归一化 (原始值)</option>
                  <option value="max">最大值归一化 (/Max)</option>
                  <option value="minmax">Min-Max [0, 1]</option>
                </select>
              </div>
              <div>
                <FieldLabel label="多文件垂直偏移" />
                <input
                  type="number"
                  step="0.5"
                  value={num("y_offset_step", 0)}
                  onChange={(e) => set("y_offset_step", Number(e.target.value))}
                  className="font-mono-num w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                />
              </div>
            </div>

            <div className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-2.5 space-y-2">
              <label className="flex items-center gap-2 font-medium text-[#0F172A]">
                <input
                  type="checkbox"
                  checked={bool("enable_linear_fit", true)}
                  onChange={(e) => set("enable_linear_fit", e.target.checked)}
                />
                启用线性拟合 y = k·x + b (输出误差与残差)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <FieldLabel label="拟合起点 Xmin (空=全段)" />
                  <input
                    type="number"
                    step="0.1"
                    placeholder="自动"
                    value={params.fit_xmin != null ? String(params.fit_xmin) : ""}
                    onChange={(e) => set("fit_xmin", e.target.value === "" ? null : Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
                <div>
                  <FieldLabel label="拟合终点 Xmax (空=全段)" />
                  <input
                    type="number"
                    step="0.1"
                    placeholder="自动"
                    value={params.fit_xmax != null ? String(params.fit_xmax) : ""}
                    onChange={(e) => set("fit_xmax", e.target.value === "" ? null : Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
              </div>
            </div>
          </>
        )}

        {module === "xrd" && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <FieldLabel label="显示模式" />
                <select
                  value={str("display_mode", "overlay")}
                  onChange={(e) => set("display_mode", e.target.value)}
                  className="w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                >
                  <option value="overlay">叠加对照 (Overlay)</option>
                  <option value="stacked">垂直堆叠 (Stacked)</option>
                  <option value="waterfall_3d">3D 瀑布图 (Waterfall)</option>
                </select>
              </div>
              <div>
                <FieldLabel label="堆叠间距 (%)" />
                <input
                  type="number"
                  step="5"
                  value={num("stack_offset_pct", 25)}
                  onChange={(e) => set("stack_offset_pct", Number(e.target.value))}
                  className="font-mono-num w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                />
              </div>
            </div>

            <div className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-2.5 space-y-2">
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 font-medium text-[#0F172A]">
                  <input
                    type="checkbox"
                    checked={bool("smooth_enabled", true)}
                    onChange={(e) => set("smooth_enabled", e.target.checked)}
                  />
                  Savitzky-Golay 平滑
                </label>
                <span className="text-[10px] text-[#64748B]">仅用于寻峰，拟合用原始净谱</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <FieldLabel label="平滑窗口点数" />
                  <input
                    type="number"
                    step="2"
                    min="5"
                    value={num("smooth_window", 11)}
                    onChange={(e) => set("smooth_window", Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
                <div>
                  <FieldLabel label="扣背底算法" />
                  <select
                    value={str("baseline_method", "asls")}
                    onChange={(e) => set("baseline_method", e.target.value)}
                    className="w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  >
                    <option value="asls">AsLS 非对称最小二乘</option>
                    <option value="snip">SNIP 削峰</option>
                    <option value="poly">多项式迭代</option>
                    <option value="none">不扣背底</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <FieldLabel label="AsLS 平滑因子 λ" />
                  <input
                    type="number"
                    value={num("baseline_lam", 100000)}
                    onChange={(e) => set("baseline_lam", Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
                <div>
                  <FieldLabel label="寻峰显著性阈值 (%)" />
                  <input
                    type="number"
                    step="1"
                    value={num("prominence_pct", 8)}
                    onChange={(e) => set("prominence_pct", Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
              </div>
            </div>

            <div className="rounded border border-[#FDE68A] bg-[#FFFBEB] p-2.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[#92400E]">Scherrer 晶粒尺寸参数</span>
                <EmpiricalBadge />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <FieldLabel label="靶材波长 λ (Å)" empirical />
                  <input
                    type="number"
                    step="0.0001"
                    value={num("wavelength_angstrom", 1.5406)}
                    onChange={(e) => set("wavelength_angstrom", Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
                <div>
                  <FieldLabel label="形状因子 K" empirical />
                  <input
                    type="number"
                    step="0.01"
                    value={num("k_factor", 0.89)}
                    onChange={(e) => set("k_factor", Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <FieldLabel label="仪器展宽 β_inst (°)" empirical />
                  <input
                    type="number"
                    step="0.01"
                    value={num("instrumental_fwhm_deg", 0.08)}
                    onChange={(e) => set("instrumental_fwhm_deg", Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
                <div>
                  <FieldLabel label="展宽扣除方法" />
                  <select
                    value={str("instrumental_method", "gaussian")}
                    onChange={(e) => set("instrumental_method", e.target.value)}
                    className="w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  >
                    <option value="gaussian">高斯平方差 √(β²-βi²)</option>
                    <option value="linear">线性直接相减 (β-βi)</option>
                  </select>
                </div>
              </div>
            </div>
          </>
        )}

        {module === "xps" && (
          <>
            <div className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-2.5 space-y-2">
              <label className="flex items-center gap-2 font-medium text-[#0F172A]">
                <input
                  type="checkbox"
                  checked={bool("auto_charge_correct", true)}
                  onChange={(e) => set("auto_charge_correct", e.target.checked)}
                />
                自动荷电校正 (对齐至参考峰位)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <FieldLabel label="参考结合能 C 1s (eV)" empirical />
                  <input
                    type="number"
                    step="0.1"
                    value={num("ref_be_ev", 284.8)}
                    onChange={(e) => set("ref_be_ev", Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
                <div>
                  <FieldLabel label="手动偏移 ΔE (关闭自动时)" />
                  <input
                    type="number"
                    step="0.05"
                    value={num("manual_shift_ev", 0.0)}
                    onChange={(e) => set("manual_shift_ev", Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <FieldLabel label="背底扣除方法" />
                <select
                  value={str("bg_method", "shirley")}
                  onChange={(e) => set("bg_method", e.target.value)}
                  className="w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                >
                  <option value="shirley">Shirley 积分背底</option>
                  <option value="poly">线性/多项式背底</option>
                  <option value="asls">AsLS 背底</option>
                </select>
              </div>
              <div>
                <FieldLabel label="拟合分峰个数" />
                <input
                  type="number"
                  min="1"
                  max="8"
                  value={num("n_peaks", 3)}
                  onChange={(e) => set("n_peaks", Number(e.target.value))}
                  className="font-mono-num w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                />
              </div>
            </div>

            <div className="rounded border border-[#FDE68A] bg-[#FFFBEB] p-2.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[#92400E]">元素原子比与灵敏度因子 (RSF)</span>
                <EmpiricalBadge text="非内置库 · 请按仪器标定编辑" />
              </div>
              <div className="space-y-1.5">
                {rsfEntries.map((row, idx) => (
                  <div key={idx} className="grid grid-cols-12 items-center gap-1">
                    <input
                      type="text"
                      value={row.name}
                      onChange={(e) => {
                        const copy = [...rsfEntries];
                        copy[idx] = { ...row, name: e.target.value };
                        set("rsf_entries", copy);
                      }}
                      className="col-span-4 rounded border border-[#CBD5E1] bg-white px-1.5 py-1 text-[11px]"
                    />
                    <input
                      type="number"
                      value={row.area}
                      title="峰面积"
                      onChange={(e) => {
                        const copy = [...rsfEntries];
                        copy[idx] = { ...row, area: Number(e.target.value) };
                        set("rsf_entries", copy);
                      }}
                      className="font-mono-num col-span-4 rounded border border-[#CBD5E1] bg-white px-1.5 py-1 text-[11px]"
                    />
                    <input
                      type="number"
                      step="0.01"
                      value={row.rsf}
                      title="RSF"
                      onChange={(e) => {
                        const copy = [...rsfEntries];
                        copy[idx] = { ...row, rsf: Number(e.target.value) };
                        set("rsf_entries", copy);
                      }}
                      className="font-mono-num col-span-3 rounded border border-[#CBD5E1] bg-white px-1.5 py-1 text-[11px]"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const copy = rsfEntries.filter((_, i) => i !== idx);
                        set("rsf_entries", copy.length ? copy : [{ name: "C 1s", area: 9000, rsf: 1.0 }]);
                      }}
                      className="col-span-1 flex justify-center text-[#B91C1C] hover:opacity-80"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={() =>
                  set("rsf_entries", [...rsfEntries, { name: `El ${rsfEntries.length + 1}`, area: 5000, rsf: 1.0 }])
                }
                className="inline-flex items-center gap-1 rounded border border-[#F59E0B] bg-white px-2 py-1 text-[11px] font-medium text-[#92400E]"
              >
                <Plus className="h-3 w-3" /> 添加对比元素峰面积与 RSF
              </button>
            </div>
          </>
        )}

        {module === "contact_angle" && (
          <>
            {onContactAnglePreset && (
              <div className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
                <FieldLabel label="快速切换合成真值液滴图" />
                <div className="grid grid-cols-3 gap-1.5">
                  {[60, 90, 120].map((deg) => (
                    <button
                      key={deg}
                      type="button"
                      onClick={() => onContactAnglePreset(deg)}
                      className="rounded border border-[#CBD5E1] bg-white py-1 font-mono-num text-xs font-medium text-[#0F172A] hover:border-[#1D4ED8] hover:text-[#1D4ED8]"
                    >
                      {deg}° 合成图
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-2">
              <div>
                <FieldLabel label="轮廓拟合模型" />
                <select
                  value={str("fit_model", "ellipse")}
                  onChange={(e) => set("fit_model", e.target.value)}
                  className="w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                >
                  <option value="ellipse">椭圆拟合 (Ellipse)</option>
                  <option value="circle">圆弧拟合 (Circle)</option>
                  <option value="polynomial">局部多项式切线 (Poly)</option>
                </select>
              </div>
              <div>
                <FieldLabel label="高斯滤波核大小" empirical />
                <input
                  type="number"
                  step="2"
                  min="1"
                  max="15"
                  value={num("blur_kernel", 5)}
                  onChange={(e) => set("blur_kernel", Number(e.target.value))}
                  className="font-mono-num w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <FieldLabel label="图像二值化模式" />
                <select
                  value={str("threshold_mode", "otsu")}
                  onChange={(e) => set("threshold_mode", e.target.value)}
                  className="w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                >
                  <option value="otsu">Otsu 自动阈值</option>
                  <option value="manual">手动阈值</option>
                </select>
              </div>
              <div>
                <FieldLabel label="手动阈值 (0–255)" />
                <input
                  type="number"
                  min="10"
                  max="245"
                  value={num("manual_threshold", 128)}
                  onChange={(e) => set("manual_threshold", Number(e.target.value))}
                  className="font-mono-num w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                />
              </div>
            </div>

            <div className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-2.5 space-y-2">
              <label className="flex items-center gap-2 font-medium text-[#0F172A]">
                <input
                  type="checkbox"
                  checked={bool("auto_baseline", true)}
                  onChange={(e) => set("auto_baseline", e.target.checked)}
                />
                自动亚像素基线检测
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <FieldLabel label="基线 Y 坐标 (手动)" />
                  <input
                    type="number"
                    placeholder="自动"
                    value={params.baseline_y != null ? String(params.baseline_y) : ""}
                    onChange={(e) => set("baseline_y", e.target.value === "" ? null : Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
                <div>
                  <FieldLabel label="基线倾角微调 (°)" />
                  <input
                    type="number"
                    step="0.2"
                    value={num("baseline_tilt_deg", 0)}
                    onChange={(e) => set("baseline_tilt_deg", Number(e.target.value))}
                    className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                  />
                </div>
              </div>
            </div>
          </>
        )}

        {module === "electrochem" && (
          <>
            <div>
              <FieldLabel label="电化学测试子类型 (切换并可加载对应示例)" />
              <div className="grid grid-cols-4 gap-1">
                {(["eis", "cv", "gcd", "cycling"] as const).map((st) => {
                  const active = str("sub_type", "eis") === st;
                  return (
                    <button
                      key={st}
                      type="button"
                      onClick={() => {
                        set("sub_type", st);
                        onSubTypeQuickLoad?.(st);
                      }}
                      className={`rounded border py-1 text-[11px] font-semibold uppercase ${
                        active
                          ? "border-[#1D4ED8] bg-[#EFF6FF] text-[#1D4ED8]"
                          : "border-[#CBD5E1] bg-white text-[#475569]"
                      }`}
                    >
                      {st === "cycling" ? "长循环" : st.toUpperCase()}
                    </button>
                  );
                })}
              </div>
            </div>

            {str("sub_type", "eis") === "eis" && (
              <div>
                <FieldLabel label="EIS 等效电路模型 (CNLS 复数拟合)" empirical />
                <select
                  value={str("circuit_model", "R(Q(RW))")}
                  onChange={(e) => set("circuit_model", e.target.value)}
                  className="font-mono-num w-full rounded border border-[#CBD5E1] px-2 py-1.5 text-xs"
                >
                  <option value="R(Q(RW))">R(Q(RW)) — Randles-CPE-Warburg</option>
                  <option value="R(QR)">R(QR) — 阻容半圆 (CPE)</option>
                  <option value="R(CR)">R(CR) — 理想电容半圆</option>
                  <option value="R(QR)(QR)">R(QR)(QR) — 双时间常数</option>
                </select>
              </div>
            )}

            {(str("sub_type", "eis") === "cv" || str("sub_type", "eis") === "gcd") && (
              <div className="rounded border border-[#FDE68A] bg-[#FFFBEB] p-2.5 space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <FieldLabel label="活性物质质量 (mg)" empirical />
                    <input
                      type="number"
                      step="0.1"
                      value={num("active_mass_mg", 1.0)}
                      onChange={(e) => set("active_mass_mg", Number(e.target.value))}
                      className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                    />
                  </div>
                  <div>
                    <FieldLabel label={str("sub_type", "eis") === "gcd" ? "恒流电流 (mA)" : "扫速 (mV/s)"} empirical />
                    {str("sub_type", "eis") === "gcd" ? (
                      <input
                        type="number"
                        step="0.1"
                        value={num("current_ma", 1.0)}
                        onChange={(e) => set("current_ma", Number(e.target.value))}
                        className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                      />
                    ) : (
                      <input
                        type="number"
                        step="5"
                        value={num("scan_rate_mv_s", 50.0)}
                        onChange={(e) => set("scan_rate_mv_s", Number(e.target.value))}
                        className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                      />
                    )}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {module === "spectroscopy" && (
          <>
            <div>
              <FieldLabel label="光谱子类型 (切换并可加载对应示例)" />
              <div className="grid grid-cols-3 gap-1.5">
                {(["uvvis", "raman", "ftir"] as const).map((st) => {
                  const active = str("sub_type", "uvvis") === st;
                  return (
                    <button
                      key={st}
                      type="button"
                      onClick={() => {
                        set("sub_type", st);
                        onSubTypeQuickLoad?.(st);
                      }}
                      className={`rounded border py-1 text-[11px] font-semibold uppercase ${
                        active
                          ? "border-[#1D4ED8] bg-[#EFF6FF] text-[#1D4ED8]"
                          : "border-[#CBD5E1] bg-white text-[#475569]"
                      }`}
                    >
                      {st === "uvvis" ? "UV-Vis" : st.toUpperCase()}
                    </button>
                  );
                })}
              </div>
            </div>

            {str("sub_type", "uvvis") === "uvvis" && (
              <div className="rounded border border-[#FDE68A] bg-[#FFFBEB] p-2.5 space-y-2">
                <label className="flex items-center gap-2 font-medium text-[#0F172A]">
                  <input
                    type="checkbox"
                    checked={bool("enable_tauc", true)}
                    onChange={(e) => set("enable_tauc", e.target.checked)}
                  />
                  Tauc Plot 光学带隙外推 (Eg ± SE)
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <FieldLabel label="跃迁指数 γ" empirical />
                    <select
                      value={num("tauc_gamma", 0.5)}
                      onChange={(e) => set("tauc_gamma", Number(e.target.value))}
                      className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                    >
                      <option value={0.5}>0.5 (直接允许)</option>
                      <option value={2.0}>2.0 (间接允许)</option>
                      <option value={1.5}>1.5 (直接禁阻)</option>
                      <option value={3.0}>3.0 (间接禁阻)</option>
                    </select>
                  </div>
                  <div>
                    <FieldLabel label="光程 L (cm)" empirical />
                    <input
                      type="number"
                      step="0.1"
                      value={num("path_length_cm", 1.0)}
                      onChange={(e) => set("path_length_cm", Number(e.target.value))}
                      className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <FieldLabel label="手动拟合起点 (eV)" />
                    <input
                      type="number"
                      step="0.05"
                      placeholder="自动寻线性区"
                      value={params.tauc_emin != null ? String(params.tauc_emin) : ""}
                      onChange={(e) => set("tauc_emin", e.target.value === "" ? null : Number(e.target.value))}
                      className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                    />
                  </div>
                  <div>
                    <FieldLabel label="手动拟合终点 (eV)" />
                    <input
                      type="number"
                      step="0.05"
                      placeholder="自动寻线性区"
                      value={params.tauc_emax != null ? String(params.tauc_emax) : ""}
                      onChange={(e) => set("tauc_emax", e.target.value === "" ? null : Number(e.target.value))}
                      className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                    />
                  </div>
                </div>
              </div>
            )}

            {(str("sub_type", "uvvis") !== "uvvis" || !bool("enable_tauc", true)) && (
              <div className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-2.5 space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <FieldLabel label="基线扣除方法" />
                    <select
                      value={str("baseline_method", "asls")}
                      onChange={(e) => set("baseline_method", e.target.value)}
                      className="w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                    >
                      <option value="asls">AsLS 非对称最小二乘</option>
                      <option value="poly">多项式迭代</option>
                      <option value="rubberband">Rubberband 凸包</option>
                      <option value="none">不扣背底</option>
                    </select>
                  </div>
                  <div>
                    <FieldLabel label="寻峰阈值 (%)" />
                    <input
                      type="number"
                      step="1"
                      value={num("prominence_pct", 8)}
                      onChange={(e) => set("prominence_pct", Number(e.target.value))}
                      className="font-mono-num w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                    />
                  </div>
                </div>
                {str("sub_type", "uvvis") === "ftir" && (
                  <div>
                    <FieldLabel label="FTIR 显示模式" />
                    <select
                      value={str("ftir_mode", "absorbance")}
                      onChange={(e) => set("ftir_mode", e.target.value)}
                      className="w-full rounded border border-[#CBD5E1] bg-white px-2 py-1 text-xs"
                    >
                      <option value="absorbance">转为吸光度 (A) 后寻峰</option>
                      <option value="transmittance">保留透过率 (%T)</option>
                    </select>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      <div className="border-t border-[#E2E8F0] p-3">
        <button
          type="button"
          disabled={disabled}
          onClick={onApply}
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-[#1D4ED8] px-3 py-2 text-xs font-semibold text-white hover:bg-[#1E40AF] disabled:opacity-40"
        >
          <Play className="h-3.5 w-3.5" />
          应用参数并重新计算
        </button>
      </div>
    </aside>
  );
};
