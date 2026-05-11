import {
  DashboardMetrics, Narrative, NarrativeDetail, Alert,
  Influencer, TrendPoint, Entity, Post,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API = `${BASE_URL}/api/v1`;

function toParams(obj?: Record<string, unknown>): string {
  if (!obj) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined && v !== null) p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Request failed");
  }
  return res.json();
}

// Dashboard
export const getDashboardMetrics = (): Promise<DashboardMetrics> =>
  request("/analytics/dashboard");

// Trends
export const getTrends = (params: {
  metric?: string;
  interval?: string;
  hours?: number;
  platform?: string;
}): Promise<TrendPoint[]> =>
  request(`/analytics/trends${toParams(params)}`);

export const getSentimentTimeline = (hours = 24): Promise<{ timeline: TrendPoint[] }> =>
  request(`/analytics/sentiment-timeline?hours=${hours}`);

export const getPlatformBreakdown = (hours = 24): Promise<{ platforms: unknown[] }> =>
  request(`/analytics/platform-breakdown?hours=${hours}`);

export const getTopHashtags = (limit = 20, hours = 24): Promise<{ hashtags: unknown[] }> =>
  request(`/analytics/hashtags?limit=${limit}&hours=${hours}`);

export const getTopEntities = (type?: string, limit = 20): Promise<{ entities: Entity[] }> =>
  request(`/analytics/entities${toParams({ entity_type: type, limit })}`);

// Narratives
export const getNarratives = (params?: {
  status?: string;
  min_threat?: number;
  limit?: number;
  offset?: number;
  sort_by?: string;
}): Promise<{ narratives: Narrative[]; total: number }> =>
  request(`/narratives${toParams(params)}`);

export const getNarrative = (id: string): Promise<NarrativeDetail> =>
  request(`/narratives/${id}`);

export const getNarrativePosts = (id: string, limit = 20, offset = 0): Promise<{ posts: Post[] }> =>
  request(`/narratives/${id}/posts?limit=${limit}&offset=${offset}`);

// Alerts
export const getAlerts = (params?: {
  status?: string;
  severity?: string;
  alert_type?: string;
  limit?: number;
  offset?: number;
}): Promise<{ alerts: Alert[]; total: number; active_critical: number; active_high: number }> =>
  request(`/alerts${toParams(params)}`);

export const updateAlert = (id: string, data: {
  status?: string;
  notes?: string;
  acknowledged_by?: string;
}): Promise<Alert> =>
  request(`/alerts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

// Influencers
export const getInfluencers = (params?: {
  platform?: string;
  is_flagged?: boolean;
  min_influence?: number;
  limit?: number;
  sort_by?: string;
}): Promise<{ influencers: Influencer[]; total: number }> =>
  request(`/influencers${toParams(params)}`);

export const flagInfluencer = (id: string, reason: string): Promise<Influencer> =>
  request(`/influencers/${id}/flag?reason=${encodeURIComponent(reason)}`, { method: "PATCH" });

// Posts
export const searchPosts = (params: {
  query?: string;
  semantic_query?: string;
  platforms?: string[];
  sentiments?: string[];
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}): Promise<{ posts: Post[]; total: number }> =>
  request("/posts/search", {
    method: "POST",
    body: JSON.stringify(params),
  });

// Export helpers
export const exportToCSV = (data: unknown[], filename: string): void => {
  if (!data.length) return;
  const keys = Object.keys(data[0] as object);
  const csv = [
    keys.join(","),
    ...data.map(row =>
      keys.map(k => {
        const val = (row as Record<string, unknown>)[k];
        return typeof val === "string" ? `"${val.replace(/"/g, '""')}"` : val ?? "";
      }).join(",")
    ),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};
