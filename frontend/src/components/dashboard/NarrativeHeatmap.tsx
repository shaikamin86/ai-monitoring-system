"use client";
import { Narrative } from "@/types";
import { getThreatColor, getThreatBg, formatRelative, NARRATIVE_STATUS_CONFIG } from "@/lib/utils";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { Layers, ExternalLink, MessageSquare, Users } from "lucide-react";

interface NarrativeHeatmapProps {
  narratives: Narrative[];
}

const THREAT_COLORS: Record<string, string> = {
  critical: "#ff2d55",
  high: "#f97316",
  medium: "#f59e0b",
  low: "#00e87a",
};

function getThreatHex(level: number): string {
  if (level >= 8) return THREAT_COLORS.critical;
  if (level >= 6) return THREAT_COLORS.high;
  if (level >= 4) return THREAT_COLORS.medium;
  return THREAT_COLORS.low;
}

function ThreatSegments({ level }: { level: number }) {
  return (
    <div className="flex gap-0.5 items-end h-4">
      {Array.from({ length: 10 }).map((_, i) => (
        <div
          key={i}
          className="w-1.5 rounded-sm transition-all"
          style={{
            height: `${30 + i * 7}%`,
            backgroundColor: i < level ? getThreatHex(level) : "rgba(22,32,53,0.8)",
            opacity: i < level ? (0.5 + (i / 10) * 0.5) : 1,
          }}
        />
      ))}
    </div>
  );
}

export function NarrativeHeatmap({ narratives }: NarrativeHeatmapProps) {
  const sorted = [...narratives].sort((a, b) => b.threat_level - a.threat_level).slice(0, 12);
  const topThree = sorted.slice(0, 3);
  const rest = sorted.slice(3, 10);

  return (
    <div className="glass-card rounded-xl border border-bg-border flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between border-b border-bg-border/50">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center">
            <Layers className="w-3.5 h-3.5 text-accent-cyan" />
          </div>
          <div>
            <div className="text-[12px] font-semibold text-text-primary">Narrative Intelligence</div>
            <div className="text-[10px] font-mono text-text-muted">EMERGING THREAT MAP</div>
          </div>
        </div>
        <Link href="/narratives" className="flex items-center gap-1 text-[10px] font-mono text-accent-cyan/70 hover:text-accent-cyan transition-colors">
          <span>VIEW ALL</span>
          <ExternalLink className="w-2.5 h-2.5" />
        </Link>
      </div>

      <div className="flex-1 p-4 space-y-4">
        {/* Top 3 — featured cards */}
        {topThree.length > 0 && (
          <div className="grid grid-cols-3 gap-2">
            {topThree.map((narrative, i) => {
              const hex = getThreatHex(narrative.threat_level);
              const statusCfg = NARRATIVE_STATUS_CONFIG[narrative.status];
              return (
                <Link key={narrative.id} href={`/narratives/${narrative.id}`}>
                  <motion.div
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.06 }}
                    className="heatmap-cell relative p-3 rounded-lg border cursor-pointer group overflow-hidden"
                    style={{
                      borderColor: `${hex}25`,
                      background: `linear-gradient(135deg, ${hex}0a 0%, rgba(11,21,37,0.95) 70%)`,
                    }}
                  >
                    {/* Threat level badge */}
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[9px] font-mono tracking-wider" style={{ color: `${hex}99` }}>
                        TL-{String(narrative.threat_level).padStart(2, "0")}
                      </span>
                      <span className={cn("text-[9px] font-mono", statusCfg.color)}>
                        {narrative.status.toUpperCase()}
                      </span>
                    </div>

                    <div className="text-[11px] font-semibold text-text-primary line-clamp-2 leading-tight mb-2 group-hover:text-white transition-colors">
                      {narrative.title}
                    </div>

                    <div className="flex items-center justify-between mt-auto">
                      <div className="flex items-center gap-1 text-[10px] font-mono text-text-muted">
                        <MessageSquare className="w-2.5 h-2.5" />
                        <span>{narrative.post_count.toLocaleString()}</span>
                      </div>
                      <div
                        className="text-[11px] font-bold font-mono"
                        style={{ color: hex }}
                      >
                        {narrative.threat_level}/10
                      </div>
                    </div>

                    {/* Bottom border glow on hover */}
                    <div
                      className="absolute bottom-0 left-0 right-0 h-px opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ background: `linear-gradient(90deg, transparent, ${hex}, transparent)` }}
                    />
                  </motion.div>
                </Link>
              );
            })}
          </div>
        )}

        {/* Rest — list rows */}
        <div className="space-y-0.5">
          {rest.map((narrative, i) => {
            const hex = getThreatHex(narrative.threat_level);
            return (
              <Link key={narrative.id} href={`/narratives/${narrative.id}`}>
                <motion.div
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: (i + 3) * 0.04 }}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.03] transition-colors group cursor-pointer"
                >
                  {/* Rank */}
                  <div className="w-5 text-[10px] font-mono text-text-dim text-right flex-shrink-0">
                    {(i + 4).toString().padStart(2, "0")}
                  </div>

                  {/* Title */}
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] text-text-secondary group-hover:text-text-primary transition-colors truncate">
                      {narrative.title}
                    </div>
                  </div>

                  {/* Segments */}
                  <ThreatSegments level={narrative.threat_level} />

                  {/* Score */}
                  <div className="text-[11px] font-mono font-bold w-7 text-right" style={{ color: hex }}>
                    {narrative.threat_level}
                  </div>

                  {/* Time */}
                  <div className="text-[10px] font-mono text-text-dim w-16 text-right flex-shrink-0 hidden lg:block">
                    {formatRelative(narrative.last_activity)}
                  </div>
                </motion.div>
              </Link>
            );
          })}
        </div>

        {narratives.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Layers className="w-8 h-8 text-text-dim mb-2" />
            <div className="text-[11px] font-mono text-text-muted">No active narratives</div>
          </div>
        )}
      </div>
    </div>
  );
}
