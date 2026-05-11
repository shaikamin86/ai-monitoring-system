"use client";
import { Alert } from "@/types";
import { SEVERITY_CONFIG } from "@/lib/utils";
import { formatDistanceToNow, parseISO } from "date-fns";
import Link from "next/link";
import { AlertTriangle, Bell, Zap, Hash, TrendingDown, ExternalLink, CheckCircle2, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

const ALERT_ICONS: Record<string, React.ElementType> = {
  narrative_spike: Zap,
  keyword_match: Bell,
  hashtag_surge: Hash,
  sentiment_shift: TrendingDown,
  coordinated_behavior: AlertTriangle,
  emerging_narrative: Activity,
  default: AlertTriangle,
};

const SEVERITY_LEFT_BORDER: Record<string, string> = {
  critical: "#ff2d55",
  high: "#f97316",
  medium: "#f59e0b",
  low: "#00e87a",
};

interface AlertsWidgetProps {
  alerts: Alert[];
  criticalCount: number;
  highCount: number;
}

export function AlertsWidget({ alerts, criticalCount, highCount }: AlertsWidgetProps) {
  return (
    <div className="glass-card rounded-xl border border-bg-border flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between border-b border-bg-border/50">
        <div className="flex items-center gap-2.5">
          <div className={cn(
            "w-7 h-7 rounded-lg flex items-center justify-center border transition-colors",
            criticalCount > 0
              ? "bg-accent-red/15 border-accent-red/30"
              : "bg-bg-elevated border-bg-border"
          )}>
            <Bell className={cn("w-3.5 h-3.5", criticalCount > 0 ? "text-accent-red" : "text-text-muted")} />
          </div>
          <div>
            <div className="text-[12px] font-semibold text-text-primary">Active Alerts</div>
            <div className="text-[10px] font-mono text-text-muted">THREAT FEED</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {criticalCount > 0 && (
            <div className="flex items-center gap-1 text-[10px] font-mono text-accent-red bg-accent-red/10 border border-accent-red/25 px-2 py-1 rounded-md">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-red animate-pulse" />
              {criticalCount} CRIT
            </div>
          )}
          {highCount > 0 && (
            <div className="text-[10px] font-mono text-orange-400 bg-orange-500/10 border border-orange-500/25 px-2 py-1 rounded-md">
              {highCount} HIGH
            </div>
          )}
          <Link href="/alerts" className="flex items-center gap-1 text-[10px] font-mono text-accent-cyan/70 hover:text-accent-cyan transition-colors">
            <span>ALL</span>
            <ExternalLink className="w-2.5 h-2.5" />
          </Link>
        </div>
      </div>

      {/* Alert list */}
      <div className="flex-1 overflow-hidden">
        <AnimatePresence mode="popLayout">
          {alerts.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-10 gap-2"
            >
              <div className="w-10 h-10 rounded-full bg-accent-green/10 border border-accent-green/20 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-accent-green" />
              </div>
              <div className="text-[11px] font-mono text-text-muted">ALL CLEAR</div>
              <div className="text-[10px] font-mono text-text-dim">No active alerts</div>
            </motion.div>
          ) : (
            <div className="divide-y divide-bg-border/50">
              {alerts.slice(0, 7).map((alert, i) => {
                const config = SEVERITY_CONFIG[alert.severity];
                const Icon = ALERT_ICONS[alert.alert_type] || ALERT_ICONS.default;
                const borderColor = SEVERITY_LEFT_BORDER[alert.severity] || "#4a5f7a";

                return (
                  <motion.div
                    key={alert.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                  >
                    <Link href={`/alerts?id=${alert.id}`}>
                      <div
                        className="flex items-start gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors relative group cursor-pointer"
                        style={{ borderLeft: `2px solid ${borderColor}30` }}
                      >
                        {/* Hover left accent */}
                        <div
                          className="absolute left-0 top-0 bottom-0 w-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                          style={{ backgroundColor: borderColor }}
                        />

                        {/* Icon */}
                        <div className={cn("mt-0.5 p-1.5 rounded-md border flex-shrink-0 transition-colors", config.bg)}>
                          <Icon className={cn("w-3 h-3", config.color)} />
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <div className="text-[12px] font-semibold text-text-primary group-hover:text-white transition-colors truncate">
                              {alert.title}
                            </div>
                            <span className={cn("text-[9px] font-mono px-1.5 py-0.5 rounded border flex-shrink-0", config.bg, config.color)}>
                              {config.label}
                            </span>
                          </div>

                          {alert.description && (
                            <div className="text-[11px] text-text-muted truncate mt-0.5">{alert.description}</div>
                          )}

                          <div className="flex items-center gap-2.5 mt-1.5">
                            <span className="text-[10px] font-mono text-text-dim">
                              {formatDistanceToNow(parseISO(alert.created_at), { addSuffix: true })}
                            </span>
                            {alert.post_count > 0 && (
                              <>
                                <span className="text-text-dim">·</span>
                                <span className="text-[10px] font-mono text-text-dim">
                                  {alert.post_count.toLocaleString()} posts
                                </span>
                              </>
                            )}
                            {alert.affected_platforms?.length > 0 && (
                              <>
                                <span className="text-text-dim">·</span>
                                <span className="text-[10px] font-mono text-text-dim capitalize">
                                  {alert.affected_platforms[0]}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    </Link>
                  </motion.div>
                );
              })}
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
