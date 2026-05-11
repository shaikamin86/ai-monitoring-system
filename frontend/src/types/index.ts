export type Platform = "twitter" | "facebook" | "instagram" | "tiktok" | "reddit" | "telegram" | "news" | "youtube" | "other";
export type Language = "ms" | "en" | "mixed" | "other";
export type Sentiment = "positive" | "negative" | "neutral" | "mixed";
export type AlertSeverity = "low" | "medium" | "high" | "critical";
export type AlertStatus = "active" | "acknowledged" | "resolved" | "dismissed";
export type NarrativeStatus = "emerging" | "active" | "declining" | "dormant";

export interface Post {
  id: string;
  external_id?: string;
  platform: Platform;
  content: string;
  author_username?: string;
  author_display_name?: string;
  author_followers: number;
  author_verified: boolean;
  url?: string;
  language: Language;
  sentiment?: Sentiment;
  sentiment_score?: number;
  engagement_score: number;
  likes_count: number;
  shares_count: number;
  comments_count: number;
  views_count: number;
  posted_at: string;
  collected_at: string;
  hashtags?: string[];
  entities?: string[];
  narrative_ids?: string[];
}

export interface Narrative {
  id: string;
  title: string;
  summary?: string;
  description?: string;
  status: NarrativeStatus;
  key_themes: string[];
  key_hashtags: string[];
  sentiment_distribution: Record<Sentiment, number>;
  post_count: number;
  unique_authors: number;
  engagement_total: number;
  virality_score: number;
  threat_level: number;
  first_detected: string;
  last_activity: string;
  is_coordinated: boolean;
  languages: Record<Language, number>;
  platforms: Record<Platform, number>;
}

export interface NarrativeDetail extends Narrative {
  timeline: TimelinePoint[];
  sample_posts: Post[];
  related_narratives: Pick<Narrative, "id" | "title" | "status" | "post_count" | "threat_level">[];
}

export interface TimelinePoint {
  bucket: string;
  post_count: number;
  new_authors: number;
  engagement: number;
  sentiment_score: number;
}

export interface Alert {
  id: string;
  title: string;
  description?: string;
  severity: AlertSeverity;
  status: AlertStatus;
  alert_type: string;
  source_id?: string;
  source_type?: string;
  trigger_data: Record<string, unknown>;
  affected_platforms: string[];
  affected_languages: string[];
  post_count: number;
  reach_estimate: number;
  created_at: string;
  acknowledged_at?: string;
  resolved_at?: string;
  notes?: string;
}

export interface Influencer {
  id: string;
  platform: Platform;
  platform_user_id: string;
  username: string;
  display_name?: string;
  bio?: string;
  followers_count: number;
  following_count: number;
  verified: boolean;
  influence_score: number;
  avg_engagement_rate: number;
  primary_language: Language;
  primary_topics: string[];
  sentiment_lean: Sentiment;
  is_flagged: boolean;
  flag_reason?: string;
  last_active: string;
}

export interface Hashtag {
  tag: string;
  total_count: number;
  period_count?: number;
}

export interface DashboardMetrics {
  total_posts_24h: number;
  active_alerts: number;
  active_narratives: number;
  critical_alerts: number;
  sentiment_distribution: Record<Sentiment, number>;
  platform_distribution: Record<Platform, number>;
  top_hashtags: Hashtag[];
  emerging_narratives: Narrative[];
  recent_alerts: Alert[];
  hourly_volume: { time: string; count: number }[];
}

export interface TrendPoint {
  time: string;
  count: number;
  positive: number;
  negative: number;
  neutral: number;
  mixed?: number;
  engagement: number;
}

export interface Entity {
  id: string;
  name: string;
  type: string;
  normalized_name: string;
  importance_score: number;
  first_seen: string;
  last_seen: string;
}

export interface WSMessage {
  type: "initial_state" | "metrics_update" | "new_alert" | "narrative_update" | "pong";
  data: unknown;
  ts: string;
}
