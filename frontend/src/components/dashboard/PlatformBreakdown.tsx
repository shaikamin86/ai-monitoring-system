"use client";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { PLATFORM_CONFIG } from "@/lib/utils";
import { Platform } from "@/types";
import { Radio } from "lucide-react";

interface PlatformData {
  platform: string;
  count: number;
  positive: number;
  negative: number;
  neutral: number;
  avg_engagement: number;
}

interface PlatformBreakdownProps {
  platforms: PlatformData[];
}

const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: unknown[]; label?: string }) => {
  if (!active || !payload?.length) return null;
  const entries = payload as Array<{ value: number; color: string; dataKey: string }>;
  const totalEntry = entries[0];
  return (
    <div className="glass-card border border-bg-border-bright rounded-lg p-3 text-[11px] font-mono shadow-card min-w-[130px]">
      <div className="text-text-muted mb-2 pb-2 border-b border-bg-border text-[10px] tracking-wider">{label}</div>
      <div className="flex items-center justify-between">
        <span className="text-text-secondary">Posts</span>
        <span className="font-semibold text-text-primary">{totalEntry.value.toLocaleString()}</span>
      </div>
    </div>
  );
};

export function PlatformBreakdown({ platforms }: PlatformBreakdownProps) {
  const data = platforms
    .map((p) => ({
      ...p,
      name: p.platform.charAt(0).toUpperCase() + p.platform.slice(1),
      color: PLATFORM_CONFIG[p.platform as Platform]?.color || "#4a5f7a",
    }))
    .sort((a, b) => b.count - a.count);

  const maxCount = Math.max(...data.map((d) => d.count), 1);

  return (
    <div className="glass-card rounded-xl border border-bg-border flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 flex items-center gap-2.5 border-b border-bg-border/50">
        <div className="w-7 h-7 rounded-lg bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center">
          <Radio className="w-3.5 h-3.5 text-accent-cyan" />
        </div>
        <div>
          <div className="text-[12px] font-semibold text-text-primary">Platform Activity</div>
          <div className="text-[10px] font-mono text-text-muted">24H VOLUME</div>
        </div>
      </div>

      <div className="flex-1 p-4 flex flex-col gap-4">
        {/* Bar chart */}
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }} barCategoryGap="30%">
            <XAxis
              dataKey="name"
              tick={{ fill: "#4a5f7a", fontSize: 9, fontFamily: "JetBrains Mono" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fill: "#4a5f7a", fontSize: 9, fontFamily: "JetBrains Mono" }}
              tickLine={false}
              axisLine={false}
              width={32}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(0,212,255,0.04)", radius: 4 }} />
            <Bar dataKey="count" radius={[3, 3, 0, 0]}>
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.color} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Platform stats rows */}
        <div className="space-y-2.5 border-t border-bg-border/50 pt-3">
          {data.slice(0, 5).map((p) => {
            const pct = ((p.count / maxCount) * 100).toFixed(0);
            const negPct = p.count > 0 ? ((p.negative / p.count) * 100).toFixed(0) : "0";
            return (
              <div key={p.platform} className="space-y-1">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: p.color }} />
                  <span className="text-[11px] font-mono text-text-secondary flex-1">{p.name}</span>
                  <span className="text-[11px] font-mono font-semibold text-text-primary tabular-nums">
                    {p.count.toLocaleString()}
                  </span>
                  {Number(negPct) > 30 && (
                    <span className="text-[9px] font-mono text-accent-red/70 bg-accent-red/10 px-1.5 py-0.5 rounded">
                      {negPct}% neg
                    </span>
                  )}
                </div>
                <div className="h-1 w-full rounded-full bg-bg-elevated overflow-hidden ml-4">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${pct}%`, backgroundColor: p.color, opacity: 0.7 }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
