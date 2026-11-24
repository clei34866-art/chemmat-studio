from __future__ import annotations

import base64
import io
import json
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.ticker import AutoMinorLocator
import numpy as np
import openpyxl
from PIL import Image

from app.schemas.models import JournalStyle, ModuleProcessResponse

STYLE_CONFIGS: dict[str, dict[str, Any]] = {
    "nature": {
        "colors": ["#1F4E79", "#B83B2A", "#2E7D32", "#7B4B94", "#D97706", "#008080"],
        "font_family": ["Microsoft YaHei", "Arial", "SimSun", "DejaVu Sans"],
        "lw": 1.35,
        "spine_lw": 0.85,
        "tick_dir": "out",
        "top_right_spines": False,
        "minor_ticks": False,
        "title_weight": "semibold",
        "label_weight": "normal",
        "line_styles": ["-", "-", "-", "-", "-"],
    },
    "adv_mater": {
        "colors": ["#0B3C5D", "#D92B2B", "#1B7F5C", "#E07A1F", "#5B3A82", "#117A8B"],
        "font_family": ["Microsoft YaHei", "Arial", "SimSun", "DejaVu Sans"],
        "lw": 1.65,
        "spine_lw": 1.25,
        "tick_dir": "in",
        "top_right_spines": True,
        "minor_ticks": True,
        "title_weight": "bold",
        "label_weight": "bold",
        "line_styles": ["-", "-", "-", "-", "-"],
    },
    "chinese_core": {
        "colors": ["#000000", "#B91C1C", "#1D4ED8", "#047857", "#92400E", "#4B5563"],
        "font_family": ["SimSun", "Microsoft YaHei", "Times New Roman", "DejaVu Sans"],
        "lw": 1.2,
        "spine_lw": 1.0,
        "tick_dir": "in",
        "top_right_spines": True,
        "minor_ticks": True,
        "title_weight": "bold",
        "label_weight": "normal",
        "line_styles": ["-", "--", "-.", ":", "-"],
    },
}


def _apply_journal_rc(style: JournalStyle) -> dict[str, Any]:
    cfg = STYLE_CONFIGS.get(style, STYLE_CONFIGS["nature"])
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": cfg["font_family"],
        "axes.unicode_minus": False,
        "figure.facecolor": "#FFFFFF",
        "axes.facecolor": "#FFFFFF",
        "savefig.facecolor": "#FFFFFF",
        "savefig.edgecolor": "none",
        "axes.edgecolor": "#000000",
        "axes.labelcolor": "#000000",
        "xtick.color": "#000000",
        "ytick.color": "#000000",
        "font.size": 10.0,
        "axes.labelsize": 10.5,
        "axes.titlesize": 11.5,
        "legend.fontsize": 9.0,
    })
    return cfg


def _style_axes(ax: matplotlib.axes.Axes, cfg: dict[str, Any], *, is_residual: bool = False) -> None:
    ax.set_facecolor("#FFFFFF")
    for side in ("bottom", "left"):
        ax.spines[side].set_linewidth(cfg["spine_lw"])
        ax.spines[side].set_color("#000000")
    for side in ("top", "right"):
        ax.spines[side].set_visible(cfg["top_right_spines"] or is_residual)
        ax.spines[side].set_linewidth(cfg["spine_lw"])
        ax.spines[side].set_color("#000000")

    ax.tick_params(
        which="both",
        direction=cfg["tick_dir"],
        top=cfg["top_right_spines"],
        right=cfg["top_right_spines"],
        width=cfg["spine_lw"],
        length=4.5,
        labelsize=9.5,
    )
    if cfg["minor_ticks"]:
        ax.xaxis.set_minor_locator(AutoMinorLocator())
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        ax.tick_params(which="minor", length=2.4, width=cfg["spine_lw"] * 0.75)


def render_publication_figure(
    resp: ModuleProcessResponse,
    journal_style: JournalStyle = "nature",
    fmt: str = "png",
    dpi: int = 300,
) -> bytes:
    """Render publication-grade pure-white-background figure (with synchronized residual panel when fitted)."""
    cfg = _apply_journal_rc(journal_style)
    colors = cfg["colors"]
    has_residual = resp.fit_report is not None and len(resp.fit_report.residual.x) > 0

    if resp.plot_mode == "waterfall_3d":
        fig = plt.figure(figsize=(7.2, 5.4), facecolor="#FFFFFF")
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor("#FFFFFF")
        for idx, s in enumerate(resp.series):
            c = colors[idx % len(colors)]
            z_vals = s.z if s.z is not None else [float(idx)] * len(s.x)
            ax.plot(s.x, z_vals, s.y, label=s.name, color=c, linewidth=cfg["lw"])
        ax.set_xlabel(resp.x_label, labelpad=8)
        ax.set_ylabel("Sample Index", labelpad=8)
        ax.set_zlabel(resp.y_label, labelpad=8)
        ax.set_title(resp.title, fontweight=cfg["title_weight"], pad=12)
        if len(resp.series) > 1:
            ax.legend(frameon=False, loc="upper left", fontsize=8.5)
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight", facecolor="#FFFFFF", edgecolor="none")
        plt.close(fig)
        return buf.getvalue()

    if has_residual:
        fig = plt.figure(figsize=(6.8, 6.2), facecolor="#FFFFFF")
        gs = gridspec.GridSpec(2, 1, height_ratios=[3.2, 1.25], hspace=0.28)
        ax = fig.add_subplot(gs[0])
        ax_res = fig.add_subplot(gs[1])
    else:
        fig, ax = plt.subplots(figsize=(6.8, 4.8), facecolor="#FFFFFF")
        ax_res = None

    if resp.plot_mode == "image" and resp.annotated_image_base64:
        raw_img = base64.b64decode(resp.annotated_image_base64)
        im = Image.open(io.BytesIO(raw_img)).convert("RGB")
        ax.imshow(im)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(resp.title, fontweight=cfg["title_weight"], pad=10)
        for sp in ax.spines.values():
            sp.set_visible(True)
            sp.set_linewidth(cfg["spine_lw"])
            sp.set_color("#000000")
    else:
        _style_axes(ax, cfg)
        ax2 = ax.twinx() if resp.plot_mode == "dual_y" and resp.y2_label else None
        if ax2 is not None:
            _style_axes(ax2, cfg)

        proc_idx = 0
        for s in resp.series:
            ls_map = {"solid": "-", "dashed": "--", "dotted": ":"}
            ls = ls_map.get(s.line_style, "-")
            if s.kind == "raw":
                color = "#64748B" if not s.show_markers else colors[0]
                alpha = 0.55 if not s.show_markers else 0.85
                if s.show_markers:
                    ax.plot(
                        s.x, s.y,
                        linestyle="none", marker="o", markersize=4.2,
                        markerfacecolor="none", markeredgecolor=color,
                        alpha=alpha, label=s.name,
                    )
                else:
                    ax.plot(s.x, s.y, color=color, lw=cfg["lw"] * 0.85, alpha=alpha, label=s.name)
            elif s.kind == "baseline":
                ax.plot(s.x, s.y, color="#94A3B8", lw=1.1, linestyle="--", label=s.name)
            elif s.kind == "fit":
                ax.plot(s.x, s.y, color="#DC2626" if journal_style != "chinese_core" else "#000000", lw=cfg["lw"] * 1.15, linestyle=ls, label=s.name)
            elif s.kind == "component":
                c = colors[(proc_idx + 1) % len(colors)]
                ax.plot(s.x, s.y, color=c, lw=1.0, linestyle="--", alpha=0.85, label=s.name)
                proc_idx += 1
            else:
                target_ax = ax2 if (ax2 is not None and s.yaxis == "y2") else ax
                c = colors[proc_idx % len(colors)]
                if journal_style == "chinese_core" and ls == "-":
                    ls = cfg["line_styles"][proc_idx % len(cfg["line_styles"])]
                marker = "o" if s.show_markers else None
                target_ax.plot(
                    s.x, s.y,
                    color=c, lw=cfg["lw"], linestyle=ls,
                    marker=marker, markersize=3.8 if marker else 0,
                    label=s.name,
                )
                proc_idx += 1

        for ann in resp.annotations[:18]:
            ax.annotate(
                ann.text,
                xy=(ann.x, ann.y),
                xytext=ann.ax_offset,
                textcoords="offset points",
                fontsize=7.8,
                ha="center",
                color="#000000",
                arrowprops={"arrowstyle": "-", "color": "#475569", "lw": 0.65},
            )

        ax.set_xlabel(resp.x_label, fontweight=cfg["label_weight"])
        ax.set_ylabel(resp.y_label, fontweight=cfg["label_weight"])
        if ax2 is not None and resp.y2_label:
            ax2.set_ylabel(resp.y2_label, fontweight=cfg["label_weight"])
        ax.set_title(resp.title, fontweight=cfg["title_weight"], pad=10)

        if resp.invert_x:
            ax.invert_xaxis()
        if resp.equal_aspect:
            ax.set_aspect("equal", adjustable="datalim")

        handles1, labels1 = ax.get_legend_handles_labels()
        if ax2 is not None:
            handles2, labels2 = ax2.get_legend_handles_labels()
            handles, labels = handles1 + handles2, labels1 + labels2
        else:
            handles, labels = handles1, labels1
        if labels:
            ax.legend(handles, labels, frameon=False, loc="best", ncol=1 if len(labels) <= 5 else 2)

    if ax_res is not None and resp.fit_report is not None:
        res_data = resp.fit_report.residual
        _style_axes(ax_res, cfg, is_residual=True)
        ax_res.axhline(0.0, color="#64748B", lw=0.9, linestyle="--")
        ax_res.plot(res_data.x, res_data.y, color=colors[0], lw=1.0, label="Residual (Obs - Fit)")
        if res_data.y_imag is not None:
            ax_res.plot(res_data.x, res_data.y_imag, color=colors[1], lw=1.0, linestyle="--", label="Imag Residual")
            ax_res.legend(frameon=False, loc="best", fontsize=8.0)
        ax_res.set_xlabel(res_data.x_label, fontweight=cfg["label_weight"])
        ax_res.set_ylabel(res_data.y_label, fontweight=cfg["label_weight"])
        ax_res.set_title(
            f"Residual Plot (R² = {resp.fit_report.r_squared:.4f}, RMSE = {resp.fit_report.rmse:.4g})",
            fontsize=9.2,
            loc="left",
            pad=4,
        )
        if resp.invert_x and resp.plot_mode != "image":
            ax_res.invert_xaxis()

    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight", pad_inches=0.14, facecolor="#FFFFFF", edgecolor="none")
    plt.close(fig)
    return buf.getvalue()


def export_processed_data(resp: ModuleProcessResponse, fmt: str = "xlsx") -> bytes:
    """Export processed curves, fitted parameters (±SE), residuals, tables, and provenance."""
    f = fmt.lower()
    if f == "json":
        return resp.model_dump_json(indent=2).encode("utf-8")

    if f == "csv":
        lines: list[str] = [f"# ChemMat Studio Export | Module: {resp.module} | Title: {resp.title}"]
        if resp.fit_report is not None:
            lines.append(f"# Fit Model: {resp.fit_report.model_name} | R^2={resp.fit_report.r_squared:.6f} | RMSE={resp.fit_report.rmse:.6g}")
            for p in resp.fit_report.parameters:
                lines.append(f"# Param {p.label}: {p.value:.6g} +/- {p.std_error:.6g} {p.unit}")
        for idx, s in enumerate(resp.series):
            lines.append(f"# Series {idx + 1}: {s.name}")
        # Build flat columns from longest series or first series pair
        max_len = max((len(s.x) for s in resp.series), default=0)
        header = []
        for s in resp.series:
            header.extend([f"{s.name}_X ({resp.x_label})", f"{s.name}_Y ({resp.y_label})"])
        lines.append(",".join(f'"{h}"' for h in header))
        for r in range(max_len):
            row_vals = []
            for s in resp.series:
                row_vals.append(f"{s.x[r]:.8g}" if r < len(s.x) else "")
                row_vals.append(f"{s.y[r]:.8g}" if r < len(s.y) else "")
            lines.append(",".join(row_vals))
        return ("\ufeff" + "\n".join(lines)).encode("utf-8")

    if f == "xlsx":
        wb = openpyxl.Workbook()
        ws_curves = wb.active
        ws_curves.title = "Curves"
        if resp.series:
            header = []
            for s in resp.series:
                header.extend([f"{s.name} | {resp.x_label}", f"{s.name} | {resp.y_label}"])
            ws_curves.append(header)
            max_len = max(len(s.x) for s in resp.series)
            for r in range(max_len):
                row_vals: list[Any] = []
                for s in resp.series:
                    row_vals.append(s.x[r] if r < len(s.x) else None)
                    row_vals.append(s.y[r] if r < len(s.y) else None)
                ws_curves.append(row_vals)

        if resp.fit_report is not None:
            ws_fit = wb.create_sheet("Fit_Parameters")
            ws_fit.append(["Model", resp.fit_report.model_name, "Equation", resp.fit_report.equation])
            ws_fit.append(["R_squared", resp.fit_report.r_squared, "RMSE", resp.fit_report.rmse])
            ws_fit.append([])
            ws_fit.append(["Name", "Label", "Value", "Std Error (1-sigma)", "Unit", "Empirical Default Input"])
            for p in resp.fit_report.parameters:
                ws_fit.append([p.name, p.label, p.value, p.std_error, p.unit, p.is_empirical_default_input])

            ws_res = wb.create_sheet("Residual")
            res_d = resp.fit_report.residual
            if res_d.y_imag is not None:
                ws_res.append([res_d.x_label, "Residual Real", "Residual Imag"])
                for xv, yr, yi in zip(res_d.x, res_d.y, res_d.y_imag):
                    ws_res.append([xv, yr, yi])
            else:
                ws_res.append([res_d.x_label, res_d.y_label])
                for xv, yr in zip(res_d.x, res_d.y):
                    ws_res.append([xv, yr])

        if resp.table_rows:
            ws_tbl = wb.create_sheet("Results_Table")
            cols = resp.table_columns or list(resp.table_rows[0].keys())
            ws_tbl.append(cols)
            for row in resp.table_rows:
                ws_tbl.append([row.get(c) for c in cols])

        ws_prov = wb.create_sheet("Provenance")
        ws_prov.append(["Step", "Parameters JSON", "Empirical Defaults Flagged"])
        for step in resp.provenance:
            ws_prov.append([
                step.step,
                json.dumps(step.parameters, ensure_ascii=False),
                ", ".join(step.empirical_defaults),
            ])

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    raise ValueError(f"Unsupported export format: {fmt}")
