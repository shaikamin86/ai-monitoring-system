import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, formatDistanceToNow, parseISO } from "date-fns";
import { AlertSeverity, NarrativeStatus, Platform, Sentiment } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string): string {
  return format(parseISO(date), "dd MMM yyyy HH:mm");
}

export function formatRelative(date: string): string {
  return formatDistanceToNow(parseISO(date), { addSuffix: true });
}

export function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

export function formatEngagement(score: number): string {
  return score.toFixed(1);
}

export const SEVERITY_CONFIG: Record<AlertSeverity, { color: string; bg: string; label: string; dot: string }> = {
  critical: { color: "text-red-400", bg: "bg-red-500/10 border-red-500/30", label: "CRITICAL", dot: "bg-red-400" },
  high: { color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/30", label: "HIGH", dot: "bg-orange-400" },
  medium: { color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/30", label: "MEDIUM", dot: "bg-amber-400" },
  low: { color: "text-green-400", bg: "bg-green-500/10 border-green-500/30", label: "LOW", dot: "bg-green-400" },
};

export const SENTIMENT_CONFIG: Record<Sentiment, { color: string; bg: string; label: string }> = {
  positive: { color: "text-green-400", bg: "bg-green-500/10", label: "Positive" },
  negative: { color: "text-red-400", bg: "bg-red-500/10", label: "Negative" },
  neutral: { color: "text-slate-400", bg: "bg-slate-500/10", label: "Neutral" },
  mixed: { color: "text-amber-400", bg: "bg-amber-500/10", label: "Mixed" },
};

export const NARRATIVE_STATUS_CONFIG: Record<NarrativeStatus, { color: string; label: string; dot: string }> = {
  emerging: { color: "text-amber-400", label: "EMERGING", dot: "bg-amber-400 animate-pulse" },
  active: { color: "text-cyan-400", label: "ACTIVE", dot: "bg-cyan-400" },
  declining: { color: "text-slate-400", label: "DECLINING", dot: "bg-slate-400" },
  dormant: { color: "text-slate-600", label: "DORMANT", dot: "bg-slate-600" },
};

export const PLATFORM_CONFIG: Partial<Record<Platform, { color: string; icon: string }>> = {
  twitter: { color: "#1DA1F2", icon: "X" },
  facebook: { color: "#1877F2", icon: "FB" },
  instagram: { color: "#E4405F", icon: "IG" },
  tiktok: { color: "#FF0050", icon: "TT" },
  reddit: { color: "#FF4500", icon: "RD" },
  telegram: { color: "#26A5E4", icon: "TG" },
  news: { color: "#94a3b8", icon: "NW" },
  youtube: { color: "#FF0000", icon: "YT" },
};

export function getThreatColor(level: number): string {
  if (level >= 8) return "text-red-400";
  if (level >= 6) return "text-orange-400";
  if (level >= 4) return "text-amber-400";
  return "text-green-400";
}

export function getThreatBg(level: number): string {
  if (level >= 8) return "bg-red-500/20 border-red-500/30";
  if (level >= 6) return "bg-orange-500/20 border-orange-500/30";
  if (level >= 4) return "bg-amber-500/20 border-amber-500/30";
  return "bg-green-500/20 border-green-500/30";
}
