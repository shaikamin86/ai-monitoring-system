"use client";
import { Hashtag } from "@/types";
import { cn } from "@/lib/utils";
import { Hash, TrendingUp } from "lucide-react";
import { motion } from "framer-motion";

interface HashtagCloudProps {
  hashtags: Hashtag[];
}

export function HashtagCloud({ hashtags }: HashtagCloudProps) {
  const max = Math.max(...hashtags.map((h) => h.total_count), 1);
  const sorted = [...hashtags].sort((a, b) => b.total_count - a.total_count);

  function getStyle(count: number): {
    size: string;
    weight: string;
    opacity: number;
    colorClass: string;
  } {
    const ratio = count / max;
    if (ratio > 0.8) return { size: "text-base", weight: "font-bold", opacity: 1, colorClass: "text-accent-cyan" };
    if (ratio > 0.6) return { size: "text-sm", weight: "font-semibold", opacity: 0.9, colorClass: "text-accent-cyan/80" };
    if (ratio > 0.4) return { size: "text-sm", weight: "font-medium", opacity: 0.75, colorClass: "text-text-primary" };
    if (ratio > 0.2) return { size: "text-[13px]", weight: "font-normal", opacity: 0.6, colorClass: "text-text-secondary" };
    return { size: "text-xs", weight: "font-normal", opacity: 0.45, colorClass: "text-text-muted" };
  }

  return (
    <div className="glass-card rounded-xl border border-bg-border flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between border-b border-bg-border/50">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-accent-purple/10 border border-accent-purple/20 flex items-center justify-center">
            <Hash className="w-3.5 h-3.5 text-accent-purple-bright" />
          </div>
          <div>
            <div className="text-[12px] font-semibold text-text-primary">Trending Hashtags</div>
            <div className="text-[10px] font-mono text-text-muted">LIVE SIGNAL</div>
          </div>
        </div>
        <div className="flex items-center gap-1 text-[10px] font-mono text-accent-green">
          <TrendingUp className="w-3 h-3" />
          <span>{hashtags.length} TAGS</span>
        </div>
      </div>

      <div className="flex-1 p-5 flex flex-col gap-5">
        {/* Tag cloud */}
        <div className="flex flex-wrap gap-2 content-start">
          {sorted.map((tag, i) => {
            const { size, weight, opacity, colorClass } = getStyle(tag.total_count);
            return (
              <motion.div
                key={tag.tag}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.025 }}
                style={{ opacity }}
                className={cn(
                  "inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-bg-border hover:border-accent-cyan/25 hover:bg-accent-cyan/[0.04] cursor-pointer transition-all duration-150 group",
                  size,
                  weight,
                  colorClass
                )}
              >
                <span className="text-text-dim group-hover:text-accent-cyan/40 transition-colors">#</span>
                <span className="font-mono">{tag.tag}</span>
                <span className="text-[10px] text-text-dim ml-0.5 tabular-nums">
                  {tag.total_count >= 1000 ? `${(tag.total_count / 1000).toFixed(1)}k` : tag.total_count}
                </span>
              </motion.div>
            );
          })}
        </div>

        {/* Top 5 ranked list */}
        {sorted.length > 0 && (
          <div className="border-t border-bg-border/50 pt-4">
            <div className="text-[10px] font-mono text-text-dim tracking-wider uppercase mb-3">Top Trending</div>
            <div className="space-y-2">
              {sorted.slice(0, 5).map((tag, i) => {
                const pct = ((tag.total_count / max) * 100).toFixed(0);
                return (
                  <div key={tag.tag} className="flex items-center gap-3">
                    <span className="text-[10px] font-mono text-text-dim w-4 text-right flex-shrink-0">{i + 1}</span>
                    <span className="text-[12px] font-mono text-text-secondary flex-shrink-0">#{tag.tag}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-bg-elevated overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ delay: i * 0.08 + 0.3, duration: 0.6, ease: "easeOut" }}
                        className="h-full rounded-full bg-gradient-to-r from-accent-cyan to-accent-cyan/50"
                      />
                    </div>
                    <span className="text-[10px] font-mono text-text-muted w-14 text-right tabular-nums flex-shrink-0">
                      {tag.total_count.toLocaleString()}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
