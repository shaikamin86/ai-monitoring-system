"use client";
import { Bell, Clock, Wifi, WifiOff, AlertTriangle, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { format } from "date-fns";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getAlerts } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import { cn } from "@/lib/utils";

const BREADCRUMB_LABELS: Record<string, string> = {
  "": "Dashboard",
  narratives: "Narratives",
  alerts: "Alert Center",
  influencers: "Influencers",
  search: "Search",
  trends: "Trend Analysis",
  reports: "Reports",
};

function useBreadcrumbs() {
  const pathname = usePathname();
  const parts = pathname.split("/").filter(Boolean);
  return parts.length === 0
    ? [{ label: "Dashboard", href: "/" }]
    : parts.map((part, i) => ({
        label: BREADCRUMB_LABELS[part] ?? part.charAt(0).toUpperCase() + part.slice(1),
        href: "/" + parts.slice(0, i + 1).join("/"),
      }));
}

export function TopBar() {
  const [time, setTime] = useState<Date | null>(null);
  const [connected, setConnected] = useState(false);
  const [wsActivity, setWsActivity] = useState(false);
  const breadcrumbs = useBreadcrumbs();

  const { data: alertsData } = useQuery({
    queryKey: ["alerts", "active"],
    queryFn: () => getAlerts({ status: "active", limit: 1 }),
    refetchInterval: 30_000,
  });

  useWebSocket((msg) => {
    if (msg.type !== "pong") {
      setConnected(true);
      setWsActivity(true);
      setTimeout(() => setWsActivity(false), 500);
    }
  });

  useEffect(() => {
    setTime(new Date());
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    setConnected(true);
  }, []);

  const activeAlerts = alertsData?.active_critical || 0;
  const totalActive = alertsData?.total || 0;

  return (
    <header className="h-14 flex items-center px-5 gap-4 flex-shrink-0 relative"
      style={{
        background: "linear-gradient(180deg, rgba(7,14,29,0.98) 0%, rgba(7,14,29,0.95) 100%)",
        borderBottom: "1px solid rgba(22, 32, 53, 0.8)",
        backdropFilter: "blur(20px)",
      }}
    >
      {/* Top scan line */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-accent-cyan/20 to-transparent" />

      {/* ── Classification badge ── */}
      <div className="flex-shrink-0 flex items-center gap-1.5 text-[9px] font-mono tracking-[0.15em] text-accent-cyan/50 border border-accent-cyan/15 px-2.5 py-1 rounded bg-accent-cyan/[0.03]">
        <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan/40" />
        CONFIDENTIAL
      </div>

      {/* ── Breadcrumbs ── */}
      <nav className="flex items-center gap-1 flex-1 min-w-0">
        <span className="text-[11px] font-mono text-text-dim">MY-INTEL</span>
        {breadcrumbs.map((crumb, i) => (
          <span key={crumb.href} className="flex items-center gap-1">
            <ChevronRight className="w-3 h-3 text-text-dim flex-shrink-0" />
            <Link
              href={crumb.href}
              className={cn(
                "text-[12px] font-medium truncate transition-colors",
                i === breadcrumbs.length - 1
                  ? "text-text-primary"
                  : "text-text-muted hover:text-text-secondary"
              )}
            >
              {crumb.label}
            </Link>
          </span>
        ))}
      </nav>

      {/* ── Right section ── */}
      <div className="flex items-center gap-4 flex-shrink-0">

        {/* Active alerts indicator */}
        {totalActive > 0 && (
          <Link href="/alerts">
            <div className="flex items-center gap-1.5 text-[11px] font-mono text-accent-red/90 bg-accent-red/8 border border-accent-red/20 px-2.5 py-1 rounded transition-all hover:bg-accent-red/12">
              <AlertTriangle className="w-3 h-3" />
              <span>{totalActive} ALERTS</span>
              {activeAlerts > 0 && (
                <span className="w-1.5 h-1.5 rounded-full bg-accent-red animate-pulse" />
              )}
            </div>
          </Link>
        )}

        {/* Connection status */}
        <div className={cn(
          "flex items-center gap-1.5 text-[10px] font-mono transition-all",
          connected ? "text-accent-green" : "text-text-muted"
        )}>
          {connected ? (
            <Wifi className={cn("w-3 h-3", wsActivity && "animate-pulse")} />
          ) : (
            <WifiOff className="w-3 h-3" />
          )}
          <span className="hidden sm:inline">{connected ? "LIVE" : "OFFLINE"}</span>
        </div>

        {/* Divider */}
        <div className="w-px h-5 bg-bg-border" />

        {/* Clock */}
        <div className="flex items-center gap-2 text-[11px] font-mono text-text-secondary">
          <Clock className="w-3 h-3 text-text-muted" />
          <span className="tabular-nums">{time ? format(time, "HH:mm:ss") : "--:--:--"}</span>
          <span className="text-text-muted hidden md:inline">{time ? format(time, "dd MMM") : "--- ---"}</span>
          <span className="text-text-dim text-[10px] hidden lg:inline">MYT</span>
        </div>

        {/* Divider */}
        <div className="w-px h-5 bg-bg-border" />

        {/* Alerts bell */}
        <Link href="/alerts" className="relative p-1 rounded hover:bg-white/[0.04] transition-colors">
          <Bell className={cn("w-4 h-4 transition-colors", activeAlerts > 0 ? "text-accent-red" : "text-text-muted")} />
          {activeAlerts > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-accent-red rounded-full text-[8px] font-bold text-white flex items-center justify-center animate-pulse border border-bg-secondary">
              {activeAlerts > 9 ? "9+" : activeAlerts}
            </span>
          )}
        </Link>

        {/* Divider */}
        <div className="w-px h-5 bg-bg-border" />

        {/* Operator */}
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent-cyan/20 to-accent-cyan/5 border border-accent-cyan/25 flex items-center justify-center text-accent-cyan text-[11px] font-bold font-mono shadow-glow-cyan-sm">
            OP
          </div>
          <div className="hidden md:block">
            <div className="text-[11px] font-mono text-text-secondary font-medium leading-none">OPERATOR</div>
            <div className="text-[9px] font-mono text-text-muted mt-0.5 tracking-wider">L3 CLEARANCE</div>
          </div>
        </div>
      </div>
    </header>
  );
}
