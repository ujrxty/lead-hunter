"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SearchSection } from "@/components/search-section";
import { LeadsSection } from "@/components/leads-section";
import { ProfileSection } from "@/components/profile-section";
import { SettingsSection } from "@/components/settings-section";
import { SchedulerSection } from "@/components/scheduler-section";
import { ConnectionStatus } from "@/components/connection-status";
import { sessionApi, jobsApi, schedulerApi } from "@/lib/api";

type Tab = "search" | "scheduler" | "leads" | "profile" | "settings";

const TABS: { id: Tab; label: string; num: string }[] = [
  { id: "search", label: "Signal", num: "01" },
  { id: "scheduler", label: "Auto", num: "02" },
  { id: "leads", label: "Leads", num: "03" },
  { id: "profile", label: "Profile", num: "04" },
  { id: "settings", label: "Settings", num: "05" },
];

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("search");

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: jobsApi.getStats,
  });

  const { data: sessionStatus } = useQuery({
    queryKey: ["session-status"],
    queryFn: sessionApi.getStatus,
    refetchInterval: 30000,
  });

  const { data: schedulerStatus } = useQuery({
    queryKey: ["scheduler-status"],
    queryFn: schedulerApi.getStatus,
    refetchInterval: 10000,
  });

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border glass">
        <div className="max-w-[1240px] mx-auto px-6">
          <div className="flex items-center justify-between h-16">
            {/* Wordmark — crosshair mark ties the hunter + signal metaphor */}
            <div className="flex items-center gap-3">
              <div
                className="relative flex items-center justify-center w-9 h-9 rounded-md border border-border overflow-hidden"
                style={{
                  background:
                    "radial-gradient(circle at 50% 50%, oklch(0.15 0.006 95), oklch(0.10 0.006 95) 70%)",
                }}
              >
                {/* Scan-line grid backdrop */}
                <div
                  className="absolute inset-0 opacity-30"
                  style={{
                    backgroundImage:
                      "linear-gradient(oklch(0.872 0.198 128 / 0.12) 1px, transparent 1px), linear-gradient(90deg, oklch(0.872 0.198 128 / 0.12) 1px, transparent 1px)",
                    backgroundSize: "6px 6px",
                  }}
                />
                {/* Crosshair reticle */}
                <svg viewBox="0 0 24 24" className="relative w-6 h-6" fill="none">
                  {/* outer ring */}
                  <circle cx="12" cy="12" r="7.5" stroke="var(--signal)" strokeWidth="1" opacity="0.9" />
                  {/* tick marks — top/right/bottom/left */}
                  <line x1="12" y1="1.5" x2="12" y2="5" stroke="var(--signal)" strokeWidth="1.2" strokeLinecap="round" />
                  <line x1="12" y1="19" x2="12" y2="22.5" stroke="var(--signal)" strokeWidth="1.2" strokeLinecap="round" />
                  <line x1="1.5" y1="12" x2="5" y2="12" stroke="var(--signal)" strokeWidth="1.2" strokeLinecap="round" />
                  <line x1="19" y1="12" x2="22.5" y2="12" stroke="var(--signal)" strokeWidth="1.2" strokeLinecap="round" />
                  {/* center dot — the lead */}
                  <circle cx="12" cy="12" r="1.8" fill="var(--signal)" />
                  <circle cx="12" cy="12" r="3.5" stroke="var(--signal)" strokeWidth="0.6" opacity="0.4" />
                </svg>
                {/* pulse ring */}
                <span
                  className="absolute inset-0 rounded-md pointer-events-none"
                  style={{
                    boxShadow: "inset 0 0 12px oklch(0.872 0.198 128 / 0.15)",
                  }}
                />
              </div>
              <div className="leading-none">
                <h1 className="font-display text-[22px] tracking-tight text-foreground">
                  Lead Hunter
                </h1>
                <p className="mono-label mt-1">Signal Terminal</p>
              </div>
            </div>

            {/* Center nav */}
            <nav className="hidden md:flex items-center gap-1">
              {TABS.map((t) => (
                <NavTab
                  key={t.id}
                  active={activeTab === t.id}
                  onClick={() => setActiveTab(t.id)}
                  num={t.num}
                  label={t.label}
                  count={t.id === "search" ? stats?.total_jobs : undefined}
                />
              ))}
            </nav>

            {/* Right */}
            <div className="flex items-center gap-3">
              {schedulerStatus?.is_running && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-signal/10 border border-signal/30">
                  <span className="status-dot connected animate-pulse" />
                  <span className="font-mono text-[11px] text-signal">Auto: {schedulerStatus.interval_minutes}m</span>
                </div>
              )}
              <ConnectionStatus status={sessionStatus} />
            </div>
          </div>

          {/* Mobile nav */}
          <nav className="md:hidden flex items-center gap-1 pb-2">
            {TABS.map((t) => (
              <NavTab
                key={t.id}
                active={activeTab === t.id}
                onClick={() => setActiveTab(t.id)}
                num={t.num}
                label={t.label}
              />
            ))}
          </nav>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-[1240px] mx-auto px-6 py-10">
        <div className="animate-fade-in" key={activeTab}>
          {activeTab === "search" && <SearchSection />}
          {activeTab === "scheduler" && <SchedulerSection />}
          {activeTab === "leads" && <LeadsSection />}
          {activeTab === "profile" && <ProfileSection />}
          {activeTab === "settings" && <SettingsSection />}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-auto">
        <div className="max-w-[1240px] mx-auto px-6 py-5 flex items-center justify-between">
          <p className="mono-label">Lead Hunter · Upwork Intelligence</p>
          <div className="flex items-center gap-5 mono-label">
            <span className="inline-flex items-center gap-1.5">
              <span className="status-dot connected" /> Live
            </span>
            <span>v1.0</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function NavTab({
  active,
  onClick,
  num,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  num: string;
  label: string;
  count?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={`group relative flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors duration-200
        ${active ? "text-foreground" : "text-faint hover:text-dim"}`}
    >
      <span className="font-mono text-[10px] tracking-widest opacity-60">{num}</span>
      <span className="font-medium">{label}</span>
      {count !== undefined && count > 0 && (
        <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--surface-2)] text-dim">
          {count > 999 ? "999+" : count}
        </span>
      )}
      <span
        className={`absolute left-3 right-3 -bottom-[1px] h-[2px] rounded-full bg-signal transition-transform duration-300 origin-left
          ${active ? "scale-x-100" : "scale-x-0 group-hover:scale-x-50"}`}
        style={{ backgroundColor: "var(--signal)" }}
      />
    </button>
  );
}
