"use client";
import { LucideIcon, TrendingUp, TrendingDown } from "lucide-react";
import { cn, formatNumber } from "@/lib/utils";
import { motion } from "framer-motion";

interface MetricCardProps {
  label: string;
  value: number | string;
  subvalue?: string;
  icon: LucideIcon;
  trend?: number;
  variant?: "default" | "critical" | "warning" | "success";
  pulse?: boolean;
}

const VARIANTS = {
  default: {
    border: "border-bg-border hover:border-accent-cyan/25",
    icon: "bg-accent-cyan/10 border-accent-cyan/20",
    iconColor: "text-accent-cyan",
    glow: "hover:shadow-glow-cyan",
    valueColor: "text-text-primary",
    accent: "rgba(0,212,255,0.06)",
    gradFrom: "rgba(0,212,255,0.05)",
  },
  critical: {
    border: "border-accent-red/25 hover:border-accent-red/40",
    icon: "bg-accent-red/10 border-accent-red/25",
    iconColor: "text-accent-red",
    glow: "hover:shadow-glow-red",
    valueColor: "text-accent-red",
    accent: "rgba(255,45,85,0.06)",
    gradFrom: "rgba(255,45,85,0.05)",
  },
  warning: {
    border: "border-accent-amber/25 hover:border-accent-amber/40",
    icon: "bg-accent-amber/10 border-accent-amber/25",
    iconColor: "text-accent-amber",
    glow: "hover:shadow-[0_0_24px_rgba(245,158,11,0.18)]",
    valueColor: "text-accent-amber",
    accent: "rgba(245,158,11,0.06)",
    gradFrom: "rgba(245,158,11,0.05)",
  },
  success: {
    border: "border-accent-green/25 hover:border-accent-green/40",
    icon: "bg-accent-green/10 border-accent-green/25",
    iconColor: "text-accent-green",
    glow: "hover:shadow-glow-green",
    valueColor: "text-accent-green",
    accent: "rgba(0,232,122,0.06)",
    gradFrom: "rgba(0,232,122,0.05)",
  },
};

export function MetricCard({ label, value, subvalue, icon: Icon, trend, variant = "default", pulse }: MetricCardProps) {
  const v = VARIANTS[variant];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "glass-card rounded-xl p-5 border relative overflow-hidden transition-all duration-300 cursor-default group",
        v.border,
        v.glow
      )}
    >
      {/* Background gradient wash */}
      <div
        className="absolute inset-0 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-300"
        style={{ background: `linear-gradient(135deg, ${v.gradFrom} 0%, transparent 60%)` }}
      />

      {/* Corner accent line */}
      <div className="absolute top-0 right-0 w-16 h-16 overflow-hidden pointer-events-none">
        <div className={cn("absolute top-0 right-0 w-px h-8 opacity-20", v.iconColor.replace("text-", "bg-"))} style={{ background: "currentColor" }} />
        <div className={cn("absolute top-0 right-0 h-px w-8 opacity-20")} style={{ background: v.accent.replace("0.06", "0.3") }} />
      </div>

      <div className="relative">
        {/* Header row */}
        <div className="flex items-start justify-between mb-4">
          <div className={cn(
            "w-9 h-9 rounded-lg border flex items-center justify-center flex-shrink-0 transition-all duration-300",
            v.icon,
            pulse && "animate-pulse-slow"
          )}>
            <Icon className={cn("w-4 h-4", v.iconColor)} />
          </div>

          {trend !== undefined && (
            <div className={cn(
              "flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded-md",
              trend > 0
                ? "text-accent-red bg-accent-red/10 border border-accent-red/20"
                : "text-accent-green bg-accent-green/10 border border-accent-green/20"
            )}>
              {trend > 0 ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}
              <span>{Math.abs(trend).toFixed(0)}%</span>
            </div>
          )}
        </div>

        {/* Value */}
        <div className={cn("text-3xl font-bold font-mono tabular-nums tracking-tight stat-number", v.valueColor)}>
          {typeof value === "number" ? formatNumber(value) : value}
        </div>

        {/* Label */}
        <div className="mt-1.5 text-[10px] font-mono text-text-muted tracking-[0.12em] uppercase">
          {label}
        </div>

        {/* Subvalue */}
        {subvalue && (
          <div className="mt-2 flex items-center gap-1.5">
            {pulse && <span className={cn("w-1.5 h-1.5 rounded-full animate-pulse flex-shrink-0", v.iconColor.replace("text-", "bg-"))} />}
            <span className="text-[11px] text-text-muted font-mono">{subvalue}</span>
          </div>
        )}
      </div>

      {/* Bottom accent bar */}
      <div
        className="absolute bottom-0 left-0 right-0 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-300"
        style={{ background: `linear-gradient(90deg, transparent, ${v.accent.replace("0.06", "0.5")}, transparent)` }}
      />
    </motion.div>
  );
}
