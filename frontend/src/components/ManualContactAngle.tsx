import React, { useCallback, useMemo, useRef, useState } from "react";
import { measureManualContactAngle, type ManualAngleResult } from "../api";

type Pt = { x: number; y: number };
type Lines = { base: [Pt, Pt]; tanL: [Pt, Pt]; tanR: [Pt, Pt] };
type HandleId = "base0" | "base1" | "tanL0" | "tanL1" | "tanR0" | "tanR1";

const HANDLE_OF: Record<HandleId, { line: keyof Lines; idx: 0 | 1 }> = {
  base0: { line: "base", idx: 0 },
  base1: { line: "base", idx: 1 },
  tanL0: { line: "tanL", idx: 0 },
  tanL1: { line: "tanL", idx: 1 },
  tanR0: { line: "tanR", idx: 0 },
  tanR1: { line: "tanR", idx: 1 },
};

function lineIntersection(a: Pt, b: Pt, c: Pt, d: Pt): Pt | null {
  const den = (a.x - b.x) * (c.y - d.y) - (a.y - b.y) * (c.x - d.x);
  if (Math.abs(den) < 1e-9) return null;
  const px =
    ((a.x * b.y - a.y * b.x) * (c.x - d.x) - (a.x - b.x) * (c.x * d.y - c.y * d.x)) / den;
  const py =
    ((a.x * b.y - a.y * b.x) * (c.y - d.y) - (a.y - b.y) * (c.x * d.y - c.y * d.x)) / den;
  return { x: px, y: py };
}

/** Interior angle (deg) between baseline and one tangent, through the liquid. */
function sideAngle(base: [Pt, Pt], tan: [Pt, Pt], isLeft: boolean): number | null {
  let bx = base[1].x - base[0].x;
  let by = base[1].y - base[0].y;
  const bn = Math.hypot(bx, by);
  if (bn < 1e-9) return null;
  bx /= bn;
  by /= bn;
  if (bx < 0) {
    bx = -bx;
    by = -by;
  }
  let tx = tan[1].x - tan[0].x;
  let ty = tan[1].y - tan[0].y;
  const tn = Math.hypot(tx, ty);
  if (tn < 1e-9) return null;
  tx /= tn;
  ty /= tn;
  if (ty > 0) {
    tx = -tx;
    ty = -ty;
  }
  const ix = isLeft ? bx : -bx;
  const iy = isLeft ? by : -by;
  const dot = Math.max(-1, Math.min(1, ix * tx + iy * ty));
  return (Math.acos(dot) * 180) / Math.PI;
}

function extend(p: Pt, q: Pt, frac: number): [Pt, Pt] {
  const dx = q.x - p.x;
  const dy = q.y - p.y;
  return [
    { x: p.x - frac * dx, y: p.y - frac * dy },
    { x: q.x + frac * dx, y: q.y + frac * dy },
  ];
}

export function ManualContactAngle() {
  const [file, setFile] = useState<File | null>(null);
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const [nat, setNat] = useState<{ w: number; h: number } | null>(null);
  const [lines, setLines] = useState<Lines | null>(null);
  const [result, setResult] = useState<ManualAngleResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dragRef = useRef<HandleId | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const onPick = (f: File | null) => {
    if (!f) return;
    setFile(f);
    setResult(null);
    setError(null);
    setLines(null);
    setNat(null);
    setImgUrl(URL.createObjectURL(f));
  };

  const onImgLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    const w = img.naturalWidth;
    const h = img.naturalHeight;
    setNat({ w, h });
    const yb = 0.62 * h;
    setLines({
      base: [
        { x: 0.06 * w, y: yb },
        { x: 0.94 * w, y: yb },
      ],
      tanL: [
        { x: 0.3 * w, y: yb },
        { x: 0.37 * w, y: 0.36 * h },
      ],
      tanR: [
        { x: 0.7 * w, y: yb },
        { x: 0.63 * w, y: 0.36 * h },
      ],
    });
  };

  const toImageCoords = useCallback(
    (clientX: number, clientY: number): Pt | null => {
      const svg = svgRef.current;
      if (!svg || !nat) return null;
      const rect = svg.getBoundingClientRect();
      return {
        x: ((clientX - rect.left) / rect.width) * nat.w,
        y: ((clientY - rect.top) / rect.height) * nat.h,
      };
    },
    [nat]
  );

  const onPointerDown = (id: HandleId) => (e: React.PointerEvent) => {
    e.preventDefault();
    dragRef.current = id;
    (e.target as Element).setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const id = dragRef.current;
    if (!id || !lines || !nat) return;
    const p = toImageCoords(e.clientX, e.clientY);
    if (!p) return;
    const clamped = {
      x: Math.max(0, Math.min(nat.w, p.x)),
      y: Math.max(0, Math.min(nat.h, p.y)),
    };
    const { line, idx } = HANDLE_OF[id];
    setLines((prev) => {
      if (!prev) return prev;
      const next: Lines = { ...prev, [line]: [...prev[line]] as [Pt, Pt] };
      next[line][idx] = clamped;
      return next;
    });
    setResult(null);
  };

  const onPointerUp = () => {
    dragRef.current = null;
  };

  const angles = useMemo(() => {
    if (!lines) return null;
    const l = sideAngle(lines.base, lines.tanL, true);
    const r = sideAngle(lines.base, lines.tanR, false);
    if (l === null || r === null) return null;
    return { l, r, mean: (l + r) / 2 };
  }, [lines]);

  const contacts = useMemo(() => {
    if (!lines) return null;
    return {
      l: lineIntersection(lines.base[0], lines.base[1], lines.tanL[0], lines.tanL[1]),
      r: lineIntersection(lines.base[0], lines.base[1], lines.tanR[0], lines.tanR[1]),
    };
  }, [lines]);

  const runAnnotate = async () => {
    if (!file || !lines) return;
    setBusy(true);
    setError(null);
    try {
      const res = await measureManualContactAngle(file, {
        baseline: [lines.base[0].x, lines.base[0].y, lines.base[1].x, lines.base[1].y],
        tangent_left: [lines.tanL[0].x, lines.tanL[0].y, lines.tanL[1].x, lines.tanL[1].y],
        tangent_right: [lines.tanR[0].x, lines.tanR[0].y, lines.tanR[1].x, lines.tanR[1].y],
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleR = nat ? Math.max(6, Math.max(nat.w, nat.h) * 0.011) : 8;
  const strokeW = nat ? Math.max(1.6, nat.w * 0.0022) : 2;

  const renderHandle = (id: HandleId, p: Pt, color: string) => (
    <circle
      key={id}
      cx={p.x}
      cy={p.y}
      r={handleR}
      fill={color}
      fillOpacity={0.9}
      stroke="#ffffff"
      strokeWidth={strokeW * 0.8}
      style={{ cursor: "grab", touchAction: "none" }}
      onPointerDown={onPointerDown(id)}
    />
  );

  return (
    <section className="mt-3.5 rounded-xl border border-[#E2E8F0] bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-bold text-[#0F172A]">手动测角（真实照片）</h3>
        <span className="text-xs text-[#64748B]">
          自动识别对带反光、倒影的照片容易测错；这里自己拖线，工具只算角度。
        </span>
        <span className="flex-1" />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="rounded-lg border border-[#CBD5E1] px-3 py-1.5 text-xs font-semibold text-[#334155] hover:bg-[#F1F5F9]"
        >
          {file ? "换一张照片" : "选择液滴照片"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        />
      </div>

      {imgUrl && (
        <p className="mt-2 text-xs leading-5 text-[#64748B]">
          拖法：蓝色基线的两个点拉到样品表面两端（表面倾斜就跟着倾斜）；红色切线每条两个点，
          下点压在接触点上、上点贴住液滴边缘靠近接触处的一小段。角度随拖动实时更新。
        </p>
      )}

      {imgUrl && nat && lines && (
        <div className="relative mt-3 select-none overflow-hidden rounded-lg border border-[#E2E8F0] bg-[#0B0F14]">
          <img src={imgUrl} alt="液滴照片" className="block w-full" draggable={false} />
          <svg
            ref={svgRef}
            viewBox={`0 0 ${nat.w} ${nat.h}`}
            className="absolute inset-0 h-full w-full"
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
          >
            {/* baseline extended to full width */}
            {(() => {
              const [a, b] = lines.base;
              if (Math.abs(b.x - a.x) > 1e-6) {
                const slope = (b.y - a.y) / (b.x - a.x);
                const y0 = a.y + slope * (0 - a.x);
                const y1 = a.y + slope * (nat.w - a.x);
                return (
                  <line x1={0} y1={y0} x2={nat.w} y2={y1} stroke="#3B82F6" strokeWidth={strokeW} />
                );
              }
              return <line x1={a.x} y1={0} x2={a.x} y2={nat.h} stroke="#3B82F6" strokeWidth={strokeW} />;
            })()}
            {(() => {
              const [a, b] = extend(lines.tanL[0], lines.tanL[1], 0.35);
              return <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#EF4444" strokeWidth={strokeW} />;
            })()}
            {(() => {
              const [a, b] = extend(lines.tanR[0], lines.tanR[1], 0.35);
              return <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#EF4444" strokeWidth={strokeW} />;
            })()}
            {contacts?.l && (
              <circle cx={contacts.l.x} cy={contacts.l.y} r={handleR * 0.55} fill="#FACC15" />
            )}
            {contacts?.r && (
              <circle cx={contacts.r.x} cy={contacts.r.y} r={handleR * 0.55} fill="#FACC15" />
            )}
            {renderHandle("base0", lines.base[0], "#3B82F6")}
            {renderHandle("base1", lines.base[1], "#3B82F6")}
            {renderHandle("tanL0", lines.tanL[0], "#EF4444")}
            {renderHandle("tanL1", lines.tanL[1], "#EF4444")}
            {renderHandle("tanR0", lines.tanR[0], "#EF4444")}
            {renderHandle("tanR1", lines.tanR[1], "#EF4444")}
          </svg>
        </div>
      )}

      {imgUrl && !nat && <img src={imgUrl} alt="" className="hidden" onLoad={onImgLoad} />}

      {angles && (
        <div className="mt-3 flex flex-wrap items-center gap-x-8 gap-y-2">
          <div className="text-sm text-[#334155]">
            左角 θ<sub>L</sub>{" "}
            <span className="text-xl font-extrabold text-[#0F172A]">{angles.l.toFixed(2)}°</span>
          </div>
          <div className="text-sm text-[#334155]">
            右角 θ<sub>R</sub>{" "}
            <span className="text-xl font-extrabold text-[#0F172A]">{angles.r.toFixed(2)}°</span>
          </div>
          <div className="text-sm text-[#334155]">
            平均{" "}
            <span className="text-xl font-extrabold text-[#1D4ED8]">{angles.mean.toFixed(2)}°</span>
          </div>
          <span className="flex-1" />
          <button
            type="button"
            disabled={busy}
            onClick={() => void runAnnotate()}
            className="rounded-lg bg-[#0F766E] px-4 py-2 text-xs font-bold text-white hover:bg-[#115E59] disabled:opacity-50"
          >
            {busy ? "生成中…" : "生成标注图"}
          </button>
        </div>
      )}

      {error && (
        <div className="mt-2 rounded border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-3">
          <img
            src={`data:image/png;base64,${result.annotated_image_base64}`}
            alt="手动测角标注图"
            className="w-full rounded-lg border border-[#E2E8F0]"
          />
          <a
            href={`data:image/png;base64,${result.annotated_image_base64}`}
            download="contact_angle_manual.png"
            className="mt-2 inline-block rounded-lg border border-[#CBD5E1] px-3 py-1.5 text-xs font-semibold text-[#334155] hover:bg-[#F1F5F9]"
          >
            下载标注图 PNG
          </a>
        </div>
      )}
    </section>
  );
}
