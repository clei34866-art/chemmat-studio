import React, { useState } from "react";
import { CheckCircle2, ClipboardList, LineChart, Sigma, Table2 } from "lucide-react";
import type { JournalStyle, ModuleProcessResponse } from "../types";
import { EmpiricalBadge } from "./EmpiricalBadge";
import { MainPlotlyChart, ResidualPlotChart } from "./PlotlyChart";

interface PlotWorkspaceProps {
  result: ModuleProcessResponse | null;
  journalStyle: JournalStyle;
  loading: boolean;
}

type BottomTab = "fit" | "table" | "ground_truth" | "provenance";

export const PlotWorkspace: React.FC<PlotWorkspaceProps> = ({
  result,
  journalStyle,
  loading,
}) => {
  const [activeTab, setActiveTab] = useState<BottomTab>("fit");

  if (!result) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed border-[#CBD5E1] bg-white p-10 text-center">
        <div>
          <LineChart className="mx-auto mb-2 h-8 w-8 text-[#94A3B8]" />
          <p className="text-sm font-medium text-[#334155]">
            将任意实验数据文件拖入左侧，或点击「加载合成真值验证数据」开始分析
          </p>
          <p className="mt-1 text-xs text-[#64748B]">
            支持 CSV / TSV / TXT / DAT / XY / XLSX 及液滴图像 PNG / JPG
          </p>
        </div>
      </div>
    );
  }

  const fit = result.fit_report;

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-3">
      {/* Main Figure + Synchronized Residual Plot Card (strict pure white background) */}
      <div className="relative rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-3">
        {loading && (
          <div className="absolute right-4 top-3 z-10 rounded bg-[#EFF6FF] px-2 py-0.5 text-[11px] font-medium text-[#1D4ED8]">
            计算更新中...
          </div>
        )}

        {result.plot_mode === "image" && result.annotated_image_base64 ? (
          <div className="flex flex-col items-center justify-center bg-white py-1">
            <div className="mb-1.5 text-[13px] font-semibold text-[#0F172A]">
              {result.title}
            </div>
            <img
              src={`data:image/png;base64,${result.annotated_image_base64}`}
              alt="Contact Angle Annotated Droplet"
              className="max-h-[345px] rounded border border-[#E2E8F0] object-contain"
            />
          </div>
        ) : (
          <MainPlotlyChart result={result} journalStyle={journalStyle} />
        )}

        {fit && fit.residual && fit.residual.x.length > 0 && (
          <div className="mt-2 border-t border-[#E2E8F0] pt-2">
            <ResidualPlotChart
              residual={fit.residual}
              rSquared={fit.r_squared}
              invertX={result.invert_x && result.plot_mode !== "image"}
              journalStyle={journalStyle}
            />
          </div>
        )}
      </div>

      {/* Bottom Analytical Tabs: Fit Parameters (±SE), Peak/Quant Table, Ground Truth Check, Provenance */}
      <div className="flex min-h-[210px] flex-col rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
        <div className="flex items-center gap-1 border-b border-[#E2E8F0] bg-[#F8FAFC] px-3 py-1.5">
          <button
            type="button"
            onClick={() => setActiveTab("fit")}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium ${
              activeTab === "fit"
                ? "bg-white text-[#1D4ED8] shadow-2xs ring-1 ring-[#E2E8F0]"
                : "text-[#475569] hover:text-[#0F172A]"
            }`}
          >
            <Sigma className="h-3.5 w-3.5" />
            拟合参数与误差 (±1σ SE)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("table")}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium ${
              activeTab === "table"
                ? "bg-white text-[#1D4ED8] shadow-2xs ring-1 ring-[#E2E8F0]"
                : "text-[#475569] hover:text-[#0F172A]"
            }`}
          >
            <Table2 className="h-3.5 w-3.5" />
            峰表 / 定量结果 ({result.table_rows.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("ground_truth")}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium ${
              activeTab === "ground_truth"
                ? "bg-white text-[#047857] shadow-2xs ring-1 ring-[#E2E8F0]"
                : "text-[#475569] hover:text-[#0F172A]"
            }`}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            合成真值精度核验
            {result.ground_truth_comparison && (
              <span
                className={`ml-1 rounded px-1 py-0.5 text-[10px] font-semibold ${
                  result.ground_truth_comparison.passed
                    ? "bg-[#ECFDF5] text-[#047857]"
                    : "bg-[#FEF2F2] text-[#B91C1C]"
                }`}
              >
                {result.ground_truth_comparison.passed ? "PASS" : "CHECK"}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("provenance")}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium ${
              activeTab === "provenance"
                ? "bg-white text-[#1D4ED8] shadow-2xs ring-1 ring-[#E2E8F0]"
                : "text-[#475569] hover:text-[#0F172A]"
            }`}
          >
            <ClipboardList className="h-3.5 w-3.5" />
            处理参数溯源日志
          </button>
        </div>

        <div className="flex-1 overflow-auto p-3">
          {activeTab === "fit" && fit && (
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-4 text-xs text-[#475569]">
                <span>
                  模型: <strong className="text-[#0F172A]">{fit.model_name}</strong>
                </span>
                <span className="font-mono-num">
                  方程: {fit.equation}
                </span>
                <span className="font-mono-num">
                  R² = <strong className="text-[#0F172A]">{fit.r_squared.toFixed(5)}</strong>
                </span>
                <span className="font-mono-num">
                  RMSE = <strong className="text-[#0F172A]">{fit.rmse.toPrecision(4)}</strong>
                </span>
              </div>
              <table className="w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC] text-[#475569]">
                    <th className="px-2.5 py-1.5 font-medium">参数</th>
                    <th className="px-2.5 py-1.5 font-medium">拟合值</th>
                    <th className="px-2.5 py-1.5 font-medium">标准误差 (±1σ SE)</th>
                    <th className="px-2.5 py-1.5 font-medium">单位</th>
                    <th className="px-2.5 py-1.5 font-medium">属性说明</th>
                  </tr>
                </thead>
                <tbody>
                  {fit.parameters.map((p) => (
                    <tr key={p.name} className="border-b border-[#F1F5F9]">
                      <td className="px-2.5 py-1.5 font-medium text-[#0F172A]">{p.label}</td>
                      <td className="font-mono-num px-2.5 py-1.5 text-[#0F172A]">
                        {Math.abs(p.value) > 0 && (Math.abs(p.value) < 1e-3 || Math.abs(p.value) >= 1e5)
                          ? p.value.toExponential(4)
                          : p.value.toFixed(4)}
                      </td>
                      <td className="font-mono-num px-2.5 py-1.5 text-[#475569]">
                        {p.is_empirical_default_input && p.std_error === 0
                          ? "输入参数"
                          : `± ${
                              Math.abs(p.std_error) > 0 && (Math.abs(p.std_error) < 1e-3 || Math.abs(p.std_error) >= 1e5)
                                ? p.std_error.toExponential(3)
                                : p.std_error.toFixed(4)
                            }`}
                      </td>
                      <td className="font-mono-num px-2.5 py-1.5 text-[#64748B]">{p.unit || "-"}</td>
                      <td className="px-2.5 py-1.5">
                        {p.is_empirical_default_input ? <EmpiricalBadge /> : <span className="text-[#64748B]">回归估计值</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === "table" && (
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC] text-[#475569]">
                  {result.table_columns.map((c) => (
                    <th key={c} className="px-2.5 py-1.5 font-medium">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.table_rows.map((row, idx) => (
                  <tr key={idx} className="border-b border-[#F1F5F9]">
                    {result.table_columns.map((c) => (
                      <td key={c} className="font-mono-num px-2.5 py-1.5 text-[#0F172A]">
                        {String(row[c] ?? "-")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {activeTab === "ground_truth" && (
            <div className="text-xs">
              {result.ground_truth_comparison ? (
                <div className="space-y-2">
                  <div
                    className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 font-semibold ${
                      result.ground_truth_comparison.passed
                        ? "bg-[#ECFDF5] text-[#047857]"
                        : "bg-[#FEF2F2] text-[#B91C1C]"
                    }`}
                  >
                    {result.ground_truth_comparison.passed
                      ? "✓ 合成真值精度验收通过"
                      : "⚠ 实测偏差超出阈值，请检查参数"}
                  </div>
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                    {Object.entries(result.ground_truth_comparison)
                      .filter(([k]) => k !== "passed")
                      .map(([k, v]) => (
                        <div key={k} className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-2">
                          <div className="text-[11px] text-[#64748B]">{k}</div>
                          <div className="font-mono-num mt-0.5 font-semibold text-[#0F172A]">
                            {typeof v === "object" ? JSON.stringify(v) : String(v)}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              ) : (
                <p className="text-[#64748B]">
                  当前处理的是用户上传文件（无预设数学真值）；点击左侧「加载合成真值验证数据」可随时检验本模块算法精度。
                </p>
              )}
            </div>
          )}

          {activeTab === "provenance" && (
            <div className="space-y-2 text-xs">
              {result.provenance.map((step, i) => (
                <div key={i} className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
                  <div className="flex items-center justify-between">
                    <span className="font-mono-num font-semibold text-[#0F172A]">
                      #{i + 1} {step.step}
                    </span>
                    {step.empirical_defaults.length > 0 && (
                      <div className="flex items-center gap-1.5">
                        <EmpiricalBadge text={`含经验默认值: ${step.empirical_defaults.join(", ")}`} />
                      </div>
                    )}
                  </div>
                  <pre className="font-mono-num mt-1.5 overflow-x-auto text-[11px] text-[#475569]">
                    {JSON.stringify(step.parameters, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
