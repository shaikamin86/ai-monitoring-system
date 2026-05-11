"use client";
import { useQuery } from "@tanstack/react-query";
import { getNarrative } from "@/lib/api";
import { use } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell,
} from "recharts";
import { format, parseISO } from "date-fns";
import Link from "next/link";
import {
  ArrowLeft, TrendingUp, Users, MessageSquare,
  AlertTriangle, Clock, Globe, Activity,
} from "lucide-react";
import {
  cn, getThreatColor, getThreatBg, SENTIMENT_CONFIG,
  NARRATIVE_STATUS_CONFIG, PLATFORM_CONFIG, formatDate, formatRelative,
} from "@/lib/utils";
import { Sentiment, Platform } from "@/types";

export default function NarrativeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const { data: narrative, isLoading } = useQuery({
    queryKey: ["narrative", id],
    queryFn: () => getNarrative(id),
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-accent-cyan font-mono animate-pulse">LOADING NARRATIVE DATA...</div>
      </div>
    );
  }

  if (!narrative) {
    return (
      <div className="text-center py-16">
        <div className="text-text-muted font-mono">Narrative not found</div>
        <Link href="/narratives" className="text-accent-cyan font-mono text-sm mt-2 inline-block hover:underline">
          ← Back to narratives
        </Link>
      </div>
    );
  }

  const statusConfig = NARRATIVE_STATUS_CONFIG[narrative.status];
  const totalSentiment = Object.values(narrative.sentiment_distribution).reduce((a, b) => a + b, 0);

  const timelineData = narrative.timeline.map((t) => ({
    ...t,
    time: format(parseISO(t.bucket), "MM/dd HH:mm"),
  }));

  const sentimentData = (Object.entries(narrative.sentiment_distribution) as [Sentiment, number][]).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    value,
    pct: totalSentiment > 0 ? ((value / totalSentiment) * 100).toFixed(1) : "0",
    color: SENTIMENT_CONFIG[key].color.replace("text-", "#").replace("green-400", "00ff88").replace("red-400", "ff3366").replace("slate-400", "475569").replace("amber-400", "f59e0b"),
  }));

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <Link href="/narratives" className="inline-flex items-center gap-1 text-[11px] font-mono text-text-muted hover:text-accent-cyan mb-4 transition-colors">
          <ArrowLeft className="w-3 h-3" /> BACK TO NARRATIVES
        </Link>

        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <div className={cn("flex items-center gap-1.5 text-[11px] font-mono", statusConfig.color)}>
                <span className={cn("w-2 h-2 rounded-full", statusConfig.dot)} />
                {statusConfig.label}
              </div>
              {narrative.is_coordinated && (
                <span className="text-[10px] font-mono text-accent-red bg-accent-red/10 border border-accent-red/20 px-2 py-0.5 rounded">
                  ⚠ COORDINATED BEHAVIOR DETECTED
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold text-text-primary">{narrative.title}</h1>
            {narrative.summary && (
              <p className="text-text-secondary mt-2 max-w-2xl">{narrative.summary}</p>
            )}
          </div>

          <div className={cn("flex-shrink-0 text-center px-6 py-3 rounded-lg border", getThreatBg(narrative.threat_level))}>
            <div className={cn("text-4xl font-bold font-mono", getThreatColor(narrative.threat_level))}>
              {narrative.threat_level}
            </div>
            <div className="text-[10px] font-mono text-text-muted">/ 10 THREAT</div>
          </div>
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { icon: MessageSquare, label: "Total Posts", value: narrative.post_count.toLocaleString() },
          { icon: Users, label: "Unique Authors", value: narrative.unique_authors.toLocaleString() },
          { icon: TrendingUp, label: "Virality Score", value: narrative.virality_score.toFixed(1) },
          { icon: Activity, label: "Engagement", value: narrative.engagement_total.toFixed(0) },
        ].map((m) => (
          <div key={m.label} className="glass-card rounded-lg border border-bg-border p-4">
            <div className="flex items-center gap-2 mb-1">
              <m.icon className="w-4 h-4 text-accent-cyan" />
              <span className="text-[10px] font-mono text-text-muted uppercase">{m.label}</span>
            </div>
            <div className="text-2xl font-bold font-mono text-text-primary">{m.value}</div>
          </div>
        ))}
      </div>

      {/* Timeline chart */}
      <div className="glass-card rounded-lg border border-bg-border p-5">
        <div className="text-[11px] font-mono text-text-muted uppercase tracking-wider mb-4">
          Narrative Activity Timeline
        </div>
        {timelineData.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={timelineData}>
              <defs>
                <linearGradient id="gradNarrative" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00d4ff" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#00d4ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(26,39,68,0.6)" />
              <XAxis dataKey="time" tick={{ fill: "#475569", fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: "#475569", fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: "#0c1428", border: "1px solid #1a2744", fontSize: 11 }} />
              <Area type="monotone" dataKey="post_count" name="Posts" stroke="#00d4ff" strokeWidth={2} fill="url(#gradNarrative)" />
              <Area type="monotone" dataKey="new_authors" name="New Authors" stroke="#7c3aed" strokeWidth={1.5} fill="none" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-48 flex items-center justify-center text-text-muted font-mono text-sm">
            No timeline data available
          </div>
        )}
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Details */}
        <div className="col-span-12 lg:col-span-7 space-y-4">
          {/* Key themes */}
          <div className="glass-card rounded-lg border border-bg-border p-5">
            <div className="text-[11px] font-mono text-text-muted uppercase tracking-wider mb-3">Key Themes</div>
            <div className="flex flex-wrap gap-2">
              {narrative.key_themes.map((theme) => (
                <span key={theme} className="text-sm bg-accent-cyan/10 border border-accent-cyan/20 text-accent-cyan px-3 py-1 rounded font-mono">
                  {theme}
                </span>
              ))}
            </div>
          </div>

          {/* Sample posts */}
          <div className="glass-card rounded-lg border border-bg-border">
            <div className="p-5 border-b border-bg-border text-[11px] font-mono text-text-muted uppercase tracking-wider">
              Representative Posts
            </div>
            <div className="divide-y divide-bg-border">
              {narrative.sample_posts.slice(0, 5).map((post) => (
                <div key={post.id} className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[10px] font-mono text-text-muted capitalize">{post.platform}</span>
                    <span className="text-text-muted">·</span>
                    <span className="text-[10px] font-mono text-text-muted">@{post.author_username}</span>
                    {post.sentiment && (
                      <span className={cn("text-[10px] font-mono", SENTIMENT_CONFIG[post.sentiment as Sentiment]?.color)}>
                        {post.sentiment}
                      </span>
                    )}
                    <span className="ml-auto text-[10px] font-mono text-text-muted">
                      sim: {((post as Record<string, unknown>).similarity as number)?.toFixed(2)}
                    </span>
                  </div>
                  <p className="text-[12px] text-text-secondary line-clamp-3">{post.content}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="col-span-12 lg:col-span-5 space-y-4">
          {/* Sentiment breakdown */}
          <div className="glass-card rounded-lg border border-bg-border p-5">
            <div className="text-[11px] font-mono text-text-muted uppercase tracking-wider mb-3">Sentiment</div>
            <div className="space-y-2">
              {sentimentData.map((s) => (
                <div key={s.name} className="flex items-center gap-2">
                  <span className="text-[11px] font-mono text-text-secondary w-16">{s.name}</span>
                  <div className="flex-1 h-2 bg-bg-elevated rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${s.pct}%`, backgroundColor: s.color.replace("text-", "") }} />
                  </div>
                  <span className="text-[11px] font-mono text-text-muted w-10 text-right">{s.pct}%</span>
                </div>
              ))}
            </div>
          </div>

          {/* Languages & Platforms */}
          <div className="glass-card rounded-lg border border-bg-border p-5">
            <div className="text-[11px] font-mono text-text-muted uppercase tracking-wider mb-3">Languages</div>
            <div className="space-y-1">
              {Object.entries(narrative.languages).map(([lang, count]) => (
                <div key={lang} className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-text-secondary uppercase">{lang}</span>
                  <span className="text-text-primary">{count}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Metadata */}
          <div className="glass-card rounded-lg border border-bg-border p-5">
            <div className="text-[11px] font-mono text-text-muted uppercase tracking-wider mb-3">Timeline</div>
            <div className="space-y-2">
              {[
                { label: "First Detected", value: formatDate(narrative.first_detected), icon: Clock },
                { label: "Last Activity", value: formatRelative(narrative.last_activity), icon: Activity },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-2 text-[11px] font-mono">
                  <item.icon className="w-3 h-3 text-text-muted" />
                  <span className="text-text-muted">{item.label}:</span>
                  <span className="text-text-secondary">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
