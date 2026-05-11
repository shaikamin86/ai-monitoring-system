"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getDashboardMetrics, getNarratives, getAlerts, exportToCSV } from "@/lib/api";
import { FileText, Download, TrendingUp, Bell, Layers, BarChart2 } from "lucide-react";
import { format } from "date-fns";
import toast from "react-hot-toast";
import { cn } from "@/lib/utils";

const REPORT_TYPES = [
  {
    id: "executive",
    label: "Executive Summary",
    icon: BarChart2,
    description: "High-level overview of monitoring activity and key findings",
  },
  {
    id: "narratives",
    label: "Narrative Intelligence Report",
    icon: Layers,
    description: "Detailed analysis of detected narratives, themes, and trends",
  },
  {
    id: "alerts",
    label: "Alert Incident Report",
    icon: Bell,
    description: "Complete log of all alerts with severity and resolution status",
  },
  {
    id: "trends",
    label: "Trend Analysis Report",
    icon: TrendingUp,
    description: "Platform activity, sentiment trends, and hashtag analysis",
  },
];

export default function ReportsPage() {
  const [selectedType, setSelectedType] = useState("executive");
  const [generating, setGenerating] = useState(false);

  const { data: metrics } = useQuery({
    queryKey: ["dashboard-metrics"],
    queryFn: getDashboardMetrics,
  });

  const { data: narrativesData } = useQuery({
    queryKey: ["narratives-report"],
    queryFn: () => getNarratives({ limit: 100 }),
  });

  const { data: alertsData } = useQuery({
    queryKey: ["alerts-report"],
    queryFn: () => getAlerts({ limit: 100 }),
  });

  const generateReport = async () => {
    setGenerating(true);
    try {
      const timestamp = format(new Date(), "yyyy-MM-dd-HHmm");
      const reportName = `SENTINEL-${selectedType.toUpperCase()}-${timestamp}`;

      switch (selectedType) {
        case "executive": {
          const data = [
            { metric: "Total Posts (24h)", value: metrics?.total_posts_24h || 0 },
            { metric: "Active Alerts", value: metrics?.active_alerts || 0 },
            { metric: "Critical Alerts", value: metrics?.critical_alerts || 0 },
            { metric: "Active Narratives", value: metrics?.active_narratives || 0 },
            { metric: "Positive Sentiment %", value: `${((metrics?.sentiment_distribution?.positive || 0) / Math.max(1, Object.values(metrics?.sentiment_distribution || {}).reduce((a: number, b: number) => a + b, 0)) * 100).toFixed(1)}%` },
            { metric: "Negative Sentiment %", value: `${((metrics?.sentiment_distribution?.negative || 0) / Math.max(1, Object.values(metrics?.sentiment_distribution || {}).reduce((a: number, b: number) => a + b, 0)) * 100).toFixed(1)}%` },
          ];
          exportToCSV(data, `${reportName}.csv`);
          break;
        }
        case "narratives": {
          const rows = (narrativesData?.narratives || []).map((n) => ({
            id: n.id,
            title: n.title,
            status: n.status,
            threat_level: n.threat_level,
            post_count: n.post_count,
            unique_authors: n.unique_authors,
            virality_score: n.virality_score.toFixed(2),
            first_detected: n.first_detected,
            last_activity: n.last_activity,
            key_themes: n.key_themes.join("; "),
            is_coordinated: n.is_coordinated,
          }));
          exportToCSV(rows, `${reportName}.csv`);
          break;
        }
        case "alerts": {
          const rows = (alertsData?.alerts || []).map((a) => ({
            id: a.id,
            title: a.title,
            severity: a.severity,
            status: a.status,
            alert_type: a.alert_type,
            post_count: a.post_count,
            created_at: a.created_at,
            resolved_at: a.resolved_at || "Pending",
            description: a.description,
          }));
          exportToCSV(rows, `${reportName}.csv`);
          break;
        }
        case "trends": {
          const data = Object.entries(metrics?.platform_distribution || {}).map(([platform, count]) => ({
            platform,
            count,
            positive: metrics?.sentiment_distribution?.positive || 0,
            negative: metrics?.sentiment_distribution?.negative || 0,
          }));
          exportToCSV(data, `${reportName}.csv`);
          break;
        }
      }
      toast.success(`Report exported: ${reportName}.csv`);
    } catch {
      toast.error("Failed to generate report");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="text-[10px] font-mono text-text-muted tracking-widest uppercase mb-1">Intelligence Output</div>
        <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
          <FileText className="w-6 h-6 text-accent-cyan" />
          Report Generation
        </h1>
      </div>

      {/* Report type selection */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {REPORT_TYPES.map((type) => (
          <button
            key={type.id}
            onClick={() => setSelectedType(type.id)}
            className={cn(
              "glass-card rounded-lg border p-5 text-left hover:border-accent-cyan/30 transition-all",
              selectedType === type.id ? "border-accent-cyan/40 bg-accent-cyan/5" : "border-bg-border"
            )}
          >
            <div className="flex items-center gap-3 mb-2">
              <div className={cn(
                "p-2 rounded border",
                selectedType === type.id ? "bg-accent-cyan/10 border-accent-cyan/20" : "bg-bg-elevated border-bg-border"
              )}>
                <type.icon className={cn("w-4 h-4", selectedType === type.id ? "text-accent-cyan" : "text-text-muted")} />
              </div>
              <div className={cn("font-semibold text-sm", selectedType === type.id ? "text-accent-cyan" : "text-text-primary")}>
                {type.label}
              </div>
              {selectedType === type.id && (
                <span className="ml-auto text-[10px] font-mono text-accent-cyan">● SELECTED</span>
              )}
            </div>
            <p className="text-[12px] text-text-muted">{type.description}</p>
          </button>
        ))}
      </div>

      {/* Report preview */}
      <div className="glass-card rounded-lg border border-bg-border p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[11px] font-mono text-text-muted uppercase tracking-wider mb-1">
              Report Preview
            </div>
            <div className="text-lg font-bold text-text-primary">
              {REPORT_TYPES.find((t) => t.id === selectedType)?.label}
            </div>
          </div>
          <div className="text-[10px] font-mono text-text-muted">
            GENERATED: {format(new Date(), "dd MMM yyyy HH:mm")} MYT
          </div>
        </div>

        <div className="border border-bg-border rounded p-4 font-mono text-[11px] text-text-muted space-y-2 bg-bg-elevated">
          <div className="text-accent-cyan">// SENTINEL MALAYSIA INTELLIGENCE SYSTEM</div>
          <div>// Classification: CONFIDENTIAL</div>
          <div>// Report Type: {selectedType.toUpperCase()}</div>
          <div>// Period: Last 24 hours</div>
          <div className="mt-2 text-text-secondary">EXECUTIVE SUMMARY:</div>
          <div>  Total Posts Monitored: {metrics?.total_posts_24h?.toLocaleString() || "—"}</div>
          <div>  Active Alerts: {metrics?.active_alerts || "—"}</div>
          <div>  Critical Alerts: {metrics?.critical_alerts || "—"}</div>
          <div>  Active Narratives: {metrics?.active_narratives || "—"}</div>
          <div className="mt-2 text-text-secondary">SENTIMENT ANALYSIS:</div>
          {metrics?.sentiment_distribution && Object.entries(metrics.sentiment_distribution).map(([k, v]) => (
            <div key={k}>  {k.charAt(0).toUpperCase() + k.slice(1)}: {v.toLocaleString()} posts</div>
          ))}
        </div>

        <button
          onClick={generateReport}
          disabled={generating}
          className="mt-4 flex items-center gap-2 px-6 py-3 bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan rounded-lg font-mono text-sm hover:bg-accent-cyan/20 transition-all disabled:opacity-50"
        >
          {generating ? (
            <><span className="animate-spin">◎</span> Generating...</>
          ) : (
            <><Download className="w-4 h-4" /> Export Report (CSV)</>
          )}
        </button>
      </div>
    </div>
  );
}
