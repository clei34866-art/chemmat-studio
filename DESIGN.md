# Design System: ChemMat Studio（一站式化材实验数据处理工作台）

> **Synthesized with Google Stitch Skills:** `taste-design`, `design-md`, `extract-design-md`  
> **Visual Direction:** Clean Scientific Workbench（简明科技风 — 专业、干净、高信息可读性、零营销装饰）  
> **Target Viewport:** Desktop Laboratory Workstation (`>= 1280px`)

---

## 1. Visual Theme & Atmosphere

ChemMat Studio is engineered as a **Focused Analytical Cockpit (密度 6/10，结构对称度 2/10，功能性克制动效 2/10)** for materials scientists and chemists. The interface rejects marketing flourishes, dark cyberpunk neon, and decorative gradients in favor of crisp laboratory clarity:

- **Paper-First Contrast:** Plots and residuals sit on pure laboratory white (`#FFFFFF`), separated cleanly from a cool mineral workspace canvas (`#F8FAFC`) by razor-thin `1px` architectural hairlines (`#E2E8F0`).
- **Radical Transparency:** Every default numerical assumption (such as XPS C 1s `284.8 eV`, Scherrer `K = 0.89`, `λ = 1.5406 Å`, RSF `1.00`) carries an explicit warm-amber pill badge so scientists never confuse empirical defaults with immutable physical constants.
- **Residual-Paired Truth:** Fitted plots never stand alone; every fit renders directly above a synchronized zero-referenced residual plot (`残差图`) and a tabular monospace uncertainty table (`± 1σ SE`).

---

## 2. Color Palette & Functional Roles

| Descriptive Name | Hex Code | Functional Role |
|---|---|---|
| **Cool Mineral Canvas** | `#F8FAFC` | Primary workbench background behind panels and empty drop zones |
| **Laboratory Paper White** | `#FFFFFF` | Plot canvas, analytical cards, export figure background (`PNG/SVG/PDF`), side rails |
| **Frosted Slate Subtle** | `#F1F5F9` | Table headers, secondary card fills, subtle plot gridlines |
| **Deep Charcoal Ink** | `#0F172A` | Primary headings, data labels, UI axis text (pure `#000000` reserved strictly for print-ready Matplotlib spines/ticks) |
| **Muted Graphite** | `#475569` | Secondary metadata, formula strings, inactive navigation icons |
| **Technical Pewter** | `#64748B` | Units, provenance timestamps, raw unhighlighted traces |
| **Architectural Hairline** | `#E2E8F0` | `1px` crisp structural borders dividing the 3-column workbench and tabs |
| **Cobalt Analytical Blue** *(Single Primary Accent)* | `#1D4ED8` | Primary CTAs ("应用参数并重新计算", "Excel 数据+日志"), active module indicator, active journal tab |
| **Cobalt Deep Press** | `#1E40AF` | Hover and active press state for primary buttons |
| **Ice Blue Selection Tint** | `#EFF6FF` | Active module pill fill, drag-over highlight, synthetic load button surface |
| **Amber Empirical Fill** | `#FEF3C7` | Fill for `经验默认值 · 可编辑` micro-badges and empirical parameter groups (`#FFFBEB` container) |
| **Amber Empirical Ink / Border** | `#92400E` / `#FDE68A` | Text and `1px` border signaling editable empirical defaults |
| **Emerald Verification Pass** | `#047857` / `#ECFDF5` | Synthetic ground-truth PASS status badges |
| **Crimson Validation Alert** | `#B91C1C` / `#FEF2F2` | Error banners and destructive delete icons |

**Explicitly Banned:** AI purple/violet/indigo gradients, neon outer glows, translucent glassmorphism, pure `#000000` web chrome, multi-accent rainbows outside scientific curve series.

---

## 3. Typography & Tabular Numeric Rules

- **Primary UI Sans Stack:** `'Outfit', 'Noto Sans SC', 'Microsoft YaHei', system-ui, -apple-system, sans-serif`
  - **Workbench Brand Title:** `15px`, SemiBold (`600`), `-0.01em` tracking.
  - **Section Headers:** `12px`, SemiBold (`600`), uppercase/compact tracking, `#0F172A` or `#64748B`.
  - **Parameter Labels & Table Cells:** `12px`, Medium (`500`), high legibility without oversized headings.
- **Scientific Monospace Stack (`.font-mono-num`):** `'JetBrains Mono', 'Cascadia Code', Consolas, monospace` with `font-variant-numeric: tabular-nums`
  - Mandatory for ALL numeric inputs, fitted values, `± 1σ SE` uncertainties, $R^2$, RMSE, peak tables, Scherrer sizes, and JSON provenance parameters.

---

## 4. Layout Principles & 3-Column Workbench Grid

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ Top Bar (56px, #FFFFFF, border-b #E2E8F0)                               │
│ Brand + "白底论文出图" | Journal Style Switch | PNG/SVG/PDF + CSV/XLSX   │
├───────────────┬─────────────────────────────────────────┬───────────────┤
│ Left Rail     │ Center Analytical Stage (flex-1)        │ Right Panel   │
│ (272px fixed) │ (overflow-y-auto, p-3.5, gap-3)         │ (348px fixed) │
│               │                                         │               │
│ • DropZone    │ ┌─────────────────────────────────────┐ │ 全透明参数面板 │
│ • 合成真值按钮 │ │ Main Figure (360px Plotly / Image)  │ │ 零黑箱·全部可改│
│ • 自动识别条   │ ├─────────────────────────────────────┤ │               │
│ • 6 大模块切换 │ │ Synchronized Residual Plot (175px)  │ │ • Module表单   │
│ • 文件队列     │ └─────────────────────────────────────┘ │ • 经验默认值   │
│               │ [拟合参数±SE][峰表/定量][真值核验][溯源]│   琥珀色徽标   │
│               │ (Tabbed Results Drawer >= 210px)        │ • 应用计算按钮 │
└───────────────┴─────────────────────────────────────────┴───────────────┘
```

- **Zero Overlapping Zones:** Plots, residuals, result drawers, and parameter controls reside in non-overlapping bordered compartments.
- **No Horizontal Scroll Traps:** Minimum desktop target `1180px`; optimal `1440×900`.

---

## 5. Component Stylings

- **Buttons:** Subtly rounded (`rounded-md`, `6px`), flat tactile fill (`#1D4ED8` primary white-text CTA or crisp `#FFFFFF` with `1px #E2E8F0` border for secondary exports). Fast `150ms` hover color shift.
- **Analytical Cards:** Flat `#FFFFFF` surface with `1px solid #E2E8F0` border and subtle `8px` (`rounded-lg`) corners — elevated by border clarity rather than heavy drop shadows.
- **Inputs & Selects:** Compact `1px #CBD5E1` stroke, crisp `#FFFFFF` interior, monospace numeric alignment, grouped logically by processing stage (Smoothing -> Baseline -> Peak/Fitting -> Empirical Constants).
- **Empirical Default Badges (`EmpiricalBadge`):** Compact pill (`rounded`, `px-1.5 py-0.5`, `text-[10px]`, `#FEF3C7` fill, `#FDE68A` border, `#92400E` ink) placed directly beside every editable empirical assumption.
- **Publication Export Figures (`Nature`, `Advanced Materials`, `中文核心期刊`):** Live Plotly preview mirrors the selected journal palette, tick direction (`out` vs `in`), spine box, and font stack, while Matplotlib exports strictly enforce `#FFFFFF` figure/axes background (`(255, 255, 255)` at all corners).

---

## 6. Per-Module UI Consistency Audit Checklist

Every Phase 1 module QA report (`docs/qa/01..06-*-qa-report.md`) verifies:
1. Top `56px` toolbar, `272px` left rail, `flex-1` plot + residual stage, and `348px` right inspector preserve clean proportions at `1440×900` without overlap or clipping.
2. Primary chart sits cleanly on `#FFFFFF` directly above its synchronized residual subplot (`残差图`).
3. All numeric readouts, `± 1σ SE`, peak tables, and inputs align with `.font-mono-num`.
4. All empirical defaults visibly show `经验默认值 · 可编辑` amber badges and are directly editable.
5. Zero banned gradients, neon glows, or decorative marketing clutter appear anywhere in the module view.
