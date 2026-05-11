"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Bell, Users, Search,
  FileText, TrendingUp, Layers, Shield,
  Activity, Radio, Cpu, ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { getAlerts } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";

const NAV_SECTIONS = [
  {
    label: "Intelligence",
    items: [
      { href: "/", icon: LayoutDashboard, label: "Dashboard", id: "dashboard" },
      { href: "/narratives", icon: Layers, label: "Narratives", id: "narratives" },
      { href: "/trends", icon: TrendingUp, label: "Trends", id: "trends" },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/alerts", icon: Bell, label: "Alert Center", id: "alerts", badge: true },
      { href: "/influencers", icon: Users, label: "Influencers", id: "influencers" },
      { href: "/search", icon: Search, label: "Search", id: "search" },
    ],
  },
  {
    label: "Reporting",
    items: [
      { href: "/reports", icon: FileText, label: "Reports", id: "reports" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { data: alertsData } = useQuery({
    queryKey: ["alerts", "active-count"],
    queryFn: () => getAlerts({ status: "active", limit: 1 }),
    refetchInterval: 30_000,
  });

  const criticalCount = alertsData?.active_critical || 0;

  return (
    <aside className="w-60 flex-shrink-0 flex flex-col relative overflow-hidden" style={{ background: "linear-gradient(180deg, #070e1d 0%, #050c1a 100%)" }}>
      {/* Left accent strip — Malaysian colors */}
      <div className="absolute left-0 top-0 bottom-0 w-[3px]" style={{ background: "linear-gradient(180deg, #CC0001 0%, #CC0001 50%, #003399 50%, #003399 100%)" }} />

      {/* Subtle grid texture */}
      <div className="absolute inset-0 pointer-events-none opacity-30"
        style={{
          backgroundImage: "linear-gradient(rgba(0,212,255,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.015) 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      />

      {/* ── Logo ── */}
      <div className="relative px-5 py-5 border-b border-bg-border/60">
        <div className="flex items-center gap-3">
          <div className="relative flex-shrink-0">
            <div className="w-9 h-9 rounded-lg bg-accent-cyan/10 border border-accent-cyan/25 flex items-center justify-center glow-cyan">
              <Shield className="w-5 h-5 text-accent-cyan" />
            </div>
            <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-accent-green rounded-full border border-bg-secondary animate-pulse-slow" />
          </div>
          <div>
            <div className="text-[13px] font-bold text-text-primary tracking-wider font-mono">SENTINEL</div>
            <div className="text-[9px] text-text-muted font-mono tracking-[0.15em] uppercase mt-0.5">MY Intelligence</div>
          </div>
        </div>
      </div>

      {/* ── System status strip ── */}
      <div className="relative px-4 py-2.5 border-b border-bg-border/40 bg-accent-cyan/[0.03]">
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
            <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-pulse" style={{ animationDelay: "0.3s" }} />
            <span className="w-1.5 h-1.5 rounded-full bg-accent-amber animate-pulse" style={{ animationDelay: "0.6s" }} />
          </div>
          <span className="text-[10px] font-mono text-text-muted tracking-wider">SYSTEMS NOMINAL</span>
          <Cpu className="w-3 h-3 text-text-dim ml-auto" />
        </div>
      </div>

      {/* ── Navigation ── */}
      <nav className="flex-1 overflow-y-auto py-3 px-2.5 space-y-4 relative">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <div className="px-3 mb-1.5 text-[9px] font-mono text-text-dim tracking-[0.2em] uppercase">
              {section.label}
            </div>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
                return (
                  <Link key={item.id} href={item.href}>
                    <motion.div
                      whileHover={{ x: 2 }}
                      transition={{ duration: 0.15 }}
                      className={cn(
                        "relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 group cursor-pointer",
                        isActive
                          ? "bg-sidebar-active text-accent-cyan"
                          : "text-text-secondary hover:text-text-primary hover:bg-white/[0.03]"
                      )}
                    >
                      {isActive && <span className="nav-active-bar" />}

                      {/* Icon container */}
                      <div className={cn(
                        "w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 transition-all duration-200",
                        isActive
                          ? "bg-accent-cyan/15 border border-accent-cyan/25"
                          : "border border-transparent group-hover:border-bg-border group-hover:bg-white/[0.04]"
                      )}>
                        <item.icon className={cn(
                          "w-3.5 h-3.5 transition-colors",
                          isActive ? "text-accent-cyan" : "text-text-muted group-hover:text-text-secondary"
                        )} />
                      </div>

                      <span className={cn("font-medium text-[13px] flex-1", isActive && "font-semibold")}>
                        {item.label}
                      </span>

                      {item.badge && criticalCount > 0 && (
                        <motion.span
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          className="badge-pulse text-[10px] font-mono font-bold bg-accent-red/20 text-accent-red border border-accent-red/30 px-1.5 py-0.5 rounded-full min-w-[20px] text-center leading-none"
                        >
                          {criticalCount > 9 ? "9+" : criticalCount}
                        </motion.span>
                      )}

                      {isActive && (
                        <ChevronRight className="w-3 h-3 text-accent-cyan/40 flex-shrink-0" />
                      )}
                    </motion.div>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* ── Live monitoring footer ── */}
      <div className="relative px-4 py-4 border-t border-bg-border/60 space-y-3">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-md bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center">
            <Radio className="w-3 h-3 text-accent-cyan animate-pulse-slow" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[11px] font-mono text-text-secondary font-medium">Live Monitoring</div>
            <div className="flex items-center gap-1 mt-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-green flex-shrink-0" />
              <span className="text-[10px] font-mono text-text-muted">7 platforms · active</span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between px-0.5">
          <div className="flex items-center gap-1.5">
            <Activity className="w-3 h-3 text-text-dim" />
            <span className="text-[10px] font-mono text-text-dim">v1.0 · MY-INTEL-01</span>
          </div>
          <div className="text-[10px] font-mono text-text-dim">UTC+8</div>
        </div>
      </div>
    </aside>
  );
}
