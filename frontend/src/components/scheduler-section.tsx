"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { schedulerApi, createNotificationStream } from "@/lib/api";
import type { SavedSearch, Notification, SchedulerRun } from "@/lib/types";

export function SchedulerSection() {
  const queryClient = useQueryClient();
  const [newSearchName, setNewSearchName] = useState("");
  const [newKeywords, setNewKeywords] = useState<string[]>([]);
  const [keywordInput, setKeywordInput] = useState("");
  const [newMaxPages, setNewMaxPages] = useState(15);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notifPermission, setNotifPermission] = useState<NotificationPermission>("default");

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ["scheduler-status"],
    queryFn: schedulerApi.getStatus,
    refetchInterval: 10000,
  });

  const { data: searches, refetch: refetchSearches } = useQuery({
    queryKey: ["saved-searches"],
    queryFn: schedulerApi.getSavedSearches,
  });

  const { data: history } = useQuery({
    queryKey: ["scheduler-history"],
    queryFn: () => schedulerApi.getHistory(10),
    refetchInterval: 30000,
  });

  const startMutation = useMutation({
    mutationFn: (interval: number) => schedulerApi.start(interval),
    onSuccess: () => refetchStatus(),
  });

  const stopMutation = useMutation({
    mutationFn: schedulerApi.stop,
    onSuccess: () => refetchStatus(),
  });

  const runNowMutation = useMutation({
    mutationFn: schedulerApi.runNow,
    onSuccess: () => {
      refetchStatus();
      queryClient.invalidateQueries({ queryKey: ["scheduler-history"] });
    },
  });

  const createSearchMutation = useMutation({
    mutationFn: schedulerApi.createSavedSearch,
    onSuccess: () => {
      refetchSearches();
      setNewSearchName("");
      setNewKeywords([]);
    },
  });

  const updateSearchMutation = useMutation({
    mutationFn: ({ id, update }: { id: number; update: Parameters<typeof schedulerApi.updateSavedSearch>[1] }) =>
      schedulerApi.updateSavedSearch(id, update),
    onSuccess: () => refetchSearches(),
  });

  const deleteSearchMutation = useMutation({
    mutationFn: schedulerApi.deleteSavedSearch,
    onSuccess: () => refetchSearches(),
  });

  useEffect(() => {
    if (typeof window !== "undefined" && "Notification" in window) {
      setNotifPermission(window.Notification.permission);
    }
  }, []);

  const requestNotificationPermission = async () => {
    if (typeof window !== "undefined" && "Notification" in window) {
      const permission = await window.Notification.requestPermission();
      setNotifPermission(permission);
      if (permission === "granted") {
        new window.Notification("Notifications Enabled", { body: "You'll get alerts for new hot leads" });
      }
    }
  };

  useEffect(() => {
    const stream = createNotificationStream(
      (notification) => {
        setNotifications((prev) => [notification, ...prev].slice(0, 20));

        // Show desktop notification for new jobs
        if (typeof window !== "undefined" && "Notification" in window && window.Notification.permission === "granted") {
          if (notification.type === "new_jobs") {
            new window.Notification(notification.title, {
              body: notification.message,
              icon: "/favicon.ico"
            });
          }
        }

        if (notification.type === "scheduler_status") {
          refetchStatus();
        }
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
        queryClient.invalidateQueries({ queryKey: ["stats"] });
        queryClient.invalidateQueries({ queryKey: ["scheduler-history"] });
      }
    );

    return () => stream.close();
  }, [queryClient, refetchStatus]);

  const addKeyword = () => {
    const v = keywordInput.trim();
    if (v && !newKeywords.includes(v)) {
      setNewKeywords([...newKeywords, v]);
      setKeywordInput("");
    }
  };

  const handleCreateSearch = () => {
    if (newSearchName && newKeywords.length > 0) {
      createSearchMutation.mutate({
        name: newSearchName,
        keywords: newKeywords,
        max_pages: newMaxPages,
        is_scheduled: true,
      });
    }
  };

  return (
    <div className="space-y-10">
      {/* Scheduler Status */}
      <section className="glass-card rounded-xl p-6">
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <span className="mono-label">Scheduler</span>
            <h2 className="font-display text-2xl text-foreground mt-1 leading-none">24/7 Job Hunter</h2>
            <p className="text-sm text-dim mt-2">Automatically scrape Upwork on a schedule. New jobs are deduplicated.</p>
          </div>
          <div className="flex items-center gap-3">
            {notifPermission !== "granted" && (
              <button
                onClick={requestNotificationPermission}
                className="px-3 py-1.5 rounded-md text-xs btn-ghost border border-signal/50 text-signal"
              >
                Enable Notifications
              </button>
            )}
            <div className="flex items-center gap-2">
              <span className={`status-dot ${status?.is_running ? "connected" : "disconnected"}`} />
              <span className="mono-label">{status?.is_running ? "Running" : "Stopped"}</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatBox label="Interval" value={`${status?.interval_minutes ?? 30}m`} />
          <StatBox label="Last Run" value={status?.last_run_at ? formatTimeAgo(status.last_run_at) : "Never"} />
          <StatBox label="Next Run" value={status?.next_run_at ? formatTimeAgo(status.next_run_at) : "—"} />
          <StatBox label="Searches" value={searches?.filter((s) => s.is_scheduled).length ?? 0} />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => runNowMutation.mutate()}
            disabled={runNowMutation.isPending}
            className="px-4 py-2 rounded-md btn-primary text-sm"
          >
            {runNowMutation.isPending ? "Running..." : "Run Now"}
          </button>
          {!status?.is_running ? (
            <>
              <span className="mono-label ml-4">Auto:</span>
              {[5, 15, 30, 60].map((m) => (
                <button
                  key={m}
                  onClick={() => startMutation.mutate(m)}
                  disabled={startMutation.isPending}
                  className="px-3 py-2 rounded-md btn-ghost text-sm border border-border"
                >
                  Every {m}m
                </button>
              ))}
            </>
          ) : (
            <button
              onClick={() => stopMutation.mutate()}
              disabled={stopMutation.isPending}
              className="px-4 py-2 rounded-md btn-ghost text-sm border border-[var(--danger)]/50 text-[var(--danger)]"
            >
              Stop Auto
            </button>
          )}
        </div>
      </section>

      {/* Saved Searches */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <span className="mono-label">Saved Searches</span>
          <span className="text-faint font-mono text-[11px]">{searches?.length ?? 0} total</span>
          <span className="flex-1 divider-gradient" />
        </div>

        <div className="glass-card rounded-xl p-6 mb-4">
          <h3 className="font-medium text-foreground mb-4">Add New Search</h3>
          <div className="flex gap-3 mb-3">
            <input
              type="text"
              value={newSearchName}
              onChange={(e) => setNewSearchName(e.target.value)}
              placeholder="Search name (e.g., React Frontend)"
              className="flex-1 h-10 px-4 rounded-md floating-input text-sm"
            />
          </div>
          <div className="flex gap-2 mb-3">
            <input
              type="text"
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addKeyword()}
              placeholder="Add keyword and press Enter"
              className="flex-1 h-10 px-4 rounded-md floating-input font-mono text-sm"
            />
            <button onClick={addKeyword} className="h-10 px-4 rounded-md btn-ghost text-sm">
              Add
            </button>
          </div>
          {newKeywords.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-4">
              {newKeywords.map((kw) => (
                <span key={kw} className="chip !text-foreground">
                  {kw}
                  <button onClick={() => setNewKeywords(newKeywords.filter((k) => k !== kw))} className="ml-1 text-faint hover:text-signal">
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="flex items-center gap-3 mb-4">
            <span className="mono-label">Pages:</span>
            {[5, 15, 25, 50].map((p) => (
              <button
                key={p}
                onClick={() => setNewMaxPages(p)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  newMaxPages === p ? "bg-signal text-[var(--signal-ink)]" : "btn-ghost border border-border"
                }`}
              >
                {p} (~{p * 10} jobs)
              </button>
            ))}
          </div>
          <button
            onClick={handleCreateSearch}
            disabled={!newSearchName || newKeywords.length === 0 || createSearchMutation.isPending}
            className="px-4 py-2 rounded-md btn-primary text-sm disabled:opacity-40"
          >
            {createSearchMutation.isPending ? "Creating..." : "Create Search"}
          </button>
        </div>

        <div className="space-y-3">
          {searches?.map((search) => (
            <SearchCard
              key={search.id}
              search={search}
              onToggleScheduled={(scheduled) =>
                updateSearchMutation.mutate({ id: search.id, update: { is_scheduled: scheduled } })
              }
              onDelete={() => deleteSearchMutation.mutate(search.id)}
            />
          ))}
          {(!searches || searches.length === 0) && (
            <div className="text-center py-10 glass-card rounded-xl">
              <p className="text-dim">No saved searches yet. Create one above to start auto-scraping.</p>
            </div>
          )}
        </div>
      </section>

      {/* Run History */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <span className="mono-label">Run History</span>
          <span className="flex-1 divider-gradient" />
        </div>
        <div className="glass-card rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left p-4 font-mono text-xs text-faint">Time</th>
                <th className="text-left p-4 font-mono text-xs text-faint">Status</th>
                <th className="text-right p-4 font-mono text-xs text-faint">Found</th>
                <th className="text-right p-4 font-mono text-xs text-faint">New</th>
                <th className="text-right p-4 font-mono text-xs text-faint">Signals</th>
              </tr>
            </thead>
            <tbody>
              {history?.map((run) => (
                <tr key={run.id} className="border-b border-border last:border-0">
                  <td className="p-4 font-mono text-xs">{formatTimeAgo(run.started_at)}</td>
                  <td className="p-4">
                    <span className={`chip ${run.status === "completed" ? "!border-signal/40 !text-signal" : run.status === "failed" ? "!border-[var(--danger)]/40 !text-[var(--danger)]" : ""}`}>
                      {run.status}
                    </span>
                  </td>
                  <td className="p-4 text-right font-mono">{run.jobs_found}</td>
                  <td className="p-4 text-right font-mono text-signal">{run.new_jobs}</td>
                  <td className="p-4 text-right font-mono text-money">{run.jobs_with_company}</td>
                </tr>
              ))}
              {(!history || history.length === 0) && (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-dim">No runs yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Live Notifications */}
      {notifications.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <span className="mono-label text-signal">Live Feed</span>
            <span className="flex-1 divider-gradient" />
          </div>
          <div className="space-y-2">
            {notifications.slice(0, 5).map((n, i) => (
              <div
                key={`${n.timestamp}-${i}`}
                className={`glass-card rounded-lg p-4 animate-slide-up ${n.type === "new_jobs" ? "signal-edge" : n.type === "error" ? "border-[var(--danger)]/30" : ""}`}
              >
                <div className="flex items-center gap-3">
                  <span className={`w-2 h-2 rounded-full ${n.type === "new_jobs" ? "bg-signal" : n.type === "error" ? "bg-[var(--danger)]" : "bg-dim"}`} />
                  <span className="font-medium text-foreground">{n.title}</span>
                  <span className="text-dim text-sm">{n.message}</span>
                  <span className="ml-auto font-mono text-xs text-faint">{formatTimeAgo(n.timestamp)}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="p-4 rounded-lg bg-[var(--surface-2)]/50 border border-border">
      <div className="mono-label mb-1">{label}</div>
      <div className="font-mono text-lg text-foreground">{value}</div>
    </div>
  );
}

function SearchCard({
  search,
  onToggleScheduled,
  onDelete,
}: {
  search: SavedSearch;
  onToggleScheduled: (scheduled: boolean) => void;
  onDelete: () => void;
}) {
  return (
    <div className={`glass-card rounded-lg p-5 ${search.is_scheduled ? "signal-edge" : ""}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="font-medium text-foreground">{search.name || "Unnamed Search"}</h3>
            {search.is_scheduled && <span className="badge-primary px-2 py-0.5 rounded text-[10px]">SCHEDULED</span>}
          </div>
          <div className="flex flex-wrap gap-1.5 mb-3">
            {search.keywords.map((kw) => (
              <span key={kw} className="chip">{kw}</span>
            ))}
          </div>
          <div className="flex items-center gap-4 font-mono text-xs text-dim">
            <span>{search.max_pages || 5} pages</span>
            <span>Runs: {search.run_count}</span>
            {search.last_run_at && <span>Last: {formatTimeAgo(search.last_run_at)}</span>}
            {search.last_new_jobs > 0 && <span className="text-signal">+{search.last_new_jobs} new</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onToggleScheduled(!search.is_scheduled)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              search.is_scheduled ? "bg-signal text-[var(--signal-ink)]" : "btn-ghost"
            }`}
          >
            {search.is_scheduled ? "Active" : "Paused"}
          </button>
          <button
            onClick={onDelete}
            className="p-2 rounded-md text-faint hover:text-[var(--danger)] hover:bg-[var(--danger)]/10 transition-all"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const diffMs = Date.now() - date.getTime();
  const m = Math.floor(diffMs / 60000);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);

  if (m < 0) return `in ${Math.abs(m)}m`;
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  if (h < 24) return `${h}h ago`;
  if (d < 7) return `${d}d ago`;
  return date.toLocaleDateString();
}
