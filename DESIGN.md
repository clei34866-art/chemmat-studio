# ChemMat Studio Design System Specification

> **Design Aesthetic:** Clean Scientific Workbench（简明科技风）  
> **Domain:** Materials Science & Chemistry Experimental Data Processing  
> **Target Surface:** Desktop Laboratory & Research Workbench (`>= 1280px` optimal)

---

## 1. Visual Atmosphere & Design Philosophy

- **Density:** `6/10` ("Daily App Balanced" moving toward "Analytical Cockpit") — high information utility without visual clutter. Data plots, residual plots, parameter errors (`± 1σ SE`), and raw controls share clear, calm spatial zones.
- **Variance:** Strict structured 3-column workbench grid (`Left Rail` + `Main Canvas` + `Right Parameter Inspector`) anchored by a `56px` global top bar.
- **Motion:** Restrained & functional (`120ms–180ms` ease-out transitions on toggles, tabs, and parameter updates). Zero decorative bouncing, zero parallax, zero AI neon glows.
- **Zero Black-Box Transparency:** Every numerical default is accompanied by a visible **`经验默认值 · 可编辑`** micro-badge so researchers never mistake empirical defaults for physical constants.

---

## 2. Color Calibration

| Token | Hex | Functional Role |
|---|---|---|
| `--bg-canvas` | `#F8FAFC` | Main laboratory workspace background (cool mineral off-white) |
| `--bg-surface` | `#FFFFFF` | Plot paper, primary analytical cards, data tables |
| `--bg-subtle` | `#F1F5F9` | Secondary panels, inspector sections, table headers |
| `--ink-primary` | `#0F172A` | Primary headings, labels, axis UI ink (never raw `#000000` in web chrome) |
| `--ink-secondary` | `#475569` | Subtitles, equations, secondary metadata |
| `--ink-muted` | `#64748B` | Units, provenance timestamps, helper hints |
| `--border-hairline` | `#E2E8F0` | 1px structural dividers and panel frames |
| `--accent-primary` | `#1D4ED8` | Single primary accent: active tab, primary run/export CTA, active series highlight |
| `--accent-hover` | `#1E40AF` | Hover/pressed state for primary actions |
| `--accent-tint` | `#EFF6FF` | Active navigation pill background & drop-zone highlight |
| `--empirical-bg` | `#FEF3C7` | Background for `经验默认值 · 可编辑` badges |
| `--empirical-ink` | `#92400E` | Text & border (`#FDE68A`) for `经验默认值 · 可编辑` badges |
| `--success-ink` | `#047857` | Passed ground-truth checks & good $R^2$ (`#ECFDF5` tint) |
| `--danger-ink` | `#B91C1C` | Validation errors & deletion actions (`#FEF2F2` tint) |

**Banned Patterns:** Purple/indigo/neon gradients, dark cyberpunk shells, glowing drop-shadows, decorative glassmorphism.

---

## 3. Typographic Architecture

- **UI Display & Body Sans:** `'Outfit', 'Noto Sans SC', 'Microsoft YaHei', system-ui, sans-serif`
  - Workbench Title: `15px`, Weight `600`, tight tracking `-0.01em`
  - Panel Section Headers: `12px`, Weight `600`, uppercase tracking `0.04em`, color `--ink-secondary`
  - Body / Form Labels: `13px`, Weight `500`, color `--ink-primary`
- **Data, Equations, Uncertainties & Tables (Mandatory Monospace):** `'JetBrains Mono', 'Cascadia Code', Consolas, monospace` with `font-variant-numeric: tabular-nums`
  - All fitted parameters (`284.80 ± 0.02`), $R^2$, RMSE, peak positions, Scherrer sizes, and parameter inputs MUST render in tabular monospace for vertical decimal alignment.

---

## 4. Layout & Workbench Anatomy

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Top Bar (56px): ChemMat Studio | Journal Style Switch | Export Actions  │
├───────────────┬─────────────────────────────────────────┬───────────────┤
│ Left Rail     │ Center Analytical Stage (flex-1)        │ Right Panel   │
│ (272px)       │                                         │ (348px)       │
│               │ [DropZone + Auto-Detect Banner]         │               │
│ • 6 Modules   │                                         │ Transparent   │
│ • File Queue  │ ┌─────────────────────────────────────┐ │ Parameter     │
│ • Load Synth  │ │ Main Interactive Figure (white bg)  │ │ Inspector     │
│   GroundTruth │ ├─────────────────────────────────────┤ │               │
│   Button      │ │ Synchronized Residual Plot (残差图) │ │ • Every algo  │
│               │ └─────────────────────────────────────┘ │   param live  │
│               │ [Fit ± SE] [Peak Table] [GT Check] [Log]│ • Empirical   │
│               │                                         │   badges      │
└───────────────┴─────────────────────────────────────────┴───────────────┘
```

---

## 5. Publication Figure Templates (Export Engine)

All exported figures (`PNG 300/600 DPI`, `SVG`, `PDF`) **enforce pure white `#FFFFFF` figure & axes backgrounds**:

1. **Nature Style (`nature`)**: Single-column (`89 mm` equiv aspect) / clean sans-serif (`DejaVu Sans` / `Arial`), `0.85 pt` spines (open top/right by default or clean box), outward short ticks, NPG/Okabe-Ito low-saturation palette (`#1F4E79`, `#B83B2A`, `#2E7D32`, `#7B4B94`, `#D97706`), frameless legend.
2. **Advanced Materials Style (`adv_mater`)**: Full closed `1.25 pt` crisp black frame, inward major & minor ticks on all 4 sides, bold sans-serif axis titles, high-contrast academic palette (`#0B3C5D`, `#D92B2B`, `#1B7F5C`, `#E07A1F`).
3. **Chinese Core Journal (`chinese_core`)**: Serif English/numbers (`Times New Roman` / `DejaVu Serif`) paired with CJK Songti/SimSun fallback (`SimSun`, `Microsoft YaHei`), standard quantity/unit slash format (e.g. `2θ / (°)`), `1.0 pt` closed box, inward ticks, distinguishable solid/dashed line styles.
