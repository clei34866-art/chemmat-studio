import React, { useCallback, useMemo, useRef, useState } from "react";
import { measureManualContactAngle, type ManualAngleResult } from "../api";

type Pt = { x: number; y: number };
type Mode = "arc" | "tangent";

/* ---------------- geometry helpers (mirror of backend math) ---------------- */

function circumcircle(
  p1: Pt,
  p2: Pt,
  p3: Pt
): { cx: number; cy: number; r: number } | null {
  const d =
    2 *
    (p1.x * (p2.y - p3.y) + p2.x * (p3.y - p1.y) + p3.x * (p1.y - p2.y));
  if (Math.abs(d) < 1e-6) return null;
  const ux =
    ((p1.x ** 2 + p1.y ** 2) * (p2.y - p3.y) +
      (p2.x ** 2 + p2.y ** 2) * (p3.y - p1.y) +
      (p3.x ** 2 + p3.y ** 2) * (p1.y - p2.y)) /
    d;
  const uy =
    ((p1.x ** 2 + p1.y ** 2) * (p3.x - p2.x) +
      (p2.x ** 2 + p2.y ** 2) * (p1.x - p3.x) +
      (p3.x ** 2 + p3.y ** 2) * (p2.x - p1.x)) /
    d;
  return { cx: ux, cy: uy, r: Math.hypot(p1.x - ux, p1.y - uy) };
}

function angleBetween(ax: number, ay: number, bx: number, by: number): number {
  const dot = Math.max(-1, Math.min(1, ax * bx + ay * by));
  return (Math.acos(dot) * 180) / Math.PI;
}

/** Contact angles for the 3-point arc flow: contacts L/R fixed, arc pulled
 *  through the third point. Baseline is the L->R line itself. */
function arcAngles(
  l: Pt,
  r: Pt,
  pull: Pt
): { l: number; r: number; mean: number } | null {
  const circ = circumcircle(l, r, pull);
  if (!circ) return null;
  let bx = r.x - l.x;
  let by = r.y - l.y;
  const bn = Math.hypot(bx, by);
  if (bn < 1e-9) return null;
  bx /= bn;
  by /= bn;

  const tangentAt = (c: Pt): Pt => {
    // radius direction -> tangent direction, oriented toward the pull point
    const rx = (c.x - circ.cx) / circ.r;
    const ry = (c.y - circ.cy) / circ.r;
    let tx = -ry;
    let ty = rx;
    if (tx * (pull.x - c.x) + ty * (pull.y - c.y) < 0) {
      tx = -tx;
      ty = -ty;
    }
    return { x: tx, y: ty };
  };

  const tl = tangentAt(l);
  const tr = tangentAt(r);
  const thetaL = angleBetween(bx, by, tl.x, tl.y);
  const thetaR = angleBetween(-bx, -by, tr.x, tr.y);
  return { l: thetaL, r: thetaR, mean: (thetaL + thetaR) / 2 };
}

/** Polyline of the arc from L to R passing through the pull side. */
function arcPolyline(l: Pt, r: Pt, pull: Pt): Pt[] {
  const circ = circumcircle(l, r, pull);
  if (!circ) return [];
  const aL = Math.atan2(l.y - circ.cy, l.x - circ.cx);
  const aR = Math.atan2(r.y - circ.cy, r.x - circ.cx);
  const aP = Math.atan2(pull.y - circ.cy, pull.x - circ.cx);
  const TAU = Math.PI * 2;
  const norm = (a: number) => ((a % TAU) + TAU) % TAU;
  // walk counter-clockwise from aL; decide direction by whether aP lies on it
  const ccwSpan = norm(aR - aL);
  const ccwPull = norm(aP - aL);
  const dir = ccwPull <= ccwSpan ? 1 : -1;
  const span = dir === 1 ? ccwSpan : TAU - ccwSpan;
  const pts: Pt[] = [];
  const steps = 72;
  for (let i = 0; i <= steps; i++) {
    const a = aL + dir * span * (i / steps);
    pts.push({ x: circ.cx + circ.r * Math.cos(a), y: circ.cy + circ.r * Math.sin(a) });
  }
  return pts;
}

/** Interior angle for one tangent line in tangent mode. */
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
  return angleBetween(ix, iy, tx, ty);
}

function extend(p: Pt, q: Pt, frac: number): [Pt, Pt] {
  const dx = q.x - p.x;
  const dy = q.y - p.y;
  return [
    { x: p.x - frac * dx, y: p.y - frac * dy },
    { x: q.x + frac * dx, y: q.y + frac * dy },
  ];
}

/* ---------------- component ---------------- */

type HandleId = "arcL" | "arcR" | "arcPull" | "base0" | "base1" | "tanL0" | "tanL1" | "tanR0" | "tanR1";

export function ManualContactAngle() {
  const [mode, setMode] = useState<Mode>("arc");
  const [file, setFile] = useState<File | null>(null);
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const [nat, setNat] = useState<{ w: number; h: number } | null>(null);
  const [arc, setArc] = useState<{ l: Pt; r: Pt; pull: Pt } | null>(null);
  const [base, setBase] = useState<[Pt, Pt] | null>(null);
  const [tanL, setTanL] = useState<[Pt, Pt] | null>(null);
  const [tanR, setTanR] = useState<[Pt, Pt] | null>(null);
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
    setNat(null);
    setArc(null);
    setBase(null);
    setTanL(null);
    setTanR(null);
    setImgUrl(URL.createObjectURL(f));
  };

  const onImgLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    const w = img.naturalWidth;
    const h = img.naturalHeight;
    setNat({ w, h });
    const yb = 0.62 * h;
    setArc({
      l: { x: 0.4 * w, y: yb },
      r: { x: 0.6 * w, y: yb },
      pull: { x: 0.5 * w, y: 0.36 * h },
    });
    setBase([
      { x: 0.06 * w, y: yb },
      { x: 0.94 * w, y: yb },
    ]);
    setTanL([
      { x: 0.3 * w, y: yb },
      { x: 0.37 * w, y: 0.36 * h },
    ]);
    setTanR([
      { x: 0.7 * w, y: yb },
      { x: 0.63 * w, y: 0.36 * h },
    ]);
  };

  const toImageCoords = useCallback(
    (clientX: number, clientY: number): Pt | null => {
      const svg = svgRef.current;
      if (!svg || !nat) return null;
      const rect = svg.getBoundingClientRect();
      return {
        x: Math.max(0, Math.min(nat.w, ((clientX - rect.left) / rect.width) * nat.w)),
        y: Math.max(0, Math.min(nat.h, ((clientY - rect.top) / rect.height) * nat.h)),
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
    if (!id) return;
    const p = toImageCoords(e.clientX, e.clientY);
    if (!p) return;
    if (id === "arcL") setArc((s) => (s ? { ...s, l: p } : s));
    else if (id === "arcR") setArc((s) => (s ? { ...s, r: p } : s));
    else if (id === "arcPull") setArc((s) => (s ? { ...s, pull: p } : s));
    else if (id === "base0") setBase((s) => (s ? [p, s[1]] : s));
    else if (id === "base1") setBase((s) => (s ? [s[0], p] : s));
    else if (id === "tanL0") setTanL((s) => (s ? [p, s[1]] : s));
    else if (id === "tanL1") setTanL((s) => (s ? [s[0], p] : s));
    else if (id === "tanR0") setTanR((s) => (s ? [p, s[1]] : s));
    else if (id === "tanR1") setTanR((s) => (s ? [s[0], p] : s));
    setResult(null);
  };

  const angles = useMemo(() => {
    if (mode === "arc") {
      if (!arc) return null;
      return arcAngles(arc.l, arc.r, arc.pull);
    }
    if (!base || !tanL || !tanR) return null;
    const l = sideAngle(base, tanL, true);
    const r = sideAngle(base, tanR, false);
    if (l === null || r === null) return null;
    return { l, r, mean: (l + r) / 2 };
  }, [mode, arc, base, tanL, tanR]);

  const arcPts = useMemo(() => {
    if (mode !== "arc" || !arc) return [];
    return arcPolyline(arc.l, arc.r, arc.pull);
  }, [mode, arc]);

  const runAnnotate = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      let res: ManualAngleResult;
      if (mode === "arc") {
        if (!arc) return;
        res = await measureManualContactAngle(file, {
          baseline: [arc.l.x, arc.l.y, arc.r.x, arc.r.y],
          arc_points: [arc.l.x, arc.l.y, arc.r.x, arc.r.y, arc.pull.x, arc.pull.y],
        });
      } else {
        if (!base || !tanL || !tanR) return;
        res = await measureManualContactAngle(file, {
          baseline: [base[0].x, base[0].y, base[1].x, base[1].y],
          tangent_left: [tanL[0].x, tanL[0].y, tanL[1].x, tanL[1].y],
          tangent_right: [tanR[0].x, tanR[0].y, tanR[1].x, tanR[1].y],
        });
      }
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleR = nat ? Math.max(6, Math.max(nat.w, nat.h) * 0.011) : 8;
  const strokeW = nat ? Math.max(1.6, nat.w * 0.0022) : 2;

  const handle = (id: HandleId, p: Pt, color: string, label?: string) => (
    <g key={id}>
      <circle
        cx={p.x}
        cy={p.y}
        r={handleR}
        fill={color}
        fillOpacity={0.92}
        stroke="#ffffff"
        strokeWidth={strokeW * 0.8}
        style={{ cursor: "grab", touchAction: "none" }}
        onPointerDown={onPointerDown(id)}
      />
      {label && (
        <text
          x={p.x}
          y={p.y - handleR * 1.5}
          textAnchor="middle"
          fontSize={handleR * 1.35}
          fill={color}
          fontWeight={700}
          style={{ pointerEvents: "none" }}
        >
          {label}
        </text>
      )}
    </g>
  );

  const ready = imgUrl && nat && arc && base && tanL && tanR;

  return (
    <section className="mt-3.5 rounded-xl border border-[#E2E8F0] bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-bold text-[#0F172A]">手动测角（真实照片）</h3>
        <span className="text-xs text-[#64748B]">
          自动识别对带反光、倒影的照片容易测错；这里自己定点拉弧，工具只算角度。
        </span>
        <span className="flex-1" />
        <div className="flex overflow-hidden rounded-lg border border-[#CBD5E1] text-xs font-semibold">
          <button
            type="button"
            onClick={() => setMode("arc")}
            className={mode === "arc" ? "bg-[#0F766E] px-3 py-1.5 text-white" : "px-3 py-1.5 text-[#334155] hover:bg-[#F1F5F9]"}
          >
            三点拉弧
          </button>
          <button
            type="button"
            onClick={() => setMode("tangent")}
            className={mode === "tangent" ? "bg-[#0F766E] px-3 py-1.5 text-white" : "px-3 py-1.5 text-[#334155] hover:bg-[#F1F5F9]"}
          >
            切线直拖
          </button>
        </div>
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

      {imgUrl && mode === "arc" && (
        <p className="mt-2 text-xs leading-5 text-[#64748B]">
          步骤：① 把<strong>左点</strong>拖到液滴左接触点；② 把<strong>右点</strong>拖到右接触点（两点连线就是基线，表面斜就跟着斜）；
          ③ 拖<strong>绿点</strong>拉弧度，让弧线贴住液滴轮廓。角度随拖动实时更新。
        </p>
      )}
      {imgUrl && mode === "tangent" && (
        <p className="mt-2 text-xs leading-5 text-[#64748B]">
          拖法：蓝色基线两点拉到样品表面两端；红色切线每条两个点，下点压接触点、上点贴住液滴边缘靠近接触处的一小段。
        </p>
      )}

      {ready && (
        <div className="relative mt-3 select-none overflow-hidden rounded-lg border border-[#E2E8F0] bg-[#0B0F14]">
          <img src={imgUrl} alt="液滴照片" className="block w-full" draggable={false} />
          <svg
            ref={svgRef}
            viewBox={`0 0 ${nat.w} ${nat.h}`}
            className="absolute inset-0 h-full w-full"
            onPointerMove={onPointerMove}
            onPointerUp={() => {
              dragRef.current = null;
            }}
          >
            {mode === "arc" && arc && (
              <>
                {/* baseline = L->R line, extended a little */}
                {(() => {
                  const [a, b] = extend(arc.l, arc.r, 0.18);
                  return <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#3B82F6" strokeWidth={strokeW} />;
                })()}
                {arcPts.length > 2 && (
                  <polyline
                    points={arcPts.map((p) => `${p.x},${p.y}`).join(" ")}
                    fill="none"
                    stroke="#22C55E"
                    strokeWidth={strokeW * 1.2}
                  />
                )}
                {handle("arcL", arc.l, "#F59E0B", "左")}
                {handle("arcR", arc.r, "#F59E0B", "右")}
                {handle("arcPull", arc.pull, "#22C55E", "拉弧")}
              </>
            )}
            {mode === "tangent" && base && tanL && tanR && (
              <>
                {(() => {
                  const [a, b] = base;
                  if (Math.abs(b.x - a.x) > 1e-6) {
                    const slope = (b.y - a.y) / (b.x - a.x);
                    const y0 = a.y + slope * (0 - a.x);
                    const y1 = a.y + slope * (nat.w - a.x);
                    return <line x1={0} y1={y0} x2={nat.w} y2={y1} stroke="#3B82F6" strokeWidth={strokeW} />;
                  }
                  return <line x1={a.x} y1={0} x2={a.x} y2={nat.h} stroke="#3B82F6" strokeWidth={strokeW} />;
                })()}
                {(() => {
                  const [a, b] = extend(tanL[0], tanL[1], 0.35);
                  return <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#EF4444" strokeWidth={strokeW} />;
                })()}
                {(() => {
                  const [a, b] = extend(tanR[0], tanR[1], 0.35);
                  return <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#EF4444" strokeWidth={strokeW} />;
                })()}
                {handle("base0", base[0], "#3B82F6")}
                {handle("base1", base[1], "#3B82F6")}
                {handle("tanL0", tanL[0], "#EF4444")}
                {handle("tanL1", tanL[1], "#EF4444")}
                {handle("tanR0", tanR[0], "#EF4444")}
                {handle("tanR1", tanR[1], "#EF4444")}
              </>
            )}
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
