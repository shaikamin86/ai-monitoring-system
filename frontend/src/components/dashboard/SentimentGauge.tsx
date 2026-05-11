"use client";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { Sentiment } from "@/types";
import { BarChart2 } from "lucide-react";

interface SentimentGaugeProps {
  distribution: Record<Sentiment, number>;
}

const SENTIMENT_META: Record<Sentiment, { color: string; hex: string; label: string; bg: string }> = {
  positive: { color: "text-accent-green", hex: "#00e87a", label: "Positive", bg: "bg-accent-green/10" },
  negative: { color: "text-accent-red",   hex: "#ff2d55", label: "Negative", bg: "bg-accent-red/10" },
  neutral:  { color: "text-text-secondary", hex: "#4a5f7a", label: "Neutral",  bg: "bg-text-muted/10" },
  mixed:    { color: "text-accent-amber", hex: "#f59e0b", label: "Mixed",    bg: "bg-accent-amber/10" },
};

const SENTIMENT_ORDER: Sentiment[] = ["positive", "negative", "neutral", "mixed"];

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: unknown[] }) => {
  if (!active || !payload?.length) return null;
  const entry = (payload as Array<{ name: string; value: number; payload: { pct: string; hex: string } }>)[0];
  return (
    <div className="glass-card border border-bg-border-bright rounded-lg p-2.5 text-[11px] font-mono shadow-card">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.payload.hex }} />
        <span className="text-text-secondary">{entry.name}</span>
        <span className="text-text-primary font-semibold ml-2">{entry.payload.pct}%</span>
      </div>
    </div>
  );
};

export function SentimentGauge({ distribution }: SentimentGaugeProps) {
  const total = Object.values(distribution).reduce((a, b) => a + b, 0);

  const data = SENTIMENT_ORDER
    .filter((key) => (distribution[key] || 0) > 0)
    .map((key) => ({
      name: SENTIMENT_META[key].label,
      value: distribution[key] || 0,
      pct: total > 0 ? ((distribution[key] / total) * 100).toFixed(1) : "0",
      hex: SENTIMENT_META[key].hex,
      meta: SENTIMENT_META[key],
    }));

  const dominant = [...data].sort((a, b) => b.value - a.value)[0];

  return (
    <div className="glass-card rounded-xl border border-bg-border panel-shine h-full flex flex-col">
      {/* Header */}
      <div className="px-5 pt-5 pb-4 flex items-center gap-2.5 border-b border-bg-border/50">
        <div className="w-7 h-7 rounded-lg bg-accent-purple/10 border border-accent-purple/20 flex items-center justify-center">
          <BarChart2 className="w-3.5 h-3.5 text-accent-purple-bright" />
        </div>
        <div>
          <div className="text-[12px] font-semibold text-text-primary">Sentiment Distribution</div>
          <div className="text-[10px] font-mono text-text-muted">PUBLIC MOOD ANALYSIS</div>
        </div>
      </div>

      <div className="flex-1 flex flex-col justify-center p-5 gap-4">
        {/* Donut chart */}
        <div className="relative mx-auto">
          <ResponsiveContainer width={160} height={160}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={48}
                outerRadius={72}
                paddingAngle={2}
                dataKey="value"
                strokeWidth={0}
                startAngle={90}
                endAngle={-270}
              >
                {data.map((entry, i) => (
                  <Cell key={i} fill={entry.hex} opacity={0.9} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>

          {/* Center label */}
          <div className="absolute inset-0 flex items-center justify-center flex-col pointer-events-none">
            <div className="text-2xl font-bold font-mono tabular-nums" style={{ color: dominant?.hex }}>
              {dominant?.pct}%
            </div>
            <div className="text-[9px] font-mono text-text-muted tracking-wider uppercase mt-0.5">
              {dominant?.name}
            </div>
          </div>
        </div>

        {/* Legend with progress bars */}
        <div className="space-y-2.5">
          {data.map((entry) => (
            <div key={entry.name} className="space-y-1">
              <div className="flex items-center justify-between text-[11px] font-mono">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: entry.hex }} />
                  <span className="text-text-secondary">{entry.name}</span>
                </div>
                <span className="font-semibold" style={{ color: entry.hex }}>{entry.pct}%</span>
              </div>
              <div className="h-1 w-full rounded-full bg-bg-elevated overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${entry.pct}%`, backgroundColor: entry.hex, opacity: 0.85 }}
                />
              </div>
            </div>
          ))}
        </div>

        <div className="pt-2 border-t border-bg-border/50 text-[10px] font-mono text-text-muted text-center">
          {total.toLocaleString()} POSTS ANALYZED
        </div>
      </div>
    </div>
  );
}
