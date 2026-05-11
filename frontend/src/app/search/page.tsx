"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { searchPosts, exportToCSV } from "@/lib/api";
import { Post, Platform, Sentiment } from "@/types";
import { Search, Filter, Download, Cpu, Globe } from "lucide-react";
import { SENTIMENT_CONFIG, PLATFORM_CONFIG, cn, formatDate } from "@/lib/utils";
import toast from "react-hot-toast";

const PLATFORMS: Platform[] = ["twitter", "facebook", "instagram", "tiktok", "reddit", "telegram", "news"];
const SENTIMENTS: Sentiment[] = ["positive", "negative", "neutral", "mixed"];

function PostCard({ post }: { post: Post }) {
  return (
    <div className="glass-card rounded-lg border border-bg-border p-4 hover:border-accent-cyan/20 transition-all">
      <div className="flex items-start gap-3">
        {/* Platform indicator */}
        <div
          className="w-8 h-8 rounded flex items-center justify-center text-[10px] font-bold flex-shrink-0"
          style={{
            backgroundColor: `${PLATFORM_CONFIG[post.platform]?.color || "#475569"}20`,
            color: PLATFORM_CONFIG[post.platform]?.color || "#475569",
            border: `1px solid ${PLATFORM_CONFIG[post.platform]?.color || "#475569"}40`,
          }}
        >
          {PLATFORM_CONFIG[post.platform]?.icon || post.platform.slice(0, 2).toUpperCase()}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] font-mono text-text-secondary">@{post.author_username}</span>
            {post.author_verified && <span className="text-accent-cyan text-[10px]">✓</span>}
            {post.language && (
              <span className="text-[10px] font-mono text-text-muted uppercase border border-bg-border px-1 rounded">
                {post.language}
              </span>
            )}
            {post.sentiment && (
              <span className={cn("text-[10px] font-mono", SENTIMENT_CONFIG[post.sentiment]?.color)}>
                {post.sentiment}
              </span>
            )}
            <span className="ml-auto text-[10px] font-mono text-text-muted">{formatDate(post.posted_at)}</span>
          </div>

          <p className="text-[13px] text-text-primary mb-2 leading-relaxed">{post.content}</p>

          <div className="flex items-center gap-4 text-[10px] font-mono text-text-muted">
            <span>♥ {post.likes_count?.toLocaleString()}</span>
            <span>↺ {post.shares_count?.toLocaleString()}</span>
            <span>◎ {post.comments_count?.toLocaleString()}</span>
            <span className="ml-auto text-accent-cyan/60">eng: {post.engagement_score?.toFixed(1)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [semanticQuery, setSemanticQuery] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState<Platform[]>([]);
  const [selectedSentiments, setSelectedSentiments] = useState<Sentiment[]>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [searchMode, setSearchMode] = useState<"keyword" | "semantic">("keyword");

  const { mutate: search, data: results, isPending } = useMutation({
    mutationFn: () =>
      searchPosts({
        query: searchMode === "keyword" ? query : undefined,
        semantic_query: searchMode === "semantic" ? semanticQuery : undefined,
        platforms: selectedPlatforms.length ? selectedPlatforms : undefined,
        sentiments: selectedSentiments.length ? selectedSentiments : undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: 50,
      }),
    onError: () => toast.error("Search failed"),
  });

  const togglePlatform = (p: Platform) =>
    setSelectedPlatforms((prev) => prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]);

  const toggleSentiment = (s: Sentiment) =>
    setSelectedSentiments((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);

  const handleExport = () => {
    if (!results?.posts?.length) return;
    exportToCSV(results.posts, `sentinel-search-${Date.now()}.csv`);
    toast.success("Exported to CSV");
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="text-[10px] font-mono text-text-muted tracking-widest uppercase mb-1">Intelligence Search</div>
        <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
          <Search className="w-6 h-6 text-accent-cyan" />
          Content Search
        </h1>
      </div>

      {/* Search panel */}
      <div className="glass-card rounded-lg border border-bg-border p-6 space-y-4">
        {/* Mode toggle */}
        <div className="flex gap-2">
          <button
            onClick={() => setSearchMode("keyword")}
            className={cn(
              "flex items-center gap-2 text-[11px] font-mono px-3 py-2 rounded border transition-all",
              searchMode === "keyword"
                ? "border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan"
                : "border-bg-border text-text-muted"
            )}
          >
            <Filter className="w-3 h-3" /> Keyword Search
          </button>
          <button
            onClick={() => setSearchMode("semantic")}
            className={cn(
              "flex items-center gap-2 text-[11px] font-mono px-3 py-2 rounded border transition-all",
              searchMode === "semantic"
                ? "border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan"
                : "border-bg-border text-text-muted"
            )}
          >
            <Cpu className="w-3 h-3" /> Semantic Search (AI)
          </button>
        </div>

        {/* Search input */}
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            value={searchMode === "keyword" ? query : semanticQuery}
            onChange={(e) => searchMode === "keyword" ? setQuery(e.target.value) : setSemanticQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
            placeholder={
              searchMode === "keyword"
                ? "Search by keyword, hashtag, or phrase..."
                : "Describe what you're looking for... (AI finds semantically similar content)"
            }
            className="w-full pl-10 pr-4 py-3 bg-bg-elevated border border-bg-border rounded-lg text-text-primary placeholder:text-text-muted font-mono text-sm focus:outline-none focus:border-accent-cyan/40 transition-colors"
          />
        </div>

        {/* Platform filter */}
        <div>
          <div className="text-[10px] font-mono text-text-muted mb-2 uppercase">Platforms</div>
          <div className="flex flex-wrap gap-2">
            {PLATFORMS.map((p) => (
              <button
                key={p}
                onClick={() => togglePlatform(p)}
                className={cn(
                  "text-[11px] font-mono px-3 py-1 rounded border transition-all capitalize",
                  selectedPlatforms.includes(p)
                    ? "border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan"
                    : "border-bg-border text-text-muted hover:text-text-secondary"
                )}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {/* Sentiment filter */}
        <div>
          <div className="text-[10px] font-mono text-text-muted mb-2 uppercase">Sentiment</div>
          <div className="flex gap-2">
            {SENTIMENTS.map((s) => (
              <button
                key={s}
                onClick={() => toggleSentiment(s)}
                className={cn(
                  "text-[11px] font-mono px-3 py-1 rounded border transition-all capitalize",
                  selectedSentiments.includes(s)
                    ? `border-current ${SENTIMENT_CONFIG[s].color} bg-current/5`
                    : "border-bg-border text-text-muted hover:text-text-secondary"
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Date range */}
        <div className="flex gap-3">
          <div className="flex-1">
            <div className="text-[10px] font-mono text-text-muted mb-1 uppercase">From</div>
            <input
              type="datetime-local"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full bg-bg-elevated border border-bg-border rounded px-3 py-2 text-text-secondary text-[12px] font-mono focus:outline-none focus:border-accent-cyan/40"
            />
          </div>
          <div className="flex-1">
            <div className="text-[10px] font-mono text-text-muted mb-1 uppercase">To</div>
            <input
              type="datetime-local"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full bg-bg-elevated border border-bg-border rounded px-3 py-2 text-text-secondary text-[12px] font-mono focus:outline-none focus:border-accent-cyan/40"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={() => search()}
            disabled={isPending}
            className="flex items-center gap-2 px-6 py-2.5 bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan rounded-lg font-mono text-sm hover:bg-accent-cyan/20 transition-all disabled:opacity-50"
          >
            {isPending ? (
              <><span className="animate-spin">◎</span> Searching...</>
            ) : (
              <><Search className="w-4 h-4" /> Execute Search</>
            )}
          </button>

          {results?.posts?.length ? (
            <button
              onClick={handleExport}
              className="flex items-center gap-2 px-4 py-2.5 border border-bg-border text-text-muted rounded-lg font-mono text-sm hover:text-text-secondary hover:border-bg-elevated transition-all"
            >
              <Download className="w-4 h-4" /> Export CSV
            </button>
          ) : null}

          {results && (
            <div className="flex items-center gap-2 text-[11px] font-mono text-text-muted ml-auto">
              <Globe className="w-3 h-3" />
              {results.total?.toLocaleString()} results
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      {results?.posts?.length ? (
        <div className="space-y-3">
          {results.posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      ) : results ? (
        <div className="text-center py-16">
          <Search className="w-10 h-10 mx-auto mb-3 text-text-muted opacity-40" />
          <div className="text-text-muted font-mono">No results found</div>
        </div>
      ) : null}
    </div>
  );
}
