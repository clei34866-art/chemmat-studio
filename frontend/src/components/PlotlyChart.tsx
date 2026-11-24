import React, { useEffect, useRef } from "react";
import type * as Plotly from "plotly.js";
import PlotlyRuntime from "plotly.js-dist-min";
import type { JournalStyle, ModuleProcessResponse, ResidualData } from "../types";

const JOURNAL_THEME: Record<
  JournalStyle,
  {
    colors: string[];
    font: string;
    mirror: boolean | "ticks";
    ticks: "outside" | "inside";
    lw: number;
    fitColor: string;
  }
> = {
  nature: {
    colors: ["#1F4E79", "#B83B2A", "#2E7D32", "#7B4B94", "#D97706", "#008080"],
    font: "Arial, Microsoft YaHei, sans-serif",
    mirror: false,
    ticks: "outside",
    lw: 2,
    fitColor: "#DC2626",
  },
  adv_mater: {
    colors: ["#0B3C5D", "#D92B2B", "#1B7F5C", "#E07A1F", "#5B3A82", "#117A8B"],
    font: "Arial, Microsoft YaHei, sans-serif",
    mirror: "ticks",
    ticks: "inside",
    lw: 2.3,
    fitColor: "#DC2626",
  },
  chinese_core: {
    colors: ["#0F172A", "#B91C1C", "#1D4ED8", "#047857", "#92400E", "#4B5563"],
    font: "SimSun, Times New Roman, Microsoft YaHei, serif",
    mirror: "ticks",
    ticks: "inside",
    lw: 1.8,
    fitColor: "#0F172A",
  },
};

interface MainPlotlyChartProps {
  result: ModuleProcessResponse;
  journalStyle: JournalStyle;
}

export const MainPlotlyChart: React.FC<MainPlotlyChartProps> = ({
  result,
  journalStyle,
}) => {
  const divRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = divRef.current;
    if (!el) return;

    const theme = JOURNAL_THEME[journalStyle] || JOURNAL_THEME.nature;
    let procIdx = 0;

    const traces: Plotly.Data[] = result.series.map((s) => {
      if (result.plot_mode === "waterfall_3d") {
        const c = theme.colors[procIdx++ % theme.colors.length];
        return {
          type: "scatter3d",
          mode: "lines",
          name: s.name,
          x: s.x,
          y: s.z ?? s.x.map(() => procIdx),
          z: s.y,
          line: { color: c, width: 3 },
        } as Plotly.Data;
      }

      const dashMap: Record<string, "solid" | "dash" | "dot"> = {
        solid: "solid",
        dashed: "dash",
        dotted: "dot",
      };

      if (s.kind === "raw") {
        const useMarkers = s.show_markers;
        return {
          type: "scatter",
          mode: useMarkers ? "markers" : "lines",
          name: s.name,
          x: s.x,
          y: s.y,
          yaxis: s.yaxis === "y2" ? "y2" : "y",
          marker: { color: useMarkers ? theme.colors[0] : "#64748B", size: 6, symbol: "circle-open" },
          line: { color: "#64748B", width: 1.3 },
          opacity: useMarkers ? 0.85 : 0.55,
        };
      }

      if (s.kind === "baseline") {
        return {
          type: "scatter",
          mode: "lines",
          name: s.name,
          x: s.x,
          y: s.y,
          line: { color: "#94A3B8", width: 1.4, dash: "dash" },
        };
      }

      if (s.kind === "fit") {
        return {
          type: "scatter",
          mode: "lines",
          name: s.name,
          x: s.x,
          y: s.y,
          yaxis: s.yaxis === "y2" ? "y2" : "y",
          line: { color: theme.fitColor, width: theme.lw + 0.4, dash: dashMap[s.line_style] || "solid" },
        };
      }

      const c = theme.colors[procIdx % theme.colors.length];
      procIdx++;
      return {
        type: "scatter",
        mode: s.show_markers ? "lines+markers" : "lines",
        name: s.name,
        x: s.x,
        y: s.y,
        yaxis: s.yaxis === "y2" ? "y2" : "y",
        marker: { color: c, size: 5 },
        line: {
          color: c,
          width: s.kind === "component" ? 1.4 : theme.lw,
          dash: s.kind === "component" ? "dash" : dashMap[s.line_style] || "solid",
        },
      };
    });

    const annotations: Partial<Plotly.Annotations>[] =
      result.plot_mode === "waterfall_3d"
        ? []
        : result.annotations.slice(0, 14).map((a) => ({
            x: a.x,
            y: a.y,
            text: a.text.replace(/\n/g, "<br>"),
            showarrow: true,
            arrowhead: 0,
            ax: a.ax_offset[0],
            ay: -a.ax_offset[1],
            bgcolor: "rgba(255,255,255,0.92)",
            bordercolor: "#CBD5E1",
            borderwidth: 0.8,
            borderpad: 3,
            font: { size: 10, color: "#0F172A", family: theme.font },
            arrowcolor: "#64748B",
            arrowwidth: 1,
          }));

    const layout: Partial<Plotly.Layout> = {
      paper_bgcolor: "#FFFFFF",
      plot_bgcolor: "#FFFFFF",
      font: { family: theme.font, size: 12, color: "#0F172A" },
      title: { text: result.title, font: { size: 13.5, color: "#0F172A" }, y: 0.97 },
      margin: { t: 74, r: result.y2_label ? 66 : 24, b: 52, l: 68 },
      legend: {
        orientation: "h",
        x: 0,
        y: 1.02,
        xanchor: "left",
        yanchor: "bottom",
        font: { size: 10.5 },
        bgcolor: "rgba(255,255,255,0.8)",
      },
      annotations,
      xaxis: {
        title: { text: result.x_label },
        autorange: result.invert_x ? "reversed" : true,
        showline: true,
        linecolor: "#0F172A",
        linewidth: 1.2,
        mirror: theme.mirror,
        ticks: theme.ticks,
        gridcolor: "#F1F5F9",
        zeroline: false,
      },
      yaxis: {
        title: { text: result.y_label },
        showline: true,
        linecolor: "#0F172A",
        linewidth: 1.2,
        mirror: theme.mirror,
        ticks: theme.ticks,
        gridcolor: "#F1F5F9",
        zeroline: false,
        ...(result.equal_aspect ? { scaleanchor: "x", scaleratio: 1 } : {}),
      },
    };

    if (result.plot_mode === "dual_y" && result.y2_label) {
      layout.yaxis2 = {
        title: { text: result.y2_label },
        overlaying: "y",
        side: "right",
        showline: true,
        linecolor: "#0F172A",
        linewidth: 1.2,
        ticks: theme.ticks,
        showgrid: false,
      };
    }

    if (result.plot_mode === "waterfall_3d") {
      layout.scene = {
        xaxis: { title: { text: result.x_label }, backgroundcolor: "#FFFFFF" },
        yaxis: { title: { text: "Sample Index" }, backgroundcolor: "#FFFFFF" },
        zaxis: { title: { text: result.y_label }, backgroundcolor: "#FFFFFF" },
      };
    }

    PlotlyRuntime.react(el, traces, layout, {
      responsive: true,
      displaylogo: false,
    });
  }, [result, journalStyle]);

  useEffect(() => {
    const el = divRef.current;
    return () => {
      if (el) PlotlyRuntime.purge(el);
    };
  }, []);

  return <div ref={divRef} className="h-[360px] w-full" />;
};

interface ResidualPlotChartProps {
  residual: ResidualData;
  rSquared: number;
  invertX?: boolean;
  journalStyle: JournalStyle;
}

export const ResidualPlotChart: React.FC<ResidualPlotChartProps> = ({
  residual,
  rSquared,
  invertX = false,
  journalStyle,
}) => {
  const divRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = divRef.current;
    if (!el) return;
    const theme = JOURNAL_THEME[journalStyle] || JOURNAL_THEME.nature;

    const traces: Plotly.Data[] = [
      {
        type: "scatter",
        mode: "lines",
        name: "Residual (Obs - Fit)",
        x: residual.x,
        y: residual.y,
        line: { color: theme.colors[0], width: 1.4 },
      },
    ];
    if (residual.y_imag && residual.y_imag.length === residual.x.length) {
      traces.push({
        type: "scatter",
        mode: "lines",
        name: "Imag Residual",
        x: residual.x,
        y: residual.y_imag,
        line: { color: theme.colors[1], width: 1.4, dash: "dash" },
      });
    }

    const shortResYLabel =
      residual.y_label.length > 18 ? "Residual (Obs - Fit)" : residual.y_label;

    const layout: Partial<Plotly.Layout> = {
      paper_bgcolor: "#FFFFFF",
      plot_bgcolor: "#FFFFFF",
      font: { family: theme.font, size: 11, color: "#0F172A" },
      title: {
        text: `残差图 Residual Plot (R² = ${rSquared.toFixed(4)}, RMSE = ${residual.rmse.toPrecision(4)})`,
        font: { size: 11.5, color: "#334155" },
        x: 0.08,
        y: 0.94,
      },
      margin: { t: 36, r: 24, b: 44, l: 68 },
      legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 1, xanchor: "right", font: { size: 10 } },
      shapes: [
        {
          type: "line",
          xref: "paper",
          x0: 0,
          x1: 1,
          yref: "y",
          y0: 0,
          y1: 0,
          line: { color: "#94A3B8", width: 1, dash: "dot" },
        },
      ],
      xaxis: {
        title: { text: residual.x_label },
        autorange: invertX ? "reversed" : true,
        showline: true,
        linecolor: "#0F172A",
        linewidth: 1,
        mirror: true,
        ticks: theme.ticks,
        gridcolor: "#F1F5F9",
      },
      yaxis: {
        title: { text: shortResYLabel, font: { size: 10.5 } },
        showline: true,
        linecolor: "#0F172A",
        linewidth: 1,
        mirror: true,
        ticks: theme.ticks,
        gridcolor: "#F1F5F9",
        zeroline: false,
      },
    };

    PlotlyRuntime.react(el, traces, layout, { responsive: true, displaylogo: false });
  }, [residual, rSquared, invertX, journalStyle]);

  useEffect(() => {
    const el = divRef.current;
    return () => {
      if (el) PlotlyRuntime.purge(el);
    };
  }, []);

  return <div ref={divRef} className="h-[175px] w-full" />;
};
