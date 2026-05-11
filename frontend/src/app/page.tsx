"use client";
import { useQuery } from "@tanstack/react-query";
import { getDashboardMetrics, getTrends, getPlatformBreakdown } from "@/lib/api";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { SentimentGauge } from "@/components/dashboard/SentimentGauge";
import { NarrativeHeatmap } from "@/components/dashboard/NarrativeHeatmap";
import { AlertsWidget } from "@/components/dashboard/AlertsWidget";
import { HashtagCloud } from "@/components/dashboard/HashtagCloud";
import { PlatformBreakdown } from "@/components/dashboard/PlatformBreakdown";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useState } from "react";
import {
  Activity, AlertTriangle, Radio,
  Layers, Globe,
} from "lucide-react";
import { DashboardMetrics } from "@/types";
import { motion } from "framer-motion";
import { format } from "date-fns";

function SkeletonCard() {
  return <div className="skeleton rounded-xl h-[130px]" />;
}

function SkeletonPanel({ height = "h-[280px]" }: { height?: string }) {
  return (
    <div className={`glass-card rounded-xl border border-bg-border overflow-hidden ${height}`}>
      <div className="p-5 border-b border-bg-border">
        <div className="flex items-center gap-2.5">
          <div className="skeleton w-7 h-7 rounded-lg" />
          <div className="space-y-1.5">
            <div className="skeleton h-3 w-32 rounded" />
            <div className="skeleton h-2 w-20 rounded" />
          </div>
        </div>
      </div>
      <div className="p-5 space-y-3">
        <div className="skeleton h-3 w-full rounded" />
        <div className="skeleton h-3 w-4/5 rounded" />
        <div className="skeleton h-3 w-3/4 rounded" />
        <div className="skeleton h-20 w-full rounded-lg mt-4" />
      </div>
    </div>
  );
}

const CONTAINER = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const ITEM = { hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };

export default function DashboardPage() {
  const [liveMetrics, setLiveMetrics] = useState<Partial<DashboardMetrics>>({});
  const now = new Date();

  const { data: metrics, isLoading } = useQuery({
    queryKey: ["dashboard-metrics"],
    queryFn: getDashboardMetrics,
    refetchInterval: 60_000,
  });

  const { data: trends, isLoading: trendsLoading } = useQuery({
    queryKey: ["trends", "24h"],
    queryFn: () => getTrends({ hours: 24, interval: "hour" }),
    refetchInterval: 300_000,
  });

  const { data: platformData, isLoading: platformLoading } = useQuery({
    queryKey: ["platform-breakdown"],
    queryFn: () => getPlatformBreakdown(24),
    refetchInterval: 300_000,
  });

  useWebSocket((msg) => {
    if (msg.type === "initial_state" || msg.type === "metrics_update") {
      setLiveMetrics(msg.data as Partial<DashboardMetrics>);
    }
  });

  const m = { ...metrics, ...liveMetrics } as DashboardMetrics;

  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="skeleton h-2.5 w-48 rounded" />
            <div className="skeleton h-7 w-64 rounded" />
          </div>
          <div className="skeleton h-9 w-52 rounded-lg" />
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => <SkeletonCard key={i} />)}
        </div>
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-12 lg:col-span-8"><SkeletonPanel height="h-[320px]" /></div>
          <div className="col-span-12 lg:col-span-4"><SkeletonPanel height="h-[320px]" /></div>
          <div className="col-span-12 lg:col-span-8"><SkeletonPanel /></div>
          <div className="col-span-12 lg:col-span-4"><SkeletonPanel /></div>
          <div className="col-span-12 lg:col-span-5"><SkeletonPanel /></div>
          <div className="col-span-12 lg:col-span-7"><SkeletonPanel /></div>
        </div>
      </div>
    );
  }

  return (
    <motion.div variants={CONTAINER} initial="hidden" animate="show" className="space-y-6">

      {/* ── Page header ── */}
      <motion.div variants={ITEM} className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[10px] font-mono text-text-muted tracking-[0.15em] uppercase mb-2">
            <Globe className="w-3 h-3" />
            <span>Malaysia Social Intelligence Platform</span>
            <span className="text-text-dim">·</span>
            <span>{format(now, "dd MMM yyyy")}</span>
          </div>
          <h1 className="text-[22px] font-bold text-text-primary tracking-tight">
            Operational Dashboard
          </h1>
          <p className="text-[13px] text-text-muted mt-1">
            Real-time narrative and sentiment monitoring across 7 platforms
          </p>
        </div>

        <div className="flex-shrink-0 flex items-center gap-2 bg-accent-green/[0.08] border border-accent-green/20 rounded-lg px-3.5 py-2.5 text-[11px] font-mono text-accent-green">
          <span className="w-2 h-2 bg-accent-green rounded-full animate-pulse" />
          <span>MONITORING ACTIVE</span>
          <span className="text-accent-green/40 mx-1">·</span>
          <span>7 PLATFORMS</span>
        </div>
      </motion.div>

      {/* ── KPI metric cards ── */}
      <motion.div variants={ITEM} className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Posts (24h)"
          value={m.total_posts_24h || 0}
          icon={Activity}
          variant="default"
        />
        <MetricCard
          label="Active Alerts"
          value={m.active_alerts || 0}
          icon={AlertTriangle}
          variant={m.critical_alerts ? "critical" : "default"}
          subvalue={m.critical_alerts ? `${m.critical_alerts} critical` : "All clear"}
          pulse={!!m.critical_alerts}
        />
        <MetricCard
          label="Active Narratives"
          value={m.active_narratives || 0}
          icon={Layers}
          variant="default"
        />
        <MetricCard
          label="Live Monitoring"
          value="ACTIVE"
          icon={Radio}
          variant="success"
          subvalue="Real-time ingestion"
          pulse
        />
      </motion.div>

      {/* ── Main content grid ── */}
      <div className="grid grid-cols-12 gap-4">

        {/* Trend chart — 8 cols */}
        <motion.div variants={ITEM} className="col-span-12 lg:col-span-8 min-h-[300px]">
          {trendsLoading
            ? <SkeletonPanel height="h-[300px]" />
            : <TrendChart data={trends || []} title="Post Volume & Sentiment" showSentiment height={230} />
          }
        </motion.div>

        {/* Sentiment gauge — 4 cols */}
        <motion.div variants={ITEM} className="col-span-12 lg:col-span-4 min-h-[300px]">
          <SentimentGauge distribution={m.sentiment_distribution || { positive: 0, negative: 0, neutral: 0, mixed: 0 }} />
        </motion.div>

        {/* Narrative heatmap — 8 cols */}
        <motion.div variants={ITEM} className="col-span-12 lg:col-span-8 min-h-[340px]">
          <NarrativeHeatmap narratives={m.emerging_narratives || []} />
        </motion.div>

        {/* Alerts widget — 4 cols */}
        <motion.div variants={ITEM} className="col-span-12 lg:col-span-4 min-h-[340px]">
          <AlertsWidget
            alerts={m.recent_alerts || []}
            criticalCount={m.critical_alerts || 0}
            highCount={Math.max(0, (m.active_alerts || 0) - (m.critical_alerts || 0))}
          />
        </motion.div>

        {/* Platform breakdown — 5 cols */}
        <motion.div variants={ITEM} className="col-span-12 lg:col-span-5 min-h-[300px]">
          {platformLoading
            ? <SkeletonPanel height="h-[300px]" />
            : <PlatformBreakdown
                platforms={
                  (platformData as { platforms: unknown[] })?.platforms as Array<{
                    platform: string; count: number; positive: number; negative: number;
                    neutral: number; avg_engagement: number;
                  }> || []
                }
              />
          }
        </motion.div>

        {/* Hashtag cloud — 7 cols */}
        <motion.div variants={ITEM} className="col-span-12 lg:col-span-7 min-h-[300px]">
          <HashtagCloud hashtags={m.top_hashtags || []} />
        </motion.div>

      </div>
    </motion.div>
  );
}
