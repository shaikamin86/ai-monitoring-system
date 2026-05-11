"use client";
import { useQuery } from "@tanstack/react-query";
import { getTrends, getSentimentTimeline, getTopHashtags, getPlatformBreakdown } from "@/lib/api";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { SentimentGauge } from "@/components/dashboard/SentimentGauge";
import { PlatformBreakdown } from "@/components/dashboard/PlatformBreakdown";
import { HashtagCloud } from "@/components/dashboard/HashtagCloud";
import { useState } from "react";
import { TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { Sentiment } from "@/types";

const TIME_WINDOWS = [
  { label: "1H", hours: 1 },
  { label: "6H", hours: 6 },
  { label: "24H", hours: 24 },
  { label: "7D", hours: 168 },
  { label: "30D", hours: 720 },
];

export default function TrendsPage() {
  const [hours, setHours] = useState(24);

  const { data: trends } = useQuery({
    queryKey: ["trends", hours],
    queryFn: () => getTrends({ hours, interval: hours > 72 ? "day" : "hour" }),
    refetchInterval: 300_000,
  });

  const { data: sentimentData } = useQuery({
    queryKey: ["sentiment-timeline", hours],
    queryFn: () => getSentimentTimeline(Math.min(hours, 168)),
    refetchInterval: 300_000,
  });

  const { data: hashtagData } = useQuery({
    queryKey: ["hashtags", hours],
    queryFn: () => getTopHashtags(30, hours),
    refetchInterval: 300_000,
  });

  const { data: platformData } = useQuery({
    queryKey: ["platform-breakdown", hours],
    queryFn: () => getPlatformBreakdown(hours),
    refetchInterval: 300_000,
  });

  // Compute aggregate sentiment
  const aggregateSentiment = sentimentData?.timeline?.reduce(
    (acc, t) => {
      acc.positive = (acc.positive || 0) + t.positive;
      acc.negative = (acc.negative || 0) + t.negative;
      acc.neutral = (acc.neutral || 0) + t.neutral;
      acc.mixed = (acc.mixed || 0) + (t.mixed || 0);
      return acc;
    },
    {} as Record<Sentiment, number>
  ) || { positive: 0, negative: 0, neutral: 0, mixed: 0 };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] font-mono text-text-muted tracking-widest uppercase mb-1">Analytics</div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-accent-cyan" />
            Trend Analysis
          </h1>
        </div>

        {/* Time window selector */}
        <div className="flex gap-1 bg-bg-secondary rounded-lg border border-bg-border p-1">
          {TIME_WINDOWS.map((w) => (
            <button
              key={w.hours}
              onClick={() => setHours(w.hours)}
              className={cn(
                "text-[11px] font-mono px-3 py-1.5 rounded transition-all",
                hours === w.hours
                  ? "bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20"
                  : "text-text-muted hover:text-text-secondary"
              )}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main trend chart */}
      <TrendChart
        data={trends || []}
        title={`Post Volume & Sentiment (${TIME_WINDOWS.find((w) => w.hours === hours)?.label})`}
        showSentiment
        height={280}
      />

      {/* Secondary metrics */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-4">
          <SentimentGauge distribution={aggregateSentiment as Record<Sentiment, number>} />
        </div>
        <div className="col-span-12 lg:col-span-8">
          <PlatformBreakdown platforms={(platformData as { platforms: Array<{ platform: string; count: number; positive: number; negative: number; neutral: number; avg_engagement: number }> })?.platforms || []} />
        </div>
        <div className="col-span-12">
          <HashtagCloud hashtags={(hashtagData as { hashtags: Array<{ tag: string; total_count: number; period_count?: number }> })?.hashtags || []} />
        </div>
      </div>
    </div>
  );
}
