"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAlerts, updateAlert } from "@/lib/api";
import { Alert } from "@/types";
import { useState } from "react";
import { SEVERITY_CONFIG, cn, formatDate } from "@/lib/utils";
import { Bell, Filter, Check, Eye, X, AlertTriangle, Zap, Hash, TrendingDown, Activity } from "lucide-react";
import toast from "react-hot-toast";
import { motion, AnimatePresence } from "framer-motion";

const ALERT_TYPE_LABELS: Record<string, string> = {
  narrative_spike: "Narrative Spike",
  keyword_match: "Keyword Match",
  influencer_activity: "Influencer Activity",
  sentiment_shift: "Sentiment Shift",
  viral_content: "Viral Content",
  coordinated_behavior: "Coordinated Behavior",
  emerging_narrative: "Emerging Narrative",
  hashtag_surge: "Hashtag Surge",
};

const ALERT_TYPE_ICONS: Record<string, React.ElementType> = {
  narrative_spike: Zap,
  keyword_match: Bell,
  hashtag_surge: Hash,
  sentiment_shift: TrendingDown,
  coordinated_behavior: AlertTriangle,
  emerging_narrative: Activity,
};

function AlertCard({ alert, onUpdate }: { alert: Alert; onUpdate: (id: string, data: object) => void }) {
  const config = SEVERITY_CONFIG[alert.severity];
  const Icon = ALERT_TYPE_ICONS[alert.alert_type] || AlertTriangle;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className={cn(
        "glass-card rounded-lg border p-5 transition-all",
        alert.severity === "critical" && alert.status === "active" ? "border-accent-red/30" : "border-bg-border"
      )}
    >
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div className={cn("p-2.5 rounded-lg border flex-shrink-0", config.bg)}>
          <Icon className={cn("w-4 h-4", config.color)} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h3 className="text-sm font-semibold text-text-primary">{alert.title}</h3>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className={cn("text-[10px] font-mono px-2 py-0.5 rounded border", config.bg, config.color)}>
                {config.label}
              </span>
              {alert.status === "active" && (
                <span className="w-2 h-2 rounded-full bg-accent-red animate-pulse" />
              )}
            </div>
          </div>

          {alert.description && (
            <p className="text-[12px] text-text-muted mb-2">{alert.description}</p>
          )}

          <div className="flex flex-wrap items-center gap-3 text-[10px] font-mono text-text-muted">
            <span className="text-accent-cyan/70">{ALERT_TYPE_LABELS[alert.alert_type] || alert.alert_type}</span>
            <span>{formatDate(alert.created_at)}</span>
            {alert.post_count > 0 && <span>{alert.post_count.toLocaleString()} posts</span>}
            {alert.affected_platforms.length > 0 && (
              <span>{alert.affected_platforms.join(", ")}</span>
            )}
          </div>

          {/* Trigger data preview */}
          {Object.keys(alert.trigger_data).length > 0 && (
            <div className="mt-2 p-2 bg-bg-elevated rounded text-[11px] font-mono text-text-muted">
              {Object.entries(alert.trigger_data).slice(0, 3).map(([k, v]) => (
                <div key={k} className="flex gap-2">
                  <span className="text-text-muted">{k}:</span>
                  <span className="text-text-secondary">{String(v)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        {alert.status === "active" && (
          <div className="flex gap-2 flex-shrink-0">
            <button
              onClick={() => onUpdate(alert.id, { status: "acknowledged", acknowledged_by: "OPERATOR" })}
              className="p-2 rounded border border-bg-border hover:border-amber-500/30 hover:text-amber-400 text-text-muted transition-all"
              title="Acknowledge"
            >
              <Eye className="w-4 h-4" />
            </button>
            <button
              onClick={() => onUpdate(alert.id, { status: "resolved" })}
              className="p-2 rounded border border-bg-border hover:border-accent-green/30 hover:text-accent-green text-text-muted transition-all"
              title="Resolve"
            >
              <Check className="w-4 h-4" />
            </button>
            <button
              onClick={() => onUpdate(alert.id, { status: "dismissed" })}
              className="p-2 rounded border border-bg-border hover:border-accent-red/30 hover:text-accent-red text-text-muted transition-all"
              title="Dismiss"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
        {alert.status !== "active" && (
          <div className={cn("text-[10px] font-mono px-2 py-1 rounded flex-shrink-0",
            alert.status === "resolved" ? "text-accent-green bg-accent-green/10" :
            alert.status === "acknowledged" ? "text-amber-400 bg-amber-500/10" :
            "text-text-muted bg-bg-elevated"
          )}>
            {alert.status.toUpperCase()}
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default function AlertsPage() {
  const [statusFilter, setStatusFilter] = useState("active");
  const [severityFilter, setSeverityFilter] = useState<string | undefined>();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["alerts", statusFilter, severityFilter],
    queryFn: () => getAlerts({ status: statusFilter, severity: severityFilter, limit: 50 }),
    refetchInterval: 30_000,
  });

  const { mutate: handleUpdate } = useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => updateAlert(id, data as Parameters<typeof updateAlert>[1]),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      toast.success("Alert updated");
    },
    onError: () => toast.error("Failed to update alert"),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] font-mono text-text-muted tracking-widest uppercase mb-1">Alert Management</div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
            <Bell className="w-6 h-6 text-accent-red" />
            Alert Center
          </h1>
        </div>

        <div className="flex items-center gap-4 text-[11px] font-mono">
          {data?.active_critical ? (
            <div className="flex items-center gap-1.5 text-accent-red">
              <span className="w-2 h-2 bg-accent-red rounded-full animate-pulse" />
              {data.active_critical} CRITICAL
            </div>
          ) : null}
          <div className="text-text-muted">{data?.total || 0} total</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Filter className="w-4 h-4 text-text-muted" />

        <div className="flex gap-1">
          {["active", "acknowledged", "resolved", "all"].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s === "all" ? undefined as unknown as string : s)}
              className={cn(
                "text-[11px] font-mono px-3 py-1.5 rounded border transition-all capitalize",
                (statusFilter === s || (!statusFilter && s === "all"))
                  ? "border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan"
                  : "border-bg-border text-text-muted hover:text-text-secondary"
              )}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-bg-border" />

        <div className="flex gap-1">
          {[undefined, "critical", "high", "medium", "low"].map((s) => {
            const cfg = s ? SEVERITY_CONFIG[s as keyof typeof SEVERITY_CONFIG] : null;
            return (
              <button
                key={s ?? "all"}
                onClick={() => setSeverityFilter(s)}
                className={cn(
                  "text-[11px] font-mono px-3 py-1.5 rounded border transition-all",
                  severityFilter === s
                    ? cfg ? `${cfg.bg} ${cfg.color}` : "border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan"
                    : "border-bg-border text-text-muted hover:text-text-secondary"
                )}
              >
                {s ? cfg?.label : "ALL"}
              </button>
            );
          })}
        </div>
      </div>

      {/* Alerts list */}
      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {isLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="skeleton rounded-lg h-32" />
            ))
          ) : data?.alerts.length === 0 ? (
            <div className="text-center py-16">
              <Check className="w-10 h-10 mx-auto mb-3 text-accent-green opacity-40" />
              <div className="text-text-muted font-mono">No alerts match current filters</div>
            </div>
          ) : (
            data?.alerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onUpdate={(id, updateData) => handleUpdate({ id, data: updateData })}
              />
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
