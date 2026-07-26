"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { aiApi } from "@/lib/api";

export function ProfileSection() {
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [skillInput, setSkillInput] = useState("");

  const { data: profile, isLoading } = useQuery({ queryKey: ["profile"], queryFn: aiApi.getProfile });
  const { data: aiStatus } = useQuery({ queryKey: ["ai-status"], queryFn: aiApi.getStatus });

  const saveMutation = useMutation({
    mutationFn: () => aiApi.saveProfile({ name, service_description: description, skills }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });

  useEffect(() => {
    if (profile) {
      setName(profile.name || "");
      setDescription(profile.service_description || "");
      setSkills(profile.skills || []);
    }
  }, [profile]);

  const addSkill = () => {
    const v = skillInput.trim();
    if (v && !skills.includes(v)) { setSkills([...skills, v]); setSkillInput(""); }
  };
  const removeSkill = (s: string) => setSkills(skills.filter((x) => x !== s));

  if (isLoading) {
    return <div className="flex items-center justify-center py-24"><Spinner /></div>;
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <span className="mono-label">Operator</span>
        <h2 className="font-display text-3xl text-foreground mt-1 leading-none">Your Profile</h2>
        <p className="text-sm text-dim mt-2">Describe what you do — the AI turns it into search keywords and proposals.</p>
      </div>

      {/* AI status */}
      <AiStatusBar configured={aiStatus?.configured} model={aiStatus?.model} />

      {/* Form */}
      <div className="glass-card rounded-xl p-6 space-y-5">
        <Field label="Your Name">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe"
                 className="w-full h-11 px-4 rounded-md floating-input text-sm text-foreground focus-ring" />
        </Field>

        <Field label="What services do you offer?" hint="Be specific about stack and specialisations for sharper keywords.">
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={5}
            placeholder="e.g. Full-stack dev — Python/FastAPI backends, Next.js frontends, web scraping, AI integrations…"
            className="w-full px-4 py-3 rounded-md floating-input text-sm text-foreground focus-ring resize-none leading-relaxed" />
        </Field>

        <Field label="Your Skills">
          <div className="flex gap-2 mb-3">
            <input value={skillInput} onChange={(e) => setSkillInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addSkill())}
              placeholder="add a skill…"
              className="flex-1 h-10 px-4 rounded-md floating-input font-mono text-sm text-foreground focus-ring" />
            <button onClick={addSkill} className="btn-ghost h-10 px-4 rounded-md text-sm font-medium">Add</button>
          </div>
          {skills.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {skills.map((s) => (
                <span key={s} className="chip animate-scale-in">
                  {s}
                  <button onClick={() => removeSkill(s)} className="text-faint hover:text-signal transition-colors">
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </span>
              ))}
            </div>
          )}
        </Field>

        <button onClick={() => saveMutation.mutate()} disabled={!description.trim() || saveMutation.isPending}
          className="w-full h-11 rounded-md btn-primary font-medium disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm">
          {saveMutation.isPending ? <><Spinner /> Generating keywords…</>
            : saveMutation.isSuccess ? <><CheckIcon /> Saved</>
            : <><SparkIcon /> Save & generate keywords</>}
        </button>
      </div>

      {/* Keywords */}
      {profile?.generated_keywords && profile.generated_keywords.length > 0 && (
        <div className="glass-card rounded-xl p-6 animate-fade-in">
          <div className="flex items-center gap-3 mb-4">
            <span className="mono-label text-signal">Generated Keywords</span>
            <span className="text-faint font-mono text-[11px]">use these on the Signal tab</span>
            <span className="flex-1 divider-gradient" />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {profile.generated_keywords.map((kw) => (
              <span key={kw} className="chip !border-[var(--signal)]/30 !text-signal">{kw}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AiStatusBar({ configured, model }: { configured?: boolean; model?: string }) {
  if (configured === undefined) return null;
  if (configured) {
    return (
      <div className="flex items-center gap-3 px-4 py-3 rounded-lg badge-success">
        <span className="status-dot connected" />
        <div className="text-sm">
          <span className="font-medium">AI online</span>
          <span className="font-mono text-xs text-dim ml-2">{model}</span>
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-3 px-4 py-3 rounded-lg border border-[var(--money)]/30 bg-[var(--money)]/8">
      <span className="status-dot pending mt-1.5" />
      <div className="text-sm">
        <p className="font-medium text-money">AI offline — running on fallbacks</p>
        <p className="text-xs text-dim mt-1 leading-relaxed">
          Set <code className="px-1 py-0.5 rounded bg-[var(--surface-2)] font-mono text-[11px] text-foreground">GROQ_API_KEY</code> in
          {" "}<code className="px-1 py-0.5 rounded bg-[var(--surface-2)] font-mono text-[11px] text-foreground">backend/.env</code>.
          {" "}Free key at <a href="https://console.groq.com" target="_blank" rel="noopener noreferrer" className="text-signal hover:underline">console.groq.com</a>.
        </p>
      </div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mono-label block mb-2">{label}</label>
      {children}
      {hint && <p className="text-xs text-faint mt-1.5">{hint}</p>}
    </div>
  );
}

function Spinner() {
  return (
    <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  );
}
const CheckIcon = () => (<svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>);
const SparkIcon = () => (<svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>);
