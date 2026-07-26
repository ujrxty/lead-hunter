"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  settingsApi,
  getApiBaseUrl,
  setApiBaseUrl,
  type SettingInfo,
} from "@/lib/api";

/**
 * Settings pane: manage API keys + backend URL from the UI so users never
 * touch .env. Backend URL lives in localStorage; API keys live in the DB
 * (see AppSetting model + /api/settings routes).
 */
export function SettingsSection() {
  const qc = useQueryClient();

  // Local override for the frontend → backend URL
  const [apiUrl, setApiUrlState] = useState<string>("");
  const [apiUrlSaved, setApiUrlSaved] = useState(false);

  useEffect(() => {
    setApiUrlState(getApiBaseUrl());
  }, []);

  const settingsQ = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.getAll,
  });

  const testGroq = useMutation({ mutationFn: settingsApi.testGroq });

  const handleSaveApiUrl = () => {
    setApiBaseUrl(apiUrl);
    setApiUrlSaved(true);
    setTimeout(() => setApiUrlSaved(false), 1800);
    // Bust every cached query since the backend URL just changed
    qc.invalidateQueries();
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <span className="mono-label">Configuration</span>
        <h2 className="font-display text-3xl text-foreground mt-1 leading-none">Settings</h2>
        <p className="text-sm text-dim mt-2">
          API keys and endpoints — all managed here, no <code className="font-mono text-signal">.env</code> editing.
        </p>
      </div>

      {/* Frontend → Backend URL */}
      <SettingsCard
        title="Backend API URL"
        description="Where the frontend sends requests. Change this if you run the backend on a different host or port."
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={apiUrl}
            onChange={(e) => setApiUrlState(e.target.value)}
            placeholder="http://localhost:8500/api"
            className="flex-1 h-11 px-4 rounded-md floating-input font-mono text-sm focus-ring"
          />
          <button
            onClick={handleSaveApiUrl}
            className="h-11 px-5 rounded-md text-sm font-semibold transition-all hover:opacity-90"
            style={{ background: "var(--signal)", color: "var(--signal-ink)" }}
          >
            {apiUrlSaved ? "Saved" : "Apply"}
          </button>
        </div>
        <p className="mt-2 font-mono text-[11px] text-faint">
          Stored in browser localStorage. Currently active: <span className="text-signal">{getApiBaseUrl()}</span>
        </p>
      </SettingsCard>

      {/* Groq / AI settings */}
      {settingsQ.isLoading ? (
        <div className="h-40 skeleton-shimmer rounded-lg" />
      ) : settingsQ.data ? (
        <>
          <SettingsCard
            title="Groq API Key"
            description={
              <>
                Required for AI features (keyword generation, proposals, lead scoring).
                Get a free key at{" "}
                <a href="https://console.groq.com" target="_blank" rel="noopener noreferrer" className="text-signal hover:underline">
                  console.groq.com
                </a>
                .
              </>
            }
          >
            <SecretField
              settingKey="groq_api_key"
              info={settingsQ.data.groq_api_key}
              placeholder="gsk_..."
              onChanged={() => qc.invalidateQueries({ queryKey: ["settings"] })}
            />

            <div className="flex items-center gap-3 mt-3">
              <button
                onClick={() => testGroq.mutate()}
                disabled={testGroq.isPending || !settingsQ.data.groq_api_key.is_set}
                className="btn-ghost h-9 px-4 rounded-md text-xs font-medium flex items-center gap-2 disabled:opacity-40"
              >
                {testGroq.isPending ? "Testing…" : "Test connection"}
              </button>
              {testGroq.data && (
                <span
                  className={`font-mono text-xs ${testGroq.data.ok ? "text-signal" : "text-[var(--danger)]"}`}
                >
                  {testGroq.data.ok
                    ? `✓ Working — model: ${testGroq.data.model}`
                    : `✗ ${testGroq.data.error}`}
                </span>
              )}
            </div>
          </SettingsCard>

          <SettingsCard
            title="Groq Model"
            description={
              <>
                Model name to use. Default is <code className="font-mono text-signal">llama-3.3-70b-versatile</code>.
                Check{" "}
                <a href="https://console.groq.com/docs/models" target="_blank" rel="noopener noreferrer" className="text-signal hover:underline">
                  Groq&apos;s model list
                </a>{" "}
                for options.
              </>
            }
          >
            <PlainField
              settingKey="groq_model"
              info={settingsQ.data.groq_model}
              placeholder="llama-3.3-70b-versatile"
              onChanged={() => qc.invalidateQueries({ queryKey: ["settings"] })}
            />
          </SettingsCard>

          <SettingsCard
            title="Scraper Headless Mode"
            description="Run Chrome invisibly. Off-screen non-headless is more reliable against Cloudflare. Set to 'false' if scrapes return 0 jobs."
          >
            <PlainField
              settingKey="scraper_headless"
              info={settingsQ.data.scraper_headless}
              placeholder="false"
              onChanged={() => qc.invalidateQueries({ queryKey: ["settings"] })}
            />
          </SettingsCard>
        </>
      ) : (
        <div className="glass-card rounded-lg p-6 text-sm text-[var(--danger)]">
          Could not reach the backend at <span className="font-mono">{getApiBaseUrl()}</span>. Check the URL above.
        </div>
      )}
    </div>
  );
}

// ============================================================
// Sub-components
// ============================================================

function SettingsCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="glass-card rounded-lg p-6">
      <h3 className="text-[15px] font-semibold text-foreground">{title}</h3>
      {description && <p className="text-xs text-dim mt-1 mb-4 leading-relaxed">{description}</p>}
      {!description && <div className="mb-4" />}
      {children}
    </div>
  );
}

function SourceBadge({ source }: { source: "db" | "env" | "unset" }) {
  const styles = {
    db: { c: "var(--signal)", label: "UI" },
    env: { c: "var(--money)", label: ".env" },
    unset: { c: "var(--text-faint)", label: "unset" },
  } as const;
  const s = styles[source];
  return (
    <span
      className="font-mono text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider"
      style={{
        color: s.c,
        backgroundColor: `color-mix(in oklch, ${s.c} 12%, transparent)`,
        border: `1px solid color-mix(in oklch, ${s.c} 30%, transparent)`,
      }}
    >
      {s.label}
    </span>
  );
}

function SecretField({
  settingKey,
  info,
  placeholder,
  onChanged,
}: {
  settingKey: string;
  info: SettingInfo;
  placeholder: string;
  onChanged: () => void;
}) {
  const [value, setValue] = useState("");
  const [saved, setSaved] = useState(false);
  const [revealed, setRevealed] = useState(false);

  const save = useMutation({
    mutationFn: () => settingsApi.set(settingKey, value),
    onSuccess: () => {
      setValue("");
      setSaved(true);
      setTimeout(() => setSaved(false), 1800);
      onChanged();
    },
  });
  const clear = useMutation({
    mutationFn: () => settingsApi.clear(settingKey),
    onSuccess: onChanged,
  });

  return (
    <div className="space-y-2">
      {info.is_set && (
        <div className="flex items-center justify-between p-2.5 rounded-md bg-[var(--surface-2)] border border-border">
          <div className="flex items-center gap-2 min-w-0">
            <SourceBadge source={info.source} />
            <span className="font-mono text-xs text-dim truncate">{info.value}</span>
          </div>
          <button
            onClick={() => clear.mutate()}
            disabled={clear.isPending}
            className="btn-ghost h-7 px-2.5 rounded text-[11px] font-medium"
          >
            Clear
          </button>
        </div>
      )}

      <div className="flex gap-2">
        <div className="flex-1 relative">
          <input
            type={revealed ? "text" : "password"}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={info.is_set ? "Enter new value to replace" : placeholder}
            className="w-full h-11 pl-4 pr-11 rounded-md floating-input font-mono text-sm focus-ring"
          />
          <button
            type="button"
            onClick={() => setRevealed((r) => !r)}
            className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7 rounded flex items-center justify-center text-faint hover:text-signal"
            title={revealed ? "Hide" : "Reveal"}
          >
            {revealed ? "🙈" : "👁"}
          </button>
        </div>
        <button
          onClick={() => save.mutate()}
          disabled={!value.trim() || save.isPending}
          className="h-11 px-5 rounded-md text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-40"
          style={{ background: "var(--signal)", color: "var(--signal-ink)" }}
        >
          {save.isPending ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
      </div>
    </div>
  );
}

function PlainField({
  settingKey,
  info,
  placeholder,
  onChanged,
}: {
  settingKey: string;
  info: SettingInfo;
  placeholder: string;
  onChanged: () => void;
}) {
  const [value, setValue] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (info.value) setValue(info.value);
  }, [info.value]);

  const save = useMutation({
    mutationFn: () => settingsApi.set(settingKey, value),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 1800);
      onChanged();
    },
  });
  const clear = useMutation({
    mutationFn: () => settingsApi.clear(settingKey),
    onSuccess: () => {
      setValue("");
      onChanged();
    },
  });

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <SourceBadge source={info.source} />
        <span className="font-mono text-[11px] text-faint">
          {info.is_set ? "currently active" : "not set — using default"}
        </span>
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          className="flex-1 h-11 px-4 rounded-md floating-input font-mono text-sm focus-ring"
        />
        <button
          onClick={() => save.mutate()}
          disabled={!value.trim() || save.isPending}
          className="h-11 px-5 rounded-md text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-40"
          style={{ background: "var(--signal)", color: "var(--signal-ink)" }}
        >
          {save.isPending ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
        {info.source === "db" && (
          <button
            onClick={() => clear.mutate()}
            disabled={clear.isPending}
            className="btn-ghost h-11 px-4 rounded-md text-sm font-medium"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
