"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, AreaSeries, type IChartApi } from "lightweight-charts";

interface DataPoint {
  time: string;
  count: number;
}

interface AssetTrendChartProps {
  data: DataPoint[];
  color?: string;
  height?: number;
}

export default function AssetTrendChart({
  data,
  color = "#22d3ee",
  height = 200,
}: AssetTrendChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "rgb(107, 114, 128)",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.03)" },
        horzLines: { color: "rgba(255,255,255,0.03)" },
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.05)",
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.05)",
      },
      crosshair: {
        horzLine: { color: "rgba(255,255,255,0.1)" },
        vertLine: { color: "rgba(255,255,255,0.1)" },
      },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: color,
      topColor: `${color}33`,
      bottomColor: `${color}05`,
      lineWidth: 2,
    });

    const chartData = data.map((d) => ({
      time: Math.floor(new Date(d.time).getTime() / 1000) as unknown as Parameters<typeof series.setData>[0][number]["time"],
      value: d.count,
    }));

    if (chartData.length > 0) {
      series.setData(chartData);
      chart.timeScale().fitContent();
    }

    chartRef.current = chart;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [data, color, height]);

  return <div ref={containerRef} style={{ width: "100%" }} />;
}
