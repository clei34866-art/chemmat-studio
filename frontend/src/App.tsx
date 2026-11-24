import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  Atom,
  Droplets,
  FileText,
  Layers,
  Sparkles,
  Trash2,
  UploadCloud,
  Waves,
} from "lucide-react";
import {
  detectFile,
  downloadData,
  downloadFigure,
  fetchSyntheticDataset,
  processModuleData,
} from "./api";
import { JournalToolbar } from "./components/JournalToolbar";
import { ParameterInspector } from "./components/ParameterInspector";
import { ManualContactAngle } from "./components/ManualContactAngle";
import { PlotWorkspace } from "./components/PlotWorkspace";
import type {
  DetectResponse,
  JournalStyle,
  ModuleName,
  ModuleProcessResponse,
} from "./types";

const MODULE_META: {
  id: ModuleName;
  label: string;
  desc: string;
  icon: React.FC<{ className?: string }>;
}[] = [
  { id: "xy", label: "1. 万能 XY", desc: "多列叠加 · 线性拟合", icon: Activity },
  { id: "xrd", label: "2. XRD 衍射", desc: "扣背底 · 寻峰 · Scherrer", icon: Layers },
  { id: "xps", label: "3. XPS 能谱", desc: "荷电校正 · Shirley · 分峰", icon: Atom },
  { id: "contact_angle", label: "4. 接触角", desc: "液滴轮廓 · 左右角标注", icon: Droplets },
  { id: "electrochem", label: "5. 电化学", desc: "CV · GCD · EIS · 长循环", icon: Sparkles },
  { id: "spectroscopy", label: "6. 光谱分析", desc: "UV-Vis Tauc · FTIR · Raman", icon: Waves },
];

export function App() {
  const [activeModule, setActiveModule] = useState<ModuleName>("xy");
  const [journalStyle, setJournalStyle] = useState<JournalStyle>("nature");
  const [files, setFiles] = useState<File[]>([]);
  const [detectInfo, setDetectInfo] = useState<DetectResponse | null>(null);
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [groundTruth, setGroundTruth] = useState<Record<string, unknown> | null>(null);
  const [result, setResult] = useState<ModuleProcessResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [exportBusy, setExportBusy] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const runProcessing = useCallback(
    async (
      mod: ModuleName,
      targetFiles: File[],
      targetParams: Record<string, unknown>,
      gt: Record<string, unknown> | null
    ) => {
      if (targetFiles.length === 0) return;
      setLoading(true);
      setErrorMsg(null);
      try {
        const res = await processModuleData(mod, targetFiles, targetParams, gt);
        setResult(res);
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const loadSynthetic = useCallback(
    async (
      mod: ModuleName,
      opts?: { sub_type?: string; angle_deg?: number }
    ) => {
      setLoading(true);
      setErrorMsg(null);
      try {
        const syn = await fetchSyntheticDataset(mod, opts);
        setActiveModule(mod);
        setFiles(syn.files);
        setParams(syn.defaultParams);
        setGroundTruth(syn.groundTruth);
        const det = await detectFile(syn.files[0]);
        setDetectInfo(det);
        const res = await processModuleData(mod, syn.files, syn.defaultParams, syn.groundTruth);
        setResult(res);
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    void loadSynthetic("xy");
  }, [loadSynthetic]);

  const handleIncomingFiles = async (incoming: FileList | File[]) => {
    const arr = Array.from(incoming);
    if (arr.length === 0) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const det = await detectFile(arr[0]);
      const nextParams = { ...det.suggested_params };
      setDetectInfo(det);
      setActiveModule(det.module);
      setFiles(arr);
      setParams(nextParams);
      setGroundTruth(null);
      const res = await processModuleData(det.module, arr, nextParams, null);
      setResult(res);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectModule = (mod: ModuleName) => {
    if (mod !== activeModule) {
      void loadSynthetic(mod);
    }
  };

  const handleExportFigure = async (fmt: "png" | "svg" | "pdf", dpi: number) => {
    if (!result) return;
    const tag = `${fmt}-${dpi}`;
    setExportBusy(tag);
    try {
      await downloadFigure(result, journalStyle, fmt, dpi);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setExportBusy(null);
    }
  };

  const handleExportData = async (fmt: "csv" | "xlsx" | "json") => {
    if (!result) return;
    setExportBusy(fmt);
    try {
      await downloadData(result, fmt);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setExportBusy(null);
    }
  };

  return (
    <div className="flex h-screen min-w-[1180px] flex-col overflow-hidden bg-[#F8FAFC] text-[#0F172A]">
      <JournalToolbar
        journalStyle={journalStyle}
        onJournalChange={setJournalStyle}
        result={result}
        exportBusy={exportBusy}
        onExportFigure={handleExportFigure}
        onExportData={handleExportData}
      />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* Left Navigation & DropZone Rail */}
        <aside className="flex w-[272px] shrink-0 flex-col border-r border-[#E2E8F0] bg-[#FFFFFF]">
          <div className="border-b border-[#E2E8F0] p-3">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                void handleIncomingFiles(e.dataTransfer.files);
              }}
              onClick={() => fileInputRef.current?.click()}
              className={`cursor-pointer rounded-lg border-2 border-dashed p-3.5 text-center transition-colors ${
                dragOver
                  ? "border-[#1D4ED8] bg-[#EFF6FF]"
                  : "border-[#CBD5E1] bg-[#F8FAFC] hover:border-[#1D4ED8]"
              }`}
            >
              <UploadCloud className="mx-auto mb-1.5 h-6 w-6 text-[#1D4ED8]" />
              <div className="text-xs font-semibold text-[#0F172A]">
                拖拽原始实验文件到此处
              </div>
              <div className="mt-0.5 text-[10px] text-[#64748B]">
                自动识别类型 · 支持 CSV / TXT / XY / XLSX / PNG / JPG
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) void handleIncomingFiles(e.target.files);
                }}
              />
            </div>

            <button
              type="button"
              onClick={() => void loadSynthetic(activeModule)}
              className="mt-2 w-full rounded-md border border-[#1D4ED8] bg-[#EFF6FF] py-1.5 text-xs font-semibold text-[#1D4ED8] hover:bg-[#DBEAFE]"
            >
              加载合成真值验证数据
            </button>
          </div>

          {/* Auto-Detection Rationale Banner */}
          {detectInfo && (
            <div className="border-b border-[#E2E8F0] bg-[#F8FAFC] px-3 py-2 text-[11px]">
              <div className="flex items-center justify-between font-semibold text-[#0F172A]">
                <span>自动识别: {detectInfo.module.toUpperCase()}</span>
                <span className="font-mono-num text-[#1D4ED8]">
                  {Math.round(detectInfo.confidence * 100)}%
                </span>
              </div>
              <p className="mt-0.5 leading-snug text-[#475569]">{detectInfo.reason}</p>
            </div>
          )}

          {/* 6 Module Switcher */}
          <div className="flex-1 overflow-y-auto p-2.5">
            <div className="mb-1.5 px-1 text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">
              实验数据处理模块
            </div>
            <div className="space-y-1">
              {MODULE_META.map((m) => {
                const Icon = m.icon;
                const active = activeModule === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => handleSelectModule(m.id)}
                    className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left transition-colors ${
                      active
                        ? "bg-[#EFF6FF] text-[#1D4ED8] ring-1 ring-[#BFDBFE]"
                        : "text-[#334155] hover:bg-[#F8FAFC]"
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <div className="min-w-0">
                      <div className="text-xs font-semibold">{m.label}</div>
                      <div className="truncate text-[10px] text-[#64748B]">{m.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>

            {files.length > 0 && (
              <div className="mt-4 border-t border-[#E2E8F0] pt-3">
                <div className="mb-1.5 flex items-center justify-between px-1 text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">
                  <span>当前数据文件 ({files.length})</span>
                  <button
                    type="button"
                    onClick={() => {
                      setFiles([]);
                      setResult(null);
                      setDetectInfo(null);
                    }}
                    className="text-[#64748B] hover:text-[#B91C1C]"
                  >
                    清空
                  </button>
                </div>
                <div className="space-y-1">
                  {files.map((f, idx) => (
                    <div
                      key={`${f.name}-${idx}`}
                      className="flex items-center justify-between rounded border border-[#E2E8F0] bg-[#F8FAFC] px-2 py-1 text-[11px]"
                    >
                      <span className="flex min-w-0 items-center gap-1.5 truncate text-[#0F172A]">
                        <FileText className="h-3 w-3 shrink-0 text-[#64748B]" />
                        <span className="truncate">{f.name}</span>
                      </span>
                      {files.length > 1 && (
                        <button
                          type="button"
                          onClick={() => {
                            const next = files.filter((_, i) => i !== idx);
                            setFiles(next);
                            void runProcessing(activeModule, next, params, groundTruth);
                          }}
                          className="ml-1 text-[#94A3B8] hover:text-[#B91C1C]"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </aside>

        {/* Center Analytical Stage */}
        <main className="flex min-w-0 flex-1 flex-col overflow-y-auto p-3.5">
          {errorMsg && (
            <div className="mb-2.5 rounded border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">
              处理提示: {errorMsg}
            </div>
          )}
          <PlotWorkspace
            result={result}
            journalStyle={journalStyle}
            loading={loading}
          />
          {activeModule === "contact_angle" && <ManualContactAngle />}
        </main>

        {/* Right Transparent Parameter Inspector */}
        <ParameterInspector
          module={activeModule}
          params={params}
          columns={detectInfo?.columns || []}
          onChange={setParams}
          onApply={() => void runProcessing(activeModule, files, params, groundTruth)}
          onSubTypeQuickLoad={(sub) => void loadSynthetic(activeModule, { sub_type: sub })}
          onContactAnglePreset={(deg) => void loadSynthetic("contact_angle", { angle_deg: deg })}
          disabled={files.length === 0 || loading}
        />
      </div>
    </div>
  );
}

export default App;
