import React from "react";
import { Download, FileSpreadsheet, FlaskConical, Image as ImageIcon } from "lucide-react";
import type { JournalStyle, ModuleProcessResponse } from "../types";

interface JournalToolbarProps {
  journalStyle: JournalStyle;
  onJournalChange: (s: JournalStyle) => void;
  result: ModuleProcessResponse | null;
  exportBusy: string | null;
  onExportFigure: (fmt: "png" | "svg" | "pdf", dpi: number) => void;
  onExportData: (fmt: "csv" | "xlsx" | "json") => void;
}

const STYLES: { id: JournalStyle; label: string; hint: string }[] = [
  { id: "nature", label: "Nature 风格", hint: "Arial · 开放上右框 · NPG配色" },
  { id: "adv_mater", label: "Advanced Materials 风格", hint: "加粗闭合框 · 朝内主次刻度" },
  { id: "chinese_core", label: "中文核心期刊", hint: "宋体+Times · 物理量/单位规范" },
];

export const JournalToolbar: React.FC<JournalToolbarProps> = ({
  journalStyle,
  onJournalChange,
  result,
  exportBusy,
  onExportFigure,
  onExportData,
}) => {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-[#E2E8F0] bg-[#FFFFFF] px-4">
      <div className="flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-[#1D4ED8] text-white">
          <FlaskConical className="h-4 w-4" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[15px] font-semibold tracking-tight text-[#0F172A]">
              ChemMat Studio
            </span>
            <span className="rounded bg-[#EFF6FF] px-1.5 py-0.5 text-[10px] font-semibold text-[#1D4ED8]">
              白底论文出图
            </span>
          </div>
          <p className="text-[11px] text-[#64748B]">
            一站式化材实验数据处理 · 全参数透明可控 · 拟合误差与残差同步输出
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-[11px] font-medium text-[#64748B]">期刊样式:</span>
        <div className="flex rounded-md border border-[#E2E8F0] bg-[#F8FAFC] p-0.5">
          {STYLES.map((st) => {
            const active = journalStyle === st.id;
            return (
              <button
                key={st.id}
                type="button"
                title={st.hint}
                onClick={() => onJournalChange(st.id)}
                className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                  active
                    ? "bg-[#1D4ED8] text-white shadow-xs"
                    : "text-[#475569] hover:text-[#0F172A]"
                }`}
              >
                {st.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <button
          type="button"
          disabled={!result || Boolean(exportBusy)}
          onClick={() => onExportFigure("png", 300)}
          className="inline-flex items-center gap-1 rounded border border-[#E2E8F0] bg-white px-2.5 py-1.5 text-xs font-medium text-[#0F172A] hover:bg-[#F8FAFC] disabled:opacity-40"
        >
          <ImageIcon className="h-3.5 w-3.5 text-[#1D4ED8]" />
          {exportBusy === "png-300" ? "导出中..." : "PNG 300"}
        </button>
        <button
          type="button"
          disabled={!result || Boolean(exportBusy)}
          onClick={() => onExportFigure("png", 600)}
          className="inline-flex items-center gap-1 rounded border border-[#E2E8F0] bg-white px-2.5 py-1.5 text-xs font-medium text-[#0F172A] hover:bg-[#F8FAFC] disabled:opacity-40"
        >
          PNG 600
        </button>
        <button
          type="button"
          disabled={!result || Boolean(exportBusy)}
          onClick={() => onExportFigure("svg", 300)}
          className="inline-flex items-center gap-1 rounded border border-[#E2E8F0] bg-white px-2 py-1.5 text-xs font-medium text-[#0F172A] hover:bg-[#F8FAFC] disabled:opacity-40"
        >
          SVG
        </button>
        <button
          type="button"
          disabled={!result || Boolean(exportBusy)}
          onClick={() => onExportFigure("pdf", 300)}
          className="inline-flex items-center gap-1 rounded border border-[#E2E8F0] bg-white px-2 py-1.5 text-xs font-medium text-[#0F172A] hover:bg-[#F8FAFC] disabled:opacity-40"
        >
          PDF
        </button>
        <div className="mx-1 h-4 w-px bg-[#E2E8F0]" />
        <button
          type="button"
          disabled={!result || Boolean(exportBusy)}
          onClick={() => onExportData("csv")}
          className="inline-flex items-center gap-1 rounded border border-[#E2E8F0] bg-white px-2 py-1.5 text-xs font-medium text-[#0F172A] hover:bg-[#F8FAFC] disabled:opacity-40"
        >
          <Download className="h-3.5 w-3.5 text-[#475569]" />
          CSV
        </button>
        <button
          type="button"
          disabled={!result || Boolean(exportBusy)}
          onClick={() => onExportData("xlsx")}
          className="inline-flex items-center gap-1 rounded bg-[#1D4ED8] px-2.5 py-1.5 text-xs font-medium text-white hover:bg-[#1E40AF] disabled:opacity-40"
        >
          <FileSpreadsheet className="h-3.5 w-3.5" />
          Excel 数据+日志
        </button>
      </div>
    </header>
  );
};
