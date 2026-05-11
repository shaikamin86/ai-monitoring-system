"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getInfluencers, flagInfluencer } from "@/lib/api";
import { Influencer } from "@/types";
import { useState } from "react";
import { PLATFORM_CONFIG, SENTIMENT_CONFIG, cn, formatRelative } from "@/lib/utils";
import { Users, Flag, TrendingUp, Filter } from "lucide-react";
import toast from "react-hot-toast";
import { motion } from "framer-motion";

function InfluencerCard({ inf, index, onFlag }: {
  inf: Influencer;
  index: number;
  onFlag: (id: string) => void;
}) {
  const platformCfg = PLATFORM_CONFIG[inf.platform];
  const sentimentCfg = SENTIMENT_CONFIG[inf.sentiment_lean];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
      className={cn(
        "glass-card rounded-lg border p-5 hover:border-accent-cyan/20 transition-all",
        inf.is_flagged ? "border-accent-red/30" : "border-bg-border"
      )}
    >
      <div className="flex items-start gap-4">
        {/* Avatar placeholder */}
        <div
          className="w-12 h-12 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
          style={{
            backgroundColor: `${platformCfg?.color || "#475569"}20`,
            border: `1px solid ${platformCfg?.color || "#475569"}40`,
            color: platformCfg?.color || "#475569",
          }}
        >
          {inf.username?.slice(0, 2).toUpperCase()}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-text-primary">@{inf.username}</span>
                {inf.verified && <span className="text-accent-cyan text-[11px]">✓ VERIFIED</span>}
                {inf.is_flagged && (
                  <span className="text-[10px] font-mono text-accent-red bg-accent-red/10 border border-accent-red/20 px-1.5 py-0.5 rounded">
                    ⚑ FLAGGED
                  </span>
                )}
              </div>
              <div className="text-[11px] font-mono text-text-muted capitalize">{inf.platform}</div>
            </div>

            <div className="text-right">
              <div className="text-lg font-bold font-mono text-accent-cyan">{inf.influence_score.toFixed(1)}</div>
              <div className="text-[10px] font-mono text-text-muted">INFLUENCE</div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 mt-3">
            <div>
              <div className="text-[10px] font-mono text-text-muted">FOLLOWERS</div>
              <div className="text-sm font-mono text-text-primary">
                {inf.followers_count >= 1000 ? `${(inf.followers_count / 1000).toFixed(0)}K` : inf.followers_count}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-mono text-text-muted">ENG. RATE</div>
              <div className="text-sm font-mono text-text-primary">{inf.avg_engagement_rate.toFixed(2)}%</div>
            </div>
            <div>
              <div className="text-[10px] font-mono text-text-muted">SENTIMENT</div>
              <div className={cn("text-sm font-mono capitalize", sentimentCfg.color)}>{inf.sentiment_lean}</div>
            </div>
          </div>

          {inf.primary_topics?.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {inf.primary_topics.slice(0, 4).map((topic) => (
                <span key={topic} className="text-[10px] font-mono bg-bg-elevated border border-bg-border px-2 py-0.5 rounded text-text-muted">
                  {topic}
                </span>
              ))}
            </div>
          )}

          <div className="mt-2 flex items-center justify-between">
            <div className="text-[10px] font-mono text-text-muted">
              Active {formatRelative(inf.last_active)}
            </div>
            {!inf.is_flagged && (
              <button
                onClick={() => onFlag(inf.id)}
                className="flex items-center gap-1 text-[10px] font-mono text-text-muted hover:text-accent-red transition-colors"
              >
                <Flag className="w-3 h-3" /> Flag
              </button>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default function InfluencersPage() {
  const [platformFilter, setPlatformFilter] = useState<string | undefined>();
  const [showFlagged, setShowFlagged] = useState(false);
  const [sortBy, setSortBy] = useState("influence_score");
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["influencers", platformFilter, showFlagged, sortBy],
    queryFn: () => getInfluencers({
      platform: platformFilter,
      is_flagged: showFlagged ? true : undefined,
      sort_by: sortBy,
      limit: 50,
    }),
    refetchInterval: 120_000,
  });

  const { mutate: doFlag } = useMutation({
    mutationFn: (id: string) => flagInfluencer(id, "Flagged by operator"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["influencers"] });
      toast.success("Influencer flagged for review");
    },
  });

  const PLATFORMS = ["twitter", "facebook", "instagram", "tiktok", "reddit", "telegram"];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] font-mono text-text-muted tracking-widest uppercase mb-1">Network Analysis</div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
            <Users className="w-6 h-6 text-accent-cyan" />
            Influencer Tracking
          </h1>
        </div>
        <div className="text-[11px] font-mono text-text-muted">{data?.total || 0} MONITORED</div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Filter className="w-4 h-4 text-text-muted" />
        {PLATFORMS.map((p) => (
          <button
            key={p}
            onClick={() => setPlatformFilter(platformFilter === p ? undefined : p)}
            className={cn(
              "text-[11px] font-mono px-3 py-1.5 rounded border transition-all capitalize",
              platformFilter === p
                ? "border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan"
                : "border-bg-border text-text-muted hover:text-text-secondary"
            )}
          >
            {p}
          </button>
        ))}

        <div className="h-4 w-px bg-bg-border" />

        <button
          onClick={() => setShowFlagged(!showFlagged)}
          className={cn(
            "flex items-center gap-1.5 text-[11px] font-mono px-3 py-1.5 rounded border transition-all",
            showFlagged ? "border-accent-red/40 bg-accent-red/10 text-accent-red" : "border-bg-border text-text-muted"
          )}
        >
          <Flag className="w-3 h-3" /> Flagged
        </button>

        <div className="h-4 w-px bg-bg-border" />

        <div className="flex items-center gap-2">
          <TrendingUp className="w-3 h-3 text-text-muted" />
          {["influence_score", "followers_count", "avg_engagement_rate"].map((s) => (
            <button
              key={s}
              onClick={() => setSortBy(s)}
              className={cn(
                "text-[11px] font-mono px-2 py-1 rounded transition-all",
                sortBy === s ? "text-accent-cyan" : "text-text-muted hover:text-text-secondary"
              )}
            >
              {s.replace(/_/g, " ").split(" ").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton rounded-lg h-40" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(data?.influencers || []).map((inf, i) => (
            <InfluencerCard key={inf.id} inf={inf} index={i} onFlag={doFlag} />
          ))}
        </div>
      )}
    </div>
  );
}
