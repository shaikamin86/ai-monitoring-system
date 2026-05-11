"use client";
import { useQuery } from "@tanstack/react-query";
import { getNarratives } from "@/lib/api";
import { Narrative } from "@/types";
import { useState } from "react";
import Link from "next/link";
import { formatRelative, NARRATIVE_STATUS_CONFIG, getThreatColor, getThreatBg, cn } from "@/lib/utils";
import { Layers, Filter, ArrowUpDown, Users, MessageSquare, TrendingUp } from "lucide-react";
import { motion } from "framer-motion";

const STATUS_OPTIONS = ["all", "emerging", "active", "declining", "dormant"];
const SORT_OPTIONS = [
  { value: "virality_score", label: "Virality" },
  { value: "threat_level", label: "Threat Level" },
  { value: "post_count", label: "Volume" },
  { value: "last_activity", label: "Recent" },
];

function NarrativeCard({ narrative, index }: { narrative: Narrative; index: number }) {
  const statusConfig = NARRATIVE_STATUS_CONFIG[narrative.status];
  const totalSentiment = Object.values(narrative.sentiment_distribution).reduce((a, b) => a + b, 0);
  const negPct = totalSentiment > 0 ? (narrative.sentiment_distribution.negative / totalSentiment) * 100 : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
    >
      <Link href={`/narratives/${narrative.id}`}>
        <div className={cn(
          "glass-card rounded-lg border p-5 hover:border-accent-cyan/30 transition-all cursor-pointer group",
          narrative.threat_level >= 7 ? "border-accent-red/20" : "border-bg-border"
        )}>
          {/* Header */}
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <div className={cn("flex items-center gap-1.5 text-[10px] font-mono", statusConfig.color)}>
                  <span className={cn("w-1.5 h-1.5 rounded-full", statusConfig.dot)} />
                  {statusConfig.label}
                </div>
                {narrative.is_coordinated && (
                  <span className="text-[10px] font-mono text-accent-red bg-accent-red/10 border border-accent-red/20 px-1.5 py-0.5 rounded">
                    COORDINATED
                  </span>
                )}
              </div>
              <h3 className="text-sm font-semibold text-text-primary group-hover:text-accent-cyan transition-colors line-clamp-2">
                {narrative.title}
              </h3>
            </div>

            {/* Threat level */}
            <div className={cn("flex-shrink-0 text-center px-3 py-1.5 rounded border", getThreatBg(narrative.threat_level))}>
              <div className={cn("text-xl font-bold font-mono", getThreatColor(narrative.threat_level))}>
                {narrative.threat_level}
              </div>
              <div className="text-[9px] font-mono text-text-muted">THREAT</div>
            </div>
          </div>

          {/* Summary */}
          {narrative.summary && (
            <p className="text-[12px] text-text-muted line-clamp-2 mb-3">{narrative.summary}</p>
          )}

          {/* Key themes */}
          <div className="flex flex-wrap gap-1 mb-3">
            {narrative.key_themes.slice(0, 4).map((theme) => (
              <span key={theme} className="text-[10px] font-mono bg-bg-elevated border border-bg-border px-2 py-0.5 rounded text-text-secondary">
                {theme}
              </span>
            ))}
          </div>

          {/* Stats */}
          <div className="flex items-center gap-4 text-[11px] font-mono text-text-muted">
            <div className="flex items-center gap-1">
              <MessageSquare className="w-3 h-3" />
              <span>{narrative.post_count.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-1">
              <Users className="w-3 h-3" />
              <span>{narrative.unique_authors.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              <span>{narrative.virality_score.toFixed(0)}</span>
            </div>

            {/* Sentiment bar */}
            <div className="ml-auto flex items-center gap-1">
              <div className="w-16 h-1.5 rounded-full bg-bg-elevated overflow-hidden">
                <div className="h-full bg-accent-red rounded-full" style={{ width: `${negPct}%` }} />
              </div>
              <span className={negPct > 60 ? "text-accent-red" : "text-text-muted"}>
                {negPct.toFixed(0)}% neg
              </span>
            </div>

            <span className="text-text-muted">{formatRelative(narrative.last_activity)}</span>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

export default function NarrativesPage() {
  const [status, setStatus] = useState("all");
  const [sortBy, setSortBy] = useState("virality_score");
  const [minThreat, setMinThreat] = useState<number | undefined>();

  const { data, isLoading } = useQuery({
    queryKey: ["narratives", status, sortBy, minThreat],
    queryFn: () => getNarratives({
      status: status === "all" ? undefined : status,
      sort_by: sortBy,
      min_threat: minThreat,
      limit: 50,
    }),
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] font-mono text-text-muted tracking-widest uppercase mb-1">
            Intelligence Analysis
          </div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
            <Layers className="w-6 h-6 text-accent-cyan" />
            Narrative Intelligence
          </h1>
        </div>
        <div className="text-[11px] font-mono text-text-muted">
          {data?.total || 0} NARRATIVES TRACKED
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Filter className="w-4 h-4 text-text-muted" />

        {/* Status filter */}
        <div className="flex gap-1">
          {STATUS_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={cn(
                "text-[11px] font-mono px-3 py-1.5 rounded border transition-all capitalize",
                status === s
                  ? "border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan"
                  : "border-bg-border text-text-muted hover:border-bg-elevated hover:text-text-secondary"
              )}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-bg-border" />

        {/* Sort */}
        <div className="flex items-center gap-2">
          <ArrowUpDown className="w-3 h-3 text-text-muted" />
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setSortBy(opt.value)}
              className={cn(
                "text-[11px] font-mono px-2.5 py-1 rounded transition-all",
                sortBy === opt.value
                  ? "text-accent-cyan"
                  : "text-text-muted hover:text-text-secondary"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-bg-border" />

        {/* Threat filter */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-text-muted">Min Threat:</span>
          {[undefined, 3, 5, 7, 9].map((t) => (
            <button
              key={t ?? "all"}
              onClick={() => setMinThreat(t)}
              className={cn(
                "text-[11px] font-mono px-2 py-1 rounded transition-all",
                minThreat === t ? getThreatColor(t || 0) + " font-bold" : "text-text-muted hover:text-text-secondary"
              )}
            >
              {t === undefined ? "ALL" : `${t}+`}
            </button>
          ))}
        </div>
      </div>

      {/* Narratives grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton rounded-lg h-48" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {(data?.narratives || []).map((narrative, i) => (
            <NarrativeCard key={narrative.id} narrative={narrative} index={i} />
          ))}
        </div>
      )}

      {data?.narratives?.length === 0 && (
        <div className="text-center py-16">
          <Layers className="w-10 h-10 mx-auto mb-3 text-text-muted opacity-40" />
          <div className="text-text-muted font-mono">No narratives match current filters</div>
        </div>
      )}
    </div>
  );
}
