"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sessionApi } from "@/lib/api";

interface SessionStatus {
  connected: boolean;
  message: string;
  last_connected: string | null;
  needs_refresh?: boolean;
  cookies_count?: number;
}

interface ConnectionStatusProps {
  status?: SessionStatus;
}

export function ConnectionStatus({ status }: ConnectionStatusProps) {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const [connectionState, setConnectionState] = useState<"idle" | "connecting" | "waiting" | "saving">("idle");
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [panelPos, setPanelPos] = useState<{ top: number; right: number } | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setPanelPos({
        top: rect.bottom + 8,
        right: window.innerWidth - rect.right,
      });
    }
  }, [isOpen]);

  const connectMutation = useMutation({
    mutationFn: sessionApi.connect,
    onSuccess: () => {
      setConnectionState("waiting");
    },
    onError: () => {
      setConnectionState("idle");
    },
  });

  const saveMutation = useMutation({
    mutationFn: sessionApi.save,
    onSuccess: () => {
      setConnectionState("idle");
      setIsOpen(false);
      queryClient.invalidateQueries({ queryKey: ["session-status"] });
    },
    onError: () => {
      setConnectionState("idle");
    },
  });

  const cancelMutation = useMutation({
    mutationFn: sessionApi.cancel,
    onSuccess: () => {
      setConnectionState("idle");
    },
  });

  const handleConnect = () => {
    setConnectionState("connecting");
    connectMutation.mutate();
  };

  const handleSave = () => {
    setConnectionState("saving");
    saveMutation.mutate();
  };

  const handleCancel = () => {
    cancelMutation.mutate();
  };

  const isConnected = status?.connected && !status?.needs_refresh;

  return (
    <div className="relative">
      {/* Status Button */}
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/30 border border-border/50 hover:bg-muted/50 transition-all"
      >
        <span className={`status-dot ${isConnected ? 'connected' : status?.needs_refresh ? 'pending' : 'disconnected'}`} />
        <span className="text-sm font-medium">
          {isConnected ? 'Connected' : status?.needs_refresh ? 'Refresh Needed' : 'Disconnected'}
        </span>
        <svg
          className={`w-4 h-4 text-muted-foreground transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown Panel - Portal escape to avoid clipping by header backdrop-filter */}
      {isOpen && mounted && panelPos && createPortal(
        <>
          <div className="fixed inset-0 z-[100]" onClick={() => setIsOpen(false)} />
          <div
            className="fixed w-80 z-[101] glass-card rounded-xl p-4 animate-scale-in"
            style={{ top: `${panelPos.top}px`, right: `${panelPos.right}px` }}
          >
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-md flex items-center justify-center border border-border"
                   style={{ backgroundColor: isConnected ? "color-mix(in oklch, var(--signal) 12%, transparent)" : "color-mix(in oklch, var(--danger) 12%, transparent)" }}>
                <svg className="w-5 h-5" style={{ color: isConnected ? "var(--signal)" : "var(--danger)" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.14 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Upwork Connection</h3>
                <p className="text-xs text-muted-foreground">{status?.message || 'No status available'}</p>
              </div>
            </div>

            {/* Last Connected */}
            {status?.last_connected && (
              <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-muted/30 mb-4">
                <span className="text-xs text-muted-foreground">Last connected</span>
                <span className="text-xs font-medium text-foreground">
                  {new Date(status.last_connected).toLocaleString()}
                </span>
              </div>
            )}

            {/* Connection States */}
            {connectionState === "idle" && (
              <button
                onClick={handleConnect}
                className="w-full h-10 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition-all hover:opacity-90"
                style={{
                  background: "var(--signal)",
                  color: "var(--signal-ink)",
                  border: "1px solid var(--signal)",
                }}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <span>{isConnected ? 'Refresh Session' : 'Connect to Upwork'}</span>
              </button>
            )}

            {connectionState === "connecting" && (
              <div className="flex items-center justify-center gap-2 py-3 text-muted-foreground">
                <Spinner />
                <span className="text-sm">Opening browser...</span>
              </div>
            )}

            {connectionState === "waiting" && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 py-2 px-3 rounded-md border border-[var(--money)]/30 bg-[var(--money)]/10">
                  <svg className="w-4 h-4 text-money flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-xs text-money">
                    Complete Cloudflare and login in the browser window, then click Save.
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleSave}
                    className="flex-1 h-10 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition-all hover:opacity-90"
                    style={{ background: "var(--signal)", color: "var(--signal-ink)" }}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Save Session</span>
                  </button>
                  <button
                    onClick={handleCancel}
                    className="h-10 px-4 rounded-lg text-sm font-medium transition-colors border border-border text-muted-foreground hover:text-foreground hover:bg-muted/30"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {connectionState === "saving" && (
              <div className="flex items-center justify-center gap-2 py-3 text-muted-foreground">
                <Spinner />
                <span className="text-sm">Saving session...</span>
              </div>
            )}

            {/* Help text */}
            <p className="text-[11px] text-muted-foreground mt-4 leading-relaxed">
              Connect your Upwork session to enable job scraping. The browser will open for you to complete Cloudflare verification.
            </p>
          </div>
        </>,
        document.body
      )}
    </div>
  );
}

function Spinner() {
  return (
    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  );
}
