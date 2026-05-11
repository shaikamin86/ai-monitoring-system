"use client";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { format, parseISO } from "date-fns";
import { TrendPoint } from "@/types";
import { Activity } from "lucide-react";

interface TrendChartProps {
  data: TrendPoint[];
  title: string;
  showSentiment?: boolean;
  height?: number;
}

const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: unknown[]; label?: string }) => {
  if (!active || !payload?.length) return null;
  const entries = payload as Array<{ name: string; value: number; color: string }>;
  return (
    <div className="glass-card border border-bg-border-bright rounded-lg p-3 shadow-card text-[11px] font-mono min-w-[140px]">
      <div className="text-text-muted mb-2 pb-2 border-b border-bg-border text-[10px] tracking-wider">{label}</div>
      {entries.map((entry) => (
        <div key={entry.name} className="flex items-center justify-between gap-4 py-0.5">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: entry.color }} />
            <span className="text-text-secondary capitalize">{entry.name}</span>
          </div>
          <span className="font-semibold text-text-primary tabular-nums">{entry.value.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
};

const LEGEND_ITEMS = [
  { key: "count", label: "Total", color: "#00d4ff" },
  { key: "negative", label: "Negative", color: "#ff2d55" },
  { key: "positive", label: "Positive", color: "#00e87a" },
];

export function TrendChart({ data, title, showSentiment = true, height = 220 }: TrendChartProps) {
  const formatted = data.map((d) => ({
    ...d,
    time: format(parseISO(d.time), "HH:mm"),
  }));

  return (
    <div className="glass-card rounded-xl border border-bg-border panel-shine h-full">
      {/* Header */}
      <div className="px-5 pt-5 pb-4 flex items-center justify-between border-b border-bg-border/50">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center">
            <Activity className="w-3.5 h-3.5 text-accent-cyan" />
          </div>
          <div>
            <div className="text-[12px] font-semibold text-text-primary">{title}</div>
            <div className="text-[10px] font-mono text-text-muted">24H ROLLING WINDOW</div>
          </div>
        </div>

        {/* Legend */}
        {showSentiment && (
          <div className="flex items-center gap-4">
            {LEGEND_ITEMS.map((item) => (
              <div key={item.key} className="flex items-center gap-1.5 text-[10px] font-mono text-text-muted">
                <div className="w-6 h-0.5 rounded-full" style={{ backgroundColor: item.color }} />
                <span>{item.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="px-2 py-4">
        <ResponsiveContainer width="100%" height={height}>
          <AreaChart data={formatted} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="gradTotal" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradNeg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ff2d55" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#ff2d55" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradPos" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00e87a" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#00e87a" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(22,32,53,0.8)"
              vertical={false}
            />
            <XAxis
              dataKey="time"
              tick={{ fill: "#4a5f7a", fontSize: 10, fontFamily: "JetBrains Mono" }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: "#4a5f7a", fontSize: 10, fontFamily: "JetBrains Mono" }}
              tickLine={false}
              axisLine={false}
              width={36}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: "rgba(0,212,255,0.15)", strokeWidth: 1 }} />

            <Area
              type="monotone"
              dataKey="count"
              name="Total"
              stroke="#00d4ff"
              strokeWidth={2}
              fill="url(#gradTotal)"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0, fill: "#00d4ff" }}
            />
            {showSentiment && (
              <>
                <Area
                  type="monotone"
                  dataKey="negative"
                  name="Negative"
                  stroke="#ff2d55"
                  strokeWidth={1.5}
                  fill="url(#gradNeg)"
                  dot={false}
                  activeDot={{ r: 3, strokeWidth: 0, fill: "#ff2d55" }}
                />
                <Area
                  type="monotone"
                  dataKey="positive"
                  name="Positive"
                  stroke="#00e87a"
                  strokeWidth={1.5}
                  fill="url(#gradPos)"
                  dot={false}
                  activeDot={{ r: 3, strokeWidth: 0, fill: "#00e87a" }}
                />
              </>
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
